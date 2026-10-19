# 10／11 October sharing session：Bao Sheng 中文准备路线

这次开会，你要做到两件事：把自己的 ingestion 和 frontend 讲清楚；参与决定项目以后怎么维护。英文详细材料在 `docs/sharing-session-preparation.en.md`，里面有 19 个章节、12 分钟分享提纲、22 个面试追问和会议记录模板。这份文件帮助你理解、安排准备顺序。

## 1. 先理解队友真正要求你做什么

队友已经给你划定范围：**Docling、labels、OCR、chunking、file browser**。你要深入自己的层，并能解释它与 retrieval／generation 如何交接。你不需要在这次分享里逐行讲完 Gemini、RRF 或所有人的代码。

你可以这样理解项目的三段工作：

1. 你的 ingestion：把原始文件变成内容可靠、带有元数据的 chunks。
2. Calvin 的 retrieval：根据问题找到相关 chunks，结合向量检索、关键词检索和 RRF 排序。
3. 队友的 generation／grounding：根据这些 chunks 生成回答，检查引用与原文是否对应。

frontend 是用户入口：选择文件、上传、显示处理中／失败／ready、打开文件、rename／move／delete。因此你的部分同时涉及用户操作、HTTP、数据库、文件系统和 AI 输入质量，能讲出有深度的工程问题。

## 2. 你最应该掌握的一条完整流程

先练习不用看稿说出这一条：

```text
Select file
  -> frontend validation
  -> POST /files
  -> ownership check + bytes + file metadata
  -> 201 Created
  -> POST /files/{id}/ingest
  -> queued run + background task
  -> 202 Accepted
  -> processing
  -> Docling parse
  -> extract text / lists / tables + metadata
  -> tokenizer-based chunks
  -> embeddings
  -> database chunks
  -> ready + active run
  -> frontend refreshed file list
```

注意三个容易被问倒的地方：

- **上传成功不等于处理成功。** 201 表示文件资源创建；202 表示 ingestion 请求被接受。最终结果可能是 ready，也可能是 failed。
- **异步函数不代表里面所有工作都不阻塞。** Docling 和 embedding 是同步重任务；当前代码用 `asyncio.to_thread`。这个改进有队友贡献，不要全部归为自己。
- **frontend 当前主要刷新 files list。** 它每 3 秒检查文件列表的状态；虽然存在 ingestion-run detail endpoint，但不要说当前 explorer 只是在轮询那个 endpoint。

英文短答使用英文材料第 6 节。先理解中文流程，再用自己的英文说出来；不需要逐字背诵。

## 3. Docling／label／OCR：你该怎样理解

Docling 是解析工具。它把文件转换成结构化 document，里面包含不同 items。label 告诉你 item 被识别成什么，例如 text、list_item、section_header 或 table。content layer 区分正文与页眉／页脚等 furniture。provenance 是来源位置信息，例如 PDF 第几页。

你的代码不能简单地说“Docling 提取好了，全部存进去”。你还要决定：

- 按什么顺序读取 items？当前用 `iterate_items()` 保持解析文档顺序。
- 哪些内容保留？正文 text／list_item、导出成 Markdown 的 table。
- 哪些内容不保留？非 body content layer、空文本、未支持的 label。
- heading 怎么处理？正常 heading 当作后续段落 metadata；bullet-like heading 保留为正文。
- 没有 page provenance 怎么办？当前用 page 1 fallback，但不能宣称这就是 DOCX 的真实页码。

OCR 是从图片识别文字。当前 PDF pipeline 的 `do_ocr=False`，原因写在代码注释里：避免装饰图案、logo 变成检索噪声。这也意味着扫描 PDF 可能没有可提取内容。

被问“你支持 scanned PDF 吗？”时，直接说明当前限制，再讲如果需要支持会怎样评估。这比含糊地回答“Docling 都支持”可靠。

## 4. 最值得讲的故事一：bullet 被误当 heading

这个例子能把你的 ingestion 工作与队友 grounding 工作连起来。

问题：一个 bullet 被 Docling 标成 section heading。如果 heading 只放 metadata，正文 chunk 就少了一部分句子。模型可能把 heading 与正文接起来引用，但 checker 在 chunk body 找不到完整 quote，于是失败。

你的修改：识别以特定 bullet 字符开头的 section_header，把它保留成正文；同时补 regression test。相关 commit：`6b80292`。

