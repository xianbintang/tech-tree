---
title: "rLLM / DeepSWE：开源 Agent RL 训练框架与 SWE Agent 训练实践"
type: post
id: "rllm-deepswe"
source_url: https://github.com/rllm-org/rllm
authors: [Michael Luo, Naman Jain, Jaskirat Singh, Sijun Tan, Colin Cai, Tarun Venkat, Manan Roongta, Li Erran Li, Raluca Ada Popa, Koushik Sen, Ion Stoica, Ameen Patel, Qingyang Wu, Alpay Ariyak, Shang Zhu, Ben Athiwaratkun, Ce Zhang]
affiliations: [Agentica (Berkeley Sky Computing Lab), Together AI]
published: 2025-07-02
created: 2026-09-30
tags: [agentic-rl, swe-agent, grpo, rollout-training-disaggregation]
concepts: [agentic-rl-frameworks, grpo, agentic-rl-training-stability, rollout-training-disaggregation]
rating: 4
issue: 72
parent: ""
---

# rLLM / DeepSWE：开源 Agent RL 训练框架与 SWE Agent 训练实践

> Agentica 团队开源的 agent RL 训练框架 rLLM（harness/沙箱/训练后端三者解耦），用它训出的 DeepSWE-Preview（Qwen3-32B 纯 RL）在 SWE-Bench-Verified 上 42.2% Pass@1、hybrid TTS 后 59.0%；训练算法 GRPO++ 与系统侧 Kubernetes 化 Docker 编排是两块对我们最有参照价值的工程细节。

## 元信息

