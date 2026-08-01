from military_video_gen.prompts.legacy_contract import (
    clean_project_settings,
    contains_legacy_prompt,
    duplicate_prompt_groups,
    scrub_legacy_prompt_payload,
)

OLD_PROMPT = (
    "a non-identifying main battle tank; generic non-identifying military environment; "
    "subject at rest with neutral markings; stable full profile with no identifying details"
)


def test_clean_project_settings_invalidates_only_the_storyboard() -> None:
    settings = {
        "active_research_job_id": "research-old",
        "workspace_draft": {
            "stage": "video",
            "narrations": ["kept narration"],
            "scriptConfirmed": True,
            "storyboardConfirmed": True,
            "contentRevision": 4,
            "storyboard": [{"mediaPrompt": OLD_PROMPT, "narration": "kept narration"}],
            "research": {"mode": "verified", "activeJobId": "research-old", "stale": False},
        },
    }

    cleaned, changed = clean_project_settings(settings)

    assert changed is True
    assert cleaned["workspace_draft"]["narrations"] == ["kept narration"]
    assert cleaned["workspace_draft"]["storyboard"] == []
    assert cleaned["workspace_draft"]["storyboardConfirmed"] is False
    assert cleaned["workspace_draft"]["stage"] == "storyboard"
    assert cleaned["workspace_draft"]["contentRevision"] == 5
    assert cleaned["workspace_draft"]["research"]["activeJobId"] is None
    assert "active_research_job_id" not in cleaned


def test_scrub_legacy_payload_removes_prompt_strings_and_constraints() -> None:
    cleaned, count = scrub_legacy_prompt_payload(
        {
            "storyboard_plan": [{"media_prompt": OLD_PROMPT}],
            "negative_constraints": ["named operational locations", "readable captions"],
        }
    )

    assert count == 2
    assert cleaned["storyboard_plan"][0]["media_prompt"] == ""
    assert cleaned["negative_constraints"] == ["readable captions"]


def test_legacy_and_duplicate_detection_normalizes_case_and_whitespace() -> None:
    assert contains_legacy_prompt("A NON-IDENTIFYING tank") is True
    assert duplicate_prompt_groups(["A tank moves.", " a  TANK moves. "]) == [[0, 1]]