队友修改：grounding checker、去除不被正文引用的 citation、在同一 marker 有 verified quote 时处理某些失败 quote。不能把这些也说成自己写的。

你可以讲的工程认识：**上游丢掉内容，下游再聪明也不能凭空还原可靠证据。** 你的工作不是只把字符串切开，而是维护可引用的 source text。

练习结构：发生什么 -> 对用户有什么影响 -> 我改了什么 -> 用什么证明 -> 还有什么限制。不要只讲“我修了 bug”。

## 5. Chunking：一定要懂 tokenizer 与 offset

token 不是 word。一个词可能对应多个 tokens，不同语言也不同。你的 chunker 使用 embedding model 的 tokenizer，目的在于让大小计算与模型输入更一致。

当前应用默认是 350 tokens。`split_long_text` 自己的参数默认 500，但 `create_chunk` 会把自己的预算传进去。不要看到 splitter 的 500 就以为整个应用改成 500。

offset mapping 的意思是：tokenizer 告诉你每个 token 对应原始字符串的哪个字符范围。你用第 N 个 token 的 end offset 去切原文，而不是把 token IDs decode 回字符串。这样更能保持原文措辞与空格，对 quotation 检查有帮助。

chunk 的形成主要看两件事：加入下一段是否超预算；heading 是否改变。最终存储前，重新计算 joined content 的 token_count。

要讲清楚的限制：

- 当前没有显式 sliding-window overlap。
- 当前没有 late chunking。
- running budget 是 individual token counts 相加；joined string 的 tokenization 可能略有不同，所以不要在没验证时保证每个结果严格不超过预算。
- heading metadata 不代表 heading 自动进入 embedding body。

如果被问“为什么不是 500？”：用实验结果回答，但不要把一个小实验讲成 universal optimum。

## 6. 数字怎么讲才有说服力

你可以直接使用仓库里的 September 21 报告：20 页、106 extracted items、20 questions；350 tokens 得到 34 chunks，500 tokens 得到 20 chunks；两者 Hit@5 都是 20／20。

这意味着：在那个 controlled corpus 上，两种设置都能在前 5 个结果中找到至少一个 relevant chunk。**它不表示答案 100% 正确，也不证明 500 永远更好。** 500 的 chunk 数少 14 个，约少 41.2%；没有测量就不能换成“速度提高 41.2%”或“成本节省 41.2%”。

Calvin 需要跑的是现在的 evaluator，并提供 Hit@5、Recall@1、MRR。不要替他填一个想象结果，也不要把旧报告当成新运行。

127 tests 是队友消息提供的数字。这次准备没有重新跑 suite，也没有找到对应日志。开会前请拿到 command、commit、date、scope／skips。测试数量是证据背景，具体测试证明什么才是重点。

September 24 Gemini 的具体数字目前能在代码注释找到，但不是完整日志。让 generation owner 解释运行顺序。你的讲法是“这些事件暴露出 ingestion 与 citation checking 的衔接问题”，而不是“我把整个 AI accuracy 从某数字提高到某数字”。

## 7. Frontend：别只讲画了页面

你应该能解释：

- React 用来构建界面；TypeScript 是语言。
- TanStack Query 管理服务器数据：files、folders、courses；mutation 后 invalidate，再 fetch authoritative data。
- Zustand 管理本地工作区选择，例如 active course／tab。
- query key 带 course ID，不同课程的结果才不会混在同一个 cache entry。
- 有 pending file 时，files list 每 3000ms refresh；不是 WebSocket。
- 50 的限制在代码里是 `50 * 1024 * 1024` bytes，即 50 MiB；UI 写 50 MB。
- 多文件 `Promise.all` 不是 all-or-nothing transaction。有些已成功，另外一个失败，并不会自动撤销。

面试官说“我按 rename，到底发生了什么？”时，回答 UI 收集新名称 -> mutation 发 PATCH -> backend 查权限／验证更新 -> commit -> 返回 -> invalidate files query -> 显示更新结果。文件 storage key 不依赖显示名称，所以 rename 不一定要搬动物理文件。

## 8. 最值得讲的故事二：replace 后不能搜索旧内容

问题：用户换了原始文件 bytes，但是 search 继续找之前生成的 chunks。页面显示新版，回答引用旧版，体验和证据都不可靠。

