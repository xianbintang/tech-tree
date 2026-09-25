---
name: research-topic
description: 针对一个 `research-topic` issue 做专题调研，先查自己的知识库再上网补充，产出 reports/topics/<slug>.md 调研报告。用户说“调研一下 XXX”“处理 topic issue #N”时使用。
---

# Research-topic：专题调研

## 输入

`.cache/issue.json`（或 `gh issue view <N>`）：主题、想回答的问题、背景、期望深度（快速简报 / 深度调研）。

## 流程

1. **拆问题**：把主题拆成 3–6 个具体子问题，写在报告开头。
2. **先查内部**：在 `wiki/concepts/`、`notes/`、`reports/` 里 grep 相关内容，列出已有结论（引用 `[[slug]]`）。明确知识库的空白。
3. **再查外部**：WebSearch / WebFetch 补齐空白。优先：论文（arXiv、会议）、官方工程博客、开源仓库、benchmark 榜单。
   每个事实都记录来源 URL。深度调研模式下至少覆盖 8 个独立来源。
4. **综合**：不是罗列，要对比——方案 A/B/C 在同一维度（成本、隔离性、吞吐、成熟度、开源情况）上的表格。
5. **落地建议**：结合 research_direction，给出对用户平台的建议与风险，以及 2–5 个值得精读的论文（附 arXiv ID）。

## 输出

`reports/topics/<slug>.md`：

```markdown
---
title: "..."
type: report
issue: N
created: YYYY-MM-DD
depth: brief | deep
---

# <主题>

## TL;DR（5 行以内）
## 要回答的问题
## 知识库里已有的
## 调研发现
### <子问题 1>
...
## 方案对比（表格）
## 对我们的建议
## 推荐精读
- [ ] <标题> — arXiv:xxxx.xxxxx — 理由
## 参考来源
1. [标题](url)
```

同时：
- 发现值得沉淀的新概念 → 按 `ingest-wiki` 规则建/更新概念页（来源写报告 slug）。
- 写 `.cache/pr_body.md`：摘要 + 文件列表 + 推荐精读清单。清单**必须**用下面的格式，
  用户勾选后合并 PR，`inbox-to-issues` workflow 会自动为勾选项建 `to-read` issue 并精读：
  ```
  - [ ] **<论文标题>** — <一句话理由> <!-- read type=paper id=<arXiv ID> url=https://arxiv.org/abs/<arXiv ID> -->
  - [ ] **<博文标题>** — <理由> <!-- read type=post id=<url 的简短 slug> url=<原文 URL> -->
  ```
- 写 `.cache/notify.txt`（3 行以内）。
