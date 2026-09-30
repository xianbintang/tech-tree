---
title: "Harbor"
aliases: [Harbor Framework, Harbor agent evaluation framework, ASP, Agent Sandbox Protocol, ATIF, Agent Trajectory Interchange Format]
created: 2026-09-29
updated: 2026-09-30
sources: [2609.26777, prime-intellect-verifiers, harbor-framework, 2601.11868]
---

# Harbor

## 一句话定义

Terminal-Bench 团队做的开源 agent 评测/优化框架，在容器化沙箱环境里执行任务；[[swe-serve]] 用其 0.13.1 版本统一管理 CPU/单卡 H100 的任务执行 [[2609.26777]]。任务是不依赖框架的自包含目录格式（`instruction.md`+`task.toml`+`environment/`+`solution/`+`tests/`），沙箱与 agent 都是可插拔接口（`BaseEnvironment`/`BaseAgent`），另有 ASP（harness-沙箱执行协议）与 ATIF（轨迹交换格式）两份配套接口标准草案 [[harbor-framework]]。这套任务格式的源头是 Terminal-Bench 2.0 论文提出的"指令+Docker 镜像+终态测试+oracle 解+时限"五元组规范 [[2601.11868]]。

## 为什么对我们重要

Harbor 是"repo 级 + GPU 依赖"这类 agent 评测任务的具体沙箱基础设施样本，它的资源配额、超时策略、重跑规则等工程细节，可以直接对标我们自己 agent 训练/评测沙箱平台的设计取舍 [[2609.26777]]。

## 核心机制 / 主要变体

