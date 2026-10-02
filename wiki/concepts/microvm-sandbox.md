---
title: "MicroVM 沙箱"
aliases: [microVM, Firecracker sandbox, VM-level agent isolation, 轻量虚拟机, micro virtual machine, microVM isolation, 轻量虚拟机隔离, Firecracker microVM]
created: 2026-09-26
updated: 2026-09-27
sources: [2609.19969, 2609.22978, 2020-agache-firecracker, 2022-li-rund, kata-containers-architecture, 2023-huang-pvm, 2020-anjali-firecracker-gvisor, 2017-manco-lightvm, 2005-bellard-qemu, 2026-gensee-agentenv-microvm-fork]
---

# MicroVM 沙箱

## 一句话定义

介于"共享内核的 Linux 容器"和"通用虚拟机（[[qemu|QEMU/KVM]] 全功能）"之间的隔离方案：用极简 VMM 只暴露虚拟化必需的最小设备集，在保留虚拟化级别安全边界的同时逼近容器的启动速度和密度，代表实现是 [[firecracker]] [[2020-agache-firecracker]]。生产落地时通常以"安全容器"（secure container：microVM 里跑一个容器运行时，如 Kata + Firecracker/QEMU）形态出现，[[rund]] 进一步表明这种复合系统的密度/并发瓶颈会分散在 VMM 之外的 guest kernel、host cgroup、rootfs 存储等多个层 [[2022-li-rund]]。相比容器，microVM 提供更强的隔离边界，代价是暂停/恢复需要保存和恢复完整的内存与执行状态快照，而非单纯冻结/唤醒进程树 [[2609.22978]]。

## 为什么对我们重要

这是 dsec-refs 阅读清单 B 类"隔离运行时/microVM"的核心概念，直接对应我们研究方向里"沙箱与执行环境基础设施：microVM、容器运行时、隔离"这一核心能力项。生产级 agent RL 平台（DSec）把 microVM 作为四种沙箱后端之一（与 FnCall、容器、full-VM 并列），用于"安全敏感任务、更强租户隔离"的场景，说明"单一沙箱抽象无法覆盖所有 agent workload"是已验证的工程结论，而非理论上的权衡讨论 [[2609.22978]]。DeepSeek-V4.1 训练进一步证明这条路线能扩展到生产规模：该训练在 DSec 上实际跑到百万级并发 agent rollout（涵盖 microVM 等多种沙箱后端）[[2609.19969]]。后续精读的 RunD、Kata Containers、PVM、LightVM、gVisor 对比研究都是在这条隔离-性能权衡谱系上的不同取舍点，本页会随着这些笔记持续补充。

## 核心机制 / 主要变体

