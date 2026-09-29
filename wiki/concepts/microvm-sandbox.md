---
title: "microVM 沙箱隔离"
aliases: [microVM, microVM isolation, 轻量虚拟机隔离, Firecracker microVM]
created: 2026-09-26
updated: 2026-09-26
sources: [2609.22978]
---

# microVM 沙箱隔离

## 一句话定义

介于容器（共享内核，隔离弱、启动快）和完整 VM（独立内核+完整 OS、隔离强、开销大）之间的轻量虚拟化隔离方案，典型代表是 Firecracker：保留 Linux 兼容性的同时提供接近 VM 级的隔离边界，代价是比容器更高的内存开销和更慢的启动。

## 为什么对我们重要

我们平台需要在"隔离强度"和"密度/成本"之间做选型：安全敏感任务（如漏洞利用类 agent 任务）不能用共享内核的容器，但完整 VM 又太重、密度撑不住 agentic RL 的规模。microVM 是目前工业界（AWS Lambda、DeepSeek DSec）验证过的中间解，直接决定我们沙箱底座的选型空间。

## 核心机制 / 主要变体

- **隔离位置**：microVM 提供独立内核和虚拟化边界，而容器共享 host 内核——这是它相对容器的核心区别，也是它能承接安全敏感任务的原因 [[2609.22978]]。
- **DSec 的四后端对比（Table 1）**：FnCall（无状态短任务，隔离最弱、性能最好）< 容器（SWE/工具调用主力，快启动高密度但共享内核）< microVM（安全敏感/强隔离，Linux 兼容，内存开销更高、启动更慢）< full VM/QEMU（完整 COTS OS，如 Android VM、GUI/图形渲染，开销最大）[[2609.22978]]。
- **生产运行方式**：DSec 的 FnCall 和容器实际上并不是直接跑在裸机上，而是先跑在 QEMU/libvirt VM 里，再在里面跑容器/FnCall——多一层安全边界，把"容器"和"microVM/fullVM"两条隔离路线在物理机层面统一起来 [[2609.22978]]。
- **microVM 专属存储路径**：由于 Firecracker 不支持 virtio-fs，DSec 用 OverlayBD（块级、经 ublk 用户态框架挂载）而非容器路线的 EROFS/overlayfs 组合来做 microVM 的可写盘和按需加载，说明 microVM 后端在文件系统兼容性上比容器更受限 [[2609.22978]]（细节见 [[sandbox-image-distribution]]）。

## 工程要点与数字

- DSec 生产单机密度：稳定运行观测到最高 3,200 容器 / 800 microVM 同节点并发，作者明确标注为"demonstrated operating points"而非硬上限 [[2609.22978]]。
- 一天采样的单机峰值：1,048 容器 vs. 524 microVM 同时在线，容器密度显著高于 microVM，符合"microVM 隔离更强但资源开销更高"的预期 [[2609.22978]]。
- 沙箱生存期中位数：容器 17.4 分钟 vs. microVM 15.5 分钟，p99 均超 3 小时——两种后端在长尾长生命周期上表现相近 [[2609.22978]]。
- microVM 内存浪费的两个具体来源：(1) 镜像数据经虚拟块设备读取，host 和 guest 各缓存一份，造成跨边界重复缓存；(2) guest 内空闲页若无显式上报机制不会自动还给 host。这两点是高密度超卖时 microVM 比容器更吃亏的直接原因，解决机制见 [[sandbox-density-overcommit]] [[2609.22978]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源；后续读 Firecracker 原始论文、RunD、Kata Containers 后补充）

## 开放问题

- DSec 论文没有解释 3,200 容器/800 microVM 这两个密度上限背后的具体限制因素（内存？调度开销？网络？），也没有给出继续往上推的实验数据。
- Firecracker 与 gVisor、Kata Containers 等其它 microVM/VM-backed 容器方案的直接性能对比（P3 引用 [[2609.22978]] 但未展开），留给后续读 category B 论文时补充。

## 相关概念

[[sandbox-image-distribution]]、[[sandbox-density-overcommit]]、[[agentic-rollout-preemption]]

## 相关来源

- [[2609.22978]] — DSec：生产级多后端沙箱平台，给出 microVM vs. 容器 vs. full VM 的取舍与生产密度数字
