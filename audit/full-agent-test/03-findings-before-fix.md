# 修复前问题清单

冻结时间：2026-07-27（生产代码修改前）。判定规则：`CONFIRMED` 需有可复现失败或明确控制流/数据流证据；`HIGHLY_LIKELY` 需有直接实现证据但缺少端到端复现；其余不进入自动修复范围。

## P0

| ID | 状态 | 问题 | 证据/复现 | 计划 |
|---|---|---|---|---|
| SEC-001 | CONFIRMED | history 删除接受任意 `session_id`，`output/session_id` 可经 `..` 或绝对路径逃逸后递归删除。 | 审计场景 S01-S06 全部失败；`PersistenceService.delete_task -> shutil.rmtree`。 | 严格任务 ID + resolve containment；所有读写删入口共用。 |
| SAFE-001 | CONFIRMED | 没有统一的军事伤害操作性内容门禁；确认脚本可直达 TTS、媒体和字幕。 | 审计场景 S12-S19；API schema 与 pipeline 边界均无 fail-closed 检查。 | 输入与 pipeline 双重确定性门禁，保留历史/新闻/教育用途。 |
| SEC-002 | CONFIRMED | 服务初始化 debug 日志可序列化包含真实 API key 的配置。 | `services/service.py`、`services/comfy_base_service.py` 直接记录 config。 | 删除整对象日志，仅记录无敏感字段的运行模式。 |

## P1

| ID | 状态 | 问题 | 证据/复现 | 计划 |
|---|---|---|---|---|
| SEC-003 | CONFIRMED | HTML 模板文本未转义，图片 URL/本地路径无充分约束，可形成 HTML 注入、SSRF 或本地文件读取。 | `_replace_parameters` 直接 `str(value)`；浏览器使用 `--no-sandbox`。 | 按类型转义；本地文件限定允许根；远程 URL 安全检查与请求拦截。 |
| FACT-001 | CONFIRMED | `verified` 门禁是 no-op，客户端可伪造 provenance/status/job id。 | S53 失败；`research/gate.py` 丢弃参数。 | 只信服务端 project/job/snapshot，并核对 revision/hash/scene/claim。 |
| FACT-002 | CONFIRMED | Claim/VisualFact 的配置阈值未执行；低置信单源事实可进入画面。 | S35-S39 失败；两个类的注释明确“never blocks”。 | 按阈值标记 verified/low/unsupported，视觉事实低于阈值拒绝。 |
| TASK-001 | CONFIRMED | `max_concurrent_tasks` 未使用且无总截止时间，任务可无限 RUNNING。 | S41-S42 失败。 | 每 manager 的 semaphore + `asyncio.timeout`。 |
| TASK-002 | CONFIRMED | coroutine 返回 `None`/空结果仍会标记 COMPLETED。 | S40 失败；manager 无结果契约。 | 拒绝 None；视频包装器再验证路径、大小和 probe。 |
| TASK-003 | CONFIRMED | DashScope 非幂等 `VideoSynthesis.call` 被网络重试包裹，可能重复创建付费任务。 | `video_dashscope.py` 多个 submit 点使用最多 5 次重试。 | 提交只尝试一次；仅查询/下载重试。 |
| TASK-004 | CONFIRMED | 单例 AssetBasedPipeline 在并发任务间共享 `asset_index` 与进度回调。 | `asset_based.py` 可变实例字段；core 缓存 pipeline 实例。 | 每任务新建 pipeline 或把状态移入 context。 |
| MEDIA-001 | CONFIRMED | 单场景静默丢 BGM。 | `video.py:130` 提前 return。 | 单场景进入 BGM 分支。 |
| MEDIA-002 | CONFIRMED | 空/损坏成品可误报成功。 | S45-S49 以及 finalize 仅 stat。 | 统一媒体完整性校验。 |
| MEDIA-003 | CONFIRMED | HTML/空/损坏下载响应可作为媒体写盘。 | S50 与 `frame_processor.py` 下载路径。 | Content-Type/大小/解码检查。 |
| SCHEMA-001 | CONFIRMED | 空白文本、空列表、min>max、重复 scene index 等矛盾输入未统一拒绝。 | S25-S34 中 8 个失败。 | Pydantic strict list/item/model validators。 |
| DB-001 | CONFIRMED | 终态数据库同步异常被吞掉，内存 completed 与 DB running 可分叉。 | `_sync_runtime_job` 捕获所有异常仅日志。 | 终态同步失败使任务失败并保留可诊断错误。 |
| STAGE-001 | CONFIRMED | 较旧并发任务可把 `project.current_stage` 倒退。 | `database/runtime_jobs.py` 直接写阶段。 | 基于显式阶段序的单调更新。 |

## P2/P3

- MEDIA-004/005/006：时长权威值、流规格统一、异常临时文件清理。
- MEDIA-007（HIGHLY_LIKELY）：比例字幕不是发音对齐；本轮明确为降级策略，不声称达到 forced alignment。
- RESEARCH-001：research DB 创建失败会留下内存 ghost task；启动恢复目前只把中断任务标失败。
- PLAY-001：共享 Playwright browser 初始化无锁，跨 event loop 字段名不一致。
- DEP-001：`postcss <= 8.5.17` 高危公告，`npm audit` 失败。
- E2E-001：浏览器测试仍断言旧文案“联网核验”，与当前“联网参考”不一致。
- QUALITY-001：Ruff 基线 122 项、117 个文件格式差异；避免无关大规模格式化，只处理触碰文件。

## 修复前故障注入结果

命令：`.venv/Scripts/python.exe -m pytest -q tests/audit/test_full_agent_scenarios.py`

结果：54 场景，51 failed、3 passed，另有 1 teardown error（测试试图临时设置尚不存在的 `task_timeout_seconds` 字段；测试夹具将在实现前改为构造参数注入）。该错误不改变 TASK-001 的生产问题判定。
