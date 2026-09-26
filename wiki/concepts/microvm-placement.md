---
title: "MicroVM Placement / 放置调度"
aliases: [microVM placement, VM placement, uVM 放置, 沙箱放置调度, PAR 峰均比]
created: 2026-09-26
updated: 2026-09-26
sources: [2021-balaji-fireplace, brooker-ten-years-of-lambda]
---

# MicroVM Placement / 放置调度

## 一句话定义

把每个到达的 microVM（如 Firecracker µVM）在线分配到某台物理机（PM）上，目标是在不违反单机资源上限的前提下，让机群整体的峰均比（PAR）最小，从而缩小机群规模、降本；一旦放置就不能迁移，且资源用量随时间变化、到达顺序不可控。

## 为什么对我们重要

这几乎就是我们沙箱调度器要解决的核心问题：agent 沙箱（不管是 microVM、容器还是安全容器）也是在线到达、生命周期不确定、资源用量随时间变化，放置决策直接决定了我们能在同样物理资源上跑多高的并发密度（超卖能力）。[[2021-balaji-fireplace]] 是目前知识库里第一篇把这个问题在生产 Lambda 流量上系统化建模的论文，其问题建模（PAR 指标、预测无关的立场、power-of-K-choices 降维）可以直接作为我们自己设计放置调度器时的参照系。

## 核心机制 / 主要变体

- **问题本质**：多维（CPU、内存）、时变的在线 bin packing，NP-complete、≥2 维时 APX-hard；不能迁移、不能预知到达顺序，是比经典 VM 迁移场景（资源用量变化慢、可以用 EWMA 之类做预测）更难的设定，因为 µVM 生命周期短、用量 spiky [[2021-balaji-fireplace]]。
- **PAR（Peak-to-Average Ratio）目标函数**：奖励定义为 $R_t = \frac{1}{|P|}\sum_p \frac{\max_{t\in\tau}C_t^p}{\max_{p,t}C^p} - W_t$（式 1，CPU 单维），鼓励让各 PM 的峰值用量趋同、同时用 $W_t$ 惩罚放置到会超限的 PM。CPU+内存二维版本把两项归一化相加（式 2）[[2021-balaji-fireplace]]。
- **预测无关（forecasting-free）的立场**：在 Lambda 生产流量上验证，µVM CPU 用量的最佳 p90 预测在整个生命周期上是 0（LSTM/TCN 给 50 步历史预测 20 步都失败），因此不走"预测用量 + Best-Fit/genetic algorithm"的传统路线，而是设计不依赖预测的算法 [[2021-balaji-fireplace]]。
- **降维手段**：用 [[power-of-two-choices]] 把动作空间从"全部 PM"降到随机采样的 K 个候选，避免了需要全机群实时状态的可扩展性问题。
- **决策算法**：详见 [[hindsight-imitation-learning]]——用离线可得的未来真实数据构造贪心"教师"（Hindsight 算法），再训练监督学习模型模仿它，得到一个只用当前特征做决策的在线策略。

## 工程要点与数字

- 决策延迟预算 ~20ms，吞吐约 5 次放置/秒——这个约束直接排除了复杂的在线优化或多步预测 [[2021-balaji-fireplace]]。
- 生产流量特征（2021 年 Lambda）：µVM 生命周期中位数 ~15 分钟、p99 > 2 小时；内存中位数 ~100MB、p99 > 1GB；执行时间中位数 0.2–0.6s、p99 > 90s；到达间隔中位数 50–100s、p99 > 10 分钟 [[2021-balaji-fireplace]]。
- 效果：FirePlace（学习式放置）相对 Baseline（均值特征 + best-of-K）在 2D（CPU+内存）打包上提升约 10–11%；Hindsight（用到未来真实数据的贪心上界）相对 Baseline 提升 9–12%，相对 Random 提升 21–33%（具体数字因数据集规模而异）[[2021-balaji-fireplace]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 只验证了同构 PM 机群（单一数据集内部同规格），异构机群下的放置效果未经实验验证 [[2021-balaji-fireplace]]。
- 未覆盖 µVM 创建/销毁时机的决策（何时提前销毁空闲实例省内存）和跨 PM 迁移——这是本问题设定之外的相邻子问题，作者列为未来工作 [[2021-balaji-fireplace]]。
- 已核实 [[2609.22978]]（DSec）§7「Placement engine strategy」确认使用 power-of-k-choices（k 个节点选负载最低者）应对亚秒级数千沙箱突发与重度超卖，并辅以"本地视图叠加近期放置"和"每 edge 保留最终准入权"两个机制；但原文未给出 PAR 式目标函数或具体 k 值，与本文的目标函数/参数是否一致仍待正式精读 DSec 全文时核实。
- DSec 全文未发现覆盖共享队列层面的 noisy-neighbor 公平性设计（对照 [[noisy-neighbor-queue-fairness]]），只覆盖了放置侧——如果我们的调度器也有共享提交队列，这可能是一个值得补的能力缺口。

## 相关概念

[[hindsight-imitation-learning]]、[[power-of-two-choices]]、[[microvm-snapshot-uniqueness]]、[[noisy-neighbor-queue-fairness]]

## 相关来源

- [[2021-balaji-fireplace]] — 在 AWS Lambda 生产 Firecracker µVM 流量上系统化建模放置问题，提出 PAR 目标与预测无关的求解思路
- [[brooker-ten-years-of-lambda]] — 确认 DSec §7 同样使用 power-of-k-choices 做沙箱放置，并补充队列层面 noisy-neighbor（[[noisy-neighbor-queue-fairness]]）的对照案例
