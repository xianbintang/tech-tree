---
title: "Agent Session Sandbox Isolation / 会话级 Agent 沙箱隔离"
aliases: [session isolation, AgentCore Runtime, per-session microVM, 会话级隔离, agent session isolation, AWS Lambda MicroVMs]
created: 2026-09-26
updated: 2026-09-26
sources: [brooker-seven-years-of-firecracker, aws-lambda-microvms-agent-sandboxes]
---

# Agent Session Sandbox Isolation / 会话级 Agent 沙箱隔离

## 一句话定义

以一次 agent session（而非单次函数调用/请求）为隔离粒度分配一个独立执行环境（如一个 microVM）：session 内允许多轮工具调用和 LLM 交互、状态在 session 生命周期内保留，session 结束时整个环境被销毁，跨 session 的交互只能通过显式的托管机制（如 Memory 服务）进行，而不是代码层面隐式共享状态。

## 为什么对我们重要

这是目前公开报道里最接近我们做 agentic RL 训练/评测沙箱这套需求的生产隔离粒度设计——agent 一次 session 里会有大量工具调用/LLM 交互，比 Lambda 单函数调用粒度粗得多，又比"整个训练 job 一个沙箱"粒度细。AWS 已经把这套模型从内部产品（AgentCore Runtime）产品化为通用基础设施（Lambda MicroVMs）并开放给第三方编排系统对接，说明这不再只是一家的内部实践，而是正在成为行业可购买的基础设施层能力——评估我们自己的沙箱生命周期管理（何时创建、何时回收、跨轮次状态如何保留、要不要对外暴露成通用原语）时，两者都是可以直接对标的生产设计。

## 核心机制 / 主要变体

- **隔离粒度**：per-session 而非 per-function/per-request——一次 session 可以跨越多轮用户交互、大量工具调用和 LLM 调用 [[brooker-seven-years-of-firecracker]]。
- **生命周期上限**：单次 session 最长 8 小时，时长跨度从毫秒（单轮、单次小模型交互）到数小时（多轮、上千次工具/LLM 调用）都要覆盖 [[brooker-seven-years-of-firecracker]]；产品化后的 Lambda MicroVMs 同样把单 microVM 最长运行时间定为 **8 小时**，与 AgentCore Runtime 的上限一致 [[aws-lambda-microvms-agent-sandboxes]]。
- **上下文规模跨度大**：单 session 上下文可以从 0 到数 GB，原文强调这正是需要 Firecracker 原地伸缩 CPU/内存能力的原因——固定规格的沙箱无法同时经济地覆盖这个范围 [[brooker-seven-years-of-firecracker]]。
- **销毁即遗忘 + 显式跨 session 交互**：session 结束 microVM 被销毁，所有 session 内上下文被安全遗忘；跨 session 的交互被限制在显式、托管的机制内（如 AgentCore Memory、有状态工具），不存在代码层面的隐式共享状态，作者认为这让安全推理更容易 [[brooker-seven-years-of-firecracker]]。
- **产品化为通用原语（AWS Lambda MicroVMs）**：AgentCore Runtime 的 per-session microVM 模型已经开放成通用计算产品——用户可编程式 launch / suspend / resume / terminate，每个环境独立 Firecracker VM 隔离，不共享内存/磁盘/网络命名空间；面向的不再只是 AWS 自家 AgentCore，而是任意第三方编排系统（示例对接 Anthropic Claude Managed Agents 的自托管沙箱）[[aws-lambda-microvms-agent-sandboxes]]。
- **原地垂直扩容（4x）**：运行中的 microVM 可以把 CPU/内存原地扩容到初始分配的最多 4 倍（初始规格 0.25 vCPU/0.5GB ~ 4 vCPU/8GB 区间），不需要终止重建——这是对"上下文规模跨度大、固定规格无法经济覆盖"这一问题的一个具体产品化解法 [[aws-lambda-microvms-agent-sandboxes]]。
- **空闲挂起 + 事件触发生命周期**：可配置的 idle policy——空闲一段时间后自动 suspend（保留磁盘和内存状态），收到入站流量或显式调用 resume API 后恢复。官方建议配套使用**事件/webhook 触发**而非常驻轮询来启动 worker，因为常驻轮询会与 idle policy 的自动挂起机制冲突 [[aws-lambda-microvms-agent-sandboxes]]。
- **凭据边界**：launcher 组件只持有触发凭据（如 webhook 签名密钥），只把执行环境凭据的**引用**（而非凭据本身）传给 microVM，microVM 在运行时用自己的 execution role 按需拉取真正的凭据——任何单一组件不同时持有两类密钥 [[aws-lambda-microvms-agent-sandboxes]]。

