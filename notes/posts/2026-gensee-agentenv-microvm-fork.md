---
title: "Inside Kimi K3's AgentENV: Can It Really Fork in 100 ms?"
type: post
id: "2026-gensee-agentenv-microvm-fork"
source_url: https://www.gensee.ai/blogs/inside-agentenv-dirty-memory-microvm-fork.html
authors: [Gensee AI team]
affiliations: [Gensee AI]
published: 2026-08-03
created: 2026-10-02
tags: [microvm-sandbox, firecracker, snapshot-restore, fork, agentic-rl, kimi-k3]
concepts: [microvm-fork-memory-cost, snapshot-layering, firecracker, microvm-sandbox, microvm-snapshot-uniqueness]
rating: 4
issue: 115
---

# Inside Kimi K3's AgentENV: Can It Really Fork in 100 ms?

> 第三方对 AgentENV（Kimi K3 的 Firecracker microVM 沙箱层）fork 机制的拆解：当前实现在 fork 返回前要把脏页同步拷进新的不可变 OverlayBD 层，这部分代价随脏内存量线性增长（1GiB guest 下 0ms→512MiB 脏内存，耗时 360ms→642ms），与官方"增量快照 <100ms"的说法衡量的是不同边界，并不矛盾。

## 元信息

- 作者/机构：Gensee AI（博文作者未署名个人，机构为 Gensee AI；Gensee 自己做 TClone/os4agent，与 AgentENV 是竞品关系，读数字时需考虑这层动机）
- 发表：2026-08-03，个人/公司技术博客
- 链接：[原文](https://www.gensee.ai/blogs/inside-agentenv-dirty-memory-microvm-fork.html)
- 对比对象：AgentENV（[kvcache-ai/AgentENV](https://github.com/kvcache-ai/AgentENV)，随 Kimi K3 开源）vs. 作者自家的 TClone（基于 CRIU 重建 Linux 进程树的容器 fork 方案，[arXiv:2605.17320](https://arxiv.org/abs/2605.17320)，本知识库暂无该论文独立笔记）
- 背景补充：GitHub issue #98 已精读过 AgentENV 文档本身（综述性笔记），但该笔记目前只存在于未合并的 `batch/74-2` 分支（对应 PR 未合入 master），本篇笔记的写作分支上无法 `[[]]` 链接到它，详见下方「相关」与 PR 描述。

## 要解决的问题

AgentENV 随 Kimi K3 发布时给出一个很抓人眼球但边界模糊的数字：**"增量快照 <100ms，即使在大量磁盘修改之后"**。这类沙箱平台的 fork/快照速度直接决定了 agent RL 训练里"从一个预热好的环境分支出多个并行 rollout"的开销上限，值得深挖这个数字具体衡量的是哪一段操作、在什么条件下成立——这正是本篇笔记要核实的问题，也是 issue #115 指派的核心任务。

## 方法

作者先铺垫了理解 microVM fork 必须具备的几个虚拟化概念，再据此拆解 AgentENV 的实际 fork 路径：

### 关键背书概念

- **guest RAM 由 host 侧 VMM 托管**：guest 页要么是全新 VM 的匿名内存，要么是从快照恢复 VM 时映射到快照文件的页；
- **一份完整 Firecracker 快照 = vCPU/KVM/设备状态 + 内存内容 + 块设备状态三类协同产物**，guest 进程树本身不需要单独的 host 侧序列化（进程表、VMA、打开文件、调度器状态全部已经编码在 guest 内核内存里）——这正是 microVM fork 与基于 CRIU 的容器 fork 相比，开销不随 guest 进程数线性增长的根本原因；
- **"追踪脏页"和"发布脏页内容"是两件不同的事**：脏页 bitmap/range 只回答"哪些地址变了"，子实例要稳定读到这些地址的字节，还需要在源 VM 继续运行并再次修改之后，有一份对子实例稳定可见的拷贝——这个发布动作具体在哪一步完成，才是 fork 延迟的关键变量；
- **Firecracker 原生快照恢复可以是懒加载的**：用 `MAP_PRIVATE` 映射内存 backing file，vCPU 第一次触碰页时才从 host page cache 缺页取入，子实例写入时才产生私有匿名 CoW 页——但懒恢复只回答"快照里已有的旧字节怎么进子实例"，不回答"最新的脏字节怎么进入这份不可变快照镜像"。

### AgentENV 的实际 fork 路径（基于其 `direct-OverlayBD` 默认配置，追代码到 `sandbox.rs`）

```
源 Firecracker 进程的匿名内存
      ↓ process_vm_readv(选中的脏页范围)
新的不可变 OverlayBD 内存层（mem_overlaybd/overlaybd.commit）
      ↓ 叠加到父层之上（mem_image.json 描述层次关系）
共享的只读 ublk 设备
      ↓ MAP_PRIVATE
子 Firecracker 进程按需缺页读取（懒加载）
```

逐步拆解（原文 9 步，合并为关键节点）：暂停源 microVM → Firecracker 落盘 `vm_state.bin`（vCPU/KVM/设备状态）→ 向 Firecracker 查询相对父快照变化的脏内存范围 → 用 `process_vm_readv` 从源进程**同步读出**这些脏页字节 → 写入临时 OverlayBD commit 文件后 rename 密封为新的不可变层 → 通过 `ublk` 暴露这条叠加链给多个沙箱共享只读访问 → 启动子 Firecracker 进程，把该设备当文件内存后端 `MAP_PRIVATE` 映射、按需缺页 → 源 VM 恢复运行，子 VM 的写入各自产生私有 CoW 页，两者分叉。

**结论（作者称为 key distinction）**：AgentENV 不会把整份快照一次性拉进子实例（这部分确实懒加载），但它会在 fork 端点返回之前，把被选中的脏 guest 内存**同步**拷贝进一个新的不可变层——capture 成本随脏字节数增长，restore 成本才是推迟到缺页发生时。磁盘侧则不同：guest 磁盘写入本来就持续累积在一个可写 OverlayBD upper 层里，快照时只需要封存这个已有 upper 层、开一个新的，不需要重新发现/拷贝每个改动过的磁盘块——这也解释了为什么"大量磁盘修改后"快照仍能保持低延迟，但内存侧的脏页拷贝是另一套机制，不享受同样的"已有累积层直接封存"待遇。

### 实测方法

同一台主机上，对每个测试点取 5 次全新 fork 的中位数，测量**完整的 fork-to-first-use 延迟**（源 VM 暂停 → 状态/内存捕获 → rootfs/内存层发布 → 源 VM 恢复 → 子 VM 创建 → 子 VM 首次成功执行命令），而非 AgentENV 文档里更窄的"增量快照操作"本身。1GiB guest 测 0→512MiB 请求脏内存，4GiB guest 补测 512MiB→2GiB（512MiB 作为两段测试的桥接重叠点，两种 guest 规格在图上分开标注，不直接拼接比较）。

## 实验与结果

- **1GiB guest**：fork-to-first-use 中位延迟从 0 脏内存的 **360ms** 增长到 512MiB 脏内存的 **642ms**。
- **4GiB guest**：从 512MiB 脏内存的 **715ms** 增长到 2GiB 脏内存的 **1.75s**。
- **拟合曲线**（4GiB guest 段）：`AgentENV 完整首用延迟 ≈ 381.6ms + 0.6728ms × 脏内存(MiB)`，R² = 0.996——线性拟合质量很高，说明脏内存量确实是一等代价变量。
- **延迟去向拆解**：fork API 返回时间几乎与总延迟同斜率增长；从 API 返回到子实例首次成功执行命令之间的间隔，始终稳定在约 **80ms**（不随脏内存量显著变化）。换句话说，高脏内存场景下绝大部分新增延迟发生在 fork 端点返回**之前**（对应 `process_vm_readv` + 写 OverlayBD 层这一步），而不是子实例后续缺页恢复的过程。
- **与官方"<100ms"说法的关系（本篇笔记的核心核实点）**：作者明确指出这**不构成矛盾**——AgentENV 文档的 100ms 说法针对的是更窄的"增量快照操作"边界（很可能只对应内部 API 层面的快照/恢复调用本身），而本文测的是外部可观测的完整 fork-to-first-use（暂停、状态捕获、层发布、恢复、子实例启动、首次可用全部算入）。两者在回答不同的问题。**成立条件**：AgentENV 的 <100ms 更接近"脏内存量较小/接近零时的内部操作耗时"（1GiB guest 零脏内存时完整外部延迟已经是 360ms，内部窄口径数字应更低但原文未单独给出）；一旦脏内存量上升（典型 agent 任务长时间运行后 pack 的沙箱状态），外部可感知延迟会按上述线性公式明显增长，脏内存量是决定"<100ms 是否仍然成立"的第一变量，而不是磁盘修改量（"heavy disk modification" 这个限定词在作者的测试里没有单独验证，宣传语聚焦磁盘修改、但真正的瓶颈在内存）。
- **与 TClone（作者自家方案）的对照**（十进程配置，同样 0→2GiB 脏内存扩展测试）：TClone 的"本地可用"延迟从 **531ms** 增长到 **897ms**，拟合斜率 **0.177ms/MiB**——约为 AgentENV 4GiB-guest 段斜率（0.6728ms/MiB）的四分之一。内存记账显示 2GiB 场景下子进程 RSS ≈2GiB 但 PSS 只有约一半，shared-dirty 内存量与 payload 大小吻合，说明子进程确实在直接映射源进程的常驻页，而非提前分配一份独立 2GiB 私有拷贝。**但这不是无条件的胜利**：TClone 走的是"重建 Linux 进程树（基于 CRIU）"路线，延迟随 guest/workload 进程数增长（文中强调 AgentENV 在进程数增长时更平坦，因为进程状态编码在被 fork 隐藏的 guest 内存里，不需要 host 侧逐进程重建）——两者是在"进程数代价"和"脏内存代价"两个维度上的不同取舍，不存在在两个维度都更优的一方。

## 局限与疑点

- **利益冲突未被充分权衡**：作者所属 Gensee AI 自己做 TClone/os4agent，文章结论客观上有利于自家方案；文中数字本身方法描述清楚（同主机、5 次中位数、给出完整拟合），可信度不低，但对比框架（选哪个基线、哪个脏内存范围）由利益相关方设定，解读时要留意。
- **测试环境细节不全**：未说明具体硬件型号、Firecracker/AgentENV 版本号（只在文末引用了具体 commit `9cca6e9...`，但未明确说该 commit 是否就是测试时跑的版本）、host 内核版本，复现性弱于本知识库已精读的 DSec/Firecracker 等一手论文。
- **"heavy disk modification"场景未被独立测试**：作者只测了内存脏页量的影响，官方"<100ms"宣传语里的磁盘修改量这一维度，本文只给出了架构层面的解释（可写 upper 层直接封存），没有给出对应的磁盘侧延迟曲线数字，核实并不完整。
- **多子实例并发 fork 的场景未覆盖**：本文每次只测一个子实例，没有讨论"同一个暂停点并发 fork 出多个子实例"时，新建的不可变层是否被多个子实例共享、是否会触发 [[microvm-snapshot-uniqueness]] 讨论的克隆唯一性问题——这正是 issue #98（AgentENV 文档精读）此前列出的未解问题之一，本文没有回答。
- **"≈80ms 固定间隙"是否包含真实的首次缺页代价**：作者说这部分不随脏内存量变化，但没有展开这 80ms 内部具体花在哪（vCPU 启动、guest 内核初始化、首次缺页轮次？），缺页本身的尾延迟敏感性未被单独测量。

## 对我们的启发

1. **"<Nms" 宣传数字几乎总是窄边界，拿来做容量规划前必须先问"衡量的是哪一段"**：这是本篇笔记最直接的可执行结论——评估任何沙箱/快照厂商给出的延迟数字时，要先确认它是"内部 API 调用耗时"还是"外部可感知的端到端耗时"，以及是否排除了随负载特征（如脏内存量、进程数）线性增长的部分。如果我们自己的平台也要对外宣传快照/fork 延迟，应该同时给出两个边界的数字，并标注影响增长的第一变量。
2. **"脏内存量"是 microVM fork 延迟的一等变量，值得在我们自己的沙箱平台上建立类似的代价模型**：$延迟 \approx 常数 + 系数 \times 脏内存(MiB)$ 这种线性拟合方法本身可以直接复用——如果我们用 Firecracker/类似 microVM 做 agent 环境 fork，应该先测出自己平台上这条曲线的截距和斜率，再决定"允许 agent 累积多少脏内存后再 fork"这类调度策略的阈值。
3. **"进程数代价" vs "脏内存代价"是两种互斥的 fork 架构取舍，选型要看 agent workload 的形状**：如果我们的 agent 任务倾向于"跑很多进程、改少量内存"（如多进程构建/测试流水线），类似 TClone 的 CoW 容器路线可能更合适；如果倾向于"少量进程但长时间运行累积大量脏内存状态"（如长 session 的数据处理/训练辅助任务），AgentENV 这种 microVM-below-kernel 路线的进程数无关性更有优势。这是一个需要先画出自己 workload 的"进程数 × 脏内存量"分布,再做选型的具体 follow-up。
4. **分层快照的"直接封存已有 upper 层"技巧值得对标到我们自己的可写层设计**：AgentENV 磁盘侧"guest 写入持续累积在可写 upper 层，快照时直接封存开新层"与 [[snapshot-layering]] 已记录的 provenance-based 去重是同一类思路的磁盘实例,但本文额外指出它和内存侧的"同步发布脏页"机制代价结构完全不同——如果我们设计统一的快照系统，不能假设内存和磁盘用同一套"封存现有层"就能两头低延迟,需要分别建模。
5. Follow-up 建议（可转 issue）：
   - 待 #98（AgentENV 文档精读，分支 `batch/74-2`）合并后，补上本篇与 `notes/posts/agentenv-docs.md` 的双向链接,并核实其"开放问题"里关于 fork 唯一性的疑点是否被本文间接回应（本文未回应,仍开放）；
   - 如果我们计划用 Firecracker 做类似 fork 能力,应该直接实测自己硬件上的 `延迟 ≈ a + b × 脏内存MiB` 曲线,而不是直接采信本文或 AgentENV 官方任一方的数字（两者都有各自的方法论盲点和潜在立场）；
   - 调研 TClone（[arXiv:2605.17320](https://arxiv.org/abs/2605.17320)）论文原文,确认其 CoW 容器 fork 的"进程数代价"量化细节,判断是否值得作为我们"多进程 workload"场景的候选方案单独开一篇论文笔记。

## 相关

- 相关概念：[[microvm-fork-memory-cost]]、[[snapshot-layering]]、[[firecracker]]、[[microvm-sandbox]]、[[microvm-snapshot-uniqueness]]
- 相关笔记：issue #98 对 AgentENV 文档本身的精读笔记（计划路径 `notes/posts/agentenv-docs.md`）目前只存在于未合并的 `batch/74-2` 分支，本笔记暂不对它建立 `[[]]` 链接以避免引入断链；待该分支合并后应补建双向链接，并把本篇列入 [[microvm-sandbox]]、[[sandbox-image-distribution]] 等页的来源列表与 #98 笔记并列。
- 与母论文的关系：本文不是来自带 `parent` 的阅读清单条目，无直接母论文；但在机制上是 [[2609.22978]]（DSec）§6.1 `pack_diff`/§3.3 OverlayBD+ublk 方案的同源生态验证——AgentENV 与 DSec 共享同一段 `storage/overlaybd` 代码路径（见 #98 笔记综述），本文揪出的"fork 时同步发布脏页"细节,是对 DSec 论文里"microVM 完整快照/恢复代价更高"这一定性判断的一次具体量化补充。
