---
title: "My VM is Lighter (and Safer) than your Container"
type: paper
id: "2017-manco-lightvm"
source_url: https://doi.org/10.1145/3132747.3132763
authors: [Filipe Manco, Costin Lupu, Florian Schmidt, Jose Mendes, Simon Kuenzer, Sumit Sati, Kenichi Yasukata, Costin Raiciu, Felipe Huici]
affiliations: [NEC Laboratories Europe, Univ. Politehnica of Bucharest]
published: 2017-10-28
created: 2026-09-26
tags: [sandbox, microvm, isolation, unikernel, xen, virtualization]
concepts: [lightvm, unikernel, microvm-sandbox, firecracker]
rating: 4
issue: 22
parent: "2609.22978"
---

# My VM is Lighter (and Safer) than your Container

> 容器不安全、VM 太重是伪二选一：把 VM 镶小（unikernel/Tinyx）、把 Xen 控制面重写掉 XenStore 瓶颈（LightVM），VM 也能做到 2.3ms 启动、8000 VM/机密度。

## 元信息

- 机构：NEC Laboratories Europe、罗马尼亚布加勒斯特理工大学
- 发表：SOSP '17（2017-10-28，Shanghai）
- 链接：[ACM DL](https://doi.org/10.1145/3132747.3132763) · [Code/项目页](http://sysml.neclab.eu/projects/lightvm)
- 对比基线：Docker 1.13、标准 Xen 4.8（`xl`/`libxl`/XenStore）、Linux `fork`/`exec` 进程创建；相关路线 [[firecracker]]（同样是"重写极简 VMM/控制面而非裁剪通用方案"的思路，但 LightVM 早三年、基于 Xen 而非 KVM，且不换 hypervisor 只换控制面）

## 要解决的问题

2017 年的多租户虚拟化面临一个被普遍接受的"二选一"：
- **容器**（Docker/LXC）：启动快、密度高、内存开销小，但隔离边界依赖 Linux syscall API——该 API 逐年膨胀（论文 Figure 1：2002 年 220 个系统调用 → 2017 年 378 个），语义复杂、难以彻底收窄，容器逃逸/DoS（fork bomb、fd 耗尽等）持续被曝出。
- **VM**（QEMU/KVM、Xen）：隔离边界退到硬件辅助的 x86 ABI（内存隔离 + CPU 特权环），远比 syscall 面简单、安全边界更好定义，但传统实现笨重——启动秒级、镜像 GB 级、单机只能跑几十到几百个。

作者的核心问题：这个取舍是否是**VM 实现方式**造成的，而不是虚拟化本身的必然代价？如果把 VM 镶小、把控制面重新设计，VM 能否达到容器级的启动时间（毫秒级）、内存占用（几 MB）、单机密度（千级以上）？

## 方法

**两条正交的优化轴**：先压缩 VM 镜像本身（§3），再压缩控制面/toolstack 开销（§4-5）——论文用实验证明单独做第一条不够（§4.2：即便最小的 unikernel VM，随着并发数增加创建耗时仍会指数级恶化），必须两条一起做。

### 镶小 VM 镜像（§3）

- **Unikernel**：把精简 guest OS（Mini-OS，Xen 自带的 toy 内核，无 user/kernel 分离、无 fork/多进程）直接和目标应用链接成单一镜像。论文的 daytime unikernel（TCP daytime server + lwip 网络栈）仅 50 行代码、480KB 镜像、3.6MB 运行时内存，是本文各类实验的下界基准；另有基于 ClickOS（[[microvm-sandbox]] 相关的网络处理 unikernel）的防火墙、TLS 终结 unikernel、基于 Micropython 的 Minipython（类 Lambda 计算服务）。
- **Tinyx**：作者新造的自动化构建系统，围绕单一目标应用生成"够用就好"的精简 Linux 分发（objdump 提取依赖库 + Debian 包管理器裁剪包集合 + BusyBox 补基础工具 + tinyconfig 起点裁剪内核选项，逐项试跑验证不破坏功能）。定位介于 unikernel（性能最好但需要专家移植应用）和通用 Linux VM（兼容性好但笨重）之间：镜像几十 MB、运行内存约 30MB，内核运行时内存 1.6MB（对比作者测的 Debian 内核 8MB）。

### 定位控制面瓶颈（§4）

在 4 核机器上连续起 1000 个 VM（Debian VM / Tinyx / daytime unikernel 三种尺寸），用 ramdisk 消除磁盘 I/O 干扰，测创建时间随并发 VM 数的变化，并对 Xen `xl`/`libxl` 打点分类。结果：
- 即便镜像已经压到 480KB 的 unikernel，创建时间仍随已运行 VM 数**超线性增长**——第 1000 个 unikernel 创建耗时 700ms（对比 Docker/进程创建时间与已有容器/进程数无关）。
- 打点分解显示瓶颈集中在两处：**XenStore 交互**（随 VM 数超线性增长，到 1000 VM 时占 610ms）和**虚拟设备创建**（占大头但基本恒定，约 100ms）。XenStore 慢的原因：协议本身贵（每次读写至少 2 次、常见 4 次软中断+域切换）、guest 名称唯一性检查是 O(n)、设备初始化要开事务，高负载下事务冲突要重试。

这一节的方法论意义：**控制面（toolstack）本身可以是比 hypervisor/guest 更大的性能瓶颈**，且这个瓶颈在小 VM 场景下被放大（因为 VM 本身的开销已经被压缩到很小，创建过程的固定开销占比反而变大）。

### LightVM：Xen 控制面重构（§5）

- **noxs（no XenStore）**：完全绕开 XenStore 这个集中式、类文件系统的注册表。做法是在 hypervisor 里给每个新 VM 开一个只读共享的"设备页"（只有 Dom0 可写），前后端驱动通过这个页面 + 共享内存 + hypercall 直接交换设备信息（event channel id、grant reference 等），不再经过 XenStore 的消息传递协议。迁移场景新增 `sysctl` 伪设备（前后端驱动模式）承载挂起/恢复相关的控制信令。
- **Chaos/libchaos**：替换 `xl`/`libxl` 的精简 toolstack，天然不依赖 XenStore。
- **Split toolstack**：把 VM 创建拆成 *prepare*（后台 daemon 持续跑，做与具体 VM 无关的共性工作——hypervisor 分配 ID、CPU 资源等——预先生成一批 VM "shell" 放进池子）和 *execute*（VM 创建命令触发时，从池子取一个 shell，只做该 VM 特有的工作：解析配置、加载内核镜像、设备初始化）两阶段，思路类似预启动池，但池化的对象是"半成品 VM 壳"而不是"完整 VM"。
- **xendevd**：用一个常驻二进制 daemon 替换传统 Xen 靠 udev 触发 bash 脚本配置虚拟设备（如挂 vif 到网桥）的方式，避免 fork+bash 解释器的启动开销。

四项优化独立可测（Figure 9）：xl（无优化）→ chaos（去掉旧 toolstack 开销）→ chaos+split → chaos+noxs → 全部叠加（LightVM），创建时间从"1000 VM 时近 1s"逐级降到"恒定 3.8-4.1ms"，其中 noxs 单项贡献最大。

## 实验与结果

评测环境：4 核 Xeon E5-1630（128GB DDR4）+ 64 核 AMD Opteron 6376×4（128GB DDR3），Xen 4.8，Docker 1.13。

- **启动/创建时间**（§6.1，Figure 9-11）：LightVM 全优化下 daytime unikernel 创建时间恒定在 3.8ms（1000 个 VM 时仍是 3.8ms），noop unikernel 最低可到 **2.3ms**，与 Linux `fork`/`exec`（约 1ms）同一量级；64 核机器上对比 Docker，LightVM 稳定在 5.5ms/VM，可跑到 **8000 个 VM**，而 Docker 3000 个容器时已到 ~1s/容器并因内存耗尽而失控（无法继续压测）。Tinyx guest 在 750 VM/机（每核 250 个）以内启动时间与 Docker 接近，超过后因 Tinyx 后台任务的 CPU 争抢而变差。
- **Checkpoint/迁移**（§6.2，Figure 12-13）：LightVM save/restore 恒定 ~30ms/~20ms（标准 Xen 需要 128ms/550ms，且随 VM 数增长）；迁移恒定 **60ms**（标准 xl 随 VM 数从 256ms 升到 460ms）。
- **内存footprint**（§6.3，Figure 14）：1000 个 guest 时，Minipython unikernel 与 Docker/Micropython 容器内存占用接近（4.35GB vs 4.6GB），Tinyx 因每 VM 独立内核副本略高（约 18-20GB），远低于完整 Debian VM（约 65GB，即约 65MB/VM）。
- **CPU 占用**（§6.4，Figure 15）：1000 guest 时 unikernel/Tinyx 与 Docker（均 <1%）接近，完整 Debian VM 因自带一堆后台服务爬升到约 25%。
- **四个用例**（§7）：ClickOS 防火墙单机跑 8000 个（64 核机）、1000 个模拟 4G 用户全部落地时人均吞吐仍能到 4Mbps；即时服务实例化场景 ping 时延中位数 13ms（每 25ms 一个新客户端到达时）；TLS 终结场景 Tinyx 吞吐接近裸机进程（约 1400 req/s @1024-bit RSA），unikernel 因 lwip 栈效率低只有约 1/5；类 Lambda 计算服务场景，过载状态下 noxs 相比走 XenStore 的版本把排队请求的完成时间缩短了约 5 倍。

## 局限与疑点

- 作者自己在 §9 列出的开放问题：LightVM 未做内存去重/页共享（假设最坏情况每个 VM 页面都不同，SnowFlock 式内存去重是留白的优化方向）；noxs/split toolstack 的思路可推广到 KVM（`ukvm` 等已有类似精简 toolstack 尝试），但 XenStore 这套问题是 Xen 特有的，KVM 用 Linux 进程信息 + QEMU 进程存类似信息，迁移经验能否直接套用未验证。
- **易用性代价明确承认**：unikernel 性能最好但需要"非同小可的工程投入"移植应用到 Mini-OS，且缺乏成熟调试工具链；Tinyx 是折中但仍不如容器生态成熟。论文承认这是 LightVM 相对容器的现实劣势，不是可以简单工程掉的问题。
- 设备销毁（VM destroy）在 noxs 下尚未优化，迁移测试中低并发时 chaos+XenStore 版本反而略快于 LightVM（§6.2 明确指出）。
- 评测全部在 2017 年硬件（Xeon E5-1630 / AMD Opteron 6376）、Xen 4.8 上完成，且是作者自研系统的自评，没有第三方复现；类似 [[firecracker]] 论文的情况，六年后的数字不能直接当作现状。
- TLS/lwip 网络栈性能差是已知短板（作者承认"达到 Linux TCP 栈的成熟度是个大工程"），这类"unikernel 网络性能不如通用内核"的问题在后续 [[2020-anjali-firecracker-gvisor]] 等评测里以不同形式反复出现。

## 对我们的启发

- **控制面（toolstack）瓶颈这个诊断框架可直接迁移到我们自己的沙箱调度层**：本文最有价值的方法论不是"镶小 VM"（这是常识），而是发现**即便 guest 已经小到 3.6MB，创建耗时依然会因为管理平面（这里是 XenStore + `xl`）本身的架构而随并发数超线性恶化**。这与 [[rund]] 揭示"安全容器瓶颈分散在 rootfs/guest kernel/host cgroup 而非 VMM"是同一类教训的不同实例：任何高密度沙箱系统，都要单独测量"控制面/管理服务本身"在高并发下的伸缩性，不能假设优化了数据面（VMM、guest OS）就够了。
- **"消除集中式注册表 + 让前后端直连共享内存"是一个可复用的伸缩性模式**：noxs 把 XenStore（集中式、类文件系统、watch 回调）换成 hypervisor 维护的每 VM 设备页 + 直接 hypercall，本质是把"通过中间人转发状态"改成"状态就近存放、直接访问"。如果我们自己的沙箱平台里存在类似 XenStore 角色的集中式元数据/配置存储（比如某个 etcd/中心 KV 在高并发创建场景下被打爆），这提示一个具体的重构方向：能否把该状态下放到调度对象自身可直接访问的位置。
- **Prepare/execute split 是比"简单预启动池"更细粒度的池化思路**：Firecracker 论文级别的"预启动完整 MicroVM 池"（[[firecracker]]）是池化"整个可用实例"；LightVM 的 split toolstack 是池化"创建过程中与具体配置无关的那部分工作"（VM shell），粒度更细，理论上能覆盖更多样的目标配置（不需要为每种规格单独维护一个池）。这是我们规划自己的冷启动加速方案时，除了"整实例预热"之外值得评估的备选粒度。
- **Tinyx 提示了一条"应用感知的镜像裁剪自动化"路线**：如果我们平台的 agent 沙箱镜像存在大量与目标任务无关的软件包/内核选项，Tinyx 的"依赖分析（objdump + 包管理器）+ 逐项裁剪并跑测试验证"这套自动化流程是一个可参考的具体实现，而不需要手工定制每个任务专用镜像。
- **警惕数字的时代局限**：本文 2.3ms 启动、8000 VM/机是 2017 年 Xen 4.8 单一硬件上的结果，且是 Xen 生态（noxs 依赖 XenStore 缺陷这个 Xen 特有前提），不能直接当作"VM 隔离能做到多快"的通用上限，也不能直接套用到我们评估 KVM/Firecracker 路线的密度规划中；但其证明的"存在性"（隔离级别不必然牺牲到容器级性能）本身是有价值的参照。
- Follow-up 建议（可转 issue）：
  1. 精读 ukvm / Solo5（本文 §8、§9 提到的 KVM 侧同类精简 unikernel monitor 尝试），看 noxs/split toolstack 的思路在 KVM/Firecracker 生态下是否已有对应实现，与我们更贴近的 KVM 路线对齐；
  2. 核对我们自己沙箱平台的元数据/配置存储服务，是否存在类似 XenStore 的集中式瓶颈模式（尤其是高并发创建场景下的一致性检查、watch 机制），作一次专项排查；
  3. 关注 ClickOS/Mirage 这类网络处理专用 unikernel 后续发展，评估是否有可直接复用的现成 unikernel 镜像用于我们平台里网络代理/流量处理类沙箱任务。

## 相关

- 相关概念：[[lightvm]]、[[unikernel]]、[[microvm-sandbox]]、[[firecracker]]
- 相关笔记：[[2020-agache-firecracker]]（同一"重写极简控制面/VMM"决策模式的后继者，3 年后、基于 KVM）、[[2022-li-rund]]（同一类"控制面/管理层瓶颈分散在 VMM 之外"的诊断方法）
- 与母论文 [[2609.22978]] 的关系：DSec 主文并未直接引用或点名 LightVM（检索母论文全文 `.cache/papers/2609.22978.txt` 未发现"LightVM"或"Manco"字样），本篇是阅读清单 `dsec-refs` B 类中标注为 P3、定位为"轻量 VM 可以比容器更快更密的经典论证"的背景补充文献，而非 DSec 直接引用链上的节点。它与母论文的关系是**技术谱系上的前身**：DSec §2.2/§9 讨论的 microVM 路线（以 [[firecracker]] 为代表）与 LightVM 共享同一个核心论点——"VM 隔离与容器级性能不是互斥的，取决于实现"——但走的是不同的技术路径（LightVM 基于 Xen + unikernel/Tinyx 镶小镜像 + 重写控制面；Firecracker 基于 KVM + 精简 VMM，不改 guest 镜像本身的构建方式，也不需要为每个应用定制 unikernel）。LightVM 2017 年做到的 2.3ms 启动/8000 VM 密度，与 Firecracker 2020 年生产验证的 150ms/10x 超卖相比，指标量级差异很大，但两者面向的场景也不同（LightVM 用 unikernel 极限压测 vs Firecracker 面向通用 Lambda 函数运行时），提醒我们比较跨系统数字时必须核对 guest 类型是否可比。DSec 本身选择的是 Firecracker 一脉的路线（microVM + 通用 guest kernel），没有采用 unikernel/超精简 guest 的思路，可能是因为 agent 训练沙箱的 guest 需要跑相对通用的 Linux 环境（不是单一专用应用），unikernel 的"每应用定制镶小"模式在这种场景下工程成本过高。
