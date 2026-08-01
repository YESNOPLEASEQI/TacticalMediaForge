# Agent 工作流与任务状态终稿

结论：状态机可达、终态诚实、并发有界、总截止时间覆盖排队和运行，未发现未解决的 `CONFIRMED P0/P1`。

## 状态与持久化

- 状态路径固定为 `PENDING -> RUNNING -> COMPLETED | FAILED | CANCELLED`；`None`、空/损坏成品、provider 子步骤失败不能标记成功。
- 终态 SQLite 同步失败会把任务转为 `FAILED`，不再出现内存 completed、数据库 running 的静默分叉。
- 项目阶段只允许单调前进；旧任务不能回退新任务阶段。
- 启动协调只结算遗留 active job；旧任务状态、参数和可变 pipeline 字段不污染新任务。

## 并发、超时与幂等

- `TaskManager` 共享 semaphore 同时约束异步任务和 `/video/generate/sync`；总 deadline 在运行时初始化和排队前开始计时。
- 活跃重复请求使用稳定请求指纹复用任务；调用方传入参数深拷贝，后续修改不能改变已提交任务。
- 每次生成创建独立 pipeline；asset index、回调和每任务 `VideoService` 不跨请求共享。
- DashScope/Kling/Seedream/RunningHub/OpenAI 图片任务的非幂等付费提交不自动重发；只允许有界的查询/下载重试。

## 取消语义

- 协程 provider 调用被 shield，终态要等真实调用结束；阻塞 worker 会调用所属服务的 cancel hook，并在退出后发布取消终态。
- FFmpeg 由每任务 `VideoService` 跟踪 `Popen`，取消时 terminate，超时后 kill；不会提前声明取消完成而让本地合成继续。
- DashScope 活跃远端 task 会尝试 provider cancel endpoint；不提供取消 API 的 provider 只能等待其有限超时，晚到结果不能覆盖终态。

## 故障传播

- 并行场景中任一图片/视频失败会取消 sibling，不继续拼装部分成品。
- TTS、字幕、FFmpeg、磁盘写入、缓存 JSON、下载解码和最终 probe 的错误均显式传播。
- 非法、截断或类型错误的工具 JSON fail closed；没有空 catch、跳过断言或伪造成功。
- verified 分镜不再把自由文本模型提示直接送入媒体 provider；服务端从证据字段和通用安全创作字段确定性渲染最终 prompt，客户端只能确认与 snapshot 完全一致的版本。

残余 P2：少数第三方 provider 没有真正的远端取消能力，已经提交的云端工作可能继续计费到 provider 超时；本地状态和晚到结果仍保持一致。建议后续为各 provider 增加官方幂等键与可查询的 cancellation receipt。
