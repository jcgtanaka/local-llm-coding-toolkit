#!/usr/bin/env python3
"""Benchmark a local Ollama model across context-window sizes.

Finds the real speed cliff on your own hardware for a given model, instead
of guessing: for each requested context size, it builds a synthetic prompt
that fills roughly 85% of that context, plants one fact at the very start
and one fact in the middle, asks the model to recall both, and reports
prompt-processing speed, generation speed, whether both facts were
correctly recalled, and whether Ollama kept the model fully on GPU or
spilled part of it to CPU.

This is a generalization of a dispatcher script used to route minor,
big-input/small-output subtasks to a local model in an AI coding workflow
(see the repo's docs/ and adapters/claude-code/ for the full pattern). It
uses only the Python standard library: urllib.request for the HTTP calls
and subprocess for `ollama ps`.

Usage:
  python3 benchmark_model.py --model <name> [--ctx 4096,8192,16384,32768]
                              [--host http://localhost:11434] [--predict 300]

  python3 benchmark_model.py --compare model-a,model-b --ctx 8192,16384

Exit code is always 0; failures for an individual (model, ctx) combination
are reported as a row in the table, not a hard stop, so one bad combination
does not prevent the rest of the sweep from running.
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

# Rough chars-per-token used only to size the synthetic prompt and to
# sanity-check truncation. Not exact, deliberately conservative.
CHARS_PER_TOKEN = 3.5

FACT_START = "The secret reference code stated at the very beginning is ALPHA-7429."
FACT_MIDDLE = "The secret backup code stated in the middle is BRAVO-1836."
FILLER_LINE = (
    "This is a filler line used only to occupy space in the synthetic "
    "benchmark prompt and carries no meaningful information on its own. "
)
QUESTION = (
    "\n\nQuestion: what is the secret reference code stated at the very "
    "beginning, and what is the secret backup code stated in the middle? "
    "Answer with just the two codes."
)


def build_prompt(target_chars: int) -> str:
    """Build a synthetic prompt of roughly target_chars characters, with one
    planted fact at the start and one planted fact in the middle."""
    filler_needed = max(target_chars - len(FACT_START) - len(FACT_MIDDLE) - len(QUESTION), 0)
    half = filler_needed // 2

    def filler_block(n_chars: int) -> str:
        reps = max(n_chars // len(FILLER_LINE), 1)
        return (FILLER_LINE * reps)[:n_chars]

    parts = [FACT_START, "\n\n", filler_block(half), "\n\n", FACT_MIDDLE, "\n\n", filler_block(half), QUESTION]
    return "".join(parts)


def call_ollama(host: str, model: str, prompt: str, num_ctx: int, num_predict: int) -> dict:
    url = f"{host.rstrip('/')}/api/generate"
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0},
    }
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        if "think" in body and "think" in detail.lower():
            body.pop("think")
            req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=1800) as r:
                return json.load(r)
        raise RuntimeError(f"Ollama HTTP error: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach Ollama at {url} ({e}). Is it running?") from e


def check_gpu_split(model: str) -> str:
    """Query `ollama ps` and report whether the model is 100% GPU or spilled
    to CPU. Returns a short string; falls back gracefully if unavailable."""
    try:
        out = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "not detected (ollama ps unavailable)"
    if out.returncode != 0:
        return "not detected (ollama ps failed)"
    for line in out.stdout.splitlines():
        if model.split(":")[0] in line:
            # Ollama prints a PROCESSOR column like "100% GPU" or "45%/55% CPU/GPU".
            tokens = line.split()
            for tok in tokens:
                if "%" in tok:
                    idx = tokens.index(tok)
                    return " ".join(tokens[idx:])
    return "not detected (model not in `ollama ps` output)"


def run_one(host: str, model: str, ctx: int, predict: int) -> dict:
    target_chars = int(ctx * 0.85 * CHARS_PER_TOKEN)
    prompt = build_prompt(target_chars)
    estimated_tokens = len(prompt) / CHARS_PER_TOKEN

    row = {"model": model, "ctx": ctx, "error": None}
    try:
        t0 = time.time()
        result = call_ollama(host, model, prompt, ctx, predict)
        wall = time.time() - t0
    except RuntimeError as e:
        row["error"] = str(e)
        return row

    prompt_tokens = result.get("prompt_eval_count", 0)
    gen_tokens = result.get("eval_count", 0)
    prompt_dur = result.get("prompt_eval_duration", 0) / 1e9
    gen_dur = result.get("eval_duration", 0) / 1e9
    response = result.get("response", "")

    truncated = prompt_tokens < estimated_tokens * 0.5 and estimated_tokens > ctx * 0.9
    recalled_start = "ALPHA-7429" in response
    recalled_middle = "BRAVO-1836" in response

    row.update({
        "prompt_tokens": prompt_tokens,
        "estimated_tokens": round(estimated_tokens),
        "prompt_tok_s": round(prompt_tokens / prompt_dur, 1) if prompt_dur else None,
        "gen_tok_s": round(gen_tokens / gen_dur, 1) if gen_dur else None,
        "wall_s": round(wall, 1),
        "recalled_both": recalled_start and recalled_middle,
        "truncated": truncated,
        "gpu_split": check_gpu_split(model),
    })
    return row


def print_table(rows: list) -> None:
    headers = ["model", "ctx", "prompt_tok/s", "gen_tok/s", "recalled_both", "truncated", "gpu_split", "note"]
    widths = [12, 8, 13, 10, 14, 10, 22, 30]
    print(" | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        if row.get("error"):
            values = [row["model"], str(row["ctx"]), "-", "-", "-", "-", "-", row["error"][:30]]
        else:
            values = [
                row["model"],
                str(row["ctx"]),
                str(row.get("prompt_tok_s", "-")),
                str(row.get("gen_tok_s", "-")),
                str(row.get("recalled_both", "-")),
                str(row.get("truncated", "-")),
                str(row.get("gpu_split", "-")),
                "",
            ]
        print(" | ".join(v.ljust(w) for v, w in zip(values, widths)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="single model to benchmark")
    ap.add_argument("--compare", help="comma-separated list of models to benchmark and compare")
    ap.add_argument("--ctx", default="4096,8192,16384,32768", help="comma-separated context sizes to test")
    ap.add_argument("--host", default="http://localhost:11434", help="Ollama host URL")
    ap.add_argument("--predict", type=int, default=64, help="max output tokens per call (kept small on purpose)")
    args = ap.parse_args()

    if not args.model and not args.compare:
        ap.error("pass --model <name> or --compare model1,model2,...")

    models = [m.strip() for m in args.compare.split(",")] if args.compare else [args.model]
    ctx_sizes = [int(c.strip()) for c in args.ctx.split(",")]

    rows = []
    for model in models:
        for ctx in ctx_sizes:
            print(f"Running {model} at ctx={ctx} ...", file=sys.stderr)
            rows.append(run_one(args.host, model, ctx, args.predict))

    print()
    print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
