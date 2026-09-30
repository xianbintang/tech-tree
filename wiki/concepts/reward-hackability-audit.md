---
title: "Code RL 环境可作弊率审计"
aliases: [reward hackability audit, environment quality score, EQS, gold-sanity gate, docker-verified reward hacking rate]
created: 2026-09-30
updated: 2026-09-30
sources: [2606.16062, 2608.22103]
---

# Code RL 环境可作弊率审计

## 一句话定义

用"生成候选错误补丁 + Docker 实测能否骗过测试套件"的方式,直接测量 code RL 训练/评测环境里有多大比例的任务会为错误解发奖励,并给出一套带 gold-sanity gate 的自动修复闭环 [[2606.16062]]。

## 为什么对我们重要

这是 [[verifiable-reward-environment-generation]] 讨论的"环境先行"范式里"reward hacking 留空间"这一抽象风险的**实证量化**:不是理论上可能被骗,而是给出了具体比例（28.5%/25.0%）和一套可复用的低成本质检组件。如果我们要把 SWE-bench 系任务或类似结构的自建环境用于内部 RL 训练,这套审计+修复流程可以直接作为环境准入前的质检步骤 [[2606.16062]]。

## 核心机制 / 主要变体

- **Docker 实测 hackability**：用前沿 LLM（论文用 Claude Sonnet 4）生成 K 个"通过现有测试但改变了可观察行为"的错误补丁候选,在任务真实 Docker 容器里跑项目自身测试 harness,只要有一个候选通过即判定该任务 hackable。第 1 轮 single-shot,第 2/3 轮用上轮失败日志引导生成（迭代攻击）[[2606.16062]]。
- **Environment Quality Score（EQS）**：EQS(t) = 0.35·V(t) + 0.30·(1−H(t)) + 0.20·F1(t) + 0.15·D(t),四个维度按"信号直接程度"降序加权：verifier 判别力 V > 实测 hackability H > LLM 判官一致性 F1 > 跨模型可学习性 D。按阈值分 KEEP(>0.70) / FIX(0.40–0.70) / DROP(<0.40),权重未在验证集调过,核心实证数字均独立于权重选择 [[2606.16062]]。
- **Docker gold-sanity gate**：修复 FIX 判定任务时,新生成的测试先在 gold 解上跑一遍——通不过就丢弃并触发重试,通过了才交给 LLM 判官判定是否真的拦住了目标漏洞。这个 gate 拦截的是"LLM 判官读懂了测试代码逻辑,但没发现测试代码本身跑不起来/断言方向反了"这类判官系统性漏检的缺陷 [[2606.16062]]。
- **134-模型元分析验证**：用固定于基准发布时的人工难度分层做协变量控制（而非跨模型 solve rate,避免 hackable 任务抬高 solve rate 造成的循环论证),对每个模型算 flagged-hackable 子集与 robust 子集的分层内 Pass@1 差值,再做随机效应元分析跨模型汇总,间接验证"测出的 hackable 任务确实被模型更多地'赢'了" [[2606.16062]]。

## 工程要点与数字

- **SWE-bench Verified 49 任务审计**：28.5%（14/49）Docker 验证 hackable,集中在 12 个仓库中的 2 个（astropy、django）;仅 single-shot 时 18.4%。花费 $6.04 API + 本地 Docker [[2606.16062]]。
- **R2E-Gym 20 任务复现（6 仓库,K=1）**：25.0%（4/16 决定性任务),作者标注为下界（攻击预算比 SWE-bench 审计弱）。花费 $8.29 API + ~2.5 小时 Docker [[2606.16062]]。
- **134-模型元分析**：分层内 Δ̂ = +14.14pp（95% CI [+11.80, +16.48], p<10⁻⁶, I²=0%,123/134 模型方向为正);未分层原始效应 +25.64pp,分层后保留 55% [[2606.16062]]。
- **61.9% 的 augmenter 缺陷率**（n=105 决定性 sanity check,论文认为是最稳定的核心数字）：无 gate 时 LLM 判官报告 10/11 任务修复成功,Docker 复核 8 个抽样判定后只有 1 个证实、6 个是 augmenter 自身 bug、1 个方法论边界情形;加 gate 后 111 次生成里 65 次被 gate 拦下,最终收敛 9/11,且总花费更低（$3.60 vs 无 gate 的 $5.57）[[2606.16062]]。
- **消融**：gate+判官但不重试,收敛只剩 3/11;加回重试恢复到 9/11——**重试是否存在**是决定性因素,diversity-biased 提示相对中性提示没有增量收益;判官采样数 3→1 掉 1 个任务但省 56% API 成本 [[2606.16062]]。

## 争议与矛盾

（暂无跨来源分歧;目前只有一篇来源。与 [[benchmark-item-validity-audit]] 的关系是互补而非冲突,见下方"相关概念"说明）

## 开放问题

- 单一攻击者（Claude Sonnet 4）测出的 28.5%/25.0% 更准确的表述是"下界":真实可被利用的比例可能更高,不同攻击者/更大预算下的上限未知 [[2606.16062]]。
- 没有做"用修复后 vs 未修复任务训练 RL,对比下游效果"的因果实验——目前的证据链是"测试套件能被骗 + 模型确实在这类任务上表现更好",但未直接证明"修复能改善训练结果" [[2606.16062]]。
- 审计样本小（SWE-bench Verified 只覆盖 12 仓库中的 2 个,R2E-Gym K=1）,134 模型元分析是唯一 n>100 的部分 [[2606.16062]]。

## 相关概念

[[verifiable-reward-environment-generation]]（同一枚硬币的另一面:那边讨论的是环境先行管线"容易给 reward hacking 留空间"这一结构性风险,本页给出的是具体比例和修复闭环的实证方法）、[[benchmark-item-validity-audit]]（互补而非重叠:后者面向评测基准的 all-fail 任务,用 oracle run / nop run / cheat-variant trial 三类主动探测区分"真难/oracle坏/基础设施坏/verifier漏洞/证据不足"五类;本页面向 code RL 训练环境,直接生成错误补丁实测能否骗过测试套件,关注的是"能通过的错误解"而非"过不了的正确解"——两者方向相反但方法论精神一致:都不满足于单一 pass/fail 分数,都要求主动构造反例去测试 verifier 本身）、[[generator-verifier-asymmetry]]（本页的 gold-sanity gate 本质是把"验证 LLM 生成的测试是否正确"这一易被误判的子问题,转化为"在 gold 解上执行"这一更便宜、更客观的验证方式,是 generator-verifier 不对称问题的一个具体解法）、[[hack-verifiable-environment]]（正交而非重叠:本页测的是环境/verifier 本身会不会为随意生成的错误解发奖励,HVE 测的是模型在真实完成任务过程中会不会主动利用暴露出来的捷径——一个面向环境质量,一个面向 agent 行为,可以叠加用于同一条可验证奖励环境流水线）

## 相关来源

- [[2606.16062]] — 提出 EQS 四维质量分数与 gold-sanity gate 修复闭环,在 SWE-bench Verified / R2E-Gym 上实测 28.5%/25.0% 的 Docker 验证 hackability,并用 134-模型元分析与 61.9% augmenter 缺陷率两组独立证据交叉验证
- [[2608.22103]] — 提出正交的 HVE 埋点检测方法论,用蜜罐文件 + inotify 监视器测真实 agent 轨迹的黑客率,而非合成错误补丁测环境弱点;在 Terminal-Bench 上实测提示披露程度能降低但不能消除黑客行为,且效果因模型而异（gemini-3.1-pro 例外反升）
