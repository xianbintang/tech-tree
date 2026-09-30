---
title: "Computer-Use Agent"
aliases: [CUA, Computer Use Agent, GUI agent, 计算机使用智能体]
created: 2026-09-29
updated: 2026-09-30
sources: [2609.24890, 2506.03569]
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
- **通用 VLM 也能追平/超过 GUI 专用模型**：MiMo-VL-7B-RL（一个通用视觉语言模型，非专为 GUI 设计）在 OSWorld-G（no_refusal 子集）拿到 56.1 分，超过专用模型 UI-TARS-1.0；在 ScreenSpot-Pro-avg 上 41.9 分，远超同规模通用模型 Qwen2.5-VL-7B（29.0）。说明 GUI grounding 能力可以作为通用多模态 RL 训练（[[grpo]] 的 RLVR 分支之一）的副产物获得，不一定需要专门的 GUI-only 训练管线 [[2506.03569]]。

## 工程要点与数字

- 长程任务轨迹平均 55.1 步、最多 149 步，每步含一张 1920×1080 截图，评测单个任务人工标注需 5–20 小时，说明 CUA 轨迹的评测和训练都是重负载场景 [[2609.24890]]。
- 不同模型在同一批 CUA 任务上的 token 成本可以相差 20 倍（$0.51 到 $9.56/任务），全量跑一次基准测试可达数千美元/模型 [[2609.24890]]。
- 强模型（Claude、GPT-5.6 高档位）在点击坐标精度、键盘/滚动操作上明显强于弱模型和小参数开源模型（Minimax M3、Kimi K3 点击进度似然仅 39–42% vs 强模型 72–92%）[[2609.24890]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- CUA 训练/评测所需的沙箱执行环境（图形界面虚拟机、快照、镜像分发）工程方案，本库尚未有笔记覆盖，是明确的调研空白。
- CUA 的 process reward 能否有效接入 RL 训练循环、对训练吞吐/成本的影响，目前只有 [[osworld-pro]] 提出方向，无实验验证 [[2609.24890]]。
- MiMo-VL 用 bbox GIoU / 点选命中作为 GUI grounding 的 RLVR 奖励，属于结果导向的静态 grounding 打分，未涉及 [[osworld-pro]] 的过程式多步子目标评测——两者是同一问题（GUI 交互能力）在"训练奖励"和"评测指标"两端的不同实现，尚未看到把过程式评测直接接入训练奖励回路的工作 [[2506.03569]] [[2609.24890]]。

## 相关概念

[[osworld-pro]]、[[process-based-evaluation]]、[[grpo]]

## 相关来源

- [[2609.24890]] — 提出 OSWorld-Pro，对多种闭源/开源模型在 CUA 长程任务上的表现、成本、失败模式做了系统分析
- [[2506.03569]] — MiMo-VL-7B-RL 用通用多模态 RL（RLVR 中的 grounding 任务）训出超过专用模型 UI-TARS 的 GUI grounding 能力
