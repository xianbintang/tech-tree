---
title: "DeepEP"
aliases: [DeepEP, DeepEP-over-EFA]
created: 2026-09-29
updated: 2026-09-29
sources: [2026-09-29-moe-rl-eks-efa-deepep]
---

# DeepEP

## 一句话定义

DeepSeek 开源的专家并行（[[expert-parallelism]]）通信库：用专用的 dispatch（把 token 从本地 GPU 路由到远端专家）和 combine（把处理完的 token 收集回来）两个 GPU kernel，替代通用 NCCL all-to-all collective，节点内走 NVLink，节点间走 RDMA，以降低 MoE 稀疏、细粒度、不均衡通信的开销 [[2026-09-29-moe-rl-eks-efa-deepep]]。

## 为什么对我们重要

DeepEP 是目前知识库里第一个具体的 EP 通信优化方案，直接关系到我们平台如果要跑大规模 MoE RL 训练，节点间网络该怎么配置、要不要适配 DeepEP 这类专用通信库，以及能不能在非 AWS EFA 的网络环境（比如 RoCE/InfiniBand）上复用。

## 核心机制 / 主要变体

- **dispatch/combine 双 kernel 设计**：dispatch kernel 把 token 从本地 GPU 路由到远端专家所在设备，combine kernel 把各专家处理完的 token 收集回来，两者都替代了通用的 NCCL all-to-all collective [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **分层传输**：节点内传输走 NVLink（通过 NVSwitch），节点间传输走 RDMA-capable backend [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **DeepEP v2 + libfabric 移植 → 原生支持 AWS EFA**：AWS 向 DeepEP 上游贡献了把通信原语从 CUDA 专用 RDMA backend 迁移到 libfabric 的改动，使传输层可移植到 libfabric 支持的多种网络 fabric，DeepEP v2 因此获得原生 EFA 支持；同期 NCCL 2.31 也为稠密 collective 通信补上了最新的 EFA 优化 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- 在 AWS P5/P6 实例上，EFA 配合 NVIDIA GPUDirect RDMA + OS bypass，可以在设备间直接搬运 GPU 显存数据，减少 CPU/操作系统介入通信路径 [[2026-09-29-moe-rl-eks-efa-deepep]]。

## 工程要点与数字

- **实测吞吐提升**：48×P5en 实例（16 台训练 + 32 台推理）跑同一个 super-sparse MoE 模型，启用 DeepEP over EFA 后，聚合 RL rollout 吞吐提升 **40%**（未给出绝对吞吐数值，只有相对提升） [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **该数字的对照组混淆变量较多**：基线技术栈（Slime，CUDA 12.9 / PyTorch 2.9.1 / NCCL 2.27 / SGLang 0.5.9）与改进技术栈（DeepEP-over-EFA，CUDA 13.0 / PyTorch 2.12 / NCCL 2.31 / EFA 1.49 / DeepEP 2.0 / SGLang 0.5.17）同时升级了 CUDA、PyTorch、NCCL、SGLang 等多个组件，不是单一开关 DeepEP 的纯消融实验，40% 里 DeepEP/EFA 本身贡献多少无法从文中拆分出来 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- 版本矩阵（用于复现该 benchmark）：CUDA 13.0、PyTorch 2.12.1（cu130）、NCCL 2.31.2、EFA installer 1.49、DeepEP 2.0.0、SGLang 0.5.17、训练脚手架 Miles 0.1.0 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- 实例要求：需要 EFA 支持的实例类型（p5.48xlarge / p5e.48xlarge / p6-b200.48xlarge），且通信节点必须在同一可用区（AZ）内 [[2026-09-29-moe-rl-eks-efa-deepep]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源；上面"对照组混淆变量较多"是本笔记对该来源数据的质疑，不是与其他来源的冲突）

## 开放问题

- DeepEP/EFA 相对于框架版本升级（NCCL 2.27→2.31、SGLang 0.5.9→0.5.17 等）各自对 40% 提升的贡献占比，需要一篇有消融实验的来源来验证。
- DeepEP 在非 EFA 网络环境（RoCE、InfiniBand）上的性能表现和移植成本，本篇来源未涉及。
- DeepEP 与其他拓扑感知 EP 通信方案的横向对比，知识库里暂无数据。

## 相关概念

[[expert-parallelism]]、[[rollout-training-disaggregation]]

## 相关来源

- [[2026-09-29-moe-rl-eks-efa-deepep]] — AWS 博客，描述 DeepEP 的 dispatch/combine kernel 设计、AWS 对 libfabric/EFA 移植的贡献，以及 40% 吞吐提升的 benchmark（但技术栈变量未隔离）
