---
title: "SkyRL-v0: Train Real-World Long-Horizon Agents via Reinforcement Learning"
type: post
id: "skyrl-v0"
source_url: https://novasky-ai.notion.site/skyrl-v0
authors: [Shiyi Cao, Sumanth Hegde, Dacheng Li, Tyler Griggs, Shu Liu, Eric Tang, Jiayi Pan, Xingyao Wang, Akshay Malik, Kourosh Hakhamaneshi, Richard Liaw, Philipp Moritz, Matei Zaharia, Joseph E. Gonzalez, Ion Stoica]
affiliations: [UC Berkeley (Sky Computing Lab), Anyscale, All Hands AI]
published: 2026-05-06
created: 2026-09-30
tags: [agentic-rl, swe-bench, rollout-efficiency, sandbox-infra]
concepts: [agentic-rl-frameworks, hybridflow, agentic-rl-environments, rollout-training-disaggregation, rollout-efficiency, async-rl-training]
rating: 4
issue: 72
---

# SkyRL-v0: Train Real-World Long-Horizon Agents via Reinforcement Learning

> Berkeley Sky Computing Lab 的博客：基于 [[hybridflow|VeRL]] + OpenHands 搭出面向 SWE-Bench 的长程 agentic RL 训练管线，用约 300 条数据把三个模型系列在 SWE-Bench-Verified 上都跑出提升。

## 元信息

