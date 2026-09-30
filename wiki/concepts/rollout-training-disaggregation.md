---
title: "Rollout/Training 分离调度（Rollout-Training Disaggregation）"
aliases: [rollout-training disaggregation, rollout/训练分离, 异步 RL 资源拆分, elastic rollout, collocated async RL]
created: 2026-09-29
updated: 2026-09-30
sources: [2026-09-29-moe-rl-eks-efa-deepep, skyrl-v0, 2511.16108, 2508.03680, 2608.17528, rllm-deepswe]
---

# Rollout/Training 分离调度

## 一句话定义

大规模异步 RL 训练里，把 rollout 生成（可分区、可容忍中断、追求聚合吞吐的推理负载）与 policy training（紧耦合、要求 lockstep 同步、对中断敏感的训练负载）拆成两类资源池分别调度：rollout 可以上 Spot/抢占式实例弹性伸缩，training 保持在稳定容量上不受 rollout 的资源波动影响 [[2026-09-29-moe-rl-eks-efa-deepep]]。

## 为什么对我们重要

这是本笔记来源里对我们最直接相关的一条：我们做的正是沙箱平台与调度系统，"两类完全不同 SLA/中断语义的 GPU workload 如何混部"是核心能力问题。这个概念给出了一个具体的设计参照：按工作负载的中断容忍度做资源池切分，而不是笼统地把所有 GPU 当同质资源调度。

## 核心机制 / 主要变体

