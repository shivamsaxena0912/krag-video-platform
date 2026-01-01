"""Story Parser Agent v1 - Parses text into SceneGraph."""

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.agents.base import BaseAgent, AgentConfig
from src.common.logging import get_logger
from src.common.models import (
    Story,
    Scene,
    SceneSetting,
    EmotionalBeat,
    EmotionalArc,
    TimeOfDay,
    Character,
    CharacterRole,
    CharacterImportance,
    Location,
    LocationType,
    SourceType,
    SourceMetadata,
    StoryStatus,
    ShotPlan,
    ShotPlanStatus,
    Shot,
    ShotType,
    Composition,
    MotionSpec,
    CameraMotion,
)
from src.knowledge_graph.scene_graph import SceneGraph

logger = get_logger(__name__)


# =============================================================================
# Input/Output Models
# =============================================================================


class StoryParserInput(BaseModel):
    """Input for the Story Parser Agent."""

    text: str
    title: str = ""
    source_type: SourceType = SourceType.NARRATIVE
    author: str | None = None
    era: str | None = None


class StoryParserOutput(BaseModel):
    """Output from the Story Parser Agent."""

    scene_graph: SceneGraph
    parsing_stats: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Story Parser Agent
# =============================================================================


class StoryParserAgent(BaseAgent[StoryParserInput, StoryParserOutput]):
    """
    Parses narrative text into a structured SceneGraph.

    This is a v1 rule-based implementation. Future versions will use LLM
    for more sophisticated parsing.
    """

    def __init__(self):
        super().__init__(AgentConfig(name="StoryParserAgent"))

    async def execute(self, input: StoryParserInput) -> StoryParserOutput:
        """Parse text into a SceneGraph."""
        logger.info("parsing_story", title=input.title)

        # Parse sections from text
        sections = self._extract_sections(input.text)

        # Create story
        story = self._create_story(input, len(sections))

        # Parse scenes
        scenes = []
        characters = {}
        locations = {}

        for i, section in enumerate(sections):
            scene, scene_chars, scene_locs = self._parse_section(
                section,
                story.id,
                i + 1,
            )
            scenes.append(scene)

            # Merge characters and locations
            for char in scene_chars:
                if char.name not in characters:
                    characters[char.name] = char
            for loc in scene_locs:
                if loc.name not in locations:
                    locations[loc.name] = loc

        # Create shot plans for each scene
        shot_plans = []
        shots = []
        for scene in scenes:
            plan, scene_shots = self._create_shot_plan(scene)
            shot_plans.append(plan)
            shots.extend(scene_shots)

            # Update scene with shot plan reference
            scene = scene.model_copy(update={
                "has_shot_plan": True,
                "shot_plan_id": plan.id,
            })

        # Build character appearances map
        character_appearances = {}
        for scene in scenes:
            char_ids = []
            for char_name, char in characters.items():
                if char_name.lower() in scene.raw_text.lower():
                    char_ids.append(char.id)
            if char_ids:
                character_appearances[scene.id] = char_ids

        # Create SceneGraph
        scene_graph = SceneGraph(
            story=story,
            scenes=scenes,
            characters=list(characters.values()),
            locations=list(locations.values()),
            shot_plans=shot_plans,
            shots=shots,
            character_appearances=character_appearances,
        )

        stats = {
            "sections_found": len(sections),
            "scenes_created": len(scenes),
            "characters_found": len(characters),
            "locations_found": len(locations),
            "shots_created": len(shots),
        }

        logger.info("story_parsed", **stats)

        return StoryParserOutput(
            scene_graph=scene_graph,
            parsing_stats=stats,
        )

    def _extract_sections(self, text: str) -> list[dict]:
        """Extract sections from text using markdown headers."""
        sections = []

        # Split by ## headers (scene markers)
        pattern = r"##\s+(.+?)(?=\n##|\Z)"
        matches = re.findall(pattern, text, re.DOTALL)

        for match in matches:
            lines = match.strip().split("\n", 1)
            title = lines[0].strip()
            content = lines[1].strip() if len(lines) > 1 else ""

            if content:  # Skip empty sections
                sections.append({
                    "title": title,
                    "content": content,
                })

        return sections

    def _create_story(self, input: StoryParserInput, scene_count: int) -> Story:
        """Create Story from input."""
        title = input.title or self._extract_title(input.text)

        return Story(
            title=title,
            source_type=input.source_type,
            source_metadata=SourceMetadata(
                title=title,
                author=input.author,
                era=input.era or self._detect_era(input.text),
                genre="historical",
            ),
            status=StoryStatus.PARSED,
            total_scenes=scene_count,
            raw_text=input.text,
        )

    def _extract_title(self, text: str) -> str:
        """Extract title from text (first # header)."""
        match = re.search(r"#\s+(.+?)(?:\n|$)", text)
        if match:
            return match.group(1).strip()
        return "Untitled Story"

    def _detect_era(self, text: str) -> str:
        """Detect historical era from text."""
        text_lower = text.lower()
        if "rome" in text_lower or "roman" in text_lower:
            return "Ancient Rome"
        if "medieval" in text_lower:
            return "Medieval"
        if "renaissance" in text_lower:
            return "Renaissance"
        return "Historical"

    def _parse_section(
        self,
        section: dict,
        story_id: str,
        sequence: int,
    ) -> tuple[Scene, list[Character], list[Location]]:
        """Parse a section into a Scene with characters and locations."""
        title = section["title"]
        content = section["content"]

        # Detect setting
        setting = self._detect_setting(content)

        # Detect emotional beat
        emotional_beat = self._detect_emotional_beat(content)

        # Extract characters mentioned
        characters = self._extract_characters(content, story_id)

        # Extract locations mentioned
        locations = self._extract_locations(content, story_id)

        # Create scene
        scene = Scene(
            story_id=story_id,
            sequence=sequence,
            raw_text=content,
            summary=self._generate_summary(title, content),
            setting=setting,
            emotional_beat=emotional_beat,
            word_count=len(content.split()),
            estimated_duration_seconds=len(content.split()) / 2.5,  # ~150 wpm
            characters=[c.id for c in characters],
            locations=[l.id for l in locations],
        )

        return scene, characters, locations

    def _detect_setting(self, text: str) -> SceneSetting:
        """Detect setting from text."""
        text_lower = text.lower()

        # Detect location
        location_name = "Unknown Location"
        if "colosseum" in text_lower:
            location_name = "The Colosseum"
        elif "rome" in text_lower:
            location_name = "Rome"
        elif "danube" in text_lower:
            location_name = "Danube Frontier"
        elif "arena" in text_lower:
            location_name = "The Arena"
        elif "temple" in text_lower:
            location_name = "Roman Temple"

        # Detect time of day
        time_of_day = TimeOfDay.UNSPECIFIED
        if "night" in text_lower or "candlelight" in text_lower:
            time_of_day = TimeOfDay.NIGHT
        elif "morning" in text_lower or "dawn" in text_lower:
            time_of_day = TimeOfDay.MORNING
        elif "afternoon" in text_lower or "sun" in text_lower:
            time_of_day = TimeOfDay.AFTERNOON
        elif "evening" in text_lower or "twilight" in text_lower:
            time_of_day = TimeOfDay.EVENING

        # Detect atmosphere
        atmosphere = "neutral"
        if any(w in text_lower for w in ["chaos", "crisis", "storm"]):
            atmosphere = "chaotic"
        elif any(w in text_lower for w in ["glory", "power", "triumph"]):
            atmosphere = "triumphant"
        elif any(w in text_lower for w in ["sad", "fall", "end"]):
            atmosphere = "melancholic"
        elif any(w in text_lower for w in ["contemplat", "meditat", "thought"]):
            atmosphere = "contemplative"

        return SceneSetting(
            location_name=location_name,
            location_description=f"A scene set in {location_name}",
            time_of_day=time_of_day,
            era="Ancient Rome",
            atmosphere=atmosphere,
            interior_exterior="mixed",
        )

    def _detect_emotional_beat(self, text: str) -> EmotionalBeat:
        """Detect emotional beat from text."""
        text_lower = text.lower()

        # Detect primary emotion
        emotion = "neutral"
        intensity = 0.5

        if any(w in text_lower for w in ["horror", "shock", "fear"]):
            emotion = "tension"
            intensity = 0.8
        elif any(w in text_lower for w in ["glory", "power", "triumph"]):
            emotion = "triumph"
            intensity = 0.7
        elif any(w in text_lower for w in ["sad", "mourn", "lost"]):
            emotion = "sorrow"
            intensity = 0.6
        elif any(w in text_lower for w in ["chaos", "crisis", "collapse"]):
            emotion = "anxiety"
            intensity = 0.75
        elif any(w in text_lower for w in ["hope", "endure", "legacy"]):
            emotion = "hope"
            intensity = 0.6

        # Detect arc
        arc = EmotionalArc.STABLE
        if any(w in text_lower for w in ["begin", "rise", "growing"]):
            arc = EmotionalArc.RISING
        elif any(w in text_lower for w in ["fall", "end", "collapse"]):
            arc = EmotionalArc.FALLING
        elif any(w in text_lower for w in ["climax", "peak", "ultimate"]):
            arc = EmotionalArc.PEAK

        return EmotionalBeat(
            primary_emotion=emotion,
            intensity=intensity,
            arc=arc,
            narrative_function="exposition",
        )

    def _extract_characters(
        self,
        text: str,
        story_id: str,
    ) -> list[Character]:
        """Extract characters from text."""
        characters = []

        # Known historical figures
        char_patterns = [
            ("Marcus Aurelius", "Roman emperor, philosopher, stoic, elderly, bearded",
             CharacterRole.PROTAGONIST, CharacterImportance.PRIMARY),
            ("Commodus", "Young Roman emperor, arrogant, muscular, dressed in lion skins",
             CharacterRole.ANTAGONIST, CharacterImportance.PRIMARY),
            ("Diocletian", "Roman soldier-emperor, stern, authoritative, Dalmatian",
             CharacterRole.SUPPORTING, CharacterImportance.SECONDARY),
            ("Constantine", "Roman emperor, visionary, military leader",
             CharacterRole.SUPPORTING, CharacterImportance.SECONDARY),
            ("Alaric", "Visigoth king, barbarian warrior, Christian",
             CharacterRole.SUPPORTING, CharacterImportance.SECONDARY),
        ]

        for name, description, role, importance in char_patterns:
            if name.lower() in text.lower():
                characters.append(Character(
                    story_id=story_id,
                    name=name,
                    physical_description=description,
                    role=role,
                    importance=importance,
                    visual_prompt=f"Historical portrait of {name}, {description}, ancient Rome, cinematic lighting",
                ))

        return characters

    def _extract_locations(
        self,
        text: str,
        story_id: str,
    ) -> list[Location]:
        """Extract locations from text."""
        locations = []

        # Known locations
        loc_patterns = [
            ("Rome", "The eternal city, capital of the Roman Empire",
             LocationType.URBAN, "marble temples, crowded streets, seven hills"),
            ("Colosseum", "The great amphitheater of Rome",
             LocationType.BUILDING, "massive stone arena, tiered seating, underground chambers"),
            ("Danube Frontier", "Northern border of the Roman Empire",
             LocationType.OUTDOOR, "military camp, tents, forest, river"),
            ("Milvian Bridge", "Bridge over the Tiber near Rome",
             LocationType.OUTDOOR, "stone bridge, river, battlefield"),
        ]

        for name, description, loc_type, visual in loc_patterns:
            if name.lower() in text.lower():
                locations.append(Location(
                    story_id=story_id,
                    name=name,
                    description=description,
                    location_type=loc_type,
                    era="Ancient Rome",
                    visual_prompt=f"{name}, {visual}, ancient Rome, cinematic, epic scale",
                ))

        return locations

    def _generate_summary(self, title: str, content: str) -> str:
        """Generate a summary of the section."""
        # Simple extractive summary: first two sentences
        sentences = re.split(r'[.!?]', content)
        summary_sentences = [s.strip() for s in sentences[:2] if s.strip()]
        summary = ". ".join(summary_sentences) + "."

        return f"{title}: {summary}"

    def _create_shot_plan(
        self,
        scene: Scene,
    ) -> tuple[ShotPlan, list[Shot]]:
        """Create a basic shot plan for a scene."""
        plan_id = f"plan_{scene.id[6:]}"  # Use scene ID suffix

        shots = []

        # Establish shot (wide)
        shots.append(Shot(
            shot_plan_id=plan_id,
            sequence=1,
            shot_type=ShotType.WIDE,
            duration_seconds=4.0,
            subject=scene.setting.location_name,
            mood=scene.emotional_beat.primary_emotion,
            lighting="natural",
            visual_description=f"Establishing shot of {scene.setting.location_name}",
            narration_text=scene.summary[:100] if scene.summary else None,
            composition=Composition(),
            motion=MotionSpec(camera_motion=CameraMotion.SLOW if scene.estimated_duration_seconds > 30 else CameraMotion.STATIC),
        ))

        # Medium shot
        shots.append(Shot(
            shot_plan_id=plan_id,
            sequence=2,
            shot_type=ShotType.MEDIUM,
            duration_seconds=3.0,
            subject="Scene activity",
            mood=scene.emotional_beat.primary_emotion,
            lighting="natural",
            visual_description=f"Medium shot showing key action in {scene.setting.location_name}",
            composition=Composition(),
            motion=MotionSpec(),
        ))

        # Close-up (emotional beat)
        shots.append(Shot(
            shot_plan_id=plan_id,
            sequence=3,
            shot_type=ShotType.CLOSE_UP,
            duration_seconds=2.5,
            subject="Key detail or character",
            mood=scene.emotional_beat.primary_emotion,
            lighting="dramatic",
            visual_description=f"Close-up emphasizing {scene.emotional_beat.primary_emotion}",
            composition=Composition(),
            motion=MotionSpec(camera_motion=CameraMotion.ZOOM_IN),
        ))

        plan = ShotPlan(
            id=plan_id,
            scene_id=scene.id,
            shots=shots,
            status=ShotPlanStatus.DRAFT,
            estimated_duration_seconds=sum(s.duration_seconds for s in shots),
            creative_direction=f"Documentary style coverage of {scene.setting.location_name}",
            pacing_rationale=f"Contemplative pacing for {scene.emotional_beat.primary_emotion} mood",
        )

        return plan, shots


# =============================================================================
# Convenience Functions
# =============================================================================


async def parse_story_file(file_path: str | Path) -> StoryParserOutput:
    """Parse a story from a file."""
    path = Path(file_path)
    text = path.read_text()

    # Extract title from filename
    title = path.stem.replace("_", " ").title()

    agent = StoryParserAgent()
    return await agent(StoryParserInput(
        text=text,
        title=title,
    ))


async def parse_story_text(
    text: str,
    title: str = "",
    author: str | None = None,
) -> StoryParserOutput:
    """Parse a story from text."""
    agent = StoryParserAgent()
    return await agent(StoryParserInput(
        text=text,
        title=title,
        author=author,
    ))
