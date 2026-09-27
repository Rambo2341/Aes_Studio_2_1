# Aes Agent OS 2.1

Aes 2.1 turns the desktop app from a chat shell into an agent workstation.

## Operating framework

For substantial tasks, Aes follows five stages inspired by practical agent-building patterns:

1. **Aim** — define the outcome and a measurable Definition of Done.
2. **Identity** — load `SOUL.md`, `IDENTITY.md`, and `USER.md`.
3. **Equip** — retrieve only the context, tools, memory, project files, and sources needed for the task.
4. **Narrow** — keep the manager context clean by delegating focused lanes to specialist agents.
5. **Trust** — run under the owner's selected permission mode and verify the work before claiming success.

The execution loop is:

`diagnose -> assemble -> act -> assess -> repair -> verify`

## Specialist agents

The main Aes agent can delegate to:

- `explore` — read-heavy project investigation
- `plan` — architecture and implementation planning
- `research` — web/source research
- `code` — implementation, builds, tests, Git diff
- `blender` — Blender/Python/3D workflows
- `unity` — Unity project changes and batch execution
- `roblox` — Luau/Rojo project workflows
- `review` — independent verification and regression checks

Each specialist is intentionally narrower than the manager agent.

## Identity files

The editable owner copy is stored under the Aes data directory:

- `SOUL.md` — behavior, values, communication and learning philosophy
- `IDENTITY.md` — role, architecture, capabilities and operating model
- `USER.md` — owner preferences, goals and working style

These files are injected into the agent's system context at runtime.

## Trust modes

- **Ask** — every non-read-only action requests approval.
- **Auto** — uses the configured per-tool policies.
- **Full access** — skips approval prompts; internal hard destructive-command blocks still remain active.

The active trust mode is visible in the Chat toolbar.

## Learning from the web

Aes now has a `web_search` tool plus `fetch_url`. Search/page content is always treated as untrusted data. Verified durable lessons can be stored through the `remember` tool, which writes to Aes long-term memory according to the active permission mode.

## Inspiration

The workflow was adapted from the concepts in Dan Martell's public guide:

`https://www.youtube.com/watch?v=Bm84BAtOfQw`

Aes uses an original clean-room implementation rather than copying another agent product's source code.
