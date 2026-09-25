# tech-tree 使用手册

> 配置相关（改兴趣、加订阅源、推送、定时）见 [配置手册](configuration.md)。

## 1. 这是什么

一条 **以论文为主、技术博文为辅** 的个人学习流水线：

```
每日拉取 → AI 精排推送 → 你勾选 → AI 精读 → 沉淀为知识库 → 专题调研 → 周报
```

两条核心原则：

1. **AI 全部在本机跑。** 精排、精读、调研、周报都由你电脑上的 Claude Code（或 Codex）完成，用的是本机登录的订阅。GitHub 上不存放任何模型凭据。
2. **GitHub 是账本。** 每个 AI 动作都产出一个 PR，每件待办都是一个 issue。做过什么、为什么做、改了哪些页面，全部可以在 GitHub 上追溯。

| 组件 | 位置 | 作用 |
|---|---|---|
| 流水线入口 | `scripts/run-local.sh` | 所有操作都从这里发起 |
| 确定性步骤 | `pipeline/` | 抓取、打分、去重、渲染、推送、体检。纯 Python，不消耗 token |
| AI 技能 | `.claude/skills/` | triage（精排）· deep-read（精读）· ingest-wiki（沉淀）· research-topic（调研）· weekly-report（周报） |
| 知识库守则 | `CLAUDE.md`（= `AGENTS.md`） | 目录约定、笔记格式、写作规则。Claude Code 和 Codex 读同一份 |
| 定时任务 | Claude 桌面 App →「Scheduled」→ `tech-tree-daily` | 每天 18:00 自动跑一次 |
| 阅读站点 | <https://xianbintang.github.io/tech-tree/> | 知识库的网页版，合并到 master 后自动更新 |

## 2. 每天怎么用（5 分钟）

```
18:00  定时任务自动运行 ──▶ 生成「daily: <日期> (N papers, M posts)」PR（+ 飞书推送，如已配置）
  │
你    打开 daily PR ──▶ 在 PR 描述里勾选想精读的条目 ──▶ Merge
  │                     （TL;DR / 推荐理由 / 摘要在「Files changed」的 inbox/<日期>.md）
  │
次日 18:00  勾选项自动变成 [read] issue ──▶ 本地精读 ──▶「read: <标题>」PR
  │
你    打开 read PR，看笔记 notes/…、概念页 wiki/concepts/… ──▶ Merge（issue 自动关闭）
```

手机上用 GitHub App 就能完成勾选和合并，电脑只需要 18:00 时开着 Claude 桌面 App。

**不想读的推送：** 什么都不勾，直接 Merge 或 Close 都可以。推过的内容已经记入去重，不会重复推送。
**PR 堆积了：** daily PR 之间互不冲突，可以攒几天一起处理。

## 3. 功能说明

### 3.1 每日推送（daily）

- **来源**：arXiv（6 个分类，每天约 1500 篇）、HuggingFace 每日论文与热门论文、60 个博客 / 实验室源。完整列表见 `config/sources.yaml`。
- **两级筛选**：
  1. 关键词打分粗排（零 token），留下约 40 篇论文和 25 篇博文作为候选。
  2. Claude 按你的研究画像精排，选出最多 10 篇论文和 6 篇博文，每篇写中文 TL;DR 和推荐理由，每天最多 2 篇 ⭐ 必读。
- **去重**：推过的（包括候选里没入选的）不会再推。还没合并的 daily PR 里的内容也算已推。
- **同一天跑第二次**：会生成 `daily/<日期>-2`，只包含第一版之后的新内容。
- **精排失败**（额度用完、网络问题）：自动回退到关键词排序，当天推送不中断。PR 里会标明「精排：keyword」。

### 3.2 精读（deep-read）

对一篇论文或博文产出三样东西：

| 产物 | 路径 | 内容 |
|---|---|---|
| 元数据卡 | `sources/papers/<arXiv ID>.md` | 标题、作者、链接、摘要（不存全文） |
| 精读笔记 | `notes/papers/<arXiv ID>.md` | 一句话总结、问题、方法（含架构图 / 公式）、实验数字（注明 Table/Figure）、局限、**对我们的启发**、相关概念 |
| 概念页更新 | `wiki/concepts/*.md` | 新建或更新相关概念，补双向链接，冲突结论写进「争议与矛盾」 |

博文的笔记路径是 `notes/posts/<日期>-<slug>.md`。

有三种触发方式：

| 方式 | 何时执行 |
|---|---|
| 在 daily PR 里勾选后合并 | 下次运行 |
| 新建 issue，用「📖 精读一篇论文 / 博文」模板 | 下次运行 |
| `scripts/run-local.sh read 2609.23377`（也可以是 URL 或 issue 号） | 立即执行（会自动建 issue 以便追溯） |

每次运行默认最多精读 3 篇（`QUEUE_READS`），多出来的排到下一次。

### 3.3 知识库沉淀（ingest-wiki，LLM-Wiki 模式）

知识分三层：

- **raw**：`sources/`，原始来源的元数据
- **笔记**：`notes/`，单篇精读
- **wiki**：`wiki/concepts/`，跨论文编译出的概念页。这是真正沉淀下来的东西

每次精读都会自动更新 wiki。概念页记录每个结论的出处，出现新旧矛盾时两方并列，不静默覆盖。页面之间用 `[[slug]]` 双链互相引用，在站点上可以直接点击跳转。

### 3.4 专题调研（research-topic）

1. 新建 issue，选「🔎 调研一个主题」模板，写想回答的问题、背景和深度（brief 快速简报 / deep 深度调研）。
2. 下次运行时（每次最多 1 个），Claude 先查你自己的知识库，再上网补充。产出 `reports/topics/<slug>.md`：TL;DR、方案对比表、对我们的建议、推荐精读清单。
3. 报告 PR 里的推荐精读清单也是勾选框。勾选后合并，这些论文会自动进入精读队列。

