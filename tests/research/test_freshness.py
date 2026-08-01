from military_video_gen.research.freshness import compute_input_hash


def _hash(**overrides: object) -> str:
    values = {
        "topic": "  F-16\t战斗机  ",
        "narrations": ["第一段  旁白", "第二段旁白"],
        "asset_type": "video",
        "mode": "verified",
    }
    values.update(overrides)
    return compute_input_hash(**values)


def test_hash_normalizes_unicode_and_whitespace() -> None:
    assert _hash() == _hash(
        topic="F-16 战斗机",
        narrations=["第一段 旁白", "第二段旁白"],
    )


def test_hash_changes_when_any_research_input_changes() -> None:
    baseline = _hash()

    assert _hash(topic="F-15 战斗机") != baseline
    assert _hash(narrations=["第二段旁白", "第一段 旁白"]) != baseline
    assert _hash(asset_type="image") != baseline


def test_hash_is_stable_sha256_hex() -> None:
    result = _hash()

    assert len(result) == 64
    assert result == _hash()
    int(result, 16)
