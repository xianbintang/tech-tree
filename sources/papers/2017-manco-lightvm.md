---
title: "My VM is Lighter (and Safer) than your Container"
type: paper
id: "2017-manco-lightvm"
source_url: https://doi.org/10.1145/3132747.3132763
authors: [Filipe Manco, Costin Lupu, Florian Schmidt, Jose Mendes, Simon Kuenzer, Sumit Sati, Kenichi Yasukata, Costin Raiciu, Felipe Huici]
affiliations: [NEC Laboratories Europe, Univ. Politehnica of Bucharest]
published: 2017-10-28
code_url: http://sysml.neclab.eu/projects/lightvm
---

容器虽轻量但隔离弱（依赖不断膨胀的 Linux syscall API），VM 隔离强但笨重；本文论证这不是必然的取舍——只要 VM 足够小、控制面（toolstack）足够快，VM 也能做到容器级的启动速度、密度与内存/CPU 开销。作者用 unikernel（Mini-OS 链接目标应用）和 Tinyx（自动生成的精简 Linux 分发）压缩 VM 镜像本身，再提出 LightVM：对 Xen 控制面的彻底重构——用 `noxs`（无 XenStore，前后端驱动通过共享内存直连 hypervisor 维护的设备页）替代集中式 XenStore，用 split toolstack（prepare/execute 两阶段，靠预生成 VM shell 池摊薡创建开销）替代单体 `xl`/`libxl`，再用二进制 daemon `xendevd` 取代慢速的 hotplug bash 脚本。LightVM 可将（unikernel）VM 启动做到 2.3ms（对比 Docker 慢两个数量级、Xen 原生 xl 高负载下近 1 秒），单机密度做到 8000 个 VM，迁移/挂起/恢复分别做到 60ms/30ms/25ms，per-VM 内存开销低至 480KB（磁盘）/3.6MB（运行时）。论文用四个用例（个人防火墙、即时服务实例化、高密度 TLS 终结、类 Lambda 计算服务）验证了这套设计在真实工作负载下的可用性。

笔记：[[2017-manco-lightvm]]
