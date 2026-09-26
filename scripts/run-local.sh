#!/usr/bin/env bash
# The whole pipeline runs locally: Claude Code (or Codex) on your own machine and
# subscription does the AI work; GitHub is only used as the issue/PR ledger via `gh`.
# No LLM credentials ever leave this machine.
#
#   scripts/run-local.sh all                 # sync → queue → daily（周日再加 report）；每天 08:00 定时
#   scripts/run-local.sh tick                # sync → queue：有待办才干活；每小时 :30 定时
#   scripts/run-local.sh bg <命令…>          # 后台运行，日志在 .cache/logs/（定时任务经 scripts/scheduled.sh 调用）
#   scripts/run-local.sh daily [YYYY-MM-DD]  # 抓取 + 精排 → daily/<date> PR
#   scripts/run-local.sh sync                # 已合并 PR 里勾选的条目 → to-read issue
#   scripts/run-local.sh queue               # 处理待办：open 的 to-read / research-topic issue
#   scripts/run-local.sh read  <issue | arXiv-id | URL>
#   scripts/run-local.sh batch <reading-list issue> [max]   # 一个分类精读成一个 PR（默认最多 BATCH_MAX=8 篇）
#   scripts/run-local.sh topic <issue>
#   scripts/run-local.sh report              # 周报 → report/<week> PR
#   scripts/run-local.sh lint                # 知识库体检（本地打印）
#
#   AGENT=codex …      用 Codex 代替 Claude Code
#   NO_PR=1 …          只写文件，不建分支 / PR
#   BASE=<branch> …    从别的分支切出并向它提 PR（默认 master）
#   QUEUE_READS=3 QUEUE_TOPICS=1   queue 每次最多处理的数量（控制用量）
set -Eeuo pipefail
cd "$(dirname "$0")/.."

# Local-only secrets (FEISHU_WEBHOOK, …). Git-ignored; never leaves this machine.
if [ -f .env.local ]; then set -a; . ./.env.local; set +a; fi

AGENT=${AGENT:-claude}
BASE=${BASE:-master}
TODAY=$(TZ=Asia/Shanghai date +%F)
TOOLS="Read,Write,Edit,Glob,Grep,WebFetch,WebSearch,Bash(uv run python -m pipeline.*),Bash(ls:*),Bash(gh issue view:*),mcp__firecrawl__firecrawl_scrape"
TRAILER="Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
ORIG_BRANCH=$(git branch --show-current)
mkdir -p .cache/logs

# Detach and return immediately (for scheduled tasks, whose session may end first).
if [ "${1:-}" = bg ]; then
  shift
  nohup "$0" "$@" >/dev/null 2>&1 &
  echo "started \`$*\` in background (pid $!); logs: $(pwd)/.cache/logs/"
  exit 0
fi

# Every top-level run keeps a log; nested calls ("$0" read …) append to the same one.
if [ -z "${TT_LOG:-}" ] && [ -n "${1:-}" ]; then
  export TT_LOG=".cache/logs/$(date +%F_%H%M%S)-$1.log"
  exec > >(tee -a "$TT_LOG") 2>&1
  find .cache/logs -name '*.log' -mtime +30 -delete 2>/dev/null || true
fi

# One pipeline run at a time. Stale locks (dead pid, or pid-less and >3h old) are cleared.
acquire_lock() {
  if ! mkdir .cache/lock 2>/dev/null; then
    local pid; pid=$(cat .cache/lock/pid 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "another run in progress (pid $pid); skipping"; exit 0
    fi
    if [ -z "$pid" ] && [ -n "$(find .cache/lock -maxdepth 0 -mmin -180)" ]; then
      echo "another run in progress (.cache/lock); skipping"; exit 0
    fi
    echo "clearing stale lock"; rm -rf .cache/lock; mkdir .cache/lock
  fi
  echo $$ > .cache/lock/pid
  trap 'rm -rf .cache/lock' EXIT
}

agent() {
  case "$AGENT" in
    claude) claude -p "$1" --allowedTools "$TOOLS" --permission-mode acceptEdits ;;
    codex)  codex exec --full-auto "$1" ;;
    *) echo "unknown AGENT=$AGENT" >&2; exit 1 ;;
  esac
}

start_branch() {
  [ -n "${NO_PR:-}" ] && return
  if [ -n "$(git status --porcelain -- inbox notes wiki reports sources state)" ]; then
    echo "working tree has uncommitted KB changes; commit or stash first" >&2; exit 1
  fi
  git fetch -q origin "$BASE"
  git switch -q -C "$1" "origin/$BASE"
}

back() { [ -n "${NO_PR:-}" ] || git switch -q "$ORIG_BRANCH"; }

