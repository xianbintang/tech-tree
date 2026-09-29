---
title: "PVM: Efficient Shadow Paging for Deploying Secure Containers in Cloud-native Environments"
type: paper
id: "2023-huang-pvm"
source_url: https://doi.org/10.1145/3600006.3613158
authors: [Hang Huang, Jiangshan Lai, Jia Rao, Hui Lu, Wenlong Hou, Hang Su, Quan Xu, Jiang Zhong, Jiahao Zeng, Xu Wang, Zhengyu He, Weidong Han, Jiang Liu, Tao Ma, Song Wu]
affiliations: [Alibaba Group, Ant Group, University of Texas at Arlington, Huazhong University of Science and Technology]
published: 2023-10-23
created: 2026-09-26
tags: [sandbox, nested-virtualization, shadow-paging, kvm, isolation, secure-container]
concepts: [pvm, nested-virtualization, microvm-sandbox]
rating: 4
issue: 22
parent: "2609.22978"
---

# PVM: Efficient Shadow Paging for Deploying Secure Containers in Cloud-native Environments

> 阿里/蚂蚁生产系统：不依赖硬件嵌套虚拟化支持、对宿主 hypervisor 透明的纯软件 guest hypervisor，用高效影子页表把嵌套虚拟化的内存虚拟化开销降到接近硬件辅助单层虚拟化的水平，已跑 10万+ 安全容器/40万+ vCPU。

## 元信息

