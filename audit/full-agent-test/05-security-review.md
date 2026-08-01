# 安全审计终稿

结论：未发现仍未解决的 `CONFIRMED P0/P1`。本次没有读取 `.env` 内容、验证密钥、调用真实付费 API、上传媒体或写入线上系统。

## 已确认并修复

- 路径安全：任务 ID、资源路径、输出文件名、上传/引用音频均执行规范化和根目录包含校验；遍历、绝对路径、UNC、恶意文件名和越界删除被拒绝。
- 密钥绑定：`api/routers/llm.py::resolve_api_key_for_base` 只允许在标准化后的同一 provider Base URL 复用已保存密钥；换地址必须显式提交新密钥，阻断 Bearer key 外带。
- 引用音频：TTS/视频 schema 只接受 `temp/`、`output/`、`data/audio/` 下的音频后缀，不能借 `ref_audio` 读取 `.env`、配置或任意本地文件。
- 日志与错误：配置对象、provider 原始响应、TTS 全量 outputs、签名 URL 查询参数、私网 URL、用户文本、session ID、本地绝对路径均改为省略、计数或统一脱敏；公共 5xx 返回通用错误，任务错误状态保存脱敏文本。
- LLM/媒体边界：所有公开文本 schema 设 20,000 字符上限并执行军事实害/提示注入门禁；模型生成的标题、旁白、画面提示在进入 TTS/图片/视频 provider 前再次校验。
- HTML 渲染：文本和属性转义，本地资源限制在批准根目录，拦截危险远程/私网请求，并串行化共享浏览器初始化。
- 研究 URL：限制 scheme、凭据、私网地址，DNS 与最终重定向地址都重新校验，抵御 SSRF/DNS rebinding。
- Crawl4AI 边界强制 `max_redirects=0`，避免外部 URL 在 crawler 容器内先重定向到私网；抓取结果仍执行最终 URL 校验。
- 公开响应统一把内部路径转换为 allowlist 项目相对路径或 `/api/files/...` URL；workflow、history、jobs、tasks、image、TTS、frame 均不再暴露用户目录或绝对路径。
- 安全门增加中英文材料/用量/爆炸装置、精确坐标/轰炸、临时手机/警方追踪、现实基地打击等换序表达，8 个独立审查绕过样本全部 fail closed。
- 依赖：前端 PostCSS 公告已通过锁文件升级消除；最终 `npm audit --audit-level=high` 为 0 vulnerabilities。

## 验证证据

- `tests/audit/test_hardening_regressions.py` 覆盖跨 provider 密钥外带、签名 URL/绝对路径脱敏、TTS 文件外带、配置/结果日志、模型输出门禁和公共错误。
- 同一回归文件覆盖公开路径序列化、损坏媒体删除和独立审查提出的中英文安全绕过；`tests/research/test_crawl4ai.py` 覆盖重定向关闭。
- `tests/audit/test_full_agent_scenarios.py` 与 `test_mandatory_scenario_gaps.py` 覆盖路径穿越、恶意 URL/文件名、用户/网页提示注入、超长输入和安全放行用例。
- 静态扫描未发现被 Git 跟踪的 `.env` 或已知凭据文件；报告仅记录文件类型/位置，不包含凭据值。

## 非阻断残余风险

- 没有安装 Python 的 `pip-audit`/Bandit，因此不能声称完成了对应公告数据库和 SAST 工具扫描；已完成锁文件一致性、`uv pip check`、Ruff 与人工静态审查。
- 未使用真实 provider，无法证明第三方 SDK 自身在所有异常模式下都不输出敏感日志；项目自身日志边界和已知 provider 响应路径已脱敏。
- 应用默认面向本机使用；部署到不受信网络前仍应增加认证、授权、速率限制和反向代理层保护。
