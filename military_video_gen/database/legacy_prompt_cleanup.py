"""One-way cleanup for persisted prompts from retired storyboard contracts."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from military_video_gen.database.models import (
    Asset,
    GenerationJob,
    Project,
    ScriptVersion,
    StoryboardScene,
)
from military_video_gen.database.session import AsyncSessionFactory
from military_video_gen.prompts.legacy_contract import (
    clean_project_settings,
    contains_legacy_prompt,
    scrub_legacy_prompt_payload,
)


@dataclass
class LegacyPromptCleanupReport:
    projects: int = 0
    jobs: int = 0
    scenes: int = 0
    assets: int = 0
    script_versions: int = 0
    removed_strings: int = 0


async def clean_legacy_prompt_records(
    *, factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory
) -> LegacyPromptCleanupReport:
    report = LegacyPromptCleanupReport()
    async with factory() as session:
        for project in (await session.scalars(select(Project))).all():
            settings, changed = clean_project_settings(project.settings_json or {})
            if changed:
                project.settings_json = settings
                report.projects += 1

        for job in (await session.scalars(select(GenerationJob))).all():
            params, param_count = scrub_legacy_prompt_payload(job.params_json or {})
            result, result_count = scrub_legacy_prompt_payload(job.result_json or {})
            if param_count or result_count:
                job.params_json = params
                job.result_json = result
                report.jobs += 1
                report.removed_strings += param_count + result_count

        for scene in (await session.scalars(select(StoryboardScene))).all():
            changed = False
            if scene.media_prompt and contains_legacy_prompt(scene.media_prompt):
                scene.media_prompt = None
                changed = True
                report.removed_strings += 1
            if scene.visual_description and contains_legacy_prompt(scene.visual_description):
                scene.visual_description = None
                changed = True
                report.removed_strings += 1
            metadata, count = scrub_legacy_prompt_payload(scene.metadata_json or {})
            if count:
                scene.metadata_json = metadata
                changed = True
                report.removed_strings += count
            if changed:
                scene.review_status = "pending"
                report.scenes += 1

        for asset in (await session.scalars(select(Asset))).all():
            if asset.prompt and contains_legacy_prompt(asset.prompt):
                asset.prompt = None
                report.assets += 1
                report.removed_strings += 1

        for version in (await session.scalars(select(ScriptVersion))).all():
            metadata, count = scrub_legacy_prompt_payload(version.metadata_json or {})
            if count:
                version.metadata_json = metadata
                report.script_versions += 1
                report.removed_strings += count

        await session.commit()
    return report
