# 独立只读复审

审查者：未参与生产修改的 `final_independent_review` 子 Agent；审查期间只读，不修改文件。共执行初审及最多 2 轮追加复审。

## 初审与第一轮

独立审查确认 7 类阻断项：Crawl4AI 重定向 SSRF、公开绝对路径泄漏、独立图片/音频损坏产物误报成功、中英文安全门换序绕过、`OTHER` 单源评分跨阈值、生产 verified provenance 不可达。修复后第一轮最小离线套件 64/64 通过，前 6 类确认关闭；审查继续阻断“把任意 claim 批量复制到五个字段”的语义 provenance 伪造。

## 第二轮（最终允许轮次）

批量复制被移除后，审查确认字段/Gate 防篡改有效，但发现模型自由文本 `media_prompt` 与分类字段脱节：恶意未来源军事细节仍能随 snapshot 通过 Gate。第二轮正式结论为 `BLOCK`：0 P0、1 P1；选定回归 35 项通过，`git diff --check` 通过。

## 第二轮之后的修复与主 Agent 验证

按复审上限未启动第三轮独立 Agent。主 Agent 修复最后 P1：

- 无语义重叠 claim 不再作为通用证据附着；
- verified 模型自由文本被完全丢弃；
- subject 从已验证 claim 的 subject 构造，其余字段是明确的 `creative + generic_safe`；
- `prompt_renderer.render_prompt()` 成为实际 `media_prompt` 来源；
- 无来源的发动机、核挂载、国籍标志和具名基地负向样本全部从最终 prompt 消失；
- Gate 要求每场至少一个非空证据字段，创作字段必须非空、无 evidence ID 且由服务端标为 generic-safe。

修复后主 Agent 运行针对性回归 9/9、最终 Python 315/315、Ruff 0。独立审查者没有检查这最后一次补丁，因此报告不伪造“独立最终通过”；基于可复现负向回归和全量测试，当前已知未解决 CONFIRMED P0/P1 为 0。

删除审查：只删除 allowlist 可再生文件；源码删除仅有前端组件移动/替代，属于审计前已有用户改动，未由独立 Agent 建议删除。`.playwright-cli/`、用户媒体和不确定文件均保留。
