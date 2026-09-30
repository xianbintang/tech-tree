---
title: "SWE-bench Multilingual"
aliases: [SWE-bench Multilingual]
created: 2026-09-25
updated: 2026-09-30
sources: [2609.23377, 2602.23866]
---

# SWE-bench Multilingual

## 一句话定义

覆盖 9 种编程语言、共 300 个 repo-level 任务的软件工程 agent 评测基准，用于检验方法是否只对 Python 有效。

## 为什么对我们重要

我们关心的 code/SWE agent 训练方法是否有跨语言泛化能力，SWE-bench Multilingual 是目前少数直接衡量这一点的基准，值得持续跟踪其榜单变化。

## 核心机制 / 主要变体

- 共 300 个任务，覆盖 9 种编程语言，是 [[swe-bench-pro]]（纯 Python）之外检验跨语言泛化的基准 [[2609.23377]]。
- [[swe-rebench-v2]] 在其 setup synthesis 消融实验中，从 SWE-bench、SWE-bench Multilingual、Multi-SWE-Bench 三个来源抽样出覆盖 10 种语言的 103 个仓库子集，把这里的人工验证任务转成自己的 pipeline 格式当 ground truth，用来对比自动化 setup agent 与人工设置的一致性 [[2602.23866]]。

## 工程要点与数字

- [[2609.23377]] 中 Qwen3.6-27B 基础模型在该基准上基线平均解决率 56.22%，经 [[category-aware-expert-training]] + [[on-policy-distillation]]（MOPD）后提升到 59.00%（+2.78pp），提升幅度小于 [[swe-bench-pro]] 上的 +5.39pp [[2609.23377]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 跨语言场景下类别专家训练的收益明显小于纯 Python 场景（+2.78pp vs +5.39pp），是否因为类别划分（服务/数据/安全、用户面应用、系统/工具/运行时）本身是针对 Python 生态设计的，论文未讨论 [[2609.23377]]。

## 相关概念

[[swe-bench-pro]]、[[category-aware-expert-training]]、[[swe-rebench-v2]]

## 相关来源

- [[2609.23377]] — 用作跨语言泛化验证基准
- [[2602.23866]] — 抽样部分任务作为 setup synthesis 消融实验的人工验证 ground truth
