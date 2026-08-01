# 真实 API 验证矩阵

执行日期：2026-07-28（Asia/Shanghai）  
范围：仅真实服务连通性与最小真实端到端闭环；未使用 Mock、Stub、Fake Response 或固定响应冒充调用结果。

| 服务 | 当前真实配置 | 最低成本真实调用 | 鉴权 / Endpoint / 解析 | 结果 |
|---|---|---|---|---|
| 搜索：SearXNG | `http://127.0.0.1:8080`；`SEARXNG_SECRET` 已配置（未记录值）；引擎 `dogpile` | 3 条短查询中的有效查询返回真实网页结果；F-16 查询共取得 8 条候选 | HTTP 200；JSON 结果能被候选筛选器解析 | 成功 |
| 网页抓取：Crawl4AI | `http://127.0.0.1:11235`；`CRAWL4AI_API_TOKEN` 已配置（未记录值） | 抓取 Lockheed Martin 公开新闻页正文 | HTTP 200；Token 鉴权成功；正文能被证据抽取器解析 | 成功 |
| LLM：DeepSeek | `https://api.deepseek.com`；模型 `deepseek-v4-pro`；密钥来自现有 `config.yaml`（未记录值） | 真实结构化查询规划、证据抽取、事实校验与分镜生成 | HTTP 200；JSON 返回能被当前 Pydantic/业务模型解析 | 成功 |
| 图片生成：自托管 ComfyUI | `http://127.0.0.1:8290`；工作流 `selfhost/image_flux.json` | `/system_stats`、`/object_info` 与 1 次真实工作流提交 | ComfyUI 0.28.0；NVIDIA L40；返回真实 PNG 并被下游读取 | 成功 |
| 配音：Edge TTS | `zh-CN-YunjianNeural`，速度 1.2 | 1 次真实联网语音合成 | 返回 33,696 字节可播放 MP3；下游 FFmpeg 可解码 | 成功 |
| 字幕 / 帧渲染 | Chromium/HTML 本地渲染 | 2 张真实字幕合成帧 | 字幕在两张帧中均可见；时间分片覆盖完整旁白 | 成功（修复后） |
| 视频合成：FFmpeg | 本机 FFmpeg | 1 镜 H.264/AAC 合成 | 1080×1080、15 fps、音视频双流、5.616 秒 | 成功 |
| 文件服务 / 下载 | 项目本地文件 API | `GET /api/files/output/20260728_135256_1437/final.mp4` | HTTP 200；下载 114,571 字节；SHA-256 与磁盘文件一致 | 成功 |
| UI / 持久化 | React `:5273`、API `:8000`、SQLite | 项目页只读浏览、任务与项目查询 | UI 显示已完成/成片/100%；两条任务 completed；大小 114,571 字节 | 成功（修复后） |

## 未配置且本轮未使用的可选提供商

以下变量在当前可读取配置中缺失，因此没有对相应可选提供商发起调用；它们不影响本轮选定的 DeepSeek + 自托管 ComfyUI + Edge TTS 闭环：

- OpenAI 图片：`OPENAI_API_KEY`
- DashScope 图片/视频/VLM：`DASHSCOPE_API_KEY`（及可选 `DASHSCOPE_BASE_URL`）
- Ark / Seedream / Seedance：`ARK_API_KEY`
- Kling：`KLING_ACCESS_KEY`、`KLING_SECRET_KEY`
- Gemini：`GEMINI_API_KEY`
- DeepSeek 的独立 provider 环境变量：`DEEPSEEK_API_KEY`（本轮已有 `config.yaml` 密钥，故服务已成功验证）
- RunningHub：`RUNNINGHUB_API_KEY`（本轮使用本地 ComfyUI，不需要该变量）

## 非阻塞观察

- 浏览器控制台唯一错误为缺少 `favicon.ico`（404），与 API、任务状态、视频播放无关。
- ComfyUI 图片是真实 AI 生成结果，不是来源照片；可见的伪标记/外挂细节不能当作军事事实证据。

## Current rerun status (2026-07-28 16:55)

| Service/path | Fresh observation | Result |
|---|---|---|
| DeepSeek planning/research | Real request reached configured endpoint/model; HTTP 402 `Insufficient Balance` | External account failure; now reported precisely |
| Verified research reuse | Snapshot `9f694887-3222-4ae0-bea4-cd017d795c24`, real source chain, `reference_ready / verified` | Success |
| ComfyUI | Desktop shortcut started configured `127.0.0.1:8290`; real image returned | Success |
| Edge TTS | Fresh playable MP3, 33,696 bytes | Success |
| Subtitles / FFmpeg | Two visible Chinese subtitle frames; H.264/AAC output | Success |
| Fresh video job | `5fcf3798-c2c6-4a8f-8c10-291ed06b0283` | Completed |
| State consistency | Project, draft, scene, job and output all synchronized | Success |
| Verified prompt enforcement | Effective prompt rebuilt from verified subject + generic-safe fields; adversarial unsupported military details removed before generation | Success (`1 passed`) |
| Current-project video binding | Historical one-scene square artifacts are hidden after the F-16 draft changed; jobs now require a matching `workflow_revision` | Success |
| Reference-script degradation | Real web search ran; empty evidence now yields five real-LLM narrations marked `reference_unavailable` instead of a failed task | Success |
