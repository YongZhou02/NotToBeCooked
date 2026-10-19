# NotToBeCooked 面试训练手册

准备日期：2026-10-01。依据当前工作区的实现，并读取 main 的 embeddings.py 确认最新模型加载锁。工作区目前在 dev；不要把本地未提交改动描述为 main 已发布功能。README 有过时描述，以函数实现为准。这份资料基于代码阅读，未重新运行项目全流程或性能测量。

## 1. 项目介绍：先讲问题，再讲实现

30 秒版本：

> NotToBeCooked 是一个针对课程资料的学习助手。用户上传讲义后，系统解析并分块，生成向量存入 PostgreSQL。提问时，我们先限制到该用户有权限的文件，再做向量和关键词混合检索，把相关内容交给 Gemini 生成带引用的回答。返回前还会检查引用是否来自检索内容。前端使用 TypeScript 和 React，后端使用 Python 和 FastAPI，桌面壳使用 Tauri。

然后补一句自己的真实职责：我负责【具体模块】，解决过【实际问题】，用【测试、日志、实际操作】验证。尚未确认的作者归属不要写成自己的贡献。

## 2. 技术名称必须分类正确

| 部分 | 语言 | 框架、库或工具 | 在项目中的作用 |
|---|---|---|---|
| 前端 | TypeScript，JSX；样式用 CSS | React、Vite、Tailwind、TanStack Query、Zustand | 页面、构建、服务端数据缓存、工作区状态 |
| API 后端 | Python | FastAPI、Pydantic、SQLModel、SQLAlchemy | HTTP 路由、请求验证、数据库访问 |
| 数据库 | SQL 是查询语言 | PostgreSQL、pgvector | 关系数据、全文索引、向量存储与检索 |
| 数据库连接与迁移 | Python | asyncpg、Alembic | 异步 PostgreSQL 驱动、数据库结构版本管理 |
| 文档与 AI | Python | Docling、SentenceTransformers、PyTorch；Gemini API | 文档解析、本地 Embedding、远程生成回答 |
| 桌面壳 | Rust；界面仍然是 TypeScript/React | Tauri | 包装共享前端为原生应用 |
| 工程管理 | 配置文件及脚本 | pnpm、uv、Turborepo、Docker、OpenAPI | 依赖、任务、数据库环境、接口契约 |

React、FastAPI、PostgreSQL 都不是编程语言。Gemini 负责生成，Embedding 模型负责检索用的向量；本项目调用和运行模型，不等于训练了基础模型。

## 3. 所有按钮问题的回答顺序

按这个顺序说：UI 事件 → 前端输入与状态 → HTTP 方法和路径 → 身份验证 → 资源权限 → 服务处理 → 数据读写与事务 → 返回值 → 页面更新 → 失败路径。

回答分三层：先用 30 秒说完整链路；对方追问时再给函数名；最后解释设计原因和局限。不要开头就报十个库名。

## 4. 点击发送问题，实际发生什么

代码路径：

1. `packages/ui/src/components/chat/ChatInput.tsx` 提交文本；`Chat.tsx` 的 `handleSend` 调用外部发送回调。
2. `packages/ui/src/pages/dashboard.tsx` 接到发送，再进入 `packages/ui/src/hooks/useChatSession.tsx`。
3. hook 解析文件 mentions、确定 course/file scope，带上 conversation_id、question、top_k 和 intent；已有会话会先做乐观缓存更新。
4. `packages/contracts/src/api_client.ts` 的 `api.chat.query` 发送 `POST /rag/query`。客户端从内存取 access token，设置 Bearer 请求头。
5. FastAPI 验证请求结构；`get_current_user` 验证身份。`apps/api/app/routers/rag.py` 获取或创建会话，把用户消息加入 session。
6. 普通问答先用 `_scope_file_ids` 通过文件、文件夹、课程与用户的关联确定允许检索的文件。结果为空时直接返回空检索结果。
7. `_retrieve` 用 `asyncio.to_thread(embed_query, ...)` 生成问题向量，再调用 `hybrid_search`。
8. `apps/api/app/db/vector_ops.py` 做向量相似度与 PostgreSQL 全文检索，只检索 active ingestion run 的块，使用加权 RRF 合并排名。
9. `build_context` 组装带来源编号的上下文；`generate_answer` 调用 Gemini。document_summary intent 则读取单文件完整的 active run 块，路径与普通 top-k 问答不同。
10. 后端解析引用，删除未使用引用，校验引用文本与来源块，检查编号及 coverage 一致性。校验失败会用不可验证提示替换回答。
11. 保存 assistant 消息、引用和 scope snapshot，更新会话时间并 commit；返回 RagAnswer。
12. 前端更新活动会话并使消息与会话列表缓存失效，重新获取服务器数据，渲染回答与引用。

60 秒口述：

