---
title: "RunD: A Lightweight Secure Container Runtime for High-density Deployment and High-concurrency Startup in Serverless Computing"
type: paper
id: "2022-li-rund"
source_url: https://www.usenix.org/conference/atc22/presentation/li-zijun-rund
authors: [Zijun Li, Jiagan Cheng, Quan Chen, Eryu Guan, Zizheng Bian, Yi Tao, Bin Zha, Qiang Wang, Weidong Han, Minyi Guo]
affiliations: [Shanghai Jiao Tong University, Alibaba Group]
published: 2022-07-11
created: 2026-09-26
tags: [sandbox, microvm, kata-containers, serverless, isolation, density, cold-start]
concepts: [rund, microvm-sandbox, firecracker]
rating: 5
issue: 22
parent: "2609.22978"
---

# RunD: A Lightweight Secure Container Runtime for High-density Deployment and High-concurrency Startup in Serverless Computing

> 阿里生产验证的安全容器运行时：用 rootfs 读写分层、内核精简+预 patch、轻量 cgroup 池三件套，把 Kata 容器单机密度做到 2,500+、200 并发启动压到 1 秒。

## 元信息

- 机构：上海交通大学 & 阿里巴巴集团
- 发表：USENIX ATC '22（2022-07-11），pp. 53–68
- 链接：[USENIX 论文页](https://www.usenix.org/conference/atc22/presentation/li-zijun-rund) · [Code](https://github.com/chengjiagan/RunD_ATC22)
- 对比基线：Kata Containers 的三种配置——Kata-qemu、Kata-template（QEMU + VM 模板）、Kata-FC（[[firecracker]] 作为 hypervisor）；同属"安全容器"路线的锚点系统是 [[2020-agache-firecracker]]

## 要解决的问题

安全容器（single-container-per-VM：一个 microVM 里跑一个容器，用 [[firecracker]] 或 QEMU 提供虚拟化级隔离，容器运行时如 Kata 负责兼容性）在生产 serverless 场景下暴露两个瓶颈，而非单纯的隔离开销问题：

- **高并发启动**：阿里生产平台上单节点经常有 200+ 容器请求几乎同时到达；论文测得 200 个 Kata 容器并发启动时，Kata-runtime 准备阶段的 rootfs 创建与 cgroup 创建出现明显性能劣化。
- **高密度部署**：47% AWS Lambda 函数用最小 128MB 内存规格，Azure 约 90% 应用不超过 400MB，理论上 384GB 内存节点可以塞下上千个函数；但 microVM 的 guest kernel + rootfs 内存占用（以及 host 侧调度开销）在超过 1,000 个容器时已经吃掉大部分内存，I/O 性能同时严重下降。

论文的定位是：Firecracker 只解决了 hypervisor 这一层的轻量化，但安全容器还叠加了 rootfs 存储、guest kernel、host cgroup 三层，这些层各自的开销在高密度/高并发场景下会被放大，需要一个贯穿 guest-to-host 全栈的方案，而不是只优化 VMM。

## 方法

RunD（基于 Kata-runtime 用 Rust 重写，四个模块：Containerd-shim 21k LOC、Device 4.4k LOC、Hypervisor 5.6k LOC、Lightweight-cgroup 20k LOC）提出三个正交的优化，分别对应上面识别的三个瓶颈来源（§3 逐一实测定位，§4 逐一给方案）：

- **rootfs 读写分层**（§4.2）：实测发现 [[microvm-sandbox|virtio-fs]] 随机/顺序写性能差且每容器需要一个 client daemon（高并发下 CPU 开销大），virtio-blk 则用 device-mapper 准备块设备耗时随并发线性恶化（200 容器并发时单个 rootfs 准备要 10 秒，串行只要 30ms）且不支持 host/guest page cache 共享。RunD 的方案：只读层走 virtio-fs（可在多个 sandbox 间共享 page cache，且用 overlay snapshotter 准备几乎零耗时），可写层走 **volatile block device**——预先建一个 storage image template，每个新 sandbox 用 reflink（CoW）从 template 克隆一个 built-in storage image，hypervisor 打开设备后立即删除该文件（open-but-unlink），保证写入不落盘持久化。效果：200 并发下 IOPS 从 4,500 降到 1,500、带宽 100MB/s→8MB/s，rootfs 准备耗时从 207ms 降到 0.2ms，写性能与主流方案持平。
- **精简 + 预 patch guest kernel**（§4.3）：guest kernel 被显式视为不可信（syscall inspection 是隔离边界），因此可以在编译期裁掉与 serverless 场景无关的功能（不预建 loop device、关闭 acpi/ftrace、去掉图形相关、i2c/ceph 等），CentOS 4.19 内核精简约 16MB 内存、镜像缩小约 4MB。更关键的发现是**内核自修改代码（self-modifying code）**会破坏 microVM template 依赖的 mmap 共享只读段假设：一个干净 microVM 从模板启动后，10,012KB 的代码+只读数据里有 7,928KB 在启动阶段被自修改覆写，导致原本该共享的页变成了每个 VM 私有。RunD 的解法是预先生成一个**已经跑过自修改阶段的 pre-patched kernel image**作为模板基础，让同节点的 sandbox 真正共享这部分内存，而不是各自重新执行一遍自修改再变成私有页。
- **轻量 cgroup + cgroup 池**（§4.4）：定位到 Linux 内核用多个全局锁（cgroup_mutex、css_set_lock、freezer_mutex）串行化 cgroup 操作，协调 cpu/cpuacct/cpuset/memory/blkio 等 10+ 个子系统；并发创建 2,000 容器时线程越多延迟反而越高（乐观自旋锁在高并发下反倒放大 CPU 消耗），且上万 cgroup 会拖慢 CFS 的 PELT 负载均衡（论文测得占 7.6% 物理机 CPU 周期）。RunD 用**joint cgroup controller**把多个子系统聚合成一个 dedicated lightweight cgroup 减少 cgroup/syscall 总数；再用**预建 cgroup 池 + rename**替代创建——cgroup rename 是不需要抢全局锁的轻量操作，容器创建时从 idle 池里取一个改名挂载，回收时改名放回池子。效果：cgroup 创建耗时从（未给出优化前具体数字，但对照 §3.3 的劣化曲线）降到 0.09s（1 线程）/0.1s（50 线程）/0.14s（200 线程），减少 94% 的 cgroup 创建时间。

三个优化分别落在图 7 的三个位置：guest 域（精简内核、pre-patched image）、host 域读写分层（virtio-fs + virtio-blk + overlayfs）、host 域资源管理（lightweight cgroup pool）。

## 实验与结果

评测环境：104 vCPU（Intel Xeon Platinum 8269CY）、384GB 内存、两块 SSD（100GB + 500GB），CentOS7 + Linux 4.19.91；对照 Kata-qemu、Kata-template、Kata-FC 三种配置（Table 1）。

- **并发启动**（§5.2，Fig 10）：200 容器并发启动，Kata-FC/Kata-qemu/Kata-template/RunD 分别耗时 47.6s / 6.85s / 2.98s / **1s**；相比最接近的 baseline（Kata-template）在 400-way 高并发下快约 40%。CPU 开销：200 并发下 RunD 比 Kata-qemu/Kata-template/Kata-FC 分别降低 89.3%/74.5%/62.1%。单容器冷启动 88ms。
- **部署密度**（§5.3，Fig 11/12）：100 sandbox 部署时，RunD 每 sandbox 内存开销 <20MB，比 Kata-qemu/Kata-template/Kata-FC 分别低 54.9%/27.2%/18.9%（即便在 128MB 规格下）；1,000 sandbox 部署时分别低 87.7%/82.4%/75.1%。**在 384GB 内存节点上支持部署超过 2,500 个 128MB 规格的 sandbox**（理论上限 384GB/(128+20)MB ≈ 2,656）。
- **密度对并发的影响**（§5.4，Fig 13）：已部署 1,000 sandbox 时，再启动 10 个新容器的耗时增量分别为 Kata-qemu +1.69s、Kata-template +0.41s、Kata-FC +10.8s、**RunD +0.22s**——高密度背景下 RunD 的并发退化最小，原因是它已经消除了大部分 cgroup 相关开销（密度越高，cgroup 数量越大，调度/管理这些 cgroup 消耗的 CPU 周期越是瓶颈）。
- **生产验证**（§5.5，Fig 14/15）：阿里 serverless 平台服务超百万函数、日均近 40 亿次调用；线上单节点峰值并发启动 191 个 sandbox，RunD 用 1.6 秒完成；单节点部署密度峰值超过 2,000 个 sandbox。CPU 利用率长期不到 50%（大量 sandbox 是 keep-alive 空闲状态），但用户无感知——说明这套系统的瓶颈设计目标是密度/启动延迟而非 CPU 利用率。
- **生产经验教训**（§5.6）：① K8s 的 CRI（pause 容器先建 cgroup 再挂载其它容器）不适合"一个 sandbox 只跑一个容器"的安全容器模型；② 若把语言运行时（如 JVM）打进 microVM template，会因为语言运行时需要预分配内存而失去 on-demand 内存加载能力——内存利用率与启动时间之间需要权衡，取决于函数间共享同一 guest 环境的比例；③ 函数实际内存使用量决定部署密度上限，多数函数是轻量级的。

## 局限与疑点

- 三项优化（rootfs 分层、内核精简+预 patch、轻量 cgroup 池）虽然论文称"holistic guest-to-host"，但彼此工程上相对独立，论文没有做单独的 ablation 量化每一项各自的贡献占比，只给出叠加后的整体对比数字。
- pre-patched kernel image 解决了"自修改代码破坏内存共享"的问题，但论文承认这带来了"potential kernel panic issues"需要额外处理稳定性（§4.3.2 一句话带过，未展开细节，可复现性存疑）。
- 评测里 Kata-qemu、Kata-template 用的是旧版本 Kata（1.12.1），论文承认新版本 Kata 有 bug 导致性能更差所以选旧版本作对比——这让"RunD 比 Kata baseline 快多少"的具体倍数打了折扣，更适合看相对趋势而非绝对倍数。
- 所有并发/密度实验都是启动**空容器**（无用户代码/数据），理由是"FaaS 预热场景常见做法"；生产数据（§5.5）只报告了启动延迟与密度，没有报告真实函数负载下三项优化的收益是否等比例保持。
- volatile block device 的"open-but-unlink 不持久化"设计，前提是 serverless 场景下沙箱内数据天然无需跨调用持久化；如果目标场景（比如我们的 agent 训练沙箱）需要长期保留 sandbox 内产生的状态，这个设计前提直接不成立，需要retrofit。

## 对我们的启发

- **RunD 证明"只优化 VMM 不够"——安全容器的密度/并发瓶颈分散在 guest kernel、host cgroup、rootfs 存储三层，需要贯穿全栈定位**。我们评估自己沙箱平台的密度/冷启动指标时，不能只看 microVM hypervisor 层（如 Firecracker）的开销数字，还要单独测 rootfs 准备、cgroup 创建这些容易被忽略的 host 侧环节，尤其是并发量上去之后的非线性劣化（论文的核心洞察是"少量开销在低密度/低并发时可忽略，但在高密度/高并发下会被放大"）。
- **"读写分层 + CoW 卷 + open-but-unlink 不持久化"这套 rootfs 方案，与 DSec 自己的 OverlayBD + ublk 方案是同一问题的不同解法**（见下方"与母论文的关系"），如果我们平台的 sandbox 也需要支持训练场景里"部分沙箱需要落盘持久化、部分不需要"的混合需求，RunD 的 volatile block device 思路可以作为"无需持久化"场景的轻量备选，比通用块设备方案更快。
- **cgroup 池 + rename 替代创建，是一个可直接复用的通用容量规划模式**：预建资源池、用重命名而非重新创建来分配/回收，避免碰全局锁——不限于 cgroup，我们平台任何"高频创建/回收、但受内核全局锁串行化"的资源（网络 namespace、cgroup、某些内核对象）都值得先测一下是否存在类似的锁瓶颈，再考虑池化。
- **内核自修改代码破坏 microVM template 内存共享，是我们做类似"沙箱模板/快照复用内存"设计时必须验证的一个具体坑**：如果我们的执行环境模板依赖 mmap 共享只读段来降低单沙箱内存开销，需要实测 guest kernel 启动阶段有多少"只读"页实际被自修改覆写，否则模板带来的内存节省可能被高估。
- Follow-up 建议（可转 issue）：
  1. 精读清单里的 Kata Containers 架构文档（[[kata-containers-architecture]]，本文三个 baseline 配置的基础），把 RunD 相对 Kata 原生的三项修改在架构图层面对齐一次；
  2. 精读母论文 DSec §5.2 的内存优化（virtio-pmem+DAX、DAMON 冷内存回收）与 RunD 的"精简+预 patch 内核"在效果量级上做一次对比，看两条路线（内存去重 vs 内核精简）是否正交可叠加；
  3. 关注 RunD 的"cgroup 全局锁"发现在更新内核版本（cgroup v2）下是否依然成立——本文用的是 Linux 4.19.91，cgroup v2 的锁设计有变化，需要验证瓶颈是否已被上游修复。

## 相关

- 相关概念：[[rund]]、[[microvm-sandbox]]、[[firecracker]]
- 相关笔记：[[2020-agache-firecracker]]（本文最直接的对比基线之一，Kata-FC 配置即用 Firecracker 做 hypervisor）
- 与母论文的关系：DSec（[[2609.22978]]）在 §9 Related Work 的"Serverless computing"一段直接点名 RunD，与 SAND、REAP、TrEnv 并列，指出这类系统"optimize cold-start latency and resource sharing for short-lived, stateless functions"，并给出一个明确的适用边界批评：*"These workloads typically reuse a limited set of images at high fanout, and many systems assume that the required images are already available locally. Agentic training instead uses long-lived, stateful sandboxes drawn from an image corpus that exceeds single-node storage and has low per-image fanout."*（DSec §9）——也就是说，DSec 认为 RunD 这类面向 Lambda 式短生命周期、高复用、镜像小而集中的函数计算场景做的密度/并发优化，不能直接套到 DSec 自己的目标场景：agent 训练用的沙箱生命周期长、有状态、镜像库规模超过单机存储且单镜像复用率低。RunD 的三项具体优化（rootfs 读写分层、内核精简、cgroup 池化）在"高并发启动、高密度部署"这两个指标维度上与 DSec 高度相关且方法上有可比性（DSec 自己也做内存优化和调度密度优化），但 RunD 隐含假设的"无状态、短生命周期、可随时丢弃可写层数据"前提，在 DSec 场景下不成立，DSec 必须额外解决状态持久化、大规模镜像按需加载（3FS + OverlayBD/ublk，见 [[firecracker]] 笔记）这两个 RunD 不需要面对的问题。RunD 在 DSec 里被归类为 Firecracker 之外的"安全容器路线的另一种密度优化尝试"，而不是被当作直接可复用的组件。
