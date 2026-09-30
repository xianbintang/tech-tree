---
title: "GRPO"
aliases: [Group Relative Policy Optimization, 组相对策略优化, group-relative advantage]
created: 2026-09-29
updated: 2026-09-30
sources: [2609.25463, skyrl-v0, 2511.16108, 2505.10978, 2504.20073, rllm-deepswe, 2511.14617]
---

# GRPO

## 一句话定义

一种不需要学习 critic 的策略优化方法：对同一 prompt 采样 $G$ 个轨迹组成一组，advantage 相对组内其他样本的奖励均值/标准差标准化，而不是像 PPO 那样用学习出的 value 函数估计 [[2609.25463]]。

## 为什么对我们重要

GRPO 是当前 reasoning RL（DeepSeek-R1、Kimi k1.5 等）事实上的默认训练算法，它的"组"结构直接决定了 rollout 的批处理粒度——一次要为同一个 prompt 生成 $G$ 个完成，这对我们的调度系统意味着"任务"的最小可调度单元往往是"一组同 prompt 的 $G$ 条轨迹"而不是单条轨迹，很多 [[rollout-efficiency]] 的调度/投机解码方法（如利用组内 sibling 相关性做草稿）都是基于这个结构设计的。

## 核心机制 / 主要变体

- **Advantage 公式**：$\hat{A}_i^{(g)} = \big(r(x_i, y_i^{(g)}) - \mu_{r,i}\big) / (\sigma_{r,i} + \epsilon)$，$\mu_{r,i}$、$\sigma_{r,i}$ 是 prompt $i$ 组内的奖励均值和标准差 [[2609.25463]]。
- **退化组（degenerate group）**：如果组内所有完成拿到相同奖励，$\sigma_{r,i}=0$，整组 advantage 全部归零——但生成和评估这一组的成本已经付出。退化概率 $P_{deg}(p,G) = p^G + (1-p)^G$，在 $p=1/2$ 时最小，$p\to0$ 或 $p\to1$ 时趋近 1。例如 $G=8$、$p=0.9$（策略十次能解对九次）时 $P_{deg}\approx0.43$；$p=0.95$ 时升到 $\approx0.66$，意味着该 prompt 三分之二的组毫无学习信号 [[2609.25463]]。
- **重要性比值 $\rho$**：PPO 式目标里用 $\rho_{i,t}^{(g)}(\theta) = \pi_\theta(y_{i,t}^{(g)}|\dots)/\pi_{\theta_{old}}(y_{i,t}^{(g)}|\dots)$ 衡量当前策略与生成该轨迹时的策略之间的差异；$\rho=1$ 即完全 on-policy，$\rho\ne1$ 意味着数据存在策略滞后（policy lag），是 [[async-rl-training]] 需要 staleness 修正的根源 [[2609.25463]]。
- **DAPO 动态采样**：面对退化组问题的参考做法——过采样 prompt，丢弃退化组，持续采样直到批次里凑够足够的非退化组；正确但随着策略变强（$p$ 向两端移动）rollout 成本会持续增长，这正是 [[rollout-efficiency]] 里 Rollout Selection 与 Prompt Filtering 两个算法杠杆家族存在的直接动机 [[2609.25463]]。
- **训练前静态筛选——SkyRL-v0 的实践**：DAPO 是训练中动态丢弃退化组，SkyRL-v0 给出了一个更极端场景的训练前静态对策——弱模型（如 7B）面对 SWE-Gym 这类高难度任务时，$p\to0$ 到连"一次成功 rollout"都生成不出来，此时不是退化组占比高的问题，而是**整批任务奖励恒为 0、完全无学习信号**，直接导致训练崩溃。SkyRL-v0 的做法是训练前用模型自身采样（16 次生成里能否中 1 次）筛出符合当前模型能力的任务子集（分 80/220/293 三档难度），本质是把 DAPO 的"训练中过采样丢弃"提前到"训练前一次性筛选"，代价是牺牲任务多样性、换取每条训练数据都有梯度 [[skyrl-v0]]。
- **放宽 lag 容忍度的变体**：VCPO 通过按有效样本量缩放学习率，报告 lag 到 128 步仍稳定；$\mu$-GRPO 用放松的 clipping 和负 advantage veto 容忍多阶段 staleness；FlashREINFORCE、SAO 直接去掉组结构，改用单条 rollout + batch-mean 或 value-model baseline [[2609.25463]]。
- **去掉标准差/长度归一化的变体——SkyRL-Agent 训练 SA-SWE-32B 的做法**：不用标准 GRPO 公式里的组内标准差归一化，改用 leave-one-out advantage 估计，且显式去掉标准差归一化和长度归一化；超出最大上下文/步数被截断的轨迹在梯度计算时 mask 掉（但不改奖励/advantage 本身），禁用 KL 和 entropy loss，学习率 1e-6。论文未做消融单独验证这一组合对训练稳定性的贡献，只作为整体配方的一部分报告——是本页现有"退化组"讨论之外，另一类"改 advantage 估计本身"而非"筛数据"的稳定性对策 [[2511.16108]]。
- **GRPO++——DeepSWE-Preview 训练 SWE agent 的做法**：融合 DAPO 的 Clip High（放宽 surrogate loss 上界裁剪，鼓励探索、稳定 entropy）与 No KL Loss、Dr.GRPO 的 No Reward Std（去标准差归一化，消除难度偏差）与 Length Normalization（loss 除以**固定的**最大上下文长度而非每条响应自身长度，消除"错误响应被鼓励变长"的偏差）、RLOO 的 Leave One Out，再加两个自研技巧：**Compact Filtering**（对到达最大上下文/生成超时/达到最大步数而终止的轨迹整条 mask 掉梯度，防止"蒙对提交"污染训练信号导致 reward collapse）与 **No Entropy Loss**（只要基座模型 token 级 entropy 落在 0.3–1，不需要额外加 entropy loss，否则训练会因 entropy 项不稳定而崩溃）。与标准差归一化/leave-one-out 上和 SkyRL-Agent 配方一致，但在**长度归一化**这一点上两者结论相反（见下方"争议与矛盾"）[[rllm-deepswe]]。
- **critic 是否有帮助取决于任务的价值函数可估计性——RAGEN 的多轮场景对照**：把 PPO（有 critic）和 GRPO（critic-free）朴素套用到多轮 agent 任务上做 trajectory-level 优化（[[agent-rl-credit-assignment]] 里的 turn-concatenation+masking 路线），两者在 Bandit、Sokoban 上都会崩溃，但 PPO 因 critic 提供更平滑的奖励估计通常崩溃更晚、性能更高；在状态值难估计的 FrozenLake 上关系反转——GRPO 反而更稳，暗示 critic 的价值不是单调优势，而是随任务的价值函数可估计性变化。崩溃现象本身（Echo Trap：奖励方差骤降、梯度尖峰、推理退化为重复模板）与稳定化方案 StarPO-S（不确定性过滤 + 梯度整形）详见 [[agentic-rl-training-stability]] [[2504.20073]]。
- **组内响应的长度/模式强相关性——退化组之外的另一个可利用的组结构性质**：GRPO 对同一 prompt 采样 $G$ 个响应，除了"标准差是否为零"这个退化组问题外，同组响应在输出长度和 token 模式上还表现出强相关性（Seer 论文图4统计证实），且这种相关性在投机解码场景下可直接转化为收益——n-gram 投机解码接受长度随"纳入组内其他响应引用"单调上升（n=0 基线 1.70 → n=15 时 2.53）。Seer 据此设计"推测请求探路 + 组内共享上下文做投机解码草稿来源"两个系统机制，是"组结构"这一 GRPO 特有性质在调度和投机解码两个方向上的具体工程利用，详见 [[rollout-efficiency]] [[2511.14617]]。
- **多轮 agent 场景下补一层 step 级 advantage——GiGPO**：标准 GRPO 把整条多轮轨迹当一个整体算单一 episode 级 advantage，无法区分轨迹内哪些具体动作好坏，在长程稀疏奖励 agent 任务（如 ALFWorld 单轮最多 50 步）上会丢失细粒度信号。GiGPO 在不增加任何额外 rollout 的前提下，离线回溯识别同一批轨迹里重复出现的环境状态（anchor state），把"同一状态下采取的不同动作"聚合成 step 级组，组内归一化得到 step 级 advantage，与原有 episode 级 advantage 加权相加；在没有状态重复的极端情况下自然退化为标准 GRPO。ALFWorld 上比 GRPO 提升 >12%，WebShop >9%，额外系统开销 < 0.002% 训练时间（详见 [[agent-rl-credit-assignment]]）[[2505.10978]]。

