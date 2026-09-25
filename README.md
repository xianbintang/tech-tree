# tech-tree

AI-native 的论文 / 技术博文学习流水线 + 个人知识库。

每日自动拉取 → AI 精排推送 → 勾选精读 → 沉淀为互链知识库 → 专题调研 → 周报。
**每一步都是一个 GitHub PR 或 issue**，全程可追溯；Claude Code 与 Codex 都能驱动；云端（GitHub Actions）和本地（Claude Code / Codex / Cowork 定时任务）两种跑法产出完全一致。

```
 arXiv · HF Daily/Trending · RSS 博客 · 无 RSS 站点列表页
        │  daily-ingest（每天 08:00，纯 Python 抓取 + 关键词粗排）
        ▼
 LLM 精排 + 中文 TL;DR（triage skill）
        │
        ▼
 PR「daily: 2026-09-25 (8 papers, 2 posts)」 ──推送──▶ 飞书 / Slack / Telegram
        │  你在 PR 描述里勾选想读的 → 合并
        ▼
 issue「[read] …」(to-read) ──▶ deep-read ──▶ PR「read: …」
        │                         笔记 notes/ + 元数据 sources/ + 概念页 wiki/concepts/
        ▼
 issue「[topic] …」(research-topic) ──▶ research ──▶ PR「topic: …」 reports/topics/
        │
 每周日 weekly-report ──▶ PR「report: 学习周报 2026-W39」
 每周一 wiki-lint ──▶ issue（断链 / 孤儿页 / 缺 frontmatter）
 合并到 master ──▶ GitHub Pages 站点
```

设计参考：[zotero-arxiv-daily](https://github.com/TideDra/zotero-arxiv-daily)（Actions 零成本每日跑 + 两级筛选）、
[ArxivDigest](https://github.com/AutoLLM/ArxivDigest)（自然语言兴趣画像 + LLM 打分）、
[Karpathy LLM Wiki](https://github.com/Astro-Han/karpathy-llm-wiki)（raw → wiki → schema 三层，ingest / query / lint）、
[claude-code-action](https://github.com/anthropics/claude-code-action) / [codex-action](https://github.com/openai/codex-action)，
以及本机已装的 dailypaper-skills（抓取打分逻辑移植自其 `fetch_and_score.py`）。

## 日常怎么用

| 想做的事 | 操作 |
|---|---|
| 看今天推送 | 打开 `daily` PR（或点飞书消息），勾选想读的条目，合并 |
| 精读指定论文 | 新建 issue → 选「📖 精读」模板，填 arXiv ID / URL |
| 调研一个主题 | 新建 issue → 选「🔎 调研」模板 |
| 问知识库问题 / 让 AI 改笔记 | 任意 issue / PR 下评论 `@claude …` |
| 加订阅源 | 改 `config/sources.yaml`，或开「➕ 新增订阅源」issue |
| 调整兴趣方向 | 改 `config/interests.yaml` |
| 本地跑（走订阅额度） | `scripts/run-local.sh daily \| read <id> \| topic <issue> \| report` |

## 目录

```
config/        interests.yaml（兴趣画像+关键词）· sources.yaml（订阅源）· notify.yaml（推送渠道）
pipeline/      确定性步骤（无 LLM）：抓取、打分、去重、渲染、推送、lint、周上下文
.claude/skills/  triage · deep-read · ingest-wiki · research-topic · weekly-report（Codex 经 .agents/skills 共用）
.github/       workflows/ · actions/run-agent（Claude/Codex 切换）· issue & PR 模板
inbox/         每日推送        sources/  元数据卡（raw 层）
notes/         精读笔记        wiki/     概念页（编译层）
reports/       周报 / 专题     state/    去重记录
CLAUDE.md      知识库 schema 与 agent 守则（AGENTS.md → 软链）
```

## 初始化（一次性）

```bash
# 1. 标签、允许 Actions 开 PR、启用 Pages
scripts/setup-github.sh

# 2. LLM 凭据（二选一或都配）
claude setup-token                                   # 生成订阅 OAuth token（走 Pro/Max 额度）
gh secret set CLAUDE_CODE_OAUTH_TOKEN                # 粘贴上一步的 token
# gh secret set ANTHROPIC_API_KEY                    # 或：按量计费 API key
# gh secret set OPENAI_API_KEY && gh variable set AI_AGENT --body codex   # 改用 Codex

# 3. 推送渠道（按需）
gh secret set FEISHU_WEBHOOK                         # 飞书自定义机器人 webhook
# gh secret set SLACK_WEBHOOK / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID，并在 config/notify.yaml 打开

# 4. 手动试跑一次
gh workflow run daily-ingest.yml
```

`@claude` 评论功能需要安装 Claude GitHub App（在交互式 `claude` 终端里运行 `/install-github-app`）。其余 workflow 不依赖它。

可选仓库变量（`gh variable set`）：`AI_AGENT`（claude|codex）、`TRIAGE_MODEL` / `READ_MODEL` / `RESEARCH_MODEL` / `REPORT_MODEL`、`AUTO_DEEP_READ=false`（合并 daily PR 只建 issue 不自动精读）。

## 成本

- **GitHub Actions**：本仓库公开 → 分钟数免费不限量（私有仓库免费账号 2000 分钟/月，也够用）。
- **LLM**：抓取、去重、渲染、推送、lint、建站都是纯 Python，零 token。LLM 只用在：每日精排（1 次/天，小）、精读（按你勾选的篇数）、调研、周报。
  用 `CLAUDE_CODE_OAUTH_TOKEN` 时消耗的是订阅额度，不另付 API 费用。

## 本地 / Cowork / Codex

`scripts/run-local.sh` 与云端 workflow 使用同一套 skill 和 pipeline，区别只是由本机的 `claude` / `codex` 执行、`gh pr create` 开 PR：

```bash
scripts/run-local.sh read 2609.23377            # 精读（自动建 issue 以便追溯）
AGENT=codex scripts/run-local.sh topic 12       # 用 Codex 做调研
NO_PR=1 scripts/run-local.sh daily              # 只生成文件，不建分支/PR
```

放进 Cowork 或 Claude Code 定时任务，prompt 写「在 ~/workspace/tech-tree 运行 scripts/run-local.sh daily」即可。
云端和本地都开着时，按日期命名的分支（`daily/<date>`）会互相去重，不会重复推送。

## 安全

- 公开仓库里，只有有写权限的人能打标签 / 触发 workflow_dispatch / 召唤 `@claude`；陌生人用 issue 模板建的 issue 不会带上触发标签。
- 自动任务里的 agent 只写文件，git 提交与开 PR 由 workflow 完成；凭据只在 Secrets 里。
