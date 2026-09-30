---
title: "Agent Rollout 与 GPU 训练抢占解耦"
aliases: [rollout preemption, 抢占安全 rollout, agent sandbox 与 worker container 解耦, preemption-safe resumption, rollout-training decoupling, agent loop 解耦, sandbox pause/resume, 抢占安全的 rollout 恢复]
created: 2026-09-26
updated: 2026-09-27
sources: [2609.19969, 2609.22978]
---

# Agent Rollout 与 GPU 训练抢占解耦

## 一句话定义

把 agentic RL 的 rollout 执行（agent sandbox + 控制 rollout 的 worker container）从可抢占的 GPU 训练池中物理搬出去，交给独立的沙箱侧组件持有，使 GPU 训练抢占不再需要杀死或重放长时状态化的 agent 轨迹——被抢占的训练任务只需"重连"而不必"重建"或靠 command log 重放来恢复 rollout 状态 [[2609.19969]] [[2609.22978]]。

## 为什么对我们重要

这直接对应研究方向里"训练系统 GPU 调度、抢占、样本级派发"与"沙箱状态保持"的交叉点：如果我们平台的训练系统还是 rollout 进程和训练进程强绑定，GPU 抢占会连带打断整条 agent 轨迹，恢复成本高且容易引入非幂等副作用的重复执行问题；抢占代价还会随 rollout 时长线性增加。DeepSeek 给出的是一条已经在生产验证过的重构路径（从 V3.2 到 V4.1 实际经历过这个演进），而不是理论提案，直接回答"训练系统调度栈要不要把沙箱生命周期和训练生命周期解耦"这个架构问题 [[2609.19969]] [[2609.22978]]。

## 核心机制 / 主要变体

- **架构解耦**：agent rollout 执行被拆成 agent sandbox（跑 scaffold，如 DeepSeek Harness，及其工具）和 worker container（scaffold-agnostic 控制层，统一异构交互为通用轨迹 schema，与 trainer 通信）两部分，两者都跑在沙箱平台（DSec）上，**都在可抢占 GPU 训练池之外**，共同构成 rollout 状态的唯一真相来源 [[2609.19969]] [[2609.22978]]。
- **旧方案的问题**：更早版本里 agent loop 跑在可抢占 GPU 训练 pod 内部，与 model-serving/RL 框架同进程；GPU job 被抢占时 agent loop 随之丢失，只能靠 command log 重放来把训练框架恢复的 rollout 状态和沙箱执行状态对齐——重放时对已完成操作复用记录结果而非重新执行，避免非幂等命令的重复副作用，但这套恢复逻辑本身就是额外的复杂度和延迟来源 [[2609.22978]]。这一改动把"rollout 状态恢复"的逻辑从 RL 框架里整体移出，简化了跨组件协调和失败处理 [[2609.22978]]。该架构改动是**从 DeepSeek-V4.1 开始**引入的 [[2609.22978]]。
- **抢占时的状态处理 / pause-resume 是配套的资源回收机制**：trainer 抢占发生时，rollout 执行可以被挂起并卸载，同时完整保留状态供后续恢复，释放 CPU/GPU 资源；若沙箱继续常驻会白白占用内存，因此 RL 框架主动向所有关联沙箱发 pause 请求，DSec 借此回收内存，同时保留执行状态；后续任何对 paused 沙箱的请求会透明地先 resume 再执行，被抢占的 GPU 任务可以直接重连继续，无需通过 command-log 重放重建执行过程 [[2609.19969]] [[2609.22978]]。
- **沙箱层的暂停/恢复实现**（进程/VM 粒度）：容器用 `docker pause` 冻结进程树，再启用 `memory.swap.max` + `memory.reclaim` 主动回收匿名页和文件页内存；恢复时用 `MADV_WILLNEED` 预取内存映射再 `docker unpause`。microVM（Firecracker）把内存和执行状态存成完整快照，终止进程释放运行时内存；恢复时新起进程并从快照恢复 guest 执行 [[2609.19969]] [[2609.22978]]。
- **比沙箱层更细的粒度：token 级状态持久化**（推理引擎侧，而非沙箱层）：生成可以在任意 token 边界几乎瞬间停止（token 级中断）；KV cache 和专家路由信息按 token 粒度持久化，新 checkpoint 上线后直接复用已持久化状态继续生成，不需要重新 prefill；配合按样本粒度的垃圾回收，及时释放已完成样本的状态。这套机制同时用于响应集群调度抢占信号，而不仅是模型 checkpoint 切换 [[2609.19969]]。
- **Agent 自建环境（pack_diff）依赖同一套基础设施**：agent 在交互过程中可用增量磁盘快照把当前沙箱状态直接固化成可复用环境，供后续训练/评测任务直接消费，不需要单独的镜像构建流水线；为防止训练答案泄漏，构建环境的账号和跑训练的账号是分离的 [[2609.22978]]。

## 工程要点与数字

- 沙箱层的 pause/resume 是进程/虚拟机粒度的暂停恢复；token 级 KV/路由状态持久化是推理引擎粒度的续跑能力——两者是互补而非替代关系，缺一个都会让抢占代价变高 [[2609.19969]]。
- 这一整套机制在论文里**没有量化评估数字**，作者明确把"框架集成"标注为 evaluation 之外的范围，只提供了生产部署的描述性经验，这是当前需要靠后续论文或我们自己实验补上的空白 [[2609.22978]]。
- 前提依赖：微服务/容器级的 pause/resume 需要 cgroup `memory.swap.max` 和 `memory.reclaim`，microVM 的 pause/resume 依赖 Firecracker 的快照能力（存/加载内存+执行状态的完整快照）[[2609.22978]]。

## 争议与矛盾

（暂无跨来源分歧；[[2609.19969]] 与 [[2609.22978]] 对同一架构改动的描述互相印证——前者从"使用方"训练效果视角，后者从沙箱平台设计视角——而非冲突）

## 开放问题

- token 级状态持久化对显存/主存的额外占用有多大（需要保留所有 in-flight 样本的 KV cache 和路由状态），论文未给出具体数字。
- 沙箱层 pause/resume 与推理引擎 token 级续跑之间的协调协议（谁先触发、超时如何处理）未展开描述；agent sandbox / worker container 这两个组件的具体通信协议、状态一致性保证细节也未展开。
- pause/resume 的恢复延迟（尤其 microVM 完整快照恢复）在高抢占频率场景下是否会成为新的瓶颈，未见量化。
- 论文没有讨论"训练框架主动发 pause 请求"和"DSec 自身 TTL 超时回收"两条路径是否会冲突或重复触发。

## 相关概念

[[sandbox-density-overcommit]]、[[microvm-sandbox]]、[[checkpoint-engine]]

## 相关来源

- [[2609.19969]] — 从"使用方"角度描述该架构改动的动机与训练侧效果（跨 scaffold RL、异步 post-training 基础设施），补充 token 级状态持久化机制
- [[2609.22978]] — DSec §6.2–6.3：rollout 与 GPU 训练解耦、pause/resume 协同抢占的生产经验（无量化评估）
