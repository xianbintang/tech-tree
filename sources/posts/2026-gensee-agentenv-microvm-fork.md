---
title: "Inside Kimi K3's AgentENV: Can It Really Fork in 100 ms?"
type: post
id: "2026-gensee-agentenv-microvm-fork"
source_url: https://www.gensee.ai/blogs/inside-agentenv-dirty-memory-microvm-fork.html
authors: [Gensee AI team]
affiliations: [Gensee AI]
published: 2026-08-03
code_url:
---

## 摘要（原文节选）

> AgentENV arrived with an attention-grabbing claim: incremental snapshots in under 100 milliseconds, even after heavy disk modification. But what exactly completes in those 100 milliseconds? ... We wanted to know whether AgentENV lives up to that headline, so we traced its dirty-page path and measured complete fork-to-first-use latency through 2 GiB of dirty memory.
>
> Short answer: AgentENV forks below the guest kernel, so the host does not reconstruct every guest process. ... But its current implementation still copies selected dirty guest-memory ranges into a new immutable OverlayBD layer before the fork endpoint returns. Restore is lazy; snapshot capture is not.

笔记：[[2026-gensee-agentenv-microvm-fork]]
