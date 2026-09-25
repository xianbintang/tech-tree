#!/usr/bin/env bash
# Run the same pipeline locally (Claude Code or Codex, on your subscription) and open a PR.
# Useful as the body of a Cowork / Claude Code scheduled task, or when you'd rather not
# use GitHub Actions minutes / API keys.
#
#   scripts/run-local.sh daily [YYYY-MM-DD]
#   scripts/run-local.sh read  <issue-number | arXiv-id | URL>
#   scripts/run-local.sh topic <issue-number>
#   scripts/run-local.sh report
#
#   AGENT=codex scripts/run-local.sh read 2609.23377     # use Codex instead of Claude Code
#   NO_PR=1 scripts/run-local.sh daily                   # write files only, no branch/PR
#   BASE=some-branch scripts/run-local.sh daily          # branch off / open PR against another base
set -euo pipefail
cd "$(dirname "$0")/.."

AGENT=${AGENT:-claude}
BASE=${BASE:-master}
TODAY=$(TZ=Asia/Shanghai date +%F)
TOOLS="Read,Write,Edit,Glob,Grep,WebFetch,WebSearch,Bash(uv run python -m pipeline.*),Bash(ls:*),Bash(gh issue view:*)"
TRAILER="Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"

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
  ORIG_BRANCH=$(git branch --show-current)
  git fetch -q origin "$BASE"
  git switch -q -c "$1" "origin/$BASE"
}

finish_pr() {  # $1 branch  $2 title  $3 label  $4.. paths
  local branch=$1 title=$2 label=$3; shift 3
  if [ -n "${NO_PR:-}" ]; then echo "NO_PR set; files written, skipping git."; return; fi
  git add -- "$@"
  if git diff --cached --quiet; then
    echo "nothing changed"; git switch -q "$ORIG_BRANCH"; git branch -q -D "$branch"; return
  fi
  git commit -q -m "$title" -m "$TRAILER"
  git push -q -u origin "$branch"
  [ -s .cache/pr_body.md ] || echo "$title" > .cache/pr_body.md
  printf '\n\n<sub>本地运行 · agent: %s</sub>\n' "$AGENT" >> .cache/pr_body.md
  gh pr create --base "$BASE" --head "$branch" --title "$title" --label "$label" --body-file .cache/pr_body.md
  git switch -q "$ORIG_BRANCH"
}

load_issue() { mkdir -p .cache; gh issue view "$1" --json number,title,body,labels > .cache/issue.json; }

uv sync -q
mkdir -p .cache
rm -f .cache/pr_body.md .cache/notify.txt .cache/triage.json

case "${1:-}" in
  daily)
    day=${2:-$TODAY}
    start_branch "daily/$day"
    : > .cache/extra_seen.txt
    for b in $(git branch -r --list 'origin/daily/*'); do
      git ls-tree -r --name-only "$b" state/seen | while read -r f; do git show "$b:$f" >> .cache/extra_seen.txt; done
    done
    uv run python -m pipeline.daily fetch --date "$day"
    agent "按 .claude/skills/triage/SKILL.md 执行每日精排：读取 .cache/candidates.json 与 config/interests.yaml，输出 .cache/triage.json。只写这一个文件。" \
      || echo "triage failed, falling back to keyword ranking"
    python3 -m json.tool .cache/triage.json >/dev/null 2>&1 || rm -f .cache/triage.json
    uv run python -m pipeline.daily render
    finish_pr "daily/$day" "$(cat .cache/pr_title.txt 2>/dev/null || echo "daily: $day")" daily inbox state
    ;;
  read)
    target=${2:?usage: read <issue|arXiv-id|URL>}
    if [[ "$target" =~ ^[0-9]+$ ]]; then
      issue=$target
    else
      # Track ad-hoc reads as issues too. No `to-read` label, so the cloud workflow doesn't also fire.
      url=$target; [[ "$target" =~ ^[0-9]{4}\.[0-9]{4,5}$ ]] && url="https://arxiv.org/abs/$target"
      issue=$(gh issue create --title "[read] $target" --label reading \
        --body "- 链接：$url"$'\n'"- 来源：本地 run-local.sh" | sed 's#.*/##')
    fi
    load_issue "$issue"
    start_branch "read/$issue"
    agent "按 .claude/skills/deep-read/SKILL.md 精读 issue #$issue（内容在 .cache/issue.json），完成后按 .claude/skills/ingest-wiki/SKILL.md 更新 wiki/concepts。今天是 $TODAY。只写文件，不做 git 操作。最后写 .cache/pr_body.md 与 .cache/notify.txt。"
    uv run python -m pipeline.wiki_lint || true
    printf '\n\nCloses #%s\n' "$issue" >> .cache/pr_body.md
    title=$(jq -r '.title | sub("^\\[read\\] *"; "")' .cache/issue.json)
    finish_pr "read/$issue" "read: $title" note sources notes wiki
    ;;
  topic)
    issue=${2:?usage: topic <issue>}
    load_issue "$issue"
    start_branch "topic/$issue"
    agent "按 .claude/skills/research-topic/SKILL.md 调研 issue #$issue（内容在 .cache/issue.json）。今天是 $TODAY。只写文件，不做 git 操作。最后写 .cache/pr_body.md 与 .cache/notify.txt。"
    printf '\n\nCloses #%s\n' "$issue" >> .cache/pr_body.md
    title=$(jq -r '.title | sub("^\\[topic\\] *"; "")' .cache/issue.json)
    finish_pr "topic/$issue" "topic: $title" report reports wiki
    ;;
  report)
    week=$(TZ=Asia/Shanghai date +%G-W%V)
    start_branch "report/$week"
    uv run python -m pipeline.week_context
    agent "按 .claude/skills/weekly-report/SKILL.md 生成周报 reports/weekly/$week.md。本周上下文在 .cache/week.json，今天是 $TODAY。只写文件，不做 git 操作。最后写 .cache/pr_body.md 与 .cache/notify.txt。"
    finish_pr "report/$week" "report: 学习周报 $week" report reports
    ;;
  *)
    sed -n '2,13p' "$0"; exit 1 ;;
esac
