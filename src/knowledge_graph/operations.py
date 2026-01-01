"""Knowledge Graph operations for upserting nodes and relationships."""

from datetime import datetime
from typing import Any

from src.common.logging import get_logger
from src.common.models import (
    Story,
    Scene,
    Shot,
    ShotPlan,
    Character,
    Location,
    Event,
    FeedbackAnnotation,
)
from src.knowledge_graph.client import Neo4jClient

logger = get_logger(__name__)


# =============================================================================
# Story Operations
# =============================================================================


async def upsert_story(client: Neo4jClient, story: Story) -> dict:
    """Upsert a Story node."""
    query = """
    MERGE (s:Story {id: $id})
    SET s.title = $title,
        s.source_type = $source_type,
        s.status = $status,
        s.total_scenes = $total_scenes,
        s.total_characters = $total_characters,
        s.total_locations = $total_locations,
        s.estimated_duration_minutes = $estimated_duration_minutes,
        s.raw_text = $raw_text,
        s.created_at = $created_at,
        s.updated_at = $updated_at,
        s.version = $version,
        s.source_metadata = $source_metadata
    RETURN s.id as id
    """

    params = {
        "id": story.id,
        "title": story.title,
        "source_type": story.source_type.value,
        "status": story.status.value,
        "total_scenes": story.total_scenes,
        "total_characters": story.total_characters,
        "total_locations": story.total_locations,
        "estimated_duration_minutes": story.estimated_duration_minutes,
        "raw_text": story.raw_text[:10000] if story.raw_text else "",  # Truncate
        "created_at": story.created_at.isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "version": story.version,
        "source_metadata": story.source_metadata.model_dump_json(),
    }

    result = await client.execute_query(query, params)
    logger.info("story_upserted", story_id=story.id)
    return {"id": story.id, "action": "upsert"}


# =============================================================================
# Scene Operations
# =============================================================================


