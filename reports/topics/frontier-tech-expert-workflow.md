---
title: "前沿技术专家的日常：每天 / 每周怎么学习、找资料、研究外部技术"
type: report
issue: 127
created: 2026-10-04
depth: brief
---

# 前沿技术专家的日常：每天 / 每周怎么学习、找资料、研究外部技术

## TL;DR

1. 一线专家的共同点不是读得多，而是**筛得狠**：Raschka 当 arXiv 审稿人时每天扫 100–300 篇标题，他的结论是难的不是找到好论文，而是不被分心；收藏的东西约 95% 最后都不重要。
2. 节奏上普遍是**每天小剂量扫描（15–30 分钟）+ 每周一次挑选和深读 + 定期写出来**。写作（博客、TIL、内部文档）是强迫自己真正读懂的主要手段。
3. 读论文用**分层深度**：Keshav 的三遍法、Ng 的多遍法，绝大多数材料只读第一遍；只有和自己问题直接相关的才读到「能在脑中复现」。
4. 研究外部技术要**问题驱动**：手里先有 10–20 个本领域重要问题（Hamming），读资料是为了给这些问题找「突破口」，而不是为了跟上新闻。
5. 资料源分四层：**一手**（论文、会议、实验室工程博客、开源仓库）> **筛选层**（每日论文榜、newsletter）> **社交层**（X、HN、知乎）> **人**（同行、作者、社区）。本仓库的订阅已覆盖前两层的大部分，缺的是系统会议、GitHub release、中文源和「人」。

## 要回答的问题

1. 一个关注前沿的技术专家，每天、每周的时间是怎么分配的？
2. 日常怎么学：怎么筛、怎么读、怎么记？
3. 研究一项外部技术（比如竞品沙箱、一篇新系统论文）的标准动作是什么？
4. 资料源在哪里？哪些是一手的，哪些只是转述？
5. 对照本仓库现有的流水线，还缺什么？

## 一线专家公开讲过的做法

