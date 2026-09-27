# ADR 0001 — Desktop UI: PySide6 (Qt) with Tk fallback

Date: 2026-09-27 · Status: accepted

## Context
The owner did not like the Tkinter UI. The master build prompt prefers Tauri v2 + React, and allows PySide6/QML
"if it substantially reduces integration risk while delivering equivalent polish".

## Decision
Use **PySide6 (Qt Widgets)** in-process with the Python core.

- One language and one process: no Rust/Node toolchain, no IPC contract to maintain yet, and the agent core stays callable directly.
- Real threading model: agent work runs on background threads and reaches the UI through Qt signals (queued), so the window never freezes.
- Native RTL support (`Qt.RightToLeft`) for Arabic, high-DPI scaling by default on Windows, Markdown rendering in labels.
- Testable headlessly (`QT_QPA_PLATFORM=offscreen`) — screenshots and a smoke test run in CI/containers.
- PyInstaller ships official PySide6 hooks.

The Tk UI (`aes/ui.py`) stays as a fallback: `python main.py --tk-ui`, or automatically if PySide6 is missing.

## Consequences
- Adds a ~100 MB dependency to the Windows build.
- A future Tauri/React shell remains possible: the agent core already emits structured events (`AgentEngine.listeners`)
  that could be exposed over a local API.
