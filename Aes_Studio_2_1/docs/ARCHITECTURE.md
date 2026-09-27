# Aes 2.0 Architecture

```text
Aes Studio UI
   |
   +-- Conversations / Projects / Settings
   |
   v
Aes Agent Engine
   |-- Context Builder
   |    |-- recent turns
   |    |-- compacted earlier state
   |    |-- long-term memory
   |    |-- private knowledge retrieval
   |    `-- relevant skills
   |
   |-- Local Model Runtime
   |    |-- Demo runtime
   |    `-- llama.cpp GGUF runtime
   |
   |-- Agent Loop
   |    model -> tool_call -> permission -> execute -> tool_result -> model
   |
   |-- Sub-agents
   |    |-- Explore (read-only)
   |    |-- Plan (read-only)
   |    `-- Review (read-only)
   |
   `-- Tool Registry
        |-- filesystem/search
        |-- command + git
        |-- task ledger
        |-- network fetch
        |-- computer use
        |-- Blender
        |-- Unity
        `-- Roblox/Rojo

Data layer (SQLite)
   |-- conversations/messages
   |-- projects
   |-- model profiles
   |-- memory
   |-- knowledge chunks + FTS
   |-- skills
   |-- tool policies + audit log
   |-- feedback + training examples
   |-- eval runs + candidates
   `-- release registry

Aes Model Factory
   approved examples -> JSONL -> LoRA/SFT -> candidate -> evals -> owner publish
```

## Why this architecture

A strong agent is more than an LLM. The model supplies reasoning/language capability; the agent harness supplies persistent state, tools, permissions, project boundaries, verification and repeatable workflows.

The implementation deliberately separates:

- **Model weights** from the **Aes agent harness**.
- **Owner tools** from the **public Hub**.
- **Training candidates** from **published versions**.
- **Read-only sub-agents** from agents allowed to modify state.
- **Private knowledge** from the model's permanent weights.

## Tool protocol

Local models do not all implement the same vendor-specific function-calling API, so Aes uses a model-agnostic text protocol:

```xml
<tool_call>{"name":"read_file","arguments":{"path":"src/main.py"}}</tool_call>
```

Aes executes the tool only after the permission engine allows it, then appends a `<tool_result>` message and continues the loop.

## Context management

Recent turns remain verbatim. When conversations become long, older turns can be compacted into a faithful state summary containing goals, decisions, constraints, paths, errors, fixes and unresolved tasks. This keeps local-model context usage manageable.

## Projects and checkpoints

A project selects the active workspace root. File tools are restricted to that root. Before `write_file` or `replace_text` changes an existing file, Aes creates a timestamped backup under `.aes_backups/` inside the workspace.
