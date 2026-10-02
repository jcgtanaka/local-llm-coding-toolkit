# Claude Code adapter

This adapter teaches Claude Code, via a `SKILL.md`, when and how to delegate
minor, big-input/small-output subtasks to a local Ollama model instead of
doing them itself, and it ships a standalone `ask_local.py` dispatcher
script to make the call. `ask_local.py` intentionally duplicates the call
logic from `../../benchmark/benchmark_model.py` so it can be copied alone;
keep the two in sync.

## Install

Only this adapter folder gets copied, so everything it needs is inside it
(links in `SKILL.md` to the rest of the repo are absolute GitHub URLs).

1. Copy this folder to one of:
   - `.claude/skills/<name>/` inside a project (one project), or
   - `~/.claude/skills/<name>/` (all projects),

   for example `<name>` = `local-model-offload`.
2. Edit `MODEL_CTX` at the top of the copied `ask_local.py` with the
   context ceilings you measured using the benchmark. `MODEL_CTX` is the
   single source of truth for ceilings; `SKILL.md` only points to it.
3. Invoke the script by its installed path. Claude Code runs commands from
   the project root, so for a project install use:

   ```
   python3 .claude/skills/<name>/ask_local.py --model <model-name> --predict 300 --file prompt.txt
   ```

   On Windows `python3` may be `python` or `py -3`.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | ok |
| 2 | usage or configuration error (no ceiling for the model, bad arguments, unreadable input file, `--num-ctx` <= 0) |
| 3 | cannot reach the server, HTTP error, timeout, or invalid JSON reply |
| 4 | truncated or unverified result, or preflight refusal (estimated prompt above 90% of the window; `--force` overrides) |

Other options: `--host` (default `$OLLAMA_HOST` or `http://localhost:11434`),
`--timeout` (default 600 seconds), `--num-ctx`, `--predict`. The JSON output
includes `done_reason` and `cut_by_predict` (true when generation stopped at
the `--predict` limit, so the answer may be incomplete).

## Model tier routing (optional)

See `model-routing.md` in this folder for an optional, separate topic:
routing across cloud model tiers inside Claude Code. It is not part of local
offload.

This repository currently ships only this one adapter. Other coding agents
can follow the same shape: a small dispatcher script plus a verification
step, with no agent-specific magic required. Contributions adding adapters
for other agents are welcome.
