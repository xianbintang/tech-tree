---
title: "QEMU"
aliases: [QEMU/KVM, dynamic binary translation, 动态二进制翻译, TCG]
created: 2026-09-26
updated: 2026-09-26
sources: [2005-bellard-qemu, 2020-agache-firecracker, 2022-li-rund]
---

# QEMU

## 一句话定义

一个可移植的机器模拟器 / VMM：最初（2005）是纯软件的动态二进制翻译器（把目标 CPU 指令翻译成宿主 CPU 指令），2006-2007 年集成 KVM 后成为 Linux 上最主流的"全虚拟化"方案——用 KVM 做 CPU/内存的硬件加速，QEMU 自己负责设备模拟与管理面 [[2005-bellard-qemu]]。

## 为什么对我们重要

QEMU 在本知识库的 dsec-refs 阅读清单里，同时扮演两个角色：（1）母论文 [[2609.22978]]（DSec）四种沙箱后端之一"full-VM"的直接实现技术，专门用于需要完整商用 OS 环境（如 Android VM）或 GUI/图形渲染的任务；（2）[[firecracker]]、[[2022-li-rund]] 等笔记里反复出现的"传统全虚拟化"性能/资源开销对比基线——是我们评估自己沙箱平台"要不要走全虚拟化路线、什么场景才需要"的直接参照系 [[2005-bellard-qemu]]。

## 核心机制 / 主要变体

- **1.0 版本：纯动态二进制翻译（本文，2005）**：把目标 CPU 指令拆成几百种"micro operation"，每个用一小段 C 代码实现并离线交给 GCC 编译；`dyngen` 工具在编译期解析目标文件的符号表/重定位信息，生成一个运行时"拼接器"——用 `memcpy` 把已编译好的机器码片段复制拼接、并 patch 常量参数，避免了传统动态翻译器"每移植一个宿主 CPU 就要重写整个代码生成器"的高成本 [[2005-bellard-qemu]]。支撑"全系统模拟"（完整未修改 OS 跑在虚拟机里）与"用户态模拟"（目标 CPU 编译的 Linux 进程直接跑在不同宿主 CPU 上）两种场景，且宿主/目标 CPU 架构可以不同——这是它区别于同期虚拟化方案（要求宿主/目标同架构）的核心能力。
- **2.0 版本：QEMU/KVM（2006-2007 年后）**：当宿主与目标 CPU 相同架构时，用 KVM 做硬件辅助虚拟化（Intel VT-x/AMD-V），CPU 指令原生执行而非动态翻译，QEMU 退化为纯设备模拟 + 管理面角色。本文 §6 Future Work 已经预告了这个方向（"当宿主和目标相同，可以让大部分代码直接跑"），但 2005 年时尚未实现 [[2005-bellard-qemu]]。这是被 [[firecracker]]、[[2022-li-rund]] 等后续论文当作"传统全虚拟化基线"引用的那个 QEMU，与本文描述的纯软件翻译器不是同一技术阶段，**不能把本文的性能数字套用到"QEMU/KVM 现状"上**。
- **跨 CPU 架构模拟能力在"全虚拟化"式微后依然不可替代**：现代 microVM/容器方案（Firecracker、gVisor）都假设宿主/目标同架构；QEMU 的动态翻译能力（TCG，本文 dyngen 的后继实现）是"在 x86 宿主上跑 ARM/Android guest"这类跨架构场景仍需依赖的技术，DSec 选择 QEMU 做 Android VM 后端正是利用这一点，而非追求更强隔离 [[2005-bellard-qemu]]。

## 工程要点与数字

- 2005 年纯软件翻译器基线：用户态模拟整数代码比原生慢约 4 倍、浮点慢约 10 倍；全系统模拟软件 MMU 额外拖慢约 2 倍；比 Bochs（解释器）快约 30 倍 [[2005-bellard-qemu]]（**历史数字，早于 KVM，不代表现状**）。
- 2020 年 QEMU/KVM（NSDI'20 Firecracker 论文测得）：每 VM 常数内存开销约 131MB（对比 Firecracker 3MB、Cloud Hypervisor 13MB），预配置启动时间比 Firecracker 慢约一倍 [[2020-agache-firecracker]]。
- 作为安全容器 hypervisor 后端（RunD 论文测得，Kata-qemu 配置）：200 容器并发启动耗时 6.85s（对比 RunD 自身 1s、Kata-FC 47.6s、Kata-template 2.98s）[[2022-li-rund]]。

## 争议与矛盾

（暂无；QEMU 在不同笔记中的角色一致——早期纯翻译器与后期 KVM 加速版本是同一项目的两个技术阶段，不构成结论冲突，只需注意区分年代。）

## 开放问题

- 现代 QEMU（TCG + KVM 混合路径）相比本文描述的 dyngen 架构具体演进了什么，本库尚未有笔记覆盖 QEMU 的中间演进历史（TCG 何时替代 dyngen、KVM 集成的具体时间线）。
- DSec 用 QEMU 承载 Android VM 场景时，是否用到 KVM 加速（要求宿主/guest 同为 ARM 或用 Intel HAXM/Houdini 类二进制翻译层），还是纯 TCG 跨架构模拟，母论文未展开，需要进一步调研 Android 模拟器（Cuttlefish/goldfish）现状。

## 相关概念

[[microvm-sandbox]]、[[nested-virtualization]]、[[firecracker]]、[[kata-containers]]

## 相关来源

- [[2005-bellard-qemu]] — QEMU 原始设计论文：dyngen 动态二进制翻译内核的技术细节，2005 年纯软件阶段，是 DSec full-VM 后端的引用出处
- [[2020-agache-firecracker]] — 把 QEMU/KVM 作为传统全虚拟化基线，给出 2020 年的内存开销/启动时间对比数字
- [[2022-li-rund]] — Kata-qemu 配置作为安全容器场景下 QEMU 的并发启动性能基线