- 机构：阿里巴巴集团、蚂蚁集团、University of Texas at Arlington、华中科技大学
- 发表：ACM SIGOPS 29th Symposium on Operating Systems Principles（SOSP '23），2023-10-23
- 链接：[ACM DL](https://doi.org/10.1145/3600006.3613158)（无公开 code_url）
- 对比基线：单层虚拟化 `kvm-ept (BM)`（硬件辅助，裸机）、`kvm-spt (BM)`（软件影子页表，裸机）、`pvm (BM)`（PVM 单层）；嵌套虚拟化 `kvm-ept (NST)`（业界标准做法 EPT-on-EPT）、`pvm (NST)`（PVM 嵌套）。同属"安全容器"路线的锚点系统：[[firecracker]]、[[kata-containers]]

## 要解决的问题

云上"安全容器"（容器跑在轻量 VM 里获取强隔离）在第三方要在 IaaS 云租来的 VM 里再跑一层容器 VM 时，需要**嵌套虚拟化**（host hypervisor *L₀* 之上跑 guest hypervisor *L₁*，*L₁* 再跑容器所在的 *L₂* guest）。现有主流方案 **EPT-on-EPT**（用 Intel EPT/AMD NPT 硬件辅助两层地址转换）依赖 *L₀* 深度参与每一次 *L₂*↔*L₁* 的切换（world switch），带来三个问题：

- **世界切换又多又贵**：4 级页表下一次 *L₂* 缺页最多触发 14 次 world switch、7 次陷入 *L₀*；论文实测嵌套场景下一次 world switch（1.3μs）比单层虚拟化（0.105μs）贵一个数量级；内存密集型基准测得嵌套虚拟化相比单层最多慢两个数量级（Fig 2）。
- **架构复杂度与攻击面上升**：*L₀* 必须为 *L₁* 模拟 VMX（VMCS shadowing、EPT 合并），"胖" host hypervisor 扩大了云厂商的攻击面；且一旦 *L₂* 在跑，*L₁* 就不能被迁移/挂起。
- **云厂商支持有限**：很多公有云不支持或严格限制租户 VM 内的嵌套虚拟化，且与 AMD SEV、Intel TDX 等机密计算特性不兼容。

论文的定位：嵌套虚拟化传统上是为了让**未修改**的 guest hypervisor（*L₁*）能跑起来而设计的，但安全容器场景的真实需求只是"给容器一个足够轻量但强隔离的边界，使其能部署在任意 IaaS 云上"——不需要 *L₁* 是通用未修改 hypervisor，因此可以为这个更窄的目标重新设计一个专用的、软件化的 guest hypervisor。

## 方法

PVM 是一个跑在 *L₁*（KVM guest）里的软件 guest hypervisor，不依赖任何硬件虚拟化扩展（不用 Intel VMX 指令做 *L₂*↔*L₁* 切换），对 *L₀* host hypervisor 完全透明（*L₀* 眼里 *L₁* 就是一个普通 VM），因此**不需要修改宿主 hypervisor、可与普通 VM 混跑在同一台物理机**。三个核心设计：

- **去特权化 + 共享内存 switcher**（§3.1-3.2）：不同于传统嵌套虚拟化把 *L₂* 的 guest 内核放在 ring 0、用户态放在 ring 3（都在 non-root 模式），PVM 把 *L₂* 的用户态和内核态**都压到最低特权级 h_ring3**，通过独立页表区分二者（效仿新一代 x86 去掉 ring 1/2 的趋势，如 AMD 与未来 Intel x86-S）。PVM 在 *L₁* 与 *L₂* 用户/内核之间共享一段**恒定虚拟地址**的代码/数据区（switcher：per-CPU syscall entry + 类 VMCS 的 switcher state + 定制 IDT），并借鉴 KPTI 思路用独立页表隔离 switcher 本身，使 *L₂* 的 syscall、hypercall、interrupt、exception 全部通过 switcher 陷入 PVM（*L₁*），而不必像传统方案那样先陷入 *L₀* 再转发。同时用 22 个 hypercall 覆盖高频特权指令、Linux 已有的 pv_cpu_ops/pv_mmu_ops/pv_irq_ops 半虚拟化接口处理敏感指令；额外设计了 **direct switch**（用户↔内核 syscall 往返可以绕开完整的 hypervisor 介入路径，靠 sysret hypercall 直接切换）。
- **PVM-on-EPT 影子页表**（§3.3.2，对应论文标题的 "shadow paging"）：与传统 SPT-on-EPT（*L₁* 用软件影子页表合并 *L₂*/*L₁* 两级页表，每次 *L₂* 缺页都要先经 *L₀* 转发）不同，PVM 把 *L₂* 的内存虚拟化**完全收敛在 *L₁* 内部处理**，*L₀* 只需要像对待普通 VM 一样维护 EPT01（*L₁* 物理地址→*L₀* 物理地址），对 PVM 的存在无感知、不用改代码。一次 *L₂* 缺页在 PVM-on-EPT 下只需 `2n+4` 次 world switch（n 为 *L₂* 页表级数），略少于 EPT-on-EPT 的 `2n+6`，但**关键差异在于每次 switch 便宜一个数量级**（PVM 0.179μs vs EPT-on-EPT 1.3μs vs 单层硬件辅助 0.105μs）——因为 PVM 的切换只是 switcher 内部的特权级/页表切换，不涉及 non-root/root 模式的硬件级世界切换。三项配套优化：① **prefault**：*L₂* 内核更新完只读的 GPT2 后，PVM 主动预取更新 SPT12，避免用户态紧接着再触发一次缺页；② **PCID 映射**：把 *L₁* 的空闲 PCID（32-63）分配给 *L₂* 用户/内核各自使用，避免整个 *L₂* guest 共享一个 VPID 导致的粗粒度 TLB flush；③ **细粒度 SPT 锁**：把原本单一全局 `mmu_lock` 拆成 inter-shadow-page 的 meta-lock、intra-shadow-page 的 per-page pt_lock、reverse-mapping 的 per-frame rmap_lock 三类锁，提高并发缺页处理的并行度。
- **中断走 *L₀*，但只经一次**（§3.3.3）：CPU 和内存虚拟化可以完全在 *L₁* 内闭环，但中断必须先触发硬件 VM Exit 到 *L₀*（这一步硬件自动完成、PVM 无法绕开），随后 PVM 用定制 IDT 把中断注入 *L₂* 全部在 *L₁* 内完成，不像 EPT-on-EPT 那样后续处理还要多次陷入 *L₀*。为让 *L₁* 知道 *L₂* 当前中断是否使能，PVM 在 *L₂*/*L₁* 间维护一个 8 字节共享结构虚拟化 RFLAGS.IF 标志位。

## 实验与结果

评测覆盖微基准、LMbench 系统基准、四个真实应用（Kbuild、Blogbench、SPECjbb2005、Fluidanimate）、Cloud Bench Suite，以及生产数据。

- **World switch 成本**（§4.1）：嵌套场景下 5 类特权操作（hypercall、异常、MSR 访问、CPUID、PIO）的平均往返延迟，PVM 相比硬件辅助的 EPT-on-EPT **平均降低超过 75%**——因为 EPT-on-EPT 每次特权操作要陷入 *L₀* 两次，PVM 只需一次且更便宜的陷入 *L₁*。
- **Syscall 延迟的代价**（Table 2）：get_pid 系统调用上 PVM 反而比硬件辅助方案**慢**——不开 direct switch 时最多慢 7x（KPTI 开启），开启 direct switch 优化后差距收窄到约 1.3x；这是纯软件方案在"硬件本可以零开销处理"的场景下的固有代价，论文承认还在开发更进一步的优化。
- **缺页处理扩展性**（Fig 10）：4GB 工作集、1-32 并发进程的内存密集微基准，`kvm-ept (NST)` 从 1 进程的 10s 恶化到 32 进程的 149s；`pvm (NST)`（全部三项优化）在 32 进程时仅 25s，与单层硬件辅助 `kvm-ept (BM)` 的 12s 处于同一数量级，远好于同样嵌套但去掉三项优化中某一项的对照列（NST-prefault/NST-pcid/NST-lock 分别为 130s/120s/28s）——论文文字说明"单独应用细粒度锁优化就已带来主要收益，prefault 与 PCID 进一步叠加提升"，但这三列具体是"仅保留该优化"还是"移除该优化"论文没有明确说明，数字的因果解读需谨慎（见"局限与疑点"）。
- **真实应用高并发下的量级差距**（Fig 11）：Kbuild 编译在 16 路并发时，`kvm-ept (NST)` 耗时 1421s，`pvm (NST)` 仅 370s（约 3.8x）；SPECjbb2005 16 路并发吞吐，`kvm-ept (NST)` 崩到 1 kbops，`pvm (NST)` 保持 15 kbops（接近单层裸机的 16 kbops）——论文称这是"最多两个数量级"的提升，根源是 `kvm-ept (NST)` 高并发下 *L₀* 变成瓶颈，而 PVM 把 *L₂* 缺页/中断处理都收敛到各自独立的 *L₁* 内、不再对 *L₀* 施压。
- **生产落地（§4.4）**：PVM 已被阿里云用于替代裸机实例承载安全容器，当前日均运行**超过 10万个安全容器、40万+ vCPU**，覆盖用户自定义 serverless 函数、Spark 数据分析、离线批处理等场景；过去一年推动 **36% 的用户从裸机实例迁移到（PVM 承载的）通用实例**；迁移到 PVM 服务器的 Spark 负载平均性能提升 22.6%（论文自己指出这部分 PVM 服务器用了更新一代处理器，因此这个数字里混有硬件代际差异，不能完全归因于 PVM）。
- **安全性讨论（§5）**：PVM 上的安全容器攻击面比传统共享内核容器更窄——只需约十几个 hypercall 接口（vs 默认 seccomp 下 250+ 系统调用），且攻击者需要先后攻破 *L₂* 内核与 *L₁* hypervisor 才能触及 *L₁* host 内核；同时 PVM 让 *L₀* 保持"瘦"（不需要为嵌套虚拟化做特殊处理），进一步收窄云厂商侧的攻击面。

## 局限与疑点

- **三项优化的 ablation 数字语义不清晰**：Fig 10 的 NST-prefault/NST-pcid/NST-lock 三列，论文正文只用一句话定性描述（"锁优化贡献最大、prefault 和 PCID 进一步提升"），没有明确说明每一列是"仅应用该优化"还是"应用除该优化外的其余优化"，也没有给出三项优化各自独立的收益占比——和 [[rund]] 论文同样存在"缺少清晰 ablation"的问题。
- **fork/mmap 密集型负载仍是软件方案的短板**（作者自己承认，§5）：频繁创建大量小内存区域（如 fork、批量小 mmap）会产生大量 *L₂* 缺页，PVM 必须逐个陷入软件处理，而硬件辅助方案下 guest 可以完全在硬件层自行处理，不需要陷入。论文提出的解法（switcher 区分 guest page fault 与 shadow page table fault）在成文时仍是 future work，未评测。
- **双影子页表的写保护（WP）开销未解决**：PVM 为 *L₂* 用户/内核分别维护独立 SPT 以隔离二者，但同步 GPT 与 SPT 依赖 WP 触发的 VM Exit，双份 SPT 意味着双份 WP 开销；论文承认这是明确的在研问题（探索去掉 WP、guest 与 hypervisor 协作维护页表），本文尚未给出方案或数字。
- **Spark 生产数字有混杂变量**：22.6% 的 Spark 性能提升是在"PVM 服务器用了更新一代处理器"的前提下测得，论文自己承认如果在同代硬件上对比，PVM 相对裸机的真实增量应该更小，具体多少未知。
- **一处评测异常未展开解释**：Fig 12 高密度场景下 `kvm-ept (NST)` 因"未能连接到 RunD 容器运行时"而崩溃，论文只有一句话带过，没有分析崩溃根因是嵌套虚拟化本身的问题还是 RunD 集成问题，可能影响该组对比数字的可信度。

## 对我们的启发

- **嵌套虚拟化是 microVM（[[firecracker]]）、VM 套容器（[[kata-containers]]/[[rund]]）之外的第三种隔离取舍点，专门解决"host 没有 hypervisor 权限"这个约束**：如果我们的沙箱平台未来要跑在租来的公有云 IaaS 虚拟机上（而不是自己控制的裸机），Firecracker/microVM 路线通常需要宿主机开放 `/dev/kvm` 或至少有 root 权限做 KVM 虚拟化，这在"VM 里再跑 VM"的场景下往往拿不到；PVM 证明了纯软件、guest 内自建 hypervisor、对宿主完全透明的方案是可行的生产路径，值得作为"我们平台跑在无 host 权限环境下如何仍然提供强隔离"这个问题的候选方案记录下来。
- **本文最可迁移的洞察不是"减少 world switch 次数"而是"降低单次 world switch 的成本"**：EPT-on-EPT 相比 PVM-on-EPT 只多 2 次 switch（2n+6 vs 2n+4），但 PVM 靠把切换收敛在同一特权环境内（不经过硬件 root/non-root 模式切换）把单次成本从 1.3μs 压到 0.179μs，是接近 7x 的差距、且在高并发下被放大到两个数量级。这提醒我们评估自己沙箱平台任何"陷入-处理"路径（不限于嵌套虚拟化，也包括我们自己 microVM/容器运行时里的 vmexit、seccomp 陷入、agent-host RPC）时，要同时测"次数"和"单次成本"两个维度，很多时候优化单次成本的天花板比减少次数更高。
- **fork/mmap 密集型工作负载是这类软件虚拟化方案的已知弱点，而这恰好是很多 agent 工作负载的典型特征**（跑测试套件、编译、起子进程执行 shell 命令）：如果我们评估 PVM 类方案或任何依赖软件缺页处理的隔离机制，必须用真实 agent workload（而非论文里的 LMbench/SPECjbb）实测 fork/exec 密集场景的开销，不能直接套用论文里"实际应用中这种模式很少见"的假设。
- Follow-up 建议（可转 issue）：
  1. 关注 PVM 是否已开源、是否有后续论文/补丁解决"去掉 WP 开销"和"direct paging"这两个作者明确列为 future work 的问题；
  2. 评估我们平台是否存在"需要在无 host 权限的租用 VM 里提供强隔离"的实际场景，如果有，把 PVM 列为候选方案做技术验证（目前未见开源实现，可能需要联系作者或复现关键设计）；
  3. 用我们自己的 agent 评测负载（如 SWE-bench、Terminal-Bench 里的编译/测试任务）复测一遍"fork/exec 密集型场景下软件虚拟化的开销"，验证论文 §5 "这类访问模式在真实应用中很少见"的假设是否适用于 agent 训练场景。

## 相关

- 相关概念：[[pvm]]、[[nested-virtualization]]、[[microvm-sandbox]]
- 相关笔记：[[2020-agache-firecracker]]、[[2022-li-rund]]（同属"安全容器"路线，但走 microVM/VM-套容器而非嵌套虚拟化）
- 与母论文的关系：DSec（[[2609.22978]]）在 §9 Related Work 的 "Lightweight isolation" 一段把本文列为多种隔离范式之一——"microVMs (Agache et al., 2020) or VM-backed kata-containers (Kata Containers, 2017), library OSes ..., unikernels ..., nested kernels ..., **and nested virtualization (Huang et al., 2023)**"，并总结这些方案"offer different trade-offs among isolation, compatibility, and performance"，DSec 自己不提出新隔离机制，而是把多种沙箱后端整合到统一平台供调用方按任务选择。这是一处点名式引用，没有展开对比。更值得注意的是 DSec §8.1 的实验设置明确写道：**"Hardware. To preclude nested virtualization, our microVMs execute directly on bare-metal hardware."**——即 DSec 自己的 microVM 后端评测特意避开嵌套虚拟化、直接跑裸机，把"容器化"对比组放在 QEMU 虚拟机里（而非嵌套 microVM），说明 DSec 团队把嵌套虚拟化视为一种会引入额外开销、需要在评测中主动规避的变量，而不是他们自己会采用的沙箱后端；PVM 在 DSec 的知识框架里更多是"这条路线存在且已有生产级方案（阿里云）"的背景知识，而非 DSec 架构本身的组成部分。
