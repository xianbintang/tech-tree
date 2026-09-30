---
title: "MiMo Code: Where Models and Agents Co-Evolve"
type: post
id: "xiaomimimo-mimo-code"
source_url: https://github.com/XiaomiMiMo/MiMo-Code
authors: [Xiaomi MiMo]
affiliations: [XiaomiMiMo]
published: 2026-09-21
code_url: https://github.com/XiaomiMiMo/MiMo-Code
---

MiMoCode 是小米 MiMo 团队开源的终端原生 AI 编程助手，基于 OpenCode fork，保留多 provider、TUI、LSP、MCP、插件等核心能力，新增持久记忆（SQLite FTS5 全文检索的项目记忆 + 会话检查点）、智能上下文管理（声称 99% 同会话 / 95% 跨会话缓存命中率）、subagent 编排、目标驱动自主循环（goal/stop condition）、"compose"规范驱动开发工作流，以及 dream/distill 自我改进机制。提供 build/plan/compose 三种内置 agent 模式，内置 20+ 技能库和四大工作流引擎（compose、deep-research、fact-check、research-experiment）。支持连接小米 MiMo Platform、OpenAI Codex、Claude Code 迁移或任意 OpenAI 兼容 API 作为模型后端。README 未给出任何 benchmark 分数，也未说明与 `XiaomiMiMo/uni-agent`（RL 训练框架）之间的直接关系。GitHub 仓库 13.6k star / 1.4k fork，MIT License + 使用限制。

笔记：[[xiaomimimo-mimo-code]]