> 点击发送后，React 先收集问题和当前课程或文件范围，通过 API client 向 /rag/query 发 POST 请求。后端验证 token 和请求，再确定该用户能访问哪些文件。问题会转成向量，与关键词检索一起查 PostgreSQL 中当前有效版本的 chunks，使用 RRF 合并结果。相关内容进入 prompt，Gemini 生成答案。我们不会直接相信模型的引用，而会在返回前检查引用来源和摘录。最后保存消息并提交事务，前端刷新会话缓存显示结果。

追问：

- 为什么前端传 file_ids 后，后端还要检查？客户端可被篡改，界面隐藏不能代替权限检查。
- 为什么空文件列表要早返回？当前底层检索把空列表当作不加文件过滤，直接传下去可能扩大到其他用户的数据。
- 用户消息 `session.add` 后就保存了吗？尚未等于最终 commit。当前请求末尾提交消息；创建新会话的函数可能更早单独 commit，不能说整个请求只有一个事务。
- 这是 streaming 吗？当前这条路径返回完整 JSON，不能因为用了 async 就说逐 token 流式返回。
- 是否一定记得上一轮问题？有消息持久化不等于历史消息被送进模型；当前生成调用传入本次问题、context 和 sources，不能仅凭 conversation_id 宣称多轮历史参与推理。

## 5. 点击上传，实际发生什么

1. `UploadModal.tsx` 检查扩展名、50 MB 限制和本次选择中的重复文件，然后调用上传回调。前端校验只改善体验，不能当安全边界。
2. dashboard 用 upload mutation；API client 创建 FormData，携带 folder_id 和 upload，发送 `POST /files`。multipart 的 boundary 由浏览器设置。
3. `routers/files.py` 验证登录用户及 folder 所属权；course_id 从已验证的 folder 得到。
4. `services/storage.py` 分段读取上传，限制字节数，计算 SHA-256，把原始文件写入本地存储。storage_key 与用户和文件 UUID 关联。
5. 数据库写 FILE 元数据，状态 uploaded，commit 后返回 `201 Created`。原始文件字节没有作为整份文件存进 PostgreSQL。
6. dashboard 随后发送 `POST /files/{id}/ingest`。后端验证文件权限，创建 queued、非 active 的 INGESTION_RUN，先 commit，然后注册 BackgroundTasks，返回 `202 Accepted`。
7. 后台任务使用自己的数据库 session。Docling 解析、extract_text 提取、create_chunk 按内容和 token 分块、embed_text 批量生成向量；阻塞解析和推理通过 to_thread 调用。
8. 写 CHUNK，记录 run 成功或失败；后台完成步骤处理 active run 的切换及文件状态。检索只读取 active 的版本。
9. `useExplorerData.ts` 在存在 uploaded/processing 文件时每 3 秒刷新课程文件列表，终态后停止该轮询条件。

60 秒口述：

> 我们把上传和索引拆成两个阶段。上传请求负责把原文件安全写入存储，并把元数据写入数据库，成功返回 201。随后前端发起 ingest，后端先记录任务，再返回 202。后台负责解析、分块、Embedding 和写入 chunks，前端轮询文件状态。因此上传成功代表文件保存了，索引 ready 才代表能用于检索。

追问：

- 为什么返回 202？已接受处理，不代表处理完成。
- BackgroundTasks 是任务队列吗？它是当前进程内响应后的后台执行机制；没有独立持久化队列的可靠投递与重启恢复保证。规模扩大后可考虑独立 worker、持久化队列、重试和幂等。
- 重复点 ingest 会怎样？需要区分“只允许一个 active run”和“只会执行一个任务”；前者的唯一约束不能自动保证后者。
- 为什么有 INGESTION_RUN？记录每次模型和分块配置，保留版本与状态，避免新旧 chunks 混用。
- SHA-256 是否自动防止重复上传？计算校验和不等于代码已实现全局去重；先查是否真的查询并拒绝重复。
- 扫描 PDF 怎么办？当前 PDF 配置关闭 OCR，可能提取不到正文；空内容会失败。未来可加按需 OCR，但不能说目前已支持所有扫描件。

## 6. OOP：用自己的代码讲

### Class 与 object

Class 定义结构与行为，object 是具体实例。`ApiClient` 是 class；用 `new ApiClient(...)` 得到客户端实例。Python 的 Course 是模型类，`Course(...)` 是实例；调用 session.add/commit 后才能成为持久化行。

### 封装 Encapsulation

`ApiClient` 把 baseUrl、token getter、refreshSubscribers 和内部 request 方法放在类内，对外提供 auth/files/chat 操作。调用者不用重复处理请求头、错误解析和 token 刷新。

TypeScript 的 private 通常是类型检查层面的访问限制，不要描述为运行时不可绕过的安全控制；JavaScript 的 #private 与它不同。Python 单下划线通常是约定，也不是权限机制。

