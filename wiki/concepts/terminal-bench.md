---
title: "Terminal-Bench"
aliases: [Terminal-Bench 2.0, Terminal-Bench 3, Frontier-Bench 0.1]
created: 2026-09-29
updated: 2026-09-30
sources: [2609.26826, 2601.11868]
---

# Terminal-Bench

## 一句话定义

Laude Institute 主导的终端 / agentic 编程任务前沿评测基准；2.0 版是 89 个众包+三重人工审核的硬任务集（前沿模型最高解出 63%）[[2601.11868]]，3.0 版（生产代号 Frontier-Bench 0.1）在排行榜分数之外还留有完整的任务生产记录（PR、评审、trial、控制实验）[[2609.26826]]。

## 为什么对我们重要

其任务规范（容器镜像+指令+终态测试+oracle 解+时限）直接就是我们在用的 [[harbor]] 任务格式的源头 [[2601.11868]]；任务生产与验证流程（reference solution、verifier、nop / oracle / cheat-variant 控制实验、评审留痕）示范了"评测基础设施"该有的形态——这正是我们平台在沙箱执行环境之上要补的"可信评测"能力：不仅要能跑 agent，还要能证明一次失败/通过说明了什么 [[2609.26826]]。

## 核心机制 / 主要变体

### Terminal-Bench 2.0（[[2601.11868]]）

- 任务规范：指令（自然语言）+ Docker 镜像 + 一组测试 + 人工参考解 + 时间限制；**结果驱动**——测试只检查任务结束时容器的最终状态，不检查命令序列或控制台输出，agent 可用任意方式达成目标。这套格式后来被固化为 [[harbor]] 的任务格式（`instruction.md`+`task.toml`+`environment/`+`solution/`+`tests/`）并由 Harbor harness 执行。
- 数据集构建：93 位贡献者众包 229 个任务，按难度评估与三名资深评审的质量审核精选出 89 个入选 Terminal-Bench 2.0；平均每个入选任务获得约 3 个评审员小时的审核投入。
- 六阶段质量审核：自动化 oracle 校验（提交时跑参考解+反 no-op 检查）→ 贡献者自查清单 → LLM 自动检查工具 → 资深评审员人工核查 → 多模型+中立 agent 实跑区分真失败/任务本身坏了 → 对抗式 exploit agent 找作弊漏洞 → 两名额外审计员终审。三个验证标准贯穿全程：specificity（测试充要性）、solvability（存在会通过的 oracle 解）、integrity（不能靠不代表真实工作流的取巧手段通过）。
- **Terminus 2**：论文自带的中立评测脚手架，唯一工具是 headless tmux 终端，agent 只能发 Bash 按键序列操作，内置上下文摘要模块支持需要数百万 token 的超长任务；用于把"模型能力"和"agent scaffold 工程"两个变量解耦。
- Adapter 层：26 个外部基准（SWE-Bench Verified、MLE-Bench、Cybench、AlgoTune、AppWorld 等）通过 adapter 翻译成 Terminal-Bench 标准 schema 接入，合入前要求做平价实验（parity experiment）确认语义未被破坏。

### Terminal-Bench 3 / Frontier-Bench 0.1（[[2609.26826]]）

- 生产记录快照 `3c5be84efd707da8`：1081 个 PR、639 个已评分任务、28801 次 trial、$105,933 记录的 agent 花费；PR 语料冻结截至 PR 1416，之后基准的线上变化不影响该快照的结论 [[2609.26826]]。
- trial 拆分为四类：21219 次普通 agent trial、4668 次 cheat-variant trial（诱导 agent 用任意手段通过，探测 verifier 可被诱导接受什么）、1605 次 oracle run（跑作者参考解，测试 verifier 是否接受既定路线）、1309 次 nop run（提交空解，测试 verifier 能否拒绝平凡非解）[[2609.26826]]。
- 每个任务都关联：提交包、PR 历史、verifier、参考解、trial 遥测、轨迹、控制实验、评审记录——论文把它当作任务生产语料而不只是一个排行榜来用 [[2609.26826]]。

## 工程要点与数字

- Terminal-Bench 2.0 实验规模：6 个 agent scaffold（Claude Code、Codex CLI、Gemini CLI、OpenHands、Mini-SWE-Agent、Terminus 2）× 16 个模型，累计 32,155 次 trial，用 [[harbor]] harness + Daytona 沙箱并行跑 32–100 个容器 [[2601.11868]]。
- Terminal-Bench 2.0 最优结果：Codex CLI + GPT-5.2 解出 62.9%±3.0%，Terminus 2 + Claude Opus 4.5 为 57.8%，开源权重最好的是 Terminus 2 + Kimi K2 Thinking（35.7%）；模型选择通常比 agent scaffold 更重要（同一 agent 换模型的提升幅度普遍大于同一模型换 agent）[[2601.11868]]。
- Terminal-Bench 2.0 成本与时长：跑完整个基准视模型定价从 \$1 到 \$100+；多数 trial 20 分钟内完成，极端情况单任务跑到 2 小时、近 1 亿 token；turn 数/token 量与成功率几乎不相关（r=-0.028 / r=-0.170）[[2601.11868]]。
- Terminal-Bench 2.0 命令级错误分析：命令失败率从 9.2%（Grok 4）到 26.7%（GPT-OSS-120B），最大单一失败来源是"调用不存在/不在 PATH 里的可执行文件"（24.1%）[[2601.11868]]。
- 555 个 closed-unmerged PR（被拒任务）中，最大拒绝原因是"难度不足"，但仍有大量任务因指令模糊、verifier 问题、环境不确定性、元数据/重复等"任务有效性"问题被拒，而非模型能力问题 [[2609.26826]]。
- 被拒任务的平均诚实通过率因拒绝原因差异巨大：难度不足类 0.64，verifier 过拟合/太难类 0.10，指令模糊类 0.17，环境损坏/不确定类 0.18，可利用 verifier 类 0.41，质量/元数据类 0.45——单看通过率无法诊断任务是"真难"还是"评测工具坏了" [[2609.26826]]。

## 争议与矛盾

（暂无跨来源分歧；[[2609.26826]] 的五分类有序验证 screen 是对 [[2601.11868]] 六阶段审核流程的延伸细化，两者结论互补而非冲突）

## 开放问题

- Terminal-Bench 2.0 论文自己承认约三人时/任务的审核投入下仍可能有任务不完全满足验证标准，但未像 [[2609.26826]] 那样做同等规模的事后再审计 [[2601.11868]]。
- 作者预计基准可能在一年内饱和（8 个月内 SOTA 从 Gemini 2.5 Pro 到 GPT-5.2 近乎翻倍），但尚未公布下一代高难度任务集的具体计划 [[2601.11868]]。
- TB3 生产记录审计论文只公开生产记录的审计方法和汇总统计，未公开具体的 125 个 all-fail 任务清单与被拒 PR 的完整明细，第三方难以直接复现审计结果 [[2609.26826]]。

## 相关概念

[[harbor]]、[[benchmark-item-validity-audit]]、[[agent-execution-sandbox]]

## 相关来源

- [[2601.11868]] — Terminal-Bench 2.0 原始论文：89 个众包+三重审核的硬任务集，任务规范（后成为 Harbor 任务格式源头）、六阶段质量审核流程、Terminus 2 中立评测脚手架、跨 6 agent×16 模型的完整实验结果
- [[2609.26826]] — 对 Terminal-Bench 3 / Frontier-Bench 0.1 生产记录做全面审计，把 2601.11868 的六阶段审核流程延伸为五分类有序验证 screen，是目前唯一公开描述其内部生产/评审语料结构的来源
</content>