finish_pr() {  # $1 branch  $2 title  $3 label  $4.. paths ; last stdout line = PR url
  local branch=$1 title=$2 label=$3; shift 3
  if [ -n "${NO_PR:-}" ]; then echo "NO_PR set; files written, skipping git."; return; fi
  git add -- "$@"
  if git diff --cached --quiet; then
    echo "nothing changed"; back; git branch -q -D "$branch"; return 1
  fi
  git commit -q -m "$title" -m "$TRAILER"
  git push -q -f -u origin "$branch"
  [ -s .cache/pr_body.md ] || echo "$title" > .cache/pr_body.md
  printf '\n\n<sub>本地运行 · agent: %s · %s</sub>\n' "$AGENT" "$(hostname -s)" >> .cache/pr_body.md
  local url
  url=$(gh pr create --base "$BASE" --head "$branch" --title "$title" --label "$label" --body-file .cache/pr_body.md)
  back
  echo "$url"
}

notify() {  # $1 title ; body from .cache/notify.txt ; $2 url
  touch .cache/notify.txt
  uv run python -m pipeline.notify --title "$1" --text-file .cache/notify.txt --url "${2:-}" || true
}

load_issue() { gh issue view "$1" --json number,title,body,labels > .cache/issue.json; }

# Mark an issue in-progress; on failure, undo the mark and leave a comment so queue retries it.
claim() {  # $1 issue  $2 label
  CLAIMED_ISSUE=$1 CLAIMED_LABEL=$2
  trap 'gh issue edit "$CLAIMED_ISSUE" --remove-label "$CLAIMED_LABEL" >/dev/null 2>&1 || true;
        gh issue comment "$CLAIMED_ISSUE" --body "❌ 本地运行失败（$(hostname -s)，$(date "+%F %T")），下次 queue 会重试。" >/dev/null 2>&1 || true;
        back 2>/dev/null || true' ERR
  gh issue edit "$1" --add-label "$2" >/dev/null
}
release() { trap - ERR; }

uv sync -q
mkdir -p .cache
rm -f .cache/pr_body.md .cache/notify.txt .cache/triage.json

case "${1:-}" in
  all)
    acquire_lock
    "$0" sync  || echo "::sync failed"
    "$0" queue || echo "::queue failed"
    "$0" daily || echo "::daily failed"
    if [ "$(TZ=Asia/Shanghai date +%u)" = 7 ]; then "$0" report || echo "::report failed"; fi
    ;;

  tick)
    acquire_lock
    "$0" sync  || echo "::sync failed"
    "$0" queue || echo "::queue failed"
    ;;

  daily)
    day=${2:-$TODAY}
    # A 2nd run on the same day becomes edition "-2" (only items new since the 1st).
    edition=""; n=1
    while [ -z "${NO_PR:-}" ] && gh pr list --state all --head "daily/$day$edition" --json number --jq '.[].number' | grep -q .; do
      n=$((n + 1)); edition="-$n"
    done
    name="$day$edition"
    start_branch "daily/$name"
    : > .cache/extra_seen.txt
    git fetch -q origin '+refs/heads/daily/*:refs/remotes/origin/daily/*' 2>/dev/null || true
    for b in $(git branch -r --list 'origin/daily/*'); do
      git ls-tree -r --name-only "$b" state/seen | while read -r f; do git show "$b:$f" >> .cache/extra_seen.txt; done
    done
    uv run python -m pipeline.daily fetch --date "$day"
    agent "按 .claude/skills/triage/SKILL.md 执行每日精排：读取 .cache/candidates.json 与 config/interests.yaml，输出 .cache/triage.json。只写这一个文件。" \
      || echo "triage failed, falling back to keyword ranking"
    python3 -m json.tool .cache/triage.json >/dev/null 2>&1 || rm -f .cache/triage.json
    rm -f .cache/render.out
    GITHUB_OUTPUT=.cache/render.out uv run python -m pipeline.daily render --edition "$edition"
    if ! grep -q '^count=[1-9]' .cache/render.out; then
      # Nothing worth pushing today; still record dedup state.
      finish_pr "daily/$name" "state: $name" daily state >/dev/null || true; exit 0
    fi
    url=$(finish_pr "daily/$name" "$(cat .cache/pr_title.txt)" daily inbox state | tail -1) || exit 0
    grep -E '^(> |- \[ \])' .cache/pr_body.md | sed -E 's/<!--.*-->//; s/^- \[ \] /• /; s/\*\*//g' | head -16 > .cache/notify.txt
    echo "$url"
    notify "📚 $(cat .cache/pr_title.txt)" "$url"
    ;;

  sync)
    uv run python -m pipeline.inbox_issues --recent-days 14
    ;;

  queue)
    # Reading lists: at most one category batch (= one PR) per tick.
    for n in $(gh issue list --state open --label to-read --label reading-list --json number,labels \
                 --jq '[.[] | select([.labels[].name] | index("reading") | not)] | sort_by(.number) | .[:1] | .[].number'); do
      "$0" batch "$n" || echo "::batch #$n failed"
    done
    for n in $(gh issue list --state open --label to-read --json number,labels \
                 --jq '[.[] | select([.labels[].name] | (index("reading") or index("reading-list")) | not)] | .[:'"${QUEUE_READS:-3}"'] | .[].number'); do
      "$0" read "$n" || echo "::read #$n failed"
    done
    for n in $(gh issue list --state open --label research-topic --json number,labels \
                 --jq '[.[] | select([.labels[].name] | index("researching") | not)] | .[:'"${QUEUE_TOPICS:-1}"'] | .[].number'); do
      "$0" topic "$n" || echo "::topic #$n failed"
    done
    ;;

  batch)
    issue=${2:?usage: batch <reading-list issue> [max]}
    max=${3:-${BATCH_MAX:-8}}
    claim "$issue" reading
    load_issue "$issue"
    uv run python -m pipeline.reading_list next "$issue" --max "$max" > .cache/batch.json
    count=$(jq length .cache/batch.json)
    if [ "$count" -eq 0 ]; then
      echo "#$issue: nothing left to read"; release
      gh issue edit "$issue" --remove-label reading --remove-label to-read >/dev/null; exit 0
    fi
    category=$(jq -r '.title | sub("^\\[reading-list\\] *"; "")' .cache/issue.json)
    n=$(( $(gh pr list --state all --json headRefName \
          --jq "[.[] | select(.headRefName | startswith(\"batch/$issue-\"))] | length") + 1 ))
    branch="batch/$issue-$n"
    start_branch "$branch"
    : > .cache/batch_summaries.md
    done_ids=()
    for i in $(seq 0 $((count - 1))); do
      jq ".[$i]" .cache/batch.json > .cache/item.json
      id=$(jq -r .id .cache/item.json); type=$(jq -r .type .cache/item.json); ititle=$(jq -r .title .cache/item.json)
      echo "── [$((i + 1))/$count] $ititle"
      rm -f .cache/item_summary.md
      if agent "按 .claude/skills/deep-read/SKILL.md 精读一篇：条目信息在 .cache/item.json（来自阅读清单 issue #$issue「$category」；why 字段是读它的原因；parent 字段是母论文 ID）。
