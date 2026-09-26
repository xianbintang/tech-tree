---
title: "Blending Containers and Virtual Machines: A Study of Firecracker and gVisor"
type: paper
id: "2020-anjali-firecracker-gvisor"
source_url: https://doi.org/10.1145/3381052.3381315
authors: [Anjali, Tyler Caraza-Harter, Michael M. Swift]
affiliations: [University of Wisconsin-Madison]
published: 2020-03-17
code_url:
---

With serverless computing, providers deploy application code and manage resource allocation dynamically, eliminating infrastructure management from application development. Serverless providers have a variety of virtualization platforms to choose from for isolating functions, ranging from native Linux processes to Linux containers to lightweight isolation platforms, such as Google gVisor and AWS Firecracker. These platforms form a spectrum as they move functionality out of the host kernel and into an isolated guest environment. In this paper, we perform a comparative study of Linux containers (LXC), gVisor secure containers, and Firecracker microVMs to understand how they use Linux kernel services differently, and we evaluate the performance costs of the designs with a series of microbenchmarks targeting different kernel subsystems. Our results show that despite moving much functionality out of the kernel, both Firecracker and gVisor execute substantially more kernel code than native Linux. gVisor and Linux containers execute substantially the same code, although with different frequency.

笔记：[[2020-anjali-firecracker-gvisor]]
