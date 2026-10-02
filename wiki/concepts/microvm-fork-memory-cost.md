---
title: "MicroVM Fork 的内存代价模型"
aliases: [dirty page fork cost, fork-to-first-use latency, 脏内存 fork 代价, 增量快照代价模型]
created: 2026-10-02
updated: 2026-10-02
sources: [2026-gensee-agentenv-microvm-fork]
---

# MicroVM Fork 的内存代价模型

## 一句话定义

把一个运行中的 microVM "fork" 成多个独立子实例时，真正决定端到端延迟的不是"要不要懒加载"，而是源 VM 自上次快照以来产生的**脏内存量**——"追踪哪些页变了"（dirty tracking）便宜且可以懒做，但"让子实例稳定看到这些变化后的字节"（发布/materialize）通常必须在子实例可用之前同步完成，这部分代价随脏内存量线性增长。

## 为什么对我们重要

Agent RL 训练天然需要"从一个预热好的环境分支出多个并行 rollout"，fork 延迟直接决定了这种分支操作的吞吐上限和调度粒度。如果我们的沙箱平台考虑用类似 Firecracker 的 microVM fork/快照机制做这件事，不能只看厂商给出的单一延迟数字（往往只覆盖窄边界），而要建立"延迟如何随脏内存量/进程数增长"的代价模型，才能回答"agent 跑多久该强制 fork 一次""能不能并发 fork 出多少子实例"这类调度策略问题 [[2026-gensee-agentenv-microvm-fork]]。

## 核心机制 / 主要变体

- **追踪脏页 ≠ 发布脏页内容**：脏页 bitmap/range-list 只回答"哪些地址变了"；子实例要读到这些地址上稳定、不再变化的字节，需要在源 VM 继续运行并再次修改之后，有一份对子实例独立可见的拷贝——这一发布动作在哪个时间点、用什么方式完成，才是不同 fork 架构的真正分歧点 [[2026-gensee-agentenv-microvm-fork]]。
- **AgentENV 路线：fork 返回前同步发布**——暂停源 VM → 用 `process_vm_readv` 从源 Firecracker 进程同步读出被标记为脏的内存范围 → 写入一个新的不可变 OverlayBD 层（`mem_overlaybd/overlaybd.commit`）→ 通过 `ublk` 暴露给子实例只读访问、`MAP_PRIVATE` 映射、按需缺页。capture（脏页同步拷贝进层）发生在 fork 端点返回之前；restore（子实例把层内容读进自己的地址空间）才是懒加载的 [[2026-gensee-agentenv-microvm-fork]]。
- **TClone 路线：直接 CoW 共享，发布推迟到之后**——不把源进程的常驻页同步拷进文件，而是让子进程的页表直接引用源进程的物理页（类比 Linux `fork()` 的匿名内存 CoW 语义），子实例可以立刻可用，序列化/持久化留到之后再做。代价是子实例在"重建 Linux 进程树"（基于 CRIU）这件事上要为每个进程、VMA、文件描述符、namespace 单独做工作，延迟随 guest 进程数增长 [[2026-gensee-agentenv-microvm-fork]]。
- **两条路线互为镜像，不存在全面占优的一方**：microVM-below-kernel 架构（AgentENV）把 guest 进程树隐藏在 guest 内核内存里，host 侧不需要逐进程重建，所以延迟几乎不随进程数增长，但脏内存必须同步发布；容器级 CoW 架构（TClone）把脏内存的发布推迟到之后，但要在 host 侧重建完整进程树，延迟随进程数增长。选型要看 agent workload 的形状偏向"多进程、少脏内存"还是"少进程、多脏内存" [[2026-gensee-agentenv-microvm-fork]]。
- **已有的"懒加载恢复"和"同步发布脏页"并不矛盾，分别解决不同问题**：Firecracker 原生的 `MAP_PRIVATE` 文件支持的快照恢复确实可以懒加载旧快照里已有的字节，但这个机制回答的是"旧字节怎么进子实例"，不回答"最新脏字节怎么进入这份不可变镜像"——AgentENV 的"direct-OverlayBD"路径同时用到了这两种机制，是复合而非单一懒加载系统 [[2026-gensee-agentenv-microvm-fork]]。

## 工程要点与数字

- **AgentENV 实测（同一台主机，5 次全新 fork 取中位数）**：1GiB guest，fork-to-first-use 延迟从 0 脏内存的 360ms 增长到 512MiB 脏内存的 642ms；4GiB guest 段从 512MiB 的 715ms 增长到 2GiB 的 1.75s；拟合 `延迟 ≈ 381.6ms + 0.6728ms × 脏内存(MiB)`，R²=0.996 [[2026-gensee-agentenv-microvm-fork]]。
- **延迟去向**：fork API 返回耗时几乎与总延迟同斜率增长（capture 阶段占主要增量），API 返回到子实例首次成功执行命令之间稳定在约 80ms（不随脏内存量显著变化）[[2026-gensee-agentenv-microvm-fork]]。
- **TClone 对照（十进程配置，同样 0→2GiB 脏内存）**：本地可用延迟从 531ms 增长到 897ms，拟合斜率 0.177ms/MiB，约为 AgentENV 4GiB-guest 段斜率的四分之一；2GiB 时子进程 RSS≈2GiB 但 PSS 仅约一半，佐证其直接映射源进程常驻页而非提前私有拷贝 [[2026-gensee-agentenv-microvm-fork]]。
- **"<100ms" 类宣传数字的成立条件**：AgentENV 官方宣传的"增量快照 <100ms"衡量的是比"fork-to-first-use"更窄的内部操作边界（具体未披露是哪一段 API），且更接近脏内存量较小时的情况；一旦脏内存量上升（典型于长时间运行后的 agent 沙箱），外部可感知延迟会按上述线性公式明显增长。两个数字不矛盾，但如果把窄边界的"<100ms"直接当作"任意状态下 fork 一个 agent 沙箱的代价"来做容量规划，会系统性低估 [[2026-gensee-agentenv-microvm-fork]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源；本文作者所属机构 Gensee AI 自身是 TClone 的开发方，与 AgentENV 存在竞品关系，解读对比结论时需考虑这层潜在立场，但文中数字本身方法描述完整，见 [[2026-gensee-agentenv-microvm-fork]] 局限与疑点）

## 开放问题

- 同一暂停点并发 fork 出多个子实例时，新建的不可变内存层是否被多个子实例共享、是否会与 [[microvm-snapshot-uniqueness]] 讨论的克隆唯一性问题产生交叉，原文未测试这一场景 [[2026-gensee-agentenv-microvm-fork]]。
- "heavy disk modification"场景下的磁盘侧延迟曲线未被独立测量，只有架构层面"直接封存已有可写层"的解释，没有对应数字 [[2026-gensee-agentenv-microvm-fork]]。
- fork API 返回到子实例首次可用之间稳定的约 80ms 具体花在哪（vCPU 启动、guest 内核初始化、首次缺页轮次）未展开 [[2026-gensee-agentenv-microvm-fork]]。
- 这条代价模型是否适用于我们自己的硬件/内核版本/workload 特征，需要在自己的平台上独立测量截距和斜率，不能直接套用本文数字。

## 相关概念

[[snapshot-layering]]、[[firecracker]]、[[microvm-sandbox]]、[[microvm-snapshot-uniqueness]]

## 相关来源

- [[2026-gensee-agentenv-microvm-fork]] — 第三方对 AgentENV fork 机制的代码级拆解与同主机实测，给出脏内存量与 fork-to-first-use 延迟的线性代价模型，并与 TClone 的直接 CoW 路线做对照
