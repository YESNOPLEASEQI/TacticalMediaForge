# 閰嶇疆鏂囦欢璇﹁В

`config.yaml` 閰嶇疆鏂囦欢鐨勮缁嗚鏄庛€?

---

## 閰嶇疆缁撴瀯

```yaml
llm:
  api_key: "your-api-key"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model: "qwen-plus"

comfyui:
  comfyui_url: "http://127.0.0.1:8188"
  comfyui_api_key: ""  # ComfyUI API 瀵嗛挜锛堝彲閫夛級
  runninghub_api_key: ""
  runninghub_concurrent_limit: 1  # 骞跺彂闄愬埗 (1-10)
  runninghub_instance_type: ""  # 瀹炰緥绫诲瀷锛堝彲閫夛紝璁句负 "plus" 浣跨敤 48GB 鏄惧瓨锛?
  
  image:
    default_workflow: "runninghub/image_flux.json"
    prompt_prefix: "Minimalist illustration style"
  
  video:
    default_workflow: "selfhost/video_ltx2_3_t2v.json"
    prompt_prefix: "Minimalist illustration style"
  
  tts:
    default_workflow: "selfhost/tts_edge.json"

template:
  default_template: "1080x1920/image_default.html"
```

---

## LLM 閰嶇疆

- `api_key`: API 瀵嗛挜
- `base_url`: API 鏈嶅姟鍦板潃锛堟敮鎸佷换浣?OpenAI 鍏煎鎺ュ彛锛?
- `model`: 妯″瀷鍚嶇О

---

## ComfyUI 閰嶇疆

### 鍩虹閰嶇疆

- `comfyui_url`: 鏈湴 ComfyUI 鍦板潃锛堥粯璁?`http://127.0.0.1:8188`锛?
- `comfyui_api_key`: ComfyUI API 瀵嗛挜锛堝彲閫夛紝鐢ㄤ簬 [Comfy Platform](https://platform.comfy.org/profile/api-keys)锛?

### RunningHub 浜戠閰嶇疆

- `runninghub_api_key`: RunningHub API 瀵嗛挜锛堜娇鐢ㄤ簯绔伐浣滄祦鏃跺繀濉級
- `runninghub_concurrent_limit`: 骞跺彂鎵ц闄愬埗锛?-10锛屾櫘閫氫細鍛橀粯璁や负 1锛?
- `runninghub_instance_type`: 瀹炰緥绫诲瀷锛堝彲閫夛級
  - 鐣欑┖鎴栦笉璁剧疆锛氫娇鐢?24GB 鏄惧瓨鏈哄櫒
  - `"plus"`: 浣跨敤 48GB 鏄惧瓨鏈哄櫒锛堥€傚悎澶у昂瀵歌棰戠敓鎴愶級

### 鍥惧儚閰嶇疆

- `default_workflow`: 榛樿鍥惧儚鐢熸垚宸ヤ綔娴?
- `prompt_prefix`: 鎻愮ず璇嶅墠缂€

### 瑙嗛閰嶇疆

- `default_workflow`: 榛樿瑙嗛鐢熸垚宸ヤ綔娴?
  - `runninghub/video_wan2.1_fusionx.json`: 浜戠宸ヤ綔娴侊紙鎺ㄨ崘锛屾棤闇€鏈湴鐜锛?
  - `selfhost/video_wan2.1_fusionx.json`: 鏈湴宸ヤ綔娴侊紙闇€瑕佹湰鍦?ComfyUI 鏀寔锛?
- `prompt_prefix`: 瑙嗛鎻愮ず璇嶅墠缂€锛堢敤浜庢帶鍒惰棰戠敓鎴愰鏍硷級

### TTS 閰嶇疆

- `default_workflow`: 榛樿 TTS 宸ヤ綔娴?

---

## 妯℃澘閰嶇疆

- `default_template`: 榛樿甯фā鏉胯矾寰勶紙渚嬪 `1080x1920/image_default.html`锛?

---

## 鏇村淇℃伅

閰嶇疆鏂囦欢浼氳嚜鍔ㄥ湪棣栨杩愯鏃跺垱寤恒€?

