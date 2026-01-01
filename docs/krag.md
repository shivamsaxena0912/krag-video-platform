# KRAG Strategy

## Overview

KRAG (Knowledge Retrieval-Augmented Generation) is our dual-plane knowledge system that provides both narrative intelligence (from text) and cinematic intelligence (from video analysis) to inform the video creation pipeline.

**Key Insight**: Vectors enable creative recall (finding similar patterns), while the Knowledge Graph enforces continuity and constraints. Both are required.

## Dual-Plane Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          KRAG KNOWLEDGE SYSTEM                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    TEXT KNOWLEDGE PLANE                              │   │
│  │                  (Narrative Intelligence)                            │   │
│  │                                                                      │   │
│  │  Sources:                      Embeddings:                           │   │
│  │  • Public-domain books         • Scene summaries                     │   │
│  │  • Historical narratives       • Narration/dialogue blocks           │   │
│  │  • Scripts & screenplays       • Emotional beat patterns             │   │
│  │  • Narrative templates         • Story arc structures                │   │
│  │                                • Hook patterns                       │   │
│  │                                • Pacing rhythms                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    VIDEO KNOWLEDGE PLANE                             │   │
│  │                   (Cinematic Intelligence)                           │   │
│  │                                                                      │   │
│  │  Sources:                      Embeddings:                           │   │
│  │  • Analyzed video content      • Shot type sequences                 │   │
│  │  • Documentary examples        • Duration/pacing metrics             │   │
│  │  • Branded content samples     • Transition patterns                 │   │
│  │  • Music video structures      • Audio-visual sync patterns          │   │
│  │                                • Color/mood progressions             │   │
│  │                                • Subtitle cadence                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      KNOWLEDGE GRAPH                                 │   │
│  │                   (Continuity & Constraints)                         │   │
│  │                                                                      │   │
│  │  Entities:                     Relationships:                        │   │
│  │  • Story                       • Scene → NEXT_SCENE → Scene          │   │
│  │  • Scene                       • Scene → HAS_SHOT → Shot             │   │
│  │  • Shot                        • Character → APPEARS_IN → Scene      │   │
│  │  • Character                   • Event → OCCURS_IN → Scene           │   │
│  │  • Location                    • Shot → FOCUSES_ON → Character       │   │
│  │  • Event                       • Scene → REUSES_PATTERN → KB_Scene   │   │
│  │  • Object/Prop                 • Asset → USED_IN → Shot              │   │
│  │  • Emotion/Beat                • Feedback → TARGETS → (Scene|Shot)   │   │
│  │  • Style                                                             │   │
│  │  • Asset                                                             │   │
│  │  • Voiceover                                                         │   │
│  │  • Dialogue                                                          │   │
│  │  • FeedbackAnnotation                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Text Knowledge Plane

### Purpose

Learn and retrieve patterns for:
- Story arc construction
- Hook creation and placement
- Pacing and rhythm
- Narration styles and tones
- Dialogue patterns
- Persuasion frameworks
- Emotional beat sequences

### Ingestion Pipeline

```
Raw Text → Chunking → Parsing → Embedding → Vector Store
              │           │
              │           ▼
              │     Metadata Extraction
              │     • Source info
              │     • Genre/style tags
              │     • Quality scores
              │     • Usage rights
              │
              ▼
        Scene Segmentation
        • Location detection
        • Time markers
        • Character mentions
        • Event boundaries
```

### Embedding Strategy

| Content Type | Chunking | Model | Dimensions |
|--------------|----------|-------|------------|
| Scene summary | Full scene | text-embedding-3-large | 3072 |
| Dialogue block | Speaker turn | text-embedding-3-large | 3072 |
| Narration | Paragraph | text-embedding-3-large | 3072 |
| Emotional beat | Beat unit | text-embedding-3-large | 3072 |
| Story arc | Chapter-level | text-embedding-3-large | 3072 |

### Retrieval Use Cases

1. **Scene Planning**: "Find similar scenes from knowledge base"
   - Query: Current scene summary
   - Return: Top-k similar scenes with shot plans

2. **Narration Style**: "Find narration style for this mood"
   - Query: Mood/tone description
   - Return: Example narration passages

3. **Hook Generation**: "Find effective hooks for this topic"
   - Query: Topic + target emotion
   - Return: Proven hook patterns

