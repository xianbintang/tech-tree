---
title: "Running self-hosted AI agent sandboxes with AWS Lambda MicroVMs"
type: post
id: "aws-lambda-microvms-agent-sandboxes"
source_url: https://aws.amazon.com/blogs/compute/running-self-hosted-ai-agent-sandboxes-with-aws-lambda-microvms/
authors: [AWS Compute Blog]
affiliations: [Amazon Web Services]
published: 2026-09-18
code_url: https://github.com/aws-samples/sample-lambda-microvm-claude-managed-agents
---

Organizations building AI agents that autonomously write code, query databases, and interact with internal systems need a secure, isolated environment for each tool-call session. This post shows how to architect a self-hosted control plane on **AWS Lambda MicroVMs** — a serverless compute environment offering general-purpose Firecracker-based VM isolation, launch-from-snapshot cold start, and up to 4x in-place vertical scaling — as sandboxes for Anthropic Claude Managed Agents' self-hosted tool-call execution. The reference architecture: an API Gateway webhook triggers a launcher Lambda function that verifies the signature, deduplicates via DynamoDB, and calls `RunMicrovm`; the MicroVM boots from a pre-captured snapshot, its worker process claims a session from the orchestration service's work queue, executes tool calls in an isolated `/workspace`, posts results, and the VM is suspended/terminated per its idle policy. Credentials are scoped per component (launcher only sees the webhook secret; the worker retrieves its own secret via its execution role) so no single component holds both.

笔记：[[aws-lambda-microvms-agent-sandboxes]]
