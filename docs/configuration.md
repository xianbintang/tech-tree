# tech-tree 配置手册

> 日常使用见 [使用手册](usage.md)。

所有配置都是仓库里的文本文件。建议改动也走分支 + PR（`git switch -c config/xxx` → 提交 → `gh pr create`），这样配置变更同样可以追溯。

| 想改什么 | 文件 |
|---|---|
| 研究方向、关键词、每天推多少 | `config/interests.yaml` |
| 订阅哪些论文源 / 博客 | `config/sources.yaml` |
| 推送到飞书 / Slack / Telegram | `config/notify.yaml` + `.env.local` |
| 每天几点跑 | Claude 桌面 App 定时任务 `tech-tree-daily` / `tech-tree-hourly` |
| 笔记格式、写作规则、目录约定 | `CLAUDE.md` |
| 精读 / 调研 / 周报的具体要求 | `.claude/skills/<名称>/SKILL.md` |

## 1. 研究兴趣 `config/interests.yaml`

同一份文件有两个用途：Python 用它做关键词粗排，Claude 用它做精排和写「对我们的启发」。

### 1.1 `research_direction`：给 LLM 看的画像

| 字段 | 作用 | 建议 |
|---|---|---|
| `summary` | 一句话方向 | 方向变了先改这里 |
| `persona` | 你是谁、看论文最关心什么 | 写得越具体，推荐理由和启发越贴近你 |
| `focus_areas` | 核心方向列表 | 精排的第一判断标准 |
| `adjacent_areas` | 相邻方向（附条件） | 写清「在什么条件下才算相关」 |
| `irrelevant_areas` | 一律不要 | 精排会直接排除，即使关键词分很高 |

### 1.2 `scoring`：关键词粗排（零 token）

| 字段 | 打分规则 |
|---|---|
| `keywords` | 标题命中 +3，摘要命中 +1 |
| `domain_boost_keywords` | 命中 1 个 +1，命中 ≥2 个 +2 |
| `negative_keywords` | 命中即丢弃（-999） |

另外，HF 论文会按点赞数加分：已命中关键词时，点赞 ≥2 / ≥5 / ≥10 分别 +1 / +2 / +3；没命中关键词时，只有点赞 ≥20 才 +1，避免热门但无关的论文刷屏。

关键词统一小写，按子串匹配，所以 `rollout` 也会命中 `rollouts`。负向词要谨慎：它会在 LLM 看到之前就把论文丢掉。

### 1.3 `limits`：数量与阈值

| 字段 | 默认 | 含义 |
|---|---|---|
| `paper_min_score` | 2 | 论文进入候选的最低关键词分 |
| `post_min_score` | 2 | 博文进入候选的最低分（= 源的 weight + 关键词分） |
| `paper_max_age_months` | 3 | 丢弃超过 N 个月的论文（HF 热门会翻出老论文） |
| `candidates_papers` / `candidates_posts` | 40 / 25 | 交给 LLM 精排的候选上限（越大越费 token） |
| `pick_papers` / `pick_posts` | 10 / 6 | 每天最终最多推几篇 |

**调参思路**
- 推送太杂：提高 `paper_min_score`，或把噪音方向加进 `irrelevant_areas`。
- 推送太少、漏掉想要的：补 `keywords`，或降低 `paper_min_score`。
- 看不过来：降低 `pick_papers`。

## 2. 订阅源 `config/sources.yaml`

### 2.1 论文源 `papers`

```yaml
papers:
  arxiv:
    categories: [cs.DC, cs.LG, cs.AI, cs.SE, cs.OS, cs.CL]   # arXiv 分类
    max_results_per_day: 1500                              # 每次最多拉多少篇（按投稿时间倒序）
  huggingface:
    daily: true      # HF 每日论文（含前一天）
    trending: true   # HF 热门论文
```

常用分类：cs.CR（安全）、cs.NI（网络）、cs.PF（性能）、cs.MA（多智能体）、cs.RO（机器人）。每多加一个大分类，就应适当调大 `max_results_per_day`。

### 2.2 博文源 `posts`

`window_days: 2` 表示只看最近 2 天发布的文章。每个源的公共字段：

| 字段 | 说明 |
|---|---|
| `name` | 显示名，会出现在推送里 |
| `type` | `rss` / `sitemap` / `html_links` / `hf_models`，见下 |
| `weight` | 加到关键词分上。**≥2 表示每篇都进 LLM 精排**（适合个人 / 实验室博客）；0–1 表示要命中关键词才入围（适合营销稿多的大厂综合博客） |
| `title_filter` | 可选。标题正则白名单，用来过滤噪音大的源 |

四种源类型，按优先级选择：

**① `rss`：有 RSS/Atom 就用它（首选）**

```yaml
- {name: Lilian Weng, type: rss, url: "https://lilianweng.github.io/index.xml", weight: 4}
```

**② `sitemap`：没有 RSS，但有站点地图（JS 渲染的官网大多如此）**

```yaml
- name: Anthropic Engineering
  type: sitemap
  url: "https://www.anthropic.com/sitemap.xml"
  pattern: '^https://www\.anthropic\.com/engineering/[a-z0-9-]+$'   # 只要这类 URL
  weight: 4
```

