"""Knowledge Graph module for Neo4j operations."""

from src.knowledge_graph.client import (
    Neo4jClient,
    get_neo4j_client,
    init_neo4j,
    close_neo4j,
)
from src.knowledge_graph.schema import (
    apply_schema,
    verify_schema,
    clear_database,
    SCHEMA_VERSION,
)
from src.knowledge_graph.operations import (
    upsert_story,
    upsert_scene,
    upsert_shot_plan,
    upsert_shot,
    upsert_character,
    upsert_location,
    upsert_feedback,
    link_scene_sequence,
    link_shot_sequence,
    link_character_to_scene,
    get_story_with_scenes,
    get_scene_with_shots,
    get_feedback_for_target,
)
from src.knowledge_graph.scene_graph import (
    SceneGraph,
    ingest_scene_graph,
)

__all__ = [
    # Client
    "Neo4jClient",
    "get_neo4j_client",
    "init_neo4j",
    "close_neo4j",
    # Schema
    "apply_schema",
    "verify_schema",
    "clear_database",
    "SCHEMA_VERSION",
    # Operations
    "upsert_story",
    "upsert_scene",
    "upsert_shot_plan",
    "upsert_shot",
    "upsert_character",
    "upsert_location",
    "upsert_feedback",
    "link_scene_sequence",
    "link_shot_sequence",
    "link_character_to_scene",
    "get_story_with_scenes",
    "get_scene_with_shots",
    "get_feedback_for_target",
    # Scene Graph
    "SceneGraph",
    "ingest_scene_graph",
]
