---
title: "Agentic RL 训练框架全景"
aliases: [agentic RL frameworks, agent RL 训练框架, harnessed agentic RL]
created: 2026-09-29
updated: 2026-09-30
sources: [2509.02547, skyrl-v0, 2511.16108, 2508.03680, 2608.17528, rllm-deepswe]
---

# Agentic RL 训练框架全景

## 一句话定义

[[2509.02547]] Table 11 对约 23 个 RL 训练代码库的分类盘点：12 个 Agentic RL 专用框架、6 个 RLHF/LLM 微调框架、5 个通用 RL 框架 [[2509.02547]]。

## 为什么对我们重要

这些框架是"训练系统与调度"这个研究方向的直接对应物——几乎每一个 Agentic RL 专用框架都把"异步执行"和"集中式环境/资源编排"列为核心特性，说明这是行业共识的架构方向，值得对照我们自己的调度系统设计逐一比较 [[2509.02547]]。

## 核心机制 / 主要变体

**Agentic RL 专用框架**（Section 5.2）：

- **Verifiers**：可验证环境设置，端到端策略优化 [[2509.02547]]。
- **rLLM**：Agentica（Berkeley Sky Computing Lab）+ Together AI 开源的 agent 后训练框架，核心卖点是把 harness、沙箱、训练后端做成三个独立可替换维度——同一份 agent 代码在 eval 和训练阶段不变，通过 Model Gateway 透明捕获 token id/logprob；训练后端可在 verl（分布式多 GPU）、tinker（单机）、fireworks 间一键切换；支持 GRPO/REINFORCE/RLOO/SFT/on-policy distillation，覆盖 60+ 基准与 10+ CLI harness（Claude Code、Codex、mini-swe-agent 等）。用 rLLM 训出的旗舰模型 **DeepSWE-Preview**（Qwen3-32B 纯 RL，无 SFT/蒸馏，训练算法见 [[grpo]] 的 GRPO++ 条目）在 SWE-Bench Verified 达 42.2% Pass@1、hybrid test-time scaling 后 59.0%，系统侧用 Kubernetes 取代原生 Docker 编排解决了单迭代 512 并发容器压垮 `dockerd` 的问题（见 [[rollout-training-disaggregation]]）。注意：[[2511.16108]] Table 1 把 rLLM 描述为"绑定单一/少数训练后端、rollout 只支持 data-parallel 一种粒度"，与本条目描述的多后端能力不一致——Table 1 对比的版本早于本文读到的 2026-09 时点 README，rLLM 显然在两者之间做了架构升级，具体版本变更节点知识库暂无记录 [[rllm-deepswe]]。
- **SkyRL-v0 → SkyRL-Agent**：长程真实世界 agent 训练 [[2509.02547]]，基于 VeRL + OpenHands 构建；用独立部署在 K8s 上的 Remote Sandbox Server 解耦环境执行（Docker/crun 容器）与训练，单 16-CPU 节点撑 80–100 容器；异步 rollout + init/run/eval 三阶段生产者-消费者流水线合计带来 4–5× rollout 生成加速；仅用 80–293 条筛选样本训练，SWE-Bench Verified 上三个模型分别提升 3.6pp、5.8pp、3.6pp [[skyrl-v0]]。后续论文化版本 **SkyRL-Agent** 把流水线升级为统一接口下的三种可配置调度策略（Async Batch / Async Batch (Bounded) / Async Pipeline，见 [[async-rl-training]]），并加上工具中心化 agent loop（无状态/改环境/改 agent 状态三类工具统一抽象，区别于 VeRL-Tool、rLLM、GEM 的 Gym 风格 `env.step` 外挂 agent 状态管理）与训练后端桥接层（transition-based 记录，可无缝切换 SkyRL-train/VeRL/Tinker）；用它训出的 SA-SWE-32B（Qwen3-32B 纯 RL）在 SWE-Bench Verified 达 39.4% Pass@1，训练成本比同数据集训练的 DeepSWE 低约 50%（4601 vs 9180 H100 小时）[[2511.16108]]。
- **AREAL**：异步、分布式架构，面向语言推理任务规模化 [[2509.02547]]。
- **MARTI**：把范式扩展到多智能体 LLM 系统，集成训练与推理 [[2509.02547]]。
- **EasyR1**：多模态支持，统一 RL 框架里融合视觉与语言信号 [[2509.02547]]。
- **AgentFly**：可扩展、可扩展的 agent-RL 框架，装饰器式工具/奖励定义 + 异步执行 + 集中式资源管理,面向高吞吐 RL 训练 [[2509.02547]]。
- **Agent Lightning**：把 agent 执行建模为 MDP（state=语义变量快照，call=组件调用），定义统一数据接口把任意执行轨迹拆成 `(input, output, reward)` transition，用分层 RL 算法 **LightningRL**（credit assignment 模块把 episode return 分配给各 action，当前实现是恒等分配，再交给 GRPO/PPO 等任意已有单轮算法处理 token 级优化）取代 turn-concatenation + masking，从而不破坏 RoPE 位置连续性、避免上下文随轮数无限拼接变长、支持多 agent 系统里选择性优化部分 agent。系统侧提出 **Training-Agent Disaggregation**：Lightning Server（跑 VeRL 等 RL 框架，按任务分发 OpenAI 兼容 API 端点）+ Lightning Client（通信模块 + Agent Runtime，复用 OpenTelemetry/AgentOps 可观测性基础设施做零代码修改的数据采集），实现"训练框架 agent-agnostic、agent trainer-agnostic"双向解耦；Client 侧还提供 Automatic Intermediate Rewarding（从工具调用返回状态等系统监控信号自动派生中间奖励）缓解稀疏奖励。三个实验任务（LangChain Text-to-SQL、OpenAI Agents SDK RAG、AutoGen 数学工具调用，均用 Llama-3.2-3B-Instruct）验证了框架通用性，但论文只给训练曲线图、未报告具体准确率提升数字，也未验证 SWE-Bench 级别长程任务规模 [[2508.03680]]。
- **Agent Lightning v1.0**：对上一条的完整重写（"a complete refactoring"，约 3500 行代码），提出并系统刻画**「harnessed agentic RL」**这个更精确的范式术语——用部署时同一套 agent harness（mini-SWE-agent、OpenHands、Claude Code、Codex 等）直接做训练，harness（而非训练引擎）拥有环境交互循环，训练引擎只能观测到离散的 LLM 调用对。论文首次系统识别并解决四个此前被现有框架（包括 verl Uni-Agent、AReaL 2.0、slime v0.3.0、Polar 这些同样采用 proxy-based 方案的框架）普遍忽视的工程挑战：retokenization/sample merging、advantage calculation（rollout-level vs sample-level）、loss normalization（token-mean/seq-mean-token-mean/rollout-level token-mean 三种公式）、training backend scheduling（详见 [[agent-rl-credit-assignment]]）。系统架构重构为 API Gateway（幂等端点）+ Rollout Controller（K8s Reconciler，标准 controller reconciliation loop）+ Customized Trainer（基于 VERL），**agent 执行改用自建 Kubernetes Job 而非 Modal Sandbox/E2B 等商业沙箱**（论文明确点名后者在 RL 训练规模下代价高昂）；另提出 **Collocated Async RL**——rollout 与权重更新共享同一 GPU 池、通过 API Gateway 准入控制做透明相位切换，相对同步 RL 约 2× 加速且比全异步用更少 GPU（见 [[rollout-training-disaggregation]]、[[async-rl-training]]）。用 Qwen3.5-9B + mini-SWE-agent 在清洗后的 SWE-smith 数据（约 6K 样本）上训练，**SWE-bench Verified 从 41.8% 提升到 56.4%**（+14.6pp），是 Agent Lightning 系列第一次给出的规模化量化验证；消融证明 advantage 计算和 loss normalization 必须同时改到 rollout 级别才有效（单独改 advantage 反而更差）[[2608.17528]]。
- **AWorld**：分布式 Agentic RL 框架，解决"经验生成"这一主瓶颈，跨集群大规模并行 rollout，**相对单机 14.6× 加速**，支撑端到端可扩展训练管线 [[2509.02547]]。
- **ROLL**：统一控制器 + 并行 worker + 自动资源映射，支撑多 GPU 稳定训练 [[2509.02547]]。
- **VerlTool**：基于 Verl 构建的工具集成 rollout 框架（ARLT），联合优化规划与执行 [[2509.02547]]。
- **AgentRL**：多轮多任务异步框架，统一环境编排，引入 cross-policy sampling 与 task advantage normalization 稳定大规模训练 [[2509.02547]]。
- **RL-Factory**：易于设计的奖励定义 [[2509.02547]]。

