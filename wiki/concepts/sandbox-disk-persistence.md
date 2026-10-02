---
title: "沙箱磁盘持久化：写时复制增量快照与分层块存储"
aliases: [disk persistence, incremental disk snapshot, copy-on-write disk snapshot, FIEMAP, NBD, Network Block Device, always-on persistence, 磁盘持久化, COW 磁盘快照]
created: 2026-10-02
updated: 2026-10-02
sources: [2026-ai-engineer-fork-to-fleet]
---

# 沙箱磁盘持久化：写时复制增量快照与分层块存储

## 一句话定义

区别于"内存/执行状态快照"（见 [[snapshot-layering]]、[[microvm-snapshot-uniqueness]]），这是专门针对 microVM **磁盘状态**持久化的工程模式：用支持 reflink 的写时复制文件系统（如 XFS）做近乎零延迟的可写副本，用 FIEMAP 等块级接口识别变更范围做增量快照（显式触发），或用 NBD 分层块缓存把磁盘持续异步写回对象存储（一直生效），使得 agent 在沙箱里积累的代码仓库、构建产物等有价值磁盘内容不随沙箱销毁而丢失 [[2026-ai-engineer-fork-to-fleet]]。

## 为什么对我们重要

我们的 agent 沙箱任务正在从"一次性函数调用"走向"长程、有状态、产出有价值磁盘内容"（写代码仓库、装依赖、生成文档）——这正是研究方向里"沙箱与执行环境基础设施：快照、冷启动"这一能力项的磁盘侧对应物。如果我们目前对"沙箱里的磁盘内容值不值得保留"没有系统设计，节点故障或抢占会直接损失已消耗的计算和用户工作，这是一个和内存/执行状态快照同等重要、但常被内存快照讨论盖过的独立维度。

## 核心机制 / 主要变体

- **触发方式的两种范式**：(1) 显式快照——harness 主动调用 Save API，返回一个快照 ID，适合"按任务节点/按轮次"地保存进度；(2) always-on 持久化——guest 看到的始终是一个块设备，所有写入自动异步落到持久层，harness 不需要显式调用任何接口 [[2026-ai-engineer-fork-to-fleet]]。
- **显式快照的写时复制实现**：从 base image 用 XFS 之类支持 reflink 的文件系统创建一个可写副本，初始状态与 base 共享所有数据块，近乎零延迟；之后对可写副本的每次写入才会把对应块私有化、脱离共享。调用快照时用 **FIEMAP**（Linux 文件扩展映射接口）取得哪些 extent（块范围）发生了变化，只打包上传这部分增量，而非整盘 [[2026-ai-engineer-fork-to-fleet]]。
- **快照 ID 与 lineage**：每次显式快照返回一个快照 ID；恢复时需要解析该 ID 对应的完整 lineage（一条由多层增量组成的链），逐层下载并应用到 base image 上，再用重建出的磁盘状态启动新 microVM——这与 [[snapshot-layering]] 讨论的内存快照树结构在"分层增量"这一设计原则上相同，但作用对象是磁盘块而非内存页。
- **异步确认与持久化的间隙**：Save API 可以在后台上传尚未完成前就先返回，用更快的调用延迟换取吞吐，但这意味着"快照已确认"（返回了快照 ID）和"快照数据已持久化、可供其它节点恢复"是两个不同的时间点——原始资料未说明这段间隙期间如何处理一致性或失败重试，是一个需要在落地时补齐的开放工程问题 [[2026-ai-engineer-fork-to-fleet]]。
- **guest 接入磁盘的两种方式**：共享文件夹式（类似网络盘挂载，每次文件系统操作都需要 host 服务，开销大）vs. 块设备式（guest 的文件系统和页缓存在 guest 内部处理大部分工作，只有真正需要访问底层块设备时才 exit 到宿主）。块设备式被认为是性能更优的默认选择 [[2026-ai-engineer-fork-to-fleet]]。
- **Always-on 持久化：NBD + 分层块缓存**：不选用 NFS（讲者认为性能较弱、且并非严格 POSIX 兼容，close-to-open 一致性模型容易给模型生成代码的行为带来意外),而是用 **NBD（Network Block Device）** 把磁盘包装成块设备接口；guest 侧写入先落到集群内缓存层,再异步写回 GCS/S3 等持久对象存储；guest 自始至终只看到一个标准块设备，拿到完整的标准文件系统语义和缓存行为 [[2026-ai-engineer-fork-to-fleet]]。
- **持久化带来的产品能力，不只是"不丢数据"**：(1) 周期性 checkpoint 支撑节点/集群故障后的跨节点重建，以及集群升级/节点 A-B 测试时的主动迁移；(2) 多日级长程任务（如多轮 agent "goal mode"）可以从检查点恢复而非从头重跑；(3) 支持"检查点 → 尝试 → 回退 → 再检查点"的分支式探索，为 harness 做 Monte Carlo tree search 式的多路径搜索提供执行substrate [[2026-ai-engineer-fork-to-fleet]]。

## 工程要点与数字

- 所有数字均为定性描述，**未给出可复现的基准测试**：reflink 写时复制初始拷贝"近乎零延迟"；增量快照方案据称能让 ChatGPT/Codex 规模下的频繁 checkpoint 保持经济可行，但未给出具体吞吐或成本对比数字 [[2026-ai-engineer-fork-to-fleet]]。
- 对比 [[2609.22978]]（DSec）§6.1 的 `pack_diff` 机制：DSec 同样是"把交互式沙箱状态做增量磁盘快照、固化成可复用环境"，但 DSec 论文完全没有提及 FIEMAP/XFS reflink 这类具体实现路径，也没有给出与本页讲座类似的块级增量快照工程细节——两者解决的问题高度相似，具体实现是否一致需要进一步对照 DSec 代码或更详细的技术文档才能确认。

## 争议与矛盾

（暂无跨来源数字冲突，仅一篇来源；与 [[2609.22978]] 的 `pack_diff` 机制是否共享同一类实现尚待确认，见下「开放问题」。）

## 开放问题

- Save API 后台异步上传与"已确认"响应之间的一致性缺口（期间节点崩溃、调用方如何感知真正落盘完成）未披露具体方案。
- 本页机制与 [[2609.22978]]（DSec）§6.1 的 `pack_diff` 增量磁盘快照是否是同一类实现（块级 diff vs. 文件级 diff、是否都基于 reflink/FIEMAP），两份资料互相都没有提及对方，需要读更详细的工程文档或源码才能确认。
- NBD 分层块缓存具体的缓存淘汰策略、写回延迟与一致性保证（guest 崩溃时缓存层未落盘的数据如何处理）未展开。
- 块级增量快照（本页）与内存快照树（[[snapshot-layering]]）是否在同一套存储后端上实现、能否共享分层/去重基础设施，两条资料线索都未说明。

## 相关概念

[[snapshot-layering]]、[[microvm-snapshot-uniqueness]]、[[microvm-placement]]、[[microvm-sandbox]]、[[sandbox-image-distribution]]

## 相关来源

- [[2026-ai-engineer-fork-to-fleet]] — 唯一来源：OpenAI 工程师讲座，给出 XFS reflink + FIEMAP 增量磁盘快照、NBD 分层块存储 always-on 持久化的设计思路，均为定性描述、无基准数字
