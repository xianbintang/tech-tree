---
title: "Agent 轨迹树构建与去重采样（Agent Trajectory Tree Dedup）"
aliases: [trajectory tree, TITO trajectory tree, 轨迹树, branching trajectory dedup, partial scoring, 分支执行去重]
created: 2026-09-30
updated: 2026-09-30
sources: [2609.33848]
---

# Agent 轨迹树构建与去重采样（Agent Trajectory Tree Dedup）

## 一句话定义

在黑盒 harness（只能拿到模型调用记录和任务级评估结果，看不到/改不了 harness 内部控制流）场景下，用 token-in/token-out（TITO）记录把一次执行的所有模型调用组织成带共享前缀的轨迹树，对超时/部分完成的执行做基于已保留产物的部分评分，再按角色优先级从树上有界、去重地采样训练轨迹，避免分支执行（compaction、sub-agent 委派、重试）产生的共享前缀被重复编码和重复计入训练损失 [[2609.33848]]。

## 为什么对我们重要

我们平台如果要支撑用生产级黑盒 harness（Claude Code、Codex 这类闭源、快速演进的 agent）做 RL rollout，就绕不开这个问题：harness 一旦开始压缩历史或派生 sub-agent，rollout 记录就不再是一条线性轨迹，而是一棵图。这个概念给出了一套具体可落地的"评测产物 → 训练数据"转换范式，尤其是"部分评分"和"有界去重采样"这两步，直接决定了我们的 agent RL 数据管线在长程任务上是否会被无意义的重复计算或劣质训练信号拖垮。

## 核心机制 / 主要变体

- **TITO 记录**：黑盒代理精确记录每次模型调用的输入/输出 token id、behavior log-prob 和元数据；同时按 call ID 缓存原始工具调用负载，在匹配历史前还原它们，避免 harness 对工具调用做格式重排导致的历史误判 [[2609.33848]]。
- **前缀共享轨迹树**：每次执行的所有 TITO 记录被组织成一棵树——新请求与已有路径做前缀匹配，只编码新增内容并挂成新节点，分叉的上下文形成分支，无匹配前缀的请求挂到根。候选轨迹在被选中前始终留在这个共享表示里，避免对每条路径做全历史展开 [[2609.33848]]。
- **Trainable token 由 provenance 决定**：只有策略在 rollout 时真正生成的 token 才是可训练目标；harness 注入的 system/user/tool 内容只作为条件上下文，被掩码、不贡献训练信号 [[2609.33848]]。
- **部分评分（Partial Scoring）**：对执行终止时**已保留的工作产物**打分，而非对时长/轨迹长度/终止状态打分——超时但有部分进展的执行能拿到区分度更高的分数，而不是和"完全没做"共享同一个失败 reward。评估失败（区别于合法的 0 分）在预算内重试，预算耗尽则整条执行被剔除出训练；对完全没有可评估产物的罕见失败（如镜像拉取失败），插入 reward=0 的占位轨迹 [[2609.33848]]。
- **按角色优先级的有界去重采样**：把轨迹树的叶子按角色分类排序（如 Claude Code 场景下 `main > main-summary > sub-agent > sub-agent-summary`），从最高优先级、仍有未掩码 token 的类别里按未掩码 token 数成比例抽样，抽中后把该叶子的 root-to-leaf 路径整条掩码（保证共享前缀只被训练一次），重复直到无可训练 token 或达到每次执行最多 $J_{\max}$ 条轨迹的上限 [[2609.33848]]。
- **两层平均防止过度加权**：被选中的轨迹继承其执行的组相对 advantage；先在执行内部对可训练 token 求平均、再对执行间求平均，防止某次执行因为选出更多轨迹（或某类轨迹本身更短）就获得更大的聚合权重 [[2609.33848]]。
- **与同类工作的定位差异**：Agent Lightning、Polar、LEGO-RL 关注在 harness 控制的上下文处理下保留 rollout-time token 身份；ClawGym II 把捕获的请求重建成共享前缀树、让 PPO/GRPO 的共享节点只贡献一次训练信号；BPO/IAPO/MileGPO 用分支/依赖图/里程碑做更细粒度的信用分配；psRL 等在样本构造之后复用共享前缀。QwenGyre 的定位是把这些各自解决"轨迹捕获/信用分配/前缀计算"单一子问题的技术，与弹性调度（见 [[elastic-rollout-training-scheduling]]）耦合在同一套系统里，覆盖从 rollout 收集、准入到训练物化的全链路 provenance [[2609.33848]]。

## 工程要点与数字

- 轨迹采样预算消融：只采主轨迹（$J_{\max}=1$）训练分数更低、梯度范数更大；$J_{\max}=5$ 已能匹配"全采样"（uncapped）的训练分数和梯度范数。前 42 步平均前向-反向时间：$J_{\max}=1$ 是 uncapped 的 41.4%，$J_{\max}=5$ 是 74.8%——即用 25.2% 的前向-反向时间节省换到几乎无损的训练效果 [[2609.33848]]。
- 这套机制在 NL2RepoBench（52.5%→58.5%，48 步）、DeepSWE、TerminalBench 三个不同评测协议上都验证过训练分数与 baseline（不做去重/部分评分的假设配置）基本一致，同时端到端提速 1.2×–1.85×（速度数字主要来自配套的弹性调度，见 [[elastic-rollout-training-scheduling]]，两者在论文里是耦合评测的，没有单独隔离轨迹处理器本身的速度贡献）[[2609.33848]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 角色优先级规则（`main > main-summary > sub-agent > sub-agent-summary`）是针对 Claude Code harness 设计的启发式，论文未讨论它在其他 harness（不同的 compaction/sub-agent 语义）上是否需要重新定义、是否具有通用性 [[2609.33848]]。
- Partial Scoring 假设执行终止时的工作产物是"可部分评估"的（如已生成代码可跑测试）；对产物形态更抽象、没有清晰部分正确性定义的任务，这套机制能否直接套用未讨论 [[2609.33848]]。
- 论文没有把"轨迹处理器"本身的速度收益从"弹性调度"的速度收益中隔离出来，两者是耦合评测的。

## 相关概念

[[elastic-rollout-training-scheduling]]、[[agentic-rollout-preemption]]、[[grpo]]、[[rollout-training-mismatch]]

## 相关来源

- [[2609.33848]] — 提出 TITO 轨迹树、部分评分、按角色优先级的有界去重采样，在黑盒 harness（Claude Code）驱动的 xLong agentic RL 场景下给出完整设计与消融数据，是本页目前唯一来源
