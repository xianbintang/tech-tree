---
title: "Ten Years of AWS Lambda"
type: post
id: "brooker-ten-years-of-lambda"
source_url: https://brooker.co.za/blog/2024/11/14/lambda-ten-years.html
authors: [Marc Brooker]
affiliations: [Amazon Web Services]
published: 2024-11-14
---

AWS Lambda 十周年回顾博文。借 Werner Vogels 公开的 Lambda 原始 PRFAQ 批注版，Firecracker/Lambda 作者 Marc Brooker 补充了几段技术史：为何首发只支持 Node.js（npm 打包体验好）、Go 支持如何倒逼出 Custom Runtime、worker manager 从纯内存单机演进为跨 AZ 持久化服务、以及一段此前较少公开的细节——共享队列（如 event invoke 队列）曾放大 noisy-neighbor 效应，团队用 stochastic fairness queuing（SFQ）+ best-of-k 放置相结合的算法解决，且已在多处内部系统复用。

笔记：[[brooker-ten-years-of-lambda]]
