# Agent Specifications

## Design Principles

1. **Typed Contracts**: Every agent has explicit Pydantic input/output schemas
2. **Single Responsibility**: Each agent has one clear purpose
3. **Stateless Execution**: Agents don't maintain internal state between calls
4. **Deterministic Ordering**: Agent invocation order is fixed by the pipeline
5. **Observable**: All agent calls are logged with inputs, outputs, and metrics

## Agent Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            AGENT ORCHESTRATION                               │
│                                                                              │
│   PARSING & UNDERSTANDING                                                    │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐     │
│   │  Story Parser    │───▶│  Continuity &    │───▶│     KRAG         │     │
│   │     Agent        │    │   Canon Agent    │    │  Retrieval Agent │     │
│   └──────────────────┘    └──────────────────┘    └──────────────────┘     │
│                                                                              │
│   PLANNING & GENERATION                                                      │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐     │
│   │    Creative      │───▶│     Prompt       │───▶│      Asset       │     │
│   │  Director Agent  │    │  Engineer Agent  │    │  Generation Agent│     │
│   └──────────────────┘    └──────────────────┘    └──────────────────┘     │
│                                                                              │
│   ASSEMBLY & REFINEMENT                                                      │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐     │
│   │     Editor       │───▶│     Critic       │───▶│    Iterative     │     │
│   │     Agent        │    │     Agent        │    │   Refinement     │     │
│   └──────────────────┘    └──────────────────┘    └──────────────────┘     │
│                                                                              │
│   HUMAN OVERSIGHT                                                            │
│   ┌──────────────────┐                                                      │
│   │      HITL        │                                                      │
│   │   Gatekeeper     │                                                      │
│   └──────────────────┘                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Story Parser Agent

**Purpose**: Parse raw text into structured scene segments.

### Contract

```python
class StoryParserInput(BaseModel):
    """Input to the Story Parser Agent."""
    text: str
    source_metadata: SourceMetadata
    parsing_config: ParsingConfig = ParsingConfig()


class ParsingConfig(BaseModel):
    """Configuration for text parsing."""
    min_scene_length: int = 100
    max_scene_length: int = 2000
    detect_dialogue: bool = True
    detect_characters: bool = True
    era_hint: str | None = None


class StoryParserOutput(BaseModel):
    """Output from the Story Parser Agent."""
    story_id: str
    title: str
    segments: list[TextSegment]
    detected_characters: list[CharacterMention]
    detected_locations: list[LocationMention]
    parsing_metadata: ParsingMetadata


class TextSegment(BaseModel):
    """A parsed segment of text."""
    id: str
    sequence: int
    content: str
    segment_type: SegmentType  # SCENE, DIALOGUE, NARRATION, TRANSITION
    detected_elements: DetectedElements
    boundaries: SegmentBoundaries


class DetectedElements(BaseModel):
    """Elements detected within a segment."""
    characters: list[str]
    locations: list[str]
    time_markers: list[str]
    events: list[str]
    emotional_tone: str
    props: list[str]
```

### Behavior

1. Segment text by scene boundaries (location change, time jump, perspective shift)
2. Detect and tag characters, locations, events, props
3. Classify emotional tone for each segment
4. Preserve original text with boundary markers
5. Generate unique IDs for tracking

### Error Handling

| Error | Handling |
|-------|----------|
| Empty input | Return error, no output |
| Unparseable text | Best-effort parse with warnings |
| Too long | Chunk and process recursively |

---

## 2. Continuity & Canon Agent

**Purpose**: Validate and enforce narrative continuity across scenes.

### Contract

```python
class ContinuityInput(BaseModel):
    """Input to the Continuity Agent."""
    story_id: str
    segments: list[TextSegment]
    existing_canon: Canon | None = None


class Canon(BaseModel):
    """Established story canon."""
    characters: dict[str, CharacterCanon]
    locations: dict[str, LocationCanon]
    timeline: list[TimelineEvent]
    rules: list[CanonRule]


class ContinuityOutput(BaseModel):
    """Output from the Continuity Agent."""
    validated_scenes: list[ValidatedScene]
    canon_updates: list[CanonUpdate]
    violations: list[ContinuityViolation]
    warnings: list[ContinuityWarning]


class ValidatedScene(BaseModel):
    """A scene validated for continuity."""
    scene_id: str
    segment_id: str
    sequence: int
    setting: SceneSetting
    characters_present: list[CharacterPresence]
    events: list[SceneEvent]
    continuity_score: float  # 0-1
    continuity_notes: list[str]


class ContinuityViolation(BaseModel):
    """A detected continuity violation."""
    scene_id: str
    violation_type: ViolationType
    description: str
    severity: Severity  # LOW, MEDIUM, HIGH, CRITICAL
    suggested_fix: str | None
```

