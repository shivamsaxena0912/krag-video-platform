# ADR-001: Deterministic Pipeline Architecture

## Status

Accepted

## Context

The AI video generation space is dominated by "prompt-to-video" approaches that treat the entire generation process as a black box. While these approaches can produce impressive results, they suffer from several critical issues:

1. **No inspectability**: Users cannot see or modify intermediate decisions
2. **Poor consistency**: Results vary unpredictably between runs
3. **No continuity control**: Multi-scene narratives lack coherence
4. **Unlearnable**: No structured feedback incorporation
5. **Debugging difficulty**: When output is poor, root cause is unclear

For our use case (narrative-to-video for historical content, evolving to brand videos), we need:
- Reliable, repeatable output quality
- Ability to maintain character/location consistency across scenes
- Human-reviewable intermediate artifacts
- Systematic quality improvement over time

## Decision

We will implement a **deterministic, stage-based pipeline architecture** where:

1. **Every stage produces inspectable artifacts**
   - Text → Scene Graph → Shot Plan → Assets → Timeline → Video
   - Each artifact is versioned, stored, and reviewable

2. **Stages have typed contracts**
   - Input/output schemas defined with Pydantic
   - Validation at stage boundaries
   - No implicit state passing

3. **Knowledge Graph as source of truth**
   - All entities (characters, locations, events) live in Neo4j
   - Relationships enforce continuity rules
   - Graph queries validate constraints

4. **Agents are stateless executors**
   - Each agent transforms input → output
   - No internal state between calls
   - Deterministic given same inputs

5. **Explicit feedback loops**
   - Structured feedback schema (not free text)
   - Feedback stored in graph for learning
   - Critique → Fix cycles with cost caps

## Consequences

### Positive

- **Debuggability**: Can identify exactly which stage/agent failed
- **Controllability**: Can intervene at any stage (modify shot plan, regenerate specific asset)
- **Consistency**: Same inputs produce same outputs (with temperature controls)
- **Learnability**: Structured feedback enables systematic improvement
- **Auditability**: Complete trace of decisions for compliance/review
- **Scalability**: Stages can be parallelized, cached, and distributed

### Negative

- **Complexity**: More components to build and maintain than end-to-end model
- **Latency**: Multiple stages add overhead vs. single model call
- **Integration effort**: Each stage needs explicit integration work
- **Schema evolution**: Changing schemas requires migration

### Neutral

- **Different skill set**: Requires pipeline engineering vs. model training
- **Infrastructure needs**: More services (graph DB, vector DB, queues)

## Alternatives Considered

### Alternative 1: End-to-End Model

Use a single model (like Sora) that takes text and produces video directly.

**Why rejected:**
- No control over intermediate decisions
- Cannot maintain consistency across scenes
- No structured feedback incorporation
- Quality varies unpredictably
- Not available/reliable for long-form content

### Alternative 2: Prompt Chaining

Use a single LLM with complex prompting to generate all outputs.

**Why rejected:**
- Context window limitations for long narratives
- No persistent memory for consistency
- No graph-based relationship enforcement
- Difficult to parallelize

### Alternative 3: Agent Framework Only

Use LangChain/AutoGPT-style autonomous agents.

**Why rejected:**
- Unpredictable execution paths
- Difficult to enforce stage boundaries
- Hard to cost-control
- Not deterministic enough for production

## References

- [Architecture Documentation](../architecture.md)
- [Pipeline Stages](../pipelines.md)
- [Agent Specifications](../agents.md)