UC Berkeley Sky Computing Lab / Anyscale / All Hands AI（Shiyi Cao, Sumanth Hegde, Dacheng Li 等）/ 2026-05-06 / [原文](https://novasky-ai.notion.site/skyrl-v0) · [Github](https://github.com/NovaSky-AI/SkyRL)

对比基线：单轮/短程 agentic RL 框架 Search-R1、ToRL、RAGEN、ReTool（交互步数有限，多是搜索/单次代码执行）；底座框架 [[hybridflow|VeRL]]（训练算法）+ OpenHands CodeAct（agent scaffold）。

## 要解决的问题

已有的 agentic RL 框架大多针对**无状态、短程**交互（搜索增强推理、单次代码执行）。而 SWE-Bench 这类真实世界任务需要**有状态、动态环境里的长程规划**：模型要调用多个工具、写测试、根据环境反馈调整、执行 20–50+ 轮的完整流程。这对训练基础设施提出两个新挑战：(1) 环境执行必须能规模化，(2) rollout 阶段本身就很贵（多轮 + 环境交互耗时不均），二者叠加让问题复杂度比训练搜索/代码这类短程 tool-use LLM 高出一个量级。

## 方法

在 OpenHands 的 CodeAct agent 抽象之上、以 [[hybridflow|VeRL]] 为训练底座，SkyRL-v0 主要解决两个系统问题：

**挑战一：环境规模化——Remote Sandbox Server**

SWE-Bench 式任务每个 rollout 都要在隔离、有状态的环境（通常是 Docker 容器）里跑，单个环境消耗 1+ CPU、约 7GB 存储；即使中等配置（batch size 16、8 条 rollout）也要 100+ CPU、接近 1TB 磁盘。把环境执行和训练协同部署（co-locate）会限制并行环境数量的伸缩性，导致 LLM 推理引擎收不到足够请求、GPU 利用率下降。SkyRL 因此把环境执行从训练进程里**拆出来**，做成一个独立的可伸缩 Remote Sandbox Server：部署在 Kubernetes 上，用存储优化实例缓存容器镜像加速冷启动，用 [aiodocker](https://aiodocker.readthedocs.io/en/latest/) + [crun](https://github.com/containers/crun)（轻量高性能容器运行时）处理并发请求，单个 16-CPU 节点可稳定运行约 80–100 个容器。这与 [[rollout-training-disaggregation]] 里 AWS EKS 博客"用中断容忍度拆分资源池"的思路同构，只是这里拆的是**环境执行 vs 训练**这条线，而不是 rollout-GPU vs training-GPU。

**挑战二：生成阶段的高开销——异步 rollout + 三段流水线**

常见的 rollout 实现（如 VeRL、OpenRLHF 里单轮 RL 用的方式）在 agentic 多轮场景下效率很低：每一步 LLM 生成都有同步屏障（依赖离线批生成），无法利用现代推理引擎的 continuous batching。SkyRL 用两个优化叠加取得 **4–5× 加速**（相对朴素基线实现）：

1. **异步 rollout**：依赖 SGLang / vLLM 等现代推理引擎的 `async_generate` 接口，每条轨迹独立推进，去掉跨轨迹的全局同步点。
2. **三段生产者-消费者流水线**：把 (i) 运行时初始化（构建镜像、启动/连接容器）、(ii) 轨迹生成、(iii) 奖励计算（发 patch、跑测试）三个阶段解耦并重叠，用 `init_queue`→`run_queue`→`eval_queue` 三个有界队列串联，用 asyncio 任务按队列占用动态伸缩，天然提供背压防止过载。这是一个把"环境交互密集"和"计算密集"两类工作重叠起来榨干 GPU 利用率的具体调度实现。

**Rollout 生成与奖励设计**：沿用 OpenHands CodeAct 框架，模型每轮从三种动作里选择——`execute_bash`（执行命令）、`finish`（结束交互）、`str_replace_editor`（查看/创建/编辑文件），OpenHands 维护交互历史直到模型 `finish` 或达到轮数上限，最终从环境里取出模型写的 git patch。奖励是简单的结果奖励：patch 应用到原始代码库、跑目标 GitHub issue 的测试套件，通过则 reward=1，否则 0。同时追踪两种失败模式："卡循环"（连续 3 轮重复同一动作）和"没有 finish 动作"（轮数预算内未终止）。

**数据选择**：直接用 SWE-Gym 的 2,438 个真实 Python 任务训练弱模型（如 7B）会因为一次成功 rollout 都拿不到（GPT-4o 在 SWE-Gym 上成功率也仅 4.55%–9.13%）而导致 GRPO/PPO 训练崩溃——没有学习信号。SkyRL 用"目标模型能否生成至少一次成功 rollout"过滤出三个递增难度的子集：80 条（OpenHands-7B-Agent 16 次采样出 1 次成功）、220 条（OpenHands-32B-Agent 同标准）、293 条（GPT-4o 或 Claude-3.5-Sonnet 能答对，来自 SWE-Gym 原始标注）。

## 实验与结果

三个不同规模/底座模型在 SWE-Bench-Verified 上的提升（评测用 OpenHands scaffold + CodeAct Agent，同一套动作集，最大轮数预算 50，最大序列长度 32k）：

| 模型 | 底座 | 训练前 → 训练后 |
| --- | --- | --- |
| SkyRL-Agent-7B-v0 | OpenHands-7B-Agent（Qwen2.5-Coder-7B-Instruct） | 11.0% → 14.6% |
| SkyRL-Agent-8B-v0 | Qwen3-8B（非思考模式） | 3.6% → 9.4% |
| SkyRL-Agent-14B-v0 | Qwen3-14B（思考模式） | 18.0% → 21.6% |

三个系列全部只用了对应过滤子集（80/220/293 条）就跑出正向提升。**成本/吞吐**：异步 rollout + 三段流水线合计 4–5× 加速（未拆分两个优化各自的贡献）；单容器 1+ CPU / ~7GB 存储，16-CPU 节点承载 80–100 容器。作者未给出解耦两个优化各自贡献多少加速、也未给出 Remote Sandbox Server 的冷启动延迟或故障恢复时间等具体数字。

## 局限与疑点

- 这是一篇厂商/实验室博客，不是同行评审论文，长程 RL 算法本身（如何处理长轨迹的 credit assignment、advantage 估计）明确写"不是本文重点"，只谈基础设施。
- 训练数据经过"目标模型能采出至少一次成功"过滤，存在幸存者偏差——被过滤掉的、模型完全无法成功的任务在这套方案下如何学习没有讨论。
- 4–5× 加速是两个优化叠加的总数，没有消融拆分异步 rollout 和三段流水线各自的贡献，无法判断哪个优化更关键。
- v0 只支持 SWE-Bench 这一种长程任务，WebArena、WebDev 等其他长程环境"计划中"但未验证——crun/aiodocker+K8s 这套方案能否直接搬到需要浏览器/GUI 而非纯代码沙箱的环境未知。
- 没有给出 Remote Sandbox Server 的成本数字（按容器数/时长计费、Spot 是否可用、镜像缓存命中率等），比 [[rollout-training-disaggregation]] 里 AWS EKS 博客的信息量更少。

## 对我们的启发

1. **具体的容器密度数字直接补上了知识库里的一个空白**：[[agentic-rl-environments]] 此前标注"论文未披露各环境的具体冷启动时间、镜像大小、并发密度"，SkyRL 给出了 SWE-Bench 场景下第一手的密度参考——单容器 1+ CPU / ~7GB 存储，16-CPU 节点承载 80–100 容器（crun + aiodocker）。这是我们规划 SWE 类沙箱密度时可以对标的具体基准点，值得实测复现验证是否适用于我们自己的容器运行时。
2. **Remote Sandbox Server 是"环境执行与训练解耦"的第二个具体案例**，和 [[rollout-training-disaggregation]] 里 AWS EKS 的 Spot rollout / 稳定 training 资源池拆分是同一设计哲学（按中断容忍度/资源特性拆分资源池）在不同粒度上的应用——一个拆的是 GPU rollout vs GPU training，一个拆的是 CPU 环境执行 vs GPU 训练。两者可以叠加：我们做沙箱平台时，环境执行本身也应该是可以独立于训练弹性伸缩的一层。
3. **三段生产者-消费者流水线（init/run/eval 三队列 + 有界背压）是一个可以直接搬进我们自己调度器的具体模式**：把"环境初始化（慢、依赖镜像/网络）"、"轨迹生成（GPU 密集）"、"奖励评估（跑测试，CPU 密集）"三个异构负载解耦重叠，而不是简单串行等待，是我们做 agentic RL 训练配套调度时可以直接复用的设计。
4. **crun 相对 runc 的性能选择**值得单独跟进——SkyRL 特意提到用 crun 而非更常见的 runc 来提升并发容器的轻量化和性能，如果我们的沙箱平台还在用 runc，这是一个具体的可验证的优化点（follow-up：调研 crun vs runc/gVisor 在我们负载下的启动延迟与密度差异）。
5. **可执行的 follow-up**：(a) 复现/验证 80–100 容器/16-CPU 节点的密度数字在我们自己的镜像和工作负载下是否成立；(b) 评估把三段流水线模式（init/run/eval 队列）引入我们现有的沙箱调度层；(c) 跟踪 SkyRL 后续版本扩展到 WebArena/WebDev 后，环境类型从纯代码沙箱扩展到 GUI/浏览器沙箱时，Remote Sandbox Server 架构有没有变化。

## 相关

- 相关概念：[[agentic-rl-frameworks]]、[[hybridflow]]、[[agentic-rl-environments]]、[[rollout-training-disaggregation]]、[[rollout-efficiency]]、[[async-rl-training]]
- 相关笔记：（暂无同主题笔记，issue #72 阅读清单内的独立条目，无指定母论文）
