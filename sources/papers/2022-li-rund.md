---
title: "RunD: A Lightweight Secure Container Runtime for High-density Deployment and High-concurrency Startup in Serverless Computing"
type: paper
id: "2022-li-rund"
source_url: https://www.usenix.org/conference/atc22/presentation/li-zijun-rund
authors: [Zijun Li, Jiagan Cheng, Quan Chen, Eryu Guan, Zizheng Bian, Yi Tao, Bin Zha, Qiang Wang, Weidong Han, Minyi Guo]
affiliations: [Shanghai Jiao Tong University, Alibaba Group]
published: 2022-07-11
code_url: https://github.com/chengjiagan/RunD_ATC22
---

The secure container that hosts a single container in a micro virtual machine (VM) is now used in serverless computing, as the containers are isolated through the microVMs. There are high demands on the high-density container deployment and high-concurrency container startup to improve both the resource utilization and user experience, as user functions are fine-grained in serverless platforms. Our investigation shows that the entire software stacks, containing the cgroups in the host operating system, the guest operating system, and the container rootfs for the function workload, together result in low deployment density and slow startup performance at high-concurrency. We propose and implement a lightweight secure container runtime, named RunD, to resolve the above problems through a holistic guest-to-host solution. With RunD, over 200 secure containers can be started in a second, and over 2,500 secure containers can be deployed on a node with 384GB of memory. RunD is adopted as Alibaba serverless container runtime to support high-density deployment and high-concurrency startup.

笔记：[[2022-li-rund]]