### Behavior

1. Build/update character introduction timeline
2. Track location establishment
3. Verify temporal consistency
4. Check prop persistence
5. Flag violations with severity

### Validation Rules

- Characters cannot appear before introduction
- Locations must be established before detailed shots
- Time cannot go backward without explicit marker
- Props mentioned must persist unless explicitly removed
- Character descriptions must be consistent

---

## 3. KRAG Retrieval Agent

**Purpose**: Retrieve relevant knowledge from text and video planes.

### Contract

```python
class KRAGRetrievalInput(BaseModel):
    """Input to the KRAG Retrieval Agent."""
    query_context: QueryContext
    retrieval_types: list[RetrievalType]
    top_k: int = 5
    filters: RetrievalFilters | None = None


class QueryContext(BaseModel):
    """Context for retrieval query."""
    scene: ValidatedScene | None
    shot: Shot | None
    free_text: str | None
    mood: str | None
    era: str | None


class RetrievalType(str, Enum):
    NARRATIVE_PATTERN = "narrative_pattern"
    SHOT_SEQUENCE = "shot_sequence"
    PACING_REFERENCE = "pacing_reference"
    NARRATION_STYLE = "narration_style"
    VISUAL_STYLE = "visual_style"
    MUSIC_MOOD = "music_mood"


class KRAGRetrievalOutput(BaseModel):
    """Output from the KRAG Retrieval Agent."""
    text_results: list[TextRetrievalResult]
    video_results: list[VideoRetrievalResult]
    graph_context: GraphContext
    retrieval_metadata: RetrievalMetadata


class TextRetrievalResult(BaseModel):
    """A result from text knowledge plane."""
    id: str
    content: str
    source: str
    similarity_score: float
    content_type: str
    metadata: dict


class VideoRetrievalResult(BaseModel):
    """A result from video knowledge plane."""
    id: str
    shot_sequence: list[ShotPattern]
    source_video: str
    similarity_score: float
    pacing_metrics: PacingMetrics
    metadata: dict
```

### Behavior

1. Query appropriate vector store(s) based on retrieval type
2. Enrich results with graph context
3. Re-rank based on quality scores and feedback history
4. Apply filters (era, mood, genre)
5. Return unified results with provenance

---

## 4. Creative Director Agent

**Purpose**: Create shot plans from validated scenes using cinematic knowledge.

### Contract

```python
class CreativeDirectorInput(BaseModel):
    """Input to the Creative Director Agent."""
    scene: ValidatedScene
    krag_context: KRAGRetrievalOutput
    style_guidelines: StyleGuidelines | None = None
    constraints: list[CreativeConstraint] = []


class StyleGuidelines(BaseModel):
    """Visual and pacing style guidelines."""
    visual_style: str  # e.g., "cinematic documentary"
    pacing: str  # e.g., "contemplative", "dynamic"
    color_palette: str | None
    era_treatment: str | None
    reference_videos: list[str] = []


class CreativeDirectorOutput(BaseModel):
    """Output from the Creative Director Agent."""
    shot_plan: ShotPlan
    creative_notes: list[str]
    estimated_duration_seconds: float
    complexity_score: float  # 0-1, affects generation cost


class ShotPlan(BaseModel):
    """Complete shot plan for a scene."""
    scene_id: str
    shots: list[PlannedShot]
    transitions: list[Transition]
    audio_plan: AudioPlan
    pacing_rationale: str


class PlannedShot(BaseModel):
    """A planned shot within a scene."""
    shot_id: str
    sequence: int
    shot_type: ShotType  # WIDE, MEDIUM, CLOSE_UP, EXTREME_CLOSE, CUTAWAY
    duration_seconds: float
    subject: str
    composition: str
    motion: MotionType  # STATIC, PAN_LEFT, PAN_RIGHT, ZOOM_IN, ZOOM_OUT, DOLLY
    mood: str
    visual_prompt_hints: list[str]
    narration_segment: str | None
    audio_cues: list[str]
```

