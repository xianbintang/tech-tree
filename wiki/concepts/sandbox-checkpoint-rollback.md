---
title: "Agent 沙箱 Checkpoint/Rollback（增量态与模板 fork）"
aliases: [sandbox C/R, checkpoint/rollback, DeltaState, DeltaFS, DeltaCR, 增量快照, 沙箱回滚, change-based checkpoint]
created: 2026-10-02
updated: 2026-10-02
sources: [2605.22781]
---

# Agent 沙箱 Checkpoint/Rollback（增量态与模板 fork）

## 一句话定义

把 agent 沙箱的"文件系统态 + 进程态"耦合地做高频 checkpoint/rollback，核心思路不是整份复制状态，而是只存相邻两次 checkpoint 之间的**增量**：文件态靠动态可重配置的 overlay 层栈（写入变 copy-on-write、回滚变层切换）,进程态靠 CRIU dump + 从冻结模板进程 `fork()`（恢复只拷页表、不拷物理内存），把 checkpoint/restore 做到毫秒级 [[2605.22781]]。

## 为什么对我们重要

这直接对应研究方向里"沙箱与执行环境基础设施"和"agentic RL rollout 效率"的交叉点：test-time 树搜索（MCTS/BoN）需要频繁回溯到任意历史状态，RL 训练每个 step 要从同一热启动状态并发 fork 出 $k$ 个 rollout——这两类负载都要求 checkpoint/rollback 在**关键路径**上做到毫秒级，而不是像传统容器/VM 快照那样把它当一次性离线操作。DeltaBox 给出的是已验证的 OS 级机制和量化数字（10.83ms checkpoint 隐藏在推理窗口里、1.86ms restore），直接回答"我们的沙箱平台要不要支持任意历史点回滚、要支持到多快"这个产品/架构问题 [[2605.22781]]。

## 核心机制 / 主要变体

- **文件态：动态 overlay 层栈（DeltaFS）**——给 overlayfs 内核模块加自定义 ioctl，在不 umount 的前提下运行时重配置层栈：checkpoint 时把当前 upper 层改名降级为新 lower、插入全新空 upper，后续写入自动 copy-on-write；rollback 变成层移除，时间复杂度 $O(1)$。配合 XFS reflink，copy-up 先共享物理块、只有被覆写的 4KB 块才真正分配，写放大与文件大小无关（只与实际改动量相关）[[2605.22781]]。
- **进程态：CRIU dump + 模板 fork（DeltaCR）**——每次 checkpoint 同时做两件事：异步 CRIU dump（存 tmpfs，慢路径兜底）+ agent 在静止点自己 `fork()` 一次，子进程冻结注册为"模板"。restore 命中模板时直接 `fork(template)` 产生新进程（只复制页表，不拷内存），毫秒级；模板被淘汰则退化到 CRIU lazy-pages 慢路径（秒级，但不影响正确性）[[2605.22781]]。
- **一致性靠同一静止瞬间**：CRIU dump 和 DeltaFS ioctl 都在同一个 SIGSTOP 静止点观察 agent 状态，保证每个 checkpoint 都是一致的 (文件系统, 内存) 配对；dump 失败时主动回滚文件系统 ioctl，不留半态 [[2605.22781]]。
- **与 VM 级快照的本质区别**：VM 级快照（[[firecracker]] 原生快照、E2B、CubeSandbox）捕获的是整个 VM（所有进程、内核态），粒度无法做到"同一 VM 内多条独立搜索分支分别回滚"；DeltaBox 走进程级 fork + 文件层切换，天然支持一个 VM 内承载多个独立可 checkpoint 的 agent，共享内核和只读基础层，互不影响 [[2605.22781]]。
- **与 DSec 的"抢占后重连"是不同问题**：[[agentic-rollout-preemption]] 页描述的 DSec pause/resume 解决的是"GPU 抢占后怎么不丢状态地重连同一个身份"；DeltaBox 瞄准的是"主动回滚到任意历史 checkpoint"（MCTS 回溯、BoN 分支探索），DeltaBox 论文（Table 1/§2.3）明确批评 DSec 只能靠 WAL 回放已缓存输出、不支持任意回滚（"no arbitrary rollback"）——两者是互补而非竞争关系 [[2605.22781]] [[2609.22978]]。
- **网络 I/O 不在回滚范围内**：LLM SDK 的长连接/线程池被隔离到独立的 Network Proxy Daemon 进程中（排除在 CRIU dump/模板 fork 之外），agent 本体只通过 FIFO 与之通信；但凡 agent 动作产生了真实的外部网络副作用（调用了有副作用的 API），rollback 无法撤销——这是设计上的显式取舍，不是遗漏 [[2605.22781]]。

