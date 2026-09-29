---
title: "FirePlace: Placing Firecracker Virtual Machines with Hindsight Imitation"
type: paper
id: "2021-balaji-fireplace"
source_url: https://proceedings.mlsys.org/paper_files/paper/2021/file/294f82c43d69f66c04440cbb2740e52d-Paper.pdf
authors: [Bharathan Balaji, Christopher Kakovitch, Balakrishnan (Murali) Narayanaswamy]
affiliations: [Amazon]
published: 2021  # MLSys 2021（San Jose, CA），论文未给出具体月日
code_url:
---

## 摘要（原文）

Virtual machines (VM) form the foundation of modern cloud computing as they help logically abstract per-user compute from shared physical infrastructure. Users of these services require VMs of varying sizes and configurations, which the provider places on a set of physical machines (PMs). VMs on the same PM share memory and CPU resources so a bad placement directly impacts the quality of user experience. We consider the placement of Firecracker VMs (a form of Micro-VMs or µVMs) - lightweight VMs that are typically used for short lived tasks. Our objective is to place each VM as it arrives, so that the peak to average ratio of resource usage across PMs is minimized. Placement is challenging as we need to consider resource use in multiple dimensions, such as CPU and memory, and because resource use changes over time. Past approaches to similar problems have suggested that one could forecast VM resource use for placement. We see that in our production traffic, µVM resource use is spiky and short lived, and that forecasting algorithms are not useful. We evaluate Reinforcement Learning (RL) approaches for this problem, but find that off-the-shelf RL algorithms are not always performant. We present a forecasting free algorithm, called FirePlace, that learns the placement decision using a variant of hindsight optimization, which we call hindsight imitation. We evaluate our approach using a production traffic trace of µVM usage from AWS Lambda. FirePlace improves upon baseline algorithms by 10% on a production data trace of 100K µVMs.

笔记：[[2021-balaji-fireplace]]