### Behavior

1. Analyze scene for key visual moments
2. Retrieve similar shot sequences from KRAG
3. Apply cinematic grammar rules
4. Balance shot variety (wide → medium → close)
5. Plan transitions and pacing
6. Allocate narration to shots
7. Specify audio requirements

### Shot Planning Rules

- Open scenes with establishing shot (wide)
- Character introductions require medium or close-up
- Emotional beats get close-ups
- Action sequences use faster cuts
- Contemplative moments hold longer
- Transitions match emotional shifts

---

## 5. Prompt Engineering Agent

**Purpose**: Generate precise prompts for asset generation models.

### Contract

```python
class PromptEngineerInput(BaseModel):
    """Input to the Prompt Engineering Agent."""
    shot: PlannedShot
    scene_context: ValidatedScene
    character_visuals: dict[str, CharacterVisual]
    location_visuals: dict[str, LocationVisual]
    style_guidelines: StyleGuidelines


class PromptEngineerOutput(BaseModel):
    """Output from the Prompt Engineering Agent."""
    image_prompts: list[ImagePrompt]
    voiceover_prompts: list[VoiceoverPrompt]
    music_prompts: list[MusicPrompt]
    consistency_tokens: dict[str, str]  # For character/style consistency


class ImagePrompt(BaseModel):
    """Prompt for image generation."""
    shot_id: str
    positive_prompt: str
    negative_prompt: str
    style_reference: str | None
    aspect_ratio: str
    generation_params: ImageGenParams


class ImageGenParams(BaseModel):
    """Parameters for image generation."""
    model: str  # e.g., "sdxl", "dalle3"
    steps: int = 30
    cfg_scale: float = 7.5
    seed: int | None = None
    style_strength: float = 0.8


class VoiceoverPrompt(BaseModel):
    """Prompt for voiceover generation."""
    shot_id: str
    text: str
    voice_id: str
    emotion: str
    pacing: str  # "slow", "moderate", "fast"
    emphasis_words: list[str]
```

### Behavior

1. Translate shot descriptions to model-specific prompts
2. Maintain character visual consistency via tokens/references
3. Apply negative prompts for quality control
4. Specify technical parameters based on target quality
5. Chunk narration for natural voiceover

### Prompt Templates

```python
IMAGE_TEMPLATE = """
{style_prefix}

{subject} in {location}, {action}.
{time_of_day} lighting, {mood} atmosphere.
{era} period accurate, {composition} composition.

Style: {visual_style}
Quality: professional cinematography, 8k, detailed
"""

NEGATIVE_TEMPLATE = """
blurry, low quality, amateur, watermark, text,
anachronistic elements, modern objects, {era_exclusions}
"""
```

---

## 6. Asset Generation Agent

**Purpose**: Orchestrate generation of images, audio, and other assets.

### Contract

```python
class AssetGenerationInput(BaseModel):
    """Input to the Asset Generation Agent."""
    prompts: PromptEngineerOutput
    quality_target: QualityTarget
    cost_budget: float | None = None
    existing_assets: list[ExistingAsset] = []


class QualityTarget(BaseModel):
    """Quality requirements for assets."""
    image_resolution: str = "1920x1080"
    voice_quality: str = "high"
    music_quality: str = "high"
    consistency_threshold: float = 0.85


class AssetGenerationOutput(BaseModel):
    """Output from the Asset Generation Agent."""
    generated_assets: list[GeneratedAsset]
    generation_costs: CostBreakdown
    quality_scores: dict[str, float]
    failures: list[GenerationFailure]


class GeneratedAsset(BaseModel):
    """A generated asset."""
    asset_id: str
    shot_id: str
    asset_type: AssetType  # IMAGE, VOICEOVER, MUSIC, SFX
    file_path: str
    generation_params: dict
    quality_score: float
    generation_time_seconds: float
    cost: float
```

### Behavior

1. Dispatch prompts to appropriate generation models
2. Apply rate limiting and cost controls
3. Validate output quality
4. Retry on failure with fallback models
5. Cache and reuse where appropriate
6. Track costs and timing

