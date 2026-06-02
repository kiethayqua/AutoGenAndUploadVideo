from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class AppConfig:
    root_dir: Path = ROOT_DIR
    moneyprinter_repo: Path = ROOT_DIR / "MoneyPrinterTurbo"
    tiktok_repo: Path = ROOT_DIR / "TiktokAutoUploader"
    moneyprinter_api_base: str = "http://127.0.0.1:8080/api/v1"
    moneyprinter_runner: tuple[str, ...] = ("uv", "run", "python")
    auto_start_moneyprinter_api: bool = True
    moneyprinter_startup_timeout_seconds: int = 120
    state_db: Path = ROOT_DIR / "auto_tiktok_orchestrator" / "state" / "orchestrator.db"
    poll_interval_seconds: int = 10
    task_timeout_seconds: int = 3600
    caption_limit: int = 2200
    max_hashtags: int = 12
    llm_provider: str = "moneyprinter"
    llm_model: str = ""
    llm_api_key_env: str = ""
    llm_api_base: str = ""
    default_video_source: str = "pexels"
    default_video_aspect: str = "9:16"
    default_paragraph_number: int = 1
    default_video_language: str = "English"
    default_voice_name: str = "en-US-JennyNeural-Female"
    default_voice_volume: float = 1.0
    default_voice_rate: float = 1.0
    default_bgm_type: str = "random"
    default_bgm_file: str = ""
    default_bgm_volume: float = 0.2
    default_subtitle_position: str = "custom"
    default_custom_position: float = 50.0
    default_font_name: str = ""
    default_text_fore_color: str = "#FFFFFF"
    default_text_background_color: bool | str = True
    default_font_size: int = 60
    default_stroke_color: str = "#000000"
    default_stroke_width: float = 1.5
    default_intro_video_file: str = ""
    default_outro_video_file: str = "tubeshad-outro.mp4"
    tiktok_accounts: tuple[str, ...] = ()
    default_tiktok_username: str = ""

    @classmethod
    def load(cls, path: str | Path | None = None) -> "AppConfig":
        cfg = cls(
            moneyprinter_api_base=os.getenv("MONEYPRINTER_API_BASE", cls.moneyprinter_api_base),
            moneyprinter_runner=tuple(shlex.split(os.getenv("MONEYPRINTER_RUNNER", "uv run python"))),
            llm_provider=os.getenv("AUTO_TIKTOK_LLM_PROVIDER", cls.llm_provider),
            llm_model=os.getenv("AUTO_TIKTOK_LLM_MODEL", cls.llm_model),
            llm_api_key_env=os.getenv("AUTO_TIKTOK_LLM_API_KEY_ENV", cls.llm_api_key_env),
            llm_api_base=os.getenv("AUTO_TIKTOK_LLM_API_BASE", cls.llm_api_base),
        )
        if not path:
            return cfg
        with Path(path).expanduser().resolve().open("r", encoding="utf-8") as f:
            raw = json.load(f)
        values: dict[str, Any] = {}
        for key, value in raw.items():
            if not hasattr(cfg, key):
                raise ValueError(f"Unknown config key: {key}")
            current = getattr(cfg, key)
            if isinstance(current, Path):
                values[key] = Path(value).expanduser().resolve()
            elif key == "moneyprinter_runner":
                values[key] = tuple(value) if isinstance(value, list) else tuple(shlex.split(str(value)))
            elif isinstance(current, tuple):
                values[key] = tuple(value) if isinstance(value, list) else tuple(part.strip() for part in str(value).split(",") if part.strip())
            else:
                values[key] = value
        return replace(cfg, **values)
