---
title: "Agent Rollout 与 GPU 训练抢占解耦"
aliases: [rollout preemption, 抢占安全 rollout, agent sandbox 与 worker container 解耦, preemption-safe resumption]
created: 2026-09-27
updated: 2026-09-27
sources: [2609.19969]
---

# Agent Rollout 与 GPU 训练抢占解耦

## 一句话定义

把 agentic RL 的 rollout 执行（agent sandbox + 控制 rollout 的 worker container）从可抢占的 GPU 训练池中物理搬出去，让 GPU 训练抢占不再需要杀死或重放长时状态化的 agent 轨迹 [[2609.19969]]。

## 为什么对我们重要

这直接对应研究方向里"训练系统 GPU 调度、抢占、样本级派发"与"沙箱状态保持"的交叉点：如果我们平台的训练系统还是 rollout 进程和训练进程强绑定，GPU 抢占会连带打断整条 agent 轨迹，恢复成本高且容易引入非幂等副作用的重复执行问题。DeepSeek 给出的是一条已经在生产验证过的重构路径，而不是理论提案 [[2609.19969]]。

## 核心机制 / 主要变体

- **架构解耦**：agent rollout 执行被拆成 agent sandbox（跑 scaffold 及其工具）和 worker container（scaffold-agnostic 控制层，统一异构交互为通用轨迹 schema，与 trainer 通信）两部分，两者都跑在沙箱平台（DSec）上，**都在可抢占 GPU 训练池之外** [[2609.19969]]。
- **旧方案的问题**（据 DSec 自述）：更早版本里 agent loop 跑在可抢占 GPU 训练 pod 内部，与 model-serving/RL 框架同进程；GPU job 被抢占时 agent loop 随之丢失，只能靠 command log 重放来把训练框架恢复的 rollout 状态和沙箱执行状态对齐——重放时对已完成操作复用记录结果而非重新执行，避免非幂等命令的重复副作用，但这套恢复逻辑本身就是额外的复杂度和延迟来源 [[2609.22978]]。
- **抢占时的状态处理**：trainer 抢占发生时，rollout 执行可以被挂起并卸载，同时完整保留状态供后续恢复，释放 CPU/GPU 资源；worker container + agent sandbox 共同持有完整 rollout 状态、作为单一事实来源，让被抢占的 GPU 任务可以直接重连继续，无需通过 command-log 重放重建执行过程 [[2609.19969]] [[2609.22978]]。
- **沙箱层的暂停/恢复实现**（进程/VM 粒度）：容器用 `docker pause` 冻结进程树，再启用 `memory.swap.max` + `memory.reclaim` 主动回收匿名页和文件页内存；恢复时用 `MADV_WILLNEED` 预取内存映射再 `docker unpause`。microVM（Firecracker）用快照保存内存和执行状态、终止进程释放运行时内存；恢复时新起进程并从快照恢复 guest 执行 [[2609.22978]]。
- **比沙箱层更细的粒度：token 级状态持久化**（推理引擎侧，而非沙箱层）：生成可以在任意 token 边界几乎瞬间停止（token 级中断）；KV cache 和专家路由信息按 token 粒度持久化，新 checkpoint 上线后直接复用已持久化状态继续生成，不需要重新 prefill；配合按样本粒度的垃圾回收，及时释放已完成样本的状态。这套机制同时用于响应集群调度抢占信号，而不仅是模型 checkpoint 切换 [[2609.19969]]。

## 工程要点与数字

- 该架构改动是**从 DeepSeek-V4.1 开始**引入的（此前版本 agent loop 与 GPU 训练 pod 同进程）[[2609.22978]]。
- 沙箱层的 pause/resume 是进程/虚拟机粒度的暂停恢复；token 级 KV/路由状态持久化是推理引擎粒度的续跑能力——两者是互补而非替代关系，缺一个都会让抢占代价变高 [[2609.19969]]。

## 争议与矛盾

（暂无跨来源分歧；[[2609.19969]] 与 [[2609.22978]] 的描述互相印证而非冲突）

## 开放问题

- token 级状态持久化对显存/主存的额外占用有多大（需要保留所有 in-flight 样本的 KV cache 和路由状态），论文未给出具体数字。
- 沙箱层 pause/resume 与推理引擎 token 级续跑之间的协调协议（谁先触发、超时如何处理）未展开描述。

## 相关概念

[[sandbox-density-overcommit]]、[[microvm-sandbox]]

## 相关来源

- [[2609.19969]] — 从"使用方"角度描述该架构改动的动机与训练侧效果（跨 scaffold RL、异步 post-training 基础设施）