| 人 | 做法 | 出处 |
|---|---|---|
| Sebastian Raschka（Ahead of AI 作者，前 arXiv cs.LG 审稿人） | 按主题建清单，什么都往里收（论文、博客、视频、讨论帖）；**每周**挑几篇来读，接受「95% 收藏的东西并不重要」；信息源靠 Google Scholar 关键词提醒、在 X 上关注对的人、几份 newsletter（Import AI、The Batch） | [Keeping Up With AI Research & News](https://sebastianraschka.com/blog/2023/keeping-up-with-ai.html) |
| Sebastian Raschka × Nathan Lambert（Interconnects） | 两人都说「看的论文远多于真正读的」；写 newsletter 是逼自己读论文的方式：读完记笔记，攒一个月再整理成文 | [Interconnects 访谈](https://www.interconnects.ai/p/interviewing-sebastian-raschka) |
| S. Keshav（滑铁卢大学） | 三遍法：第一遍约 10 分钟，只看标题、摘要、引言、小标题、结论，回答「5 个 C」（类别、背景、正确性、贡献、清晰度）；第二遍约 1 小时，看懂图表和主线；第三遍「在脑中重新实现一遍」，找隐含假设和缺陷。做文献调研时先找 3–5 篇近作，再顺着共同引用找到关键论文和关键作者 | [How to Read a Paper（CCR 2007）](http://ccr.sigcomm.org/online/files/p83-keshavA.pdf) |
| Andrew Ng（斯坦福 CS230） | 先列清单；按「标题摘要图 → 结论和实验 → 跳过数学通读 → 全文」多遍读；一个方向读 5–20 篇能入门，读 50–100 篇能做研究；读完要动手复现 | [CS230 Lecture 8](https://www.youtube.com/watch?v=733m6qBH-jI) |
| Andrej Karpathy | 用 LLM 辅助阅读：先把章节原文贴给模型，看总结，再读原文，边读边问 | [How I use LLMs](https://www.youtube.com/watch?v=EWvNQjAaOHw)（约 54:55 处） |
| Simon Willison | 「学到什么就写下来」：TIL（Today I Learned）博客的门槛只是「我刚学到了点东西」；链接博客每条都写一两句自己的评论 | [What to blog about](https://simonwillison.net/2022/Nov/6/what-to-blog-about/)、[My approach to running a link blog](https://simonwillison.net/2024/Dec/22/link-blog/) |
| Richard Hamming（贝尔实验室） | 伟大的科学家心里有 10–20 个重要问题，时刻在找突破口；每周五下午留给「重大思考」（great thoughts），想领域的大方向；开着门工作的人更能抓到正确的问题；每隔约 7 年换一个方向 | [You and Your Research（1986）](https://www.cs.virginia.edu/~robins/YouAndYourResearch.html) |

几条共同规律：

- **筛选比阅读重要。** 所有人都在讲怎么不读、怎么只读第一遍。
- **输出驱动输入。** 写 newsletter、TIL、链接点评、内部文档，是把「看过」变成「懂了」的关键一步。
- **问题驱动而不是新闻驱动。** Hamming 的「10–20 个重要问题」和 Raschka 的「只收能让我学到新东西的」是同一个意思：带着问题读。
- **动手。** Keshav 的第三遍、Ng 的复现，在系统方向就是去跑一跑、测一测。

## 一个可执行的节奏（按沙箱平台工程师调整）

下面是综合上面做法、按你的方向调整后的建议，不是某个人的原样作息。

### 每天（30–45 分钟）

| 时间 | 做什么 | 对应本仓库 |
|---|---|---|
| 早上 15 分钟 | 扫当天推送：只看标题和 TL;DR，勾选想精读的（Keshav 第一遍的强度） | 08:00 的 daily PR，勾选后合并 |
| 碎片时间 | 读 1 篇已生成的精读笔记，或一篇短博文 | `notes/` 与网站 |
| 晚上 5 分钟 | 记一条 TIL：今天学到的一件事，哪怕只有一句 | 可加 `notes/til/`（见文末建议） |

原则：**每天只做扫描和轻量阅读，不做深读。** 深读放到每周固定的时间块。

### 每周（3–5 小时）

| 时间块 | 做什么 |
|---|---|
| 周一 30 分钟 | 看上周周报，从收藏和阅读清单里挑本周要深读的 2–3 篇（Raschka 的周挑选） |
| 周中 2 个时间块，每块 1.5–2 小时 | 深读：Keshav 第二遍、第三遍；系统论文要画出架构图，想清楚「换成我们的平台会怎样」 |
| 周五下午 1 小时 | Hamming 式「重大思考」：更新自己的「重要问题清单」（比如：fork 能不能做到 10ms 以内？百万并发沙箱的瓶颈在哪？）；看本周哪条资料推进了哪个问题 |
| 周末（可选） | 动手：跑一个竞品（E2B、Modal、Daytona）或开源实现（Arrakis、AgentENV），测冷启动、fork、快照数据 |

对应本仓库：周报（`reports/weekly/`）就是周五那一小时的产物；「重要问题清单」目前还没有固定位置。

### 每月 / 每季度

- **每月**：写一篇对外或对内的总结（技术分享、内部文档），把一个月的笔记串成一条线。对应本仓库的专题报告（`reports/topics/`）。
- **每季度**：顺着一篇重要论文的引用链系统补课，做法和 DSec 引用链、混元团队清单一样。看顶会论文集（见下文资料源），更新「领域地图」。
- **每年**：参加或补看 1–2 个会议（OSDI/SOSP、KubeCon、AI Engineer），重新审视自己的方向（Hamming 的「7 年一换」放到年度做小调整）。

## 研究一项外部技术的标准动作

以「研究一个竞品沙箱」或「研究一篇新的系统论文」为例：

1. **定问题**：我想知道什么？比如「它的 fork 为什么能快」，而不是「了解一下它」。
2. **建地图**：找 3–5 篇相关近作，读它们的 Related Work；顺着共同引用找到关键论文和关键作者（Keshav 的文献调研法，也是我们做 DSec 引用链的方法）。有综述就先读综述。
3. **分层读**：所有材料先过第一遍，只有 2–3 篇读到第三遍。
4. **看一手实现**：读代码仓库（README、架构文档、关键模块）、release notes、issue 区。系统方向的很多真相在 issue 里，比如 agent-sandbox 的控制器 bug。
5. **动手测**：跑起来，测几个关键数字（冷启动、fork 延迟、密度）。厂商博客里的数字要打折扣。
6. **做对比表**：维度 × 方案，和我们平台放在一起。
7. **写出来**：笔记或报告，结尾一定要有「对我们的启发」和可执行的 follow-up。
8. **找人聊**：给作者发邮件、在社区（Discord、Slack、GitHub Discussions）提问，或找内部做过的同事。很多关键细节只在这一步拿得到。

## 资料源地图

### 一手来源（最可信）

| 类型 | 具体来源 | 本仓库是否已覆盖 |
|---|---|---|
| 预印本 | arXiv cs.DC / cs.OS / cs.LG / cs.AI / cs.SE / cs.CL | ✅ 每日抓取 |
| 系统顶会 | OSDI、SOSP、NSDI、USENIX ATC、EuroSys、ASPLOS、FAST、MLSys、SoCC：论文集和演讲视频（USENIX 的论文和视频都免费公开） | ❌ 没有订阅；只在引用链精读里零散读到 |
| 实验室技术报告 | DeepSeek、Kimi、Qwen、MiMo、混元等的技术报告（通常发 arXiv，加上 HF 模型发布） | ✅ arXiv + `hf_models` |
| 工程博客 | Anthropic、OpenAI、Google、AWS、Meta、Cloudflare、Fly.io 等 | ✅ 约 60 个源 |
| 开源仓库 | firecracker、gVisor、kata、cloud-hypervisor、agent-sandbox、verl、slime、vLLM、AgentENV、CubeSandbox 的 release、设计文档、issue 讨论 | ❌ 没有订阅 GitHub release 或 issue |
| 内核与虚拟化社区 | LWN.net、KVM Forum、Linux Plumbers 演讲 | ❌ |

### 筛选层（帮你挑）

| 来源 | 说明 | 本仓库是否已覆盖 |
|---|---|---|
| HF Daily Papers | 社区投票的每日论文 | ✅ |
| Newsletter | Import AI、Interconnects、Ahead of AI、SemiAnalysis、AI News（smol.ai） | ✅ |
| 会议演讲 | AI Engineer（带逐字稿） | ✅（PR #101） |
| 会议演讲 | KubeCon、USENIX 会议视频 | ❌ |
| 论文发现工具 | Google Scholar 关键词提醒、Semantic Scholar、Connected Papers、alphaXiv | ❌（可选，见下） |

### 社交层（最快，但噪声大）

- **X / Twitter**：大多数研究者先在这里发论文和观点。Raschka 说他的 ML 新闻主要来自「关注对的人」。可以建一个 30–50 人的 list，只看 list。
- **Hacker News、Reddit**（r/LocalLLaMA、r/MachineLearning）：看讨论区里懂行的人怎么评价。
- **中文**：知乎、各实验室公众号、机器之心等科技媒体。国内团队的一手消息常常先出现在这里，但转述多，要回到原文核对。

### 人

- 内部同事：训练团队、框架团队，他们知道「现在真正卡在哪」。你的混元团队清单（#44）就是从这个角度出发的。
- 论文作者：系统论文作者普遍愿意回邮件，尤其是问具体实现细节时。
- 开源社区：GitHub Discussions、项目的 Slack 或 Discord。

## 对照本仓库：已经做到的和缺口

**已经做到的**（大致对应上面专家的做法）：

- 每日扫描与筛选：08:00 推送 PR，关键词粗排 + LLM 精排，勾选后才精读。对应 Raschka 的「先收，再每周挑」。
- 分层阅读：精读笔记的「对我们的启发」一节、学习路线里的「精读 / 了解 / 略读」分级。对应 Keshav 的三遍法。
- 引用链补课：DSec 引用链（#21–#28）、混元团队清单（#57、#70–#74）。对应 Keshav 的文献调研法。
- 输出：笔记、概念页、周报、专题报告。对应 Willison 和 Lambert 的「写出来」。
- LLM 辅助阅读：deep-read 流水线加上交互式提问。对应 Karpathy 的做法。

**缺口**（按价值排序）：

1. **「重要问题清单」**：没有一个地方记录你当前最关心的 10–20 个问题。建议建 `wiki/open-questions.md`，周报每周回顾一次，精读笔记里写明推进了哪个问题。这是 Hamming 讲的核心，也最便宜。
2. **系统顶会论文集**：OSDI、SOSP、NSDI、ATC、EuroSys、FAST、MLSys 没有订阅。建议每次会议论文集公开时，建一个阅读清单，只挑沙箱、调度、存储相关的论文（一年约 7 次）。
3. **GitHub release 与设计文档**：对标项目（firecracker、gVisor、kata、cloud-hypervisor、agent-sandbox、AgentENV、CubeSandbox、verl、slime）的 release 可以用 GitHub 的 Atom feed（`https://github.com/<org>/<repo>/releases.atom`）直接加进 `config/sources.yaml`。
4. **动手实测**：目前只读不测。建议每月一次「竞品实测」issue，结果写进对应概念页。
5. **TIL**：每天一句话的学习记录，门槛最低，长期最有用。
6. **人**：这一层工具解决不了，要靠自己：每月主动找一位作者或同行交流一次。

## 建议的 follow-up（可直接转成 issue）

- 建 `wiki/open-questions.md`：先写下你现在最关心的 10 个沙箱 / 调度问题，周报模板里加「本周推进了哪个问题」。
- 在 `config/sources.yaml` 加 GitHub releases.atom 订阅（约 10 个对标项目，weight 3）。
- 建「系统顶会」阅读清单模板：每次会议论文集公开时，跑一次「标题关键词筛选 + LLM 精排」，生成清单 issue。
- 每月一次竞品实测 issue：E2B、Modal、Daytona、AgentENV，测冷启动、fork、快照延迟。

## 参考

- Sebastian Raschka, [Keeping Up With AI Research & News](https://sebastianraschka.com/blog/2023/keeping-up-with-ai.html), 2023
- Nathan Lambert, [Interviewing Sebastian Raschka](https://www.interconnects.ai/p/interviewing-sebastian-raschka), Interconnects, 2024
- S. Keshav, [How to Read a Paper](http://ccr.sigcomm.org/online/files/p83-keshavA.pdf), ACM SIGCOMM CCR, 2007
- Andrew Ng, [Stanford CS230 Lecture 8: Career Advice / Reading Research Papers](https://www.youtube.com/watch?v=733m6qBH-jI), 2018
- Andrej Karpathy, [How I use LLMs](https://www.youtube.com/watch?v=EWvNQjAaOHw), 2025
- Simon Willison, [What to blog about](https://simonwillison.net/2022/Nov/6/what-to-blog-about/), 2022；[My approach to running a link blog](https://simonwillison.net/2024/Dec/22/link-blog/), 2024
- Richard Hamming, [You and Your Research](https://www.cs.virginia.edu/~robins/YouAndYourResearch.html), 1986

说明：每日、每周的时间分配是综合上述做法给出的建议，不是某个人的原样作息；Ng 的「5–20 篇 / 50–100 篇」来自课程讲解的转述，没有逐字核对视频原文。
