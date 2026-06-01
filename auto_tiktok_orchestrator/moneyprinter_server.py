from __future__ import annotations

import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import TextIO

from .config import AppConfig
from .moneyprinter_client import MoneyPrinterClient, MoneyPrinterError

class MoneyPrinterServerError(RuntimeError):
    pass

class MoneyPrinterServerManager:
    def __init__(self, config: AppConfig, client: MoneyPrinterClient):
        self.config = config
        self.client = client
        self.process: subprocess.Popen | None = None
        self.log_file: TextIO | None = None
        self.log_path = config.root_dir / "auto_tiktok_orchestrator" / "state" / "moneyprinter_server.log"

    def __enter__(self) -> "MoneyPrinterServerManager":
        if not self.config.auto_start_moneyprinter_api:
            return self
        if self.client.is_server_available():
            return self
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    @property
    def started(self) -> bool:
        return self.process is not None

    def start(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_path.open("a", encoding="utf-8")
        self.log_file.write(f"\n--- auto-start MoneyPrinterTurbo at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        self.log_file.flush()
        cmd = [*self.config.moneyprinter_runner, "main.py"]
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=self.config.moneyprinter_repo,
                stdout=self.log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except FileNotFoundError as exc:
            self._close_log()
            raise MoneyPrinterServerError(f"Cannot start MoneyPrinterTurbo with {cmd!r}: {exc}") from exc
        try:
            self.wait_until_ready()
        except Exception:
            self.stop()
            raise

    def wait_until_ready(self) -> None:
        deadline = time.time() + self.config.moneyprinter_startup_timeout_seconds
        while time.time() < deadline:
            if self.client.is_server_available():
                return
            if self.process and self.process.poll() is not None:
                raise MoneyPrinterServerError(
                    f"MoneyPrinterTurbo exited during startup with code {self.process.returncode}. Log: {self.log_path}"
                )
            time.sleep(1)
        raise MoneyPrinterServerError(f"Timed out starting MoneyPrinterTurbo. Log: {self.log_path}")

    def stop(self) -> None:
        proc = self.process
        self.process = None
        if proc is None:
            self._close_log()
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=15)
        self._close_log()

    def _close_log(self) -> None:
        if self.log_file:
            self.log_file.close()
            self.log_file = None

def moneyprinter_docs_url(config: AppConfig) -> str:
    parsed = urllib.parse.urlparse(config.moneyprinter_api_base)
    if not parsed.scheme or not parsed.netloc:
        raise MoneyPrinterError(f"Invalid MoneyPrinter API base URL: {config.moneyprinter_api_base}")
    return f"{parsed.scheme}://{parsed.netloc}/docs"
