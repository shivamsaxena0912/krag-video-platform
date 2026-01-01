# Development Roadmap

## Overview

This document outlines the 90-day MVP development plan for the KRAG video platform. The goal is to demonstrate end-to-end capability with a single narrative → video workflow.

## Phase Structure

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              90-DAY MVP ROADMAP                                  │
│                                                                                  │
│  PHASE 1: Foundation (Weeks 1-4)                                                │
│  ════════════════════════════════                                               │
│  • Repository & infrastructure setup                                            │
│  • Core data models & schemas                                                   │
│  • Knowledge graph implementation                                               │
│  • Basic text parsing                                                           │
│                                                                                  │
│  PHASE 2: Pipeline Core (Weeks 5-8)                                             │
│  ══════════════════════════════════                                             │
│  • Scene graph generation                                                       │
│  • Shot planning agent                                                          │
│  • Asset generation integration                                                 │
│  • Basic video assembly                                                         │
│                                                                                  │
│  PHASE 3: Intelligence (Weeks 9-11)                                             │
│  ═══════════════════════════════════                                            │
│  • KRAG knowledge planes                                                        │
│  • Critic agent                                                                 │
│  • Refinement loop                                                              │
│  • Quality metrics                                                              │
│                                                                                  │
│  PHASE 4: Polish & Demo (Week 12)                                               │
│  ═════════════════════════════════                                              │
│  • End-to-end testing                                                           │
│  • Demo video production                                                        │
│  • Documentation                                                                │
│  • Demo presentation                                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Foundation (Weeks 1-4)

### Week 1: Project Setup

**Objectives**:
- Repository initialized with structure
- Development environment configured
- CI/CD pipeline basic setup
- Team onboarding complete

**Deliverables**:
- [ ] Repository with full directory structure
- [ ] Docker Compose for local development
- [ ] Pre-commit hooks configured
- [ ] Basic CI pipeline (lint, type check)
- [ ] README and initial documentation

**Tasks**:
```
1.1 Initialize repository structure
1.2 Set up Python project (pyproject.toml, dependencies)
1.3 Configure Docker Compose for local services
1.4 Set up pre-commit (black, ruff, mypy)
1.5 Create GitHub Actions workflow
1.6 Write initial documentation
```

### Week 2: Data Models & Database

**Objectives**:
- All core data models implemented
- Database schemas created
- Basic CRUD operations working

**Deliverables**:
- [ ] Pydantic models for all entities
- [ ] PostgreSQL schema and migrations
- [ ] Neo4j schema and indexes
- [ ] Repository pattern for data access
- [ ] Unit tests for models

**Tasks**:
```
2.1 Implement Story, Scene, Shot models
2.2 Implement Character, Location, Event models
2.3 Implement Asset, Feedback models
2.4 Create PostgreSQL migrations (Alembic)
2.5 Create Neo4j schema setup script
2.6 Implement repository classes
2.7 Write model unit tests
```

### Week 3: Knowledge Graph Core

**Objectives**:
- Neo4j integration complete
- Graph operations implemented
- Continuity queries working

**Deliverables**:
- [ ] Neo4j client wrapper
- [ ] Graph CRUD operations
- [ ] Relationship management
- [ ] Continuity validation queries
- [ ] Integration tests

**Tasks**:
```
3.1 Create Neo4j connection manager
3.2 Implement node creation/update/delete
3.3 Implement relationship operations
3.4 Write Cypher queries for continuity checks
3.5 Create query result mappers
3.6 Write integration tests
```

### Week 4: Text Parsing Foundation

**Objectives**:
- Basic text ingestion working
- Scene segmentation implemented
- Entity extraction started

**Deliverables**:
- [ ] Text loader with format detection
- [ ] Scene boundary detection (rule-based)
- [ ] Character/location extraction (NER)
- [ ] Story Parser Agent (v1)
- [ ] Test with sample texts

**Tasks**:
```
4.1 Implement text ingestion utilities
4.2 Create scene boundary detector
4.3 Integrate NER for entity extraction
4.4 Build Story Parser Agent scaffold
4.5 Implement LLM-based scene analysis
4.6 Test with 3+ sample narratives
```

---

## Phase 2: Pipeline Core (Weeks 5-8)

### Week 5: Scene Graph Generation

**Objectives**:
- Full scene graph from text
- Entities linked in graph
- Continuity Agent working

**Deliverables**:
- [ ] Complete scene graph generation
- [ ] Entity resolution and linking
- [ ] Continuity & Canon Agent (v1)
- [ ] Scene graph visualization
- [ ] Validation test suite

**Tasks**:
```
5.1 Enhance scene segmentation with LLM
5.2 Implement entity resolution
5.3 Create scene-to-graph transformation
5.4 Build Continuity Agent
5.5 Add validation rules
5.6 Create visualization utility
```

### Week 6: Shot Planning

**Objectives**:
- Creative Director Agent working
- Shot plans generated from scenes
- Cinematic grammar rules applied

**Deliverables**:
- [ ] Creative Director Agent (v1)
- [ ] Shot type selection logic
- [ ] Duration estimation
- [ ] Transition planning
- [ ] Audio plan generation

**Tasks**:
```
6.1 Design shot planning prompt templates
6.2 Implement Creative Director Agent
6.3 Add cinematic grammar rules
6.4 Create shot plan validator
6.5 Implement audio plan generation
6.6 Test with multiple scene types
```

### Week 7: Asset Generation

**Objectives**:
- Image generation integrated
- Voice synthesis integrated
- Asset Generation Agent working

**Deliverables**:
- [ ] Prompt Engineering Agent (v1)
- [ ] Replicate/OpenAI image integration
- [ ] ElevenLabs voice integration
- [ ] Asset Generation Agent (v1)
- [ ] Asset quality validation