## 工程要点与数字

- 端到端：checkpoint ≈10.83ms（主要是模板 fork 8.87ms，异步 CRIU dump 隐藏在 LLM 推理窗口里、不计入 agent 感知延迟，故 agent 侧感知阻塞为 0ms）；restore 快路径 ≈1.86ms，慢路径（CRIU lazy-pages）≈9.29ms [[2605.22781]]。
- 相对基线的量级：restore 比 E2B（VM 级增量快照）快 ~480×，比 Firecracker 增量内存快照+dm-snapshot 快 ~1800×，比"复制目录+命令重放"快 ~15000×（SWE-bench MCTS 加权平均）[[2605.22781]]。
- RL fan-out 场景下的 GPU 占用率：$N{=}16/64$ 并发 rollout 时，DeltaBox 维持 95–97% 的 GPU 同步训练占用率，对比 CubeSandbox 77–80%、E2B 29–36%——sandbox fan-out 延迟直接换算成 GPU 空闲时间的量化模型可直接复用：$(T_{gen}+T_{train})/(\text{sandbox}+T_{gen}+T_{train})$ [[2605.22781]]。
- 原生内核 `fork()` 本身的开销：$N{=}1$ 时 p50 0.57ms，$N{=}64$ 时 p50 5.47ms/p99 14.74ms，子进程继承页表级 CoW,不是高并发 fan-out 场景下的瓶颈来源 [[2605.22781]]。
- Reachability-aware 垃圾回收（只保留搜索树还可能选中的节点镜像）比"保留所有 checkpoint"减少末态存储 46–63%（9 条 SWE-bench 轨迹）[[2605.22781]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源；与 [[2609.22978]] 的关系是"解决不同问题"而非观点冲突，见上文「与 DSec 的关系」）

## 开放问题

- **RL fan-out 场景下的克隆唯一性问题未被讨论**：从同一个冻结模板连续 `fork()` 出 $N$ 个子进程做并发 rollout,正是 [[microvm-snapshot-uniqueness]] 页描述的"多个克隆实例共享完全相同内存状态"场景（PRNG 种子等本该唯一的值可能重复）。DeltaBox 论文全文未提及对 fork 出的子进程做任何重新播种/身份重置处理,这是论文未覆盖、但实际落地这套机制时需要自己补上的风险点。
- 网络 I/O 回滚被显式排除在设计范围外,如果 agent 任务里网络副作用（如调用计费 API、发消息）是回滚语义里必须覆盖的部分，DeltaBox 这套机制不能直接满足；需要额外的"幂等重放"或"外部副作用隔离"机制配合。
- 评测环境单一（单台四路服务器），没有多节点/跨机场景下 StateManager（host 侧 Sandbox Controller 的全局快照索引树）的扩展性数据。
- DeltaCR 的协调逻辑（~1200 行 Python，编排 CRIU/模板池/async-warm/NPD）在更高并发下是否会受 Python 自身调度/GIL 影响引入新的尾延迟，论文未做专门压力测试。

## 相关概念

[[microvm-sandbox]]、[[firecracker]]、[[snapshot-layering]]、[[microvm-snapshot-uniqueness]]、[[agentic-rollout-preemption]]、[[rollout-efficiency]]

## 相关来源

- [[2605.22781]] — DeltaBox（锚点论文）：overlay 动态分层（DeltaFS）+ CRIU dump/模板 fork（DeltaCR）实现毫秒级 agent 沙箱 checkpoint/rollback，给出与 E2B/Firecracker/CubeSandbox/DSec 的详细对比数字
