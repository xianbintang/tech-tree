---
title: "Agent 执行沙箱（Execution Sandbox）"
aliases: [execution sandbox, agent sandbox, nono, E2B, Anthropic sandbox-runtime, agent 执行隔离, AgentENV]
created: 2026-09-29
updated: 2026-09-30
sources: [2609.29647, agentenv-docs]
---

# Agent 执行沙箱（Execution Sandbox）

## 一句话定义

在 OS 或云端层面隔离 agent 工具调用的实际执行，防止工具实现本身（无论是被投毒还是本来就恶意）访问声明之外的文件、网络或系统资源——是"harness 四层"（编排框架/运行时/治理平台/执行沙箱）里离我们平台最近的一层。

## 为什么对我们重要

这是四个 harness 层级里唯一直接对应我们"沙箱与执行环境基础设施"方向的一类系统，[[2609.29647]] 给出了三个具体对照系统（nono、E2B、Anthropic sandbox-runtime）的隔离机制和 GitHub 热度，可以作为我们做技术选型/竞品调研的起点，也提示了一个我们目前架构里可能缺的能力：**按身份/输入来源/记忆污点动态计算的细粒度 allowlist**，而不是启动时一次性写死的静态权限。

## 核心机制 / 主要变体

- **nono**：Landlock/Seatbelt 内核级沙箱 + Sigstore 对 agent 指令包做签名 + 凭证代理注入 + 网络 allowlist。GitHub ~2.4K star（截至 2026-05）。[[2609.29647]]
- **E2B**：云侧隔离执行环境，提供 Python/JS SDK。GitHub ~12.2K star（截至 2026-05）。[[2609.29647]]
- **Anthropic sandbox-runtime**：在不使用容器运行时的前提下，做 OS 级文件系统 + 网络限制（process-level）。GitHub ~4.1K star（截至 2026-05）。[[2609.29647]]
- **共同特征（[[2609.29647]] 的定性判断）**：隔离粒度是**二元的**——在沙箱内 vs. 沙箱外，一次性配置，执行期间不随身份/输入 provenance/记忆污点动态调整。
- **AgentENV**：与 E2B 定位不同的第四种选择——**开源、自托管、E2B API 兼容**的 Firecracker microVM 沙箱运行时，为 Moonshot AI Kimi K3 的 agentic RL 训练供能。E2B SDK 代码不改动即可指向自建的 AgentENV 服务，兼顾"用现成生态工具链"与"数据/基础设施自主可控"两个诉求；隔离级别是 Firecracker 强隔离（非 [[2609.29647]] 列出的三者那种 OS 级沙箱），并原生支持快照/fork/模板等训练场景常用能力 [[agentenv-docs]]，详见 [[agentenv-docs]] 笔记。

## 工程要点与数字

- 三个系统的 GitHub star 数（2026-05 快照）：nono ~2.4K、E2B ~12.2K、Anthropic sandbox-runtime ~4.1K。[[2609.29647]]
- 除此之外**没有性能、成本、密度、冷启动方面的实测数字**——[[2609.29647]] 只是把这三个系统列为背景对照，本身不是三者的评测来源，不能作为容量规划依据。
- AgentENV 反而**有**生产规模数字（但同样是 vendor claim,无测试方法说明）：快照沙箱冷启动/恢复 <50ms、暂停 <100ms、增量快照捕获 <100ms、内存超卖比 9.6x（生产,来源 README）、GitHub 3.6k star [[agentenv-docs]]。这是本页目前唯一带具体数字的系统,即便数字本身待验证,也比其余三个系统的"仅 star 数"更接近我们需要的容量规划信息。

## 争议与矛盾

[[2609.29647]] 提出 AgentKernel 的 Execution 支柱"包含并扩展"了这类沙箱的能力（论据：动态 allowlist vs. 静态二元隔离），但这是作者自己的定位论点，**没有给出任何对比实测**（延迟、开销、安全有效性都未验证）——引用时需注明这是未经验证的架构主张，不是既定结论。

## 开放问题

- 三个系统各自的冷启动延迟、并发密度、超卖能力等我们最关心的指标，目前知识库里没有一手数据，需要单独调研或实测。
- "动态 allowlist（按身份/污点收敛）" vs. "静态权限配置" 这两种设计在真实工作负载下的开销差异未知，值得我们自己验证而非直接采信 [[agent-os-kernel]] 论文的定性论点。
- AgentENV 的隔离粒度模型（Firecracker 强隔离 + 三种独立凭据分权）与 [[2609.29647]] 讨论的"二元隔离"框架如何对应，尚未仔细对照——AgentENV 的 `trafficAccessToken`/`envdAccessToken`/API key 三分是否构成比"沙箱内 vs 沙箱外"更细的粒度，值得单独分析。

## 相关概念

[[agent-os-kernel]]

## 相关来源

- [[2609.29647]] — 在 §6.1.4 把 nono/E2B/Anthropic sandbox-runtime 作为"执行沙箱"这一 harness 层级的代表系统给出简要对照，并论证 AgentKernel 的 Execution 支柱在此基础上补充了语义层动态权限收敛
- [[agentenv-docs]] — AgentENV：开源、自托管、E2B API 兼容的 Firecracker 沙箱运行时，为 Kimi K3 agentic RL 训练供能，是本页第四个、也是唯一带生产规模数字的候选系统
