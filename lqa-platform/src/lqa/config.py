# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
ENV_PATH = BASE / ".env"

VALID_PROVIDERS = ("deepseek", "openai", "mimo", "custom")

# 记录本进程内由 load_env_file 写入过进程环境的键。
# 重载 .env 时，这些键以文件最新值为准（支持密钥轮换）；
# 非本函数写入的键（如 shell 导出）不被覆盖，保持「环境变量优先」语义。
_ENV_KEYS_WRITTEN: set[str] = set()


def load_env_file(path: Path = ENV_PATH) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and (k not in os.environ or k in _ENV_KEYS_WRITTEN):
            os.environ[k] = v
            _ENV_KEYS_WRITTEN.add(k)


@dataclass
class Settings:
    provider: str
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.2
    timeout_s: float = 120.0

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def masked_key(self) -> str:
        k = self.api_key
        if not k:
            return ""
        if len(k) <= 12:
            return "已配置"
        return f"{k[:4]}…{k[-4:]}"

    def public_dict(self) -> dict:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "has_api_key": self.has_key,
            "api_key_masked": self.masked_key(),
            "temperature": self.temperature,
        }


def _default_for(provider: str) -> tuple[str, str]:
    p = provider.lower()
    if p == "openai":
        return "https://api.openai.com/v1", os.getenv("OPENAI_API_KEY") or ""
    if p == "mimo":
        return (
            os.getenv("MIMO_BASE_URL") or "https://api.mimo.com/v1",
            os.getenv("MIMO_API_KEY") or "",
        )
    if p == "custom":
        return (
            os.getenv("CUSTOM_BASE_URL") or "http://127.0.0.1:11434/v1",
            os.getenv("CUSTOM_API_KEY") or "ollama",
        )
    return "https://api.deepseek.com/v1", os.getenv("DEEPSEEK_API_KEY") or ""


def load_settings(
    *,
    provider: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> Settings:
    load_env_file()
    prov = (provider or os.getenv("LQA_PROVIDER") or "deepseek").lower()
    if prov not in VALID_PROVIDERS:
        prov = "deepseek"
    def_base, def_key = _default_for(prov)
    base = (base_url or os.getenv("LQA_BASE_URL") or def_base).rstrip("/")
    key = (api_key or os.getenv("LQA_API_KEY") or def_key or "").strip()
    if prov == "mimo":
        default_model = "mimo-v2.5"
    elif prov == "openai":
        default_model = "gpt-4o-mini"
    elif prov == "custom":
        default_model = "qwen2.5"
    else:
        default_model = "deepseek-chat"
    mdl = model or os.getenv("LQA_MODEL") or default_model
    return Settings(
        provider=prov,
        base_url=base,
        api_key=key,
        model=mdl,
        temperature=float(os.getenv("LQA_TEMPERATURE", "0.2")),
        timeout_s=float(os.getenv("LQA_TIMEOUT_S", "120")),
    )
