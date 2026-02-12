"""
Application configuration management using Pydantic BaseSettings.

Loads configuration from environment variables with .env file support.
"""

from typing import List

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database Configuration
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://opendiscuss:opendiscuss_dev@localhost:5432/opendiscuss",
        description="PostgreSQL connection URL for async SQLAlchemy",
    )

    # Redis Configuration
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for timing coordination and caching",
    )

    # Security Configuration
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        min_length=32,
        description="Secret key for JWT token signing and session management",
    )

    # CORS Configuration
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins for frontend applications",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Application Configuration
    app_name: str = Field(
        default="OpenDiscuss Discussion Protocol",
        description="Application name for logging and monitoring",
    )

    environment: str = Field(
        default="development",
        description="Environment name: development, staging, production",
    )

    debug: bool = Field(
        default=True,
        description="Enable debug mode (detailed error messages, auto-reload)",
    )

    # API Configuration
    api_v1_prefix: str = Field(
        default="/api/v1",
        description="API version 1 route prefix",
    )

    # Timing Configuration
    timing_precision_ms: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum allowed timing drift in milliseconds (±100ms default)",
    )

    timing_poll_interval_ms: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Redis timing service polling interval in milliseconds",
    )

    # Submission Window Configuration
    submission_window_min_seconds: int = Field(
        default=180,
        ge=60,
        le=600,
        description="Minimum submission window duration (3 minutes default)",
    )

    submission_window_max_seconds: int = Field(
        default=360,
        ge=180,
        le=900,
        description="Maximum submission window duration (6 minutes default)",
    )

    submission_window_duration_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Default submission window duration in minutes (Spec 002)",
    )

    # Rate Limiting Configuration
    max_submissions_per_round: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of submissions per participant per round",
    )

    api_rate_limit_per_minute: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="API rate limit: requests per minute per IP address (T086)",
    )

    # Performance Configuration
    max_concurrent_participants: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum concurrent participants per discussion",
    )

    max_parallel_discussions: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum parallel discussions per community",
    )

    # Database Pool Configuration
    db_pool_size: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Database connection pool size",
    )

    db_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Maximum overflow connections beyond pool size",
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    log_format: str = Field(
        default="json",
        description="Log format: json or text",
    )

    # Feature Flags
    enable_telemetry: bool = Field(
        default=False,
        description="Enable OpenTelemetry instrumentation",
    )

    enable_approval_timeout: bool = Field(
        default=True,
        description="Enable automatic approval deadline timeout handling",
    )

    approval_timeout_minutes: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Minutes before unapproved summaries trigger timeout",
    )

    # Ephemeral Data Configuration
    submission_ttl_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Minutes to retain submissions after approval (grace period)",
    )

    # LLM Configuration (Spec 002: Input Collection - Whisper transcription)
    # LLM Configuration (Spec 003: Summarization - GPT-4-turbo/GPT-3.5)
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key for Whisper transcription and summarization",
    )

    openai_org_id: str = Field(
        default="",
        description="OpenAI Organization ID (optional)",
    )

    openai_default_model: str = Field(
        default="gpt-4-turbo",
        description="Default OpenAI model for summarization (gpt-4-turbo or gpt-3.5-turbo)",
    )

    openai_fallback_model: str = Field(
        default="gpt-3.5-turbo",
        description="Fallback OpenAI model for cost optimization or retry",
    )

    llm_cache_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="LLM response cache TTL in seconds (1 hour default)",
    )

    openai_moderation_enabled: bool = Field(
        default=True,
        description="Enable OpenAI Moderation API for threat detection (Spec 003 User Story 4)",
    )

    # LLM Configuration (Spec 006: Question Progression)
    claude_api_key: str = Field(
        default="",
        description="Anthropic Claude API key for question generation",
        alias="ANTHROPIC_API_KEY",
    )

    claude_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Claude model for question generation",
    )

    question_generation_timeout_seconds: int = Field(
        default=30,
        ge=10,
        le=120,
        description="Timeout for Claude API question generation requests",
    )

    question_generation_max_retries: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum retry attempts for question generation",
    )

    # Clustering & Alignment Configuration (Spec 004: T079)
    align_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold for cross-round cluster alignment (default 0.7)",
    )

    hdbscan_min_cluster_size: int = Field(
        default=2,
        ge=2,
        le=100,
        description="HDBSCAN min_cluster_size parameter - minimum points to form a cluster (default 2 for minority preservation)",
    )

    hdbscan_cluster_selection_method: str = Field(
        default="eom",
        pattern="^(eom|leaf)$",
        description="HDBSCAN cluster_selection_method - 'eom' (Excess of Mass) or 'leaf' (default eom)",
    )

    embedding_model_version: str = Field(
        default="all-MiniLM-L6-v2",
        description="SBERT embedding model version (default all-MiniLM-L6-v2, 384-dimensional)",
    )

    # Monitoring & Observability Configuration (Spec 004: T078)
    enable_clustering_metrics: bool = Field(
        default=True,
        description="Enable clustering performance metrics and observability logging",
    )

    clustering_latency_threshold_ms: int = Field(
        default=5000,
        ge=1000,
        le=30000,
        description="Threshold for clustering latency warning logs (5s default)",
    )

    alignment_latency_threshold_ms: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Threshold for alignment latency warning logs (1s default)",
    )

    # Miller's Law Clustering Configuration
    clustering_adaptive_enabled: bool = Field(
        default=True,
        description="Enable adaptive parameter scaling for Miller's Law (7±2 clusters)",
    )

    clustering_merge_threshold: float = Field(
        default=0.82,
        ge=0.7,
        le=0.95,
        description="Minimum centroid similarity to merge near-duplicate clusters (0.82 = semantic equivalence)",
    )

    clustering_noise_reassignment_threshold: float = Field(
        default=0.4,
        ge=0.0,
        le=0.7,
        description="Minimum similarity to reassign noise points to clusters (0.4 default)",
    )

    clustering_target_range_min: int = Field(
        default=5,
        ge=3,
        le=7,
        description="Minimum target cluster count (Miller's Law lower bound)",
    )

    clustering_target_range_max: int = Field(
        default=9,
        ge=7,
        le=12,
        description="Maximum target cluster count (Miller's Law upper bound)",
    )

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"


# Global settings instance
settings = Settings()
