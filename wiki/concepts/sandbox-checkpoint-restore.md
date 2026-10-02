---
title: "Agent 沙箱 Checkpoint/Restore 路线"
aliases: [C/R, checkpoint/restore, 沙箱快照恢复, semantics-aware checkpointing, 语义感知快照, agent-OS semantic gap, change-based checkpoint]
created: 2026-10-02
updated: 2026-10-02
sources: [2604.28138]
---

# Agent 沙箱 Checkpoint/Restore 路线

## 一句话定义

Agent 沙箱的 checkpoint/restore（C/R）要同时满足三个互相拉扯的目标——恢复正确性（必须覆盖文件系统+进程态，不能只存对话历史）、低暴露开销（不能拖慢 agent 关键路径）、高密度下可扩展（不能让 checkpoint 流量压垮共享的宿主机 I/O）——现有工作沿两条不同的轴线逼近这三个目标:**捕获时机**（要不要为这个 turn 做 checkpoint）和**捕获粒度**（checkpoint 本身存多少、存得多便宜）。

## 为什么对我们重要

这是研究方向里"沙箱与执行环境基础设施"和"训练系统 rollout 效率"的交叉点：故障容错、spot 抢占迁移、tree-based RL rollout 分支、安全回滚这四个场景都要求沙箱平台能快速存取状态，但全量 C/R（CRIU、Firecracker 快照）在高密度部署下开销不可接受。如果我们要在自己的平台上支持"RL rollout 分支复用状态"或"agent 自己调用 rollback"这类能力，C/R 的时机/粒度设计直接决定了能不能同时做到正确、便宜、扛得住密度。

## 核心机制 / 主要变体

- **应用层/框架层恢复（最便宜，不正确）**：只存对话历史或工作区文件（Claude Code rewind、LangGraph 持久化），丢失进程态、后台服务、已安装依赖等 OS 副作用。实测 Chat-only 在 Terminal-Bench 上恢复正确率只有 8–13%，Chat+FS（加文件系统）28–48%——取决于 benchmark 本身对运行态的依赖程度（SWE-bench 主要看最终 patch，可以到 100%）[[2604.28138]]。
- **OS/VM 层全量 C/R（正确，不便宜）**：每个 turn 都做完整的文件系统+进程快照（CRIU+ZFS、Firecracker snapshot）。正确性 100%，但高密度下被 I/O 带宽和进程 dump 开销压垮：100 沙箱/128 核主机下 checkpoint 到达速率中位数 17 req/s；64 并发 1GB 进程 dump 需 47s；64/96 密度下相对无故障执行慢 3.06×/3.78×，比直接 restart 还差 [[2604.28138]]。
- **路线一：语义驱动的捕获时机（Crab，[[2604.28138]]）**——不改变"一次 checkpoint 存多少"，而是决定"这个 turn 到底要不要 checkpoint"。用 eBPF（文件系统：syscall tracepoint）+ cgroup/soft-dirty 页追踪（进程/内存）在 turn 边界上做**净变化**检测，忽略 fork 短命子进程、同 turn 内创建又删除的临时文件等瞬时效果；观测到 >75% 的 agent turn 不产生任何 recovery-relevant 状态变化，据此把 checkpoint 流量砍掉最多 87%。checkpoint 工作异步派发、与 LLM 推理等待窗口重叠，host 级反应式调度（是否已暴露在关键路径上）处理高密度下的资源争用。代价是需要侵入式的内核级观测（eBPF），且后端仍是传统的 CRIU dump（本身仍是百毫秒到近秒级的慢操作，只是被跳过或藏起来了）[[2604.28138]]。
- **路线二：增量式的捕获粒度（DeltaBox，[[2605.22781]]，**issue #113，目前只读过摘要，未精读，以下为初步判断，待确认**）**——不判断"要不要 checkpoint"，而是让"每次 checkpoint 本身"足够便宜：提出 OS 级抽象 DeltaState，DeltaFS 把文件状态组织成分层（类似 [[snapshot-layering]] 但面向可写层而非一次性快照树），checkpoint 时冻结当前可写层并插入新层，文件更新退化为 CoW，rollback 退化为切换层；DeltaCR 用增量 dump + 直接从冻结的模板进程 fork() 来跳过传统恢复流程。摘要称 checkpoint ~14ms、rollback ~5ms（SWE-bench + RL micro-benchmark）。如果这个数字成立，意味着 DeltaBox 可能是"每个 turn 都 checkpoint 但代价很低"，和 Crab"大部分 turn 直接跳过 checkpoint"是两种不冲突、理论上可叠加的策略——但具体 DeltaBox 是否也做了类似的语义判断（跳过无效 turn），摘要没有说明，需要精读 #113 后确认。

