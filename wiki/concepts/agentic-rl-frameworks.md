---
title: "Agentic RL 训练框架全景"
aliases: [agentic RL frameworks, agent RL 训练框架]
created: 2026-09-29
updated: 2026-09-30
sources: [2509.02547, 2409.19256, 2505.24298, 2506.06122, skyrl-v0]
---

# Agentic RL 训练框架全景

## 一句话定义

[[2509.02547]] Table 11 对约 23 个 RL 训练代码库的分类盘点：12 个 Agentic RL 专用框架、6 个 RLHF/LLM 微调框架、5 个通用 RL 框架 [[2509.02547]]。

## 为什么对我们重要

这些框架是"训练系统与调度"这个研究方向的直接对应物——几乎每一个 Agentic RL 专用框架都把"异步执行"和"集中式环境/资源编排"列为核心特性，说明这是行业共识的架构方向，值得对照我们自己的调度系统设计逐一比较 [[2509.02547]]。

## 核心机制 / 主要变体

**Agentic RL 专用框架**（Section 5.2）：

- **Verifiers**：可验证环境设置，端到端策略优化 [[2509.02547]]。
- **SkyRL-v0**：长程真实世界 agent 训练 [[2509.02547]]；原始博客（Berkeley Sky Computing Lab，详见 [[skyrl-v0]]）给出完整实现——基于 [[hybridflow|VeRL]] + OpenHands CodeAct scaffold，用独立可伸缩的 **Remote Sandbox Server**（K8s 部署，crun + aiodocker，单 16-CPU 节点承载 80–100 容器）把环境执行从训练里拆出来，配合异步 rollout（`async_generate`）+ 三段生产者-消费者流水线（init/run/eval 三队列重叠环境初始化、轨迹生成、奖励计算）取得 4–5× 加速；仅用约 300 条精选 SWE-Gym 数据，SWE-Bench-Verified 上三个模型系列（7B/8B/14B）均取得正向提升（11.0%→14.6%、3.6%→9.4%、18.0%→21.6%），但未拆分两个加速优化各自的贡献，也未给出 Remote Sandbox Server 的成本/故障恢复数字 [[skyrl-v0]]。
- **AREAL**：异步、分布式架构，面向语言推理任务规模化 [[2509.02547]]；原始论文（详见 [[async-rl-training]]）给出完整实现——interruptible rollout worker + staleness 上限 $\eta$ + 解耦 PPO 目标，1.5B–32B 训练时长缩短 2.77×、精度持平或更好，但仅验证了单轮数学/代码任务，多轮 agentic 场景是作者自己列出的未来工作 [[2505.24298]]。
- **MARTI**：把范式扩展到多智能体 LLM 系统，集成训练与推理 [[2509.02547]]。
- **EasyR1**：多模态支持，统一 RL 框架里融合视觉与语言信号 [[2509.02547]]。
- **AgentFly**：可扩展、可扩展的 agent-RL 框架，装饰器式工具/奖励定义 + 异步执行 + 集中式资源管理,面向高吞吐 RL 训练 [[2509.02547]]。
- **Agent Lightning**：把 agent 执行建模为独立 MDP，**将执行与训练解耦**，用分层 RL 算法（LightningRL）以近零代码修改训练任意 AI agent [[2509.02547]]。
- **AWorld**：分布式 Agentic RL 框架，解决"经验生成"这一主瓶颈，跨集群大规模并行 rollout，**相对单机 14.6× 加速**，支撑端到端可扩展训练管线 [[2509.02547]]。
- **ROLL**：统一控制器 + 并行 worker + 自动资源映射，支撑多 GPU 稳定训练 [[2509.02547]]；原始论文（阿里，详见 [[async-rl-training]]、[[rollout-training-disaggregation]]）给出更多细节——**样本粒度的 Rollout Scheduler**（异步 reward 计算 + 动态 add/abort 请求）支撑 dynamic sampling，AutoDeviceMapping 允许训练/生成**不 colocate 也能**用 `ModelUpdateGroup`（NCCL）同步参数，Data Transfer 直接复用 [[hybridflow]] 的 Transfer Protocol；RLVR 多域任务上 Qwen2.5-7B-Base 准确率 0.18→0.52（2.89×）、Qwen3-30B-A3B-Base 0.27→0.62（2.30×），agentic 任务 Sokoban 成功率 16.8%→26.0%、FrozenLake 12.9%→23.8%，但**"200B+ MoE、数千 GPU、两周不中断"的旗舰容错声明没有给出任何吞吐、GPU 数量或故障恢复时间的量化数字**，且与 veRL/OpenRLHF/StreamRL 等基线的比较全部停留在特性列表层面，没有实测吞吐对比表 [[2506.06122]]。
- **VerlTool**：基于 Verl 构建的工具集成 rollout 框架（ARLT），联合优化规划与执行 [[2509.02547]]。
- **AgentRL**：多轮多任务异步框架，统一环境编排，引入 cross-policy sampling 与 task advantage normalization 稳定大规模训练 [[2509.02547]]。
- **RL-Factory**：易于设计的奖励定义 [[2509.02547]]。

