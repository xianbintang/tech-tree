---
title: "RL 后训练执行计划在线自适应（Elastic Parallelism Adaptation / EMU）"
aliases: [Nereus, Elastic Model Unit, EMU, online TP/PP adaptation, payback-based admission, elastic execution plan, 在线并行度重规划, 弹性执行计划]
created: 2026-09-30
updated: 2026-09-30
sources: [2609.34645]
---

# RL 后训练执行计划在线自适应（Elastic Parallelism Adaptation / EMU）

## 一句话定义

在一次 RL 后训练运行过程中，当资源供给、工作负载（如生成序列长度）或硬件效率发生漂移（drift）时，在线重新选择跨 actor/critic/reward/reference 等多模型、多阶段（generation/inference/training）的执行计划（DP/TP/PP 与 GPU 分配），并通过与依赖结构对齐的状态单元（Elastic Model Unit, EMU）复用 GPU 常驻状态完成迁移，而不是启动时定死计划或靠 checkpoint/restart 整体重建 [[2609.34645]]。

## 为什么对我们重要

这是「训练系统 GPU 调度、抢占、弹性与容错」这条研究主线里目前知识库中最系统化的一篇：它把"执行计划该不该变、变了怎么不丢状态、多个模型抢同一批 GPU 时怎么排序"这三个我们自己做沙箱/调度平台迟早要面对的问题，给出了一套已验证的工程方案和量化的收益/代价数字，而不是停留在架构直觉层面 [[2609.34645]]。

## 核心机制 / 主要变体

- **漂移的三个来源**：资源供给（Spot 回收、集群重分配）、工作负载需求（生成序列变长导致 KV cache/激活内存暴涨）、硬件效率（网络拥塞、多租户干扰、离线预测器失准）。三者都会让"启动时选定、之后不变"的执行计划变慢甚至不可行 [[2609.34645]]。
- **状态边界决定迁移代价**：把 TP/PP（紧耦合，需跨 rank 强同步）封装进单个状态单元内部，DP 副本（松耦合，只需周期性同步）作为该单元的"个数"暴露给外部——这是 EMU（Elastic Model Unit）抽象的核心设计原则，四个原语 Split/Merge（parallelism resharding）+ Extend/Destroy（resource scaling）覆盖整个计划空间的迁移 [[2609.34645]]。
- **何时迁移——payback-based 准入**：$\Delta L>0 \land \widehat{L}_{\mathrm{tran}}/\Delta L \le \gamma H_x$，即预测的单步延迟节省要能在"距离下次漂移还剩多少步"（$H_x$，EMA 估计）的一定比例内收回迁移代价（$\gamma$ 默认 0.5）。把 Pollux/Sia 那套跨 job 集群调度的 payback 原则，搬到单个耦合多模型 job 内部 [[2609.34645]]。
- **如何执行——带跨阶段依赖的全局迁移 DAG**：每个 model-stage 的变化按 Split→Destroy→Extend→Merge 固定序编译成局部 DAG；当多个 model-stage 争抢同一批临近满载的 GPU 时，用 release-before-acquire + 阶段序（generation→inference→training）破环，必要时插入资源依赖边，保证 DAG 无环、不会死锁 [[2609.34645]]。
- **安全边界**：只在 RL-step 完成（同步执行）或权重同步点（异步执行）触发迁移，保证参数/优化器状态、更新计数器、策略版本、RNG/dataloader 状态在迁移前后维持训练语义一致 [[2609.34645]]。

## 工程要点与数字

- **迁移代价对比（同一 16→32 GPU 迁移，8B actor/critic）**：checkpoint/restart（UCP）836.74s，shard 级（Tenplex）66.43s，EMU（Nereus）6.52s——粒度选择带来两个数量级的差距 [[2609.34645]]。
- **大规模下迁移开销可以忽略**：1000 步、扩展到 1024 GPU 的完整 run 里，6 次 TP/PP 迁移只占总运行时间的 0.079%（49.5s / 62353s）[[2609.34645]]。
- **端到端收益**：真实数据构造的 drift trace 上，在线 TP/PP 自适应比固定初始布局降低平均 step latency 27.7%；8B PPO 端到端吞吐相对 OpenRLHF 提升 2.14–7.27×（中位数 3.99×），相对 Verl 提升 1.10–1.47× [[2609.34645]]。
- **计划选择质量有实测上界**：480 个穷举可行计划中，在线代价模型选中的计划 61.1% 精确命中经验最优，全部设置都在 5% 以内（p95 gap 4.1%），代价模型对训练阶段延迟预测 MAPE 4.96% [[2609.34645]]。
- **跨模型并发协调是易错点**：DynaRL 式"每个 model-stage 独立局部 DAG、不做跨阶段协调"在 GPU 资源重叠场景下只有 34–62% 成功率，失败全部是共享 GPU 死锁；加全局资源依赖边后 Nereus 在所有重叠测试中 100% 成功 [[2609.34645]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源；论文自身把 DynaRL 定位为"固定资源池内的组件级动态调度"，与 Nereus"跨资源池变化的计划级重规划"做了明确的能力边界区分，而非结论冲突）

## 开放问题

- 没有开源代码，43k 行实现的可复现性未经第三方验证 [[2609.34645]]。
- 论文假设 TP/PP 只搜索 2 的幂次配置，非 2 的幂配置下的机会损失未讨论 [[2609.34645]]。
- 异构模型混部（不同架构/精度共享代价模型的算子效率校准）是否仍然成立，论文未展开 [[2609.34645]]。
- 评测所用的"真实数据 drift trace"是基于观测构造的离线 trace，而非在生产环境在线接入，资源撤销与抢占叠加发生的复杂交互未见验证 [[2609.34645]]。
- 我们自己平台的弹性调度/checkpoint 系统当前处于 job 级还是 shard 级粒度，是否值得引入"model-stage 副本"级抽象，需要结合自己的系统做调研（见 [[2609.34645]] 笔记的 follow-up）。

## 相关概念

[[rollout-training-disaggregation]]、[[async-rl-training]]、[[agentic-rollout-preemption]]、[[expert-parallelism]]、[[grpo]]

## 相关来源

- [[2609.34645]] — 提出 Nereus：payback-based 准入策略 + EMU 状态抽象 + 安全并发迁移 DAG，是本页所有结论的唯一来源
