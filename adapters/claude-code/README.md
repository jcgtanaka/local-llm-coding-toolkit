# Claude Code adapter

This adapter teaches Claude Code, via a `SKILL.md`, when and how to delegate
minor, big-input/small-output subtasks to a local Ollama model instead of
doing them itself, and it ships a small `ask_local.py` dispatcher script
adapted from the request-building logic in `../../benchmark/benchmark_model.py`
to actually make the call.

To install it, copy this whole folder into a project as
`.claude/skills/local-model-offload/` (or any skill name you prefer), then
fill in the per-model context ceilings in `SKILL.md` after running the
benchmark script on your own hardware.

This repository currently ships only this one adapter. Other coding agents
(Cursor, Aider, plain scripts, or anything else) can follow the same shape:
a small dispatcher script plus a verification step, with no agent-specific
magic required. Contributions adding adapters for other agents are welcome.
