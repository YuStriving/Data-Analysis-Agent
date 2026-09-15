from __future__ import annotations

from pathlib import Path

import pytest

from agent_backend.foundation.llm import (
    LLM_CONFIG_PATH_ENV,
    LlmClientRegistry,
    LlmCompletionRequest,
    LlmConfigError,
    LlmMessage,
    build_llm_client_registry_from_env,
    load_llm_registry_config,
    load_llm_registry_config_from_env,
)


def test_load_llm_registry_config_from_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "llm.yaml"
    config_path.write_text(
        """
default_client_id: sql-generator
clients:
  - client_id: sql-generator
    provider: openai-compatible
    model_name: deepseek-chat
    options:
      base_url: https://api.deepseek.com/v1
      api_key_env: DEEPSEEK_API_KEY
      timeout_ms: 30000
  - client_id: summary
    provider: fake
    model_name: fake-summary
    options:
      outputs:
        - first
        - second
""",
        encoding="utf-8",
    )

    config = load_llm_registry_config(config_path)

    assert config.default_client_id == "sql-generator"
    assert [client.client_id for client in config.clients] == ["sql-generator", "summary"]
    assert config.clients[0].provider == "openai-compatible"
    assert config.clients[0].options["base_url"] == "https://api.deepseek.com/v1"
    assert config.clients[1].options["outputs"] == ["first", "second"]


def test_build_llm_client_registry_from_env_with_fake_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "llm.yaml"
    config_path.write_text(
        """
default_client_id: summary
clients:
  - client_id: summary
    provider: fake
    model_name: fake-summary
    options:
      outputs: summary ok
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(LLM_CONFIG_PATH_ENV, str(config_path))

    registry = build_llm_client_registry_from_env()
    request = LlmCompletionRequest(messages=[LlmMessage(role="user", content="Hello.")])

    assert isinstance(registry, LlmClientRegistry)
    assert registry.get_default().complete(request).content == "summary ok"


def test_load_llm_registry_config_from_env_requires_config_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LLM_CONFIG_PATH_ENV, raising=False)

    with pytest.raises(LlmConfigError) as exc:
        load_llm_registry_config_from_env()

    assert exc.value.code == "LLM_CONFIG_ERROR"
    assert LLM_CONFIG_PATH_ENV in exc.value.message


def test_load_llm_registry_config_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(LlmConfigError) as exc:
        load_llm_registry_config(tmp_path / "missing.yaml")

    assert exc.value.code == "LLM_CONFIG_ERROR"


def test_load_llm_registry_config_raises_for_yaml_syntax_error(tmp_path: Path) -> None:
    config_path = tmp_path / "llm.yaml"
    config_path.write_text("clients: [", encoding="utf-8")

    with pytest.raises(LlmConfigError) as exc:
        load_llm_registry_config(config_path)

    assert exc.value.code == "LLM_CONFIG_ERROR"


def test_load_llm_registry_config_raises_when_root_is_not_mapping(tmp_path: Path) -> None:
    config_path = tmp_path / "llm.yaml"
    config_path.write_text("- not-a-mapping", encoding="utf-8")

    with pytest.raises(LlmConfigError) as exc:
        load_llm_registry_config(config_path)

    assert exc.value.message == "LLM config root must be a mapping"


def test_load_llm_registry_config_wraps_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "llm.yaml"
    config_path.write_text(
        """
clients:
  - client_id: ""
    provider: fake
    model_name: fake-model
""",
        encoding="utf-8",
    )

    with pytest.raises(LlmConfigError) as exc:
        load_llm_registry_config(config_path)

    assert exc.value.message == "Invalid LLM registry config"
    assert exc.value.__cause__ is not None
