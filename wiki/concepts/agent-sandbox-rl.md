---
title: "agent-sandbox-rl"
aliases: [agent_sandbox_rl, SandboxFleet, k8s-agent-sandbox 批量编排, sandbox warm pool orchestration, SandboxWarmPool, SandboxClaim, 沙箱预热池编排]
created: 2026-10-02
updated: 2026-10-02
sources: [2026-k8s-agent-sandbox-rl]
---

# agent-sandbox-rl

## 一句话定义

`kubernetes-sigs/agent-sandbox`（v1beta1 `SandboxTemplate`/`SandboxWarmPool`/`SandboxClaim`/`Sandbox` CRD）之上的多集群批量编排 Python 包：把"镜像预热 → 按任务 claim 一个沙箱（拿到 hostname/endpoint）→ 释放 → 拆除"的完整生命周期封装成框架无关的通用 API，核心是四种预热池策略（`none`/`naive`/`sliding`/`pipelined`）、按并发预算做副本 sizing、RL 场景的 instant-claim 优化（`warm_per_task` + `colocate_replicas`）、实验性的沙箱复用（git-restore reset）[[2026-k8s-agent-sandbox-rl]]。

## 为什么对我们重要

这是目前知识库里**唯一一个开源、生产可读代码级别**的 agent 沙箱批量编排系统，直接对标我们自己的编排层设计：预热池 sizing 公式、RL vs 评测两种负载的差异化配置（`warm_per_task` vs 按并发预算）、沙箱复用的"reset + determinism canary"模式，都是可以逐条拿来对比甚至复用的具体工程方案，而不是论文里的抽象描述 [[2026-k8s-agent-sandbox-rl]]。它暴露的两个生产级 bug（控制器过量创建、run-id 标签被下游剥除）也是 CRD controller 批量编排场景下的通用教训。

## 核心机制 / 主要变体

- **生命周期**：`load_tasks → preflight → plan → [prepull] → start_warmpools → acquire* → release* → teardown`；claim 本身完全复用下层 `k8s-agent-sandbox` SDK（`create_sandbox`/`terminate`），只有 Template/WarmPool CRUD 和多集群客户端路由（"属性注入"：每个 `Cluster` 自建 `ApiClient`，塞进一个新建的 `SandboxClient` 实例，不 fork SDK）是新代码 [[2026-k8s-agent-sandbox-rl]]。
- **四种预热池策略**：`naive`（全量预热，footprint 最高，适合 image 集合能放进磁盘或 RL 配 `warm_per_task`）、`sliding`（滚动窗口，窗口按磁盘预算自动定）、`pipelined`（窗口化 + 预取下一窗口与当前窗口执行重叠，适合**拉取受限的 1:1 评测**，footprint ≤2 个窗口）、`none`（按需 size-1 池，适合小规模/调试）[[2026-k8s-agent-sandbox-rl]]。
- **选择逻辑（两个问题）**：预热集合放不放得下磁盘？拉取是不是瓶颈？评测场景（image 多、1:1）两者通常都成立 → `pipelined`；RL 场景（1 个 image 被 G 个 rollout 共享）用 `naive`/`sliding` + `warm_per_task`，**不能用 `pipelined`**——深副本会让预取窗口收缩，序列化任务（实测 wall 55s→97s）[[2026-k8s-agent-sandbox-rl]]。
- **默认 sizing（按并发预算分摊，非按任务数）**：$\text{replicas}_{image} = \text{clamp}(\text{round}(\text{MAX\_CONCURRENT} \times \text{tasks}_{image}/\text{tasks}_{total}), 1, \min(\text{tasks}_{image}, \text{MAX\_WARMPOOL\_SIZE}))$，优化目标是成本（给定吞吐下最少常驻副本）[[2026-k8s-agent-sandbox-rl]]。
- **RL 专用 instant-claim 开关（默认关闭，二者独立）**：`warm_per_task=True`（每任务一个预热副本，`min(tasks_image, max_warmpool_size)`）解决"claim 延迟尾部"（同 image 的第 2 个 rollout 不该排队等第 1 个）；`colocate_replicas=True`（软 pod affinity 把同池副本挤到一个节点，只有第一个副本真正拉镜像）解决"同池副本重复拉镜像"。两者只改善 claim 尾延迟，**不改善 batch wall-clock**（wall 已被 `max_concurrent` 卡住）[[2026-k8s-agent-sandbox-rl]]。
- **沙箱复用（recycling，实验性，`recycle=True`）**：正交于策略的修饰符——保留一个已 claim 的沙箱，在同 image 任务间做 `git reset --hard` + `clean -xdff` + 残留进程清理，**校验**回到 pristine SHA 且干净，任何偏差**隔离**（释放+重新 claim）而非冒险复用，因为"静默污染 reward"比"崩溃"更危险。靠持久 exec session（O(沙箱数) 而非 O(任务数) 的 exec 连接）规模化；信任前必须跑 `determinism_canary`（同任务跑两次验证输出逐位相同 + reset 干净）[[2026-k8s-agent-sandbox-rl]]。
- **多集群 placement**：`RoundRobin`/`LeastLoaded`/`CapacityWeighted`/`ImageAffinity`（按 image 路由到固定集群复用缓存层），默认 `ImageAffinity` 回退 `LeastLoaded`；跨集群连接性（cross-cluster learner 怎么连到沙箱）文档明确标注为调用方自己解决 [[2026-k8s-agent-sandbox-rl]]。
- **安全网**：熔断器（实时沙箱数超 `min(期望×overcommit_factor, max_live_sandboxes)` 就整体 teardown）+ reaper（按 `run_id` 标签扫残留资源，应对 SIGKILL/OOM/节点丢失这类 atexit 钩子catch不到的情形）[[2026-k8s-agent-sandbox-rl]]。

