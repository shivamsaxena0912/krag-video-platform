# Evaluation & Quality Metrics

## Overview

Quality in the KRAG video platform is measured at multiple levels: pipeline stage outputs, final video quality, and system performance. This document defines the metrics, measurement methods, and targets.

## Quality Dimensions

### 1. Narrative Clarity (1-5)

**Definition**: How clearly the video conveys the story.

**Measurement**:
- AI evaluation: LLM rates transcript vs original text alignment
- Human evaluation: "Could you follow the story?" (1-5 scale)

**Sub-dimensions**:
- Story coherence: Events flow logically
- Character clarity: Characters are distinguishable
- Event sequencing: Timeline is understandable
- Information density: Not too fast or slow

**Target**: ≥3.5 average

### 2. Hook Strength (1-5)

**Definition**: How effectively the opening captures attention.

**Measurement**:
- First 3 seconds engagement potential
- Opening shot impact
- Narrative hook presence

**Criteria**:
| Score | Description |
|-------|-------------|
| 5 | Immediately compelling, must watch more |
| 4 | Strong opening, draws interest |
| 3 | Adequate opening, neutral |
| 2 | Weak opening, easy to skip |
| 1 | Boring or confusing opening |

**Target**: ≥3.5 average

### 3. Pacing (1-5)

**Definition**: Rhythm and flow of the video.

**Measurement**:
- Shot duration distribution
- Transition frequency
- Narrative beat timing
- Viewer attention modeling

**Metrics**:
- Average shot duration
- Shot duration variance
- Transition type distribution
- Beat timing accuracy

**Target**: ≥3.5 average

### 4. Shot Composition (1-5)

**Definition**: Visual quality and cinematography.

**Measurement**:
- Framing correctness
- Subject focus
- Visual balance
- Style consistency

**Automated checks**:
- Face/subject detection
- Rule of thirds alignment
- Color consistency
- Resolution and clarity

**Target**: ≥3.5 average

### 5. Continuity (1-5)

**Definition**: Visual and narrative consistency.

**Measurement**:
- Character appearance consistency
- Location consistency
- Prop persistence
- Timeline coherence

**Automated checks**:
- Image similarity scores for characters
- Location visual matching
- Graph-based continuity validation

**Target**: ≥4.0 average (critical dimension)

### 6. Audio Mix (1-5)

**Definition**: Quality of voice, music, and sound.

**Measurement**:
- Voice clarity and audibility
- Music appropriateness
- Volume balance
- Audio-visual sync

**Automated checks**:
- Voice-to-music ratio
- Silence detection
- Sync offset measurement

**Target**: ≥3.5 average

---

## Stage-Level Metrics

### Scene Graph Accuracy

**Definition**: How accurately the scene graph represents the source text.

**Measurement**:
- Entity extraction recall
- Scene boundary accuracy
- Relationship correctness

**Metrics**:
| Metric | Formula | Target |
|--------|---------|--------|
| Entity recall | Found entities / True entities | ≥0.85 |
| Boundary F1 | 2 * (P * R) / (P + R) | ≥0.80 |
| Relationship precision | Correct relations / Extracted relations | ≥0.75 |

### Shot Plan Quality

**Definition**: How well the shot plan translates the scene.

**Measurement**:
- Coverage of key moments
- Cinematic grammar adherence
- Pacing appropriateness

**Metrics**:
| Metric | Description | Target |
|--------|-------------|--------|
| Key moment coverage | % of important events with dedicated shots | ≥0.90 |
| Grammar score | Adherence to cinematographic rules | ≥0.75 |
| Pacing variance | Deviation from reference pacing | ≤0.20 |

### Asset Quality

**Definition**: Quality of generated images and audio.

**Measurement**:
- Image quality scores (CLIP, FID)
- Voice naturalness (MOS)
- Style consistency

**Metrics**:
| Metric | Tool | Target |
|--------|------|--------|
| CLIP alignment | CLIP score | ≥0.30 |
| Image quality | BRISQUE | ≤30 |
| Voice MOS | Automated or human | ≥3.5 |
| Style consistency | Embedding similarity | ≥0.85 |

### Refinement Effectiveness

**Definition**: How much quality improves per iteration.

**Measurement**:
- Score delta per iteration
- Issue resolution rate
- Cost efficiency

**Metrics**:
| Metric | Formula | Target |
|--------|---------|--------|
| Score improvement | (Final - Initial) / Iterations | ≥0.5 per iteration |
| Issue resolution | Fixed issues / Total issues | ≥0.70 |
| Cost per point | $ spent / Score improvement | ≤$1 per 0.1 point |

---

## System Performance Metrics

### Pipeline Performance

| Metric | Description | Target |
|--------|-------------|--------|
| End-to-end latency | Time from input to draft | <30 min per scene |
| Stage latency | Time per pipeline stage | Varies by stage |
| Throughput | Scenes processed per hour | ≥4 |
| Error rate | Failed runs / Total runs | <5% |

### Cost Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Cost per minute | Total cost / Video minutes | <$5 |
| LLM cost ratio | LLM cost / Total cost | <30% |
| Regeneration rate | Re-generated assets / Total assets | <20% |
| Refinement cost | Refinement cost / Total cost | <25% |

### Reliability Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Pipeline success rate | Completed / Started | ≥95% |
| Asset generation success | Successful / Attempted | ≥98% |
| API availability | Uptime % | ≥99.5% |
| Mean time to recovery | Average recovery time | <5 min |

---

## Evaluation Framework

### Automated Evaluation Pipeline

