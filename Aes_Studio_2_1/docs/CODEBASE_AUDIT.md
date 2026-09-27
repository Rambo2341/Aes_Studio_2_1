# Aes Studio codebase audit (2.1 → 2.2)

Scope: every module under `aes/`, identity files, skills, trainer, build scripts. Findings are prioritised; status reflects this branch.

| # | Pri | Finding | Status |
|---|---|---|---|
| 1 | P0 | Hub default token `change-me` accepted by the API | Fixed: random token generated and migrated; constant-time compare |
| 2 | P0 | No way to stop a running agent task; tool subprocesses could run up to 10 min unkillable | Fixed: `AgentEngine.cancel()`, `ToolRegistry.cancel_event`, process-tree kill (`_exec`) |
| 3 | P0 | Agent loop could end with a raw `<tool_call>` as the final answer when the step budget ran out | Fixed: honest status report |
| 4 | P1 | Only demo/llama.cpp runtimes; no streaming | Fixed: OpenAI-compatible (Ollama/LM Studio/vLLM) + optional cloud adapters; token streaming |
| 5 | P1 | `fetch_url` returned raw HTML | Fixed: readable text, PDFs, optional rendered browser |
| 6 | P1 | No record of which model produced an answer | Fixed: run_id, runtime and model id stored in message meta; audit log per run |
| 7 | P1 | Repeated identical failing tool calls not detected | Fixed: warning injected after 3 identical calls |
| 8 | P1 | UI disliked by owner; Tk limits RTL/markdown | Fixed: new PySide6 UI (ADR 0001) |
| 9 | P1 | Default brain was an empty GGUF profile (nothing worked out of the box) | Fixed: `Aes Local` (Ollama, free) is the default; `--doctor` recommends models for the real GPU |
| 10 | P2 | Folder import could duplicate documents | Fixed for `library_import` (source-path dedupe); single-file import still re-imports |
| 11 | P2 | Memory records have no provenance/confidence/scope fields | Open |
| 12 | P2 | Retrieval is lexical only (FTS5 + keyword); no local embeddings | Open |
| 13 | P2 | Task runs are not resumable after an app restart (Autopilot goals are) | Open |
| 14 | P2 | Tool schemas are informal dicts, not JSON Schema with validation | Open |
| 15 | P3 | Old demo profiles (Aes 1.0/1.1 Demo) clutter the model list | Open (kept for compatibility) |
