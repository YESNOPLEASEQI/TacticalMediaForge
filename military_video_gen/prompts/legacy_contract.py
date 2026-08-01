"""Detection helpers for prompt contracts retired before LTX-2.3 creative v2."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

PROMPT_CONTRACT_VERSION = "ltx-2.3-creative-v2"

# These phrases were emitted by the former evidence-first visual renderer. They
# produce catalog/profile shots and must never be accepted as current prompts.
LEGACY_PROMPT_FRAGMENTS = (
    "non-identifying",
    "generic non-identifying military environment",
    "subject at rest with neutral markings",
    "non-operational exterior observation",
    "stable full profile with no identifying details",
    "unverified model-specific details",
    "national or unit insignia",
    "weapon loads or internal structures",
    "named operational locations",
)


def normalize_prompt(value: str) -> str:
    return " ".join(value.casefold().split())


def contains_legacy_prompt(value: str) -> bool:
    normalized = normalize_prompt(value)
    return any(fragment in normalized for fragment in LEGACY_PROMPT_FRAGMENTS)


def duplicate_prompt_groups(prompts: list[str]) -> list[list[int]]:
    positions: dict[str, list[int]] = {}
    for index, prompt in enumerate(prompts):
        normalized = normalize_prompt(prompt)
        if normalized:
            positions.setdefault(normalized, []).append(index)
    return [indexes for indexes in positions.values() if len(indexes) > 1]


def scrub_legacy_prompt_payload(value: Any) -> tuple[Any, int]:
    """Return a deep-cleaned JSON-like value and the number of removed strings."""
    if isinstance(value, str):
        return ("", 1) if contains_legacy_prompt(value) else (value, 0)
    if isinstance(value, list):
        cleaned: list[Any] = []
        removals = 0
        for item in value:
            next_item, count = scrub_legacy_prompt_payload(item)
            removals += count
            # Legacy negative constraints and prompt-list entries are removed,
            # while dictionary fields retain an empty value as an invalidation
            # marker that cannot be mistaken for a usable prompt.
            if not (isinstance(item, str) and count):
                cleaned.append(next_item)
        return cleaned, removals
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        removals = 0
        for key, item in value.items():
            cleaned[key], count = scrub_legacy_prompt_payload(item)
            removals += count
        return cleaned, removals
    return deepcopy(value), 0


def clean_project_settings(settings: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Invalidate a saved storyboard containing any retired prompt contract."""
    cleaned = deepcopy(settings or {})
    draft = cleaned.get("workspace_draft")
    if not isinstance(draft, dict):
        scrubbed, removals = scrub_legacy_prompt_payload(cleaned)
        return scrubbed, bool(removals)
    storyboard = draft.get("storyboard")
    if not isinstance(storyboard, list):
        scrubbed, removals = scrub_legacy_prompt_payload(cleaned)
        return scrubbed, bool(removals)

    state_changed = False
    research = draft.get("research")
    if not storyboard and isinstance(research, dict) and research.get("stale") is True:
        if research.get("activeJobId") is not None:
            research["activeJobId"] = None
            state_changed = True
        if "active_research_job_id" in cleaned:
            cleaned.pop("active_research_job_id", None)
            state_changed = True

    contaminated = any(
        isinstance(scene, dict)
        and any(
            contains_legacy_prompt(str(scene.get(field) or ""))
            for field in ("mediaPrompt", "visualDescription", "media_prompt", "visual_description")
        )
        for scene in storyboard
    )
    if not contaminated:
        draft["promptContractVersion"] = PROMPT_CONTRACT_VERSION
        if state_changed:
            cleaned["legacy_prompt_cleanup"] = PROMPT_CONTRACT_VERSION
        scrubbed, removals = scrub_legacy_prompt_payload(cleaned)
        return scrubbed, bool(removals or state_changed)

    draft["storyboard"] = []
    draft["storyboardConfirmed"] = False
    draft["stage"] = "storyboard" if draft.get("scriptConfirmed") else "script"
    draft["contentRevision"] = int(draft.get("contentRevision") or 0) + 1
    draft["promptContractVersion"] = PROMPT_CONTRACT_VERSION
    if isinstance(research, dict):
        research["activeJobId"] = None
        research["stale"] = True
        if research.get("mode") == "verified":
            research["status"] = "reference_unavailable"
    cleaned["workspace_draft"] = draft
    cleaned.pop("active_research_job_id", None)
    cleaned["legacy_prompt_cleanup"] = PROMPT_CONTRACT_VERSION
    scrubbed, _ = scrub_legacy_prompt_payload(cleaned)
    return scrubbed, True


def remove_legacy_fragments_from_text(value: str) -> tuple[str, int]:
    """Redact retired fragments from archival text that is not valid JSON."""
    removals = 0
    result = value
    for fragment in sorted(LEGACY_PROMPT_FRAGMENTS, key=len, reverse=True):
        result, count = re.subn(re.escape(fragment), "", result, flags=re.IGNORECASE)
        removals += count
    return result, removals
