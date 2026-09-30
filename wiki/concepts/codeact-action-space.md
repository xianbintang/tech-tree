---
title: "CodeAct：代码即动作空间"
aliases: [CodeAct, code-as-action, unified code action space, 代码即动作, agent-computer interface, ACI]
created: 2026-09-30
updated: 2026-09-30
sources: [2407.16741]
---

# CodeAct：代码即动作空间

## 一句话定义

让 agent 的动作空间统一为"可执行代码/命令"（bash、Python/IPython、或某种 DSL），而不是为每个工具单独定义 JSON function-calling schema——工具调用、状态保持、组合逻辑都通过代码本身表达，agent 甚至能现场写代码自造新工具。

## 为什么对我们重要

这是我们做沙箱/调度平台时要对外暴露的"agent-runtime 交互协议"的候选设计范式之一。如果我们的平台要给不同来源的 agent 提供统一的执行接口，CodeAct 这种"REST API 背后跑持久化 bash/IPython/browser 会话"的模式，比逐工具定义 schema 的 function-calling 方案更省维护成本、更容易适配新场景——直接决定了我们沙箱要暴露的最小接口集合应该是什么。

## 核心机制 / 主要变体

- **三类核心动作覆盖软件工程/数据分析/Web 任务**：[[2407.16741]]（OpenHands）用 `CmdRunAction`（bash）、`IPythonRunCellAction`（Python）、`BrowserInteractiveAction`（浏览器，DSL 来自 BrowserGym）这三个动作原语，声称足够覆盖人类软件工程师和分析师能做的绝大多数任务。
- **与 JSON function-calling 的关系是互补而非替代**：OpenHands 的设计兼容传统工具调用——用户可以用 PL（Python 等）写好函数，再包装成 JSON-style function-calling 体验暴露给 agent；核心论点是 PL 原语更通用，能表达 function-calling 表达不了的组合逻辑（循环、条件、中间变量复用）[[2407.16741]]。
- **Agent-Computer Interface（ACI）扩展哲学**：工具库（OpenHands 里叫 AgentSkills）只在两种情况下新增工具——(1) LLM 靠直接写代码做不到的操作（如按行精确编辑文件），(2) 需要调用外部模型（如语音转文字）——明确不重新教 agent 它已经会用的标准库（如 pandas）[[2407.16741]]。这一设计哲学继承自 SWE-Agent 提出的 ACI 概念（文件编辑工具 `edit_file`/`scroll_up`/`scroll_down` 直接改编自 SWE-Agent 和 Aider）。
- **执行侧落地为沙箱内持久化会话**：代码动作不是一次性 eval，而是在沙箱容器内维护持久化的 bash shell 和 Jupyter IPython kernel，变量/工作目录状态跨多轮动作保留，通过 REST API 与外部 event stream 通信，详见 [[agent-execution-sandbox]] 的 OpenHands 变体 [[2407.16741]]。

## 工程要点与数字

- 目前知识库内只有 OpenHands 一个具体实现的数字：SWE-Bench Lite（300 实例）用 CodeAct 动作空间 + claude-3.5-sonnet 达 26.0% 解决率，单实例均成本 $1.10（2024 年中定价）[[2407.16741]]。
- 论文没有给出"CodeAct 动作空间 vs. 纯 JSON function-calling"在相同任务、相同底座模型下的直接消融对比，"更通用/更省维护成本"目前是设计论点而非实测结论。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源引用了 CodeAct 范式；原始 CodeAct 论文（Wang et al. 2024a）本身尚未精读，待补充第一手数据）

## 开放问题

- CodeAct 式持久化代码执行会话相对 stateless JSON function-calling，在沙箱资源占用（内存驻留、清理复杂度）上的代价未被量化——这是我们评估要不要把它作为平台默认协议时需要自己补的数据。
- 代码执行动作空间对 agent 训练（RL rollout）的影响未讨论：持久化状态是否会让 rollout 的环境重置/快照恢复更复杂，值得关注 [[microvm-snapshot-uniqueness]]、[[agentic-rollout-preemption]] 相关笔记后续对照。

## 相关概念

[[agent-execution-sandbox]]、[[agent-session-sandbox-isolation]]

## 相关来源

- [[2407.16741]] — OpenHands：CodeAct 动作空间的具体开源实现（三类核心动作 + AgentSkills 工具库扩展哲学），给出 SWE-Bench/WebArena 等 15 个基准的评测数字
