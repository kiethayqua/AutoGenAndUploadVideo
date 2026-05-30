from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig
from .dedupe_store import DedupeStore
from .metadata import MoneyPrinterLlm, generate_tiktok_metadata, generate_unique_idea
from .moneyprinter_client import MoneyPrinterClient
from .tiktok_cli import TikTokCliPublisher


class PipelineError(RuntimeError):
    pass


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
        self.llm = MoneyPrinterLlm(config)
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
        allow_duplicate: bool = False,
    ) -> PipelineResult:
        if not allow_duplicate and self.store.has_idea(idea):
            raise PipelineError(f"Duplicate idea already generated: {idea}")

        script = self.moneyprinter.generate_script(
            idea,
            language=self.config.default_video_language,
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
            language=self.config.default_video_language,
            paragraph_number=self.config.default_paragraph_number,
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
        if publish:
            self.publisher.publish(username=tiktok_username, video_path=video_path, title=metadata.title)
            status = "published"

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
