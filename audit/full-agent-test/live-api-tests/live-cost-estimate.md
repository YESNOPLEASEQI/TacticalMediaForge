# 本轮真实调用成本估算

## 估算结论

预计可计费 API 成本约 **US$0.05–0.30**。这是保守区间，不含本机 L40/GPU、电力、Docker、浏览器和 FFmpeg 的设备成本；服务商账单控制台是最终依据。

| 服务 | 本轮用量性质 | 预计可计费成本 |
|---|---|---:|
| DeepSeek `deepseek-v4-pro` | 真实查询规划、证据抽取、事实校验、分镜；修复过程中有少量失败后重试 | US$0.05–0.30 |
| SearXNG | 本地容器，真实联网查询 | 无按次 API 费用 |
| Crawl4AI | 本地容器，真实联网抓取 | 无按次 API 费用 |
| ComfyUI | 本机 NVIDIA L40，1 张真实生成图 | 无外部 API 账单；本机算力未计量 |
| Edge TTS | 1 次联网语音合成，未配置计费 API 密钥 | 未观察到直接账单费用 |
| FFmpeg / HTML 字幕 | 本地处理 | 无外部 API 费用 |

## 计算依据与限制

DeepSeek 官方当前价格页列出 `deepseek-v4-pro`：缓存未命中输入 US$0.435 / 百万 token、输出 US$0.87 / 百万 token（缓存命中输入更低）。官方价格页：<https://api-docs.deepseek.com/quick_start/pricing>。

项目当前没有持久化每次 DeepSeek 响应的 `usage` 字段，因此无法给出精确 token 总数。上述区间按本轮少量结构化调用及排障重试作保守估算；没有把 Mock 流量计入，也没有产生 OpenAI、DashScope、Ark、Kling、Gemini 或 RunningHub 费用。

## Rerun note (2026-07-28 16:55)

The fresh video rerun reused the one already-generated ComfyUI image hash while still executing the real ComfyUI retrieval path, fresh Edge TTS, subtitle rendering and FFmpeg composition. Minimal DeepSeek probes returned HTTP 402 before generating billable output. No exact additional charge can be derived from provider usage data; no new high-cost candidate generation was performed.

The 18:26 reference-script regression performed two web queries, reference extraction, and one fallback narration-generation request. Exact token usage was not persisted; this adds only a small LLM charge within the existing conservative estimate and no image/video-generation charge.
