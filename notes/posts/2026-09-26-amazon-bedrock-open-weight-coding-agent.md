---
title: "Use open weight models as your AI coding agent with Amazon Bedrock"
type: post
id: bc04984d3646
source_url: https://aws.amazon.com/blogs/machine-learning/use-open-weight-models-as-your-ai-coding-agent-with-amazon-bedrock/
authors: [Aris Tsakpinis, Suryansh Rana, Saurabh Trikande, Sainath Miriyala]
affiliations: [AWS]
published: 2026-09-23
created: 2026-09-26
tags: [coding-agent, inference-serving, cost, model-routing, bedrock]
concepts: [agentic-token-cost, model-routing-by-task]
rating: 3
issue: 14
---

# Use open weight models as your AI coding agent with Amazon Bedrock

> 用 OpenCode + Bedrock 开放权重模型（Kimi K3 / GPT-OSS 120B / Nemotron 3 Super 120B）做编码 agent，靠按角色路由模型和分层定价把 agentic 工作流的高 token 成本摊下来。

## 元信息

AWS（Aris Tsakpinis, Suryansh Rana, Saurabh Trikande, Sainath Miriyala） / 2026-09-23 / [原文](https://aws.amazon.com/blogs/machine-learning/use-open-weight-models-as-your-ai-coding-agent-with-amazon-bedrock/)

这是一篇厂商技术博文（AWS Bedrock 产品团队），不是研究论文，没有对照实验，很多数字来自第三方报告或客户案例转述，需要打折看待。

## 要解决的问题

Agentic coding 工作流（多轮工具调用、长上下文、多文件读写）比单轮问答消耗的 token 多得多，专有模型的按 token 计费在规模化部署（文中提到「月均数百万对话」量级）下成本会失控。文章要回答的是：**能不能用开放权重模型替代专有模型做 coding agent 的后端，同时保住企业需要的数据驻留、合规与权限控制**。

## 方法

架构很简单，两部分：

1. **OpenCode**（Go 写的开源终端原生 coding agent，TUI 界面）跑在本地/开发机上，作为用户交互层。
2. 所有推理请求走 **Amazon Bedrock 的 Converse API**：每个请求过 AWS IAM 鉴权，CloudTrail 记录调用日志，数据不出账户、不用于训练模型。

关键设计是**按 agent 角色分模型**，在项目根目录的 `opencode.json` 里配置：

```json
{
  "model": "amazon-bedrock/us.openai.gpt-oss-120b-1:0",
  "agent": {
    "plan": { "model": "amazon-bedrock/global.moonshotai.kimi-k3" },
    "build": { "model": "amazon-bedrock/us.nvidia.nemotron-super-3-120b" }
  }
}
```

规划/架构分析这类需要长程推理的任务路由到 Kimi K3（MoE，1M 上下文，有 low/high/max 三档推理强度可调延迟-正确性权衡）；批量代码生成路由到 Nemotron 3 Super 120B（论文/文档里说"仅激活 12B/120B 参数"，即稀疏 MoE 推理，吞吐比稠密基线提升 7 倍）。切模型只是改一个字符串，不用改代理逻辑。

进一步规模化时提到的是**路由器架构**：意图分类 → 低成本模型；代码生成 → 中层开放权重模型；复杂推理 → 高阶推理模型。文中引用生产案例 Ethara.AI：用 Oh-My-OpenAgent 做编排层，按任务类别（规划、执行、代码审查、架构分析、知识检索、多模态理解、基准测试）把请求分派到专门优化过的 agent 队列，工程师"请求能力"而系统负责挑模型。这是一个应用层的**按类别路由**模式，和训练侧 [[category-aware-expert-training]] 里"按类别拆专家"的思路是同构的，只是一个发生在推理时间的模型选择，一个发生在训练时间的策略分化。

安全上给了个最小权限 IAM 策略样例，只放行需要的 `bedrock:InvokeModel*` 到具体模型 ARN，并可选接 Bedrock Guardrails 做内容过滤 / PII 脱敏。

## 实验与结果

没有作者自己的 benchmark，都是引用数字，**可信度需要打折**：

- Agentic 工作流的 token 消耗比单轮问答高 **5–30 倍**（文中未给来源方法论，视为量级参考）。
- McKinsey（2025）：76% 组织预计增加开源 AI 使用；领先采用者用开放权重模型的可能性高 40%（这是采用意愿调查，不是性能数据）。
- 引用 CrowdStrike 案例：微调过的 Nemotron 在特定领域任务上"有效查询准确率" 96% vs GPT-4o 61%——**这是厂商案例转述，缺具体任务定义和评测方法，不可直接采信为通用结论**。
- Bedrock 定价分三档：Priority（低延迟）、Standard（按需按 token）、Flex（可变延迟，成本低 50%，适合可容忍延迟的批量任务，如文中批量生成单测的例子）。
- 跨区推理（global inference profile）比指定地理区域便宜约 10%。
- 默认账户容量：每分钟 1 亿 token、每分钟 1 万请求（Bedrock 平台限额，不是这几个模型本身的极限）。

## 局限与疑点

- 全文没有一个自己跑出来的数字，7 倍吞吐、96% vs 61%、5–30 倍 token 倍数都是引用或转述，具体测量口径、任务分布、样本量一概没有。
- "路由器架构降低 TCO"是定性论断，没给出实际成本对比（比如同一批任务用单一大模型 vs 路由架构的账单差异）。
- 完全没有涉及沙箱/执行环境层面的东西——OpenCode 怎么执行代理生成的代码、有没有隔离、并发多个 agent session 时的资源开销，文章完全没提，这是它作为"coding agent 基础设施"文章的一个明显空白。
- Kimi K3 / Nemotron 3 Super 120B 都是 2026 年才在 Bedrock 上线的新模型条目，命名（如 `nemotron-super-3-120b`）在博文里前后不完全一致，可能是发布节奏导致的文档不同步，具体 API 标识以 Bedrock 控制台为准。

## 对我们的启发

这篇跟我们沙箱/调度平台的核心基础设施（隔离、冷启动、镜像分发）没有直接关系，价值主要在**成本模型**和**路由模式**两点：

1. **agentic 工作流的 token 放大效应（5–30x）是我们规划训练/评测集群容量时要考虑的成本系数**，尤其是 rollout 阶段大量多轮工具调用——如果我们内部也有类似"按角色分模型"的需求（比如规划用大模型、大批量执行用小模型），这是一个现成的可参考模式，虽然文章没给可执行的量化方法。
2. **按任务类别路由到不同规格模型/agent 的调度模式**（Ethara.AI 案例）值得我们对照自己平台的 agent 调度设计——本质上是一个轻量级的"分类器 + 路由表"，如果要在我们的调度系统里做类似分层（比如高优先级/低延迟 vs 可容忍延迟批量任务），Bedrock 的 Priority/Standard/Flex 三档定价+SLA 划分是一个可以借鉴的分层思路。
3. **可执行的 follow-up**：调研开放权重 MoE 模型（Kimi K3、Nemotron 系列）在自建推理服务上的稀疏激活吞吐收益是否可复现（不依赖 Bedrock 的托管数字），如果我们自己的训练集群也跑推理服务，这直接关系到我们能不能用同样的稀疏激活策略降低服务成本——这个可以开一个新 issue 去查对应的模型技术报告。

## 相关

- 相关概念：[[agentic-token-cost]]、[[model-routing-by-task]]、[[category-aware-expert-training]]
- 相关笔记：（暂无同主题笔记）
