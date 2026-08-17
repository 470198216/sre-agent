from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"
TRACE_DIR = ROOT / "traces"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    ssh_private_key_path: str = Field(default="", alias="SSH_PRIVATE_KEY_PATH")
    ssh_passphrase: str | None = Field(default=None, alias="SSH_PASSPHRASE")
    max_agent_steps: int = Field(default=8, alias="MAX_AGENT_STEPS")


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def load_hosts() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "hosts.yaml")


def load_tools_config() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "tools.yaml")
