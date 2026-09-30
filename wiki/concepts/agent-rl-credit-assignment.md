---
title: "多轮/多 Agent RL 的轨迹→训练样本转换"
aliases: [credit assignment for agent RL, turn concatenation masking, transition-based RL, LightningRL, trajectory decomposition, harnessed agentic RL, retokenization, token-prefix continuity]
created: 2026-09-30
updated: 2026-09-30
sources: [2508.03680, 2608.17528, 2505.10978, 2504.20073]
---

# 多轮/多 Agent RL 的轨迹→训练样本转换

## 一句话定义

现有单轮 RL 算法（GRPO、PPO、REINFORCE++）只处理"一个 prompt → 一次生成"的样本结构；把它们应用到多轮、多 agent、动态编排的 agent 执行轨迹上，核心工程问题是**如何把一条完整执行轨迹拆解/组织成这些算法能吃的训练样本**，业界目前主要有两条路线：把整条轨迹拼接成一条长序列再用 mask 控制哪些 token 参与优化（turn-concatenation + masking），或者把轨迹拆成独立的 `(input, output, reward)` transition、每个 transition 当作一条独立单轮样本（transition-based，代表是 Agent Lightning 的 LightningRL）[[2508.03680]]。这个问题在「harnessed agentic RL」范式（用部署时同一套 agent harness 直接做训练，训练引擎只能观测到离散的 LLM 调用对，harness 内部状态转移不可见）下进一步升级为一个**动态运行时问题**：同一条 rollout 会因为 retokenization、子 agent 分支、上下文摘要而产生数量不确定的训练样本，advantage 计算和 loss 归一化都必须显式决定"要不要让这个偶然的样本数影响梯度权重" [[2608.17528]]。

## 为什么对我们重要

如果我们要给用户提供"接入任意框架写的 agent、直接做 RL 训练"的托管服务，"轨迹怎么切成训练样本"是训练数据管道设计里绕不开的一步——选错会导致上下文随轮数爆炸、mask 逻辑与训练框架强耦合、多 agent 系统无法做选择性优化。这个设计决策直接决定了我们的训练接口对用户 agent 实现方式的侵入性有多低。

## 核心机制 / 主要变体

