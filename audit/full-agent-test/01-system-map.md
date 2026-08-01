# 阶段 1：完整项目地图

## 技术栈与入口

- 后端：Python 3.11+、FastAPI、Pydantic v2、SQLAlchemy async、SQLite、Loguru。
- 前端：React 18、TypeScript、Vite、TanStack Query、Vitest、Playwright。
- 媒体：FFmpeg/ffprobe、ffmpeg-python、MoviePy、Pillow、HTML/Playwright 截图。
- 外部生成：OpenAI 兼容 LLM、DashScope、Seedream、Seedance、Kling、ComfyKit/ComfyUI/RunningHub、Edge TTS。
- 联网研究：SearXNG 搜索、Crawl4AI 抓取、LLM 结构化抽取与规划。
- CLI/桌面：没有独立 CLI 或桌面应用；`start_react_stack.bat` 负责 Windows 本地后端/前端启动。
- Web：`frontend/src/main.tsx` → `App.tsx` → 项目中心/视频生成页面。
- API：`api/app.py`，默认 `127.0.0.1:8000`，路由前缀 `/api`。

## 主要模块

| 关注点 | 位置 | 职责 |
|---|---|---|
| API 装配 | `api/app.py` | 生命周期、路由、中间件、任务管理器启动/停止 |
| API Schema | `api/schemas/` | 内容、分镜、视频、任务、项目、资源等请求/响应 |
| 前台任务 | `api/tasks/manager.py` | 内存状态机、asyncio future、进度、取消、清理 |
| 持久任务 | `military_video_gen/database/runtime_jobs.py` | 将内存任务同步到 `generation_jobs`，启动时对中断任务对账 |
| 核心服务容器 | `military_video_gen/service.py` | LLM/TTS/媒体/视频/持久化服务和管线注册 |
| 视频管线 | `military_video_gen/pipelines/` | 模板方法状态流；standard/custom/asset_based 三种实现 |
| 分镜/媒体 | `military_video_gen/services/frame_processor.py` | 按镜头生成 TTS、视觉素材、HTML 画面和分段视频 |
| 视频处理 | `military_video_gen/services/video.py` | 探测、时长对齐、音轨、字幕卡、串接、BGM、导出 |
| 事实研究 | `military_video_gen/research/` | 查询、URL 安全、抓取、来源排序、证据抽取、冲突、视觉事实、规划、缓存 |
| 提示词 | `military_video_gen/prompts/` | 旁白、标题、图片、视频、风格及资产脚本提示词 |
| 配置 | `config.example.yaml`、`military_video_gen/config/` | Pydantic 配置、环境变量展开、热加载 |
| 持久化 | `military_video_gen/database/`、`migrations/` | 项目、脚本、分镜、任务、资产、输出版本及迁移 |
| 文件存储 | `output/`、`data/`、`temp/` | 生成结果、SQLite/研究日志、临时媒体 |
| 工作流定义 | `workflows/`、`workflow_sources/` | ComfyUI/RunningHub JSON 工作流 |
| 模板 | `templates/` | 1080x1920、1920x1080、1080x1080 HTML 帧模板 |
| 测试 | `tests/`、`frontend/src/**/*.test.*`、`frontend/e2e/` | pytest、Vitest、Playwright |
| 部署 | `Dockerfile`、`docker-compose.yml`、`deploy/` | API 镜像及可选研究依赖 |

## 状态机与工作流

### 前端编辑状态

`script` → 用户确认脚本 → `storyboard` → 用户确认分镜 → `video` → 提交生成。

前端草稿保存项目设置、脚本、分镜和研究元数据；TanStack Query 轮询项目任务与全局任务。UI 只在脚本/分镜已确认且每个镜头含旁白与媒体提示时允许提交视频。

### 后端任务状态

`PENDING` → `RUNNING` → `COMPLETED | FAILED | CANCELLED`。

