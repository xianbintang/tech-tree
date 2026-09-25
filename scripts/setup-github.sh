#!/usr/bin/env bash
# One-time GitHub setup: labels + allow Actions to open PRs + enable Pages (Actions source).
set -euo pipefail
REPO=${REPO:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}

label() { gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force; }
label daily          0E8A16 "每日推送 PR"
label to-read        1D76DB "待精读（打上即触发 deep-read）"
label reading        5319E7 "精读进行中"
label note           C5DEF5 "精读笔记 PR"
label research-topic D93F0B "待调研主题（打上即触发 research）"
label researching    F9D0C4 "调研进行中"
label report         FBCA04 "报告 PR（周报 / 专题）"
label wiki-lint      B60205 "知识库体检问题"
label add-source     BFD4F2 "新增订阅源"
label source:paper   EDEDED "来源：论文"
label source:post    EDEDED "来源：博文 / 技术报告"
label priority:p0    B60205 "必读"
label priority:p1    E99695 "重要"
label priority:p2    F9D0C4 "有空再看"

# Let workflows (GITHUB_TOKEN) create pull requests.
gh api -X PUT "repos/$REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=write -F can_approve_pull_request_reviews=true

# GitHub Pages built by Actions.
gh api -X POST "repos/$REPO/pages" -f build_type=workflow 2>/dev/null \
  || gh api -X PUT "repos/$REPO/pages" -f build_type=workflow

echo "done. Next: add secrets (see README)."
