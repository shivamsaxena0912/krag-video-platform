# Infrastructure Design

## Overview

The KRAG video platform is designed for production deployment with scalability, reliability, and cost efficiency in mind.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 EDGE LAYER                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         CDN / Load Balancer                              │   │
│  │                    (CloudFlare / AWS CloudFront)                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               APPLICATION LAYER                                  │
│                                                                                  │
│  ┌───────────────────────┐    ┌───────────────────────┐                        │
│  │     API Gateway       │    │    WebSocket Server   │                        │
│  │    (FastAPI + Uvicorn)│    │   (HITL Real-time)    │                        │
│  └───────────────────────┘    └───────────────────────┘                        │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        Pipeline Workers (N instances)                    │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │   │
│  │  │ Parser  │  │ Planner │  │Generator│  │ Editor  │  │ Critic  │       │   │
│  │  │ Worker  │  │ Worker  │  │ Worker  │  │ Worker  │  │ Worker  │       │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 DATA LAYER                                       │
│                                                                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │  PostgreSQL   │  │    Neo4j      │  │    Qdrant     │  │     Redis     │   │
│  │  (State, Jobs)│  │(Knowledge Graph)│ │ (Vector Store)│  │   (Cache)     │   │
│  └───────────────┘  └───────────────┘  └───────────────┘  └───────────────┘   │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                        Object Storage (S3 / MinIO)                        │ │
│  │                    Assets, Videos, Logs, Artifacts                        │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                                   │
│                                                                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │    OpenAI     │  │    Anthropic  │  │  ElevenLabs   │  │   Replicate   │   │
│  │    (GPT-4)    │  │   (Claude)    │  │  (Voice)      │  │   (SDXL)      │   │
│  └───────────────┘  └───────────────┘  └───────────────┘  └───────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Component Specifications

### API Gateway

**Technology**: FastAPI + Uvicorn

**Responsibilities**:
- REST API endpoints
- Request validation
- Authentication/Authorization
- Rate limiting
- Request logging

**Endpoints**:
```
POST /api/v1/stories           # Create new story
GET  /api/v1/stories/{id}      # Get story details
POST /api/v1/stories/{id}/run  # Start pipeline
GET  /api/v1/runs/{id}         # Get run status
GET  /api/v1/runs/{id}/output  # Get run output
POST /api/v1/feedback          # Submit feedback
```

**Scaling**: 2-10 instances behind load balancer

---

### Job Queue

**Technology**: Redis + Celery (or Temporal for complex workflows)

**Queue Types**:
- `pipeline.high` - New pipeline runs
- `pipeline.normal` - Refinement iterations
- `generation.images` - Image generation jobs
- `generation.audio` - Audio generation jobs
- `notification` - Alerts and notifications

**Job Schema**:
```python
class Job(BaseModel):
    id: str
    queue: str
    payload: dict
    priority: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    status: JobStatus
    retries: int
    max_retries: int
```

---

### PostgreSQL

**Purpose**: Transactional data, job state, audit logs

**Schema**:
```sql
-- Core tables
CREATE TABLE stories (
    id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    source_type VARCHAR NOT NULL,
    source_metadata JSONB,
    status VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE pipeline_runs (
    id VARCHAR PRIMARY KEY,
    story_id VARCHAR REFERENCES stories(id),
    status VARCHAR NOT NULL,
    current_stage VARCHAR,
    stage_outputs JSONB,
    costs JSONB,
    config JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE assets (
    id VARCHAR PRIMARY KEY,
    run_id VARCHAR REFERENCES pipeline_runs(id),
    asset_type VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    generation_params JSONB,
    quality_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE feedback (
    id VARCHAR PRIMARY KEY,
    target_type VARCHAR NOT NULL,
    target_id VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    scores JSONB,
    issues JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_runs_story ON pipeline_runs(story_id);
CREATE INDEX idx_runs_status ON pipeline_runs(status);
CREATE INDEX idx_assets_run ON assets(run_id);
CREATE INDEX idx_feedback_target ON feedback(target_type, target_id);
```

**Scaling**: Primary + read replicas

---

### Neo4j

**Purpose**: Knowledge Graph storage

**Deployment**: Neo4j Aura (managed) or self-hosted cluster

**Configuration**:
```yaml
neo4j:
  uri: bolt://neo4j:7687
  database: krag_video
  max_connection_pool_size: 50
  connection_timeout: 30s
```

**Indexes**:
```cypher
CREATE INDEX scene_id FOR (s:Scene) ON (s.id);
CREATE INDEX character_name FOR (c:Character) ON (c.name);
CREATE INDEX story_id FOR (st:Story) ON (st.id);
CREATE FULLTEXT INDEX scene_content FOR (s:Scene) ON EACH [s.summary, s.raw_text];
```

---

### Qdrant

**Purpose**: Vector storage for KRAG

**Collections**:
```yaml
collections:
  text_knowledge:
    vectors:
      size: 3072
      distance: Cosine
    optimizers_config:
      indexing_threshold: 10000
    replication_factor: 2

  video_knowledge:
    vectors:
      size: 768
      distance: Cosine
    optimizers_config:
      indexing_threshold: 5000
    replication_factor: 2
```

**Deployment**: Qdrant Cloud or self-hosted cluster

---

### Redis

**Purpose**: Caching, session storage, rate limiting

**Data Structures**:
- `cache:embedding:{hash}` - Embedding cache (TTL: 1 hour)
- `cache:asset:{hash}` - Asset metadata cache (TTL: 24 hours)
- `rate_limit:{user_id}` - Rate limit counters
- `session:{session_id}` - User sessions
- `lock:run:{run_id}` - Distributed locks

