---
title: "Harbor（Terminal-Bench 团队的 agent 评测 / 环境框架）"
type: post
id: "harbor-framework"
source_url: https://github.com/harbor-framework/harbor
authors: [Harbor Framework Team]
affiliations: [Laude Institute]
published: 2025-08-04
created: 2026-09-30
tags: [harbor, agent-environment-interface, sandbox-runtime, environment-packaging, atif, asp, network-policies]
concepts: [harbor, agent-execution-sandbox, openenv-interface-spec, verifiers-framework, agentic-rl-frameworks]
rating: 5
issue: 70
parent: ""
---

# Harbor（Terminal-Bench 团队的 agent 评测 / 环境框架）

> Terminal-Bench 团队开源的容器化 agent 评测/RL rollout 统一运行框架：任务 = 自包含目录格式，沙箱/agent 都是可插拔接口，另有 ASP（harness-沙箱执行协议）和 ATIF（轨迹交换格式）两份配套接口标准草案。

## 元信息

- 机构 / 发表时间：Laude Institute（Terminal-Bench 团队），仓库创建于 2025-08-04（GitHub 组织已从 `laude-institute` 迁移为 `harbor-framework`）
- 链接：[GitHub](https://github.com/harbor-framework/harbor)（Apache-2.0，2026-09-30 精读时 5,698 star / 1,889 fork，仍在活跃开发） · [文档](https://docs.harborframework.com) · [Cookbook](https://github.com/harbor-framework/harbor-cookbook) · 官方 harness of [Terminal-Bench-2.0](https://github.com/laude-institute/terminal-bench-2)
- 精读范围：README + 文档站核心页面——任务格式总览（`core-concepts/tasks/overview`）、环境（`environment`）、网络策略（`network-policies`）、独立验证器（`separate-verifier`）、artifacts、自定义沙箱/agent（`custom-sandboxes`/`custom-agents`）、预集成沙箱清单（`pre-integrated-sandboxes`）、ASP 与 ATIF 两份 RFC 页面。未读：`rewardkit`、`harbor-hub`（托管运行）、`jobs/*` 配置细节、`multi-container`/`multi-step` 全文。
- 对比基线/相关：[[openenv-interface-spec]]（另一套 agent-环境通信协议标准，Meta×HF）、[[verifiers-framework]]（本次精读之前，我们对 Harbor 的了解全部来自 verifiers 集成层的转述和 [[2609.26777]] 的使用侧描述，这是第一次直接读 Harbor 自己的文档）

## 要解决的问题

Agent 评测/RL rollout 长期存在两类割裂：一是"任务格式"没有标准，每个 benchmark 自己定义环境怎么跑、怎么打分；二是"harness（agent 循环）"与"沙箱（执行环境）"耦合在一起——要么 agent 的开发者自己动手拆分（只有 Claude Code、Codex 这类agent 自己的团队能做到），要么谁都无法把一个 agent 套到不同的沙箱 provider 上跑。Harbor 想同时解决这两层：任务是不依赖框架的自包含目录格式，可被任何兼容实现消费；沙箱和 agent 各自是一个可插拔接口（`BaseEnvironment`/`BaseAgent`），让"同一个任务、换一个 agent、换一个 sandbox provider"变成配置项而不是重写代码。

## 方法

### 任务格式：自包含目录，不依赖框架

一个 Harbor 任务是 `instruction.md`（指令）+ `task.toml`（配置）+ `environment/`（Dockerfile 或 docker-compose.yaml 等，定义执行环境）+ `solution/`（oracle 解法）+ `tests/`（打分脚本）组成的目录。核心约束：**任务本身不依赖 Harbor 框架**，可以被任何支持该格式的框架消费——Harbor 只是"一种简单的规模化运行方式"，不是任务的必需运行时。打分脚本必须在环境里产出 `/logs/verifier/reward.txt`（或多维度的 `reward.json`）。支持多步任务（`steps/step-1/`、`step-2/`…），每步有自己的 instruction/tests/solution，可共享 `tests/helpers.py` 打分工具函数。

### `BaseEnvironment`：沙箱接口是七个方法

自定义沙箱只需实现 `BaseEnvironment`：`start`/`stop`（生命周期）、`exec`（命令执行，带 cwd/env/timeout/user）、`upload_file`/`upload_dir`/`download_file`/`download_dir`（文件传输），外加声明一个 `EnvironmentCapabilities`（沙箱支持哪些网络模式、Compose、GPU 等）。`_merge_env()` 合并沙箱/agent 阶段/verifier 阶段的环境变量、`_resolve_user()` 解析默认执行用户，官方要求每个 `exec()` 实现都必须调用这两者。这套接口目前已有 30+ provider 实现（本地：Docker/Podman/Apple Container/Singularity；云端：Daytona、Modal、E2B、GKE、EC2、Runloop、Beam、Vercel Sandbox、Prime 等），**任务的 `environment/` 定义在切换 provider 时不用改**，只受 provider 声明的 capabilities 约束。

### `BaseAgent`/`BaseInstalledAgent`：两种 agent 接入方式

Installed agent（推荐，多数内置 agent 走这条路，如 Claude Code）：Harbor 把 agent CLI **装进任务环境内部**跑，只需实现 `install()`（如 `pip install my-agent`）和 `run()`（`exec_as_agent` 在沙箱里跑指令）。External agent（如 Terminus-2）：agent 循环跑在 Harbor 进程里，通过 `BaseEnvironment` 的原语（几乎就是系统调用级别）远程操作沙箱——这是"agent 循环在外、执行在沙箱内"这一模式在 Harbor 里的具体落地方式，对应 [[openenv-interface-spec]] 里"Agent 只管 model/tokenizer"的瘦包装层设计，但 Harbor 给出的是可运行的两条具体接入路径而非单一模式。

### ASP（Agent Sandbox Protocol）：v0 RFC 草案，harness-沙箱执行边界的协议化

这是本次精读里对"环境接入标准与交互规范"这个问题回答最直接的一份材料。ASP 要解决的是比 `BaseEnvironment` 更窄、但更根本的一层：**把"任意 agent harness"和"任意远程沙箱"解耦**，让 Claude Code、Codex 这类别人写的 harness 不用被其开发者重写，也能在远程沙箱里执行工具。核心设计：
- agent 工具分两层——面向模型的**策略层**（工具 schema、截断、分页）和底层的**机制层**（原始 read/write/exec）；ASP 只替换机制层的 I/O 从本地变成走传输协议，策略层不变，因此模型看到的工具行为完全一致，已有 prompt 和 eval 不失效。
- v0 只定义一种传输：**SSH**（已经原生具备命令执行、SFTP 文件传输、认证），协议本身只是一个声明式配置文件 `.asp.json`（`version`/`transport`/`connection.host,port,user,identity,host_key`/`workspace`）。harness 在工作目录（及父目录）发现 `.asp.json` 就把工具 I/O 绑定到该沙箱，**agent 完全不知道自己在远程执行**——它没有任何 verb 能触达 harness 所在机器，边界是能力上的隔离而非提示词约束。
- 范围明确收窄：只标准化 `execute(name, input) -> String` 这一半，**显式排除 `provision({resources})`**——沙箱的创建/配置是编排器（如 Harbor 自己）的职责，必须在 agent 启动前完成，agent 运行期不能拥有 provision 的自由。
- 已验证的 SDK/provider 组合：Python `asyncssh`（异步，支持 SFTP）、OpenSSH 客户端（ControlMaster 复用连接）；Docker（容器内 sshd + 映射端口）、Apple Container、Daytona（managed gateway，token 作为用户名，支持 SFTP 与 `network_block_all`）已验证，E2B/Modal/GKE 尚未验证（缺少原生 SSH endpoint）。
- 一个具体的安全组合验证：SSH 作为**入站**连接，有状态防火墙只放行 harness 发起连接的回包、丢弃沙箱主动发起的一切连接——在 Docker 和 Daytona 上都验证过"全部出站流量断开时 SSH 工具仍能正常工作"，说明 ASP 可以和"沙箱完全无 egress"这一常见安全基线正交组合。
- 这是 **v0 RFC 草案**，作者明确写"schema 在 v0.1/v1 前都可能改"，欢迎评论（PR #3023）；未来计划支持 stdio/HTTP 等更多传输，以及为多语言生成 SDK。

### ATIF（Agent Trajectory Interchange Format）：轨迹的统一 JSON 格式

因为不同 agent 产出的原生日志格式各不相同，每接一个新 agent 就要写一个专属解析器，Harbor 定义了 `trajectory.json`（当前版本 `ATIF-v1.7`）作为统一表示：`agent`（名称/版本/模型）、`steps`（顺序的 system/user/agent 交互，`step_id` 从 1 开始连续编号，agent 步骤可带 `tool_calls`+对应 `observation`+逐步 `metrics`）、可选的 `session_id`/`trajectory_id`/`final_metrics`/`subagent_trajectories`（v1.7 新增，支持嵌套子 agent 轨迹）/`extra`（自定义元数据，Pydantic 模型拒绝未声明字段）。声明 `capabilities.atif = true` 的 agent 会把轨迹写到 `agent/trajectory.json`，结果查看器直接读这个文件渲染 Trajectory 标签页；产出 ATIF 与消费 ATIF（把已有轨迹加载进新 session）是两个独立能力，agent 可以只实现其中一个。提供官方 CLI 校验器（`harbor.utils.trajectory_validator`，检查 schema、step 连续性、tool-call 引用、时间戳、图片引用）。

### 网络策略：三态 + 按阶段覆盖 + capability 门控（比 verifiers 转述的更精确）

`network_mode` 有 `public`/`no-network`/`allowlist` 三态，可以在 `[environment]`（沙箱启动时的默认基线）、`[agent]`（仅 `agent.run()` 阶段，不含 `agent.setup()`）、`[verifier]`（仅打分阶段）、`[verifier.environment]`（独立验证器沙箱的基线）四个阶段分别覆盖——典型用法是装 agent 时用 `public` 基线保证能装依赖，`agent.run()` 阶段切到 `allowlist` 只放行必要 API。每个 `BaseEnvironment` 实现声明自己的 `EnvironmentCapabilities`（`disable_internet`/`network_allowlist`/`network_allowlist_hostnames`/`…_wildcard_hostnames`/`…_ipv4/ipv6_addresses`/`…_cidrs`/`dynamic_network_policy` 等九项细粒度能力），**任务要求的网络模式如果 provider 没声明对应能力，Harbor 在校验阶段直接拒绝这次试验，而不是降级成弱策略跑**。Docker/Podman 的 allowlist 依赖 nftables 内核特性做出站控制（Harbor 自己的 egress-control sidecar），各云 provider 对精确域名/通配符域名/IPv4/IPv6/CIDR 的支持程度参差不齐（如 TensorLake 只支持 IPv4、Vercel 只匹配 TLS SNI 且仅单容器任务生效）——这份能力矩阵本身就是"接入标准要面对多 provider 能力不对齐"这一现实的一份具体样本。

### 独立验证器（Separate Verifier）：官方语义，验证了 verifiers 转述的准确性

默认验证器和 agent 共用同一个容器（`tests/` 在打分阶段上传到 `/tests/`）；`[verifier].environment_mode = "separate"` 或直接声明 `[verifier.environment]` 会在全新沙箱里跑验证——好处除了隔离性，还有可以**预装依赖到验证器镜像里、提前 build**（减少安装抖动、加快打分阶段）以及支持 [regrade](https://docs.harborframework.com/core-concepts/jobs/regrade)（用更新过的验证器对已录制的输出重新打分，不用重跑 agent）。镜像选择优先级明确：`[verifier.environment].docker_image` > `tests/Dockerfile` > `[environment].docker_image` > `environment/Dockerfile`（后两者需要把 `tests/` 上传到 `/tests/`）——**专属验证器镜像必须自带 `/tests/test.sh`，Harbor 不会往这类镜像里上传测试**，这与 [[prime-intellect-verifiers]] 转述的"验证器镜像需自带完整 `/tests` 套件"完全一致，本次精读把这条从"集成层观察到的行为"确认为"Harbor 规范本身的原生要求"。

### Artifacts：声明式产出物收集，agent 文件系统变更默认不传给验证器

`artifacts` 在 `task.toml` 顶层声明要收集的文件/目录（字符串或 `{source, destination, exclude, service}` 对象），Harbor 收集到 `<trial-dir>/artifacts/`。独立验证器场景下**agent 对文件系统的修改默认不会带到新沙箱**，验证器需要的每个产出必须显式声明为 artifact 才会被复制进去（路径按原始 `source` 恢复，`destination` 只影响 host 上的保存路径）；官方明确标注"从 `/logs/artifacts/` 自动收集"这条旧行为即将废弃，要求新任务都显式声明。

### Provider 生态与资源声明

`task.toml` 的 `[environment]` 可声明 `cpus`/`memory_mb`/`storage_mb`/`gpus`/`gpu_types`/`[environment.tpu]`（type/topology），省略则用 provider 默认值；CLI 的 `--cpus`/`--memory` 控制这些声明被解释成 `auto`/`limit`/`request`/`guarantee`/`ignore` 中的哪种语义。30+ 预集成 provider 里 GPU 支持的只有 Daytona/Modal/GKE/Beam/OpenSandbox/Prime 几家，TPU 仅 GKE；provider capability 矩阵（Compose/GPU/Windows/host-mounted logs/SSH streaming）同样是"能力不对齐，Harbor 校验时门控"的模式。

## 实验与结果

这是一个框架/文档仓库，不含基准测评数字：

- 没有给出任何 provider 的冷启动延迟、并发密度、成本对比——这与 [[prime-intellect-verifiers]] 的情况一致（框架文档层面普遍缺失这类量化数据，需要单独实测）。
- 唯一的规模化数字是仓库本身的热度快照：5,698 star / 1,889 fork（2026-09-30，Apache-2.0，组织 `harbor-framework`）。
- ASP 页面给出的是**定性验证**而非量化实验："全部出站流量断开时 SSH 工具仍正常工作"在 Docker 和 Daytona 上验证过，但没有给出延迟、吞吐等数字。

## 局限与疑点

- **ASP 是 v0 RFC 草案，非稳定规范**：作者自己标注 schema 在 v0.1/v1 前会变，目前只验证了两个 agent 示例（一个 vanilla Python agent + 一个叫 pi 的极简 harness 扩展），尚未验证在 Claude Code/Codex 这类生产 agent 上的落地成本。
- **ASP 对 sandbox provider 的验证覆盖率不高**：30+ 预集成沙箱里，ASP 页面只验证了 Docker/Apple Container/Daytona 三家，E2B/Modal/GKE 等仍标"no"，意味着"标准化 harness-沙箱执行边界"这件事目前只是被验证在少数 provider 上，距离"通用协议"还有距离。
- **本次精读止于文档层**，未读 Harbor 源码（`BaseEnvironment`/egress-control sidecar 的具体实现）、未实际跑过 `harbor run`，因此"文档描述的行为"与"实际运行时行为"是否完全一致未经验证。
- **`rewardkit`、`harbor-hub`（托管运行/密钥管理）、`jobs/*` 配置的完整 schema 未读**，这些是文档站里体量不小但本次跳过的部分，如果要评估"是否直接用 Harbor 作为我们的评测/rollout 运行器"，还需要补这几块。
- 与之前 [[harbor]] 概念页"开放问题"里记录的两个疑点对照：一是"Harbor 的沙箱隔离技术细节（容器运行时选型、GPU 资源隔离与超卖策略）仍未披露"——**本次精读依然没有解决这一点**，文档层面只给了 capability 声明（谁支持 GPU/网络隔离），没有给出隔离机制本身的实现细节；二是"verifiers 与 Harbor 是否功能对等需要直读 Harbor 文档才能分清"——**本次精读部分解决**：独立验证器的镜像选择优先级、artifacts 恢复路径规则，都在 Harbor 官方文档里得到了逐字确认，与 verifiers 的转述一致。

## 对我们的启发

- **ASP 的"策略层 vs 机制层"拆分，是目前知识库里对"如何把一个别人写好的 agent harness 接入我们自己的沙箱"这一具体工程问题回答最精确的一份材料**：如果我们平台希望复用 Claude Code / Codex 这类第三方 agent 而不改它们的源码，ASP 提示的路径是找到它们工具实现里的原始 I/O 函数（read/write/exec），把这一层换成走我们沙箱的传输协议，而不用碰它们面向模型的工具 schema/截断/分页逻辑——这比重新实现一遍工具集成的成本低得多。
- **ASP 显式排除 `provision`、只标准化 `execute`，这个边界划分值得直接借鉴**：我们如果要定义"agent 执行层接口"，应该把"沙箱怎么创建/配置/扩缩容"和"agent 怎么在已就绪的沙箱里执行命令"分成两个不相交的关注点，前者留给编排层、绝不让 agent 在运行期有能力触达，这与 [[openenv-interface-spec]] 里"reset/step 永远不作为 MCP 工具暴露给 agent"是同一条原则在不同协议里的重复出现——两个独立来源都得出同一结论，值得当作一条比较可信的设计共识。
- **网络策略"四阶段覆盖 + capability 门控 + 校验不通过就拒绝试验而非降级跑"，是一份可以直接照抄的安全默认值模式**：如果我们平台目前的网络策略配置是"要么全放行要么全禁止"的粗粒度开关，或者在某 provider 不支持某策略时选择静默放宽，Harbor 这里给出的具体反例（宁可拒绝执行也不悄悄放宽）值得对照检查。
- **ATIF 这类统一轨迹格式，如果我们平台需要同时接入多个 agent 并做训练数据收集/离线分析，是一个可以直接复用或参照设计的 schema**，比自己为每个 agent 写专属日志解析器成本低；`subagent_trajectories` 字段对多 agent/子 agent 场景的支持也提示了我们自己轨迹格式设计时应该预留的扩展点。
- **独立验证器沙箱的镜像选择优先级规则**（`[verifier.environment].docker_image` > `tests/Dockerfile` > 继承 agent 镜像）**和 artifacts 必须显式声明才传递**这两条具体规则，可以直接对照我们自己"评测阶段是否复用训练/执行阶段的镜像"这一设计决策——Harbor 的默认假设是"不信任 agent 沙箱残留状态，只信任显式声明的产出"，这与 [[prime-intellect-verifiers]] 里 `IsolatedVerifierEnv` 的假设完全一致，是两个独立框架收敛到同一原则的又一例证。
- Follow-up 建议（可转 issue）：
  1. 实际跑一次 `harbor run`（Docker 本地 + 至少一个云 provider），测一下冷启动延迟、`--n-concurrent` 到多少会遇到瓶颈，填补文档层完全缺失的量化数据空白；
  2. 深入评估 ASP 是否可以直接用于我们自己"复用第三方 agent harness 接入自建沙箱"的场景，先看 Claude Code/Codex 这类目标 agent 的工具实现是否容易做机制层替换；
  3. 读一下 Harbor 的 egress-control sidecar 和容器运行时隔离的源码实现，填补"沙箱隔离技术细节"这个在 [[harbor]] 概念页里持续未解决的开放问题。

## 相关

- 相关概念：[[harbor]]、[[agent-execution-sandbox]]、[[openenv-interface-spec]]、[[verifiers-framework]]
- 相关笔记：[[prime-intellect-verifiers]]（此前对 Harbor 的了解全部来自这篇的集成层转述，本篇是第一次直读 Harbor 官方文档，多处交叉验证一致）、[[openenv]]（另一套 agent-环境接口标准，ASP 的"控制类操作不给 agent"设计与 OpenEnv 的 MCP/HTTP 分离原则相互印证）