async def upsert_scene(client: Neo4jClient, scene: Scene) -> dict:
    """Upsert a Scene node and link to Story."""
    # Upsert scene node
    query = """
    MERGE (sc:Scene {id: $id})
    SET sc.story_id = $story_id,
        sc.sequence = $sequence,
        sc.raw_text = $raw_text,
        sc.summary = $summary,
        sc.word_count = $word_count,
        sc.estimated_duration_seconds = $estimated_duration_seconds,
        sc.complexity_score = $complexity_score,
        sc.continuity_score = $continuity_score,
        sc.has_shot_plan = $has_shot_plan,
        sc.shot_plan_id = $shot_plan_id,
        sc.setting = $setting,
        sc.emotional_beat = $emotional_beat,
        sc.created_at = $created_at,
        sc.updated_at = $updated_at
    WITH sc
    MATCH (s:Story {id: $story_id})
    MERGE (s)-[:HAS_SCENE]->(sc)
    RETURN sc.id as id
    """

    params = {
        "id": scene.id,
        "story_id": scene.story_id,
        "sequence": scene.sequence,
        "raw_text": scene.raw_text[:5000] if scene.raw_text else "",
        "summary": scene.summary,
        "word_count": scene.word_count,
        "estimated_duration_seconds": scene.estimated_duration_seconds,
        "complexity_score": scene.complexity_score,
        "continuity_score": scene.continuity_score,
        "has_shot_plan": scene.has_shot_plan,
        "shot_plan_id": scene.shot_plan_id,
        "setting": scene.setting.model_dump_json(),
        "emotional_beat": scene.emotional_beat.model_dump_json(),
        "created_at": scene.created_at.isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    await client.execute_query(query, params)
    logger.info("scene_upserted", scene_id=scene.id, story_id=scene.story_id)
    return {"id": scene.id, "action": "upsert"}


async def link_scene_sequence(
    client: Neo4jClient,
    story_id: str,
) -> dict:
    """Create NEXT_SCENE relationships between scenes in order."""
    query = """
    MATCH (s:Story {id: $story_id})-[:HAS_SCENE]->(sc:Scene)
    WITH sc ORDER BY sc.sequence
    WITH collect(sc) as scenes
    UNWIND range(0, size(scenes)-2) as i
    WITH scenes[i] as current, scenes[i+1] as next
    MERGE (current)-[:NEXT_SCENE]->(next)
    RETURN count(*) as links_created
    """

    result = await client.execute_query(query, {"story_id": story_id})
    links = result[0]["links_created"] if result else 0
    logger.info("scene_sequence_linked", story_id=story_id, links=links)
    return {"links_created": links}


# =============================================================================
# Shot Operations
# =============================================================================


async def upsert_shot_plan(client: Neo4jClient, shot_plan: ShotPlan) -> dict:
    """Upsert a ShotPlan node and link to Scene."""
    query = """
    MERGE (sp:ShotPlan {id: $id})
    SET sp.scene_id = $scene_id,
        sp.version = $version,
        sp.status = $status,
        sp.estimated_duration_seconds = $estimated_duration_seconds,
        sp.complexity_score = $complexity_score,
        sp.creative_direction = $creative_direction,
        sp.pacing_rationale = $pacing_rationale,
        sp.created_at = $created_at
    WITH sp
    MATCH (sc:Scene {id: $scene_id})
    MERGE (sc)-[:HAS_SHOT_PLAN]->(sp)
    RETURN sp.id as id
    """

    params = {
        "id": shot_plan.id,
        "scene_id": shot_plan.scene_id,
        "version": shot_plan.version,
        "status": shot_plan.status.value,
        "estimated_duration_seconds": shot_plan.estimated_duration_seconds,
        "complexity_score": shot_plan.complexity_score,
        "creative_direction": shot_plan.creative_direction,
        "pacing_rationale": shot_plan.pacing_rationale,
        "created_at": shot_plan.created_at.isoformat(),
    }

    await client.execute_query(query, params)
    logger.info("shot_plan_upserted", plan_id=shot_plan.id)
    return {"id": shot_plan.id, "action": "upsert"}


async def upsert_shot(client: Neo4jClient, shot: Shot) -> dict:
    """Upsert a Shot node and link to ShotPlan."""
    query = """
    MERGE (sh:Shot {id: $id})
    SET sh.shot_plan_id = $shot_plan_id,
        sh.sequence = $sequence,
        sh.shot_type = $shot_type,
        sh.duration_seconds = $duration_seconds,
        sh.subject = $subject,
        sh.mood = $mood,
        sh.lighting = $lighting,
        sh.narration_text = $narration_text,
        sh.visual_description = $visual_description,
        sh.image_prompt = $image_prompt,
        sh.composition = $composition,
        sh.motion = $motion
    WITH sh
    MATCH (sp:ShotPlan {id: $shot_plan_id})
    MERGE (sp)-[:HAS_SHOT]->(sh)
    RETURN sh.id as id
    """

    params = {
        "id": shot.id,
        "shot_plan_id": shot.shot_plan_id,
        "sequence": shot.sequence,
        "shot_type": shot.shot_type.value,
        "duration_seconds": shot.duration_seconds,
        "subject": shot.subject,
        "mood": shot.mood,
        "lighting": shot.lighting,
        "narration_text": shot.narration_text or "",
        "visual_description": shot.visual_description,
        "image_prompt": shot.image_prompt or "",
        "composition": shot.composition.model_dump_json(),
        "motion": shot.motion.model_dump_json(),
    }

    await client.execute_query(query, params)
    logger.info("shot_upserted", shot_id=shot.id)
    return {"id": shot.id, "action": "upsert"}


async def link_shot_sequence(
    client: Neo4jClient,
    shot_plan_id: str,
) -> dict:
    """Create NEXT_SHOT relationships between shots in order."""
    query = """
    MATCH (sp:ShotPlan {id: $shot_plan_id})-[:HAS_SHOT]->(sh:Shot)
    WITH sh ORDER BY sh.sequence
    WITH collect(sh) as shots
    UNWIND range(0, size(shots)-2) as i
    WITH shots[i] as current, shots[i+1] as next
    MERGE (current)-[:NEXT_SHOT]->(next)
    RETURN count(*) as links_created
    """

    result = await client.execute_query(query, {"shot_plan_id": shot_plan_id})
    links = result[0]["links_created"] if result else 0
    return {"links_created": links}


# =============================================================================
# Character Operations
# =============================================================================


async def upsert_character(client: Neo4jClient, character: Character) -> dict:
    """Upsert a Character node and link to Story."""
    query = """
    MERGE (c:Character {id: $id})
    SET c.story_id = $story_id,
        c.name = $name,
        c.physical_description = $physical_description,
        c.role = $role,
        c.importance = $importance,
        c.visual_prompt = $visual_prompt,
        c.introduction_scene_id = $introduction_scene_id,
        c.created_at = $created_at
    WITH c
    MATCH (s:Story {id: $story_id})
    MERGE (s)-[:HAS_CHARACTER]->(c)
    RETURN c.id as id
    """

    params = {
        "id": character.id,
        "story_id": character.story_id,
        "name": character.name,
        "physical_description": character.physical_description,
        "role": character.role.value,
        "importance": character.importance.value,
        "visual_prompt": character.visual_prompt,
        "introduction_scene_id": character.introduction_scene_id,
        "created_at": character.created_at.isoformat(),
    }

    await client.execute_query(query, params)
    return {"id": character.id, "action": "upsert"}


async def link_character_to_scene(
    client: Neo4jClient,
    character_id: str,
    scene_id: str,
) -> dict:
    """Create APPEARS_IN relationship between Character and Scene."""
    query = """
    MATCH (c:Character {id: $character_id})
    MATCH (sc:Scene {id: $scene_id})
    MERGE (c)-[:APPEARS_IN]->(sc)
    RETURN c.id as character_id, sc.id as scene_id
    """

    await client.execute_query(query, {
        "character_id": character_id,
        "scene_id": scene_id,
    })
    return {"linked": True}


# =============================================================================
# Location Operations
# =============================================================================


async def upsert_location(client: Neo4jClient, location: Location) -> dict:
    """Upsert a Location node and link to Story."""
    query = """
    MERGE (l:Location {id: $id})
    SET l.story_id = $story_id,
        l.name = $name,
        l.description = $description,
        l.era = $era,
        l.location_type = $location_type,
        l.visual_prompt = $visual_prompt,
        l.created_at = $created_at
    WITH l
    MATCH (s:Story {id: $story_id})
    MERGE (s)-[:HAS_LOCATION]->(l)
    RETURN l.id as id
    """

    params = {
        "id": location.id,
        "story_id": location.story_id,
        "name": location.name,
        "description": location.description,
        "era": location.era,
        "location_type": location.location_type.value,
        "visual_prompt": location.visual_prompt,
        "created_at": location.created_at.isoformat(),
    }

    await client.execute_query(query, params)
    return {"id": location.id, "action": "upsert"}


# =============================================================================
# Feedback Operations
# =============================================================================


async def upsert_feedback(
    client: Neo4jClient,
    feedback: FeedbackAnnotation,
) -> dict:
    """Upsert a FeedbackAnnotation node and link to target."""
    query = """
    MERGE (f:FeedbackAnnotation {id: $id})
    SET f.source = $source,
        f.reviewer_id = $reviewer_id,
        f.target_type = $target_type,
        f.target_id = $target_id,
        f.overall_score = $overall_score,
        f.recommendation = $recommendation,
        f.dimension_scores = $dimension_scores,
        f.taxonomy_labels = $taxonomy_labels,
        f.issues = $issues,
        f.strengths = $strengths,
        f.fix_requests = $fix_requests,
        f.created_at = $created_at
    RETURN f.id as id
    """

    params = {
        "id": feedback.id,
        "source": feedback.source.value,
        "reviewer_id": feedback.reviewer_id,
        "target_type": feedback.target_type.value,
        "target_id": feedback.target_id,
        "overall_score": feedback.overall_score,
        "recommendation": feedback.recommendation.value,
        "dimension_scores": feedback.dimension_scores.model_dump_json(),
        "taxonomy_labels": feedback.taxonomy_labels,
        "issues": [i.model_dump_json() for i in feedback.issues],
        "strengths": feedback.strengths,
        "fix_requests": [f.model_dump_json() for f in feedback.fix_requests],
        "created_at": feedback.created_at.isoformat(),
    }

    await client.execute_query(query, params)

    # Link to target based on target_type
    link_query = f"""
    MATCH (f:FeedbackAnnotation {{id: $feedback_id}})
    MATCH (t:{feedback.target_type.value.title()} {{id: $target_id}})
    MERGE (f)-[:TARGETS]->(t)
    """

    try:
        await client.execute_query(link_query, {
            "feedback_id": feedback.id,
            "target_id": feedback.target_id,
        })
    except Exception as e:
        logger.warning("feedback_link_failed", error=str(e))

    logger.info("feedback_upserted", feedback_id=feedback.id)
    return {"id": feedback.id, "action": "upsert"}


# =============================================================================
# Query Operations
# =============================================================================


async def get_story_with_scenes(
    client: Neo4jClient,
    story_id: str,
) -> dict | None:
    """Get a story with all its scenes."""
    query = """
    MATCH (s:Story {id: $story_id})
    OPTIONAL MATCH (s)-[:HAS_SCENE]->(sc:Scene)
    WITH s, sc ORDER BY sc.sequence
    RETURN s as story, collect(sc) as scenes
    """

    result = await client.execute_query(query, {"story_id": story_id})
    if not result:
        return None

    return {
        "story": dict(result[0]["story"]) if result[0]["story"] else None,
        "scenes": [dict(sc) for sc in result[0]["scenes"]],
    }


async def get_scene_with_shots(
    client: Neo4jClient,
    scene_id: str,
) -> dict | None:
    """Get a scene with its shot plan and shots."""
    query = """
    MATCH (sc:Scene {id: $scene_id})
    OPTIONAL MATCH (sc)-[:HAS_SHOT_PLAN]->(sp:ShotPlan)
    OPTIONAL MATCH (sp)-[:HAS_SHOT]->(sh:Shot)
    WITH sc, sp, sh ORDER BY sh.sequence
    RETURN sc as scene, sp as shot_plan, collect(sh) as shots
    """

    result = await client.execute_query(query, {"scene_id": scene_id})
    if not result:
        return None

    return {
        "scene": dict(result[0]["scene"]) if result[0]["scene"] else None,
        "shot_plan": dict(result[0]["shot_plan"]) if result[0]["shot_plan"] else None,
        "shots": [dict(sh) for sh in result[0]["shots"]],
    }


async def get_feedback_for_target(
    client: Neo4jClient,
    target_type: str,
    target_id: str,
) -> list[dict]:
    """Get all feedback for a target."""
    query = """
    MATCH (f:FeedbackAnnotation {target_type: $target_type, target_id: $target_id})
    RETURN f
    ORDER BY f.created_at DESC
    """

    result = await client.execute_query(query, {
        "target_type": target_type,
        "target_id": target_id,
    })

    return [dict(r["f"]) for r in result]
