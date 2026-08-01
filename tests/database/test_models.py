import uuid

from sqlalchemy import inspect

from military_video_gen.database.base import Base
from military_video_gen.database.models import (
    ActivityEvent,
    Asset,
    GenerationJob,
    OutputVersion,
    Project,
    ScriptSegment,
    ScriptVersion,
    StoryboardScene,
    StoryboardVersion,
    WorkflowSnapshot,
)


def test_database_metadata_contains_first_version_tables():
    assert set(Base.metadata.tables) == {
        "projects",
        "script_versions",
        "script_segments",
        "storyboard_versions",
        "storyboard_scenes",
        "generation_jobs",
        "assets",
        "workflow_snapshots",
        "output_versions",
        "activity_events",
    }


def test_uuid_primary_keys_and_required_unique_constraints():
    models = (
        Project,
        ScriptVersion,
        ScriptSegment,
        StoryboardVersion,
        StoryboardScene,
        GenerationJob,
        Asset,
        WorkflowSnapshot,
        OutputVersion,
        ActivityEvent,
    )
    for model in models:
        instance = model()
        assert str(uuid.UUID(instance.id)) == instance.id
        assert inspect(model).primary_key[0].name == "id"

    constraints = {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if constraint.name
    }
    assert {
        "uq_script_versions_project_version",
        "uq_script_segments_version_index",
        "uq_storyboard_versions_project_version",
        "uq_storyboard_scenes_version_index",
        "uq_generation_jobs_provider_external",
        "uq_assets_job_role_path",
        "uq_output_versions_project_version",
    } <= constraints


def test_relationships_use_explicit_back_populates():
    assert Project.script_versions.property.back_populates == "project"
    assert ScriptVersion.segments.property.back_populates == "script_version"
    assert StoryboardVersion.scenes.property.back_populates == "storyboard_version"
    assert GenerationJob.workflow_snapshots.property.back_populates == "job"
    assert Asset.project.property.back_populates == "assets"
    assert OutputVersion.project.property.back_populates == "output_versions"
    assert ActivityEvent.project.property.back_populates == "activity_events"
