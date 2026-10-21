# 你的项目贡献：中文学习路线与英文面试表达

核查日期：2026-10-02，马来西亚时间。

身份说明：当前 Git 配置为 BaoSheng05；本次先把 BaoSheng05 和 CH'NG BAO SHENG 作为同一位候选作者进行分析，等待你确认。下面的“我”是供该作者使用的英文稿，不能在身份或个人理解未确认时当作已经验证的个人陈述。

研究范围是当前 NotToBeCooked 仓库，不包含其他项目。已刷新远程分支，读取 GitHub PR/评论、提交历史、重点实现及测试 diff。没有重新执行全套测试或性能实验。

## 1. 你适合怎样介绍自己的角色

不是简单的“做 UI”，也不必说“整个系统都是我做的”。更准确的定位是：

**后端为主，同时参与前后端集成，重点负责文档处理与文件管理流程。**

先用这版简单英文：

> My main contributions were document ingestion and file-management APIs. I also connected the file browser to real backend APIs and built a small retrieval evaluation.

意思：我主要贡献是文档摄取与文件管理 API，也把文件浏览器接到真实后端，并做了一个小型检索评估。

不要一上来报提交数量。面试官真正想知道你解决了什么问题、为何这样做、怎么验证。

## 2. 我核查到的贡献主线

候选作者在 main 有 76 个非 merge 提交和 12 个 merge 提交。76 包含功能、测试、文档、格式修改和撤销，不等于 76 个功能。备份分支发现重复 patch，不能重复算成果。

主线包括：

- Docling 文档解析，标题/页码保留，token 分块与长文本切分。
- 解析、Embedding、chunks 写入的处理编排，以及空内容和处理状态管理。
- ingestion 状态查询 API，202 接口外层改动。
- course/folder/file 的管理 API、权限关联、文件预览内容、删除和替换。
- 文件浏览器状态、上传校验与错误恢复、重试、键盘操作和布局修正。
- 把 mock 文件浏览器替换成 API 驱动的数据与 mutation，处理缓存刷新和轮询。
- 单文档 summary intent、完整文档上下文、表格和 bullet 内容保留。
- 350/500 token 分块的受控检索评估。

完整证据见 `output/contribution-audit/commit-ledger.md`，英文故事见 `contribution-interview-playbook.en.md`。

## 3. 第一优先：旧索引失效这个故事

先理解五个名词：

- 原文件：用户上传的 PDF 等文件字节。
- FILE：数据库里的文件元数据。
- CHUNK：从文件抽出的文本片段及其向量。
- INGESTION_RUN：某一次索引处理的记录。
- active：这次处理的 chunks 是否允许被当前检索使用。

问题：用户替换了 PDF，但旧 chunks 没有跟着失效。阅读器显示新文件，问答却可能仍使用旧内容。

你的候选提交 `9878edd`：把这个文件旧的 active runs 设为 inactive。保留历史记录，但当前检索不再读它们，等新文件完成索引。

先练这三句：

> I fixed a consistency issue when a document was replaced.
> The old chunks could still be used for retrieval even though the file content had changed.
> I deactivated the previous ingestion runs so search would not use the stale content.

面试官追问时再加：

> The tradeoff is that the file is temporarily unavailable for retrieval until it is indexed again.

为什么有实力：你理解原文件、数据库状态和向量索引是不同的数据，知道必须修改检索真正使用的状态。

别说“完全保证原子性”：本地文件写入与数据库事务不是同一个事务。你可以提出版本化文件、数据库指针切换和清理机制作为改进。

## 4. 第二优先：mock 接真实 API

mock 意味着页面展示的是预先写好的数据或本地模拟状态，不一定真正改变服务器数据。

你的候选提交 `6ea628f`：引入真实 courses/folders/files queries 与 mutations，删除许多本地 fixture/override 逻辑。写操作成功后刷新相关缓存；有 pending 文件时每 3 秒刷新列表。

先练：

