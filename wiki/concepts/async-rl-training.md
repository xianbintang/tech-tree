---
title: "异步 RL 训练（Pipeline Decoupling / Policy Staleness）"
aliases: [asynchronous RL training, pipeline decoupling, policy lag, policy staleness, rollout-train 解耦, collocated async RL]
created: 2026-09-29
updated: 2026-09-30
sources: [2609.25463, skyrl-v0, 2511.16108, 2608.17528, 2504.20073, 2511.14617]
---

# 异步 RL 训练（Pipeline Decoupling / Policy Staleness）

## 一句话定义

让 rollout 生成 worker 和训练 worker 并发运行，不再等待整批 rollout 完成才开始训练、也不等训练更新完成才恢复生成，代价是训练用到的轨迹可能来自旧一点的策略版本（policy lag），需要 staleness bound 或 off-policy 修正 [[2609.25463]]。

## 为什么对我们重要

这是 [[rollout-efficiency]] 系统杠杆里收益潜力最大、也最直接对应我们做调度系统关心的问题：同步 RL 训练里 rollout worker 和训练 worker 任一时刻总有一方空闲，异步化本质是一个"用多少调度自由度换多少陈旧数据"的权衡——这跟我们平台设计抢占/弹性调度策略时面对的权衡结构是一致的。

## 核心机制 / 主要变体

设计空间的核心变量是**允许跨越 rollout–训练 barrier 的最小工作单元**，越细的粒度换取更高利用率、但引入更多策略滞后：

