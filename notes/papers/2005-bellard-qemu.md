---
title: "QEMU, a Fast and Portable Dynamic Translator"
type: paper
id: "2005-bellard-qemu"
source_url: https://www.usenix.org/conference/2005-usenix-annual-technical-conference/qemu-fast-and-portable-dynamic-translator
authors: [Fabrice Bellard]
affiliations: []
published: 2005-04-10
created: 2026-09-26
tags: [full-vm, emulation, dynamic-translation, virtualization, sandbox]
concepts: [qemu, microvm-sandbox]
rating: 3
issue: 22
parent: "2609.22978"
---

# QEMU, a Fast and Portable Dynamic Translator

> 一个可移植的动态二进制翻译器：把目标 CPU 指令拆成几百种"micro operation"，用 GCC 离线编译后在运行时拼接成宿主机代码，让 QEMU 能在六种宿主 CPU 上模拟四种目标 CPU 的完整系统或用户态进程。

## 元信息

- 机构：无（Fabrice Bellard 个人项目，论文未列机构）
- 发表：FREENIX Track，2005 USENIX Annual Technical Conference（2005-04-10，Anaheim, CA）
- 链接：[USENIX 论文页](https://www.usenix.org/conference/2005-usenix-annual-technical-conference/qemu-fast-and-portable-dynamic-translator) · [Code（现状）](https://github.com/qemu/qemu) · [原始发布页](http://bellard.org/qemu)（§7，2005 年时的地址）
- 对比基线：Bochs（纯解释型 x86 模拟器）、valgrind --skin=none（手写的 x86→x86 动态翻译器）
- 注意：这篇论文写于 2005 年，**早于 KVM（2006-2007 年并入 Linux/QEMU）**。本文描述的是纯软件的动态二进制翻译技术（后来演化为 QEMU 的 TCG），不涉及硬件辅助虚拟化；"virtualization" 在本文里只出现在 §6 的 Future Work，作为尚未实现的方向。今天被称为"QEMU/KVM"、在 [[firecracker]]、[[2022-li-rund]] 等笔记里作为"传统全虚拟化 VMM"基线的 QEMU，其硬件加速能力来自后续加入的 KVM 后端，本文只是这套系统最早的、纯模拟器阶段的设计文档。

## 要解决的问题

2005 年之前的机器模拟器面临一个两难：解释器（如 Bochs）足够简单可移植但速度慢（本文测得 QEMU 全系统模拟比 Bochs 快约 30 倍）；动态翻译器速度快，但传统实现（如 [1] 引用的 selective inlining 方案）每移植一个新宿主 CPU 都要重写整个代码生成器——工作量和给 C 编译器加一个新后端相当，导致这类工具难以支持"多目标 CPU × 多宿主 CPU"的组合爆炸。QEMU 要解决的核心问题是：**如何做一个动态翻译器，让"移植到新宿主"这件事的复杂度大幅低于传统方案**，同时支持完整操作系统模拟（不修改的 Windows/Linux 跑在虚拟机里）和 Linux 用户态跨 CPU 模拟（交叉编译产物在另一种 CPU 上直接跑，用于测试交叉编译器或调试 CPU 模拟器本身）两种场景。

## 方法

**核心思路（§2）**：把动态代码生成的工作尽量挪到编译期，运行时只做"拼接"，而不是运行时生成机器码。

- **Micro operation 拆解**：每条目标 CPU 指令被手工翻译成若干条"micro operation"（如 `movl_T0_r1`、`addl_T0_im`），每个 micro operation 是一小段 C 代码，用少量固定的临时寄存器（T0/T1/T2，通过 GCC 的 static register variable 扩展映射到宿主寄存器）传值。这些 micro operation 的 C 源码用 GCC 离线编译成目标文件——真正的代码生成工作在这一步已经由 GCC 完成。
- **dyngen 工具（§2.3）**：编译期工具，解析 micro operation 目标文件的符号表、重定位项和代码段（依赖宿主目标文件格式：ELF/PE-COFF/MACH-O），定位每个 micro operation 的代码边界，生成一段"运行时代码生成器"——本质是一个大 switch-case，每个 case 对应一种 micro operation，用 `memcpy` 把已编译好的机器码片段复制到输出缓冲区，并用重定位信息现场打补丁常量参数。
- **常量参数处理**：GCC 为每个 micro operation 里的常量参数生成"哑重定位"（`__op_paramN`），dyngen 借此在生成的代码里定位并替换运行时才知道的常量值（例子：PowerPC `addi r1,r1,-16` → micro operation `addl_T0_im` 里的立即数 -16 在运行时被 patch 进复制出的 x86 机器码）。
- **Translated Block（TB）与代码缓存（§3.1）**：以"下一条跳转指令或改变静态 CPU 状态的指令"为界切出基本块（TB），16MB 缓存保存最近使用的 TB，满了就整体 flush（简单但有效）。"静态 CPU 状态"（如 x86 的 protected/real mode、user/kernel mode、操作数宽度）在进入 TB 时被认为已知，用于生成更优代码。
- **固定寄存器分配（§3.2）**：目标寄存器直接映射到内存地址，只有少量临时变量映射到宿主寄存器，牺牲部分性能换取简单性和可移植性（作者预告未来会做动态临时寄存器分配）。
- **惰性条件码求值（§3.3）**：不在每条指令后都计算 x86 的 eflags，而是记录操作数、结果和操作类型（CC_SRC/CC_DST/CC_OP），需要时才按需重建具体标志位；并在 TB 生成时做一次反向扫描，删掉后续代码用不到的条件码赋值。
- **直接块链接（§3.4）**：TB 执行完后用模拟 PC 查哈希表找下一个 TB；如果目标已翻译，直接 patch 跳转指令使其直接跳到下一个 TB（部分宿主架构可以无额外开销地做到）。
- **内存管理（§3.5）**：优先用 `mmap()` 模拟目标 MMU（要求 guest 不使用宿主保留的地址区间，此模式后来被弃用因为不安全）；否则用软件 MMU 在每次内存访问时做地址翻译，并用物理地址索引翻译缓存，避免 MMU 映射变化时整体 flush 代码缓存（但需要重置块链接）。
- **自修改代码处理（§3.6）**：x86 等 CPU 不会主动通知指令缓存失效，QEMU 给已翻译代码对应的宿主页设为写保护，写入触发失效对应 TB；软件 MMU 模式下用页内 bitmap 精确到"哪部分代码真的需要失效"，避免数据写入误伤代码失效判断。
- **精确异常与硬件中断（§3.7-3.8）**：用 `longjmp` 实现异常跳转；不显式存储的状态（如当前 PC）通过在异常模式下重新翻译发生异常的 TB 来恢复；中断通过异步调用重置当前 TB 链接、把执行拉回主循环来处理，避免每个 TB 都做中断检查的开销。
- **用户态模拟（§3.9）**：不做 MMU 模拟（信任宿主 OS 处理内存映射），带通用的 Linux 系统调用转换层处理大小端和 32/64 位差异，每个目标线程映射到一个宿主线程。

## 实验与结果

评测环境未详述具体硬件（论文正文未给出机型），核心对比数据（§5 Performance）：

- 用户态模拟（QEMU v0.4.2）在 BYTEmark 基准上，整数代码比原生慢约 **4 倍**，浮点代码慢约 **10 倍**（作者归因于静态 CPU 状态未包含 x86 FPU 栈指针）。
- 全系统模拟下，软件 MMU 额外带来约 **2 倍**慢化。
- 全系统模拟下 QEMU 比 Bochs（纯解释器）快约 **30 倍**。
- 用户态 QEMU 比 valgrind `--skin=none`（手写 x86→x86 动态翻译器，用于调试）快约 **1.2 倍**。

论文没有给出与同期虚拟化方案（如 VMware、Xen）的直接性能对比，评测范围局限在"动态翻译器之间"和"与纯解释器"两类基线。

## 局限与疑点

- 论文自己在 §6 列出的未决问题：Sparc/Alpha/ARM/MIPS 宿主支持还不成熟；ARM/MIPS 目标的全系统模拟还没做；软件 MMU 性能还能优化；且**明确写道**"当宿主和目标 CPU 相同时，可以让大部分代码直接跑而不翻译"——这正是后来 KVM 硬件辅助虚拟化思路的雏形，但 2005 年这篇论文里只是一句 Future Work，尚未实现。
- 线程支持在脚注 5 里被作者自己评价为"immature due to locking issues"，用户态多线程模拟当时并不可靠。
- 自修改代码处理（写保护 + 失效）和软件 MMU 地址翻译缓存都是经典但有明显开销的机制，论文没有给出这些机制单独的开销数据（只有整体 2x/4x/10x 的汇总数字），无法判断具体是哪个环节占主要开销。
- 这是一篇 2005 年的系统实现论文，此后 QEMU 经历了 TCG（Tiny Code Generator，取代 dyngen）重写和 KVM 集成两次架构级变化；本文描述的 dyngen + micro operation 拼接方案**在现代 QEMU 代码库里已不存在**，只有历史参考价值，不能作为理解当前 QEMU/KVM 性能特征的依据。

## 对我们的启发

- **DSec 用 QEMU 撑起的"full-VM"后端，价值不在虚拟化隔离强度，而在"跨 CPU 架构模拟"这个能力本身**：DSec §2.2 明确把 QEMU 全虚拟机用于"需要完整商用操作系统环境的工作负载，比如通过 QEMU 跑的 Android VM，以及需要 GUI/图形渲染的任务"，而不是作为通用隔离手段（那是 microVM/容器的职责）。这与本文的用户态模拟设计初衷一脉相承——本文强调 QEMU 能做"target CPU 编译的 Linux 进程跑在不同 host CPU 上"，Android 模拟器长期以来正是利用 QEMU 这种跨架构（ARM guest / x86 host）动态翻译能力，而非依赖硬件虚拟化。理解这一点后，我们评估"要不要在平台里接入 QEMU 全虚拟机后端"时，判断标准应该是"是否有跨 CPU 架构模拟需求（移动端 App、旧硬件固件）"，而不是"是否需要更强隔离"——后者用 [[microvm-sandbox]] 或 [[nested-virtualization]] 路线的性价比明显更高。
- **"资源开销最高，只在必须时用"是 DSec 分层沙箱后端设计里 full-VM 的明确定位**：DSec §2.2 把 FnCall/容器/microVM/full-VM 按隔离强度和资源开销排成一个谱系，全虚拟机在最贵的一端，仅用于"依赖 OS 特定 API、移动端运行时行为、或全系统执行"的任务。这提示我们自己的沙箱平台如果要支持类似的"Android/GUI/完整 OS"场景，应该把它做成一个显式的、代价最高的独立后端，而不是试图用 microVM 或容器折中实现——本文的动态翻译开销数据（用户态 4-10 倍慢化）本身就说明"完整模拟"路线的性能天花板远低于硬件辅助虚拟化，只有在必须模拟不同 CPU 架构时才值得付这个代价。
- **QEMU/libvirt 的编排复杂度是我们如果引入 full-VM 后端要单独评估的成本**：DSec §3.3 提到 edge 组件要为 "container、microVM、QEMU-based full VM、FnCall" 四种后端分别处理创建请求，并协调 "QEMU/libvirt VMs" 而非直接操作宿主——相比 [[firecracker]] 单一进程管理单一 MicroVM 的简单模型，QEMU + libvirt 的管理面本身就多一层复杂度，这是我们做后端选型/自建 vs 复用时需要计入的工程成本，而不只是运行时性能开销。
- Follow-up 建议（可转 issue）：
  1. 现代 QEMU（KVM 加速路径）与本文描述的纯 TCG 路径在 CPU 密集型工作负载上的性能差距，需要找更新的资料补充（本文数据是 2005 年纯软件翻译器的历史基线，不能直接引用到"QEMU/KVM 现状"的讨论里，[[firecracker]] 笔记里引用的"QEMU 131MB/VM 内存开销"来自 2020 年 NSDI 论文，与本文无直接关系）；
  2. 如果我们平台确实要支持 Android/移动端 App 沙箱场景，需要专门调研当前 Android 模拟器（Cuttlefish/goldfish）是否仍走 QEMU 动态翻译路径，还是已经切换到硬件辅助方案（如 ARM 主机上直接 KVM 加速）；
  3. 关注 QEMU 从 dyngen 到 TCG 的架构演进历史，理解当前 QEMU 代码生成路径与本文描述的差异，避免团队内部讨论"QEMU 性能"时用错时代的技术细节。

## 相关

- 相关概念：[[qemu]]、[[microvm-sandbox]]
- 相关笔记：[[2020-agache-firecracker]]（把 QEMU 列为传统全虚拟化 VMM 基线，测得 QEMU 每 VM 内存开销约 131MB、启动比 Firecracker 慢约一倍——但这些数字来自 2020 年的 QEMU/KVM，与本文 2005 年的纯软件翻译器不是同一技术阶段）、[[2022-li-rund]]（Kata-qemu 作为最慢的对比基线之一）、[[2023-huang-pvm]]（嵌套虚拟化场景下 QEMU/libvirt 常作为 L1 hypervisor 的软件栈）
- 与母论文 [[2609.22978]] 的关系：DSec §2.2 明确指出 full-VM 后端"通过 QEMU（Bellard, 2005）"实现 Android VM 等需要完整 COTS 操作系统环境的工作负载，以及需要 GUI/图形渲染的任务，是四种沙箱后端（FnCall/容器/microVM/full-VM）里资源开销最高、但对"依赖 OS 专有 API、移动运行时行为、全系统执行"任务不可替代的一层。§3.3 描述 DSec 的 edge 组件统一处理 container、microVM、QEMU-based full VM、FnCall 四类创建请求，并特别指出这类工作负载要协调 "QEMU/libvirt VMs" 而非直接操作宿主机——即 DSec 把 QEMU 当作一个通过 libvirt 编排的、独立于其自研 microVM/容器技术栈的现成方案直接复用，而不是像对待 microVM 那样自研或深度定制。本文作为 DSec 引用的原始出处，提供的是 QEMU 动态二进制翻译内核这一 2005 年设计的技术背景，DSec 本身并未在 fullVM 这条路径上做架构创新，只是把 QEMU/libvirt 作为四种后端之一纳入统一 SDK。
