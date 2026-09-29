---
title: "Agent OS Kernel（Trust-Native Agent Operating System）"
aliases: [agent operating system, trust-native agent OS, AgentKernel, agent 操作系统, 智能体操作系统内核]
created: 2026-09-29
updated: 2026-09-29
sources: [2609.29647]
---

# Agent OS Kernel（Trust-Native Agent Operating System）

## 一句话定义

把身份、输入中介、内存治理、执行控制做成**强制性、不可绕过**的语义层操作系统服务，而不是 agent 应用可以选择性调用的 guardrail 库——类比传统 OS kernel 对进程的强制中介。

## 为什么对我们重要

我们做沙箱与调度平台，日常关心的是隔离级别、冷启动、并发密度这类"执行层"问题；这个概念把视角拉高一层：**执行沙箱只是四个支柱之一（Execution），单独的沙箱隔离不等于完整的 agent 信任边界**。如果未来我们的平台要支持更强的多 agent 协作、跨组织委托场景，身份（谁在代表谁行动）、输入中介（防止污染进入模型上下文）、内存治理（防止记忆投毒跨 session 传播）这几类能力是我们目前架构里基本没有覆盖的空白，值得作为"平台要不要补"的候选能力清单来源。

## 核心机制 / 主要变体

- **三信任域模型**：Input World（不可信）→ AgentKernel 安全内核 → Protected Agent Core → Output World（可审计）。每次跨域都是必须中介的 trust boundary crossing。[[2609.29647]]
- **四支柱**（都是同一套 reference-monitor 纪律在语义面的实例化，不是互相独立的插件）：
  - **Identity**：kernel 托管的密码学身份（Agent Identity Card，Ed25519 签名，四维绑定开发者/代码制品/运营方/部署上下文），委托是 kernel 系统调用而非应用层操作，权限上限 $S_{\max}$ 贯穿其余三支柱。[[2609.29647]]
  - **Perception**：四层递进式输入防御（源标签 → 规则过滤 → 语义防火墙 LLM 分类器 → 多轮越狱检测），在内容进入 LLM context 之前完成。[[2609.29647]]
  - **Cognition**：记忆污点在**乘积格（product lattice）上逐条目传播**，而非整个 session 取最差标签；默认私有、显式共享；检索内容标记为不可执行数据。[[2609.29647]]
  - **Execution**：语义权限 → syscall 级 eBPF 强制执行的四层桥接（E1 规则 → E2 LLM 校验 → E3 eBPF 进程树监控/动态 allowlist → E4 计划-轨迹对齐检测幻觉动作）。[[2609.29647]]
- **设计原则**：策略组合取交集而非并集（converge-on-strictest）；安全内核必须在 LLM 推理循环之外（LLM 本身可被 prompt injection 操纵，检查逻辑不能和被检查对象共享同一个可操纵上下文）；agent 只暴露三个窄适配器（LLM/工具/存储），其余路径视为绕过。[[2609.29647]]
- **与执行沙箱的关系**：论文认为 [[agent-execution-sandbox]]（nono/E2B/Anthropic sandbox-runtime）提供的是**二元隔离**（在/不在沙箱内），AgentKernel 的 Execution 支柱提供的是**按身份/输入 provenance/记忆污点动态计算**的细粒度 allowlist，声称"包含并扩展"沙箱能力——这个论点目前没有实测支持。[[2609.29647]]

## 工程要点与数字

**这个概念目前只有一篇来源论文，且该论文本身没有任何实测数字**（性能开销、误报/漏报率、并发下的竞态都留作 future work）。已知的唯一"数据"是作者自评的能力对比表（Table 3，AgentKernel vs. AGT/AIOS/OpenFang/SmythOS/Letta/nono，15 个维度打分），不是可复现的测评协议。[[2609.29647]]

## 争议与矛盾

（暂无——目前知识库内只有一篇来源，尚未出现跨来源的冲突结论）

## 开放问题

- eBPF probe 安装/拆除延迟在并发 agent 工作负载下的分布未知。
- lattice 污点检索在百万级 provenance 标注记忆条目下的可扩展性未知。
- P3 语义防火墙、E2 LLM 校验这两个位于 TCB 内部的 LLM 组件本身的对抗鲁棒性未表征——"用 LLM 守卫 LLM"的问题并未真正解决。
- 非绕过假设（三适配器是唯一路径）依赖部署方保证，论文没给出自动化验证部署完整性的机制。
- eBPF 强依赖 Linux，macOS/Windows 上的等价后端未定。
- 所有架构不变量目前只是"按构造声称成立"，形式化验证（Coq/TLA+）推迟到后续论文。

## 相关概念

[[agent-execution-sandbox]]

## 相关来源

- [[2609.29647]] — 唯一来源：提出 AgentKernel 架构、四支柱设计、与六个同类系统的自评对比表，明确承认无实测评估
