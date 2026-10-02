---
title: "FineWeb: decanting the web for the finest text data at scale"
type: post
id: "fineweb-v1"
source_url: https://huggingface.co/spaces/HuggingFaceFW/blogpost-fineweb-v1
authors: [Guilherme Penedo, Hynek Kydlíček, Loubna Ben Allal, Anton Lozhkov, Colin Raffel, Leandro von Werra, Thomas Wolf]
affiliations: [HuggingFace]
published: 2024-05-31
code_url: https://github.com/huggingface/datatrove
---

LLM 预训练数据集的质量与规模直接决定模型效果，但 Llama 3、Mixtral 等 SOTA 开放模型的预训练数据都不公开，构建过程也很少被披露。本报告详细记录了 HuggingFace 构建 🍷 FineWeb（15T token、44TB，源自 96 个 CommonCrawl 快照）的完整流程与每一步的消融实验，包括文本抽取、基础规则过滤、MinHash 模糊去重（并给出"全局去重反而更差"的反直觉发现）、统计驱动的定制过滤器，以及用 Llama-3-70B 标注 + 蒸馏小分类器构造的教育质量子集 📚 FineWeb-Edu（1.3T / 5.4T 两档）。FineWeb 在开放网页数据集中取得了当时最优的模型训练效果，FineWeb-Edu 在 MMLU/ARC/OpenBookQA 等基准上进一步超越。数据集以 ODC-By 1.0 协议开放。

笔记：[[fineweb-v1]]
