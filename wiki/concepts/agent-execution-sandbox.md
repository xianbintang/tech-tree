---
title: "Agent 执行沙箱（Execution Sandbox）"
aliases: [execution sandbox, agent sandbox, nono, E2B, Anthropic sandbox-runtime, agent 执行隔离]
created: 2026-09-29
updated: 2026-09-30
sources: [2609.29647, xiaomimimo-uni-agent, xiaomimimo-mimo-code]
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
- **[[uni-agent]] 的多后端可插拔设计**：训练框架侧的另一种做法——不自己实现隔离机制，而是通过 `SandboxConfig(provider=...)` 统一接口切换 local（非沙箱，仅用于不需隔离的任务）、Docker（本地容器）、veFaaS、Modal、OpenYuanrong（三家远程弹性沙箱）；后端 SDK 懒加载，切换后端不改上层 Agent/Tool 代码 [[xiaomimimo-uni-agent]]。
- **比"静态二元隔离"更弱的一档：交互式权限提示（无隔离）**：终端原生编程 agent **MiMo Code**（同属 XiaomiMiMo 组织，与 [[uni-agent]] 是姊妹项目但 README 互不引用）默认没有任何 OS/容器级隔离，权限模型是"读写项目工作目录之外的文件才触发 `external_directory` 确认提示"；提供 `--dangerously-skip-permissions` flag 一键跳过所有确认，文档自己承认"permissions bypassed 后，被投毒的 prompt/文件/插件可以执行任意 shell 命令并读写外泄数据"，仅建议在受信任的一次性环境使用。README 全文未出现 sandbox/isolation/container 字样 [[xiaomimimo-mimo-code]]。

## 工程要点与数字

- 三个系统的 GitHub star 数（2026-05 快照）：nono ~2.4K、E2B ~12.2K、Anthropic sandbox-runtime ~4.1K。[[2609.29647]]
- 除此之外**没有性能、成本、密度、冷启动方面的实测数字**——[[2609.29647]] 只是把这三个系统列为背景对照，本身不是三者的评测来源，不能作为容量规划依据。
- [[uni-agent]] 的 Docker 后端把镜像拉取与容器启动拆成两段独立超时预算（`pull_timeout` 单独切出拉取阶段，`start_timeout` 只约束 `docker run`；两者缺省时统一受 `SANDBOX_STARTUP_TIMEOUT`，默认 600s，约束），是一个可直接参考的冷启动预算拆分模式；veFaaS/Modal/OpenYuanrong 三个远程后端同样**没有公开冷启动延迟、并发密度数字** [[xiaomimimo-uni-agent]]。

## 争议与矛盾

[[2609.29647]] 提出 AgentKernel 的 Execution 支柱"包含并扩展"了这类沙箱的能力（论据：动态 allowlist vs. 静态二元隔离），但这是作者自己的定位论点，**没有给出任何对比实测**（延迟、开销、安全有效性都未验证）——引用时需注明这是未经验证的架构主张，不是既定结论。

## 开放问题

- 三个系统各自的冷启动延迟、并发密度、超卖能力等我们最关心的指标，目前知识库里没有一手数据，需要单独调研或实测。
- "动态 allowlist（按身份/污点收敛）" vs. "静态权限配置" 这两种设计在真实工作负载下的开销差异未知，值得我们自己验证而非直接采信 [[agent-os-kernel]] 论文的定性论点。

## 相关概念

[[agent-os-kernel]]、[[uni-agent]]

## 相关来源

- [[2609.29647]] — 在 §6.1.4 把 nono/E2B/Anthropic sandbox-runtime 作为"执行沙箱"这一 harness 层级的代表系统给出简要对照，并论证 AgentKernel 的 Execution 支柱在此基础上补充了语义层动态权限收敛
- [[xiaomimimo-uni-agent]] — agentic RL 训练框架侧的沙箱抽象样本：可插拔多后端（local/Docker/veFaaS/Modal/OpenYuanrong），但同样缺公开的冷启动/密度数据
- [[xiaomimimo-mimo-code]] — 终端原生编程 agent 的权限模型样本：越界目录才提示确认、可一键跳过，不是隔离，提供了"隔离谱系"里比静态二元隔离更弱的一个真实产品案例
