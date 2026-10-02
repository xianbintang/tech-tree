---
title: "预训练数据清洗与去重流水线"
aliases: [pretraining data curation, FineWeb recipe, web data decanting, MinHash 去重, LLM 标注蒸馏分类器]
created: 2026-10-03
updated: 2026-10-03
sources: [fineweb-v1]
---

# 预训练数据清洗与去重流水线

## 一句话定义

把 CommonCrawl 这类原始网页抓取数据加工成高质量 LLM 预训练语料的标准化工序：文本抽取 → 基础规则过滤 → 模糊去重（MinHash）→ 统计/分类器驱动的质量过滤，每一步都用小模型消融实验验证收益，而非凭直觉决定 [[fineweb-v1]]。

## 为什么对我们重要

我们的核心方向是 agentic RL 训练基础设施，不直接做预训练数据，但这套"大规模语料清洗"的工程方法论——尤其是"LLM 标注种子集 + 蒸馏小分类器规模化打分"与"用消融实验而非直觉验证每一步数据处理决策"——可以直接迁移到我们未来可能需要的 agent 轨迹数据质检、环境语料去重等场景 [[fineweb-v1]]。

## 核心机制 / 主要变体

- **文本抽取**：trafilatura 从 WARC 原始 HTML 重新抽取文本，优于 CommonCrawl 官方的 WET 纯文本版本——WET 多出的 ~25% token 主要是导航栏/样板文字噪声，用它训练效果更差 [[fineweb-v1]]。
- **基础规则过滤**：fastText 语言分类（阈值 ≥0.65）+ URL 黑名单 + MassiveText 质量/重复过滤，96 个 CommonCrawl dump 处理后从约 400TB 原始内容收敛到 36T token [[fineweb-v1]]。
- **模糊去重（MinHash）**：
  - 112 个哈希函数、14 桶 × 8 哈希的小参数配置，在召回率和计算成本之间做权衡（相比 RefinedWeb 的 9000 哈希/450 桶方案省资源）[[fineweb-v1]]。
  - **反直觉发现**：跨全部 96 个 dump 一起做"全局去重"，效果反而比"每个 dump 独立去重"更差——全局去重会把旧 dump 里"仅存的非重复数据"过度保留，而这类数据本身质量更差（更多广告、关键词堆砌）；真正该去掉的是"在几乎所有 dump 里都重复出现的大簇"（模板页、聚合站），而非跨 dump 的小规模重复 [[fineweb-v1]]。
  - 最终采用"逐 dump 独立 MinHash 去重"，得到 20T token，效果与 RefinedWeb 打平；在此基础上再叠加 URL 去重/行级去重等全局方案，效果反而全部变差 [[fineweb-v1]]。
- **统计驱动的启发式过滤**：收集 50+ 文档级/重复性统计指标，对比高质量（独立去重）与低质量（全局去重）两个版本数据集的分布，用 Wasserstein 距离筛出差异最大的指标，人工检查直方图定阈值，再逐个做小模型消融验证——这套"统计发现 → 候选阈值 → 消融验证"的流程本身是可复用的方法论，不只是产出了 3 个具体过滤器 [[fineweb-v1]]。
- **LLM 标注 + 蒸馏分类器规模化质量过滤**（FineWeb-Edu）：用 Llama-3-70B 对 50 万样本做 0–5 分教育质量标注（additive scale，让模型逐分说理由），用这些标注训练一个轻量分类器（embedding 模型 + 回归头，F1 82%），再用分类器给全部 15T token 打分（耗时 6,000 H100 GPU 小时），阈值 3 过滤出 1.3T 高教育价值子集——在 MMLU/ARC/OpenBookQA 等基准上超过所有开放数据集，比 C4/Dolma 少用约 10 倍 token 即可打平 MMLU [[fineweb-v1]]。

## 工程要点与数字

- 96 个 CommonCrawl dump，基础过滤后 36T token → 独立 MinHash 去重后 20T token → 最终 FineWeb 15T token、44TB [[fineweb-v1]]。
- 全局去重的反例：2013-48 这个旧 dump，490B token 全局去重后只剩 31B（10%），但这 10% 实测比被去掉的 171B 质量更差（消融模型得分更低，人工检查也确认噪声更多）[[fineweb-v1]]。
- FineWeb-Edu 规模化打分阶段的关键成本数字：6,000 H100 GPU 小时处理 15T token；筛选后 92% 数据被丢弃，只留 1.3T token（阈值 2 则留 5.4T）[[fineweb-v1]]。
- 192 个 1.8B 模型 × 27B token 的消融实验（约 6 万 H100 GPU 小时）用于比较不同 CommonCrawl dump 的质量差异，但未找到确定性根因 [[fineweb-v1]]。
- `datatrove`：HuggingFace 自研的开源数据处理库，支撑了整条流水线向数千 CPU 核心的扩展 [[fineweb-v1]]。

## 争议与矛盾

（暂无跨来源分歧，仅一篇来源）

## 开放问题

- 为什么不同 CommonCrawl dump 的质量差异很大：作者检查了 URL 分布变化和 benchmark 污染两个假设，均未找到确定性解释 [[fineweb-v1]]。
- "全局去重更差"这一结论背后的因果机制（大簇重复损害 vs 小簇分布外价值）只是作者给出的假设，未经过严格的消融分离验证 [[fineweb-v1]]。
- 所有消融都在 1.8B 模型、数十 B 到 350B token 规模完成，能否外推到更大模型、更长训练仍未知 [[fineweb-v1]]。
- 用"delve”“as a large language model”等词频做合成数据代理指标，precision/recall 不明，无法确定合成数据具体占比及其在大规模训练下的真实影响 [[fineweb-v1]]。

## 相关概念

[[verifiable-reward-environment-generation]]（"LLM 标注 + 训练小模型解耦人工打分"是同一套模式在数据过滤与 reward 设计两个领域的变体）、[[generator-verifier-asymmetry]]

## 相关来源

- [[fineweb-v1]] — FineWeb / FineWeb-Edu 技术报告博文，完整给出抽取/过滤/去重/分类器蒸馏四段式流水线与各步消融结果
