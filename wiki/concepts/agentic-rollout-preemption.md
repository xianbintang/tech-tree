---
title: "Agent Rollout 与训练抢占协同"
aliases: [rollout-training decoupling, agent loop 解耦, sandbox pause/resume, 抢占安全的 rollout 恢复]
created: 2026-09-26
updated: 2026-09-26
sources: [2609.22978]
---

# Agent Rollout 与训练抢占协同

## 一句话定义

把 agentic RL 的 rollout 执行（agent loop + 沙箱状态）从可抢占的 GPU 训练进程中解耦出来，交给独立的沙箱侧组件持有，使 GPU 训练被抢占时只需"重连"而不必"重建"或靠 command log 重放来恢复 rollout 状态。

## 为什么对我们重要

我们的 GPU 训练资源大概率会被抢占式调度频繁打断；如果 agent loop 状态和 GPU 训练进程绑在一起，抢占代价会随 rollout 时长线性增加。这条经验直接回答"训练系统调度栈要不要把沙箱生命周期和训练生命周期解耦"这个架构问题，是可以对标的成熟做法而不是理论设想（DeepSeek 从 V3.2 到 V4.1 实际经历过这个演进）。

## 核心机制 / 主要变体

- **早期方案的问题**：agent loop 跑在可抢占的 GPU 训练 pod 里，和 model-serving、RL 框架挤在一起。GPU job 被抢占时 agent loop 直接丢失，但沙箱状态还在，只能靠 command log 重放来对账——重放时要跳过已完成的非幂等操作，否则会产生重复副作用 [[2609.22978]]。
- **DeepSeek-V4.1 起的新方案**：把 rollout 执行整体挪到 DSec 平台，拆成两个独立于可抢占 GPU 池之外的组件：agent sandbox（跑 scaffold，如 DeepSeek Harness，及其工具）+ worker container（管理沙箱、提供 scaffold-agnostic 的控制层）。这两者共同构成 rollout 状态的**唯一真相来源**，GPU 训练被抢占后重新连接即可继续，不需要重建执行或重放 command log [[2609.22978]]。这一改动把"rollout 状态恢复"的逻辑从 RL 框架里整体移出，简化了跨组件协调和失败处理 [[2609.22978]]。
- **Pause/resume 是配套的资源回收机制**：GPU job 被抢占后，如果沙箱继续常驻，会白白占用内存。RL 框架主动向所有关联沙箱发 pause 请求，DSec 借此回收内存，同时保留执行状态；后续任何对 paused 沙箱的请求会透明地先 resume 再执行 [[2609.22978]]。
  - 容器：`docker pause` 冻结进程树 → 打开 `memory.swap.max` 允许 swap → `memory.reclaim` 主动回收匿名页和文件页；resume 时先 `MADV_WILLNEED` 异步预取，再 `docker unpause` [[2609.22978]]。
  - microVM：pause 时把内存和执行状态存成完整快照，杀掉 Firecracker 进程释放运行时内存；resume 时起新进程加载快照继续执行 [[2609.22978]]。
- **Agent 自建环境（pack_diff）也依赖同一套基础设施**：agent 在交互过程中可用增量磁盘快照把当前沙箱状态直接固化成可复用环境，供后续训练/评测任务直接消费，不需要单独的镜像构建流水线；为防止训练答案泄漏，构建环境的账号和跑训练的账号是分离的 [[2609.22978]]。

## 工程要点与数字

- 这一整套机制在论文里**没有量化评估数字**，作者明确把"框架集成"标注为 evaluation 之外的范围，只提供了生产部署的描述性经验 [[2609.22978]]。这是当前唯一来源留下的明显空白，需要靠后续论文或我们自己的实验补上。
- 前提依赖：微服务/容器级的 pause/resume 需要 cgroup `memory.swap.max` 和 `memory.reclaim`，microVM 的 pause/resume 依赖 Firecracker 的快照能力（存/加载内存+执行状态的完整快照）[[2609.22978]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源，且该来源本身对此机制未给量化数据；后续如有其它训练框架论文披露类似机制的评测数字，在此对照）

## 开放问题

- rollout 与训练解耦之后，agent sandbox / worker container 这两个组件的具体通信协议、状态一致性保证细节，论文未展开。
- pause/resume 的恢复延迟（尤其 microVM 完整快照恢复）在高抢占频率场景下是否会成为新的瓶颈，未见量化。
- 论文没有讨论"训练框架主动发 pause 请求"和"DSec 自身 TTL 超时回收"两条路径是否会冲突或重复触发。

## 相关概念

[[microvm-sandbox]]、[[sandbox-density-overcommit]]

## 相关来源

- [[2609.22978]] — DSec §6.2–6.3：rollout 与 GPU 训练解耦、pause/resume 协同抢占的生产经验（无量化评估）
