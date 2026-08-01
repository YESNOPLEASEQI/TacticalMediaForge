# 媒体流水线终稿

结论：最终文件存在、非空、可解码且包含所需音视频流后才会成功；真实本地 FFmpeg 合成与损坏文件拒绝测试均通过。

## 已修复

- 下载校验 content type、最大大小、非空和图片解码/视频 probe，HTML 错误页不能冒充媒体。
- 独立图片接口在成功前执行 Pillow decode；独立 TTS 接口和 `TTSService` 在成功前执行真实 ffprobe 音频流与有限正时长校验，不再用估算时长掩盖损坏音频。损坏产物会在批准根目录内删除。
- Comfy workflow 对外只返回项目相对路径，内部执行使用不序列化的 `_internal_path`，兼顾自托管兼容和路径隐私。
- TTS 时长驱动视频目标时长；短视频冻结尾帧补齐，长视频/音频按显式策略处理。
- 字幕拆成连续 cue，覆盖完整音频区间且不超出镜头；多字幕卡按时间叠加。
- 单 scene + BGM 不再被快速返回绕过；BGM 只在最终拼接阶段混入一次。
- overlay/trim/pad/filelist 使用唯一临时名并在成功、异常、取消路径清理。
- 所有 FFmpeg 调用使用参数列表而非 shell 拼接；进程被每任务服务实例跟踪并可终止。
- standard/custom 最终输出都经 ffprobe 校验视频流、音频流、有限正 duration；结果时长以最终 probe 为准。
- Windows 中文和空格路径、过长文件名、缺失 FFmpeg、非零退出码、磁盘/权限错误均有故障注入。

## 最终证据

- `tests/services/test_video_integrity.py`: 单 scene BGM、真实 FFmpeg 音视频文件、损坏 MP4。
- `tests/audit/test_mandatory_scenario_gaps.py`: 部分生成失败、TTS/字幕失败、FFmpeg 缺失/非零、不可写/磁盘满、旁白超长、并发临时名。
- 直接 `ffprobe` 默认 BGM：MP3，可读，157.946750 秒，2,529,519 bytes。

残余 P2：不同 provider 返回的片段并非全部先重编码到统一 FPS/time-base；当前最终 probe 能阻止损坏成品，但极端异构片段仍可能在 stream-copy concat 中失败。字幕为确定性比例 cue，不是所有 TTS provider 的逐词 forced alignment。
