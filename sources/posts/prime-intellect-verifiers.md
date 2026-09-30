---
title: "verifiers — Prime Intellect 的 RL 环境与评测库"
type: post
id: "prime-intellect-verifiers"
source_url: https://github.com/PrimeIntellect-ai/verifiers
authors: [William Brown]
affiliations: [Prime Intellect]
published: 2025-01-22
code_url: https://github.com/PrimeIntellect-ai/verifiers
---

verifiers 是 Prime Intellect 用于"创建环境来训练与评测 LLM"的开源库（MIT 许可，Will Brown 原作者，现由 Prime Intellect 维护，4.7K+ star）。它定义了 Taskset / Task / Harness / Agent / Env / Runtime 一套正交抽象：Taskset 打包数据与评分逻辑，Harness 是模型运行所在的程序（Claude Code、Codex、bash 等），Runtime 是执行沙箱（subprocess/docker/podman/apptainer/prime/modal），Env 编排单/多 agent 的控制流。配套 `vf-init`/`vf-eval` CLI 脚手架与运行环境包，并原生支持把 Harbor（Terminal-Bench 团队的容器化评测框架）任务集接入为 Taskset，同时与 Prime Intellect 的 Environments Hub、训练框架 prime-rl、Hosted Training 平台打通。

笔记：[[prime-intellect-verifiers]]
