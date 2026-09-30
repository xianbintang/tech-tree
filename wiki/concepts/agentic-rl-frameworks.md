---
title: "Agentic RL 训练框架全景"
aliases: [agentic RL frameworks, agent RL 训练框架]
created: 2026-09-29
updated: 2026-09-30
sources: [2509.02547, 2601.02780]
---

# Agentic RL 训练框架全景

## 一句话定义

[[2509.02547]] Table 11 对约 23 个 RL 训练代码库的分类盘点：12 个 Agentic RL 专用框架、6 个 RLHF/LLM 微调框架、5 个通用 RL 框架 [[2509.02547]]。

## 为什么对我们重要

这些框架是"训练系统与调度"这个研究方向的直接对应物——几乎每一个 Agentic RL 专用框架都把"异步执行"和"集中式环境/资源编排"列为核心特性，说明这是行业共识的架构方向，值得对照我们自己的调度系统设计逐一比较 [[2509.02547]]。

## 核心机制 / 主要变体

**Agentic RL 专用框架**（Section 5.2）：

- **Verifiers**：可验证环境设置，端到端策略优化 [[2509.02547]]。
- **SkyRL-v0**：长程真实世界 agent 训练 [[2509.02547]]。
- **AREAL**：异步、分布式架构，面向语言推理任务规模化 [[2509.02547]]。
- **MARTI**：把范式扩展到多智能体 LLM 系统，集成训练与推理 [[2509.02547]]。
- **EasyR1**：多模态支持，统一 RL 框架里融合视觉与语言信号 [[2509.02547]]。
- **AgentFly**：可扩展、可扩展的 agent-RL 框架，装饰器式工具/奖励定义 + 异步执行 + 集中式资源管理,面向高吞吐 RL 训练 [[2509.02547]]。
- **Agent Lightning**：把 agent 执行建模为独立 MDP，**将执行与训练解耦**，用分层 RL 算法（LightningRL）以近零代码修改训练任意 AI agent [[2509.02547]]。
- **AWorld**：分布式 Agentic RL 框架，解决"经验生成"这一主瓶颈，跨集群大规模并行 rollout，**相对单机 14.6× 加速**，支撑端到端可扩展训练管线 [[2509.02547]]。
- **ROLL**：统一控制器 + 并行 worker + 自动资源映射，支撑多 GPU 稳定训练 [[2509.02547]]。
- **VerlTool**：基于 Verl 构建的工具集成 rollout 框架（ARLT），联合优化规划与执行 [[2509.02547]]。
- **AgentRL**：多轮多任务异步框架，统一环境编排，引入 cross-policy sampling 与 task advantage normalization 稳定大规模训练 [[2509.02547]]。
- **RL-Factory**：易于设计的奖励定义 [[2509.02547]]。

**RLHF/微调框架**：OpenRLHF（高性能可扩展对齐工具包）、TRL（HuggingFace 基线实现）、trlX（数百亿参数分布式微调）、HybridFlow（RLHF 实验管理与规模化）、SLiMe（Megatron+SGLang 组合的异步 RL、解耦式 reward/数据生成）、Oat（轻量 RL 支持）[[2509.02547]]。

**通用 RL 框架**：RLlib（生产级可扩展库）、Acme（模块化分布式组件）、Tianshou（纯 PyTorch 高性能平台）、Stable Baselines3（可靠 PyTorch 实现）、PFRL（原 ChainerRL，基准化原型算法）[[2509.02547]]。

**生产级"集中式环境编排"的具体实现（MiMo-V2-Flash 的 Toolbox / Tool Manager）**：基于 Ray 调度，职责拆成两层——**Toolbox** 是集中式资源分配器，对并发任务间的工具调用强制资源配额和 QPS 限制，用容错 Ray actor pool 消除冷启动延迟；**Tool Manager** 与 rollout 引擎集成，靠环境预热（pre-warming）和序列级异步 reward 计算加速训练，并用超时恢复、实时监控维持稳定性。两者职责分离——工具管理逻辑与系统级调度策略解耦——使新增工具类型不需要改动 rollout 主流程，是本页"12 个专用框架均强调集中式环境编排"这一共识架构方向的一个有具体机制描述（而非仅特性列表）的实例 [[2601.02780]]。同一套系统里的 **Data Scheduler** 按细粒度序列（而非 micro-batch）调度、动态采样时参考历史通过率做负载均衡，并集成 partial rollout + staleness-aware truncated importance sampling 处理超长轨迹，是 [[async-rl-training]] 里"样本/轨迹粒度解耦"思路的生产实例 [[2601.02780]]。

## 工程要点与数字

- **AWorld 14.6× 加速**是全文少数几个量化的工程数字之一，直接印证"rollout/环境执行吞吐是 agent RL 训练规模化的主瓶颈"这一判断，与我们平台的核心关注点（生产可跑性、成本与密度）高度一致 [[2509.02547]]。
- 除 AWorld 外，其余框架均**只给定性特性描述、无量化吞吐/成本数字**——这是本综述在工程细节上的已知缺口 [[2509.02547]]。
- 12 个 Agentic RL 专用框架里，AREAL、AgentFly、ROLL、AgentRL 都明确强调"异步执行"或"异步训练"，是这批框架的共同架构选择 [[2509.02547]]。
- MiMo-V2-Flash 的 Toolbox/Tool Manager/Data Scheduler 三个组件**同样只有架构描述，没有给出吞吐提升、冷启动延迟节省、GPU 利用率等量化数字**——与该团队上一代模型 [[2505.07608]] 的 Seamless Rollout Engine（给出明确的 2.29×/2.61× 加速和空闲率数字）相比，是工程量化上的倒退，评估这套系统时不能只看架构描述 [[2601.02780]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- Agent Lightning 的"执行与训练解耦"架构（agent 执行 = 独立 MDP，近零代码修改接入）与我们"沙箱执行服务 + 训练循环通过异步 API 对接"的设想高度吻合，值得深入精读其论文/代码验证细节（follow-up，见 [[2509.02547]] 笔记）。
- AWorld、AgentRL 的"环境编排 + 跨集群并行 rollout"具体实现机制未在综述里展开，需要回到原始论文对比我们自己的调度系统设计。
- Toolbox 的"容错 Ray actor pool 消除冷启动延迟"具体怎么做到（预留多少常驻 actor、如何按负载扩缩容）未披露，值得对照我们自己的沙箱冷启动优化方案（follow-up，见 [[2601.02780]] 笔记）。

## 相关概念

[[agentic-rl]]、[[agentic-rl-environments]]、[[async-rl-training]]

## 相关来源

- [[2509.02547]] — Table 11 系统盘点约 23 个 RL 训练框架，AWorld 的 14.6× 加速是本综述唯一量化的训练吞吐数字
- [[2601.02780]] — Toolbox/Tool Manager/Data Scheduler：生产级"集中式环境编排"实现，给出资源配额、容错 actor pool、环境预热等具体机制（但无量化效果数字）
