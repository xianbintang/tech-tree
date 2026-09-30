---
title: "verifiers — Prime Intellect 的 RL 环境与评测库"
type: post
id: "prime-intellect-verifiers"
source_url: https://github.com/PrimeIntellect-ai/verifiers
authors: [William Brown]
affiliations: [Prime Intellect]
published: 2025-01-22
created: 2026-09-30
tags: [agentic-rl-frameworks, environment-packaging, harness, sandbox-runtime, harbor, mcp]
concepts: [verifiers-framework, agentic-rl-frameworks, agent-execution-sandbox, harbor, openenv-interface-spec]
rating: 5
issue: 70
parent: ""
---

# verifiers — Prime Intellect 的 RL 环境与评测库

> Prime Intellect 维护的开源库：把"环境"拆成 Taskset/Harness/Agent/Env/Runtime 五个正交抽象，配 `vf-init`/`vf-eval` CLI 与 Environment Hub，是"环境+验证器打包与分发规范"的一个可运行实现，而非纸面标准。

## 元信息

- 机构 / 作者：Prime Intellect（原作者 William Brown @willccbb），仓库创建于 2025-01-22，本次精读时（2026-09-30）4,660 star / 685 fork，MIT 许可，仍在活跃开发（当天有 push）
- 链接：[GitHub](https://github.com/PrimeIntellect-ai/verifiers) · [Environment Hub](https://app.primeintellect.ai/dashboard/environments) · [PyPI](https://pypi.org/project/verifiers/) · 训练配套框架 [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl)
- 精读范围：README + `docs/v1/`（overview、architecture、tasksets、env、harnesses、agent、evaluation、harbor）+ `AGENTS.md` + `pyproject.toml`。仓库正处于 v0 → v1 的重写：v1 是当前主线（`verifiers.v1`），旧的 `import verifiers as vf`（v0）已被移除，文档明确写"v1 is what environments should target"。**这本身是一条值得记录的事实**：一个 4.7K star 的生产库在半年多的窗口里做了一次不兼容的大重写，说明"环境接口标准"这件事在 2025–2026 还处于快速迭代期，还没有定型。
- 对比基线/相关：[[openenv-interface-spec]]（另一套环境接口标准，来自 Meta×HF）、[[harbor]]（verifiers 原生支持接入的容器化评测框架）、[[agentic-rl-frameworks]]（verifiers 在综述 Table 11 里已被列为 12 个 Agentic RL 专用框架之一，但此前只有一句话描述）

## 要解决的问题

Agentic RL 训练里，"环境"（数据 + 打分逻辑 + agent 执行方式 + 隔离沙箱）长期是每个团队各写一套的碎片化状态。verifiers 想解决的是比 OpenEnv 更落地的一层问题：不只定义"agent 和环境该用什么协议通信"，还定义了**一整套可安装、可复用、可发布的环境打包格式**——一个环境是一个可以 `pip install`/editable-install 的 Python 包，遵循固定的类结构（`Taskset`/`Task`/`TaskData`/`TasksetConfig`），可以被 `vf-eval` 直接发现、可以推送到 Environment Hub 给别人复用，也可以作为训练信号接入 prime-rl。

## 方法

### 五层正交抽象

- **Taskset**：数据集 + 加载器。`load()` 方法从数据源构造一组 `Task`，用 `Taskset[TaskT, ConfigT]` 声明任务类型和配置类型。
- **Task**：单个任务的行为——评分（`@vf.reward`）、停止条件（`@vf.stop`）、生命周期钩子、工具、指标（`@vf.metric`）。任务数据本身（`TaskData`）是不可变对象（prompt、文件、参考答案、资源需求）。
- **Harness**：模型运行所在的**程序**——Claude Code、Codex、bash、browser_use（CDP 驱动）、null（无工具）等内置，也支持自定义（继承 `Harness`，实现 `setup()` 装环境、`launch()` 跑到完成）。
- **Agent**：`harness × model × runtime policy` 的组合，产出一条 `Trace`。
- **Env**：定义多 agent 之间的控制流（最简单是 `SingleAgentEnv`），内置 `IsolatedVerifierEnv`（评分在独立沙箱里跑）、`AgenticJudgeEnv`（solver+judge 两阶段）、`UserSimEnv`（模拟用户多轮对话）、`BestOfNEnv`（n 次独立尝试取最优/pass@k）。
- **Runtime**：执行沙箱，六种：`subprocess`（本地进程，仅调试用，会有副作用串扰）、`docker`、`podman`、`apptainer`（HPC 场景，host network，无 egress 策略）、`prime`/`modal`（远程 sandbox，面向训练与高并发评测的生产路径）。

### 打包与分发：一个环境 = 一个 Python 包

`uv run vf-init addition-v1` 脚手架出 `environments/addition_v1/addition_v1/{__init__.py, taskset.py}`，`taskset.py` 里只需定义 `TaskData`（不可变数据行）、`Task`（`@vf.reward` 装饰评分函数）、`TasksetConfig`（暴露给用户的可配置项）、`Taskset`（`load()` 构造任务列表），`__init__.py` 导出这个 `Taskset` 类作为入口点——`vf-eval` 靠这个入口点发现并加载环境。`-T`/`-H` 选项可以同时脚手架一个 `vf.Toolset`（工具服务器，走 MCP 装进支持的 harness）或自定义 `vf.Harness`。仓库自己的 `pyproject.toml` 用 `[tool.uv.sources]` 把 18 个内置 example 环境都注册成 `path = "environments/xxx", editable = true` 的本地包，这正是"环境即包"这个设计在真实仓库里的样子。

### 配置面：TOML + CLI 双通道，任务级/任务集级分层

配置分两层：`TasksetConfig`（如数据集切分、大小、种子）和 `TasksetConfig.task`（每个任务执行/打分时用到的值，如 judge 模型、容差）。两层都可以从 CLI 用点号覆盖（`--env.taskset.num-tasks`、`--env.taskset.task.tolerance`）或写进 TOML（`[env.taskset]`）。更进一步，stop/metric/reward 三种钩子可以**完全不改代码**、只靠 TOML 把外部函数按 import path 挂进任务（`fn = "my_hooks.py:two_turns"`），挂载的钩子会替换同名的装饰器方法，支持权重（reward）和优先级排序。这套"任务集作者写代码定义结构，使用者靠配置调参和换打分函数"的分层，是 AGENTS.md 里"minimal config surface"原则的具体落地。

### 任务选择与惰性/无限任务集

`taskset.include(idx=[...]).exclude(names=[...]).shuffle(seed=0).take(5)` 链式视图选任务；CLI/TOML 的 `select` 块按固定顺序 `include → exclude → shuffle → skip → limit` 应用。`load()` 可以是生成器而非列表，支持**无限任务集**（`INFINITE = True`，如程序化生成的 wordle），但必须用 `take`/`-n`/闭区间 `include.idx` 显式限界，否则报错——这是对"程序化生成环境"这一趋势（对照 [[agentic-rl-environments]] 里 R2E-Gym/SWE-Smith 的程序化合成）在框架层给出的具体工程约束。

### 隔离评分：IsolatedVerifierEnv 与"独立验证器沙箱"

这是与我们沙箱平台关系最直接的设计。默认情况下 agent 的评分逻辑跑在它自己污染过的同一个沙箱里，容易被 agent 的副作用（篡改测试文件、留下作弊痕迹）干扰。`--env.id isolated-verifier` 选择另一条路径：agent 正常跑完并声明产出的 artifacts（`TaskData.artifacts`），环境**销毁 solver 的沙箱**，创建一个全新的验证器沙箱，把声明的 artifacts 和 `/logs/artifacts` 恢复进去，再跑确定性的 `@vf.reward`/`@vf.metric`。验证器沙箱可以独立配置 runtime 类型、资源、网络策略（`--env.verifier.runtime.*`），失败时按 `--env.verifier.retries`（默认 2）重试整条链路（setup→恢复→staging→打分）。约束也很明确：验证器沙箱必须是容器/远程类型（Docker/Prime），host subprocess runtime 拒绝做绝对路径 artifact 恢复；配置了模型 judge 的任务不能走这条路径（judge 需要走 `AgenticJudgeEnv`）。

### Harbor 集成：复用容器化评测任务集的具体细节

verifiers 原生支持把 [[harbor]] 的任务集（如 terminal-bench-2）接成 `HarborTaskset`，只需继承 `HarborConfig` 指定数据集名。几个对我们平台直接有用的工程细节：
- **Harbor 超时默认被忽略**（`ignore_timeouts = true`）：因为 Harbor 任务的超时是按 Harbor 自己的 runtime 校准的，直接套用会把"模型能力"和"你自己推理栈的速度"混在一起——这是一个容易被忽视但很实际的评测方法论坑；`timeout_multiplier`/`resource_multiplier` 可以整体缩放超时和 CPU/内存/磁盘配额。
- **镜像构建与缓存**：在 `prime` runtime 上，任意可拉取的镜像引用第一次被沙箱使用时，平台会现场 build 并缓存（VM sandbox 首次构建约 10 分钟，eval dashboard 标记为 `build` 状态并打警告），之后同引用的沙箱几秒启动——这是一个具体的"首次冷启动代价 vs. 后续复用收益"的量化参照点。
- **独立验证器环境是 Harbor 规范原生支持的**（`[verifier].environment_mode = "separate"`），verifiers 的实现严格照抄 Harbor 语义：验证器镜像必须自带完整 `/tests` 套件且可直接拉取（**verifiers 本身不构建镜像**，需要用户自己 build+push），分数从 `/logs/verifier/reward.json`（或 `reward.txt`）读取；非 separate 模式下重新走 separate 语义会直接拒绝执行（"refuses to grade in the agent's box rather than silently losing its isolation"）而不是静默降级。
- **网络策略三态**：`public`（allowlist = `["*"]`）/`no-network`（allowlist = `[]`，只留框架路由）/`allowlist`（自定义 `allowed_hosts`），trusted 的 task/harness setup 阶段始终在线，策略从 agent 启动前生效到评分结束；OpenAI/Anthropic 的托管 web search/fetch 工具会被翻译成对应 provider 域名的白名单，翻译不了就直接禁用而不是放宽策略。
- **Docker Compose 多服务任务**：本地 Docker 需要显式 `--env.trust-compose`（因为 compose 任务可以声明挂载 host 文件和 Docker 特权，framework 明确把它标为"仅信任来源使用"）；Prime/Modal 两种远程 runtime 分别用一整台 VM 跑 Docker+全部服务、或用 Modal 的实验性 VM backend，GPU Compose 任务目前不支持。
- **Artifact 传输有硬预算**：`--env.taskset.artifact-max-bytes` 默认 32MiB（每个 solver 跨所有服务合计），需要传训练 checkpoint 或整块 VM 磁盘文件时要显式调大；一个失败的 collect hook 会直接判 rollout 失败（对照 Harbor 自己"记录日志但继续跑"的宽松处理——因为这里的 artifact 是打分输入而不是可观测性日志，静默缺失会让验证器打分一个过期状态）。

### 架构：orchestrator/worker 分离 + 模型请求拦截层

服务端评测或 prime-rl 的 orchestrator 创建 worker 进程分发 rollout 请求；client 侧持有 taskset（只加载一次，逐任务发给 worker）。真正跑 harness 的是 worker 里的 runtime。Harness 不直接调用模型 provider 的 endpoint，而是走一个**拦截服务器**（interception server，走本地连接或 Prime Tunnel），按 harness 期望的协议转发（Codex 期待 OpenAI Responses API，Claude Code 期待 Anthropic Messages API，拦截层各自适配）。这个拦截层顺带做了三件事：实时构建 trace（trajectory 边产生边收集，不用等 harness 跑完再解析日志）、给不暴露采样参数配置口的 harness 强行设置 sampling 参数、拦截/改写工具响应或 web search 结果以屏蔽 reward hacking——第三点是一个我们平台目前可能没有的能力：**在模型流量层做 reward-hacking 检测/改写**，而不只是在最终打分脚本里做静态检测。

## 实验与结果

这是一个框架仓库，不含基准测评数字：

- 没有给出各 runtime（docker/podman/apptainer/prime/modal）的冷启动时间、并发密度对比，也没有给拦截服务器的延迟开销数据。
- 唯一一处具体量化信息是 Harbor 集成里"prime runtime 首次镜像构建约 10 分钟、后续秒级启动"这一条——且这是产品行为描述，不是受控实验结果。
- `pyproject.toml` 里 `exclude-newer = "7 days"`（uv 锁定策略，只锁定 7 天内发布的依赖版本）和大量绑定 Prime Intellect 自家包（`prime-tunnel`、`prime-sandboxes`、`prime-runs`）说明这个库与 Prime Intellect 自己的云基础设施耦合较深，本地 `docker`/`podman`/`apptainer` 是"够用但非生产主推"的路径，`prime`/`modal` 才是官方定位的生产路径。

## 局限与疑点

- **v0 → v1 重写带来的文档/生态断层**：仓库明确写"legacy v0 stack has been removed"，意味着任何基于旧版 `import verifiers as vf`（Environment/Rubric/Parser 那套更广为人知的经典设计）写的教程、博客、第三方集成代码目前已经不适用于当前主线；本次精读只覆盖了 v1。
- **`docs/`/`skills/`/`configs/` 被 AGENTS.md 明确标注为"deliberately sparse"**：意味着这份公开文档本身就不是完整规范，很多细节（如具体的拦截服务器实现、Prime Tunnel 协议细节）要读源码才能确认，本笔记未深入到源码层。
- **Harbor 集成"目前还没有和 Harbor 平级"**：文档自己列出的 Shortcomings 包括不能从 `tests/Dockerfile` 现场构建验证器镜像（必须用户自己 build+push）、shared 验证器不能切换网络策略、不支持 multi-step 任务——这些是明确的功能缺口而非设计终态。
- **网络策略"翻译"机制的鲁棒性未经验证**：把通配符 host allowlist 翻译成 OpenAI/Anthropic 托管工具的域名列表这件事，本文只给出行为描述（翻译不了就禁用），没有给出翻译规则本身的完整性/时效性说明（provider 侧域名变化会不会导致误禁用）。
- 本次精读止于文档层，没有实际跑 `vf-eval` 验证过 CLI 行为、拦截服务器实测延迟、或 Harbor 集成的端到端效果，这些是留给后续验证的开放项。

## 对我们的启发

- **"独立验证器沙箱"（IsolatedVerifierEnv / Harbor separate verifier）这套设计，是目前我们知识库里关于"防止 agent 污染自己的评分环境"最具体的一份工程参照**：销毁 solver 沙箱 → 全新沙箱 → 恢复声明的 artifacts → 打分，并且明确把"agent 生成代码不可信"作为默认假设（validator 只信任声明的 artifacts，不信任 solver 沙箱残留状态）。如果我们现有的评测流水线是"agent 跑完直接在同一个沙箱里跑测试脚本"，这是一个可以直接抄的隔离模式，比自己重新设计风险更低。
- **"网络策略翻译成允许的托管工具域名，翻译不了就禁用而不是放宽"**——这是一条比较克制的安全默认值原则，值得对照我们自己在处理"agent 需要访问外部 API/工具"时是怎么做网络策略降级的：宁可功能缺失也不悄悄放宽白名单。
- **模型流量拦截层做实时 trace 构建 + reward-hacking 检测/改写，是一个我们目前架构里可能没有覆盖的能力面**：如果我们的沙箱执行层是"训练循环外部黑盒调用模型 API，事后从日志解析 trajectory"，verifiers 的做法提示了另一条路——在离 agent 和模型之间插一层可编程的中间人，可以更早、更细粒度地拿到信号（不用等一整条 episode 跑完再解析）。
- **"环境=可安装 Python 包 + 固定入口点 + Environment Hub 分发"这套打包规范，直接回答了 issue #70 关心的"环境+验证器打包与分发规范"这个问题**：相比 OpenEnv 的"接口协议标准"，verifiers 给出的是"打包元数据+CLI+Hub"这一整套更完整的分发工具链范式，如果我们要自建"环境市场/环境复用机制"，这是比 OpenEnv 更直接可抄的参照（两者不冲突：verifiers 甚至把 `openenv` 作为可选依赖、`openenv_wordle` 作为示例环境，说明两套标准在实践中可以叠加）。
- **Harbor 镜像"首次 build ~10 分钟、后续秒级启动"这条具体数字，是对我们自己"镜像分发与按需加载"（参见 [[sandbox-image-distribution]]）优化优先级排序的一个外部印证**：即使不掌握 Harbor 内部实现，这条产品行为描述本身说明"首次构建代价 vs. 复用收益"在业界是被明确当作产品体验问题在处理的（现场标记 `build` 状态、打警告），而不是被忽略的细节。
- Follow-up 建议（可转 issue）：
  1. 实际跑一次 `uv run vf-init` + `uv run vf-eval`，验证 `IsolatedVerifierEnv` 的沙箱切换延迟、artifact 恢复的实际开销，看是否可以直接复用这套模式改造我们自己的评测流水线；
  2. 深入读一下拦截服务器（interception server）的源码实现（本次只读到文档层的行为描述），评估我们是否需要类似的"模型流量中间层"来做实时 trace 采集或 reward-hacking 拦截；
  3. 追踪 verifiers v0→v1 的迁移文档/changelog，确认目前公开的第三方环境（Environment Hub 上的用户贡献环境）有多大比例还停留在 v0，评估这对"环境生态互操作性"的实际影响有多大。

## 相关

- 相关概念：[[verifiers-framework]]、[[agentic-rl-frameworks]]、[[agent-execution-sandbox]]、[[harbor]]、[[openenv-interface-spec]]
- 相关笔记：[[openenv]]（另一套环境接口标准，两者可叠加而非竞争）、[[2609.26777]]（SWE-Serve 论文用 Harbor 0.13.1 跑评测，是 [[harbor]] 概念页现有的唯一来源）
