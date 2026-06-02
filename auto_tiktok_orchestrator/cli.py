from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Literal, TextIO

from .agent_planner import AgentPlanner
from .config import AppConfig
from .pipeline import AutoVideoPipeline, PipelineError, UploadReview

InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]
ChatIntent = Literal["video_request", "conversation"]

CASUAL_CHAT_MESSAGES = {
    "hi",
    "hello",
    "hey",
    "yo",
    "sup",
    "thanks",
    "thank you",
    "ok",
    "okay",
    "cool",
}
VIDEO_WORDS = {"video", "videos", "tiktok", "short", "shorts", "reel", "reels", "clip", "clips"}
VIDEO_PHRASES = {"tik tok", "youtube short", "youtube shorts"}
VIDEO_ACTIONS = {"make", "create", "generate", "produce", "plan", "build", "draft"}

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-tiktok", description="Agent-assisted MoneyPrinterTurbo video generation and TikTok publishing")
    parser.add_argument("--config", help="Optional JSON config override file")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate one video and TikTok metadata")
    gen.add_argument("--idea", required=True, help="Video idea prompt")
    add_common_run_args(gen)

    agent = sub.add_parser("agent", help="Run the video agent once with --prompt, or start chat mode without it")
    agent.add_argument("--prompt", default="", help="What the video should accomplish; omit to start chat mode")
    agent.add_argument("--account", default="", help="Preferred TikTok account username for upload")
    add_llm_args(agent)
    add_common_run_args(agent)

    chat = sub.add_parser("chat", help="Start an interactive Claude/Codex-style agent chat")
    chat.add_argument("--account", default="", help="Preferred TikTok account username for upload")
    add_llm_args(chat)
    add_common_run_args(chat)

    daily = sub.add_parser("daily", help="Generate one unique daily idea from a theme, then generate the video")
    daily.add_argument("--theme", required=True, help="Daily content strategy theme")
    daily.add_argument("--loop", action="store_true", help="Keep running every interval; default runs once")
    daily.add_argument("--interval-seconds", type=int, default=86400)
    add_common_run_args(daily)
    return parser

def add_common_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--custom-hashtag", action="append", default=[], help="Custom hashtag to force include; repeatable")
    parser.add_argument("--publish", action="store_true", help="Publish to TikTok via TiktokAutoUploader CLI after generation")
    parser.add_argument("--tiktok-username", default="", help="TikTokAutoUploader login username for --publish")
    parser.add_argument("--tiktok-proxy", default="", help="Optional proxy URL passed to TiktokAutoUploader upload via -p/--proxy")
    parser.add_argument("--allow-duplicate", action="store_true", help="Allow duplicate idea/script generation")

def add_llm_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--llm-provider", default="", help="LLM provider: moneyprinter, claude/anthropic, codex/openai, or gemini")
    parser.add_argument("--llm-model", default="", help="Provider model name")
    parser.add_argument("--llm-api-key-env", default="", help="Environment variable that contains the provider API key")
    parser.add_argument("--llm-api-base", default="", help="Optional provider API base URL")

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = apply_cli_overrides(AppConfig.load(args.config), args)
    pipeline = AutoVideoPipeline(config)
    try:
        if args.command == "generate":
            result = pipeline.generate(
                idea=args.idea,
                custom_hashtags=args.custom_hashtag,
                publish=args.publish,
                tiktok_username=resolve_upload_account(pipeline, args.tiktok_username, args.publish),
                tiktok_proxy=args.tiktok_proxy,
                allow_duplicate=args.allow_duplicate,
                confirm_upload=confirm_tiktok_upload if args.publish else None,
            )
            print_result(result)
            return 0
        if args.command == "agent":
            if not args.prompt:
                return run_agent_chat(args, config, pipeline)
            return run_agent_prompt(args, config, pipeline)
        if args.command == "chat":
            return run_agent_chat(args, config, pipeline)
        if args.command == "daily":
            while True:
                idea = pipeline.choose_daily_idea(args.theme)
                result = pipeline.generate(
                    idea=idea,
                    custom_hashtags=args.custom_hashtag,
                    publish=args.publish,
                    tiktok_username=resolve_upload_account(pipeline, args.tiktok_username, args.publish),
                    tiktok_proxy=args.tiktok_proxy,
                    allow_duplicate=args.allow_duplicate,
                    confirm_upload=confirm_tiktok_upload if args.publish else None,
                )
                print_result(result)
                if not args.loop:
                    return 0
                time.sleep(args.interval_seconds)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0

