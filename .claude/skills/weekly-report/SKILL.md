---
name: weekly-report
description: 生成每周学习报告：汇总本周推送、精读、概念页变化和调研，提炼洞见与下周计划，写入 reports/weekly/YYYY-Www.md。每周定时任务或用户说“出本周学习报告”时使用。
---

# Weekly-report：周学习报告

## 输入

- `.cache/week.json`：由 `uv run python -m pipeline.week_context` 生成（新增/修改的文件、合并的 PR、关闭的 issue、未完成的调研主题）。不存在就先跑这条命令。
- 读 `files_added` / `files_modified` 里的笔记、概念页、报告正文。
- 本周的 `inbox/*.md`（看推送了什么、选了什么没读）。

## 报告结构 `reports/weekly/<YYYY>-W<ww>.md`

```markdown
---
title: "学习周报 YYYY-Www"
type: report
created: YYYY-MM-DD
range: [YYYY-MM-DD, YYYY-MM-DD]
---

# 学习周报 YYYY-Www

## 本周一句话

## 数字
推送 N 篇 · 精读 N 篇 · 新增概念 N · 更新概念 N · 调研 N

## 关键洞见（3–5 条）
每条：结论 + 支撑来源 [[...]] + 对我们的意义。优先写跨论文的综合判断，而不是单篇复述。

## 趋势观察
本周推送里反复出现的方向、机构、方法；与前几周（读 reports/weekly/ 历史）相比的变化。

## 知识图谱变化
新增/显著更新的概念页及一句话说明；新出现的矛盾。

## 积压
推送了但没读的高分条目；打开状态的 to-read / research-topic issue。

## 下周建议
2–4 条：读什么、调研什么、概念页该补什么。
```

## 收尾

- 写 `.cache/pr_body.md`（报告摘要 + 链接）与 `.cache/notify.txt`（≤5 行，适合推到飞书）。
- 不编造没发生的阅读；本周什么都没读就如实写，并给出积压清单。
