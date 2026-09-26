#!/usr/bin/env bash
# Single fixed entry point for the Claude desktop scheduled tasks, so the task only ever
# runs one allow-listed command and never stops on a permission prompt.
#
#   scripts/scheduled.sh all    # 08:00 daily
#   scripts/scheduled.sh tick   # hourly
#
# Everything lives inside main(): bash parses the whole function before running it,
# so the `git pull` below can safely rewrite this very file.
main() {
  set -uo pipefail
  cd "$(dirname "$0")/.."
  case "${1:-}" in
    all|tick) ;;
    *) echo "usage: scripts/scheduled.sh all|tick" >&2; return 2 ;;
  esac
  # Update code only when no pipeline is running and there are no local code edits.
  if [ ! -d .cache/lock ] && [ -z "$(git status --porcelain -- pipeline scripts config)" ]; then
    { git switch -q master && git pull -q --ff-only; } || echo "git update skipped"
  fi
  scripts/run-local.sh bg "$1"
}
main "$@"
exit
