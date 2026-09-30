---
title: "沙箱高密度资源超卖"
aliases: [sandbox density, high-density sandbox execution, container overcommit, sub-NUMA partitioning, latency-sensitive execution class, high-density resource management, CPU/memory overcommit, QoS-aware CPU scheduling, 内存共享与回收, core scheduling]
created: 2026-09-26
updated: 2026-09-30
sources: [2609.19969, 2609.22978, 2507.20534]
---

# 沙箱高密度资源超卖

## 一句话定义

利用 agent 沙箱"CPU 稀疏、常年等待模型下一步动作"的特点做资源超卖：在单物理节点上通过硬件级 NUMA 分区绑定 worker VM、并用两层 CPU QoS（SCHED_IDLE + core scheduling）区分延迟敏感/非延迟敏感任务的调度优先级，同时用内存共享/回收机制解决超卖带来的内存膨胀，在提升并发沙箱密度的同时避免高密度超卖污染时间敏感评测结果 [[2609.19969]] [[2609.22978]]。

## 为什么对我们重要

这是研究方向"沙箱与执行环境基础设施：密度、超卖、隔离"的核心命题——沙箱平台的单位成本很大程度上由"每节点能撑多少并发沙箱"决定，超卖密度直接等于我们单位算力能承接的并发 agent 数量。但纯粹堆密度会让吞吐类评测结果失真（后台批量负载干扰延迟敏感任务），DeepSeek 给出的是"密度"和"评测可信度"两个目标同时满足的具体机制组合，而不是单纯的超卖比调优或理论方案，可以直接作为我们自己超卖策略设计的对照基准 [[2609.19969]] [[2609.22978]]。

## 核心机制 / 主要变体

- **超卖的前提观测**：约 90% 的容器和 microVM 沙箱平均 CPU 使用率不超过请求容量的 5%，因为 agent 在等模型生成下一步动作时 CPU 基本空闲，这是超卖成立的物理基础 [[2609.22978]]。
- **sub-NUMA 分区**：在节点级使用硬件支持的 sub-NUMA 分区，把每个 worker VM 绑定到一个独立的 NUMA domain；容器运行在这些 worker VM 内，其 CPU 和内存分配被限制在该 VM 的本地 NUMA 资源范围内。这一设置在"激进内存超卖"和"Linux 内核锁竞争"之间取得平衡，同时把内存压力和运行时故障局部化到单个 NUMA domain 内，不扩散到整节点 [[2609.19969]]。
- **内存问题的两个来源（microVM 尤其严重）**：(1) 镜像数据经虚拟块设备读取时，host 和 guest 各缓存一份，造成跨边界重复缓存；(2) guest 内空闲页默认不会主动还给 host。由于沙箱生存期长（p99 超 3 小时）、请求内存常超实际需求，guest 内部缺乏回收压力，这些问题被长生命周期放大 [[2609.22978]]，详见 [[microvm-sandbox]]。
- **virtio-pmem + DAX**：把文件访问直接映射到 host 页而不拷入 guest RAM，让多个 co-located microVM 共享同一份 host 页缓存，从根上消除重复缓存问题；代价是冷访问需要同步缺页处理（不像 virtio-blk 能享受 guest 侧 readahead 和批量 I/O），且 guest 要为整个 pmem 地址范围分配 `struct page` 元数据（128GB pmem 设备占 2GB guest RAM）[[2609.22978]]。
- **DAMON + virtio-balloon free-page reporting**：对不适合走 pmem 的可写盘，用 DAMON（Linux 采样式内存访问监测框架）识别超过年龄阈值未被访问的冷页并主动回收，回收后的零散页被 buddy allocator 聚合成高阶块，满足 free-page reporting 默认要求的 2MiB（order-9）粒度门槛，再由 virtio-balloon 上报给 host、host 用 `madvise(MADV_DONTNEED)` 释放 [[2609.22978]]。
- **延迟敏感（LS）/ Best-Effort（BE）两层 CPU QoS**：高密度部署会通过后台负载干扰时间敏感的评测。DSec 因此引入 LS 执行类：对非 LS/BE 任务应用 `SCHED_IDLE` 把调度优先级压到最低（只在 LS 无事可做时才抢 CPU）；但光靠调度优先级防不住同一物理核内 SMT 兄弟线程的干扰，于是叠加 Linux core scheduling（`prctl(PR_SCHED_CORE)` 按 QoS class 分组，禁止不相关 BE 任务跑在 LS 任务的兄弟硬件线程上），从而消除超线程间的干扰 [[2609.19969]] [[2609.22978]]。

## 工程要点与数字

