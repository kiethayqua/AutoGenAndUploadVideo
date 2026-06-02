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

## Agent Mode

Use `agent` mode when you want to give one high-level prompt and let the orchestrator plan the best video settings before generation. The agent can choose a concrete video idea, language, voice, subtitle font settings, background music settings, optional intro/outro videos, TikTok account, and upload verification questions.

```bash
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli agent \
  --prompt "Create a high-retention TikTok teaching one useful English idiom for office workers" \
  --custom-hashtag "#mybrand"
```

The command prints the agent's video plan before running the normal generation pipeline. By default, `llm_provider` is `moneyprinter`, so the agent uses the LLM provider configured in `MoneyPrinterTurbo/config.toml`.

### Agent Chat Mode

Use chat mode when you want a Claude Code/Codex-style interactive session where you can type requests, review the agent's plan, answer follow-up confirmations, and keep iterating without restarting the CLI.

```bash
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli chat \
  --llm-provider claude \
  --llm-model claude-3-5-haiku-latest \
  --custom-hashtag "#mybrand"
```

You can also enter the same chat mode by running `agent` without `--prompt`:

```bash
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli agent
```

Inside chat, video requests create a plan; casual chat will not start generation:

```text
auto-tiktok> Create a high-retention English idiom video for office workers
Planning video...
Agent video plan:
{ ... }
Generate this video now? [yes/no]: yes
Generating video with MoneyPrinterTurbo...
```

Chat commands:

| Command | Purpose |
| --- | --- |
| `/help` | Show available chat commands |
| `/status` | Show provider, publish, account, and hashtag settings |
| `/accounts` | List discovered TikTok accounts |
| `/account <username>` | Set the TikTok account for future turns |
| `/publish on\|off` | Toggle TikTok publishing for future turns |
| `/hashtags #a #b` | Replace custom hashtags for future turns |
| `/exit` | Exit chat |

When publishing is enabled, chat still uses the same TikTok verification gate before upload. The agent shows its plan first, asks whether to generate, then asks the upload verification questions after video generation.

### Agent LLM Providers

You can also connect the agent directly to common LLM providers. API keys are read from environment variables, not config files.

```bash
export ANTHROPIC_API_KEY="..."
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli agent \
  --prompt "Make a motivational video for founders" \
  --llm-provider claude \
  --llm-model claude-3-5-haiku-latest
```

```bash
export OPENAI_API_KEY="..."
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli agent \
  --prompt "Make a concise productivity tip video" \
  --llm-provider codex \
  --llm-model gpt-4o-mini
```

```bash
export GEMINI_API_KEY="..."
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli agent \
  --prompt "Make a travel inspiration short" \
  --llm-provider gemini \
  --llm-model gemini-1.5-flash
```

Supported provider aliases:

| Provider | Aliases | Default key env |
| --- | --- | --- |
| MoneyPrinterTurbo config | `moneyprinter` | Uses `MoneyPrinterTurbo/config.toml` |
| Anthropic Claude | `claude`, `anthropic` | `ANTHROPIC_API_KEY` |
| OpenAI-compatible / Codex | `codex`, `openai` | `OPENAI_API_KEY` |
| Gemini | `gemini` | `GEMINI_API_KEY` |

If you use a custom gateway, pass `--llm-api-base`. If your key is in a different environment variable, pass `--llm-api-key-env`. The same fields can be set in `auto_tiktok_orchestrator/config.example.json`.

### Agent Video Styling Defaults

The agent can override these MoneyPrinterTurbo options when planning a video:

- `voice_name`, `voice_rate`, `voice_volume`
- `bgm_type`, `bgm_file`, `bgm_volume`
- `font_name`, `font_size`, `text_fore_color`, `text_background_color`
- `subtitle_position`, `custom_position`, `stroke_color`, `stroke_width`
- `intro_video_file`, `outro_video_file` for optional local intro/outro clips

Set safe defaults in your config file when you want the agent to stay close to a known style:

