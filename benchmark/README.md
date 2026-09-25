# benchmark_model.py

Finds the real speed cliff of a local Ollama model on your own hardware,
instead of guessing a safe context-window size.

## Running it

Single model, across several context sizes:

```
python3 benchmark_model.py --model <name> --ctx 4096,8192,16384,32768
```

Compare several installed models at the same context sizes:

```
python3 benchmark_model.py --compare model-a,model-b,model-c --ctx 8192,16384
```

Other flags: `--host` (default `http://localhost:11434`), `--predict` (max
output tokens per call, kept small by default since this is a recall check,
not a generation-quality test).

## Reading the output table

Each row is one (model, context size) combination:

- `prompt_tok/s` and `gen_tok/s`: processing and generation speed. Watch for
  a sharp drop between two context sizes: that drop is the GPU-offload
  cliff described in `../docs/context-window-pitfalls.md`, the point where
  Ollama starts spilling part of the model off the GPU.
- `recalled_both`: whether the model correctly recalled both facts planted
  in the synthetic prompt (one at the very start, one in the middle). A
  `False` here at a context size that should comfortably fit the prompt is
  a warning sign, not just a curiosity.
- `truncated`: a heuristic flag comparing the reported prompt-token count
  against a rough estimate of the actual input size. `True` means the
  runtime likely truncated the prompt silently; treat that row as a failed
  call, not a usable result.
- `gpu_split`: what `ollama ps` reports for the model's processor split at
  that context size (for example fully on GPU, or split between CPU and
  GPU). Once this stops reading as fully on GPU, expect the speed collapse
  described above.

## What this does NOT measure

This benchmark measures raw speed and one shallow, single-fact recall
check. It does **not** measure real-world task quality: whether the model
is actually good at your extraction, summarization, or tagging task. A
model can pass this recall check and still produce mediocre or wrong
results on your specific data.

Use this benchmark to find a safe, fast context-window ceiling for a model
on your hardware. Then pair it with your own spot-checks on your actual use
case (see `../docs/verification-before-trust.md`) before trusting that
model for anything beyond mechanical, low-judgment tasks.
