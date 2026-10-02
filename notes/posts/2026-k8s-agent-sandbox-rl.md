---
title: "agent-sandbox-rl: multi-cluster batch orchestration for SWE-bench-style RL on Kubernetes Agent Sandbox"
type: post
id: "2026-k8s-agent-sandbox-rl"
source_url: https://github.com/kubernetes-sigs/agent-sandbox/tree/main/examples/agent-sandbox-rl
authors: [kubernetes-sigs/agent-sandbox contributors]
affiliations: [Kubernetes SIG (agent-sandbox), Google]
published: 2026-09-20
created: 2026-10-02
tags: [sandbox-orchestration, agentic-rl, kubernetes, warm-pool, sandbox-recycling]
concepts: [agent-sandbox-rl, rollout-efficiency, sandbox-image-distribution, on-demand-image-loading, microvm-placement, agentic-rollout-preemption]
rating: 4
issue: 117
---

# agent-sandbox-rl: multi-cluster batch orchestration for SWE-bench-style RL on Kubernetes Agent Sandbox

> kubernetes-sigs/agent-sandbox 官方 example：把"预热池 → claim 一个沙箱 → 跑 → 释放 → 拆除"的 RL/评测批量生命周期封装成通用多集群 API，是我们编排层的直接对标基线。

## 元信息

