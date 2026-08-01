# API 姒傝

MilitaryVideoGen 鎻愪緵 Python SDK 鍜?HTTP REST API 涓ょ鏂瑰紡銆?

---

## Python SDK

### MilitaryVideoGenCore

涓昏鏈嶅姟绫伙紝鎻愪緵瑙嗛鐢熸垚鍔熻兘銆?

```python
from military_video_gen.service import MilitaryVideoGenCore

military_video_gen = MilitaryVideoGenCore()
await military_video_gen.initialize()
```

### generate_video()

鐢熸垚瑙嗛鐨勪富瑕佹柟娉曘€?

**鍙傛暟**:

- `text` (str): 涓婚鎴栧畬鏁存枃妗?
- `mode` (str): 鐢熸垚妯″紡 ("generate" 鎴?"fixed")
- `n_scenes` (int): 鍒嗛暅鏁伴噺
- `title` (str, optional): 瑙嗛鏍囬
- `tts_workflow` (str): TTS 宸ヤ綔娴?
- `media_workflow` (str): 濯掍綋鐢熸垚宸ヤ綔娴侊紙鍥惧儚鎴栬棰戯級
- `frame_template` (str): 瑙嗛妯℃澘
- `template_params` (dict, optional): 妯℃澘鑷畾涔夊弬鏁?
- `bgm_path` (str, optional): BGM 鏂囦欢璺緞
- `bgm_volume` (float): BGM 闊抽噺 (0.0-1.0)

**杩斿洖**: `VideoResult` 瀵硅薄

---

## HTTP REST API

鍚姩 API 鏈嶅姟鍣細

```bash
uv run uvicorn api.app:app --host 0.0.0.0 --port 8000
```

### 瑙嗛鐢熸垚 - 鍚屾

`POST /api/video/generate/sync`

鍚屾鐢熸垚瑙嗛锛岀瓑寰呭畬鎴愬悗杩斿洖缁撴灉銆傞€傚悎灏忚棰戯紙< 30 绉掞級銆?

**璇锋眰浣?*:

```json
{
  "text": "涓轰粈涔堣鍏绘垚闃呰涔犳儻",
  "mode": "generate",
  "n_scenes": 5,
  "frame_template": "1080x1920/image_default.html",
  "template_params": {
    "accent_color": "#3498db",
    "background": "https://example.com/custom-bg.jpg"
  },
  "title": "闃呰鐨勫姏閲?
}
```

**鍝嶅簲**:

```json
{
  "success": true,
  "message": "Success",
  "video_url": "http://localhost:8000/api/files/xxx/final.mp4",
  "duration": 45.5,
  "file_size": 12345678
}
```

### 瑙嗛鐢熸垚 - 寮傛

`POST /api/video/generate/async`

寮傛鐢熸垚瑙嗛锛岀珛鍗宠繑鍥炰换鍔?ID銆傞€傚悎澶ц棰戙€?

**鍝嶅簲**:

```json
{
  "success": true,
  "message": "Task created successfully",
  "task_id": "abc123"
}
```

### 鏌ヨ浠诲姟鐘舵€?

`GET /api/tasks/{task_id}`

**鍝嶅簲**:

```json
{
  "task_id": "abc123",
  "status": "completed",
  "result": {
    "video_url": "http://localhost:8000/api/files/xxx/final.mp4",
    "duration": 45.5,
    "file_size": 12345678
  }
}
```

---

## 璇锋眰鍙傛暟璇存槑

| 鍙傛暟 | 绫诲瀷 | 蹇呭～ | 璇存槑 |
|------|------|------|------|
| `text` | string | 鏄?| 涓婚鎴栧畬鏁存枃妗?|
| `mode` | string | 鍚?| `"generate"` (AI 鐢熸垚) 鎴?`"fixed"` (鍥哄畾鏂囨) |
| `n_scenes` | int | 鍚?| 鍒嗛暅鏁伴噺 (1-20)锛屼粎 generate 妯″紡鏈夋晥 |
| `title` | string | 鍚?| 瑙嗛鏍囬锛堜笉濉垯鑷姩鐢熸垚锛?|
| `frame_template` | string | 鍚?| 妯℃澘璺緞锛屽 `1080x1920/image_default.html` |
| `template_params` | object | 鍚?| 妯℃澘鑷畾涔夊弬鏁帮紙棰滆壊銆佽儗鏅瓑锛?|
| `media_workflow` | string | 鍚?| 濯掍綋宸ヤ綔娴侊紙鍥惧儚鎴栬棰戠敓鎴愶級 |
| `tts_workflow` | string | 鍚?| TTS 宸ヤ綔娴?|
| `ref_audio` | string | 鍚?| 澹伴煶鍏嬮殕鍙傝€冮煶棰戣矾寰?|
| `prompt_prefix` | string | 鍚?| 鍥惧儚椋庢牸鍓嶇紑 |
| `bgm_path` | string | 鍚?| BGM 鏂囦欢璺緞 |
| `bgm_volume` | float | 鍚?| BGM 闊抽噺 (0.0-1.0锛岄粯璁?0.3) |

---

## 鏇村淇℃伅

API 鏂囨。涔熷彲閫氳繃 Swagger UI 璁块棶锛歚http://localhost:8000/docs`