### 抽象 Abstraction

UI 调用 `api.files.upload` 而不必了解 fetch 的具体细节；storage 模块用 storage_key 隔离本地路径。抽象不一定需要 abstract class，函数或模块也能隐藏实现细节。

### 继承 Inheritance

`Course(SQLModel, table=True)`、`Chunk(Base)`、`TSVector(TypeDecorator)`、`UploadTooLargeError(Exception)` 是实际继承例子。继承应表达 is-a 关系和合理契约，不是为了减少几行重复就建立层次。

### 多态 Polymorphism

同一接口能由不同实现响应。Python 支持 duck typing；TypeScript 可通过 interface/structural typing 表达相同契约。`TSVector` 作为 TypeDecorator 参与 ORM 的类型机制。

扩展示例（尚非现有实现）：定义 Storage 的 put/get/delete 契约，LocalStorage 与 ObjectStorage 实现它，上传服务依赖该契约。必须说“可以这样改”，不要说项目已有这些类。

### 组合 Composition 与 SOLID

React 用组件组合；服务把检索、模型生成与 grounding 检查组合成流程。组合表达 has-a/uses-a，常比复杂继承更便于替换与测试。

- S：API client 统一请求行为；storage 隔离字节存储，但是否职责过大仍需按变化原因判断。
- O：新存储实现通过稳定契约扩展，这是演进方向，不能说当前已经完成。
- L：子类必须满足调用者对父类的行为预期；不仅方法名相同。
- I：客户端不应被迫依赖自己不用的巨大接口。
- D：高层逻辑依赖抽象契约；FastAPI Depends 是依赖注入机制，但仅使用 Depends 不代表整套代码已符合 DIP。

## 7. 高频问题与合格回答要点

| 面试题 | 回答必须包含 |
|---|---|
| 为什么不用直接让 LLM 看整份 PDF？ | 上下文限制、成本、延迟、来源定位；RAG 先筛资料，但效果依赖检索质量 |
| 为什么 hybrid search？ | 向量擅长语义近似，关键词擅长术语/精确词；二者互补，需要评估而不是假定更好 |
| RRF 是什么？ | 每份榜单按 weight/(k+rank) 加分再排序；不直接相加不同量纲的相似度分数 |
| Embedding 是什么？ | 把文本映射到向量，语义相近通常距离更近；本项目使用 1024 维；模型切换需考虑重建索引 |
| chunk 太大或太小呢？ | 大块可能混入无关内容并占上下文，小块可能丢语境；用检索测试和答案证据评估 |
| 为什么 PostgreSQL + pgvector？ | 同一数据库管理关系、事务、权限关联和向量；运维简单，但超大规模需要重新评估 |
| 用了什么索引？ | chunk embedding 的 HNSW，content_tsv 的 GIN；具体查询是否使用须看 EXPLAIN，不凭建了索引就断言 |
| 什么是 PK/FK/unique？ | 标识行、约束关联、禁止重复组合；结合 user/course/folder/file/run/chunk 举例 |
| 什么是事务、flush 和 commit？ | 一组数据库操作提交/回滚；flush 发 SQL但通常尚未提交，commit 完成事务；refresh 从库读取状态 |
| ACID 是什么？ | 原子性、一致性、隔离性、持久性；数据库事务不能把本地文件和远程模型请求自动纳入原子提交 |
| async 为什么不自动变快？ | 等 I/O 时可让出执行；阻塞计算仍会卡 event loop；to_thread 移开阻塞不保证 CPU 吞吐提升 |
| 模型为什么不每次重新加载？ | 冷启动昂贵、占内存；main 缓存模型，初次加载加 threading.Lock 并二次检查，防并发重复加载 |
| JWT 是加密的吗？ | 常见签名 JWT 不加密 payload；验证签名、允许算法、过期时间；不要放秘密 |
| 登录和权限有什么区别？ | authentication 确认你是谁，authorization 确认你能访问该资源；登录不代表拥有所有 UUID |
| CORS 能保护 API 吗？ | 浏览器跨来源访问规则；不能代替认证和授权，也不能阻止所有非浏览器请求 |
| 密码怎么保存？ | Argon2 hash，不能明文存储；hash 不是可逆 encryption |
| access token 放哪里？ | 当前 API client 从内存获取；refresh 使用 HttpOnly cookie；401 时协调刷新，再重试 |
| TypeScript 足以验证 API 返回吗？ | 静态类型不能保证网络 JSON；需要运行时验证；项目有 Zod 与 OpenAPI 契约 |
| useState、Zustand、Query 的区别？ | 组件局部状态、跨组件客户端工作区状态、服务器数据与缓存；不要所有数据都放一处 |
| 什么是 optimistic update？ | 先显示预期变化，失败回滚/纠正，成功刷新服务器真值；不是数据库已提交 |
| 401/403/404/422/500 怎么区分？ | 身份失败/无权限/不可见或不存在/输入验证失败/服务端异常；本项目部分资源用 404 隐藏存在性 |
| 如何减少 hallucination？ | 限定来源、检索、prompt、引用验证、拒答；引用存在性不证明所有推理与事实正确 |
| 如何测 RAG？ | 固定问答与相关块集合；Recall@k、MRR/nDCG、引用正确率、回答质量、延迟、拒答；不虚构结果 |
| 怎么测试权限？ | 两个用户访问互相的文件/会话；无权限、空 scope、跨课程、失效 token；检查不会泄漏内容 |
| mock 测试够吗？ | 不够；mock 隔离逻辑，真实 PostgreSQL 才能验证约束、驱动、JSONB 序列化与事务行为 |
| 服务慢怎么定位？ | 分阶段测解析、Embedding、数据库、模型请求和序列化；观察资源；瓶颈确定后改 |
| 并发扩大到 1000 用户？ | 先定义请求率/文件大小/延迟目标；限流、worker、队列、模型资源、连接池、索引与压测；不是只加 async |
| AI 写了代码，你贡献在哪里？ | 说明自己定义约束、审查、定位问题、测试与验证；现场解释与修改自己的模块 |

