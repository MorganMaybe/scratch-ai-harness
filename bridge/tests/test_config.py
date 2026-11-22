from __future__ import annotations

import pytest

from harness.config import (
    BUILTIN_PROFILES,
    ConfigError,
    ModelConfig,
    default_config_path,
    read_ini,
    resolve_config,
)


def test_default_profile_is_opencode_go(tmp_path):
    config = resolve_config(config_path=tmp_path / "missing.ini", env={})
    assert config.profile == "opencode-go"
    assert config.base_url == "https://opencode.ai/inference/go/openai/v1"
    assert config.model == "deepseek-v4.1-flash"
    # The old hardcoded fallback must be gone.
    assert "deepseek-flash" != config.model
    assert "api.deepseek.com" not in config.base_url


@pytest.mark.parametrize(
    ("profile", "base_url", "model"),
    [
        ("opencode-go", "https://opencode.ai/inference/go/openai/v1", "deepseek-v4.1-flash"),
        ("deepseek-direct", "https://api.deepseek.com", "deepseek-chat"),
        ("local", "http://127.0.0.1:11434/v1", "qwen2.5-coder"),
    ],
)
def test_builtin_profiles_resolve(profile, base_url, model, tmp_path):
    config = resolve_config(profile, config_path=tmp_path / "missing.ini", env={})
    assert (config.base_url, config.model) == (base_url, model)


def test_mock_profile_needs_no_key(tmp_path):
    config = resolve_config("mock", config_path=tmp_path / "missing.ini", env={})
    assert config.is_mock
    assert config.has_api_key(env={}) is False


def test_unknown_profile_is_one_clear_error(tmp_path):
    with pytest.raises(ConfigError) as excinfo:
        resolve_config("nope", config_path=tmp_path / "missing.ini", env={})
    message = str(excinfo.value)
    assert "unknown profile 'nope'" in message
    assert "opencode-go" in message


def test_ini_supplies_default_and_overrides(tmp_path):
    ini = tmp_path / "harness.ini"
    ini.write_text(
        "[model]\n"
        "default=work\n"
        "\n"
        "[profile:work]\n"
        "base_url=https://example.invalid/v1\n"
        "model=local-model\n"
        "api_key_env=WORK_KEY\n"
        "timeout=12\n"
        "retries=1\n",
        encoding="utf-8",
    )
    config = resolve_config(None, config_path=ini, env={})
    assert config.profile == "work"
    assert config.base_url == "https://example.invalid/v1"
    assert config.model == "local-model"
    assert config.api_key_env == "WORK_KEY"
    assert config.timeout_s == 12
    assert config.max_retries == 1


def test_ini_can_extend_a_builtin_profile(tmp_path):
    ini = tmp_path / "harness.ini"
    ini.write_text("[profile:opencode-go]\nmodel=deepseek-v4.1-flash-alt\n", encoding="utf-8")
    config = resolve_config(None, config_path=ini, env={})
    assert config.model == "deepseek-v4.1-flash-alt"
    # Unspecified keys still come from the built-in profile.
    assert config.base_url == BUILTIN_PROFILES["opencode-go"]["base_url"]


def test_precedence_cli_over_env_over_ini(tmp_path):
    ini = tmp_path / "harness.ini"
    ini.write_text(
        "[profile:opencode-go]\nmodel=from-ini\nbase_url=https://ini.invalid/v1\n",
        encoding="utf-8",
    )
    env = {"DEEPSEEK_MODEL": "from-env", "DEEPSEEK_BASE_URL": "https://env.invalid/v1"}
    config = resolve_config("opencode-go", config_path=ini, env=env)
    assert config.model == "from-env"
    assert config.base_url == "https://env.invalid/v1"

    config = resolve_config(
        "opencode-go",
        config_path=ini,
        env=env,
        model="from-cli",
        base_url="https://cli.invalid/v1",
        timeout=7,
        retries=0,
    )
    assert config.model == "from-cli"
    assert config.base_url == "https://cli.invalid/v1"
    assert config.timeout_s == 7
    assert config.max_retries == 0


def test_env_profile_selects_profile(tmp_path):
    config = resolve_config(None, config_path=tmp_path / "missing.ini", env={"HARNESS_PROFILE": "deepseek-direct"})
    assert config.profile == "deepseek-direct"


def test_missing_key_is_clear_and_secret_free(tmp_path):
    config = resolve_config("opencode-go", config_path=tmp_path / "missing.ini", env={})
    assert config.has_api_key(env={}) is False
    with pytest.raises(ConfigError) as excinfo:
        config.api_key(env={})
    message = str(excinfo.value)
    assert "DEEPSEEK_API_KEY is not set" in message
    assert "bridge/.deepseek_key" in message
    assert "oc_sk_" not in message


def test_api_key_reads_environment(tmp_path):
    config = resolve_config("opencode-go", config_path=tmp_path / "missing.ini", env={})
    assert config.api_key(env={"DEEPSEEK_API_KEY": " test-key "}) == "test-key"


def test_describe_never_contains_the_key(tmp_path):
    config = resolve_config("opencode-go", config_path=tmp_path / "missing.ini", env={})
    text = config.describe()
    assert "profile=opencode-go" in text
    assert "deepseek-v4.1-flash" in text
    assert "key" not in text.lower()


def test_read_ini_missing_file(tmp_path):
    assert read_ini(tmp_path / "absent.ini") == (None, {})


def test_bad_numeric_value_is_a_config_error(tmp_path):
    ini = tmp_path / "harness.ini"
    ini.write_text("[profile:work]\nbase_url=https://x.invalid/v1\nmodel=m\ntimeout=soon\n", encoding="utf-8")
    with pytest.raises(ConfigError) as excinfo:
        resolve_config("work", config_path=ini, env={})
    assert "timeout must be a number" in str(excinfo.value)


def test_default_config_path_points_at_bridge_root():
    assert default_config_path().name == "harness.ini"
    assert default_config_path().parent.name == "bridge"


def test_model_config_is_frozen():
    config = ModelConfig(profile="p", base_url="u", model="m")
    with pytest.raises(Exception):
        config.model = "other"  # type: ignore[misc]
