# JevChat-Windows Custom

这是基于 [jev-chat/jev-chat-windows](https://github.com/jev-chat/jev-chat-windows)
`v0.1.12` 的源码级二次开发版本，维护仓库为
[XiaoRui114514/jev-chat-windows-custom](https://github.com/XiaoRui114514/jev-chat-windows-custom)。
它保留上游的 Windows Graphics Capture、离线 OCR、Jev 判断、候选生成、排序和“填入但不发送”流程，
并把 custom-jev 的自定义 Provider 正式整合进源码。

## 功能

- OpenRouter、TypeSafe、任意 OpenAI Compatible 判断来源；自定义 Base URL、API Key、模型和 `/models` 获取。
- 自定义 TypeSafe 兼容来源，模型列表不可用时仍可手填模型 id。
- 结构化微信消息：发送人、时间、文本、消息类型、区域和分层置信度。
- 普通文字走快速路径；图片、贴纸、GIF、视频号、文章、链接走可选的高级识别路径。
- 本地 emoji 语义识别，以及可选的视觉描述和上下文意图分析。
- 视频号和文章卡片识别，支持标题、作者、来源、缩略图区域和“未开启内容识别”状态。
- 有界缓存、调用次数统计、调试窗口中的 OCR/媒体/视觉耗时和最终模型上下文。
- 旧 `config.json` 自动补齐新字段；默认关闭所有视觉和富媒体识别。

程序不会自动点击发送。聊天截图只在内存中处理；启用视觉功能时只上传必要的裁剪区域，API Key 不写入日志。

## 安装运行

发布包为 Windows onedir 目录，下载后保持目录结构并运行 `jev-chat-windows.exe`。系统要求 Windows 10 1903+
或 Windows 11，并需要打开可识别的微信聊天窗口。

源码运行需要 Python 3.10–3.12：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## 模型配置

设置页分为“判断 · Jev”和“起草 · 语言模型”。判断来源可选 OpenRouter、TypeSafe 或自定义来源；自定义
OpenAI Compatible 使用 `Base URL`、`API Key`、`Model`，程序会请求 `GET /models`（服务不提供时可手填）
并通过 `POST /chat/completions` 判断。Base URL 只接受 `http(s)` 地址，不允许把密钥放入 URL。

TypeSafe 直连和自定义 TypeSafe 保留上游协议；自定义来源不依赖二进制补丁。配置写入 `config.json`，密钥继续
使用 Windows 当前用户环境变量槽位，并兼容旧变量名。

## 识别设置

“识别”页默认关闭：

- 视频号识别
- 文章/链接识别
- 图片内容识别
- 复杂表情包视觉识别与上下文意图分析

开启某个选项后，系统先用本地几何、OCR 和文件特征判断是否确有对应卡片，再只对命中的消息调用 Vision Provider。
普通文字、标准 emoji 和关闭状态下的卡片不会触发视觉 API。Vision Provider 使用独立的 OpenAI Compatible 配置，
支持 Base URL、API Key 和模型；同一裁剪区域在短期缓存有效期内不会重复调用。

## 代码结构

```text
app/                 窗口、设置、截图子进程、调试视图
core/providers/      判断 Provider 抽象、OpenRouter、TypeSafe、自定义协议和 HTTP 传输
core/ocr/            OCR 清洗和保守预处理
core/parser/         微信区域、头像、气泡、发送人和媒体类型解析
core/message/        Message 数据结构、上下文渲染、连续消息跟踪
core/media/          可选富媒体识别、Vision Provider、有界缓存
core/emoji/          本地 emoji 语义与可选上下文意图分析
tests/               设置迁移、Provider、解析、媒体开关和 Engine 回归测试
```

## 测试与构建

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q app core main.py
pyinstaller --noconfirm --clean jev.spec
.\.venv\Scripts\python.exe tools/verify_frozen.py dist/jev-chat-windows/jev-chat-windows.exe
```

`jev.spec` 使用 onedir 打包，显式收集 OCR、Qt、模型 SDK 和新增识别模块。CI 配置在
`.github/workflows/release.yml`，tag 发布会构建 Windows zip。

v0.2.1 修复启动时 `DLL load failed while importing QtCore: 找不到指定的程序`：打包时隔离
DLL 搜索路径，避免把 Poppler 等其他工具的同名 `icuuc.dll` 收进程序。Windows 系统 ICU
由操作系统提供。构建和 CI 在压缩发布前会实际启动 exe，验证主界面、设置页、调试窗和
离线 OCR；检查过程不采集微信、不联网、不读写用户配置或密钥。

## 已知限制

微信改版、非标准 DPI、极小窗口或严重遮挡可能降低区域和发送人置信度；低置信度消息会保留为 `unknown` 或
`uncertain`，不会强行猜测。视频号和文章正文目前只识别卡片可见信息，不下载或抓取外部页面。OCR 仍依赖本地
RapidOCR 模型，Windows Graphics Capture 需要聊天窗口可见且未最小化。

## 版权与许可

本项目保留上游 MIT License、原作者归属和 `NOTICE`。本项目是独立的二次开发版本，不代表官方发布或背书。
Jev 判断内核和原始 Windows 项目归属见上游仓库；第三方依赖的许可证见 `NOTICE`。分发时请一并保留
`LICENSE` 和 `NOTICE`，并只处理自己有权查看的聊天内容。
