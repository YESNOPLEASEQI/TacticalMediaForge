"""LTX-2.3-oriented video prompt generation template."""

import json
import math
from collections.abc import Sequence
from typing import List

VIDEO_PROMPT_GENERATION_PROMPT = """# Role Definition
You are a creative cinematographer writing prompts directly for the LTX-2.3
text-to-video model. Expand each narration into a vivid, filmable shot while
preserving the user's subject and creative intent.

# Core Task
Create exactly one English video prompt for each input scene. Treat narration,
duration, neighboring-scene context, and web reference notes as creative inputs.
Reference notes are useful context, not a checklist, and must never appear as
research commentary or citations in the output.

# Input Scenes
{scenes_json}

# LTX-2.3 Prompt Contract
- Write one continuous natural-language paragraph per scene, in English only.
- Follow the target word range and never exceed 200 English words.
- Start directly with the visible scene or the main action. Do not use a title,
  preface, bullet list, timestamp, policy statement, or "the scene opens".
- Resolve and name the actual visible subject. Preserve public model names,
  historical identities, national context, markings, locations, and equipment
  when the narration or references provide them. Never anonymize a subject merely
  because it is military.
- Describe events chronologically in present tense: establish the initial state,
  follow one principal action through natural intermediate motion, and finish on
  a concrete visible state. Use active verbs and temporal connectors naturally.
- Include the details LTX-2.3 can render: subject appearance and materials,
  environment, scale, movement, physical interaction, shot size, camera position,
  lighting, color, atmosphere, and synchronized environmental or mechanical sound.
- Use one clear camera behavior that serves the action. A static camera is valid;
  when the camera moves, describe its relationship to the subject precisely.
- Keep each prompt to one coherent shot. Avoid montage, split screen, unrelated
  locations, contradictory camera instructions, and overloaded simultaneous action.
- Match detail to duration and shot scale. Short shots need a focused action;
  longer shots may contain two directly connected action phases.
- Use neighboring-scene context only to maintain continuity and to make this shot
  visibly distinct in action, framing, distance, location detail, or ending state.

# Creative Freedom and Practical Limits
- Prefer literal, visually specific language over abstract mood labels. Express
  emotion through visible posture, motion, facial expression, light, and sound.
- Publicly described military hardware, mechanisms, personnel, operations, and
  historical scenes are valid visual subjects. Approximate minor visual details
  when necessary instead of replacing the whole scene with generic stock footage.
- Keep motion physically legible and internally consistent. Avoid impossible
  camera paths, teleportation, accidental object morphing, and chaotic combinations
  that are unlikely to fit the requested duration.
- Do not rely on readable captions, interface overlays, watermarks, or long printed
  text because current video models render them unreliably.
- Include only natural environmental and mechanical audio. Do not invent dialogue,
  narration, singing, or music because voice-over and background music are added
  separately by this project.
- Never include evidence status, uncertainty disclaimers, source limitations, or
  policy language in a generation prompt.

# Output Format
Return strict JSON only:

```json
{{
  "video_prompts": [
    "one complete English prompt for scene 1",
    "one complete English prompt for scene 2"
  ]
}}
```

The video_prompts array must contain exactly {scenes_count} items in input order.
Do not include explanations or any keys other than video_prompts.
{revision_feedback}
"""


def estimate_video_prompt_duration(narration: str) -> int:
    """Estimate whole-second narration duration before TTS is available."""
    character_count = len("".join(narration.strip().split()))
    return max(2, math.ceil(character_count / 4.2))


def video_prompt_word_range(duration_seconds: float) -> tuple[int, int]:
    """Return an LTX prompt word range matched to the visible shot duration."""
    if duration_seconds <= 4:
        return 40, 100
    if duration_seconds <= 8:
        return 60, 140
    if duration_seconds <= 15:
        return 90, 170
    return 110, 195


def build_video_prompt_prompt(
    narrations: List[str],
    min_words: int = 30,
    max_words: int = 60,
    *,
    estimated_durations: Sequence[float] | None = None,
    reference_contexts: Sequence[Sequence[str]] | None = None,
    previous_prompts: Sequence[str] | None = None,
    validation_feedback: Sequence[Sequence[str]] | None = None,
) -> str:
    """Build the shared prompt contract used by quick and reference storyboards.

    ``min_words`` and ``max_words`` remain accepted for older callers. Video
    prompts use duration-aware ranges because a single global image-prompt range
    cannot describe both short and long shots reliably.
    """
    del min_words, max_words
    durations = list(estimated_durations or [])
    contexts = list(reference_contexts or [])
    scenes = []
    for index, narration in enumerate(narrations):
        duration = (
            float(durations[index])
            if index < len(durations) and durations[index] > 0
            else float(estimate_video_prompt_duration(narration))
        )
        target_min, target_max = video_prompt_word_range(duration)
        notes = contexts[index] if index < len(contexts) else []
        scenes.append(
            {
                "scene_index": index + 1,
                "narration": narration,
                "estimated_duration_seconds": math.ceil(duration),
                "target_english_words": {"min": target_min, "max": target_max},
                "reference_notes": [str(note).strip() for note in notes if str(note).strip()],
            }
        )

    feedback = ""
    if previous_prompts and validation_feedback:
        revisions = []
        for index, old_prompt in enumerate(previous_prompts):
            issues = validation_feedback[index] if index < len(validation_feedback) else []
            revisions.append(
                {
                    "scene_index": index + 1,
                    "previous_prompt": old_prompt,
                    "problems_to_fix": list(issues),
                }
            )
        feedback = (
            "\n# Revision Request\nRewrite the supplied previous prompts and fix only "
            "the listed problems while preserving valid scene facts and continuity.\n"
            + json.dumps(revisions, ensure_ascii=False, indent=2)
        )

    return VIDEO_PROMPT_GENERATION_PROMPT.format(
        scenes_json=json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2),
        scenes_count=len(scenes),
        revision_feedback=feedback,
    )