## 工程要点与数字

- Replica sizing 对照（100 任务/8 image 偏斜分布，`MAX_WARMPOOL_SIZE=32`）：naive 全预热基线恒 92 pod；按并发预算 sizing 在 `MAX_CONCURRENT=1/8/32/256` 下压到 **8/11/32/92** pod；sliding 窗口进一步压到 **1/5/8/8** [[2026-k8s-agent-sandbox-rl]]。
- 沙箱复用 vs 新鲜 claim（50 problems × 40 rollouts，无操作负载，`mc=100`）：复用在 wall-clock（**416s vs 944s**）、claim 数（**81 vs 1,987，24.5×**）、成功率（**100% vs 99.35%**）全面更优；评测场景（1:1）反过来，复用只省 claim 数 [[2026-k8s-agent-sandbox-rl]]。
- instant-claim 具体实测（10 problems × 8 rollouts，每条 15s，`naive` 策略）：claim 尾延迟 9s→6s，wall 基本不变；另一处文档（architecture.md）给出的是数量级相近但未标注测试条件的"示意性"数字（10s→3s），与前者口径不一致，可能是示意而非同一次实测 [[2026-k8s-agent-sandbox-rl]]。
- 控制器高并发 worker 建议值（默认偏保守）：`--sandbox-concurrent-workers` 100→1000，`--sandbox-claim-concurrent-workers` 50→1000，`--sandbox-template-concurrent-workers` 1→1000，`--sandbox-warm-pool-max-batch-size` 300→1000；`--sandbox-warm-pool-concurrent-workers` 的建议值**版本相关**（见下方 bug 修复前后对比）[[2026-k8s-agent-sandbox-rl]]。
- 所有数字来自作者在自己集群上的自测（Kubernetes SIG 贡献者，生产验证但非独立论文复现），样本量/重复次数/置信区间均未披露 [[2026-k8s-agent-sandbox-rl]]。

### 生产级 bug 两例（CRD controller 批量编排的通用教训）

- **#1215（控制器过量创建副本，2026-07-24 修复）**：500 个 WarmPool × 40 副本（目标 ~20,000）在调度容量不足时观测到 **~90,000–110,000 个 pod**（4.5–5.5× 超额）。根因不是"按 Ready 而非存在计数"的朴素误判，而是 create-delta 读取的 `activeSandboxes` 来自**落后于自己刚发出创建请求的 informer 缓存**，高并发 reconcile worker 在缓存追上之前反复"追加"创建（约 10× 超额创建）。修复：引入 ReplicaSet 式"expectations"追踪（记录预期创建数，观测到之前不再追加）+ terminating pod 计入目标 + 不可调度 pod 改"hold+退避"而非"删除重建"。修复前后实测（20 pools × 25 副本，冷镜像，workers=1000）：控制器 POST 数 **5,537→1,004**，峰值 pod **1,230→502**，全部就绪耗时 **+48s→+19s** [[2026-k8s-agent-sandbox-rl]]。
- **#1807/#1811（run-id 标签被下游 controller 剥除，2026-10-01 修复）**：Sandbox 控制器自 PR #894 起会剥掉 pod 上所有 `agents.x-k8s.io/*` 前缀标签（系统保留前缀），而 `agent-sandbox-rl` 的 run-id 标签恰好用这个前缀——结果熔断器 `live_owned_count()` 永远数出 0，`reap(run_id=...)` 的 pod 强删匹配不到任何目标。修复：给 pod 加非保留前缀的新标签 `agent-sandbox-rl/run-id`。验证：`live_owned_count()` 从 0 恢复到 3，reap 清理延迟 31s→0.1s。**代码审查标出但未解决的残留风险**：若 run B 复用 run A 拥有的模板（on-demand acquire 路径），B 的沙箱 pod 携带 A 的 run-id 标签，`reap(run_id=A)` 会误删 B 正在跑的 pod——这是模板归属和实际 claim 方未解耦导致的跨 run 可用性干扰，截至合并时仍未从根上解决 [[2026-k8s-agent-sandbox-rl]]。

## 争议与矛盾

（暂无跨来源分歧，仅一个来源；见上方"instant-claim 具体实测"条目里 README 与 architecture.md 两处数字口径不一致，已在该条目标注，不是结论性矛盾）

## 开放问题

- #1215 的修复只在 500 pools 规模内验证过（README 称"validated clean at 500 with 500 pools"），对我们可能需要的千级以上并发沙箱规模是否仍然成立未知 [[2026-k8s-agent-sandbox-rl]]。
- #1811 合并时明确留下"模板归属 vs 实际 claim 方"未解耦的跨 run 可用性风险，截至精读时未见后续修复 PR [[2026-k8s-agent-sandbox-rl]]。
- 沙箱复用只验证了 git 版本化、无操作（no-op）负载；真实 SWE-bench 任务下 reset 耗时、脚手架开销、env/config 层漂移（默认关闭检查）的实际风险未知 [[2026-k8s-agent-sandbox-rl]]。
- 跨集群连接性（cross-cluster learner 如何连到另一集群的沙箱）完全留给调用方，没有给出推荐方案，这对我们如果要做跨 region/跨集群编排是一个需要自己补的设计点 [[2026-k8s-agent-sandbox-rl]]。

## 相关概念

[[rollout-efficiency]]、[[sandbox-image-distribution]]、[[on-demand-image-loading]]、[[microvm-placement]]、[[agentic-rollout-preemption]]、[[sandbox-density-overcommit]]

## 相关来源

- [[2026-k8s-agent-sandbox-rl]] — 精读笔记，覆盖 README/design.md/architecture.md 三份文档，以及 #1215（控制器过量创建）、#1811（run-id 标签被剥除）两个生产 bug 的根因与修复