### Model Routing

| Asset Type | Primary | Fallback |
|------------|---------|----------|
| Image | SDXL | DALL-E 3 |
| Voiceover | ElevenLabs | OpenAI TTS |
| Music | Licensed library | Suno (future) |
| SFX | Licensed library | Generated |

---

## 7. Editor Agent

**Purpose**: Assemble assets into a coherent video timeline.

### Contract

```python
class EditorInput(BaseModel):
    """Input to the Editor Agent."""
    shot_plan: ShotPlan
    assets: list[GeneratedAsset]
    editing_style: EditingStyle


class EditingStyle(BaseModel):
    """Style parameters for editing."""
    transition_style: str  # "smooth", "dynamic", "minimal"
    motion_intensity: float  # 0-1
    subtitle_style: SubtitleStyle | None
    color_grading: str | None


class EditorOutput(BaseModel):
    """Output from the Editor Agent."""
    timeline: VideoTimeline
    draft_video_path: str
    duration_seconds: float
    edit_notes: list[str]


class VideoTimeline(BaseModel):
    """Complete video timeline."""
    scene_id: str
    tracks: list[TimelineTrack]
    total_duration: float
    render_settings: RenderSettings


class TimelineTrack(BaseModel):
    """A track in the timeline."""
    track_type: TrackType  # VIDEO, AUDIO_VO, AUDIO_MUSIC, AUDIO_SFX, SUBTITLE
    clips: list[TimelineClip]


class TimelineClip(BaseModel):
    """A clip on a timeline track."""
    clip_id: str
    asset_id: str
    start_time: float
    end_time: float
    effects: list[Effect]
    transitions: list[ClipTransition]
```

### Behavior

1. Sequence assets according to shot plan
2. Apply motion effects (Ken Burns, parallax)
3. Sync voiceover to visuals
4. Layer music and SFX
5. Add transitions between shots
6. Generate subtitles if required
7. Render draft video

### Motion Effects

| Effect | Parameters | Use Case |
|--------|------------|----------|
| Ken Burns | zoom %, direction | Static images |
| Parallax | layer depth, movement | Layered images |
| Fade | duration | Transitions |
| Crossfade | duration | Scene changes |

---

## 8. Critic Agent

**Purpose**: Evaluate draft videos and provide structured feedback.

### Contract

```python
class CriticInput(BaseModel):
    """Input to the Critic Agent."""
    draft_video_path: str
    shot_plan: ShotPlan
    scene_context: ValidatedScene
    evaluation_criteria: list[EvaluationCriterion]


class CriticOutput(BaseModel):
    """Output from the Critic Agent."""
    overall_score: float  # 1-10
    dimension_scores: DimensionScores
    issues: list[CriticIssue]
    strengths: list[str]
    recommendation: CriticRecommendation


class DimensionScores(BaseModel):
    """Scores across evaluation dimensions."""
    narrative_clarity: int  # 1-5
    hook_strength: int  # 1-5
    pacing: int  # 1-5
    shot_composition: int  # 1-5
    continuity: int  # 1-5
    audio_mix: int  # 1-5


class CriticIssue(BaseModel):
    """An issue identified by the critic."""
    issue_id: str
    severity: Severity
    dimension: str
    description: str
    timestamp_start: float | None
    timestamp_end: float | None
    fix_taxonomy: list[FixCategory]
    suggested_fix: str


class FixCategory(str, Enum):
    REGENERATE_IMAGE = "regenerate_image"
    ADJUST_TIMING = "adjust_timing"
    CHANGE_SHOT_TYPE = "change_shot_type"
    ADJUST_AUDIO_MIX = "adjust_audio_mix"
    REGENERATE_VOICEOVER = "regenerate_voiceover"
    ADD_TRANSITION = "add_transition"
    REWRITE_NARRATION = "rewrite_narration"


class CriticRecommendation(str, Enum):
    APPROVE = "approve"
    MINOR_FIXES = "minor_fixes"
    MAJOR_REVISION = "major_revision"
    REJECT = "reject"
```

### Behavior

1. Analyze video against shot plan
2. Score each dimension
3. Identify specific issues with timestamps
4. Categorize fixes needed
5. Make pass/fail recommendation
6. Compare against learned quality standards

### Evaluation Criteria

