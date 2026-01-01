# KRAG Video Platform

> A deterministic, inspectable AI pipeline for transforming textual narratives into coherent cinematic videos.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Vision

This platform converts unfilmed textual narratives—historical books, long-form stories, scripts—into coherent, cinematic videos using structured planning, knowledge-augmented retrieval, agent orchestration, and expert feedback loops.

**This is NOT prompt-to-video.** The system follows a deterministic, inspectable pipeline where every decision is traceable, every intermediate artifact is reviewable, and every output is explainable.

### Long-Term Goal

A creative operating system that reliably produces brand-quality marketing videos (reels, ads, explainers, brand films) for startups and enterprises via APIs and self-serve workflows.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT LAYER                                     │
│  Text Sources: Books, Scripts, Narratives, Story Outlines                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KNOWLEDGE LAYER (KRAG)                               │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────────┐ │
│  │  Text Knowledge Plane   │    │      Video Knowledge Plane              │ │
│  │  ───────────────────    │    │      ─────────────────────              │ │
│  │  • Story arcs           │    │      • Shot grammar                     │ │
│  │  • Pacing logic         │    │      • Editing language                 │ │
│  │  • Narration styles     │    │      • Pacing norms                     │ │
│  │  • Persuasion patterns  │    │      • Audio/visual alignment           │ │
│  └─────────────────────────┘    └─────────────────────────────────────────┘ │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      KNOWLEDGE GRAPH                                   │  │
│  │  Entities: Story, Scene, Shot, Character, Location, Event, Asset      │  │
│  │  Ground-truth for continuity, constraints, and canon                  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PROCESSING PIPELINE                                 │
│                                                                              │
│  ┌──────────┐   ┌───────────┐   ┌──────────┐   ┌────────────┐   ┌────────┐ │
│  │   Text   │──▶│   Scene   │──▶│   Shot   │──▶│   Asset    │──▶│Timeline│ │
│  │  Input   │   │   Graph   │   │   Plan   │   │ Generation │   │Assembly│ │
│  └──────────┘   └───────────┘   └──────────┘   └────────────┘   └────────┘ │
│                                                                      │       │
│                                                                      ▼       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    CRITIQUE & REFINEMENT LOOP                          │ │
│  │  AI Critic ←→ Human Expert ←→ Iterative Refinement Controller          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             OUTPUT LAYER                                     │
│  Final Video: Narrated cinematic content with generated visuals,            │
│               professional voiceover, background music, tight pacing        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Pipeline

| Stage | Input | Output | Agent(s) |
|-------|-------|--------|----------|
| **1. Text Parsing** | Raw text/book | Structured segments | Story Parser Agent |
| **2. Scene Graph** | Segments | Scene nodes with metadata | Continuity Agent |
| **3. Shot Planning** | Scene Graph | Shot sequences with specs | Creative Director Agent |
| **4. Asset Generation** | Shot Plan | Images, audio, clips | Asset Generation Agent |
| **5. Timeline Assembly** | Assets + Plan | Draft video | Editor Agent |
| **6. Critique** | Draft video | Structured feedback | Critic Agent |
| **7. Refinement** | Feedback + Draft | Improved video | Refinement Controller |
| **8. Final Output** | Approved video | Published content | HITL Gatekeeper |

## MVP Scope (v1)

- **Output Format**: Narrated documentary-style videos
- **Visual Style**: AI-generated images with subtle motion (Ken Burns, parallax)
- **Audio**: Professional AI voiceover + background music
- **Duration**: 2-10 minute segments
- **No full video generation** in v1 (no Sora/Runway-style synthesis)

## Repository Structure

```
krag-video-platform/
├── docs/                    # Documentation
│   ├── vision.md           # Product vision and strategy
│   ├── architecture.md     # System architecture deep-dive
│   ├── krag.md             # KRAG strategy and implementation
│   ├── agents.md           # Agent specifications and contracts
│   ├── data-models.md      # Schema definitions
│   ├── pipelines.md        # Pipeline stage details
│   ├── infra.md            # Infrastructure design
│   ├── evaluation.md       # Quality metrics and evaluation
│   ├── roadmap.md          # Development roadmap
│   ├── gtm.md              # Go-to-market strategy
│   └── adr/                # Architecture Decision Records
├── src/                     # Source code
│   ├── ingestion/          # Text and video ingestion
│   ├── rag/                # Retrieval-augmented generation
│   ├── knowledge_graph/    # Graph database operations
│   ├── agents/             # Agent implementations
│   ├── orchestration/      # Pipeline orchestration
│   ├── generation/         # Asset generation
│   ├── editing/            # Video editing and assembly
│   ├── api/                # REST/GraphQL API
│   └── common/             # Shared utilities
├── configs/                 # Configuration files
├── scripts/                 # Utility scripts
├── tests/                   # Test suites
│   ├── unit/
│   └── integration/
├── examples/                # Example inputs and outputs
└── assets/                  # Sample assets
    └── samples/
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Neo4j (Graph DB)
- Qdrant or Pinecone (Vector DB)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/krag-video-platform.git
cd krag-video-platform

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp configs/.env.example configs/.env

# Start infrastructure
docker-compose up -d

# Run tests
pytest tests/
```

### First Run

```python
from src.orchestration import Pipeline
from src.ingestion import TextLoader

# Load narrative text
text = TextLoader.from_file("examples/sample_narrative.txt")

# Initialize pipeline
pipeline = Pipeline.from_config("configs/default.yaml")

# Process text to video
result = pipeline.run(text)

# Output: Draft video ready for review
print(f"Draft video saved to: {result.output_path}")
```

## Key Design Decisions

1. **Deterministic Pipeline**: Every stage produces inspectable artifacts. No black-box generation.

2. **Dual KRAG**: Separate knowledge planes for narrative (text) and cinematic (video) intelligence.

3. **Knowledge Graph as Source of Truth**: Neo4j graph maintains continuity, constraints, and canon across scenes.

4. **Typed Agents**: Each agent has strict input/output Pydantic schemas. No ambiguous interfaces.

5. **Structured Feedback**: Critiques follow a fixed schema (1-5 scores + taxonomy) for learnable improvement.

6. **Cost-Aware Iteration**: Refinement loops have max iterations and cost caps.

## Documentation

| Document | Description |
|----------|-------------|
| [Vision](docs/vision.md) | Product vision and strategic context |
| [Architecture](docs/architecture.md) | System design and component interactions |
| [KRAG Strategy](docs/krag.md) | Knowledge retrieval and augmentation |
| [Agents](docs/agents.md) | Agent specifications and contracts |
| [Data Models](docs/data-models.md) | Schema definitions for all entities |
| [Roadmap](docs/roadmap.md) | 90-day MVP development plan |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Built for production. Designed for scale. Engineered for quality.**
