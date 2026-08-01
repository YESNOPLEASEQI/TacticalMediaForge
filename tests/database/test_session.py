import pytest

from military_video_gen.database.session import create_session_factory, session_scope


@pytest.mark.asyncio
async def test_session_scope_creates_independent_sessions(tmp_path):
    factory = create_session_factory(f"sqlite+aiosqlite:///{tmp_path / 'sessions.db'}")

    async with session_scope(factory) as first:
        async with session_scope(factory) as second:
            assert first is not second
