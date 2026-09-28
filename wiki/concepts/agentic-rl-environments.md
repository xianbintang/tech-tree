---
title: "Agentic RL 环境与基准全景"
aliases: [agentic RL environments, agent RL 训练环境, agentic RL benchmarks]
created: 2026-09-29
updated: 2026-09-29
sources: [2509.02547, 2511.09586]
---

# Agentic RL 环境与基准全景

## 一句话定义

[[2509.02547]] Table 10 对约 43 个开源 Agentic RL 训练环境/基准的分类盘点，按"agent 能力标签 + 任务域 + 模态"归类，覆盖 Web、GUI、代码与 SWE、领域特定、游戏、通用六大类 [[2509.02547]]。

## 为什么对我们重要

这份清单本质上是"我们沙箱平台需要覆盖哪些执行环境类型"的需求地图——每一类环境背后对应不同的隔离级别、状态管理方式和冷启动成本。逐类盘点能直接回答"我们平台目前能跑哪些、缺哪些"这个问题 [[2509.02547]]。

## 核心机制 / 主要变体

按任务域六分类（Section 5.1）：

- **Web 环境**：WebShop（模拟电商站点）、Mind2Web、WebArena / VisualwebArena（可自托管、Docker 容器交付的全功能网站集合）、AppWorld（9 个日常应用 + 457 个可调用 API 的多应用生态）。这类环境的状态**只在 agent 动作下改变**，适合"按需启动、空闲挂起"的沙箱生命周期 [[2509.02547]]。
- **GUI 环境**：AndroidWorld（真实 Android 模拟器，116 个手工任务 + 参数化生成百万级任务变体）、OSWorld（跨 Ubuntu/Windows/macOS 的真实计算机环境，涉及真实桌面应用和 OS 文件 I/O）。这类环境需要**完整操作系统**，隔离成本远高于轻量代码沙箱 [[2509.02547]]。
- **代码与 SWE 环境**：分"交互式环境"（Debug-Gym 用 Docker 容器包裹 pdb 调试器、R2E-Gym 程序化生成 8K+ 任务、TheAgentCompany 模拟软件公司长程工作流）和"基准数据集"（SWE-bench、SWE-rebench、BigCodeBench、LiveCodeBench、DevBench、ProjectEval、NoCode-bench 等），前者代码库状态可变、后者多是固定评测管线 [[2509.02547]]。
- **领域特定环境**：科研（PaperBench 复现 ICML 论文）、MLE（MLE-Dojo/MLE-Bench 基于真实 Kaggle 竞赛）、生物医学（MedAgentGym）、网络安全（SecRepoBench，27 个仓库、15 类 CWE）[[2509.02547]]。
- **模拟与游戏环境**：Crafter/Craftax（2D 开放世界生存游戏，Craftax 用 JAX 做 GPU 加速）、SMAC/SMAC-Hard（StarCraft II 多智能体协作）、**Factorio**（tick-based 工业模拟，agent 不动作时世界仍在演化——是少数"动态"环境的代表）[[2509.02547]]。
- **通用环境**：AgentGym（指令微调 + 自我纠正提升泛化）、Agentbench（跨 SQL/游戏/网页等多种场景的广谱评测框架）、InternBootcamp（1000+ 可验证推理任务，标准化 RL 训练接口）[[2509.02547]]。

## 工程要点与数字

- Table 10 共收录约 43 个环境/基准，模态分布为 Text / Text+Visual / Visual 三类 [[2509.02547]]。
- **静态 vs 动态是调度设计的关键区分**：绝大多数环境（WebArena、OSWorld 等）状态仅随 agent 动作改变，可视为"请求驱动"资源；Factorio 是明确反例——tick 制世界持续演化，需要常驻后台进程而非"空闲即挂起" [[2509.02547]]。
- 论文**未披露**各环境的具体冷启动时间、镜像大小、并发密度等我们最关心的工程数字——这是这份全景图的已知缺口，需要逐个环境回到原始仓库调研 [[2509.02547]]。
- **SWE 方向有量化的规模效应证据**：SWE-Gym-32B（2,438 任务，真实仓库）SWE-bench 解决率 20.6% → R2E-Gym-32B（8,135 任务，程序化合成）34.4% → SWE-Smith-32B（50,137 任务，真实+合成混合）40.2%——任务/轨迹规模每提升一个数量级，下游解决率显著提升，是"环境规模化"论点少有的直接量化支撑 [[2511.09586]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 逐项盘点 OSWorld / AndroidWorld / WindowsAgentArena 这类全 OS 环境的具体隔离方案，评估我们 microVM 沙箱能否覆盖，缺口在哪（follow-up，见 [[2509.02547]] 笔记）。
- 环境生成/自动化课程（而非人工预先构建）的趋势，见 [[verifiable-reward-environment-generation]]。
- 深挖 R2E-Gym / SWE-Smith 这类"程序化生成可执行 Docker 环境"的具体合成流水线（如何从 GitHub 仓库自动生成 buildable/testable 环境、规模、故障率），评估能否复用到 [[repolaunch]] 的沙箱镜像构建能力（follow-up，见 [[2511.09586]] 笔记）。

## 相关概念

[[agentic-rl]]、[[agentic-rl-frameworks]]、[[verifiable-reward-environment-generation]]、[[repolaunch]]、[[gef-loop]]

## 相关来源

- [[2509.02547]] — Table 10 系统盘点约 43 个开源 Agentic RL 环境/基准
- [[2511.09586]] — 提供 SWE 方向环境规模化的量化证据（任务/轨迹规模 vs SWE-bench 解决率），并给出 GEF loop 分类法（见 [[gef-loop]]）