```json
{
  "default_video_language": "English",
  "default_voice_name": "en-US-JennyNeural-Female",
  "default_bgm_type": "random",
  "default_font_size": 60,
  "default_text_fore_color": "#FFFFFF",
  "default_stroke_color": "#000000",
  "default_intro_video_file": "brand-intro.mp4",
  "default_outro_video_file": "brand-outro.mp4"
}
```

Intro/outro files must be uploaded to or placed in `MoneyPrinterTurbo/storage/local_videos`; use the file name in config or in an agent prompt. The agent keeps these fields empty unless a default is configured or the prompt explicitly names a local intro/outro file.

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

Before uploading, the orchestrator always shows an interactive verification screen with the selected account, generated video path, title, caption, hashtags, and review questions. Publishing only continues after you answer `yes` to every question and confirm the final publish prompt.

Agent mode supports the same upload gate:

```bash
PYTHONPATH=. python3 -m auto_tiktok_orchestrator.cli agent \
  --prompt "Create a high-retention TikTok teaching one English idiom" \
  --publish \
  --account "your_username"
```

### Multiple TikTok Accounts

Log in once per TikTok account. Each login creates a cookie file named `TiktokAutoUploader/CookiesDir/tiktok_session-<username>.cookie`.

```bash
cd TiktokAutoUploader
python3 cli.py login -n brand_account
python3 cli.py login -n personal_account
```

When `--publish` is used, the orchestrator discovers accounts from `CookiesDir` plus any `tiktok_accounts` configured in JSON. If multiple accounts are available and you do not pass `--tiktok-username` or `--account`, it asks you to pick one before upload.

```json
{
  "tiktok_accounts": ["brand_account", "personal_account"],
  "default_tiktok_username": "brand_account"
}
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

## Best Saudi Arabia Posting Times From UTC+7

If you are scheduling from a `UTC+7` timezone for a Saudi Arabia-focused TikTok audience, Saudi Arabia uses Arabia Standard Time (`UTC+3`), so it is 4 hours behind `UTC+7`. Start with these `UTC+7` posting windows:

| UTC+7 Time | Saudi Arabia Audience Window | Notes |
| --- | --- | --- |
| `12:00 PM - 2:00 PM` | Saudi morning, `8:00 AM - 10:00 AM` | Good commute / early scroll window |
| `4:00 PM - 6:00 PM` | Saudi midday, `12:00 PM - 2:00 PM` | Useful lunch-break test window |
| `11:00 PM - 3:00 AM` | Saudi evening, `7:00 PM - 11:00 PM` | Strong primary window after work/school |
| `3:00 AM - 5:00 AM` | Saudi late night, `11:00 PM - 1:00 AM` | Optional test slot for late-night scrollers |

Recommended starting schedule:

```text
2 posts/day: 1:00 PM and 12:30 AM UTC+7
3 posts/day: 1:00 PM, 5:00 PM, and 12:30 AM UTC+7
4 posts/day test: 1:00 PM, 5:00 PM, 12:30 AM, and 4:00 AM UTC+7
```

For Saudi Arabia, prioritize evening tests from Sunday through Thursday and include Friday/Saturday late-evening slots. Track results for at least 2 weeks, then keep the slots with the highest Saudi viewer percentage, engagement, completion rate, and app conversions.

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
auto_tiktok_orchestrator/cli.py                 CLI entrypoint, one-shot agent, and chat mode
auto_tiktok_orchestrator/pipeline.py            End-to-end pipeline
auto_tiktok_orchestrator/moneyprinter_client.py MoneyPrinterTurbo API client
auto_tiktok_orchestrator/agent_planner.py       Agent video planning and upload questions
auto_tiktok_orchestrator/llm_provider.py        Direct Claude/OpenAI/Gemini provider adapters
auto_tiktok_orchestrator/metadata.py            Caption/hashtag LLM helpers
auto_tiktok_orchestrator/dedupe_store.py        SQLite duplicate prevention
auto_tiktok_orchestrator/tiktok_cli.py          TikTokAutoUploader CLI adapter and account discovery
auto_tiktok_orchestrator/config.example.json    Example orchestrator config
```
