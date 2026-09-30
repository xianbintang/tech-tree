---
title: "Agent 执行沙箱（Execution Sandbox）"
aliases: [execution sandbox, agent sandbox, nono, E2B, Anthropic sandbox-runtime, agent 执行隔离]
created: 2026-09-29
updated: 2026-09-30
sources: [2609.29647, openenv, prime-intellect-verifiers, harbor-framework, 2404.07972, 2308.03688]
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
- **OpenEnv（Docker 容器隔离 + Cloud Sandbox Providers 安全不变量）**：Meta×HF 的 agentic RL 环境标准默认用 Docker 容器做隔离，`ContainerProvider` 抽象把编排细节与客户端解耦；其 2026-06 提出、尚未定稿的 Cloud Sandbox Providers 修订给出 6 条面向不可信工作负载的安全不变量（S1-S6）：加密传输、ingress URL 限时限权、默认拒绝出站+屏蔽云元数据/IMDS 端点、控制面凭据不进沙箱、禁止命令注入、资源硬限额；并明确 suspend/resume/快照等生命周期操作只能走编排层、绝不作为工具暴露给 agent。与 nono/E2B/Anthropic sandbox-runtime 一样偏静态配置（不做基于身份/污点的动态收敛），但把"面向不可信代码"的安全基线写成了可检查的清单形式，是三个系统之外一份新的参照 [[openenv]]。
- **verifiers 的独立验证器沙箱（[[verifiers-framework]]）**：与前几个系统关注"agent 执行时的隔离边界"不同，这是"agent 执行结束后如何隔离打分"的具体方案——`IsolatedVerifierEnv` 销毁 solver 沙箱，创建全新验证器沙箱恢复声明的 artifacts 后跑确定性打分，默认假设 solver 沙箱残留状态不可信（只信任显式声明的 artifacts）。六种 Runtime（subprocess/docker/podman/apptainer/prime/modal）里只有容器/远程类型能承担验证器角色，host subprocess 被显式拒绝做绝对路径 artifact 恢复。Harbor 集成额外给出网络策略三态（`public`/`no-network`/`allowlist`，翻译不了托管工具域名就禁用而非放宽）和 artifact 传输硬预算（默认 32MiB）两条具体工程约束 [[prime-intellect-verifiers]]。
- **[[agentbench]] 的任务级 Docker 隔离（早期历史锚点）**：2023 年最早的系统性 LLM-as-Agent 评测框架，把每类任务（OS/DB/KG 等）封装进 Docker 镜像、每个任务再拆成独立 Task Worker 进程避免环境冲突，配合 Task Server/Agent Server/Evaluation Client 三方 HTTP 解耦部署。隔离粒度是纯静态的任务级容器，没有 suspend/resume、没有动态权限收敛、没有安全不变量清单——是这条"沙箱执行环境标准化"技术线的起点，可用来对照后续系统（Harbor ASP、OpenEnv ContainerProvider）具体补上了哪些能力 [[2308.03688]]。
- **OSWorld 的 GUI/桌面 VM 沙箱**：面向 computer-use agent（而非 code/terminal agent）的执行沙箱，用传统虚拟机（而非 microVM/容器）跑完整 Ubuntu/Windows/macOS 桌面，通过快照恢复实现高效重置；采用"启动 VM → 按需下载文件 → 执行预处理命令"的三段式混合初始化，而非逐任务全量快照（避免每个样例占用数 GB 存储）；评测阶段需要从沙箱取回文件、浏览器 cookie、accessibility 树等多种格式的产物，比纯 stdout 捕获的取数接口更丰富。多 VM 可在单机并行跑、支持 headless，但论文完全未披露密度、冷启动时间等具体数字 [[2404.07972]]。
- **Harbor 的 ASP（Agent Sandbox Protocol）**：与前几个系统关注"沙箱本身怎么隔离"不同，这是"如何把任意 agent harness 的工具执行接到远程沙箱"的协议化方案（v0 RFC 草案）——把 agent 工具拆成面向模型的策略层（不变）和底层机制层（原始 read/write/exec，替换成走传输协议），agent **完全不知道自己在远程执行**，没有任何 verb 能触达 harness 所在机器；协议显式只标准化 `execute`、排除 `provision`（沙箱创建/配置留给编排层）。目前只支持 SSH 传输，已验证 Docker/Apple Container/Daytona 三个 provider，并验证过"沙箱无 egress 时 SSH 工具仍正常工作"，说明这套协议可以与"默认拒绝出站"这类安全基线正交组合，与 [[openenv]] 的 Cloud Sandbox Providers 安全不变量（S1-S6，同样把生命周期操作限定在编排层、不让 agent 触达）是同一条设计原则在两个独立来源里的重复出现 [[harbor-framework]]。

## 工程要点与数字

- 三个系统的 GitHub star 数（2026-05 快照）：nono ~2.4K、E2B ~12.2K、Anthropic sandbox-runtime ~4.1K。[[2609.29647]]
- 除此之外**没有性能、成本、密度、冷启动方面的实测数字**——[[2609.29647]] 只是把这三个系统列为背景对照，本身不是三者的评测来源，不能作为容量规划依据。

## 争议与矛盾

[[2609.29647]] 提出 AgentKernel 的 Execution 支柱"包含并扩展"了这类沙箱的能力（论据：动态 allowlist vs. 静态二元隔离），但这是作者自己的定位论点，**没有给出任何对比实测**（延迟、开销、安全有效性都未验证）——引用时需注明这是未经验证的架构主张，不是既定结论。

## 开放问题

- 三个系统各自的冷启动延迟、并发密度、超卖能力等我们最关心的指标，目前知识库里没有一手数据，需要单独调研或实测。
- "动态 allowlist（按身份/污点收敛）" vs. "静态权限配置" 这两种设计在真实工作负载下的开销差异未知，值得我们自己验证而非直接采信 [[agent-os-kernel]] 论文的定性论点。

## 相关概念

[[agent-os-kernel]]、[[openenv-interface-spec]]、[[verifiers-framework]]、[[harbor]]、[[computer-use-agent]]

## 相关来源

- [[2609.29647]] — 在 §6.1.4 把 nono/E2B/Anthropic sandbox-runtime 作为"执行沙箱"这一 harness 层级的代表系统给出简要对照，并论证 AgentKernel 的 Execution 支柱在此基础上补充了语义层动态权限收敛
- [[openenv]] — OpenEnv 的 Docker 容器隔离方案 + Cloud Sandbox Providers 安全不变量清单（S1-S6），提供了 agentic RL 训练场景下的又一个执行沙箱参照系
- [[prime-intellect-verifiers]] — verifiers 的独立验证器沙箱设计（IsolatedVerifierEnv）+ 六种 Runtime 隔离级别 + Harbor 集成的网络策略/artifact 预算，提供"评分阶段隔离"这一具体角度的参照
- [[harbor-framework]] — Harbor 官方文档：ASP（Agent Sandbox Protocol）v0 RFC 草案，"harness ↔ 远程沙箱执行边界"的协议化方案，策略层/机制层拆分与"排除 provision"的范围收窄
- [[2404.07972]] — OSWorld：面向 GUI/桌面 computer-use agent 的传统 VM 沙箱，快照式重置 + 混合式初始状态配置，是本页里唯一针对"多 OS 桌面环境"而非"code/terminal 容器隔离"的参照系
- [[2308.03688]] — AgentBench：2023 年最早的任务级 Docker 隔离 + Server-Client 解耦评测框架，是本页技术线的历史起点，见 [[agentbench]]