以「第一次见到」判定新文章；`<lastmod>` 只作辅助过滤，因为有些站点会批量刷新它。
**首次运行只记录已有文章、不推送**，之后只推新增的。

**③ `html_links`：连站点地图都没有，但列表页是服务端渲染的**

```yaml
- name: Meta AI Blog
  type: html_links
  url: "https://ai.meta.com/blog/"
  pattern: 'href="(https://ai\.meta\.com/blog/[a-z0-9-]+/)"'   # 第 1 个捕获组是文章 URL
  base: ""            # 捕获的是相对路径（如 /blog/xxx）时，填站点前缀
  weight: 1
```

首次运行规则同 `sitemap`。标题取自 URL 的 slug，精读时会抓到真实标题。

**④ `hf_models`：官网是纯 JS、没有 feed 的实验室，用 HuggingFace 新模型发布作为信号**

```yaml
- {name: Kimi (Moonshot), type: hf_models, org: moonshotai, weight: 4}
- {name: Tencent Hunyuan, type: hf_models, org: tencent, title_filter: '^(hy|hunyuan)', weight: 3}
```

量化版本（GGUF / AWQ / FP8 / …）会被自动过滤；同一批的 Base / Instruct / Thinking 变体合并成一条。

### 2.3 加一个新源（推荐流程）

1. 找 feed：先试 `<站点>/feed`、`/rss`、`/index.xml`、`/atom.xml`、`/feed.xml`；没有的话试 `/sitemap.xml`。
2. 验证能抓到内容：

   ```bash
   uv run python -c "import feedparser as f; d=f.parse('https://example.com/feed'); print(len(d.entries), d.entries[0].title if d.entries else '')"
   ```

3. 加到 `sources.yaml` 对应分组下，干跑一次看效果：

   ```bash
   NO_PR=1 scripts/run-local.sh daily
   ```

   检查日志里这个源的 `N recent` / `bootstrapping`，再看 `inbox/<日期>.md`。检查完用 `git checkout -- inbox state` 还原。
4. 提 PR 合并。

也可以直接让 Claude 做：在仓库里打开 `claude`，说「把 xxx 的博客加到订阅源，先验证 feed 能用，再提 PR」。

### 2.4 当前订阅（60 个）

- **Anthropic**：Engineering、Research、News、Transformer Circuits
- **OpenAI**：Research、Engineering、Publications、News
- **Google**：DeepMind、Research
- **AWS / Amazon**：Compute、Containers、ML、Architecture、Amazon Science、Werner Vogels
- **Meta**：AI Blog、Engineering
- **DeepSeek**：News、HF 新模型
- **Kimi**：HF 新模型
- **阿里**：Qwen HF 新模型、阿里云博客（已过滤）
- **腾讯**：混元 HF 新模型
- **实验室 / 系统**：Thinking Machines、HuggingFace、vLLM、PyTorch、Together、SemiAnalysis、GitHub、Cloudflare、Fly.io、Kubernetes
- **个人博客**：Karpathy ×2、Lilian Weng、Chip Huyen、Jason Wei、Horace He、Tim Dettmers、Nathan Lambert、Finbarr Timbers、Brendan Gregg、Sebastian Raschka、苏剑林、Eugene Yan、Hamel Husain、Jay Alammar、Jack Clark、Philipp Schmid、Answer.AI、Latent Space、Dwarkesh、Simon Willison

## 3. 推送 `config/notify.yaml` + `.env.local`

`notify.yaml` 只放开关，凭据放在仓库根目录的 `.env.local`。这个文件已被 git 忽略，不会上传。

```yaml
# config/notify.yaml
channels:
  feishu:   {enabled: true,  env: FEISHU_WEBHOOK}
  slack:    {enabled: false, env: SLACK_WEBHOOK}
  telegram: {enabled: false, env_token: TELEGRAM_BOT_TOKEN, env_chat: TELEGRAM_CHAT_ID}
```

```bash
# .env.local（每行一个，不要提交）
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx
```

- **飞书**：群设置 →「群机器人」→ 添加「自定义机器人」→ 复制 webhook。如果开启了「自定义关键词」安全设置，关键词填 `tech-tree`：每条推送都带 PR / issue 链接，链接里包含这个词。
- **Slack**：创建 Incoming Webhook，把 `enabled` 改为 `true`，在 `.env.local` 里写 `SLACK_WEBHOOK=…`。
- **Telegram**：用 @BotFather 建 bot 拿到 token，再取 chat id。把 `enabled` 改为 `true`，写入两个变量。

测试推送：

```bash
set -a; . ./.env.local; set +a
uv run python -m pipeline.notify --title "tech-tree 测试" --text "hello"
```

某个渠道开启了但没配凭据时会被静默跳过；推送失败只记日志，不影响流水线。

## 4. 定时任务

Claude 桌面 App 左侧栏「Scheduled」里有两个任务：

