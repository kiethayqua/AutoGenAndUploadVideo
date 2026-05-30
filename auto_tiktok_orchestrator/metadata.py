from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass

from .config import AppConfig


class MetadataError(RuntimeError):
    pass


@dataclass(frozen=True)
class TikTokMetadata:
    caption: str
    hashtags: list[str]
    title: str


class MoneyPrinterLlm:
    def __init__(self, config: AppConfig):
        self.config = config

    def complete(self, prompt: str, timeout: int = 180) -> str:
        helper = (
            "import json, sys\n"
            "from app.services import llm\n"
            "prompt = sys.stdin.read()\n"
            "print(json.dumps({'text': llm._generate_response(prompt)}, ensure_ascii=False))\n"
        )
        cmd = [*self.config.moneyprinter_runner, "-c", helper]
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.config.moneyprinter_repo,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise MetadataError(f"Cannot run MoneyPrinterTurbo LLM command {cmd!r}: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise MetadataError("Timed out waiting for MoneyPrinterTurbo LLM") from exc
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout).strip()
            raise MetadataError(f"MoneyPrinterTurbo LLM failed: {err[-1200:]}")
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
            return str(payload["text"]).strip()
        except Exception as exc:
            raise MetadataError(f"MoneyPrinterTurbo LLM returned invalid output: {proc.stdout[-1200:]}") from exc


def generate_unique_idea(llm: MoneyPrinterLlm, theme: str, previous_ideas: list[str]) -> str:
    prompt = f"""
Return one unique TikTok short-form video idea as strict JSON.
Theme: {theme}
Already used ideas:
{json.dumps(previous_ideas[:50], ensure_ascii=False, indent=2)}
Rules:
- Do not repeat or closely paraphrase any already used idea.
- Make the idea concrete enough for stock footage generation.
- Return only: {{"idea":"..."}}
""".strip()
    data = parse_json_object(llm.complete(prompt))
    idea = str(data.get("idea", "")).strip()
    if not idea:
        raise MetadataError("LLM did not return a unique idea")
    return idea


def generate_tiktok_metadata(
    llm: MoneyPrinterLlm,
    *,
    idea: str,
    script: str,
    terms: list[str],
    custom_hashtags: list[str],
    caption_limit: int,
    max_hashtags: int,
) -> TikTokMetadata:
    prompt = f"""
Create TikTok publishing metadata for a generated short video. Return strict JSON only.
Video idea: {idea}
Video script: {script}
Stock search terms: {json.dumps(terms, ensure_ascii=False)}
Custom hashtags that must be included: {json.dumps(custom_hashtags, ensure_ascii=False)}
Rules:
- Write a compelling caption in the same language as the idea/script when possible.
- Do not put hashtags in the caption field.
- Recommend relevant TikTok hashtags.
- Include all custom hashtags exactly once.
- Keep the final caption plus hashtags under {caption_limit} characters.
- Return only: {{"caption":"...","hashtags":["#tag1","#tag2"]}}
""".strip()
    data = parse_json_object(llm.complete(prompt))
    caption = str(data.get("caption", "")).strip()
    raw_tags = data.get("hashtags", [])
    if not caption or not isinstance(raw_tags, list):
        raise MetadataError(f"Invalid metadata JSON: {data}")
    hashtags = merge_hashtags([str(tag) for tag in raw_tags], custom_hashtags, max_hashtags)
    title = build_title(caption, hashtags, caption_limit)
    return TikTokMetadata(caption=caption, hashtags=hashtags, title=title)


def parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise MetadataError(f"LLM response did not contain JSON: {text[:500]}")
        obj = json.loads(match.group(0))
    if not isinstance(obj, dict):
        raise MetadataError(f"Expected JSON object, got: {obj!r}")
    return obj


def merge_hashtags(generated: list[str], custom: list[str], max_hashtags: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    def add(tag: str) -> None:
        normalized = normalize_hashtag(tag)
        key = normalized.lower()
        if normalized and key not in seen:
            result.append(normalized)
            seen.add(key)

    for tag in custom:
        add(tag)
    for tag in generated:
        if len(result) >= max_hashtags:
            break
        add(tag)
    return result[:max_hashtags]


def normalize_hashtag(tag: str) -> str:
    value = tag.strip().lstrip("#")
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[^\w]", "", value, flags=re.UNICODE)
    return f"#{value}" if value else ""


def build_title(caption: str, hashtags: list[str], limit: int) -> str:
    suffix = " ".join(hashtags)
    if not suffix:
        return caption[:limit]
    available = max(0, limit - len(suffix) - 1)
    trimmed_caption = caption[:available].rstrip()
    return f"{trimmed_caption} {suffix}".strip()[:limit]
