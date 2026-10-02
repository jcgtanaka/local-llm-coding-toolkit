#!/usr/bin/env python3
"""Benchmark a local Ollama model across context-window sizes.

Finds the real speed cliff on your own hardware for a given model, instead
of guessing: for each requested context size, it builds a synthetic prompt
that fills a fraction of that context (default 85%, see --fill), plants one
fact at the very start and one fact in the middle, asks the model to recall
both, and reports prompt-processing speed, generation speed, whether both
facts were recalled, whether the prompt was truncated, and how much of the
model Ollama kept on the GPU (from GET /api/ps).

It uses only the Python standard library.

NOTE: adapters/claude-code/ask_local.py intentionally duplicates the call
logic, truncation rule, and host handling from this file so it can be copied
on its own. Keep the two in sync.

Usage:
  python3 benchmark_model.py --model <name> [--ctx 4096,8192,16384,32768]
                              [--host http://localhost:11434] [--predict 64]
                              [--fill 0.85] [--timeout 1800]

  python3 benchmark_model.py --compare model-a,model-b --ctx 8192,16384

Truncation rule (applied after each call): a row is flagged when
prompt_tokens >= num_ctx - margin, with margin = max(8, 1% of num_ctx),
because that means the runtime filled the window and dropped the rest. If
the runtime reports no prompt-token count, the row is flagged "unverified".
Use --fill 1.0 or higher to deliberately overflow the window and see the flag.

Exit codes:
  0  at least one row completed (individual row failures are listed in the
     table and below it, and do not stop the sweep)
  2  usage error (bad arguments)
  3  every row failed (for example the server is unreachable)
"""
import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_PORT = "11434"

# Rough chars-per-token used only to size the synthetic prompt.
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

ROW_ERRORS = (RuntimeError, TimeoutError, socket.timeout, json.JSONDecodeError, ValueError, OSError)


def normalize_host(value):
    """Return a base URL. A bare 'host' or 'host:port' becomes http://...;
    a bare host without a port gets Ollama's default port."""
    value = (value or "").strip()
    if not value:
        return DEFAULT_HOST
    if "://" not in value:
        if value.startswith(":"):
            value = "localhost" + value
        if ":" not in value or value.endswith("]"):
            value = value + ":" + DEFAULT_PORT
        value = "http://" + value
    return value.rstrip("/")


def default_host():
    return normalize_host(os.environ.get("OLLAMA_HOST"))


def truncation_margin(num_ctx):
    return max(8, num_ctx // 100)


def assess_truncation(prompt_tokens, num_ctx):
    """Return 'ok', 'truncated', or 'unverified'.

    'truncated': the runtime reports a prompt that fills the window, so the
    rest was dropped. 'unverified': no usable prompt-token count, so
    truncation cannot be ruled out."""
    if not prompt_tokens or prompt_tokens <= 0:
        return "unverified"
    if prompt_tokens >= num_ctx - truncation_margin(num_ctx):
        return "truncated"
    return "ok"


def tokens_per_second(tokens, duration_ns):
    """Tokens per second, or None when the duration is missing or zero."""
    if not duration_ns or duration_ns <= 0 or tokens is None:
        return None
    return round(tokens / (duration_ns / 1e9), 1)


def build_prompt(target_chars: int) -> str:
    """Build a synthetic prompt of roughly target_chars characters, with one
    planted fact at the start and one planted fact in the middle."""
    filler_needed = max(target_chars - len(FACT_START) - len(FACT_MIDDLE) - len(QUESTION), 0)
    half = filler_needed // 2

    def filler_block(n_chars: int) -> str:
        reps = n_chars // len(FILLER_LINE) + 1
        return (FILLER_LINE * reps)[:n_chars]

    parts = [FACT_START, "\n\n", filler_block(half), "\n\n", FACT_MIDDLE, "\n\n", filler_block(half), QUESTION]
    return "".join(parts)


def _http_detail(err):
    try:
        return err.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - best effort only
        return str(err)


def _post(url, body, timeout):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        result = json.load(r)
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected reply from Ollama (not a JSON object).")
    return result


def call_ollama(host, model, prompt, num_ctx, num_predict, timeout=1800):
    """POST to Ollama /api/generate. Raises RuntimeError for HTTP and
    connection errors; timeouts and bad JSON propagate as TimeoutError,
    socket.timeout, or json.JSONDecodeError."""
    url = host.rstrip("/") + "/api/generate"
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0},
    }
    try:
        return _post(url, body, timeout)
    except urllib.error.HTTPError as e:
        detail = _http_detail(e)
        if "think" in detail.lower():
            # Older runtimes or models reject the `think` option: retry without it.
            body.pop("think")
            try:
                return _post(url, body, timeout)
            except urllib.error.HTTPError as e2:
                raise RuntimeError(f"Ollama HTTP error {e2.code}: {_http_detail(e2)}") from e2
            except urllib.error.URLError as e2:
                raise RuntimeError(f"Cannot reach Ollama at {url} ({e2}). Is it running?") from e2
        raise RuntimeError(f"Ollama HTTP error {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach Ollama at {url} ({e}). Is it running?") from e