- **两种工作负载的性质差异**：rollout 生成是大规模分布式推理，优化目标是聚合吞吐而非首 token 延迟（TTFT）或逐 token 延迟；policy training 要求 worker 紧耦合、lockstep 推进，类似预训练/SFT，任何延迟尖峰或掉队 worker 都可能让整个 job 卡住或触发 NCCL 超时 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **Spot 承载 rollout 的可行性来自任务的可分区性**：rollout worker 被 Spot 中断不需要整个 RL job 停下——未完成的 rollout 任务可以退回队列被其他 worker 重新领取，其余 worker 继续生成经验 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **设计要点**：rollout worker 应处理有界（bounded）的工作单元、频繁发布已完成样本；收到 Spot 中断通知时，worker 排空（drain）在途请求、把未完成任务退回队列 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **调度层面按队列深度独立伸缩**：基于 EKS，可以按 rollout 需求和队列深度独立伸缩 Spot-based rollout node group，同时为 policy training 维持稳定容量；policy-training worker 因此不受 Spot 中断、延迟或 NCCL 超时影响 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **三层独立伸缩的整体架构**：编排（EKS 控制面：调度、扩缩容、故障恢复）、跨节点高性能通信（NVLink 管节点内、EFA 管节点间）、数据层（经验缓冲区做高频读写的非持久层 + S3 做 checkpoint/训练产物的持久层）三者解耦，各自独立扩缩容 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- **同一模式在"环境执行"层的又一个触发动机——DeepSWE 的 Kubernetes 化 Docker 编排**：与下一条 SkyRL-v0 的动机（GPU 利用率不足）不同，DeepSWE 训练 SWE agent 时把环境执行从训练进程里独立出来是为了解决**稳定性问题**——每轮 RL 迭代要并发起 512 个 Docker 容器（batch size 64 × 8 passes），叠加并行实验后同时存在的容器数轻松上千，压垮了 Docker API server、导致 `dockerd` 崩溃。解决办法是把 R2E-Gym 环境迁移到 Kubernetes 调度：每个 worker 节点约 200 CPU 核心、6TB+ 本地 NVMe SSD，预加载 SWE-bench 镜像使绝大多数层直接从磁盘读取；集群可扩展到 1000+ CPU 核心，用 Kubernetes Cluster Autoscaler 按 pod 排队情况自动增减节点（pod 排队一段时间即扩容，节点闲置约 20 分钟即缩容）。这提示"环境执行与训练解耦"不只是吞吐/利用率优化，在容器编排层本身就有稳定性门槛——单个 Docker daemon 撑不住训练规模的并发容器数，这个门槛比"要不要提升 GPU 利用率"出现得更早、更硬 [[rllm-deepswe]]。
- **同一模式在"环境执行"层的实例——SkyRL 的 Remote Sandbox Server**：AWS 博客的拆分发生在 GPU 层（rollout worker vs. policy training worker 两个 GPU 资源池），SkyRL 把这个思路搬到更上游的**环境执行层**——SWE-Bench 这类任务每条 rollout 需要独立的 Docker 容器环境（1+ CPU、~7GB 存储），若与训练同机部署会限制隔离性和环境并行扩展的灵活性，进而拉低对 LLM 推理引擎的请求速率、浪费 GPU。SkyRL 因此把环境执行整体拆成独立的 Kubernetes 服务（Remote Sandbox Server），用存储优化实例缓存镜像加速冷启动、crun + aiodocker 处理并发，单 16-CPU 节点稳定跑 80–100 容器，训练侧和环境执行侧各自独立伸缩 [[skyrl-v0]]。
- **同一模式在 GUI/OS 沙箱场景的又一实例——SkyRL-Agent 的 Computer Use agent**：OSWorld 训练场景把每个虚拟桌面环境作为 Ray remote task 启动，用 Async Batch (Bounded) 调度器维护 32 个固定虚拟机，显式把"CPU 密集的环境反馈循环"与"GPU 密集的模型生成"解耦——与 SkyRL-v0 的 Docker 容器方案、AWS EKS 的 GPU rollout/training 池方案相比，资源单元从"容器"换成了"完整虚拟机"，隔离成本更高、可复用性诉求也更强（虚拟机生命周期比容器更长，倾向于固定池复用而非按需启停）[[2511.16108]]。
- **同一模式在更上游"agent 编排逻辑"层的实例——Agent Lightning 的 Training-Agent Disaggregation**：前几例都是在"环境/沙箱执行"层做拆分（训练 GPU vs 容器/虚拟机），Agent Lightning 把拆分再往上提一层——拆的是"LLM 生成（GPU，训练框架管）vs agent 的编排逻辑与工具调用本身（CPU，client 端，完全不需要与 GPU 同机部署）"。具体实现是 Lightning Server（跑 VeRL 等 RL 框架，按任务分发一个 OpenAI 兼容 API 端点）+ Lightning Client（通信模块 + Agent Runtime，跑用户原样的 agent 代码），训练框架因此变成 agent-agnostic（不需要感知 agent 内部编排逻辑），agent 也变成 trainer-agnostic（不需要感知底层用什么 RL 框架）。这比"沙箱执行 vs 训练"的拆分更彻底：agent 的控制流本身完全留在 client 侧，训练侧只暴露一个模型推理接口 [[2508.03680]]。
- **Agent Lightning v1.0：同一拆分思路的完整重写，补上此前缺失的执行层细节**：把 Server/Client 重构为 API Gateway（幂等的 rollout API + OpenAI 兼容 proxy API，唯一有状态组件）+ Rollout Controller（K8s Reconciler/Local Reconciler，标准 K8s controller 的 reconciliation loop：轮询 queuing rollout → 起 K8s Job → watch 状态 → 定期兜底 list）+ Customized Trainer（基于 VERL，取回 events 组装训练样本）。关键的新增点是**agent 执行调度到标准 Kubernetes Job、完全跑在自建/on-premise 算力上**——论文明确点名 verl Uni-Agent 用 Modal Sandbox/Volcano veFaas、slime 用 E2B 这类商业托管沙箱做规模化并发执行代价高昂，v1.0 选择自建 K8s 避免这笔持续费用，让训练栈保持开源可控 [[2608.17528]]。
- **Collocated Async RL：训练/rollout 共享同一 GPU 池而非拆成两池**——是本页"拆分资源池"思路的一个重要反例/补充变体。前述所有实例都是把 rollout 执行和 training 拆到不同资源池（不同 GPU 池、不同容器/虚拟机池）；Agent Lightning v1.0 额外提出一种**不拆池**的方案：rollout 和权重更新共享同一批 GPU，攒够 rollout 数据后开始更新，API Gateway 同时停止接受新请求、排空在途请求，更新期间到达的新请求被暂停、等重新进入 rollout 阶段再处理——切换对上层 agent harness 完全透明。相对同步 RL 有约 2× 端到端加速，且比 AReaL 式全异步（拆两个独立 GPU 池）用的 GPU 更少，是预算有限、硬件数量不富裕场景下的折中方案 [[2608.17528]]。

