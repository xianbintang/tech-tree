---
title: "rLLM / DeepSWE：开源 Agent RL 训练框架与 SWE Agent 训练实践"
type: post
id: "rllm-deepswe"
source_url: https://github.com/rllm-org/rllm
authors: [Michael Luo, Naman Jain, Jaskirat Singh, Sijun Tan, Colin Cai, Tarun Venkat, Manan Roongta, Li Erran Li, Raluca Ada Popa, Koushik Sen, Ion Stoica, Ameen Patel, Qingyang Wu, Alpay Ariyak, Shang Zhu, Ben Athiwaratkun, Ce Zhang]
affiliations: [Agentica (Berkeley Sky Computing Lab), Together AI]
published: 2025-07-02
code_url: https://github.com/rllm-org/rllm
---

rLLM 是 Agentica（Berkeley Sky Computing Lab）开源的 agent 强化学习后训练框架："Bring any harness, run it in any sandbox, and switch training backends with one flag"——agent 代码在 eval 和训练阶段保持不变，通过透明的 model gateway 捕获 token id 和 logprob，支持 GRPO/REINFORCE/RLOO/SFT/on-policy distillation 等算法，训练后端可选 verl（分布式多 GPU）、tinker（单机）或 fireworks，覆盖 60+ 基准（SWE-bench、Terminal-Bench 2.0、AIME、GPQA 等）与 10+ CLI harness（Claude Code、Codex、mini-swe-agent 等）。

rLLM 训出的旗舰模型之一是 DeepSWE-Preview：从 Qwen3-32B 出发、仅用强化学习（无 SFT/蒸馏）训练的编码 agent，基于 R2E-Gym 环境的 4,500 个真实 SWE 任务、64 张 H100 训练 6 天，在 SWE-Bench-Verified 上取得 42.2% Pass@1（16 次评测均值）、71.0% Pass@16，配合 hybrid test-time scaling 达到 59.0%，是当时开放权重编码 agent 的 SOTA。训练算法上提出 GRPO++（融合 DAPO 的 Clip High/No KL、Dr.GRPO 的去标准差/长度归一化、RLOO 的 leave-one-out，以及自研的 Compact Filtering 与 No Entropy Loss），系统侧用 Kubernetes 取代原生 Docker 编排解决了大规模并发容器导致 dockerd 崩溃的问题。数据集、训练代码、评测日志全部开源。

笔记：[[rllm-deepswe]]
