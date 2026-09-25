---
name: triage
description: 每日推送的 LLM 精排。读取 .cache/candidates.json（关键词粗排后的论文/博文候选），按用户研究方向挑选并写中文 TL;DR 与推荐理由，输出 .cache/triage.json。在 daily-ingest 流程中、或用户说“精排今天的候选”时使用。
---

# Triage：每日候选精排

## 输入

- `.cache/candidates.json`：`{date, papers: [...], posts: [...]}`，每项有 `id, title, abstract, score, source, hf_upvotes?`。
- `config/interests.yaml`：`research_direction`（画像）与 `limits.pick_papers / pick_posts`（入选上限）。
- 可选：`wiki/concepts/` 下已有的概念页名 —— 用来判断“这篇是否补上了知识库的空白”。

## 判断标准（按优先级）

1. **与 focus_areas 的直接相关度**：是否正面讨论 agentic RL 训练系统、沙箱/执行环境、训练侧系统工程、agent 环境与评测。只沾边（摘要里提了一句 tool use）不算。
2. **对用户工作的可落地性**：给出系统设计、成本/密度/吞吐数字、开源实现的优先于纯算法刷点。
3. **新颖度**：与 wiki 已有概念重复度高、只是增量刷榜的降权。
4. **信号**：HF upvotes、知名机构只做加分参考，不能压过 1 和 2。
5. `irrelevant_areas` 里的一律不选，哪怕关键词分很高。

宁缺毋滥：候选里真正相关的不够上限就少选。博文同理（公司营销稿、产品发布会通稿不选，除非有技术细节）。

## 输出

写 `.cache/triage.json`（严格 JSON，UTF-8）：

```json
{
  "summary": "一句话概括今天的看点（≤60 字）",
  "papers": [
    {
      "id": "2609.23377",
      "tldr": "≤80 字，说清做了什么、结果如何",
      "why": "≤80 字，为什么值得用户看；落到用户方向",
      "tags": ["agentic-rl", "swe-agent"],
      "must_read": true
    }
  ],
  "posts": [ { "id": "<candidates 里的 id>", "tldr": "...", "why": "...", "tags": [], "must_read": false } ]
}
```

规则：
- `id` 必须原样来自 candidates，**不要自己编 URL/标题**（渲染脚本只认 id）。
- 数组按推荐度排序；`must_read` 每天最多 2 个。
- 只写这一个文件，不改其它文件，不做 git 操作。
