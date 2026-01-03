# Pipeline Architecture

## Overview

The KRAG video platform uses a deterministic, stage-based pipeline architecture. Each stage produces versioned, inspectable artifacts that feed into subsequent stages.

## Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PIPELINE EXECUTION FLOW                            │
│                                                                              │
│   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐           │
│   │INGEST  │──▶│ PARSE  │──▶│ SCENE  │──▶│CONTINUE│──▶│  KRAG  │           │
│   │        │   │        │   │ GRAPH  │   │  ITY   │   │RETRIEVE│           │
│   └────────┘   └────────┘   └────────┘   └────────┘   └────────┘           │
│                                                              │               │
│   ┌────────────────────────────────────────────────────────┘               │
│   │                                                                         │
│   ▼                                                                         │
│   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐           │
│   │  SHOT  │──▶│ PROMPT │──▶│ ASSET  │──▶│ASSEMBLE│──▶│CRITIQUE│           │
│   │  PLAN  │   │ENGINEER│   │GENERATE│   │        │   │        │           │
│   └────────┘   └────────┘   └────────┘   └────────┘   └────────┘           │
│                                                              │               │
│                         ┌────────────────────────────────────┘               │
│                         │                                                    │
│                         ▼                                                    │
│                    ┌────────┐   ┌────────┐   ┌────────┐                     │
│                    │REFINE  │──▶│  HITL  │──▶│FINALIZE│                     │
│                    │        │   │ REVIEW │   │        │                     │
│                    └────────┘   └────────┘   └────────┘                     │
│                         ▲           │                                        │
│                         └───────────┘ (if changes requested)                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Stage Specifications

### Stage 1: Ingestion

**Purpose**: Load and validate input text

| Property | Value |
|----------|-------|
| Input | Raw text file, URL, or direct text |
| Output | `IngestedText` with metadata |
| Agent | None (utility function) |
| Duration | < 1 second |

```python
class IngestedText(BaseModel):
    content: str
    source_type: SourceType
    source_metadata: SourceMetadata
    word_count: int
    language: str
    encoding: str
```

**Validations**:
- Non-empty content
- Supported encoding
- Within size limits
- Language detection

---

### Stage 2: Parsing

**Purpose**: Segment text into structured units

| Property | Value |
|----------|-------|
| Input | `IngestedText` |
| Output | `list[TextSegment]` |
| Agent | Story Parser Agent |
| Duration | 5-30 seconds |

**Operations**:
1. Identify scene boundaries
2. Extract characters, locations, events
3. Detect dialogue vs narration
4. Tag emotional beats
5. Assign sequence numbers

---

### Stage 3: Scene Graph Construction

**Purpose**: Build graph representation of narrative

| Property | Value |
|----------|-------|
| Input | `list[TextSegment]` |
| Output | `SceneGraph` |
| Agent | Story Parser Agent (continued) |
| Duration | 10-60 seconds |

**Operations**:
1. Create Story node
2. Create Scene nodes with relationships
3. Create Character/Location/Event nodes
4. Establish relationships (APPEARS_IN, OCCURS_IN, etc.)
5. Compute derived metrics

---

### Stage 4: Continuity Validation

**Purpose**: Ensure narrative consistency

| Property | Value |
|----------|-------|
| Input | `SceneGraph` |
| Output | `ValidatedSceneGraph` |
| Agent | Continuity & Canon Agent |
| Duration | 5-20 seconds |

**Validations**:
- Character introduction order
- Location establishment
- Timeline consistency
- Prop persistence
- Canon compliance

**Output includes**:
- Continuity scores per scene
- Violations (if any)
- Suggested fixes

---

### Stage 5: KRAG Retrieval

**Purpose**: Retrieve relevant knowledge for planning

| Property | Value |
|----------|-------|
| Input | `ValidatedSceneGraph` |
| Output | `KRAGContext` per scene |
| Agent | KRAG Retrieval Agent |
| Duration | 2-10 seconds per scene |

**Retrieves**:
- Similar scene patterns
- Shot sequence templates
- Narration style examples
- Pacing references
- Visual style guides

---

### Stage 6: Shot Planning

**Purpose**: Create cinematic shot plan with duration budgeting and hook strategy.

| Property | Value |
|----------|-------|
| Input | `Scene` + `DirectorConfig` |
| Output | `ShotPlan` + `list[Shot]` |
| Agent | **DirectorAgent v1** |
| Duration | 10-30 seconds per scene |

**Features**:
- **Variable shot counts**: 3-10 shots based on scene complexity and pacing
- **Duration budgeting**: Allocates time across shots, reserving 3s for hook
- **Hook planning**: Explicit first-3-seconds strategy (visual_impact, mystery, action, emotional)
- **Playbook constraints**: Applies learned constraints from feedback

**Creates**:
- Ordered shot sequence with Ken Burns motion specs
- Shot specifications (type, duration, motion, composition)
- Transition plan with pacing-appropriate transitions
- Audio cues (music start, swell, fade)
- Narration allocation

