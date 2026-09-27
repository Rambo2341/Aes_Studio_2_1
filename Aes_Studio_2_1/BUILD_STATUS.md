# Aes Studio 2.2 Build Status

Validated headlessly on Linux / Python 3.11 (`tests/test_core.py`, 18 tests, all passing):

- Agent tool loop against an OpenAI-compatible server (real HTTP) — PASS
- Step-budget status report (no raw tool call as final answer) — PASS
- Ask mode without UI refuses write tools — PASS
- Destructive command block — PASS
- run_python, remember/recall — PASS
- learn_topic -> knowledge + memory — PASS
- Autopilot goal -> reviewer DONE -> report file — PASS
- Screenshot marker -> OpenAI image_url / Claude image block conversion — PASS
- Hub token auth, /v1/goals, /v1/agent gate — PASS
- Upgrade of a 2.1 database (new columns, token rotation, identity upgrade with .bak) — PASS (manual)

Not verified here: the Tk GUI (no display/tkinter in the build container — syntax-checked only), real mouse/keyboard/screenshot on Windows, live Claude/Ollama/DeepSeek calls (need keys / local servers).

---

# Aes Studio 2.1 Build Status

Validated in the build environment:

- Python source compilation: PASS
- Database migration/seed for 2.1.0: PASS
- `Aes 2.1 Local` profile creation: PASS
- SOUL / IDENTITY / USER template deployment: PASS
- Identity injection into agent system context: PASS
- AGENT framework injection: PASS
- Specialist role registration: PASS
- Tool registry includes web search, durable memory, Blender, Unity, Roblox and delegation: PASS
- Demo agent loop + real file-list tool execution: PASS
- Ask / Auto / Full access permission-state persistence: PASS
- Aes logo runtime loading: PASS
- Desktop UI startup under a virtual 1920x1080 display: PASS
- UI preview capture: PASS

Not built inside this Linux environment:

- Native Windows `AesStudio.exe`. Run `build_exe.bat` on Windows or use the included GitHub Actions Windows workflow.
- A third-party/local GGUF checkpoint is not bundled. Select your own legally usable model in Models.