4. **Pacing Reference**: "Find pacing pattern for this scene type"
   - Query: Scene type (action, dialogue, contemplative)
   - Return: Beat timing patterns

## Video Knowledge Plane

### Purpose

Learn and retrieve patterns for:
- Shot grammar (shot types, compositions)
- Editing language (transitions, cuts)
- Pacing norms (shot durations, rhythm)
- Audio-visual alignment
- Color and mood progressions
- Subtitle/caption timing

### Ingestion Pipeline

```
Video File → Frame Extraction → Scene Detection → Analysis → Embedding
                  │                   │               │
                  │                   │               ▼
                  │                   │        Shot Classification
                  │                   │        • Type (wide/med/close)
                  │                   │        • Duration
                  │                   │        • Motion
                  │                   │
                  │                   ▼
                  │            Audio Analysis
                  │            • Speech segments
                  │            • Music detection
                  │            • Mood classification
                  │
                  ▼
            Visual Analysis
            • Color palette
            • Composition
            • Subject detection
```

### Embedding Strategy

| Content Type | Representation | Model | Dimensions |
|--------------|----------------|-------|------------|
| Shot sequence | Shot type + duration list | Custom encoder | 512 |
| Scene visual | Keyframe composite | CLIP | 768 |
| Audio segment | Mel spectrogram | Custom encoder | 256 |
| Pacing pattern | Duration histogram | Custom encoder | 128 |
| Transition | Type + context | One-hot + embedding | 64 |

### Retrieval Use Cases

1. **Shot Planning**: "Find shot sequence for this scene type"
   - Query: Scene description + mood
   - Return: Example shot sequences with timings

2. **Pacing**: "Find pacing for documentary about war"
   - Query: Genre + topic
   - Return: Duration distributions, transition frequencies

3. **Music Selection**: "Find music mood for contemplative scene"
   - Query: Scene mood + tempo preference
   - Return: Music segment examples

4. **Visual Style**: "Find visual treatment for historical content"
   - Query: Era + content type
   - Return: Color palettes, compositions, filters

## Knowledge Graph

### Schema

```cypher
// Core Entities
(s:Story {
  id: string,
  title: string,
  source_type: string,  // BOOK, SCRIPT, NARRATIVE
  created_at: datetime,
  status: string
})

(sc:Scene {
  id: string,
  sequence: int,
  setting_description: string,
  time_of_day: string,
  era: string,
  mood: string,
  duration_estimate_seconds: int
})

(sh:Shot {
  id: string,
  sequence: int,
  shot_type: string,  // WIDE, MEDIUM, CLOSE_UP, EXTREME_CLOSE_UP
  duration_seconds: float,
  motion_type: string,  // STATIC, PAN, ZOOM, DOLLY
  focus_subject: string,
  prompt_text: string
})

(c:Character {
  id: string,
  name: string,
  description: string,
  visual_prompt: string,
  voice_profile: string
})

(l:Location {
  id: string,
  name: string,
  description: string,
  visual_prompt: string,
  era: string
})

(e:Event {
  id: string,
  name: string,
  description: string,
  event_type: string  // ACTION, DIALOGUE, REVELATION, TRANSITION
})

(a:Asset {
  id: string,
  asset_type: string,  // IMAGE, AUDIO, VOICEOVER, MUSIC
  file_path: string,
  generation_params: map,
  quality_score: float
})

(f:FeedbackAnnotation {
  id: string,
  source: string,  // AI_CRITIC, HUMAN_EXPERT
  scores: map,
  notes: list,
  fix_taxonomy: list,
  created_at: datetime
})

// Relationships
(s)-[:HAS_SCENE]->(sc)
(sc)-[:NEXT_SCENE]->(sc)
(sc)-[:HAS_SHOT]->(sh)
(c)-[:APPEARS_IN]->(sc)
(e)-[:OCCURS_IN]->(sc)
(sh)-[:FOCUSES_ON]->(c)
(sh)-[:SHOWS_LOCATION]->(l)
(a)-[:USED_IN]->(sh)
(sc)-[:REUSES_PATTERN_FROM]->(kb_sc:KnowledgeBaseScene)
(f)-[:TARGETS]->(sc|sh|a)
```

### Query Patterns

1. **Continuity Check**: "Has this character been introduced?"
```cypher
MATCH (c:Character {name: $name})-[:APPEARS_IN]->(sc:Scene)
WHERE sc.sequence < $current_sequence
RETURN c, sc
ORDER BY sc.sequence
LIMIT 1
```

