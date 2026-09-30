---
title: "Terminal-Bench"
aliases: [Terminal-Bench 3, Frontier-Bench 0.1]
created: 2026-09-29
updated: 2026-09-30
sources: [2609.26826, 2608.22103]
---

# Terminal-Bench

## 一句话定义

面向 terminal / agentic 编程任务的前沿评测基准；Terminal-Bench 3（生产代号 Frontier-Bench 0.1）除了排行榜分数外，还留有完整的任务生产记录（PR、评审、trial、控制实验）[[2609.26826]]。

## 为什么对我们重要

其任务生产与验证流程（reference solution、verifier、nop / oracle / cheat-variant 控制实验、评审留痕）示范了"评测基础设施"该有的形态——这正是我们平台在沙箱执行环境之上要补的"可信评测"能力：不仅要能跑 agent，还要能证明一次失败/通过说明了什么 [[2609.26826]]。

## 核心机制 / 主要变体

- 生产记录快照 `3c5be84efd707da8`：1081 个 PR、639 个已评分任务、28801 次 trial、$105,933 记录的 agent 花费；PR 语料冻结截至 PR 1416，之后基准的线上变化不影响该快照的结论 [[2609.26826]]。
- trial 拆分为四类：21219 次普通 agent trial、4668 次 cheat-variant trial（诱导 agent 用任意手段通过，探测 verifier 可被诱导接受什么）、1605 次 oracle run（跑作者参考解，测试 verifier 是否接受既定路线）、1309 次 nop run（提交空解，测试 verifier 能否拒绝平凡非解）[[2609.26826]]。
- 每个任务都关联：提交包、PR 历史、verifier、参考解、trial 遥测、轨迹、控制实验、评审记录——论文把它当作任务生产语料而不只是一个排行榜来用 [[2609.26826]]。
- [[hack-verifiable-environment]] 把 Terminal-Bench 全量任务自动转换成 8989 个"黑客可验证"版本（HVTB）：在 agent 工作目录埋入暴露真实解/测试的 `admin/` 蜜罐目录，用 inotify 监视器确定性检测是否被访问，测出的是"agent 在真实完成任务时会不会主动利用暴露出来的捷径"，与本页关注的"任务生产/评审质量"是互补的两个视角 [[2608.22103]]。

## 工程要点与数字

- 555 个 closed-unmerged PR（被拒任务）中，最大拒绝原因是"难度不足"，但仍有大量任务因指令模糊、verifier 问题、环境不确定性、元数据/重复等"任务有效性"问题被拒，而非模型能力问题 [[2609.26826]]。
- 被拒任务的平均诚实通过率因拒绝原因差异巨大：难度不足类 0.64，verifier 过拟合/太难类 0.10，指令模糊类 0.17，环境损坏/不确定类 0.18，可利用 verifier 类 0.41，质量/元数据类 0.45——单看通过率无法诊断任务是"真难"还是"评测工具坏了" [[2609.26826]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 论文只公开生产记录的审计方法和汇总统计，未公开具体的 125 个 all-fail 任务清单与被拒 PR 的完整明细，第三方难以直接复现审计结果 [[2609.26826]]。

## 相关概念

[[benchmark-item-validity-audit]]、[[hack-verifiable-environment]]

## 相关来源

- [[2609.26826]] — 对 Terminal-Bench 3 / Frontier-Bench 0.1 生产记录做全面审计，是目前唯一公开描述其内部生产/评审语料结构的来源
- [[2608.22103]] — 把 HVE 方法论套到 Terminal-Bench 上构造 HVTB（8989 个黑客可验证环境），测量 5 个前沿模型在不同提示披露程度下的 reward hacking 率
</content>