| 任务 | 时间 | 执行 | 作用 |
|---|---|---|---|
| `tech-tree-daily` | 每天 08:00 | `scripts/scheduled.sh all` | sync → queue → daily（出当天推送 PR），周日再加周报 |
| `tech-tree-hourly` | 每小时 :30 | `scripts/scheduled.sh tick` | sync → queue：处理勾选项和待办 issue；没有待办几秒就结束 |

- **不会弹权限确认**：任务只执行 `scripts/scheduled.sh` 这一条固定命令（内部先在空闲时 `git pull` 更新代码，再在后台启动流水线），这条命令已加入本机 `.claude/settings.local.json` 的允许列表：

  ```json
  {"permissions": {"allow": ["Bash(/Users/xianb/workspace/tech-tree/scripts/scheduled.sh *)"]}}
  ```

  只放行这一个脚本，不需要给启动会话开 bypass 全权限。换电脑时记得把这条加回去。
- **定时任务只是启动器**：在后台启动脚本后，会话立刻结束。所以会话显示「完成」不代表流水线跑完了。进度看 `.cache/logs/`，结果看 GitHub / 飞书。
- **不会撞车**：同一时间只允许一个流水线运行（`.cache/lock` 记录进程号），后到的会自动跳过。hourly 放在 :30，就是为了避开 08:00。
- **改时间**：在任务里编辑，或在 Claude 会话里说「把 tech-tree-daily 改到每天 7 点」。
- **立即跑一次**：点「Run now」。注意对 daily 点会多生成一个 `-2` 版推送；只想处理待办，就对 hourly 点。
- **暂停**：关掉任务开关。
- **任务定义**：`~/.claude/scheduled-tasks/<任务名>/SKILL.md`。任务**不会**合并 PR、改代码或删分支。
- **前提**：到点时桌面 App 需要开着；App 关着时错过的任务会在下次打开时补跑。第一次运行时批准的命令权限会保存下来，之后自动沿用。
- **开销**：hourly 每次会启动一个很短的 Claude 会话（只执行一条命令）。只有真正精读、调研时才会消耗较多额度。

不想依赖桌面 App 的话，也可以用系统 crontab 直接调用脚本（同样只用本机的 `claude` 登录态，没有会话开销）：

```bash
0 8 * * *  cd ~/workspace/tech-tree && scripts/run-local.sh all
30 * * * * cd ~/workspace/tech-tree && scripts/run-local.sh tick
```

## 5. Agent 与模型

| 设置 | 方法 |
|---|---|
| 改用 Codex | 命令前加 `AGENT=codex`，Codex 通过 `AGENTS.md`（软链到 `CLAUDE.md`）和 `.agents/skills` 读取同一套规则。如果要在定时任务里切换，编辑任务 prompt，把命令改为 `AGENT=codex scripts/run-local.sh all` |
| Claude 用哪个模型 | 跟随本机 Claude Code 的默认模型设置 |
| 精读时允许的工具 | `scripts/run-local.sh` 里的 `TOOLS` 变量：读写文件、WebFetch/WebSearch、`uv run python -m pipeline.*`、`gh issue view`。agent 不会执行 git 操作，也不能推送 |

## 6. 笔记与知识库格式 `CLAUDE.md`

笔记和概念页的 frontmatter 字段、目录约定、命名规则、写作规则（中文、注明出处、必须有「对我们的启发」、冲突不覆盖）都定义在 `CLAUDE.md`。修改后，下一次精读就会按新规则执行。

各技能的具体产出结构（笔记有哪些小节、周报写什么、调研报告的格式）在 `.claude/skills/<名称>/SKILL.md`，改法相同。

改完建议跑一次体检，确认 lint 规则和新格式一致（必填字段见 `pipeline/wiki_lint.py` 的 `REQUIRED`）：

```bash
scripts/run-local.sh lint
```

## 7. 一次性初始化（换电脑时）

```bash
git clone git@github.com:xianbintang/tech-tree.git ~/workspace/tech-tree
cd ~/workspace/tech-tree
uv sync                        # Python 依赖
gh auth login                  # 如果还没登录
claude                         # 确认 Claude Code 已登录
scripts/setup-github.sh        # 标签 + Pages（仓库已配置过则可跳过）
cp /path/to/old/.env.local .   # 推送凭据（可选）
```

最后在 Claude 桌面 App 里重新创建两个定时任务：让 Claude「每天 08:00 运行 /Users/xianb/workspace/tech-tree/scripts/scheduled.sh all」和「每小时 :30 运行 …/scripts/scheduled.sh tick」，并把第 4 节的允许规则加进 `.claude/settings.local.json`。

## 8. 重置与维护

| 操作 | 方法 |
|---|---|
| 让某篇文章可以被重新推送 | 从 `state/seen/*.txt` 删掉对应行（论文是 `arxiv:<ID>`，博文是 `post:<哈希>`）后提交 |
| 重新初始化某个无 RSS 源 | 删掉该源在 `state/seen/` 里的记录会导致再次「首次运行」，一般不需要这样做 |
| 清理本地缓存 | `rm -rf .cache`（只放临时文件，随时可删） |
| 看历史 | 所有 AI 动作都在 GitHub 的 PR 列表里，可按标签筛选 `daily` / `note` / `report` |