你的修改：replacement 后停用 old active ingestion runs；新版本需要再 ingestion，成功后才有新的 active run。相关 commit：`9878edd`。

这里适合展示你理解数据生命周期：File 是文档身份／原件 metadata；IngestionRun 是某一次处理；Chunk 是那次处理产物。history 可以保留，但 current searchable evidence 必须对应当前有效版本。

不要过度保证：file system 与 database 不是同一个事务。`Path.replace` 可以处理本地替换，但不能让 DB commit 和文件操作成为跨系统原子操作。你应该知道还有失败恢复问题。

同理 delete 的 `acb4a59`：先 DB commit 再删 bytes，避免 rollback 后 row 还在而文件已没了；但之后 physical delete 失败可能留下 orphan file。能解释这个边界，比说“我保证了完全一致性”更有实力。

## 9. maintenance mode：开会时你可以怎样讨论

推荐立场：支持 maintenance mode，保留核心可运行，解决少量真实影响使用／数据的缺陷，把大新功能移到 backlog。建议 async update + 有议题时 monthly check-in，但这是讨论建议，不能当作大家已经答应。

Tuesday 8:30pm 的选择要结合实际义务：还有外部 deadline，可以继续每周；偶尔需要协调，可以两周／每月；没有 active work，可以取消固定会，必要时约。

31 Dec 要先问清：是学校硬性截止，还是团队自己的 planning date？外部要求不能因为 maintenance 就不管。内部目标可以提议变成 review checkpoint，记录文档、已知问题和项目状态，而不是承诺 finish 全部 features。

19 个 open Gantt rows 要逐项讨论。这份仓库没有原 workbook，不能准确替你认定哪 19 行。会前拿到表后，按以下类别处理：

- finish：必须交付／影响核心可靠性，有人愿意接、验收标准明确。
- defer：有价值但现在不做，移出 active schedule。
- cut：明确从本期 scope 删除，说明原因。
- verify-and-close：代码可能已实现，补证据后关计划项。

特别留意 README 还说 file-browser 用 fixtures，而代码已经 real API wiring。r81 可能需要核对完成状态，但不能仅凭这点认定 Gantt 已完成。

开会记录每项 ID、title、证据、决定、owner、acceptance criterion、deadline／review date。不要为了看起来负责把全部 19 项都揽下来。

## 10. OOP 与 framework 讨论

OOP 可能会问四个概念：encapsulation、abstraction、inheritance、polymorphism。先掌握一句解释和一个具体例子，再看项目中的 SQLModel classes。你的 ingestion 很多是函数式／procedural orchestration，不要硬说所有东西都用了四大原则。

可以提议未来 parser／embedder interface + dependency injection，让 production 用真实组件、tests 用 fakes。这是改进想法，不是当前已经完成的架构。

LangChain 的讨论保持准确：队友说明没有 LangGraph loops，不能 claim LangGraph。可以说团队选择直接实现 pipeline，保持 source selection 和 citation verification 可检查。July 决策文档没在当前仓库找到，开会问队友要链接再引用。

## 11. 从现在到周末怎么准备

第一轮，约 45 分钟：阅读 `ingestion.py`，把 `ingest_document`、`extract_text`、`split_long_text`、`create_chunk` 四个函数的输入／输出写出来。用一张纸解释 bullet、table、heading、page provenance 的处理。

第二轮，约 45 分钟：阅读 UploadModal、dashboard upload callback、useExplorerData、useExplorerMutations，以及 files routes。把 Upload／Rename／Replace 三条请求路径分别讲一次。

第三轮，约 30 分钟：准备两个贡献故事。每个故事用 90 秒英文，必须包括 actual change、evidence、limitation、teammate boundary。再补你实际怎样使用 AI 辅助；不要凭 commit history 推断。

第四轮，约 30 分钟：练习英文材料的 22 个问答。优先 OCR、350 vs 500、partial batch failure、127 tests、unknown performance 这五题，因为它们最容易暴露夸大的表述。

最后一次，约 20 分钟：完整讲 12 分钟 sharing，录音检查是否经常只报 tool name，却没说输入／输出／原因。检查 demonstration fallback，再准备 maintenance 的立场。

你现在需要的是把自己做过的东西理解到可以解释、证明、讨论取舍。能够坦然说清一个限制，往往比背很多术语更能体现工程判断。把这次 sharing 当成一次可控的面试练习，一次把一条流程练扎实。