机构：Agentica / Berkeley Sky Computing Lab、Together AI / 发表：DeepSWE 博客 2025-07-02（rLLM 仓库本身持续演进，本文读的是 2026-09 时点的 README + DeepSWE 原始博客）/ 链接：[rLLM GitHub](https://github.com/rllm-org/rllm) · [DeepSWE 博客](https://pretty-radio-b75.notion.site/DeepSWE-Training-a-Fully-Open-sourced-State-of-the-Art-Coding-Agent-by-Scaling-RL-22281902c1468193aabbe9a8c59bbe33) · [HF Model](https://huggingface.co/agentica-org/DeepSWE-Preview) · [R2E-Gym Dataset](https://huggingface.co/datasets/R2E-Gym/R2E-Gym-Subset) / 对比基线：Devstral-Small(24B)、Openhands-LM(32B)、SWE-Agent-LM(32B)、R2EGym-Agent(32B)、Skywork-SWE(32B)、[[skyrl-v0]] 系的 SkyRL-Agent(14B)。

## 要解决的问题

已有的 reasoning RL 工作（DeepScaleR、DeepCoder）证明了单轮数学/代码任务上 RL scaling 的有效性，但把 RL scaling 推广到长程、多步、agentic 任务（尤其是真实软件工程：导航代码库、编辑文件、跑测试、根据反馈迭代）仍是开放问题。同时，训练这类 agent 的基础设施本身也不成熟——不同框架（VeRL、OpenHands、SWE-Agent、rLLM 前身版本）各自绑定固定的 harness/环境/训练后端组合，eval 用的 agent 代码和训练用的往往是两套实现，难以复用和对比。rLLM 想解决的是后者（框架层面的解耦），DeepSWE-Preview 是用 rLLM 解决前者（长程 SWE agent 的 RL scaling）的一个具体案例。

## 方法

**rLLM 框架**：核心抽象是 `Agent → Traces（自动记录）→ Rewards（用户逻辑）→ RL Update`。Workflow Engine 并行跑 N 个 agent 实例做 rollout 收集；Model Gateway 通过 URL 路由的 session 透明捕获每次 LLM 调用的 token id 和 logprob，agent 代码本身不需要感知训练/推理的区别；Transform Pipeline 把 trace 分组算 advantage；训练后端在 verl（分布式多 GPU）、tinker（单机）、fireworks 之间切换只需改一个 flag。数据结构分三层：Episode（一个任务）→ Trajectory（一次 agent 运行）→ Step（一次 LLM 调用）。这与 [[agent-rl-credit-assignment]] 里讨论的 transition-based 拆分（Agent Lightning 的 LightningRL）思路一致，都是把"一条完整 agent 执行"拆成训练算法能吃的最小单元，但 rLLM 没有像 Agent Lightning v1.0 那样系统化讨论 retokenization/动态样本数带来的具体工程挑战，README 层面看不到这部分细节。

**DeepSWE 的训练环境（R2E-Gym）**：四个工具构成动作空间——Execute Bash、Search（目录/文件内查询）、File Editor（查看/创建/替换/插入/撤销）、Finish/Submit。Reward 是稀疏 outcome reward model：生成的 patch 在时间限制内（训练时 5 分钟，官方 SWE-Bench 评测是 30 分钟）通过选定的 Pass2Pass + Fail2Pass 测试给 1，否则 0。数据集是 R2E-Gym 的 4,500 个真实 PR 任务子集，训练前过滤掉与 SWE-Bench-Verified 同源仓库（如 sympy）的任务防止污染。

**GRPO++：DeepSWE 的稳定训练配方**。在标准 [[grpo]] 基础上融合多篇前作技巧：

- Clip High（DAPO）：放宽 surrogate loss 的上界裁剪，鼓励探索、稳定 entropy。
- No KL Loss（DAPO）：去掉 KL 惩罚项，不把策略约束在 SFT 初始模型的信任域内。
- No Reward Std（Dr.GRPO）：去掉组内奖励标准差归一化，消除难度偏差，让难易样本的 advantage 幅度更可区分。
- Length Normalization（Dr.GRPO）：surrogate loss 除以**固定的**最大上下文长度（而非每条响应自己的长度），消除标准 GRPO 里"错误响应会被鼓励变长"的长度偏差。
- Leave One Out（RLOO）：advantage 估计时去掉一个样本降方差、不引入偏差。
- **Compact Filtering**（本文提出）：对到达最大上下文、生成超时（20 分钟）、或达到最大步数而终止的轨迹，在梯度计算时整条 mask 掉（不改奖励/advantage 本身，只是不参与梯度更新）。
- No Entropy Loss（本文提出）：entropy loss 会带来不稳定并最终导致 entropy 指数增长、训练崩溃；只要基座模型 token 级 entropy 落在 0.3–1 区间，不需要额外加 entropy loss。

Compact Filtering 是这套配方里最值得记的一条：多轮 agentic 场景下，agent 可能"蒙对"——前几步恰好提交了正确 patch 通过测试，但后续步骤又去改了不相关文件，若这类轨迹仍被计入正奖励训练，会强化"没有充分验证就提交"的错误行为、并随着此类行为在训练中累积最终导致 reward collapse（[[agentic-rl-training-stability]] 详述的崩溃现象在此篇里的一个独立复现）。Compact Filtering 同时观察到副作用：随着训练推进，平均响应长度下降但环境步数上升，说明模型学会了减少每步过度思考、转而依赖更多步的行动来推理（Figure 7）。

**系统侧：Kubernetes 化的可扩展 rollout 采集**。DeepSWE 训练每轮 RL 迭代要并发起 512 个 Docker 容器（batch size 64 × 8 passes）；叠加并行实验，同时存在的容器数轻松上千，压垮了 Docker API server、导致 `dockerd` 崩溃。解决办法是把 R2E-Gym 迁移到 Kubernetes 调度：每个 worker 节点约 200 CPU 核心、6TB+ 本地 NVMe SSD，预加载 SWE-bench 镜像使绝大多数层直接从磁盘读取、避免频繁拉取 Docker Hub；集群可扩展到 1000+ CPU 核心，用 Kubernetes Cluster Autoscaler 按 pod 调度情况自动增减节点（pod 排队一段时间即扩容，节点闲置约 20 分钟即缩容）。这一实现思路与 [[rollout-training-disaggregation]] 页面里 SkyRL-v0 的 Remote Sandbox Server 是同一个模式（环境执行从训练进程里解耦、独立 K8s 部署、镜像预热），差异在于 DeepSWE 这里的动机更聚焦"避免单点 Docker daemon 过载"而非"提升 GPU 利用率"。

**Test-Time Scaling（TTS）**：官方 SWE-Bench 评测才有 30 分钟测试预算和真实测试用例，训练/推理阶段的候选 patch 之间要靠额外的验证器排序。DeepSWE 组合两类验证器——execution-free verifier（DeepSWE-Verifier，在正确/错误 patch 上训练 2 epoch 的分类器，直接判断 trajectory 好坏）与 execution-based verifier（R2E-Gym 风格，另一个 LLM 生成多样测试用例，最佳 trajectory 是通过测试最多的那个），两者混合（hybrid scaling）。K=16 条候选 rollout 下达到 59.0%；作者指出大部分 TTS 收益在 K=8 时已经拿到。扩大上下文长度（16K→128K）本身对 SWE 类任务收益有限，超过 32K 后提升 ≤2%——与 DeepSWE 组的前作 DeepCoder 里"扩大上下文对代码单轮任务持续有效"的结论不同，提示长上下文 scaling 的收益在多轮 agentic 场景下更早饱和。

## 实验与结果

SWE-Bench Verified，DeepSWE-Preview 用 R2E-Gym 官方代码库评测（64K 上下文，最多 100 环境步），16 次评测取平均 Pass@1：

| 模型 | Scaffold | 形式 | SWE-Bench Verified |
|---|---|---|---|
| DeepSWE-Preview (32B) | R2E-Gym | Agent | 42.2% |
| DeepSWE-Preview (32B) | R2E-Gym | Agent + Hybrid Best@8 | 57.9% |
| DeepSWE-Preview (32B) | R2E-Gym | Agent + Hybrid Best@16 | **59.0%** |
| Devstral-Small (24B) | OpenHands | Agent | 46.6% |
| Skywork-SWE (32B) | OpenHands | Agent | 38.0% |
| Skywork-SWE (32B) | OpenHands | Agent + Execution-Free Best@8 | 47.0% |
| SWE-Agent-LM (32B) | SWE-Agent | Agent | 40.2% |
| Openhands-LM (32B) | OpenHands | Agent (Iterative) | 37.2% |
| R2EGym-Agent (32B) | R2E-Gym | Agent | 34.4% |
| SkyRL-Agent (14B) | OpenHands | Agent | 21.6% |

训练成本：4,500 个任务、64 张 H100、6 天。仅用纯 RL（无蒸馏/SFT）在同等或更少数据下超过多篇依赖更强专有教师模型蒸馏/SFT 的前作。据 [[agentic-rl-frameworks]] 页面已记录的对照，同期 SkyRL-Agent 训出的 SA-SWE-32B 达到 39.4% Pass@1，训练成本比 DeepSWE 低约 50%（4,601 vs 9,180 H100 小时）——DeepSWE 分数更高但代价也更高，两者不在同一效率前沿上，具体差异归因（数据集规模、算法配方、还是训练时长）原文均未展开对比。

## 局限与疑点

- rLLM 当前 README 描述的是 2026 年时点的框架能力（60+ 基准、10+ harness、snapshot+warm-pool 加速），与 2025-07 训练 DeepSWE 时使用的 rLLM 版本很可能有实质差异；本文没有单独的"版本变更记录"可对照，读到的是"现状"与"历史案例"的拼接，不能假设 DeepSWE 训练时已具备当前 README 描述的全部能力。
- Compact Filtering 与 No Entropy Loss 是作者自己提出的新技巧，博客用 FrozenLake 玩具环境的一张图（Figure 5、Figure 6）做消融，没有在 SWE-Bench 规模上单独消融验证这两个技巧各自的贡献——GRPO++ 是作为整体配方报告的，无法判断哪个组件贡献最大。
- 512 容器/迭代下 Docker daemon 崩溃、迁移 Kubernetes 解决的具体过程只有定性描述，没有给出崩溃前的容器数阈值、Kubernetes 化后的单节点容器密度上限、以及与 [[skyrl-v0]] 的"80–100 容器/16-CPU 节点"经验值的可比性数据。
- 长上下文 scaling 收益饱和（>32K 后 ≤2%）只在 DeepSWE-Preview 和"部分基线"上验证，具体是哪些基线、是否普遍适用于其他 32B 级 SWE agent，原文未列全。
- Section 6"其他尝试但未成功的实验"（用 Claude-Sonnet 3.7/4 做 SFT cold start、不同训练数据集/环境、non-thinking 模式）只给了标题，未展开具体结果和失败原因，是可以进一步深挖的地方。

## 对我们的启发

- **Compact Filtering 是"改梯度 mask 规则"这一类稳定性对策里的又一个具体实例**，与 [[agentic-rl-training-stability]] 页面记录的 StarPO-S（按轨迹级奖励方差过滤高不确定性样本）是不同的筛选维度：StarPO-S 按"结果不确定性"选样本，Compact Filtering 按"终止原因"（是否因为超时/超步数/超长度而非正常提交）mask 样本。如果我们要给用户提供 agent RL 训练托管服务，这提示我们的训练可观测性/回放系统至少要能标记"轨迹终止原因"（正常提交 / 超时 / 超步数 / 超上下文），这是比奖励数值本身更细粒度、但同样重要的训练健康度信号，且比方差统计更容易低成本地在系统侧统一实现。
- **GRPO++ 与 SkyRL-Agent（SA-SWE-32B）在"是否做长度归一化"这一点上给出了相反选择**：GRPO++ 主张按固定最大上下文长度归一化（Dr.GRPO 式，消除长度偏差但保留归一化），SkyRL-Agent 主张干脆去掉长度归一化。两者都是 SWE-Bench 场景、都基于 Qwen3-32B、发表时间接近，却给出相反的工程结论——这是本次精读发现的一处新矛盾，已写入 [[grpo]] 概念页的"争议与矛盾"一节，值得在我们自己后续做类似训练时留意，不能默认某一方是"更优实践"直接套用。
- **DeepSWE 的 Kubernetes 化 Docker 编排给了 SkyRL-v0 Remote Sandbox Server 模式之外的第二个真实案例**：同样是"环境执行从训练进程解耦、独立 K8s 部署、镜像预加载到本地磁盘"，但触发动机不同（这里是 Docker daemon 过载崩溃，而不是 GPU 利用率不足）。这提示我们即便平台不追求极致 GPU 利用率，仅仅是把上千并发容器直接挂在单个 Docker daemon 下这件事本身就有稳定性风险，容器编排层需要提前按"每训练迭代峰值并发容器数"设计好水平扩展能力，而不能假设 Docker 原生 API server 能扛住这个量级。
- **rLLM 把"harness/沙箱/训练后端"三者做成三个独立可替换的维度**，是一个值得参考的产品化思路：如果我们要对外提供 agent RL 训练能力，用户很可能希望自带 harness（Claude Code、Codex 等既有工具），我们只提供沙箱执行与训练后端两层——rLLM 的 Model Gateway（transparent token id/logprob capture）是这层解耦具体怎么做到"harness 代码零改动接入训练"的一个可以直接参考的实现思路，值得和 Agent Lightning 的 Training-Agent Disaggregation（[[rollout-training-disaggregation]]）做架构对比。
- follow-up 建议：
  1. 直接读 rLLM 源码里 Model Gateway 的具体实现，确认它捕获 token id/logprob 的机制与 Agent Lightning 的 API Gateway + best-effort sequence merging（[[agent-rl-credit-assignment]]）相比，是否也要处理 retokenization 问题，还是遗留给了更上层。
  2. 追踪 GRPO++ 的 Length Normalization 与 SkyRL-Agent 去长度归一化这一矛盾点后续是否有第三方消融实验给出结论，更新 [[grpo]] 页面。
  3. 若我们自己要落地"agent RL 训练环境执行层"，直接调研 rLLM/DeepSWE 的 Kubernetes Cluster Autoscaler 配置（节点规格、扩缩容阈值）作为容量规划的第二个参照点，与 SkyRL-v0 数字并列比较。

## 相关

- 相关概念：[[agentic-rl-frameworks]]、[[grpo]]、[[agentic-rl-training-stability]]、[[rollout-training-disaggregation]]、[[agent-rl-credit-assignment]]
- 相关笔记：[[skyrl-v0]]（同一时期、同一问题域的另一个团队方案，Remote Sandbox Server 与本文 Kubernetes 化 Docker 编排是同一模式的两个独立实现）；[[2511.16108]]（SkyRL-Agent/SA-SWE-32B，与 DeepSWE 直接构成 SWE-Bench Verified 分数与训练成本的对照组，且在长度归一化上给出相反工程选择）；[[2504.20073]]（RAGEN/StarPO，Echo Trap 崩溃模式与本文 reward collapse 现象在不同任务规模下的独立互证）
- 母论文：无（`parent` 为空，本篇是独立阅读清单条目）
