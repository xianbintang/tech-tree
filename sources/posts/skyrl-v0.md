---
title: "SkyRL-v0: Train Real-World Long-Horizon Agents via Reinforcement Learning"
type: post
id: "skyrl-v0"
source_url: https://novasky-ai.notion.site/skyrl-v0
authors: [Shiyi Cao, Sumanth Hegde, Dacheng Li, Tyler Griggs, Shu Liu, Eric Tang, Jiayi Pan, Xingyao Wang, Akshay Malik, Kourosh Hakhamaneshi, Richard Liaw, Philipp Moritz, Matei Zaharia, Joseph E. Gonzalez, Ion Stoica]
affiliations: [UC Berkeley (Sky Computing Lab), Anyscale, All Hands AI]
published: 2026-05-06
code_url: https://github.com/NovaSky-AI/SkyRL
---

## 摘要（原文）

Most existing RL frameworks are optimized for tasks that involve stateless interactions over short horizons, such as search-augmented reasoning or simple code execution. In contrast, real-world tasks, like those represented in SWE-Bench, benefit from long-horizon planning in stateful, dynamic environments. This presents new challenges in both infrastructure and training algorithms. We introduce SkyRL, our RL training pipeline for multi-turn tool use LLMs, optimized for long-horizon, real-environment tasks like SWE-Bench, built on top of VeRL and OpenHands. Using SkyRL, we are able to achieve promising results on SWE-Bench-Verified across model lines, using around 300 samples of training data.

笔记：[[skyrl-v0]]
