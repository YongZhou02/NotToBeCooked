# NTBC 面试演示：已验证的本机流程

> 历史验收记录（2026-11-01），并非当前功能清单。2026-11-07 已新增 Replace file UI、反馈与 chart extraction 配置；下文保留验收当时的结果和限制。

验收日期：2026-11-01，供 11 月 2 日面试准备。本次验收对象是 Windows 本机 Web，地址 **http://127.0.0.1:5173/dashboard**。没有部署线上，也不代表桌面版、Android 和所有并发场景均已验收。

## 明天如何启动

1. 打开 Docker Desktop，等待其正常运行。
2. 双击项目根目录 **Start-NTBC.cmd**。
3. 启动程序会检查并启动已有数据库、本机 API 和 Web，随后打开浏览器。使用你已有的本机账号 `abc@gmail.com` 登录，密码未改。
4. 启动后先实际提一个问题，让本机 embedding 模型完成首次加载；首次解析／提问可能比后续慢。真实 Gemini 问答需要网络和有效 API 配额。

启动入口没有重建数据库、清空资料或修改 `.env`。Windows 后端进程会带 `TORCHDYNAMO_DISABLE=1`，避免本机缺少 `cl.exe` 导致解析失败。前后端使用一致的本机主机名，避免刷新时 cookie 丢失。

如果启动失败，窗口会停留并显示原因；日志在 `output/demo-run/api.log` 和 `web.log`。诊断命令：

```powershell
.\apps\api\.venv\Scripts\python.exe scripts\start_demo.py --check
```

## 建议演示路线

先选 **Year 1 → Sem 1 → DEMO-QA / Interview Demo Validation → Other → NTBC Interview Demo.pdf**。这是明确标注为受控测试的文档，用于验证系统流程，不能介绍成生产数据或正式评测 benchmark。

可直接使用以下已实测问题：

| 问题 | 已验证答案 |
|---|---|
| What is the release verification code? | DEMO-739 |
| What about the inspection interval? | 17 days，支持同一会话追问 |
| Who is the designated inspection owner? | Mira Tan |
| What is the purchase price of this product? | 文档未提供，系统拒答 |

演示顺序：选择文件 → 提问 → 点击 citation → 看原文高亮 → 追问 → Condense 摘要 → 打开聊天历史 → 刷新确认状态保留。需展示上传时，可用 `output/readiness/NTBC_Interview_Demo_Check_v2.pdf`，它是本次替换测试后的当前版本；文件名里的 v1/v2 是测试输入，不是实际产品发布版本。

再展示真实课程 PDF：**UNSORTED → Image PDF UI Test 2026-11-01 → CHAPTER 1.2.pdf**。该文件 27 页没有可提取的原生文字层，以下问题已正确返回并引用第 11 页：

> According to page 11, why is the resulting image in a pinhole camera very dim?

期望：只有一条光线从每个点进入相机，所以成像很暗。

你原有的大部分课程资料在 **COURSE / Course Workspace**；UNSORTED 和 COURSE 是不同的课程范围。

## 已完成的检查

| 范围 | 验证结果 |
|---|---|
| 登录与刷新登录 | 浏览器真实登录；HttpOnly 刷新 cookie 正常；刷新后仍在 Dashboard |
| 创建课程 | 通过界面创建 DEMO-QA，自动产生 5 个默认文件夹 |
| 文件夹 | 界面创建、重命名、删除本次创建的空文件夹均成功 |
| 上传／索引 | 浏览器实际选择 PDF 上传，状态变为 READY |
| 文件重命名／移动 | 界面操作成功；标签名称与列表数量更新 |
| 文件删除 | 界面删除专门创建的临时 TXT；数据库记录和原文件均删除，仅测试资料受影响 |
| 替换与旧索引失效 | 真实 API 替换测试 PDF；重新索引前 used_chunks=0，索引后返回 DEMO-739，未沿用 DEMO-482 |
| PDF 阅读 | 文件内容可加载；翻页、缩放正常；临界窗口尺寸抖动已修复 |
| 真实问答与追问 | Gemini 返回正确事实，引用对应原文；无答案时拒答 |
| 引用跳转／高亮 | 点击引用后，目标 PDF 原文出现 `.ntbc-quote` 高亮 |
| 摘要 | Condense 实际发送 document_summary，返回涵盖当前文件事实的摘要及引用 |
| 聊天历史 | 历史面板列出会话；选择后恢复完整问答 |
| 重启恢复 | 使用新启动脚本实际重启前后端；登录、课程、文档标签和聊天恢复 |
| 数据一致性 | 最终 19 条文件记录均有原文件；无处理中的遗留 ingestion；临时删除文件无残留 |

自动检查：UI **66 项通过**；后端独立数据库测试 **157 项通过、1 项跳过**（可选的真实 embedding 模型专项测试；真实 embedding 已在实际解析／问答中使用）。前端构建、前后端类型检查、lint、OpenAPI 合约检查、ERD 一致性检查均通过。构建有 bundle 大小提示，不影响本次构建成功。

## 今天修复／处理的具体问题

- PDF 临界高度下滚动条反复出现消失，造成 ResizeObserver 和 canvas 重画循环。固定滚动条占位后，同样 5 秒观察窗口的画布属性更新由 400 次降至 0；另检查了 3 种窗口尺寸、翻页和缩放。
- `127.0.0.1` 前端访问 `localhost` API 造成刷新 cookie 未保存。现在仅在前后端都是同协议的 loopback 地址时统一主机名；生产／相对 API 地址保持原配置。
- 6 个既有上传文件缺少存储原件。根据数据库 SHA256 找到完全一致的 D 盘原件并补回。未重新生成内容或改写原有数据库记录。
- 本机 PyTorch 需要不存在的 C++ 编译器。启动入口为 Windows 后端设置经过验证的禁用编译环境变量，应用解析逻辑没有为测试而替换成 mock。

## 仍需明确的边界

- **复杂图像 PDF 不是全面支持。** OCR 能提取部分图片文字；仍可能漏页、重复、损坏公式；照片颜色、物体数量、箭头关系不能可靠回答。不能用 READY 或 grounded=true 表示整份资料都理解正确。
- **检索覆盖仍有限。** 真实课程 PDF 上发现文字已提取但 top-k 没召回全部要点，造成部分回答。本次没有在面试前大改检索算法。
- **线上未作为演示环境验收。** 相同本机账号在线上返回过 401；不能直接把线上网址当成相同环境。本次修复保留在本机代码中。
- **替换文件没有相应的界面入口。** 此功能验证的是后台真实 API；不要预期文件菜单会出现 Replace。旧聊天保留历史答案，替换后要新提问验证新内容。

## 备份与证据

数据库验收前备份：`output/backups/ntbc-before-readiness-20261101.dump`。原始上传文件备份：`output/backups/ntbc-storage-ready-20261101.zip`。备份含私人数据，已加入 Git 忽略规则。

运行记录在 `output/readiness/` 与 `output/playwright/readiness-*.txt`；真实图片型课程 PDF 测试报告在 `output/visual-pdf-probe/real-pdf/REAL_PDF_UI_REPORT.md`。这些是本次实际运行记录，不是对所有输入的准确率保证。
