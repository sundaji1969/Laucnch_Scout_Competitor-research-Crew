"""Application settings, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_model: str = "anthropic/claude-sonnet-5-5"
    # Optional cheaper model for the two tool-using research agents (empty = use llm_model)
    llm_model_research: str = ""
    llm_temperature: float = 0.2

    # Search
    serper_api_key: str = ""
    serper_country: str = "in"
    serper_locale: str = "en"
    serper_results: int = 6
    # Cache identical Serper queries in Redis (0 = off)
    search_cache_ttl_seconds: int = 86_400
    # Give the Market Researcher a Google Maps price lookup (Serper Places, no scraping)
    places_lookup_enabled: bool = True

    # Crew
    process_mode: str = "sequential"
    guardrail_max_retries: int = 2
    run_timeout_seconds: int = 900
    outputs_dir: Path = Path("outputs")
    crew_verbose: bool = False
    # Context size controls: everything an agent reads is re-sent on every step of its loop
    scrape_max_chars: int = 5_000
    agent_max_iter: int = 12

    # Cost guards
    # Max new runs per UTC day across all users (0 = unlimited)
    daily_run_cap: int = 30
    # Serve an existing report for the same idea + city + customer from the last N days (0 = off)
    reuse_window_days: int = 7

    # Infra
    database_url: str = "postgresql+asyncpg://launchscout:launchscout@localhost:5432/launchscout"
    redis_url: str = "redis://localhost:6379/0"

    # Hardening
    rate_limit_runs: str = "3/day"
    max_concurrent_runs: int = 2
    cors_origins: str = "http://localhost:3000"
    max_input_chars: int = 300
    trust_proxy_headers: bool = False
    log_json: bool = True
    log_level: str = "INFO"

    turnstile_enabled: bool = False
    turnstile_secret_key: str = ""

    feature_pitch_deck: bool = False
    feature_weekly_rerun: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def outputs_path(self) -> Path:
        p = self.outputs_dir
        return p if p.is_absolute() else (Path.cwd() / p)


@lru_cache
def get_settings() -> Settings:
    return Settings()
