---
title: "GRPO"
aliases: [Group Relative Policy Optimization, 组相对策略优化, group-relative advantage]
created: 2026-09-29
updated: 2026-09-29
sources: [2609.25463]
---

# GRPO

## 一句话定义

一种不需要学习 critic 的策略优化方法：对同一 prompt 采样 $G$ 个轨迹组成一组，advantage 相对组内其他样本的奖励均值/标准差标准化，而不是像 PPO 那样用学习出的 value 函数估计 [[2609.25463]]。

## 为什么对我们重要

GRPO 是当前 reasoning RL（DeepSeek-R1、Kimi k1.5 等）事实上的默认训练算法，它的"组"结构直接决定了 rollout 的批处理粒度——一次要为同一个 prompt 生成 $G$ 个完成，这对我们的调度系统意味着"任务"的最小可调度单元往往是"一组同 prompt 的 $G$ 条轨迹"而不是单条轨迹，很多 [[rollout-efficiency]] 的调度/投机解码方法（如利用组内 sibling 相关性做草稿）都是基于这个结构设计的。

## 核心机制 / 主要变体

- **Advantage 公式**：$\hat{A}_i^{(g)} = \big(r(x_i, y_i^{(g)}) - \mu_{r,i}\big) / (\sigma_{r,i} + \epsilon)$，$\mu_{r,i}$、$\sigma_{r,i}$ 是 prompt $i$ 组内的奖励均值和标准差 [[2609.25463]]。
- **退化组（degenerate group）**：如果组内所有完成拿到相同奖励，$\sigma_{r,i}=0$，整组 advantage 全部归零——但生成和评估这一组的成本已经付出。退化概率 $P_{deg}(p,G) = p^G + (1-p)^G$，在 $p=1/2$ 时最小，$p\to0$ 或 $p\to1$ 时趋近 1。例如 $G=8$、$p=0.9$（策略十次能解对九次）时 $P_{deg}\approx0.43$；$p=0.95$ 时升到 $\approx0.66$，意味着该 prompt 三分之二的组毫无学习信号 [[2609.25463]]。
- **重要性比值 $\rho$**：PPO 式目标里用 $\rho_{i,t}^{(g)}(\theta) = \pi_\theta(y_{i,t}^{(g)}|\dots)/\pi_{\theta_{old}}(y_{i,t}^{(g)}|\dots)$ 衡量当前策略与生成该轨迹时的策略之间的差异；$\rho=1$ 即完全 on-policy，$\rho\ne1$ 意味着数据存在策略滞后（policy lag），是 [[async-rl-training]] 需要 staleness 修正的根源 [[2609.25463]]。
- **DAPO 动态采样**：面对退化组问题的参考做法——过采样 prompt，丢弃退化组，持续采样直到批次里凑够足够的非退化组；正确但随着策略变强（$p$ 向两端移动）rollout 成本会持续增长，这正是 [[rollout-efficiency]] 里 Rollout Selection 与 Prompt Filtering 两个算法杠杆家族存在的直接动机 [[2609.25463]]。
- **放宽 lag 容忍度的变体**：VCPO 通过按有效样本量缩放学习率，报告 lag 到 128 步仍稳定；$\mu$-GRPO 用放松的 clipping 和负 advantage veto 容忍多阶段 staleness；FlashREINFORCE、SAO 直接去掉组结构，改用单条 rollout + batch-mean 或 value-model baseline [[2609.25463]]。

## 工程要点与数字

- 组大小 $G$、成功概率 $p$ 共同决定退化概率，是设计 rollout 预算分配时的关键变量——$p$ 是"prompt-策略对"的属性，会随训练进程漂移，不是 prompt 的固有属性 [[2609.25463]]。
- 具体数值参见上方"核心机制"小节中 $G=8$ 时的例子；论文未给出更大规模 $G$（如 16、32、64）下的系统性 $P_{deg}$ 曲线，是可以自己补的简单计算。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 如何在训练中在线、低成本地估计 prompt 的成功概率 $p$ 及其漂移，而不是依赖静态先验或过采样——[[2609.25463]] 指出这方面只有 KGPS 显式建模了漂移，其余估计器未在同一工作负载上比较过。

## 相关概念

[[rollout-efficiency]]、[[async-rl-training]]

## 相关来源

- [[2609.25463]] — 详细推导退化组概率公式，并把它作为算法杠杆两大技术家族（rollout selection、prompt filtering）存在的根本动机
