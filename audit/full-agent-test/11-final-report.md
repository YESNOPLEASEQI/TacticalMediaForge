# 军事视频生成 Agent 全量无人值守审计最终报告

完成时间：2026-07-28（Asia/Shanghai）
基线提交：`8c13e253a1098cfa14b0c745bfd11126636ebe13`
审计分支：`audit/full-agent-unattended-20260727`
实现提交：`b1a28719266e21f8c713d6ea5fdebd5062423aaa`

## 最终结论

项目在本地、离线、Mock/Stub 条件下可安装、导入、构建和运行完整测试链。Python 315/315、前端 71/71、Chromium E2E 1/1 全部通过；Ruff、Python 编译、TypeScript、Vite、npm 高危依赖审计、Python 依赖一致性、wheel/sdist、Docker Compose、API 50 路由导入以及默认 BGM FFprobe 均通过。审计未调用公网、付费模型、图片、视频、TTS、搜索或发布服务。

共确认 31 个缺陷：P0 4 个、P1 19 个、P2 7 个、P3 1 个。最终完全修复 28 个，部分修复 2 个，保留 1 个非阻断缺陷；当前已知未解决的 confirmed P0/P1 为 0。57/57 个强制编号故障场景通过。

## 原始状态与边界

- 原始 Python 测试 168/168 通过，但 Ruff 有 122 项、前端 E2E 1/1 失败、npm audit 有 1 个 high 公告。
- 初始目录实际是主 worktree，而不是任务描述所称的 linked worktree；审计在原目录创建专用分支继续执行，没有改写历史、推送或访问其他仓库。
- 审计开始前已有 16 个受跟踪文件改动和 5 个未跟踪路径，主要是前端 UI/启动脚本工作。为保留用户工作，它们没有被回滚，并随专用分支实现提交一并保存；详细基线见 `00-baseline.md`。
- `.env` 仅确认存在和未被 Git 跟踪，从未读取内容或测试凭据；真实 provider 行为不在本次离线验收范围内。

## 修复结果

- 安全：统一任务、资源、输出及引用音频路径 containment；阻断 HTML 注入、SSRF/重定向、敏感配置日志、私有绝对路径泄漏和中英文现实伤害提示换序绕过。
- Agent/任务：严格 schema；总 deadline、并发上限、幂等、请求状态隔离、单次付费提交、终态持久化、单调阶段和取消后迟到结果保护。
- 事实性：服务端持有 verified research snapshot；来源质量、时效、claim/visual ID 和字段级 provenance 校验；最终媒体提示由服务端确定性渲染，未经来源支持的发动机、核挂载、国籍标志和具名基地细节被丢弃。
- 媒体：图片/音频/视频真实解码与 ffprobe 合同；损坏产物删除；单场景 BGM、时长、音轨、临时文件唯一性与清理修复。
- 工程：PostCSS 高危公告清零，Ruff 122 项降至 0，陈旧 E2E 契约修复，新增精确清理工具与审计证据。

逐项结论与证据见 `bugs-final.json`、`04-fix-log.md`、`05-security-review.md`、`06-agent-logic-review.md`、`07-military-factuality-review.md` 和 `08-media-pipeline-review.md`。

## 测试与覆盖变化

| 项目 | 原始 | 最终 |
|---|---:|---:|
| Python pytest | 168/168 | 315/315（23.61s，12 个 Pydantic 弃用警告） |
| 新增 pytest case | — | 147（+87.5%） |
| 强制故障场景 | 未覆盖 | 57/57 |
| 前端 Vitest | 71/71 | 71/71 |
| Playwright Chromium | 0/1 | 1/1 |
| Ruff | 122 项 | 0 |
| npm high audit | 1 | 0 |

项目没有配置统一 line/branch coverage 工具，因此不虚构覆盖率百分比；可执行 case 数和场景矩阵是本次可复现的覆盖增量，详见 `09-test-coverage.md`。

## 清理与保留

