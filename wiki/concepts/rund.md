---
title: "RunD"
aliases: [RunD runtime, 阿里安全容器运行时, lightweight secure container runtime]
created: 2026-09-26
updated: 2026-09-26
sources: [2022-li-rund, kata-containers-architecture]
---

# RunD

## 一句话定义

阿里巴巴基于 Kata-runtime 用 Rust 重写的安全容器运行时，用「rootfs 读写分层 + guest kernel 精简/预 patch + host 侧轻量 cgroup 池」三项贯穿 guest-to-host 全栈的优化，解决 [[microvm-sandbox]] 路线下安全容器的高密度部署与高并发启动瓶颈，生产验证支持单节点 2,500+ 容器部署、200 容器/秒并发启动 [[2022-li-rund]]。

## 为什么对我们重要

RunD 是 dsec-refs 阅读清单 B 类（隔离运行时/microVM）里被母论文 [[2609.22978]]（DSec）§9 直接点名、且"最贴近我们密度/冷启动目标"的一篇。它的核心价值不在于提出新的隔离机制（隔离边界仍然是 [[microvm-sandbox]] 的虚拟化级边界），而在于系统性拆解了"安全容器"这个复合系统（VMM + guest kernel + container runtime + host cgroup）在高密度、高并发场景下真正的瓶颈分布，给出了一套可复用的诊断方法和三个正交的具体优化。这直接对应我们评估自己沙箱平台"密度天花板在哪、并发启动卡在哪一层"时应该采用的分析框架。

## 核心机制 / 主要变体

- **诊断方法**：不满足于"microVM 隔离有开销"这个笼统结论，而是用 [[kata-containers]] 作为代表系统（架构见 [[kata-containers-architecture]]），实测拆出四个具体瓶颈——rootfs 创建（并发瓶颈）、cgroup 创建（并发瓶颈）、microVM 内存footprint（密度瓶颈）、cgroup 调度扫描开销（密度瓶颈），§3 逐一定位、§4 逐一给方案，这个"先拆解复合系统各层开销、再针对性优化"的方法本身比具体数字更值得复用 [[2022-li-rund]]。
- **rootfs 读写分层**：只读层用 virtio-fs（可共享 page cache，overlay snapshotter 准备几乎零耗时），可写层用**volatile block device**（reflink CoW 克隆 storage image template，open-but-unlink 保证不落盘持久化），解决了"virtio-fs 写性能差 + 每容器一个 daemon 高并发 CPU 贵"与"virtio-blk 靠 device-mapper 建块设备在高并发下耗时随并发数线性恶化"这两个互斥的问题 [[2022-li-rund]]。
- **内核自修改代码是 microVM template 内存共享的隐藏杀手**：template 依赖 mmap 共享只读段来省内存，但 guest kernel 启动阶段的自修改代码会把本该共享的只读页变成每 VM 私有页（实测 10,012KB 只读段里 7,928KB 被自修改覆写）；RunD 用**预先跑过一遍自修改阶段的 pre-patched kernel image**恢复共享有效性 [[2022-li-rund]]。
- **cgroup 池 + rename 替代创建**：Linux 内核用多个全局互斥锁（cgroup_mutex 等）串行化 cgroup 操作，高并发创建反而因为乐观自旋锁放大 CPU 消耗；RunD 用 joint controller 把多个子系统聚合成一个 lightweight cgroup，并预建 cgroup 池，创建容器时只做**不需要抢全局锁的 rename 操作**而非重新创建，是"高频创建/回收资源、用改名替代创建来绕过锁瓶颈"的通用模式 [[2022-li-rund]]。

## 工程要点与数字

- 并发启动 200 容器：RunD 1s，对比 Kata-template 2.98s、Kata-qemu 6.85s、Kata-FC 47.6s；单容器冷启动 88ms [[2022-li-rund]]。
- 密度：384GB 内存节点部署 2,500+ 个 128MB 规格容器（理论上限约 2,656）；1,000 容器部署时每容器内存开销比 Kata-qemu/Kata-template/Kata-FC 分别低 87.7%/82.4%/75.1% [[2022-li-rund]]。
- cgroup 优化效果：创建耗时降到 0.09–0.14s（1–200 线程），减少 94% 的 cgroup 创建时间 [[2022-li-rund]]。
- rootfs 优化效果：200 并发下 IOPS 4,500→1,500、准备耗时 207ms→0.2ms [[2022-li-rund]]。
- 生产规模：阿里 serverless 平台服务超百万函数、日均近 40 亿次调用，线上单节点峰值并发启动 191 个 sandbox（1.6s 完成）、密度峰值超 2,000 [[2022-li-rund]]。

## 争议与矛盾

暂无跨来源数字冲突。但存在一个**适用场景边界的分歧**，值得记录：母论文 DSec（[[2609.22978]] §9）明确指出 RunD 这类系统的密度/并发优化建立在"短生命周期、无状态、镜像集中且高复用"的假设上，而 DSec 自己的目标场景（长生命周期、有状态的 agent 训练沙箱，镜像库超单机存储且低复用）不满足这个假设——即 RunD 的具体方案（尤其是 volatile block device 的"不持久化"设计）不能直接迁移到有状态场景，但其诊断方法与 cgroup 池化思路是场景无关的、可迁移的 [[2022-li-rund]]。

## 开放问题

- RunD 用的是 Linux 4.19.91，cgroup 全局锁瓶颈的发现是否在 cgroup v2（锁设计有变化）下依然成立，尚待验证。
- 三项优化（rootfs 分层、内核精简+预 patch、cgroup 池化）没有独立 ablation，各自对整体密度/并发数字的贡献占比不明确。
- RunD 的方法能否迁移到有状态场景：如果放宽"可写层不持久化"这一假设，volatile block device 的设计需要如何改造，改造后的性能优势是否还保留，未在本文讨论范围内。

## 相关概念

[[microvm-sandbox]]、[[firecracker]]、[[kata-containers]]

## 相关来源

- [[2022-li-rund]] — RunD 原始设计论文（USENIX ATC'22），三项优化与生产评测数字的出处
- [[kata-containers-architecture]] — Kata Containers 架构文档，RunD 三种 baseline 配置（Kata-qemu/Kata-template/Kata-FC）共同依赖的基础架构说明
