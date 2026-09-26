---
title: "Firecracker: Lightweight Virtualization for Serverless Applications"
type: paper
id: "2020-agache-firecracker"
source_url: https://www.usenix.org/conference/nsdi20/presentation/agache
authors: [Alexandru Agache, Marc Brooker, Andreea Florescu, Alexandra Iordache, Anthony Liguori, Rolf Neugebauer, Phil Piwonka, Diana-Maria Popa]
affiliations: [Amazon Web Services]
published: 2020-02-25
created: 2026-09-26
tags: [sandbox, microvm, isolation, serverless, virtualization]
concepts: [firecracker, microvm-sandbox]
rating: 5
issue: 22
parent: "2609.22978"
---

# Firecracker: Lightweight Virtualization for Serverless Applications

> 用一个 KVM 上的极简 Rust VMM 替代 QEMU，在虚拟化级别的隔离下做到接近容器的启动速度与密度，撑起 AWS Lambda 的多租户沙箱。

## 元信息

- 机构：Amazon Web Services
- 发表：NSDI '20（2020-02-25）
- 链接：[USENIX 论文页](https://www.usenix.org/conference/nsdi20/presentation/agache) · [Code](https://github.com/firecracker-microvm/firecracker)
- 对比基线：QEMU/KVM v4.2.0（静态编译精简配置）、Intel Cloud Hypervisor；相关路线 [[kata-containers-architecture]]（未精读，本篇 §2.1.3 提及）、LightVM（Manco et al. 2017，同样在清单中）

## 要解决的问题

多租户 serverless（Lambda、Fargate）需要在同一台物理机上运行大量互不信任的客户函数，传统上被认为只能二选一：
- **虚拟化隔离**（QEMU/KVM、Xen）：安全边界强，但 VMM 复杂度高（QEMU >140 万行代码，可达 270 个独立系统调用）、内存开销大（QEMU 每 VM 约 131MB）、启动慢（秒级）；
- **Linux 容器**（Docker/LXC）：共享内核，靠 cgroups/namespaces/seccomp-bpf 隔离，启动快、密度高，但安全边界依赖内核 syscall 面的收窄，与兼容性直接冲突（一个典型 Ubuntu 15.04 安装需要 224 个 syscall 才能正常跑）。

Lambda 早期方案是"同客户函数共享容器、不同客户用不同 VM"，但存在容器安全/兼容性两难、以及固定大小 VM 装箱效率低的问题。作者据此提出六条选型标准：Isolation、Overhead and Density、Performance、Compatibility、Fast Switching、Soft Allocation（§2）。

## 方法

**核心思路**：保留 KVM，完全替换 QEMU，用 Rust 重写一个极简 VMM（Firecracker），只做 serverless/容器场景真正需要的那部分虚拟化。

- **设备模型**（§3.1）：只实现网络、块设备（virtio）、串口、部分 i8042，不做 BIOS、不支持任意 guest 内核启动、不支持 PCI 直通、不支持 VM 迁移、不能跑 Windows。整个 virtio block 实现约 1400 行 Rust；i8042 driver 不到 50 行。选择块设备而非文件系统透传，是为了不把宿主内核的文件系统面暴露给 guest。
- **API**（§3.2）：Unix socket 上的 REST API，管理 MicroVM 的生命周期（配置→启动→关闭），可以先配置后按需启动以降低启动延迟。
- **限流与机器配置**（§3.3）：网络/磁盘的 IOPS 与带宽用 token bucket 限流，cpuid 可被宿主裁剪以在异构机队上呈现同构视图；相比 cgroups 功能少很多，仅在"不信任 guest 自我限流"的场景才在 VMM 层做限流，其余交给宿主 OS。
- **安全加固**（§3.4）：应对 Meltdown/Spectre/Zombieload 等侧信道，生产环境建议关闭 SMT、开启内核缓解补丁、禁用 swap 与 KSM（同页合并）、避免跨租户共享文件。**Jailer** 组件在 Firecracker 进程外再包一层 chroot + pid/net namespace + 降权 + 白名单 24 个 syscall/30 个 ioctl 的 seccomp-bpf profile，作为防止 VMM 本身被攻破的第二道防线。
- **实现血统**：源自 Google Chrome OS 的 crosvm，代码量精简到 crosvm 的不到一半（约 5 万行 Rust，是 QEMU 的 4%），移除了 USB/GPU/9p 等驱动；与 crosvm 共享的底层 crate 沉淀为 rust-vmm 项目。

**架构落地到 Lambda**（§4.1）：Frontend 接收调用请求 → Worker Manager 做 sticky routing（同一函数尽量路由到已有"slot"以复用 MicroVM 和进程）→ 无可用 slot 时 Placement service 用装箱优化选择宿主并创建新 slot（通常 <20ms）→ 每个 worker 上的 MicroManager 管理本机所有 Firecracker 进程，并维护一个小型预启动 MicroVM 池以掩盖启动延迟。Slot 生命周期：Init → Idle ↔ Busy → Dead（Figure 4），最长存活 12 小时后回收。

## 实验与结果

评测环境：EC2 m5d.metal（2×Intel Xeon Platinum 8175M，48 核关闭 SMT，384GB RAM，4×840GB NVMe），Firecracker v0.20.0 vs QEMU v4.2.0 vs Intel Cloud Hypervisor。

- **启动时间**（§5.1，Figure 5/6）：预配置 Firecracker 串行启动中位数与 Cloud Hypervisor 相当，比 QEMU 快约一倍；端到端（含 REST API 配置）Firecracker 与 QEMU 差距缩小到约 50ms。1000 个 MicroVM 以 50 并发批量启动，预配置 Firecracker 99 分位 146ms（QEMU/CloudHV 更高）。生产内核配置（精简驱动、不加载模块、禁用串口日志）下端到端最快到 **150ms**；对比默认 Ubuntu 18.04 内核配置反而多花 900ms 启动时间。
- **内存开销**（§5.2，Figure 7）：Firecracker 每 VM 常数开销约 **3MB**，Cloud Hypervisor 约 13MB，QEMU 约 131MB，与配置的 VM 大小无关。
- **IO 性能**（§5.3）：4KB 随机读在物理机可达 34 万 IOPS，Firecracker/CloudHV guest 限制在约 1.3 万 IOPS（52MB/s）；4KB 读延迟只比裸机慢 49μs，大块（128KB）与写路径开销更明显（Firecracker/CloudHV 当时不支持 flush-on-write）。网络单流吞吐 Firecracker 约 15Gb/s（裸机 tap 接口可达 44Gb/s），QEMU/CloudHV 略高但生产上未成为瓶颈。
- **生产验证**（§5.4）：内存/CPU 超卖比在生产中跑到 **10x**，测试验证过 20x 无问题；2018 年起在 Lambda/Fargate 上无中断迁移，服务**数百万工作负载、每月万亿级请求**。

## 局限与疑点

- 论文自己列出的方向性局限（§6 Conclusion）：密度还能靠内存去重进一步提升；网络/存储/加速器的高密度 host bypass 还没做；VMM 的可信计算基还能再缩小；启动与切换成本还有下降空间。
- 块 IO 的写路径当时**不支持 flush-to-disk**，高写吞吐是以牺牲持久性为代价换来的（§5.3 明确提示"需谨慎看待"）。
- 网络吞吐（15Gb/s 单流）明显低于裸机和 QEMU/CloudHV，论文承认但称"生产环境未见成为限制"——这是厂商自证，没有给出具体业务场景下的瓶颈分析。
- 评测只在单一硬件型号（m5d.metal）上做，且是 2019–2020 年的硬件/内核版本，六年后的现状（NVMe 性能、内核 virtio 栈演进）需要结合更新的资料（清单里的 [[brooker-seven-years-of-firecracker|Seven Years of Firecracker]] 可能有后续数据）。
- 论文是 AWS 自己的系统论文，评测基线和结论服务于"证明 Firecracker 达到了 Lambda 的六项目标"，没有第三方复现数据。

## 对我们的启发

- **"重写极简 VMM 而非裁剪 QEMU"是隔离基础设施的一个可复用决策模式**：当通用虚拟化软件的复杂度（攻击面、代码量）本身就是隔离目标的对立面时，为专用场景重新设计一个只做"必要子集"的组件（这里是 VMM，我们平台上可能是某个通用组件的等价物）往往比裁剪通用方案更彻底。这与我们评估"要不要自研 vs 复用现成隔离方案"的决策直接相关。
- **Jailer 的"沙箱套沙箱"思路值得对照我们自己的多层防御设计**：即便 microVM 本身提供了强隔离边界，作者仍然不信任 VMM 进程本身，用 chroot + namespace + seccomp 再包一层。如果我们平台的执行环境只依赖单一隔离层（比如只信任 gVisor 或只信任 microVM），这篇提示我们应该评估是否需要给控制面进程本身也加一层最小权限沙箱。
- **3MB/VM 的内存开销和 150ms 冷启动是 2020 年的历史基线**，我们评估现在的 Firecracker（或同类 microVM 方案）在自己硬件/内核上的真实数字时，不能直接引用这篇论文的数字当作现状——需要用清单里更新的博文（Seven Years of Firecracker）或自己实测。
- **预启动池 + Little's law 反推池大小**（§4.1.2：150ms 创建延迟对应约每秒 8 次创建配 1 个预启动 MicroVM）是一个具体可执行的容量规划公式，如果我们的冷启动延迟已知、创建速率已知，可以直接套用来定池子大小，而不是拍脑袋定一个固定池容量。
- **超卖比 10x（生产）/20x（测试）验证过无问题**，是我们规划自己 microVM 密度/超卖策略时的一个外部参照锚点，但要注意这是 Lambda 场景（小内存函数、短生命周期）下的数字，不能直接套到我们训练用 agent 沙箱（可能资源占用模式差异很大）。
- Follow-up 建议（可转 issue）：
  1. 精读清单里的 [[brooker-seven-years-of-firecracker|Seven Years of Firecracker]]，看六年后 Firecracker 的启动时间/密度/新增能力（如 SnapStart 依赖的快照）相比本文数字有何变化；
  2. 精读 RunD（清单 B 类，"最贴近我们密度/冷启动目标"）时对照本文的六项选型标准，看 RunD 在哪些维度做了进一步优化；
  3. 关注 Firecracker 的 virtio-fs 支持现状（DSec §3.3 提到 Firecracker 后端不支持 virtio-fs，只能走 ublk+OverlayBD），这是我们如果选型 Firecracker 类 microVM 时会直接撞上的存储集成限制。

## 相关

- 相关概念：[[firecracker]]、[[microvm-sandbox]]
- 相关笔记：（暂无同类笔记，本篇是 B 类"隔离运行时/microVM"分类的第一篇）
- 与母论文 [[2609.22978]] 的关系：DSec（DeepSeek Elastic Compute）在 §2.2 沙箱后端选型中把 Firecracker microVM 列为四种底座之一（另有 FnCall、container、full-VM），定位为"隔离边界强于容器、保留 Linux 兼容性，但内存开销更高、启动比容器慢"——与本文 §2.1.3 对虚拟化 vs 容器的取舍分析一致，DSec 直接复用了 Firecracker 建立的这套权衡框架。DSec §3.3 描述其架构落地：microVM 磁盘走 OverlayBD 格式 + ublk 用户态块设备按需从分布式文件系统（3FS）加载，因为**Firecracker 后端不支持 virtio-fs**，这是本文未展开但对我们直接相关的一个存储集成约束。DSec §5.2 的内存优化（virtio-pmem + DAX 消除 guest/host 页缓存重复、DAMON 配合气球设备回收冷内存）是在本文"soft allocation/超卖"目标之上做的更细粒度工程延伸。DSec §9 相关工作部分把 Firecracker 与 VM 支持的 Kata Containers 并列，定位为隔离-性能权衡谱系上的一个选项，强调 DSec 的创新在于**整合多个后端**而非提出新隔离机制——即 DSec 是 Firecracker 之上的编排/调度/密度优化层，而不是替代品。
  （以上 DSec 章节内容来自对论文原文的检索转述，非逐字引用，未见到 notes/papers/2609.22978.md，待该笔记建立后应交叉核对本节。）
