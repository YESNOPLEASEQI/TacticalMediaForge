# API 浣跨敤

MilitaryVideoGen 鎻愪緵瀹屾暣鐨?Python API锛屾柟渚块泦鎴愬埌浣犵殑椤圭洰涓€?

---

## 蹇€熷紑濮?

```python
from military_video_gen.service import MilitaryVideoGenCore
import asyncio

async def main():
    # 鍒濆鍖?
    military_video_gen = MilitaryVideoGenCore()
    await military_video_gen.initialize()
    
    # 鐢熸垚瑙嗛
    result = await military_video_gen.generate_video(
        text="涓轰粈涔堣鍏绘垚闃呰涔犳儻",
        mode="generate",
        n_scenes=5
    )
    
    print(f"瑙嗛宸茬敓鎴? {result.video_path}")

# 杩愯
asyncio.run(main())
```

---

## API 鍙傝€?

璇︾粏 API 鏂囨。璇锋煡鐪?[API 姒傝](../reference/api-overview.md)銆?

---

## 绀轰緥

鏇村浣跨敤绀轰緥璇峰弬鑰冮」鐩殑 `examples/` 鐩綍銆?

