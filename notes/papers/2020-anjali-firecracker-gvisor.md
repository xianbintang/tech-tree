---
title: "Blending Containers and Virtual Machines: A Study of Firecracker and gVisor"
type: paper
id: "2020-anjali-firecracker-gvisor"
source_url: https://doi.org/10.1145/3381052.3381315
authors: [Anjali, Tyler Caraza-Harter, Michael M. Swift]
affiliations: [University of Wisconsin-Madison]
published: 2020-03-17
created: 2026-09-26
tags: [sandbox, microvm, gvisor, isolation, serverless, kernel-footprint]
concepts: [gvisor, firecracker, microvm-sandbox, kata-containers]
rating: 4
issue: 22
parent: "2609.22978"
---

# Blending Containers and Virtual Machines: A Study of Firecracker and gVisor

> 用内核代码覆盖率（lcov）+ 微基准测试对比 LXC、[[gvisor]]、[[firecracker]]：三者都比原生 Linux 执行更多内核代码，"移出内核"不等于"减少内核依赖"。

## 元信息

- 机构：University of Wisconsin-Madison
- 发表：VEE '20（2020-03-17，Lausanne, Switzerland），13 页
- 链接：[ACM DL](https://doi.org/10.1145/3381052.3381315)
- 对比基线：原生 Linux 进程、LXC（Docker `runc`）、[[gvisor]]（KVM-mode）、[[firecracker]]；未评测 QEMU/KVM 全虚拟化
- 相关：母论文 Firecracker 设计论文 [[2020-agache-firecracker]]、安全容器架构 [[kata-containers-architecture]]、密度优化 [[2022-li-rund]]

## 要解决的问题

Firecracker（虚拟化路线，跑完整 guest 内核）和 gVisor（用户态 Sentry 拦截转发系统调用）都号称"移出了大量宿主内核功能"来换取更强隔离，但论文提出一个此前没人系统量化过的问题：**这些平台实际上把多少宿主内核代码留在了执行路径里？** 仅比较启动时间、内存开销、吞吐量（如 [[2020-agache-firecracker]] 做的）无法回答"隔离边界收窄了多少攻击面"，因为宿主内核代码量本身就是攻击面的代理指标——功能移出内核不代表宿主内核不再被调用，也不代表调用的是同一份代码。此前 Bottomley 的工作只做过函数粒度的覆盖率测量，本文是第一个用行/分支粒度做细粒度覆盖率分析的研究。

## 方法

**架构定位**（§2，图 1）：把四种隔离方案摆在"OS 功能位于宿主内核 vs 移出宿主内核"的谱系上——原生 Linux（全在宿主内核）→ LXC（宿主内核 + 用户态 daemon 做编排）→ [[gvisor]]（多数系统调用在用户态 Sentry 里重新实现，仅 Sentry 自身对宿主内核发起有限调用）→ [[firecracker]]（完整 guest 内核跑在 microVM 里，宿主只提供 KVM + 有限设备）→ 全虚拟化 QEMU/KVM（功能移到 guest OS 或 QEMU 进程）。

**gVisor 架构**（§2.3，Figure 2）：用户空间 Go 实现的 *Sentry* 内核拦截容器发出的全部系统调用，自己实现其中 237/350 个（据 2019-11 的 5.3.11 内核版本统计），Sentry 本身仅向宿主发起 53 个（不开 host networking）或 68 个（开 host networking）白名单系统调用；两种拦截方式：ptrace-mode（用内核 ptrace 转发）与 KVM-mode（用 KVM 在到达 Linux 内核前拦截系统调用转发给 Sentry，性能更好，本文全程用这个模式）。文件访问通过每容器一个的 *Gofer* 进程代理，Sentry 被攻破也不能直接读写宿主文件；有自己的用户态网络栈 *netstack*（TCP/UDP/IP4/IP6/ICMP 全部在 Sentry 里实现），也可选用宿主网络栈换性能。

**Firecracker 架构**（§2.4）：与 [[2020-agache-firecracker]] 一致的极简 VMM + Jailer 权限收紧描述，本文额外给出系统调用白名单具体数字：36 个（vs Jailer 论文里提到的 24 syscall/30 ioctl 是 Jailer 自身再加一层的收紧范围，两者统计口径不同，不构成矛盾）。

**评测方法**（§3.1）：CloudLab xl170（10 核 Intel E5-2640v4 2.4GHz、64GB ECC 内存、480GB SSD、10Gbps 网卡），Ubuntu 18.04（内核 v5.4.13），gVisor release-20200127.0，Firecracker v0.19.1。用 `lcov` 对内核代码做行覆盖率统计，每个微基准跑 10 分钟；先测空闲宿主 10 分钟算出每行代码的"背景命中率"，只有命中率显著高于背景值才算作该平台"执行了"这行代码，以过滤后台噪音（这一步能过滤掉约 1-1.5 万行背景代码）。四类微基准：CPU（sysbench + LLCProbe）、网络（iperf3 带宽 + ping 延迟）、内存（mmap/munmap）、文件访问（顺序读写）。

## 实验与结果

**系统调用白名单**（Table 1，宿主内核共 350 个系统调用入口）：LXC 除 44 个（Docker 默认屏蔽过时/需 root/无 namespace 保护的调用）外全部放行；Firecracker 白名单 36 个；gVisor 不开 host networking 时 53 个，开启后 68 个——Firecracker 的白名单比 gVisor 更紧。

**总代码footprint**（Table 2，宿主内核共 806,318 行代码，四类工作负载覆盖率取并集）：原生 Linux 63,163 行（7.83%）< Firecracker 77,392 行（9.59%）< LXC 90,595 行（11.23%）< gVisor 91,161 行（11.31%，四者中最高）。**核心反直觉发现**：即便 gVisor 把系统调用大部分实现在用户态 Sentry、Firecracker 把功能移进 guest 内核，两者执行的宿主内核代码量反而都明显超过完全没做特殊隔离的原生 Linux——"移出内核的功能"变成了"新增的宿主内核交互面（KVM 虚拟化支持代码、networking 设置代码等）"，而不是纯粹的减法。

**CPU 工作负载**（§4，sysbench + LLCProbe）：分平台看总 footprint，gVisor 最大（78k LOC）、Firecracker 最小（49k LOC）；`/virt` 目录（KVM 相关）只有 Firecracker/gVisor 涉及，Firecracker 因为要做 virtio 网络/块设备模拟，比 gVisor 多用 43% 的代码；`/arch/x86/kvm` 里 Firecracker 比 gVisor 多执行 2,550 行（模拟设备代码）。但纯 CPU 计算性能（sysbench events/秒、LLCProbe 探测数）四个平台几乎相同（10 实例时性能均下降约 23%）——**隔离层对纯计算负载几乎零性能代价，代价体现在代码面而非速度**。

**网络**（§5，iperf3 + ping）：gVisor 尽管有自己的用户态网络栈，`/net` 目录覆盖率反而与 LXC 高度重叠（`dev_get_by_index()` 只在 LXC/gVisor 执行，说明两者用了同类型的桥接网络接口）；Firecracker 执行的网络代码量最少（大部分处理在 guest 内完成）。性能上：单流带宽 Host/Firecracker 约 9.4-9.5Gbps 最高，LXC 7-10.1Gbps，**gVisor 最慢，单实例仅 0.805Gbps**（10 实例聚合到 3.294Gbps），开启 host networking 后单实例提升到 3.03Gbps 仍是四者最慢；RTT 延迟反而是 **Firecracker 最高（371μs）**，超过 gVisor（319μs）、LXC（149μs）、原生（146μs）——因为一个包要穿两层内核网络栈（guest + host）。**Firecracker 网络吞吐好、延迟差；gVisor 带宽差、延迟中等**，两个平台没有一个在网络维度全面占优。

**内存管理**（§6，mmap/munmap）：gVisor 有 app→Sentry→host 两级页表转换，1GB 内存请求时 Sentry 把请求合并成 64 次 16MB 粒度的 mmap 调用发给宿主（vs LXC 的 `do_mmap()` 调用超百万次），理论上减少了调用次数，但**小粒度（4KB）分配+触碰+释放耗时反而是四者中最差**（7.4s vs host 500ms、LXC 550ms、Firecracker 650ms，约 10 倍），大粒度（1MB）时才追平；Firecracker 初始化后完全不再对宿主发起 mmap 调用，内存栈完全在 guest 内闭环，多数场景性能贴近原生。

**文件访问**（§7）：Firecracker 用块设备（宿主文件承载虚拟磁盘），只涉及文件数据不涉及目录元数据，footprint 适中；gVisor 和 LXC 都用 overlayfs 叠加 ext4，footprint 更高（overlay 文件系统重度依赖底层文件系统元数据）。写吞吐（Figure 19）：**Firecracker 最快（500-1020 MB/s），因为不做落盘持久化保证**，几乎跑在内存速度；host/LXC 约 270-320MB/s；**gVisor 最慢（140-300MB/s）**。读吞吐（Figure 20）：全部清缓存时四者接近（都要从存储读取）；只清 guest 内缓存但宿主缓存热时，Firecracker 可达 4100-6300MB/s（约 2 倍于宿主热缓存吞吐）。

## 局限与疑点

- 论文自陈（§8 Limitations）：覆盖率方法论是"全系统 profiling"与"前台专属 profiling"的折中，仍可能混入少量后台噪音；微基准覆盖率只能提示安全性，不能替代更丰富工作负载下的完整覆盖率评估；因为当时 Firecracker 还没接入 Docker，无法跑现成的容器化 benchmark 套件做更贴近真实的评测。
- 未评测 KVM/QEMU 全虚拟化（只作架构背景介绍），也没有 Kata Containers（用文字提及为"相似目标系统"但未纳入实测）。
- 硬件与内核版本较老（2020 年 CloudLab 机型、Linux 5.4.13、gVisor 2020-01 版本、Firecracker v0.19.1），gVisor 和 Firecracker 六年来迭代很快（如 [[2020-agache-firecracker]] 笔记提到的 Seven Years of Firecracker 待读），本文的具体代码行数/吞吐数字很可能已经过时，但"移出内核不等于减少内核依赖""复合系统瓶颈分散在多层"这类结构性结论更可能仍然成立。
- "代码行数多=攻击面大"是论文自己承认的一个近似代理指标，未必等价于真实可利用漏洞数，作者在结论里也只说这类分析"能作为架构设计的参考和安全研究的动机"，没有声称给出了确定性的安全结论。

## 对我们的启发

- **"隔离边界强"不等于"宿主内核依赖少"，评估自研/选型隔离方案时不能只看该方案的设计文档说了什么，要实测它在真实工作负载下到底触达了宿主内核的哪些代码路径**。如果我们平台上同时跑多种隔离后端（容器、gVisor 类沙箱、microVM），可以借用本文的方法论（覆盖率 + 微基准）而非厂商宣传数字来横向评估攻击面。
- **没有一个隔离方案在所有维度都占优，权衡是精细的、按工作负载类型分的**：Firecracker 网络吞吐好但延迟差、内存/文件在"初始化后不碰宿主"的场景下最快；gVisor 网络带宽最差、小粒度内存操作最慢，但 CPU 计算几乎零损耗。如果我们的 agent 沙箱工作负载画像明确（比如以文件 IO、代码执行为主 vs 以网络密集型工具调用为主），选型时应该按workload 类型挑，而不是选一个"平均最优"的方案。
- **Firecracker 写吞吐快是因为不做持久化保证**——这与 [[2020-agache-firecracker]] 笔记里"写路径不支持 flush-to-disk"的局限一致，是同一个设计取舍的两次独立验证：用 Firecracker 类 microVM 承载有状态、需要持久化保证的 agent 训练沙箱时，必须在系统层面（而不是指望 VMM）解决持久化问题（比如 DSec 的 3FS + OverlayBD 方案）。
- **gVisor 的双层页表（app→Sentry→host）在小粒度内存操作下有数量级的性能损失（4KB mmap/munmap 慢 10 倍）**，如果我们评估 gVisor 作为某类沙箱后端，需要关注目标工作负载是否有频繁的小粒度内存分配模式（比如某些解释器、动态语言运行时），这类模式下 gVisor 可能不是好选择。
- Follow-up 建议（可转 issue）：
  1. 找 gVisor 和 Firecracker 更新的性能对比数据（两者都在 2020 年后大幅迭代，尤其 gVisor 网络性能官方文档提到已提升约 8 倍），避免拿本文六年前的绝对数字做选型依据；
  2. 精读清单里的 LightVM（Manco et al. 2017，本文 §9 提到的同类"窄接口"系统），补齐"容器可以比 VM 更快更密"这条经典论证的原始出处；
  3. 如果我们平台评估过 gVisor 作为某类任务的隔离后端，应该补一份类似本文方法论的内部覆盖率/微基准测试，而不是直接采信 Google 官方文档的数字。

## 相关

- 相关概念：[[gvisor]]、[[firecracker]]、[[microvm-sandbox]]、[[kata-containers]]
- 相关笔记：[[2020-agache-firecracker]]（Firecracker 原始设计论文，本文的对比对象之一）、[[2022-li-rund]]（安全容器高密度优化，同属 B 类隔离运行时清单）
- 与母论文的关系：**本文并不是 [[2609.22978]]（DSec）实际引用的参考文献**——检索 DSec 全文与参考文献列表，其 §9 "Lightweight isolation" 只点名了 microVM（Agache et al.）、Kata Containers、library OS、WebAssembly、unikernel、nested kernel、nested virtualization 几条路线，完全没有提到 gVisor 或本文。阅读清单把本文标注为 "P3：Firecracker 与 gVisor 的内核路径/性能对比，补上 gVisor 这一支"，即它是清单维护者主动补充的延伸阅读，用来填补 DSec 自己隔离路线综述里遗漏的 gVisor 这一支，而不是 DSec 论证链条的一部分。本文与母论文的实质联系在于：DSec §2.2 把"容器"和"microVM"列为四种沙箱后端中的两种，用的权衡描述（容器隔离弱但快、microVM 隔离强但慢）与本文的谱系框架（图 1）完全一致，本文相当于给 DSec 未展开的"容器 vs microVM 隔离强度差多少"这个问题提供了内核代码覆盖率层面的量化证据；同时本文里 Firecracker 网络延迟高、写吞吐快但不持久化的发现，与 [[2020-agache-firecracker]] 笔记中转引的 DSec §3.3（microVM 后端不支持 virtio-fs、要靠 OverlayBD+ublk+3FS 补足存储）互相印证——都指向"Firecracker 的性能优势建立在牺牲部分持久化/兼容性保证"这一个共同结论。
