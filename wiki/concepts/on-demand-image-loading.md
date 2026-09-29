---
title: "On-demand Image Loading / 镜像按需加载"
aliases: [on-demand container loading, 按需镜像加载, 稀疏加载, sparse loading, lazy loading]
created: 2026-09-26
updated: 2026-09-26
sources: [2023-brooker-lambda-container-loading, brooker-lambda-snapstart]
---

# On-demand Image Loading / 镜像按需加载

## 一句话定义

利用"容器/沙箱启动时只会访问镜像数据的一小部分"（sparsity）这一特性，把镜像下载从"启动前一次性拉取解压全量数据"改造成"运行时按实际访问的块/层懒加载"，从而把冷启动时间和 I/O 量从镜像大小解耦。

## 为什么对我们重要

我们的沙箱平台同样面临"镜像/环境体积远超单节点存储、也远超冷启动延迟预算能承受的下载量"的问题（agent 沙箱镜像常常是多 GB 的完整开发环境）。[[2023-brooker-lambda-container-loading]] 与 [[2609.22978]]（DSec §5.3）分别给出了两条不同的按需加载路线，都验证了同一个前提性观察——sparsity——是解决这类问题的关键突破口，值得作为我们设计镜像分发层时的第一手参照。

## 核心机制 / 主要变体

按加载粒度可以分成两条路线：

- **块级（block-level）路线**：把镜像"打平"成单一块设备镜像（如 ext4），通过 virtio-blk/FUSE 之类的块接口按需读取，文件系统语义完全留在 guest 内部处理，host 侧只关心块。[[2023-brooker-lambda-container-loading]] 采用此路线，理由是保持 host 侧接口简单（攻击面小），代价是失去了"按文件/层"做更精细策略（如区分启动必需 vs 可延后）的能力。DADI 也是块级路线，但用 P2P 分发而非专用缓存层，且不支持 [[2023-brooker-lambda-container-loading]] 这种程度的去重。
- **文件系统层（filesystem-level）路线**：保留容器 OCI 镜像的分层结构，在文件/层粒度做懒加载（如 Slacker、Starlight、eStargz），或者用专门的只读压缩文件系统分离 metadata 与 data（如 DSec 用 EROFS：metadata 本地化、data 按需从 3FS 拉取,§5.3）。这条路线更贴近容器原生的分层语义，但引入了 overlay 多层文件系统的复杂度。
- **两条路线共同的前提性发现**：容器/沙箱启动时只需要访问镜像很小一部分数据——Harter et al.（被 [[2023-brooker-lambda-container-loading]] 引用）测得平均只需 6.4%；DSec §5.3 独立观测到同样的 sparsity 现象并作为其设计的出发点（Tab. 3）。
- **去重是块级路线的自然延伸**：[[2023-brooker-lambda-container-loading]] 通过确定性 flatten（消除文件系统实现的非确定性）保证共享 base layer 的镜像在块级产生逐位相同的数据，再用收敛加密（chunk 内容派生密钥）在不共享密钥的前提下去重——这是多租户公开云场景下"既要去重又要租户隔离"的一个成熟方案。DSec 场景是单租户训练基础设施，直接复用已有的 3FS 存储，未做类似的去重加密层。
- **尾延迟优化**：加载路径命中率越高，尾延迟对系统整体吞吐的影响越大（一次容器启动要读上千个块，任一慢查询都会拖慢整体）。[[2023-brooker-lambda-container-loading]] 用纠删码（4-of-5，类似 EC-Cache）而非副本复制来解决单节点缓存故障/尾延迟问题,以 25% 存储/请求开销换取显著更稳定的尾延迟,并强调这比"重试掩盖尾延迟"更安全（后者容易诱发 metastable failure）。

## 工程要点与数字