- **整批粒度**：LlamaRL，全异步跑到 405B 参数规模，用 Asynchronous Importance-weighted Policy Optimization (AIPO) 修正 1-step lag，单步吞吐提升 10.7×（405B）[[2609.25463]]。
- **样本粒度**：AReaL——权重更新时停止 rollout、在新权重下恢复，一条轨迹可能跨越多个策略版本；吞吐 2.77×（1.5B–32B）。DORA 把这一思路扩展到同时跨越多个版本 [[2609.25463]]。
- **轨迹粒度**：Laminar，通过 relay worker 把权重传给正在生成的轨迹，不等全局 barrier，lag 上限 $s\le4$ [[2609.25463]]。
- **服务接口粒度**：ProRL Agent 把环境搭建/工具调用/reward 打分整个放到 HTTP 接口后面，训练器只提交任务、收取完成的轨迹；FlexMARL、RollArt、AstraFlow 把同一思路用到 agent/多策略流水线（一连串 barrier 而不是单个）[[2609.25463]]。**SkyRL-v0** 是这一粒度的另一个具体实现：环境执行被拆成独立的 Remote Sandbox Server（K8s 部署），训练侧通过 init/run/eval 三个队列的生产者-消费者流水线异步提交/收取任务，环境初始化、多轮轨迹生成、reward 计算三阶段解耦重叠，配合异步 `async_generate` rollout，合计带来 4–5× 加速；这一实现同时解决了"环境资源与训练资源co-locate 导致 GPU 利用率不足"的问题（见 [[rollout-training-disaggregation]]）[[skyrl-v0]]。**SkyRL-Agent** 把 SkyRL-v0 的单一流水线升级成统一接口下的三种可配置调度策略：Async Batch（全部轨迹并发启动，适合初始化/评估都轻量的任务，如 search-integrated reasoning）、Async Batch (Bounded)（限并发池大小，适合需要限流保护运行时或持久化资源可复用的场景，如 computer-use 里的长生命周期虚拟机）、Async Pipeline（三个可独立配置大小的有界队列重叠 CPU 密集阶段与 GPU 密集推理，适合运行时或 reward 阶段开销大的任务）；SWE 训练场景下 Async Pipeline 相对 Async Batch (Bounded) 再提速约 1.55×，生成阶段 GPU 利用率稳定在约 90%（对照组因 CPU 密集阶段阻塞 GPU 而大幅波动），2×8 H100、batch size 64、8 rollouts/task 下测得 [[2511.16108]]。
- **不引入 staleness 的重叠**：RolloutPipe 证明"重叠不一定要牺牲 on-policy"——在组粒度上重叠 disaggregated rollout 与训练，同时严格保持 on-policy [[2609.25463]]。
- **不拆资源池的异步——Collocated Async RL（Agent Lightning v1.0）**：以上所有变体的共同前提是 rollout worker 和训练 worker 是两个独立的资源池（不同粒度只是决定跨越 barrier 的最小工作单元）。Agent Lightning v1.0 提出另一个维度的取舍：rollout 与权重更新**共享同一个 GPU 池**，攒够 rollout 数据后触发更新，API Gateway 同时停止接受新请求、排空在途请求；更新期间到达的新请求被暂停，直到系统重新进入 rollout 阶段——切换对上层 agent harness 完全透明。相对同步 RL 报告约 2× 端到端加速，且比 AReaL 式全异步（拆两个独立 GPU 池）用的 GPU 更少，代价是仍然存在"停止接受新请求"这段等待窗口，不是真正意义上的重叠——是"样本粒度"异步（如 AReaL）在硬件预算受限场景下的一个更省资源的替代方案，而不是更细粒度的改进 [[2608.17528]]。
- **放宽"训练本身能容忍多少 lag"**（而非"多细粒度跨越 barrier"的新方向）：VCPO 通过按有效样本量缩放学习率，报告 lag 到 128 步仍稳定；$\mu$-GRPO 用放松 clipping + 负 advantage veto 容忍多阶段 staleness；FlashREINFORCE、SAO 去掉组 baseline，用单条 rollout + batch-mean/value-model baseline，从根本上去掉组 barrier [[2609.25463]]。
- **staleness 的标准修正**：按 [[grpo]] 里的重要性比值 $\rho$ 做 importance weighting，让每个采样动作按其在当前策略下相对行为策略的似然比贡献；这不会让任意陈旧数据等价于新鲜 on-policy 数据，只是限制了两者差异，差异越大 ratio 方差越大，更新越噪 [[2609.25463]]。
- **独立的训练质量证据——RAGEN 的 Online-$k$ 消融**：以上所有变体都从系统吞吐角度论证陈旧度的代价；RAGEN 从纯训练质量角度给出了独立验证——固定一组 rollout 复用 $k$ 次策略更新（$k$ 越小越新鲜，Online-1 即完全在线），在 Sokoban 等多轮 agent 任务上 Online-1 收敛明显更快、跨任务泛化更好，$k$ 越大（如 Online-5、Online-10）收敛越慢。这与本页系统侧的 lag-吞吐权衡是同一现象的另一面：本页关注"用陈旧数据换吞吐能省多少"，RAGEN 关注"陈旧数据本身对最终模型质量的损耗有多大"，两者目前是两条独立证据链，没有同一团队在同一任务上把两条曲线画在一起（见「开放问题」）[[2504.20073]]。

## 工程要点与数字

