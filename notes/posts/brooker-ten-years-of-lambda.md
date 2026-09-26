---
title: "Ten Years of AWS Lambda"
type: post
id: "brooker-ten-years-of-lambda"
source_url: https://brooker.co.za/blog/2024/11/14/lambda-ten-years.html
authors: [Marc Brooker]
affiliations: [Amazon Web Services]
published: 2024-11-14
created: 2026-09-26
tags: [aws-lambda, scheduling, control-plane, noisy-neighbor]
concepts: [power-of-two-choices, noisy-neighbor-queue-fairness, microvm-placement]
rating: 3
issue: 23
parent: "2609.22978"
---

# Ten Years of AWS Lambda

> Lambda 十周年回顾：worker manager 从单机内存态到跨 AZ 持久化的演进，以及共享队列曾放大 noisy-neighbor、靠 SFQ + best-of-k 解决的往事。

## 元信息

作者 / 机构：Marc Brooker（AWS，Firecracker/Lambda 作者之一）· 个人博客 · 2024-11-14 发布
链接：[原文](https://brooker.co.za/blog/2024/11/14/lambda-ten-years.html)
体裁：借 Werner Vogels 公开 Lambda 原始 PRFAQ 批注版而写的回顾文，无实验数据，多为工程史与经验总结。

## 要解决的问题

文章本身不是在解决单一问题，而是回顾 Lambda 十年里几个决策/教训：
1. 为什么 2014 首发只支持 Node.js；
2. worker manager（Lambda 里把到达的 invoke 分配到可用容量的核心组件）为什么要从纯内存单机重构为跨 AZ 持久化服务，以及这次重构如何在提升可用性的同时还降低了中位数延迟；
3. 一个此前较少被提及的教训：共享队列（如 event invoke 背后的队列）会放大 noisy-neighbor 效应。

## 方法

- **语言支持**：npm 让 NodeJS 函数打包（`zip -r function.zip index.mjs node_modules`）几乎零改造成本，是 2014 年选 Node 首发的关键原因之一；Go 支持（2018-01）本质是 Custom Runtime 的雏形，客户用它塞入 C++/Rust/各种 JVM 后倒逼团队正式推出 Custom Runtime（2018-11）——这与十年前 EC2 客户绕过官方支持自带内核/OS 的历史重演。
- **worker manager 重构**：2014 版 worker manager 是纯内存进程，延迟好、能跨大范围工作负载做全局优化，但代价是单机故障会丢失全部内存态、重建成本高；团队借助 AWS 内部的 Journal 服务把它重构为跨 AZ 持久化服务，且做到了在提升可用性的同时降低中位数延迟（原文未给出具体延迟数字，只强调"median latency 对客户比 tail latency 更重要"，尤其是微服务/SOA 架构下延迟会累加）。
- **共享队列 noisy-neighbor**：Lambda 早期已经在计算硬件热管理和 noisy-neighbor（函数间）上做了设计，但**遗漏了共享队列本身**——高频调用、尤其是失败率高的函数会把 event invoke 等共享队列打满，造成跨租户的延迟影响。团队与 Amazon Scholars 合作，把 **stochastic fairness queuing (SFQ)** 与 **best-of-k 放置**（即 [[power-of-two-choices]] 的 k 选一思路，作者称之为 "best-of-k"）结合，在队列机群的机器间不需要共享状态的前提下，对 noisy-neighbor 效应给出了紧的边界，据称此后在其他多个内部系统复用。

## 实验与结果

已获取全文，但文章本身不含实验数据或基准测试表格，属于经验回顾性质的叙述，无量化数字可引用。

## 局限与疑点

- 未给出 worker manager 重构前后的具体延迟数字，也未说明"跨 AZ 持久化 + 降延迟"具体靠什么机制同时做到（只提到用了 Journal 服务，细节见 2024 年 MemoryDB 相关博文，未深入本篇）。
- SFQ + best-of-k 的具体算法描述非常简略，没有边界证明或量化效果数字，只说"tight bounds"和"已复用到其他系统"，均未展开。
- 这是个人博客经验分享，非同行评审文献，结论可信度依赖作者本人一手经验，但缺乏可复现的实验验证。

## 对我们的启发

1. **共享队列本身也是 noisy-neighbor 的攻击面**：我们的沙箱调度器如果有共享的任务提交队列/事件队列（不只是计算资源放置），需要单独评估"高频/失败重试的租户是否会打满队列、影响其他租户延迟"——这是比"计算资源隔离"更容易被忽略的维度。
2. **SFQ + best-of-k 是队列层面的免费降维方案**：与 [[power-of-two-choices]] 在放置侧的思路一脉相承（同一作者提出/复用），且不需要队列机器间共享状态，值得在设计任务队列/事件总线时优先评估，已建概念页 [[noisy-neighbor-queue-fairness]] 跟踪。
3. **有状态控制面组件的可用性升级要盯住延迟回归**：worker manager 从单机内存态改造为跨 AZ 持久化服务时特意做到"提升可用性的同时不牺牲（甚至降低）中位数延迟"——这提示我们自己的调度器控制面做持久化/多活改造时，应把中位数延迟作为硬性验收指标，而不只是可用性指标。

## 相关

- 相关概念：[[power-of-two-choices]]、[[noisy-neighbor-queue-fairness]]、[[microvm-placement]]
- 相关笔记：[[2021-balaji-fireplace]]（同样使用 best-of-k/power-of-k-choices 做 Lambda µVM 放置，但解决的是计算资源放置而非共享队列公平性）
- 与母论文的关系：逐字检索 DSec（[[2609.22978]]）全文确认，DSec 未提及本文、worker manager、SFQ 或 noisy-neighbor 相关字样；DSec §7「Placement engine strategy」确认其调度器同样采用 power-of-k-choices（采样 k 个节点选负载最低者）应对亚秒级数千沙箱的突发与重度超卖，并辅以"本地视图叠加未反映的近期放置"和"每个 edge 保留最终准入权"两个机制；但全文未出现队列层面的公平性设计，说明 DSec 目前公开的调度器设计只覆盖了本文提到的"放置侧 noisy-neighbor"，尚未看到覆盖"共享队列侧 noisy-neighbor"的对应机制——这是母论文相对本文经验的一个可能空白点，而非两者的直接引用关系。
