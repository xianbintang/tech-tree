---
title: "SWE-Serve"
aliases: [SWE-Serve, 生产推理工程基准]
created: 2026-09-29
updated: 2026-09-29
sources: [2609.26777]
---

# SWE-Serve

## 一句话定义

面向"生产推理引擎工程"的 repo 级 agent 评测基准：53 个从 SGLang 真实合并 PR 抽取的任务，用隐藏的功能/回归/端到端（E2E）测试和校准性能门槛评分，核心贡献是把"局部测试通过"与"生产可用"之间的差距（见 [[production-correctness-gap]]）变成可量化指标 [[2609.26777]]。

## 为什么对我们重要

这是目前唯一一个把"推理服务系统的生产可用性"当作一等评测目标的 repo 级 agent 基准，任务全部来自真实合并的 SGLang PR，且专门测了持久状态、并发协调这些和沙箱/调度系统直接相关的维度。对我们判断"agent 能不能在我们的平台上产出生产可用的推理服务代码"有直接参考价值 [[2609.26777]]。

## 核心机制 / 主要变体

- 任务来源：SGLang 自 2025 年 12 月以来合并的变更，横跨六个工程家族——模型/后端支持、投机与高级解码、kernel/量化/性能、缓存与运行时状态、分布式执行与调度、服务 API 与运行时正确性 [[2609.26777]]。
- 任务粒度：37 个单 PR 任务 + 16 个跨 2–6 个相关 PR 组合的任务，共取材 83 个独立 PR，突破了"一个任务必须对应一个 PR"的边界，做法上参考了 FeatureBench、SWE-EVO 的多 PR 构造思路 [[2609.26777]]。
- 执行环境：12 个 CPU-only 任务 + 41 个单卡 H100 任务，用 [[harbor]] 统一管理沙箱执行 [[2609.26777]]。
- 评分沿用 SWE-bench 的 fail-to-pass / pass-to-pass 范式，19 个任务额外带模型服务端到端（E2E）测试，3 个任务带校准性能门槛；完整测试集合定义任务的 production correctness 要求，见 [[production-correctness-gap]] [[2609.26777]]。
- 任务标签体系：构造时（不看模型结果）就给每个任务打三个标签——runtime-domain 广度（request I/O / 调度与生命周期 / 模型执行 / KV cache 与资源管理，四域归纳自 vLLM、SGLang、TensorRT-LLM、Triton）、是否测持久状态、是否测并发协调 [[2609.26777]]。
- 资格审查漏斗：786 条来源候选 → 203 个来源候选 → 156 个任务候选 → 53 个入选（34.0% 录取率），录取要求 no-op 全挂 F2P/全过 P2P、oracle 全过，外加 agent 辅助对抗性探测和人工裁决 [[2609.26777]]。
- 闭卷评测：屏蔽公网和上游仓库检索（仅放行 Hugging Face 模型权重源），逐轨迹审计违规检索 [[2609.26777]]。
- 评测 harness：主榜单用 mini-SWE-agent（模型无关，只用 Bash），11 个模型 + 31 个模型-effort 组合；额外验证了换成模型原生 harness（Codex、Claude Code）并不会提升 pass@1 [[2609.26777]]。

## 工程要点与数字

- 最佳配置 pass@1：Claude Opus 5 与 GPT-5.6 Sol 并列 75%，最低 Inkling S 35%，40 个百分点跨度 [[2609.26777]]。
- 同为 64% pass@1 的四个配置之间，单任务均成本相差 7.6×（$0.95–$7.24），耗时相差 3.9×（25.5–99.9 分钟）[[2609.26777]]。
- oracle 补丁规模中位数 553 行 / 7 个文件（最大 6,077 行 / 35 个文件），比 [[swe-bench-pro]]、SWE-bench Verified、DeepSWE 的 oracle 补丁平均更大，但平均 prompt 比 DeepSWE、SWE-bench Pro 更短 [[2609.26777]]。
- 单任务执行上限 350 步或 210 分钟，单条命令超时 120 秒；仅因基础设施问题（而非 agent 失败）才重跑任务 [[2609.26777]]。
- 详细的"局部正确 ≠ 生产正确"数字见 [[production-correctness-gap]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 只取材 SGLang，能否推广到 vLLM/TensorRT-LLM/Triton 等其他推理系统未验证 [[2609.26777]]。
- 限定单卡 H100/纯 CPU 执行，排除了多 GPU/多节点场景（并行、disaggregation、分布式协调），而这类场景往往是生产推理系统最容易出问题的地方 [[2609.26777]]。
- 论文提到"we release the benchmark, execution environments, and verifiers"，但正文与参考文献中没有给出可点击的代码/数据发布链接，需要后续跟踪确认 [[2609.26777]]。

## 相关概念

[[production-correctness-gap]]、[[harbor]]、[[swe-bench-pro]]

## 相关来源

- [[2609.26777]] — 提出 SWE-Serve 基准本身，含完整构造方法论、11 模型评测结果与生产正确性 gap 的量化分析
