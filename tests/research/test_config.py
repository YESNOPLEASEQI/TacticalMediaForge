from pathlib import Path

from military_video_gen.config.loader import load_config_dict
from military_video_gen.config.schema import MilitaryVideoGenConfig


def test_research_defaults_are_disabled_and_match_design() -> None:
    config = MilitaryVideoGenConfig()

    assert config.research.enabled is False
    assert config.research.default_mode == "verified"
    assert config.research.search.max_queries == 5
    assert config.research.search.max_pages == 8
    assert config.research.search.max_pages_per_domain == 2
    assert config.research.crawl.auth_token_env == "CRAWL4AI_API_TOKEN"
    assert config.research.crawl.allow_proxy_fake_ip is False
    assert config.research.crawl.respect_robots_txt is False
    assert config.research.verification.minimum_verified_claim_confidence == 0.75
    assert config.research.verification.minimum_low_confidence_claim_confidence == 0.65
    assert config.research.verification.minimum_discovery_claim_confidence == 0.55
    assert config.research.verification.minimum_visual_fact_confidence == 0.65
    assert config.research.verification.total_timeout_seconds == 120
    assert config.research.verification.extraction_timeout_seconds == 45
    assert config.research.verification.planning_timeout_seconds == 30


def test_loader_expands_nested_environment_placeholders(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SEARXNG_BASE_URL", "http://localhost:8080")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "research:\n"
        "  search:\n"
        '    base_url: "${SEARXNG_BASE_URL:-http://searxng:8080}"\n'
        "  crawl:\n"
        '    base_url: "${MISSING_CRAWL_URL:-http://crawl4ai:11235}"\n',
        encoding="utf-8",
    )

    loaded = load_config_dict(str(config_path))

    assert loaded["research"]["search"]["base_url"] == "http://localhost:8080"
    assert loaded["research"]["crawl"]["base_url"] == "http://crawl4ai:11235"


def test_auth_token_env_is_a_name_not_expanded_secret(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CRAWL4AI_API_TOKEN", "super-secret")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "research:\n  crawl:\n    auth_token_env: CRAWL4AI_API_TOKEN\n",
        encoding="utf-8",
    )

    config = MilitaryVideoGenConfig.model_validate(load_config_dict(str(config_path)))
    dumped = config.model_dump()

    assert dumped["research"]["crawl"]["auth_token_env"] == "CRAWL4AI_API_TOKEN"
    assert "super-secret" not in repr(dumped)