```python
class AutomatedEvaluator:
    """Runs automated quality checks on pipeline outputs."""

    async def evaluate_scene_graph(
        self,
        scene_graph: SceneGraph,
        source_text: str
    ) -> SceneGraphEvaluation:
        """Evaluate scene graph accuracy."""
        pass

    async def evaluate_shot_plan(
        self,
        shot_plan: ShotPlan,
        scene: Scene
    ) -> ShotPlanEvaluation:
        """Evaluate shot plan quality."""
        pass

    async def evaluate_assets(
        self,
        assets: list[Asset],
        shot_plan: ShotPlan
    ) -> AssetEvaluation:
        """Evaluate generated assets."""
        pass

    async def evaluate_video(
        self,
        video_path: str,
        shot_plan: ShotPlan,
        scene: Scene
    ) -> VideoEvaluation:
        """Evaluate assembled video."""
        pass
```

### Expert Feedback CLI

**Implementation**: `scripts/submit_feedback.py`

The CLI provides three modes for expert feedback submission:

**1. Template Generation**:
```bash
python scripts/submit_feedback.py template --story-id story_abc123 --output feedback.json
```

Generates a JSON template with all feedback fields:
```json
{
  "target_type": "story",
  "target_id": "story_abc123",
  "dimension_scores": {
    "narrative_clarity": 4,
    "hook_strength": 3,
    "pacing": 4,
    "shot_composition": 4,
    "continuity": 5,
    "audio_mix": 4
  },
  "overall_score": 7.0,
  "recommendation": "revise_minor",
  "issues": [...],
  "strengths": [...],
  "fix_requests": [...],
  "playbook_constraints": [
    "prefer_static_shots_for_dialogue",
    "min_duration:3.0"
  ]
}
```

**2. File Submission**:
```bash
python scripts/submit_feedback.py submit --file feedback.json
```

Parses JSON, validates structure, stores in Neo4j with full feedback schema.

**3. Interactive Mode**:
```bash
python scripts/submit_feedback.py interactive --story-id story_abc123
```

Prompts for dimension scores, issues, strengths, and recommendation interactively.

### Human Evaluation Protocol

**Reviewer Types**:
- Internal team (quick iteration)
- Domain experts (directors, editors)
- Target audience (content consumers)

**Evaluation Interface**:
```
┌─────────────────────────────────────────────────────────────────┐
│                     VIDEO REVIEW INTERFACE                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                                                          │   │
│  │                    [Video Player]                        │   │
│  │                                                          │   │
│  │  ◀ ▶ ■  ──────────●──────────────  2:34 / 5:00          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  DIMENSION SCORES                                               │
│  ─────────────────                                              │
│  Narrative Clarity  [1] [2] [3] [4] [5]                        │
│  Hook Strength      [1] [2] [3] [4] [5]                        │
│  Pacing             [1] [2] [3] [4] [5]                        │
│  Shot Composition   [1] [2] [3] [4] [5]                        │
│  Continuity         [1] [2] [3] [4] [5]                        │
│  Audio Mix          [1] [2] [3] [4] [5]                        │
│                                                                  │
│  Overall Score      [1] [2] [3] [4] [5] [6] [7] [8] [9] [10]   │
│                                                                  │
│  TIMESTAMPED NOTES                                              │
│  ─────────────────                                              │
│  [+ Add note at current timestamp]                              │
│  • 0:15 - Opening shot too long                                 │
│  • 1:23 - Character appearance inconsistent                    │
│                                                                  │
│  ┌─────────┐  ┌──────────────┐  ┌─────────┐                   │
│  │ APPROVE │  │ REQUEST EDITS │  │ REJECT  │                   │
│  └─────────┘  └──────────────┘  └─────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### Benchmark Dataset

**Composition**:
- 10 short narratives (1-2 pages)
- 5 medium narratives (5-10 pages)
- 3 long narratives (20+ pages)

**Diversity**:
- Historical fiction
- Documentary style
- Action sequences
- Dialogue-heavy scenes
- Contemplative passages

**Ground Truth**:
- Human-created scene graphs
- Expert shot plans
- Reference quality scores

---

## Continuous Improvement

### Learning from Feedback

1. **Immediate**: Update knowledge graph annotations
2. **Short-term**: Adjust retrieval rankings
3. **Medium-term**: Update prompt templates and rules
4. **Long-term**: Fine-tune models (future)

### A/B Testing Framework

```python
class ExperimentConfig(BaseModel):
    """Configuration for A/B experiment."""
    experiment_id: str
    variants: list[Variant]
    traffic_split: dict[str, float]
    metrics: list[str]
    duration_days: int


class Variant(BaseModel):
    """A variant in an A/B test."""
    name: str
    changes: dict[str, Any]  # Config overrides
```

### Quality Dashboards

**Real-time Dashboard**:
- Pipeline status
- Current quality scores
- Error rates
- Cost tracking

**Historical Dashboard**:
- Quality trends over time
- Improvement velocity
- Cost efficiency trends
- Benchmark comparisons

---

## Failure Analysis

### Common Failure Modes

| Mode | Detection | Resolution |
|------|-----------|------------|
| Character inconsistency | Embedding similarity | Regenerate with reference |
| Pacing issues | Duration analysis | Adjust shot durations |
| Audio desync | Offset detection | Re-sync audio |
| Narrative gaps | Coverage analysis | Add bridge shots |
| Style drift | Style embedding | Apply style correction |

### Post-mortem Process

1. Identify failed pipeline runs
2. Categorize failure mode
3. Trace to root cause
4. Implement fix
5. Add to test suite
6. Update documentation

---

*See [agents.md](agents.md) for Critic Agent details.*
*See [data-models.md](data-models.md) for feedback schemas.*
