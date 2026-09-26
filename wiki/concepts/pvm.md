---
title: "PVM"
aliases: [PVM hypervisor, 影子页表嵌套虚拟化, Alibaba/Ant nested virtualization]
created: 2026-09-26
updated: 2026-09-26
sources: [2023-huang-pvm]
---

# PVM

## 一句话定义

阿里巴巴/蚂蚁集团联合研发、跑在 KVM guest（*L₁*）里的纯软件 guest hypervisor：不依赖任何硬件虚拟化扩展、对宿主 host hypervisor（*L₀*）完全透明，用"去特权化 *L₂* + 共享内存 switcher + 高效影子页表（PVM-on-EPT）"三件套，让[[nested-virtualization|嵌套虚拟化]]在内存虚拟化上的开销接近硬件辅助单层虚拟化，已在阿里云日均承载 10万+ 安全容器、40万+ vCPU [[2023-huang-pvm]]。

## 为什么对我们重要

PVM 代表[[microvm-sandbox|安全容器]]隔离谱系里一个和 [[firecracker]]（microVM）、[[kata-containers]]/[[rund]]（VM 套容器）都不同的取舍点：**它解决的是"host 没有 hypervisor 控制权"这个约束**——当我们的沙箱需要跑在从公有云 IaaS 租来的 VM 里（而不是自己控制的裸机），无法要求宿主开放 `/dev/kvm` 或获得 root 权限时，PVM 证明了纯软件、guest 内自建 hypervisor 的方案在生产环境下可行，是我们评估"无 host 权限场景如何仍提供强隔离"这个问题时必须记录的候选方案。母论文 [[2609.22978]]（DSec）在 §9 把"nested virtualization (Huang et al., 2023)"列为多种隔离范式之一，但 DSec 自己的评测明确"排除嵌套虚拟化，microVM 直接跑裸机"，说明 DSec 团队视其为会引入额外开销、需要主动规避的路线，而非自身架构的组成部分。

## 核心机制 / 主要变体

- **去特权化 + 共享内存 switcher**：把 *L₂*（容器所在的嵌套 guest）的用户态和内核态都压到最低特权级 h_ring3，靠独立页表区分二者；*L₁*、*L₂* 用户、*L₂* 内核三方在恒定虚拟地址处共享一段代码/数据区（switcher），syscall/hypercall/interrupt/exception 全部通过 switcher 直接陷入 *L₁* 内的 PVM，不必像传统嵌套虚拟化那样先陷入 *L₀* 再转发 [[2023-huang-pvm]]。
- **PVM-on-EPT 影子页表**：*L₂* 的内存虚拟化完全收敛在 *L₁* 内部处理，*L₀* 只需要像对待普通 VM 一样维护一层 EPT，对 PVM 的存在无感知、不用改宿主代码。配套三项优化：prefault（内核更新只读 GPT 后主动预取更新影子页表）、PCID 映射（给 *L₂* 用户/内核分配独立 PCID 避免粗粒度 TLB flush）、细粒度 SPT 锁（拆分全局 mmu_lock 为三类更细粒度的锁）[[2023-huang-pvm]]。
- **核心洞察是"降低单次 world switch 成本"而非"减少切换次数"**：PVM-on-EPT 相比业界标准 EPT-on-EPT 只少 2 次 world switch（2n+4 vs 2n+6），但把每次切换的成本从 1.3μs 压到 0.179μs（十倍量级），因为切换收敛在同一特权环境内、不经过硬件 root/non-root 模式切换 [[2023-huang-pvm]]。
- **安全模型**：secure container 只需约十几个 hypercall 接口即可与 *L₁* host 内核交互（vs 默认 seccomp 下 250+ 系统调用），且攻击者需要先后攻破 *L₂* 内核与 *L₁* hypervisor 才能触及 *L₁* host 内核；PVM 让 *L₀* 保持"瘦"，不需要为嵌套虚拟化做特殊处理，进一步收窄云厂商侧攻击面 [[2023-huang-pvm]]。

## 工程要点与数字

- World switch 成本：PVM 0.179μs，业界标准 EPT-on-EPT 1.3μs，单层硬件辅助虚拟化 0.105μs（嵌套场景下 PVM 比 EPT-on-EPT 快约 7x）[[2023-huang-pvm]]。
- 嵌套场景 5 类特权操作平均往返延迟，PVM 相比 EPT-on-EPT 平均降低超过 75% [[2023-huang-pvm]]。
- 真实应用高并发下差距可达两个数量级：Kbuild 16 路并发编译，EPT-on-EPT 1421s vs PVM 370s（约 3.8x）；SPECjbb2005 16 路并发吞吐，EPT-on-EPT 崩到 1 kbops vs PVM 15 kbops（接近单层裸机的 16 kbops）[[2023-huang-pvm]]。
- 已知短板：syscall（get_pid）延迟上 PVM 不开 direct switch 优化时反而比硬件辅助慢最多 7x，开启后收窄到约 1.3x——纯软件方案在"硬件本可零开销处理"的场景下有固有代价 [[2023-huang-pvm]]。
- 生产规模：阿里云日均 10万+ 安全容器、40万+ vCPU；过去一年推动 36% 用户从裸机实例迁移到 PVM 承载的通用实例；迁移到 PVM 的 Spark 负载平均性能提升 22.6%（但论文承认这批 PVM 服务器用了更新一代处理器，数字里混有硬件代际差异）[[2023-huang-pvm]]。

## 争议与矛盾

暂无跨来源数字冲突。但存在一个**方法论上的疑点**（论文自身分析不充分，值得记录）：Fig 10 中 NST-prefault/NST-pcid/NST-lock 三个 ablation 列的具体含义（"仅应用该优化"还是"移除该优化"）论文未明确说明，导致"哪项优化贡献最大"这个结论的数字依据不够扎实 [[2023-huang-pvm]]。

## 开放问题

- PVM 是否已开源、是否有开源实现或后续论文可供复现，笔记写作时未找到公开代码仓库。
- fork/mmap 密集型工作负载（频繁产生大量 *L₂* 缺页）下的实际开销，论文承认是短板但未评测；这恰好是很多 agent 工作负载（跑测试、编译、起子进程）的典型特征，需要用真实 agent workload 验证。
- 双影子页表（*L₂* 用户/内核分别维护）的写保护（WP）同步开销，论文列为未解决的 future work，尚无具体数字。
- PVM 与 [[microvm-sandbox]]、[[kata-containers]] 等路线在同等密度/并发目标下的直接对比（同一评测环境、同一工作负载）尚无数据，两条路线目前只能分别看各自论文的生产数字，不能直接比较。

## 相关概念

[[nested-virtualization]]、[[microvm-sandbox]]、[[firecracker]]、[[kata-containers]]、[[rund]]

## 相关来源

- [[2023-huang-pvm]] — PVM 原始设计论文（SOSP '23），去特权化 switcher 与 PVM-on-EPT 影子页表设计、微基准/系统基准/真实应用评测、阿里云生产数字的出处
