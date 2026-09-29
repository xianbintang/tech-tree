---
title: "gVisor"
aliases: [Google gVisor, runsc, Sentry, 用户态内核沙箱]
created: 2026-09-26
updated: 2026-09-26
sources: [2020-anjali-firecracker-gvisor]
---

# gVisor

## 一句话定义

Google 开源的 OCI 兼容沙箱容器运行时（`runsc`）：用 Go 写的用户态内核 *Sentry* 拦截并重新实现容器发出的绝大多数系统调用，在不引入完整 guest 虚拟机的前提下把应用与宿主内核隔开，是介于 Linux 容器与 [[firecracker]] 之类 microVM 之间的"paravirtualization"路线 [[2020-anjali-firecracker-gvisor]]。

## 为什么对我们重要

gVisor 是我们研究方向关键词表（`config/interests.yaml`）里明确列出的隔离方案之一，也是 dsec-refs 阅读清单 B 类"隔离运行时/microVM"专门补读的一支——母论文 [[2609.22978]]（DSec）自己的隔离路线综述（§9）只提到 microVM、Kata、library OS、WebAssembly、unikernel、nested virtualization，完全没有讨论 gVisor，这是 DSec 论证链条里的一个空白，需要独立资料补齐才能完整评估"容器 vs microVM vs paravirtualization"这三条路线的取舍。

## 核心机制 / 主要变体

- **Sentry**：用户态内核，Go 实现，运行在受限 seccomp 容器里；容器发出的系统调用全部被重定向到 Sentry，由 Sentry 自己实现其中 237/350 个（2019-11 时基于 Linux 5.3.11 的统计），Sentry 本身只向宿主内核发起 53 个（关闭 host networking）或 68 个（开启后）白名单系统调用 [[2020-anjali-firecracker-gvisor]]。
- **两种系统调用拦截方式**：*ptrace-mode* 用内核 ptrace 转发系统调用；*KVM-mode* 用 KVM 在系统调用到达 Linux 内核前拦截转发给 Sentry，性能优于 ptrace 模式，是 gVisor 官方文档推荐的生产配置 [[2020-anjali-firecracker-gvisor]]。
- **Gofer**：每个容器伴生一个 Gofer 进程，代理 Sentry 对宿主文件系统的访问，即便 Sentry 被攻破也不能直接读写宿主文件；可选叠加 tmpfs 做完全隔离，或开放共享文件访问模式与宿主/其它容器共享数据 [[2020-anjali-firecracker-gvisor]]。
- **netstack**：Go 实现的用户态网络栈，TCP/UDP/IP4/IP6/ICMP 的连接状态、控制消息、分包组装全部在 Sentry 内完成，不依赖宿主内核共享网络状态；也可切换为宿主网络栈换取更高性能，代价是隔离性下降 [[2020-anjali-firecracker-gvisor]]。
- **内存管理是两级页表**：应用→Sentry 一级，Sentry→宿主 一级；Sentry 把宿主 mmap 请求按 16MB 粒度合并，1GB 内存请求只需 64 次宿主 mmap 调用，理论上大幅减少了宿主内核调用次数，但小粒度（4KB）分配/释放的实际耗时反而是四个对比平台里最差的，因为双层页表管理的代码路径本身更重 [[2020-anjali-firecracker-gvisor]]。

## 工程要点与数字

- 系统调用白名单：不开 host networking 时 53 个，开启后 68 个（宿主内核共 350 个入口）；作为对比，[[firecracker]] 的白名单是 36 个，比 gVisor 更紧 [[2020-anjali-firecracker-gvisor]]。
- 宿主内核代码覆盖率（四类微基准 union，宿主内核共 806,318 行）：gVisor 91,161 行（11.31%），是原生 Linux（63,163 行/7.83%）、Firecracker（77,392 行/9.59%）、LXC（90,595 行/11.23%）四者中**最高**——尽管把大部分系统调用实现挪进了用户态 Sentry [[2020-anjali-firecracker-gvisor]]。
- 网络性能是四个平台里最弱的一环：单实例带宽仅 0.805Gbps（对比 Firecracker/宿主约 9.4-9.5Gbps），10 实例聚合到 3.294Gbps；启用 host networking 后单实例提升到 3.03Gbps 仍是最慢；RTT 延迟 319μs（宿主 146μs、LXC 149μs，但比 Firecracker 的 371μs 略好）[[2020-anjali-firecracker-gvisor]]。
- 小粒度内存操作代价高：4KB 粒度 mmap+touch+munmap 1GB 数据耗时 7.4s，是宿主（500ms）、LXC（550ms）、Firecracker（650ms）的约 10 倍；大粒度（1MB）时才追平其它平台 [[2020-anjali-firecracker-gvisor]]。
- 文件写吞吐是四个平台里最慢的（140-300MB/s，因走 overlayfs 叠加 ext4，元数据开销重）；读吞吐（缓存清空后）与宿主/LXC 接近（约 150MB/s）[[2020-anjali-firecracker-gvisor]]。
- CPU 计算类负载（sysbench、LLCProbe）性能与宿主/LXC/Firecracker 几乎一致，隔离层对纯计算几乎零性能代价 [[2020-anjali-firecracker-gvisor]]。

## 争议与矛盾

暂无跨来源数字冲突（本页目前仅有一篇来源）。

## 开放问题

- 本页数字来自 gVisor release-20200127.0（2020 年 1 月版本），六年间 gVisor 网络性能等已有大幅迭代（论文自述相比更早的 release-20190304 版本网络吞吐提升近 800%），当前版本的真实数字需要独立验证，不能直接引用本页数字做选型依据。
- gVisor 与 [[microvm-sandbox]]（Firecracker）在同等密度/并发目标下没有第三方在同一评测环境下做过直接对比（[[microvm-sandbox]] 页开放问题里也提到这一点），本页只能提供"两者各有短板、没有全面占优者"的定性结论。
- 未找到 gVisor 在 agent/RL 训练沙箱场景（长生命周期、有状态、高并发文件 IO）下的公开评测数据，本页数字均来自 serverless 短生命周期场景的微基准，外推到我们的实际工作负载需要自己实测。

## 相关概念

[[microvm-sandbox]]、[[firecracker]]、[[kata-containers]]

## 相关来源

- [[2020-anjali-firecracker-gvisor]] — 唯一来源：gVisor 与 Firecracker 的内核代码覆盖率 + 微基准对比研究（VEE'20），本页几乎所有事实与数字均出自此文
