from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from .config import AppConfig
from .llm_provider import LlmClient
from .metadata import MetadataError, parse_json_object

class AgentPlanningError(RuntimeError):
    pass

@dataclass(frozen=True)
class VideoPlan:
    idea: str
    video_language: str
    voice_name: str
    voice_volume: float
    voice_rate: float
    bgm_type: str
    bgm_file: str
    bgm_volume: float
    subtitle_position: str
    custom_position: float
    font_name: str
    text_fore_color: str
    text_background_color: bool | str
    font_size: int
    stroke_color: str
    stroke_width: float
    tiktok_username: str
    verification_questions: list[str]
    rationale: str = ""

    def video_options(self) -> dict[str, Any]:
        return {
            "voice_volume": self.voice_volume,
            "voice_rate": self.voice_rate,
            "bgm_type": self.bgm_type,
            "bgm_file": self.bgm_file,
            "bgm_volume": self.bgm_volume,
            "subtitle_position": self.subtitle_position,
            "custom_position": self.custom_position,
            "font_name": self.font_name,
            "text_fore_color": self.text_fore_color,
            "text_background_color": self.text_background_color,
            "font_size": self.font_size,
            "stroke_color": self.stroke_color,
            "stroke_width": self.stroke_width,
        }

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

class AgentPlanner:
    def __init__(self, config: AppConfig, llm: LlmClient):
        self.config = config
        self.llm = llm

    def plan(self, prompt: str, *, available_accounts: list[str], requested_account: str = "") -> VideoPlan:
        raw_prompt = self._build_prompt(prompt, available_accounts, requested_account)
        try:
            data = parse_json_object(self.llm.complete(raw_prompt))
        except MetadataError as exc:
            raise AgentPlanningError(f"Could not create agent video plan: {exc}") from exc
        return self._coerce_plan(data, prompt, available_accounts, requested_account)

    def _build_prompt(self, prompt: str, available_accounts: list[str], requested_account: str) -> str:
        defaults = {
            "video_language": self.config.default_video_language,
            "voice_name": self.config.default_voice_name,
            "voice_volume": self.config.default_voice_volume,
            "voice_rate": self.config.default_voice_rate,
            "bgm_type": self.config.default_bgm_type,
            "bgm_file": self.config.default_bgm_file,
            "bgm_volume": self.config.default_bgm_volume,
            "subtitle_position": self.config.default_subtitle_position,
            "custom_position": self.config.default_custom_position,
            "font_name": self.config.default_font_name,
            "text_fore_color": self.config.default_text_fore_color,
            "text_background_color": self.config.default_text_background_color,
            "font_size": self.config.default_font_size,
            "stroke_color": self.config.default_stroke_color,
            "stroke_width": self.config.default_stroke_width,
        }
        return f"""
You are an autonomous short-video production agent. Convert the user's prompt into the best execution plan for a TikTok short generated with MoneyPrinterTurbo.
User prompt: {prompt}
Available TikTok accounts: {json.dumps(available_accounts, ensure_ascii=False)}
Requested account, if any: {requested_account or "(none)"}
Current safe defaults: {json.dumps(defaults, ensure_ascii=False)}

Rules:
- Pick a concrete, stock-footage-friendly video idea.
- Pick a suitable language and voice_name. Use the default voice if unsure.
- Pick readable subtitle styling for TikTok mobile video.
- Pick bgm_type "random" unless a specific local bgm_file from the user's environment is clearly needed.
- If an available/requested TikTok account is suitable, set tiktok_username to that exact username; otherwise use an empty string.
- Include 3 short verification questions the user must answer before uploading.
- Return strict JSON only with exactly these keys:
{{"idea":"...","video_language":"...","voice_name":"...","voice_volume":1.0,"voice_rate":1.0,"bgm_type":"random","bgm_file":"","bgm_volume":0.2,"subtitle_position":"bottom","custom_position":70.0,"font_name":"","text_fore_color":"#FFFFFF","text_background_color":true,"font_size":60,"stroke_color":"#000000","stroke_width":1.5,"tiktok_username":"","verification_questions":["..."],"rationale":"..."}}
""".strip()

    def _coerce_plan(
        self,
        data: dict[str, Any],
        original_prompt: str,
        available_accounts: list[str],
        requested_account: str,
    ) -> VideoPlan:
        username = str(data.get("tiktok_username") or requested_account or self.config.default_tiktok_username or "").strip()
        if username and available_accounts and username not in available_accounts:
            username = requested_account if requested_account in available_accounts else ""
        questions = data.get("verification_questions")
        if not isinstance(questions, list):
            questions = []
        questions = [str(item).strip() for item in questions if str(item).strip()][:5]
        if not questions:
            questions = default_upload_questions()
        return VideoPlan(
            idea=str(data.get("idea") or original_prompt).strip(),
            video_language=str(data.get("video_language") or self.config.default_video_language).strip(),
            voice_name=str(data.get("voice_name") or self.config.default_voice_name).strip(),
            voice_volume=clamp_float(data.get("voice_volume"), self.config.default_voice_volume, 0.1, 2.0),
            voice_rate=clamp_float(data.get("voice_rate"), self.config.default_voice_rate, 0.5, 2.0),
            bgm_type=coerce_bgm_type(data.get("bgm_type"), self.config.default_bgm_type),
            bgm_file=str(data.get("bgm_file") or self.config.default_bgm_file or "").strip(),
            bgm_volume=clamp_float(data.get("bgm_volume"), self.config.default_bgm_volume, 0.0, 1.0),
            subtitle_position=coerce_subtitle_position(data.get("subtitle_position"), self.config.default_subtitle_position),
            custom_position=clamp_float(data.get("custom_position"), self.config.default_custom_position, 0.0, 100.0),
            font_name=str(data.get("font_name") or self.config.default_font_name or "").strip(),
            text_fore_color=str(data.get("text_fore_color") or self.config.default_text_fore_color).strip(),
            text_background_color=data.get("text_background_color", self.config.default_text_background_color),
            font_size=clamp_int(data.get("font_size"), self.config.default_font_size, 24, 120),
            stroke_color=str(data.get("stroke_color") or self.config.default_stroke_color).strip(),
            stroke_width=clamp_float(data.get("stroke_width"), self.config.default_stroke_width, 0.0, 8.0),
            tiktok_username=username,
            verification_questions=questions,
            rationale=str(data.get("rationale") or "").strip(),
        )

def default_upload_questions() -> list[str]:
    return [
        "Is this the correct TikTok account?",
        "Are the title, caption, and hashtags ready to publish?",
        "Have you reviewed the generated video and confirmed it is safe to upload?",
    ]

def clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    return max(minimum, min(maximum, number))

def clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(default)
    return max(minimum, min(maximum, number))

def coerce_subtitle_position(value: Any, default: str) -> str:
    position = str(value or default or "bottom").strip().lower()
    return position if position in {"top", "center", "bottom", "custom"} else "bottom"

def coerce_bgm_type(value: Any, default: str) -> str:
    bgm_type = str(value or default or "random").strip().lower()
    return bgm_type if bgm_type in {"random", "custom", "none"} else "random"
