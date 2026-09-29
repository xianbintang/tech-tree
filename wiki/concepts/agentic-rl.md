---
title: "Agentic RL"
aliases: [Agentic Reinforcement Learning, agentic 强化学习, agent 强化学习]
created: 2026-09-29
updated: 2026-09-29
sources: [2509.02547]
---

# Agentic RL

## 一句话定义

把 LLM 从"单轮输出对齐"的静态条件生成器，重新定义为嵌入在时序展开、部分可观测环境（POMDP）中的自主决策 agent，用 RL 训练其规划、工具使用、记忆、推理、自我提升、感知等能力 [[2509.02547]]。

## 为什么对我们重要

这是"agentic RL 训练基础设施"这一研究方向的顶层概念——我们关心的沙箱、调度、训练系统工程，本质上都是为了支撑 Agentic RL 的 POMDP 展开（多轮交互、工具调用、环境状态转移）而存在的基础设施。理解这个形式化区分，能帮助判断一篇具体论文/系统是在解决"单步 MDP"式的传统 LLM RL 问题，还是真正的 Agentic RL 问题（后者才需要我们平台的沙箱/环境能力）[[2509.02547]]。

## 核心机制 / 主要变体

- **形式化区分**：传统 LLM RL（RLHF/RLAIF/DPO）是退化的单步 MDP——状态是 prompt，动作是完整 response，一步终止；Agentic RL 是时序展开的 POMDP——状态转移、观测、reward 都在多轮交互中演化，reward 可能延迟或稀疏（Section 2）[[2509.02547]]。
- **双轴分类法**：一轴按核心能力（规划 planning、工具使用 tool use、记忆 memory、推理 reasoning、自我提升 self-improvement、感知 perception，Section 3）；另一轴按应用任务域（搜索、代码与 SWE、数学、GUI 导航、视觉理解、具身交互、多智能体、其他，Section 4）[[2509.02547]]。
- **RL 的核心作用**：把上述能力从"静态启发式模块"训练成"自适应、鲁棒的 agentic 行为"，是贯穿全文的中心论点 [[2509.02547]]。
- **RL 机制之争（Section 6.4）**：一派认为 RL（尤其配合 GRPO 等 PPO 变体）本质是"放大器"——重塑采样分布、提升 pass@1，但 pass@k 边界不变（elicitation 而非 creation）；另一派认为 RL 能安装"质变的新能力"，在 OOD 泛化、诱导反思/回溯等认知行为上有实证支持。作者认为两种效应都存在，取决于奖励信号保真度、任务的组合/多步结构、以及基础模型所处的能力区间（既不接近随机也不接近饱和）[[2509.02547]]。

## 工程要点与数字

- 综述综合 500+ 篇近期工作，是目前该领域范围最广的一份全景图（截至 2026-01 刊发于 TMLR）[[2509.02547]]。
- 具体的环境/框架工程数字见 [[agentic-rl-environments]] 与 [[agentic-rl-frameworks]]。

## 争议与矛盾

- Section 6.4 的"放大器 vs 新能力来源"之争尚无定论，本综述明确标注为开放问题，不是结论性共识 [[2509.02547]]。

## 开放问题

- 可信性：RL 会放大 reward hacking、幻觉、谄媚等风险，需要沙箱级别的权限隔离作为第一道防线（Section 6.1）[[2509.02547]]。
- 环境规模化：见 [[agentic-rl-environments]] 与 [[verifiable-reward-environment-generation]]。

## 相关概念

[[agentic-rl-environments]]、[[agentic-rl-frameworks]]、[[verifiable-reward-environment-generation]]

## 相关来源

- [[2509.02547]] — 提出 Agentic RL 的 POMDP 形式化与"能力×任务域"双轴分类法，综合 500+ 篇工作