## 工程要点与数字

- Session/microVM 时长上限：毫秒级 ~ 8 小时，AgentCore Runtime 与 Lambda MicroVMs 产品规格一致 [[brooker-seven-years-of-firecracker]] [[aws-lambda-microvms-agent-sandboxes]]。
- 上下文规模跨度：0 ~ 数 GB [[brooker-seven-years-of-firecracker]]。
- Lambda MicroVMs 初始资源规格区间：0.25 vCPU/0.5GB ~ 4 vCPU/8GB，可原地扩容至初始值的最多 4 倍 [[aws-lambda-microvms-agent-sandboxes]]。
- 具体的 microVM 原地伸缩机制内部实现（是否涉及短暂 pause+resize+resume）、跨 session 资源调度算法、idle policy 的具体阈值/resume 延迟均未披露，两篇来源都只给出产品能力层面的描述，没有可量化的基准数字 [[brooker-seven-years-of-firecracker]] [[aws-lambda-microvms-agent-sandboxes]]。

## 争议与矛盾

（暂无跨来源分歧，两篇来源分别是同一设计的早期案例披露与后续产品化说明）

## 开放问题

- 具体隔离/伸缩机制（microVM 如何原地 resize、session 间资源如何调度）未披露 [[brooker-seven-years-of-firecracker]] [[aws-lambda-microvms-agent-sandboxes]]。
- 与 DSec（[[2609.22978]]）自己的沙箱生命周期模型（§2.3 统一 SDK 生命周期、§6.3 抢占式挂起/恢复）相比：DSec 的 pause/resume 机制（快照+终止进程 / 恢复快照+新进程）与 Lambda MicroVMs 的 idle-suspend/resume 在机制上高度相似，但触发方式不同——DSec 由 RL 框架在 GPU 抢占时**主动显式**触发，Lambda MicroVMs 是平台**空闲超时自动**触发；DSec 全文未发现类似"session 中途原地垂直扩容 4x"的能力描述，这是 Lambda MicroVMs 相对 DSec 目前公开设计的一个能力差异点，详见 [[aws-lambda-microvms-agent-sandboxes]]「与母论文的关系」。
- Lambda MicroVMs 从快照启动的产品说明完全未提及克隆/快照恢复后的唯一性问题（对照 [[microvm-snapshot-uniqueness]]、[[2102.12892]]）——是平台层已处理还是文档简化略过，未确认 [[aws-lambda-microvms-agent-sandboxes]]。

## 相关概念

[[microvm-snapshot-uniqueness]]、[[guest-memory-marginal-cost]]、[[snapshot-layering]]

## 相关来源

- [[brooker-seven-years-of-firecracker]] — 描述 Amazon Bedrock AgentCore Runtime 采用每 agent session 一个独立 microVM 的隔离模型
- [[aws-lambda-microvms-agent-sandboxes]] — AgentCore per-session microVM 模型的产品化：AWS Lambda MicroVMs，开放给第三方编排系统对接，新增 4x 原地垂直扩容、idle policy 挂起/恢复、凭据引用传递等具体工程细节
