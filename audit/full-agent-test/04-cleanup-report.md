# 项目清理报告

结论：仅删除可再生缓存、测试/构建产物及已确认无引用的旧媒体中间件；没有删除源码、配置、锁文件、迁移、用户媒体、未知二进制文件或凭据文件。

## 清理结果

- 首次清理：456 个文件，136,324,740 bytes。包括 Python/工具缓存、前端测试/构建产物、审计 wheel/sdist，以及 105 个经 `output/`、`data/` 引用扫描确认无引用的 `padded_*` / `trimmed_*` FFmpeg 中间件。
- 后续 3 次精确清理：700 次文件删除操作，67,420,232 bytes，259 个唯一相对路径，0 个删除错误。逐文件路径、大小、SHA-256、Git 跟踪状态、原因、引用检查、风险和恢复方式见 `cleanup-manifest-final.json`。
- 累计：1,156 次删除操作，203,744,972 bytes（194.31 MiB）。缓存会被测试重建，因此“操作次数/累计字节”不等同于 1,156 个永久唯一文件。
- 精确清单分类：Python bytecode 618 次；工具缓存 61 次；前端构建 9 次；浏览器测试产物 3 次；包构建产物 6 次；TypeScript 缓存 3 次。

## 保护与恢复

`output/**`、`data/**`、`.env`、`.playwright-cli/**`、`temp/latest-video-diagnostic.jpg`、默认 BGM、模板、字体及所有 Git 跟踪资产均保留。清理后逐项确认 `.env`、`.playwright-cli/`、`output/`、`data/`、`temp/` 仍存在。

删除使用仓库内 allowlist、绝对路径 containment、Git 跟踪保护及删除前 SHA-256 二次校验。缓存/构建产物可通过报告中的测试和构建命令恢复；旧 FFmpeg 中间件只能通过重跑对应任务恢复。

## 证据限制

首次清理的 `cleanup-manifest-before.json` 只保存了分类级数量、字节数和组合 inventory hash，没有保存规范要求的逐文件路径与单文件 SHA-256。该历史证据缺口在后续阶段已通过 `scripts/audit_cleanup.py` 修正：`cleanup-manifest-final.json` 的 700 条记录均在各自删除前生成并校验。首次已删除的 456 个文件无法事后可靠重建逐文件清单，因此不伪造记录；这是本次审计唯一已知的过程合规缺口。
