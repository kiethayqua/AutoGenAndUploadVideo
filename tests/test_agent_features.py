from pathlib import Path
from types import SimpleNamespace

from auto_tiktok_orchestrator.agent_planner import AgentPlanner
from auto_tiktok_orchestrator.config import AppConfig
from auto_tiktok_orchestrator.moneyprinter_client import MoneyPrinterClient
from auto_tiktok_orchestrator.tiktok_cli import TikTokCliPublisher

class FakeLlm:
    def complete(self, prompt, timeout=180):
        return '{"idea":"teach one English idiom with office footage","video_language":"English","voice_name":"en-US-GuyNeural-Male","voice_rate":1.1,"bgm_type":"random","font_size":72,"tiktok_username":"brand","verification_questions":["Correct account?","Caption ok?","Video reviewed?"]}'

def test_agent_planner_coerces_video_plan():
    config = AppConfig(default_tiktok_username="brand")
    plan = AgentPlanner(config, FakeLlm()).plan("make an English learning video", available_accounts=["brand"])

    assert plan.idea == "teach one English idiom with office footage"
    assert plan.voice_name == "en-US-GuyNeural-Male"
    assert plan.font_size == 72
    assert plan.tiktok_username == "brand"
    assert plan.video_options()["bgm_type"] == "random"
    assert plan.verification_questions == ["Correct account?", "Caption ok?", "Video reviewed?"]

