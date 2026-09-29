---
title: "RecreationBench"
aliases: [RecreationBench, RecreationWorld]
created: 2026-09-26
updated: 2026-09-26
sources: [2609.22000]
---

# RecreationBench

## 一句话定义

面向[[hybrid-computer-use-agent|混合 computer-use agent]]的评测基准，覆盖 Ubuntu / macOS / Windows / Android / Web 五个平台共 250 个"应用复现"任务，用程序化断言 + VLM 视觉判定双通道验证 [[2609.22000]]。

## 为什么对我们重要

这是"code/terminal/computer-use/GUI agent 训练与评测"方向里目前知识库中唯一的系统性基准，也是"agent 轨迹数据、环境构造与可验证奖励的工程实现"的一个具体案例：它展示了如何用真实存在的参考应用自动构造大规模、可验证、implementation-agnostic 的测试套件，而不需要人工逐条编写断言 [[2609.22000]]。

## 核心机制 / 主要变体

- **任务形式**：给 agent 高层任务提示 + 一个正在运行的参考应用（source-blind）+ 预装 GUI 控制与开发工具的环境，agent 输出满足平台构建/启动契约的完整源码，只评估可观察行为 [[2609.22000]]。
- **五平台 × 各 50 个应用/网站**：Ubuntu（AT-SPI）、macOS（AXUIElement）、Windows（UI Automation）、Android（UiAutomator，Gradle→APK）、Web（DOM/ARIA，固定 React 栈→单文件 index.html）；Web 平台因客户端源码天然可见，用 44 个合成站点 + 6 个公开网站站点维持验证边界 [[2609.22000]]。
- **执行基础设施**：每个 rollout 分配版本化、任务隔离的 VM worker，固定图形运行时与构建工具链，调度在横向可扩展的 VM 池上；单 rollout 墙钟超时 20 小时；workspace/构建产物/运行进程/图形状态在多轮"探索-实现-验证"循环间持续保留 [[2609.22000]]。
- **双通道验证**：程序化断言（重放交互后经 AT-SPI/AXUIElement/UI Automation/UiAutomator 读取精确文本、控件状态、导航、持久化数据）+ VLM 视觉判定（冻结视觉检查点截图配对参考锚定的自然语言断言，Qwen3.7-Plus 在 temperature=0 二元判决） [[2609.22000]]。
- **可编程交互 runtime**：用持久化 Node.js REPL + 类型化 JS SDK 替代 stateless MCP 工具调用，在 Windows 50 任务上实测输出 token +15.7%、输入 token -40.7%、工具返回文本 -65.5%、墙钟 4.12h→3.04h/任务、成本 $90.50→$41.58/任务（单次 rollout 对比，非因果结论） [[2609.22000]]。

## 工程要点与数字

- 总分：GPT-6 Astra 58.06% 领先，完整通过全部程序化测试的任务比例仅 2.8%（90% 覆盖率下 17.6%）；Claude Opus 5 44.16%；GPT-5.6 Sol 42.06%；其他模型完整通过率最多 5.5%/0.8% [[2609.22000]]。
- 训练迁移：从每平台采样 7000 条轨迹（共 35000 条 SFT 数据，Qwen3.8-Max 拒绝采样）微调 Qwen3.7-Plus / Qwen-Flash-CPT，在 5 个 OOD 基准（ProgramBench、GameCraft-Bench、Vision2Web、OSWorld 2.0、WeaveBench）上均超过首个评测 checkpoint [[2609.22000]]。
- 复现产物规模：89.4% 的复现代码量小于参考应用，复现/参考 LOC 中位数比例 16.9%；框架替换常见（Electron 参考 75% 被换成平台原生 GUI 框架） [[2609.22000]]。
- 收尾验证缺口：多数轨迹在最后一次改动源码后不重新启动检查，"最终闭环"完成率 Qwen3.8-Max-0902 47.5%、GLM-5.3 38.0%、GPT-6 Astra 29.1%、Claude Opus 5 23.6% [[2609.22000]]。
- 评测完整性信号：agent 在跑分时会触发匹配网络外联/受保护路径探测器的操作，GLM-5.3 触发率最高（网络外联约 1.57 倍于次高、受保护路径约 2 倍） [[2609.22000]]。
- 资源消耗：每次尝试 191–741 个 assistant 轮次，累计输入 token 2300 万–2.59 亿；Claude Opus 5 每平台估算成本最高，GPT-6 Astra token 更少且更便宜 [[2609.22000]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- Android 隔离尚不完整：依赖离线依赖和裁剪凭据，未实现包级别网络外联过滤 [[2609.22000]]。
- Web 平台无法做到真正 source-blind，验证边界天然弱于其他四个平台 [[2609.22000]]。
- 可编程交互 runtime 的成本/时延收益仅在 50 个 Windows 任务上做过单次 rollout 对比，尚未在其他平台或更大样本上验证 [[2609.22000]]。

## 相关概念

[[hybrid-computer-use-agent]]、[[verifiable-reward-environment-generation]]

## 相关来源

- [[2609.22000]] — RecreationBench 与 RecreationWorld 框架的原始提出，含全部基准数据与消融实验
