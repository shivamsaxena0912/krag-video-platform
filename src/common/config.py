"""Configuration management."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "krag-video-platform"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/krag"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "krag_password_123"
    neo4j_database: str = "neo4j"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Object Storage
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minio"
    s3_secret_key: str = "minio123"
    s3_bucket: str = "krag-video"
    s3_region: str = "us-east-1"

    # LLM Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Image Generation
    replicate_api_token: str = ""

    # Voice Synthesis
    elevenlabs_api_key: str = ""

    # Default Models
    default_llm_model: str = "gpt-4-turbo"
    default_embedding_model: str = "text-embedding-3-large"
    default_image_model: str = "sdxl"
    default_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs default

    # Pipeline Defaults
    default_max_cost: float = 50.0
    default_max_iterations: int = 3
    default_quality_threshold: float = 7.0

    # Timeouts
    llm_timeout_seconds: int = 60
    generation_timeout_seconds: int = 300

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
