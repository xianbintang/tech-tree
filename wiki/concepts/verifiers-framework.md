---
title: "verifiers：Taskset/Harness/Runtime 环境打包框架"
aliases: [Verifiers, prime-intellect-verifiers, vf-eval, vf-init, Taskset, Environment Hub]
created: 2026-09-30
updated: 2026-09-30
sources: [prime-intellect-verifiers]
---

# verifiers：Taskset/Harness/Runtime 环境打包框架

## 一句话定义

Prime Intellect 维护的开源库：把"agentic RL 环境"拆成 Taskset（数据+打分）/ Harness（模型运行的程序）/ Agent（harness×model×runtime）/ Env（多 agent 控制流）/ Runtime（执行沙箱）五个正交抽象，并给出"环境=可安装 Python 包+固定入口点"的具体打包规范，配 `vf-init`/`vf-eval` CLI 和 Environment Hub 分发 [[prime-intellect-verifiers]]。

## 为什么对我们重要

这是目前知识库里关于"环境+验证器打包与分发规范"最完整的一份可运行参照——不是像 [[openenv-interface-spec]] 那样只定义通信协议，而是把"怎么打包一个环境、怎么让它被别人的 CLI 发现和复用、怎么在沙箱里跑评分"整条链路都给出了具体实现，包括一个和我们平台高度相关的设计：**独立验证器沙箱**（solver 沙箱销毁后在全新沙箱里恢复 artifacts 打分），直接对应"如何防止 agent 污染自己的评分环境"这个我们必须解决的问题 [[prime-intellect-verifiers]]。

## 核心机制 / 主要变体

- **五层正交抽象**：Taskset（`load()` 构造 Task 列表）、Task（`@vf.reward`/`@vf.stop`/`@vf.metric` 装饰的评分与生命周期）、Harness（Claude Code/Codex/bash/browser_use/null 等内置，也支持自定义）、Agent（harness×model×runtime 组合）、Env（`SingleAgentEnv`/`IsolatedVerifierEnv`/`AgenticJudgeEnv`/`UserSimEnv`/`BestOfNEnv`）[[prime-intellect-verifiers]]。
- **六种 Runtime（执行沙箱）**：`subprocess`（本地进程，仅调试，有副作用串扰风险）、`docker`、`podman`、`apptainer`（HPC 场景，host network，无 egress 策略）、`prime`/`modal`（远程 sandbox，官方定位的生产路径）[[prime-intellect-verifiers]]。
- **打包规范**：`vf-init <name>` 脚手架出 `环境包/{__init__.py, taskset.py}`，`__init__.py` 导出 `Taskset` 类作为入口点供 `vf-eval` 发现；仓库自身用 `[tool.uv.sources]` 把内置环境注册成本地 editable 包——这就是"环境即包"的具体样子 [[prime-intellect-verifiers]]。
- **配置分层**：`TasksetConfig`（数据集级：切分/大小/种子）与 `TasksetConfig.task`（任务执行/打分级：judge 模型、容差），均可 CLI 点号覆盖或 TOML 配置；stop/metric/reward 钩子可以完全不改代码、靠 TOML 按 import path 挂载外部函数替换同名装饰器方法 [[prime-intellect-verifiers]]。
- **独立验证器沙箱（IsolatedVerifierEnv）**：`--env.id isolated-verifier` 时，agent 正常跑完声明 artifacts，环境**销毁 solver 沙箱**，创建全新验证器沙箱恢复 artifacts 后跑确定性打分；验证器沙箱可独立配置 runtime/资源/网络策略，必须是容器/远程类型（Docker/Prime），host subprocess 拒绝绝对路径 artifact 恢复，配置了模型 judge 的任务不能走这条路径 [[prime-intellect-verifiers]]。
- **Harbor 集成**（原生支持 [[harbor]] 任务集接入为 `HarborTaskset`）：默认忽略 Harbor 自带超时（避免把模型能力和自己推理栈速度混在一起）；`prime` runtime 上镜像首次使用现场 build+缓存、后续秒级启动；独立验证器环境严格照抄 Harbor 语义（验证器镜像需自带完整 `/tests` 且可拉取，verifiers 本身不构建镜像）；网络策略三态 `public`/`no-network`/`allowlist`，托管 web search 工具按 provider 域名翻译白名单、翻译不了就禁用而非放宽；Compose 多服务任务本地需显式 `--env.trust-compose`；artifact 传输默认 32MiB 硬预算，collect hook 失败直接判 rollout 失败（不像 Harbor 自己"记日志继续跑"）[[prime-intellect-verifiers]]。
- **架构**：orchestrator/worker 分离（client 侧持有 taskset，只加载一次分发给 worker）；模型流量走**拦截服务器**而非直连 provider，按 harness 期望协议适配（Codex→OpenAI Responses，Claude Code→Anthropic Messages），顺带做实时 trace 构建、强行设置采样参数、拦截改写工具响应/web search 结果以屏蔽 reward hacking [[prime-intellect-verifiers]]。
- **与 OpenEnv 的关系**：两者不是竞争标准——verifiers 把 `openenv` 作为可选依赖，`openenv_wordle` 是内置示例环境，说明"打包分发框架"和"agent-环境通信协议标准"可以叠加使用 [[prime-intellect-verifiers]]。