**Tasks**:
```
7.1 Implement Prompt Engineering Agent
7.2 Create image generation client
7.3 Create voice synthesis client
7.4 Build Asset Generation Agent
7.5 Implement consistency mechanisms
7.6 Add quality scoring
```

### Week 8: Video Assembly

**Objectives**:
- Timeline assembly working
- Motion effects applied
- Draft video output

**Deliverables**:
- [ ] Editor Agent (v1)
- [ ] FFmpeg-based video assembly
- [ ] Ken Burns motion effects
- [ ] Audio synchronization
- [ ] Draft video rendering

**Tasks**:
```
8.1 Design timeline data structure
8.2 Implement FFmpeg wrapper
8.3 Create motion effect generators
8.4 Build Editor Agent
8.5 Implement audio sync
8.6 End-to-end assembly test
```

---

## Phase 3: Intelligence (Weeks 9-11)

### Week 9: KRAG Implementation

**Objectives**:
- Vector stores configured
- Embedding pipeline working
- Retrieval agent functional

**Deliverables**:
- [ ] Qdrant collections setup
- [ ] Embedding generation pipeline
- [ ] Text knowledge ingestion
- [ ] KRAG Retrieval Agent (v1)
- [ ] Retrieval quality metrics

**Tasks**:
```
9.1 Set up Qdrant collections
9.2 Implement embedding generation
9.3 Create knowledge ingestion pipeline
9.4 Build KRAG Retrieval Agent
9.5 Integrate retrieval into planning
9.6 Measure retrieval quality
```

### Week 10: Critique & Feedback

**Objectives**:
- Critic Agent evaluating videos
- Structured feedback generated
- Feedback stored in graph

**Deliverables**:
- [ ] Critic Agent (v1)
- [ ] Evaluation prompt templates
- [ ] Score calibration
- [ ] Feedback storage
- [ ] Feedback UI mockup

**Tasks**:
```
10.1 Design critic evaluation prompts
10.2 Implement Critic Agent
10.3 Create scoring calibration
10.4 Build feedback storage layer
10.5 Link feedback to graph
10.6 Design HITL interface
```

### Week 11: Refinement Loop

**Objectives**:
- Iterative refinement working
- Convergence detection
- Cost controls enforced

**Deliverables**:
- [ ] Iterative Refinement Controller
- [ ] Fix execution pipeline
- [ ] Convergence detection
- [ ] Cost tracking and caps
- [ ] Refinement metrics

**Tasks**:
```
11.1 Design refinement controller
11.2 Implement fix dispatching
11.3 Create re-critique loop
11.4 Add convergence detection
11.5 Implement cost controls
11.6 Measure refinement effectiveness
```

---

## Phase 4: Polish & Demo (Week 12)

### Week 12: Integration & Demo

**Objectives**:
- End-to-end pipeline working
- Demo video produced
- Documentation complete

**Deliverables**:
- [ ] Complete pipeline integration
- [ ] Demo narrative processed
- [ ] 5-minute demo video
- [ ] Final documentation
- [ ] Demo presentation

**Tasks**:
```
12.1 Full pipeline integration testing
12.2 Bug fixes and polish
12.3 Select demo narrative
12.4 Run demo production
12.5 Prepare presentation
12.6 Final documentation review
```

---

## Success Criteria

### MVP Requirements

| Requirement | Target | Validation |
|-------------|--------|------------|
| Process 5-page narrative | Yes | Demo |
| Generate 3-5 minute video | Yes | Demo |
| Scene graph accuracy | >80% | Manual review |
| Shot plan coherence | >70% | Expert review |
| Visual consistency | >70% | Visual inspection |
| Audio synchronization | >90% | Manual check |
| Pipeline completion | <30 min | Timing |
| Cost per minute | <$5 | Tracking |

### Quality Metrics

| Metric | Target |
|--------|--------|
| Narrative clarity score | ≥3.5/5 |
| Pacing score | ≥3.5/5 |
| Overall quality score | ≥6/10 |
| Human approval rate | ≥50% |

---

## Resource Requirements

### Team

| Role | Allocation |
|------|------------|
| Lead Engineer | 100% |
| ML Engineer | 50% (Weeks 5-11) |
| Backend Engineer | 50% (Weeks 1-8) |

### Infrastructure

| Service | Monthly Cost |
|---------|--------------|
| Cloud compute | $200-500 |
| Neo4j Aura | $65 |
| Qdrant Cloud | $25 |
| OpenAI API | $100-300 |
| ElevenLabs | $100-200 |
| Replicate | $100-300 |

### External Dependencies

- OpenAI API access
- Anthropic API access
- ElevenLabs API access
- Replicate API access
- Public domain narrative texts

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Image consistency issues | High | Medium | Reference image system, seed control |
| Voice synthesis quality | Medium | Medium | Multiple voice options, fallbacks |
| LLM rate limits | Medium | Low | Retry logic, multiple providers |
| Cost overruns | Medium | Medium | Cost caps, budget monitoring |
| Timeline slip | Medium | High | Weekly scope review, cut features |
| Integration complexity | Low | High | Incremental integration, testing |

---

## Post-MVP Roadmap

### Q2 Priorities
- HITL review interface
- Video knowledge plane ingestion
- Template system for shot patterns
- API for external access

### Q3 Priorities
- Multi-scene video stitching
- Character voice consistency
- Music generation integration
- Quality automation

### Q4 Priorities
- Brand brief input format
- Campaign orchestration
- A/B testing framework
- Enterprise features

---

*This roadmap will be updated weekly based on progress and learnings.*