| Dimension | What's Evaluated |
|-----------|------------------|
| Narrative clarity | Is the story understandable? |
| Hook strength | Does it grab attention in first 3s? |
| Pacing | Are durations appropriate? |
| Shot composition | Are visuals well-framed? |
| Continuity | Are transitions smooth? |
| Audio mix | Are voice/music balanced? |

---

## 9. Iterative Refinement Controller

**Purpose**: Orchestrate the critique → fix → critique loop.

### Contract

```python
class RefinementInput(BaseModel):
    """Input to the Refinement Controller."""
    draft_video_path: str
    critic_output: CriticOutput
    shot_plan: ShotPlan
    assets: list[GeneratedAsset]
    max_iterations: int = 3
    cost_cap: float | None = None
    quality_threshold: float = 7.0


class RefinementOutput(BaseModel):
    """Output from the Refinement Controller."""
    final_video_path: str
    final_score: float
    iterations_used: int
    total_cost: float
    refinement_history: list[RefinementIteration]
    status: RefinementStatus


class RefinementIteration(BaseModel):
    """Record of one refinement iteration."""
    iteration: int
    issues_addressed: list[str]
    fixes_applied: list[AppliedFix]
    score_before: float
    score_after: float
    cost: float


class RefinementStatus(str, Enum):
    APPROVED = "approved"
    MAX_ITERATIONS = "max_iterations_reached"
    COST_CAP = "cost_cap_reached"
    FAILED = "failed"
```

### Behavior

1. Analyze critic feedback
2. Prioritize fixes by severity and cost
3. Execute fixes (regenerate assets, re-edit)
4. Re-run critic
5. Check convergence
6. Repeat until pass or limits reached

### Convergence Rules

- Stop if score >= threshold
- Stop if score improvement < 0.5 for 2 iterations
- Stop if max iterations reached
- Stop if cost cap exceeded

---

## 10. Human-in-the-Loop Gatekeeper

**Purpose**: Present videos for human review and collect structured feedback.

### Contract

```python
class HITLInput(BaseModel):
    """Input to the HITL Gatekeeper."""
    video_path: str
    ai_critic_output: CriticOutput
    scene_context: ValidatedScene
    refinement_history: list[RefinementIteration]


class HITLOutput(BaseModel):
    """Output from the HITL Gatekeeper."""
    decision: HITLDecision
    human_feedback: HumanFeedback | None
    reviewer_id: str
    review_time_seconds: float


class HITLDecision(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class HumanFeedback(BaseModel):
    """Structured feedback from human reviewer."""
    dimension_scores: DimensionScores
    timestamped_notes: list[TimestampedNote]
    fix_requests: list[FixRequest]
    overall_notes: str
```

### Behavior

1. Present video via review interface
2. Show AI critic scores and notes
3. Collect structured human feedback
4. Route decision (approve/revise/reject)
5. Store feedback for learning

### Review Interface (Future)

- Video player with timestamp markers
- Side-by-side with shot plan
- Dimension score sliders
- Note input with timestamp linking
- Approve/Reject buttons

---

## Agent Infrastructure

### Base Agent Class

```python
class BaseAgent(ABC, Generic[TInput, TOutput]):
    """Base class for all agents."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        self.metrics = MetricsCollector()

    @abstractmethod
    async def execute(self, input: TInput) -> TOutput:
        """Execute the agent's primary function."""
        pass

    async def __call__(self, input: TInput) -> TOutput:
        """Execute with logging and metrics."""
        start = time.time()
        self.logger.info(f"Starting execution", input_summary=input.summary())

        try:
            output = await self.execute(input)
            self.metrics.record_success(time.time() - start)
            self.logger.info(f"Execution complete", output_summary=output.summary())
            return output
        except Exception as e:
            self.metrics.record_failure(time.time() - start, str(e))
            self.logger.error(f"Execution failed", error=str(e))
            raise
```

### Agent Registry

```python
class AgentRegistry:
    """Registry for agent instances."""

    _agents: dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, name: str, agent: BaseAgent) -> None:
        cls._agents[name] = agent

    @classmethod
    def get(cls, name: str) -> BaseAgent:
        return cls._agents[name]
```

---

*See [data-models.md](data-models.md) for complete schema definitions.*
*See [architecture.md](architecture.md) for integration details.*
