"""Director Agent v1 - Creates shot plans with cinematic intelligence."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.agents.base import BaseAgent, AgentConfig
from src.common.logging import get_logger
from src.common.models import (
    Scene,
    ShotPlan,
    ShotPlanStatus,
    Shot,
    ShotType,
    ShotRole,
    Composition,
    Framing,
    CameraAngle,
    DepthOfField,
    MotionSpec,
    CameraMotion,
    MotionSpeed,
    Transition,
    TransitionType,
    AudioCue,
    AudioCueType,
    LensType,
    LightingStyle,
    CompositionZone,
    SubjectEntity,
    VisualSymbol,
    ShotVisualSpec,
)
from src.knowledge_graph.scene_graph import SceneGraph

logger = get_logger(__name__)


# =============================================================================
# Configuration Models
# =============================================================================


class PacingStyle(str, Enum):
    """Pacing style for shot planning."""
    CONTEMPLATIVE = "contemplative"  # Longer shots, slower movement
    MODERATE = "moderate"  # Balanced pacing
    DYNAMIC = "dynamic"  # Faster cuts, more variety
    INTENSE = "intense"  # Quick cuts, high energy


class HookStrategy(str, Enum):
    """Strategy for the opening hook."""
    VISUAL_IMPACT = "visual_impact"  # Start with striking image
    MYSTERY = "mystery"  # Start with intriguing detail
    ACTION = "action"  # Start mid-action
    EMOTIONAL = "emotional"  # Start with emotional close-up


class DirectorConfig(BaseModel):
    """Configuration for the Director Agent."""

    # Duration budgets
    target_duration_seconds: float = 60.0  # Target scene duration
    min_shot_duration: float = 2.0
    max_shot_duration: float = 8.0
    hook_duration: float = 3.0  # First 3 seconds for hook

    # Shot count constraints
    min_shots_per_scene: int = 3
    max_shots_per_scene: int = 10

    # Style preferences
    default_pacing: PacingStyle = PacingStyle.MODERATE
    default_hook_strategy: HookStrategy = HookStrategy.VISUAL_IMPACT

    # Quality settings
    prefer_variety: bool = True  # Prefer varied shot types
    include_transitions: bool = True
    include_audio_cues: bool = True


# =============================================================================
# Input/Output Models
# =============================================================================


class DirectorInput(BaseModel):
    """Input for the Director Agent."""

    scene: Scene
    scene_index: int = 0  # Position in story (0 = first scene)
    total_scenes: int = 1
    config: DirectorConfig = Field(default_factory=DirectorConfig)

    # Context from previous scenes (for continuity)
    previous_ending_shot_type: ShotType | None = None
    story_mood: str = "neutral"

    # Playbook constraints from feedback
    playbook_constraints: list[str] = Field(default_factory=list)


class AppliedConstraint(BaseModel):
    """Record of an applied constraint."""

    constraint: str
    applied_to: list[str] = Field(default_factory=list)  # Shot IDs or "all"
    parameter_changes: dict[str, Any] = Field(default_factory=dict)


class DirectorOutput(BaseModel):
    """Output from the Director Agent."""

    shot_plan: ShotPlan
    shots: list[Shot]
    hook_analysis: dict[str, Any] = Field(default_factory=dict)
    duration_budget: dict[str, float] = Field(default_factory=dict)
    planning_notes: list[str] = Field(default_factory=list)

    # Constraint tracking
    constraints_applied: list[AppliedConstraint] = Field(default_factory=list)
    constraint_source: str = ""  # Where constraints came from


# =============================================================================
# Director Agent
# =============================================================================


class DirectorAgent(BaseAgent[DirectorInput, DirectorOutput]):
    """
    Creates cinematic shot plans for scenes.

    Features:
    - Variable shot counts based on scene complexity
    - Duration budgeting to hit target length
    - Explicit hook planning for first 3 seconds
    - Shot variety and pacing control
    - Playbook constraint integration
    """

    def __init__(self):
        super().__init__(AgentConfig(name="DirectorAgent"))

    async def execute(self, input: DirectorInput) -> DirectorOutput:
        """Create a shot plan for the scene."""
        logger.info(
            "planning_scene",
            scene_id=input.scene.id,
            scene_index=input.scene_index,
        )

        config = input.config
        scene = input.scene

        # Analyze scene to determine shot count and pacing
        analysis = self._analyze_scene(scene, config)

        # Determine hook strategy
        hook_strategy = self._determine_hook_strategy(
            scene,
            input.scene_index,
            config,
        )

        # Calculate duration budget
        duration_budget = self._calculate_duration_budget(
            analysis["shot_count"],
            config,
            scene,
        )

        # Generate shots
        shots = self._generate_shots(
            scene,
            analysis,
            hook_strategy,
            duration_budget,
            config,
            input,
        )

        # Apply playbook constraints
        constraints_applied = []
        constraint_source = ""
        if input.playbook_constraints:
            shots, constraints_applied = self._apply_constraints(shots, input.playbook_constraints)
            constraint_source = "playbook_constraints from feedback"

        # Create shot plan
        plan_id = f"plan_{scene.id[6:]}"

        shot_plan = ShotPlan(
            id=plan_id,
            scene_id=scene.id,
            shots=shots,
            status=ShotPlanStatus.DRAFT,
            estimated_duration_seconds=sum(s.duration_seconds for s in shots),
            creative_direction=self._generate_creative_direction(scene, analysis),
            pacing_rationale=self._generate_pacing_rationale(analysis, config),
            style_notes=analysis.get("style_notes", []),
        )

        # Update shot references
        for shot in shots:
            shot = shot.model_copy(update={"shot_plan_id": plan_id})

        planning_notes = [
            f"Shot count: {len(shots)} (target: {analysis['shot_count']})",
            f"Total duration: {shot_plan.estimated_duration_seconds:.1f}s",
            f"Hook strategy: {hook_strategy.value}",
            f"Pacing: {analysis['pacing'].value}",
        ]

        logger.info(
            "scene_planned",
            scene_id=scene.id,
            shots=len(shots),
            duration=shot_plan.estimated_duration_seconds,
        )

        return DirectorOutput(
            shot_plan=shot_plan,
            shots=shots,
            hook_analysis={
                "strategy": hook_strategy.value,
                "hook_duration": config.hook_duration,
                "hook_shot_count": self._count_hook_shots(shots, config.hook_duration),
            },
            duration_budget=duration_budget,
            planning_notes=planning_notes,
            constraints_applied=constraints_applied,
            constraint_source=constraint_source,
        )

    def _analyze_scene(
        self,
        scene: Scene,
        config: DirectorConfig,
    ) -> dict[str, Any]:
        """Analyze scene to determine shot planning parameters."""

        # Calculate complexity score
        complexity = scene.complexity_score

        # Adjust for content length
        word_count = scene.word_count
        if word_count > 200:
            complexity = min(1.0, complexity + 0.2)
        elif word_count < 50:
            complexity = max(0.0, complexity - 0.2)

        # Determine pacing based on emotional beat
        emotion = scene.emotional_beat.primary_emotion.lower()
        intensity = scene.emotional_beat.intensity

        if emotion in ["tension", "anxiety", "action"] or intensity > 0.7:
            pacing = PacingStyle.DYNAMIC
        elif emotion in ["sorrow", "contemplative", "hope"] or intensity < 0.4:
            pacing = PacingStyle.CONTEMPLATIVE
        elif emotion in ["triumph", "chaos"]:
            pacing = PacingStyle.INTENSE
        else:
            pacing = config.default_pacing

        # Calculate shot count
        base_shots = 4
        complexity_bonus = int(complexity * 3)  # 0-3 extra shots
        pacing_adjustment = {
            PacingStyle.CONTEMPLATIVE: -1,
            PacingStyle.MODERATE: 0,
            PacingStyle.DYNAMIC: 1,
            PacingStyle.INTENSE: 2,
        }.get(pacing, 0)

        shot_count = base_shots + complexity_bonus + pacing_adjustment
        shot_count = max(config.min_shots_per_scene,
                        min(config.max_shots_per_scene, shot_count))

        # Generate style notes
        style_notes = []
        if scene.setting.atmosphere:
            style_notes.append(f"Atmosphere: {scene.setting.atmosphere}")
        if scene.setting.time_of_day.value != "unspecified":
            style_notes.append(f"Time: {scene.setting.time_of_day.value}")
        style_notes.append(f"Emotional intensity: {intensity:.0%}")

        return {
            "complexity": complexity,
            "pacing": pacing,
            "shot_count": shot_count,
            "emotion": emotion,
            "intensity": intensity,
            "style_notes": style_notes,
        }

    def _determine_hook_strategy(
        self,
        scene: Scene,
        scene_index: int,
        config: DirectorConfig,
    ) -> HookStrategy:
        """Determine the best hook strategy for the scene."""

        emotion = scene.emotional_beat.primary_emotion.lower()
        intensity = scene.emotional_beat.intensity

        # First scene should be visually striking
        if scene_index == 0:
            return HookStrategy.VISUAL_IMPACT

        # High intensity scenes start with action
        if intensity > 0.7:
            if emotion in ["tension", "action", "chaos"]:
                return HookStrategy.ACTION
            else:
                return HookStrategy.EMOTIONAL

        # Mysterious or contemplative scenes
        if emotion in ["mystery", "contemplative"]:
            return HookStrategy.MYSTERY

        # Emotional scenes
        if emotion in ["sorrow", "hope", "triumph"]:
            return HookStrategy.EMOTIONAL

        return config.default_hook_strategy

    def _calculate_duration_budget(
        self,
        shot_count: int,
        config: DirectorConfig,
        scene: Scene,
    ) -> dict[str, float]:
        """Calculate duration budget for each shot."""

        # Use estimated duration or target
        total_duration = max(
            scene.estimated_duration_seconds,
            config.target_duration_seconds * 0.5,
        )
        total_duration = min(total_duration, config.target_duration_seconds * 1.5)

        # Reserve time for hook
        hook_budget = config.hook_duration
        remaining = total_duration - hook_budget

        # Distribute remaining time
        avg_duration = remaining / max(shot_count - 1, 1)

        return {
            "total": total_duration,
            "hook": hook_budget,
            "remaining": remaining,
            "average_shot": avg_duration,
            "min_shot": config.min_shot_duration,
            "max_shot": config.max_shot_duration,
        }

    def _generate_shots(
        self,
        scene: Scene,
        analysis: dict,
        hook_strategy: HookStrategy,
        duration_budget: dict,
        config: DirectorConfig,
        input: DirectorInput,
    ) -> list[Shot]:
        """Generate the actual shot list."""

        shots = []
        plan_id = f"plan_{scene.id[6:]}"
        shot_count = analysis["shot_count"]
        pacing = analysis["pacing"]

        # Track used shot types for variety
        used_types = set()

        # Generate hook shot (first shot)
        hook_shot = self._create_hook_shot(
            scene,
            hook_strategy,
            duration_budget["hook"],
            plan_id,
            input.previous_ending_shot_type,
        )
        shots.append(hook_shot)
        used_types.add(hook_shot.shot_type)

        # Calculate remaining shot durations
        remaining_duration = duration_budget["remaining"]
        remaining_shots = shot_count - 1

        # Generate middle shots
        for i in range(remaining_shots - 1):
            shot_duration = self._calculate_shot_duration(
                remaining_duration,
                remaining_shots - i,
                pacing,
                config,
            )

            shot_type = self._select_shot_type(
                i + 1,
                remaining_shots,
                used_types,
                pacing,
                config,
            )
            used_types.add(shot_type)

            shot = self._create_middle_shot(
                scene,
                i + 2,  # sequence starts at 2 (hook is 1)
                shot_type,
                shot_duration,
                plan_id,
                analysis,
                config,
            )
            shots.append(shot)
            remaining_duration -= shot_duration

        # Generate closing shot
        if remaining_shots > 0:
            closing_shot = self._create_closing_shot(
                scene,
                shot_count,
                remaining_duration,
                plan_id,
                analysis,
                input.scene_index == input.total_scenes - 1,
            )
            shots.append(closing_shot)

        # Add transitions if enabled
        if config.include_transitions:
            shots = self._add_transitions(shots, pacing)

        # Add audio cues if enabled
        if config.include_audio_cues:
            shots = self._add_audio_cues(shots, scene, analysis)

        return shots

    def _create_visual_spec(
        self,
        shot_role: ShotRole,
        shot_type: ShotType,
        motion: MotionSpec,
        scene: Scene,
        sequence: int,
        total_shots: int,
    ) -> ShotVisualSpec:
        """Create deterministic visual specification based on shot role and mood.

        This method maps shot roles and scene moods to explicit visual parameters
        for the renderer and image generator.
        """
        emotion = scene.emotional_beat.primary_emotion.lower()
        intensity = scene.emotional_beat.intensity

        # Determine lens type based on shot type
        lens_map = {
            ShotType.EXTREME_WIDE: LensType.ULTRA_WIDE,
            ShotType.WIDE: LensType.WIDE,
            ShotType.MEDIUM_WIDE: LensType.WIDE,
            ShotType.MEDIUM: LensType.NORMAL,
            ShotType.MEDIUM_CLOSE: LensType.SHORT_TELE,
            ShotType.CLOSE_UP: LensType.SHORT_TELE,
            ShotType.EXTREME_CLOSE: LensType.MACRO,
            ShotType.CUTAWAY: LensType.NORMAL,
            ShotType.POV: LensType.NORMAL,
        }
        lens_type = lens_map.get(shot_type, LensType.NORMAL)

        # Determine lighting style based on mood
        lighting_map = {
            "tension": LightingStyle.LOW_KEY,
            "sorrow": LightingStyle.BLUE_HOUR,
            "hope": LightingStyle.GOLDEN_HOUR,
            "triumph": LightingStyle.HIGH_KEY,
            "contemplative": LightingStyle.DIFFUSED,
            "action": LightingStyle.DRAMATIC,
            "mystery": LightingStyle.SILHOUETTE,
            "chaos": LightingStyle.DRAMATIC,
            "anxiety": LightingStyle.LOW_KEY,
        }
        lighting_style = lighting_map.get(emotion, LightingStyle.NATURAL)

        # Determine composition zone based on shot role
        zone_map = {
            ShotRole.ESTABLISHING: CompositionZone.FULL_FRAME,
            ShotRole.ACTION: CompositionZone.CENTER,
            ShotRole.REACTION: CompositionZone.MIDDLE_RIGHT,
            ShotRole.DETAIL: CompositionZone.CENTER,
            ShotRole.TRANSITION: CompositionZone.CENTER,
            ShotRole.MONTAGE: CompositionZone.CENTER,
            ShotRole.CLIMAX: CompositionZone.CENTER,
            ShotRole.RESOLUTION: CompositionZone.CENTER,
        }
        primary_zone = zone_map.get(shot_role, CompositionZone.CENTER)

        # Determine camera height based on shot role and emotion
        if shot_role == ShotRole.ESTABLISHING:
            camera_height = "aerial" if scene.setting.interior_exterior == "exterior" else "high"
        elif shot_role == ShotRole.CLIMAX or emotion in ["triumph", "hope"]:
            camera_height = "low"  # Hero angle
        elif shot_role == ShotRole.REACTION:
            camera_height = "eye_level"
        elif emotion in ["sorrow", "tension"]:
            camera_height = "high"  # Oppressive angle
        else:
            camera_height = "eye_level"

        # Color temperature based on mood
        if emotion in ["tension", "sorrow", "anxiety", "mystery"]:
            color_temperature = "cool"
        elif emotion in ["hope", "triumph", "action"]:
            color_temperature = "warm"
        else:
            color_temperature = "neutral"

        # Color palette based on emotion and era
        color_palettes = {
            "tension": ["desaturated", "dark shadows", "muted reds"],
            "sorrow": ["blue tones", "grey", "desaturated"],
            "hope": ["golden light", "warm earth tones", "soft highlights"],
            "triumph": ["vibrant gold", "warm highlights", "rich colors"],
            "contemplative": ["muted pastels", "soft contrast", "earth tones"],
            "action": ["high contrast", "rich saturation", "dynamic shadows"],
            "mystery": ["deep shadows", "silhouettes", "blue-black tones"],
        }
        color_palette = color_palettes.get(emotion, ["natural colors", "balanced exposure"])

        # Ken Burns parameters based on motion spec
        if motion.camera_motion == CameraMotion.ZOOM_IN:
            kb_start = CompositionZone.FULL_FRAME
            kb_end = CompositionZone.CENTER
            zoom_dir = "in"
        elif motion.camera_motion == CameraMotion.ZOOM_OUT:
            kb_start = CompositionZone.CENTER
            kb_end = CompositionZone.FULL_FRAME
            zoom_dir = "out"
        elif motion.camera_motion in [CameraMotion.PAN_LEFT, CameraMotion.TRACK_LEFT]:
            kb_start = CompositionZone.MIDDLE_RIGHT
            kb_end = CompositionZone.MIDDLE_LEFT
            zoom_dir = "none"
        elif motion.camera_motion in [CameraMotion.PAN_RIGHT, CameraMotion.TRACK_RIGHT]:
            kb_start = CompositionZone.MIDDLE_LEFT
            kb_end = CompositionZone.MIDDLE_RIGHT
            zoom_dir = "none"
        elif motion.camera_motion == CameraMotion.TILT_UP:
            kb_start = CompositionZone.BOTTOM_CENTER
            kb_end = CompositionZone.TOP_CENTER
            zoom_dir = "none"
        elif motion.camera_motion == CameraMotion.TILT_DOWN:
            kb_start = CompositionZone.TOP_CENTER
            kb_end = CompositionZone.BOTTOM_CENTER
            zoom_dir = "none"
        else:
            kb_start = CompositionZone.CENTER
            kb_end = CompositionZone.CENTER
            zoom_dir = "none"

        # Fill ratio based on lighting style
        if lighting_style in [LightingStyle.LOW_KEY, LightingStyle.DRAMATIC, LightingStyle.SILHOUETTE]:
            fill_ratio = "high_contrast"
        elif lighting_style in [LightingStyle.HIGH_KEY, LightingStyle.DIFFUSED]:
            fill_ratio = "balanced"
        else:
            fill_ratio = "balanced"

        # Key light direction based on shot role
        if shot_role == ShotRole.ESTABLISHING:
            key_light = "back" if lighting_style == LightingStyle.SILHOUETTE else "front"
        elif shot_role == ShotRole.DETAIL:
            key_light = "side"
        elif emotion == "mystery":
            key_light = "back"
        else:
            key_light = "side" if intensity > 0.6 else "front"

        # Style keywords for image generation
        style_keywords = [
            "cinematic",
            "film grain",
            "high production value",
            f"{scene.setting.era} era",
        ]
        if intensity > 0.7:
            style_keywords.append("dramatic")
        if shot_role == ShotRole.ESTABLISHING:
            style_keywords.append("epic scale")
        if shot_role == ShotRole.DETAIL:
            style_keywords.append("macro photography")

        # Reference films based on era and mood (documentary style)
        reference_films = []
        era_lower = scene.setting.era.lower() if scene.setting.era else ""
        if "rome" in era_lower or "roman" in era_lower:
            reference_films = ["Gladiator", "Rome HBO", "Ben-Hur"]
        elif "greek" in era_lower:
            reference_films = ["Troy", "300", "Alexander"]
        elif "medieval" in era_lower:
            reference_films = ["Kingdom of Heaven", "The Last Duel"]
        elif "egypt" in era_lower:
            reference_films = ["The Egyptian", "Cleopatra"]
        else:
            reference_films = ["Planet Earth", "Ken Burns documentaries"]

        # Create subject entities
        subjects = []
        if scene.setting.location_name:
            subjects.append(SubjectEntity(
                entity_type="location",
                name=scene.setting.location_name,
                screen_position=primary_zone,
                prominence="primary" if shot_role == ShotRole.ESTABLISHING else "background",
            ))

        # Add visual symbols based on emotion
        symbols = []
        symbol_map = {
            "sorrow": VisualSymbol(symbol="shadows", meaning="grief and loss", visual_treatment="prominent in frame"),
            "hope": VisualSymbol(symbol="light breaking through", meaning="optimism", visual_treatment="lens flare"),
            "triumph": VisualSymbol(symbol="elevated position", meaning="victory", visual_treatment="low angle"),
            "tension": VisualSymbol(symbol="confined space", meaning="pressure", visual_treatment="tight framing"),
        }
        if emotion in symbol_map:
            symbols.append(symbol_map[emotion])

        return ShotVisualSpec(
            role=shot_role,
            lens_type=lens_type,
            camera_height=camera_height,
            primary_zone=primary_zone,
            lighting_style=lighting_style,
            key_light_direction=key_light,
            fill_ratio=fill_ratio,
            subjects=subjects,
            color_palette=color_palette,
            color_temperature=color_temperature,
            symbols=symbols,
            ken_burns_start_zone=kb_start,
            ken_burns_end_zone=kb_end,
            zoom_direction=zoom_dir,
            style_keywords=style_keywords,
            reference_films=reference_films,
        )

    def _create_hook_shot(
        self,
        scene: Scene,
        strategy: HookStrategy,
        duration: float,
        plan_id: str,
        previous_shot_type: ShotType | None,
    ) -> Shot:
        """Create the hook shot (first 3 seconds)."""

        # Select shot type based on strategy
        if strategy == HookStrategy.VISUAL_IMPACT:
            shot_type = ShotType.EXTREME_WIDE
            subject = scene.setting.location_name
            description = f"Dramatic establishing shot of {subject}"
            motion = MotionSpec(
                camera_motion=CameraMotion.ZOOM_IN,
                motion_speed=MotionSpeed.SLOW,
            )
        elif strategy == HookStrategy.MYSTERY:
            shot_type = ShotType.EXTREME_CLOSE
            subject = "Intriguing detail"
            description = f"Mysterious close-up revealing atmosphere"
            motion = MotionSpec(
                camera_motion=CameraMotion.DOLLY_OUT,
                motion_speed=MotionSpeed.VERY_SLOW,
            )
        elif strategy == HookStrategy.ACTION:
            shot_type = ShotType.MEDIUM
            subject = "Key action"
            description = f"Dynamic shot capturing movement"
            motion = MotionSpec(
                camera_motion=CameraMotion.TRACK_RIGHT,
                motion_speed=MotionSpeed.MODERATE,
            )
        else:  # EMOTIONAL
            shot_type = ShotType.CLOSE_UP
            subject = "Character emotion"
            description = f"Emotional close-up capturing {scene.emotional_beat.primary_emotion}"
            motion = MotionSpec(
                camera_motion=CameraMotion.STATIC,
                motion_speed=MotionSpeed.SLOW,
            )

        # Avoid repeating previous shot type
        if previous_shot_type and shot_type == previous_shot_type:
            shot_type = ShotType.MEDIUM if shot_type != ShotType.MEDIUM else ShotType.WIDE

        # Determine shot role based on hook strategy
        role_map = {
            HookStrategy.VISUAL_IMPACT: ShotRole.ESTABLISHING,
            HookStrategy.MYSTERY: ShotRole.DETAIL,
            HookStrategy.ACTION: ShotRole.ACTION,
            HookStrategy.EMOTIONAL: ShotRole.REACTION,
        }
        shot_role = role_map.get(strategy, ShotRole.ESTABLISHING)

        # Create visual specification
        visual_spec = self._create_visual_spec(
            shot_role=shot_role,
            shot_type=shot_type,
            motion=motion,
            scene=scene,
            sequence=1,
            total_shots=1,  # Unknown at this point
        )

        return Shot(
            shot_plan_id=plan_id,
            sequence=1,
            shot_type=shot_type,
            duration_seconds=duration,
            subject=subject,
            mood=scene.emotional_beat.primary_emotion,
            lighting="dramatic" if strategy in [HookStrategy.VISUAL_IMPACT, HookStrategy.EMOTIONAL] else "natural",
            visual_description=description,
            narration_text=scene.summary[:80] if scene.summary else None,
            composition=Composition(
                framing=Framing.CENTERED,
                angle=CameraAngle.EYE_LEVEL if strategy != HookStrategy.VISUAL_IMPACT else CameraAngle.LOW_ANGLE,
                depth_of_field=DepthOfField.SHALLOW if strategy == HookStrategy.EMOTIONAL else DepthOfField.DEEP,
            ),
            motion=motion,
            visual_spec=visual_spec,
        )

    def _create_middle_shot(
        self,
        scene: Scene,
        sequence: int,
        shot_type: ShotType,
        duration: float,
        plan_id: str,
        analysis: dict,
        config: DirectorConfig,
    ) -> Shot:
        """Create a middle shot."""

        subjects = {
            ShotType.WIDE: scene.setting.location_name,
            ShotType.MEDIUM_WIDE: f"Activity in {scene.setting.location_name}",
            ShotType.MEDIUM: "Scene subject",
            ShotType.MEDIUM_CLOSE: "Character or key element",
            ShotType.CLOSE_UP: "Important detail",
            ShotType.CUTAWAY: "Contextual detail",
            ShotType.POV: "Character perspective",
        }

        # Select motion based on pacing
        pacing = analysis["pacing"]
        if pacing == PacingStyle.CONTEMPLATIVE:
            motion = MotionSpec(
                camera_motion=CameraMotion.STATIC,
                motion_speed=MotionSpeed.SLOW,
            )
        elif pacing == PacingStyle.DYNAMIC:
            motions = [CameraMotion.PAN_LEFT, CameraMotion.PAN_RIGHT, CameraMotion.ZOOM_IN]
            motion = MotionSpec(
                camera_motion=motions[sequence % len(motions)],
                motion_speed=MotionSpeed.MODERATE,
            )
        elif pacing == PacingStyle.INTENSE:
            motion = MotionSpec(
                camera_motion=CameraMotion.ZOOM_IN,
                motion_speed=MotionSpeed.FAST,
            )
        else:
            motion = MotionSpec()

        # Determine shot role based on shot type and position
        if shot_type in [ShotType.CLOSE_UP, ShotType.EXTREME_CLOSE]:
            shot_role = ShotRole.DETAIL
        elif shot_type == ShotType.CUTAWAY:
            shot_role = ShotRole.DETAIL
        elif shot_type == ShotType.POV:
            shot_role = ShotRole.REACTION
        elif analysis["intensity"] > 0.7:
            shot_role = ShotRole.CLIMAX
        else:
            shot_role = ShotRole.ACTION

        # Create visual specification
        visual_spec = self._create_visual_spec(
            shot_role=shot_role,
            shot_type=shot_type,
            motion=motion,
            scene=scene,
            sequence=sequence,
            total_shots=analysis["shot_count"],
        )

        return Shot(
            shot_plan_id=plan_id,
            sequence=sequence,
            shot_type=shot_type,
            duration_seconds=duration,
            subject=subjects.get(shot_type, "Scene element"),
            mood=scene.emotional_beat.primary_emotion,
            lighting="natural",
            visual_description=f"{shot_type.value} shot of {subjects.get(shot_type, 'scene')}",
            composition=Composition(),
            motion=motion,
            visual_spec=visual_spec,
        )

    def _create_closing_shot(
        self,
        scene: Scene,
        sequence: int,
        duration: float,
        plan_id: str,
        analysis: dict,
        is_final_scene: bool,
    ) -> Shot:
        """Create the closing shot."""

        if is_final_scene:
            # Final scene of story - wide shot for closure
            shot_type = ShotType.EXTREME_WIDE
            description = f"Final wide shot of {scene.setting.location_name}"
            motion = MotionSpec(
                camera_motion=CameraMotion.ZOOM_OUT,
                motion_speed=MotionSpeed.VERY_SLOW,
            )
            shot_role = ShotRole.RESOLUTION
        else:
            # Transition shot - medium for continuity
            shot_type = ShotType.MEDIUM
            description = f"Closing shot bridging to next scene"
            motion = MotionSpec(
                camera_motion=CameraMotion.STATIC,
                motion_speed=MotionSpeed.SLOW,
            )
            shot_role = ShotRole.TRANSITION

        # Create visual specification
        visual_spec = self._create_visual_spec(
            shot_role=shot_role,
            shot_type=shot_type,
            motion=motion,
            scene=scene,
            sequence=sequence,
            total_shots=analysis["shot_count"],
        )

        return Shot(
            shot_plan_id=plan_id,
            sequence=sequence,
            shot_type=shot_type,
            duration_seconds=max(duration, 2.0),
            subject=scene.setting.location_name,
            mood=scene.emotional_beat.primary_emotion,
            lighting="natural",
            visual_description=description,
            composition=Composition(
                framing=Framing.CENTERED,
                angle=CameraAngle.EYE_LEVEL,
                depth_of_field=DepthOfField.DEEP,
            ),
            motion=motion,
            visual_spec=visual_spec,
        )

    def _calculate_shot_duration(
        self,
        remaining_duration: float,
        remaining_shots: int,
        pacing: PacingStyle,
        config: DirectorConfig,
    ) -> float:
        """Calculate duration for a single shot."""

        avg_duration = remaining_duration / max(remaining_shots, 1)

        # Adjust based on pacing
        pacing_factor = {
            PacingStyle.CONTEMPLATIVE: 1.2,
            PacingStyle.MODERATE: 1.0,
            PacingStyle.DYNAMIC: 0.8,
            PacingStyle.INTENSE: 0.6,
        }.get(pacing, 1.0)

        duration = avg_duration * pacing_factor

        # Clamp to limits
        duration = max(config.min_shot_duration, min(config.max_shot_duration, duration))

        return round(duration, 1)

    def _select_shot_type(
        self,
        index: int,
        total: int,
        used_types: set[ShotType],
        pacing: PacingStyle,
        config: DirectorConfig,
    ) -> ShotType:
        """Select shot type with variety."""

        # Preferred shot type sequence
        preferred = [
            ShotType.MEDIUM,
            ShotType.CLOSE_UP,
            ShotType.MEDIUM_WIDE,
            ShotType.CUTAWAY,
            ShotType.MEDIUM_CLOSE,
            ShotType.WIDE,
        ]

        # Intense pacing prefers closer shots
        if pacing == PacingStyle.INTENSE:
            preferred = [
                ShotType.CLOSE_UP,
                ShotType.MEDIUM_CLOSE,
                ShotType.MEDIUM,
                ShotType.CUTAWAY,
            ]

        # Select based on variety preference
        if config.prefer_variety:
            for shot_type in preferred:
                if shot_type not in used_types:
                    return shot_type

        # Fall back to index-based selection
        return preferred[index % len(preferred)]

    def _add_transitions(
        self,
        shots: list[Shot],
        pacing: PacingStyle,
    ) -> list[Shot]:
        """Add transitions between shots."""

        # Select transition type based on pacing
        if pacing == PacingStyle.CONTEMPLATIVE:
            transition_type = TransitionType.DISSOLVE
            duration = 0.8
        elif pacing == PacingStyle.INTENSE:
            transition_type = TransitionType.CUT
            duration = 0.0
        else:
            transition_type = TransitionType.CUT
            duration = 0.0

        updated_shots = []
        for i, shot in enumerate(shots):
            if i < len(shots) - 1:
                shot = shot.model_copy(update={
                    "transition_out": Transition(
                        type=transition_type,
                        duration_seconds=duration,
                    )
                })
            updated_shots.append(shot)

        return updated_shots

    def _add_audio_cues(
        self,
        shots: list[Shot],
        scene: Scene,
        analysis: dict,
    ) -> list[Shot]:
        """Add audio cues to shots."""

        updated_shots = []
        for i, shot in enumerate(shots):
            cues = list(shot.audio_cues)

            # First shot: music start
            if i == 0:
                cues.append(AudioCue(
                    cue_type=AudioCueType.MUSIC_START,
                    description=f"Begin {scene.emotional_beat.primary_emotion} mood music",
                    timing="start",
                ))

            # Peak intensity shot: music swell
            if i == len(shots) // 2 and analysis["intensity"] > 0.6:
                cues.append(AudioCue(
                    cue_type=AudioCueType.MUSIC_SWELL,
                    description="Emotional peak",
                    timing="middle",
                ))

            # Last shot: music fade
            if i == len(shots) - 1:
                cues.append(AudioCue(
                    cue_type=AudioCueType.MUSIC_FADE,
                    description="Fade out",
                    timing="end",
                ))

            if cues != shot.audio_cues:
                shot = shot.model_copy(update={"audio_cues": cues})

            updated_shots.append(shot)

        return updated_shots

    def _apply_constraints(
        self,
        shots: list[Shot],
        constraints: list[str],
    ) -> tuple[list[Shot], list[AppliedConstraint]]:
        """Apply playbook constraints from feedback. Returns (updated_shots, applied_constraints)."""

        updated_shots = shots.copy()
        applied = []

        for constraint in constraints:
            constraint_lower = constraint.lower()

            # Constraint: avoid certain shot types
            if "avoid_extreme_close" in constraint_lower:
                affected = [s.id for s in updated_shots if s.shot_type == ShotType.EXTREME_CLOSE]
                if affected:
                    updated_shots = [
                        s.model_copy(update={"shot_type": ShotType.CLOSE_UP})
                        if s.shot_type == ShotType.EXTREME_CLOSE else s
                        for s in updated_shots
                    ]
                    applied.append(AppliedConstraint(
                        constraint=constraint,
                        applied_to=affected,
                        parameter_changes={"shot_type": "EXTREME_CLOSE -> CLOSE_UP"},
                    ))

            # Constraint: minimum duration
            if "min_duration" in constraint_lower:
                try:
                    min_dur = float(constraint.split(":")[-1])
                    affected = [s.id for s in updated_shots if s.duration_seconds < min_dur]
                    if affected:
                        updated_shots = [
                            s.model_copy(update={"duration_seconds": max(s.duration_seconds, min_dur)})
                            for s in updated_shots
                        ]
                        applied.append(AppliedConstraint(
                            constraint=constraint,
                            applied_to=affected,
                            parameter_changes={"min_duration": min_dur},
                        ))
                except ValueError:
                    pass

            # Constraint: prefer static shots
            if "prefer_static" in constraint_lower:
                affected = [s.id for s in updated_shots if s.motion.camera_motion != CameraMotion.STATIC]
                if affected:
                    updated_shots = [
                        s.model_copy(update={
                            "motion": MotionSpec(camera_motion=CameraMotion.STATIC)
                        })
                        for s in updated_shots
                    ]
                    applied.append(AppliedConstraint(
                        constraint=constraint,
                        applied_to=affected,
                        parameter_changes={"camera_motion": "* -> STATIC"},
                    ))

            # Constraint: reduce shot count (pacing too fast)
            if "reduce_shots" in constraint_lower or "fewer_shots" in constraint_lower:
                if len(updated_shots) > 4:
                    # Remove every other middle shot
                    middle_shots = updated_shots[1:-1]
                    keep_indices = [0] + [i+1 for i in range(0, len(middle_shots), 2)] + [len(updated_shots)-1]
                    removed = [s.id for i, s in enumerate(updated_shots) if i not in keep_indices]
                    updated_shots = [updated_shots[i] for i in keep_indices]
                    applied.append(AppliedConstraint(
                        constraint=constraint,
                        applied_to=removed,
                        parameter_changes={"action": "removed_shots", "removed_count": len(removed)},
                    ))

            # Constraint: longer establishing shots
            if "longer_establishing" in constraint_lower:
                affected = []
                new_shots = []
                for s in updated_shots:
                    if s.shot_type in [ShotType.EXTREME_WIDE, ShotType.WIDE] and s.sequence == 1:
                        affected.append(s.id)
                        new_shots.append(s.model_copy(update={"duration_seconds": s.duration_seconds * 1.5}))
                    else:
                        new_shots.append(s)
                if affected:
                    updated_shots = new_shots
                    applied.append(AppliedConstraint(
                        constraint=constraint,
                        applied_to=affected,
                        parameter_changes={"duration_multiplier": 1.5},
                    ))

            # Constraint: mystery hook strategy
            if "hook_mystery" in constraint_lower or "mystery_hook" in constraint_lower:
                if updated_shots and updated_shots[0].sequence == 1:
                    first = updated_shots[0]
                    updated_shots[0] = first.model_copy(update={
                        "shot_type": ShotType.EXTREME_CLOSE,
                        "motion": MotionSpec(camera_motion=CameraMotion.DOLLY_OUT, motion_speed=MotionSpeed.VERY_SLOW),
                        "visual_description": f"Mysterious close-up detail - {first.visual_description}",
                    })
                    applied.append(AppliedConstraint(
                        constraint=constraint,
                        applied_to=[first.id],
                        parameter_changes={"hook_strategy": "MYSTERY", "shot_type": "EXTREME_CLOSE"},
                    ))

        logger.info("constraints_applied", count=len(applied), total_constraints=len(constraints))
        return updated_shots, applied

    def _count_hook_shots(
        self,
        shots: list[Shot],
        hook_duration: float,
    ) -> int:
        """Count shots within hook duration."""
        total = 0.0
        count = 0
        for shot in shots:
            total += shot.duration_seconds
            count += 1
            if total >= hook_duration:
                break
        return count

    def _generate_creative_direction(
        self,
        scene: Scene,
        analysis: dict,
    ) -> str:
        """Generate creative direction summary."""
        return (
            f"{analysis['pacing'].value.capitalize()} pacing documentary coverage of "
            f"{scene.setting.location_name}. "
            f"Emotional tone: {scene.emotional_beat.primary_emotion} "
            f"(intensity: {analysis['intensity']:.0%}). "
            f"Era: {scene.setting.era}."
        )

    def _generate_pacing_rationale(
        self,
        analysis: dict,
        config: DirectorConfig,
    ) -> str:
        """Generate pacing rationale."""
        return (
            f"Using {analysis['pacing'].value} pacing with {analysis['shot_count']} shots. "
            f"Scene complexity: {analysis['complexity']:.0%}. "
            f"Target duration: {config.target_duration_seconds}s."
        )


# =============================================================================
# Convenience Functions
# =============================================================================


async def create_shot_plans(
    scene_graph: SceneGraph,
    config: DirectorConfig | None = None,
) -> tuple[list[ShotPlan], list[Shot]]:
    """Create shot plans for all scenes in a SceneGraph."""

    config = config or DirectorConfig()
    director = DirectorAgent()

    all_plans = []
    all_shots = []
    previous_shot_type = None

    for i, scene in enumerate(scene_graph.scenes):
        result = await director(DirectorInput(
            scene=scene,
            scene_index=i,
            total_scenes=len(scene_graph.scenes),
            config=config,
            previous_ending_shot_type=previous_shot_type,
            story_mood=scene_graph.story.source_metadata.genre or "neutral",
        ))

        all_plans.append(result.shot_plan)
        all_shots.extend(result.shots)

        # Track last shot type for continuity
        if result.shots:
            previous_shot_type = result.shots[-1].shot_type

    return all_plans, all_shots
