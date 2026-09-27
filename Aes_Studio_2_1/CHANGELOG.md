# Changelog

## Aes Studio 2.2.0 — Brain & Autopilot

- **Daily training** (`--daily`, `run_daily_training.bat`, `install_daily_task.bat`, GUI button): curriculum progression across all tracks, computer-graded maths/science/code drills, harvesting of verified examples, evals, daily score trend, optional automatic LoRA candidate once enough data exists.

- **Learning from everything:** `read_document` (local PDFs/magazines/books page by page), `library_import` (whole folders), `fetch_url` reads online PDFs and `render=true` uses a real browser (Playwright), `video_transcript` / `learn_from_video` (YouTube subtitles, yt-dlp, faster-whisper for local files).
- **Training curriculum:** `curriculum/aes_curriculum.json` (41 units, primary → specialist); `--curriculum`, **Load training plan** button; video goals (`--video`).
- `docs/TRAINING_PLAN.md`: nightly study → data collection → LoRA Aes 3.0 → evals.

- **Real brains:** new `openai_compat` runtime (Ollama, LM Studio, llama.cpp server, vLLM, DeepSeek, OpenRouter, …) and `anthropic` runtime (Claude via the official SDK, adaptive thinking, streaming). Seeded profiles: `Aes 2.2 Claude`, `Aes 2.2 Ollama`, `Aes 2.2 LM Studio`, `Aes 2.2 DeepSeek`. API keys can be stored as `env:VARIABLE`.
- **Vision + full computer control:** `look_at_screen` (screenshot the model can actually see), `mouse_move/drag/scroll`, double-click, `key_press` hotkeys, Arabic-safe typing through the clipboard, `clipboard_get/set`, `open_url` (Chrome), `screen_info`. pyautogui fail-safe enabled.
- **Autopilot:** goal queue + strict reviewer rounds + morning report in `<data>/reports/`. GUI page, `run_autopilot.bat`, `--autopilot`, remote `/v1/goals`. Emergency stop via Stop button or a `STOP` file.
- **Self-learning:** `learn_topic` (search → read several sources → cited study notes → knowledge + memory), `recall`, `knowledge_add`, `goal_add`, `self_status`, `run_python` for verifying maths/science.
- **Self-knowledge:** a live SELF MODEL block (version, brain, storage, counts) is injected every session; identity files rewritten (SOUL / IDENTITY / USER, version-tagged; old copies kept as `.bak`).
- **Dedicated memory drive:** `AES_DATA_DIR` or `aes_data_location.txt`.
- **Agent loop:** step budget raised to a setting (default 30); when the budget runs out Aes now returns an honest status report instead of a raw tool call; only the latest screenshot is sent as an image.
- **Owner API:** random Hub token generated (legacy `change-me` replaced), constant-time token check, optional `/v1/agent` (off by default).
- **Headless CLI:** `python main.py --chat | --ask | --goal | --learn | --goals | --autopilot | --api | --status`.
- New skills: Programming Languages Mastery, Self-Learning Curriculum, Math & Proof, Computer Operator; deeper Roblox Creator.
- `fetch_url` returns readable text instead of raw HTML; `run_command` supports `shell=true`.
- Headless test suite: `python -m unittest discover -s tests -v`.

## Aes Studio 2.1.0 — Agent OS

- Added the custom Aes Studio blue/cyan logo and Windows icon.
- Redesigned the Chat workspace with a narrow icon rail, conversation sidebar, central work area and right-side agent context/activity panel.
- Added visible `Ask`, `Auto`, and `Full access` trust modes.
- Added runtime loading of `SOUL.md`, `IDENTITY.md`, and `USER.md`.
- Added the Aes AGENT framework: Aim, Identity, Equip, Narrow, Trust.
- Added Definition-of-Done guidance for substantial tasks.
- Expanded specialist delegation roles: Explore, Plan, Research, Code, Blender, Unity, Roblox and Review.
- Added public-web `web_search` and durable `remember` tools.
- Upgraded context compaction to preserve completion criteria.
- Added the `Aes 2.1 Local` model profile with a larger default context and manager-agent prompt.
- Bundled identity templates and Skills in the Windows build.
- Preserved hard destructive-command blocks even in Full access mode.

## Aes Studio 2.0.1

- Multi-tool batches for independent reads.
- Explicit untrusted tool-result handling.
- Static/dynamic context boundary.
- Slash workflows for plan, code, research, diff, tasks, memory and skills.
