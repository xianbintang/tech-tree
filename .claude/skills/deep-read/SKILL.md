---
name: deep-read
description: 精读一篇论文或技术博文，生成结构化中文笔记并录入知识库。输入是一个 `to-read` GitHub issue（或 arXiv ID / URL）。产出 sources/ 元数据卡 + notes/ 笔记，然后调用 ingest-wiki 更新概念页。用户说“精读 XXX”“读一下 issue #N”时使用。
---

# Deep-read：精读 + 录入

## 1. 确定对象

- 来自 issue：读 `.cache/issue.json`（run-local.sh 已准备好：`number, title, body`）或 `gh issue view <N>`。body 里有类型、ID、链接。
- 来自用户直接给的 arXiv ID / URL 也可以。
- 已存在 `notes/papers/<id>.md` 时：不要重写，改为补充/修订，并在 PR 描述里说明。

## 2. 获取内容（优先级）

论文：
1. arXiv 论文：`https://arxiv.org/html/<id>`（结构化最好）→ `https://arxiv.org/abs/<id>` + PDF。
2. 非 arXiv 论文（USENIX / ACM / MLSys / 期刊）或 HTML 版读不全时：
   `uv run python -m pipeline.fetch_paper <url> --id <note-id>`，然后读它输出的 `.cache/papers/<id>.txt`（全文，按需分段读）。
   - 退出码 3（被 Cloudflare 等拦截，ACM DL 常见）：对最后一行打印的 PDF URL 调用
     `mcp__firecrawl__firecrawl_scrape`（`parsers: ["pdf"]`，`formats: ["markdown"]`，长论文用 `pdfOptions.maxPages` 分段）。
   - 退出码 2：不是 PDF，按网页读（WebFetch）。
3. 仍不行 → 代码仓库 README / 作者主页 / 会议页面摘要。

博文 / 项目文档：直接抓原文 URL（WebFetch；被拦截时用 firecrawl_scrape）。GitHub 上的文档优先读 raw 内容。
无法获取全文时，基于摘要写**简版**笔记，frontmatter 加 `depth: abstract-only`，并在 PR 描述里标明。
PDF 与全文只放在 `.cache/`，**不要**写进仓库；笔记里只引用单句并注明出处。

## 3. 写 `sources/<papers|posts>/<id>.md`

元数据卡：frontmatter（title, type, id, source_url, authors, affiliations, published, code_url）+ 摘要原文 + 一行「笔记：[[<id>]]」。

## 4. 写笔记 `notes/papers/<id>.md`（博文：`notes/posts/<date>-<slug>.md`）

frontmatter 按 `CLAUDE.md` 的规定（`issue:` 填 issue 编号）。正文结构：

```markdown
# <标题>

> 一句话总结（≤50 字）

## 元信息
机构 / 发表时间 / 链接（arXiv · Code · 项目页） / 对比基线 [[...]]

## 要解决的问题
现有方法的局限、本文动机。

## 方法
核心设计，技术术语用 [[概念]] 链接。关键公式用 $$ $$，每个符号解释。
系统类论文画出架构/数据流（mermaid）。

## 实验与结果
关键表格的核心数字（注明 Table/Figure 编号）；消融结论；**成本、吞吐、资源规模**要单独列。

## 局限与疑点
作者承认的 + 你看出来的（评测设置、可复现性、规模外推）。

## 对我们的启发
落到用户的沙箱/调度/训练平台：需要什么能力（隔离级别、冷启动、并发密度、快照、镜像分发、GPU 调度……）、
可以借鉴什么、要警惕什么。给 1–3 条可执行的 follow-up（可以建成新 issue 的那种）。

## 相关
- 相关概念：[[...]]
- 相关笔记：[[...]]
- （有母论文时）与母论文的关系：见下
```

**来自阅读清单、带母论文（frontmatter `parent:`）时**，「相关」里必须有一段「与母论文的关系」：
母论文在哪一节、为什么引用这篇（先读母论文笔记 `notes/papers/<parent>.md`，没有就读母论文原文对应章节），
这篇的做法与母论文的做法有何异同、母论文在它基础上改了什么，并链接 `[[<parent>]]`。

博文可以精简「方法/实验」，但「对我们的启发」必须有。

## 5. 编译进 wiki

按 `.claude/skills/ingest-wiki/SKILL.md` 更新概念页。

## 6. 收尾

- 写 `.cache/pr_body.md`：
  ```
  ## 精读：<标题>
  <一句话总结>
  ### 新增 / 修改
  - notes/...  - sources/...  - wiki/concepts/...（新建 N / 更新 M）
  ### 值得追问
  - <follow-up 建议，用户可转成 issue>
  ```
- 写 `.cache/notify.txt`：3 行以内的推送摘要（标题 + 一句话 + 评分）。
- 不做 git 操作；分支、提交、PR 由 `scripts/run-local.sh` 处理。
