---
name: local-model-offload
description: >
  Offload minor, big-input/small-output subtasks (extraction, tagging,
  sorting, first-pass summarization of large text) to a local Ollama model
  instead of spending cloud tokens on them. Trigger whenever a task is
  mechanical, non-reasoning, and involves large input relative to the needed
  output. Do not trigger for code changes, anything needing judgment, or
  small inputs.
---

# Local model offload

A local Ollama model is available on this machine as a cheap worker for
minor tasks. The cloud model (you) stays the thinker: it decides what to
delegate, writes the prompt, and **always verifies the output before using
it**. The local model never ships unverified output into code, published
documents, or any decision.

## When to use this

Use it only when BOTH are true:

- The task is mechanical: extract a value, list/tag/sort many items,
  produce a first-pass draft to be reviewed, summarize a large log or file
  into a few lines.
- Input is large relative to output. The whole point is saving cloud
  tokens: a small edit costs more in the prompt than it would save. See
  [why-route-to-local-models](https://github.com/jcgtanaka/local-llm-coding-toolkit/blob/main/docs/why-route-to-local-models.md)
  for the full reasoning and a good-vs-bad task table.

Never use it for:

- High-stakes or irreversible code, secrets, or anything where a wrong
  answer is costly.
- Anything requiring multi-step reasoning or judgment.
- Small inputs where writing the delegation prompt costs as much as doing
  the task directly.

## Per-model context ceilings

The single source of truth is the `MODEL_CTX` dict at the top of
`ask_local.py` (in this folder). Read it there; this file deliberately does
not repeat the numbers so they cannot drift. If a model has no entry, pass
`--num-ctx` explicitly or add an entry after measuring it with the
[benchmark](https://github.com/jcgtanaka/local-llm-coding-toolkit/blob/main/benchmark/README.md).
Why ceilings matter:
[context-window-pitfalls](https://github.com/jcgtanaka/local-llm-coding-toolkit/blob/main/docs/context-window-pitfalls.md).

Default to the smallest model that passes your own spot-checks for the task
shape you care about; do not assume a larger model is automatically safer
(see
[verification-before-trust](https://github.com/jcgtanaka/local-llm-coding-toolkit/blob/main/docs/verification-before-trust.md)).

## How to invoke it

Call the dispatcher by its installed path, from the project root (see the
adapter README for install steps). Use `python`, or `py -3` on Windows, if
`python3` is not available:

```
python3 .claude/skills/local-model-offload/ask_local.py --model <your-model-name> --predict 300 --file <path-to-prompt.txt>
```

Or pipe a prompt through stdin:

```
echo "<prompt text>" | python3 .claude/skills/local-model-offload/ask_local.py --model <your-model-name> --predict 300 --stdin
```

(Use the folder name you installed under, and `~/.claude/skills/...` for a
user-level install.)

`ask_local.py` is a standalone copy of the call logic in the repository's
benchmark script (it does not import it); the two are kept in sync by hand.

The script prints JSON with `response`, `prompt_tokens`, `gen_tok_s`,
`truncated`, `truncation_status`, `done_reason`, and `cut_by_predict`.

Exit codes: `0` ok, `2` usage/config (for example no ceiling for the
model), `3` server unreachable, HTTP error, timeout or bad JSON, `4`
truncated, unverified, or input too large for the window (preflight
refusal; `--force` overrides). Treat any non-zero exit or `truncated: true`
as a failed call, never as a partial answer to salvage. If `cut_by_predict`
is true the answer hit the `--predict` limit and may be incomplete.

## Mandatory verification step

After every call:

1. Check the exit code and the `truncated` flag first.
2. Spot-check the response against the source input (quote or line-number
   claims, counts, extracted values) before using it downstream.
3. If the task has any ambiguity the local model might have guessed
   through, do not trust the output; do the task directly instead.

This verification is the cloud model's responsibility, not something to
script away.
