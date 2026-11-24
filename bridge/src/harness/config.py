"""Model configuration: profiles from ``harness.ini``, environment, and CLI.

Resolution order (later wins)::

    built-in defaults  <  bridge/harness.ini  <  environment  <  CLI arguments

The file holds no secret. It only names the environment variable that holds the
key, so the key can never end up in a config file, the image, or a log line.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

DEFAULT_PROFILE = "opencode-go"

#: Reply formats the model may be asked to produce.  ``json`` is the original
#: contract; ``dsl`` asks for one Scratch-Python module that the bridge
#: transpiles into the same change set.
GENERATORS = ("json", "dsl")

#: Models offered by the in-image Usage switcher, in bridge order (the image
#: selects a model by 1-based index).  They share one profile and endpoint; a
#: switch changes only the model id.  Keep labels short enough for the rail.
MODEL_CHOICES: tuple[tuple[str, str], ...] = (
    ("deepseek-v4.1-flash", "DeepSeek"),
    ("hy4-flash-free", "HY4 Flash Free"),
)

#: Profiles whose gateway knows every :data:`MODEL_CHOICES` id.
MODEL_CHOICE_PROFILES = frozenset({"opencode-go"})

#: Safe defaults. ``opencode-go`` is the verified live path; the old
#: ``api.deepseek.com`` / ``deepseek-flash`` fallback was simply wrong.
BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "opencode-go": {
        "base_url": "https://opencode.ai/inference/go/openai/v1",
        "model": "deepseek-v4.1-flash",
        "api_key_env": "DEEPSEEK_API_KEY",
        # Large scenes need output headroom even with reasoning disabled.  The
        # cap does not slow normal turns; it only prevents a truncated JSON
        # reply from being retried at the same limit.
        "timeout": "120",
        "retries": "2",
        "max_tokens": "16384",
        "thinking": "off",
    },
    "deepseek-direct": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "timeout": "90",
        "retries": "2",
        "thinking": "off",
    },
    "local": {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5-coder",
        "api_key_env": "LOCAL_API_KEY",
        "timeout": "120",
        "retries": "0",
        "thinking": "off",
    },
    "mock": {
        "base_url": "",
        "model": "mock",
        "api_key_env": "",
        "timeout": "5",
        "retries": "0",
        "thinking": "off",
    },
}

_INI_KEYS = {
    "base_url": "base_url",
    "model": "model",
    "api_key_env": "api_key_env",
    "timeout": "timeout",
    "retries": "retries",
    "temperature": "temperature",
    "max_tokens": "max_tokens",
    "thinking": "thinking",
    "session_id": "session_id",
}


class ConfigError(RuntimeError):
    """Bad configuration: unknown profile, unreadable ini, bad value."""


@dataclass(frozen=True)
class ModelConfig:
    profile: str
    base_url: str
    model: str
    api_key_env: str = "DEEPSEEK_API_KEY"
    timeout_s: float = 90.0
    max_retries: int = 2
    temperature: float = 0.2
    max_tokens: int = 8192
    thinking: str = "off"
    session_id: str = "scratch-ai-harness"

    @property
    def is_mock(self) -> bool:
        return self.profile == "mock"

    def api_key(self, env: Mapping[str, str] | None = None) -> str:
        """Return the key from the environment, or raise one clear error."""
        env = os.environ if env is None else env
        if not self.api_key_env:
            raise ConfigError(f"profile '{self.profile}' does not use an API key")
        value = (env.get(self.api_key_env) or "").strip()
        if not value:
            raise ConfigError(
                f"{self.api_key_env} is not set for profile '{self.profile}'. "
                f"Put the key in bridge/.deepseek_key (run_live.ps1 loads it) "
                f"or export {self.api_key_env}."
            )
        return value

    def has_api_key(self, env: Mapping[str, str] | None = None) -> bool:
        env = os.environ if env is None else env
        return bool(self.api_key_env and (env.get(self.api_key_env) or "").strip())

    def describe(self) -> str:
        """One line for the launcher and bridge-status: never includes the key."""
        if self.is_mock:
            return "profile=mock (offline)"
        return (
            f"profile={self.profile} model={self.model} base_url={self.base_url} "
            f"timeout={self.timeout_s:g}s retries={self.max_retries}"
        )


def default_config_path() -> Path:
    """``bridge/harness.ini`` next to the package, unless HARNESS_CONFIG says otherwise."""
    override = os.environ.get("HARNESS_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "harness.ini"


def _coerce_float(key: str, value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{key} must be a number, got {value!r}") from exc


def _coerce_int(key: str, value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{key} must be an integer, got {value!r}") from exc


def read_ini(path: Path | None) -> tuple[str | None, dict[str, dict[str, str]]]:
    """Return ``(default_profile, {profile: values})``; missing file is not an error."""
    if path is None or not Path(path).exists():
        return None, {}
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # keep key spelling
    try:
        with open(path, encoding="utf-8-sig") as handle:
            parser.read_file(handle)
    except (OSError, configparser.Error) as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc

    default: str | None = None
    if parser.has_section("model"):
        default = (parser.get("model", "default", fallback="") or "").strip() or None

    profiles: dict[str, dict[str, str]] = {}
    for section in parser.sections():
        if not section.startswith("profile:"):
            continue
        name = section.split(":", 1)[1].strip()
        values = {
            key: (parser.get(section, key) or "").strip()
            for key in _INI_KEYS
            if parser.has_option(section, key)
        }
        if values:
            profiles[name] = values
    return default, profiles


def _read_harness_option(path: Path | None, key: str) -> str | None:
    """Read one ``[harness]`` option without touching :func:`read_ini`.

    A missing file or section is not an error; a file that exists but cannot be
    parsed is, matching ``read_ini``'s behaviour.
    """
    if path is None or not Path(path).exists():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with open(path, encoding="utf-8-sig") as handle:
            parser.read_file(handle)
    except (OSError, configparser.Error) as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc
    if not parser.has_section("harness"):
        return None
    value = (parser.get("harness", key, fallback="") or "").strip()
    return value or None


def _read_harness_generator(path: Path | None) -> str | None:
    return _read_harness_option(path, "generator")


def resolve_generator(
    config_path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """HARNESS_GENERATOR env > harness.ini [harness] generator > 'json'."""
    env = os.environ if env is None else env
    raw_env = (env.get("HARNESS_GENERATOR") or "").strip()
    if raw_env:
        value = raw_env.lower()
        if value not in GENERATORS:
            raise ConfigError("generator must be one of: json, dsl")
        return value
    path = Path(config_path) if config_path is not None else default_config_path()
    raw_ini = _read_harness_generator(path)
    if raw_ini:
        value = raw_ini.lower()
        if value not in GENERATORS:
            raise ConfigError("generator must be one of: json, dsl")
        return value
    return "json"


def _parse_history(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered == "on":
        return True
    if lowered == "off":
        return False
    raise ConfigError("history must be one of: on, off")


def resolve_history(
    config_path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """HARNESS_HISTORY env > harness.ini [harness] history > on.

    With history off, prompts are byte-identical to the pre-history bridge:
    nothing is recorded and no section is rendered.
    """
    env = os.environ if env is None else env
    raw_env = (env.get("HARNESS_HISTORY") or "").strip()
    if raw_env:
        return _parse_history(raw_env)
    path = Path(config_path) if config_path is not None else default_config_path()
    raw_ini = _read_harness_option(path, "history")
    if raw_ini:
        return _parse_history(raw_ini)
    return True


def _parse_stop_sequence(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in ("on", "true", "1"):
        return True
    if lowered in ("off", "false", "0"):
        return False
    raise ConfigError("stop_sequence must be one of: on, true, 1, off, false, 0")


def resolve_stop_sequence(
    config_path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """HARNESS_STOP_SEQUENCE env > harness.ini [harness] stop_sequence > off.

    The stop sequence is the DSL reply's newline plus closing fence, so the
    model cannot append anything after the module.  Off by default: the
    provider derives it for DSL replies only, and flipping it on waits for a
    live ladder A/B showing it is honoured without hurting prompt caching.
    """
    env = os.environ if env is None else env
    raw_env = (env.get("HARNESS_STOP_SEQUENCE") or "").strip()
    if raw_env:
        return _parse_stop_sequence(raw_env)
    path = Path(config_path) if config_path is not None else default_config_path()
    raw_ini = _read_harness_option(path, "stop_sequence")
    if raw_ini:
        return _parse_stop_sequence(raw_ini)
    return False


def resolve_config(
    profile: str | None = None,
    config_path: str | Path | None = None,
    *,
    model: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    retries: int | None = None,
    env: Mapping[str, str] | None = None,
) -> ModelConfig:
    """Resolve one ``ModelConfig``. Never reads or returns the API key value."""
    env = os.environ if env is None else env
    ini_default, ini_profiles = read_ini(
        Path(config_path) if config_path is not None else default_config_path()
    )

    name = (profile or env.get("HARNESS_PROFILE") or ini_default or DEFAULT_PROFILE).strip()
    known = sorted(set(BUILTIN_PROFILES) | set(ini_profiles))
    if name not in BUILTIN_PROFILES and name not in ini_profiles:
        raise ConfigError(
            f"unknown profile '{name}'. Known profiles: {', '.join(known)}. "
            f"Add [profile:{name}] to bridge/harness.ini or rename it."
        )

    values: dict[str, Any] = dict(BUILTIN_PROFILES.get(name, {}))
    values.update(ini_profiles.get(name, {}))

    # Environment overrides (kept for one release; run_live.ps1 used these).
    if env.get("DEEPSEEK_MODEL"):
        values["model"] = env["DEEPSEEK_MODEL"]
    if env.get("DEEPSEEK_BASE_URL"):
        values["base_url"] = env["DEEPSEEK_BASE_URL"]
    if env.get("DEEPSEEK_TIMEOUT"):
        values["timeout"] = env["DEEPSEEK_TIMEOUT"]
    if env.get("DEEPSEEK_RETRIES"):
        values["retries"] = env["DEEPSEEK_RETRIES"]
    if env.get("DEEPSEEK_SESSION"):
        values["session_id"] = env["DEEPSEEK_SESSION"]

    # CLI wins.
    if model:
        values["model"] = model
    if base_url:
        values["base_url"] = base_url
    if timeout is not None:
        values["timeout"] = timeout
    if retries is not None:
        values["retries"] = retries

    resolved = ModelConfig(
        profile=name,
        base_url=str(values.get("base_url") or ""),
        model=str(values.get("model") or ""),
        api_key_env=str(values.get("api_key_env") or "DEEPSEEK_API_KEY"),
        timeout_s=_coerce_float("timeout", values.get("timeout", 90)),
        max_retries=_coerce_int("retries", values.get("retries", 2)),
        temperature=_coerce_float("temperature", values.get("temperature", 0.2)),
        max_tokens=_coerce_int("max_tokens", values.get("max_tokens", 8192)),
        thinking=str(values.get("thinking") or "off"),
        session_id=str(values.get("session_id") or "scratch-ai-harness"),
    )

    if not resolved.is_mock and (not resolved.base_url or not resolved.model):
        raise ConfigError(f"profile '{name}' needs both base_url and model")
    if resolved.max_retries < 0:
        raise ConfigError("retries must be >= 0")
    if resolved.timeout_s <= 0:
        raise ConfigError("timeout must be > 0")
    return resolved


def with_overrides(config: ModelConfig, **changes: Any) -> ModelConfig:
    """Small helper for tests and callers that tweak a resolved config."""
    return replace(config, **changes)
