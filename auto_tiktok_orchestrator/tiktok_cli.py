from __future__ import annotations

import subprocess
from pathlib import Path

from .config import AppConfig


class TikTokCliError(RuntimeError):
    pass


class TikTokCliPublisher:
    def __init__(self, config: AppConfig):
        self.config = config

    def publish(self, *, username: str, video_path: Path, title: str, proxy: str = "") -> str:
        if not username:
            raise TikTokCliError("TikTok username is required when publishing")
        if not video_path.exists():
            raise TikTokCliError(f"Video does not exist: {video_path}")
        cmd = ["python3", "cli.py", "upload", "-u", username, "-v", str(video_path), "-t", title]
        if proxy:
            cmd.extend(["-p", proxy])
        proc = subprocess.Popen(
            cmd,
            cwd=self.config.tiktok_repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        lines: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            lines.append(line.rstrip("\n"))
        returncode = proc.wait()
        output = "\n".join(lines).strip()
        if returncode != 0:
            raise TikTokCliError(f"TikTok upload failed: {output[-2000:]}")
        return output
