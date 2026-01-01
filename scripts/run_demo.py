#!/usr/bin/env python3
"""
KRAG Video Platform Demo Script

This script demonstrates the full pipeline:
1. Parse example story into SceneGraph
2. Ingest SceneGraph into Neo4j
3. Index scenes and shots into Qdrant
4. Evaluate with Critic Agent
5. Store feedback in Neo4j

Usage:
    python scripts/run_demo.py

Prerequisites:
    docker-compose up -d
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents import StoryParserAgent, StoryParserInput, CriticAgent, CriticInput
from src.knowledge_graph import (
    Neo4jClient,
    apply_schema,
    ingest_scene_graph,
    upsert_feedback,
    get_story_with_scenes,
)
from src.rag import (
    QdrantVectorClient,
    get_embedding_provider,
    ensure_collections,
    index_scenes,
    index_shots,
)
from src.common.logging import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


async def check_services() -> bool:
    """Check if required services are running."""
    print("\n🔍 Checking services...")

    # Check Neo4j
    neo4j = Neo4jClient()
    try:
        await neo4j.connect()
        neo4j_ok = await neo4j.health_check()
        await neo4j.close()
        print(f"  ✅ Neo4j: {'Connected' if neo4j_ok else 'Failed'}")
    except Exception as e:
        print(f"  ❌ Neo4j: {e}")
        neo4j_ok = False

    # Check Qdrant
    qdrant = QdrantVectorClient()
    try:
        await qdrant.connect()
        qdrant_ok = await qdrant.health_check()
        await qdrant.close()
        print(f"  ✅ Qdrant: {'Connected' if qdrant_ok else 'Failed'}")
    except Exception as e:
        print(f"  ❌ Qdrant: {e}")
        qdrant_ok = False

    return neo4j_ok and qdrant_ok


async def run_demo():
    """Run the full demo pipeline."""
    print("\n" + "=" * 60)
    print("🎬 KRAG Video Platform Demo")
    print("=" * 60)

    # Check services
    services_ok = await check_services()
    if not services_ok:
        print("\n❌ Required services are not running.")
        print("   Please run: docker-compose up -d")
        return False

    # Load example story
    story_path = Path(__file__).parent.parent / "examples" / "story_001.txt"
    if not story_path.exists():
        print(f"\n❌ Example story not found: {story_path}")
        return False

    story_text = story_path.read_text()
    print(f"\n📖 Loaded story: {story_path.name}")
    print(f"   Length: {len(story_text)} characters")

    # Initialize clients
    neo4j = Neo4jClient()
    qdrant = QdrantVectorClient()
    embedder = get_embedding_provider("stub", dimension=384)

    try:
        await neo4j.connect()
        await qdrant.connect()

        # Step 1: Apply Neo4j schema
        print("\n📊 Step 1: Applying Neo4j schema...")
        schema_result = await apply_schema(neo4j)
        print(f"   Constraints: {schema_result['constraints_applied']}")
        print(f"   Indexes: {schema_result['indexes_applied']}")

        # Step 2: Ensure Qdrant collections
        print("\n📊 Step 2: Ensuring Qdrant collections...")
        await ensure_collections(qdrant, embedder.dimension)
        print("   Collections ready")

        # Step 3: Parse story
        print("\n🔍 Step 3: Parsing story with StoryParserAgent...")
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=story_text,
            title="The Fall of Rome: A Documentary Narrative",
            author="KRAG Demo",
            era="Ancient Rome",
        ))

        scene_graph = parse_result.scene_graph
        print(f"   Story ID: {scene_graph.story.id}")
        print(f"   Scenes: {len(scene_graph.scenes)}")
        print(f"   Characters: {len(scene_graph.characters)}")
        print(f"   Locations: {len(scene_graph.locations)}")
        print(f"   Shot Plans: {len(scene_graph.shot_plans)}")
        print(f"   Shots: {len(scene_graph.shots)}")

        # Step 4: Ingest into Neo4j
        print("\n💾 Step 4: Ingesting SceneGraph into Neo4j...")
        ingest_result = await ingest_scene_graph(neo4j, scene_graph)
        print(f"   Scenes stored: {ingest_result['scenes']}")
        print(f"   Characters stored: {ingest_result['characters']}")
        print(f"   Relationships: {ingest_result['relationships']}")

        # Step 5: Index into Qdrant
        print("\n🔎 Step 5: Indexing into Qdrant...")
        scene_result = await index_scenes(
            qdrant, embedder, scene_graph.scenes, scene_graph.story.id
        )
        print(f"   Scenes indexed: {scene_result['indexed']}")

        total_shots_indexed = 0
        for scene in scene_graph.scenes:
            scene_shots = [
                s for s in scene_graph.shots
                if s.shot_plan_id.endswith(scene.id[6:])
            ]
            if scene_shots:
                shot_result = await index_shots(
                    qdrant, embedder, scene_shots, scene.id, scene_graph.story.id
                )
                total_shots_indexed += shot_result["indexed"]
        print(f"   Shots indexed: {total_shots_indexed}")

        # Step 6: Evaluate with Critic
        print("\n🎯 Step 6: Evaluating with CriticAgent...")
        critic = CriticAgent()
        critic_result = await critic(CriticInput(scene_graph=scene_graph))

        story_fb = critic_result.story_feedback
        print(f"   Overall Score: {story_fb.overall_score}/10")
        print(f"   Recommendation: {story_fb.recommendation.value}")
        print(f"   Strengths: {len(story_fb.strengths)}")
        print(f"   Issues: {len(story_fb.issues)}")

        # Print dimension scores
        scores = story_fb.dimension_scores
        print("\n   Dimension Scores:")
        print(f"     Narrative Clarity: {scores.narrative_clarity}/5")
        print(f"     Hook Strength: {scores.hook_strength}/5")
        print(f"     Pacing: {scores.pacing}/5")
        print(f"     Shot Composition: {scores.shot_composition}/5")
        print(f"     Continuity: {scores.continuity}/5")
        print(f"     Audio Mix: {scores.audio_mix}/5")

        # Step 7: Store feedback
        print("\n💾 Step 7: Storing feedback in Neo4j...")
        await upsert_feedback(neo4j, story_fb)
        for scene_fb in critic_result.scene_feedbacks:
            await upsert_feedback(neo4j, scene_fb)
        print(f"   Feedback stored: {1 + len(critic_result.scene_feedbacks)} annotations")

        # Save SceneGraph JSON
        output_dir = Path(__file__).parent.parent / "outputs"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"{scene_graph.story.id}.json"
        scene_graph.to_json_file(output_path)
        print(f"\n📁 SceneGraph saved: {output_path}")

        # Summary
        print("\n" + "=" * 60)
        print("✅ Demo Complete!")
        print("=" * 60)
        print(f"\nSummary:")
        print(f"  Story: {scene_graph.story.title}")
        print(f"  Scenes: {len(scene_graph.scenes)}")
        print(f"  Total Shots: {len(scene_graph.shots)}")
        print(f"  Quality Score: {story_fb.overall_score}/10")
        print(f"  Recommendation: {story_fb.recommendation.value}")

        print(f"\nNext Steps:")
        print(f"  1. View Neo4j: http://localhost:7474")
        print(f"  2. View Qdrant: http://localhost:6333/dashboard")
        print(f"  3. SceneGraph JSON: {output_path}")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await neo4j.close()
        await qdrant.close()


def main():
    """Main entry point."""
    success = asyncio.run(run_demo())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
