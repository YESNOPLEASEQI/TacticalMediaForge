# MilitaryVideoGen

MilitaryVideoGen 是一个面向军事科技科普内容的 AI 短视频生成项目。

项目通过大语言模型生成分镜解说和媒体提示词，结合图片或视频生成、TTS 配音、HTML 模板渲染与 FFmpeg 合成，输出完整短视频。后端使用 FastAPI，前端使用 React、TypeScript 和 Vite。

## 本地启动

在 Windows 环境中运行：

```bat
start_react_stack.bat
```

后端默认地址为 `http://127.0.0.1:8000`，前端默认地址为 `http://127.0.0.1:5173`。

## Python 包

项目的 Python 包名为 `military_video_gen`：

```python
from military_video_gen import military_video_gen
```

## 许可证

本项目采用 Apache License 2.0。
