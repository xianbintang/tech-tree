---
title: "Uni-Agent"
aliases: [Uni-Agent Gateway, verl-project/uni-agent, XiaomiMiMo/uni-agent]
created: 2026-09-30
updated: 2026-09-30
sources: [xiaomimimo-uni-agent, xiaomimimo-mimo-code]
---

# Uni-Agent

## 一句话定义

开源的长程 agent 训练框架：用一个 OpenAI/Anthropic 兼容的 Gateway 把任意已有 agent harness（Claude Code、Mini-SWE-Agent……）接入 RL 训练，用 Agent/Tool/Task/Sandbox 四个抽象统一管理数千并发、长程、有状态的 agent session，沙箱后端可插拔（local/Docker/veFaaS/Modal/OpenYuanrong）[[xiaomimimo-uni-agent]]。

## 为什么对我们重要

这是一个"训练系统 + 沙箱基础设施"合一的具体样本，直接对应我们研究方向里"agentic RL 训练基础设施"和"沙箱与执行环境"两个焦点：它的 Gateway 接入模式回答了"如何低成本支持多种 agent harness"，它的可插拔 `SandboxConfig` 回答了"如何在本地容器与多家云 serverless 沙箱之间切换"——两者都是我们自己平台需要给出答案的设计问题 [[xiaomimimo-uni-agent]]。

## 核心机制 / 主要变体

- **Gateway 接入**：harness 只需把模型 endpoint 指向 Uni-Agent Gateway（OpenAI/Anthropic 兼容协议），无需为接入训练改造 harness 本身；Gateway 负责把请求/响应转成训练用的 token 序列（"request string in, training tokens out"）[[xiaomimimo-uni-agent]]。
- **四个可复用抽象**：`Agent`、`Tool`、`Task`、`Sandbox` 独立定制，复用同一套评测与训练 runtime [[xiaomimimo-uni-agent]]。
- **规模化执行**：分布式 worker + 池化 Gateway session + 隔离沙箱 + 异步调度，支持 1,000+ 长程、有状态 session 并发，每条 trajectory/日志/reward 正确关联回对应 session [[xiaomimimo-uni-agent]]。
- **集成 [[harbor]]** 作为额外任务格式，Harbor 覆盖的任务可直接跑在 Uni-Agent 推理管线上 [[xiaomimimo-uni-agent]]。
- **五种可插拔沙箱后端**（`SandboxConfig(provider=...)`，懒加载 SDK）：
  - `local`——宿主机直接执行，**非沙箱**，文档明确禁止用于需要隔离的任务；
  - `docker`——本地容器隔离，`pull_timeout`/`start_timeout` 分别限制镜像拉取与容器启动两个阶段；
  - `vefaas`（Volcengine FaaS）——远程弹性沙箱，支持多 function id/route 列表做负载分散；
  - `modal`——远程 serverless 沙箱；
  - `openyuanrong`——远程/自建弹性沙箱，支持 CPU/内存 request-limit、`idle_timeout`、镜像挂载、反向隧道回连本地 Gateway、端口转发 [[xiaomimimo-uni-agent]]。
- **RL 训练**：与推理复用同一交互栈，全异步（fully async）训练 recipe，[[grpo|GRPO]]/GSPO 类目标 + partial rollout 支持 [[xiaomimimo-uni-agent]]。

## 工程要点与数字

- **推理/评测分数（README 自报表格）**：SWE-Bench Verified 最高 64.2%（ReAct + Qwen3-Coder-480B，500 turns/256K）；[[swe-bench-multilingual]] 35.0%（ReAct + Qwen3-Coder-30B，200 turns/128K）；Terminal-Bench v2.1 最高 67.4%（Claude Code + GLM5.2-733B，256K）[[xiaomimimo-uni-agent]]。
- **RL 训练提升（Base → RL，README 自报）**：Qwen3-30B-A3B 在 R2E-Gym 上 22.2 → 36.8（Fully Async, 100 turns, 128K）；Qwen3-Coder-30B-A3B 在 SWE-reBench 上 Claude Code harness 下 40.2 → 46.2（Colocate Async, 200 turns, 128K）[[xiaomimimo-uni-agent]]。
- 以上分数均为项目自报，**未见第三方复现或方差数据**，各行的 turns/context window 设置不统一，横向比较需谨慎 [[xiaomimimo-uni-agent]]。
- Docker 后端把镜像拉取与容器启动拆成两段独立超时预算（`SANDBOX_STARTUP_TIMEOUT` 默认 600s 同时约束两者，`pull_timeout` 可单独把拉取预算切出来），避免慢镜像仓库拖垮整个启动预算——是一个可直接参考的冷启动预算设计 [[xiaomimimo-uni-agent]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- veFaaS、Modal、OpenYuanrong 三个远程沙箱后端的冷启动延迟、并发密度、超卖能力，文档完全没有给出实测数字，需要单独调研，可与 [[agent-execution-sandbox]] 里 nono/E2B/Anthropic sandbox-runtime 的对比放在一起看 [[xiaomimimo-uni-agent]]。
- README 自报的 benchmark 表格缺少重复次数、方差、第三方审计信息，可信度需要通过读文档站的详细 benchmark 页面进一步核实 [[xiaomimimo-uni-agent]]。
- 同属 XiaomiMiMo 组织、几乎同期开源的终端编程 agent **MiMo Code** 是否与 Uni-Agent 共享模型/训练管线（例如 MiMo Code 内置模型是否用 Uni-Agent 训出），两者 README 互不引用，无法确认，需要找官方博客或论文核实 [[xiaomimimo-mimo-code]]。

## 相关概念

[[agentic-rl-frameworks]]、[[agent-execution-sandbox]]、[[harbor]]、[[swe-bench-multilingual]]、[[grpo]]、[[async-rl-training]]

## 相关来源

- [[xiaomimimo-uni-agent]] — Uni-Agent 项目 README + 文档站，本页全部事实的唯一来源
