---
title: "RLHF"
aliases: [Reinforcement Learning from Human Feedback, 基于人类反馈的强化学习, InstructGPT 三步法]
created: 2026-10-03
updated: 2026-10-03
sources: [2203.02155, 2501.12948, 2407.21783]
---

# RLHF

## 一句话定义

用人类对模型输出的偏好训练一个奖励模型（RM），再用 RM 作为奖励信号、以 PPO 对语言模型做强化学习微调的三步法：SFT（监督微调）→ RM 训练 → PPO 优化 [[2203.02155]]。

## 为什么对我们重要

RLHF 是后训练（post-training）流水线的源头范式——后续的 RLVR、GRPO 等方法都是在"要不要学 critic / value 函数""奖励从哪来（人类偏好 vs 可验证规则）"这两个维度上对 RLHF 做变体。理解 RLHF 原始形态的工作负载特征（单轮 bandit、RM 独立推理、PPO rollout-训练耦合），能帮我们判断后续方法（如 [[grpo]]）在哪些地方真的改变了系统需求，哪些地方只是算法层面的调整。

## 核心机制 / 主要变体

- **三步法**：(1) 标注员写示范 → 监督微调 SFT 模型；(2) 标注员对同一 prompt 的 K=4~9 个模型输出排序 → 训练 RM 预测人类偏好；(3) 用 RM 分数作为奖励、PPO 优化 SFT 模型，每 token 加一个相对 SFT 模型的 KL 惩罚防止 reward hacking [[2203.02155]]。
- **RM 损失**：$\text{loss}(\theta) = -\frac{1}{\binom{K}{2}} \mathbb{E}_{(x,y_w,y_l)\sim D}\left[\log\sigma(r_\theta(x,y_w) - r_\theta(x,y_l))\right]$，把同一 prompt 的 $\binom{K}{2}$ 个比较对打包成一个 batch element（而非拆成独立样本）避免同一补全被多次用于梯度更新导致过拟合 [[2203.02155]]。
- **PPO 目标（含 KL 惩罚 + 可选预训练梯度）**：$\mathbb{E}_{(x,y)\sim D_{\pi_\phi^{RL}}}\left[r_\theta(x,y) - \beta\log(\pi_\phi^{RL}(y|x)/\pi^{SFT}(y|x))\right] + \gamma\,\mathbb{E}_{x\sim D_{pretrain}}[\log \pi_\phi^{RL}(x)]$；$\gamma=0$ 时为纯 "PPO"，$\gamma>0$ 混入预训练分布似然梯度为 "PPO-ptx"，用于缓解对齐税 [[2203.02155]]。
- **Alignment tax（对齐税）**：RLHF 微调会导致模型在部分公开 NLP 基准（SQuAD、DROP、HellaSwag、WMT 翻译）上性能回退；混入预训练梯度（PPO-ptx）比单纯增大 KL 系数更能缓解，且不损失标注员偏好分数 [[2203.02155]]。
- **rollout 环境形态**：InstructGPT 的 RL 环境是一个 bandit——给定 prompt，生成一次回复，RM 打一次分，episode 结束，没有多轮交互、没有工具调用、没有状态持久化 [[2203.02155]]。这是 agentic RL 之前"最简单"的 rollout 形态。
- **用 DPO 替代 PPO 做策略优化（Llama 3 的生产实践）**：RM 训练与拒绝采样环节与标准 RLHF 一致，但策略优化阶段用 Direct Preference Optimization（DPO）取代 PPO——作者明确说明"探索过 PPO 等 on-policy 算法，但 DPO 对大规模模型需要更少算力、且在 IFEval 等指令遵循基准上表现更好"。DPO 省去了独立的 RL rollout 推理服务，策略优化变成纯离线训练，是 RLHF 三步法在系统架构上的简化变体 [[2407.21783]]。为稳定 DPO 训练，Llama 3 还做了两处修改：屏蔽 chosen/rejected 回复中共享的格式化特殊 token（避免对同一 token 同时增大和减小似然的冲突目标）；加入 0.2 系数的 NLL 正则项防止 chosen 回复似然被压低 [[2407.21783]]。
- **六轮迭代的生产流水线**：每轮 = 收集新偏好标注 → 训 RM → 拒绝采样生成 SFT 数据 → SFT → DPO → 多版本模型权重平均，循环六轮，每轮用上一轮最强模型重新采样标注。偏好数据额外引入"编辑后回复"，形成 edited > chosen > rejected 的三元排序而非只有二元比较对 [[2407.21783]]。