- 首次清理：456 个可再生缓存、构建/测试产物及已确认无引用的旧媒体中间文件，136,324,740 bytes。
- 后续 3 次精确清理：700 次删除操作、259 个唯一相对路径、67,420,232 bytes、0 错误；每条均在删除前记录并复核路径、大小、SHA-256、Git 状态、分类、原因、引用、风险、恢复方式和 containment。
- 累计：1,156 次删除操作、203,744,972 bytes（194.31 MiB）。测试反复重建缓存，所以该操作数不等于永久唯一文件数。
- 首次清理清单只保留分类计数、字节数和组合 inventory hash，缺少逐文件路径/SHA-256，无法事后可靠重建。本报告不伪造证据；这是唯一已知的过程合规缺口。后续已由 `scripts/audit_cleanup.py` 和逐文件 `cleanup-manifest-final.json` 修正。
- 明确保留：`.playwright-cli/**`（用户已有未跟踪资产）、`.env`、`output/**`、`data/**`、`temp/latest-video-diagnostic.jpg`、默认 BGM、字体、模板、迁移及所有不确定二进制文件。

唯一受 Git 跟踪的删除是 `frontend/src/components/react-bits/ElectricBorder.tsx`，它属于审计前已有的组件移动/替代，并非审计清理建议。完整代码变更清单见 `changed-files.txt`（含本报告共 160 个路径），受跟踪删除清单见 `deleted-files.txt`；清理删除逐项记录见两个 cleanup manifest。

## 独立复审

独立只读子 Agent 完成初审及允许的最多 2 轮追加复审，发现并推动修复 7 类高风险问题。第二轮正式结论仍因 verified `media_prompt` 可夹带无来源细节而为 BLOCK（0 P0、1 P1）；达到复审轮次上限后未伪造第三轮通过。主 Agent 随后删除自由文本通路，改为服务端字段分类和确定性 prompt 渲染，并完成恶意负向回归 9/9 与最终 Python 315/315。当前可复现证据显示 known confirmed P0/P1 为 0，但最后补丁未获第三轮独立 Agent 签字。详见 `10-independent-review.md`。

## 未解决风险与未完成项

- P2：不同 provider 片段并非在所有路径统一重编码为同一 FPS/time-base；最终产物合同会拒绝不可用媒体。
- P2：所有 provider 都没有字级 TTS 时间戳；现有 timed cues 只能改善而不能保证字级对齐。
- P2：Python 无法强制终止已经在 SDK worker thread 内执行的第三方调用；状态机会锁定取消/超时终态并忽略迟到结果。
- P3：Vite 仍提示一个 805.10 kB minified chunk；Python 测试仍有 12 个 Pydantic v2 弃用警告；全库格式未设为发布门禁。
- 真实付费 provider 的取消确认、限流、长轮询和媒体编码差异未测试，原因是任务明确禁止真实 API/费用调用。
- 项目未配置 Python 类型检查、安全公告扫描及 line/branch coverage 门禁；建议后续在 CI 中加入 pyright/mypy、pip-audit/bandit 和 pytest-cov。

## 实际命令、文件与 Git

脱敏后的实际执行命令全集按阶段记录在 `command-history.txt`，涵盖 Git/环境基线、依赖、静态检查、全量与定向测试、构建、E2E、媒体探测、安全扫描、清理、独立复审回归及最终验收。原始/最终输出摘要在 `logs/`。完整变更和删除列表分别在 `changed-files.txt`、`deleted-files.txt`。

一次性重跑全部最终验证的 PowerShell 单条命令（不触发公网或付费 API）：

```powershell
cmd /d /c "uv lock --check && uv pip check --python .venv\Scripts\python.exe && uv run ruff check . && uv run python -m compileall -q api military_video_gen tests scripts && uv run pytest -q && cd frontend && npm test -- --run && npm run typecheck && npm run build && npm audit --audit-level=high && npm run e2e"
```

实现已本地提交为 `b1a28719266e21f8c713d6ea5fdebd5062423aaa`（`Complete unattended audit and hardening`）。最终报告已作为后续文档提交追加到同一审计分支；没有推送远端。

## 建议下一步

1. 在隔离的 provider 沙箱中运行显式 opt-in live contract 测试，验证取消、限流、轮询和编码统一化。
2. 将本报告中的单条验证命令迁入应用 CI，并增加 coverage、类型与 Python 依赖安全门禁。
3. 分批修复 Pydantic 弃用项和前端 chunk 拆分；若要求逐字字幕，再为各 TTS provider 增加时间戳适配层。