def run_agent_prompt(args: argparse.Namespace, config: AppConfig, pipeline: AutoVideoPipeline) -> int:
    planner = AgentPlanner(config, pipeline.llm)
    requested_account = args.account or args.tiktok_username
    accounts = pipeline.publisher.list_accounts()
    plan = planner.plan(args.prompt, available_accounts=accounts, requested_account=requested_account)
    print("Agent video plan:")
    print(plan.to_json())
    upload_account = resolve_upload_account(pipeline, plan.tiktok_username or requested_account, args.publish)
    result = pipeline.generate(
        idea=plan.idea,
        custom_hashtags=args.custom_hashtag,
        publish=args.publish,
        tiktok_username=upload_account,
        tiktok_proxy=args.tiktok_proxy,
        allow_duplicate=args.allow_duplicate,
        video_language=plan.video_language,
        voice_name=plan.voice_name,
        video_options=plan.video_options(),
        upload_questions=plan.verification_questions,
        confirm_upload=confirm_tiktok_upload if args.publish else None,
    )
    print_result(result)
    return 0

def run_agent_chat(
    args: argparse.Namespace,
    config: AppConfig,
    pipeline: AutoVideoPipeline,
    *,
    input_func: InputFunc = input,
    output: OutputFunc = print,
) -> int:
    planner = AgentPlanner(config, pipeline.llm)
    print_chat_intro(args, config, pipeline, output=output)
    while True:
        try:
            line = input_func("auto-tiktok> ").strip()
        except (EOFError, KeyboardInterrupt):
            output("")
            output("Bye.")
            return 0
        if not line:
            continue
        command_result = handle_chat_command(line, args, config, pipeline, output=output)
        if command_result == "exit":
            output("Bye.")
            return 0
        if command_result == "handled":
            continue
        if classify_chat_input(line) != "video_request":
            respond_to_casual_chat(line, output=output)
            continue
        try:
            run_chat_turn(line, args=args, pipeline=pipeline, planner=planner, input_func=input_func, output=output)
        except Exception as exc:
            output(f"ERROR: {exc}")

def classify_chat_input(line: str) -> ChatIntent:
    normalized = normalize_chat_text(line)
    if not normalized:
        return "conversation"
    if normalized in CASUAL_CHAT_MESSAGES:
        return "conversation"
    words = normalized.split()
    if has_video_keyword(normalized, words):
        return "video_request"
    if len(words) >= 4 and words[0] in VIDEO_ACTIONS:
        return "video_request"
    if len(words) >= 5 and words[:2] in (["i", "want"], ["i", "need"]):
        if any(action in words for action in VIDEO_ACTIONS):
            return "video_request"
    return "conversation"

def has_video_keyword(normalized: str, words: list[str]) -> bool:
    return any(phrase in normalized for phrase in VIDEO_PHRASES) or any(word in VIDEO_WORDS for word in words)

def normalize_chat_text(line: str) -> str:
    return " ".join(line.strip().lower().strip(".!?,;:\"'()[]{}").split())

def respond_to_casual_chat(line: str, *, output: OutputFunc = print) -> None:
    normalized = normalize_chat_text(line)
    if normalized in {"hi", "hello", "hey", "yo", "sup"}:
        output("Hi! Tell me the TikTok video you want to create, or type /help for commands.")
        return
    output("I did not detect a video request. Ask me to create a TikTok/video prompt, or type /help for commands.")

def run_chat_turn(
    prompt: str,
    *,
    args: argparse.Namespace,
    pipeline: AutoVideoPipeline,
    planner: AgentPlanner,
    input_func: InputFunc = input,
    output: OutputFunc = print,
) -> None:
    requested_account = args.account or args.tiktok_username
    output("Planning video...")
    accounts = pipeline.publisher.list_accounts()
    plan = planner.plan(prompt, available_accounts=accounts, requested_account=requested_account)
    output("Agent video plan:")
    output(plan.to_json())
    if plan.rationale:
        output(f"Rationale: {plan.rationale}")
    if not ask_yes_no("Generate this video now?", input_func=input_func, output=output):
        output("Skipped. Tell me what to change, or type another prompt.")
        return
    output("Generating video with MoneyPrinterTurbo...")
    upload_account = resolve_upload_account(pipeline, plan.tiktok_username or requested_account, args.publish)
    if args.publish:
        output("Publishing is enabled; TikTok upload verification will run after generation.")
    result = pipeline.generate(
        idea=plan.idea,
        custom_hashtags=args.custom_hashtag,
        publish=args.publish,
        tiktok_username=upload_account,
        tiktok_proxy=args.tiktok_proxy,
        allow_duplicate=args.allow_duplicate,
        video_language=plan.video_language,
        voice_name=plan.voice_name,
        video_options=plan.video_options(),
        upload_questions=plan.verification_questions,
        confirm_upload=confirm_tiktok_upload if args.publish else None,
    )
    output("Completed run:")
    print_result(result)