## 工程要点与数字

- 三个正确性档位的量化对比（Terminal-Bench，确定性回放）：Chat-only 6%、Chat+FS 48%、FullCkpt/Crab/Restart 均 100% [[2604.28138]]。
- Crab 的 Inspector 准确率（2,063 个人工标注 turn）：进程变化检测 100% 准确、零 FP/FN；文件系统变化检测 98.3% 准确、2.3% FPR、**零 FNR**——唯一真正危险的错误类型（漏报）为零 [[2604.28138]]。
- Crab 端到端开销：16–96 沙箱/主机密度下始终在无故障执行的 0–1.9% 以内；组件开销 Coordinator 每 turn 几十微秒（<0.02%）、Inspector 中位数 31–72ms（p95<200ms）、checkpoint 延迟双峰分布（文件系统 20–100ms / 进程 700–1000ms）[[2604.28138]]。
- Crab 在 RL tree-rollout 场景实测 rollout token 减少 40.0–64.2%（分支数 1–5）[[2604.28138]]；DeltaBox 摘要未给出对应的 RL token 节省数字，只给了 checkpoint/rollback 绝对延迟。

## 争议与矛盾

（暂无真正的结论冲突；Crab 与 DeltaBox 是两条正交的技术路线，不是互相反驳的关系——但目前只精读了 Crab 一篇，DeltaBox 侧的细节需要 #113 精读后补全才能确认"正交"这个判断是否站得住）

## 开放问题

- **捕获时机 vs 捕获粒度能否叠加**：Crab 的"跳过无效 turn"判断 + DeltaBox 的"让有效 turn 的 checkpoint 更便宜"是否可以组合成一个系统？两者的核心机制（eBPF 净变化检测 vs 分层 CoW+fork）看起来不冲突，但需要验证是否有工程上的互斥点（比如 DeltaBox 的 fork() 模板进程假设和 Crab 的 agent-in-sandbox fast-forward 机制是否兼容）。
- **DeltaBox 是否也面临 agent–OS 语义鸿沟**：如果 DeltaBox 对每个 turn 都做增量 checkpoint（不做语义判断），那么在 Crab 论文量化的"60.4% 工具调用是语义不透明的 shell 命令"场景下，DeltaBox 的增量 dump 开销是否会因为频繁但微小的变化而被摊薄到可忽略，还是仍然累积可观开销？取决于 DeltaFS/DeltaCR 增量机制的最小粒度，需要精读 #113 确认。
- **与 [[microvm-snapshot-uniqueness]] 的交互**：无论是 Crab 的 CRIU fork（投机执行场景）还是 DeltaBox 的"直接从冻结模板进程 fork()"，都在恢复/克隆路径上产生新实例——这类操作是否会重新触发 PRNG 种子/UUID/TLS 会话重复的"意外 Sybil"问题，两篇论文都未讨论。
- **eBPF/内核级观测在非 runc/VM 后端（gVisor、Kata 等用户态内核）上的可行性**：Crab 的 Inspector 依赖 syscall tracepoint 可见性，这类强隔离沙箱后端往往会拦截或重写 syscall，是否需要改造方案未知。

## 相关概念

[[snapshot-layering]]、[[microvm-snapshot-uniqueness]]、[[agentic-rollout-preemption]]、[[sandbox-density-overcommit]]

## 相关来源

- [[2604.28138]] — Crab：eBPF 语义感知 C/R，决定"要不要 checkpoint"，跳过 75–87% 无效 turn，端到端开销 <1.9%
- [[2605.22781]] — DeltaBox（摘要级，#113 待精读）：增量式 DeltaFS/DeltaCR，决定"checkpoint 本身多便宜"，声称 14ms/5ms
