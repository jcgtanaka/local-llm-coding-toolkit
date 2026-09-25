---
name: local-model-offload
description: >
  Offload minor, big-input/small-output subtasks (extraction, tagging,
  sorting, first-pass summarization of large text) to a local Ollama model
  instead of spending cloud tokens on them. Trigger whenever a task in this
  project is mechanical, non-reasoning, and involves large input relative to
  the needed output. Do not trigger for code changes, anything needing
  judgment, or small inputs.
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
  the parent repo's `docs/why-route-to-local-models.md` for the full
  reasoning and a good-vs-bad task table.

Never use it for:

- Any change to production, live, or safety/financial-logic-relevant code.
- Anything requiring multi-step reasoning or judgment.
- Small inputs where writing the delegation prompt costs as much as doing
  the task directly.

## Per-model context ceilings (fill in after benchmarking)

Run `../../benchmark/benchmark_model.py` on your own machine before relying
on any of these numbers. Past a model's ceiling, generation speed can
collapse by 10-20x with no error (see
`../../docs/context-window-pitfalls.md`). This table is a placeholder: fill
it in with your own measured values.

| Model | Safe num_ctx | Notes |
|---|---:|---|
| `<your-model-name>` | `<measured-ceiling>` | `<any notes from your benchmark run>` |

Default to the smallest model that passes your own spot-checks for the task
shape you care about; do not assume a larger model is automatically safer
(see `../../docs/verification-before-trust.md`).

## How to invoke it

Call the dispatcher script (adapt `ask_local.py` in this folder, which
reuses the request-building logic from `../../benchmark/benchmark_model.py`)
via Bash:

```
python3 ask_local.py --model <your-model-name> --predict 300 --file <path-to-prompt.txt>
```

Or pipe a prompt through stdin:

```
echo "<prompt text>" | python3 ask_local.py --model <your-model-name> --predict 300 --stdin
```

The script prints JSON with `response`, `prompt_tokens`, `gen_tok_s`, and a
`truncated` flag. It exits non-zero and prints a warning to stderr if the
model's reported prompt-token count is suspiciously low for the input
size, which is the signature of the runtime silently truncating input.
Treat any `truncated: true` or non-zero exit as a failed call, never as a
partial answer to salvage.

## Mandatory verification step

After every call:

1. Check the exit code and the `truncated` flag first.
2. Spot-check the response against the source input (quote or line-number
   claims, counts, extracted values) before using it downstream.
3. If the task has any ambiguity the local model might have guessed
   through, do not trust the output; do the task directly instead.

This verification is the cloud model's responsibility, not something to
script away.

## Formatting and language

Write in English by default: prompts sent to the local model, any file
created or modified, and any output kept downstream. Do not use em dashes;
use a comma, colon, or parentheses instead.
