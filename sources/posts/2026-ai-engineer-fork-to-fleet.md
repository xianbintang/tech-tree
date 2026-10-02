---
title: "From fork() to Fleet: Designing an Agent Sandbox Cloud"
type: post
id: "2026-ai-engineer-fork-to-fleet"
source_url: https://ai.engineer/talks/OqM67QG_Ikk-from-fork-fleet-designing-agent-sandbox-cloud
authors: [Abhishek Bhardwaj]
affiliations: [OpenAI]
published: 2026-10-01
---

OpenAI RL 与 agent 基础设施团队的 Abhishek Bhardwaj 在 AI Engineer World's Fair 2026 的演讲（44 分钟，页面带完整逐字稿）。第一性原理地讲完整条"agent 沙箱云"设计链路：为什么需要代码执行（可验证奖励训练）→ 运行时隔离谱系（fork/exec → Linux 容器+namespaces/cgroups/seccomp → gVisor 用户态内核 → 硬件虚拟化/crosvm 系 microVM，Firecracker 与 Cloud Hypervisor）→ 磁盘持久化（XFS reflink 写时复制 + FIEMAP 增量快照、NBD 分层块存储做 always-on 持久化）→ 跨节点编排（集群/区域层级调度、warm pool / 内存快照恢复 / 混合三种冷启动策略、快照分层感知调度）。是作者上一场《How to Build an AI Sandbox from Scratch》的"精神续作"，并指向其开源项目 Arrakis。

笔记：[[2026-ai-engineer-fork-to-fleet]]