## 工程要点与数字

- 来源给出了架构设计（分节点组、Spot 承载 rollout、queue-based 重分配），但**没有给出 Spot 相对 On-Demand 的具体成本节省数字，也没有给出中断率或排空延迟的工程数据** [[2026-09-29-moe-rl-eks-efa-deepep]]。
- Benchmark 场景里训练与推理的资源配比是 16 台训练 : 32 台推理（共 48×P5en 实例），但这只是单一 case，来源未讨论该配比如何随模型稀疏度/EP 并行度调整 [[2026-09-29-moe-rl-eks-efa-deepep]]。
- DeepSWE 侧的具体数字：单轮 RL 迭代峰值 512 个并发 Docker 容器（batch size 64 × 8 passes）即可压垮原生 Docker API server；Kubernetes 化后单 worker 节点约 200 CPU 核心 / 6TB+ 本地 NVMe SSD，集群规模可扩展到 1000+ CPU 核心；节点闲置约 20 分钟触发缩容。未给出 Kubernetes 化后单节点的容器密度上限，无法与 SkyRL-v0"80–100 容器/16-CPU 节点"直接对照换算 [[rllm-deepswe]]。
- SkyRL 侧的具体数字：单环境 1+ CPU / ~7GB 存储；batch size 16、每 prompt 8 条 rollout 这种适中配置需要 100+ CPU、接近 1TB 磁盘；单 16-CPU 节点可稳定跑约 80–100 容器（经验值，非压测上限）[[skyrl-v0]]。
- SkyRL-Agent 的 Computer Use agent 案例未给出虚拟机规模的资源数字（CPU/内存/存储），只报告了固定 32 个虚拟机的池大小；论文报告该场景下训练奖励持续提升但验证准确率不涨，提示"环境执行与训练解耦"解决的是吞吐/利用率问题，不能替代任务本身对模型能力的要求 [[2511.16108]]。
- Agent Lightning 同样**没有给出任何系统吞吐/资源数字**（无 Server-Client 通信开销、无扩展性上限测试）；实验规模也明显小于 SkyRL 系列（3B base model、Text-to-SQL/RAG/数学工具调用三个相对轻量任务，未验证 SWE-Bench 级别长程场景），是四个来源里工程细节最薄弱的一个 [[2508.03680]]。
- **v1.0 补上了旧版缺失的规模化数字**：Qwen3.5-9B + mini-SWE-agent 在 SWE-smith 数据（约 6K 训练样本）上训练，SWE-bench Verified 从 41.8% 提升到 56.4%（+14.6pp）；但 Collocated Async RL 的"约 2× 加速、比全异步用更少 GPU"只有一句话带过，没有给出与全异步在相同总 GPU 数下的正面对比数字，也没有报告暂停接受新请求引入的额外延迟；K8s 原生方案相对商业沙箱的实际成本节省也没有量化数字，只有定性论证 [[2608.17528]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- rollout worker 的"有界工作单元"具体应该切多细、Spot 中断到任务重新被领取之间的延迟对整体 rollout 吞吐的影响，来源未量化。
- 该模式在非 AWS 环境（自建集群、其他云的抢占式实例）下的等价实现与踩坑点，知识库里暂无数据，需要另外调研。
- rollout:training 的资源配比应该如何随 MoE 稀疏度、专家并行度动态调整，目前没有定量指导。
- SkyRL 的 Remote Sandbox Server 未披露冷启动延迟、镜像分发具体机制、超卖上限的压测数据，80–100 容器/16-CPU 节点是否还能再提升未知 [[skyrl-v0]]。
- Docker 容器（SkyRL-v0 SWE 场景、DeepSWE Kubernetes 场景）、完整虚拟机（SkyRL-Agent computer-use 场景）、GPU 资源池（AWS EKS 场景）几种资源单元的密度/成本/冷启动画像目前只能分别对照单一来源的数字，没有同一团队在同一硬件上做过横向对比；DeepSWE 更是完全没有披露单节点容器密度数字，只有"扩容前会崩溃、扩容后不再崩溃"的定性结论 [[2511.16108]] [[rllm-deepswe]]。
- Agent Lightning 的"agent 编排逻辑层解耦"与前三例的"环境/沙箱执行层解耦"能否组合使用（例如用 Agent Lightning 的 Server/Client + OpenAI-like API 做训练侧标准化，同时用 SkyRL 风格的 Remote Sandbox Server 做具体环境执行）目前没有已知实践或文献讨论，是我们自己平台设计时需要验证的组合方式 [[2508.03680]]。
- Collocated Async RL（同池共享）与前述所有"拆两池"方案之间的选型依据——什么规模/预算/延迟容忍度下该选哪种——目前没有任何来源做过正面对比，是我们自己设计调度策略时需要通过实验回答的问题 [[2608.17528]]。
- Agent Lightning v1.0 的 K8s 原生执行相对商业沙箱服务（Modal Sandbox、Volcano veFaas、E2B）具体能省多少成本、运维自建 K8s 集群的隐性成本有多大，知识库里暂无数字，需要另外调研或自己压测。

## 相关概念

[[expert-parallelism]]、[[deepep]]、[[sandbox-density-overcommit]]

## 相关来源

- [[2026-09-29-moe-rl-eks-efa-deepep]] — AWS 博客，提出 EKS 上按中断容忍度拆分 rollout（Spot）与 training（稳定容量）资源池的架构模式
- [[skyrl-v0]] — SkyRL-v0 博客，同一"执行与训练解耦"模式在环境执行（CPU/Docker 沙箱）层的具体实现：独立 K8s 部署的 Remote Sandbox Server，给出容器密度与资源占用数字
- [[2511.16108]] — SkyRL-Agent 论文，同一模式在 GUI/OS 沙箱场景的实例：Computer Use agent 训练把虚拟机作为 Ray remote task 启动，解耦环境反馈与模型生成
- [[2508.03680]] — Agent Lightning 论文，同一模式在更上游"agent 编排逻辑"层的实例：Training-Agent Disaggregation 用 Lightning Server/Client + OpenAI-like API 把 LLM 生成与 agent 控制流完全分离，训练框架 agent-agnostic、agent trainer-agnostic
- [[2608.17528]] — Agent Lightning v1.0，完整重写版：把 Server/Client 落地为 API Gateway + Rollout Controller（K8s Reconciler）+ Customized Trainer，agent 执行改用自建 Kubernetes Job 替代商业沙箱服务；另提出 Collocated Async RL——rollout 与训练共享同一 GPU 池而非拆两池，是本页"拆分资源池"思路的一个重要反例/补充变体
- [[rllm-deepswe]] — DeepSWE-Preview 训练案例：同一"环境执行独立 K8s 部署"模式的又一实例，但触发动机是原生 Docker API server 在 512+ 并发容器下崩溃这一稳定性问题，而非 GPU 利用率优化；给出节点规格与 Cluster Autoscaler 策略，但未披露密度上限
