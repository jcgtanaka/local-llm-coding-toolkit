#!/usr/bin/env python3
"""Dispatch a minor, big-input/small-output task to a local Ollama model.

This is the dispatcher a coding agent (or a human) calls to actually run a
delegated subtask, as opposed to benchmark_model.py, which is only for
measuring speed and finding a safe context-window ceiling ahead of time.
Adapt the MODEL_CTX table below with the ceilings you found by running
../../benchmark/benchmark_model.py on your own hardware.

Usage:
  ask_local.py --model <name> --predict 400 [--file input.txt | --stdin]

Prints a JSON object to stdout:
  {"response": str, "prompt_tokens": int, "gen_tokens": int,
   "prompt_tok_s": float, "gen_tok_s": float, "num_ctx": int,
   "truncated": bool}

Exits non-zero (and prints a warning to stderr) if the model's reported
prompt-token count is suspiciously smaller than the input actually sent,
which is the signature of the runtime silently truncating the prompt to
fit num_ctx. Treat that as a failed call, never as a partial answer to
salvage. See ../../docs/context-window-pitfalls.md for why this check
exists.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

URL = "http://localhost:11434/api/generate"

# Fill this in with the ceilings you measured on your own machine using
# benchmark/benchmark_model.py. Past these, the model spills off the GPU
# and generation speed can collapse by 10-20x with no error. Values below
# are placeholders only; do not trust them without benchmarking your own
# hardware.
MODEL_CTX = {
    # "<your-model-name>": <safe-num-ctx-from-benchmark>,
}

# Rough chars-per-token used only to sanity-check truncation; not exact.
CHARS_PER_TOKEN = 3.5


def call_ollama(model: str, prompt: str, num_ctx: int, num_predict: int) -> dict:
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0},
    }
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        if "think" in body and "think" in detail.lower():
            body.pop("think")
            req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)
        raise RuntimeError(f"Ollama HTTP error: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach Ollama at {URL} ({e}). Is it running?") from e


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="model name as known to Ollama")
    ap.add_argument("--predict", type=int, default=400, help="max output tokens")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="path to a text file holding the full prompt")
    src.add_argument("--stdin", action="store_true", help="read the full prompt from stdin")
    ap.add_argument("--num-ctx", type=int, default=None, help="override the model's configured context window")
    args = ap.parse_args()

    if args.num_ctx is None and args.model not in MODEL_CTX:
        print(
            f"No configured context ceiling for '{args.model}'. Either pass --num-ctx "
            "explicitly, or add an entry to MODEL_CTX after benchmarking this model with "
            "benchmark/benchmark_model.py.",
            file=sys.stderr,
        )
        return 2

    prompt = sys.stdin.read() if args.stdin else open(args.file, encoding="utf-8").read()
    num_ctx = args.num_ctx or MODEL_CTX[args.model]

    result = call_ollama(args.model, prompt, num_ctx, args.predict)

    prompt_tokens = result.get("prompt_eval_count", 0)
    gen_tokens = result.get("eval_count", 0)
    prompt_dur = result.get("prompt_eval_duration", 1) / 1e9
    gen_dur = result.get("eval_duration", 1) / 1e9

    expected_min_tokens = len(prompt) / CHARS_PER_TOKEN * 0.5  # generous lower bound
    truncated = prompt_tokens < expected_min_tokens and len(prompt) / CHARS_PER_TOKEN > num_ctx * 0.9

    out = {
        "response": result.get("response", ""),
        "prompt_tokens": prompt_tokens,
        "gen_tokens": gen_tokens,
        "prompt_tok_s": round(prompt_tokens / prompt_dur, 1) if prompt_dur else None,
        "gen_tok_s": round(gen_tokens / gen_dur, 1) if gen_dur else None,
        "num_ctx": num_ctx,
        "truncated": truncated,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if truncated:
        print(
            f"WARNING: prompt_tokens={prompt_tokens} looks truncated for an input of "
            f"~{len(prompt)} chars at num_ctx={num_ctx}. Raise --num-ctx (after re-checking "
            "the GPU-offload cliff) or shrink the input.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