**Configuration** (DirectorConfig):
```python
target_duration_seconds: float = 60.0
min_shot_duration: float = 2.0
max_shot_duration: float = 8.0
hook_duration: float = 3.0
min_shots_per_scene: int = 3
max_shots_per_scene: int = 10
default_pacing: PacingStyle = MODERATE
default_hook_strategy: HookStrategy = VISUAL_IMPACT
```

---

### Stage 7: Prompt Engineering

**Purpose**: Generate prompts for asset generation

| Property | Value |
|----------|-------|
| Input | `ShotPlan` |
| Output | `GenerationPrompts` |
| Agent | Prompt Engineering Agent |
| Duration | 5-15 seconds per scene |

**Generates**:
- Image prompts (positive + negative)
- Voiceover prompts
- Music selection criteria
- Consistency tokens

---

### Stage 8: Asset Generation

**Purpose**: Generate images, audio, and other assets with manifest tracking.

| Property | Value |
|----------|-------|
| Input | `ShotPlan` + `list[Shot]` |
| Output | `AssetManifest` + `list[Asset]` |
| Agent | Asset Generation Agent (or PlaceholderGenerator for testing) |
| Duration | 30-120 seconds per scene |

**Asset Manifest**:
Tracks all required assets and their generation status:
```python
class AssetManifest(BaseModel):
    story_id: str
    status: ManifestStatus  # pending, in_progress, completed, partial, failed
    requirements: list[AssetRequirement]
    assets: list[Asset]
    total_generation_cost: float
```

**Generates**:
- Images (1 per shot, 1920x1080)
- Voiceover audio (if narration text present)
- Music track selection
- Sound effects

**Placeholder Generator** (for MVP testing):
- Creates styled placeholder images with mood-based colors
- Includes shot type badges and composition guides
- No API costs, instant generation

**Cost control**:
- Budget tracking per manifest
- Priority ordering of requirements
- Fallback models
- Caching of reusable assets

---

### Stage 9: Assembly

**Purpose**: Combine assets into video timeline using Ken Burns renderer.

| Property | Value |
|----------|-------|
| Input | `list[Shot]` + `AssetManifest` |
| Output | `RenderResult` (draft MP4) |
| Agent | VideoRenderer |
| Duration | 30-90 seconds per scene |

**VideoRenderer** (FFmpeg-based):
```python
class RenderConfig(BaseModel):
    output_width: int = 1920
    output_height: int = 1080
    fps: int = 30
    video_codec: str = "libx264"
    crf: int = 23  # Quality (lower = better)
```

**Ken Burns Effect**:
Converts camera motion to zoom/pan animation:
| Camera Motion | Ken Burns Direction |
|--------------|---------------------|
| ZOOM_IN | Scale 1.0 → 1.3 |
| ZOOM_OUT | Scale 1.3 → 1.0 |
| PAN_LEFT | X offset +0.1 → -0.1 |
| PAN_RIGHT | X offset -0.1 → +0.1 |
| STATIC | No movement |

**Operations**:
1. Render each shot as Ken Burns video clip
2. Concatenate clips with transitions
3. Apply audio (future)
4. Output draft MP4

---

### Stage 10: Critique

**Purpose**: Evaluate draft quality

| Property | Value |
|----------|-------|
| Input | `DraftVideo` |
| Output | `CritiqueResult` |
| Agent | Critic Agent |
| Duration | 10-30 seconds |

**Evaluates**:
- Narrative clarity
- Hook strength
- Pacing
- Shot composition
- Continuity
- Audio mix

**Outputs**:
- Dimension scores (1-5)
- Overall score (1-10)
- Issues with fix taxonomy
- Recommendation

---

### Stage 11: Refinement

**Purpose**: Iterate to improve quality via Critic → Fix → Critic loop.

| Property | Value |
|----------|-------|
| Input | `SceneGraph` + `RefinementConfig` |
| Output | `RefinementResult` + refined `SceneGraph` |
| Agent | **IterativeRefinementController** |
| Duration | Variable (1-5 iterations typical) |

**Configuration** (RefinementConfig):
```python
class RefinementConfig(BaseModel):
    max_iterations: int = 5
    min_iterations: int = 1
    max_cost_dollars: float = 10.0
    cost_per_critique: float = 0.05
    cost_per_fix: float = 0.50
    target_overall_score: float = 7.5
    improvement_threshold: float = 0.5
```

**Loop**:
1. Run Critic Agent → get dimension scores and issues
2. Prioritize issues by severity × dimension weight
3. Apply fix function to SceneGraph
4. Re-run Critic to measure improvement
5. Check stopping conditions
6. Record iteration history

**Dimension Weights** (for prioritization):
```python
dimension_weights = {
    "hook_strength": 1.5,      # Hook is critical
    "narrative_clarity": 1.2,
    "pacing": 1.0,
    "shot_composition": 1.0,
    "continuity": 0.8,
    "audio_mix": 0.7,
}
```

**Exit conditions** (RefinementStatus):
- `CONVERGED`: Score >= target OR critic approved OR no improvement
- `MAX_ITERATIONS`: Iteration cap reached
- `BUDGET_EXCEEDED`: Cost cap reached
- `FAILED`: Unrecoverable error

---

### Stage 12: Human Review

