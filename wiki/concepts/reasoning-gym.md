---
title: "Reasoning Gym"
aliases: [RG, reasoning gym, 推理体育馆, procedural reasoning environments]
created: 2026-09-30
updated: 2026-09-30
sources: [2505.24760]
---

# Reasoning Gym

## 一句话定义

一个开源库：100+ 个程序化生成、算法可验证的**单轮、纯文本**推理任务生成器（算数、代数、几何、算法、逻辑、图论、常见游戏等），每个任务可通过难度/结构/风格三类参数控制复杂度，从而提供"虚拟无限"且难度可调的 RLVR 训练与评测数据，替代传统固定问答对数据集 [[2505.24760]]。

## 为什么对我们重要

Reasoning Gym 代表环境隔离需求光谱上**最轻的一端**：任务本身是"生成问题字符串 → 模型作答 → 纯函数比对/计算验证"，没有文件系统、网络、持久状态、多轮交互，验证器就是一次无副作用的函数调用。这与我们平台主要关注的 agentic/工具调用环境（需要完整容器或 microVM 隔离）形成明确对照，帮助我们在给环境分级时划出一档"无状态纯函数验证"类型——这类任务完全不需要占用重沙箱资源，可以用进程内调用甚至不隔离的方式获得远高于容器/microVM 的并发密度 [[2505.24760]]。

## 核心机制 / 主要变体

- **三条设计原则**：(P1) 算法可验证性——每个任务自动可验证，无需人工判断；(P2) 大解空间——奖励泛化策略、抑制 reward hacking；(P3) 参数化难度控制——难度/结构/风格三类参数系统控制问题特征，支持动态课程 [[2505.24760]]。
- **100+ 生成器分十类**（附录 Table 6）：Algorithms(32)、Games(18)、Cognition(14)、Arithmetic(11)、Logic(7)、Algebra(6)、Graphs(6)、Geometry(4)、Code(2)、Induction(2) [[2505.24760]]。
- **三类可调参数**：难度参数（节点数、多项式次数、单词长度）直接控制复杂度；结构参数（维度、约束类型、证明深度）决定问题本质属性；风格参数（变量命名、数字格式）只影响呈现、不影响难度 [[2505.24760]]。
- **Curriculum RLVR**：滑动窗口 20 个训练步内成功率超过 70% 就自动升一级难度，对比"固定难度、均匀采样所有等级"的基线——课程学习在所有测试环境上稳定优于固定难度（如 Spell Backwards 单词长度 4 提升 40.67%）[[2505.24760]]。
- **训练算法**：用 [[grpo]]（GRPO）在 Qwen2.5-3B-Instruct 上做实验，验证 intra-domain、cross-domain 迁移与外部基准（GSM8K/MATH/BBH/MMLU-Pro）迁移效果 [[2505.24760]]。
- **明确的能力边界（作者自述局限）**：仅支持单轮、纯文本任务，不含多轮交互或多模态任务——这是与工具调用/agentic 环境（如 [[tau-bench]]、[[agentbench]]）的关键区别；验证只看最终答案，不检查解题过程 [[2505.24760]]。

## 工程要点与数字

- **零样本难度悬崖**：从 easy 切到 hard 配置，o3-mini 在 code 上暴跌 −71.9%、graphs −33.8%、geometry −33.1%、algorithms −25.6%；DeepSeek-R1 同类别分别 −61.8%、−29.6%、−11.8%、−27.9%——视觉-空间推理类任务（cognition、games）即使最强模型也不到 50% 准确率 [[2505.24760]]。
- **推理 vs 非推理模型有约 22 个百分点的系统性差距**：o3-mini 63.5%、DeepSeek-R1 59.5% 领先，Llama 4 Maverick 41.5%、Claude 3.5 Sonnet 40.3%、Gemma 3 27B 20.3% 明显落后 [[2505.24760]]。
- **Intra-domain 迁移全面为正**（Table 1，Acc@3）：Algebra +11.7pp、Algorithmic +7.4pp、Arithmetic +6.3pp、Cognition +2.0pp、Games 0→3.3（从零起步）[[2505.24760]]。
- **Cross-domain 迁移大多为正但有例外**（Table 2）：RG-Algorithmic→Algebra +29.1pp、→Geometry +22.3pp；RG-Logic→Cognition +13.3pp；但 ARC 上两个训练方向都是负迁移（−2.2~−2.3pp），Games 测试集上 RG-Logic 训练反而 −0.8pp [[2505.24760]]。
- **外部基准迁移**（RG-Math，algebra+arithmetic+geometry composite，800 步 GRPO）：GSM8K +0.5pp、MATH +9.7pp、Big-Bench Hard +7.66pp、MMLU-Pro Math +5.62pp [[2505.24760]]。
- **训练算力**：全部实验约 **1500 个 A6000 GPU-hour**（Runpod 云租用）——论文唯一披露的算力成本数字，是"轻量可验证环境 + 小模型 RLVR"这条路线的具体成本量级参照 [[2505.24760]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- Cross-domain 迁移里 ARC、Games→Games 的负迁移案例未被论文进一步解释，是否与"视觉-空间推理用纯文本表征"这一根本局限有关，尚待验证 [[2505.24760]]。
- 论文自己承认实验假设数据均匀采样，未反映真实场景数据分布非平稳变化的情况；程序化生成器能否扩展到需要深厚领域知识/创造力的复杂推理域也未验证 [[2505.24760]]。
- Reasoning Gym 这类单轮任务目前未见接入 [[openenv-interface-spec]] 或 [[verifiers-framework]] 这类环境标准/打包框架的证据，与 agentic 环境生态的整合路径尚不明确。
- 实测我们自己训练管线上跑 Reasoning Gym 生成器的吞吐/并发密度，验证"无状态纯函数验证任务可以不占用重沙箱资源"这一判断在我们基础设施上的实际收益（follow-up，见 [[2505.24760]] 笔记）。

## 相关概念

[[verifiable-reward-environment-generation]]、[[generator-verifier-asymmetry]]、[[agentic-rl-environments]]、[[grpo]]、[[verifiers-framework]]

## 相关来源

- [[2505.24760]] — Reasoning Gym 原始论文：100+ 生成器分类、参数化难度控制、Curriculum RLVR、intra/cross-domain 迁移与外部基准迁移实验、1500 A6000-hour 训练算力