- 机构/来源：`kubernetes-sigs/agent-sandbox` 仓库（Kubernetes SIG），example 包 `examples/agent-sandbox-rl`
- 发布：README/design.md/architecture.md 标注状态为"implemented"；仓库活跃 PR/issue 时间集中在 2026-07~2026-10
- 链接：[GitHub](https://github.com/kubernetes-sigs/agent-sandbox/tree/main/examples/agent-sandbox-rl) · [design.md](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/examples/agent-sandbox-rl/docs/design.md) · [architecture.md](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/examples/agent-sandbox-rl/docs/architecture.md)
- 对比基线：下层 SDK `k8s-agent-sandbox`（single-sandbox/single-cluster，无 CRUD/sizing/批量编排，被本包复用而非 fork）

## 要解决的问题

`k8s-agent-sandbox` Python SDK 只提供单沙箱、单集群的 claim 原语（`SandboxClient.create_sandbox(warmpool=...)`），没有 `SandboxTemplate`/`SandboxWarmPool` 的 CRUD、没有副本 sizing、没有 preflight、没有预拉取、也没有多集群概念——每个消费方（R2E-Gym 的 kubernetes-sandbox backend、tunix 的 `eval_deepswe.py` 等）都要重新实现这套批量编排逻辑。`agent-sandbox-rl` 把这套逻辑抽成一个独立 pip 包，一次实现、跨集群通用，可插入任意 RL 框架（R2E-Gym、tunix、TorchRL、SkyRL）。

## 方法

### 生命周期与分层

```
load_tasks ─▶ preflight ─▶ plan ─▶ [prepull] ─▶ start_warmpools ─▶ acquire* ─▶ release* ─▶ teardown
```

`SandboxFleet`/`AsyncSandboxFleet` 是顶层编排器，往下依次是 `sources`（任务从哪来）、`placement`（image→哪个集群）、`sizing`（每个 image 建多少副本）、`strategies`（预热池何时建好）、`preflight`/`prepull`，再到 `ClusterRegistry → Cluster(s) → Resources`（Template/WarmPool CRUD）+ 复用的 `k8s-agent-sandbox` SDK（claim/exec/terminate）。**只有 Template/WarmPool CRUD 和多集群客户端路由是新代码**；claim 生命周期完全复用上游 SDK，通过"属性注入"把每个 `Cluster` 自己的 `ApiClient`/`K8sHelper` 挂到一个新建的 `SandboxClient` 实例上（每集群一个 SDK 实例，不 fork SDK）。

### acquire 的实际路径（router-free）

```
fleet.acquire(task)
  → plan lookup: image → (cluster, warmpool)
  → SDK create_sandbox(warmpool, namespace, ready_timeout, labels)
      ├─ POST SandboxClaim CR → 绑定一个预热 pod
      ├─ 轮询 claim.status → 具体 Sandbox 名字
      └─ 轮询 Sandbox CR → status=Ready
  → 包装成 SandboxHandle（hostname/pod_name/pod_ip/endpoint/exec）
```

没有 SSH/登录环节：`exec` 直接走 Kubernetes pod-exec API（绕开 SDK 自带的 Sandbox Router），`endpoint(port)` 是沙箱的稳定 in-cluster DNS 名。**claim 不等于新建 pod**——claim 绑定的是池子里已经在跑的预热 pod，这正是"亚秒级 claim"而非"整个镜像拉取耗时"的来源；release 删除 claim 后，controller 回收/替换该 pod，下一个任务绑定的是池子里*另一个*副本。

### 预热池四种策略与如何选

| 策略 | 行为 | 内存/磁盘footprint | 适用 |
| --- | --- | --- | --- |
| `naive` | 一次性预热所有 image 的池，并行跑完，拆除 | 最高（全部同时常驻） | image 集合不大；RL（配合 `warm_per_task`） |
| `sliding` | 只保持一个滚动窗口的池常驻 | 受窗口大小限制（随 `max_concurrent` 自动定窗） | image 集合大、磁盘放不下 |
| `pipelined` | 类似 sliding，但**预取**下一窗口，和当前窗口的执行重叠 | 受限（≤2 个窗口，窗口减半把峰值压到 ≈ `max_concurrent`） | **拉取受限的 1:1 评测**（image 多、每个只跑 1 个任务） |
| `none` | 每个 image 临时建一个 size-1 池，跑完即拆 | 最低（每 image 冷启动） | 小规模/调试 |

选择逻辑是两个问题：(1) 预热集合能不能放进磁盘——放得下用 `naive` 最简单；放不下必须用窗口化策略（`sliding`/`pipelined`，窗口按 `avg_image_gb`/`node_ephemeral_gb`/`cluster_nodes` 算磁盘预算自动定）。(2) 拉取是不是瓶颈——1:1 评测场景拉取占主导，`pipelined` 把下一窗口的拉取和当前窗口的执行重叠；RL 场景（1 个 image 被 G 个 rollout 共享）要用 `naive`/`sliding` + `warm_per_task`，**不要用 `pipelined`**：per-image 深副本会让 pipelined 的预取窗口收缩，导致任务序列化（实测 wall 55s → 97s）。

### 副本 sizing 与 instant-claim（RL 专用两个开关）

默认 sizing 按并发预算分摊、不是按任务数：

$$\text{replicas}_{image} = \text{clamp}\left(\text{round}\left(\text{MAX\_CONCURRENT} \times \frac{\text{tasks}_{image}}{\text{tasks}_{total}}\right), 1, \min(\text{tasks}_{image}, \text{MAX\_WARMPOOL\_SIZE})\right)$$

这个默认模式优化的是**成本**（给定吞吐下最少的常驻副本）。RL 更关心**claim 延迟**（time-to-sandbox）——G 个 rollout 同时打同一个 problem image，第二个 rollout 不该排队等第一个。两个默认关闭的开关：
- `warm_per_task=True`：每个 image 的副本数 = `min(tasks_image, max_warmpool_size)`，一个任务一个预热副本。
- `template.colocate_replicas=True`：软 pod affinity 把同一池的副本尽量挤到同一节点，只有第一个副本真正拉镜像，其余靠节点 containerd 层缓存启动。

**这两个开关只改善 claim 延迟的尾部，不改善 batch wall-clock**（wall 本来就被 `max_concurrent` 卡住，默认 sizing 已经让它饱和）。README 给出的具体实测（10 problems × 8 rollouts，每条 15s）：`naive` 策略下 claim 尾延迟 9s → 6s，wall 基本不变。architecture.md 的"优化发现"一节另外举了一个数量级相近但不完全相同的说法——"claim tail（如 10s → 3s）"——未标注具体测试条件，与 README 的具体实测数字口径不一致，疑似一处是具体实验数字、一处是示意性数量级，这里不确定两者是否指同一次测量。

### 沙箱复用（recycling）——实验性，`recycle=True`

`warm_per_task` 给每个 rollout 一个全新沙箱；recycling 反过来**保留一个已 claim 的沙箱、在同 image 任务之间原地 reset**，使 claim 数随"问题数"而非"任务数"缩放（÷ 每 image 任务数）。是 `fleet.run(...)` 上的一个**正交修饰符**（不是策略值）：选定的 `strategy` 仍然管预热，`recycle` 只是把 task→sandbox 绑定换成"reset 复用"。

reset 实现（`GitRestoreReset`）：`git reset --hard` 到 pristine tag + `clean -xdff` + 扫掉残留进程/`/tmp`，然后**校验**仓库回到了 pristine SHA 且干净；任何偏差都会**隔离**该沙箱（释放 + 重新 claim），而不是冒险把污染状态带给下一个 rollout——作者的理由是 RL 场景下一个被污染的沙箱会**静默**偏置 reward，比直接崩溃更危险。默认只做 git 层检查（快），更贵的 `pip freeze` 环境检查和 git-config/hooks 检查是 opt-in。规模化靠**持久 exec session**（一个常驻 `bash` 流每沙箱一个，exec 成本是 O(沙箱数) 而非 O(任务数)）。

**信任前必须跑的校验**：`determinism_canary`——同一个带种子的任务在同一个复用沙箱里跑两次，断言输出逐位相同且 reset 后状态干净（`identical and reset_clean`）。

## 实验与结果

- **Replica sizing 对照表**（100 任务 / 8 image 偏斜分布，`MAX_WARMPOOL_SIZE=32`）：naive 全预热基线恒为 92 pod；按并发预算 sizing 在 `MAX_CONCURRENT=1/8/32/256` 下分别压到 **8 / 11 / 32 / 92** pod；sliding 窗口进一步压到 **1 / 5 / 8 / 8**。
- **沙箱复用 vs 新鲜 claim**（50 problems × 40 rollouts，无操作 payload，`mc=100`）：复用在 wall-clock（**416s vs 944s**）、claim 数（**81 vs 1,987，24.5×**）、成功率（**100% vs 99.35%**）三项都更优——常规方案的浅层 per-image 预热池在同 image 并发争抢下会饱和。评测场景（image 多、1:1）则反过来：复用只省 claim 数，仍应配 `pipelined` + 新鲜 claim。
- **Controller 高并发 worker 配置**（控制器默认偏保守）：`--sandbox-concurrent-workers` 100→建议 1000，`--sandbox-claim-concurrent-workers` 50→1000，`--sandbox-template-concurrent-workers` 1→1000，`--sandbox-warm-pool-max-batch-size` 300→1000；`--sandbox-warm-pool-concurrent-workers` 的建议值**随控制器版本变化**（见下）。
- **成本/吞吐数字均来自作者自测，论文式的独立第三方复现未见**——这是一个 example 包的 README/文档，不是经过同行评审的论文，数字的统计严谨度（样本量、重复次数、置信区间）均未披露。

## 局限与疑点

- **#1215：SandboxWarmPool 控制器过量创建副本（已修复，merged 2026-07-24）**。现象：500 个 WarmPool × 40 副本（目标 ~20,000）在调度容量不足时观测到 **~90,000–110,000 个 pod**（~4.5–5.5× 超额），约 65% 卡在 Pending，控制面过载。根因（作者 `tomergee` 用控制器日志定位）**不是**"按 Ready 而非存在计数"的朴素误判——create-delta 计算本身是对的（`desiredReplicas - len(activeSandboxes)`），但 `activeSandboxes` 读自 informer 缓存，**落后于自己刚发出的 create**；高并发 reconcile worker（`--sandbox-warm-pool-concurrent-workers` 默认值在触发规模下被设得很高）会在缓存追上之前反复"追加"创建，实测约 10× 超额创建（≥5,000 次 create 对应 500 的目标）。修复 PR #1266：给 warm-pool 创建加上 ReplicaSet 式的"expectations"追踪（记录预期创建数，观测到之前不再追加创建）+ terminating pod 计入目标 + 不可调度 pod 的"hold+退避"而非"删除重建"+ `WarmPoolNotProgressing`/`Progressing` 状态事件。修复前后实测（kops/GCE，20 pools × 25 副本，冷镜像，workers=1000）：控制器 POST 数 **5,537 → 1,004**（精确匹配 500 目标 + 2 次合理替换），峰值 pod **1,230 → 502**，全部就绪耗时 **+48s → +19s**。`agent-sandbox-rl` 这边的缓解措施（staged 创建 `warm_create_budget`、`--sandbox-warm-pool-concurrent-workers` 低并发建议）在 v0.5.4 之前只能"缓解"不能"消除"这个 bug。
- **#1807/#1811：run-id 标签在 pod 上被剥掉，熔断器和 reaper 失效（merged 2026-10-01，发布前一天）**。根因：自 PR #894 起，Sandbox 控制器会从 pod 上剥掉所有 `agents.x-k8s.io/*` 前缀的标签（系统保留前缀），而 `agent-sandbox-rl` 的 run-id 标签恰好用的是这个前缀——结果是熔断器的 `live_owned_count()` 永远数出 0（无法触发熔断保护），`reap(run_id=...)` 的 pod 强删也匹配不到任何 pod。修复：给 pod 加一个**非保留前缀**的新标签 `agent-sandbox-rl/run-id`（CRD 资源继续用旧的 `agents.x-k8s.io/asrl-run-id` 做归属判断）。kind 集群验证：`live_owned_count()` 从 0 恢复到正确值 3；`reap(run_id=...)` 的 pod 清理延迟从 31s 降到 0.1s。**代码审查中标出但未解决的残留风险**（PR 的安全审查标为 Moderate）：如果 run B 在"复用他人模板"（on-demand acquire 路径）下 claim 了 run A 拥有的模板，B 的沙箱 pod 携带的是 A 的 run-id 标签——`reap(run_id=A)` 会把 B 正在跑的 pod 一并强删，而 B 自己的 reap 选择器反而选不到这些 pod。这是一个**跨 run 的可用性干扰**问题（不是凭据/沙箱逃逸），截至 merge 时仍未解决，该 PR 只是阻止了"借用方意外重新打标"这一个诱因，没有从根上把"模板归属"和"实际 claim 方"两个概念分开。
- 所有性能数字都来自作者（`tomergee`/`igooch`/`aditya-shantanu` 等 Kubernetes SIG 贡献者）自己的集群实验，属于生产验证但非独立复现；recycling 的"50 problems × 40 rollouts 无操作 payload"是合成负载（no-op），不是真实 SWE-bench 任务，真实任务下的 reset 耗时和脚手架开销未知。
- recycling 只覆盖 git 版本化的 `/testbed`，非 git 镜像自动降级为"每任务新 claim"，不构成额外风险但也不带来收益；env/config 层漂移检查默认关闭，意味着默认配置下，环境变量/依赖漂移不受 canary 保护。
- 跨集群连接性（cross-cluster learner 如何连到另一个集群的沙箱）被文档明确标注为"调用方自己解决"（Gateway/LoadBalancer/VPC 对等），包本身不提供方案。

## 对我们的启发

1. **"按并发预算 sizing，而非按任务数 sizing"这个思路可以直接搬**：我们如果目前预热池大小是按"有多少不同 image"或"有多少任务"线性算的，`clamp(round(MAX_CONCURRENT × tasks_image/tasks_total), 1, min(tasks_image, cap))` 这个公式本身很薄，2026 年 Q4 可以作为我们自己预热池 sizing 的起点，尤其是"eval 按并发预算 / RL 按任务数深预热"两套模式分开配置这个区分，直接对应我们"评测密度 vs RL rollout 密度"两类不同的负载画像。
2. **沙箱复用（reset 而非重建）在高并发同 image 争抢场景下收益很大（24.5× claim 数降低，wall-clock 近半），但前提是有一个可验证的"determinism canary"**——如果我们要做类似的沙箱复用（而不是每个 rollout 都新建环境），"复用前必须有可自动化的清洁度校验"这个设计约束应该提前列进我们自己的方案里，不能只靠约定式的"约定 reset 脚本"。
3. **#1215 和 #1811 两个坑都是"controller 的二级效应没被一线开发者意料到"**：#1215 的"informer 缓存滞后于自己的写"是**任何**基于 list-watch 的控制器在高并发 reconcile 下都会踩的通用坑（ReplicaSet controller 的 expectations 模式是标准解法），如果我们自己的沙箱调度器或任何 CRD controller 也在高频 reconcile + 高并发 worker 下运行批量创建逻辑，应该主动检查是否存在同样的"创建后立刻再读、读到的是旧缓存"模式。#1811 则提示我们：如果给资源打的标签前缀恰好和下游系统（这里是 Kubernetes 自身的 Sandbox 控制器）的"系统保留前缀"规则冲突，标签会被静默剥掉而没有任何报错——排查这类"安全机制突然失效"问题时，优先检查标签/注解是否被中间层悄悄过滤掉了。
4. Follow-up（可转 issue）：
   - 调研 `warm_create_budget`（staged 创建，默认 1000-wave）这个模式能否直接搬到我们自己的批量创建逻辑里，作为"不管底层 controller 有没有 expectations bug，客户端侧先限流"的通用防御层。
   - 对比我们自己沙箱生命周期管理是否也存在"标签被下游系统静默剥除"的风险，排查我们所有跨组件的标签/选择器契约。
   - 评估 `determinism_canary` 这套"复用前自动校验 + 隔离而非信任"的模式，看能否迁移到我们自己的沙箱状态复用方案（如果我们有类似"环境 reset 复用"的设计）。

## 相关

- 相关概念：[[agent-sandbox-rl]]、[[rollout-efficiency]]、[[sandbox-image-distribution]]、[[on-demand-image-loading]]、[[microvm-placement]]、[[agentic-rollout-preemption]]
- 相关笔记：（暂无同主题笔记，本篇是该系统在知识库里的首次精读）
