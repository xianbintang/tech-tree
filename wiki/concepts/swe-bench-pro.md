---
title: "SWE-bench Pro"
aliases: [SWE-bench Pro, Pro-618]
created: 2026-09-25
updated: 2026-09-30
sources: [2609.23377, 2609.26777, 2609.32577]
---

# SWE-bench Pro

## 一句话定义

面向 repository-level 软件工程任务的评测基准，共 731 个 Python 任务；[[2609.23377]] 中使用其审计过滤后的子集 Pro-618（618 个任务）。

## 为什么对我们重要

作为 code/SWE agent 训练与评测的标准基准之一，SWE-bench Pro 的任务分布和评测方式直接影响我们判断一个训练方法是否"在生产意义上"有效。它也是 [[category-aware-expert-training]] 划分任务类别、验证"类别跷跷板"现象的具体数据基础。

## 核心机制 / 主要变体

- 全集 731 个 repo-level Python 任务；[[2609.23377]] 审计过滤后剩余 618 个，即 Pro-618（丢弃约 15%，具体过滤标准未详细披露） [[2609.23377]]。
- [[2609.23377]] 用 SWE Labeler 把 Pro-618 路由为三个操作类别：Pro-A 服务/数据/安全（221 任务）、Pro-B 用户面向应用（201 任务）、Pro-C 系统/工具/运行时（196 任务） [[2609.23377]]。
- 环境构建工具：论文用 [[repolaunch]] 搭建可执行仓库环境，验证器基于 fail-to-pass / pass-to-pass 测试 [[2609.23377]]。

## 工程要点与数字

- [[2609.23377]] 中 Qwen3.6-27B 基础模型在 Pro-618 上基线平均解决率 52.64%，经类别专家训练 + MOPD 蒸馏后提升到 58.04%（+5.39pp） [[2609.23377]]。
- [[2609.32577]] 用完整 SWE-bench Pro（非 Pro-618 子集）评测 MiMo-V2.6-Flash/Pro：Flash 纯代码 RL 上二值奖励基线在约 59% 停滞，[[groupwise-agentic-grading]] 方法持续涨到 62.5%（avg@3，step52）；工业级混合任务 RL 最终 Flash 60.9%、Pro 62.7%，Pro 超过 GPT-5.6 Sol（60.5%）但落后 Claude Opus 5 约 17.2pp（79.9%） [[2609.32577]]。

## 与 [[groupwise-agentic-grading]] 的方法关系

[[2609.32577]] 未说明是否使用了 [[2609.23377]] 的 Pro-618 审计子集还是完整 731 任务集，两篇论文都以 SWE-bench Pro 为评测基准但走的是不同技术路线（类别专家训练+蒸馏 vs 组内质量打分+advantage 重分配），彼此没有直接对比。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- Pro-618 的审计过滤标准和被丢弃的 113 个任务的分布未公开，可能影响不同工作之间的可比性 [[2609.23377]]。

## 相关概念

[[category-aware-expert-training]]、[[swe-bench-multilingual]]、[[repolaunch]]、[[swe-serve]]、[[groupwise-agentic-grading]]

## 相关来源

- [[2609.23377]] — 使用 Pro-618 子集验证类别感知专家训练 + MOPD 蒸馏的效果
- [[2609.26777]] — 作为对比基线之一；指出 [[swe-serve]] 的 oracle 补丁规模（中位数 553 行/7 个文件）比 SWE-bench Pro 更大，但平均 prompt 更短
- [[2609.32577]] — 用作代码 agent RL 的两个主评测基准之一（另一个是 DeepSWE v1.1），验证 groupwise agentic grading + sum-preserving advantage 重分配的效果