## 工程要点与数字

- Harbor 集成里 `prime` runtime 首次镜像 build 约 10 分钟（VM sandbox，dashboard 标记 `build` 状态并打警告），之后同引用秒级启动——本次精读唯一一处具体量化数字，且是产品行为描述而非受控实验 [[prime-intellect-verifiers]]。
- Artifact 传输默认预算 32MiB（每 solver 跨所有服务合计），训练 checkpoint/VM 磁盘文件场景需显式调大 [[prime-intellect-verifiers]]。
- 验证器沙箱失败重试次数默认 2（`--env.verifier.retries`），覆盖 setup→恢复→staging→打分整条链路 [[prime-intellect-verifiers]]。
- 仓库层面：4,660 star / 685 fork（2026-09-30 快照），MIT 许可，创建于 2025-01-22，仍在活跃开发；`pyproject.toml` 用 `exclude-newer = "7 days"` 的 uv 锁定策略，并深度绑定 Prime Intellect 自家包（prime-tunnel/prime-sandboxes/prime-runs），说明本地 docker/podman/apptainer 路径"够用但非生产主推" [[prime-intellect-verifiers]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源；注意仓库正处于 v0→v1 不兼容重写，文档明确"legacy v0 stack has been removed"——任何基于旧版 `import verifiers as vf`（经典 Environment/Rubric/Parser 设计）的第三方资料目前已不适用于当前主线，引用时需注明版本 [[prime-intellect-verifiers]]）

## 开放问题

- 拦截服务器（interception server）的具体实现、延迟开销未披露，本次精读止于文档层的行为描述 [[prime-intellect-verifiers]]。
- 网络策略"翻译成 provider 域名白名单"的规则完整性/时效性未说明（provider 侧域名变化是否会导致误禁用）[[prime-intellect-verifiers]]。
- Environment Hub 上的第三方用户环境有多大比例还停留在 v0（未随重写迁移），影响"环境生态互操作性"的实际程度未知，需要单独调研 [[prime-intellect-verifiers]]。
- 各 Runtime（docker/podman/apptainer/prime/modal）之间的冷启动时间、并发密度对比数据未披露，需要自己实测才能拿到可比数字 [[prime-intellect-verifiers]]。

## 相关概念

[[agentic-rl-frameworks]]、[[agent-execution-sandbox]]、[[harbor]]、[[openenv-interface-spec]]、[[agentic-rl-environments]]、[[reasoning-gym]]（同一批"环境接入标准"精读里唯一的非 agentic 单轮环境案例，二者面向的任务类型互补）

## 相关来源

- [[prime-intellect-verifiers]] — 精读 README + docs/v1 全部文档 + AGENTS.md + pyproject.toml：五层抽象、打包规范、独立验证器沙箱、Harbor 集成细节、拦截服务器架构
