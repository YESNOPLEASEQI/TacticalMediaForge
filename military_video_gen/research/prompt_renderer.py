"""Pure, deterministic rendering of structured storyboard scenes."""

import re

from .models import GroundedStoryboardScene

DOCUMENTARY_STYLE = (
    "authentic military documentary, factual visual reconstruction, "
    "physically plausible motion"
)
_WHITESPACE = re.compile(r"\s+")


def _clean(value: str) -> str:
    return _WHITESPACE.sub(" ", value.strip()).strip(" ,;.")


def _stable_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean(value)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def render_prompt(
    scene: GroundedStoryboardScene,
    *,
    max_length: int = 4000,
) -> str:
    """Render a scene in a fixed order without paraphrasing any field."""
    ordered_values = [
        scene.subject.value,
        scene.environment.value,
        scene.opening_state.value,
        scene.action.value,
        scene.camera.value,
        scene.composition.value,
        scene.lighting.value,
        scene.ending_frame.value,
        DOCUMENTARY_STYLE,
    ]
    segments = _stable_unique(ordered_values)
    negative = _stable_unique(scene.negative_constraints)
    if negative:
        segments.append(f"avoid: {', '.join(negative)}")

    if max_length <= 0:
        return ""
    rendered: list[str] = []
    for segment in segments:
        candidate = "; ".join([*rendered, segment])
        if len(candidate) > max_length:
            break
        rendered.append(segment)
    return "; ".join(rendered)
