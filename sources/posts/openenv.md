---
title: "Building the Open Agent Ecosystem Together: Introducing OpenEnv"
type: post
id: "openenv"
source_url: https://huggingface.co/blog/openenv
authors: [Joseph Spisak, Davide Testuggine, Zach Wentz, Pierre Andrews, Sanyam Bhutani, Hamid Shojanazeri, Pankit Thapar, Emre Guven, Lewis Tunstall, Vaibhav Srivastav]
affiliations: [Meta (PyTorch), Hugging Face]
published: 2025-10-23
code_url: https://github.com/meta-pytorch/OpenEnv
---

Agentic environments define everything an agent needs to perform a task: the tools, APIs, credentials, execution context, and nothing else. Meta-PyTorch and Hugging Face are partnering to launch the OpenEnv Hub — a shared, open community hub for agentic environments used for both training and deployment — together with the OpenEnv 0.1 Spec (RFC), which defines a Gymnasium-style `reset`/`step`/`state` client-server interface (environments run as FastAPI servers in Docker containers) plus an MCP-based tool interface shared between RL training and production inference.

笔记：[[openenv]]