笔记文件名用条目 id：${type}s → notes/${type}s/$id.md，元数据卡 sources/${type}s/$id.md，frontmatter 写 id: \"$id\"、issue: $issue、parent: \"$(jq -r .parent .cache/item.json)\"。
完成后按 .claude/skills/ingest-wiki/SKILL.md 更新 wiki/concepts。今天是 $TODAY。只写文件，不做 git 操作，不写 .cache/pr_body.md。
最后把本篇 3–5 行中文摘要（标题、核心贡献、与母论文的关系、对我们的启发）写到 .cache/item_summary.md。" \
         && [ -f "notes/${type}s/$id.md" ]; then
        done_ids+=("$id")
        { echo "### $ititle"; echo "笔记：notes/${type}s/$id.md"; cat .cache/item_summary.md 2>/dev/null; echo; } >> .cache/batch_summaries.md
      else
        echo "::item $id failed (no notes/${type}s/$id.md)"
      fi
    done
    if [ ${#done_ids[@]} -eq 0 ]; then echo "::batch #$issue produced nothing"; false; fi
    uv run python -m pipeline.wiki_lint >/dev/null 2>&1 || true
    left=$(( $(uv run python -m pipeline.reading_list left "$issue") - ${#done_ids[@]} ))
    agent "为阅读清单分类「$category」（issue #$issue）这批精读写 PR 描述到 .cache/pr_body.md，并写 3 行以内推送摘要到 .cache/notify.txt。
素材：.cache/batch_summaries.md（逐篇摘要）、对应的 notes/ 笔记、本次新增或更新的 wiki/concepts/ 页面、母论文笔记（若存在）。
PR 描述结构：## 综述（一段到三段：这些工作之间的关系与演进、各自对应母论文哪些机制、对我们沙箱/调度平台的启发）；## 逐篇（每篇一行：标题 — 一句话 — 笔记路径）；## 知识库变化（新建/更新的概念页）；## 值得追问（可转成 issue 的问题）。
只写这两个文件，不改其它文件，不做 git 操作。" || echo "## ${category}（${#done_ids[@]} 篇）" > .cache/pr_body.md
    if [ "$left" -le 0 ]; then printf '\n\nCloses #%s\n' "$issue" >> .cache/pr_body.md
    else printf '\n\nRefs #%s（本分类还剩 %s 篇，下一批会继续）\n' "$issue" "$left" >> .cache/pr_body.md; fi
    url=$(finish_pr "$branch" "read(batch): ${category}（${#done_ids[@]} 篇）" note sources notes wiki | tail -1)
    release
    echo "$url"
    if [ -z "${NO_PR:-}" ]; then
      uv run python -m pipeline.reading_list tick "$issue" "${done_ids[@]}"
      gh issue edit "$issue" --remove-label reading >/dev/null
      [ "$left" -le 0 ] && gh issue edit "$issue" --remove-label to-read >/dev/null
      gh issue comment "$issue" --body "📚 本批精读 ${#done_ids[@]} 篇：$url（剩余 $left 篇）" >/dev/null
    fi
    notify "📚 分类精读完成：$category（${#done_ids[@]} 篇）" "$url"
    ;;

  read)
    target=${2:?usage: read <issue|arXiv-id|URL>}
    if [[ "$target" =~ ^[0-9]+$ ]]; then
      issue=$target
    else
      url=$target; [[ "$target" =~ ^[0-9]{4}\.[0-9]{4,5}$ ]] && url="https://arxiv.org/abs/$target"
      issue=$(gh issue create --title "[read] $target" --label to-read \
        --body "- 链接：$url"$'\n'"- 来源：本地 run-local.sh" | sed 's#.*/##')
    fi
    claim "$issue" reading
    load_issue "$issue"
    start_branch "read/$issue"
    agent "按 .claude/skills/deep-read/SKILL.md 精读 issue #$issue（内容在 .cache/issue.json），完成后按 .claude/skills/ingest-wiki/SKILL.md 更新 wiki/concepts。今天是 $TODAY。只写文件，不做 git 操作。最后写 .cache/pr_body.md 与 .cache/notify.txt。"
    uv run python -m pipeline.wiki_lint >/dev/null 2>&1 || true
    [ -s .cache/pr_body.md ] || echo "## 精读 #$issue" > .cache/pr_body.md
    printf '\n\nCloses #%s\n' "$issue" >> .cache/pr_body.md
    title=$(jq -r '.title | sub("^\\[read\\] *"; "")' .cache/issue.json)
    # Issues opened from a bare arXiv ID / URL: rename to the real title from the note.
    note=$(grep -rlx "issue: $issue" notes 2>/dev/null | head -1 || true)
    if [ -n "$note" ] && [ "$title" = "$target" ]; then
      real=$(sed -n 's/^title: *"\{0,1\}\(.*[^"]\)"\{0,1\} *$/\1/p' "$note" | head -1)
      if [ -n "$real" ]; then title=$real; gh issue edit "$issue" --title "[read] $title" >/dev/null; fi
    fi
    url=$(finish_pr "read/$issue" "read: $title" note sources notes wiki | tail -1)
    release
    echo "$url"
    [ -n "${NO_PR:-}" ] || gh issue comment "$issue" --body "📖 精读完成：$url" >/dev/null
    notify "📖 精读完成：$title" "$url"
    ;;

  topic)
    issue=${2:?usage: topic <issue>}
    claim "$issue" researching
    load_issue "$issue"
    start_branch "topic/$issue"
    agent "按 .claude/skills/research-topic/SKILL.md 调研 issue #$issue（内容在 .cache/issue.json）。今天是 $TODAY。只写文件，不做 git 操作。最后写 .cache/pr_body.md 与 .cache/notify.txt。"
    [ -s .cache/pr_body.md ] || echo "## 调研 #$issue" > .cache/pr_body.md
    printf '\n\nCloses #%s\n' "$issue" >> .cache/pr_body.md
    title=$(jq -r '.title | sub("^\\[topic\\] *"; "")' .cache/issue.json)
    url=$(finish_pr "topic/$issue" "topic: $title" report reports wiki | tail -1)
    release
    echo "$url"
    [ -n "${NO_PR:-}" ] || gh issue comment "$issue" --body "🔎 调研完成：$url" >/dev/null
    notify "🔎 调研完成：$title" "$url"
    ;;

  report)
    week=$(TZ=Asia/Shanghai date +%G-W%V)
    start_branch "report/$week"
    uv run python -m pipeline.week_context
    agent "按 .claude/skills/weekly-report/SKILL.md 生成周报 reports/weekly/$week.md。本周上下文在 .cache/week.json，今天是 $TODAY。只写文件，不做 git 操作。最后写 .cache/pr_body.md 与 .cache/notify.txt。"
    url=$(finish_pr "report/$week" "report: 学习周报 $week" report reports | tail -1) || exit 0
    echo "$url"
    notify "🗓️ 学习周报 $week" "$url"
    ;;

  lint)
    uv run python -m pipeline.wiki_lint
    ;;

  *)
    sed -n '2,20p' "$0"; exit 1 ;;
esac
