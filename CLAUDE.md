# tech-tree — 知识库 schema 与 agent 工作守则

本仓库是一个 **AI-native 的论文 / 技术博文学习流水线 + 个人知识库**。
Claude Code 读本文件，Codex 读 `AGENTS.md`（软链到本文件）。两者遵守同一套约定，谁来跑结果都一样。

## 研究方向

读 `config/interests.yaml` 的 `research_direction`。所有筛选、点评、总结都要站在这个视角：
用户做沙箱平台与调度系统，关心「生产上跑不跑得起来、成本与密度、我们平台要补什么能力」。

## 目录约定（LLM-Wiki 三层模式）

| 层 | 路径 | 谁写 | 说明 |
|---|---|---|---|
| 收件箱 | `inbox/YYYY-MM-DD.md` | `pipeline/daily.py` 渲染 | 每日推送，只追加不修改 |
| 原始层 raw | `sources/{papers,posts}/<id>.md` | deep-read | 元数据卡片：标题、作者、链接、摘要。**不存全文**（版权） |
| 笔记层 | `notes/papers/<arxiv-id>.md`、`notes/posts/<YYYY-MM-DD>-<slug>.md` | deep-read | 单篇精读笔记 |
| 编译层 wiki | `wiki/concepts/<slug>.md` | ingest-wiki | 跨来源的概念页，互相链接，是“知识沉淀”的主体 |
| 报告 | `reports/weekly/YYYY-Www.md`、`reports/topics/<slug>.md` | weekly-report / research-topic | 学习报告与专题调研 |
| 状态 | `state/seen/YYYY-MM-DD.txt` | pipeline | 去重记录，**不要手改** |

### 命名与链接

- 概念页 slug：英文小写 kebab-case，如 `grpo`、`microvm-sandbox`、`kv-cache-offload`。一个概念一页，先搜再建，避免同义重复（在 frontmatter `aliases` 里记中文名/别名）。
- 链接统一用 Obsidian 双链：`[[grpo]]`、`[[2609.23377]]`、`[[grpo|GRPO 算法]]`。文件名（不含 .md）全库唯一。
- 论文笔记文件名 = arXiv ID（无版本号）；非 arXiv 论文用 `<year>-<first-author>-<slug>`。

### Frontmatter（必填，`pipeline/wiki_lint.py` 会检查）

笔记：
```yaml
---
title: "..."
type: paper            # paper | post | report
id: "2609.23377"
source_url: https://arxiv.org/abs/2609.23377
authors: [...]
affiliations: [...]
published: 2026-09-20
created: 2026-09-25    # 写笔记当天
tags: [agentic-rl, swe-agent]
concepts: [grpo, swe-bench]   # 与正文中的 [[链接]] 保持一致
rating: 4              # 1-5，对用户方向的价值
issue: 12              # 对应的 GitHub issue 编号
---
```

概念页：
```yaml
---
title: "GRPO"
aliases: [Group Relative Policy Optimization, 组相对策略优化]
created: 2026-09-25
updated: 2026-09-25
sources: [2609.23377, 2609.28963]   # 支撑本页结论的笔记
---
```

## 四个核心操作

1. **ingest**（录入）：新来源 → `sources/` 卡片 + `notes/` 笔记 → 编译进 `wiki/concepts/`。
   见 `.claude/skills/deep-read` 与 `.claude/skills/ingest-wiki`。
2. **query**（查询）：回答问题时**先查 wiki 与 notes**，引用具体文件（`[[slug]]`），不够再上网，并说明哪些来自外部。
3. **research**（调研）：一个主题 issue → `reports/topics/<slug>.md`。见 `.claude/skills/research-topic`。
4. **lint**（体检）：`uv run python -m pipeline.wiki_lint`，修断链、孤儿页、缺 frontmatter。

## 写作规则

- 中文写作，术语保留英文原词（首次出现给中文解释）。
- 结论要有出处：论文结论标注到章节/表格（如「Table 3」），网络来源给链接。**不确定就说不确定，不编造数字。**
- 每篇笔记必须有「对我们的启发」一节：落到沙箱/调度/训练平台的具体能力、成本、风险。
- 新信息与 wiki 已有结论冲突时，不要静默覆盖：在概念页「争议与矛盾」一节并列两方观点和出处。
- 不复制大段原文；引用单句且注明出处。

## 可追溯性（GitHub 即日志）

- 每个 AI 动作 = 一个 PR；要做的事 = 一个 issue。分支：`daily/<date>`、`read/<issue>`、`topic/<issue>`、`report/<week>`。
- **所有 AI 工作都在本地运行**（Claude Code / Codex，用本机登录的订阅），GitHub 只作为 issue / PR 账本，通过本地 `gh` 操作。不在 GitHub Actions 里放任何 LLM 凭据。
- 由 `scripts/run-local.sh` 调起的任务（prompt 里写了“只写文件”）：**只写文件，不要 git commit / push / 开 PR**，脚本统一建分支、提交、`gh pr create`。
  把 PR 描述写到 `.cache/pr_body.md`（说明做了什么、新增/修改了哪些页面、仍有疑问的地方）。
- 用户在交互式会话里直接让你做的事：同样遵守本文件约定；需要留痕时走 `run-local.sh read/topic` 或手动开 PR。

## 常用命令

```bash
uv sync                                   # 安装依赖
uv run python -m pipeline.daily fetch     # 抓取候选 → .cache/candidates.json
uv run python -m pipeline.daily render    # 渲染 inbox + PR 描述
uv run python -m pipeline.wiki_lint       # 知识库体检
uv run python -m pipeline.week_context    # 本周上下文 → .cache/week.json
scripts/run-local.sh all                  # sync → queue → daily（每天 08:00 定时）
scripts/run-local.sh tick                 # sync → queue（每小时 :30 定时）
scripts/run-local.sh read <id>|topic <issue>|report|lint
```
