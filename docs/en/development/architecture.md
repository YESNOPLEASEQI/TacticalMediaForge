# Architecture

Technical architecture overview of MilitaryVideoGen.

---

## Core Architecture

MilitaryVideoGen uses a layered architecture design:

- **Web Layer**: React frontend interface
- **Service Layer**: Core business logic
- **ComfyUI Layer**: Image and TTS generation

---

## Main Components

### MilitaryVideoGenCore

Core service class coordinating all sub-services.

### LLM Service

Responsible for calling large language models to generate scripts.

### Image Service

Responsible for calling ComfyUI to generate images.

### TTS Service

Responsible for calling ComfyUI to generate speech.

### Video Generator

Responsible for composing the final video.

---

## Tech Stack

- **Backend**: Python 3.10+, AsyncIO
- **Web**: React + Vite
- **AI**: OpenAI API, ComfyUI
- **Configuration**: YAML
- **Tools**: uv (package management)

---

## More Information

Detailed architecture documentation coming soon.

