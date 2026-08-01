# 真实端到端视频生成报告

## 结论

真实最小闭环已成功：联网搜索、真实网页抓取、DeepSeek 文案/证据处理、军事事实门禁、自托管 ComfyUI 图片生成、Edge TTS 配音、字幕渲染、FFmpeg 合成、文件下载、数据库任务状态和 UI 展示全部完成。最终文件真实存在、可下载、可解码，有画面、有声音、有可见字幕。

本轮没有用 Mock、Stub、Fake Response 或固定响应替代任何要求中的真实服务调用，也没有重跑全量仓库测试。

## 输入与实际闭环

测试主题采用用户建议的 F-16 基础科普方向。为降低成本，使用 1 镜、1 张 1024×1024 真实生成图片、1 次真实 TTS、15 fps、无 BGM；最终成片为 5.616 秒。链路如下：

1. SearXNG 通过真实联网搜索取得 8 条候选结果。
2. Crawl4AI 真实抓取 Lockheed Martin 厂商新闻正文。
3. DeepSeek `deepseek-v4-pro` 真实执行查询规划、证据抽取、事实校验和带溯源分镜生成。
4. 研究任务 `9f694887-3222-4ae0-bea4-cd017d795c24` 完成，状态 `reference_ready / verified`，无警告。
5. 对最终来源无法充分支持的“首飞年代、典型外观特征”没有补写；最终旁白收敛为：`F-16由洛克希德·马丁制造，首架生产型于1978年交付。`
6. ComfyUI 0.28.0 在 NVIDIA L40 上执行 `selfhost/image_flux.json`，真实返回 `01_image.png`。
7. Edge TTS 通过 `zh-CN-YunjianNeural` 真实返回可播放 MP3。
8. HTML 帧渲染生成两张字幕帧；FFmpeg 合成 H.264/AAC MP4。
9. 文件 API 下载返回 HTTP 200，下载内容与磁盘文件 SHA-256 完全一致。

## 资料与事实校验

- 搜索查询：
  - `F-16 fighter aircraft first flight manufacturer history`
  - `F-16 fighter aircraft official manufacturer design`
  - `F-16 site:lockheedmartin.com history first flight design`
