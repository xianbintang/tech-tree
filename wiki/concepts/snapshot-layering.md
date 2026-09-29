---
title: "Snapshot Layering / 分层增量快照"
aliases: [layered snapshots, incremental snapshot tree, 快照树, provenance-based deduplication, 分层快照]
created: 2026-09-26
updated: 2026-09-26
sources: [brooker-lambda-snapstart, brooker-seven-years-of-firecracker, aws-lambda-microvms-agent-sandboxes]
---

# Snapshot Layering / 分层增量快照

## 一句话定义

在 microVM 生命周期的多个自然阶段（刚启动、语言运行时就绪、客户代码初始化后）分别打快照，形成一棵快照树、每一层只存相对父快照的增量，使得共享组件（内核、运行时）的数据无需在每次克隆时重复分发，并天然支持按层分离加密密钥。

## 为什么对我们重要

我们的沙箱/agent 环境构建通常本身就有天然的分阶段结构（base 镜像 → 装依赖 → agent 专属配置/预热）。如果我们用快照或 checkpoint-restore 做冷启动优化，分层快照是比"整份快照去重"或 [[on-demand-image-loading]] 里"整份镜像去重"更细粒度的优化方向——它不需要事后扫描比对内容，去重发生在快照生成的那一刻，天然与我们环境构建的阶段边界对齐。

## 核心机制 / 主要变体

- **快照点选择**：可以在 microVM 刚启动后、语言运行时启动后、客户代码初始化后分别打快照，不必只选一个 [[brooker-lambda-snapstart]]。
- **增量存储**：后一层快照只存相对父快照变化的内存页，恢复时先恢复父层再应用子层的增量 [[brooker-lambda-snapstart]]。
- **Provenance-based 去重 vs 事后扫描去重（对比 KSM）**：子快照本就是从父快照恢复而来，哪些页相同是天然已知的，不需要像 Kernel Samepage Merging 那样运行时后台扫描比对内容，因此没有 KSM 式的 CPU vs 内存权衡 [[brooker-lambda-snapstart]]。
- **分层密钥管理**：不同层级可用不同加密密钥——公共组件（如内核、运行时）用服务侧密钥，客户数据用客户自己控制的密钥，只有一句话带过，未展开密钥派生/轮换/撤销机制 [[brooker-lambda-snapstart]]。
- **与克隆/唯一性问题的关系**：分层快照解决的是"数据怎么分层存、怎么少传输"，不解决 [[microvm-snapshot-uniqueness]] 讨论的"克隆出的实例状态相同"问题——两者是快照复用场景下正交的两类工程挑战，通常需要同时处理。

## 工程要点与数字

- Firecracker 快照恢复最快可到 4ms（完整 Linux 系统约 10ms），作者认为亚毫秒级恢复"应该可能"（推测，非实测）[[brooker-lambda-snapstart]]。
- 分层快照对常见负载最多减少 90% 的数据搬运量——**未说明测量方法与基线**，应视为厂商声称而非独立验证结果 [[brooker-lambda-snapstart]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 与本页机制相邻但不同的一种收益：Aurora DSQL 从同一份快照批量克隆出多个 Query Processor microVM 时，克隆实例之间可以共享**未被修改的干净内存页**（省内存 + 部分 CPU 缓存层级只需存一份）——这不是"分层增量快照"（跨阶段边界存增量），而是"同一层快照的多个并发克隆共享未变内存"，两者是快照复用场景下两种不同但可能共存的省数据手段，原文没有说明 DSQL 的共享机制是否基于 provenance（与本页去重逻辑相同）还是事后扫描 [[brooker-seven-years-of-firecracker]]。
- 具体的密钥派生/轮换/撤销机制未披露，对比 [[2023-brooker-lambda-container-loading]] 收敛加密方案的详尽程度，这部分明显只是简化科普 [[brooker-lambda-snapstart]]。
- 分层快照针对的是**快照内存**的去重与分发，与 [[on-demand-image-loading]] 里 [[2023-brooker-lambda-container-loading]] 针对**容器镜像**的按需加载+ 收敛加密去重是否共享底层基础设施，两篇文本均未说明，仅问题描述与时间线高度吻合（详见 [[on-demand-image-loading]] 「开放问题」）。
- DSec（[[2609.22978]]）§6.3 的 microVM pause/resume 是单实例挂起-恢复同一身份，不是本页讨论的"多层快照树 + 克隆多实例"场景，DSec 是否在内部使用了类似的分层快照机制，原文未说明，无法确认。
- AWS Lambda MicroVMs 的"从快照启动"（[[aws-lambda-microvms-agent-sandboxes]]）是本页机制的又一个生产实例，但公开描述里只有单层快照（镜像构建完成后打一次快照，之后所有 session 都从这一份启动），未提及多阶段分层快照树；与 DSec §6.1 的 `pack_diff`（把交互式 session 的增量磁盘快照直接变成可复用环境构建产物，本身会形成一条不断增长的快照演化链）相比，用法更接近"一次性冷启动优化"而非"把快照当持续演化的构建工具"，两者是快照复用的两种不同使用模式。

## 相关概念

[[microvm-snapshot-uniqueness]]、[[on-demand-image-loading]]

## 相关来源

- [[brooker-lambda-snapstart]] — Firecracker/Lambda 作者 Marc Brooker 提出分层快照树的设计思路：按 provenance 去重 + 分层密钥，声称最多减少 90% 数据搬运量
- [[brooker-seven-years-of-firecracker]] — Aurora DSQL 案例：同一份快照的多个克隆实例共享未修改内存页，是与分层增量快照相邻但不同的省数据手段（见「开放问题」）
- [[aws-lambda-microvms-agent-sandboxes]] — 又一个"从快照启动跳过初始化"的生产案例（AWS Lambda MicroVMs），但只用单层快照，未披露分层机制，也未讨论克隆唯一性问题
