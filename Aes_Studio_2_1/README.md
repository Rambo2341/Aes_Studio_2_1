# Aes Studio 2.2 — Brain & Autopilot

Aes Studio is a Windows-first **private local AI agent workstation**. It is designed to run an owner-selected local GGUF model, combine it with identity files, memory, private knowledge, specialist skills and computer tools, and improve through feedback/evals fully local, or with an optional cloud brain (Claude, DeepSeek, …) that the owner chooses.

## Aes 2.2 — what's new

- **Pick a real brain** (Models page): Claude (`anthropic`), Ollama / LM Studio / DeepSeek / any OpenAI-compatible server (`openai_compat`), or a local GGUF (`llama_cpp`). Aes's intelligence is mostly the brain; Aes adds identity, memory, skills, tools, permissions and the agent loop.
- **Sees and controls the PC:** screenshots the model can see, mouse, keyboard/hotkeys, clipboard, Chrome.
- **Autopilot:** queue goals, pick Auto/Full access, press *Run Autopilot* (or `run_autopilot.bat`), sleep, read the morning report in `<data>\reports`.
- **Learns by itself:** `learn_topic` studies a subject from several web sources and stores cited notes; `recall` searches what it already knows.
- **Training plan:** `docs/TRAINING_PLAN.md` + a 41-unit curriculum (Autopilot → *Load training plan*). Reads PDFs/magazines/folders and learns from videos.
- **Its own memory drive:** rename `aes_data_location.example.txt` to `aes_data_location.txt` and write e.g. `D:\AesBrain`.
- **Owner API:** `python main.py --api` → `POST /v1/goals`, `POST /v1/agent` (enable in Settings) with `Authorization: Bearer <hub_token>`.

### Quick start (brain)

| Brain | Profile | What to do |
|---|---|---|
| Claude | `Aes 2.2 Claude` | `setx ANTHROPIC_API_KEY sk-ant-...` then restart Aes |
| Ollama (free, local) | `Aes 2.2 Ollama` | install Ollama, `ollama pull qwen2.5-coder:32b` (or any model; for screen vision use a vision model, e.g. `qwen2.5vl`) |
| LM Studio (free, local) | `Aes 2.2 LM Studio` | start the local server, put the model id in the profile |
| DeepSeek | `Aes 2.2 DeepSeek` | `setx DEEPSEEK_API_KEY ...` |

Select the profile in Chat → **Set default**. Then try: `who are you?` / `مين أنت؟`

### تشغيل سريع (عربي)
1. شغّل `run_windows.bat`.
2. من صفحة **Models** اختر العقل (Claude أو Ollama أو DeepSeek) واضغط **Test model** ثم **Set default**.
3. للشغل وأنت نايم: صفحة **Autopilot** → اكتب الهدف و"متى يعتبر خلص" → اختر **Auto** أو **Full access** → **Run Autopilot**. التقرير يطلع في مجلد `reports`.
4. لإيقاف فوري: زر **Stop** أو سوّ ملف اسمه `STOP` في مجلد بيانات Aes، أو ودّ الماوس لزاوية الشاشة.

## Aes 2.1 highlights

- **New Aes visual identity** — custom blue/cyan Aes logo, Windows icon and redesigned dark workstation UI.
- **Three identity files** — `SOUL.md`, `IDENTITY.md`, `USER.md` are loaded into the agent context every session.
- **AGENT operating framework** — Aim -> Identity -> Equip -> Narrow -> Trust.
- **Definition of Done** — substantial tasks are framed around an outcome and completion criteria instead of only steps.
- **Manager + specialist agents** — Explore, Plan, Research, Code, Blender, Unity, Roblox and Review lanes.
- **Trust control in the composer** — Ask, Auto and Full access.
- **Web learning tools** — `web_search` + `fetch_url`; external content is treated as untrusted data.
- **Durable learning** — a `remember` tool lets Aes save verified lessons/facts/procedures into long-term memory.
- **Context compaction** — older state is summarized while important goals, constraints, errors and completion criteria are preserved.
- **Projects + task ledger** — isolated project folders, instructions, tasks and tool traces.
- **Coding/3D/game tools** — filesystem, command execution, Git, Blender, Unity, Roblox/Rojo and computer-use tools.
- **Evals + Training Lab** — owner feedback can become training examples/candidates instead of uncontrolled self-modification.

## Local model profiles

The project seeds:

- `Aes 1.0 Demo`
- `Aes 1.1 Demo`
- `Aes 2.0 Local`
- `Aes 2.1 Local` — the recommended orchestration profile

Aes Studio does **not** ship a third-party checkpoint. Import a legally usable GGUF model yourself.

## Headless / terminal

```
python main.py --chat                 # talk to Aes in the terminal
python main.py --goal "Make a Roblox obby with 10 stages" --detail "Rojo project builds; checkpoints saved in DataStore"
python main.py --learn "Linear algebra fundamentals"
python main.py --autopilot --mode auto
python main.py --status
python -m unittest discover -s tests -v
```

## Run on Windows

1. Install Python 3.11 or 3.12.
2. Extract the project.
3. Run `run_windows.bat`.
4. For local inference, run `setup_local_model.bat`.
5. Open **Models**, select `Aes 2.1 Local`, browse to your `.gguf`, test it, then set it as default.

Persistent data is stored under:

`%LOCALAPPDATA%\AesStudio`

unless `AES_PORTABLE=1` is set.

## Build the EXE

Run:

`build_exe.bat`

Output:

`dist\AesStudio\AesStudio.exe`

The PyInstaller bundle includes the Aes brand assets, Skills folder, and identity templates.

## Permission modes

- **Ask** — all non-safe actions ask the owner first.
- **Auto** — follows per-tool Allow / Ask / Deny policies.
- **Full access** — skips approval prompts for maximum autonomy. The tool layer still blocks a set of obviously destructive system commands.

## Agent architecture

For complex work, the main Aes agent manages specialist lanes rather than trying to keep every discipline in one active context. See:

`docs\AGENT_OS.md`

The high-level loop is:

`diagnose -> assemble -> act -> assess -> repair -> verify`

Aes uses the requested three identity files as stable context, retrieves only relevant memory/knowledge, delegates when useful, and verifies work against a Definition of Done.

## Self-improvement

Aes improves through a controlled pipeline:

`task -> traces -> owner feedback -> memory/skill/training examples -> candidate -> evals -> owner promotion`

This makes improvement measurable and reversible instead of allowing the agent to silently rewrite its own core policies.

## Clean-room note

Aes is an original implementation. Public agent-design material and architecture references are used to learn patterns such as tool loops, context management, specialist agents and permission systems; proprietary/leaked source code is not copied into Aes.
