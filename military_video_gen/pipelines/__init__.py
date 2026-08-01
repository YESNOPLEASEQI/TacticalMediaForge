"""
MilitaryVideoGen Pipelines

Video generation pipelines with different strategies and workflows.
Each pipeline implements a specific video generation approach.
"""

from military_video_gen.pipelines.asset_based import AssetBasedPipeline
from military_video_gen.pipelines.base import BasePipeline
from military_video_gen.pipelines.custom import CustomPipeline
from military_video_gen.pipelines.linear import LinearVideoPipeline, PipelineContext
from military_video_gen.pipelines.standard import StandardPipeline

__all__ = [
    "BasePipeline",
    "LinearVideoPipeline",
    "PipelineContext",
    "StandardPipeline",
    "CustomPipeline",
    "AssetBasedPipeline",
]

