---
title: "Harbor（Terminal-Bench 团队的 agent 评测 / 环境框架）"
type: post
id: "harbor-framework"
source_url: https://github.com/harbor-framework/harbor
authors: [Harbor Framework Team]
affiliations: [Laude Institute]
published: 2025-08-04
code_url: https://github.com/harbor-framework/harbor
---

Harbor 是 Terminal-Bench 团队做的开源框架，用于在容器化沙箱里评测和优化 agent/模型（Apache-2.0 许可，2026-09-30 精读时 5,698 star / 1,889 fork，仍在活跃开发）。它把一个"任务"定义为 `instruction.md` + `task.toml` + `environment/`（Dockerfile 等）+ `solution/` + `tests/` 的自包含目录，任务本身不依赖 Harbor 框架、可被任何遵循该格式的运行器消费。Harbor 提供统一的 CLI（`harbor run`）与 `BaseEnvironment`/`BaseAgent`/`BaseInstalledAgent` 三个可扩展基类，支持数十种本地/云沙箱 provider（Docker、Daytona、Modal、E2B 等）、内置多种 agent（Claude Code、Codex CLI、OpenHands 等），并原生支持 RL rollout 生成。它同时在推进两份接口标准草案：ASP（Agent Sandbox Protocol，规范"harness ↔ 远程沙箱"的执行层协议，SSH 优先）和 ATIF（Agent Trajectory Interchange Format，统一的 agent 轨迹 JSON 格式）。是 Terminal-Bench-2.0 的官方评测 harness。

笔记：[[harbor-framework]]