- **DSec 的四后端谱系（Table 1）**：FnCall（无状态短任务，隔离最弱、性能最好）< 容器（SWE/工具调用主力，快启动高密度但共享内核）< microVM（安全敏感/强隔离，Linux 兼容，内存开销更高、启动更慢）< full VM/QEMU（完整 COTS OS，如 Android VM、GUI/图形渲染，开销最大）[[2609.22978]]。DeepSeek-V4.1 训练规模化使用了这套多后端沙箱平台支撑百万级并发 agent [[2609.19969]]。
- **DSec 的生产部署方式**：FnCall 和容器并不直接跑在裸机上，而是先跑在 QEMU/libvirt VM 里、再在里面跑容器/FnCall——多一层安全边界，把"容器"和"microVM/fullVM"两条隔离路线在物理机层面统一起来 [[2609.22978]]。
- **microVM 的暂停/恢复**：暂停时把 microVM 的内存和执行状态保存为快照，再终止运行中的 Firecracker 进程以释放该 microVM 的运行时内存；恢复时启动一个新进程并从快照恢复以继续 guest 执行 [[2609.19969]] [[2609.22978]]。这与容器的暂停/恢复（`docker pause` + `memory.reclaim` / `MADV_WILLNEED` + `docker unpause`）机制不同：容器是冻结/唤醒进程树，microVM 是完整的状态快照/恢复，代价更高但隔离边界更强 [[2609.22978]]。
- **microVM 专属存储路径**：Firecracker 不支持 virtio-fs，DSec 用 OverlayBD（块级、经 ublk 用户态框架挂载）而非容器路线的 EROFS/overlayfs 组合来做 microVM 的可写盘和按需加载，说明 microVM 后端在文件系统兼容性上比容器更受限（细节见 [[sandbox-image-distribution]]）[[2609.22978]]。
- **容器 vs 虚拟化的根本取舍**：容器共享宿主内核，靠 cgroups/namespaces/seccomp-bpf 隔离，安全边界依赖 syscall 面收窄（与兼容性直接冲突）；虚拟化把安全边界移到硬件辅助的 VMM 层，guest 内核可以有完整功能而不改变威胁模型，但传统 VMM（QEMU）复杂度高、启动慢、内存开销大 [[2020-agache-firecracker]]。
- **MicroVM 的解法**：不是在容器上加固，也不是裁剪 QEMU，而是为专用场景（serverless/容器工作负载）重新实现一个只做"必要子集"的极简 VMM——去掉 BIOS、任意内核启动、PCI、VM 迁移等通用虚拟化功能，只保留 virtio 网络/块设备和最基本的设备模型 [[2020-agache-firecracker]]。
- **六条选型标准**（源自 Firecracker 论文 §2，可作为评估任意隔离方案的通用框架）：Isolation（安全边界强度）、Overhead and Density（单机可承载密度）、Performance（相对裸机的性能损耗）、Compatibility（对未修改二进制的兼容性）、Fast Switching（创建/回收速度）、Soft Allocation（资源超卖能力）[[2020-agache-firecracker]]。
- **多层防御**：即便 microVM 本身提供强隔离边界，仍可在 VMM 进程外再包一层最小权限沙箱（Firecracker 的 Jailer：chroot + namespace + seccomp-bpf + 降权），防止 VMM 自身被攻破后波及宿主 [[2020-agache-firecracker]]。
- **"安全容器"的标准实现是 [[kata-containers]]**：shimv2 兼容运行时 + guest kernel/image + Rust agent 三段式架构，把"一个 microVM 跑一个 pod/多个容器"接入标准 OCI/K8s CRI 生态，支持 QEMU/Cloud Hypervisor/Firecracker/Dragonball 等多种 hypervisor 后端；[[rund]]、Kata-FC 等评测里的 baseline 配置都构建在这套架构上 [[kata-containers-architecture]]。
- **安全容器的瓶颈不止 VMM 一层**：[[rund]] 的实测拆解表明，"安全容器"（Kata + microVM）在高密度/高并发场景下的瓶颈分散在 rootfs 创建（virtio-fs 写性能差 vs virtio-blk 建块设备耗时随并发线性恶化）、guest kernel 内存占用（且自修改代码会破坏 microVM template 依赖的只读段共享假设）、host 侧 cgroup 创建（内核全局锁串行化）三处，只优化 VMM 本身（如换用更轻的 Firecracker）不足以解决高密度/高并发问题 [[2022-li-rund]]。
- **[[gvisor]] 是容器与 microVM 之间的第三条路线（paravirtualization）**：不跑完整 guest 内核，而是用用户态 *Sentry* 进程拦截并重新实现容器发出的绝大多数系统调用；用独立第三方内核代码覆盖率测量看，gVisor 的宿主内核代码覆盖率（91,161 行）反而是原生 Linux/LXC/Firecracker 四者里最高的一个，说明"把功能挪到用户态"并不等价于"减少了对宿主内核的依赖"——这是评估任何隔离方案时不能只看架构图、必须实测的一个反直觉例子 [[2020-anjali-firecracker-gvisor]]。
- **[[lightvm]] 是这条谱系更早、路线不同的前身**：2017 年就论证了"VM 隔离与容器级性能不是互斥取舍"这一核心命题,但走的是"Xen + unikernel/Tinyx 定制镜像 + 重写控制面（消除集中式 XenStore）"路线,而非"KVM + 精简 VMM、保留通用 guest 镜像"（[[firecracker]] 一脉）;两者共享同一论点但技术路径、时代硬件、评测场景都不可直接比较（LightVM 2.3ms/8000VM 是 unikernel 极限压测,Firecracker 150ms/10x 超卖是通用 Lambda 函数场景）,DSec 本身选择了后一条路线,可能是因为 agent 训练沙箱需要跑相对通用的 Linux 环境,unikernel 式"每应用定制镜像"的工程成本过高 [[2017-manco-lightvm]]。
- **[[nested-virtualization|嵌套虚拟化]]是第三种取舍点，解决的是"host 没有 hypervisor 控制权"这个约束**：microVM（Firecracker）通常要求宿主开放 `/dev/kvm` 或 root 权限；当沙箱需要跑在租来的公有云 VM 里（而非自己控制的裸机）时，[[pvm]] 这类不依赖硬件虚拟化支持、对宿主 hypervisor 透明的软件嵌套虚拟化方案是候选出路，已在阿里云生产环境日均承载 10万+ 安全容器 [[2023-huang-pvm]]。但代价是嵌套虚拟化天然多一层地址转换，即便像 PVM 那样优化到"单次 world switch 成本降低一个数量级"，仍无法完全消除；DSec 自己的评测选择"排除嵌套虚拟化，microVM 直接跑裸机"，说明这条路线的适用前提是"没有 host 控制权"，而不是普适的隔离方案 [[2023-huang-pvm]]。
- **agent 建环境即 microVM/容器通用**：DSec 支持 `pack_diff`——agent 可以在任意时刻对一个沙箱做增量磁盘快照，之后可作为新沙箱恢复，把交互式会话直接变成可复用环境，不需要独立的镜像构建流水线 [[2609.22978]]。
- **microVM fork 的进程数无关性与脏内存代价是一体两面**：第三方对 AgentENV（Kimi K3 的 Firecracker 沙箱层）的拆解证实了本页第一条机制（guest 进程树编码在 guest 内核内存里、host 不需要单独序列化）的另一面影响——fork 延迟几乎不随 guest 进程数增长，但 AgentENV 当前实现会在 fork 端点返回前把源 VM 的脏内存同步拷贝进新的不可变层，这部分 capture 代价随脏内存量线性增长（实测 1GiB guest 0→512MiB 脏内存：360ms→642ms）。这与基于 CRIU 重建进程树的容器 fork（如 TClone）正好是相反的取舍：后者子实例可以更快可用，但延迟随进程数增长。详见 [[microvm-fork-memory-cost]] [[2026-gensee-agentenv-microvm-fork]]。

