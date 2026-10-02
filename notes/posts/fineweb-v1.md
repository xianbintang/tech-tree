---
title: "FineWeb: decanting the web for the finest text data at scale"
type: post
id: "fineweb-v1"
source_url: https://huggingface.co/spaces/HuggingFaceFW/blogpost-fineweb-v1
authors: [Guilherme Penedo, Hynek Kydlíček, Loubna Ben Allal, Anton Lozhkov, Colin Raffel, Leandro von Werra, Thomas Wolf]
affiliations: [HuggingFace]
published: 2024-05-31
created: 2026-10-03
tags: [pretraining-data, data-curation, deduplication]
concepts: [pretraining-data-curation-pipeline]
rating: 3
issue: 123
parent: ""
---

# FineWeb: decanting the web for the finest text data at scale

> HuggingFace 公开了从 96 个 CommonCrawl 快照构建 15T token 预训练数据集 FineWeb 的完整流程与消融实验，并蒸馏出教育质量子集 FineWeb-Edu。

## 元信息

机构：HuggingFace / 发表时间：2024-05-31 / 链接：[博文](https://huggingface.co/spaces/HuggingFaceFW/blogpost-fineweb-v1) · [FineWeb 数据集](https://huggingface.co/datasets/HuggingFaceFW/fineweb) · [FineWeb-Edu 数据集](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu) · [datatrove 代码](https://github.com/huggingface/datatrove) / 对比基线：RefinedWeb、C4、Dolma v1.6、The Pile、SlimPajama、RedPajama2

## 要解决的问题

Llama 3、Mixtral 等 SOTA 开放权重模型的预训练数据集并不公开，构建细节（过滤规则、去重方法、质量标准）也极少披露，社区缺乏一份"如何把 CommonCrawl 原始抓取数据加工成高质量预训练语料"的可复现指南。本报告把 FineWeb 的全部设计选择（包括失败的尝试）记录并消融，试图让这一过程透明化。

## 方法

四段式流水线，每一步都用 1.82B 参数的小模型在 ~28B token（部分验证实验用 350B token）上跑消融，在 CommonsenseQA / HellaSwag / OpenBookQA / PIQA / SIQA / WinoGrande / ARC / MMLU 等"小规模高信噪比"基准上评估：

1. **文本抽取**：CommonCrawl 提供 WARC（原始 HTML）与 WET（纯文本）两种格式。作者用 [trafilatura](https://github.com/adbar/trafilatura) 从 WARC 重新抽取文本，而非直接用官方 WET：WET 版本多出约 25% token（254B vs 200B，基于 2019-18 单个 dump 对比），但这些多出的 token 主要是导航栏/样板文字噪声，用 WET 训出的模型效果更差。抽取用 [`datatrove`](https://github.com/huggingface/datatrove)（HuggingFace 自研、可扩展到数千 CPU 核心的开源数据处理库）完成。

2. **基础过滤**：沿用 RefinedWeb 的设置——URL 黑名单过滤成人内容、fastText 语言分类器只保留英文（阈值 ≥0.65）、套用 MassiveText 的质量与重复过滤规则（默认阈值）。96 个 dump 处理后得到约 36T token。

3. **去重（MinHash）**：收集每篇文档的 5-gram，用 112 个哈希函数（14 桶 × 8 哈希）配置 MinHash，相似度阈值约 75%（9000 哈希/450 桶的 RefinedWeb 方案精度更高但计算成本大得多，这里是故意的成本权衡）。
   - 最初假设"全局去重（跨全部 96 个 dump 一起去重）效果最好"，按时间从新到旧迭代去重，结果只剩 4T token，但训出的模型效果出奇地差，远低于 RefinedWeb。
   - 深挖最旧的 2013-48 dump 发现：全局去重后保留的 31B token（10%）实际上比被去掉的 171B token 质量更差（人工检查确认有更多广告、关键词堆砌、格式错乱内容）。
   - 作者据此提出假设：真正该去掉的是"在几乎每个 dump 里都重复出现的大簇"（如模板页、聚合站），而"仅在少数 dump 里重复、未在其他 dump 找到匹配"的数据，往往是因为内容本身质量差/分布外，而非因为它"干净"。全局去重会把这类低质量数据保留下来并相对放大其比例。
   - 改为**逐 dump 独立 MinHash 去重**（不跨 dump 比较），得到 20T token，效果与 RefinedWeb 打平。作者还尝试了 URL 去重、行级去重等多种"独立去重之上再叠加全局去重"的方案，结果全部比"仅逐 dump独立去重"更差。

4. **统计驱动的额外质量过滤**：先复现 C4 的过滤规则集（去掉不以标点结尾的行、含 JavaScript/cookie 提示的行、过短过长文档、含 "lorem ipsum" 或花括号的文档），发现其中"行必须以标点结尾"这一条单独贡献最大收益但也删掉约 30% token，性价比不高；弃用该条后其余 C4 过滤规则仍能追平 C4 在 HellaSwag 上的表现、且少删数据。随后用更系统的方法开发定制过滤器：收集 50+ 文档级/重复性统计指标，对比独立去重版（更干净）和全局去重版（更脏）两个旧 dump 的指标分布，用 Wasserstein 距离筛出差异最大的指标，人工检查直方图定阈值，再逐个做消融验证，最终确认 3 个有效过滤器（基于"行尾标点占比"“重复行字符占比"“短行占比"），组合后删除约 22% token，效果超过 C4。

5. **FineWeb-Edu：LLM 标注 + 蒸馏分类器的规模化质量过滤**：用 Llama-3-70B-Instruct 对 50 万条 FineWeb 样本做 0–5 分教育价值打分（采用 additive scale 而非单次 Likert 打分，让模型逐分说理由），再用这 45 万条标注训练一个轻量分类器（[Snowflake-arctic-embed](https://huggingface.co/Snowflake/snowflake-arctic-embed-m) embedding 模型 + 回归头，冻结 embedding/encoder，只训练头部），在 4.5 万条held-out 验证集上取最佳 F1 checkpoint，转成以阈值 3 二分类，F1 达 82%。用该分类器为全部 15T token 打分（耗时 6,000 H100 GPU 小时），阈值 3 过滤后留下 1.3T token（删掉 92%），阈值 2 则留 5.4T token（作为备选版本一并发布）。

## 实验与结果

- 独立 MinHash 去重（20T token）效果与 RefinedWeb 持平；全局去重（4T token）效果明显更差。
- 2013-48 dump 个案：全局去重后保留的 31B token 比被去掉的 171B token 质量更差（两者估计重叠仅约 4B token）。
- 最终 FineWeb（15T token，44TB）在同等规模对比中全面优于 RefinedWeb（500B）、C4（172B）、Dolma v1.6（3T，CommonCrawl 部分）、The Pile（340B）、SlimPajama（627B）、RedPajama2（20T，已去重）。
- FineWeb-Edu（阈值 3，1.3T token）在 350B token 规模的消融里超过 FineWeb 及所有对比开放数据集，在 MMLU/ARC/OpenBookQA 等教育类基准上提升显著，比 C4/Dolma 少用约 10 倍 token 即可打平 MMLU，但在 HellaSwag 上略有退步。
- 额外发现：对 192 个 1.8B 模型（每个训练 27B token，共约 6 万 H100 GPU 小时）按 CommonCrawl dump 分别训练评测，不同 dump 的质量差异明显，但作者未能找到确定性解释（排查过 URL 分布变化、benchmark 污染等假设）。
- 用"delve"“as a large language model”“rich tapestry”等 ChatGPT 高频词作代理指标，发现 2023 年起（ChatGPT 发布之后）这些词在新 crawl 中的频率陡增，提示合成数据占比在上升，但小规模训练下未观察到明显的负面影响。

## 局限与疑点

- "全局去重效果更差"背后的因果机制（大簇重复 vs 小簇分布外）只是作者给出的假设性解释，论文没有做进一步的消融把"去掉大簇"和"保留小簇"这两个效应分离验证。
- 所有消融实验都在 1.82B 参数模型、数十 B 到 350B token 规模完成，是否能外推到当前主流的更大模型规模、更长训练（多 epoch、更大 batch）没有直接证据。
- 合成数据代理指标（关键词频率）precision/recall 未知，既可能漏判不含这些短语的合成文本，也可能误判人类写的同类表达，因此"合成数据占比上升但未见明显损害"这一结论的置信度有限。
- FineWeb-Edu 的"地面真值"本身就是 Llama-3-70B 的打分，没有与人工标注做交叉验证，继承了该模型自身的偏好与偏差（比如论文提到为了避免模型偏爱技术性强的 arXiv 类文本，专门把标注导向"中小学知识水平"，这是一个人工介入校正的信号，但校正是否充分未知）。
- 不同 dump 质量差异的根因未查明，意味着目前的 dump 筛选/配比策略仍有信息缺口。

## 对我们的启发

这篇是预训练数据管线而非直接的沙箱/调度话题，但有几条工程方法论可以迁移到我们"agent 轨迹数据 / RL 环境语料"的构造与质检场景：

1. **LLM 标注 + 蒸馏小分类器做规模化质量过滤**（FineWeb-Edu 的核心套路）与 [[verifiable-reward-environment-generation]] 笔记里"用辅助 agent 生成轨迹、训练奖励模型，把人工 reward 设计解耦"是同一个模式的两个领域变体：先用大模型标注一个几十万量级的种子集，再蒸馏出一个便宜的小分类器批量打分。6,000 H100 GPU 小时处理 15T token 这个数字，给了我们"规模化打分阶段"成本量级的一个参照系——如果我们要对大规模 agent 轨迹/环境语料做类似的自动质检或可用性打分，直接每条跑一次大模型推理可能不是最优解。
2. **"去重越彻底越好"是一个需要警惕的直觉陷阱**：FineWeb 最初认为全局去重效果最好，结果实测反而更差，根源是"仅出现一次的数据"未必是高质量数据、反而可能是噪声。如果未来我们要对 agent 轨迹/会话日志做跨批次/跨时间的去重，不能默认"去重比例越高越好"，而要先用小规模消融验证，再决定是否全量推广。
3. **`datatrove` 这类可扩展到数千 CPU 核心的开源数据处理框架**，是我们如果要自建大规模轨迹/日志/环境语料处理流水线时值得参考的架构范式（流水线化的 filter/dedup pipeline，而非单机脚本堆叠）。

可执行的 follow-up：
- 调研 `datatrove` 的 pipeline 抽象，评估能否直接复用于处理我们自己的 agent 轨迹/日志数据。
- 调研"LLM 标注 + 小模型蒸馏打分"模式是否已经被用在 agent 轨迹过滤或 reward model 蒸馏相关论文中，与 FineWeb-Edu 做跨领域对照。
- 若我们计划对跨会话/跨时间的 trace 做去重，先用小规模消融验证"全局去重 vs 分批独立去重"哪个更好，避免重蹈 FineWeb 最初"全局去重反而更差"的覆辙。

## 相关

- 相关概念：[[pretraining-data-curation-pipeline]]