- 定位：容器环境中评测和优化 agent/模型的开源框架，来自 Terminal-Bench 的创建团队 [[2609.26777]]。
- 支持异构硬件：可在纯 CPU 或单卡 H100 GPU 的沙箱环境里执行任务，[[swe-serve]] 用它同时跑 12 个 CPU 任务和 41 个 GPU 任务 [[2609.26777]]。
- 版本：论文实验使用 0.13.1（`github.com/harbor-framework/harbor`）[[2609.26777]]。
- **verifiers 原生支持 Harbor 任务集接入**（`HarborTaskset`，见 [[verifiers-framework]]），从这层集成可以看到 Harbor 规范本身的一些具体设计：任务超时默认应按框架自身速度校准而非直接套用 Harbor 自带值（否则会把模型能力和推理栈速度混在一起）；`[verifier].environment_mode = "separate"` 是 Harbor 规范原生定义的"独立验证器沙箱"语义（验证器镜像需自带完整 `/tests` 套件且可直接拉取）；任务网络策略分 `public`/`no-network`/`allowlist` 三态，`task.toml` 里的 `artifacts` 字段和 verifier collect 钩子（TOML 数组表）定义产出物收集规则 [[prime-intellect-verifiers]]。**本条已通过直读 Harbor 官方文档交叉验证一致**：镜像选择优先级明确为 `[verifier.environment].docker_image` > `tests/Dockerfile` > `[environment].docker_image`/`environment/Dockerfile`（后两者需上传 `tests/`），独立验证器场景下 agent 对文件系统的修改默认不传给验证器，每个产出必须在 `task.toml` 顶层 `artifacts` 里显式声明才会被复制（按原始 `source` 路径恢复，`destination` 只影响 host 保存路径）；网络策略实际是四阶段（`[environment]`/`[agent]`/`[verifier]`/`[verifier.environment]`）可分别覆盖，且每个 provider 通过声明 `EnvironmentCapabilities`（九项细粒度网络能力）门控，任务要求的模式若 provider 未声明支持，Harbor 在校验阶段直接拒绝这次试验，而不是降级成弱策略跑 [[harbor-framework]]。
- **`BaseEnvironment` 沙箱接口**：`start`/`stop`/`exec`（cwd/env/timeout/user）/`upload_file`/`upload_dir`/`download_file`/`download_dir` 七个方法，目前有 30+ provider 实现（本地 Docker/Podman/Apple Container/Singularity；云端 Daytona/Modal/E2B/GKE/EC2/Runloop/Beam/Vercel Sandbox/Prime 等），任务的 `environment/` 定义切换 provider 时不用改，只受 provider 声明的 capabilities 约束 [[harbor-framework]]。
- **`BaseAgent`/`BaseInstalledAgent` 两种 agent 接入方式**：Installed agent（如 Claude Code）把 agent CLI 装进任务环境内部跑；External agent（如 Terminus-2）agent 循环跑在 Harbor 进程里、通过 `BaseEnvironment` 原语远程操作沙箱 [[harbor-framework]]。
- **任务格式的设计哲学：结果驱动（outcome-driven）**——测试只检查任务结束时容器的最终状态，不检查 agent 具体的命令序列或控制台输出，agent 可以用任意方式达成目标；配套的六阶段质量审核（自动 oracle 校验→自查清单→LLM 检查工具→人工评审→多模型实跑区分真失败/任务本身坏了→对抗式 exploit agent→终审）确保任务同时满足 specificity（测试充要性）、solvability（存在会通过的 oracle 解）、integrity（不能靠取巧手段通过）三个标准 [[2601.11868]]。
- **ASP（Agent Sandbox Protocol，v0 RFC 草案）**：标准化"任意 agent harness ↔ 任意远程沙箱"这一执行边界，只覆盖 `execute(name, input) -> String`，显式排除 `provision`（沙箱创建/配置留给编排层，agent 运行期不能有 provision 自由）。核心设计是把 agent 工具拆成面向模型的策略层（schema/截断/分页，不变）和底层机制层（原始 read/write/exec，ASP 替换成走传输协议），因此 agent **完全不知道自己在远程执行**——没有任何 verb 能触达 harness 所在机器，边界是能力隔离而非提示词约束。v0 只支持 SSH 传输，配置是声明式的 `.asp.json`。已验证 SDK：Python `asyncssh`、OpenSSH 客户端；已验证 provider：Docker、Apple Container、Daytona（E2B/Modal/GKE 因缺原生 SSH endpoint 尚未验证）。一个具体验证结果：Docker 和 Daytona 上，沙箱全部出站流量断开时 SSH 工具仍正常工作（有状态防火墙只放行 harness 发起连接的回包），说明 ASP 可以和"沙箱无 egress"安全基线正交组合 [[harbor-framework]]。
- **ATIF（Agent Trajectory Interchange Format，当前 ATIF-v1.7）**：统一的 agent 轨迹 JSON 格式（`agent`/`steps`/`session_id`/`trajectory_id`/`final_metrics`/`subagent_trajectories`/`extra`），解决"每接一个新 agent 就要写专属日志解析器"的问题；声明 `capabilities.atif = true` 的 agent 把轨迹写到 `agent/trajectory.json`，产出 ATIF 与消费 ATIF（加载轨迹进新 session）是两个独立能力；官方提供 CLI 校验器检查 schema/step 连续性/tool-call 引用/时间戳/图片引用 [[harbor-framework]]。

## 工程要点与数字