- Sparsity：容器启动平均只需 ~6.4% 的镜像数据（Harter et al.,经 [[2023-brooker-lambda-container-loading]] 引用)。
- 去重效果（[[2023-brooker-lambda-container-loading]],生产数据）：约 80% 新上传函数产生零唯一 chunk（CI/CD 重复上传）；其余 20% 平均唯一 chunk 占比 4.3%（中位数 2.5%）。整体去重最多减少 23x 存储,对零唯一 chunk 的函数再省 5x。
- 缓存命中率（[[2023-brooker-lambda-container-loading]],一周生产数据）：本地缓存（L1）中位命中 67%,AZ 级分布式缓存（L2）中位命中 99.9%,仅 0.06% 落到 S3 origin。
- 延迟（[[2023-brooker-lambda-container-loading]]）：L2 缓存命中中位 550µs vs S3 origin 中位 36ms；端到端读延迟呈三模态分布（本地 <100µs / L2 命中 ~2.75ms / origin 拉取更慢）。
- 规模（[[2023-brooker-lambda-container-loading]]）：单客户最高 15,000 容器/秒创建速率;累计处理"数百万亿次"invocation。
- DSec §5.3 的对应数字：8,192 容器并发启动测试中,按需 EROFS 加载相比 eager Docker pull 快 1.71x（35 分钟 vs 60+ 分钟完成全部任务）,磁盘写入量减少约 57%（~700GB vs ~1,600GB/节点）,接近全本地基线（~600GB）。

## 争议与矛盾

- **块级 vs 文件系统层孰优孰劣,两篇来源没有直接对比数字**：[[2023-brooker-lambda-container-loading]] 选块级理由是攻击面更小；DSec §5.3 选 EROFS（文件系统层,但用多设备模式分离 metadata/data）理由是复用已有 3FS 存储基础设施、避免部署独立分发层。两者面对的信任边界不同（公开多租户 vs 内部单租户）,尚不能得出哪条路线在同等条件下性能更优的结论,需要待读 DADI/FaaSNet/CoFS/Nydus（阅读清单 Key E）后补充跨系统对比。

## 开放问题

- 同一团队半年前（2022-11）的博文 [[brooker-lambda-snapstart]] 把"把快照数据分发到需要它的地方"称为"构建 SnapStart 最大的挑战"，并预告"会在不久的将来详细介绍具体解法"——时间线与问题描述都与 [[2023-brooker-lambda-container-loading]] 高度吻合，但**两者对象不同**：博文讨论的是**快照内存**的按需加载/预取，论文讨论的是**容器镜像**的按需加载，无法从文本直接确认是否为同一套底层机制,只能确认是同一团队在解决相邻问题。
- [[2023-brooker-lambda-container-loading]] 论文本身承认：容器作为"大号静态链接依赖闭包"在此场景下效率不高,呼吁需要更轻量的机制,但未给出具体方案。
- 两条路线在我们自己的 agent 沙箱镜像负载（比容器镜像更大、生命周期可能更长、跨 region 分发需求不明）下的适用性,尚未有直接证据支持,需要在自己的 trace 上验证 sparsity 假设是否同样成立。
- DSec 是否借鉴了 [[2023-brooker-lambda-container-loading]] 的具体机制（块级 FUSE、纠删码缓存、收敛加密去重）**无法从 DSec 原文确认**——逐字检索 DSec 全文未发现提及 Lambda 或本文作者,§5.3 与 §9 引用的是 FaaSNet/Nydus/DADI/CoFS/EROFS,不包含本文。两篇论文只是面对相似问题给出了不同架构答案，不存在已证实的引用关系。

## 相关概念

[[microvm-placement]]

## 相关来源

- [[2023-brooker-lambda-container-loading]] — AWS Lambda 生产系统:块级按需加载 + 收敛加密去重 + 纠删码缓存,处理数百万亿次 invocation 的完整设计与运维经验
- [[brooker-lambda-snapstart]] — 提出"快照数据搬运是规模化的最大挑战"，是本概念页问题动机的一处旁证（针对快照内存而非镜像，参见「开放问题」）
