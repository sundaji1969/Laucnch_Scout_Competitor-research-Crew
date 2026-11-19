import os
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("SERPER_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")


@pytest.fixture
def settings(tmp_path: Path) -> Any:
    from app.config import Settings

    return Settings(outputs_dir=tmp_path / "outputs", llm_model="anthropic/claude-sonnet-5-5")
