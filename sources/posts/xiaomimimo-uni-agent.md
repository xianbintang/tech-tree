---
title: "Uni-Agent: Train Long-Horizon Agents at Scale"
type: post
id: "xiaomimimo-uni-agent"
source_url: https://github.com/XiaomiMiMo/uni-agent
authors: [Yuyang Ding, Bo Wen, Xubo Cao, Zhiqiang Zhai, Guangming Sheng, Xibin Wu, Juntao Li, Min Zhang, Uni-Agent Contributors]
affiliations: [verl-project, XiaomiMiMo]
published: 2026-09-21
code_url: https://github.com/verl-project/uni-agent
---

Uni-Agent 是一个训练长程（long-horizon）agent 的框架：把任意已有 agent harness（如 Claude Code、Mini-SWE-Agent）接入 RL 训练，用统一接口（Agent / Tool / Task / Sandbox）承载不同类型的 agent 任务，并支持数千个长程、有状态 session 并发运行，产出可追溯的训练数据（SFT + RL）。README 报告了 SWE-Bench Verified（最高 64.2%，Qwen3-Coder-480B）、SWE-Bench Multilingual、Terminal-Bench v2.0/v2.1（最高 67.4%，Claude Code + GLM5.2-733B）等评测结果，以及在 R2E-Gym、SWE-reBench 上用 GRPO/GSPO 类目标做 RL 训练带来的提升（如 Qwen3-30B-A3B 从 22.2 → 36.8）。沙箱后端支持 local/Docker（本地）与 veFaaS、Modal、OpenYuanrong（远程弹性沙箱）。GitHub 仓库 `XiaomiMiMo/uni-agent` 是 `verl-project/uni-agent` 的 fork（fork 创建于 2026-09-21）。

笔记：[[xiaomimimo-uni-agent]]
