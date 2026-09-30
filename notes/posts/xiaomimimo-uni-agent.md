---
title: "Uni-Agent: Train Long-Horizon Agents at Scale"
type: post
id: "xiaomimimo-uni-agent"
source_url: https://github.com/XiaomiMiMo/uni-agent
authors: [Yuyang Ding, Bo Wen, Xubo Cao, Zhiqiang Zhai, Guangming Sheng, Xibin Wu, Juntao Li, Min Zhang, Uni-Agent Contributors]
affiliations: [verl-project, XiaomiMiMo]
published: 2026-09-21
created: 2026-09-30
tags: [agentic-rl-frameworks, agent-sandbox, rollout-efficiency, swe-bench, terminal-bench]
concepts: [agentic-rl-frameworks, agent-execution-sandbox, harbor, swe-bench-multilingual, grpo, async-rl-training]
rating: 4
issue: 73
parent: ""
---

# Uni-Agent: Train Long-Horizon Agents at Scale

> 把任意 agent harness（Claude Code、Mini-SWE-Agent……）接入 RL 训练的开源框架，用 Agent/Tool/Task/Sandbox 四个抽象统一管理数千并发、长程、有状态的 agent session。

## 元信息

- 机构：仓库 `XiaomiMiMo/uni-agent` 是 `verl-project/uni-agent` 的 fork（GitHub `repository_parent_nwo` 字段确认），fork 于 2026-09-21 创建；引用信息（BibTeX）列出的作者包含 Yuyang Ding、Bo Wen、Xubo Cao、Zhiqiang Zhai、Guangming Sheng、Xibin Wu、Juntao Li、Min Zhang，"Supervisor: Xibin Wu and Juntao Li"——具体所属公司（Xiaomi / verl-project 团队关系）原文未明说，此处不做推断。
- 发表：GitHub 项目，无单独论文；README + [文档站](https://uni-agent.readthedocs.io/en/latest/) 是主要信息来源。
- 链接：[GitHub（XiaomiMiMo fork）](https://github.com/XiaomiMiMo/uni-agent) · [GitHub（verl-project 上游）](https://github.com/verl-project/uni-agent) · [文档](https://uni-agent.readthedocs.io/en/latest/)
- 对比/关联基线：与 [[agentic-rl-frameworks]] 里综述过的 AWorld、ROLL、AgentRL 等框架同属"agentic RL 专用训练框架"一类；任务执行integrates [[harbor]] 作为额外的任务格式；沙箱后端可选 [[agent-execution-sandbox]] 类似的多云隔离方案。

## 要解决的问题

现状是"agent harness"（Claude Code、各类 ReAct/SWE agent 实现）与"RL 训练系统"之间割裂：每接入一个新 harness 或新任务类型，往往要重新写一套 rollout、沙箱管理、reward 计算的胶水代码；同时要把 agent 执行扩展到上千并发的长程、有状态 session（而不是单轮短任务）又对基础设施（沙箱隔离、调度、trajectory 追溯）提出额外要求。Uni-Agent 想用统一接口同时解决这两个问题：**接入任意 harness** + **规模化执行**。

## 方法

### 架构：Gateway + 四个抽象

- **Uni-Agent Gateway**：任何能把模型请求指向 OpenAI/Anthropic 兼容 endpoint 的 harness，都可以直接把该 endpoint 指到 Gateway 上接入——"request string in, training tokens out"，即 Gateway 负责把 harness 的请求/响应转成训练用的 token 序列，harness 本身不需要为接入训练做改造。
- **Agent / Tool / Task / Sandbox** 四个可复用抽象：agent 逻辑、工具、任务环境、沙箱后端、reward 可以独立定制，同时复用同一套评测与训练 runtime。

### 规模化执行

- 支持 1,000+ 长程、有状态 session 并发：分布式 worker + 池化的 Gateway session + 隔离沙箱 + 异步调度；每条 trajectory、日志、reward 都要正确关联回对应 session，保证评测、RL 训练、数据合成的可靠性。
- 集成 [[harbor]]（Terminal-Bench 团队的开源 agent 评测/优化框架）作为额外的任务格式，Harbor 覆盖的所有任务可以直接跑在 Uni-Agent 的推理管线上。

### 沙箱后端：可插拔的多云隔离方案

`SandboxConfig(provider=...)` 支持五种后端，按需选择（provider 懒加载，只需装选中后端的 SDK）：

- **local**：直接在宿主机执行，**不是沙箱**，文档明确警告不要用于需要隔离的任务（命令可读写/删除宿主机文件、改变当前 Python 环境），只建议用于不需要隔离的任务（如 HotpotQA）。
- **Docker**：本地容器隔离，起一个 ephemeral 容器，用 `docker exec` 执行命令、`docker cp` 传文件，退出时销毁容器；`pull_timeout`（默认走 `SANDBOX_STARTUP_TIMEOUT`，600s）与 `start_timeout` 分别限制镜像拉取和容器启动两个阶段，避免卡在慢镜像仓库上耗尽整个启动预算。
- **veFaaS**（Volcengine Function-as-a-Service）：远程弹性沙箱；支持传入多个 function id/route 的逗号分隔列表做负载分散，每个沙箱在生命周期内随机绑定一对 id/route。
- **Modal**：远程 serverless 沙箱，按需拉起、无需自管集群。
- **OpenYuanrong**：远程/自建的弹性沙箱管理服务，配置项包括 CPU/内存 request 与 limit、`idle_timeout`、把某个 image 挂载到指定路径（如工具运行时镜像）、反向隧道（让沙箱通过 `127.0.0.1:<proxy_port>` 访问本地 Gateway）、端口转发到宿主机。

### RL 训练目标

训练侧复用与推理时相同的交互栈，提供全异步（fully async）训练 recipe，用 [[grpo|GRPO]]/GSPO 类目标 + partial rollout 支持，覆盖多任务、多模型、多数据集组合（示例脚本见 `examples/quickstart/training`）。

## 实验与结果

**并行推理与验证**（README「Results」表，节选）：

| Benchmark | Agent | Model | Setting | Score |
|---|---|---|---|:--:|
| SWE-Bench Verified | ReAct | Qwen3-Coder-30B | 100 turns, 128K | 49.2 |
| SWE-Bench Verified | ReAct | Qwen3-Coder-480B | 500 turns, 256K | **64.2** |
| SWE-Bench Verified | Claude Code | Qwen3.5-9B | 200 turns, 128K | 51.0 |
| SWE-Bench Multilingual | ReAct | Qwen3-Coder-30B | 200 turns, 128K | 35.0 |
| Terminal-Bench v2.0 | ReAct | Qwen3.6-35B | 256K | 42.5 |
| Terminal-Bench v2.1 | Claude Code | GLM5.2-733B | 256K | **67.4** |

**Agent RL 训练**（README「Results」表，节选，Base → RL）：

| Model | Agent | Dataset | Setting | Base | RL |
|---|---|---|---|:--:|:--:|
| Qwen3-30B-A3B | ReAct | R2E-Gym | Fully Async, 100 turns, 128K | 22.2 | **36.8** |
| Qwen3-Coder-30B-A3B | ReAct | R2E-Gym | Fully Async, 100 turns, 128K | 46.2 | **52.0** |
| Qwen3.5-9B | ReAct | SWE-reBench | Fully Async, 100 turns, 128K | 53.8 | **59.2** |
| Qwen3-Coder-30B-A3B | ReAct | SWE-reBench | Colocate Async, 200 turns, 128K | 47.4 | **54.2** |
| Qwen3-Coder-30B-A3B | Claude Code | SWE-reBench | Colocate Async, 200 turns, 128K | 40.2 | **46.2** |

这些数字均来自 README 自报表格，未见第三方复现；仓库同时承诺发布"可复现的 recipe"（完整配置、benchmark 设置、结果表、学习曲线）来降低复现门槛，但本笔记未去核实 `examples/` 目录是否覆盖了表中每一行。

## 局限与疑点

- 所有分数都是项目自报（self-reported），README 未说明评测的重复次数、方差、是否有第三方审计——与 [[terminal-bench]] 笔记里强调的"任务有效性审计"角度对照，这里完全没有类似的透明度信息。
- 模型规模、setting（turns/context window）在各行之间不统一（如 SWE-Bench Verified 三行分别用 100/500/200 turns、128K/256K/128K），直接横向比较分数可能不公平，需要看文档里的详细 benchmark 设置页面（README 链接了 `benchmark/inference.html` 与 `benchmark/rl-training.html`，本笔记未展开读取）。
- `local` 后端被文档反复强调"不是沙箱"，说明框架本身把隔离责任交给使用者选型；如果用户为图方便默认选 `local` 跑不受信任的 agent 生成代码，存在明显的安全风险——这是框架设计上留给使用者的坑，而非框架本身的缺陷。
- veFaaS、OpenYuanrong 两个远程后端目前看起来都是国内云厂商生态（火山引擎、OpenYuanrong），Modal 是海外主流 serverless 沙箱服务；三者的冷启动延迟、并发密度、超卖能力等我们最关心的指标，文档中完全没有给出实测数字。

## 对我们的启发

- **"多沙箱后端可插拔"的抽象值得直接对照我们自己的沙箱平台接口设计**：Uni-Agent 用同一个 `SandboxConfig(provider=...)` 接口切换 local/Docker/veFaaS/Modal/OpenYuanrong 五种后端，且明确把"本地直接执行"与"真正隔离"区分开、把 pull/start 超时拆成独立的两段——这种"provider 懒加载 + 分阶段超时预算"的做法可以直接参考，用来加固我们自己沙箱冷启动路径里"镜像拉取慢拖垮整体启动预算"这类问题。
- **"Gateway 统一 harness 接入"这个思路，是我们如果要支持多种 agent harness（而不是自己重新实现每种 agent 逻辑）时的一个可行模式**：只要 harness 能把模型 endpoint 指向一个 OpenAI/Anthropic 兼容的 Gateway，就不需要改 harness 本身代码即可接入训练/评测——这降低了我们平台支持新 agent 框架的边际成本，值得评估我们现有的 rollout 服务是否已经具备类似的"协议兼容层"，还是每接入一个新 harness 都要写专门适配代码。
- **OpenYuanrong 后端的"反向隧道 + 端口转发"配置**（沙箱通过 `127.0.0.1:<proxy_port>` 反向访问宿主 Gateway、`port_forwardings` 把沙箱端口转发到宿主）提示了一种"沙箱网络默认隔离、按需开一条特定通道回连控制面"的网络拓扑模式，可以对照我们自己沙箱的网络策略（是否默认放通所有出站，还是像这里一样收敛到点对点隧道）。
- Follow-up 建议（可转 issue）：
  1. 精读 Uni-Agent 文档站的 `benchmark/inference.html` 与 `benchmark/rl-training.html`，核实各行结果的完整实验设置（重复次数、方差、评测集版本），判断自报表格的可信度；
  2. 找 veFaaS / OpenYuanrong 两个后端的独立资料，补齐冷启动延迟、并发密度、成本这三项我们最关心但本文完全没给的数字，与 [[agent-execution-sandbox]] 笔记里 nono/E2B/Anthropic sandbox-runtime 的对比放在一起看；
  3. 评估我们自己 rollout 服务是否可以提供一个类似 Uni-Agent Gateway 的"OpenAI/Anthropic 兼容 endpoint"，用来降低接入外部 agent harness 的成本。

## 相关

- 相关概念：[[agentic-rl-frameworks]]、[[agent-execution-sandbox]]、[[harbor]]、[[swe-bench-multilingual]]、[[grpo]]、[[async-rl-training]]
- 相关笔记：[[2609.26777]]（Harbor / SWE-Serve，Uni-Agent 集成的任务格式来源）、[[2609.26826]]（Terminal-Bench 3 任务生产审计，可用来对照 Uni-Agent 自报 Terminal-Bench 分数的透明度差距）、[[2609.23377]]（SWE-bench Multilingual 基准来源）
