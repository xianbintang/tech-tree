# tech-tree

AI-native 的论文 / 技术博文学习流水线 + 个人知识库。

每日拉取 → AI 精排推送 → 勾选精读 → 沉淀为互链知识库 → 专题调研 → 周报。
**所有 AI 工作都在本机由 Claude Code（或 Codex）完成**，用的是本机登录的订阅，不把任何 LLM token 放到 GitHub；
GitHub 只是 issue / PR 账本（本地 `gh` 操作），每一步都有 PR 或 issue 可追溯。

```
 arXiv · HF Daily/Trending · RSS 博客 · 无 RSS 站点列表页
        │  run-local.sh daily：纯 Python 抓取 + 关键词粗排（零 token）
        ▼
 本地 claude -p：LLM 精排 + 中文 TL;DR（triage skill）
        │
        ▼
 PR「daily: 2026-09-25 (10 papers, 1 posts)」 ──推送──▶ 飞书 / Slack / Telegram（可选）
        │  你在 PR 描述里勾选想读的 → 合并（手机上也能操作）
        ▼
 run-local.sh sync：勾选项 → issue「[read] …」(to-read)
 run-local.sh queue：本地 claude 精读 ──▶ PR「read: …」
        │               笔记 notes/ + 元数据 sources/ + 概念页 wiki/concepts/
        ▼
 issue「[topic] …」(research-topic) ──queue──▶ PR「topic: …」 reports/topics/
 run-local.sh report ──▶ PR「report: 学习周报 2026-W39」
 合并到 master ──▶ GitHub Pages 站点（唯一的 Action，不含任何密钥）
```

设计参考：[zotero-arxiv-daily](https://github.com/TideDra/zotero-arxiv-daily)（两级筛选）、
[ArxivDigest](https://github.com/AutoLLM/ArxivDigest)（自然语言兴趣画像 + LLM 打分）、
[Karpathy LLM Wiki](https://github.com/Astro-Han/karpathy-llm-wiki)（raw → wiki → schema 三层，ingest / query / lint），
以及本机已装的 dailypaper-skills（抓取打分逻辑移植自其 `fetch_and_score.py`）。

📘 **[使用手册](docs/usage.md)** · ⚙️ **[配置手册](docs/configuration.md)**

## 日常怎么用

| 想做的事 | 操作 |
|---|---|
| 每天自动跑 | 桌面 App 定时任务 `tech-tree-daily` 每天 18:00 执行 `scripts/run-local.sh all`（sync → queue → daily，周日加周报） |
| 看今天推送 | 打开 `daily` PR，勾选想读的条目，合并；下次运行自动精读 |
| 精读指定论文 | 开「📖 精读」issue 排队，或立即 `scripts/run-local.sh read 2609.23377` |
| 调研一个主题 | 开「🔎 调研」issue 排队，或立即 `scripts/run-local.sh topic <issue>` |
| 周报 | `scripts/run-local.sh report`（可设每周定时） |
| 问知识库问题 | 在本仓库里开 `claude`，直接问（CLAUDE.md 规定先查 wiki 再上网） |
| 加订阅源 / 调兴趣 | 改 `config/sources.yaml` / `config/interests.yaml` |

`AGENT=codex` 切换到 Codex；`NO_PR=1` 只写文件不开 PR；`QUEUE_READS=3` 控制每次精读篇数。

## 目录

```
config/          interests.yaml（兴趣画像+关键词）· sources.yaml（订阅源）· notify.yaml（推送渠道）
pipeline/        确定性步骤（无 LLM）：抓取、打分、去重、渲染、推送、lint、周上下文、勾选→issue
.claude/skills/  triage · deep-read · ingest-wiki · research-topic · weekly-report（Codex 经 .agents/skills 共用）
scripts/         run-local.sh（唯一入口）· setup-github.sh · build_site.sh
inbox/  每日推送   sources/  元数据卡（raw 层）   notes/  精读笔记   wiki/  概念页（编译层）
reports/  周报 / 专题   state/  去重记录   CLAUDE.md  知识库 schema 与 agent 守则（AGENTS.md → 软链）
```

## 初始化（一次性）

```bash
uv sync
scripts/setup-github.sh        # 建标签 + 启用 Pages
echo 'FEISHU_WEBHOOK=https://open.feishu.cn/...' > .env.local   # 可选推送；git 已忽略，不会上传
```

## 安全

- LLM 凭据只存在本机（Claude Code / Codex 自己的登录态），GitHub 上没有任何 secret。
- 唯一的 GitHub Action 是 Pages 构建，只用内置只读 token，不调用任何模型。
- 公开仓库里，陌生人开的 issue 不会带上 `to-read` / `research-topic` 标签（需要 triage 权限），所以不会进入本地队列。
