# 閰嶇疆璇存槑

瀹屾垚瀹夎鍚庯紝闇€瑕侀厤缃湇鍔℃墠鑳戒娇鐢?MilitaryVideoGen銆?

---

## LLM 閰嶇疆

LLM锛堝ぇ璇█妯″瀷锛夌敤浜庣敓鎴愯棰戞枃妗堛€?

### 蹇€熼€夋嫨棰勮

1. 浠庝笅鎷夎彍鍗曢€夋嫨棰勮妯″瀷锛?
   - 閫氫箟鍗冮棶锛堟帹鑽愶紝鎬т环姣旈珮锛?
   - GPT-4o
   - DeepSeek
   - Ollama锛堟湰鍦拌繍琛岋紝瀹屽叏鍏嶈垂锛?

2. 绯荤粺浼氳嚜鍔ㄥ～鍏?`base_url` 鍜?`model`

3. 鐐瑰嚮銆岎煍?鑾峰彇 API Key銆嶉摼鎺ワ紝娉ㄥ唽骞惰幏鍙栧瘑閽?

4. 濉叆 API Key

---

## 鍥惧儚/瑙嗛鐢熸垚閰嶇疆

鏀寔涓ょ鏂瑰紡锛?

### 鏈湴閮ㄧ讲

浣跨敤鏈湴 ComfyUI 鏈嶅姟锛?

1. 瀹夎骞跺惎鍔?ComfyUI
2. 濉啓 ComfyUI URL锛堥粯璁?`http://127.0.0.1:8188`锛?
3. 鐐瑰嚮銆屾祴璇曡繛鎺ャ€嶇‘璁ゆ湇鍔″彲鐢?
4. 锛堝彲閫夛級濉啓 ComfyUI API Key锛堜粠 [Comfy Platform](https://platform.comfy.org/profile/api-keys) 鑾峰彇锛?

### 浜戠閮ㄧ讲锛堟帹鑽愶級

浣跨敤 RunningHub 浜戠鏈嶅姟锛屾棤闇€鏈湴 GPU锛?

1. 娉ㄥ唽 RunningHub 璐﹀彿
2. 鑾峰彇 API Key
3. 鍦ㄩ厤缃腑濉啓 API Key
4. 閰嶇疆楂樼骇閫夐」锛堝彲閫夛級锛?
   - **骞跺彂闄愬埗**: 璁剧疆鍚屾椂鎵ц鐨勪换鍔℃暟锛?-10锛屾櫘閫氫細鍛橀粯璁や负 1锛?
   - **瀹炰緥绫诲瀷**: 閫夋嫨 24GB 鎴?48GB 鏄惧瓨鏈哄櫒锛?8GB 閫傚悎澶у昂瀵歌棰戠敓鎴愶級

---

## 淇濆瓨閰嶇疆

濉啓瀹屾墍鏈夊繀闇€鐨勯厤缃悗锛岀偣鍑汇€屼繚瀛橀厤缃€嶆寜閽€?

閰嶇疆浼氫繚瀛樺埌 `config.yaml` 鏂囦欢涓€?

---

## 涓嬩竴姝?

- [蹇€熷紑濮媇(quick-start.md) - 鐢熸垚浣犵殑绗竴涓棰?

## 联网参考增强（可选）

研究功能默认关闭。使用以下命令启动相互独立的研究依赖：

```bash
docker compose --profile research up -d searxng crawl4ai
```

将 `.env.example` 复制为 `.env`，设置 `CRAWL4AI_API_TOKEN`，并在
`config.yaml` 中设置 `research.enabled: true`。直接在宿主机运行 API 时，
SearXNG 和 Crawl4AI 地址分别使用 `http://localhost:8080` 和
`http://localhost:12135`。YAML 只保存 Token 的环境变量名称，不能保存 Token 值。

普通 `docker compose up` 不会启动研究服务。联网资料只作为分镜生成的参考；
搜索、抓取、资料清洗或超时不可用时，系统会自动按普通模式生成分镜并显示轻量提示，
不会阻止后续视频生成。

