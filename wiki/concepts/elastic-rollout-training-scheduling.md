---
title: "弹性 Rollout-训练 GPU 调度（Elastic Rollout-Training Scheduling）"
aliases: [elastic scheduler, elastic GPU reallocation, cell-based role switching, 弹性调度, GPU 角色切换]
created: 2026-09-30
updated: 2026-09-30
sources: [2609.33848]
---

# 弹性 Rollout-训练 GPU 调度（Elastic Rollout-Training Scheduling）

## 一句话定义

把 GPU 组织成若干同构、可独立切换角色的小单元（cell），根据"未完成 rollout 工作量 vs 剩余 rollout 容量"的实时水位信号，动态把 cell 在 rollout/训练两个角色间转移，同时保持 harness 执行状态不受影响，从而在同一批物理 GPU 上兼顾训练吞吐和 rollout 服务可用性 [[2609.33848]]。

## 为什么对我们重要

这是"训练系统 GPU 调度"这个研究方向里，介于 [[async-rl-training|静态 pipeline decoupling]] 和 [[rollout-training-disaggregation|按中断容忍度物理拆池]] 之间的第三条路径：不预先固定资源边界，也不要求两类负载物理隔离，而是让同一批 GPU 单元按需切换角色。对我们做沙箱/调度平台来说，这提供了一个具体的、已经在数小时级 agent rollout 场景下验证过的设计参照：调度触发信号可以很简单（一个基于计数器的水位线），复杂度主要在"角色切换时如何不丢状态"这一层。

## 核心机制 / 主要变体

- **Cell 抽象**：K 个同构 elastic cell 共享同一套训练并行布局（TP/PP/EP/CP 组不跨 cell），外加可选的 standalone rollout 池；cell 按固定顺序排列，core cell 持有权威权重和唯一的 optimizer 状态，其余是 satellite cell [[2609.33848]]。
- **Waterlevel 触发**：用三个累计计数器（已派发 $d(t)$、已启动 $p(t)$、已终止 $f(t)$）定义未完成执行数 $w(t)=d(t)-f(t)$（burst 内单调不增）；只有当剩余 rollout 容量能覆盖 $w(t)$（$w(t)\le C_R(t)-C_e$）时，下一个 cell 才允许从 rollout 转去训练，转移按 core 优先、satellite 按序**串行**发生，形成不断增长的"训练前缀"，直到 burst 结束 [[2609.33848]]。burst 结束后 core 是否继续留在训练，还要看下一批数据是否已备好、剩余容量是否覆盖待发执行 [[2609.33848]]。
- **Harness-preserving 角色转移**：转移只发生在"转发点"（黑盒代理）——harness、工作区、工具执行状态全程不受影响；源 cell 先停止接收新请求，调度器预留目标容量并更新路由，取消源端在途请求后代理透明重试到新目的地，源端优先转发给可用时间更长的目的地（standalone 引擎 > 更靠后的 rollout cell）以减少同一执行被反复重路由 [[2609.33848]]。
- **KV-cache RDMA 迁移**：源端在请求取消前先 pin 住对应 KV 块，取消并停止写入后目标端通过 RDMA 读取，源端等待目标确认接管后才释放缓存，用来减少前缀重算 [[2609.33848]]。
- **流式训练 + 动态成员**：core 通过 Mooncake Transfer Engine 在每个 step 前暴露权重 buffer，satellite 按固定顺序原子加入正在进行的 batch、RDMA 拉取快照后不打断 core 地开始训练；梯度累积期间权重固定，保证加入者读到一致快照。轨迹缓冲区+流打包缓冲区把数据切成小粒度 micro-step，cell 从共享队列按算力到达情况原子领取，更快/更早的 cell 多领，帮助各 cell 在 batch 末尾同时收尾，减少收尾空闲 [[2609.33848]]。
- **与同类工作的关系**：TideRL 用就绪信号调整 rollout/reference 执行；BiDiRL 允许异步流水线两侧互相借用空闲资源；DynaResize 用通信器复用+状态暂存重分配 GPU；Libra 用全局资源规划器+弹性混合池；QwenGyre 相对这些工作的差异化在于把"细粒度、串行、可回退的 cell 级切换"与"harness 状态完全不动、只在代理层重路由"结合起来，并给出了在小时级、近百万 token 规模上的验证 [[2609.33848]]。

## 工程要点与数字

- 实测切换耗时：rollout→训练 8.52s，训练→rollout 3.46s，相对数小时的 rollout 执行几乎可忽略 [[2609.33848]]。
- 32 节点预算下，cell 粒度从 8×4 节点降到 4×8 节点，12 步训练时间只增加 2.2%（因为细粒度切换本身已经让训练大部分被 rollout 隐藏，20.85% slack）——说明存在一个"够用就好"的 cell 粒度阈值，继续切细边际收益很小 [[2609.33848]]。
- 端到端速度：Qwen 3.6 122B 上相对 Async 提速 1.38×–1.57×、相对 Colocate 1.36×–1.85×（因任务而异）；Qwen 3.8 2.4T（700K token/rollout）上相对 Async 1.78×、相对 Colocate 1.21×，旗舰模型上相对 Colocate 的收益因 query 时长集中在超时上限附近而收窄 [[2609.33848]]。
- 消融证明两个要素缺一不可：streaming（让数据更早可用）单独加到 Async 上只省 11.6%；细粒度弹性分配单独加到 Colocate+streaming 上再提速 1.19×——两者组合（而非单独任一个）才是收益的来源 [[2609.33848]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 更小 GPU 总预算下这套组织形式的效率退化曲线未评测——论文只承认"预算太小可能不可行"，没给出定量边界 [[2609.33848]]。
- 多步 burst 下 streaming training 无法做跨 minibatch 的全局 shuffle，这对学习质量本身的影响未被单独隔离测量（论文只测了执行时间）[[2609.33848]]。
- 该机制假设 RDMA 权重拉取 + KV-cache 迁移在集群互联拓扑上可行，未讨论在不支持这类互联的环境下如何退化。

## 相关概念

[[async-rl-training]]、[[rollout-training-disaggregation]]、[[agentic-rollout-preemption]]、[[rollout-efficiency]]、[[epoch-fencing]]

## 相关来源

- [[2609.33848]] — 提出 cell 级弹性调度器（waterlevel 触发 + harness-preserving 角色转移 + 流式动态数据并行），在小时级/近百万 token 的 agentic RL 场景下给出端到端速度和详细消融数据，是本页目前唯一来源
