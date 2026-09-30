---
title: "AgentENV Documentation"
type: post
id: "agentenv-docs"
source_url: https://kvcache-ai.github.io/AgentENV/latest/
authors: [kvcache-ai]
affiliations: [kvcache-ai]
published: 2026-09-30
code_url: https://github.com/kvcache-ai/AgentENV
---

AgentENV (AENV) is a self-hosted sandbox runtime for AI agents. It runs isolated Firecracker microVMs and exposes an E2B-compatible HTTP API, so existing E2B SDK code works against it without modification. Key claims: massive-scale Firecracker environments across machines with on-demand overlaybd image loading and a bounded local-disk cache; snapshot-backed environments boot/resume in under 50ms and pause in under 100ms; incremental memory+filesystem snapshots complete in under 100ms even under heavy disk modification; a running environment can fork into multiple independent sandboxes; high-performance I/O via ublk with shared host page cache across storage and memory-snapshot data; memory ballooning sustains overcommit as environments diverge over time. Architecture: per-node orchestrator + Firecracker runtime + OverlayBD/ublk storage subsystem, with a multi-node gateway+scheduler control plane and an optional P2P (iroh) artifact-transport layer. Also ships a PVM (software nested-virtualization) deployment path for hosts without standard KVM access.

笔记：[[agentenv-docs]]
