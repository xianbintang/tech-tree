---
title: "沙箱镜像分发与按需加载"
aliases: [on-demand image loading, 按需镜像分发, 可组合镜像层, EROFS, composable environment layers]
created: 2026-09-26
updated: 2026-09-26
sources: [2609.22978]
---

# 沙箱镜像分发与按需加载

## 一句话定义

面对"环境组件多、复用率低、单机存不下"的沙箱镜像语料，用（1）独立版本化的可组合层替代单一镜像、（2）从共享存储按需拉取而非整体预拉取这两条原则，把镜像维护成本和 I/O 开销都降到与实际访问量匹配的水平。

## 为什么对我们重要

这是 DSec 论文里对我们平台**工程杠杆最高**的部分：如果我们目前是整包镜像分发（每次升级重建整个镜像、每次启动整体拉取），这套"分层 + 按需"模式是可以直接对标、优先级应该高于很多算法层优化的改造点。

## 核心机制 / 主要变体

- **问题根源**：把 base image、workspace、toolkit 三种独立生命周期的组件揉进单一 OCI 镜像，会造成组合爆炸——升级 $m$ 个 base image 要重建 $O(m \cdot N)$ 个镜像，升级 $k$ 个 toolkit 要重建 $O(k \cdot N)$ 个（$N$ 是 workspace 数）[[2609.22978]]。
- **可组合层（composable layers）**：用 overlayfs 的多层只读栈合并语义（多个 lower 目录叠加，冲突按优先级解决，可写 upper 层吸收运行时写入），把 base/workspace/toolkit 三层独立版本化、创建时动态组合（DSec 改造 `dockerd`，仅 30 行 Go 代码实现动态插入 lowerdir），把升级成本降到 $O(m)$、$O(k)$ [[2609.22978]]。
- **EROFS 只读文件系统**：发布后不可变的层用 EROFS 存储（专为只读数据设计，比 ext4/XFS 省掉写相关记账、布局更紧凑，支持压缩且保留随机访问——不像 tar.gz 必须整体解压才能读任意文件）[[2609.22978]]。
- **3FS 按需加载**（区别于常见的"registry + P2P"组合）：镜像直接放在集群已有的 3FS 分布式文件系统上，按 3FS 的不对称 I/O 特性（大块顺序读写快、小随机 I/O 差）设计三条原则——写留本地盘、读按需+批量拉取、元数据尽量留本地（EROFS 支持 metadata/data 分离设备模式，只把 metadata 下载到本地）[[2609.22978]]。
- **层合并优化**：为避免挂载层数过多拖慢创建，DSec 离线把小于阈值（如 3GB）的连续层合并成一对 EROFS 镜像（保留 overlayfs whiteout 语义表示文件删除），减少最终 mount 数量，同时保留跨镜像共享层的页缓存复用 [[2609.22978]]。
- **microVM 侧的对应方案**：容器路线的 EROFS/overlayfs 组合不满足 microVM 需求（如 Docker overlay2 driver 不支持 overlayfs 数据目录，Firecracker 不支持 virtio-fs）；microVM 改用 OverlayBD 块级格式 + 团队自研的 ublk 用户态块设备框架，256KiB 粒度按需拉取 + 二级本地缓存，支持增量磁盘快照而不需要重新打包成 EROFS [[2609.22978]]。

## 工程要点与数字

- 一周生产快照（Table 2）：容器后端服务 11,266 个 base image + 102,171 个 workspace（合计 82.8TB）；microVM 后端仅 2 个 base image + 53,590 个 task workspace（合计 50.9TB）；另有 103 个 toolkit，67.8% 的沙箱需要额外挂 workspace/toolkit [[2609.22978]]。
- **镜像实际访问比例极低**（Table 3）：不同语言镜像运行时只访问 4.2%（JavaScript）到 13.3%（Go）的镜像数据，这是"整包预拉取绝大部分是浪费"这一判断的直接证据 [[2609.22978]]。
- 消融数字（8192 容器突发，Figure 10）：按需 EROFS 加载比冷拉取快 **1.71×**（~35 分钟 vs. 60+ 分钟，接近全本地缓存基线），累计磁盘写少 **57%**（~700GB vs. >1600GB）[[2609.22978]]。
- 消融数字（EROFS vs. tar.gz 分层挂载，Figure 11）：任务完成时间从 79 分钟降到 45 分钟（**1.76×**），tar 方案磁盘写流量是 EROFS 的 **5.5×**、峰值写吞吐 **3.4×**[[2609.22978]]。
- 云 bursting 场景：一个去重后 30TB 的 EROFS 镜像集覆盖了 70% 容器任务的镜像依赖，可整体同步到云端文件系统供 cloud burst 使用 [[2609.22978]]。
- 相关系统（DSec 论文点名但未展开精读，留待 category E）：Nydus（EROFS 兼容格式 + fscache/FUSE 懒加载）、DADI（块级按需镜像）、FaaSNet（P2P 镜像分发）——DSec 强调自己复用已有 3FS 而非另起 registry+P2P 分发层 [[2609.22978]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源；后续读 EROFS、DADI、Nydus、FaaSNet、CoFS 原始论文后补充）

## 开放问题

- DSec 的"3GB 阈值合并连续层"是具体工程参数，论文未说明这个阈值如何调优、是否随负载类型变化。
- 按需加载的收益量级（1.71×/1.76×）依赖于镜像访问比例确实很低（4%–13%）这一前提，不同团队的负载分布若访问比例更高，收益可能显著缩水——需要在自己的负载上先采样验证。

## 相关概念

[[microvm-sandbox]]、[[sandbox-density-overcommit]]

## 相关来源

- [[2609.22978]] — DSec：提出可组合环境层 + EROFS/3FS 按需加载，给出量化消融数据
