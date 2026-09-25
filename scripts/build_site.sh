#!/usr/bin/env bash
# Assemble the knowledge base into _site_src/ and build the static site into site/.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf _site_src site
mkdir -p _site_src
for d in docs wiki notes reports inbox sources; do
  [ -d "$d" ] && cp -R "$d" _site_src/
done
find _site_src -name .gitkeep -delete

count() { find "_site_src/$1" -name '*.md' 2>/dev/null | wc -l | tr -d ' '; }
latest() { { ls -1 "_site_src/$1" 2>/dev/null | grep '\.md$' || true; } | sort -r | head -"$2" | sed "s#^\(.*\)\.md#- [\1]($1/\1.md)#"; }
{
  echo "# tech-tree"
  echo
  echo "概念 $(count wiki) · 笔记 $(count notes) · 报告 $(count reports) · 推送 $(count inbox)"
  echo
  echo "[使用手册](docs/usage.md) · [配置手册](docs/configuration.md)"
  echo
  echo "## 最新周报"; latest reports/weekly 4; echo
  echo "## 最新专题"; latest reports/topics 8; echo
  echo "## 最近推送"; latest inbox 7; echo
} > _site_src/index.md

uv run --group site mkdocs build --quiet
echo "built site/ ($(find site -name '*.html' | wc -l | tr -d ' ') pages)"