def gpu_split_from_ps(data, model):
    """Compute the GPU share for the EXACT model name from an /api/ps reply
    (size_vram / size). Returns a short string; never raises."""
    names = {model}
    if ":" not in model:
        names.add(model + ":latest")
    try:
        for entry in data.get("models", []):
            if entry.get("name") in names or entry.get("model") in names:
                size = entry.get("size") or 0
                vram = entry.get("size_vram") or 0
                if size <= 0:
                    return "not detected (/api/ps reported no size)"
                pct = round(100 * vram / size)
                if pct >= 100:
                    return "100% GPU"
                return f"{pct}% GPU / {100 - pct}% CPU"
    except (AttributeError, TypeError):
        return "not detected (unexpected /api/ps reply)"
    return "not detected (model not loaded in /api/ps)"


def get_gpu_split(host, model, timeout=10):
    """Query GET {host}/api/ps and report the GPU share; degrade gracefully."""
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/api/ps", timeout=timeout) as r:
            data = json.load(r)
    except (OSError, ValueError):
        return "not detected (/api/ps unavailable)"
    return gpu_split_from_ps(data, model)


def run_one(host, model, ctx, predict, fill=0.85, timeout=1800):
    target_chars = int(ctx * fill * CHARS_PER_TOKEN)
    prompt = build_prompt(target_chars)

    row = {"model": model, "ctx": ctx, "error": None}
    try:
        t0 = time.time()
        result = call_ollama(host, model, prompt, ctx, predict, timeout)
        wall = time.time() - t0
    except ROW_ERRORS as e:
        row["error"] = f"{type(e).__name__}: {e}" if not str(e) else str(e)
        return row

    prompt_tokens = result.get("prompt_eval_count") or 0
    gen_tokens = result.get("eval_count") or 0
    response = result.get("response", "") or ""

    status = assess_truncation(prompt_tokens, ctx)
    recalled_start = "ALPHA-7429" in response
    recalled_middle = "BRAVO-1836" in response

    row.update({
        "prompt_tokens": prompt_tokens,
        "prompt_tok_s": tokens_per_second(prompt_tokens, result.get("prompt_eval_duration")),
        "gen_tok_s": tokens_per_second(gen_tokens, result.get("eval_duration")),
        "wall_s": round(wall, 1),
        "recalled_both": recalled_start and recalled_middle,
        "truncated": status != "ok",
        "truncation_status": status,
        "gpu_split": get_gpu_split(host, model),
    })
    return row


def print_table(rows):
    headers = ["model", "ctx", "prompt_tok/s", "gen_tok/s", "recalled_both", "truncated", "gpu_split", "note"]
    widths = [12, 8, 13, 10, 14, 10, 22, 12]
    print(" | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("-+-".join("-" * w for w in widths))
    errors = []
    for row in rows:
        if row.get("error"):
            errors.append(row)
            values = [row["model"], str(row["ctx"]), "-", "-", "-", "-", "-", "ERROR (below)"]
        else:
            values = [
                row["model"],
                str(row["ctx"]),
                str(row.get("prompt_tok_s")),
                str(row.get("gen_tok_s")),
                str(row.get("recalled_both")),
                str(row.get("truncation_status")),
                str(row.get("gpu_split", "-")),
                "",
            ]
        print(" | ".join(v.ljust(w) for v, w in zip(values, widths)))
    if errors:
        print()
        print("Errors:")
        for row in errors:
            print(f"  {row['model']} @ ctx={row['ctx']}: {row['error']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="single model to benchmark")
    ap.add_argument("--compare", help="comma-separated list of models to benchmark and compare")
    ap.add_argument("--ctx", default="4096,8192,16384,32768", help="comma-separated context sizes to test")
    ap.add_argument("--host", default=None, help="Ollama base URL (default: $OLLAMA_HOST or http://localhost:11434)")
    ap.add_argument("--predict", type=int, default=64, help="max output tokens per call (kept small on purpose)")
    ap.add_argument("--fill", type=float, default=0.85,
                    help="prompt size as a fraction of each context size (default 0.85; use 1.0 or more to demonstrate the truncation flag)")
    ap.add_argument("--timeout", type=float, default=1800, help="HTTP timeout per call in seconds (default 1800)")
    args = ap.parse_args(argv)

    if not args.model and not args.compare:
        ap.error("pass --model <name> or --compare model1,model2,...")
    if args.fill <= 0:
        ap.error("--fill must be greater than 0")

    models = [m.strip() for m in args.compare.split(",") if m.strip()] if args.compare else [args.model]
    try:
        ctx_sizes = [int(c.strip()) for c in args.ctx.split(",") if c.strip()]
    except ValueError:
        ap.error("--ctx must be a comma-separated list of integers")
    if not ctx_sizes or any(c <= 0 for c in ctx_sizes):
        ap.error("--ctx values must be positive integers")

    host = normalize_host(args.host) if args.host else default_host()

    rows = []
    for model in models:
        for ctx in ctx_sizes:
            print(f"Running {model} at ctx={ctx} ...", file=sys.stderr)
            rows.append(run_one(host, model, ctx, args.predict, args.fill, args.timeout))

    print()
    print_table(rows)
    if all(r.get("error") for r in rows):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
