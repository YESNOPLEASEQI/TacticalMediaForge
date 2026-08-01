# 修复日志

## 修复循环 1：安全边界与输入契约

- 为任务目录、资源目录、标题输出名增加规范化、单组件和根目录包含校验；所有历史读写/删除均复用同一入口。
- 增加中英文的确定性高危军事操作请求门禁，并保留历史、博物馆、公开资料比较和武装冲突法教育等正常用途。
- 对文本、列表、scene index、字数区间和项目相对资源路径使用严格 schema；拒绝空白、string-as-list、重复 index 和范围倒置。
- HTML 渲染器转义文本与属性，限制本地文件根目录，拦截危险远程请求，并串行化共享浏览器初始化。
- 去除包含完整服务配置对象的日志，避免 API key 被插值输出。

定向回归：S01-S34、S50-S52 与 5 项 hardening regression 全部通过。

## 修复循环 2：任务、研究事实性与媒体完整性

- TaskManager 实施深拷贝、活跃相同请求幂等复用、最大并发、总 deadline、`None` 结果失败和终态数据库同步失败回滚。
- DashScope 付费视频提交改为只提交一次；轮询/下载仍允许重试。
- 每个请求新建 pipeline 实例；FFmpeg 合成移入工作线程，使事件循环可及时处理 timeout/cancel。
- 研究 verified gate 改为服务端所有权校验：完成态研究、revision/hash、来源、claim provenance 与 scene 映射必须一致；置信度阈值真实生效。
- stale research retry 支持携带完整替代请求，同时保留父任务链和 revision；前端关键流程 E2E 覆盖该行为。
- 下载媒体校验 content-type、非空、可解码/可 probe；最终视频必须有视频流、音频流、有限正 duration。
- 单 scene + BGM 不再走丢失 BGM 的早返回；临时 overlay/trim/pad 文件在成功和失败路径清理。
- 项目阶段只允许单调前进，旧任务不能把新阶段回退。

定向回归：S35-S57、真实 FFmpeg 合成、研究 API、数据库阶段和浏览器 stale-retry 全部通过。

## 修复循环 3：全量静态与兼容性收口

- Ruff 自动修复未使用 import、无效 f-string 和导入顺序，并人工修复剩余未定义/未使用变量；`ruff check .` 从 122 项降为 0。
- PostCSS 升级到无已知高危审计项的锁定版本；`npm audit --audit-level=high` 为 0 vulnerabilities。
- 更新已失效的 Playwright 断言为当前可访问语义和真实 research retry contract。
- 最终运行 Python、前端单测、类型检查、构建、Chromium E2E、锁文件、依赖兼容、wheel/sdist、Compose、API 路由与 FFprobe 冒烟。

没有调用公网或付费模型 API；故障注入全部使用本地临时目录、mock provider contract 或本地 FFmpeg。

## 修复循环 4：独立复审阻断项

- Crawl4AI 禁止 crawler 内重定向；公开 API 路径统一脱敏；独立图片/TTS 产物执行真实 decode/probe。
- 增加中英文安全换序、随机博客单源、verified 生产链负向回归。
- 两次复审揭示并修复 provenance 形式化与实际 prompt 脱节：最终 verified prompt 只由服务端分类字段确定性生成，模型恶意自由文本不会进入媒体流水线。
- 最终 Python 315/315、前端 71/71、Chromium 1/1、Ruff/类型/构建/依赖/媒体检查通过。
