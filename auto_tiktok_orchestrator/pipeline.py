from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agent_planner import default_upload_questions
from .config import AppConfig
from .dedupe_store import DedupeStore
from .llm_provider import create_llm_client
from .metadata import generate_tiktok_metadata, generate_unique_idea
from .moneyprinter_client import MoneyPrinterClient
from .moneyprinter_server import MoneyPrinterServerManager
from .tiktok_cli import TikTokCliPublisher

class PipelineError(RuntimeError):
    pass

@dataclass(frozen=True)
class UploadReview:
    idea: str
    video_path: Path
    title: str
    caption: str
    hashtags: list[str]
    username: str
    questions: list[str]

@dataclass(frozen=True)
class PipelineResult:
    run_id: int
    idea: str
    task_id: str
    video_path: Path
    caption: str
    hashtags: list[str]
    title: str
    status: str

class AutoVideoPipeline:
    def __init__(self, config: AppConfig):
        self.config = config
        self.store = DedupeStore(config.state_db)
        self.moneyprinter = MoneyPrinterClient(config)
        self.llm = create_llm_client(config)
        self.publisher = TikTokCliPublisher(config)

    def choose_daily_idea(self, theme: str, max_attempts: int = 5) -> str:
        previous = self.store.recent_ideas(limit=50)
        for _ in range(max_attempts):
            idea = generate_unique_idea(self.llm, theme, previous)
            if not self.store.has_idea(idea):
                return idea
            previous.insert(0, idea)
        raise PipelineError("Could not generate a non-duplicate daily idea")

    def generate(
        self,
        *,
        idea: str,
        custom_hashtags: list[str],
        publish: bool = False,
        tiktok_username: str = "",
        tiktok_proxy: str = "",
        allow_duplicate: bool = False,
        video_language: str = "",
        voice_name: str = "",
        video_options: dict[str, Any] | None = None,
        upload_questions: list[str] | None = None,
        confirm_upload: Callable[[UploadReview], bool] | None = None,
    ) -> PipelineResult:
        if not allow_duplicate and self.store.has_idea(idea):
            raise PipelineError(f"Duplicate idea already generated: {idea}")

        language = video_language or self.config.default_video_language
        selected_voice = voice_name or self.config.default_voice_name
        options = video_options or {}
        with MoneyPrinterServerManager(self.config, self.moneyprinter):
            script = self.moneyprinter.generate_script(
                idea,
                language=language,
                paragraph_number=self.config.default_paragraph_number,
            )
            script_hash = self.store.hash_text(script.strip())
            if not allow_duplicate and self.store.has_script_hash(script_hash):
                raise PipelineError("Duplicate script already generated")

            terms = self.moneyprinter.generate_terms(idea, script)
            task_id = self.moneyprinter.create_video(
                idea=idea,
                script=script,
                terms=terms,
                video_source=self.config.default_video_source,
                video_aspect=self.config.default_video_aspect,
                language=language,
                voice_name=selected_voice,
                paragraph_number=self.config.default_paragraph_number,
                **options,
            )
            task = self.moneyprinter.wait_for_video(task_id)
            video_path = self.moneyprinter.resolve_video_path(task)
        metadata = generate_tiktok_metadata(
            self.llm,
            idea=idea,
            script=script,
            terms=terms,
            custom_hashtags=custom_hashtags,
            caption_limit=self.config.caption_limit,
            max_hashtags=self.config.max_hashtags,
        )

        status = "generated"
        error = ""
        username = tiktok_username or self.config.default_tiktok_username
        if publish:
            questions = upload_questions or default_upload_questions()
            if confirm_upload is None:
                raise PipelineError("TikTok publish requires an explicit upload verification callback")
            approved = confirm_upload(
                UploadReview(
                    idea=idea,
                    video_path=video_path,
                    title=metadata.title,
                    caption=metadata.caption,
                    hashtags=metadata.hashtags,
                    username=username,
                    questions=questions,
                )
            )
            if not approved:
                status = "upload_cancelled"
            else:
                try:
                    self.publisher.publish(
                        username=username,
                        video_path=video_path,
                        title=metadata.title,
                        proxy=tiktok_proxy,
                    )
                    status = "published"
                except Exception as exc:
                    error = str(exc)
                    run_id = self.store.record_run(
                        idea=idea,
                        script=script,
                        script_hash=script_hash,
                        terms=terms,
                        video_task_id=task_id,
                        video_path=video_path,
                        caption=metadata.caption,
                        hashtags=metadata.hashtags,
                        custom_hashtags=custom_hashtags,
                        status="publish_failed",
                        error=error,
                    )
                    raise PipelineError(
                        f"Video generated but TikTok publish failed; run_id={run_id}; video_path={video_path}: {exc}"
                    ) from exc

        run_id = self.store.record_run(
            idea=idea,
            script=script,
            script_hash=script_hash,
            terms=terms,
            video_task_id=task_id,
            video_path=video_path,
            caption=metadata.caption,
            hashtags=metadata.hashtags,
            custom_hashtags=custom_hashtags,
            status=status,
            error=error,
        )
        return PipelineResult(
            run_id=run_id,
            idea=idea,
            task_id=task_id,
            video_path=video_path,
            caption=metadata.caption,
            hashtags=metadata.hashtags,
            title=metadata.title,
            status=status,
        )