- **Turn-concatenation + masking**（RAGEN、Trinity-RFT、rLLM、Search-R1，均基于 VeRL）：把一条轨迹里的所有轮次拼接成一条长序列，用 mask 标记哪些 token 是待优化 LLM 生成的、哪些是工具输出/环境反馈等不参与梯度更新的部分。只适合简单、顺序化的单 agent 工作流；mask 会打断 RoPE 等位置编码假设依赖的 token 连续性；每个应用的 mask 策略往往要手写、难以泛化；上下文随轮数增长不断变长，加重训练侧显存/序列长度压力 [[2508.03680]]。**RAGEN/StarPO 是这条路线的一手确认**：StarPO 把观测、推理痕迹、动作、反馈组成的整条轨迹当作一个整体做 rollout 和优化，策略概率分解到 token 级似然，直接在拼接后的长序列上套用 PPO/GRPO 的 token 级更新公式；RAGEN 论文本身聚焦训练稳定性（Echo Trap / StarPO-S，见 [[agentic-rl-training-stability]]），未讨论 mask 的具体实现细节或与其他三个框架的差异，Trinity-RFT/rLLM/Search-R1 仍待直接精读确认 [[2504.20073]]。
- **Transition-based（LightningRL，Agent Lightning）**：把 agent 执行建模为 MDP——state 是一组"语义变量"的快照，一次组件调用（LLM 或工具）定义为 `call=(meta, input, output)`。从完整执行里只抽取"待优化 LLM 每次调用"的三元组 `(input_t, output_t, r_t)` 作为一条 transition，忽略产生该 input 的具体拼接/渲染逻辑。LightningRL 分两步：(1) credit assignment 模块把整条轨迹的 episode-level return $R=\sum_t r_t$ 分配给各个 action——当前实现是最简单的**恒等分配**（每个 action 都拿到与 $R$ 相同的值）；(2) 分配后每条 transition 变成标准单轮训练样本，同一 task 的多次执行按 task 分组，套用 GRPO 的组内归一化（见 [[grpo]]），可以不做任何修改直接喂给 GRPO/PPO/REINFORCE++ [[2508.03680]]。
- **Transition-based 的三个直接好处**：(a) transition 天然对齐 LLM 输入结构，不需要手写 mask，不破坏位置编码连续性；(b) 长轨迹拆成一批批独立 transition 而不是一条不断变长的拼接序列，可以用 batch accumulation 缓解上下文爆炸；(c) 可以选择性优化多 agent 系统里的部分 agent——只需把想训练的 agent 对应的 transition 纳入优化集合（Agent Lightning 的 Text-to-SQL 实验，3 个 agent 里只训 2 个，用的就是这个机制）[[2508.03680]]。
- **Credit assignment 仍是简化实现，非终局方案**：LightningRL 当前的"恒等分配"策略把同一轨迹里每个 action 都当作对最终 return 贡献相同，本质上丢失了"哪个 action 对结果更关键"的信息。论文明确把"学习一个逐 action 的价值函数做更精细的 credit assignment"列为未来工作，尚未验证 [[2508.03680]]；v1.0 也没有推进这一点，它解决的是另一个层面的问题（见下）[[2608.17528]]。
- **一个不学价值函数也能做到细粒度的具体方案——GiGPO 的 anchor state grouping**：GiGPO 回答的是与上一条"未来工作"同方向但更窄的问题——不训练价值函数，也不额外 rollout，只靠离线回溯同一批轨迹里重复出现的环境状态（anchor state）：把"同一状态下采取的不同动作"聚合成 step 级组，组内按折扣回报归一化得到 step 级相对 advantage，与标准 episode 级 GRPO advantage 加权相加；没有状态重复时自然退化为标准 GRPO。这和本页的"轨迹→训练样本转换"问题是两个不同层次：turn-concatenation+masking 与 transition-based（LightningRL）解决的是"怎么把一条轨迹切成训练样本"，GiGPO 假设样本结构已经是标准的逐轮 action（未做切分改造），只回答"切好的每个样本该分多少信用"。两者原则上正交、可以叠加（GiGPO 的分组逻辑可以套在 LightningRL 拆出的 transition 之上），但论文都未验证这一组合 [[2505.10978]]。GiGPO 在 ALFWorld/WebShop 上比标准 GRPO 提升 >12%/>9%，额外开销 < 0.002% 训练时间；局限是依赖状态精确/近似匹配才能识别重复，在 ALFWorld/WebShop 这类离散、可回退环境里状态重复率高（训练全程 group size=1 的比例 < 35%），但在代码/沙箱这类几乎不会产生完全相同状态的场景里收益存疑，论文未验证 [[2505.10978]]。

**Harnessed agentic RL 的四个动态样本数挑战（Agent Lightning v1.0）**：

