# benchmark_model.py

Finds the real speed cliff of a local Ollama model on your own hardware,
instead of guessing a safe context-window size. Python 3.8+, standard
library only.

## Running it

Single model, across several context sizes:

```
python3 benchmark_model.py --model <name> --ctx 4096,8192,16384,32768
```

(`python3` may be `python` or `py -3` on Windows.)

Compare several installed models at the same context sizes:

```
python3 benchmark_model.py --compare model-a,model-b,model-c --ctx 8192,16384
```

Other flags:

- `--host`: Ollama base URL. Default is `$OLLAMA_HOST` if set (a bare
  `host:port` is accepted), else `http://localhost:11434`.
- `--predict`: max output tokens per call (default 64, kept small since this
  is a recall check, not a generation-quality test).
- `--fill`: prompt size as a fraction of each context size (default `0.85`).
  Use `1.0` or higher to overflow the window on purpose and see the
  truncation flag fire.
- `--timeout`: HTTP timeout per call in seconds (default 1800).

## Exit codes

- `0`: at least one row completed. A failure in one row (timeout, bad JSON,
  HTTP error) is recorded in that row and does not stop the sweep.
- `2`: usage error.
- `3`: every row failed (for example, the server is unreachable).

## Reading the output table

Each row is one (model, context size) combination:

- `prompt_tok/s` and `gen_tok/s`: processing and generation speed (`None`
  if the runtime did not report a duration). Watch for a sharp drop between
  two context sizes: that is the GPU-offload cliff. See
  `../docs/context-window-pitfalls.md` for what it is and how to act on it.
- `recalled_both`: whether the model recalled both facts planted in the
  synthetic prompt (one at the very start, one in the middle). A `False` at
  a context size that should comfortably fit the prompt is a warning sign.
- `truncated`: `ok`, `truncated`, or `unverified`. A row is `truncated` when
  `prompt_tokens >= num_ctx - margin` (margin is the larger of 8 tokens or
  1% of `num_ctx`), meaning the runtime filled the window and dropped the
  rest. It is `unverified` when the runtime reported no prompt-token count.
  Treat both as a failed call. Details are in
  `../docs/context-window-pitfalls.md`.
- `gpu_split`: the GPU share for the exact model name, computed from
  `size_vram / size` in Ollama's `GET /api/ps`, read right after the call.
  Reads "not detected" if the endpoint or the model entry is unavailable.
- `note`: `ERROR (below)` marks a failed row. The full error text is printed
  below the table.

## What this does NOT measure

This benchmark measures raw speed and one shallow recall check. It does
**not** measure real-world task quality: whether the model is good at your
extraction, summarization, or tagging task. A model can pass this recall
check and still produce mediocre or wrong results on your data.

Use it to find a safe, fast context-window ceiling on your hardware, then
pair it with your own spot-checks (see `../docs/verification-before-trust.md`)
before trusting the model with anything beyond mechanical, low-judgment work.
