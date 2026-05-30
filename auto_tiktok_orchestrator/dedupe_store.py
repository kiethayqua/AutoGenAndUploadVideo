from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DedupeStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def has_idea(self, idea: str) -> bool:
        return self._exists("idea_hash", self.hash_text(normalize_idea(idea)))

    def has_script_hash(self, script_hash: str) -> bool:
        return self._exists("script_hash", script_hash)

    def recent_ideas(self, limit: int = 50) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT idea FROM runs WHERE status IN ('generated', 'published') ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [row[0] for row in rows]

    def record_run(self, **values: Any) -> int:
        payload = {
            "created_at": now_iso(),
            "idea": values["idea"],
            "normalized_idea": normalize_idea(values["idea"]),
            "idea_hash": self.hash_text(normalize_idea(values["idea"])),
            "script": values.get("script", ""),
            "script_hash": values.get("script_hash", ""),
            "terms_json": json.dumps(values.get("terms", []), ensure_ascii=False),
            "video_task_id": values.get("video_task_id", ""),
            "video_path": str(values.get("video_path", "")),
            "caption": values.get("caption", ""),
            "hashtags_json": json.dumps(values.get("hashtags", []), ensure_ascii=False),
            "custom_hashtags_json": json.dumps(values.get("custom_hashtags", []), ensure_ascii=False),
            "status": values.get("status", "generated"),
            "error": values.get("error", ""),
        }
        keys = list(payload.keys())
        placeholders = ", ".join("?" for _ in keys)
        with self._connect() as conn:
            cur = conn.execute(
                f"INSERT INTO runs ({', '.join(keys)}) VALUES ({placeholders})",
                [payload[k] for k in keys],
            )
            conn.commit()
            return int(cur.lastrowid)

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _exists(self, column: str, value: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(f"SELECT 1 FROM runs WHERE {column} = ? LIMIT 1", (value,)).fetchone()
        return row is not None

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    idea TEXT NOT NULL,
                    normalized_idea TEXT NOT NULL,
                    idea_hash TEXT NOT NULL,
                    script TEXT,
                    script_hash TEXT,
                    terms_json TEXT,
                    video_task_id TEXT,
                    video_path TEXT,
                    caption TEXT,
                    hashtags_json TEXT,
                    custom_hashtags_json TEXT,
                    status TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_idea_hash ON runs(idea_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_script_hash ON runs(script_hash)")
            conn.commit()


def normalize_idea(value: str) -> str:
    lowered = value.strip().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", lowered)).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