- **Retokenization 打破 token-prefix 连续性**：harness 视角下相邻调用通常满足文本级前缀关系，但 token 级前缀关系不被保证。三种具体机制：(1) chat-template 非组合性——完整渲染消息历史 $\ne$ 分别渲染再拼接，模板可能在边界插入/省略分隔符（例：Qwen 模板会移除更早的 `<think>` 标记）；(2) decode-retokenize 漂移——decode 非单射，`Tok(Decode(a_i^{tok})) \ne a_i^{tok}`（例：`having` 采样时是 `h`+`aving` 两个 token，重新分词后可能变成 `hav`+`ing`）；(3) 推理时输出变换——工具调用/结构化输出的解析、规范化、重序列化改变了文本本身。三种缓解策略：①每次调用独立训练（token 级正确但重复计算共享前缀，效率差）；②prefix-shared/tree-structured training（共享前缀只算一次+分支感知 attention mask，但需要大量训练后端支持）；③best-effort sequence merging（只在满足严格 token 前缀关系时合并，否则断开另起一条）——v1.0 采用③，作为效率与正确性的折中 [[2608.17528]]。
- **AReaL/verl Uni-Agent 的"buffered token replacement" vs v1.0 的 best-effort merging**：前者把新 prompt 里对应旧 response 的 token 段替换成缓存的原始 token 以提高合并率，但如果替换后的 stitched prompt 与模型实际看到的 prompt 不同，会引入 off-policy 偏差——response 明明是在真实 $p_{i+1}^{tok}$ 下采样的，却被当成在替换后的 prompt 下训练；slime、Polar 不做这个替换。v1.0 认为"exact token-prefix overlap 只应该在它确实保留了 rollout 实际消费的 prompt 时才用来合并"，因此选择更保守的 best-effort 策略 [[2608.17528]]。
- **Advantage calculation：rollout-level vs sample-level**：同一条 rollout 因为上述原因可能产生动态数量的训练样本 $N_\rho$；计算 [[grpo]] 式组内 baseline 时应该在 rollout 级别统计还是样本级别统计？verl Uni-Agent、Polar 选 rollout 级别，slime、AReaL 选样本级别。具体数值例子：同一 prompt 的 Rollout 1（奖励 1，产生 3 个样本）和 Rollout 2（奖励 0，产生 1 个样本），rollout-level baseline $=(1+0)/2=1/2$，sample-level baseline $=(1+1+1+0)/4=3/4$——两者给出完全不同的数字。v1.0 论证 rollout-level 更合理：retokenization、子 agent 分支、上下文摘要都是偶然/harness 内部因素，不该改变整组的 baseline [[2608.17528]]。
- **Loss normalization：三种公式给出不同梯度权重**：token-mean（DAPO，全 batch 所有 token 求和再除以总 token 数）、seq-mean-token-mean（GRPO，先样本内平均再对样本均匀平均——对一条 rollout 产生的样本数敏感，样本越多权重越大）、rollout-level token-mean（slime，先 rollout 内汇总平均再对 rollout 均匀平均）。v1.0 理论上认为前者和后者更 principled，但实践中 token-mean 对长负样本敏感、训练后期不稳定，最终选择 **rollout-level token-mean**——这个选择带有经验调参成分，未在其他模型规模上做消融验证 [[2608.17528]]。
- **Training backend scheduling**：rollout batch 的样本数/长度只有在 harness 执行完、样本组装完才知道，训练 GPU 数与并行配置通常固定；backend 必须在扁平化成物理张量 batch 时保留每条序列的 rollout ID/prompt-group ID，且同一条 rollout 产生的所有序列必须留在同一次 optimizer update 内——否则一条 rollout 的不同部分会在不同策略版本下被评估，引入 rollout 内部的策略偏移 [[2608.17528]]。

## 工程要点与数字

- 论文只做了方法论层面的定性区分，**没有给出 transition-based 相对 concatenation+masking 在显存占用、训练速度、最终效果上的直接数值对比**——"更优"目前停留在设计论证，不是实证结论 [[2508.03680]]。
- 三个验证任务（LangChain Text-to-SQL、OpenAI Agents SDK RAG、AutoGen 数学工具调用）都用 3B 级别的 base model 和相对轻量的任务，尚未在 SWE-Bench 级别的长程（20+ 轮）编码 agent 场景验证这套转换机制的扩展性，对照 [[skyrl-v0]] 在该场景下的实测规模明显更小。
- **v1.0 用真实 coding-agent 训练场景验证了"动态样本数不是边缘情况"**：Qwen3.5-9B + mini-SWE-agent 在 SWE-smith 任务上，平均只有 36% 的 rollout 保持为单一训练样本，每条 rollout 平均产生 2.41 个训练样本 [[2608.17528]]。
- **消融数字（固定同一 GRPO 目标，验证奖励 @ step 128）**：Sample-level Advantage 35.0% < Rollout-level Advantage（只改 advantage、仍用 token-mean loss）33.1%（反而更低）< Rollout-level Advantage + Rollout-level Norm（advantage 和 loss normalization 一起改）38.2%（最优，且策略熵增长更慢更稳定）——提示单独修正 advantage 计算而不配套修正 loss normalization 可能带来负面效果，两者需要一起改 [[2608.17528]]。
- 最终 checkpoint 在 SWE-bench Verified 从 41.8% 提升到 56.4%（+14.6pp，约 6K 训练样本），是本页所有结论里唯一有真实基准数字支撑的规模化验证 [[2608.17528]]。

