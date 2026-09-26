---
title: "Firecracker"
aliases: [Firecracker VMM, AWS Firecracker, crosvm 衍生 VMM]
created: 2026-09-26
updated: 2026-09-26
sources: [2020-agache-firecracker, 2022-li-rund, kata-containers-architecture, 2020-anjali-firecracker-gvisor]
---

# Firecracker

## 一句话定义

AWS 开源的极简 KVM VMM（Rust 实现，源自 crosvm），专为 serverless/容器工作负载设计，用虚拟化级别的隔离边界换取接近容器的启动速度与密度，是 AWS Lambda/Fargate 的隔离底座 [[2020-agache-firecracker]]。

## 为什么对我们重要

Firecracker 是"隔离运行时/microVM"这条技术路线里被引用最多的锚点系统——本知识库的 dsec-refs 阅读清单里，RunD、Kata Containers、PVM、gVisor 对比研究等都直接以它为参照基线。它给出的六条隔离方案选型标准（Isolation / Overhead and Density / Performance / Compatibility / Fast Switching / Soft Allocation）以及"重写极简 VMM 而非裁剪 [[qemu|QEMU]]"的设计决策，是我们评估自己沙箱平台隔离底座时的直接参照系 [[2020-agache-firecracker]]。母论文 [[2609.22978]]（DSec）就把 Firecracker microVM 列为其四种沙箱后端之一。

## 核心机制 / 主要变体

- **架构**：一个 Firecracker 进程管理一个 MicroVM，只实现网络/块设备（virtio）、串口、部分 i8042；不提供 BIOS、PCI、任意内核启动、VM 迁移；代码量约 5 万行 Rust（QEMU 的 4%）[[2020-agache-firecracker]]。
- **Jailer**：在 Firecracker 进程外再包一层 chroot + pid/net namespace + seccomp-bpf（白名单 24 syscall/30 ioctl）+ 降权，作为 VMM 本身被攻破时的第二道防线 [[2020-agache-firecracker]]。
- **REST API**：通过 Unix socket 配置/启停 MicroVM，支持先配置后启动以降低感知延迟 [[2020-agache-firecracker]]。
- **存储集成限制**：不支持 virtio-fs，只能走块设备透传；DSec 因此为 Firecracker 后端设计了 OverlayBD 格式镜像 + ublk 用户态块设备 + 分布式文件系统（3FS）按需加载的组合方案 [[2020-agache-firecracker]]（转引自 DSec §3.3）。

## 工程要点与数字

- 内存开销约 **3MB/VM**（常数，与 VM 配置大小无关），对比 QEMU 约 131MB、Cloud Hypervisor 约 13MB [[2020-agache-firecracker]]（NSDI'20 评测，2019–2020 年硬件/内核基线）。
- 生产内核配置下端到端启动时间可到 **150ms**；1000 VM 以 50 并发批量启动，99 分位 146ms [[2020-agache-firecracker]]。
- 生产环境验证过 CPU/内存超卖比 **10x**，测试验证到 20x 无问题 [[2020-agache-firecracker]]。
- 4KB 随机读 IOPS 被限制在约 1.3 万（物理机可达 34 万），当时（v0.20.0）块设备写路径不支持 flush-to-disk [[2020-agache-firecracker]]。
- 2018 年起在 AWS Lambda/Fargate 生产环境跑，服务数百万工作负载、每月万亿级请求 [[2020-agache-firecracker]]。
- 独立第三方内核代码覆盖率测量（非 AWS 自评）：seccomp 白名单 36 个系统调用（宿主内核共 350 个入口，比 [[gvisor]] 的 53/68 个更紧）；宿主内核代码覆盖 77,392 行（9.59%），四个对比平台（原生 Linux/LXC/gVisor/Firecracker）里除原生 Linux 外**最低**；初始化后完全不再对宿主发起 mmap 调用，内存栈完全在 guest 内闭环 [[2020-anjali-firecracker-gvisor]]。
- 网络 RTT 延迟 371μs，是原生 Linux（146μs）、LXC（149μs）、gVisor（319μs）四者中**最高**——因为一个包要穿两层内核网络栈（guest + host）；反过来写吞吐是四者中最快（500-1020 MB/s），但代价是不做落盘持久化保证，与 [[2020-agache-firecracker]] 里"写路径不支持 flush-to-disk"的局限是同一取舍的两次独立验证 [[2020-anjali-firecracker-gvisor]]。

## 争议与矛盾

- **两处"白名单系统调用数量"的说法不完全一致，但统计口径不同、不构成真正矛盾**：[[2020-agache-firecracker]]（Firecracker 原始论文）描述 Jailer 组件白名单 24 个 syscall/30 个 ioctl；独立第三方研究 [[2020-anjali-firecracker-gvisor]] 测得 Firecracker 自身的 seccomp 白名单是 36 个 syscall。前者是 Jailer 在 Firecracker 进程外再包一层的收紧范围，后者是 Firecracker 内建 seccomp 过滤器允许的调用总数，两者统计的是不同层，都可信，只是不能直接相加或替换比较。
- **Firecracker 作为 hypervisor 不足以撑起安全容器的高密度/高并发目标**：[[rund]] 用 Kata-FC（[[kata-containers]] + Firecracker 作 hypervisor）做对比基线，测得 200 容器并发启动需要 47.6 秒——是四个 baseline 里最慢的一个（Kata-qemu 6.85s、Kata-template 2.98s），原因是 Kata-FC 用 virtio-blk 处理 rootfs，在高并发下 device-mapper 建块设备的耗时随并发数线性恶化，这个瓶颈发生在 Firecracker 之外的 rootfs 存储层，Firecracker 本身的启动速度优势没有被发挥出来 [[2022-li-rund]]。这说明 Firecracker 论文自身的 150ms/3MB 数字衡量的是纯 VMM 层，接入完整安全容器软件栈（rootfs、guest kernel、host cgroup）后瓶颈会转移到其它层。

## 开放问题

- 上述性能/密度数字是 2020 年论文发表时的基线，六年后（本知识库清单中的《Seven Years of Firecracker》博文）实际数字是否有大幅变化，尚待精读确认。
- virtio-fs 不支持这一限制在后续版本是否已解决，需要跟进 Firecracker 项目现状。
- Kata-FC 在 RunD 评测中的并发劣势主要来自 rootfs 存储层而非 Firecracker 本身，若把 RunD 的 rootfs 读写分层方案接到 Firecracker 后端（而非 Kata 默认的 virtio-blk），并发数字是否能追平甚至超过 Kata-template，未见后续研究验证。

## 相关概念

[[microvm-sandbox]]、[[rund]]、[[kata-containers]]、[[gvisor]]、[[lightvm]]

## 相关来源

- [[2020-agache-firecracker]] — Firecracker 原始设计论文（NSDI'20），六项选型标准、Jailer 设计、生产评测数字的出处
- [[2022-li-rund]] — 用 Kata-FC（Firecracker 作 hypervisor）做对比基线，揭示接入完整安全容器软件栈后 Firecracker 单层优化的局限
- [[kata-containers-architecture]] — Kata Containers 架构文档，说明 Firecracker 作为 hypervisor 后端接入 Kata（Kata-FC 配置）时所在的通用架构位置
- [[2020-anjali-firecracker-gvisor]] — 独立第三方内核代码覆盖率与微基准对比研究，给出 Firecracker 相对 gVisor/LXC 的量化数字（syscall 白名单、内核代码覆盖率、网络延迟、文件吞吐）
