# 阶段 0：初始化与安全基线

记录时间：2026-07-27（Asia/Shanghai）
工作目录在本报告中统一记为 `<WORKTREE>`，未记录任何凭据值或私人绝对路径。

## Git 基线

- 当前分支：`main`
- 基线提交：`8c13e253a1098cfa14b0c745bfd11126636ebe13`
- 最近提交：`Improve script feedback, subtitles, and repository security`
- Git 目录与 common dir 均为 `<WORKTREE>/.git`。因此当前目录是主 worktree，而不是 Git linked worktree；继续在现有工作目录内执行，不触碰其他仓库或分支。
- 工作树在审计开始前已有未提交变更。它们视为用户已有工作，后续不回滚、不覆盖，并在最终报告中与本次审计修改一并披露。

审计开始前已修改/删除的受跟踪文件：

```text
M frontend/components.json
M frontend/package-lock.json
M frontend/package.json
M frontend/src/components/app/AppShell.test.tsx
M frontend/src/components/app/AppShell.tsx
D frontend/src/components/react-bits/ElectricBorder.tsx
M frontend/src/features/history/GenerationCard.tsx
M frontend/src/features/history/SessionList.tsx
M frontend/src/features/projects/ProjectStageRail.tsx
M frontend/src/features/video/LaunchMissionButton.tsx
M frontend/src/features/video/WorkflowStepNav.test.tsx
M frontend/src/features/video/WorkflowStepNav.tsx
M frontend/src/index.css
M frontend/tailwind.config.ts
M start_react_stack.bat
M tests/scripts/test_start_react_stack.py
```

审计开始前未跟踪路径：

```text
.playwright-cli/
frontend/src/components/ElectricBorder.tsx
frontend/src/components/StarBorder.tsx
frontend/src/components/Stepper.tsx
scripts/stop_frontend.ps1
```

## 规模基线

- 全目录（包含 `.git`、虚拟环境、依赖、输出与缓存）：27,786 个文件，1,057,647,296 字节。
- 逻辑项目（排除 `.git`、虚拟环境、`node_modules`、构建/覆盖率/测试缓存、`output` 与 `temp`）：440 个文件，10,987,320 字节。
- 主要大目录：`.venv`、`output`、`frontend`、`temp`；其中输出、临时媒体、依赖缓存只作为清理候选分析，不在基线阶段修改。

## 环境与工具

| 项目 | 版本/状态 |
|---|---|
| 操作系统 | Windows 11 Home China 64-bit, 10.0.26200 |
| PowerShell | 5.1.26100.8875 |
| Python | 3.13.12（项目要求 >=3.11） |
| pip | 26.0.1 |
| uv | 0.11.18 |
| Node.js | v24.3.0 |
| npm | 11.4.2 |
| Git | 2.53.0.windows.1 |
| FFmpeg / ffprobe | 8.1.1，均可用 |
| Docker | 29.2.0 |
| Docker Compose | v5.0.2 |
| Yarn | 未安装（项目未声明需要 Yarn） |

## 项目配置与入口

- 未发现 `AGENTS.md`。
- 文档入口：`README.md`；声明 FastAPI 后端、React/TypeScript/Vite 前端和 Windows 启动脚本。
- Python 清单/锁：`pyproject.toml`、`uv.lock`；开发工具声明 pytest、pytest-asyncio、ruff。
- 前端清单/锁：`frontend/package.json`、`frontend/package-lock.json`；脚本包含 `build`、`typecheck`、`test`、`e2e`。
- 容器配置：`Dockerfile`、`docker-compose.yml`。
- CI：仅发现文档构建/发布工作流 `.github/workflows/docs.yml`；未发现应用测试 CI。
- 环境模板：根目录与前端各有 `.env.example`。
- 本地存在被 `.gitignore` 排除的 `.env`，只确认了存在性和大小，未读取内容、未测试其中任何凭据、未发现其被 Git 跟踪。
- 外部媒体工具：FFmpeg 与 ffprobe 均可执行。
- 默认禁止真实付费服务调用；除非明确存在 `ALLOW_LIVE_API_TESTS=1`，本次仅使用 Mock、Stub、固定响应和本地测试资源。

## 初始风险/约束

1. 当前并非声明中的隔离 linked worktree，且分支为 `main`；所有操作严格限制在 `<WORKTREE>`，不推送、不改写历史。
2. 工作树已有大量用户改动；所有后续编辑采取增量方式并避免覆盖这些内容。
3. `output/`、`temp/`、`data/` 含媒体和运行数据，可能是用户资产或运行状态；在清理分类完成前绝不删除。
4. 项目包含可触发 LLM、图片、视频、TTS、搜索和爬取的代码；现有检查必须在禁用真实外部调用的条件下运行。