**Purpose**: Human expert approval

| Property | Value |
|----------|-------|
| Input | `RefinedVideo` |
| Output | `ApprovedVideo` or `ChangeRequests` |
| Agent | HITL Gatekeeper |
| Duration | Human-dependent |

**Interface**:
- Video player with timestamp marking
- AI critique summary
- Structured feedback form
- Approve/Revise/Reject buttons

---

### Stage 13: Finalization

**Purpose**: Prepare final deliverable

| Property | Value |
|----------|-------|
| Input | `ApprovedVideo` |
| Output | `FinalVideo` |
| Agent | None (utility function) |
| Duration | 30-60 seconds |

**Operations**:
1. Final render at target quality
2. Generate thumbnails
3. Create metadata file
4. Upload to storage
5. Update knowledge graph
6. Store feedback for learning

---

## Pipeline Orchestration

### Pipeline Controller

```python
class PipelineController:
    """Orchestrates pipeline execution."""

    async def run(
        self,
        input: PipelineInput,
        config: PipelineConfig
    ) -> PipelineResult:
        """Execute full pipeline."""
        run = await self.create_run(input, config)

        try:
            # Execute stages in order
            for stage in self.stages:
                run = await self.execute_stage(run, stage)

                if run.status == PipelineStatus.FAILED:
                    break

                if stage.requires_human_review:
                    run = await self.await_human_review(run)

            return self.finalize(run)

        except Exception as e:
            return self.handle_failure(run, e)
```

### Stage Execution

```python
async def execute_stage(
    self,
    run: PipelineRun,
    stage: PipelineStage
) -> PipelineRun:
    """Execute a single pipeline stage."""
    self.logger.info(f"Starting stage: {stage.name}")

    # Get input from previous stage
    stage_input = self.get_stage_input(run, stage)

    # Execute with retry
    for attempt in range(stage.max_retries):
        try:
            output = await stage.agent.execute(stage_input)
            break
        except TransientError as e:
            if attempt == stage.max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)

    # Store output
    run.stage_outputs[stage.name] = output
    run.current_stage = stage.name
    run.updated_at = datetime.utcnow()

    await self.persist_run(run)
    return run
```

### Error Recovery

| Error Type | Recovery Strategy |
|------------|-------------------|
| Transient (API timeout) | Exponential backoff, 3 retries |
| Rate limit | Queue with delay |
| Generation failure | Fallback model, then human override |
| Validation failure | Return to previous stage |
| Cost exceeded | Pause, notify, await decision |

---

## Parallel Processing

### Scene-Level Parallelism

Stages 5-9 can run in parallel across scenes:

```
Scene 1: [KRAG] → [PLAN] → [PROMPT] → [GENERATE] → [ASSEMBLE]
Scene 2: [KRAG] → [PLAN] → [PROMPT] → [GENERATE] → [ASSEMBLE]
Scene 3: [KRAG] → [PLAN] → [PROMPT] → [GENERATE] → [ASSEMBLE]
                                                          ↓
                                                    [MERGE SCENES]
                                                          ↓
                                                    [CRITIQUE]
```

### Asset-Level Parallelism

Within a scene, asset generation is parallel:

```
Shot 1: [IMAGE] ─────┐
Shot 2: [IMAGE] ─────┼──→ [ASSEMBLE]
Shot 3: [IMAGE] ─────┤
[VOICEOVER] ─────────┤
[MUSIC] ─────────────┘
```

---

## Cost Controls

### Budget Allocation

```python
class CostBudget(BaseModel):
    total: float
    llm: float  # 20%
    image_generation: float  # 50%
    voice_synthesis: float  # 15%
    music: float  # 10%
    compute: float  # 5%

    @classmethod
    def from_total(cls, total: float) -> "CostBudget":
        return cls(
            total=total,
            llm=total * 0.20,
            image_generation=total * 0.50,
            voice_synthesis=total * 0.15,
            music=total * 0.10,
            compute=total * 0.05,
        )
```

### Cost Tracking

Every stage reports costs:

```python
class StageCost(BaseModel):
    stage: str
    llm_tokens: int
    llm_cost: float
    generation_calls: int
    generation_cost: float
    storage_bytes: int
    storage_cost: float
    total: float
```

### Cost Enforcement

```python
async def check_budget(self, run: PipelineRun) -> None:
    if run.costs.total_cost >= run.config.cost_budget.total:
        run.status = PipelineStatus.PAUSED
        await self.notify_cost_exceeded(run)
        raise CostExceededException(run.costs)
```

---

## State Persistence

All pipeline state is persisted to PostgreSQL:

```sql
CREATE TABLE pipeline_runs (
    id VARCHAR PRIMARY KEY,
    story_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    current_stage VARCHAR NOT NULL,
    stage_outputs JSONB,
    costs JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_runs_story ON pipeline_runs(story_id);
CREATE INDEX idx_runs_status ON pipeline_runs(status);
```

This enables:
- Resume after failure
- Audit trails
- Cost analysis
- Performance monitoring

---

*See [architecture.md](architecture.md) for system overview.*
*See [agents.md](agents.md) for agent specifications.*
