"""SceneGraph model and ingestion utilities."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.common.logging import get_logger
from src.common.models import (
    Story,
    Scene,
    Character,
    Location,
    Event,
    ShotPlan,
    Shot,
)
from src.knowledge_graph.client import Neo4jClient
from src.knowledge_graph.operations import (
    upsert_story,
    upsert_scene,
    upsert_character,
    upsert_location,
    upsert_shot_plan,
    upsert_shot,
    link_scene_sequence,
    link_shot_sequence,
    link_character_to_scene,
)

logger = get_logger(__name__)


class SceneGraph(BaseModel):
    """Complete scene graph representation for a story."""

    story: Story
    scenes: list[Scene] = Field(default_factory=list)
    characters: list[Character] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    shot_plans: list[ShotPlan] = Field(default_factory=list)
    shots: list[Shot] = Field(default_factory=list)

    # Relationships (scene_id -> list of character_ids)
    character_appearances: dict[str, list[str]] = Field(default_factory=dict)
    # Relationships (scene_id -> list of location_ids)
    location_usages: dict[str, list[str]] = Field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SceneGraph":
        """Create SceneGraph from JSON data."""
        return cls.model_validate(data)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SceneGraph":
        """Load SceneGraph from a JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return cls.from_json(data)

    def to_json(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return self.model_dump(mode="json")

    def to_json_file(self, path: str | Path) -> None:
        """Save SceneGraph to a JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_json(), f, indent=2, default=str)

    def summary(self) -> dict[str, Any]:
        """Return a summary of the scene graph."""
        return {
            "story_id": self.story.id,
            "story_title": self.story.title,
            "scenes": len(self.scenes),
            "characters": len(self.characters),
            "locations": len(self.locations),
            "events": len(self.events),
            "shot_plans": len(self.shot_plans),
            "shots": len(self.shots),
        }


async def ingest_scene_graph(
    client: Neo4jClient,
    scene_graph: SceneGraph,
) -> dict[str, Any]:
    """Ingest a complete SceneGraph into Neo4j."""
    results = {
        "story": None,
        "scenes": 0,
        "characters": 0,
        "locations": 0,
        "events": 0,
        "shot_plans": 0,
        "shots": 0,
        "relationships": 0,
        "errors": [],
    }

    try:
        # 1. Upsert Story
        await upsert_story(client, scene_graph.story)
        results["story"] = scene_graph.story.id
        logger.info("ingested_story", story_id=scene_graph.story.id)

        # 2. Upsert Characters
        for character in scene_graph.characters:
            await upsert_character(client, character)
            results["characters"] += 1

        # 3. Upsert Locations
        for location in scene_graph.locations:
            await upsert_location(client, location)
            results["locations"] += 1

        # 4. Upsert Scenes
        for scene in scene_graph.scenes:
            await upsert_scene(client, scene)
            results["scenes"] += 1

        # 5. Link scene sequence
        if scene_graph.scenes:
            link_result = await link_scene_sequence(client, scene_graph.story.id)
            results["relationships"] += link_result.get("links_created", 0)

        # 6. Link characters to scenes
        for scene_id, char_ids in scene_graph.character_appearances.items():
            for char_id in char_ids:
                await link_character_to_scene(client, char_id, scene_id)
                results["relationships"] += 1

        # 7. Upsert Shot Plans
        for shot_plan in scene_graph.shot_plans:
            await upsert_shot_plan(client, shot_plan)
            results["shot_plans"] += 1

        # 8. Upsert Shots
        for shot in scene_graph.shots:
            await upsert_shot(client, shot)
            results["shots"] += 1

        # 9. Link shot sequences
        for shot_plan in scene_graph.shot_plans:
            link_result = await link_shot_sequence(client, shot_plan.id)
            results["relationships"] += link_result.get("links_created", 0)

        logger.info(
            "scene_graph_ingested",
            story_id=scene_graph.story.id,
            scenes=results["scenes"],
            shots=results["shots"],
        )

    except Exception as e:
        results["errors"].append(str(e))
        logger.error("scene_graph_ingestion_error", error=str(e))
        raise

    return results