## 工程要点与数字

- **算力成本远低于预训练**：175B 模型 SFT 训练 4.9 petaflops/s-days，PPO-ptx 训练 60 petaflops/s-days，而同规模 GPT-3 预训练需要 3,640 petaflops/s-days——RLHF 全流程算力仅为预训练的约 1.6%，但效果超过把模型做大 100 倍（1.3B InstructGPT 输出被偏好于 175B GPT-3）[[2203.02155]]。
- **数据规模**：SFT 约 1.3 万 prompt，RM 约 3.3 万 prompt，PPO 约 3.1 万 prompt（仅来自产品 API，无人工标签）[[2203.02155]]。
- **RM 规模选择**：论文只用 6B RM，175B RM 训练不稳定、不适合用作 RL 中的 value function 初始化 [[2203.02155]]。
- **标注员一致率**：训练标注员之间一致率 72.6±1.5%，held-out 标注员 77.3±1.3%；RM 预测 held-out 标注员偏好的准确率 69.6±0.9%，仅比训练集内（72.4±0.4%）略低，说明偏好有一定跨标注员泛化性 [[2203.02155]]。
- **拒绝采样吞吐优化**：Llama 3 用 PagedAttention 做拒绝采样加速，但发现原生实现有 swap-out 风险，因此预先限定最大输出长度、仅在显存够用时才接受请求，并让同一 prompt 的多个输出共享 KV cache 页，整体吞吐提升 **2 倍以上** [[2407.21783]]。
- **后训练总成本未披露**：与 InstructGPT 给出"RLHF 仅占预训练算力 1.6%"的具体 petaflops/s-days 数字不同，Llama 3 全文未披露六轮 SFT+RM+DPO 迭代的总算力/时间成本，是该报告在后训练成本维度上的披露空白 [[2407.21783]]。

## 争议与矛盾

- RLHF 的标准流程是"先 SFT 再 RL"，SFT 提供强初始化、防止 RL 阶段的 mode collapse [[2203.02155]]；但 DeepSeek-R1-Zero 证明对可规则验证的推理任务（数学、代码），**完全跳过 SFT、直接在 base model 上做纯 RL** 反而能涌现出更强、更不受人类先验束缚的推理策略——作者认为人类示范数据可能限制模型探索非人类式的推理路径。两者并不矛盾：RLHF 的"先 SFT"是为了对齐人类偏好这种缺乏可靠奖励信号的任务，RLVR（见 [[rlvr]]）在有规则奖励兜底时可以放弃这个安全网 [[2501.12948]]。

## 开放问题

- RLHF 对齐的是"一小群特定标注员+研究者"的偏好，而非普适人类价值观；如何设计更具代表性、能处理标注员分歧的偏好聚合机制，论文本身列为未解决问题 [[2203.02155]]。
- "对齐"（服从指令）与"安全"（拒绝有害指令）是两件事——RLHF 原始设计里模型会服从几乎所有指令（包括被明确要求输出有毒内容时比基线更毒），拒绝机制是后续工作的方向 [[2203.02155]]。
- RM 训练在大规模（175B）下的不稳定性原因未在本文解决，只是规避（降级用 6B RM）。

## 相关概念

[[grpo]]、[[rlvr]]（RLHF 奖励模型式偏好学习 vs RLVR 规则验证式奖励，是后训练奖励来源的两条主线，DeepSeek-R1 在通用数据上实际把两者结合使用）

## 相关来源

- [[2203.02155]] — RLHF 三步法的奠基工程论文（InstructGPT），给出完整的 SFT/RM/PPO 实现细节、算力成本对比和对齐税缓解方法
- [[2501.12948]] — 用"跳过 SFT 直接 RL"的 DeepSeek-R1-Zero 对照组，反衬出 RLHF 标准流程里 SFT 阶段的作用边界；且在 R1 第二阶段 RL 里把奖励模型（helpfulness/safety）与规则奖励混合使用，是 RLHF 与 RLVR 奖励来源结合的具体实例
- [[2407.21783]] — Llama 3 技术报告，提供"SFT→DPO 替代 SFT→RM→PPO"的生产级工程实践与六轮迭代流水线细节，是 RLHF 系统架构简化的具体实例
