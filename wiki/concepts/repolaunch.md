---
title: "RepoLaunch"
aliases: [RepoLaunch]
created: 2026-09-25
updated: 2026-09-25
sources: [2609.23377]
---

# RepoLaunch

## 一句话定义

[[2609.23377]] 中用于搭建 repo-level 可执行仓库环境的工具，配合 fail-to-pass / pass-to-pass 测试做验证器，是 SWE agent 可执行任务构建流程的一环。

## 为什么对我们重要

repo-level 可执行环境的构建（拉取仓库、装依赖、跑测试）直接对应我们沙箱平台需要提供的能力：镜像分发、依赖安装的冷启动开销、隔离与并发密度。RepoLaunch 是这类工具的一个具体样本，值得跟进它的实现细节，与我们自己的沙箱方案对标。

## 核心机制 / 主要变体

- 用于构建 repo-level 任务的可执行环境（Section 4.1）[[2609.23377]]。
- 验证器基于 fail-to-pass（修复前失败、修复后通过）和 pass-to-pass（不应被破坏的既有测试）两类测试信号 [[2609.23377]]。
- 配合"反 reward hacking"完整性检查协议，防止策略通过篡改测试等方式骗取奖励（Section 5.7）[[2609.23377]]。

## 工程要点与数字

- 论文未披露 RepoLaunch 的具体架构、镜像分发机制、单任务环境构建耗时等工程细节——这是一个待补充的调研点 [[2609.23377]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- RepoLaunch 的环境构建成本（尤其是在 [[category-aware-expert-training]] 的 RRE 循环需要频繁批量重估的场景下）是否是训练吞吐的瓶颈，论文未量化，值得后续调研。

## 相关概念

[[category-aware-expert-training]]、[[swe-bench-pro]]

## 相关来源

- [[2609.23377]] — 使用 RepoLaunch 构建可执行任务环境，作为 Agentic RL 训练和验证的基础设施
