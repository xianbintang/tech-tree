---
title: "Skill-to-Task Pipeline"
aliases: [skill-to-task pipeline, 技能到任务管线, skill internalization, agent skill 内化, 对比式 skill 依赖性测试]
created: 2026-09-29
updated: 2026-09-29
sources: [2609.27717]
---

# Skill-to-Task Pipeline

## 一句话定义

把人写的 agent skill（工作流说明文档：流程描述、用例、伪代码、执行约束）批量转成可执行、可代码化验证的训练任务环境的管线，核心创新是用"有/无 target skill 的对比执行"来验证一个任务是否真的依赖该 skill [[2609.27717]]。

## 为什么对我们重要

这是"agent 轨迹数据、环境构造与可验证奖励的工程实现"这一关注方向下的一个具体、可复用的方法论：不同于纯手工设计任务或纯程序化生成，它拿**已有的、人写的 skill 库**当种子，用模板化+对比验证的方式批量转成训练环境。如果我们平台要支撑"把内部 runbook/SOP/skill 库变成训练数据"这类需求，这条管线的两级准入设计（可行性 + 对比依赖性）是可以直接借鉴的质量控制思路 [[2609.27717]]。

## 核心机制 / 主要变体

- **三阶段管线**：
  1. **Skill-Aware Template Construction**：按 skill 子类手工设计可复用任务模板 $\mathcal{T}_c$（任务蓝图、输入资产、文件结构、验证规范），不是逐 skill 单独设计 [[2609.27717]]。
  2. **Environment Construction & Validation**：$E_i=\text{Instantiate}(K_i,\mathcal{T}_{c(i)})=(x_i,A_i,\rho_i,V_i)$，$V_i$ 是代码化 outcome verifier（含反捷径检查：防输入篡改、防答案抄袭、防绕过需求、防伪造输出）[[2609.27717]]。
  3. **Multi-Harness Trajectory Sampling**：用多组 harness-model 配置（不同 agent scaffold × 不同教师模型）在准入环境上采样轨迹，verifier 二次过滤，只留成功轨迹供下游 SFT/RL 使用 [[2609.27717]]。
- **两级准入（Two-level Acceptance）**：
  - Level 1 可行性检查：环境结构完整、端到端可执行。
  - Level 2 **对比 skill 依赖性测试**：同一参考 agent 分别在"有 target skill 文本"和"无 target skill 文本"两种条件下各跑一次 $(r_i^+,r_i^-)$；$(1,0)$（有则过、无则败）才标 **Skill-Dep.**；仍通过 verifier 但不满足这个对比条件的，退而标 **Verifier-Passed** 备选；两者都不满足则丢弃 [[2609.27717]]。
  - 失败驱动修正：把构建失败按环境错误/验证器错误/难度不匹配/弱 skill 依赖分组，用构建日志指导模板修订，形成反馈闭环 [[2609.27717]]。
- **产出只喂 SFT，不做 RL**：verifier 给出的是 0/1 outcome reward，理论上可直接支撑 RL，但 [[2609.27717]] 只做了拒绝采样 + 全参数 SFT，RL 是明确写的未来工作 [[2609.27717]]。

## 工程要点与数字

- 规模：2,756 个准入环境（12 大类、63 子类），Skill-Dep. 1,081 个（39.2%）、Verifier-Passed 备选 1,675 个（60.8%）[[2609.27717]]。
- 构建成本：平均 **4.5 小时/任务**（人工+agent 混合构建，不同类别间差异较大：research 类最低约 2.6h，documentation 类最高约 6.3h）[[2609.27717]]。
- 采样成功率：48,152 次采样试验仅 8,364 条通过 outcome verifier，**总体成功率 17.4%** [[2609.27717]]。
- 成功轨迹里**只有 36.8% 显式调用了 target skill**（跨配置 17.1%–57.4% 浮动）——说明"通过 verifier"和"确实用了 skill 里教的流程"是两件事，验证器通过率不能代表过程性知识被复用 [[2609.27717]]。
- 训练侧：8,364 条轨迹（平均 49.0 次工具调用、63.4k token、35.2 步）对 Qwen3.5-35B-A3B 做全参数 SFT，16×H200，Megatron 后端 [[2609.27717]]。
- 效果：SFT 后模型即使**不给**推理时 skill，也超过 base 模型**给了** skill 的分数（Claude Code harness 下 SkillsBench v1.1：26.81% vs 23.34%），是这条管线"内化而非照抄"论点的核心证据 [[2609.27717]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 对比依赖性测试的结论只对参考 agent 配置成立，换一个更强/更弱的 agent，Skill-Dep. 标签是否还准确，论文承认未验证 [[2609.27717]]。
- 沙箱/执行环境的具体实现（$\rho_i$ 运行时约束怎么落地、Docker 化细节、并发与冷启动开销）论文正文未披露，需要去读代码仓库补充 [[2609.27717]]。
- 这条"离线拒绝采样 + SFT"路线与真正把 verifier reward 接入 RL 相比效果差多少，尚无对照实验——环境和数据都已开源，是一个可以后续验证的具体问题 [[2609.27717]]。
- 与 [[verifiable-reward-environment-generation]] 里 VHD-Play 的"机制先行"范式相比，两者对"环境生成成本"的可比性有限（VHD-Play 报 $0.01–0.03/条纯生成成本，SkillGym 报 4.5 小时/任务的人工+agent 混合构建成本，统计口径不同），跨范式的成本对比是个开放问题。

## 相关概念

[[verifiable-reward-environment-generation]]、[[on-policy-distillation]]

## 相关来源

- [[2609.27717]] — 提出 skill-to-task pipeline 与两级准入（可行性 + 对比 skill 依赖性测试），构建 2,756 环境 / 8,364 轨迹，用 SFT 内化到 35B 模型并验证
