from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .config import AppConfig

class MoneyPrinterError(RuntimeError):
    pass

class MoneyPrinterClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self.base = config.moneyprinter_api_base.rstrip("/")

    def is_server_available(self) -> bool:
        parsed = urllib.parse.urlparse(self.base)
        if not parsed.scheme or not parsed.netloc:
            return False
        url = f"{parsed.scheme}://{parsed.netloc}/docs"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return 200 <= int(resp.status) < 500
        except urllib.error.URLError:
            return False

    def generate_script(self, idea: str, language: str = "", paragraph_number: int = 1) -> str:
        data = self._post(
            "/scripts",
            {
                "video_subject": idea,
                "video_language": language,
                "paragraph_number": paragraph_number,
            },
        )
        script = data.get("video_script", "").strip()
        if not script:
            raise MoneyPrinterError("MoneyPrinterTurbo returned an empty script")
        return script

    def generate_terms(self, idea: str, script: str, amount: int = 5) -> list[str]:
        data = self._post(
            "/terms",
            {"video_subject": idea, "video_script": script, "amount": amount},
        )
        terms = data.get("video_terms") or []
        if isinstance(terms, str):
            return [terms]
        return [str(term) for term in terms]

    def create_video(
        self,
        *,
        idea: str,
        script: str,
        terms: list[str],
        video_source: str,
        video_aspect: str,
        language: str,
        voice_name: str,
        paragraph_number: int,
        voice_volume: float | None = None,
        voice_rate: float | None = None,
        bgm_type: str | None = None,
        bgm_file: str | None = None,
        bgm_volume: float | None = None,
        subtitle_position: str | None = None,
        custom_position: float | None = None,
        font_name: str | None = None,
        text_fore_color: str | None = None,
        text_background_color: bool | str | None = None,
        font_size: int | None = None,
        stroke_color: str | None = None,
        stroke_width: float | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "video_subject": idea,
            "video_script": script,
            "video_terms": terms,
            "video_aspect": video_aspect,
            "video_source": video_source,
            "video_language": language,
            "voice_name": voice_name,
            "paragraph_number": paragraph_number,
            "subtitle_enabled": True,
            "voice_volume": self.config.default_voice_volume if voice_volume is None else voice_volume,
            "voice_rate": self.config.default_voice_rate if voice_rate is None else voice_rate,
            "bgm_type": bgm_type or self.config.default_bgm_type,
            "bgm_file": self.config.default_bgm_file if bgm_file is None else bgm_file,
            "bgm_volume": self.config.default_bgm_volume if bgm_volume is None else bgm_volume,
            "subtitle_position": subtitle_position or self.config.default_subtitle_position,
            "custom_position": self.config.default_custom_position if custom_position is None else custom_position,
            "text_fore_color": text_fore_color or self.config.default_text_fore_color,
            "text_background_color": self.config.default_text_background_color if text_background_color is None else text_background_color,
            "font_size": self.config.default_font_size if font_size is None else font_size,
            "stroke_color": stroke_color or self.config.default_stroke_color,
            "stroke_width": self.config.default_stroke_width if stroke_width is None else stroke_width,
        }
        selected_font = font_name if font_name is not None else self.config.default_font_name
        if selected_font:
            payload["font_name"] = selected_font
        data = self._post("/videos", payload)
        task_id = data.get("task_id")
        if not task_id:
            raise MoneyPrinterError(f"MoneyPrinterTurbo did not return task_id: {data}")
        return str(task_id)

    def wait_for_video(self, task_id: str) -> dict[str, Any]:
        deadline = time.time() + self.config.task_timeout_seconds
        last: dict[str, Any] = {}
        while time.time() < deadline:
            last = self.get_task(task_id)
            state = int(last.get("state", 0) or 0)
            progress = int(last.get("progress", 0) or 0)
            if state < 0:
                raise MoneyPrinterError(f"MoneyPrinterTurbo task failed: {last}")
            if progress >= 100 and (last.get("videos") or last.get("combined_videos")):
                return last
            time.sleep(self.config.poll_interval_seconds)
        raise MoneyPrinterError(f"Timed out waiting for MoneyPrinterTurbo task {task_id}: {last}")

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._get(f"/tasks/{urllib.parse.quote(task_id)}")

    def resolve_video_path(self, task: dict[str, Any]) -> Path:
        videos = task.get("videos") or task.get("combined_videos") or []
        if not videos:
            raise MoneyPrinterError(f"Task has no video output: {task}")
        first = str(videos[0])
        parsed = urllib.parse.urlparse(first)
        path = parsed.path if parsed.scheme else first
        marker = "/tasks/"
        if marker in path:
            rel = path.split(marker, 1)[1]
            candidate = self.config.moneyprinter_repo / "storage" / "tasks" / rel
        else:
            candidate = Path(path)
            if not candidate.is_absolute():
                candidate = self.config.moneyprinter_repo / candidate
        candidate = candidate.resolve()
        if not candidate.exists():
            raise MoneyPrinterError(f"Resolved video does not exist: {candidate}")
        return candidate

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._request(req)

    def _get(self, path: str) -> dict[str, Any]:
        return self._request(urllib.request.Request(self.base + path, method="GET"))

    def _request(self, req: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise MoneyPrinterError(f"MoneyPrinterTurbo API request failed: {exc}") from exc
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MoneyPrinterError(f"MoneyPrinterTurbo returned invalid JSON: {raw[:500]}") from exc
        if obj.get("status") not in (None, 200):
            raise MoneyPrinterError(f"MoneyPrinterTurbo error: {obj}")
        data = obj.get("data")
        return data if isinstance(data, dict) else {"value": data}
