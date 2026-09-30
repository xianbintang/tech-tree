---
title: "AgentBench"
aliases: [Agentbench, AgentBench 评测框架]
created: 2026-09-30
updated: 2026-09-30
sources: [2308.03688]
---

# AgentBench

## 一句话定义

2023 年提出的首个系统性 LLM-as-Agent 多环境评测基准：8 类环境（OS/DB/知识图谱/卡牌游戏/海龟汤/家居/网购/网页浏览）覆盖 code/game/web 三种 grounding，配套一套 Docker 隔离 + Server-Client 解耦 + max-flow 调度的通用评测工具链 [[2308.03688]]。

## 为什么对我们重要

它是"异构环境统一接入"这条问题线的早期实践样本——在我们今天讨论 OpenEnv、Harbor ASP 这类环境接入标准之前，AgentBench 已经用 Docker-per-task-worker + HTTP 解耦的方式解决过"如何让评测框架同时对接多种互不兼容的执行环境"这个问题。它本身不含我们最想要的隔离开销/密度/冷启动数字，但作为历史锚点，能帮我们判断后续系统（Harbor、OpenEnv）具体在哪些能力上做了升级 [[2308.03688]]。

## 核心机制 / 主要变体

- **8 类环境、3 种 grounding**：Code-grounded（Operating System 真实 Ubuntu Docker bash 交互、Database 真实 SQL 接口、Knowledge Graph 部分可观测 KG 问答）、Game-grounded（Digital Card Game 简化卡牌对战、Lateral Thinking Puzzles 海龟汤猜谜、House-Holding 家居具身任务）、Web-grounded（Web Shopping 改编自 WebShop、Web Browsing 改编自 Mind2Web）[[2308.03688]]。
- **Decoupled Server-Client 评测框架**：Task Server（任务控制器 + Docker 隔离的 Task Worker）、Agent Server（HTTP 暴露的模型服务）、Evaluation Client 三方解耦部署，摆脱此前"必须同机部署、一次只能评一对 agent-task"的限制 [[2308.03688]]。
- **max-flow 动态调度**：把"n 个 agent × m 个任务 × 待评样本数"建模为二部图网络流问题，用 Edmonds–Karp 实现 Ford–Fulkerson 求最大流（复杂度 $O(|V||E|^2)$），周期性重跑把新增评测三元组分配给空闲 worker，支持多 agent、多任务同时协作评测 [[2308.03688]]。
- **最原始 CoT + greedy decoding 评测协议**：不引入 ensemble/reflection/search 等改进策略，temperature=0 保证可复现；用"倒数均值权重"归一化各任务分数后加权平均为 Overall Score，避免高分任务掩盖区分度 [[2308.03688]]。

## 工程要点与数字

- 29 个模型（10 API-based + 19 个 ≤70B OSS）全量评测；gpt-4 (0613) OA=4.01 排名第一，OSS 模型平均 OA 仅 0.51 vs API 模型 2.32，差距显著 [[2308.03688]]。
- 失败模式以 Task Limit Exceeded 为主导（尤其海龟汤 82.5%、知识图谱 67.9%），暴露长程推理/决策能力不足是当时 LLM agent 的核心瓶颈 [[2308.03688]]。
- **论文未披露评测框架本身的工程数字**：Docker 隔离开销、Worker 并发密度、冷启动时间、跨设备部署延迟等我们最关心的指标完全缺失——这是一篇评测方法论 + 排行榜论文，不是系统性能论文 [[2308.03688]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- AgentBench 的 Docker-per-task 隔离方案与 [[harbor]] 的 ASP 协议、[[openenv-interface-spec]] 的 ContainerProvider 相比，具体在哪些能力上（suspend/resume、动态权限收敛、安全不变量）做了升级，尚未有来源逐条对比 [[2308.03688]]。
- max-flow agent-task 调度算法能否直接复用到我们平台的批量评测/训练 rollout 调度场景，需要自己估算在实际规模下的调度开销（follow-up，见 [[2308.03688]] 笔记）。
- 同期并行工作 InterCode（Bash/SQL 交互框架）与 AgentBench 的 OS/DB 环境设计差异尚未核实，值得单独评估是否要精读。

## 相关概念

[[agentic-rl-environments]]、[[agent-execution-sandbox]]、[[harbor]]、[[openenv-interface-spec]]

## 相关来源

- [[2308.03688]] — AgentBench 原始论文：8 类环境定义、Docker+S/C 解耦评测框架、max-flow 调度算法、29 模型评测结果与失败模式分析
