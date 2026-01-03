"""Pipeline execution models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.common.models.base import generate_id


class PipelineStatus(str, Enum):
    """Status of pipeline execution."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(str, Enum):
    """Stage of pipeline execution."""

    INGESTION = "ingestion"
    PARSING = "parsing"
    SCENE_GRAPH = "scene_graph"
    CONTINUITY = "continuity"
    KRAG_RETRIEVAL = "krag_retrieval"
    SHOT_PLANNING = "shot_planning"
    PROMPT_ENGINEERING = "prompt_engineering"
    ASSET_GENERATION = "asset_generation"
    ASSEMBLY = "assembly"
    CRITIQUE = "critique"
    REFINEMENT = "refinement"
    HUMAN_REVIEW = "human_review"
    FINALIZATION = "finalization"


class CostBreakdown(BaseModel):
    """Cost tracking for a pipeline run."""

    model_config = ConfigDict(frozen=True)

    total_cost: float = 0.0
    llm_cost: float = 0.0
    image_generation_cost: float = 0.0
    voice_synthesis_cost: float = 0.0
    music_cost: float = 0.0
    storage_cost: float = 0.0
    compute_cost: float = 0.0

    def add(self, other: "CostBreakdown") -> "CostBreakdown":
        """Add two cost breakdowns."""
        return CostBreakdown(
            total_cost=self.total_cost + other.total_cost,
            llm_cost=self.llm_cost + other.llm_cost,
            image_generation_cost=self.image_generation_cost
            + other.image_generation_cost,
            voice_synthesis_cost=self.voice_synthesis_cost
            + other.voice_synthesis_cost,
            music_cost=self.music_cost + other.music_cost,
            storage_cost=self.storage_cost + other.storage_cost,
            compute_cost=self.compute_cost + other.compute_cost,
        )


class PipelineError(BaseModel):
    """An error during pipeline execution."""

    model_config = ConfigDict(frozen=True)

    stage: PipelineStage
    error_type: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    recoverable: bool = True
    stack_trace: str | None = None


class PipelineConfig(BaseModel):
    """Configuration for a pipeline run."""

    model_config = ConfigDict(frozen=True)

    # Cost controls
    max_cost: float = 50.0
    max_iterations: int = 3
    quality_threshold: float = 7.0

    # Parallelism
    max_parallel_scenes: int = 3
    max_parallel_assets: int = 5

    # Timeouts
    stage_timeout_seconds: int = 600
    total_timeout_seconds: int = 3600

    # Quality
    require_human_review: bool = True
    auto_approve_threshold: float = 8.5


class PipelineRun(BaseModel):
    """State of a pipeline execution."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("run"))
    story_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Configuration
    config: PipelineConfig = Field(default_factory=PipelineConfig)

    # Status
    status: PipelineStatus = PipelineStatus.PENDING
    current_stage: PipelineStage = PipelineStage.INGESTION
    progress_percent: float = Field(ge=0, le=100, default=0.0)

    # Stage outputs
    stage_outputs: dict[str, Any] = Field(default_factory=dict)

    # Costs
    costs: CostBreakdown = Field(default_factory=CostBreakdown)

    # Iteration
    refinement_iterations: int = 0

    # Results
    output_video_path: str | None = None
    final_quality_score: float | None = None

    # Error handling
    errors: list[PipelineError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def summary(self) -> dict:
        """Return summary for logging."""
        return {
            "id": self.id,
            "story_id": self.story_id,
            "status": self.status.value,
            "stage": self.current_stage.value,
            "progress": self.progress_percent,
            "cost": self.costs.total_cost,
            "iterations": self.refinement_iterations,
        }

    def with_stage_output(
        self, stage: PipelineStage, output: Any
    ) -> "PipelineRun":
        """Return a copy with stage output added."""
        new_outputs = dict(self.stage_outputs)
        new_outputs[stage.value] = output
        return self.model_copy(
            update={
                "stage_outputs": new_outputs,
                "updated_at": datetime.utcnow(),
            }
        )

    def with_error(self, error: PipelineError) -> "PipelineRun":
        """Return a copy with error added."""
        return self.model_copy(
            update={
                "errors": [*self.errors, error],
                "status": PipelineStatus.FAILED if not error.recoverable else self.status,
                "updated_at": datetime.utcnow(),
            }
        )