想立即执行：`scripts/run-local.sh topic <issue号>`。

### 3.5 周报（weekly-report）

定时任务每周日会额外生成 `reports/weekly/<年>-W<周>.md`，内容包括：本周数字、3–5 条跨论文洞见、趋势、知识图谱变化、积压清单、下周建议。
手动生成：`scripts/run-local.sh report`。

### 3.6 知识库问答（query）

在仓库目录里打开 Claude Code，直接提问：

```bash
cd ~/workspace/tech-tree && claude
```

> 我们知识库里关于 SWE agent RL 训练的环境构造有哪些做法？各自成本多少？

`CLAUDE.md` 要求它先查 `wiki/` 和 `notes/`，引用具体页面，不够时再上网，并标明哪些内容来自外部。

### 3.7 知识库体检（lint）

`scripts/run-local.sh lint` 检查四类问题：断链、孤儿概念页、没有链接任何概念的笔记、frontmatter 缺字段。每次精读结束也会自动跑一遍。

### 3.8 阅读站点

合并到 master 后，GitHub Pages 会自动重建 <https://xianbintang.github.io/tech-tree/>。站点支持中文搜索、`[[双链]]` 跳转、公式和 mermaid 图。这是仓库里唯一的 GitHub Action，只做静态构建，不调用模型，也不使用任何密钥。

## 4. 命令参考

所有命令都在仓库根目录执行。

| 命令 | 作用 |
|---|---|
| `scripts/run-local.sh all` | 依次跑 sync → queue → daily（定时任务跑的就是这条） |
| `scripts/run-local.sh daily [YYYY-MM-DD]` | 抓取 + 精排，生成 daily PR |
| `scripts/run-local.sh sync` | 最近 14 天内已合并 PR 里的勾选项转成 `to-read` issue（幂等，重复跑不会重复建） |
| `scripts/run-local.sh queue` | 处理打开状态的 `to-read` / `research-topic` issue |
| `scripts/run-local.sh read <issue号 \| arXiv ID \| URL>` | 立即精读 |
| `scripts/run-local.sh topic <issue号>` | 立即调研 |
| `scripts/run-local.sh report` | 生成本周周报 |
| `scripts/run-local.sh lint` | 知识库体检 |

环境变量开关：

| 变量 | 默认 | 说明 |
|---|---|---|
| `AGENT` | `claude` | 设为 `codex` 改用 Codex CLI |
| `NO_PR` | 空 | 设为 `1` 时只写文件，不建分支、不开 PR（调试用） |
| `BASE` | `master` | 从哪个分支切出、向哪个分支提 PR |
| `QUEUE_READS` | `3` | 每次 queue 最多精读几篇 |
| `QUEUE_TOPICS` | `1` | 每次 queue 最多调研几个 |

示例：

```bash
AGENT=codex scripts/run-local.sh read https://www.anthropic.com/engineering/claude-code-sandboxing
QUEUE_READS=6 scripts/run-local.sh queue
NO_PR=1 scripts/run-local.sh daily
```

## 5. GitHub 约定

### 标签

| 标签 | 含义 |
|---|---|
| `daily` | 每日推送 PR |
| `to-read` → `reading` | 待精读 → 精读中（本地已领取，PR 已开或正在跑） |
| `note` | 精读笔记 PR |
| `research-topic` → `researching` | 待调研 → 调研中 |
| `report` | 周报 / 专题报告 PR |
| `source:paper` / `source:post` | 来源类型 |
| `priority:p0/p1/p2` | 你自己标注的优先级（可选） |

### issue 状态流转

```
[read] issue  (to-read)
   │ queue 领取：加 reading
   ▼
read PR「Closes #N」 ── 你 Merge ──▶ issue 自动关闭
   │ 运行失败：去掉 reading 并留言 ──▶ 下次 queue 自动重试
```

### 分支命名

`daily/<日期>[-2]`、`read/<issue>`、`topic/<issue>`、`report/<年>-W<周>`。每个 PR 描述末尾会注明「本地运行 · agent · 主机名」。

### 安全边界

陌生人在公开仓库开的 issue 不会带上 `to-read` / `research-topic` 标签（加标签需要 triage 权限），所以不会进入你的本地队列。

## 6. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 18:00 没有生成 PR | 桌面 App 没开，或定时任务在等权限确认。打开侧边栏「Scheduled」→ `tech-tree-daily` 查看；App 关着时错过的任务会在下次启动时补跑 |
| `another run in progress (.cache/lock)` | 上一次运行还没结束，或异常退出后锁没删。确认没有在跑后执行 `rmdir .cache/lock` |
| `working tree has uncommitted KB changes` | 主仓库的 `inbox/ notes/ wiki/ …` 下有未提交的改动。先提交或 stash；自己手改知识库请走分支 + PR |
| PR 里写「精排：keyword」 | 当天 LLM 精排失败，已回退到关键词排序，不影响使用 |
| 某个博客一直没内容 | 可能是那段时间没更新，也可能 feed 失效。看运行日志里的 `[WARN]`，或参考配置手册里的「验证订阅源」 |
| 新加的无 RSS 源第一次没推送 | 设计如此：`sitemap` / `html_links` 类型首次运行只记录已有文章，之后只推新文章 |
| 精读失败 | issue 上会有 ❌ 留言，下次 queue 会自动重试。想立即重试：`scripts/run-local.sh read <issue号>` |
| 想重读已读过的论文 | `scripts/run-local.sh read <arXiv ID>`，会在已有笔记上补充修订，而不是重写 |
