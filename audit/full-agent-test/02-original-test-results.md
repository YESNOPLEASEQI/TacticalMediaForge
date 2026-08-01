# 阶段 2：原始检查结果

所有结果均在生产代码修改前采集。真实 LLM、图片、视频、TTS、云存储和发布 API 均未调用。

## 汇总

| 检查 | 命令 | 退出码 | 结果 | 分类 |
|---|---|---:|---|---|
| Python 锁文件 | `uv lock --check` | 0 | 140 包可解析 | 通过 |
| Python 安装一致性 | `uv sync --frozen --extra dev` | 0 | 135 包已检查 | 通过 |
| Python 依赖兼容 | `uv pip check --python .venv/Scripts/python.exe` | 0 | 无不兼容依赖 | 通过 |
| Python 编译 | `uv run python -m compileall -q ...` | 0 | 无语法/字节码错误 | 通过 |
| Python 单元/集成测试 | `uv run python -m pytest -q` | 0 | 168/168 通过，12 个 Pydantic 弃用警告 | 通过，有维护风险 |
| Python lint | `uv run ruff check .` | 1 | 122 个问题；104 个可安全自动修复 | 代码问题 |
| Python 格式 | `uv run ruff format --check .` | 1 | 117 个文件格式不符合 | 代码/基线问题 |
| Python 构建 | `uv build --out-dir audit/full-agent-test/logs/build-artifacts` | 0 | sdist 与 wheel 成功 | 通过，但 sdist 19 MB 需审查 |
| Python 类型检查 | 可用性探测 | 不适用 | mypy/pyright 未安装且项目未配置 | 工具/文档缺口 |
| Python安全/依赖公告 | 可用性探测 | 不适用 | bandit、pip-audit 未安装 | 工具/CI 缺口 |
| 未使用代码 | Ruff F401/F841 | 1 | 30 项未使用 import/变量 | 代码问题 |
| 循环依赖 | 可用性探测 | 不适用 | 未配置专用分析器 | 工具缺口 |
| 前端安装检查 | `npm ci --dry-run --ignore-scripts` | 0 | lock 与安装树一致 | 通过 |
| 前端依赖树 | `npm ls --depth=0` | 0 | 顶层依赖完整 | 通过 |
| 前端类型检查 | `npm run typecheck` | 0 | TypeScript 通过 | 通过 |
| 前端单测 | `npm test -- --run` | 0 | 71/71 通过，18 个文件 | 通过 |
| 前端构建 | `npm run build` | 0 | Vite 构建成功 | 通过，有 805 kB chunk 警告 |
| 前端依赖审计 | `npm audit --audit-level=high` | 1 | PostCSS 1 个 high 公告，可升级修复 | 依赖问题 |
| Mock E2E | `npm run e2e` | 1 | 1/1 失败：找不到“联网核验”按钮 | 代码/测试契约问题 |
| Docker 配置 | `docker compose config --quiet` | 0 | Compose 配置有效 | 通过 |
| API 导入烟测 | 导入 `api.app` 并读取路由 | 0 | 50 条路由，导入成功 | 通过 |
| 媒体探测 | `ffprobe ... bgm/default.mp3` | 0 | MP3 可读，157.94675 秒 | 通过 |
| 凭据模式扫描 | `rg -l`（只输出文件名） | 0 | 仅文档/启动脚本命中；未发现被跟踪的 `.env`/私钥文件 | 需人工静态复核 |

## 失败分析

### Ruff lint（代码问题）

统计：61 个 import 顺序、25 个未使用 import、16 个无插值 f-string、12 个非文件顶部 import、5 个未使用变量、2 个重复定义、1 个 bare except。这里同时包含长期格式债务和少量可影响异常诊断的真实问题。不会为通过测试而全库无差别改写；专项审计后只修复低风险、明确问题。

### Ruff format（基线问题）

117 个文件会被重新格式化。全量格式化会放大 diff 并覆盖用户正在进行的修改，因此本次只格式化实际编辑/新增文件，并把全库格式债务保留为 P3。

### Mock E2E（代码/测试契约问题）

Playwright 打开项目生成页后，按可访问名称 `/联网核验/` 查找模式按钮失败。Vitest 仍全部通过，说明当前 E2E 与近期 UI 改动之间存在契约漂移，或页面初始化错误使目标控件未渲染。失败包含截图和 trace，已由 Playwright 保存在被忽略的 `frontend/test-results/`，将在回归测试前定位并修复。

### npm audit（依赖问题）

安装树中的 PostCSS 8.5.16 命中 source map 自动加载路径穿越/任意 `.map` 文件披露公告。`npm audit` 表明可直接修复；后续将升级锁文件并复测前端。

### 工具缺口（环境/CI 问题）

项目未声明 Python 类型检查、安全公告扫描、覆盖率、未使用代码和循环依赖的专用工具。不会在报告中伪称这些检查通过；专项静态审计、Ruff 和确定性测试用于补足核心风险，最终报告保留 CI 加固建议。

## 脱敏说明

- 测试警告和应用导入日志中的绝对工作目录未复制到报告。
- `.env` 只检查存在性与 Git 跟踪状态，未读取、未验证任何值。
- 原始命令输出的压缩摘要存放于 `logs/`；Playwright 失败产物属于可再生测试输出，后续纳入清理清单。
