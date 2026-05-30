from __future__ import annotations

import subprocess
from pathlib import Path

from .config import AppConfig


class TikTokCliError(RuntimeError):
    pass


class TikTokCliPublisher:
    def __init__(self, config: AppConfig):
        self.config = config

    def publish(self, *, username: str, video_path: Path, title: str) -> str:
        if not username:
            raise TikTokCliError("TikTok username is required when publishing")
        if not video_path.exists():
            raise TikTokCliError(f"Video does not exist: {video_path}")
        cmd = ["python3", "cli.py", "upload", "-u", username, "-v", str(video_path), "-t", title]
        proc = subprocess.run(
            cmd,
            cwd=self.config.tiktok_repo,
            text=True,
            capture_output=True,
            check=False,
        )
        output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part)
        if proc.returncode != 0:
            raise TikTokCliError(f"TikTok upload failed: {output[-2000:]}")
        return output
