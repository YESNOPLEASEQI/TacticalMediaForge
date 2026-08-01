import pytest
from fastapi import HTTPException

from military_video_gen.research.gate import enforce_verified_storyboard_gate


@pytest.mark.asyncio
async def test_unverified_generation_does_not_require_reference_metadata() -> None:
    request = type("Request", (), {"verification_mode": "unverified"})()
    await enforce_verified_storyboard_gate(object(), request)


@pytest.mark.asyncio
async def test_verified_generation_requires_server_owned_project_context() -> None:
    request = type(
        "Request",
        (),
            {
                "verification_mode": "verified",
                "session_id": None,
                "script_revision": 99,
                "confirmed_storyboard": [],
        },
    )()
    with pytest.raises(HTTPException) as caught:
        await enforce_verified_storyboard_gate(object(), request)
    assert caught.value.status_code == 409