## 工程要点与数字

- Firecracker 实现：内存开销约 3MB/VM，端到端冷启动可到 150ms，生产超卖比 10x（详见 [[firecracker]]）[[2020-agache-firecracker]]。
- 预启动池容量可用 Little's law 反推：池大小 = 创建速率 × 单次创建延迟（Firecracker 案例：150ms 创建延迟对应约每 8 次/秒创建配 1 个预启动 MicroVM）[[2020-agache-firecracker]]。
- 存储集成是 microVM 路线的一个共性工程难点：不支持 virtio-fs 时需要块设备层面的按需加载方案（如 DSec 的 OverlayBD + ublk + 3FS 组合，DSec §3.3）[[2609.22978]]。
- DSec 生产单机密度：稳定运行观测到最高 3,200 容器 / 800 microVM 同节点并发，作者标注为"demonstrated operating points"而非硬上限；一天采样的单机峰值 1,048 容器 vs. 524 microVM 同时在线 [[2609.22978]]。DeepSeek-V4.1 训练场景下，sub-NUMA 分区优化把单物理节点支持的并发存活容器数从约 1,000 提升到 2,500+，详见 [[sandbox-density-overcommit]]（两组数字口径不同，不能直接比较）[[2609.19969]]。
- DSec 沙箱生存期中位数：容器 17.4 分钟 vs. microVM 15.5 分钟，p99 均超 3 小时——两种后端长尾生命周期相近，与 Lambda 式短函数假设明显不同 [[2609.22978]]。
- microVM 高密度下比容器更吃内存的两个来源：(1) 镜像数据经虚拟块设备读取，host 和 guest 各缓存一份；(2) guest 空闲页若无显式上报不会还给 host。解决机制见 [[sandbox-density-overcommit]] [[2609.22978]]。
- [[rund]] 的密度/并发数字：单节点部署 2,500+ 个 128MB 规格安全容器，200 容器/秒并发启动，相比 Kata-qemu/Kata-template/Kata-FC 在 1,000 容器密度下每容器内存开销低 87.7%/82.4%/75.1%（阿里生产验证，日均近 40 亿次调用）[[2022-li-rund]]。
- 高频创建/回收资源绕过内核全局锁的通用模式：cgroup 池化 + rename 替代创建，使 cgroup 创建耗时减少 94%（不限于 microVM 场景，任何受内核锁串行化的资源池都可参考）[[2022-li-rund]]。

## 争议与矛盾

- **RunD 优化方案的适用边界受 DSec 明确质疑**：DSec（[[2609.22978]] §9）指出 RunD 这类"高密度安全容器"系统的优化建立在"短生命周期、无状态、镜像集中且高复用"的假设上（典型如 Lambda 场景）；DSec 自身面向的 agent 训练沙箱是长生命周期、有状态、镜像库超单机存储且低复用，RunD 的 volatile block device（可写层不持久化）等具体设计不能直接迁移，但其"贯穿全栈定位瓶颈"的诊断方法与 cgroup 池化思路被认为是场景无关、可迁移的 [[2022-li-rund]]。