**RLHF/微调框架**：OpenRLHF（高性能可扩展对齐工具包）、TRL（HuggingFace 基线实现）、trlX（数百亿参数分布式微调）、HybridFlow（RLHF 实验管理与规模化）、SLiMe（Megatron+SGLang 组合的异步 RL、解耦式 reward/数据生成）、Oat（轻量 RL 支持）[[2509.02547]]。

**通用 RL 框架**：RLlib（生产级可扩展库）、Acme（模块化分布式组件）、Tianshou（纯 PyTorch 高性能平台）、Stable Baselines3（可靠 PyTorch 实现）、PFRL（原 ChainerRL，基准化原型算法）[[2509.02547]]。

## 工程要点与数字

- **框架能力对比（SkyRL-Agent 论文 Table 1）**：VeRL-Tool、rLLM、GEM、Agent-Lightning 均绑定单一/少数训练后端，rollout 执行只支持 data-parallel 一种粒度；SkyRL-Agent 声称支持 Multi 后端 + Data/Pipeline 混合调度（可扩展）、统一工具接口、Ray/K8s 运行时伸缩，是这四个对比对象里唯一同时具备"多后端 + 细粒度调度 + 统一工具接口"三项的框架——但这是作者自评对比表，未见第三方复现验证；且该表对比的是旧版 Agent Lightning，Table 1 发表时 v1.0 尚未发布 [[2511.16108]]。
- **Agent Lightning v1.0 的 SWE-bench 消融数字**：Sample-level Advantage 35.0% < Rollout-level Advantage（只改 advantage）33.1% < Rollout-level Advantage + Rollout-level Norm（advantage+loss 一起改）38.2%（验证奖励 @ step 128）；最终 checkpoint 在 SWE-bench Verified 41.8%→56.4%（+14.6pp，约 6K 训练样本）。平均每条 rollout 产生 2.41 个训练样本、只有 36% 保持单样本，证明动态样本数在真实场景里是常态而非边缘情况 [[2608.17528]]。
- **AWorld 14.6× 加速**是全文少数几个量化的工程数字之一，直接印证"rollout/环境执行吞吐是 agent RL 训练规模化的主瓶颈"这一判断，与我们平台的核心关注点（生产可跑性、成本与密度）高度一致 [[2509.02547]]。
- 除 AWorld 外，其余框架均**只给定性特性描述、无量化吞吐/成本数字**——这是本综述在工程细节上的已知缺口 [[2509.02547]]。
- 12 个 Agentic RL 专用框架里，AREAL、AgentFly、ROLL、AgentRL 都明确强调"异步执行"或"异步训练"，是这批框架的共同架构选择 [[2509.02547]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- ~~Agent Lightning 的"执行与训练解耦"架构（agent 执行 = 独立 MDP，近零代码修改接入）与我们"沙箱执行服务 + 训练循环通过异步 API 对接"的设想高度吻合，值得深入精读其论文/代码验证细节。~~ 已精读 [[2508.03680]]：确认了 MDP 形式化、LightningRL 分层算法与 Training-Agent Disaggregation（Lightning Server/Client + OpenAI-like API）的具体设计，但论文未给出量化实验结果与系统吞吐数字，规模也明显小于 SkyRL 系列。~~GitHub 仓库（microsoft/agent-lightning）里的通信协议与 AIR 默认实现细节仍待进一步确认~~ 已由 v1.0 论文部分回答 [[2608.17528]]：v1.0 是完整重写，用 API Gateway/Rollout Controller/Customized Trainer 替代了旧版模糊的 Server/Client 描述，并给出 SWE-bench Verified 规模化验证；仍待确认的是 AIR（Automatic Intermediate Rewarding）在 v1.0 里是否保留、默认实现细节需要直接查代码。
- AWorld、AgentRL 的"环境编排 + 跨集群并行 rollout"具体实现机制未在综述里展开，需要回到原始论文对比我们自己的调度系统设计。
- verl Uni-Agent、AReaL 2.0、slime v0.3.0、Polar 这几个 Agent Lightning v1.0 点名的同类 proxy-based 框架，在 retokenization/advantage/loss normalization 上的具体选择是否已有独立于 Agent Lightning 论文之外的实证对比，知识库里暂无数据，需要直接精读这几个框架的论文/文档 [[2608.17528]]。

## 相关概念

[[agentic-rl]]、[[agentic-rl-environments]]、[[agent-rl-credit-assignment]]

## 相关来源

- [[2509.02547]] — Table 11 系统盘点约 23 个 RL 训练框架，AWorld 的 14.6× 加速是本综述唯一量化的训练吞吐数字
- [[skyrl-v0]] — SkyRL-v0 原始博客，补上综述里缺失的工程细节：Remote Sandbox Server 架构、容器密度、异步流水线加速比、SWE-Bench Verified 实测提升
- [[2511.16108]] — SkyRL-v0 的论文化后继框架 SkyRL-Agent：Table 1 给出与 VeRL-Tool/rLLM/GEM/Agent-Lightning（旧版）的能力对比，用统一调度接口 + 工具中心化 agent loop + 训练后端桥接训出 SA-SWE-32B，SWE-Bench Verified 39.4% Pass@1、训练成本比 DeepSWE 低约 50%
- [[2508.03680]] — Agent Lightning 原始论文：MDP 形式化 + LightningRL 分层算法（transition 取代拼接+mask）+ Training-Agent Disaggregation 架构，三个轻量任务验证通用性但缺量化结果与系统吞吐数字
- [[2608.17528]] — Agent Lightning v1.0，完整重写版：提出「harnessed agentic RL」范式，系统刻画四个动态样本数挑战并给出具体设计选择，系统架构重构为 API Gateway/Rollout Controller/Customized Trainer，agent 执行改用自建 K8s 替代商业沙箱，提出 Collocated Async RL，SWE-bench Verified 规模化验证 41.8%→56.4%
- [[rllm-deepswe]] — rLLM 框架现状（harness/沙箱/训练后端三维解耦）+ 旗舰模型 DeepSWE-Preview 训练案例：GRPO++ 算法配方、Kubernetes 化 Docker 编排解决大规模并发容器问题、SWE-Bench Verified 42.2%→59.0%（hybrid TTS）