def handle_chat_command(
    line: str,
    args: argparse.Namespace,
    config: AppConfig,
    pipeline: AutoVideoPipeline,
    *,
    output: OutputFunc = print,
) -> str:
    parts = line.split()
    command = parts[0].lower()
    if command in {"/exit", "/quit", "exit", "quit"}:
        return "exit"
    if command in {"/help", "help"}:
        print_chat_help(output=output)
        return "handled"
    if command == "/accounts":
        accounts = pipeline.publisher.list_accounts()
        output("TikTok accounts: " + (", ".join(accounts) if accounts else "none found"))
        return "handled"
    if command == "/status":
        output(f"Provider: {config.llm_provider or 'moneyprinter'}")
        output(f"Publish: {'on' if args.publish else 'off'}")
        output(f"Account: {args.account or args.tiktok_username or config.default_tiktok_username or '(auto)'}")
        output(f"Hashtags: {', '.join(args.custom_hashtag) if args.custom_hashtag else '(none)'}")
        return "handled"
    if command == "/publish":
        if len(parts) != 2 or parts[1].lower() not in {"on", "off"}:
            output("Usage: /publish on|off")
            return "handled"
        args.publish = parts[1].lower() == "on"
        output(f"Publish {'enabled' if args.publish else 'disabled'}.")
        return "handled"
    if command == "/account":
        if len(parts) != 2:
            output("Usage: /account <username>")
            return "handled"
        args.account = parts[1]
        output(f"Account set to {args.account}.")
        return "handled"
    if command == "/hashtags":
        args.custom_hashtag = parts[1:]
        output(f"Hashtags set to: {', '.join(args.custom_hashtag) if args.custom_hashtag else '(none)'}")
        return "handled"
    return "unhandled"

def print_chat_intro(args: argparse.Namespace, config: AppConfig, pipeline: AutoVideoPipeline, *, output: OutputFunc = print) -> None:
    accounts = pipeline.publisher.list_accounts()
    output("Auto TikTok Agent Chat")
    output("Type a video request, or /help for commands. Ctrl-D exits.")
    output(f"LLM provider: {config.llm_provider or 'moneyprinter'}")
    output(f"Publishing: {'on' if args.publish else 'off'}")
    if accounts:
        output(f"TikTok accounts: {', '.join(accounts)}")

def print_chat_help(*, output: OutputFunc = print) -> None:
    output("Commands:")
    output("  /help                 Show this help")
    output("  /status               Show provider, publish, account, and hashtag settings")
    output("  /accounts             List discovered TikTok accounts")
    output("  /account <username>   Set the TikTok account for future turns")
    output("  /publish on|off       Toggle publishing for future turns")
    output("  /hashtags #a #b       Replace custom hashtags for future turns")
    output("  /exit                 Exit chat")
    output("Video requests create a plan; casual chat will not start generation.")

def ask_yes_no(prompt: str, *, input_func: InputFunc = input, output: OutputFunc = print) -> bool:
    while True:
        answer = input_func(f"{prompt} [yes/no]: ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        output("Please answer yes or no.")

def apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    updates = {}
    for arg_name, field_name in (
        ("llm_provider", "llm_provider"),
        ("llm_model", "llm_model"),
        ("llm_api_key_env", "llm_api_key_env"),
        ("llm_api_base", "llm_api_base"),
    ):
        value = getattr(args, arg_name, "")
        if value:
            updates[field_name] = value
    return replace(config, **updates) if updates else config

def resolve_upload_account(pipeline: AutoVideoPipeline, requested: str, publish: bool) -> str:
    if not publish:
        return requested
    accounts = pipeline.publisher.list_accounts()
    if requested:
        if accounts and requested not in accounts:
            raise PipelineError(f"TikTok account '{requested}' is not available. Available accounts: {', '.join(accounts)}")
        return requested
    default = pipeline.config.default_tiktok_username
    if default:
        if accounts and default not in accounts:
            raise PipelineError(f"Default TikTok account '{default}' is not available. Available accounts: {', '.join(accounts)}")
        return default
    if not accounts:
        raise PipelineError("No TikTok accounts found. Run TiktokAutoUploader login first or add tiktok_accounts to config.")
    if len(accounts) == 1:
        return accounts[0]
    if not sys.stdin.isatty():
        raise PipelineError("Multiple TikTok accounts are available; pass --tiktok-username or --account")
    print("Pick a TikTok account to upload:")
    for index, account in enumerate(accounts, start=1):
        print(f"  {index}. {account}")
    while True:
        choice = input("Account number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(accounts):
            return accounts[int(choice) - 1]
        print("Please enter a valid account number.")

def confirm_tiktok_upload(review: UploadReview) -> bool:
    if not sys.stdin.isatty():
        raise PipelineError("TikTok upload requires interactive verification before publishing")
    print("\nTikTok upload verification")
    print(f"Account: {review.username}")
    print(f"Video: {review.video_path}")
    print(f"Title: {review.title}")
    print(f"Caption: {review.caption}")
    print(f"Hashtags: {' '.join(review.hashtags)}")
    print("Questions:")
    for question in review.questions:
        answer = input(f"- {question} [yes/no]: ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Upload cancelled.")
            return False
    final = input("Publish this video to TikTok now? [yes/no]: ").strip().lower()
    return final in {"y", "yes"}

def print_result(result, *, file: TextIO | None = None) -> None:
    payload = asdict(result)
    payload["video_path"] = str(result.video_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=file)

if __name__ == "__main__":
    raise SystemExit(main())
