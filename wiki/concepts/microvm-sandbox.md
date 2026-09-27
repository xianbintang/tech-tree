---
title: "microVM 沙箱（Firecracker 类隔离后端）"
aliases: [microVM, Firecracker sandbox, VM-level agent isolation]
created: 2026-09-27
updated: 2026-09-27
sources: [2609.19969]
---

# microVM 沙箱（Firecracker 类隔离后端）

## 一句话定义

用轻量虚拟机（如 Firecracker microVM）作为 agent 执行环境的隔离后端之一，相比容器提供更强的隔离边界，代价是暂停/恢复需要保存和恢复完整的内存与执行状态快照 [[2609.22978]]。

## 为什么对我们重要

对应研究方向里"沙箱与执行环境基础设施：microVM、容器运行时、隔离"这一核心能力项。生产级 agent RL 平台（DSec）把 microVM 作为多种隔离后端之一（与 FnCall、容器、full-VM 并列），说明"单一沙箱抽象无法覆盖所有 agent workload"是已验证的工程结论，而不是理论上的权衡讨论 [[2609.22978]]。

## 核心机制 / 主要变体

- **多后端并存**：DSec 通过统一 SDK 暴露 FnCall（无状态函数调用）、容器、microVM、full-VM 四种沙箱后端。轻量、无状态的短任务适合 FnCall；需要完整商用操作系统的工作负载（如需要完整系统功能、更强隔离的场景）更适合 VM 类后端 [[2609.22978]]。
- **microVM 的暂停/恢复**：暂停时把 microVM 的内存和执行状态保存为快照，再终止运行中的 Firecracker 进程以释放该 microVM 的运行时内存；恢复时启动一个新进程并从快照恢复以继续 guest 执行 [[2609.22978]]。这与容器的暂停/恢复（`docker pause` + `memory.reclaim` / `MADV_WILLNEED` + `docker unpause`）机制不同：容器是冻结/唤醒进程树，microVM 是完整的状态快照/恢复，代价更高但隔离边界更强 [[2609.22978]]。
- **agent 建环境即 microVM/容器通用**：DSec 支持 `pack_diff`——agent 可以在任意时刻对一个沙箱做增量磁盘快照，之后可作为新沙箱恢复，把交互式会话直接变成可复用环境，不需要独立的镜像构建流水线 [[2609.22978]]。

## 工程要点与数字

- 生产环境中单节点最多可承载约 **800** 个 microVM 或 **3,200** 个容器（不同后端密度上限不同，一般容器密度高于 microVM，因为隔离开销更小）[[2609.22978]]。
- microVM 后端与容器后端在同一套高密度调度机制（sub-NUMA 分区、LS 执行类）下运行，详见 [[sandbox-density-overcommit]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- microVM 相对容器的性能开销（冷启动时间、内存开销）具体数字未在本次精读的章节中披露，需要读 DSec 论文的实现/评测章节（§7–§8）补充。
- 什么类型的 agent 任务被路由到 microVM 而非容器，路由决策的具体标准未展开。

## 相关概念

[[sandbox-density-overcommit]]、[[agentic-rollout-preemption]]

## 相关来源

- [[2609.19969]] — 提及 DSec 支持 microVM 后端，并描述 V4.1 训练如何使用该沙箱平台跑百万级并发 agent
