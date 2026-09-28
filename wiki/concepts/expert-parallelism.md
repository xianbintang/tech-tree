---
title: "专家并行（Expert Parallelism, EP）"
aliases: [Expert Parallelism, EP, 专家并行]
created: 2026-09-29
updated: 2026-09-29
sources: [2026-09-29-moe-rl-eks-efa-deepep]
---

# 专家并行（Expert Parallelism, EP）

## 一句话定义

MoE（Mixture-of-Experts）模型特有的并行方式：把不同专家（expert）分布到不同设备上，运行时按 token 动态路由到对应专家所在设备，产生稀疏、细粒度、负载不均衡的 all-to-all 通信，区别于 TP/DP/PP 那种结构规整、可预测的通信模式 [[2026-09-29-moe-rl-eks-efa-deepep]]。

## 为什么对我们重要

我们平台做 GPU 调度和节点 placement，通常默认参照 TP/PP 这类规整通信模式来设计拓扑亲和策略。但 MoE 训练（尤其是大规模 RL 后训练）越来越依赖 EP，而 EP 的通信特征完全不同——稀疏、动态、随专家并行度增大而更依赖跨节点带宽。这直接影响我们该如何为 MoE 类工作负载做节点选型、gang scheduling 和网络拓扑感知调度。

## 核心机制 / 主要变体

- **动态 all-to-all token 路由**：EP 在 TP（Tensor Parallelism）、DP（Data Parallelism）、PP（Pipeline Parallelism）的稠密、结构化通信之上，额外引入按 token 动态路由到专家的稀疏 all-to-all 通信 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **稀疏性放大通信瓶颈**：MoE 架构为了降低推理成本做得越来越稀疏，代价是训练侧越来越受通信瓶颈约束而非算力约束——稀疏度越高，同样计算量下 EP 通信开销占比越大 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **随 EP 并行度增长，通信从节点内转向节点间**：EP 并行度越大，token 路由跨越的设备越多，通信越依赖低带宽的节点间链路而非节点内 NVLink，导致跨节点同步与单条消息开销的占比上升 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- 在 RL 后训练场景（RLHF/GRPO）中，EP 的通信压力还要和 rollout 生成（[[rollout-training-disaggregation]]）、reward 模型推理、checkpoint 更新等其他子系统的资源需求叠加，任何一环的通信延迟都可能让紧耦合的 policy training 卡住 [[2026-09-29-moe-rl-eks-efa-deepep]]。

## 工程要点与数字

- 具体的通信优化实现见 [[deepep]]：用专用 dispatch/combine kernel 替代通用 NCCL all-to-all collective，节点内走 NVLink，节点间走 RDMA。
- 暂无来源给出 EP 通信量随专家数/并行度增长的定量公式或 benchmark 曲线——目前的证据只是定性描述"EP 通信随并行度增大更依赖跨节点带宽" [[2026-09-29-moe-rl-eks-efa-deepep]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- EP 通信开销与专家数、每 token 激活专家数（top-k）、批大小之间的定量关系，需要更多来源补充。
- 除 DeepEP 外的其他 EP 通信优化方案（如不同厂商的拓扑感知路由算法）与 DeepEP 的性能对比，目前知识库里没有数据。
- 我们自己平台在做 EP 类工作负载的节点 placement 时，应该用什么具体策略（专家分片的节点亲和规则、跨节点带宽预留），尚待结合我们自己的网络拓扑做调研。

## 相关概念

[[deepep]]、[[rollout-training-disaggregation]]

## 相关来源

- [[2026-09-29-moe-rl-eks-efa-deepep]] — AWS 博客，定义了 EP 的通信模式及其与 TP/DP/PP 的区别，指出 EP 通信随并行度增长更依赖跨节点带宽
