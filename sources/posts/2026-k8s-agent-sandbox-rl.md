---
title: "agent-sandbox-rl: multi-cluster batch orchestration for SWE-bench-style RL on Kubernetes Agent Sandbox"
type: post
id: "2026-k8s-agent-sandbox-rl"
source_url: https://github.com/kubernetes-sigs/agent-sandbox/tree/main/examples/agent-sandbox-rl
authors: [kubernetes-sigs/agent-sandbox contributors]
affiliations: [Kubernetes SIG (agent-sandbox), Google]
published: 2026-09-20
code_url: https://github.com/kubernetes-sigs/agent-sandbox/tree/main/examples/agent-sandbox-rl
---

`agent-sandbox-rl`（import 名 `agent_sandbox_rl`）是 `kubernetes-sigs/agent-sandbox` 仓库下的一个 example 包：在 Agent Sandbox v1beta1（`SandboxTemplate`/`SandboxWarmPool`/`SandboxClaim`/`Sandbox` CRD）之上提供通用、框架无关、多集群的批量编排 API，覆盖"镜像预热 → 按任务 claim 沙箱（拿到 hostname/endpoint）→ 释放 → 拆除"完整生命周期，专门针对 SWE-bench 风格的 RL rollout 和评测批量作业。核心能力：四种预热池策略（none/naive/sliding/pipelined）、按并发预算做副本 sizing、RL 场景的 instant-claim 优化（`warm_per_task` + `colocate_replicas`）、实验性的"沙箱复用"（git-restore reset + determinism canary）、多集群 placement、可观测性（RunReport/Prometheus/OTel）与熔断/reaper 安全网。文档含 README.md、docs/design.md（设计理由）、docs/architecture.md（架构与生命周期）。

笔记：[[2026-k8s-agent-sandbox-rl]]
