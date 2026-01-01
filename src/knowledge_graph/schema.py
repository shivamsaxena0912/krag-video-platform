"""Neo4j schema definitions, constraints, and migrations."""

from src.common.logging import get_logger
from src.knowledge_graph.client import Neo4jClient

logger = get_logger(__name__)

# =============================================================================
# Schema Version
# =============================================================================

SCHEMA_VERSION = "1.0.0"

# =============================================================================
# Constraints (Uniqueness)
# =============================================================================

CONSTRAINTS = [
    # Story
    "CREATE CONSTRAINT story_id IF NOT EXISTS FOR (s:Story) REQUIRE s.id IS UNIQUE",
    # Scene
    "CREATE CONSTRAINT scene_id IF NOT EXISTS FOR (sc:Scene) REQUIRE sc.id IS UNIQUE",
    # Shot
    "CREATE CONSTRAINT shot_id IF NOT EXISTS FOR (sh:Shot) REQUIRE sh.id IS UNIQUE",
    # Character
    "CREATE CONSTRAINT character_id IF NOT EXISTS FOR (c:Character) REQUIRE c.id IS UNIQUE",
    # Location
    "CREATE CONSTRAINT location_id IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE",
    # Event
    "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
    # Asset
    "CREATE CONSTRAINT asset_id IF NOT EXISTS FOR (a:Asset) REQUIRE a.id IS UNIQUE",
    # Feedback
    "CREATE CONSTRAINT feedback_id IF NOT EXISTS FOR (f:FeedbackAnnotation) REQUIRE f.id IS UNIQUE",
    # ShotPlan
    "CREATE CONSTRAINT shot_plan_id IF NOT EXISTS FOR (sp:ShotPlan) REQUIRE sp.id IS UNIQUE",
]

# =============================================================================
# Indexes (Performance)
# =============================================================================

INDEXES = [
    # Story lookups
    "CREATE INDEX story_status IF NOT EXISTS FOR (s:Story) ON (s.status)",
    "CREATE INDEX story_title IF NOT EXISTS FOR (s:Story) ON (s.title)",
    # Scene lookups
    "CREATE INDEX scene_story IF NOT EXISTS FOR (sc:Scene) ON (sc.story_id)",
    "CREATE INDEX scene_sequence IF NOT EXISTS FOR (sc:Scene) ON (sc.sequence)",
    # Shot lookups
    "CREATE INDEX shot_plan IF NOT EXISTS FOR (sh:Shot) ON (sh.shot_plan_id)",
    "CREATE INDEX shot_sequence IF NOT EXISTS FOR (sh:Shot) ON (sh.sequence)",
    # Character lookups
    "CREATE INDEX character_story IF NOT EXISTS FOR (c:Character) ON (c.story_id)",
    "CREATE INDEX character_name IF NOT EXISTS FOR (c:Character) ON (c.name)",
    # Location lookups
    "CREATE INDEX location_story IF NOT EXISTS FOR (l:Location) ON (l.story_id)",
    # Event lookups
    "CREATE INDEX event_story IF NOT EXISTS FOR (e:Event) ON (e.story_id)",
    "CREATE INDEX event_scene IF NOT EXISTS FOR (e:Event) ON (e.scene_id)",
    # Feedback lookups
    "CREATE INDEX feedback_target IF NOT EXISTS FOR (f:FeedbackAnnotation) ON (f.target_type, f.target_id)",
    "CREATE INDEX feedback_source IF NOT EXISTS FOR (f:FeedbackAnnotation) ON (f.source)",
]

# =============================================================================
# Full-text indexes for search
# =============================================================================

FULLTEXT_INDEXES = [
    # Scene content search
    """
    CREATE FULLTEXT INDEX scene_content IF NOT EXISTS
    FOR (sc:Scene) ON EACH [sc.raw_text, sc.summary]
    """,
    # Character search
    """
    CREATE FULLTEXT INDEX character_content IF NOT EXISTS
    FOR (c:Character) ON EACH [c.name, c.physical_description]
    """,
]


async def apply_schema(client: Neo4jClient) -> dict:
    """Apply all schema constraints and indexes."""
    results = {
        "constraints_applied": 0,
        "indexes_applied": 0,
        "errors": [],
    }

    # Apply constraints
    for constraint in CONSTRAINTS:
        try:
            await client.execute_write(constraint)
            results["constraints_applied"] += 1
            logger.debug("constraint_applied", query=constraint[:50])
        except Exception as e:
            if "already exists" not in str(e).lower():
                results["errors"].append(f"Constraint error: {e}")
                logger.warning("constraint_error", error=str(e))

    # Apply indexes
    for index in INDEXES:
        try:
            await client.execute_write(index)
            results["indexes_applied"] += 1
            logger.debug("index_applied", query=index[:50])
        except Exception as e:
            if "already exists" not in str(e).lower():
                results["errors"].append(f"Index error: {e}")
                logger.warning("index_error", error=str(e))

    # Apply fulltext indexes
    for ft_index in FULLTEXT_INDEXES:
        try:
            await client.execute_write(ft_index)
            results["indexes_applied"] += 1
            logger.debug("fulltext_index_applied")
        except Exception as e:
            if "already exists" not in str(e).lower():
                results["errors"].append(f"Fulltext index error: {e}")
                logger.warning("fulltext_index_error", error=str(e))

    logger.info(
        "schema_applied",
        constraints=results["constraints_applied"],
        indexes=results["indexes_applied"],
        errors=len(results["errors"]),
    )

    return results


async def verify_schema(client: Neo4jClient) -> dict:
    """Verify schema is properly applied."""
    # Get existing constraints
    constraints = await client.execute_query(
        "SHOW CONSTRAINTS YIELD name RETURN collect(name) as names"
    )

    # Get existing indexes
    indexes = await client.execute_query(
        "SHOW INDEXES YIELD name RETURN collect(name) as names"
    )

    return {
        "constraints": constraints[0]["names"] if constraints else [],
        "indexes": indexes[0]["names"] if indexes else [],
    }


async def clear_database(client: Neo4jClient, confirm: bool = False) -> dict:
    """Clear all data from the database. USE WITH CAUTION."""
    if not confirm:
        raise ValueError("Must set confirm=True to clear database")

    logger.warning("clearing_database")

    result = await client.execute_write(
        "MATCH (n) DETACH DELETE n"
    )

    logger.info("database_cleared", nodes_deleted=result["nodes_deleted"])
    return result
