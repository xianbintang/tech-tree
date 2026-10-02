---
title: "Behind the scenes of Modal sandboxes"
type: post
id: "2026-amplify-modal-sandboxes"
source_url: https://www.amplifypartners.com/blog-posts/behind-the-scenes-of-modal-sandboxes
authors: [Sarah Catanzaro]
affiliations: [Amplify Partners]
published: 2026-09-04
code_url:
---

Amplify Partners（Modal 投资方）采访 Modal 工程团队后写的深度报道：Modal 的 sandbox 产品从 3 年前的"一个周末原型"，发展到如今支撑某 AI lab 10 万级并发 agentic RL 训练沙箱（目标 100 万）。内容覆盖：为什么 agentic RL 对沙箱基础设施提出远超普通 coding agent 的规模需求；v1 为何能一周做出来（依赖 Modal 多年积累的快容器启动、自研文件系统、gVisor 隔离、调度层、存储层等既有原语，v1 工作主要是 API/SDK 设计）；随规模增长暴露出的调度问题（控制面用数据库做 source of truth，调度器基于内存态集群视图做低延迟放置决策，单调度器在更大规模下会成为瓶颈，需要分片）；多区域场景下的冷启动与镜像缓存取舍；GPU 沙箱新增的调度复杂度；存储层的四种原语（filesystem snapshot、directory snapshot、memory snapshot、volume）及各自适用场景；单机打包密度（单 VM 可容纳数百个 sandbox）对训练吞吐上限的直接影响。投资方视角写的文章，具体数字（如"百万级并发"）未经第三方验证，需要打折扣看待。

笔记：[[2026-amplify-modal-sandboxes]]
