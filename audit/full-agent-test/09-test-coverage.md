# 审计测试覆盖矩阵

固定种子/离线原则：测试不访问公网、不调用付费 API；并发场景仅用本地 `asyncio`；媒体场景使用合成 probe、损坏文件或本机 FFmpeg；路径场景使用 pytest 临时目录。

| 场景 | 覆盖 | 最终结果 |
|---|---|---|
| S01-S06 | POSIX、Windows、绝对路径、空值和嵌套任务 ID 穿越 | 6/6 PASS |
| S07-S11 | 模板、工作流、BGM 资源路径穿越 | 5/5 PASS |
| S12-S19 | 中英文现实攻击计划、目标选择、武器/爆炸物操作与规避检测门禁 | 8/8 PASS |
| S20-S24 | 历史、博物馆、公开外形比较、法律教育允许用例 | 5/5 PASS |
| S25-S34 | 空白输入、string-as-list、空列表、min/max 倒置、空 scene、重复 index | 10/10 PASS |
| S35-S39 | verified/low/unsupported、缺来源和视觉事实最低置信度 | 5/5 PASS |
| S40-S44 | None 结果、总 deadline、最大并发、幂等复用、参数隔离 | 5/5 PASS |
| S45-S50 | 缺 probe/stream、非法 duration、无音频、HTML 错误页伪装媒体 | 6/6 PASS |
| S51-S54 | 输出名穿越、verified 服务端研究上下文、unverified 兼容 | 4/4 PASS |
| S55-S57 | 单场景 BGM、真实 FFmpeg 最终契约、非空损坏 MP4 | 3/3 PASS |

共 57/57 个编号故障场景通过。另有 hardening、数据库、研究、媒体和 API 契约回归，覆盖 HTML 转义、非幂等提交一次、敏感配置日志、终态 DB 同步、pipeline 隔离、Crawl4AI 零重定向、公开路径脱敏、损坏图片/音频删除、中英安全换序、低质量单源和 verified prompt 语义约束。

最终全量覆盖：Python 315/315；前端 Vitest 71/71；Playwright Chromium 1/1；Ruff 0；TypeScript、Vite、wheel/sdist、Compose、API 50 路由、默认 BGM FFprobe 均通过。相对原始 Python 168 项，增加 147 个可执行 pytest case（+87.5%）。项目未配置统一行覆盖率门禁，因此不虚构 line/branch coverage 百分比。

最终恶意 verified prompt 回归使用生产 `VisualPlanner -> ResearchService -> ResearchSnapshot -> gate` 路径：模型返回无来源发动机、核挂载、国籍标志和前线基地细节，服务端确定性 prompt 不包含任一恶意片段，且无语义重叠 claim 不会附着到场景。

已知非阻塞覆盖缺口：没有真实付费 provider 的沙箱凭据，因此无法验证其服务端取消确认和长时间限流行为；本地 contract 已确保取消后的迟到结果不能改写终态，并确保付费提交不自动重发。