## 8. 四个可以研究的真实工程故事

1. 空 scope 可能成为无过滤查询：读 `_scope_file_ids`、`_retrieve`、vector_ops 和 test_rag_scope，理解权限必须在检索前确定。
2. 阻塞解析使健康检查无响应：读 processing 的 to_thread 调用和相关测试，说明 event loop 为什么被占用。代码注释里的测量是仓库记录，不是你本人测量，也不是本次重新验证的性能。
3. 并发首次加载模型：读 main 的 embeddings.py 与 test_embeddings，画出两个线程都看到 None 的时序以及锁内二次检查。
4. UUID 在 JSONB 中序列化失败：读 database.py 与 test_jsonb_uuid；mock 没有真实序列化，真实驱动才暴露问题。只转换 UUID，其他无法序列化对象继续报错。

每个故事按：触发条件 → 可观察症状 → 假设 → 验证证据 → 根因 → 修复 → 回归 → 局限。若不是自己实现，表述为“团队的实现中，我研究并验证了……”。

## 9. 面试时怎样表现实力

把“用了 async”升级成“解析是同步阻塞工作，即使放在 async 函数内也会占住 event loop，所以我们把解析和 Embedding 放到 worker thread”。

把“有权限检查”升级成“请求的 file_ids 不可信，我们从当前用户拥有的课程关联出文件集合，再交给检索，而且空集合必须早返回”。

把“回答有引用所以准确”升级成“我们验证引用编号及摘录与检索来源一致，但这并不证明每一句推理在语义上正确，后续还要做答案评估”。

把“我做了整个系统”改成可验证的职责描述。自信来自能追到代码、解释取舍、承认局限并提出验证步骤，不靠虚构生产规模、指标或个人贡献。

不知道时：

> 这一点我还没验证。我目前判断是【推理】，依据是【代码/原理】；我会用【实验/日志/查询计划】确认，再决定【改动】。

## 10. 七天训练安排

1. 第一天：画架构和九个实体关系，练 30 秒和 90 秒项目介绍。
2. 第二天：逐个断点/日志追发送问题。记录 request payload、路由、查询、commit、response 和 UI 更新，不展示真实 token。
3. 第三天：追上传与索引，分别观察 201、202、queued/processing/ready/failed；模拟空正文和无权限。
4. 第四天：讲 class/object 和 OOP 四概念，现场用 ApiClient 和模型类举例；区分封装与权限。
5. 第五天：SQL join、事务、索引、async、锁、JWT、错误码；每题一分钟并接受两次追问。
6. 第六天：整理两个真实贡献故事和一个失败/改进故事；提供自己实际的验证证据。
7. 第七天：模拟 45 分钟面试：项目介绍 3 分钟、按钮追踪 10 分钟、技术追问 15 分钟、代码/SQL 12 分钟、反问 5 分钟。

如果只有一天：优先项目介绍、发送链路、上传两阶段、OOP、一个真实贡献故事、一个当前局限。

## 11. 模拟面试评分

每轮 10 分：链路完整 2；代码与数据事实准确 2；解释为什么 2；失败/权限/事务边界 2；表达和真实职责 2。

首题：用户在课程页面输入问题并按下 Send。请用 60–90 秒从 React 事件讲到 PostgreSQL 和返回页面；再回答“为什么浏览器传来的 file_ids 不可信？”

答题后逐轮修正，不要求先背整份资料。能够不看稿解释并承受追问，才算掌握。
