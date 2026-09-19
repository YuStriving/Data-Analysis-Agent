from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import ValidationError
from yaml import YAMLError

from agent_backend.foundation.llm.config import LlmRegistryConfig
from agent_backend.foundation.llm.errors import LlmConfigError
from agent_backend.foundation.llm.registry import LlmClientRegistry

LLM_CONFIG_PATH_ENV = "LLM_CONFIG_PATH"
DEFAULT_LLM_CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "llm.local.yaml"


def load_llm_registry_config(path: str | Path) -> LlmRegistryConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise LlmConfigError(f"LLM config file does not exist: {config_path}")
    if not config_path.is_file():
        raise LlmConfigError(f"LLM config path is not a file: {config_path}")

    try:
        raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LlmConfigError(f"Failed to read LLM config file: {config_path}") from exc
    except YAMLError as exc:
        raise LlmConfigError(f"Invalid LLM config YAML: {config_path}") from exc

    if not isinstance(raw_config, dict):
        raise LlmConfigError("LLM config root must be a mapping")

    try:
        return LlmRegistryConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise LlmConfigError("Invalid LLM registry config") from exc


def load_llm_registry_config_from_env() -> LlmRegistryConfig:
    config_path = os.environ.get(LLM_CONFIG_PATH_ENV)
    if config_path is None or not config_path.strip():
        config_path = str(DEFAULT_LLM_CONFIG_PATH)
    return load_llm_registry_config(config_path)


def build_llm_client_registry_from_env() -> LlmClientRegistry:
    return LlmClientRegistry.from_config(load_llm_registry_config_from_env())
