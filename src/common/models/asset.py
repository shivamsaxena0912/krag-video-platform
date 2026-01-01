"""Asset models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.common.models.base import generate_id


class AssetType(str, Enum):
    """Type of generated asset."""

    IMAGE = "image"
    VOICEOVER = "voiceover"
    MUSIC = "music"
    SFX = "sfx"
    AMBIENT = "ambient"
    VIDEO_CLIP = "video_clip"


class Asset(BaseModel):
    """A generated asset."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("asset"))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Type and source
    asset_type: AssetType
    shot_id: str
    scene_id: str

    # Storage
    file_path: str
    file_size_bytes: int = 0
    mime_type: str = ""
    checksum: str = ""

    # Generation
    generation_model: str = ""
    generation_params: dict = Field(default_factory=dict)
    generation_prompt: str | None = None
    generation_time_seconds: float = 0.0
    generation_cost: float = 0.0

    # Quality
    quality_score: float = Field(ge=0, le=1, default=0.0)
    quality_notes: list[str] = Field(default_factory=list)

    # Usage
    used_in_video_ids: list[str] = Field(default_factory=list)

    def summary(self) -> dict:
        """Return summary for logging."""
        return {
            "id": self.id,
            "type": self.asset_type.value,
            "shot_id": self.shot_id,
            "quality": self.quality_score,
            "cost": self.generation_cost,
        }
