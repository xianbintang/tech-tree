---
title: "共享队列的 Noisy-Neighbor 公平性"
aliases: [noisy neighbor queue fairness, stochastic fairness queuing, SFQ, 队列层公平性, 事件队列 noisy neighbor]
created: 2026-09-26
updated: 2026-09-26
sources: [brooker-ten-years-of-lambda]
---

# 共享队列的 Noisy-Neighbor 公平性

## 一句话定义

当多租户共享同一个提交/事件队列（而非只共享计算资源）时，高频调用或高失败率的租户会把队列打满、拖累其他租户的延迟；AWS Lambda 用 stochastic fairness queuing（SFQ）与 best-of-k 放置结合，在队列机群的机器间不共享状态的前提下给出了紧的公平性边界 [[brooker-ten-years-of-lambda]]。

## 为什么对我们重要

我们通常把 noisy-neighbor 隔离想成"计算资源隔离"（CPU/内存/microVM 边界），但如果沙箱调度器有共享的任务提交队列、事件总线或 API 网关排队层，这条路径本身也可能成为跨租户干扰的攻击面——而且往往比计算资源隔离更容易被设计时忽略，因为它不在"每个沙箱一个 microVM"的隔离叙事里 [[brooker-ten-years-of-lambda]]。

## 核心机制 / 主要变体

- **问题起源**：Lambda 早期在计算硬件热管理和函数间 noisy-neighbor 上已有设计，但遗漏了共享队列（如 event invoke 背后的队列）本身；高频调用尤其是失败率高的函数会填满这些队列，造成跨客户的延迟影响 [[brooker-ten-years-of-lambda]]。
- **解法**：stochastic fairness queuing（SFQ，队列调度里的经典公平性算法）与 best-of-k 放置（即 [[power-of-two-choices]] 的 k 选一采样思路）结合，设计出不需要队列机群机器间共享状态、也能对 noisy-neighbor 效应给出紧界的系统 [[brooker-ten-years-of-lambda]]。
- **与放置侧 power-of-two-choices 的关系**：两者都用"随机采样 k 个候选、选负载最低"的降维思路，但作用对象不同——[[power-of-two-choices]]/[[microvm-placement]] 解决的是"新实例放到哪台物理机"，本概念解决的是"排队中的请求如何在共享队列资源上被公平地服务/丢弃"，是同一算法思想在不同层（放置 vs 排队接纳）的复用 [[brooker-ten-years-of-lambda]]。

## 工程要点与数字

原文未给出 SFQ+best-of-k 方案的具体边界证明或量化效果数字，只称其给出了"紧的边界（tight bounds）"且此后被复用到其他多个内部系统；无可引用的具体吞吐/延迟改善数字 [[brooker-ten-years-of-lambda]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源，且原文本身缺乏量化细节）

## 开放问题

- 具体 SFQ 算法参数、与 best-of-k 的结合方式（是否 best-of-k 只用于队列机器选择、SFQ 只用于队列内部调度）原文未展开，需要找 2019/2022 reInvent 相关演讲或论文补充。
- 待确认 DSec（[[2609.22978]]）等 agent 沙箱调度系统是否存在共享任务提交队列/事件总线，以及是否需要类似机制——目前逐字检索 DSec 全文未发现队列层面的公平性设计，只有放置侧的 [[power-of-two-choices]]，这可能是一个未被覆盖的风险点。

## 相关概念

[[power-of-two-choices]]、[[microvm-placement]]

## 相关来源

- [[brooker-ten-years-of-lambda]] — 揭示 Lambda 共享队列曾放大 noisy-neighbor，并给出 SFQ + best-of-k 的解法思路
