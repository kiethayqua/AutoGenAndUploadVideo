from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol

from .config import AppConfig
from .metadata import MetadataError, MoneyPrinterLlm

class LlmClient(Protocol):
    def complete(self, prompt: str, timeout: int = 180) -> str:
        ...

class ProviderLlm:
    def __init__(self, config: AppConfig):
        self.config = config
        self.provider = config.llm_provider.strip().lower()

    def complete(self, prompt: str, timeout: int = 180) -> str:
        if self.provider in {"openai", "codex"}:
            return self._openai_complete(prompt, timeout)
        if self.provider in {"anthropic", "claude"}:
            return self._anthropic_complete(prompt, timeout)
        if self.provider == "gemini":
            return self._gemini_complete(prompt, timeout)
        raise MetadataError(f"Unsupported LLM provider: {self.config.llm_provider}")

    def _openai_complete(self, prompt: str, timeout: int) -> str:
        base = (self.config.llm_api_base or "https://api.openai.com/v1").rstrip("/")
        model = self.config.llm_model or "gpt-4o-mini"
        data = self._post_json(
            f"{base}/chat/completions",
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Return concise, valid outputs exactly as requested."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
            },
            {"Authorization": f"Bearer {self._api_key('OPENAI_API_KEY')}"},
            timeout,
        )
        return str(data["choices"][0]["message"]["content"]).strip()

    def _anthropic_complete(self, prompt: str, timeout: int) -> str:
        base = (self.config.llm_api_base or "https://api.anthropic.com/v1").rstrip("/")
        model = self.config.llm_model or "claude-3-5-haiku-latest"
        data = self._post_json(
            f"{base}/messages",
            {
                "model": model,
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            },
            {
                "x-api-key": self._api_key("ANTHROPIC_API_KEY"),
                "anthropic-version": "2023-06-01",
            },
            timeout,
        )
        chunks = data.get("content", [])
        text = "".join(str(chunk.get("text", "")) for chunk in chunks if isinstance(chunk, dict))
        return text.strip()

    def _gemini_complete(self, prompt: str, timeout: int) -> str:
        model = self.config.llm_model or "gemini-1.5-flash"
        base = (self.config.llm_api_base or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        url = f"{base}/models/{model}:generateContent?key={self._api_key('GEMINI_API_KEY')}"
        data = self._post_json(
            url,
            {"contents": [{"parts": [{"text": prompt}]}]},
            {},
            timeout,
        )
        candidates = data.get("candidates", [])
        if not candidates:
            raise MetadataError(f"Gemini returned no candidates: {data}")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict)).strip()

    def _api_key(self, default_env: str) -> str:
        env_name = self.config.llm_api_key_env or default_env
        value = os.getenv(env_name, "").strip()
        if not value:
            raise MetadataError(f"Missing API key environment variable: {env_name}")
        return value

    @staticmethod
    def _post_json(url: str, payload: dict, headers: dict[str, str], timeout: int) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MetadataError(f"LLM provider request failed: HTTP {exc.code}: {detail[-1200:]}") from exc
        except urllib.error.URLError as exc:
            raise MetadataError(f"LLM provider request failed: {exc}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MetadataError(f"LLM provider returned invalid JSON: {raw[:500]}") from exc
        return data if isinstance(data, dict) else {"value": data}

def create_llm_client(config: AppConfig) -> LlmClient:
    provider = config.llm_provider.strip().lower()
    if provider in {"", "moneyprinter"}:
        return MoneyPrinterLlm(config)
    return ProviderLlm(config)