- **两级收益的量级差异**：SkyRL-v0 的 4–5× 是相对"同步单批 rollout"这个明显低效基线的加速；SkyRL-Agent 的 1.55× 是相对已经异步化的 Async Batch (Bounded) 基线、在同一 SWE 训练场景下测得——"从同步到异步"这第一档收益远大于"异步内部继续精细化调度粒度"的第二档收益，做调度优化投入排序时应优先保证拿到第一档 [[2511.16108]]。
- 收益上限被"重叠能消除的空闲时间"卡住——大集群、长且方差大的轨迹、agentic 长链条 barrier 场景下收益最大；一旦阶段已经重叠，进一步异步化只增加 lag 和协调成本、边际收益很小 [[2609.25463]]。
- 与调度/负载均衡的交互：StaleFlow 指出紧的 lag 上限会限制哪些轨迹可以被迁移，压缩调度器纠正长度不均衡的自由度，需要全局跟踪轨迹状态才能同时满足两个约束 [[2609.25463]]。
- 与资源感知执行的重叠：Pipeline decoupling 和"在线重规划 rollout/训练 GPU 配比"（Libra、BiDiRL、DynaResize）争夺同一份空闲容量——一旦阶段已重叠，剩余的空闲容量所剩无几，没有研究测过两者叠加的效果；但"收割集群外部空闲/spare 容量"（RLBoost、ROSE）、"异构硬件按阶段特性放置"（AReaL-Hex）不受此影响，在全异步下依然有效 [[2609.25463]]。
- 与投机解码的冲突：pipeline decoupling 引入的策略滞后会削弱投机解码所需的"drafting 策略和 verifying 策略保持接近"的前提，两者叠加可能互相拖累（BubbleSpec 反过来用严格同步保住投机所需的策略接近性，是一种设计取舍）[[2609.25463]]。**Seer** 是这一取舍的另一个完整系统实例：明确论证保持严格同步（避免异步引入的 off-policy）后，靠分割推理（细粒度块级调度 + 全局共享 KVCache 池）+ 上下文感知调度 + 组内共享上下文做草稿来源的投机解码三件套，同样拿到 2.04× 吞吐提升、72–94% 长尾延迟削减；论文还直接对比了放弃同步、超发 2× 请求的 Partial Rollout 方案，指出后者在内存受限场景下高并发反而加剧抢占（平均吞吐低 43%），且会降低长输出请求比例、可能给训练带来分布偏差——是"同步优化 vs 异步/超发换吞吐"这一权衡目前少数给出正面对照数字的案例，补充了本页"两者被论文标记为共享同一份空闲容量，理论上有冲突但没有实证"这一开放问题之外的一个具体反例（详见 [[rollout-efficiency]]）[[2511.14617]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 文献里没有系统扫过"lag–质量"曲线：各系统固定一个 lag 上限（$k=1$、$s\le4$ 等）报一个操作点，VCPO 报告到 lag 128 是唯一的例外，没有两个方法在同一 lag 下被比较过 [[2609.25463]]。
- Pipeline decoupling 与在线资源重规划叠加的增量效果未被测量（两者被论文标记为共享同一份空闲容量，理论上有冲突，但没有实证）[[2609.25463]]。
- Collocated Async RL 相对全异步（拆两池）的 2× 加速只有一句话带过：没有给出相同总 GPU 数下的正面对比数字，也没有报告"暂停接受新请求"这段等待窗口对端到端延迟的具体影响，是我们自己评估该方案时需要压测的问题 [[2608.17528]]。
- RAGEN 的 Online-$k$ 消融只报告了收敛速度/泛化性的相对趋势（$k=1$ 最优），没有给出具体的吞吐-质量权衡数字，也没有和本页任何一个系统侧方案（AReaL、Laminar 等）在同一任务/同一硬件上直接对比，两条证据链尚未被统一 [[2504.20073]]。

## 相关概念

[[rollout-efficiency]]、[[grpo]]、[[rollout-training-mismatch]]、[[rollout-training-disaggregation]]、[[agentic-rl-training-stability]]

## 相关来源

- [[2609.25463]] — 系统性归纳 Pipeline Decoupling 的设计空间（粒度谱）与 lag 容忍度的新趋势，并给出与其他技术家族的可组合性分析
- [[skyrl-v0]] — 服务接口粒度解耦在 agentic/SWE 场景的具体工程实现：Remote Sandbox Server + 三阶段生产者-消费者流水线
- [[2511.16108]] — SkyRL-v0 的论文化后继：把单一流水线升级为统一接口下三种可配置调度策略（Async Batch / Bounded / Pipeline），给出 1.55× 加速与 90% GPU 利用率的量化对照实验
- [[2608.17528]] — Agent Lightning v1.0，提出 Collocated Async RL：rollout 与训练共享同一 GPU 池而非拆两池，约 2× 加速且比全异步用更少 GPU，是"不拆资源池"这一维度的新变体
- [[2504.20073]] — RAGEN/StarPO：从训练质量（而非系统吞吐）角度独立验证 rollout 新鲜度的价值，Online-1（完全在线）收敛更快、泛化更好，是本页 staleness 讨论之外的一条独立证据链
- [[2511.14617]] — Seer，严格保持同步（不异步化）仍拿到 2.04× 吞吐提升的完整系统案例，并给出与非严格同步方案（Partial Rollout）的正面对照数字，是"同步优化 vs 异步换吞吐"权衡的具体反例
