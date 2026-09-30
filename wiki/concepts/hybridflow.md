---
title: "HybridFlow / veRL"
aliases: [veRL, verl, HybridFlow, 3D-HybridEngine, hybrid programming model for RLHF]
created: 2026-09-30
updated: 2026-09-30
sources: [2409.19256, 2506.06122]
---

# HybridFlow / veRL

## 一句话定义

HybridFlow（开源实现名 veRL）是一个 RLHF/RL 训练框架，用"节点间单控制器 + 节点内多控制器"的混合编程模型灵活表达 RLHF 数据流，并用 3D-HybridEngine 让 actor 模型在训练与生成两阶段之间零冗余地共享/重分片权重，实测吞吐比 DeepSpeed-Chat/OpenRLHF/NeMo-Aligner 快 1.53×~20.57× [[2409.19256]]。

## 为什么对我们重要

veRL 是当前最常用的开源 agentic RL / RLHF 框架底座之一（[[2609.22978]] DSec 把它列为"把执行环境当黑盒"的代表性 RL 训练系统之一），也是 [[agentic-rl-frameworks]] 综述里 RLHF/微调框架分类中的一项。它的架构选择（单控制器编排 + 多控制器执行、GPU placement 搜索算法、权重零冗余共享）直接对应我们做沙箱/调度平台时要回答的问题：训练与推理（rollout 生成）该不该共享设备、该怎么调度。

## 核心机制 / 主要变体

- **Hybrid 编程模型**：节点间（模型与模型之间的数据依赖、resharding）用单控制器统一编排，节点内（每个模型自己的分布式训练/推理/生成）用多控制器执行，兼顾灵活性与低 dispatch 开销 [[2409.19256]]。
- **传输协议（transfer protocol）**：每个模型 API 注册一个 collect+distribute 函数对，由单控制器协调不同并行策略模型间的多对多数据 resharding，但实际数据搬运只发生在 GPU 之间，不经过中心节点；内置 8 种协议覆盖常见场景 [[2409.19256]]。
- **`ResourcePool`**：虚拟化一组 GPU，决定哪些模型 colocate（同一组设备，时分复用）、哪些 standalone（各自一组设备，可并行执行）[[2409.19256]]。
- **3D-HybridEngine**：actor 模型训练与生成用不同的 3D 并行配置（生成阶段更小 TP/PP、更大 DP），但共享同一份权重副本；通过让生成阶段 TP/PP group 按间隔取 rank（而非连续取），使训练/生成权重在每张卡上天然重叠，resharding 时仅需 micro DP group 内 all-gather，实现零冗余显存与最小通信量 [[2409.19256]]。
- **Auto Device Mapping**：给定 dataflow 图和模型 workload，枚举可行 placement（4 模型时对应 15 种 Bell 划分）与并行策略组合，用延迟模拟器搜索端到端延迟最小的方案；缓存 (模型, GPU 数) 下的最优并行策略避免重复搜索 [[2409.19256]]。

## 工程要点与数字

- **端到端吞吐**：128×A100，Llama 7B~70B，PPO/ReMax/Safe-RLHF 三种算法下，比 DeepSpeed-Chat/OpenRLHF/NeMo-Aligner 平均快 3.67×/3.25×/12.52×（最高 7.84×/5.93×/20.57×），70B 模型上平均加速 9.64× [[2409.19256]]。
- **Transition（训练↔生成权重切换）开销**：相比 DeepSpeed-Chat 最多降低 89.1%（70B 模型，78.2s→数秒级），平均降低 55.2%（11.7s），且开销不随集群规模增长（baseline 会退化）[[2409.19256]]。
- **Model Placement 随规模反转**：16~64 GPU 时 colocate 全部模型最优；34B 模型 96~128 GPU（13B 在 96 GPU）时 split（actor+ref 一组/critic+reward 一组）最优；13B 在 128 GPU 时 standalone（四模型各自一组设备）最优——没有一种 placement 全局最优，Auto-Mapping 算法能在测试的每个规模点找到最优或近最优方案 [[2409.19256]]。
- **Auto-Mapping 搜索时间**：随模型规模线性增长，靠缓存把最坏情况控制在半小时内 [[2409.19256]]。
- 系统规模：约 12k 行 Python；单控制器基于 Ray+RPC，训练/推理引擎支持 Megatron-LM/FSDP/DeepSpeed，生成引擎基于 vLLM（KVCache manager 改为分布式版本）[[2409.19256]]。

## 下游采用的证据

- [[2506.06122]]（ROLL，阿里的大规模 RL 训练库）明确说明其 Data Transfer 模块**直接复用 HybridFlow 提出的 Transfer Protocol** 做跨阶段 resharding，且其单控制器管线设计也是在 HybridFlow 的单控制器架构基础上构建；但 ROLL 的 AutoDeviceMapping 走了不同取舍——**允许训练/生成不 colocate 也能**靠 `ModelUpdateGroup`（NCCL）同步参数，不要求像 3D-HybridEngine 那样共享同一份权重做零冗余 resharding。这是 HybridFlow 架构思想被后续系统直接沿用、同时在关键设计点上分叉的一个具体例子 [[2506.06122]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源；注意 HybridFlow 的"训练/生成共享设备、零冗余 resharding"与 [[rollout-training-disaggregation]] 里 AWS 博客提出的"训练/rollout 拆到不同资源池"是两种不同场景下的设计取舍，不是直接矛盾——前者优化的是同一份 actor 权重在训练与生成两阶段之间的切换成本，后者优化的是整个 RL job 里训练 worker 与 rollout worker 的资源弹性与中断容忍，二者可以叠加使用）

## 开放问题

- 论文吞吐数字全部基于**固定长度**（prompt/response 各 1024 token）测试，为了公平对比不支持 continuous batching 的 baseline；真实变长 rollout 下的吞吐倍数未知，不能直接套用 [[2409.19256]]。
- Auto Device Mapping 假设同构 GPU，异构设备扩展只是设计讨论、无实验验证 [[2409.19256]]。
- 细粒度 GPU 资源共享（并发跑 colocate 的多个模型而非顺序执行）被明确列为未来工作，论文当前实现为避免 OOM 采用顺序执行 [[2409.19256]]。
- 论文发表于 2024-09，veRL 项目本身迭代极快，需要再核实当前（2026）GitHub 主分支架构是否已偏离论文描述（例如是否仍是 Ray+RPC 单控制器）——见 [[2409.19256]] 笔记的 follow-up。

## 相关概念

[[agentic-rl-frameworks]]、[[rollout-training-disaggregation]]

## 相关来源

- [[2409.19256]] — HybridFlow 原始论文，给出编程模型设计、3D-HybridEngine、Auto Device Mapping 算法与全部量化吞吐数字
- [[2506.06122]] — ROLL 原始论文，证实 HybridFlow 的 Transfer Protocol 被后续大规模 RL 训练库直接复用，同时展示了"不要求 colocate"的另一种设备映射取舍