## 争议与矛盾

- **Advantage/loss 归一化该在 rollout 级别还是样本级别计算，业界框架选择不一致**：verl Uni-Agent、Polar、Agent Lightning v1.0 选 rollout 级别；slime、AReaL 选样本级别。Agent Lightning v1.0 给出了具体数值反例说明两者结果可以差一倍（1/2 vs 3/4 的 baseline），并论证 rollout-level 更合理，但这只是一方的立场，slime/AReaL 为何选样本级别的论证知识库里暂无，需要直接查阅这两个框架的文档/论文补充 [[2608.17528]]。

## 开放问题

- Transition-based 方案在真正长程、高分支（LLM 动态决定下一步调用谁）的多 agent 场景下的实际收益尚未有量化数据，需要等后续论文或我们自己的实验补充。
- 更精细的 credit assignment（逐 action 价值函数）会如何影响 LightningRL 与标准 GRPO/PPO 的兼容性假设，目前是完全开放的问题；v1.0 也没有在这个方向推进 [[2608.17528]]。
- Transition-based 与 concatenation+masking 两条路线能否根据任务特性（轮数、分支程度、多 agent vs 单 agent）给出选型依据，知识库里暂无数据，需要另外调研或等更多论文补充对比实验。
- RAGEN 只确认了 StarPO 采用 turn-concatenation+masking 的整体思路，未披露 mask 的具体实现（如何标记环境反馈 token、是否处理 RoPE 位置连续性问题）；Trinity-RFT、rLLM、Search-R1 三个框架仍完全依赖 Agent Lightning 的转引，尚待直接精读原始论文/代码确认实现细节 [[2504.20073]]。
- Best-effort sequence merging 在 retokenization 漂移严重的场景下会显著降低合并率（更多独立训练样本、更多重复前缀计算），v1.0 没有报告这带来的计算开销增幅，是一个可以自己压测的具体问题 [[2608.17528]]。
- slime/AReaL 选择 sample-level advantage/loss 的具体论证未见于本知识库，需要直接查阅这两个框架的文档补充，才能判断这是设计取舍还是工程简化。
- GiGPO 的 anchor state grouping 与 LightningRL/Agent Lightning v1.0 的 transition 拆分能否实际叠加（先按 harness 调用拆 transition，再对 transition 里的状态做 anchor grouping），两篇论文都没有验证，是一个直接可做的实验型 follow-up。

## 相关概念

[[agentic-rl-frameworks]]、[[grpo]]、[[rollout-training-disaggregation]]、[[async-rl-training]]、[[agentic-rl-training-stability]]

## 相关来源

- [[2508.03680]] — Agent Lightning 论文，提出 MDP 形式化 + LightningRL 分层算法，是本页 transition-based 路线的唯一来源；turn-concatenation+masking 路线（RAGEN/Trinity-RFT/rLLM/Search-R1）的描述最初转引自该论文 Related Work 对已有工作的归纳，其中 RAGEN 已由 [[2504.20073]] 直接精读确认
- [[2608.17528]] — Agent Lightning v1.0，完整重写版，提出「harnessed agentic RL」范式并系统刻画 retokenization/advantage calculation/loss normalization/training backend scheduling 四个动态样本数挑战，给出具体设计选择与 SWE-bench Verified 规模化验证（41.8%→56.4%）
- [[2505.10978]] — GiGPO：不切分训练样本、只改进 step 级信用分配的具体方案，用 anchor state grouping 无额外 rollout/价值函数地给出比 LightningRL"恒等分配"更细粒度的信号，与本页 transition-based/turn-concatenation 两条路线处于不同问题层次
- [[2504.20073]] — RAGEN/StarPO 论文，turn-concatenation+masking 路线里 RAGEN 一侧的一手来源：确认 StarPO 把整条轨迹拼接成长序列、套用 PPO/GRPO token 级更新公式，但未涉及 mask 具体实现细节；论文主体聚焦训练稳定性问题（见 [[agentic-rl-training-stability]]）
