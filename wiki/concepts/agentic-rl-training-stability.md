---
title: "多轮 Agent RL 的训练不稳定性（Echo Trap）"
aliases: [Echo Trap, StarPO, StarPO-S, agent RL training collapse, reward variability collapse, multi-turn RL instability]
created: 2026-09-30
updated: 2026-09-30
sources: [2504.20073, rllm-deepswe]
---

# 多轮 Agent RL 的训练不稳定性（Echo Trap）

## 一句话定义

把单轮 RL 方法（PPO、[[grpo]]）直接套到多轮 agent 任务上做 trajectory-level 优化时，训练会规律性地出现一种可命名、可预警的崩溃模式——**Echo Trap**：模型把局部被奖励的推理捷径过度放大，输出从早期多样推理收敛为重复、确定性的固定话术，伴随奖励方差骤降、输出熵异常、梯度范数尖峰，最终性能不可逆下滑 [[2504.20073]]。

## 为什么对我们重要

如果我们的平台要给用户提供 agent RL 训练的托管能力，"训练会不会中途崩掉、能不能在崩掉之前自动预警/干预"是比"跑得快不快"更基础的可用性问题——这类稳定性失效目前没有被当作系统可观测性的一部分对待，而是训练算法团队事后从 loss 曲线里肉眼诊断，属于我们调度/监控系统可以标准化承接的能力缺口。

## 核心机制 / 主要变体

- **StarPO（State-Thinking-Actions-Reward Policy Optimization）**：把单轮目标 $J_{\text{step}}(\theta)=\mathbb{E}_{s\sim\mathcal{D},a\sim\pi_\theta}[R(s,a)]$ 推广为轨迹级目标 $J_{\text{StarPO}}(\theta)=\mathbb{E}_{\mathcal{M},\tau\sim\pi_\theta}[R(\tau)]$，把观测、推理痕迹、动作、环境反馈组成的整条轨迹 $\tau$ 当作一个整体做 rollout 和优化；策略概率分解到 token 级似然，与 PPO/GRPO 的 token 级更新公式直接兼容——本质是把整条多轮交互拼接成一条长序列，是 [[agent-rl-credit-assignment]] 里 turn-concatenation + masking 路线的一手实现来源（此前该路线只能从 Agent Lightning 的 Related Work 转引）[[2504.20073]]。
- **Echo Trap 的诊断信号**：平均奖励（Average Reward）和梯度范数（Gradient Norm）直接反映崩溃发生；奖励标准差（Reward Std）和输出熵（Entropy）是**早期预警信号**——在三个测试任务里都比奖励均值更早出现异常（如 FrozenLake-PPO 的 reward std 在 step 40 骤降，reward mean 到 step 90 才真正崩），梯度范数骤增标志不可逆崩溃的临界点（Bandit step 170、Sokoban step 110、FrozenLake step 90）[[2504.20073]]。
- **StarPO-S：不确定性过滤 + 梯度整形**：假设方差高（结果不确定）的训练样本信息量最大（借鉴 Active Learning）。定义轨迹级不确定性 $U(\pi_\theta,\mathcal{M},s_0)=\text{Std}_{\tau\sim\pi_\theta(\cdot|s_0)}[R(\tau)]$，每步训练只保留标准差 top-$p\%$ 的 prompt（默认 $p=25\%$，作者强调非普适最优值）；PPO 上效果显著（保留 75% 把 FrozenLake 崩溃点从 step 100 推迟到 140，保留 50% 完全避免崩溃），GRPO（无 critic）改善更温和。叠加借鉴 DAPO 的 KL Term Removal 与 Clip-Higher（非对称裁剪）两个梯度整形技巧，进一步提升成功率、延长稳定阶段 [[2504.20073]]。
- **PPO 的 critic 能延迟但不能阻止崩溃**：朴素 PPO/GRPO 在 Bandit、Sokoban 上早期都有提升，随后几乎必然崩溃；PPO 因 critic 提供更平滑的奖励估计，通常崩溃更晚、性能更高，但在状态值难估计的 FrozenLake 上 GRPO 反而更稳——critic 的价值随任务的价值函数可估计性变化，不是单调优势 [[2504.20073]]。
- **推理会在多轮场景下随训练衰退**：显式推理（`<think>` 痕迹）在单轮 Bandit 上明显提升泛化，即使在语义反转（BanditRev）的更难设置下依然稳定优于无推理版本；但在多轮 Sokoban/FrozenLake 上，去掉推理段效果往往持平甚至更好，且推理痕迹长度随训练持续缩短（Bandit 从 66.0 token 降到 17.6 token @ step 200）。作者认为稀疏、延迟的多轮奖励结构无法区分"连贯推理"和"歪打正着"，模型据此学会压抑思考过程，甚至生成幻觉式推理却仍拿到高奖励 [[2504.20073]]。
- **Rollout 质量的三个可调维度**：(1) 任务多样性——固定批大小下，更多不同 prompt（如 4 responses/prompt）比更多响应集中在少数 prompt 上（32 responses/prompt）泛化更好，前提是每个 prompt 仍需多条 rollout 做对比；(2) 每轮动作预算——5–6 个动作/轮是甜蜜点，太小限制规划、太大（7 个）引入噪声转移、稀释奖励；(3) rollout 新鲜度（Online-$k$，一组 rollout 复用 $k$ 次更新）——$k=1$（完全在线）收敛最快、泛化最好，这与 [[async-rl-training]] 纯系统侧的 staleness/吞吐权衡是同一现象的训练质量侧证据 [[2504.20073]]。
- **同类崩溃现象在完全不同规模/任务上的独立复现——DeepSWE 的"蒙对提交"问题**：RAGEN 的 Echo Trap 在 0.5B–3B 模型、Bandit/Sokoban/FrozenLake 等短程符号任务上观测到；DeepSWE-Preview（32B、真实 SWE-Bench 长程编码任务、64 张 H100 规模训练）独立报告了一种同族现象——agent 有时前几步"蒙对"提交了能通过测试的 patch，但后续步骤又去修改不相关文件，若这类轨迹仍按正奖励训练，会强化"未充分验证就提交"的行为，此类行为在训练中累积最终导致 reward collapse。两者观测规模、任务类型、模型量级完全不同，却指向同一个根本问题——稀疏结果奖励无法区分"真正做对"与"歪打正着"，是本知识库里首次出现的跨规模互证 [[2504.20073]] [[rllm-deepswe]]。
- **两种不同层次的稳定性对策——按不确定性筛 vs 按终止原因筛**：StarPO-S 按轨迹级奖励方差（结果不确定性）保留 top-p% 样本，是一种"猜哪些样本信息量大"的主动学习式过滤；DeepSWE 的 Compact Filtering 按轨迹终止原因（是否因超时/超步数/超上下文而非正常提交终止）mask 梯度，是一种更廉价、不依赖统计量、只需读轨迹元数据就能实现的过滤。两者可能正交、原则上可以叠加，但都未在同一任务上互相对比或组合验证 [[rllm-deepswe]]。