- `TaskManager.create_task()` 创建内存任务。
- `execute_task()` 创建 asyncio future，状态变化同步至 SQLite `generation_jobs`。
- `cancel_task()` 取消 future 并标记取消；应用关闭时取消所有非终态任务。
- 启动时 `reconcile_interrupted_jobs()` 将上次进程遗留的 pending/running 任务对账为中断状态。
- 任务只在协程正常返回后标记完成；异常标记失败。

### 研究工作流

主题/旁白 → 查询规划 → SearXNG → URL 安全检查 → Crawl4AI → 来源去重/分组/评分 → 证据抽取 → claim 清理与冲突标记 → 视觉事实抽取 → 分镜规划 → ResearchSnapshot/数据库。

当前代码将研究定位为“best effort”：参考不可用时仍可生成普通旁白；`research/gate.py` 的视频门禁是空实现。这是后续专项审计与测试的重点，不在系统地图阶段下结论。

## 一条视频任务的完整路径

1. 用户在 React `VideoGeneratorPage` 输入军事主题或脚本，选择 quick/reference、媒体/TTS 工作流、模板、BGM 等。
2. 脚本阶段调用 `/api/content/narration/async`。参考模式先尝试研究并将安全 claim 拼为参考上下文，再由 LLM 生成旁白；quick 模式直接生成。结果保存到项目/任务状态。
3. 分镜阶段调用 `/api/content/image-prompt/async` 或 `/api/content/research/async`，形成旁白、英文媒体提示、来源和研究警告；用户确认后前端构造 `confirmed_storyboard`。
4. 视频阶段 POST `/api/video/generate/async`。API 解析模板媒体尺寸，创建内存 Task 和持久 GenerationJob，然后启动后台协程。
5. `MilitaryVideoGenCore.generate_video()` 选择默认 `StandardPipeline`（也支持 custom/asset_based）。每次执行创建独立 `output/<task-id>/`。
6. `StandardPipeline` 顺序执行：环境准备 → 使用已确认分镜或生成/拆分旁白 → 标题 → 视觉提示 → Storyboard → 素材生产 → 后期 → finalize。
7. 每个镜头由 FrameProcessor 处理：TTS 旁白 → 图片/视频 API 或 Comfy 工作流 → HTML 模板渲染字幕/画面 → FFmpeg 生成/合成镜头片段。进度事件回写 TaskManager。
8. VideoService 使用 ffprobe 校验/读取媒体属性，以 FFmpeg 串接镜头、对齐音频和视觉时长、叠加字幕卡并可混入 BGM，输出 `final.mp4`。
9. Pipeline finalize 构造 `VideoGenerationResult`，持久化 metadata/storyboard/history；后台任务把结果路径、时长等写入内存与 SQLite，并转为 `COMPLETED`。
10. 前端轮询 `/api/jobs`、`/api/projects/{id}/jobs` 或 `/api/tasks/{id}`。文件通过受控 `/api/files/{path}` 路由读取，历史/项目页面展示最终视频及过程资产。

## 外部边界与安全边界

- 付费/远程边界：LLM、图片、视频、TTS、Comfy/RunningHub、搜索、爬取。本次审计不调用真实服务。
- URL 边界：研究 URL 经 `research/crawlers/security.py` 做 scheme、主机、DNS 与私网地址限制。
- 文件边界：模板、BGM、输出、上传/资源路由、工作流 JSON；需要防路径穿越、任意覆盖和恶意文件名。
- 子进程边界：FFmpeg/ffprobe 与启动脚本；需要固定参数传递和可靠终止。
- 数据边界：SQLite `data/military_video_gen.db`、JSON metadata、研究缓存/日志。
- 密钥边界：`.env`、`config.yaml`、环境变量；日志和响应必须掩码。

## 缓存、日志与生成物

- Python/pytest/ruff、Vite/TypeScript/Playwright 缓存可重新生成。
- 研究缓存由 `research/cache.py` 管理，研究监控写入 data 日志。
- 运行输出在 `output/`，临时文件在 `temp/`，可能包含用户资产或未完成任务，清理前必须分类。
- `PersistenceService` 在输出目录维护任务元数据和索引；`HistoryManager` 提供历史、重试参数复制等兼容接口。
