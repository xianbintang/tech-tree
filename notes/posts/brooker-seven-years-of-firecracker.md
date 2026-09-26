---
title: "Seven Years of Firecracker"
type: post
id: "brooker-seven-years-of-firecracker"
source_url: https://brooker.co.za/blog/2025/09/18/firecracker.html
authors: [Marc Brooker]
affiliations: [Amazon Web Services]
published: 2025-09-18
created: 2026-09-26
tags: [firecracker, microvm-sandbox, snapshot-restore, agent-sandbox, serverless-database]
concepts: [microvm-snapshot-uniqueness, snapshot-layering, microvm-placement, agent-session-sandbox-isolation, guest-memory-marginal-cost]
rating: 4
issue: 23
parent: "2609.22978"
---

# Seven Years of Firecracker

> Firecracker 作者回顾七年演进，重点介绍 NSDI'20 论文未覆盖的两个新场景：Bedrock AgentCore（每 agent session 一个 microVM 的会话级隔离）与 Aurora DSQL（每 SQL 事务一个 microVM，用快照克隆+共享干净内存页加速创建）。

## 元信息

- 作者：Marc Brooker（AWS，Firecracker 与 Lambda 团队，现从事 agentic AI 的安全与策略工作）
- 发表：个人博客，2025-09-18
- 链接：[博文原文](https://brooker.co.za/blog/2025/09/18/firecracker.html)
- 关联：Firecracker NSDI'20 论文（[Agache et al., 2020](https://www.usenix.org/conference/nsdi20/presentation/agache)，本文回顾对象）；[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)；[Aurora DSQL 架构博文](https://brooker.co.za/blog/2024/12/03/aurora-dsql.html)；[Resource management in Aurora Serverless](https://www.amazon.science/publications/resource-management-in-aurora-serverless)；[[2102.12892]]（脚注 2 直接引用，说明克隆随机数问题）

## 要解决的问题

本文不是论文，是七周年回顾博文：Firecracker 2018 年 re:Invent 发布、2020 年 NSDI 论文发表之后，作者想补充论文里没写的两个新用例——它们不是"解决同一个问题"，而是分别展示 Firecracker 的两类能力（会话级强隔离 vs 快照克隆加速创建+内存共享）在生产系统里的具体落地。

## 方法

### 1. Bedrock AgentCore Runtime：会话级 microVM 隔离

AgentCore 是 AWS 面向"运行 AI agent"的产品。作者指出 Lambda 的"per-function"隔离粒度对 agent 不够——agent 会代表不同客户做许多不同种类的工作，因此 AgentCore Runtime 采用**每个 agent session 一个独立 microVM**（[[agent-session-sandbox-isolation]]）的隔离模型：一次 session（最长 8 小时）内可以有多轮用户交互、大量工具调用与 LLM 调用；session 结束时 microVM 被销毁，所有 session 上下文被安全遗忘,session 之间没有代码级交互（跨 session 的交互只能通过 AgentCore Memory 等显式机制）。作者强调 Firecracker 的价值在于**弹性范围极大**：session 时长从毫秒（单轮小模型交互）到数小时（多轮、上千次工具/LLM 调用）都要覆盖，上下文从 0 到数 GB 不等，Firecracker 原地伸缩 CPU/内存的能力是这套方案能做到经济可行的关键。

### 2. Aurora DSQL：每事务一个 Query Processor，快照克隆 + 共享干净页

DSQL（AWS 的 serverless、PostgreSQL 兼容关系型数据库）里，每个活跃 SQL 事务运行在自己的 Query Processor（QP，内含一份独立的 PostgreSQL）里，QP 可被同一数据库的多个事务复用，但同一时刻只处理一个事务。朴素做法（启动 Firecracker → 启动 Linux → 启动 PostgreSQL → 启动可观测性 agent → 加载 metadata）需要"几百毫秒"；DSQL 用**快照克隆**大幅加速：先启动+初始化+做一些定制，打一份快照，之后每次需要新 QP 就从快照恢复，创建时间快"几个数量级"。快照克隆带来第二个好处：多个克隆出的 microVM 之间可以**共享未被修改的干净（clean）内存页**（细粒度控制哪些页共享,写过的页各自拥有私有拷贝,隔离性不受影响），显著降低内存需求；作为副产物,共享页在部分 CPU 缓存层级里也只需存一份,进一步提升性能。克隆后随机数等状态的正确性问题（脚注 2）直接指向 [[2102.12892]]。

### 3. Linux 内存管理的两种应对策略对比：DSQL vs Aurora Serverless

作者借这个场景讨论一个更通用的问题（[[guest-memory-marginal-cost]]）：Linux 默认认为"空闲内存页是被浪费的页"，会尽量用 page cache/buffer 等填满物理内存——这在单机场景是合理默认值,但在 DSQL/Aurora Serverless 这类"guest VM 持有一个页的边际成本非零"的场景下是错误的默认值。两个系统给出了不同粒度的解法：
- **Aurora Serverless**（作者此前博文/论文介绍过）：用内核态进程 DARC 持续监控页访问频率,识别冷页,把冷的 file-backed 页标记为可释放、把冷的 anonymous 页 swap 出——做法更精细,但更"重"。
- **DSQL**：采用更简单的策略——**固定时长后直接终止 QP VM**,借此自然清理掉所有累积的内存"垃圾",不需要额外的访问频率统计。作者说明这之所以可行,是因为连接处理、缓存、并发控制都在 QP VM 之外处理,QP 本身可以做成"用完就扔"。作者把这个思路类比到 DSQL 的 MVCC GC 设计：不像 PostgreSQL VACUUM 那样精细追踪旧版本的引用,而是用一条简单规则（事务不能运行超过 5 分钟）划定运行事务集合的边界,过期版本可直接丢弃。

## 实验与结果

本文是回顾性博文，没有系统实验或量化对比表格：
- Firecracker QP 创建时间：朴素启动"几百毫秒"，快照克隆"快几个数量级"——均为定性描述，无具体数字。
- AgentCore session 时长跨度"毫秒到数小时"、上下文"0 到数 GB"——定性范围，无分布统计。
- 内存/缓存收益（共享干净页、CPU 缓存命中）——只有机制描述，没有给出内存节省比例或缓存命中率的具体数字。

## 局限与疑点

- 本文是 AWS 官方产品（AgentCore、DSQL）的回顾/宣传性博文，两个案例都没有给出可复现的量化数据（内存节省多少、创建加速多少倍、DARC vs 固定时长终止在同等负载下的开销对比），应视为架构描述而非评测结果。
- AgentCore Runtime 部分完全没有提及具体的隔离/伸缩机制细节（如 microVM 如何原地 resize、session 间硬件资源如何调度），只有产品层面的能力描述。
- DSQL 快照克隆共享干净页的机制（KSM 式事后扫描，还是类似 [[snapshot-layering]] 的 provenance-based 克隆时天然共享）文中未说明，只说"细粒度控制哪些页共享"，需要看 Firecracker 官方文档或 NSDI 论文原文确认具体实现路径。
- "固定时长终止 QP"这个策略的适用边界（多长的固定时长、如何选择）未讨论，作者只强调它比 DARC 式追踪更简单，没有给出两者的性能/内存权衡数据。

## 对我们的启发

- **会话级 microVM 隔离（AgentCore Runtime）是目前公开报道里最接近我们自己场景的生产设计**：按 agent session（而非按单次函数调用）分配一个 microVM、session 内允许长达数小时的多轮工具/LLM 调用、session 结束整个销毁不留状态——这与我们做 agentic RL 训练/评测沙箱的隔离粒度诉求几乎一致，值得作为对照基准：我们的沙箱生命周期管理、跨轮次状态保留方式，可以直接与"per-session microVM + 显式跨 session 交互（Memory/工具）"这套设计对比评估。
- **快照克隆共享干净内存页，是比"整份快照去重"或分层快照更细粒度的内存优化维度**：DSQL 场景提示我们，克隆出的多个 microVM 实例除了要处理 [[microvm-snapshot-uniqueness]] 讨论的"唯一性代价"，还可以在正确性允许的前提下反向利用"内存内容相同"这一事实来省内存（共享干净页）——如果我们的沙箱平台也用"预热后克隆多实例"的模式（如同一 base 环境批量拉起多个 agent 训练 rollout 沙箱），这是一个值得评估的、内存密度侧的额外收益点，而不仅是要规避的风险。
- **"guest VM 持有空闲内存边际成本非零"时，"固定时长终止+重建"可以是比精细化页追踪（DARC 式）更简单的工程选择**：这与 [[brooker-lambda-snapstart]] 里"Hungry Hungry Hippos"一节提出但没给方案的开放问题形成一个具体的回答——如果我们的沙箱/QP 类角色本身生命周期短、状态可以外置（连接、缓存、并发控制都不在这个角色内部），直接用固定生命周期强制回收可能比自适应缓存策略更容易落地和调试，值得在我们自己评估类似"边际成本非零"的组件（如快照模板 VM、常驻 worker）时优先考虑这条更简单的路线。
- Follow-up 建议（可转 issue）：
  1. 待精读同清单剩余条目（Ten Years of AWS Lambda、Running self-hosted AI agent sandboxes with AWS Lambda MicroVMs），核实 AgentCore 的 session 隔离机制是否与 2026 年面向 agent 沙箱的 Lambda MicroVMs 产品共享同一套底层设计；
  2. 找 Firecracker 官方快照/克隆文档，确认"共享干净内存页"的具体实现机制（页级去重时机、是否有 KSM 式扫描开销），评估是否能在我们自己的 microVM 快照方案里复用；
  3. 评估我们沙箱平台里是否存在"边际内存成本非零但当前用精细化追踪/回收机制管理"的组件，对照 DSQL 的"固定时长终止"策略做一次简化的可行性评估。

## 相关

- 相关概念：[[agent-session-sandbox-isolation]]、[[guest-memory-marginal-cost]]、[[microvm-snapshot-uniqueness]]、[[snapshot-layering]]、[[microvm-placement]]
- 相关笔记：[[2102.12892]]（本文脚注直接引用，说明快照克隆后随机数正确性问题）、[[brooker-lambda-snapstart]]（同一作者更早的博文，"Hungry Hungry Hippos"一节提出的边际内存成本问题，本文的 DSQL 案例给出了一个具体的简化解法）
- 与母论文的关系：逐字检索 `.cache/papers/2609.22978.txt`（DSec 全文）确认，DSec 引用了 Firecracker NSDI'20 论文（Agache et al., 2020，作者列表含 Brooker）作为其 microVM 后端的技术基础（§2.2, §5.3, §6.3 等多处），但正文完全没有出现"AgentCore""DSQL""seven years"等词，也没有引用本文——本文发表于 2025-09，DSec 发表于 2026-09，两者没有直接引用关系，本文只是同一技术（Firecracker）在 AWS 内部的独立应用案例。有一处值得对照的机制相似性：DSec §6.3「Suspending Sandboxes for Preemptive RL Training」的 microVM pause（打快照后终止 Firecracker 进程释放运行时内存）/resume（恢复快照继续执行）是**单实例挂起-恢复同一身份**，与本文 DSQL 案例的**从一份快照克隆出多个独立 QP 实例**是不同的使用模式（前者时间轴上是同一实例的两个状态，后者是空间上的多个并发实例）——DSec 是否在其他地方（如批量拉起同类型 microVM 沙箱时）采用了类似 DSQL 的"克隆+共享干净页"模式，原文未说明，无法确认。