## 开放问题

- 容器级密度/超卖数字（本页 10x-20x 及 RunD 的 2,500+/节点）来自 Lambda/阿里 serverless 场景（小内存函数、短生命周期），是否适用于 agent 训练场景的沙箱（可能资源占用模式差异很大，尤其是有状态、长生命周期的假设不成立），尚待更贴近训练场景的论文验证。
- microVM 与 [[nested-virtualization|嵌套虚拟化]]（[[pvm]]）在同等密度目标下的性能差距：PVM 论文只报告了自己相对硬件辅助嵌套虚拟化的提升（World switch 成本降低约 7x，高并发下最多两个数量级），没有与 microVM/Kata 路线做同一评测环境下的直接对比，这个跨路线的量化差距仍是开放问题。microVM（Firecracker）与 [[gvisor]] 之间已有独立第三方对比 [[2020-anjali-firecracker-gvisor]]：两者各有短板（Firecracker 网络延迟差但吞吐/内存/CPU 接近原生，gVisor 网络带宽差但延迟略优于 Firecracker），没有一个在所有维度全面占优，具体选型需按工作负载类型（网络密集 vs 文件/内存密集）判断。
- RunD 的 cgroup 全局锁瓶颈发现基于 Linux 4.19.91（cgroup v1 语义），在 cgroup v2 下是否依然成立尚未验证。
- DSec 没有解释 3,200 容器 / 800 microVM 两个密度上限背后的限制因素（内存？调度开销？网络？），也没有给出继续往上推的实验数据 [[2609.22978]]。
- 我们自己的沙箱平台是否存在"需要在无 host 权限的租用 VM 里提供强隔离"的实际场景，若存在，[[pvm]] 是目前记录到的唯一候选方案，但尚未找到其开源实现。
- 什么类型的 agent 任务被路由到 microVM 而非容器，路由决策的具体标准未展开。

## 相关概念

[[firecracker]]、[[rund]]、[[kata-containers]]、[[nested-virtualization]]、[[pvm]]、[[gvisor]]、[[lightvm]]、[[unikernel]]、[[qemu]]、[[sandbox-image-distribution]]、[[sandbox-density-overcommit]]、[[agentic-rollout-preemption]]、[[microvm-fork-memory-cost]]

## 相关来源

- [[2609.19969]] — 提及 DSec 支持 microVM 后端，并描述 DeepSeek-V4.1 训练如何使用该沙箱平台跑百万级并发 agent
- [[2609.22978]] — DSec（母论文）：生产级多后端沙箱平台，给出 microVM vs. 容器 vs. full VM 的取舍与生产密度、生存期数字
- [[2005-bellard-qemu]] — QEMU 原始设计论文，是本页"通用虚拟机"一端的技术源头，也是母论文 DSec 第四种沙箱后端（full-VM，用于 Android VM/GUI 场景）的直接引用出处，详见 [[qemu]]
- [[2017-manco-lightvm]] — 更早（2017）、路线不同（Xen + unikernel/控制面重写）的"VM 隔离与容器级性能不互斥"经典论证,是本页整条谱系的前身参照
- [[2020-agache-firecracker]] — 提出 microVM 六条选型标准与极简 VMM 设计范式的锚点论文
- [[2022-li-rund]] — 拆解安全容器（Kata+microVM）在高密度/高并发场景下 VMM 之外的瓶颈（rootfs、guest kernel、host cgroup），生产验证的密度/并发优化方案
- [[kata-containers-architecture]] — Kata Containers 官方架构文档，"安全容器"（VM 套容器）路线的标准架构说明：shimv2、三层环境模型、guest assets、agent 通信、存储两条路径
- [[2023-huang-pvm]] — 提出第三种隔离取舍点：不依赖硬件支持、对宿主透明的软件嵌套虚拟化，解决"host 无 hypervisor 控制权"场景下的强隔离需求
- [[2020-anjali-firecracker-gvisor]] — 独立第三方内核代码覆盖率与微基准对比研究，量化 [[gvisor]] 与 Firecracker 两条 microVM/paravirtualization 路线的实际差异
- [[2026-gensee-agentenv-microvm-fork]] — 第三方对 AgentENV fork 机制的代码级拆解与实测，验证并量化了"microVM fork 进程数无关、但脏内存同步发布代价随之线性增长"这一机制
