---
title: "Rollout/Training 分离调度（Rollout-Training Disaggregation）"
aliases: [rollout-training disaggregation, rollout/训练分离, 异步 RL 资源拆分, elastic rollout]
created: 2026-09-29
updated: 2026-09-29
sources: [2026-09-29-moe-rl-eks-efa-deepep]
---

# Rollout/Training 分离调度

## 一句话定义

大规模异步 RL 训练里，把 rollout 生成（可分区、可容忍中断、追求聚合吞吐的推理负载）与 policy training（紧耦合、要求 lockstep 同步、对中断敏感的训练负载）拆成两类资源池分别调度：rollout 可以上 Spot/抢占式实例弹性伸缩，training 保持在稳定容量上不受 rollout 的资源波动影响 [[2026-09-29-moe-rl-eks-efa-deepep]]。

## 为什么对我们重要

这是本笔记来源里对我们最直接相关的一条：我们做的正是沙箱平台与调度系统，"两类完全不同 SLA/中断语义的 GPU workload 如何混部"是核心能力问题。这个概念给出了一个具体的设计参照：按工作负载的中断容忍度做资源池切分，而不是笼统地把所有 GPU 当同质资源调度。

## 核心机制 / 主要变体

- **两种工作负载的性质差异**：rollout 生成是大规模分布式推理，优化目标是聚合吞吐而非首 token 延迟（TTFT）或逐 token 延迟；policy training 要求 worker 紧耦合、lockstep 推进，类似预训练/SFT，任何延迟尖峰或掉队 worker 都可能让整个 job 卡住或触发 NCCL 超时 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **Spot 承载 rollout 的可行性来自任务的可分区性**：rollout worker 被 Spot 中断不需要整个 RL job 停下——未完成的 rollout 任务可以退回队列被其他 worker 重新领取，其余 worker 继续生成经验 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **设计要点**：rollout worker 应处理有界（bounded）的工作单元、频繁发布已完成样本；收到 Spot 中断通知时，worker 排空（drain）在途请求、把未完成任务退回队列 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **调度层面按队列深度独立伸缩**：基于 EKS，可以按 rollout 需求和队列深度独立伸缩 Spot-based rollout node group，同时为 policy training 维持稳定容量；policy-training worker 因此不受 Spot 中断、延迟或 NCCL 超时影响 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **三层独立伸缩的整体架构**：编排（EKS 控制面：调度、扩缩容、故障恢复）、跨节点高性能通信（NVLink 管节点内、EFA 管节点间）、数据层（经验缓冲区做高频读写的非持久层 + S3 做 checkpoint/训练产物的持久层）三者解耦，各自独立扩缩容 [[2026-09-29-moe-rl-eks-efa-deepep]]。

## 工程要点与数字

- 来源给出了架构设计（分节点组、Spot 承载 rollout、queue-based 重分配），但**没有给出 Spot 相对 On-Demand 的具体成本节省数字，也没有给出中断率或排空延迟的工程数据** [[2026-09-29-moe-rl-eks-efa-deepep]]。
- Benchmark 场景里训练与推理的资源配比是 16 台训练 : 32 台推理（共 48×P5en 实例），但这只是单一 case，来源未讨论该配比如何随模型稀疏度/EP 并行度调整 [[2026-09-29-moe-rl-eks-efa-deepep]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- rollout worker 的"有界工作单元"具体应该切多细、Spot 中断到任务重新被领取之间的延迟对整体 rollout 吞吐的影响，来源未量化。
- 该模式在非 AWS 环境（自建集群、其他云的抢占式实例）下的等价实现与踩坑点，知识库里暂无数据，需要另外调研。
- rollout:training 的资源配比应该如何随 MoE 稀疏度、专家并行度动态调整，目前没有定量指导。

## 相关概念

[[expert-parallelism]]、[[deepep]]

## 相关来源

- [[2026-09-29-moe-rl-eks-efa-deepep]] — AWS 博客，提出 EKS 上按中断容忍度拆分 rollout（Spot）与 training（稳定容量）资源池的架构模式
