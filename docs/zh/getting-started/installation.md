# 瀹夎

鏈〉闈㈠皢鎸囧浣犲畬鎴?MilitaryVideoGen 鐨勫畨瑁呫€?

---

## 绯荤粺瑕佹眰

### 蹇呴渶鏉′欢

- **Python**: 3.10 鎴栨洿楂樼増鏈?
- **鎿嶄綔绯荤粺**: Windows銆乵acOS 鎴?Linux
- **鍖呯鐞嗗櫒**: uv锛堟帹鑽愶級鎴?pip

### 鍙€夋潯浠?

- **GPU**: 濡傞渶鏈湴杩愯 ComfyUI锛屽缓璁厤澶?NVIDIA 鏄惧崱锛?GB+ 鏄惧瓨锛?
- **缃戠粶**: 绋冲畾鐨勭綉缁滆繛鎺ワ紙鐢ㄤ簬璋冪敤 LLM API 鍜屽浘鍍忕敓鎴愭湇鍔★級

---

## 馃獰 Windows 涓€閿暣鍚堝寘锛堟帹鑽?Windows 鐢ㄦ埛浣跨敤锛?

**鏃犻渶瀹夎 Python銆乽v 鎴?ffmpeg锛屼竴閿紑绠卞嵆鐢紒**

### 涓嬭浇鍜屽畨瑁?

1. 璁块棶 [GitHub Releases](https://github.com/YESNOPLEASEQI/MilitaryVideoGenAgent/releases/latest) 涓嬭浇鏈€鏂扮増鏈?
2. 涓嬭浇鏈€鏂扮殑 Windows 涓€閿暣鍚堝寘骞惰В鍘嬪埌浠绘剰鐩綍
3. 鍙屽嚮杩愯 `start.bat` 鍚姩 Web 鐣岄潰
4. 娴忚鍣ㄤ細鑷姩鎵撳紑 `http://localhost:5173`

!!! success "瀹夎瀹屾垚锛?
    鏁村悎鍖呭凡鍖呭惈鎵€鏈変緷璧栵紝鏃犻渶鎵嬪姩瀹夎浠讳綍鐜銆傞娆′娇鐢ㄥ彧闇€鍦ㄣ€屸殭锔?绯荤粺閰嶇疆銆嶄腑閰嶇疆 API 瀵嗛挜鍗冲彲寮€濮嬩娇鐢ㄣ€?

!!! tip "涓嬩竴姝?
    瀹夎瀹屾垚鍚庯紝璇锋煡鐪?[閰嶇疆璇存槑](configuration.md) 鏉ヨ缃?LLM 鍜屽浘鍍忕敓鎴愭湇鍔★紝鐒跺悗鏌ョ湅 [蹇€熷紑濮媇(quick-start.md) 鐢熸垚绗竴涓棰戙€?

---

## 浠庢簮鐮佸畨瑁咃紙閫傚悎 macOS / Linux 鐢ㄦ埛鎴栭渶瑕佽嚜瀹氫箟鐨勭敤鎴凤級

### 绗竴姝ワ細鍏嬮殕椤圭洰

```bash
git clone https://github.com/YESNOPLEASEQI/MilitaryVideoGenAgent.git
cd MilitaryVideoGen
```

### 绗簩姝ワ細瀹夎渚濊禆

!!! tip "鎺ㄨ崘浣跨敤 uv"
    鏈」鐩娇鐢?`uv` 浣滀负鍖呯鐞嗗櫒锛屽畠姣斾紶缁熺殑 pip 鏇村揩銆佹洿鍙潬銆?

#### 浣跨敤 uv锛堟帹鑽愶級

```bash
# 濡傛灉杩樻病鏈夊畨瑁?uv锛屽厛瀹夎瀹?
curl -LsSf https://astral.sh/uv/install.sh | sh

# 瀹夎椤圭洰渚濊禆锛坲v 浼氳嚜鍔ㄥ垱寤鸿櫄鎷熺幆澧冿級
uv sync
```

#### 浣跨敤 pip

```bash
# 鍒涘缓铏氭嫙鐜
python -m venv venv

# 婵€娲昏櫄鎷熺幆澧?
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 瀹夎渚濊禆
pip install -e .
```

---

## 楠岃瘉瀹夎

杩愯浠ヤ笅鍛戒护楠岃瘉瀹夎鏄惁鎴愬姛锛?

```bash
# 浣跨敤 uv
start_react_stack.bat

# 鎴栦娇鐢?pip锛堥渶鍏堟縺娲昏櫄鎷熺幆澧冿級
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

娴忚鍣ㄥ簲璇ヤ細鑷姩鎵撳紑 `http://localhost:5173`锛屾樉绀?MilitaryVideoGen 鐨?Web 鐣岄潰銆?

!!! success "瀹夎鎴愬姛锛?
    濡傛灉鑳界湅鍒?Web 鐣岄潰锛岃鏄庡畨瑁呮垚鍔熶簡锛佹帴涓嬫潵璇锋煡鐪?[閰嶇疆璇存槑](configuration.md) 鏉ヨ缃湇鍔°€?

---

## 鍙€夛細瀹夎 ComfyUI锛堟湰鍦伴儴缃诧級

濡傛灉甯屾湜鏈湴杩愯鍥惧儚鐢熸垚鏈嶅姟锛岄渶瑕佸畨瑁?ComfyUI锛?

### 蹇€熷畨瑁?

```bash
# 鍏嬮殕 ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# 瀹夎渚濊禆
pip install -r requirements.txt
```

### 鍚姩 ComfyUI

```bash
python main.py
```

ComfyUI 榛樿杩愯鍦?`http://127.0.0.1:8188`

!!! info "ComfyUI 妯″瀷"
    ComfyUI 闇€瑕佷笅杞藉搴旂殑妯″瀷鏂囦欢鎵嶈兘宸ヤ綔銆傝鍙傝€?[ComfyUI 瀹樻柟鏂囨。](https://github.com/comfyanonymous/ComfyUI) 浜嗚В濡備綍涓嬭浇鍜岄厤缃ā鍨嬨€?

---

## 涓嬩竴姝?

- [閰嶇疆鏈嶅姟](configuration.md) - 閰嶇疆 LLM 鍜屽浘鍍忕敓鎴愭湇鍔?
- [蹇€熷紑濮媇(quick-start.md) - 鐢熸垚绗竴涓棰?

