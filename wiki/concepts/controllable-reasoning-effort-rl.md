---
title: "RL 中的可控推理力度（Reasoning Effort Control）"
aliases: [reasoning effort control, controllable reasoning effort, exponential token penalty, 推理力度可控, 成本-质量前沿]
created: 2026-09-27
updated: 2026-09-27
sources: [2609.19969]
---

# RL 中的可控推理力度（Reasoning Effort Control）

## 一句话定义

在 RL 训练中把一个标量"努力程度"（effort，1–100）作为显式条件信号注入 system prompt，通过随 effort 指数衰减的长度惩罚系数，让同一个模型 checkpoint 在部署时能沿着学到的成本-质量前沿做细粒度的推理长度/质量权衡 [[2609.19969]]。

## 为什么对我们重要

对应研究方向"训练侧系统工程"与"adjacent_areas：LLM 推理与服务优化（与训练吞吐/成本相关时）"的交叉点：output token 数量直接决定 serving 成本，这个机制把"用多少 token 思考"变成一个可在部署时连续调节的旋钮，而不是训练时固定死的行为——对我们评估"一个模型能不能灵活适配不同延迟/成本预算的生产场景"是一个具体的可比较维度 [[2609.19969]]。

## 核心机制 / 主要变体

- **条件信号注入**：训练和推理时都在 system prompt 里显式声明 `Reasoning Effort: {effort}`（范围 1–100，越高要求越充分的推理），同时用于单轮推理任务和多轮 agentic 任务 [[2609.19969]]。
- **组内奖励中心化**：对每个训练 prompt $x$，在每个 effort 等级 $b\in\mathcal{B}$ 各采样 $M_b$ 个响应；共享同一 $(x,b)$ 的响应构成一个子组，组内做奖励均值中心化算相对优势——不同 effort 等级的响应彼此不直接比较，效果通过让长度惩罚项依赖 $b$ 来实现 [[2609.19969]]。
- **指数衰减的长度惩罚**：
  $$r^{len}_{b,j} = -\min\left\{C_{max},\, k(b)\frac{\ell_{b,j}}{L_{norm}}\right\}, \qquad k(b) = k_0\exp\left(-\frac{b-b_{min}}{\tau}\right),\ \tau=\lambda\overline{\Delta b}$$
  其中 $\ell_{b,j}$ 是推理 token 数，$L_{norm}$ 是参考长度，$C_{max}$ 是最大惩罚扣减上限；effort 每增加 $\tau$，惩罚系数乘以 $e^{-1}$。$k_0$ 控制整体"往短打"的压力强度，$\tau$ 越小则不同 effort 等级之间的行为分离越明显 [[2609.19969]]。
- **部署时的连续插值**：训练只用有限个离散 effort 等级，但部署时可以用训练中未出现过的中间值来诱导插值式的推理行为，提供细粒度的测试时资源分配手段；生产 API 通常只暴露少数几档预设值映射到底层标量（如 max/high/low）[[2609.19969]]。

## 工程要点与数字

- DeepSeek-V4.1-Flash 生产 API 暴露三档：`max`→$b=100$、`high`→$b=75$、`low`→$b=50$ [[2609.19969]]。
- Effort 从 25 升到 100：八个推理密集型基准（AIME 2026、Apex 2025 Shortlist、GPQA Diamond、HLE、IMO-AnswerBench、LiveCodeBench、MathArena-Apex、SimpleQA-Verified）均分 Pass@1 从 67.1% 升到 76.3%；DeepSWE v1.1 从 66.0% 升到 74.2%；Terminal-Bench 2.1 从 82.4% 升到 90.6%；代价约 2.5× 输出 token 量 [[2609.19969]]。
- 收益前置：60–80 区间已经能拿到接近最大 effort 的大部分精度收益，且 token 预算不到最大档的一半；从 80 到 100 的最后一段只换来边际提升，但轨迹长度膨胀 1.6–1.8×——这意味着"拉满"档位只适合最难的任务，日常场景用中等 effort 性价比更高 [[2609.19969]]。
- 单轮推理上学到的 effort 控制能力可以**迁移到长程 agentic 轨迹**，在多轮场景里控制跨轮次的探索和验证总量，不是只对单次生成有效 [[2609.19969]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- effort 值与实际 serving 延迟/成本之间的映射关系（不同硬件、不同并发度下）未给出量化模型，只有 token 数的代理指标。
- 训练时只用少数离散 effort 等级，部署时插值行为的稳定性边界（比如 effort=60 和 effort=65 之间的行为差异是否单调、是否存在不稳定区间）未做专门验证。

## 相关概念

（暂无，后续如有更多论文涉及"推理力度/思考预算可控"可在此补充）

## 相关来源

- [[2609.19969]] — 提出该机制并给出跨 effort 等级的推理/agentic 基准量化结果（§5.1.4、§5.3.3、Appendix C）
