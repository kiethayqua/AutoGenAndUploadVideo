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

## Configure Orchestrator Language and Voice

The orchestrator defaults to English script generation and an English US female voice to avoid MoneyPrinterTurbo's Chinese TTS fallback:

```json
{
  "default_video_language": "English",
  "default_voice_name": "en-US-JennyNeural-Female"
}
```

To use another language, copy `auto_tiktok_orchestrator/config.example.json`, edit these fields, then run commands with `--config path/to/config.json`. Example Vietnamese config values:

```json
{
  "default_video_language": "Vietnamese",
  "default_voice_name": "vi-VN-HoaiMyNeural-Female"
}
```

Common Edge/Azure voice examples:

- `en-US-JennyNeural-Female` for English US female
- `en-US-GuyNeural-Male` for English US male
- `vi-VN-HoaiMyNeural-Female` for Vietnamese female
- `vi-VN-NamMinhNeural-Male` for Vietnamese male

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

To publish through an upload proxy, add `--tiktok-proxy`. The value is forwarded to TiktokAutoUploader's `-p/--proxy` option:

```bash
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli generate \
  --idea "A short motivational video about building discipline" \
  --custom-hashtag "#mybrand" \
  --publish \
  --tiktok-username "your_username" \
  --tiktok-proxy "http://proxy.example:8080"
```

The same proxy option also works with daily generation:

```bash
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli daily \
  --theme "daily productivity and self improvement videos" \
  --custom-hashtag "#mybrand" \
  --publish \
  --tiktok-username "your_username" \
  --tiktok-proxy "http://proxy.example:8080"
```

Proxy support applies to the upload request path. If your proxy provider requires authentication, use the proxy URL format they provide. For consistent account signals, log in from the same network/proxy environment you plan to use for publishing.

### Free US Proxy Notes

Free public proxies are useful only for low-risk testing. Avoid using them for real TikTok login or publishing because the proxy operator may log traffic, steal cookies, disappear without notice, or use IPs already flagged by TikTok. For production posting, prefer a stable trusted residential/mobile proxy.

Common places to look for free US proxies:

- ProxyScrape US list: `https://proxyscrape.com/free-proxy-list/united-states`
- Proxifly GitHub list: `https://github.com/proxifly/free-proxy-list`
- Spys.one US list: `https://spys.one/free-proxy-list/US/`
- FreeProxy.World US filter: `https://www.freeproxy.world/?country=US`
- ProxyNova list: `https://www.proxynova.com/proxy-server-list/`

Use an `HTTP` or `HTTPS` proxy URL first, because this uploader passes the value to TiktokAutoUploader's upload proxy option:

```text
http://host:port
```

Before using a proxy with this tool, test only the public IP and country without sending TikTok credentials:

```bash
curl -x "http://host:port" https://ipinfo.io/ip
curl -x "http://host:port" https://ifconfig.me
```

Then publish with the working proxy:

```bash
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli generate \
  --idea "Your video idea" \
  --publish \
  --tiktok-username "your_username" \
  --tiktok-proxy "http://host:port"
```

## Best Turkey Posting Times From UTC+7

If you are scheduling from a `UTC+7` timezone for a Turkey-focused TikTok audience, Turkey is 4 hours behind at `UTC+3`. Start with these `UTC+7` posting windows:

| UTC+7 Time | Turkey Audience Window | Notes |
| --- | --- | --- |
| `11:00 AM - 1:00 PM` | Turkey morning, `7:00 AM - 9:00 AM` | Good commute / early-day window |
| `4:00 PM - 6:00 PM` | Turkey midday, `12:00 PM - 2:00 PM` | Useful lunch-break test window |
| `11:00 PM - 3:00 AM` | Turkey evening, `7:00 PM - 11:00 PM` | Strong primary window |

Recommended starting schedule:

```text
2 posts/day: 12:00 PM and 12:30 AM UTC+7
3 posts/day: 12:00 PM, 5:00 PM, and 12:30 AM UTC+7
```

Track results for at least 2 weeks, then keep the slots with the highest Turkey viewer percentage, engagement, and app conversions.

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