- [[swe-serve]] 中的执行限额：单次任务尝试最多 350 步或 210 分钟（先到为止），单条命令超时 120 秒 [[2609.26777]]。
- 210 分钟上限是为容纳长任务设置的：[[swe-serve]] 平均任务耗时 43.3 分钟（对比 DeepSWE 的 34.3 分钟），24.5% 的任务均值落在 1–4 小时区间（对比 DeepSWE 的 3.5%）[[2609.26777]]。
- 重跑策略：仅当评测因模型服务路由、runner、硬件或验证器基础设施本身的问题而未能产出有效分数时才重跑；因 agent 自身错误、预算耗尽、测试失败或 agent 补丁导致的崩溃不重跑——即"只为基础设施故障兜底，不为 agent 表现兜底" [[2609.26777]]。
- 执行限额触发率很低：[[swe-serve]] 11 个最佳模型配置的 1,749 次尝试中只有 2.4%（42 次）因超限失败（15 次因 210 分钟耗尽，27 次因 350 步耗尽）[[2609.26777]]。
- **镜像构建与缓存（经 verifiers 的 `prime` runtime 观察到）**：任意可拉取镜像引用第一次被沙箱使用时现场 build 并缓存，VM sandbox 首次构建约 10 分钟（eval dashboard 标记 `build` 状态并打警告），之后同引用的沙箱秒级启动——这是目前知识库里关于 Harbor 生态镜像分发唯一的一条具体数字，但它是 verifiers 集成层观察到的产品行为，不是 Harbor 自身的受控实测 [[prime-intellect-verifiers]]。
- **Artifact 传输默认硬预算 32MiB**（每个 solver 跨所有服务合计，可调），失败的 collect hook 会直接判 rollout 失败，因为 artifact 在这里是打分输入而非可观测性日志 [[prime-intellect-verifiers]]。

## 争议与矛盾

（暂无跨来源分歧；[[harbor-framework]] 直读官方文档后，[[prime-intellect-verifiers]] 转述的镜像选择优先级、独立验证器语义、网络策略三态均得到逐字确认，未发现矛盾）

## 开放问题

- **Harbor 的沙箱隔离技术细节（容器运行时选型、GPU 资源隔离与超卖策略）本次精读仍未解决**：直读官方文档后，文档层面只给出了 provider capability 声明（谁支持 GPU/哪种网络隔离），没有披露隔离机制本身的实现（如是否用 gVisor/Kata 这类容器运行时增强隔离、GPU 是否超卖）——这个问题已经跨两轮精读（论文使用侧 + 官方文档侧）都未获得答案，值得直接读源码或联系维护者 [[2609.26777]] [[harbor-framework]]。
- verifiers 文档承认自己与 Harbor 尚未功能对等（不能从 `tests/Dockerfile` 现场构建验证器镜像、shared 验证器不能切换网络策略、不支持 multi-step 任务）——**这一点已通过直读 Harbor 文档部分厘清**：独立验证器镜像选择优先级、artifacts 恢复规则确认是 Harbor 原生规范而非 verifiers 集成层的取舍；但 verifiers 具体缺失的三项能力（现场构建验证器镜像等）背后 Harbor 自身是如何实现的仍未读到 [[prime-intellect-verifiers]] [[harbor-framework]]。
- **ASP（Agent Sandbox Protocol）是 v0 RFC 草案**，只验证了 2 个 agent 示例、3 个 sandbox provider（Docker/Apple Container/Daytona），尚未验证在 Claude Code/Codex 这类生产 agent 上的落地成本，也未支持 SSH 之外的传输（stdio/HTTP 待定）[[harbor-framework]]。

## 相关概念

[[swe-serve]]、[[verifiers-framework]]、[[agent-execution-sandbox]]、[[openenv-interface-spec]]

## 相关来源

- [[2609.26777]] — 用 Harbor 0.13.1 执行 SWE-Serve 的全部 53 个任务，报告了具体的资源配额与重跑策略
- [[prime-intellect-verifiers]] — verifiers 对 Harbor 任务集的原生集成，补充了镜像构建缓存行为、独立验证器沙箱语义、网络策略三态等具体工程细节
- [[harbor-framework]] — 直读 Harbor 官方文档：任务格式、`BaseEnvironment`/`BaseAgent` 接口、ASP（harness-沙箱执行协议）、ATIF（轨迹交换格式）、网络策略四阶段与 capability 门控、独立验证器镜像选择规则，交叉验证了此前从 verifiers 转述得到的多条结论
- [[2601.11868]] — Terminal-Bench 2.0 论文：Harbor 任务格式与结果驱动测试哲学的源头，六阶段质量审核流程与 specificity/solvability/integrity 三标准的出处
