---
title: "MiMo Code: Where Models and Agents Co-Evolve"
type: post
id: "xiaomimimo-mimo-code"
source_url: https://github.com/XiaomiMiMo/MiMo-Code
authors: [Xiaomi MiMo]
affiliations: [XiaomiMiMo]
published: 2026-09-21
created: 2026-09-30
tags: [coding-agent, agent-harness, context-management, agent-execution-sandbox]
concepts: [agent-execution-sandbox, uni-agent, agentic-token-cost, model-routing-by-task]
rating: 3
issue: 73
parent: ""
---

# MiMo Code: Where Models and Agents Co-Evolve

> 小米 MiMo 团队基于 OpenCode fork 的终端原生编程 agent：持久记忆 + 智能上下文压缩 + subagent 编排 + 目标驱动自主循环，权限模型是"越界目录触发确认提示"，可用一个危险 flag 整体跳过。

## 元信息

- 机构：Xiaomi MiMo。GitHub 仓库 `XiaomiMiMo/MiMo-Code`，13.6k star / 1.4k fork（未标注快照时间，抓取于 2026-09-30），MIT License + 使用限制条款。
- 发表：GitHub 项目，无论文，README 是唯一信息来源。
- 链接：[GitHub](https://github.com/XiaomiMiMo/MiMo-Code) · 安装：`curl -fsSL https://mimo.xiaomi.com/install | bash` 或 `npm install -g @mimo-ai/cli`
- 对比/关联基线：同属 XiaomiMiMo 组织的 [[uni-agent]]（agentic RL 训练框架）是姊妹项目，但 README 未明说两者的直接关系（见「相关」）；架构上是 OpenCode 的 fork，OpenCode 本身也出现在 [[model-routing-by-task]] 笔记的按角色路由案例里。

## 要解决的问题

终端 agent 编程助手普遍存在两个痛点：长会话里上下文迅速膨胀导致成本失控，以及每次新会话都要重新"认识"项目（无跨会话记忆）。MiMoCode 想通过持久记忆系统 + 智能上下文管理，把"模型"和"agent 框架层"做成可以互相促进演进的一体（"Where Models and Agents Co-Evolve"）。

## 方法

### 基于 OpenCode fork，叠加五类能力

原文："MiMoCode is built as a fork of OpenCode. It keeps all core OpenCode capabilities (multiple providers, TUI, LSP, MCP, plugins) and adds persistent memory, intelligent context management, subagent orchestration, goal-driven autonomous loops, compose workflows, and self-improvement via dream/distill."

- **持久记忆**：SQLite FTS5 全文检索，覆盖项目记忆（`MEMORY.md`）、会话检查点（`checkpoint.md`）、任务进度追踪。
- **智能上下文管理**：自动检查点决策 + 上下文重建，声称"up to 99% same-session and 95% cross-session cache hit rates"，可调压缩点（`/context-limit`）。
- **三种内置 agent 模式**：`build`（默认，完整工具权限）、`plan`（只读，代码探索/方案设计）、`compose`（规范驱动开发编排，`/compose-next` 走"规范→实现→验证→审查→完成"全流程）。
- **Subagent 系统**：原文"Subagents share the current session context and can work in parallel, with lifecycle tracking, cancellation, and background execution."——共享当前会话上下文、支持并行创建、生命周期追踪、取消与后台执行。
- **目标驱动自主循环**：`/goal` 设定停止条件；停止判定不是 agent 自己说了算，原文"When the agent tries to stop, an independent judge model evaluates the conversation to decide whether the condition is truly satisfied — preventing premature 'optimistic stops' during autonomous work."——用独立 judge 模型二次校验，防止"乐观提前停止"。
- **dream/distill**：`/dream` 提取持久知识，`/distill` 发现重复工作流,用于把重复经验固化成可复用资产。

### 权限模型：确认提示，而非沙箱隔离

原文明确写道，读写项目工作目录之外的文件会触发提示："reading or writing files outside the project working directory triggers an `external_directory` permission prompt"。同时提供一个整体跳过确认的 flag：`mimo --dangerously-skip-permissions`，并附警告原文："This is dangerous. With permissions bypassed, a malicious prompt, file, or plugin can run arbitrary shell commands and read, modify, or exfiltrate your data"，文档建议该模式"仅建议用于受信任的一次性环境"。**README 全文未出现 sandbox / isolation / container 字样**——这是一个基于交互式确认（越界目录才提示）的权限模型，不是 OS/容器级隔离，与 [[agent-execution-sandbox]] 笔记里 nono/E2B/Anthropic sandbox-runtime 的内核级隔离是完全不同的安全等级。

### 模型接入

支持小米 MiMo Platform（OAuth）、OpenAI Codex（OAuth）、Claude Code 迁移、任意 OpenAI 兼容 API 四种方式接入模型后端；Desktop Beta 版本额外提供"智能编排（动态模型/框架选择）"，但具体路由逻辑 README 未展开。

## 实验与结果

**README 未给出任何 benchmark 分数或第三方评测**（与同组织的 [[uni-agent]] 至少提供了自报表格不同）。唯一的量化说法是上下文缓存命中率"99% same-session / 95% cross-session"，没有测量方法论、样本规模或统计口径,应视为厂商自报的定性宣传,不是可复现基准。

## 局限与疑点

- 缓存命中率数字缺乏方法论说明，参照 [[agentic-token-cost]] 笔记对"5–30 倍 token 放大"类厂商自报数字的处理方式，这里同样应存疑、不直接采信。
- 权限模型是"越界目录才提示 + 可整体跳过"的交互式确认,而非隔离——`--dangerously-skip-permissions` 模式下,一旦 prompt/文件/插件被投毒,可以执行任意 shell 命令并读写外泄数据,这是文档自己承认的风险,但没有给出除"只在受信任一次性环境使用"之外的缓解建议(如网络 allowlist、只读挂载等)。
- Subagent"后台执行 + 生命周期追踪"具体的并发上限、资源隔离方式（是否共享同一 workspace、是否有并发写冲突保护）README 未披露。
- 与 [[uni-agent]] 的关系全靠猜测：两者同属 XiaomiMiMo 组织、时间上前后脚开源（uni-agent fork 于 2026-09-21，MiMoCode 同期），但 README 互相都没有引用对方，无法确认是否有共享的模型/数据管线。

## 对我们的启发

- **"越界目录才触发确认"的权限模型，是沙箱能力谱系里比"静态二元隔离"更弱的一档**：nono/E2B/Anthropic sandbox-runtime（见 [[agent-execution-sandbox]]）好歹在内核/进程层面划了执行边界，MiMoCode 默认是"在项目目录内什么都能跑，出了目录才问一句"，且有一键跳过全部确认的 flag。如果我们平台要支持类似 MiMoCode 这种"终端原生、直接改宿主文件系统"的编程 agent 产品接入，需要明确告诉客户/团队：这类工具默认不提供沙箱级别的 blast-radius 控制，要隔离必须自己在外面包一层（容器、microVM 或至少只读挂载敏感目录）。
- **"目标驱动自主循环 + 独立 judge 模型做停止判定"值得关注**：这解决的是"agent 会不会在没真正完成时就自称完成"的问题，如果我们平台未来要支持长时间无人值守的 agent 任务（对应我们研究方向里的"长程、有状态 session"），这种"执行者和终止判定者分离"的模式可以作为验证/终止逻辑设计的参考，避免单一模型自我报告完成状态。
- **subagent"并行 + 生命周期追踪 + 取消 + 后台执行"这组能力，本质是一个轻量级的进程/任务调度需求**：即便运行在单机终端场景，这四个能力（并发创建、追踪、取消、后台）和我们平台面向沙箱 session 的调度需求是同构的，只是规模从"单机几个 subagent"到"集群数千并发 session"。可以把 MiMoCode 当作"调度需求最小化版本"的参考样本，对照检查我们自己的 session 调度接口是否覆盖了这四类基本操作。
- Follow-up 建议（可转 issue）：
  1. 找 MiMoCode 的 `external_directory` 权限提示与 `--dangerously-skip-permissions` 的具体实现代码，核实它是纯 CLI 层拦截还是有更底层的钩子，评估能否在此基础上外挂一层轻量沙箱（不改造整个工具）；
  2. 核实 `XiaomiMiMo/uni-agent` 与 `XiaomiMiMo/MiMo-Code` 是否共享同一套模型/训练管线（例如 MiMo-Code 里跑的模型是否用 uni-agent 训练），需要看小米官方博客或论文而非仓库 README；
  3. 99%/95% 缓存命中率的宣传数字，找是否有独立评测或作者后续公开的方法论说明，判断是否可以作为我们自己上下文缓存策略的参考基准。

## 相关

- 相关概念：[[agent-execution-sandbox]]、[[uni-agent]]、[[agentic-token-cost]]、[[model-routing-by-task]]
- 相关笔记：[[xiaomimimo-uni-agent]]（同组织的 RL 训练框架，与本项目关系未在双方 README 中说明，仅并列参考）
