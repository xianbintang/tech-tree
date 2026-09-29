---
title: "Seven Years of Firecracker"
type: post
id: "brooker-seven-years-of-firecracker"
source_url: https://brooker.co.za/blog/2025/09/18/firecracker.html
authors: [Marc Brooker]
affiliations: [Amazon Web Services]
published: 2025-09-18
---

Firecracker 发布七年后的回顾博文。作者（Firecracker/Lambda 作者之一）简述 2018 年 re:Invent 发布与 2020 年 NSDI 论文的背景，然后聚焦论文未覆盖的两个新用例：Amazon Bedrock AgentCore Runtime（每个 agent session 一个 microVM 的会话级隔离）与 Aurora DSQL（每个 SQL 事务一个 Query Processor microVM，用 Firecracker 快照克隆加速创建并共享未修改的干净内存页），并借 DSQL 与 Aurora Serverless 的对比讨论了两种不同的"客户 VM 持有空闲内存边际成本非零"应对策略。

笔记：[[brooker-seven-years-of-firecracker]]
