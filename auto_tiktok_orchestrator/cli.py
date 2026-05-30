from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict

from .config import AppConfig
from .pipeline import AutoVideoPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-tiktok", description="Generate MoneyPrinterTurbo videos and prepare TikTok metadata")
    parser.add_argument("--config", help="Optional JSON config override file")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate one video and TikTok metadata")
    gen.add_argument("--idea", required=True, help="Video idea prompt")
    add_common_run_args(gen)

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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = AppConfig.load(args.config)
    pipeline = AutoVideoPipeline(config)
    try:
        if args.command == "generate":
            result = pipeline.generate(
                idea=args.idea,
                custom_hashtags=args.custom_hashtag,
                publish=args.publish,
                tiktok_username=args.tiktok_username,
                tiktok_proxy=args.tiktok_proxy,
                allow_duplicate=args.allow_duplicate,
            )
            print_result(result)
            return 0
        if args.command == "daily":
            while True:
                idea = pipeline.choose_daily_idea(args.theme)
                result = pipeline.generate(
                    idea=idea,
                    custom_hashtags=args.custom_hashtag,
                    publish=args.publish,
                    tiktok_username=args.tiktok_username,
                    tiktok_proxy=args.tiktok_proxy,
                    allow_duplicate=args.allow_duplicate,
                )
                print_result(result)
                if not args.loop:
                    return 0
                time.sleep(args.interval_seconds)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def print_result(result) -> None:
    payload = asdict(result)
    payload["video_path"] = str(result.video_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
