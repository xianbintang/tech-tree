---
title: "Computer-Use Agent"
aliases: [CUA, Computer Use Agent, GUI agent, 计算机使用智能体]
created: 2026-09-29
updated: 2026-09-30
sources: [2609.24890, 2404.07972]
---

# Computer-Use Agent

## 一句话定义

通过截图观察图形界面、用鼠标/键盘操作（如 pyautogui 指令）完成桌面任务的智能体（CUA），与 code/terminal agent 并列，是"agent 训练与评测基准"覆盖的一类具体智能体 [[2609.24890]]。

## 为什么对我们重要

CUA 是我们研究方向里"code / SWE / terminal / computer-use / GUI agent 的训练、环境合成与评测基准"这一关注点的直接组成部分。CUA 任务通常是长程、多步骤、依赖截图输入的重负载任务，对训练/评测基础设施（推理服务成本、沙箱执行环境）的要求和纯文本 code agent 不同，值得单独追踪。

## 核心机制 / 主要变体

- 典型任务形式：给定一个自然语言目标 + 一个可"看到"的 Linux 图形界面环境，agent 生成一段轨迹（截图观察 + 推理 + pyautogui 代码动作）来达成目标 [[2609.24890]]。
- 评测范式分两类：**结果导向**（如 OSWorld，只检查最终产物是否匹配参考文件）和 [[process-based-evaluation]]（如 [[osworld-pro]]，逐子目标打分）[[2609.24890]]。
- 动作类型分布（[[osworld-pro]] 统计）：点击类占主导（51.0% click + 3.6% doubleClick + 2.8% rightClick + 2.7% tripleClick），其次键盘（16.6% press + 13.6% typewrite）、滚动（3.3% scroll）、执行控制（1.9% sleep 等）[[2609.24890]]。
- CUA 任务的形式化：把任务建模为 POMDP，观测是自然语言指令 + 截图/accessibility(a11y) 树（或组合），动作是原始鼠标键盘代码（如 pyautogui 的 `.click(x,y)`、`.hotkey(...)`）外加 `WAIT`/`FAIL`/`DONE` 三个特殊动作，是这套形式化最早被系统提出、并被后续工作（含 [[osworld-pro]]）沿用的版本 [[2404.07972]]。
- 结果导向评测的原型 [[2404.07972]]（OSWorld，2024-04）：369 个真实 Ubuntu/Windows 任务，用 example-wise 的 getter（提取最终状态：文件、cookie、a11y 树片段）+ evaluator（判定是否达成）组合出 134 个不重复评测函数，远超此前 WebArena（5 个）、AgentBench（7 个）等工作；覆盖 OS/Office/Daily/Professional/Workflow 五类任务，跨应用 workflow 占 27.4%。

## 工程要点与数字

- 长程任务轨迹平均 55.1 步、最多 149 步，每步含一张 1920×1080 截图，评测单个任务人工标注需 5–20 小时，说明 CUA 轨迹的评测和训练都是重负载场景 [[2609.24890]]。
- 不同模型在同一批 CUA 任务上的 token 成本可以相差 20 倍（$0.51 到 $9.56/任务），全量跑一次基准测试可达数千美元/模型 [[2609.24890]]。
- 2024 年 OSWorld 首次系统测量的能力缺口：人类完成率 72.36%（中位耗时 111.94 秒），当时最强模型（GPT-4，a11y tree 输入）只有 12.24%；跨应用 workflow 任务上所有模型均低于 7%；失败样本里 >75% 是鼠标点击坐标不准 [[2404.07972]]。两年后 [[osworld-pro]] 显示顶尖闭源模型在结果导向的 OSWorld 上已能到 83.4%，但换到过程式评测（OSWorld-Pro）会跌到 77.7%，说明"结果导向分数走高"不等于"过程执行同样可靠"。
- 强模型（Claude、GPT-5.6 高档位）在点击坐标精度、键盘/滚动操作上明显强于弱模型和小参数开源模型（Minimax M3、Kimi K3 点击进度似然仅 39–42% vs 强模型 72–92%）[[2609.24890]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- CUA 训练/评测所需的沙箱执行环境（图形界面虚拟机、快照、镜像分发）工程方案，本库尚未有笔记覆盖，是明确的调研空白——[[2404.07972]] 只披露了"VM 快照恢复 + 混合式初始状态配置"的架构思路，没有给出密度、冷启动、镜像大小等数字，[[2609.24890]] 更是完全未披露。
- CUA 的 process reward 能否有效接入 RL 训练循环、对训练吞吐/成本的影响，目前只有 [[osworld-pro]] 提出方向，无实验验证 [[2609.24890]]。

## 相关概念

[[osworld-pro]]、[[process-based-evaluation]]、[[agent-execution-sandbox]]

## 相关来源

- [[2609.24890]] — 提出 OSWorld-Pro，对多种闭源/开源模型在 CUA 长程任务上的表现、成本、失败模式做了系统分析
- [[2404.07972]] — OSWorld 原论文：首次提出 CUA 的 POMDP 形式化、可执行 VM 环境架构、example-wise execution-based 评测方法，是 [[osworld-pro]] 沿用的模型 harness 与评测范式起点