- V4.1-Flash 训练场景下，在可比工作负载配置下，sub-NUMA 分区优化把单物理节点支持的并发存活容器数从约 **1,000** 提升到 **2,500+**（以端到端可测退化出现前为界）[[2609.19969]]。
- 内存消融（Figure 12，4 种 Firecracker 配置对照）：virtio-pmem+DAX 单独把峰值 host 内存降 **40.2%**，但把瞬时峰值 CPU 利用率从 26.5% 拉到 **41.4%**（冷访问同步缺页所致）；DAMON+balloon FPR 单独不改变峰值但把**时间积分**内存消耗降 **21.2%**、无显著 CPU 开销；两者叠加内存消耗最低。作者建议 CPU 受限场景可以只开 FPR、保留 virtio-blk [[2609.22978]]。
- CPU QoS 消融（Figure 13，chess 延迟敏感任务 + 10%–50% BE 负载对照）：无保护基线在 50% BE 负载下每步延迟膨胀 **45.2%**；单独 `SCHED_IDLE` 只改善到 41.8%（改善幅度仅 3.4pp，因为 SMT 兄弟线程仍会争抢共享执行资源）；叠加 core scheduling 把膨胀压到 **17.3%**，且改善幅度随 BE 负载增大而增大 [[2609.22978]]。
- 残余干扰来源：turbo 频率因高负载多核而降频、LLC/内存带宽争用——作者认为这部分残余延迟已可接受，**没有**再上内存带宽隔离机制 [[2609.22978]]。
- 生产密度参照：稳定运行 3,200 容器 / 800 microVM 每节点（demonstrated operating point，非硬上限）[[2609.22978]]，详见 [[microvm-sandbox]]。
- **同类团队对标（F 对标）**：Kimi K2 对其 SWE agentic 数据合成用的沙箱基础设施只有一句话披露——"由 Kubernetes 支撑可扩展性与安全性，支持 1 万+ 并发沙箱实例，性能稳定"，是**集群总并发数**而非节点密度，且没有配套的单节点容量、隔离机制、内存/CPU 超卖策略、失败恢复设计等任何工程细节 [[2507.20534]]。与 DeepSeek 的 DSec 论文（独立成文、给出 sub-NUMA 分区+内存超卖+CPU QoS 的完整消融数字）相比，披露深度差距悬殊——头条并发数（1 万+ vs 千级/节点）不可直接比较量级，因为统计口径（集群 vs 单节点）本身不同。
- Agent 交互过程中沙箱经常在等待 LLM 生成下一步动作，CPU 使用天然稀疏，适合超卖；但内存足迹、guest page cache、host page cache、可写状态可能在 CPU 空闲后仍长期占用，因此高密度超卖下内存共享与回收和 CPU 调度同样重要 [[2609.22978]]。

## 争议与矛盾

- 两份材料给出的"单节点密度"数字口径不同：sub-NUMA 分区 A/B 对比得到的"1,000→2,500+"是同一负载配置下优化前后的对比，而"单节点最多 800 microVM 或 3,200 容器"是生产环境里不同 sandbox 后端（microVM vs 容器）各自的通用上限——两者不能直接比较，不构成真正的结论冲突，但并列阅读时容易误判为矛盾数据，故在此明确标注差异来源 [[2609.19969]] [[2609.22978]]。

## 开放问题

- sub-NUMA 分区在什么规模的节点（NUMA domain 数、每 domain 核心数）上验证过 2,500+ 的数字，是否能线性外推到更大规格的节点，论文未展开。
- LS 执行类的判定标准（哪些任务算"延迟敏感"）由谁在什么时机设置，机制细节未披露。
- virtio-pmem 引入的 CPU 开销上升（26.5%→41.4%）在什么规模/负载下会反过来成为瓶颈，论文没有给出临界点分析。
- core scheduling 之外，内存带宽/LLC 隔离是否值得投入，DSec 判断"已可接受"但没有量化不同 BE 负载强度下 LLC 争用对 LS 任务的具体贡献占比。
- Kimi K2 的"1 万+ 并发沙箱"是否有量化的密度/隔离工程支撑，还是纯粹的 K8s 默认调度 + 硬件堆量，公开材料完全没有回答，需要靠社区分析或后续论文补充 [[2507.20534]]。

## 相关概念

[[agentic-rollout-preemption]]、[[microvm-sandbox]]、[[sandbox-image-distribution]]

## 相关来源

- [[2609.19969]] — 给出 sub-NUMA 分区带来的具体密度提升数字（1,000→2,500+）与 LS 执行类机制
- [[2609.22978]] — DSec：virtio-pmem+DAMON 内存优化、SCHED_IDLE+core scheduling CPU QoS 的设计与量化消融
- [[2507.20534]] — 对照组：同类团队（Kimi）对沙箱基础设施的披露仅一句话（K8s、1 万+ 并发），无节点密度/隔离/超卖工程细节，与 DSec 形成披露深度的直接对比
