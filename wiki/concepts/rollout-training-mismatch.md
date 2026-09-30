---
title: "Rollout–训练不一致（Rollout–Training Mismatch）"
aliases: [rollout-training mismatch, rollout–training consistency, sampler-trainer mismatch, 采样-训练数值不一致, MoE 路由不一致, Rollout Routing Replay, R3]
created: 2026-09-29
updated: 2026-09-30
sources: [2609.25463, 2601.02780]
---

# Rollout–训练不一致（Rollout–Training Mismatch）

## 一句话定义

即使在完全同步、零策略滞后的 RL 训练流水线里，rollout 引擎（如 vLLM/SGLang）和训练引擎（如 FSDP/Megatron-LM）用不同的 kernel、batching 方式、数值精度实现同一个模型，对同一个采样 token 算出的概率并不完全相等——这个差异不会随 lag=0 消失，是纯数值层面的问题，且会在长轨迹上累积 [[2609.25463]]。

## 为什么对我们重要

如果我们平台要对外提供"rollout 生成"能力（而不只是通用推理 serving），这是一个容易被忽略但会静默腐蚀训练信号的正确性问题——"用同样的模型权重"不等于"算出同样的 log-prob"，需要把一致性检验作为产品/API 设计的显式约束，尤其是在我们同时运营推理 serving 引擎和训练引擎、试图把两者的算力打通复用时（参见 [[async-rl-training]] 里"借用 serving 空闲 GPU 做 rollout"的方向）。

## 核心机制 / 主要变体

- **本质**：把 rollout 引擎当作行为策略（behavior policy），训练引擎的 log-prob 计算当作目标策略；即使权重相同，误差来源是数值精度/kernel/batching 差异而非时间差异，所以不能靠缩短同步间隔消除，只能靠数值对齐或显式修正 [[2609.25463]]。
- **修正方式一：镜像 staleness 修正**——用 rollout 引擎记录的概率做 token 级 importance weighting，与 [[async-rl-training]] 里处理策略滞后的方式相同结构，但这里差距来自数值而非时间 [[2609.25463]]。
- **修正方式二：对齐两个引擎的数值实现**，避免让差异发生。
- **主动放大差距换吞吐的场景（footprint 降低）**：量化/稀疏化 rollout 本身会故意加大这个 gap 来换吞吐，因此这类方法都自带显式修正机制：
  - FP8-RL：token 级 importance weighting；
  - QaRL：训练端重新量化的前向 forward pass；
  - Sparse-RL：拒绝采样 + 重加权；
  - AIS：按批次的有效样本量（effective sample size）诊断动态调整 importance-weight 混合比例 [[2609.25463]]。
- **异步场景下的叠加风险**：在异步训练（[[async-rl-training]]）里，policy lag 造成的 importance weighting 与数值 mismatch 造成的 importance weighting 会叠加在同一个 ratio 上——footprint 降低那一翼的方法（FP8-RL、QaRL、AIS 等）如果再叠加异步执行，等于把两层修正堆到一起，论文指出目前没有方法测量过这种叠加组合 [[2609.25463]]。
- **投机解码的关联风险**：数值 mismatch 会同时降低草稿接受率，因为 drafting 和 verifying 概率本就存在细微差异，mismatch 进一步拉大这个差距 [[2609.25463]]。
- **MoE 专属子问题：路由不一致（Rollout Routing Replay / R3）**：对 MoE 模型，rollout 引擎和训练引擎不仅计算的 log-prob 有数值误差，连同一个 token 被路由到**哪些专家**都可能因精度差异而不同——这比稠密模型的 mismatch 更严重，因为路由错位会让训练梯度更新到"rollout 时根本没激活"的专家上。MiMo-V2-Flash 提出的修正方式是**在训练时强制复用 rollout 阶段实际选中的专家**（而不是让训练引擎重新计算路由），通过优化数据类型和通信重叠把额外开销做到可忽略；多轮 agent 训练场景下再配一个请求级前缀缓存，同时保存 KVCache 和 MoE 路由结果供后续轮次复用——与常见的跨请求共享的 radix cache 不同，这个缓存不做跨请求共享，专门保证同一请求内路由的一致性 [[2601.02780]]。这属于本页"修正方式二：对齐两个引擎的数值实现"的一个具体化，但只处理路由这一个专属于 MoE 的错位来源，不能替代 token 级 log-prob 的数值对齐。

## 工程要点与数字

- 三个层次的"实际是同一个正确性问题"需要区分清楚（论文 Section 6.3 的核心论点）：① 对原目标的**精确保真**（仅在投机解码严格按接受/拒绝采样时成立）；② 对**修改后目标**的无偏估计（如 importance-corrected staleness、ESPO 把截断定义为显式终止状态、已知重加权规则下的 filtering）；③ **仅有实证观察**质量被保留（大部分 filtering/selection/mismatch 结果属于这一类，只说明在评测场景下有效，不是估计量正确性的保证）[[2609.25463]]。
- 效率声明只有在明确说清楚属于三层里的哪一层时才有意义，这也是判断两个方法能否安全组合的前提 [[2609.25463]]。
- 异步下的放大效应：ratio clipping 或拒绝极端 ratio 样本是目前实践上限制该风险的常用手段 [[2609.25463]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 没有方法测量过"policy lag 修正 + 数值 mismatch 修正"叠加后的稳定性，AIS 的按批效应样本量诊断是目前唯一给出的缓解手段但未在叠加场景下验证 [[2609.25463]]。
- 论文没有给出"多大的数值 mismatch 才会实质影响训练结果"的量化阈值，只指出它会随轨迹长度累积。
- R3 的额外开销被描述为"可忽略"，但 [[2601.02780]] 未给出具体的延迟/显存数字，也没有说明该机制对非 MoE（稠密）模型是否有等价需求或完全不适用。

## 相关概念

[[async-rl-training]]、[[rollout-efficiency]]

## 相关来源

- [[2609.25463]] — 把 rollout–训练不一致作为独立于策略滞后的正确性问题系统讨论，并归纳三层估计量正确性区分（精确保真/修改目标无偏/仅实证观察）
- [[2601.02780]] — 提出 Rollout Routing Replay（R3），针对 MoE 模型路由不一致这一专属子问题，训练时强制复用 rollout 阶段的实际路由