2. **Asset Reuse**: "Find existing asset for this character"
```cypher
MATCH (c:Character {id: $char_id})<-[:FOCUSES_ON]-(sh:Shot)<-[:USED_IN]-(a:Asset)
WHERE a.quality_score >= 0.8
RETURN a
ORDER BY a.quality_score DESC
LIMIT 5
```

3. **Feedback History**: "Get all feedback for this scene"
```cypher
MATCH (f:FeedbackAnnotation)-[:TARGETS]->(sc:Scene {id: $scene_id})
RETURN f
ORDER BY f.created_at DESC
```

4. **Scene Pattern Lookup**: "Find similar scenes from KB"
```cypher
MATCH (sc:Scene {id: $scene_id})-[:REUSES_PATTERN_FROM]->(kb:KnowledgeBaseScene)
RETURN kb
```

## Integration Points

### KRAG Retrieval Agent

```python
class KRAGRetrievalAgent:
    """Unified retrieval across both knowledge planes."""

    async def retrieve_for_scene(
        self,
        scene: Scene,
        retrieval_type: RetrievalType
    ) -> RetrievalResult:
        """
        Retrieve relevant knowledge for a scene.

        Args:
            scene: The scene being processed
            retrieval_type: What to retrieve (NARRATIVE, CINEMATIC, BOTH)

        Returns:
            RetrievalResult with ranked items from both planes
        """
        pass

    async def retrieve_similar_shots(
        self,
        shot_description: str,
        mood: str,
        top_k: int = 5
    ) -> list[ShotPattern]:
        """Retrieve similar shot patterns from video knowledge."""
        pass

    async def retrieve_narration_style(
        self,
        tone: str,
        era: str,
        top_k: int = 3
    ) -> list[NarrationExample]:
        """Retrieve narration examples from text knowledge."""
        pass
```

### Learning from Feedback

When feedback is received:

1. **Update Graph**: Add FeedbackAnnotation node, link to target
2. **Update Metadata**: Adjust quality scores on related vectors
3. **Update Constraints**: If systematic issue, add to constraint rules
4. **Update Playbooks**: If new pattern, add to shot planning rules

```python
async def ingest_feedback(
    self,
    feedback: StructuredFeedback,
    target_id: str,
    target_type: TargetType
) -> None:
    # 1. Store in graph
    await self.graph.create_feedback_annotation(feedback, target_id)

    # 2. Update vector metadata if applicable
    if feedback.overall_score < 3.0:
        await self.vector_store.downrank(target_id, feedback.fix_taxonomy)

    # 3. Check for constraint violations
    if "CONTINUITY" in feedback.fix_taxonomy:
        await self.update_continuity_rules(target_id, feedback)

    # 4. Update playbooks if systematic
    if await self.is_systematic_issue(feedback):
        await self.update_playbooks(feedback)
```

## Infrastructure

### Vector Store (Qdrant)

```yaml
collections:
  - name: text_knowledge
    vectors:
      size: 3072
      distance: Cosine
    payload_schema:
      source_id: keyword
      content_type: keyword
      genre: keyword
      quality_score: float
      usage_count: integer

  - name: video_knowledge
    vectors:
      size: 768
      distance: Cosine
    payload_schema:
      source_id: keyword
      shot_type: keyword
      duration_bucket: keyword
      mood: keyword
      quality_score: float
```

### Graph Store (Neo4j)

```yaml
neo4j:
  database: krag_video
  indexes:
    - CREATE INDEX scene_id FOR (s:Scene) ON (s.id)
    - CREATE INDEX character_name FOR (c:Character) ON (c.name)
    - CREATE INDEX shot_type FOR (sh:Shot) ON (sh.shot_type)
    - CREATE INDEX feedback_target FOR (f:FeedbackAnnotation) ON (f.target_id)
```

## Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Retrieval latency | Time to retrieve top-k | < 100ms |
| Retrieval relevance | Human-judged relevance@5 | > 0.8 |
| Graph query latency | Cypher query time | < 50ms |
| Feedback incorporation | Time to update from feedback | < 5s |
| Knowledge coverage | % of scenes with KB matches | > 70% |

---

*See [data-models.md](data-models.md) for complete schema definitions.*
