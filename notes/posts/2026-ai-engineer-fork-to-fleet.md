---
title: "From fork() to Fleet: Designing an Agent Sandbox Cloud"
type: post
id: "2026-ai-engineer-fork-to-fleet"
source_url: https://ai.engineer/talks/OqM67QG_Ikk-from-fork-fleet-designing-agent-sandbox-cloud
authors: [Abhishek Bhardwaj]
affiliations: [OpenAI]
published: 2026-10-01
created: 2026-10-02
tags: [agent-sandbox, microvm, gvisor, snapshot, disk-persistence, scheduling]
concepts: [microvm-sandbox, gvisor, sandbox-disk-persistence, snapshot-layering, microvm-placement, firecracker]
rating: 4
issue: 102
---

# From fork() to Fleet: Designing an Agent Sandbox Cloud

> OpenAI RL/agent 基础设施工程师第一性原理讲清"agent 沙箱云"全链路：隔离谱系 → 磁盘快照 → 跨节点编排，无新基准数字，但给出 DSec 论文之外的独立产品视角与几处母论文未覆盖的具体机制（crosvm 谱系、COW+FIEMAP 磁盘快照、NBD 分层块存储、快照分层感知调度）。

## 元信息

- 讲者：Abhishek Bhardwaj（OpenAI，RL 与 agent infrastructure 团队；此前供职 Google，参与 crosvm；个人开源项目 [Arrakis](https://github.com/abshkbh/arrakis)）
- 发表：AI Engineer World's Fair 2026，演讲 44 分钟，页面附逐字稿
- 链接：[AI Engineer 讲座页](https://ai.engineer/talks/OqM67QG_Ikk-from-fork-fleet-designing-agent-sandbox-cloud)（含摘要式逐节讲稿 + 完整逐字稿）
- 对比基线/关联：[[microvm-sandbox]]、[[gvisor]]、[[firecracker]]（提及 crosvm/Cloud Hypervisor 谱系）；与母论文 [[2609.22978]]（DSec）覆盖同一问题域但完全独立成文

## 要解决的问题

这不是一篇论文，而是一次面向工程师的科普/设计讲座：从"为什么 agent 需要代码执行"讲起，第一性原理地推导出"一个安全、可持久化、可规模化的 agent 沙箱云"需要解决的三个问题——单节点运行时隔离、磁盘持久化、跨节点编排——并给出讲者认为合理的参考方案。内容广度大、深度中等（44 分钟讲座体量），很多地方只给出设计直觉和定性判断（"几毫秒""几个数量级"），不含可复现的量化实验，这点与 [[2609.22978]]（DSec，有完整消融实验）的论文形态不同，应作为互补的"从业者经验谈"来读，而非等同强度的证据来源。

## 方法

### 1. 为什么需要沙箱：可验证奖励训练 + 产品侧执行环境

模型对"3+3"这类见过很多次的内容回答准确，但对"strawberry 里有几个 r"这类未被充分验证过的问题常出错；给模型代码执行能力、用可验证奖励（verifiable reward）训练，就能让它通过"写代码检验答案"来提升这类任务的正确率。训练循环因此必须包含：训练框架出题 → 模型生成（可能含工具调用请求）→ harness 解析并通过 tool runtime 执行代码 → grader 判定 reward → 回传更新权重。这把"何时调用工具"和"生成的代码能否真正解决问题"两件事同时训练了出来，harness 和 runtime 是学习系统的一部分而非训练后才加的外围设施。推理时去掉权重更新环节，但 harness 仍要解析/执行/返回观测——产品侧（本地 Codex、Codex Web、ChatGPT）必须提供真实的执行环境，且必须把模型生成的代码当作**不可信代码**：即便没有恶意，一个"过度热心"想完成任务的 agent 也可能尝试获取 root。研究场景优化吞吐（many rollouts in parallel），产品场景优化延迟与可靠性，但两者都要防止 GPU token 被浪费、都要保护基础设施和数据。

### 2. 运行时隔离谱系：从 fork/exec 到硬件虚拟化

逐层推导出隔离方案演进链（术语解释见 [[microvm-sandbox]] 与 [[gvisor]]）：

- **fork/exec**：最简单、性能最好（原生性能），但子进程直接触达宿主内核攻击面，且无资源约束（一个 while 循环 fork 就能拖垮整节点）——安全隔离和资源隔离都没有。
- **容器（namespaces + cgroups）**：namespaces 提供资源视图隔离（PID/mount/network 等各自看到独立视图,宿主侧仍是普通进程），cgroups 控制资源消耗上限,解决了"吵闹邻居"问题,但容器仍是宿主内核上的原生进程,系统调用直接到达共享内核；seccomp 能收紧系统调用白名单降低攻击面,但对开放式 agent workload 预先枚举所需系统调用很难,策略反复调整的反馈循环对产品体验不友好。
- **gVisor**：用户态 *Sentry*（Go 实现）重新实现大部分 Linux 系统调用，文件系统访问经由 *Gofer* 代理，使得利用链从"直接到内核"变成"先攻破 Sentry/Gofer，再从它们攻破宿主内核"的两步攻击链——更难，但宿主内核终究还在攻击链末端。讲者明确指出，模型在寻找漏洞和串联 exploit chain 的能力正在变强，这是继续往"硬件级隔离"推进的动机。
- **硬件虚拟化（VMX root/non-root）**：guest 内核运行在独立的处理器执行上下文（VMX non-root）里的 ring 0，即便 guest 拿到 root 或内核级利用，也不能直接控制宿主（VMX root）；代价是 guest/host 切换有性能开销。QEMU 等 VMM 负责配置 guest 并调用 `/dev/kvm`；paravirtualization（virtio）让 guest 驱动感知到自己在虚拟机里，用更高效的方式与宿主通信（PCI 设备形式，访问时 "exit" 到宿主侧）。
- **crosvm → Firecracker / Cloud Hypervisor（microVM）**：2023 年前后（讲者原话，但 Firecracker 实际公开发布于 2018 年，与此处口径不完全一致，需注意）一批 Rust 实现的轻量 VMM 出现。讲者所在团队在 Google 时为 Chromebook 上跑 Linux VM 写了 **crosvm**——内存安全（Rust）+ 砍掉 QEMU 的大量设备/架构支持（QEMU 历史上多次被攻击的正是 C 实现的设备代码）。Firecracker 从 crosvm fork 而来，用于 AWS Lambda/serverless；Cloud Hypervisor 是多家公司共同维护的、范围更通用的同类 VMM。"micro"指的是 VMM 自身的内存footprint、设备集合和启动开销更小，**不是**对 guest 内部能力的限制。此外还可以做**设备级别的 jail**：block 设备后端只给块资源权限、network 设备后端只给网络权限,即使某个设备被攻破也不能直接拿到其它设备的权限——是 VMM 架构内部最小权限原则的具体应用,这一机制在 [[microvm-sandbox]] 现有笔记中未展开。
- **控制通路**：harness fork 一个 cloud-hypervisor 进程 → 该进程通过 Unix domain socket 暴露 API → 调用 create（给定 rootfs/kernel/CPU/内存配置）→ 调用 start（VMM 调 `/dev/kvm` 真正跑起 guest）。guest 内 PID 1 再暴露一个 API server，供 harness 通过 vsock 或节点 IP 栈与 guest 内部通信（存状态、挂设备等）。
- **microVM 的代价**：guest/host 切换开销；内存回收依赖 balloon driver，只能"要求 guest 归还"、是被动/滞后的；GPU 访问受限——`virtio-gpu` 只提供高层图形库接口，直通（VFIO）式的"metal access"同一时刻只能给一个沙箱独占，不支持多租户共享。讲者给出一条经验法则：**优先优化性能来迁就安全边界，而不是反过来**——系统技巧能掩盖性能问题,但掩盖不了安全漏洞,公司一旦失去信任很难挽回。他把自己见过的团队演进路径总结为"沙箱悲伤的七个阶段"：几乎所有团队都是先试容器、gVisor、V8 隔离,最后发现 agent 需要一台完整的 Linux 机器,于是又要求这台机器必须安全——他给创业团队的建议是**从一开始就用 microVM**,行不通再谈其它方案。这是一条独立于 DSec 论文的从业者经验判断,不是量化结论,但与 DSec 选择 microVV/容器/FnCall/fullVM 四后端、而非单压 gVisor 的架构决策方向一致。

### 3. 磁盘持久化：写时复制增量快照 + 分层块存储

区别于"内存快照"（克隆/恢复完整执行状态，见 [[snapshot-layering]]、[[microvm-snapshot-uniqueness]]），这部分专讲**磁盘状态**的持久化：

- **为什么需要**：agent 任务越来越长程（写代码仓库、做演示文稿），节点故障或模型 flake 导致磁盘状态丢失，既浪费已消耗的 GPU token，也是糟糕的用户体验。持久化带来的不只是"数据不丢"，还有三个具体收益：(1) 周期性 checkpoint 让节点/集群故障后可在别处用保存的状态重建沙箱,也支持集群升级/节点 A-B 测试时的主动迁移;(2) 长程任务（讲者提到自己跑过约 3 天的 Codex "goal mode"）需要可恢复的检查点而不是从头重跑;(3) 支持"检查点-尝试-回退-再检查点"的分支式探索（Monte Carlo tree search 式的 harness 设计）,让多日级 rollout 可以在不破坏公共起点的前提下探索多个方向。
- **设计选择矩阵**：触发方式（一直保存 vs. 显式调用 Save API）、快照内容（全量 vs. 增量）、覆盖范围（整个 root FS vs. 指定目录/挂载点）、变更粒度（整文件 vs. 变更的块）。讲者的取舍：在 ChatGPT/Codex 规模下必须做**增量快照**（否则每次都存几 GB 数据，既烧钱又慢），且 Save API 本身要足够快，恢复（本质上就是"用快照重新创建"）也要足够快。
- **磁盘给 guest 的两种接入方式**：共享文件夹式（类似 Google Drive 挂载，每次文件操作都要 host 介入处理，效率低）vs. 块设备式（给 guest 一个块设备，guest 自己的文件系统和缓存能处理更多工作，只有真正需要访问块设备时才 exit 到宿主）。讲者明确倾向块设备路径。
- **显式增量快照的具体实现**：用支持 reflink 的 **XFS** 做写时复制——从 base image 建一个"近乎零延迟"的可写副本（讲者原话，未给基准数字），只有实际写入的块才会脱离与 base 的共享；调用 Save API 时用 **FIEMAP** 取得哪些 extent（块范围）发生了变化，把这些变化压缩打包上传，返回一个**快照 ID**；Save API 可以在后台上传尚未完成前就先返回（讲者称为"我在上传时可以先骗你一下"），换取更快的调用延迟，但这意味着"快照已确认"和"快照数据已持久化落地可供别处恢复"是两个不同的时间点，原始资料没有说明这段 gap 期间如何处理读一致性或失败重试。恢复时按快照 ID 解析出完整的快照 lineage（一条链上的多层增量）,逐层下载并在 base image 上应用这些 extent,再拿重建出的磁盘状态启动新的 microVM。
- **Always-on 持久化**：讲者认为 NFS 不够高性能、也不是严格 POSIX 兼容，模型对标准 POSIX 行为的适配更好；替代方案是用 **NBD（Network Block Device）**把磁盘包装成块设备接口，写入先落到集群内的缓存层，再异步写回 GCS/S3 等持久对象存储，guest 侧始终只看到一个普通块设备，拿到的仍是标准文件系统语义和缓存行为。

### 4. 跨节点编排：集群分层调度 + 快照分层感知放置

延续 [[microvm-placement]] 的放置调度主题，但角度不同：讲者描述的是"顶层控制面按区域负载/延迟选集群 → 集群内调度器按负载和健康状况选节点"的常规分层结构（未命名具体编排框架），随后给出三种冷启动策略——warm pool（预热池，常驻消耗 CPU/内存换低延迟）、内存快照即时恢复（讲者称可在"几毫秒"内完成，未说明测量条件/硬件/快照大小）、二者的混合（用快照恢复动态补充预热池容量）。更具体的一点是**快照分层感知的调度**：当要从某个快照 ID 恢复、而该快照对应一条由多层组成的 lineage 时，调度器可以知道"哪个节点已经缓存了这条 lineage 里的大部分/全部层"，优先把恢复请求路由到命中层数最多的节点，从而减少需要下载的数据量——这与 [[microvm-placement]] 现有笔记里 FirePlace 的 PAR（峰均比）式 bin-packing 调度目标是**不同维度**的放置信号：一个优化"新建 VM 时各机器峰值负载的均衡"，一个优化"恢复已有快照时的数据亲和性"，两者可以同时存在于同一个调度器里。

## 实验与结果

本讲座不含可复现的量化实验或基准测试表格；所有数字均为定性/示例性描述，需明确标注"未经验证"：

- "近乎零延迟"的 XFS reflink 拷贝——无基准数据。
- 内存快照恢复"可以达到毫秒级"——未说明硬件、镜像大小、是否预热缓存等测量条件。
- 讲者个人 Codex "goal mode" 跑了约 3 天——轶事性描述，非系统性负载统计。
- 全篇没有给出任何吞吐、并发密度、成本或资源开销的具体数字（这点与 [[2609.22978]] 的生产消融实验形成明显反差）。

## 局限与疑点

- 整场讲座面向教育/布道目的，所有量化描述都是"几毫秒""几个数量级"式的定性说法，不能当作工程选型的证据来引用，只能当作设计思路的参照。
- "2023 年是新一代 Rust VMM 出现的转折点"这一说法与 Firecracker 2018 年已公开发布、crosvm 更早的事实存在时间线上的不一致，讲者本人对自己团队历史的回忆可能有偏差，不应作为可靠的时间线来源。
- Save API"提前返回、后台异步上传"的一致性问题（后台上传失败怎么办、调用方如何知道真正落盘完成）完全没有展开,只提到这是一个有意的设计权衡。
- GPU 直通的"同一时刻只能给一个沙箱"这一限制是否有除 VFIO mediated device 之外的解法（原始资料的"延伸阅读"部分提到了 VFIO mediated device 框架，但讲座正文没有展开其在 agent 沙箱场景下的适用性），需要后续笔记补充。
- 快照分层感知调度只给了一个教学示意图（三节点、四层 lineage），没有给出real 生产场景下层命中率、调度延迟、与 bin-packing 目标冲突时如何折中的任何细节，比 [[microvm-placement]] 已有的 FirePlace 论文（给出了具体目标函数和生产流量统计）粗糙得多。

## 对我们的启发

1. **"设备级 jail"（block 后端只给块权限、net 后端只给网络权限）是 VMM 架构里可以直接复用的最小权限设计**：如果我们的沙箱平台在 VMM/宿主侧有自己的设备模拟或透传层，即便整体隔离级别已经是 microVM，仍然值得检查各设备后端进程是否做了类似的权限收窄——这是"再加一道防线"的低成本改造，而不需要换架构。
2. **磁盘持久化的 COW + FIEMAP 增量快照思路，和我们已经记录的"内存快照分层"（[[snapshot-layering]]）是正交的两类状态，值得分开设计**：如果我们的沙箱平台目前只考虑了"要不要做内存/执行状态快照"，这场讲座提醒我们磁盘状态本身也值得单独做增量快照（而不是整盘复制或依赖共享文件系统），尤其是 agent 任务会在沙箱里持续产出代码仓库、构建产物等**有价值且会不断增长**的磁盘内容时。具体选型（reflink XFS + FIEMAP vs. 我们自己存储栈等价的块级 diff 能力）需要先确认自己的底层文件系统/块设备是否支持类似的写时复制原语。
3. **"快照数据亲和性"可以作为放置调度的独立信号，叠加在现有的负载均衡/bin-packing 目标之上**：如果我们后续要支持"从快照恢复沙箱"这种场景（比如复用预构建的环境模板，或做抢占后恢复），在调度器里加一条"优先选缓存了最多所需快照层的节点"的规则，是对现有 [[microvm-placement]] 讨论的 PAR 式放置目标的自然补充，而不是替代——两者可以按优先级或加权组合。
4. **"always-on 持久化优先选 POSIX 兼容的块设备路径（NBD + 分层缓存），谨慎评估 NFS"这一判断，值得在我们自己选型时交叉验证**：讲者给出的理由（agent 生成的代码对标准 POSIX 语义的适配更好、NFS 的 close-to-open 一致性模型容易踩坑）是定性判断，没有给出具体故障案例或基准数字，建议在我们自己的沙箱存储选型评审时作为"需要验证的假设"而非直接采纳的结论。
5. Follow-up 建议（可转 issue）：
   - 找 Firecracker/Cloud Hypervisor 官方文档，核实"设备级 jail"的具体实现方式（seccomp profile 还是独立进程权限），评估能否在我们自己的 VMM 配置里直接复用；
   - 调研 XFS reflink + FIEMAP 这套"写时复制 + 增量块快照"方案的具体工程细节（和 [[2609.22978]] 的 `pack_diff` 增量磁盘快照机制做一次正面对比：两者解决的是否是同一问题、实现路径有何不同）；
   - 关注讲者提到的 Arrakis 开源项目（self-hosted agent sandbox，带 microVM 隔离、backtracking、computer use），评估其实现细节是否可以作为我们自己技术预研的参考实现。

## 相关

- 相关概念：[[microvm-sandbox]]、[[gvisor]]、[[sandbox-disk-persistence]]（新建）、[[snapshot-layering]]、[[microvm-placement]]、[[firecracker]]
- 相关笔记：[[2609.22978]]（DSec，覆盖同一问题域的生产级论文，可相互印证/对照）、[[2020-agache-firecracker]]（Firecracker 原始论文，本文 crosvm/microVM 谱系的技术源头）、[[2020-anjali-firecracker-gvisor]]（gVisor vs Firecracker 的独立量化对比，补充本文"两步攻击链"的定性描述）、[[brooker-lambda-snapstart]]、[[brooker-seven-years-of-firecracker]]（同样讨论 Firecracker 快照/克隆机制，可与本文磁盘快照部分对照）