def test_moneyprinter_payload_includes_agent_style(monkeypatch):
    captured = {}
    client = MoneyPrinterClient(AppConfig())

    def fake_post(path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return {"task_id": "task-1"}

    monkeypatch.setattr(client, "_post", fake_post)
    task_id = client.create_video(
        idea="idea",
        script="script",
        terms=["term"],
        video_source="pexels",
        video_aspect="9:16",
        language="English",
        voice_name="en-US-GuyNeural-Male",
        paragraph_number=1,
        voice_rate=1.1,
        bgm_volume=0.3,
        font_name="Arial.ttf",
        font_size=72,
    )

    assert task_id == "task-1"
    assert captured["path"] == "/videos"
    assert captured["payload"]["voice_rate"] == 1.1
    assert captured["payload"]["bgm_volume"] == 0.3
    assert captured["payload"]["font_name"] == "Arial.ttf"
    assert captured["payload"]["font_size"] == 72

def test_tiktok_accounts_include_config_and_cookie_files(tmp_path):
    cookies = tmp_path / "CookiesDir"
    cookies.mkdir()
    (cookies / "tiktok_session-second.cookie").write_bytes(b"cookie")
    publisher = TikTokCliPublisher(SimpleNamespace(tiktok_repo=tmp_path, tiktok_accounts=("first",)))

    assert publisher.list_accounts() == ["first", "second"]

from auto_tiktok_orchestrator.agent_planner import VideoPlan
from auto_tiktok_orchestrator.cli import build_parser, classify_chat_input, handle_chat_command, run_agent_chat, run_chat_turn
from auto_tiktok_orchestrator.pipeline import PipelineResult

class FakePublisher:
    def list_accounts(self):
        return ["brand"]

class FakePipeline:
    def __init__(self):
        self.config = AppConfig(default_tiktok_username="brand")
        self.publisher = FakePublisher()
        self.llm = FakeLlm()
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return PipelineResult(
            run_id=1,
            idea=kwargs["idea"],
            task_id="task-1",
            video_path=Path("/tmp/video.mp4"),
            caption="caption",
            hashtags=["#x"],
            title="caption #x",
            status="generated",
        )

class FakePlanner:
    def plan(self, prompt, *, available_accounts, requested_account=""):
        return VideoPlan(
            idea=f"planned {prompt}",
            video_language="English",
            voice_name="en-US-GuyNeural-Male",
            voice_volume=1.0,
            voice_rate=1.0,
            bgm_type="random",
            bgm_file="",
            bgm_volume=0.2,
            subtitle_position="bottom",
            custom_position=70.0,
            font_name="",
            text_fore_color="#FFFFFF",
            text_background_color=True,
            font_size=60,
            stroke_color="#000000",
            stroke_width=1.5,
            tiktok_username="brand",
            verification_questions=["Review video?"],
            rationale="good fit",
        )

def test_chat_parser_does_not_require_prompt():
    args = build_parser().parse_args(["chat", "--llm-provider", "claude", "--custom-hashtag", "#x"])

    assert args.command == "chat"
    assert args.llm_provider == "claude"
    assert args.custom_hashtag == ["#x"]

def test_agent_without_prompt_enters_chat_shape():
    args = build_parser().parse_args(["agent", "--llm-provider", "gemini"])

    assert args.command == "agent"
    assert args.prompt == ""
    assert args.llm_provider == "gemini"

def test_chat_intent_routes_casual_and_video_requests():
    assert classify_chat_input("hi") == "conversation"
    assert classify_chat_input("thanks") == "conversation"
    assert classify_chat_input("make a video about discipline") == "video_request"
    assert classify_chat_input("Create a high-retention English idiom TikTok") == "video_request"

def test_agent_chat_casual_message_does_not_plan_or_generate():
    args = build_parser().parse_args(["chat"])
    pipeline = FakePipeline()
    outputs = []
    inputs = iter(["hi", "/exit"])

    result = run_agent_chat(
        args,
        AppConfig(),
        pipeline,
        input_func=lambda prompt: next(inputs),
        output=outputs.append,
    )

    assert result == 0
    assert pipeline.calls == []
    assert any("Hi!" in item for item in outputs)
    assert not any("Planning video" in item for item in outputs)

def test_chat_turn_decline_skips_generation():
    args = build_parser().parse_args(["chat", "--custom-hashtag", "#x"])
    pipeline = FakePipeline()
    outputs = []
    inputs = iter(["no"])

    run_chat_turn(
        "make a video",
        args=args,
        pipeline=pipeline,
        planner=FakePlanner(),
        input_func=lambda prompt: next(inputs),
        output=outputs.append,
    )

    assert pipeline.calls == []
    assert any("Planning video" in item for item in outputs)
    assert any("Skipped" in item for item in outputs)

def test_chat_turn_generates_after_approval(capsys):
    args = build_parser().parse_args(["chat", "--custom-hashtag", "#x"])
    pipeline = FakePipeline()
    outputs = []
    inputs = iter(["yes"])

    run_chat_turn(
        "make a video",
        args=args,
        pipeline=pipeline,
        planner=FakePlanner(),
        input_func=lambda prompt: next(inputs),
        output=outputs.append,
    )

    assert len(pipeline.calls) == 1
    call = pipeline.calls[0]
    assert call["idea"] == "planned make a video"
    assert call["custom_hashtags"] == ["#x"]
    assert call["voice_name"] == "en-US-GuyNeural-Male"
    assert call["upload_questions"] == ["Review video?"]
    assert "generated" in capsys.readouterr().out

def test_chat_commands_mutate_session_args():
    args = build_parser().parse_args(["chat"])
    pipeline = FakePipeline()
    outputs = []

    assert handle_chat_command("/publish on", args, AppConfig(), pipeline, output=outputs.append) == "handled"
    assert args.publish is True
    assert handle_chat_command("/account brand", args, AppConfig(), pipeline, output=outputs.append) == "handled"
    assert args.account == "brand"
    assert handle_chat_command("/hashtags #one #two", args, AppConfig(), pipeline, output=outputs.append) == "handled"
    assert args.custom_hashtag == ["#one", "#two"]
    assert handle_chat_command("/exit", args, AppConfig(), pipeline, output=outputs.append) == "exit"

from auto_tiktok_orchestrator.pipeline import AutoVideoPipeline

class FakeStoreForPipeline:
    def __init__(self):
        self.runs = []
    def has_idea(self, idea):
        return False
    def has_script_hash(self, script_hash):
        return False
    def hash_text(self, text):
        return "hash"
    def record_run(self, **values):
        self.runs.append(values)
        return 7

class FakeMoneyPrinterForPipeline:
    def generate_script(self, idea, language, paragraph_number):
        return "script"
    def generate_terms(self, idea, script):
        return ["term"]
    def create_video(self, **kwargs):
        return "task-1"
    def wait_for_video(self, task_id):
        return {"videos": ["/tmp/video.mp4"], "progress": 100}
    def resolve_video_path(self, task):
        return Path("/tmp/video.mp4")

class FakeMetadataLlm:
    def complete(self, prompt, timeout=180):
        return '{"caption":"caption","hashtags":["#x"]}'

def test_pipeline_wraps_generation_in_moneyprinter_server_manager(monkeypatch, tmp_path):
    events = []

    class FakeServerManager:
        def __init__(self, config, client):
            events.append(("init", client.__class__.__name__))
        def __enter__(self):
            events.append(("enter",))
            return self
        def __exit__(self, exc_type, exc, tb):
            events.append(("exit", exc_type))

    monkeypatch.setattr("auto_tiktok_orchestrator.pipeline.MoneyPrinterServerManager", FakeServerManager)
    config = AppConfig(state_db=tmp_path / "state.db")
    pipeline = AutoVideoPipeline(config)
    pipeline.store = FakeStoreForPipeline()
    pipeline.moneyprinter = FakeMoneyPrinterForPipeline()
    pipeline.llm = FakeMetadataLlm()

    result = pipeline.generate(idea="idea", custom_hashtags=[])

    assert result.status == "generated"
    assert events == [("init", "FakeMoneyPrinterForPipeline"), ("enter",), ("exit", None)]
