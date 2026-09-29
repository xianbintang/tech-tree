---
title: "Kata Containers Architecture"
type: post
id: "kata-containers-architecture"
source_url: https://github.com/kata-containers/kata-containers/blob/main/docs/design/architecture/README.md
authors: [Kata Containers Community]
affiliations: [Kata Containers project (OpenInfra Foundation)]
published: "无固定发表日期（持续更新的项目架构文档，main 分支）"
created: 2026-09-26
tags: [sandbox, microvm, kata-containers, isolation, architecture]
concepts: [kata-containers, microvm-sandbox, firecracker, rund]
rating: 4
issue: 22
parent: "2609.22978"
---

# Kata Containers Architecture

> Kata 用 shimv2 运行时 + guest kernel/image + Rust agent 的三段式架构，把"一个 microVM 里跑 pod/多个容器"的安全容器模型标准化，是 [[rund]]、[[firecracker]] 相关评测里反复出现的 baseline 架构底座。

## 元信息

- 类型：项目官方架构设计文档（持续更新，非某个固定版本的快照）
- 机构：Kata Containers 社区（OpenInfra Foundation 托管）
- 链接：[架构文档](https://github.com/kata-containers/kata-containers/blob/main/docs/design/architecture/README.md) · [Code](https://github.com/kata-containers/kata-containers)
- 关联：作为 hypervisor 后端之一使用 [[firecracker]]（即 Kata-FC 配置）；[[rund]] 基于 kata-runtime 用 Rust 重写；母论文 [[2609.22978]] §9 把 Kata Containers 与 Firecracker 并列为"VM 支持"的安全容器路线。

## 要解决的问题

容器共享内核换来的启动速度/密度，与全虚拟化（QEMU/KVM）的强隔离边界，历史上被视为二选一。Kata 的定位是：**保留标准容器的使用体感（OCI 兼容、K8s CRI 兼容），但用虚拟化作为第二道防线**——即架构上兼容 [[microvm-sandbox]] 描述的"虚拟化级隔离"取舍，同时对上层完全暴露标准容器接口。这篇文档要解决的是"如何把 VM 和容器两层模型拼接起来又不破坏 OCI/K8s 兼容性"的架构问题，而不是某个具体性能指标。

## 方法（架构要点）

- **Shimv2 架构**：`containerd-shim-kata-v2` 单进程管理任意数量的容器/pod（替代旧架构下每个容器都要拉起一次 runtime 的 `2N+1` 模型），container manager 通过一个 Unix socket 上的 gRPC 协议驱动它。这让一个 pod 内的多个容器可以共享同一个 VM，而不必每个容器单独起一个 shim 进程。
- **三层环境模型**（Environments 表）：Host（物理机）→ Guest VM root（VM 内顶层环境，rootfs 挂载点由 hypervisor 决定，通过 DAX 映射）→ VM container root（容器专属环境，rootfs 类型用户指定，通过 `virtio-fs`/`kataShared` 挂载）。容器进程被再包一层容器化，理由是：把 workload 完全隔离出 VM 环境本身、pod 内多容器之间也需要隔离、workload 仍能用标准 cgroup 管理。这个三层表是理解任何"VM 套容器"架构的通用坐标系——[[microvm-sandbox]]、[[rund]] 里讨论的 rootfs/内存/cgroup 优化，都可以定位到这三层的某一层。
- **Guest assets**：guest kernel（针对容器场景高度精简，只保留必要服务，基于最新 LTS 内核）+ guest image（`osbuilder` 构建的 mini-OS，支持 rootfs 或 initrd 两种形态）。initrd 模式下 agent 直接作 PID 1（跳过 systemd），启动更快；rootfs 模式下 systemd 作 PID 1 再拉起 agent，灵活性更高但多一层。
- **Agent**（`kata-agent`，Rust 实现）：每个 VM 内唯一的长驻进程，负责在 guest 内创建容器环境（namespace/cgroup 由 guest kernel 创建，语义等价于 `runc`）、管理 workload 生命周期，通过 VSOCK 上的 ttRPC 协议与 host 侧 runtime 通信。
- **Runtime**（`containerd-shim-kata-v2`，重度依赖 `virtcontainers` 库）：负责拉起 hypervisor、通过 ttRPC/VSOCK 下发容器管理指令给 agent，并承载 stdout/stderr/stdin 的转发。
- **存储的两条正交路径**：block-based（`virtio-scsi` 或 devicemapper 块设备，直接映射块设备做可写层，I/O 性能更好、支持热插拔，用户可通过 `mount(8)` 看到 rootfs 挂在 `/dev/vda`）vs `virtio-fs`（文件级 overlay 挂载，host 侧每个 VM 起一个 `virtiofsd` daemon）。这两条路径在 Kata 架构文档里是**并列的可配置项**，不是谁取代谁——[[rund]] 论文里对比的"virtio-fs 写性能差 + 每容器一个 daemon 高并发 CPU 贵 vs virtio-blk 靠 device-mapper 建块设备耗时随并发线性恶化"，正是这两条 Kata 原生路径各自的已知短板；RunD 的贡献是把两者结合（只读层用 virtio-fs 共享 page cache，可写层换成专用的 volatile block device），而不是简单二选一。
- **DAX（Direct Access）**：QEMU 用 NVDIMM 模拟设备、Cloud Hypervisor 用 PMEM，把 guest image 直接映射进 guest 的内存地址空间，绕开 guest kernel 页缓存实现 zero-copy，并靠 `mmap(2)` 的 `MAP_SHARED` 支持 host 侧多 VM 间共享同一份只读页。这正是 [[rund]] 笔记里"内核自修改代码破坏 microVM template 内存共享假设"问题的架构背景：DAX/模板机制的省内存效果依赖"只读段真的能在多 VM 间共享物理页"，RunD 发现的坑是 guest kernel 启动阶段的自修改代码会把本该共享的只读页变成每 VM 私有页，从架构层面看，这是 DAX 假设与 guest kernel 实际行为之间的一个落差，不是 DAX 机制本身的缺陷。
- **Policy 机制**：`kata-runtime policy set` 可以给 guest 装一份 `policy.rego`，通过策略引擎控制 agent API 的哪些调用被允许——是对 agent 攻击面的一层细粒度访问控制，配套工具是 `genpolicy`。

## 实验与结果

本文档是架构设计说明，不含任何性能评测数字；量化对比（如 Kata-qemu/Kata-template/Kata-FC 的启动时间、内存开销）需要看 [[2022-li-rund]] 等外部评测论文，不能从本文档获得。

## 局限与疑点

- 本文档对应的是抓取时（2026-09-26）main 分支的当前状态，架构会随项目演进持续变化，没有版本号或日期锚点，未来引用时需要重新核对。
- 只讲了通用架构和默认配置（mini-OS/initrd/systemd/genpolicy 等），没有展开不同 hypervisor（QEMU/Cloud Hypervisor/Firecracker/Dragonball）之间的实现差异，需要另外精读 `virtualization.md`、`hypervisors.md`（本次未读）才能补全。
- 作为项目自己的架构文档，没有第三方视角的评估或已知问题清单；`policy.rego`/genpolicy 这类较新特性只给了命令行入口，没有说明其设计动机与局限。

## 对我们的启发

- **三层环境模型（Host / Guest VM root / Container）是审视任何"VM 套容器"沙箱架构的通用心智工具**：不管我们自己怎么实现隔离后端，都可以把隔离边界、rootfs 类型、mount 方式分别定位到这三层中的某一层，避免把"VM 级隔离"和"容器级隔离"这两条独立的安全边界混为一谈来讨论。
- **Shimv2 单进程管理多容器/pod**是"一个隔离单元内允许多个协作进程共享执行环境"的可复用接口范式：如果我们平台需要支持"一个 sandbox 内跑多个协作任务"，这提供了一个减少进程数、统一生命周期管理的参照设计，而不必为每个子任务单独起一个 runtime 实例。
- **存储两条路径（block-based vs virtio-fs）是并列的可配置项，不是互斥选择**：我们平台如果要同时支持"有状态"和"无状态"两类沙箱，可以借鉴这种"按场景选择 rootfs 后端"的架构，而不是为每种场景重新设计一套存储集成方案。[[rund]] 证明了这两条路径也可以在同一个 sandbox 内分层组合（只读走一条、可写走另一条）。
- **DAX 的内存共享假设需要结合 guest kernel 实际行为验证**：如果我们的沙箱模板/快照复用依赖类似的"只读段跨实例共享物理页"设计，需要像 RunD 一样实测 guest kernel 启动阶段有多少页被自修改覆写，否则模板带来的内存节省可能被高估——这条启发已经在 [[rund]] 笔记里写过，这里作为架构背景再确认一次。
- Follow-up 建议（可转 issue）：
  1. 精读 `virtualization.md`/`hypervisors.md`，把 Kata 支持的多 hypervisor（QEMU/Cloud Hypervisor/Firecracker/Dragonball）在架构图层面跟本篇的通用流程对齐，搞清楚哪些环节是 hypervisor-specific；
  2. 对照 [[rund]] 的三项优化，在 Kata 官方文档体系里找到对应的默认实现（`storage.md` 的两条 rootfs 路径、`guest-assets.md` 的 kernel/image 构建流程），确认 RunD 的改动相对 Kata 默认架构是"替换组件"还是"新增旁路"；
  3. 评估 `genpolicy`/`policy.rego` 机制能否借用到我们自己沙箱 agent 的权限模型——这是 Kata 对 agent API 做细粒度访问控制的较新特性，值得单独调研。

## 相关

- 相关概念：[[kata-containers]]、[[microvm-sandbox]]、[[firecracker]]、[[rund]]
- 相关笔记：[[2020-agache-firecracker]]（Kata-FC 配置用 Firecracker 作 hypervisor）、[[2022-li-rund]]（三种 Kata baseline 配置全部构建在本文档描述的 shimv2+agent+runtime 架构上）
- 与母论文的关系：DSec（[[2609.22978]]）§9 在讨论安全容器路线时把 Kata Containers 与 Firecracker 并列提及（具体措辞待 `notes/papers/2609.22978.md` 建立后交叉核对，本篇未见到该笔记）。本文档本身不是 DSec 直接引用的文献，而是理解 dsec-refs 清单里 RunD、Firecracker 笔记反复提到"Kata baseline"时所依赖的基础架构说明——[[2022-li-rund]] 的三种 baseline 配置（Kata-qemu、Kata-template、Kata-FC）差异只在 hypervisor 选择，全部共享本文档描述的 shimv2 + guest assets + agent 三段式架构。阅读清单把它安排在 B 类"隔离运行时/microVM"里，作为 RunD 的前置背景阅读。
