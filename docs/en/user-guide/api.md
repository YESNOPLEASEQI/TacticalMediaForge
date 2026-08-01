# API Usage

MilitaryVideoGen provides a complete Python API for easy integration into your projects.

---

## Quick Start

```python
from military_video_gen.service import MilitaryVideoGenCore
import asyncio

async def main():
    # Initialize
    military_video_gen = MilitaryVideoGenCore()
    await military_video_gen.initialize()
    
    # Generate video
    result = await military_video_gen.generate_video(
        text="Why develop a reading habit",
        mode="generate",
        n_scenes=5
    )
    
    print(f"Video generated: {result.video_path}")

# Run
asyncio.run(main())
```

---

## API Reference

For detailed API documentation, see [API Overview](../reference/api-overview.md).

---

## Examples

For more usage examples, check the `examples/` directory in the project.