**RLHF/微调框架**：OpenRLHF（高性能可扩展对齐工具包）、TRL（HuggingFace 基线实现）、trlX（数百亿参数分布式微调）、**HybridFlow/veRL**（单控制器编排+多控制器执行的混合编程模型，3D-HybridEngine 实现训练/生成权重零冗余共享，实测吞吐 1.53×~20.57× 于 DeepSpeed-Chat/OpenRLHF/NeMo-Aligner，详见 [[hybridflow]]）、SLiMe（Megatron+SGLang 组合的异步 RL、解耦式 reward/数据生成）、Oat（轻量 RL 支持）[[2509.02547]] [[2409.19256]]。

**通用 RL 框架**：RLlib（生产级可扩展库）、Acme（模块化分布式组件）、Tianshou（纯 PyTorch 高性能平台）、Stable Baselines3（可靠 PyTorch 实现）、PFRL（原 ChainerRL，基准化原型算法）[[2509.02547]]。

## 工程要点与数字

- **AWorld 14.6× 加速**是综述全文少数几个量化的工程数字之一，直接印证"rollout/环境执行吞吐是 agent RL 训练规模化的主瓶颈"这一判断，与我们平台的核心关注点（生产可跑性、成本与密度）高度一致 [[2509.02547]]。
- 综述里除 AWorld 外，其余框架均**只给定性特性描述、无量化吞吐/成本数字**——这是本综述在工程细节上的已知缺口 [[2509.02547]]，AREAL 是目前唯一被精读过原始论文、补上量化数字的条目：2.77× 端到端训练加速（1.5B–32B）、interruptible generation 贡献 12%–17% 生成吞吐、动态 micro-batch 分配贡献约 30% [[2505.24298]]。
- 12 个 Agentic RL 专用框架里，AREAL、AgentFly、ROLL、AgentRL 都明确强调"异步执行"或"异步训练"，是这批框架的共同架构选择 [[2509.02547]]。
- ROLL 是第二个被精读过原始论文、补上量化数字的 Agentic RL 专用框架条目，但它的量化数字集中在"RL 训练能把准确率/成功率提多少"，**没有像 AReaL 那样给出异步机制本身贡献了多少吞吐提升的拆解**，也没有像 [[hybridflow]] 那样给出与其他框架的直接吞吐对比表——这是目前综述条目里量化程度参差不齐的一个具体例子 [[2506.06122]]。
- SkyRL-v0 是第三个被精读过原始来源（博客而非论文）的 Agentic RL 专用框架条目，给出了这批框架里**第一个具体的环境执行密度数字**（1+ CPU/~7GB 存储每容器、16-CPU 节点 80–100 容器）和 rollout 加速数字（4–5×），但同样没有拆分两个优化各自的贡献，且训练数据规模（约 300 条）远小于其他条目，泛化性未知 [[skyrl-v0]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- Agent Lightning 的"执行与训练解耦"架构（agent 执行 = 独立 MDP，近零代码修改接入）与我们"沙箱执行服务 + 训练循环通过异步 API 对接"的设想高度吻合，值得深入精读其论文/代码验证细节（follow-up，见 [[2509.02547]] 笔记）。
- AWorld、AgentRL 的"环境编排 + 跨集群并行 rollout"具体实现机制未在综述里展开，需要回到原始论文对比我们自己的调度系统设计。

## 相关概念

[[agentic-rl]]、[[agentic-rl-environments]]、[[hybridflow]]、[[async-rl-training]]

## 相关来源

- [[2509.02547]] — Table 11 系统盘点约 23 个 RL 训练框架，AWorld 的 14.6× 加速是本综述唯一量化的训练吞吐数字
- [[2409.19256]] — HybridFlow/veRL 原始论文，本综述里唯一被单独精读过的 RLHF/微调框架，补上了具体的架构设计与量化吞吐数字（详见 [[hybridflow]]）
- [[2505.24298]] — AReaL 原始论文，本综述里第二个被单独精读过的 Agentic RL 专用框架，补上完整异步架构细节与量化数字（详见 [[async-rl-training]]）
- [[2506.06122]] — ROLL 原始论文，阿里出品的大规模 RL 训练库，补上样本级 Rollout Scheduler、AutoDeviceMapping 设计细节与 RLVR/agentic 任务的量化提升数字，但容错/规模声明缺乏量化支撑
- [[skyrl-v0]] — SkyRL-v0 原始博客，Berkeley Sky Computing Lab，本综述里唯一被单独精读过的 SWE-Bench 长程 agent 训练系统，补上 Remote Sandbox Server 环境密度数字、异步 rollout + 三段流水线设计与 SWE-Bench-Verified 量化结果
