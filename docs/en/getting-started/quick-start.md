# Quick Start

Already installed and configured? Let's create your first video!

---

## Start the Web Interface

### Windows All-in-One Package Users

If you're using the Windows All-in-One Package, simply:
1. Double-click `start.bat`
2. Your browser will automatically open `http://localhost:5173`

### Install from Source Users

```bash
# Using uv
start_react_stack.bat
```

Your browser will automatically open `http://localhost:5173`

---

## Create Your First Video

### Step 1: Check Configuration

On first use, expand the銆屸殭锔?System Configuration銆峱anel and confirm:

- **LLM Configuration**: Select an AI model (e.g., Qianwen, GPT) and enter API Key
- **Image Configuration**: Configure ComfyUI address or RunningHub API Key

If not yet configured, see the [Configuration Guide](configuration.md).

Click "Save Configuration" when done.

---

### Step 2: Enter a Topic

In the left panel's銆岎煋?Content Input銆峴ection:

1. Select銆?*AI Generate Content**銆峬ode
2. Enter a topic in the text box, for example:
   ```
   Why develop a reading habit
   ```
3. (Optional) Set number of scenes, default is 5 frames

!!! tip "Topic Examples"
    - Why develop a reading habit
    - How to improve work efficiency
    - The importance of healthy eating
    - The meaning of travel

---

### Step 3: Configure Voice and Visuals

In the middle panel:

**Voice Settings**
- Select TTS workflow (default Edge-TTS works well)
- For voice cloning, upload a reference audio file

**Visual Settings**
- Select image generation workflow (default works well)
- Set image dimensions (default 1024x1024)
- Choose video template (recommend portrait 1080x1920)

---

### Step 4: Generate Video

Click the銆岎煄?Generate Video銆峛utton in the right panel!

The system will show real-time progress:
- Generate script
- Generate images (for each scene)
- Synthesize voice
- Compose video

!!! info "Generation Time"
    Generating a 5-scene video takes about 2-5 minutes, depending on: LLM API response speed, image generation speed, TTS workflow type, and network conditions

---

### Step 5: Preview Video

Once complete, the video will automatically play in the right panel!

You'll see:
- 馃摴 Video preview player
- 鈴憋笍 Video duration
- 馃摝 File size
- 馃幀 Number of scenes
- 馃搻 Video dimensions

The video file is saved in the `output/` folder.

---

## Next Steps

Congratulations! You've successfully created your first video 馃帀

Next, you can:

- **Adjust Styles** - See the [Custom Visual Style](../tutorials/custom-style.md) tutorial
- **Clone Voices** - See the [Voice Cloning with Reference Audio](../tutorials/voice-cloning.md) tutorial
- **Use API** - See the [API Usage Guide](../user-guide/api.md)
- **Develop Templates** - See the [Template Development Guide](../user-guide/templates.md)