## 工程要点与数字

- 组大小 $G$、成功概率 $p$ 共同决定退化概率，是设计 rollout 预算分配时的关键变量——$p$ 是"prompt-策略对"的属性，会随训练进程漂移，不是 prompt 的固有属性 [[2609.25463]]。
- 具体数值参见上方"核心机制"小节中 $G=8$ 时的例子；论文未给出更大规模 $G$（如 16、32、64）下的系统性 $P_{deg}$ 曲线，是可以自己补的简单计算。

## 争议与矛盾

- **长度归一化该保留（改用固定分母）还是干脆去掉，两个同期 SWE agent 训练配方给出相反选择**：DeepSWE 的 GRPO++ 主张保留长度归一化但把分母从"每条响应自身长度"换成"固定的最大上下文长度"（Dr.GRPO 式，消除长度偏差但不放弃归一化）；SkyRL-Agent 训练 SA-SWE-32B 则直接去掉长度归一化。两者都基于 Qwen3-32B、都训练 SWE-Bench 场景的 agent、发表时间接近（2025-07 vs 后续论文化版本），却在这一具体设计选择上相反，且都没有做消融单独验证这一项的贡献，无法判断哪种选择更优、还是任务/数据规模不同导致的经验性分歧 [[rllm-deepswe]] [[2511.16108]]。

