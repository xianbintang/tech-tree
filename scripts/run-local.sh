#!/usr/bin/env bash
# The whole pipeline runs locally: Claude Code (or Codex) on your own machine and
# subscription does the AI work; GitHub is only used as the issue/PR ledger via `gh`.
# No LLM credentials ever leave this machine.
#
#   scripts/run-local.sh all                 # sync → queue → daily（定时任务就跑这一条）
#   scripts/run-local.sh daily [YYYY-MM-DD]  # 抓取 + 精排 → daily/<date> PR
#   scripts/run-local.sh sync                # 已合并 PR 里勾选的条目 → to-read issue
#   scripts/run-local.sh queue               # 处理待办：open 的 to-read / research-topic issue
#   scripts/run-local.sh read  <issue | arXiv-id | URL>
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

AGENT=${AGENT:-claude}
BASE=${BASE:-master}
TODAY=$(TZ=Asia/Shanghai date +%F)
TOOLS="Read,Write,Edit,Glob,Grep,WebFetch,WebSearch,Bash(uv run python -m pipeline.*),Bash(ls:*),Bash(gh issue view:*)"
TRAILER="Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
ORIG_BRANCH=$(git branch --show-current)

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
  gh issue edit "$1" --add-label "$2" >/dev/null
  trap 'gh issue edit "$CLAIMED_ISSUE" --remove-label "$CLAIMED_LABEL" >/dev/null 2>&1 || true;
        gh issue comment "$CLAIMED_ISSUE" --body "❌ 本地运行失败（$(hostname -s)，$(date "+%F %T")），下次 queue 会重试。" >/dev/null 2>&1 || true;
        back 2>/dev/null || true' ERR
}
release() { trap - ERR; }

uv sync -q
mkdir -p .cache
rm -f .cache/pr_body.md .cache/notify.txt .cache/triage.json

case "${1:-}" in
  all)
    # One run at a time (scheduled task + manual run could overlap).
    mkdir .cache/lock 2>/dev/null || { echo "another run in progress (.cache/lock)"; exit 0; }
    trap 'rmdir .cache/lock' EXIT
    "$0" sync  || echo "::sync failed"
    "$0" queue || echo "::queue failed"
    "$0" daily || echo "::daily failed"
    ;;

  daily)
    day=${2:-$TODAY}
    if [ -z "${NO_PR:-}" ] && gh pr list --state all --head "daily/$day" --json number --jq '.[].number' | grep -q .; then
      echo "daily/$day already has a PR; skipping"; exit 0
    fi
    start_branch "daily/$day"
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
    GITHUB_OUTPUT=.cache/render.out uv run python -m pipeline.daily render
    if ! grep -q '^count=[1-9]' .cache/render.out; then
      # Nothing worth pushing today; still record dedup state.
      finish_pr "daily/$day" "state: $day" daily state >/dev/null || true; exit 0
    fi
    url=$(finish_pr "daily/$day" "$(cat .cache/pr_title.txt)" daily inbox state | tail -1) || exit 0
    grep -E '^(> |- \[ \])' .cache/pr_body.md | sed -E 's/<!--.*-->//; s/^- \[ \] /• /; s/\*\*//g' | head -16 > .cache/notify.txt
    echo "$url"
    notify "📚 $(cat .cache/pr_title.txt)" "$url"
    ;;

  sync)
    uv run python -m pipeline.inbox_issues --recent-days 14
    ;;

  queue)
    for n in $(gh issue list --state open --label to-read --json number,labels \
                 --jq '[.[] | select([.labels[].name] | index("reading") | not)] | .[:'"${QUEUE_READS:-3}"'] | .[].number'); do
      "$0" read "$n" || echo "::read #$n failed"
    done
    for n in $(gh issue list --state open --label research-topic --json number,labels \
                 --jq '[.[] | select([.labels[].name] | index("researching") | not)] | .[:'"${QUEUE_TOPICS:-1}"'] | .[].number'); do
      "$0" topic "$n" || echo "::topic #$n failed"
    done
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
    sed -n '2,19p' "$0"; exit 1 ;;
esac
