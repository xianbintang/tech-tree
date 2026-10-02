---
title: "自我对弈策略迭代（Self-Play Policy Iteration）"
aliases: [self-play reinforcement learning, AlphaGo Zero, MCTS 自我对弈, 策略迭代, self-play + MCTS]
created: 2026-10-03
updated: 2026-10-03
sources: [2017-silver-alphago-zero]
---

# 自我对弈策略迭代

## 一句话定义

用 MCTS 搜索作为"策略提升算子"（搜索出的落子概率总是比网络原始输出更强）、用自我对弈的终局胜负作为"策略评估算子"，让神经网络不断逼近搜索结果，在策略迭代循环里自己生成越来越强的训练数据，完全不依赖人类数据 [[2017-silver-alphago-zero]]。

## 为什么对我们重要

AlphaGo Zero 是"奖励=环境规则本身、零人工标注"这条路线的最早、最极端的大规模实证——环境是一个验证成本近乎为零的完美模拟器（棋类规则引擎）。它的自我对弈训练基础设施（持续生成 rollout + 异步训练 + 评测门控晋升）是今天 agentic RL rollout 调度问题的一个历史先例，拿来和 [[rollout-training-disaggregation]]、[[async-rl-training]] 等现代设计对照，能看清"生成数据的策略要不要门控"这个设计维度一直存在，只是不同系统做出了不同取舍。

## 核心机制 / 主要变体

- **MCTS 作为策略提升 + 自我对弈作为策略评估**：单个网络 $f_\theta(s)=(p,v)$ 同时输出落子概率与局面胜率；每步执行一次 MCTS 搜索得到比 $p$ 更强的搜索概率 $\pi$，用 $\pi$ 走棋、终局胜负 $z$ 当价值标签，训练 $(p,v)\to(\pi,z)$——$l=(z-v)^2-\pi^\top\log p+c\|\theta\|^2$ [[2017-silver-alphago-zero]]。
- **三组件异步流水线**：Self-Play（当前最佳网络 $f_{\theta^*}$ 持续生成自我对弈数据）、Optimization（64 GPU worker + 19 CPU 参数服务器持续训练新 checkpoint）、Evaluator（新 checkpoint 需以 >55% 胜率在 400 局对局中战胜当前最佳才能"转正"、成为下一轮生成数据的来源）三者全程并行、互不阻塞 [[2017-silver-alphago-zero]]。
- **"评测门控晋升"而非"始终用最新策略"**：Self-Play 用的是通过评测晋升的 $f_{\theta^*}$，不是训练模块刚产出的最新 checkpoint——这是刻意牺牲一部分数据吞吐，换取"只用验证过真的更强的策略生成数据"这个质量保证 [[2017-silver-alphago-zero]]。
- **探索与计算节省的工程细节**：前 30 步用温度 $\tau=1$ 按访问次数采样保持局面多样性，之后 $\tau\to0$ 确定性选择；根节点加 Dirichlet 噪声（$\epsilon=0.25$）保证所有着法都有机会被尝试；明显劣势对局提前认输节省算力，认输阈值自动调节以把"误判率"（本可翻盘却认输）控制在 5% 以下（10% 对局关闭认输用于测量这个误判率）[[2017-silver-alphago-zero]]。
- **验证成本近乎为零**：除棋局规则（合法落子、终局判定、棋盘的旋转/翻转对称性）外不使用任何人类数据、手工特征或启发式；判断一局棋谁赢是规则引擎的确定性计算，没有代码执行沙箱那种不可忽略的运行时开销 [[2017-silver-alphago-zero]]。

## 工程要点与数字

- 小规模跑（20 残差块）：训练约 3 天，490 万局自我对弈，1,600 次 MCTS 模拟/步（约 0.4s/步），70 万个 mini-batch 更新（每 batch 2,048 个局面）；72 小时后以 100-0 击败分布式 48 TPU 的 AlphaGo Lee，而 AlphaGo Zero 自己只用单机 4 TPU [[2017-silver-alphago-zero]]。
- 大规模跑（40 残差块）：训练约 40 天，2,900 万局自我对弈，310 万个 mini-batch 更新；Elo 5,185，对比 AlphaGo Master 4,858、AlphaGo Lee 3,739、AlphaGo Fan 3,144、不用搜索的原始网络 3,055 [[2017-silver-alphago-zero]]。
- 训练集群（64 GPU+19 CPU 参数服务器）与推理/对局硬件（单机 4 TPU）规模高度不对称——高质量的策略可以大幅压缩推理侧资源需求，但论文未讨论训练算力里"评测门控"这部分占比 [[2017-silver-alphago-zero]]。

## 争议与矛盾

- MCTS 自我对弈在棋类这种完美信息、规则可完美模拟的领域效果极佳，但 DeepSeek-R1（Appendix G.2）明确尝试过把 MCTS 搬到 LLM 推理场景并失败——token 级搜索空间远大于棋类游戏的落子空间，价值模型难以训练到能指导精细搜索 [[2501.12948]]。这两篇来源不是直接矛盾（领域前提不同），但说明"MCTS + 自我对弈"这套方法论的成功高度依赖"状态空间有限、规则可完美模拟、验证近乎零成本"这几个前提，一旦前提不满足（LLM 的 token 级动作空间），方法论本身可能不再适用，而不只是工程调参的问题。

## 开放问题

- "评测门控晋升"这种生成策略在现代大规模 agentic RL 系统里是否还有实践者使用、相对于"始终用最新策略容忍 policy lag"（见 [[async-rl-training]]）的吞吐/质量权衡是否被系统性测量过，知识库里暂无数据。
- 验证成本近乎为零这个前提在多大程度上是 AlphaGo Zero 结果"看起来很强"的必要条件——如果把同样的策略迭代思路搬到验证有真实开销的领域（代码执行、agent 轨迹判定），三组件异步流水线的吞吐瓶颈会如何变化，目前没有直接对照实证。

## 相关概念

[[rlvr]]（本概念是"规则奖励"思路在验证成本几乎为零场景下的历史先例；[[rlvr]] 讨论的代码执行验证有不可忽略的沙箱开销，是光谱上更贵的一端）、[[generator-verifier-asymmetry]]、[[async-rl-training]]、[[rollout-training-disaggregation]]、[[verifiable-reward-environment-generation]]

## 相关来源

- [[2017-silver-alphago-zero]] — 提出 MCTS 自我对弈 + 策略迭代训练 AlphaGo Zero，给出三组件异步训练基础设施与 rollout 规模的完整数字