> I connected the file browser to real backend APIs.
> I added query and mutation hooks so file actions were saved on the server.
> After successful changes, I refreshed the relevant queries to keep the UI consistent with the backend.

需要理解：query 读数据，mutation 发起修改，cache 是前端保存的服务器数据副本，invalidate 表示这个副本可能过时、需要更新。

练按钮路径：

上传按钮 -> FormData -> POST /files -> 验证身份/文件夹归属 -> 存原文件/写元数据 -> 201 -> POST ingest -> queued/202 -> 后台处理 -> 前端轮询 -> ready 或 failed。

别把“改过 API client”说成“整个 API client 是我写的”，它原有基础来自队友。

## 5. 第三优先：分块评估

你的候选提交 `6041da4`：同一份 20 页 PDF、同一组 20 道题，比较 350 与 500 token 最大分块尺寸。

仓库当时记录：350 产生 34 chunks，500 产生 20 chunks；两者 Hit@5 都为 20/20。

Hit@5 的意思：一个问题的前五个检索结果里，至少有一个符合你的 relevance 条件的片段。它不等于模型回答正确率。

先练：

> I built a controlled experiment to compare two chunk sizes.
> Both configurations achieved 20 out of 20 on Hit@5 in our small test corpus.
> This did not prove that either configuration was better overall, so a larger and harder benchmark would be the next step.

面试官喜欢的部分：变量控制、明确 relevance 条件、承认 ceiling effect、实验数据 rollback，不是“100%”本身。

MRR 和后来的排名比较由 Calvin 的 `94c2ae2` 加入。准确说法是你做了原始评估，队友后来扩展指标。

## 6. 你必须区分的团队贡献

这些可以学会解释，但不能因为在同一个文件里就说是自己实现：

| 工作 | 正确归属/说法 |
|---|---|
| 登录、JWT、refresh 基础 | Calvin 的工作；你是在其基础上做资源权限与集成 |
| 原始向量/混合检索和 Embedding 服务 | Calvin 的工作；你使用、集成并评估它们 |
| 202 请求外层 | 候选作者有贡献，但当时后台函数仍是 NotImplementedError |
| 202 后台执行体、to_thread 修复 | SussyMouse 的后续实现 |
| 模型首次加载锁 | Lim Yong Zhou 的工作 |
| JSONB UUID serializer | Lim Yong Zhou 实现；你的 ec3b327 调整消息代码以使用它 |
| grounding 基础与后续引用过滤 | 队友工作；你有 summary 集成和相关测试贡献 |

面试句式：

> Our system does **[整体行为]**. My specific contribution was **[你的改动]**.

> That part was implemented by my teammate. I worked on **[你的模块]**, which uses it to **[连接关系]**.

这样说不会削弱你，反而表明你了解团队分工和自己的边界。

## 7. GitHub PR 暴露了一个值得研究的点

你候选身份的 PR #4 添加 GET 文件内容。自动 review 指出：接口返回文件 bytes，但 OpenAPI 生成的响应类型没有正确描述 binary 内容。

这能教你区分：服务器实际返回什么、客户端怎么解析、接口文档/类型怎么描述。当前 client 使用 Blob，但不能因此断言 OpenAPI 问题已经修好。没有证据就不要说你修复了该 review。

PR 当时写的 59 tests passed 是历史报告，本次没有重跑。你可以说当时 PR 记录了测试结果，不能说我刚替你验证了全套测试。

## 8. 训练方式

你目前还在熟悉 language/framework/pgvector 等基础，所以不必马上背长稿。每次一个故事，按三层练：

1. 先把中文原因讲清楚。
2. 用英文三句讲问题、改动、结果。
3. 回答 why、failure、test 三类追问。

每次回答后检查：你说的每个技术词，能不能用普通话解释，并指到具体代码？如果不能，先缩短句子、补基础。

第一题：

> What was your main contribution to this project?

第二题：

> Why did you deactivate the old ingestion runs when a file was replaced?

第三题：

> What does Hit@5 measure, and what does it not measure?

掌握这三题，再扩展到 OOP、SQL、异步与完整 Send 流程。
