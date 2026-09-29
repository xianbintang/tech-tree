---
title: "沙箱高密度资源超卖"
aliases: [high-density resource management, CPU/memory overcommit, QoS-aware CPU scheduling, 内存共享与回收, core scheduling]
created: 2026-09-26
updated: 2026-09-26
sources: [2609.22978]
---

# 沙箱高密度资源超卖

## 一句话定义

利用 agent 沙箱"CPU 稀疏、常年等待模型下一步动作"的特点做资源超卖，同时用内存共享/回收机制和两层 CPU QoS 调度分别解决超卖带来的内存膨胀和延迟敏感任务被干扰的问题。

## 为什么对我们重要

超卖密度直接等于我们单位算力能承接的并发 agent 数量，是沙箱平台成本结构里最核心的杠杆之一。DSec 给出了生产验证过的具体机制组合（不是理论方案）和量化的收益/代价数字，可以直接作为我们自己超卖策略设计的对照基准。

## 核心机制 / 主要变体

- **超卖的前提观测**：约 90% 的容器和 microVM 沙箱平均 CPU 使用率不超过请求容量的 5%，因为 agent 在等模型生成下一步动作时 CPU 基本空闲，这是超卖成立的物理基础 [[2609.22978]]。
- **内存问题的两个来源（microVM 尤其严重）**：(1) 镜像数据经虚拟块设备读取时，host 和 guest 各缓存一份，造成跨边界重复缓存；(2) guest 内空闲页默认不会主动还给 host。由于沙箱生存期长（p99 超 3 小时）、请求内存常超实际需求，guest 内部缺乏回收压力，这些问题被长生命周期放大 [[2609.22978]]，详见 [[microvm-sandbox]]。
- **virtio-pmem + DAX**：把文件访问直接映射到 host 页而不拷入 guest RAM，让多个 co-located microVM 共享同一份 host 页缓存，从根上消除重复缓存问题；代价是冷访问需要同步缺页处理（不像 virtio-blk 能享受 guest 侵 readahead 和批量 I/O），且 guest 要为整个 pmem 地址范围分配 `struct page` 元数据（128GB pmem 设备占 2GB guest RAM）[[2609.22978]]。
- **DAMON + virtio-balloon free-page reporting**：对不适合走 pmem 的可写盘，用 DAMON（Linux 采样式内存访问监测框架）识别超过年龄阈值未被访问的冷页并主动回收，回收后的零散页被 buddy allocator 聚合成高阶块，满足 free-page reporting 默认要求的 2MiB（order-9）粒度门槛，再由 virtio-balloon 上报给 host、host 用 `madvise(MADV_DONTNEED)` 释放 [[2609.22978]]。
- **两层 CPU QoS**：先把沙箱分成 latency-sensitive（LS）和 best-effort（BE），BE 用 `SCHED_IDLE`（只在 LS 无事可做时抢 CPU）；但光靠调度优先级防不住 SMT 同物理核内的兄弟线程干扰，于是叠加 Linux core scheduling（`prctl(PR_SCHED_CORE)` 按 QoS class 分组，禁止不相关 BE 任务跑在 LS 任务的兄弟硬件线程上）[[2609.22978]]。

## 工程要点与数字

- 内存消融（Figure 12，4 种 Firecracker 配置对照）：virtio-pmem+DAX 单独把峰值 host 内存降 **40.2%**，但把瞬时峰值 CPU 利用率从 26.5% 拉到 **41.4%**（冷访问同步缺页所致）；DAMON+balloon FPR 单独不改变峰值但把**时间积分**内存消耗降 **21.2%**、无显著 CPU 开销；两者叠加内存消耗最低。作者建议 CPU 受限场景可以只开 FPR、保留 virtio-blk [[2609.22978]]。
- CPU QoS 消融（Figure 13，chess 延迟敏感任务 + 10%–50% BE 负载对照）：无保护基线在 50% BE 负载下每步延迟膨胀 **45.2%**；单独 `SCHED_IDLE` 只改善到 41.8%（改善幅度仅 3.4pp，因为 SMT 兄弟线程仍会争抢共享执行资源）；叠加 core scheduling 把膨胀压到 **17.3%**，且改善幅度随 BE 负载增大而增大 [[2609.22978]]。
- 残余干扰来源：turbo 频率因高负载多核而降频、LLC/内存带宽争用——作者认为这部分残余延迟已可接受，**没有**再上内存带宽隔离机制 [[2609.22978]]。
- 生产密度参照：稳定运行 3,200 容器 / 800 microVM 每节点（demonstrated operating point，非硬上限）[[2609.22978]]，详见 [[microvm-sandbox]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源；后续读 category F《资源超卖与调度》里的 ESX 内存管理、DAMON 原始论文、Linux core scheduling 文档、power-of-two-choices 论文后补充）

## 开放问题

- virtio-pmem 引入的 CPU 开销上升（26.5%→41.4%）在什么规模/负载下会反过来成为瓶颈，论文没有给出临界点分析。
- core scheduling 之外，内存带宽/LLC 隔离是否值得投入，DSec 判断"已可接受"但没有量化不同 BE 负载强度下 LLC 争用对 LS 任务的具体贡献占比。

## 相关概念

[[microvm-sandbox]]、[[sandbox-image-distribution]]、[[agentic-rollout-preemption]]

## 相关来源

- [[2609.22978]] — DSec：virtio-pmem+DAMON 内存优化、SCHED_IDLE+core scheduling CPU QoS 的设计与量化消融
