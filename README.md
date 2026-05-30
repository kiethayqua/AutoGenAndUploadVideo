# Auto TikTok Video Orchestrator

This project combines two submodules with a small Python orchestration layer:

- `MoneyPrinterTurbo/`: generates short videos from an idea, script, terms, TTS, subtitles, and stock footage.
- `TiktokAutoUploader/`: logs in to TikTok and can upload generated videos.
- `auto_tiktok_orchestrator/`: coordinates the end-to-end flow and stores generation history to avoid duplicate content.

## Clone With Submodules

```bash
git clone --recurse-submodules <this-repo-url>
```

If the repo is already cloned:

```bash
git submodule update --init --recursive
```

## Configure MoneyPrinterTurbo

Create/configure MoneyPrinterTurbo's `config.toml` with your LLM provider, stock footage provider, TTS, and related API keys.

```bash
cd MoneyPrinterTurbo
cp config.example.toml config.toml
```

Then edit `config.toml` as needed.

## Start MoneyPrinterTurbo

```bash
cd MoneyPrinterTurbo
uv run python main.py
```

The orchestrator expects the API at:

```text
http://127.0.0.1:8080/api/v1
```

Override it with `MONEYPRINTER_API_BASE` or `auto_tiktok_orchestrator/config.example.json`.

## Generate One Video

From the top-level project directory:

```bash
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli generate \
  --idea "A short motivational video about building discipline" \
  --custom-hashtag "#mybrand"
```

This will:

1. Ask MoneyPrinterTurbo's LLM to generate a video script.
2. Ask MoneyPrinterTurbo's LLM to generate stock-video search terms.
3. Generate a vertical `9:16` video with MoneyPrinterTurbo.
4. Generate a TikTok caption and hashtags.
5. Store the run in `auto_tiktok_orchestrator/state/orchestrator.db` to prevent duplicates.

## Daily Unique Generation

```bash
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli daily \
  --theme "daily productivity and self improvement videos" \
  --custom-hashtag "#mybrand"
```

To keep it running once per day:

```bash
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli daily \
  --theme "daily productivity and self improvement videos" \
  --custom-hashtag "#mybrand" \
  --loop \
  --interval-seconds 86400
```

## Optional TikTok Publishing

First log in through TikTokAutoUploader so it creates a valid cookie file:

```bash
cd TiktokAutoUploader
python3 cli.py login -n your_username
```

Then run the orchestrator with publishing enabled:

```bash
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli generate \
  --idea "A short motivational video about building discipline" \
  --custom-hashtag "#mybrand" \
  --publish \
  --tiktok-username "your_username"
```

## Duplicate Prevention

The orchestrator stores generated ideas and script hashes in SQLite. By default it refuses to generate a duplicate idea or duplicate script.

Use this only when you intentionally want to bypass dedupe:

```bash
--allow-duplicate
```

## Useful Files

```text
auto_tiktok_orchestrator/cli.py                 CLI entrypoint
auto_tiktok_orchestrator/pipeline.py            End-to-end pipeline
auto_tiktok_orchestrator/moneyprinter_client.py MoneyPrinterTurbo API client
auto_tiktok_orchestrator/metadata.py            Caption/hashtag LLM helpers
auto_tiktok_orchestrator/dedupe_store.py        SQLite duplicate prevention
auto_tiktok_orchestrator/tiktok_cli.py          TikTokAutoUploader CLI adapter
auto_tiktok_orchestrator/config.example.json    Example orchestrator config
```
