# System Architecture

## Design Principles

1. **Deterministic Pipeline**: Every stage produces versioned, inspectable artifacts
2. **Explicit Contracts**: All agents have typed input/output schemas
3. **Separation of Concerns**: Knowledge, planning, generation, and critique are independent
4. **Graph as Ground Truth**: Knowledge graph is the authoritative source for continuity
5. **Fail-Safe Iteration**: Cost caps and max iterations prevent runaway loops

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   API LAYER                                      │
│                        REST/GraphQL + WebSocket for HITL                        │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            ORCHESTRATION LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        Pipeline Controller                               │   │
│  │  • Stage sequencing          • State management                         │   │
│  │  • Error handling            • Cost tracking                            │   │
│  │  • Retry logic               • Audit logging                            │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      Iterative Refinement Controller                     │   │
│  │  • Critique → Fix cycles     • Convergence detection                    │   │
│  │  • Max iteration enforcement • Cost cap enforcement                     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               AGENT LAYER                                        │
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │Story Parser  │  │ Continuity   │  │    KRAG      │  │  Creative    │        │
│  │   Agent      │  │    Agent     │  │   Retrieval  │  │  Director    │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Prompt     │  │    Asset     │  │    Editor    │  │    Critic    │        │
│  │  Engineer    │  │  Generation  │  │    Agent     │  │    Agent     │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                                  │
│  ┌──────────────┐                                                               │
│  │    HITL      │                                                               │
│  │  Gatekeeper  │                                                               │
│  └──────────────┘                                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              KNOWLEDGE LAYER                                     │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         Vector Store (KRAG)                              │   │
│  │  ┌───────────────────────┐      ┌───────────────────────────────────┐   │   │
│  │  │  Text Knowledge Plane │      │     Video Knowledge Plane         │   │   │
│  │  │  • Scene summaries    │      │     • Shot patterns               │   │   │
│  │  │  • Narrative patterns │      │     • Pacing metrics              │   │   │
│  │  │  • Dialogue styles    │      │     • Transition types            │   │   │
│  │  │  • Emotional beats    │      │     • Audio/visual alignment      │   │   │
│  │  └───────────────────────┘      └───────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         Knowledge Graph (Neo4j)                          │   │
│  │  • Story → Scene → Shot hierarchy                                       │   │
│  │  • Character/Location continuity                                        │   │
│  │  • Event causality chains                                               │   │
│  │  • Feedback annotations                                                 │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           GENERATION LAYER                                       │
│                                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐              │
│  │ Image Generation │  │  Voice Synthesis │  │  Music Selection │              │
│  │  (SDXL, DALL-E)  │  │  (ElevenLabs)    │  │   (Licensed DB)  │              │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘              │
│                                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                                    │
│  │ Motion Effects   │  │  Video Assembly  │                                    │
│  │ (Ken Burns, etc) │  │    (FFmpeg)      │                                    │
│  └──────────────────┘  └──────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            STORAGE LAYER                                         │
│                                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐              │
│  │   Object Store   │  │   PostgreSQL     │  │   Redis Cache    │              │
│  │   (S3/MinIO)     │  │ (Job State, Logs)│  │  (Hot artifacts) │              │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Pipeline Stages

### Stage 1: Text Ingestion & Parsing

**Input**: Raw text (book, script, narrative)
**Output**: Parsed segments with metadata

```python
@dataclass
class TextSegment:
    id: str
    content: str
    segment_type: SegmentType  # CHAPTER, SECTION, PARAGRAPH
    metadata: dict
```

### Stage 2: Scene Graph Generation

**Input**: Parsed segments
**Output**: Scene graph with nodes and edges

The Story Parser Agent analyzes text to extract:
- Scene boundaries (location/time changes)
- Characters present
- Key events/actions
- Emotional beats
- Props and artifacts

### Stage 3: Continuity Validation

**Input**: Scene graph
**Output**: Validated scene graph with continuity annotations

The Continuity Agent ensures:
- Characters don't appear before introduction
- Locations are consistent
- Timeline is coherent
- Props persist appropriately

### Stage 4: Shot Planning

**Input**: Validated scene graph
**Output**: Shot plan with detailed specifications

The Creative Director Agent creates:
- Shot sequence for each scene
- Shot types (wide, medium, close-up)
- Camera movements
- Duration estimates
- Transition types

### Stage 5: Asset Generation

**Input**: Shot plan
**Output**: Generated assets (images, audio)

The Asset Generation Agent orchestrates:
- Image generation with style consistency
- Voiceover synthesis
- Music selection/generation
- Sound effect placement

### Stage 6: Timeline Assembly

**Input**: Assets + shot plan
**Output**: Draft video

The Editor Agent:
- Sequences assets according to shot plan
- Applies motion effects
- Synchronizes audio
- Adds transitions

### Stage 7: Critique & Refinement

**Input**: Draft video
**Output**: Feedback + refined video

Iterative loop:
1. Critic Agent evaluates draft
2. If below threshold, identify fixes
3. Apply fixes (re-generate specific assets/shots)
4. Re-evaluate
5. Repeat until pass or max iterations

### Stage 8: Human Review

**Input**: AI-approved video
**Output**: Final approved video

HITL Gatekeeper:
- Presents video for human review
- Collects structured feedback
- Either approves or triggers refinement

## Data Flow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  Text   │────▶│  Scene  │────▶│  Shot   │────▶│ Assets  │
│  Input  │     │  Graph  │     │  Plan   │     │         │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                     │               │               │
                     ▼               ▼               ▼
              ┌──────────────────────────────────────────┐
              │           Knowledge Graph                 │
              │    (Persistence + Continuity)            │
              └──────────────────────────────────────────┘
                                   │
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
              ┌───────────┐               ┌───────────┐
              │  Vector   │               │ Feedback  │
              │   Store   │◀─────────────▶│   Store   │
              └───────────┘               └───────────┘
```

## State Management

Each pipeline run maintains:

```python
@dataclass
class PipelineState:
    run_id: str
    status: PipelineStatus
    current_stage: str
    stage_outputs: dict[str, Any]
    costs_incurred: CostBreakdown
    iteration_count: int
    started_at: datetime
    updated_at: datetime
```

States are persisted to PostgreSQL for:
- Resume after failure
- Audit trails
- Cost analysis
- Performance monitoring

## Error Handling

| Error Type | Handling |
|------------|----------|
| Transient (API timeout) | Exponential backoff retry (3x) |
| Rate limit | Queue with delay |
| Generation failure | Fallback model, then human override |
| Validation failure | Return to previous stage |
| Cost limit exceeded | Pause, notify, await decision |

## Scaling Considerations

### Horizontal Scaling
- Stateless agents (can run N instances)
- Queue-based job distribution
- Sharded vector stores

### Vertical Scaling
- GPU instances for generation
- Large memory for graph operations

### Caching
- Generated assets by content hash
- Embedding cache
- Shot plan templates

## Security

- All secrets in environment/vault
- API authentication (JWT)
- Rate limiting
- Input sanitization
- Output content moderation
- Audit logging

---

*See [data-models.md](data-models.md) for detailed schema definitions.*
*See [agents.md](agents.md) for agent contracts.*
