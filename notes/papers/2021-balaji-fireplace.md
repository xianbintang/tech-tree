---
title: "FirePlace: Placing Firecracker Virtual Machines with Hindsight Imitation"
type: paper
id: "2021-balaji-fireplace"
source_url: https://proceedings.mlsys.org/paper_files/paper/2021/file/294f82c43d69f66c04440cbb2740e52d-Paper.pdf
authors: [Bharathan Balaji, Christopher Kakovitch, Balakrishnan (Murali) Narayanaswamy]
affiliations: [Amazon]
published: 2021
created: 2026-09-26
tags: [scheduling, placement, microvm-sandbox, serverless, imitation-learning]
concepts: [hindsight-imitation-learning, power-of-two-choices, microvm-placement]
rating: 4
issue: 23
parent: "2609.22978"
---

# FirePlace: Placing Firecracker Virtual Machines with Hindsight Imitation

> 用"完美未来信息的贪心算法"生成标签，训练一个轻量分类器模仿它，来做 AWS Lambda 上 Firecracker microVM 的在线放置，比强化学习更省样本、更好部署。

## 元信息

- 机构：Amazon
- 发表：MLSys 2021（San Jose, CA），论文未标注具体月日
- 链接：[MLSys 2021 论文 PDF](https://proceedings.mlsys.org/paper_files/paper/2021/file/294f82c43d69f66c04440cbb2740e52d-Paper.pdf)
- 对比基线：Random（随机选 PM）、Baseline（均值特征 + best-of-K）、off-the-shelf RL（Ray RLlib 的 PPO）、Hindsight（本文提出的"教师"算法，用到未来真实数据，仅离线可用）

## 要解决的问题

AWS Lambda 把每次函数调用（invoke）放进一个 Firecracker microVM（µVM），µVM 再被放置（place）到某台物理机（PM）上。µVM 一旦放置就不能迁移，且必须在到达时（online，无法看到后续到达顺序）立刻决定放哪台 PM。目标是让整个机群的**峰均比**（PAR, Peak-to-Average Ratio）最小化，从而在不违反单机资源上限的前提下缩小机群规模、降本。

这本质是一个多维度、时变的在线 bin packing 问题（NP-complete、≥2 维时 APX-hard），传统思路是"先预测每个 VM 未来的资源用量，再用 Best-Fit/genetic algorithm 之类的启发式去放置"。但作者在 Lambda 生产流量上验证：µVM 的 CPU 用量高度spiky、生命周期短（中位数 ~15 分钟，p99 > 2 小时），无论 LSTM 还是 TCN，给 50 步历史预测未来 20 步都失败（Figure 3、4）——**µVM CPU 用量的最佳 p90 预测在整个生命周期上是 0**。预测这条路走不通，作者转向"预测无关"（forecasting-free）的放置算法。

## 方法

整体思路：把"放置决策"问题拆成"用完美未来信息的贪心算法生成标签" → "用监督学习模仿这个标签"两步，绕开预测。

```mermaid
flowchart LR
    subgraph 离线_用历史数据
        H1[历史 uVM 时序: 真实 CPU/内存] --> H2["Hindsight 算法\n(贪心, 用到未来真实值)"]
        H2 --> H3[state, action 标签对]
    end
    H3 --> T[训练分类器\nRandom Forest / SVM]
    T --> F[FirePlace 模型]
    F --> P["在线放置\n(只用当前特征, 不看未来)"]
```

### 1. 问题建模：Power-of-K-choices + PAR 奖励

为避免动作空间随机群规模爆炸，每次放置时只从机群里随机采样 K 个 PM（本文 K=2），在 K 个候选里选一个，这是经典的 [[power-of-two-choices]] 技巧——比纯随机指数级更优，又比"看全部 PM"的状态空间小得多。

单维（仅 CPU）奖励定义为（式 1）：

$$R_t = \frac{1}{|P|}\sum_{p\in P}\frac{\max_{t\in\tau} C_t^p}{\max_{p\in P,t\in\tau} C^p} - W_t$$

其中 $C_t^p$ 是 PM $p$ 在 $t$ 时刻的 CPU 用量，$W_t=1$ 表示选中的 PM 放不下这个 µVM（违规），否则为 0。第一项鼓励让各 PM 的峰值用量趋同（即降低 PAR），$W_t$ 惩罚"塞爆"。CPU+内存二维时（式 2）把两项归一化后相加。

### 2. Hindsight 算法：用未来真实值的贪心"教师"

Hindsight 算法假设可以看到 µVM 和 PM 未来完整的真实资源时序（只在离线训练时可行），对每个候选 PM 计算"如果把这个 µVM 放进去，它未来的峰值用量会变成多少"，选峰值最小的那个（CPU 单维，式 3–4）：

$$B_k^{cpu} = \max_{t\in T}(c_t^v + C_t^k), \quad A = \arg\min_{k\in K} B_k^{cpu}$$

二维版本用 CPU/内存峰值的 L2 范数（式 5，作者承认这个度量选择"来自经验而非第一性原理"）。Hindsight 仍是贪心的——它不考虑未来会有哪些新 µVM 到达，只是能看到已放置 µVM 未来会怎样变化。

### 3. FirePlace：模仿 Hindsight 的监督学习

核心创新：**不是训练 RL 智能体直接优化 PAR，而是先用 Hindsight 算法在历史数据上离线跑一遍、记录每一步的 (state, action)，再训练一个分类器去模仿 Hindsight 的选择**（作者称为 hindsight imitation，见 [[hindsight-imitation-learning]]）。

- 特征：CPU 用量取多窗口分位数（p10/p25/p50/p75/p100/mean），内存只取 p100 和 mean（内存单调增长到删除为止，分位数意义不大）。
- 模型：Random Forest 和 SVM 里选验证集准确率更高的一个；简单 2 层神经网络效果不好；引入原始时序特征+LSTM 会过拟合。
- 训练集划分：交替把 µVM 分到 train/test 两个分区（保证分布一致又互不泄漏），在 train 分区上跑 Hindsight 生成标签，75%/25% 切 train/validation。
- 关键工程细节：**跨天/跨 region 部署时准确率会因需求分布漂移而下降，解决办法是把 CPU/内存特征改成"PM 之间的相对值"而非绝对值归一化**——这是论文里为数不多明确点出的可复现落地经验。

### 4. RL 作为对照，而非最终方案

作者也用 Ray RLlib 的 PPO 训练了 RL 策略（状态=K 个候选 PM 及待放置 µVM 的分位数特征，动作=选哪个 PM）。结果是 RL 有时能匹配甚至略超 Hindsight，但经常明显更差，且在 20K→100K 数据集规模变大时训练曲线更容易在远低于 Baseline 的水平就 plateau（Figure 6）——**样本效率不足、且长时序+噪声状态空间让 RL 训练不稳定**是作者放弃直接上 RL 的原因。

## 实验与结果

数据：单个 region 的两个数据集（20K / 100K 个 µVM，24 小时生产流量）；20K 数据集用 4 核 16GB 的 PM，100K 数据集用 8 核 64GB 的 PM。

| 场景 | 数据集 | Hindsight vs Baseline | Hindsight vs Random | FirePlace vs Baseline |
|---|---|---|---|---|
| 仅 CPU 打包 | 20K/100K | +9% | +33% | 持平（FirePlace ≈ Baseline，CPU 太 spiky 难模仿） |
| CPU+内存 2D 打包 | 20K/100K | +12% | +21% | **+11%**（论文摘要给出的整体数字是 +10%，100K 数据集上） |

- Hindsight 模仿分类器的验证准确率：CPU 打包 91%/92%（20K/100K），2D 打包 79%/85%（20K/100K）——2D 场景更难学，这与 CPU 用量本身难以模仿一致。
- Table/Figure 对应：Figure 5（在线放置对比 Random/RL/Hindsight/Baseline/FirePlace）、Figure 6（RL 训练曲线，20K 与 100K）、Figure 2/3/4（µVM 资源特征与预测失败示例）。
- 生产 A/B 测试方案：起两个与生产隔离、大小相等的 fleet，各分一小部分等量流量，用聚合 CPU/内存对比 FirePlace 与 baseline 的表现——**论文只描述了 A/B 测试的设计，没有给出线上实测的具体数字**。
- 决策延迟约束：~20ms 内做出放置决策、吞吐约 5 次/秒——这两个数字直接约束了模型选择（放弃了预算内跑不完的多步预测/复杂 forecasting）。
- **没有披露**：模型推理延迟的具体测量值、机群规模缩减带来的成本节省百分比、生产 A/B 的实测提升。

## 局限与疑点

- 作者自己承认（Section 6–7、Conclusion）：① 这只是"概念验证"（proof of concept），需要在更多数据集、更长时间窗口上验证鲁棒性；② CPU 打包场景 FirePlace 只能追平 Baseline，未能像 2D 场景那样明显超越，作者猜测是 CPU 随机性太强导致模仿学习学不到有效信号，但没有进一步定量分析；③ 2D 打包某个子场景里 RL 反而超过了 Hindsight 教师（Figure 5b），说明本文选用的 L2 范数并非 CPU/内存权衡的最优度量，作者承认这个度量"来自经验，非第一性原理"。
- Hindsight 教师本身是贪心的，不考虑未来到达的新 µVM，其"上限"性质存疑——论文没有和真正的（哪怕是离线求解的）全局最优做对比，只知道它比 Random/Baseline 好，不知道离全局最优还差多少。
- 只在单一 region、单一同构 PM 规格（每个数据集内部同构）上验证，论文提到可扩展到异构机群但未做实验。
- 完全没有涉及 µVM 的创建/销毁决策（何时提前销毁空闲 µVM 省内存）——作者在 Conclusion 里明确说这是未来工作，也没有涉及跨 PM 的迁移（本设定里 µVM 一旦放置就不能迁移）。
- 论文发表于 2021 年，用的是 2021 年前后的 Lambda 生产流量特征（函数内存 128MB–3000MB、执行时间上限 15 分钟），与今天 agent 场景下的沙箱负载形态（例如更长的 agent 会话、更大的内存/磁盘需求）差异可能很大，结论的外推适用性需要打问号。

## 对我们的启发

- **"预测无关"的教训值得直接借鉴**：作者在真实 Lambda 流量上验证了 microVM 资源用量的 CPU 侧几乎不可预测（p90 预测在整个生命周期上是 0）。如果我们的沙箱调度也想走"先预测资源用量再做放置决策"的路子，这篇论文是一个明确的反例——**在动手做预测式调度前，先在自己的生产 trace 上验证可预测性**，否则大概率重蹈覆辙。
- **Hindsight imitation 是一个通用的"离线生成标签 + 监督学习模仿"套路**，比直接上 RL 更省样本、更好部署（延迟可预测、模型简单如 Random Forest/SVM，不需要在线探索）。如果我们的调度/超卖场景有类似"决策在线做、但训练可以离线用完整历史信息"的结构（例如沙箱冷启动的宿主机选择、镜像预热节点选择），这个套路值得复用，且比强化学习更容易在生产落地和调试。
- **Power-of-two(K)-choices 是把动作空间从"全机群"降到"K 个候选"的低成本手段**，配合几乎任意的打分函数（哪怕是简单的贪心 Hindsight 度量）就能拿到大部分收益——这对我们平台设计沙箱放置调度器时是一个非常低门槛、值得优先尝试的基线,而不是一上来就上复杂的全局优化或 RL。
- **跨天/跨 region 的分布漂移**：作者发现把特征改成"PM 间相对值"而非绝对值能显著缓解模型在新数据上的性能下降。这提示我们如果做类似的学习式调度器，从一开始就应该用相对/归一化特征，而不是等上线后发现漂移问题再改。
- **20ms 决策延迟、5 次/秒吞吐**的约束直接排除了复杂预测模型——这个数量级值得作为我们自己设计沙箱放置决策延迟预算时的参考基准（虽然我们的负载形态和量级未必一致）。
- Follow-up 建议（可转 issue）：
  1. 在我们自己的沙箱调度 trace 上验证 CPU/内存用量的可预测性（p90/p99 预测误差),决定是否值得投入预测式调度；
  2. 调研 hindsight imitation 这套"离线贪心标签 + 监督学习模仿"的思路能否直接搬到我们的沙箱放置/超卖决策上，作为比 RL 更易落地的基线；
  3. 待精读 [[2609.22978]]（DSec）§7 调度器章节后，回来补充"DSec 的 power-of-k-choices 放置器与 FirePlace 的具体异同"（目前只能确认两者都用 power-of-k-choices 降低动作空间，具体调度目标函数、超卖策略是否借鉴 Hindsight/FirePlace 尚不确定）。

## 相关

- 相关概念：[[hindsight-imitation-learning]]、[[power-of-two-choices]]、[[microvm-placement]]
- 相关笔记：（知识库内暂无同主题笔记）
- 与母论文的关系：[[2609.22978]]（DSec）尚未精读，无法逐节核对引用上下文。根据阅读清单 `config/reading-lists/dsec-refs.yaml` 的标注，本文被归入 Key C「AWS Lambda 专题」，理由是"Lambda 上 Firecracker VM 的放置调度（hindsight imitation）；对应我们的调度/超卖"；同一份阅读清单 Key F「资源超卖与调度」的描述提到"DSec §7 调度器用 power-of-k-choices 做沙箱放置"（对应条目 2001-mitzenmacher-power-of-two，尚未精读）。据此**推断**（非直接核实）DSec 很可能在讨论自身沙箱放置调度器时，把 FirePlace 作为"Firecracker/Lambda 生产环境里 power-of-k-choices + 学习式放置"的先例引用，但 DSec 自己的调度目标函数、是否采用了 hindsight imitation 式的模仿学习、超卖策略与本文有何异同，需要等 [[2609.22978]] 精读后回来补充，**不确定的地方已如实标注**。
