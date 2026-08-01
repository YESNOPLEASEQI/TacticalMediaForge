from military_video_gen.prompts.content_narration import build_content_narration_prompt


def test_content_narration_prompt_uses_short_subtitle_cards() -> None:
    prompt = build_content_narration_prompt(
        content="解释火炮如何发射弹丸",
        n_storyboard=5,
        min_words=5,
        max_words=20,
    )

    assert "12~22 Chinese-character subtitle card" in prompt
    assert "at most one comma" in prompt
    assert "never chain several facts with commas" in prompt
    assert "without padding or unnecessary expansion" in prompt