## 工程要点与数字

- 主实验规模较小：Qwen-2.5-Instruct 0.5B（Bandit/Sokoban/FrozenLake）、3B（WebShop），H100 上 100–200 轮迭代，每批 $P=8$ 个 prompt、$N=16$ 条轨迹/prompt，最多 5 轮、每轮最多 10 个动作；72B 及 GPT-4o/Qwen-2.5-72B 对照放在附录，正文未展开量化讨论 [[2504.20073]]。
- 论文**未报告 GPU 小时、墙钟时间或每次迭代的具体成本**，只给出迭代数与批配置，没有工程规模化的资源数字，和 [[agentic-rl-frameworks]] 页面里"多数框架只给定性特性、缺量化吞吐数字"的已知缺口是同一类问题 [[2504.20073]]。
- Echo Trap 的诊断指标在论文的四个环境（三个相对简单的符号/半符号任务 + 一个短程 WebShop）上普遍成立，**未在 SWE-Bench 级别长程（20+ 轮）、动作空间巨大的编码 agent 场景验证**这套早期预警信号是否依然有效，是本页结论外推到我们最关心场景时最大的不确定性 [[2504.20073]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- StarPO-S 的关键超参数（保留 top-25% 高方差 prompt）是经验选择，论文没有给出选择 $p$ 的系统性方法或跨任务敏感性分析，是否能通用到编码/终端类 agent 任务未知 [[2504.20073]]。
- 推理衰退的解释（稀疏延迟奖励无法区分连贯推理与歪打正着）停留在观察+假设层面，论文没有做对照实验（如设计能区分两者的奖励函数重新训练）直接验证因果关系 [[2504.20073]]。
- Echo Trap 的早期预警信号（奖励标准差、熵）能否直接作为我们训练可观测性系统的标准指标、触发自动降级或人工介入的具体阈值该怎么定，知识库里暂无跨规模/跨任务的验证数据，是一个可以自己在真实训练 job 上验证的具体 follow-up。
- Online-$k$ 的"新鲜度影响训练质量"结论与 [[async-rl-training]] 的系统侧 staleness/吞吐权衡目前是两条独立证据链，没有同一团队在同一任务上把"lag 对吞吐的收益"和"lag 对最终质量的损失"画在同一张图上，是我们自己设定 staleness 上限时值得先做的实验。

## 相关概念

[[agent-rl-credit-assignment]]、[[grpo]]、[[async-rl-training]]、[[rollout-efficiency]]、[[agentic-rl-frameworks]]、[[rollout-training-disaggregation]]

## 相关来源

- [[2504.20073]] — RAGEN/StarPO 原始论文，提出 StarPO 轨迹级优化框架，识别 Echo Trap 失败模式与早期预警指标，提出 StarPO-S 稳定化方案，并给出 rollout 多样性/粒度/新鲜度、推理衰退的实证发现
- [[rllm-deepswe]] — DeepSWE-Preview 训练案例：在 32B、真实 SWE-Bench 长程场景下独立复现同族 reward collapse 现象（"蒙对提交"），并给出 Compact Filtering 这一按终止原因筛选轨迹的稳定性对策，与 StarPO-S 的按不确定性筛选形成对照
