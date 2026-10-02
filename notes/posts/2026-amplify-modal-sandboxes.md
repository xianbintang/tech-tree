---
title: "Behind the scenes of Modal sandboxes"
type: post
id: "2026-amplify-modal-sandboxes"
source_url: https://www.amplifypartners.com/blog-posts/behind-the-scenes-of-modal-sandboxes
authors: [Sarah Catanzaro]
affiliations: [Amplify Partners]
published: 2026-09-04
created: 2026-10-02
tags: [agent-sandbox, gvisor, sandbox-scheduling, snapshot-restore, image-distribution, agentic-rl]
concepts: [gvisor, microvm-sandbox, sandbox-density-overcommit, microvm-placement, sandbox-image-distribution, snapshot-layering, microvm-snapshot-uniqueness, async-rl-training]
rating: 4
issue: 116
---

# Behind the scenes of Modal sandboxes

> Modal 的 sandbox 产品从周末原型扩展到支撑单客户 10 万（目标 100 万）并发 agentic RL 沙箱，暴露出的核心矛盾是"调度器需要低延迟的实时集群视图"与"集群规模增大后单调度器会成为瓶颈"。

## 元信息

- 作者/机构：Sarah Catanzaro，Amplify Partners（Modal 投资方），采访 Modal 工程团队后写的深度报道，2026-09-04 发布
- 链接：[原文](https://www.amplifypartners.com/blog-posts/behind-the-scenes-of-modal-sandboxes)
- 对比基线/相关笔记：[[2609.22978]]（DSec，生产级多后端沙箱平台，规模级别相近）、[[gvisor]]、[[microvm-sandbox]]、[[aws-lambda-microvms-agent-sandboxes]]（同样是"把内部沙箱能力产品化开放"的案例）
- **注意**：本文是投资方写的宣传性报道，不是 Modal 官方工程博客或论文，文中出现的"10 万/100 万并发""单 VM 可容纳数百个 sandbox"等数字均为采访中口头给出，**没有任何图表、基准测试或第三方验证**，精读与录入知识库时按"厂商/投资方声称"而非"已验证结论"处理。

## 要解决的问题

coding agent（Lovable、Cursor 等）需要沙箱执行生成的代码，但文章认为更具基础设施挑战性的新负载是 **agentic RL 训练**：verifiable reward 的 RL 训练需要让 agent 在隔离环境里实际执行生成的代码/命令（SWE-bench、terminal-bench 式的 test harness），一次训练/评测会产生"任务数 × 每任务采样轨迹数 × 每轨迹步数"量级的沙箱执行次数，远超单纯推理服务的规模。文章围绕 Modal 如何把一个"周末写出来的 v1"撑到某 AI lab 10 万级并发（目标 100 万）的过程，讲了四类具体工程问题：调度、跨区域容量/冷启动、存储/快照、打包密度。

## 方法

### v1 为什么能一周写出来

Modal 在做 sandbox 产品之前，已经为其核心声明式 FaaS 产品打磨了多年的底层原语：快速容器启动、两套自研文件系统、基于 [[gvisor]] 的隔离、跨机器/跨云的调度层、支持动态挂载的存储层。Sandbox 产品只是把这些已有原语通过一个新的**命令式**接口（`Sandbox.create()` 返回句柄，可执行命令、挂存储、读文件、开端口）暴露出来，而不是重新发明基础设施——所以 v1 的工程重心实际是 API/SDK 设计，而不是底层系统。沙箱默认不继承调用方在 Modal 生态里的凭据/权限，需要显式授予。

### 调度：从"够用的在线放置"到"调度器本身要分片"

Modal 核心 FaaS 产品面对的是相对有界、可预测的活跃容器数量；sandbox 产品暴露的则是可直接寻址、异构资源需求/生命周期、分布在多区域的大量独立容器，调度退化成一个实时系统问题：调度器需要持续更新的集群状态视图，因为每个放置决策都依赖"此刻"的可用容量，且决策要快速、重复地做。

Modal 的架构是**控制面用数据库做 source of truth，调度器基于一份内存态集群视图做低延迟放置决策**。文章明确指出这套架构在较小规模下运作良好，但 Modal 正在重新设计以支撑数量级更大的并发沙箱——核心矛盾在于：单一调度器迟早成为瓶颈，必须做分区（partition），但放置决策依赖"足够新"的可用容量视图，节点数/沙箱数/状态转换数越多，维持哪怕近似一致的跨机视图就越难。文章没有给出 Modal 新架构的具体设计，只说明了问题和目标。

### 跨区域容量与冷启动

部分竞品只在单一云区域运营，可以激进地缓存镜像、让热容量贴近调度器，从而在冷启动基准测试上刷出好成绩——文章认为这类对比"选择性忽略了"单区域架构本身的优势。Modal 因数据驻留（如 EU-only）、就近低延迟执行、聚合多区域容量等用户需求而跨多区域运行，代价是镜像缓存被分散到各区域、镜像可能需要按需拉进某个区域、放置决策要同时考虑资源可用性和地域约束——文章声称 Modal 在此前提下仍保持"state-of-the-art"的冷启动表现，但未给出具体数字或第三方对比。

Modal 还支持对**任意**容器镜像（而非一小组预先优化过的镜像）做快速冷启动，这意味着镜像更不容易被预缓存、环境差异更大，进一步加大了冷启动工程难度。

### GPU 沙箱

Modal 支持 GPU-backed sandbox，用于自动化 kernel 生成、ML 实验循环、依赖 FFmpeg 等硬件加速流水线的视频处理 agent，以及"AI research agent"（自动生成假设、设计实验、跑训练/评测循环、汇总结果的迭代式研究循环）。GPU 是稀缺且区域碎片化的资源，放置约束比 CPU 沙箱更紧，进一步加剧了调度复杂度。

### 存储层：四种原语，不同粒度

- **Filesystem snapshot**：捕获沙箱某一时刻的完整文件系统，可用于恢复长任务/工作流（挂起-恢复）；只存相对 base image 的增量，与 Modal 的快速启动路径集成。
- **Directory snapshot**：只捕获某个工作目录（而非整个环境），可以在更换底层镜像/环境的前提下跨沙箱复用项目文件或中间产物。
- **Memory snapshot**：同时捕获文件系统和运行中进程的内存状态，原则上可以让执行从完全相同的点恢复；**文章明确说明该特性仍处于 alpha 阶段且有限制**。
- **Volume**：与快照正交，提供可跨沙箱/函数挂载的共享持久存储，更适合长期数据而非执行态 checkpoint。

文章认为这组原语对"agent workflow 本质上是有状态的"这一事实很重要：一条轨迹不是单次函数调用，而是一串会修改文件/环境/中间结果的步骤，这些原语让状态变得显式、可控——可以不重跑整条轨迹，而是 checkpoint 进度、从共享起点分支、并行探索多个续写。

### 打包密度

一个物理 VM 可以容纳数百个 sandbox（取决于每个 sandbox 的 CPU/内存需求），因为每个 sandbox 通常只占一小部分 core 和少量 RAM——这比"每个环境一个 VM"效率高得多（固定开销被摊薄）。文章强调打包/调度在这个密度下变得关键，因为整体系统效率取决于资源利用率而不产生争用；沙箱密度直接决定了能并行执行多少轨迹，进而决定训练/评测的数据吞吐上限。

### RL 场景下，沙箱延迟直接影响训练效率

文章给出一条因果链：轨迹生成（rollout/评测）在沙箱里跑，策略优化在独立的 GPU 训练基础设施上跑；由于策略更新用的数据来自一个"正在移动"的策略，生成和优化之间的延迟越短，off-policy 偏移越小，训练数据与当前策略越对齐，更新质量越高。因此更快的沙箱 provisioning 和执行速度，直接提升了"新鲜、on-policy 数据"进入训练的速率，直接影响整体学习效率——这是文章把"sandbox 吞吐"和"RL 训练效率"挂钩的核心论点，但只是定性描述，没有给出量化的延迟-效率曲线。

## 局限与疑点

- 全文没有一张图表、一个基准测试数字，所有规模/性能声称（"某 AI lab 10 万级并发，目标 100 万""冷启动 state-of-the-art""单 VM 数百个 sandbox"）均为采访中的口头表述，无法核实。
- "Modal 的新调度架构解决了分片问题"这一点没有展开——文章只描述了问题（单调度器瓶颈、集群视图一致性随规模变难），未描述 Modal 实际采用的分片方案，不能作为可复用的架构参照，只能作为问题陈述参照。
- 文章把 Modal 的 sandbox 隔离基础描述为"gVisor-based isolation"，但未说明是否所有沙箱类型（含 GPU-backed sandbox）都走 gVisor 路径，还是 GPU 场景下用了不同的隔离机制——这一点与 [[gvisor]] 页面已记录的"gVisor 在计算密集负载上性能损耗接近零、但网络/小粒度内存操作较弱"的实测结论之间的关系未说明。
- Memory snapshot 处于 alpha 阶段，文章完全没有提及"从同一份内存快照启动多个并发实例时的唯一性问题"（PRNG/密钥/连接状态重复，详见 [[microvm-snapshot-uniqueness]]）——与 AWS Lambda MicroVMs 的产品文档存在相同的疑点模式：产品化叙事里这类问题被系统性略过，不代表已经被解决。
- "Modal 跨区域仍保持 state-of-the-art 冷启动"与"部分竞品靠单区域架构在冷启动基准上刷分"这组对比完全是 Modal 单方面叙述，没有第三方基准数据支撑，不能作为选型依据。

## 对我们的启发

- **调度器是否要为"数据库做 source of truth + 内存态低延迟视图"这种架构预留分片路径**：Modal 公开承认这套架构在更大规模下会遇到瓶颈，这比空谈"我们用了内存态调度器很快"更有价值——如果我们自己的调度器也是类似的"DB 持久化 + 内存态快照做决策"结构，值得现在就评估单点调度器的分片方案（哈希分区？按资源池切分？按区域切分？），而不是等规模上来再重新设计。
- **多区域场景下的冷启动/镜像缓存是一个我们可能低估的工程成本**：如果我们的沙箱平台未来需要跨机房/跨区域部署（数据驻留、就近执行、聚合容量等诉求），"任意镜像的快速冷启动"在多区域下的难度会显著上升（缓存碎片化、按需跨区域拉取），需要提前规划，而不是假设单机房的 EROFS/3FS 式方案能直接套用到多区域。
- **"沙箱 provisioning 延迟 → off-policy 偏移 → 训练效率"这条因果链值得量化**：我们如果要给 RL 训练团队提供 SLA，"沙箱创建/执行延迟"不应该只看绝对数值，还要换算成"对 on-policy 程度的影响"，可以参考 [[async-rl-training]] 里 policy staleness 的修正框架，把"基础设施延迟"和"算法侧能容忍的 staleness"统一到同一套度量下讨论，而不是把两者当成互不相关的两个团队的问题。
- **filesystem/directory/memory 三级快照粒度的产品化拆分值得借鉴**：相比"只有一种快照原语"，按"整环境恢复"（filesystem snapshot）、"仅复用工作目录"（directory snapshot，换底层镜像场景）、"完全恢复执行态"（memory snapshot，alpha）三种粒度分别暴露给用户，是比我们目前可能有的"单一快照机制"更灰度的设计，值得作为我们自己做 checkpoint/restore API 时的参照，但 memory snapshot 的唯一性问题（见「局限与疑点」）需要我们自己提前设计方案，不能假设产品化后这个问题会自动消失。

## 相关

- 相关概念：[[gvisor]]、[[microvm-sandbox]]、[[sandbox-density-overcommit]]、[[microvm-placement]]、[[sandbox-image-distribution]]、[[snapshot-layering]]、[[microvm-snapshot-uniqueness]]、[[async-rl-training]]
- 相关笔记：[[2609.22978]]（DSec，同规模级别的生产沙箱平台对照）、[[aws-lambda-microvms-agent-sandboxes]]（同类"内部能力产品化"案例）、[[2020-anjali-firecracker-gvisor]]（gVisor 独立实测，用于校验本文"gVisor-based isolation"的性能含义）
