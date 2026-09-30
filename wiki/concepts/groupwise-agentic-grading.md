---
title: "组内 Agentic 打分与 Sum-Preserving Advantage 重分配（Groupwise Agentic Grading & Advantage Redistribution）"
aliases: [Gagar, groupwise agentic grading, sum-preserving advantage redistribution, quality-aware credit redistribution, agentic grader]
created: 2026-09-30
updated: 2026-09-30
sources: [2609.32577]
---

# 组内 Agentic 打分与 Sum-Preserving Advantage 重分配

## 一句话定义

在 [[grpo]] 的组相对 advantage 框架下，用一个能读代码、跑测试的 agentic 评审模型对同组内"都通过测试"的轨迹按实现质量排名降权，再用一个保持组内正 advantage 总量不变的重缩放公式把降权扣掉的 credit 还给高质量轨迹，从而在不破坏正负 advantage 平衡的前提下引入质量学习信号 [[2609.32577]]。

## 为什么对我们重要

这是一个训练算法层面的技术，但它把"打分"变成了 RL rollout 流水线里的一个新阶段——这个阶段要读仓库、跑测试，本质上要占用和 rollout 生成同样的执行沙箱资源。对我们的沙箱/调度平台而言，它提示了一类新负载：**异步、有延迟 SLA、需要执行环境访问权限的"评审"任务**，需要在容量规划和调度架构里单独考虑，而不能简单归入 rollout 生成或 policy training 两类既有负载 [[2609.32577]]。

## 核心机制 / 主要变体

- **前提：动态采样保留混合结果组**：沿用 DAPO 式过滤，只保留组内通过率 $0<\bar R<1$ 的组，[[grpo]] 下所有通过轨迹初始 advantage 相同，都是 $1-\bar R$ [[2609.32577]]。
- **Groupwise 而非逐条打分**：grader 把整组（含失败轨迹作上下文）放进共享 workspace 联合审查，能发现单独看一条轨迹时看不出的"多余复杂度"或"低效策略"；迭代式取证——先看逐轮摘要定位可疑处，再读具体轨迹片段、交叉核对补丁与仓库/测试日志，必要时自己跑 targeted checks [[2609.32577]]。
- **五维质量标准 + 三档分层**：approach suitability、implementation precision、minimality of changes、unintended side effects、codebase consistency 五个维度加权打分；先筛出有严重问题的 $\mathcal T_3$，再从剩余候选里挑全维度高分的进 $\mathcal T_1$，其余进 $\mathcal T_2$；每个候选的档位+组内并列排名映射为折扣因子 $f_i\in(0,1]$ [[2609.32577]]。
- **Sum-Preserving 重缩放公式**：单纯乘折扣因子 $\widetilde A_i=f_iA_i$ 会让组内负 advantage 总量超过正 advantage 总量（原始 advantage 和为零），因此对所有通过轨迹统一乘重缩放系数 $\lambda=S_+/\sum_{j\in\mathcal P}f_jA_j$（$S_+$ 为原始正 advantage 总和），恢复 $\sum_{i\in\mathcal P}A_i^\star=S_+$，同时保持折扣产生的相对权重比不变、失败轨迹 advantage 不动。闭式解 $A_i^\star=(1-\bar R)\,f_i/\bar f_{\mathcal P}$ [[2609.32577]]。
- **可等价改写为 reward-space 变换**：在 mean-centered advantage 估计器下，该重缩放等价于一个显式的奖励变换 $R_i'=\bar R+(1-\bar R)f_i/\bar f_{\mathcal P}$（通过）/ $R_i'=0$（失败），不是额外引入的独立 reward-shaping 规则，而是从目标 advantage 反推出的等价形式 [[2609.32577]]。
- **工程安全阀**：重缩放系数设上限 $\lambda_{max}$（论文 Flash 配置用 1.5），超限后不再严格保和，只做重新中心化；打分结果不可用（如排名缺失通过轨迹）时回退原始二值 advantage；确认作弊（抄袭/外部答案）的轨迹奖励清零后单独重算组统计，与质量重排序分开处理 [[2609.32577]]。
- **打分与 rollout 异步重叠**：grader 用与被训练模型无关的独立 checkpoint（论文用 MiMo-V2.6-Pro 的 pre-RL SFT checkpoint），SFT 蒸馏出专用 grader 把端到端打分时间从用 Claude Opus 5 的约 2000s/组降到约 600s/组，并结合 partial-rollout 调度让打分与其他任务的 rollout 生成重叠，避免打分阻塞训练关键路径 [[2609.32577]]。

## 工程要点与数字

- 打分延迟：Claude Opus 5 做 grader 约 2000s/组；SFT 蒸馏专用 grader 约 600s/组 [[2609.32577]]。
- 在 MiMo-V2.6-Flash（310B/15B 激活）纯代码 RL 上，相比二值奖励基线：DeepSWE v1.1 通过率同 step 领先 12.1pp（62.2% vs 50.2% @step28），且基线因性能骤降在 step28 提前停止训练；SWE-bench Pro 上基线在约 59% 停滞、Gagar 持续涨到 62.5%（step52）[[2609.32577]]。
- 同时降低交互开销：DeepSWE 平均轮数 -15.6%、token 长度 -9.9%（@step28）；SWE-bench Pro 平均轮数 -6.5%、token 长度 -14.1% [[2609.32577]]。
- **只降权不重缩放（ablation）的失败模式**：policy-gradient loss 均值涨 14 倍（0.0304 vs 0.0021）；policy entropy 30 步内从 0.359 涨到 0.905（完整方法只到 0.513）；平均 rollout 长度 30 步内从 47.1k 涨到 114.1k token（完整方法只到 69.9k）；DeepSWE 通过率剧烈震荡（56.5%→48.8%→部分回升 56.2%，远低于完整方法 62.2%）[[2609.32577]]。
- 工业级混合任务 RL（1568 prompt/更新、16 rollout/prompt）验证了方法在 310B 和 1.02T 参数规模上都可用：最终 MiMo-V2.6-Pro 在 DeepSWE v1.1 上以 1.02T 总参数超过 2.8T 参数的 Kimi K3（71.9% vs 69.0%），在 SWE-bench Pro 上超过 GPT-5.6 Sol（62.7% vs 60.5%），但仍落后 Claude Opus 5 约 17.2pp（62.7% vs 79.9%）[[2609.32577]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 打分阶段本身消耗多少推理算力/沙箱执行配额（相对 rollout 生成的比例）未量化，不清楚在更大 batch 下是否会成为新瓶颈 [[2609.32577]]。
- 训练期 SFT grader 最初蒸馏自 Claude Opus 5 的打分行为，评测期又用 Claude Opus 5 做外部裁判、用同一套五维 rubric——训练信号来源和评测标准的独立性有限，存在"优化目标即评测目标"的自我印证风险 [[2609.32577]]。
- 折扣因子（$f_{runner}, f_{min}, f_{max}, f_{low}$）和 $\lambda_{max}$ 只公布了 Flash 一组配置，敏感性、跨任务分布/模型规模的可迁移性未做研究 [[2609.32577]]。
- 反作弊检测（识别抄袭/外部答案）依赖同一个 grader，假阳性/假阴性率未报告 [[2609.32577]]。

## 相关概念

[[grpo]]、[[swe-bench-pro]]、[[rollout-training-disaggregation]]

## 相关来源

- [[2609.32577]] — 提出该方法的原始论文：agentic grader + sum-preserving 重分配，在 MiMo-V2.6-Flash/Pro 上做工业级验证，并用消融实验证明"只降权不重缩放"会导致训练不稳定