- 最终采用来源：[Lockheed Martin Commemorates 25th Anniversary of First Global Production F-16 Delivery](https://news.lockheedmartin.com/2003-08-18-Lockheed-Martin-Commemorates-25th-Anniversary-of-First-Global-Production-F-16-Delivery)
- 来源类别：厂商；选择分数 0.8。
- 结构化事实：2 条，置信度均为 1.0；分镜携带 `claim-1`、`claim-2`、字段级 provenance、`fallback_level=verified_generic` 和 `verification_status=verified`。
- 审查确实生效：主题要求中的首飞年代和典型外观描述未获得当前最终来源的充分支撑，因此被省略，没有凭模型常识补写。

说明：画面为 AI 生成的通用视觉重建，不是史料照片；画面中的伪标记或外挂细节不作为事实证据。

## 真实生成结果

- 最终视频：`output/20260728_135256_1437/final.mp4`
- 大小：114,571 字节
- SHA-256：`5EF63E6AC41017FB3BF794264817B0031265555E2D1A87AD96ACE76DC51C9FB8`
- 容器时长：5.616 秒
- 视频流：H.264，1080×1080，15 fps，5.600 秒
- 音频流：AAC，24 kHz，单声道，5.616 秒
- 原始 TTS：MP3，33,696 字节，可由 FFmpeg 解码
- 字幕：两段时间片均成功渲染，合成帧中实际可见
- 下载：HTTP 200，114,571 字节，哈希与本地文件一致

## UI、任务与数据库一致性

- 项目 `1b07c106-eaf4-4ac2-8bbe-73769330f869`：`completed / output`。
- 运行任务 `ce092b1a-8f41-448a-98db-9787cd9a04fb`：`completed`。
- 持久任务 `54c728ec-e3ac-575d-95e5-18ff819c7e77`：`completed`。
- 两条任务的结果大小均为 114,571 字节；输出版本为 `approved`。
- UI 真实浏览结果：已完成、成片、脚本已确认、1 镜、生成完成、100%；脚本和分镜显示同一条核验旁白。
- UI 截图：`output/playwright/live-e2e-project-state.png`。
- 唯一浏览器控制台错误是 `favicon.ico` 404，不影响功能或成片。

## 真实调用中暴露并修复的问题

- Dogpile 并发搜索会失败：改为顺序调用、限制查询和重试；真实搜索复测成功。
- DeepSeek 证据抽取曾返回 HTTP 200 但正文 JSON 为空（推理消耗输出预算）：提高结构化输出预算至 4000，单批 1 页、最多 2 条声明，并正确上抛批量错误；真实抽取复测成功。
- 厂商来源/跨语言 F-16 相关性和正文摘录排序不足：补充厂商识别、历史页加权、可靠正文行选择；最终产生可核验来源和声明。
- 5173 落入本机 Windows/Docker 保留端口范围：项目与 Vite 端口改为 5273；真实前端 HTTP 200。
- 字幕模板的通用 `.footer` 被品牌隐藏规则误伤：停止隐藏该内容类，并仅复用已生成图片/音频重渲染字幕和 FFmpeg，不重复调用高成本服务。
- 字幕修复后旧内存任务会遮盖数据库新文件大小：终态任务改为以持久结果为准；目标测试 `tests/api/test_jobs.py` 为 3 passed，API 重启后返回 114,571。
- 项目 UI 草稿仍保留早期试输入：仅同步到已核验脚本、已完成分镜和成片阶段，不重新调用 LLM。

## 未执行内容

- 未重跑整仓全量测试。
- 未重新做仓库审计、重构或文件清理。
- 未调用未配置的 OpenAI、DashScope、Ark、Kling、Gemini、RunningHub 路径。
- 未额外生成候选图、候选视频或第二条 TTS。

## 2026-07-28 16:55 fresh rerun addendum

The reported `research snapshot is not ready` failure was traced to several concrete causes and fixed at their source: the visual-planning timeout had remained hard-coded at 20 seconds, English SearX queries were sent without an English language hint, cross-language claim matching could over-link on the token `F-16`, and provider failures were collapsed into a generic snapshot error. Planning now uses the configured 300-second limit, search retries/falls back across enabled engines, cross-language evidence mapping is entailment-only and fails closed, numeric claims receive a subset guard, and HTTP 401/402/404/429 are reported accurately.

The current DeepSeek credential and endpoint were tested again with real requests. Authentication reaches `https://api.deepseek.com` and model `deepseek-v4-pro`, but the provider now returns HTTP 402 `Insufficient Balance`. This is an external account state, not a timeout. A brand-new research snapshot therefore cannot honestly be claimed for this rerun. In accordance with the user's explicit permission to reuse completed review, the already real, verified snapshot `9f694887-3222-4ae0-bea4-cd017d795c24` was restored and reused; it contains real SearX/Crawl4AI/DeepSeek results produced before the balance was exhausted.

A fresh video job `5fcf3798-c2c6-4a8f-8c10-291ed06b0283` then completed through real ComfyUI, Edge TTS, subtitle rendering and FFmpeg. The output is `output/20260728_165429_1f15/final.mp4`, 115,493 bytes, SHA-256 `8B066C2CBAEAABDC949C493A2AEC2E67CE9D705108140E1F3E21ABDBF095A03D`. FFprobe reports H.264 1080x1080 at 16 fps and AAC audio, with a 5.625-second container duration. Both Chinese subtitle intervals are visibly present. Project, workspace draft, scene and video-job records all report completed/output and refer to the same verified research snapshot.

No full repository suite was rerun. Only focused research/provider/gate regressions were run during these fixes; all selected groups passed (latest gate/service selection: 23 passed).

Final independent-review finding closed: verified scenes no longer pass the planner's free-form `media_prompt` to media generation. The server reconstructs the effective prompt deterministically from the verified subject plus broad non-identifying creative fields, adds explicit negative constraints, then stores the same rendered value in `media_prompt` and `visual_description`; the existing snapshot gate prevents later substitution. A focused adversarial regression containing unsupported engine count, nuclear weapons, national insignia and a named frontline base passed (`1 passed`), confirming all such details are absent from the prompt that reaches generation.

## 2026-07-28 current-project correction

The two square F-16 MP4 files above are technically valid live-E2E artifacts, but they do **not** represent the user's later seven-scene vertical-video draft and must not be treated as that project's current output. The project had been incorrectly kept in `completed/output` because any historical completed video was considered current. Its draft was seven-scene/vertical/LTX while the attached job was one-scene/square/image Flux. Video jobs are now bound to an explicit `workflow_revision`; old jobs cannot populate the current task, preview, project card, or completion status after script, storyboard, template, workflow or BGM changes. Browser verification now shows the F-16 project as `active / script / 0 scenes` and its output tab contains no current video.

A real reference-mode script retry was performed for project `0a9e4c2e-1983-4eb9-a433-98f66abac2b4` with job `379b61a9-4d40-41b4-a37b-cb60bd056ffc`. It executed two real web queries and retained two candidate sources. Evidence extraction still returned `reference_extraction_empty`, but the new fail-open policy continued through the configured real LLM and produced five narrations. The job completed with an explicit `reference_unavailable` status and warning; the UI and database show the new script without presenting it as source-verified.
