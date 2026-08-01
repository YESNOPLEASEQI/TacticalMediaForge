from military_video_gen.research.models import (
    FieldProvenance,
    GroundedField,
    GroundedStoryboardScene,
)
from military_video_gen.research.prompt_renderer import render_prompt


def make_scene() -> GroundedStoryboardScene:
    provenance = FieldProvenance(
        claim_ids=["claim-1"], visual_fact_ids=["visual-1"]
    )
    return GroundedStoryboardScene(
        scene_index=1,
        narration="A verified exterior inspection.",
        visual_description="A generic aircraft is inspected on an apron.",
        subject=GroundedField(value="generic military aircraft", provenance=provenance),
        environment=GroundedField(value="concrete airbase apron", provenance=provenance),
        opening_state=GroundedField(value="aircraft stationary", provenance=provenance),
        action=GroundedField(value="crew inspect the exterior", provenance=provenance),
        camera=GroundedField(value="slow lateral tracking shot", creative=True),
        composition=GroundedField(value="aircraft centered", creative=True),
        lighting=GroundedField(value="neutral natural daylight", creative=True),
        ending_frame=GroundedField(value="verified exterior profile", provenance=provenance),
        claim_ids=["claim-1"],
        visual_fact_ids=["visual-1"],
        negative_constraints=["no logos", "no readable markings", "no logos"],
        confidence=0.9,
        fallback_level="verified_generic",
        verification_status="verified",
    )


def test_render_is_byte_deterministic_and_has_fixed_field_order() -> None:
    scene = make_scene()

    first = render_prompt(scene)
    second = render_prompt(scene)

    assert first.encode() == second.encode()
    assert first.index("generic military aircraft") < first.index("concrete airbase apron")
    assert first.index("aircraft stationary") < first.index("crew inspect the exterior")
    assert first.count("no logos") == 1


def test_renderer_does_not_invent_model_numbers_or_actions() -> None:
    rendered = render_prompt(make_scene())

    assert "F-35" not in rendered
    assert "missile" not in rendered
    assert "takeoff" not in rendered
    assert "001" not in rendered


def test_renderer_skips_empty_optional_values() -> None:
    scene = make_scene().model_copy(
        update={"camera": GroundedField(value="", creative=True)}
    )

    rendered = render_prompt(scene)

    assert "; ;" not in rendered
    assert not rendered.startswith(";")
    assert not rendered.endswith(";")
