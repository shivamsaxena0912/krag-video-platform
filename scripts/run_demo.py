#!/usr/bin/env python3
"""
KRAG Video Platform Demo Script

This script demonstrates the full pipeline with founder validation:
1. Parse example story into SceneGraph
2. Create shot plans with DirectorAgent (marketing-intent-driven)
3. Apply editorial and rhythmic authority
4. Generate asset manifest and placeholder images
5. Render draft video with Ken Burns effect
6. Validate SLA constraints
7. Generate founder review pack
8. Track time-to-value metrics
9. Store all artifacts

Output artifacts in outputs/<run_id>/:
- scene_graph.json
- shot_plan.json
- asset_manifest.json
- draft_v1.mp4
- review_v1_*/                # Founder review pack
  - final_video.mp4
  - marketing_summary.txt
  - director_notes.txt
  - what_changed_since_last_version.txt
  - recommended_publish_checklist.txt
- run_report.json             # Time-to-value metrics
- run_report.txt              # Human-readable summary

Usage:
    python scripts/run_demo.py
    python scripts/run_demo.py --scenario feature_launch
    python scripts/run_demo.py --scenario funding_announcement
    python scripts/run_demo.py --scenario problem_solution
    python scripts/run_demo.py --intent paid_ad  # Direct intent override
    python scripts/run_demo.py --brand acme     # Apply brand biasing
    python scripts/run_demo.py --playbook data/playbook.json  # Apply playbook

Founder Scenarios:
    feature_launch       - New feature or product update (social_reel)
    funding_announcement - Raise announcement (social_reel)
    problem_solution     - Cold outreach positioning (paid_ad)

Prerequisites:
    docker-compose up -d
    ffmpeg installed
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents import (
    StoryParserAgent,
    StoryParserInput,
    CriticAgent,
    CriticInput,
    DirectorAgent,
    DirectorInput,
    DirectorConfig,
)
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
from src.generation import (
    AssetManifest,
    PlaceholderGenerator,
    VideoRenderer,
    RenderConfig,
    create_manifest_from_shots,
)
from src.editing import (
    EditorialAuthority,
    EditorialConfig,
    RhythmicAuthority,
    RhythmConfig,
    generate_director_notes_file,
    validate_version_improvement,
)
from src.marketing import (
    MarketingIntent,
    get_preset,
    get_configs_for_intent,
    generate_marketing_summary,
    validate_pipeline_sla,
)
from src.founder import (
    FounderScenario,
    get_scenario,
    SCENARIOS,
    ReviewPackBuilder,
    TimeToValueMetrics,
    create_run_report,
)
from src.brand import (
    BrandContext,
    ToneProfile,
    ClaimConservativeness,
    create_brand_context,
    apply_brand_bias,
)
from src.playbook import (
    Playbook,
    create_playbook,
    load_playbook,
    save_playbook,
    apply_playbook,
    describe_application,
)
from src.orchestration import (
    IterativeRefinementController,
    RefinementConfig,
    RefinementResult,
)
from src.common.logging import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed."""
    import subprocess
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  ✅ FFmpeg: {result.stdout.split(chr(10))[0]}")
            return True
    except FileNotFoundError:
        pass
    print("  ❌ FFmpeg: Not found. Please install FFmpeg.")
    print("     macOS: brew install ffmpeg")
    print("     Ubuntu: sudo apt install ffmpeg")
    return False


async def check_services() -> bool:
    """Check if required services are running."""
    print("\n🔍 Checking services...")

    # Check FFmpeg first
    ffmpeg_ok = check_ffmpeg()

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

    return neo4j_ok and qdrant_ok and ffmpeg_ok