## 开放问题

- 如何在训练中在线、低成本地估计 prompt 的成功概率 $p$ 及其漂移，而不是依赖静态先验或过采样——[[2609.25463]] 指出这方面只有 KGPS 显式建模了漂移，其余估计器未在同一工作负载上比较过。

## 相关概念

[[rollout-efficiency]]、[[async-rl-training]]、[[agent-rl-credit-assignment]]、[[agentic-rl-training-stability]]

## 相关来源

- [[2609.25463]] — 详细推导退化组概率公式，并把它作为算法杠杆两大技术家族（rollout selection、prompt filtering）存在的根本动机
- [[skyrl-v0]] — 真实 SWE-Bench 训练场景下"零学习信号导致训练崩溃"的具体案例，以及训练前按模型采样成功率静态筛选任务难度的工程对策
- [[2511.16108]] — SkyRL-Agent 训练 SA-SWE-32B 的算法配方：leave-one-out advantage + 去掉标准差/长度归一化 + 截断轨迹梯度 mask，是"改 advantage 估计"而非"筛数据"的稳定性对策
- [[2505.10978]] — GiGPO：在多轮 agent 场景下用 anchor state grouping 无额外 rollout 地补一层 step 级 advantage，退化情况下等价于标准 GRPO
- [[2504.20073]] — RAGEN/StarPO：多轮 agent 任务上 PPO vs GRPO 稳定性对照（critic 价值随任务价值函数可估计性变化），以及 Echo Trap 崩溃模式与 StarPO-S 稳定化方案
- [[rllm-deepswe]] — DeepSWE-Preview 训练 SWE agent 的 GRPO++ 配方：融合 DAPO/Dr.GRPO/RLOO 已知技巧 + 自研 Compact Filtering/No Entropy Loss；在长度归一化选择上与 SkyRL-Agent 配方相反，是本页新增的一处争议
- [[2511.14617]] — Seer：实证证实 GRPO 组内响应长度/模式强相关性，并把这一性质转化为调度（推测请求探路）和投机解码（组内共享上下文做草稿）两个系统机制，是"退化组"之外另一个被工程化利用的组结构性质
