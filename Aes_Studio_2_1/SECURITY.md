# Aes Owner Control & Security

Aes can control files, commands and the desktop, so owner control is part of the architecture rather than a prompt-only promise.

## Permission modes

Every tool has one of three policies:

- **Allow** — execute without a popup.
- **Ask** — Aes Studio requests owner confirmation for every call.
- **Deny** — execution is blocked.

Read-only tools default to Allow. File writes, commands, network access and computer control default to Ask. New system-level tools should default to Deny.

## Workspace containment

File read/write/search operations resolve paths against the selected project workspace and reject path traversal outside it. Existing files are backed up before Aes overwrites or exact-replaces content.

## Command execution

Commands run without `shell=True`. Several destructive system command patterns are blocked in code. This is a guardrail, not a perfect sandbox. For untrusted workloads, run Aes inside a disposable VM/container and keep owner policies on Ask/Deny.

## Public Aes Hub

The Hub intentionally exposes only plain model chat and no owner filesystem/desktop tools. It binds to localhost by default and uses a bearer token. Internet deployment needs a production reverse proxy, HTTPS, account isolation, rate limits, monitoring and secret management.

## Self-improvement

Auto-evolve can **stage** a candidate; it cannot grant itself additional permissions or silently publish a new model version. Owner review remains the release boundary.