def save_json(data: dict, path: Path, name: str) -> None:
    """Save data as JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"   📄 {name}: {path.name}")


async def run_demo(
    with_constraints: bool = False,
    intent: MarketingIntent | None = None,
    scenario: FounderScenario | None = None,
    brand: BrandContext | None = None,
    playbook_path: Path | None = None,
):
    """Run the full demo pipeline with founder validation."""
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent.parent / "outputs" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Start time-to-value metrics
    metrics = TimeToValueMetrics()

    # Resolve scenario and intent
    if scenario is None:
        scenario = get_scenario("feature_launch")  # Default scenario

    if intent is None:
        intent = scenario.marketing_intent  # Use scenario's intent

    # Get marketing preset and base configs
    preset = get_preset(intent)
    director_config, editorial_config, rhythm_config = get_configs_for_intent(intent)

    # Apply brand biasing if provided
    brand_biases_applied = []
    if brand:
        biased = apply_brand_bias(
            brand=brand,
            intent=intent,
            base_director_config=director_config,
            base_editorial_config=editorial_config,
            base_rhythm_config=rhythm_config,
        )
        director_config = biased.director_config
        editorial_config = biased.editorial_config
        rhythm_config = biased.rhythm_config
        brand_biases_applied = biased.biases_applied

    # Load and apply playbook if provided
    playbook = None
    playbook_application = None
    if playbook_path and playbook_path.exists():
        playbook = load_playbook(playbook_path)
        director_config, editorial_config, rhythm_config, playbook_application = apply_playbook(
            playbook=playbook,
            director_config=director_config,
            editorial_config=editorial_config,
            rhythm_config=rhythm_config,
            scenario_id=scenario.scenario_id,
            intent=intent.value,
        )

    print("\n" + "=" * 60)
    print("🎬 KRAG Video Platform - Founder Demo")
    print(f"   Run ID: {run_id}")
    print(f"   Scenario: {scenario.scenario_name}")
    print(f"   Goal: {scenario.goal.value.upper()}")
    print(f"   Platform: {scenario.platform}")
    print(f"   Target: {scenario.recommended_length}")
    if brand:
        print(f"   Brand: {brand.brand_name} ({brand.tone.value})")
    if playbook:
        print(f"   Playbook: {playbook.name} (v{playbook.current_version})")
    print("=" * 60)

    # Check services
    services_ok = await check_services()
    if not services_ok:
        print("\n❌ Required services are not running.")
        print("   Please run: docker-compose up -d")
        print("   And ensure FFmpeg is installed.")
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

        # Save scene_graph.json
        save_json(
            scene_graph.model_dump(mode="json"),
            output_dir / "scene_graph.json",
            "Scene Graph",
        )

        # Step 4: Create shot plans with DirectorAgent (marketing-intent-driven)
        print(f"\n🎬 Step 4: Creating shot plans with DirectorAgent...")
        print(f"   Intent: {intent.value} → target {director_config.target_duration_seconds:.0f}s")

        # Report brand biases if applied
        if brand_biases_applied:
            print(f"   Brand biases applied ({len(brand_biases_applied)}):")
            for bias in brand_biases_applied[:3]:  # Show first 3
                print(f"      - {bias}")

        # Report playbook application if used
        if playbook_application and playbook_application.entries_applied:
            print(f"   Playbook entries applied ({len(playbook_application.entries_applied)}):")
            for entry in playbook_application.entries_applied[:3]:  # Show first 3
                print(f"      - {entry.description}")

        # Test constraints if requested
        playbook_constraints = []
        if with_constraints:
            playbook_constraints = [
                "prefer_static",
                "min_duration:3.5",
                "longer_establishing",
            ]
            print(f"   Using constraints: {playbook_constraints}")

        director = DirectorAgent()
        # Use marketing-derived config instead of default
        config = director_config

        all_shots = []
        all_plans = []
        all_constraints_applied = []

        for i, scene in enumerate(scene_graph.scenes):
            result = await director(DirectorInput(
                scene=scene,
                scene_index=i,
                total_scenes=len(scene_graph.scenes),
                config=config,
                playbook_constraints=playbook_constraints,
            ))
            all_plans.append(result.shot_plan)
            all_shots.extend(result.shots)

            if result.constraints_applied:
                for constraint in result.constraints_applied:
                    all_constraints_applied.append({
                        "scene_id": scene.id,
                        "constraint": constraint.constraint,
                        "applied_to": constraint.applied_to,
                        "parameter_changes": constraint.parameter_changes,
                    })

        total_duration = sum(s.duration_seconds for s in all_shots)
        print(f"   Shot plans: {len(all_plans)}")
        print(f"   Total shots: {len(all_shots)}")
        print(f"   Total duration: {total_duration:.1f}s")

        # Save shot_plan.json
        shot_plan_data = {
            "story_id": scene_graph.story.id,
            "total_shots": len(all_shots),
            "total_duration_seconds": total_duration,
            "plans": [p.model_dump(mode="json") for p in all_plans],
            "shots": [s.model_dump(mode="json") for s in all_shots],
        }
        save_json(shot_plan_data, output_dir / "shot_plan.json", "Shot Plan")

        # Save constraints_applied.json if any
        if all_constraints_applied:
            save_json(
                {
                    "constraints_requested": playbook_constraints,
                    "constraints_applied": all_constraints_applied,
                    "total_applied": len(all_constraints_applied),
                },
                output_dir / "constraints_applied.json",
                "Constraints Applied",
            )

        # Step 4.5: Apply Editorial Authority (marketing-intent-driven trimming)
        print(f"\n✂️  Step 4.5: Applying editorial authority...")
        print(f"   Target reduction: {editorial_config.target_reduction_percent:.0%}")
        editorial = EditorialAuthority(editorial_config)

        original_count = len(all_shots)
        original_duration = sum(s.duration_seconds for s in all_shots)

        all_shots, editorial_report = editorial.apply(all_shots)

        print(f"   Original: {original_count} shots, {original_duration:.1f}s")
        print(f"   After trim: {len(all_shots)} shots, {sum(s.duration_seconds for s in all_shots):.1f}s")
        print(f"   Reduction: {editorial_report.reduction_percent:.1%}")
        print(f"   Emotional density: {editorial_report.emotional_density:.0%}")

        # Step 4.6: Apply Rhythmic Authority (marketing-intent-driven tempo)
        print(f"\n🎵 Step 4.6: Applying rhythmic authority...")
        rhythm = RhythmicAuthority(rhythm_config)

        pre_rhythm_duration = sum(s.duration_seconds for s in all_shots)
        all_shots, rhythm_report = rhythm.apply(all_shots)

        print(f"   Pre-rhythm: {pre_rhythm_duration:.1f}s")
        print(f"   Post-rhythm: {sum(s.duration_seconds for s in all_shots):.1f}s")
        print(f"   Monotony score: {rhythm_report.monotony_score:.0%} (lower is better)")
        print(f"   Attention dips: {rhythm_report.attention_dip_count}")
        print(f"   Final shot intent: {rhythm_report.ending_intent.value}")

        # Save rhythm report
        save_json(
            {
                "monotony_score": rhythm_report.monotony_score,
                "attention_dip_count": rhythm_report.attention_dip_count,
                "max_intensity_run": rhythm_report.max_intensity_run,
                "duration_variation_achieved": rhythm_report.duration_variation_achieved,
                "emotion_shots_tightened": rhythm_report.emotion_shots_tightened,
                "ending_intent": rhythm_report.ending_intent.value,
                "intensity_distribution": {
                    k.value: v for k, v in rhythm_report.intensity_distribution.items()
                },
                "rhythm_notes": rhythm_report.rhythm_notes,
            },
            output_dir / "rhythm_report.json",
            "Rhythm Report",
        )

        # Generate director notes (with both editorial and rhythm critique)
        generate_director_notes_file(
            all_shots,
            editorial_report,
            output_dir / "director_notes.txt",
            rhythm_report=rhythm_report,
        )
        print(f"   📝 Director notes: {output_dir / 'director_notes.txt'}")

        # Save editorial report
        save_json(
            {
                "original_shots": editorial_report.original_shot_count,
                "original_duration": editorial_report.original_duration,
                "trimmed_shots": editorial_report.trimmed_shot_count,
                "trimmed_duration": editorial_report.trimmed_duration,
                "reduction_percent": editorial_report.reduction_percent,
                "emotional_density": editorial_report.emotional_density,
                "information_density": editorial_report.information_density,
                "removed_information": editorial_report.removed_information,
                "removed_atmosphere": editorial_report.removed_atmosphere,
                "shortened_shots": editorial_report.shortened_shots,
                "director_notes": editorial_report.director_notes,
                "biggest_flaw": editorial_report.biggest_flaw,
            },
            output_dir / "editorial_report.json",
            "Editorial Report",
        )

        # Update total_duration after trimming
        total_duration = sum(s.duration_seconds for s in all_shots)

        # Step 4.7: Validate SLA constraints
        print(f"\n📋 Step 4.7: Validating SLA constraints...")
        sla_report = validate_pipeline_sla(
            shots=all_shots,
            intent=intent,
            iteration_count=0,  # Will be updated after refinement
            total_cost=0.0,
        )

        if sla_report.passed:
            print(f"   ✅ SLA PASSED: {intent.value} constraints met")
        else:
            print(f"   ⚠️  SLA WARNINGS: {len(sla_report.violations)} violations")
            for v in sla_report.violations[:3]:  # Show first 3
                print(f"      - {v.message}")

        if sla_report.warnings:
            print(f"   📝 {len(sla_report.warnings)} warnings")

        # Save SLA report
        save_json(
            {
                "intent": intent.value,
                "passed": sla_report.passed,
                "total_duration": sla_report.total_duration,
                "shot_count": sla_report.shot_count,
                "violations": [
                    {"type": v.violation_type.value, "message": v.message}
                    for v in sla_report.violations
                ],
                "warnings": [
                    {"type": v.violation_type.value, "message": v.message}
                    for v in sla_report.warnings
                ],
            },
            output_dir / "sla_report.json",
            "SLA Report",
        )

        # Step 4.8: Generate marketing summary
        print(f"\n📊 Step 4.8: Generating marketing summary...")
        marketing_summary = generate_marketing_summary(
            shots=all_shots,
            intent=intent,
            editorial_report=editorial_report,
            rhythm_report=rhythm_report,
            output_path=output_dir / "marketing_summary.txt",
        )
        print(f"   Platform: {preset.platform}")
        print(f"   Target audience: {preset.target_audience[:50]}...")
        print(f"   CTA: {preset.intended_cta}")
        print(f"   📄 Summary: marketing_summary.txt")

        # Step 5: Generate asset manifest and placeholders
        print("\n🖼️  Step 5: Generating assets...")
        manifest = create_manifest_from_shots(
            scene_graph.story.id,
            all_shots,
            output_dir=str(output_dir / "assets"),
        )

        placeholder_gen = PlaceholderGenerator(output_dir=str(output_dir / "assets"))
        pending = manifest.get_pending_requirements()

        for req in pending:
            if req.asset_type.value == "image":
                asset = await placeholder_gen.generate(req)
                manifest = manifest.mark_completed(req.id, asset)

        print(f"   Assets generated: {manifest.completed_count}")
        print(f"   Failed: {manifest.failed_count}")

        # Save asset_manifest.json
        save_json(
            manifest.model_dump(mode="json"),
            output_dir / "asset_manifest.json",
            "Asset Manifest",
        )

        # Step 6: Render draft video
        print("\n🎥 Step 6: Rendering draft video...")
        renderer = VideoRenderer(
            config=RenderConfig(fps=24, crf=28, enable_music_bed=True),
            output_dir=str(output_dir),
        )

        render_result = await renderer.render_video(
            all_shots,
            manifest,
            output_filename="draft_v1.mp4",
            scenes=scene_graph.scenes,  # Pass scenes for music bed mood detection
        )

        if render_result.success:
            print(f"   ✅ Draft video: draft_v1.mp4")
            print(f"   Duration: {render_result.duration_seconds:.1f}s")
            print(f"   Size: {render_result.file_size_bytes / 1024:.1f} KB")

            # Record first cut time
            metrics.record_first_cut()
            ttfc = metrics.time_to_first_cut_seconds
            print(f"   ⏱️  Time to first cut: {ttfc:.1f}s")

            # Save render_report.json
            if render_result.render_report:
                save_json(
                    render_result.render_report.model_dump(mode="json"),
                    output_dir / "render_report.json",
                    "Render Report",
                )

            # Step 6.5: Build founder review pack
            print(f"\n📦 Step 6.5: Building founder review pack...")
            review_builder = ReviewPackBuilder(output_dir)
            review_pack = review_builder.build(
                scenario=scenario,
                version=1,
                video_path=output_dir / "draft_v1.mp4",
                marketing_summary_path=output_dir / "marketing_summary.txt",
                director_notes_path=output_dir / "director_notes.txt",
                previous_pack=None,
                duration_seconds=render_result.duration_seconds,
                shot_count=len(all_shots),
            )
            print(f"   📁 Review pack: {review_pack.pack_path.name}/")
            print(f"   ├── final_video.mp4")
            print(f"   ├── marketing_summary.txt")
            print(f"   ├── director_notes.txt")
            print(f"   ├── what_changed_since_last_version.txt")
            print(f"   └── recommended_publish_checklist.txt")
        else:
            print(f"   ❌ Rendering failed: {render_result.errors}")
            review_pack = None

        # Step 7: Evaluate with Critic
        print("\n🎯 Step 7: Evaluating with CriticAgent...")
        critic = CriticAgent()
        critic_result = await critic(CriticInput(scene_graph=scene_graph))

        story_fb = critic_result.story_feedback
        print(f"   Overall Score: {story_fb.overall_score}/10")
        print(f"   Recommendation: {story_fb.recommendation.value}")
        print(f"   Issues: {len(story_fb.issues)}")

        # Save critic_v1.json
        save_json(
            {
                "story_feedback": story_fb.model_dump(mode="json"),
                "scene_feedbacks": [
                    sf.model_dump(mode="json") for sf in critic_result.scene_feedbacks
                ],
            },
            output_dir / "critic_v1.json",
            "Critic V1",
        )

        # Step 8: Refinement loop (SLA-constrained)
        print(f"\n🔄 Step 8: Running refinement loop...")
        print(f"   Max iterations: {preset.max_iterations} (SLA limit)")
        print(f"   Max cost: ${preset.max_cost_dollars:.2f} (SLA limit)")
        refinement_config = RefinementConfig(
            max_iterations=preset.max_iterations,
            max_cost_dollars=preset.max_cost_dollars,
            target_overall_score=7.0,
        )
        controller = IterativeRefinementController(config=refinement_config)

        refined_graph, refinement_result = await controller.run(scene_graph)

        print(f"   Status: {refinement_result.status.value}")
        print(f"   Stop reason: {refinement_result.stop_reason}")
        print(f"   Iterations: {refinement_result.iterations_completed}")
        print(f"   Score: {refinement_result.initial_score:.1f} → {refinement_result.final_score:.1f}")
        print(f"   Cost: ${refinement_result.total_cost:.2f}")

        # Save iteration_history.json
        save_json(
            {
                "id": refinement_result.id,
                "status": refinement_result.status.value,
                "stop_reason": refinement_result.stop_reason,
                "iterations_completed": refinement_result.iterations_completed,
                "initial_score": refinement_result.initial_score,
                "final_score": refinement_result.final_score,
                "score_improvement": refinement_result.score_improvement,
                "target_met": refinement_result.target_met,
                "total_cost": refinement_result.total_cost,
                "iterations": [
                    {
                        "iteration": it.iteration,
                        "input_score": it.input_score,
                        "output_score": it.output_score,
                        "score_improvement": it.score_improvement,
                        "issues_identified": it.issues_identified,
                        "fixes_applied": it.fixes_applied,
                        "fix_descriptions": it.fix_descriptions,
                        "recommendation": it.recommendation.value if it.recommendation else None,
                        "iteration_cost": it.iteration_cost,
                    }
                    for it in refinement_result.iterations
                ],
            },
            output_dir / "iteration_history.json",
            "Iteration History",
        )

        # Step 9: Render v2 if refinement ran multiple iterations
        if refinement_result.iterations_completed > 1 and render_result.success:
            print("\n🎥 Step 9: Rendering refined video (draft_v2)...")
            render_v2 = await renderer.render_video(
                all_shots,  # Would use refined shots in production
                manifest,
                output_filename="draft_v2.mp4",
                scenes=scene_graph.scenes,
            )
            if render_v2.success:
                print(f"   ✅ Refined video: draft_v2.mp4")

        # Step 10: Ingest into Neo4j
        print("\n💾 Step 10: Ingesting into Neo4j...")
        ingest_result = await ingest_scene_graph(neo4j, scene_graph)
        print(f"   Scenes stored: {ingest_result['scenes']}")

        # Store feedback
        await upsert_feedback(neo4j, story_fb)
        print(f"   Feedback stored")

        # Step 11: Generate run report
        print("\n📊 Step 11: Generating run report...")
        run_report = create_run_report(
            run_id=run_id,
            scenario=scenario,
            metrics=metrics,
            final_duration_seconds=render_result.duration_seconds if render_result.success else 0.0,
            final_shot_count=len(all_shots),
            total_cost_dollars=refinement_result.total_cost,
            output_dir=output_dir,
        )
        run_report.save()
        print(f"   📄 run_report.json")
        print(f"   📄 run_report.txt")

        # Summary
        print("\n" + "=" * 60)
        print("✅ Demo Complete!")
        print("=" * 60)

        print(f"\n📋 SCENARIO: {scenario.scenario_name}")
        print(f"   Goal: {scenario.goal.value.upper()}")
        print(f"   Platform: {scenario.platform}")
        print(f"   Target: {scenario.recommended_length}")

        print(f"\n⏱️  TIME TO VALUE:")
        ttfc = metrics.time_to_first_cut_seconds
        if ttfc:
            if ttfc < 60:
                print(f"   Time to first cut: {ttfc:.1f} seconds")
            else:
                print(f"   Time to first cut: {ttfc / 60:.1f} minutes")
        print(f"   Iterations: {metrics.number_of_iterations}")
        print(f"   Status: {run_report.final_status.upper()}")

        print(f"\n📦 REVIEW PACK:")
        if review_pack:
            print(f"   {review_pack.pack_path.name}/")
            print(f"   ├── final_video.mp4")
            print(f"   ├── marketing_summary.txt")
            print(f"   ├── what_changed_since_last_version.txt")
            print(f"   └── recommended_publish_checklist.txt")

        print(f"\n📊 QUALITY:")
        print(f"   Video Duration: {render_result.duration_seconds:.1f}s" if render_result.success else "   Video: Failed")
        print(f"   Total Shots: {len(all_shots)}")
        print(f"   Quality Score: {refinement_result.final_score:.1f}/10")
        print(f"   SLA: {'✅ PASSED' if sla_report.passed else '⚠️  VIOLATIONS'}")

        # Report brand and playbook usage
        if brand or playbook:
            print(f"\n🎨 CUSTOMIZATION:")
            if brand:
                print(f"   Brand: {brand.brand_name} ({brand.tone.value})")
                print(f"   Biases applied: {len(brand_biases_applied)}")
            if playbook and playbook_application:
                print(f"   Playbook: {playbook.name} v{playbook.current_version}")
                print(f"   Entries applied: {len(playbook_application.entries_applied)}")

        print(f"\n🚀 NEXT STEPS:")
        print(f"   1. Open review pack: open {review_pack.pack_path if review_pack else output_dir}")
        print(f"   2. Watch: open {output_dir}/draft_v1.mp4")
        print(f"   3. Read checklist: cat {review_pack.checklist_path if review_pack else 'N/A'}")
        print(f"   4. Try different scenario: python scripts/run_demo.py --scenario problem_solution")

        print(f"\nOutput directory: {output_dir}")

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
    import argparse
    parser = argparse.ArgumentParser(
        description="KRAG Video Platform - Founder Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Founder Scenarios:
  feature_launch       New feature or product update
  funding_announcement Raise announcement
  problem_solution     Cold outreach positioning

Brand Presets:
  acme       Bold tech startup (bold tone, aggressive pacing)
  wellness   Health/wellness brand (empathetic tone, gentle pacing)
  enterprise B2B enterprise (professional tone, moderate pacing)

Examples:
  python scripts/run_demo.py --scenario feature_launch
  python scripts/run_demo.py --scenario problem_solution
  python scripts/run_demo.py --intent paid_ad  # Direct intent override
  python scripts/run_demo.py --brand acme      # Apply brand biasing
  python scripts/run_demo.py --playbook data/playbook.json  # Apply playbook
""",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=list(SCENARIOS.keys()),
        default="feature_launch",
        help="Founder scenario (default: feature_launch)",
    )
    parser.add_argument(
        "--intent",
        type=str,
        choices=["paid_ad", "social_reel", "youtube_explainer"],
        default=None,
        help="Marketing intent override (uses scenario's intent by default)",
    )
    parser.add_argument(
        "--brand",
        type=str,
        choices=["acme", "wellness", "enterprise"],
        default=None,
        help="Brand preset for biasing (optional)",
    )
    parser.add_argument(
        "--playbook",
        type=str,
        default=None,
        help="Path to playbook JSON file (optional)",
    )
    parser.add_argument(
        "--with-constraints",
        action="store_true",
        help="Test with feedback constraints applied",
    )
    args = parser.parse_args()

    # Get scenario
    scenario = get_scenario(args.scenario)

    # Parse intent override if provided
    intent = None
    if args.intent:
        intent_map = {
            "paid_ad": MarketingIntent.PAID_AD,
            "social_reel": MarketingIntent.SOCIAL_REEL,
            "youtube_explainer": MarketingIntent.YOUTUBE_EXPLAINER,
        }
        intent = intent_map[args.intent]

    # Create brand context if specified
    brand = None
    if args.brand:
        brand_presets = {
            "acme": create_brand_context(
                brand_name="Acme Corp",
                tone=ToneProfile.BOLD,
                pacing_aggressiveness=0.8,
                claim_conservativeness=ClaimConservativeness.AGGRESSIVE,
            ),
            "wellness": create_brand_context(
                brand_name="Serenity Wellness",
                tone=ToneProfile.EMPATHETIC,
                pacing_aggressiveness=0.3,
                claim_conservativeness=ClaimConservativeness.CONSERVATIVE,
            ),
            "enterprise": create_brand_context(
                brand_name="Enterprise Solutions Inc",
                tone=ToneProfile.PROFESSIONAL,
                pacing_aggressiveness=0.5,
                claim_conservativeness=ClaimConservativeness.MODERATE,
            ),
        }
        brand = brand_presets[args.brand]

    # Load playbook if specified
    playbook_path = None
    if args.playbook:
        playbook_path = Path(args.playbook)
        if not playbook_path.exists():
            print(f"Warning: Playbook not found at {playbook_path}, ignoring")
            playbook_path = None

    success = asyncio.run(run_demo(
        with_constraints=args.with_constraints,
        intent=intent,
        scenario=scenario,
        brand=brand,
        playbook_path=playbook_path,
    ))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
