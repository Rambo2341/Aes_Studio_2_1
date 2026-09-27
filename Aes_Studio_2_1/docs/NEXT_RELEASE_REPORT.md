# Aes Studio 2.2 — Release report

Honest status of this development cycle against `Aes_Opus_5_5_Master_Build_Prompt.md`. "Tested" means an automated
test in `tests/test_core.py` (23 tests, all passing on Linux/Python 3.11) unless stated otherwise.

| Requirement | Implementation | Test | Status | Remaining limitation |
|---|---|---|---|---|
| Local-first, no paid API needed | `Aes Local` profile (Ollama, own GPU) is the default; cloud profiles marked ☁ paid | `test_hardware_recommendation_and_cloud_flag` | ✅ | Owner must install Ollama + pull a model |
| Hardware-aware recommendations | `aes/hardware.py`, `python main.py --doctor`, Brains page | same | ✅ | NVIDIA only (nvidia-smi) |
| New professional UI | `aes/qt_ui.py` (PySide6): rail, chats (search/pin/rename/export), composer with model+trust, activity/sources/goals panel, Training Center, Library, Brains, Permissions, Settings (identity editor) | `test_qt_interface_smoke` + offscreen screenshots in `docs/screenshots/` | ✅ | No Monaco editor/diff viewer yet; code blocks are plain monospace |
| Arabic/English + RTL | UI language switch, `Qt.RightToLeft`, per-message direction | screenshots `ui_ar_*` | ✅ | Not tested on a real Windows display |
| Stop / cancellation | `AgentEngine.cancel()`, `ToolRegistry.cancel_event`, process-tree kill | `test_stop_cancels_running_task_and_kills_process` | ✅ | Model call in progress finishes its current request before stopping |
| Streaming | token streaming for llama.cpp, OpenAI-compatible, Claude | `test_streaming_tokens_reach_listeners` | ✅ | — |
| Tool activity timeline | agent events (`tool_start/tool_end` with duration/status) | streaming test + UI smoke | ✅ | Not persisted as a separate table (kept in message meta + audit log) |
| Model traceability | run_id, runtime, model id in message meta; audit log per run | agent tests | ✅ | No model file hash yet |
| Daily training by hours | `DailyTrainer.run(hours=…)`, Training Center, `run_daily_training.bat`, `install_daily_task.bat` | `test_daily_cycle_report` | ✅ | Real multi-hour run not executed here |
| Verified self-training data | computer-graded drills (`aes/drills.py`) | `test_drill_grading` | ✅ | Drill bank is small (11 generators, 12 katas) |
| Research Mode | `aes/research.py` | `test_research_mode_expands_and_archives` | ✅ | Live web/YouTube blocked in the build container; tested with mocks |
| Documents / folders / videos | `read_document`, `library_import`, `video_transcript`, `learn_from_video` | tests with local files + mocks | ✅ | Videos: transcripts only (no frame understanding) |
| Brain training (LoRA/QLoRA) | `trainer/train_lora.py --qlora`, `trainer/cloud_train.sh`, automatic candidate in daily training (off by default) | — | ⚠️ not executed | Needs a CUDA GPU; not run in this environment |
| Candidate promotion gate | candidates stored as `needs_eval`; never auto-promoted | — | ✅ by design | Promotion UI still minimal |
| Permissions Ask/Auto/Full | existing manager + Permissions page | `test_ask_mode_without_ui_denies_writes` | ✅ | No per-project grants yet |
| Public Hub isolation | `/v1/chat` has no tools; `/v1/agent` off by default | `test_hub_auth_and_goals` | ✅ | No multi-user accounts / rate limits |
| Structured memory (provenance, confidence, scope) | — | — | ❌ open | see `docs/CODEBASE_AUDIT.md` #11 |
| Local embeddings / hybrid retrieval | — | — | ❌ open | lexical FTS5 only |
| Task resume after restart | Autopilot goals survive restarts | autopilot test | ⚠️ partial | chat task runs do not resume |
| Windows EXE / installer | `AesStudio.spec`, `build_exe.bat` | — | ⚠️ not built here | Must be built on Windows |

## Commands
```
run_windows.bat                      # install + start the new UI
python main.py --doctor              # check GPU / Ollama / tools, get free model recommendations
python main.py --daily --hours 3     # one training day
install_daily_task.bat 02:00         # train every night
python main.py --research "Master Blender" --hours 2
python -m unittest discover -s tests -v
build_exe.bat                        # Windows build
```
