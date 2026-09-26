---
title: "Kata Containers"
aliases: [Kata, kata-runtime, containerd-shim-kata-v2, 安全容器运行时]
created: 2026-09-26
updated: 2026-09-26
sources: [kata-containers-architecture, 2022-li-rund, 2020-agache-firecracker]
---

# Kata Containers

## 一句话定义

开源的安全容器运行时项目：用 shimv2 兼容的 `containerd-shim-kata-v2` + guest kernel/image + Rust 写的 `kata-agent` 三段式架构，把"一个 microVM 里跑一个 pod/多个容器"的 [[microvm-sandbox]] 模型标准化并接入标准 OCI/Kubernetes CRI 生态，支持多种 hypervisor 后端（QEMU、Cloud Hypervisor、[[firecracker]]、Dragonball）[[kata-containers-architecture]]。

## 为什么对我们重要

Kata 是 dsec-refs 阅读清单 B 类"隔离运行时/microVM"里被 [[rund]]、[[firecracker]] 两篇笔记反复当作 baseline 引用、却一直没有被单独精读的一块底层拼图——[[2022-li-rund]] 的三种对比配置（Kata-qemu、Kata-template、Kata-FC）全部构建在 Kata 的通用架构上，差异只在 hypervisor 选择。理解 Kata 的架构分层，才能看懂 RunD 的三项优化具体改在哪一层、Firecracker 作为 hypervisor 接入 Kata 之后为什么会暴露出 VMM 之外的瓶颈。母论文 [[2609.22978]]（DSec）§9 把 Kata Containers 与 Firecracker 并列为"VM 支持"的安全容器路线之一。

## 核心机制 / 主要变体

- **Shimv2 架构**：单个 `containerd-shim-kata-v2` 进程管理任意数量的容器/pod，替代旧架构下每容器都要起一次 runtime 的 `2N+1` 模型；container manager 通过 gRPC-over-socket 驱动它，支持一个 pod 内多个容器共享同一个 VM [[kata-containers-architecture]]。
- **三层环境模型**：Host（物理机）→ Guest VM root（VM 内顶层环境，rootfs 由 hypervisor 通过 DAX 映射）→ VM container root（容器专属环境，rootfs 由用户指定，经 `virtio-fs` 挂载）。这是审视任何"VM 套容器"架构时定位隔离边界、rootfs 类型、mount 方式的通用坐标系 [[kata-containers-architecture]]。
- **Guest assets**：高度精简的 guest kernel（仅保留容器工作负载需要的服务）+ `osbuilder` 构建的 mini-OS guest image（rootfs 或 initrd 两种形态；initrd 下 agent 直接作 PID 1，跳过 systemd，启动更快）[[kata-containers-architecture]]。
- **Agent**（`kata-agent`，Rust，VM 内唯一长驻进程）：在 guest 内创建容器环境（namespace/cgroup 由 guest kernel 创建，语义等价 `runc`）、管理 workload 生命周期，通过 VSOCK 上的 ttRPC 协议与 host 侧 runtime 通信 [[kata-containers-architecture]]。
- **存储两条正交路径**：block-based（`virtio-scsi`/devicemapper，直接用块设备做可写层，I/O 更好、可热插拔）与 `virtio-fs`（文件级 overlay，host 侧每 VM 一个 `virtiofsd` daemon）在 Kata 架构里是并列的可配置项，不是互斥选择 [[kata-containers-architecture]]。[[rund]] 的评测显示这两条路径各自的短板正对应这一架构选择——virtio-fs 写性能差、每容器一个 daemon 高并发 CPU 贵；virtio-blk 靠 device-mapper 建块设备耗时随并发线性恶化 [[2022-li-rund]]。
- **DAX（Direct Access）**：QEMU 用 NVDIMM、Cloud Hypervisor 用 PMEM 模拟设备，把 guest image 直接映射进 guest 内存地址空间，绕开 guest 页缓存实现 zero-copy，并靠 `mmap(2)` 的 `MAP_SHARED` 支持多 VM 间共享同一份只读页 [[kata-containers-architecture]]——是 [[rund]] 中"内核自修改代码破坏 microVM template 内存共享假设"问题的架构背景：DAX/模板机制的省内存效果依赖只读段能跨 VM 共享物理页，RunD 发现 guest kernel 启动阶段的自修改代码会打破这个假设 [[2022-li-rund]]。
- **Policy 机制**：`kata-runtime policy set` 可为 guest 装 `policy.rego`，对 agent API 调用做细粒度访问控制（配套工具 `genpolicy`）[[kata-containers-architecture]]。

## 工程要点与数字

Kata 官方架构文档本身不含性能评测数字；已知的量化对比数字均来自使用 Kata 作 baseline 的外部评测：

- [[rund]] 的 baseline 对比：200 容器并发启动，Kata-FC/Kata-qemu/Kata-template 分别耗时 47.6s/6.85s/2.98s（RunD 本身 1s）；1,000 容器密度下 RunD 相比 Kata-qemu/Kata-template/Kata-FC 每容器内存开销分别低 87.7%/82.4%/75.1%（详见 [[rund]]）[[2022-li-rund]]。
- Kata-FC（Kata + Firecracker 作 hypervisor）在高并发场景下是四个 baseline 里最慢的，瓶颈定位在 rootfs 存储层（virtio-blk 建块设备耗时随并发线性恶化）而非 Firecracker 本身，说明"接入完整 Kata 软件栈"会让瓶颈从 VMM 层转移到 rootfs/cgroup 层 [[2022-li-rund]]。

## 争议与矛盾

暂无跨来源数字冲突。

## 开放问题

- Kata 支持的多个 hypervisor 后端（QEMU、Cloud Hypervisor、Firecracker、Dragonball）在架构实现上的具体差异，本页尚未覆盖，需要精读 `virtualization.md`/`hypervisors.md` 后补充。
- `policy.rego`/`genpolicy` 这个较新的 agent 访问控制机制的设计动机与实际效果，尚无独立评测数据。
- RunD 相对 Kata 默认架构的三项改动（rootfs 分层、guest kernel 精简+预 patch、cgroup 池化）具体是"替换 Kata 组件"还是"在 Kata 架构上新增旁路"，需要对照 Kata 源码结构进一步确认。

## 相关概念

[[microvm-sandbox]]、[[firecracker]]、[[rund]]

## 相关来源

- [[kata-containers-architecture]] — Kata Containers 官方架构设计文档：shimv2、三层环境模型、guest assets、agent/runtime 通信、存储两条路径、DAX 机制的出处
- [[2022-li-rund]] — 用 Kata-qemu/Kata-template/Kata-FC 三种配置做 baseline，实测拆解出 Kata 架构在高密度/高并发场景下的具体瓶颈
- [[2020-agache-firecracker]] — Kata 的 hypervisor 后端之一（Kata-FC 配置）