**Configuration**:
```yaml
redis:
  url: redis://redis:6379
  max_connections: 100
  socket_timeout: 5
  retry_on_timeout: true
```

---

### Object Storage

**Technology**: S3 (AWS) or MinIO (self-hosted)

**Bucket Structure**:
```
krag-video-platform/
├── inputs/
│   └── {story_id}/
│       └── source.txt
├── assets/
│   └── {run_id}/
│       ├── images/
│       │   └── {shot_id}.png
│       ├── audio/
│       │   ├── voiceover.mp3
│       │   └── music.mp3
│       └── video/
│           └── draft.mp4
├── outputs/
│   └── {run_id}/
│       └── final.mp4
└── artifacts/
    └── {run_id}/
        ├── scene_graph.json
        ├── shot_plan.json
        └── feedback.json
```

**Lifecycle Policies**:
- Draft assets: Delete after 7 days
- Final outputs: Keep indefinitely
- Artifacts: Archive after 30 days

---

## External Service Integration

### LLM Providers

**Primary**: OpenAI GPT-4 / Anthropic Claude

```python
class LLMConfig(BaseModel):
    provider: str  # "openai" | "anthropic"
    model: str
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 60
    retry_attempts: int = 3


# Fallback chain
LLM_FALLBACK_CHAIN = [
    LLMConfig(provider="anthropic", model="claude-3-opus"),
    LLMConfig(provider="openai", model="gpt-4-turbo"),
    LLMConfig(provider="anthropic", model="claude-3-sonnet"),
]
```

### Image Generation

**Primary**: Replicate (SDXL) / OpenAI DALL-E 3

```python
class ImageGenConfig(BaseModel):
    provider: str  # "replicate" | "openai"
    model: str
    width: int = 1920
    height: int = 1080
    num_inference_steps: int = 30
    guidance_scale: float = 7.5


IMAGE_GEN_FALLBACK = [
    ImageGenConfig(provider="replicate", model="sdxl"),
    ImageGenConfig(provider="openai", model="dall-e-3"),
]
```

### Voice Synthesis

**Primary**: ElevenLabs

```python
class VoiceConfig(BaseModel):
    provider: str  # "elevenlabs" | "openai"
    voice_id: str
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
```

---

## Deployment

### Docker Compose (Development)

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/krag
      - REDIS_URL=redis://redis:6379
      - NEO4J_URI=bolt://neo4j:7687
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - db
      - redis
      - neo4j
      - qdrant

  worker:
    build: .
    command: celery -A src.orchestration.worker worker -l info
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/krag
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: krag
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  neo4j:
    image: neo4j:5
    environment:
      NEO4J_AUTH: neo4j/password
    volumes:
      - neo4j_data:/data

  qdrant:
    image: qdrant/qdrant
    volumes:
      - qdrant_data:/qdrant/storage

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio123
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  redis_data:
  neo4j_data:
  qdrant_data:
  minio_data:
```

### Kubernetes (Production)

Key manifests:
- API Deployment (HPA: 2-10 replicas)
- Worker Deployment (HPA: 2-20 replicas)
- PostgreSQL StatefulSet (or managed RDS)
- Neo4j StatefulSet (or Aura)
- Qdrant StatefulSet (or Qdrant Cloud)
- Redis Cluster (or ElastiCache)
- Ingress with TLS

---

## Monitoring & Observability

### Metrics (Prometheus)

```python
# Pipeline metrics
pipeline_duration = Histogram(
    'pipeline_duration_seconds',
    'Pipeline execution duration',
    ['stage']
)

generation_cost = Counter(
    'generation_cost_dollars',
    'Generation API costs',
    ['provider', 'model']
)

# Agent metrics
agent_calls = Counter(
    'agent_calls_total',
    'Agent invocations',
    ['agent', 'status']
)

agent_latency = Histogram(
    'agent_latency_seconds',
    'Agent execution latency',
    ['agent']
)
```

### Logging (Structured JSON)

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "pipeline_stage_complete",
    run_id=run.id,
    stage="shot_planning",
    duration_ms=1234,
    output_shots=len(shot_plan.shots),
)
```

### Tracing (OpenTelemetry)

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("execute_agent") as span:
    span.set_attribute("agent.name", agent.name)
    span.set_attribute("run.id", run_id)
    result = await agent.execute(input)
```

### Alerting

| Alert | Condition | Severity |
|-------|-----------|----------|
| High error rate | >5% failures in 5 min | Critical |
| Pipeline stuck | No progress in 10 min | Warning |
| Cost spike | >200% of daily average | Warning |
| API latency | P99 > 5s | Warning |
| Worker queue depth | >100 jobs for 5 min | Warning |

---

## Security

### Authentication

- JWT tokens for API access
- API keys for service accounts
- OAuth2 for user authentication (future)

### Authorization

- Role-based access control (RBAC)
- Story-level permissions
- Resource quotas per user

### Data Protection

- TLS for all connections
- Encryption at rest (S3, databases)
- Secrets in Vault/SSM
- PII handling policies

### Network Security

- VPC isolation
- Security groups
- WAF for API
- DDoS protection

---

## Cost Optimization

### Compute

- Spot instances for workers
- Right-sizing based on metrics
- Auto-scaling policies

### Storage

- Tiered storage (hot/warm/cold)
- Lifecycle policies
- Compression for artifacts

### API Costs

- Caching embeddings
- Batch processing where possible
- Model selection by task complexity
- Cost caps and alerts

---

*See [architecture.md](architecture.md) for system design.*
