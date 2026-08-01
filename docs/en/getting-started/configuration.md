# Configuration

After installation, you need to configure services to use MilitaryVideoGen.

---

## LLM Configuration

LLM (Large Language Model) is used to generate video scripts.

### Quick Preset Selection

1. Select a preset model from the dropdown:
   - Qianwen (recommended, great value)
   - GPT-4o
   - DeepSeek
   - Ollama (local, completely free)

2. The system will auto-fill `base_url` and `model`

3. Click銆岎煍?Get API Key銆峵o register and obtain credentials

4. Enter your API Key

---

## Image/Video Generation Configuration

Two options available:

### Local Deployment

Using local ComfyUI service:

1. Install and start ComfyUI
2. Enter ComfyUI URL (default `http://127.0.0.1:8188`)
3. Click "Test Connection" to verify
4. (Optional) Enter ComfyUI API Key (get from [Comfy Platform](https://platform.comfy.org/profile/api-keys))

### Cloud Deployment (Recommended)

Using RunningHub cloud service, no local GPU required:

1. Register for a RunningHub account
2. Obtain API Key
3. Enter API Key in configuration
4. Configure advanced options (optional):
   - **Concurrent Limit**: Set number of simultaneous tasks (1-10, default 1 for regular members)
   - **Instance Type**: Choose 24GB or 48GB VRAM machine (48GB for large video generation)

---

## Save Configuration

After filling in all required configuration, click the "Save Configuration" button.

Configuration will be saved to `config.yaml` file.

---

## Next Steps

- [Quick Start](quick-start.md) - Create your first video

## Web reference enhancement (optional)

Research is disabled by default. Start its isolated dependencies with:

```bash
docker compose --profile research up -d searxng crawl4ai
```

Copy `.env.example` to `.env`, set `CRAWL4AI_API_TOKEN`, and set
`research.enabled: true` in `config.yaml`. When running the API directly on the
host, use `http://localhost:8080` for SearXNG and `http://localhost:12135` for
Crawl4AI. The configuration stores only the token variable name; never place
the token value in YAML.

The default `docker compose up` command does not start these services. Web
references enrich storyboard prompts but never gate generation. If search,
crawling, cleanup, or the reference timeout fails, the system completes the
research job with ordinary prompts and a lightweight warning.

