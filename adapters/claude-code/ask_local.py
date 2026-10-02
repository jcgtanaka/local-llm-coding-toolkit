#!/usr/bin/env python3
"""Dispatch a minor, big-input/small-output task to a local Ollama model.

This is the dispatcher a coding agent (or a human) calls to actually run a
delegated subtask, as opposed to benchmark/benchmark_model.py, which is only
for measuring speed and finding a safe context-window ceiling ahead of time.

NOTE: this file is intentionally standalone and self-contained (it imports
nothing from this repository) so it can be copied on its own into any
project. For that reason it intentionally DUPLICATES the call logic,
truncation rule, and host handling of benchmark/benchmark_model.py. When you
change one, keep the other in sync.

MODEL_CTX below is the single source of truth for per-model context
ceilings. Fill it in with the ceilings you found by running the benchmark
on your own hardware, or pass --num-ctx explicitly.

Usage:
  ask_local.py --model <name> --predict 400 [--file input.txt | --stdin]
               [--num-ctx N] [--host URL] [--timeout SECONDS] [--force]

Prints a JSON object to stdout:
  {"response": str, "prompt_tokens": int, "gen_tokens": int,
   "prompt_tok_s": float|null, "gen_tok_s": float|null, "num_ctx": int,
   "truncated": bool, "truncation_status": "ok"|"truncated"|"unverified",
   "done_reason": str|null, "cut_by_predict": bool}

Truncation rule: after the call, the prompt is flagged when
prompt_tokens >= num_ctx - margin, where margin = max(8, 1% of num_ctx).
That means the runtime filled the whole window and dropped the rest. If the
runtime reports no prompt-token count (0 or missing), the result is flagged
"unverified": truncation cannot be ruled out. Both cases set
"truncated": true and exit with code 4. Before calling, a preflight check
refuses prompts estimated above 90% of num_ctx (exit 4) unless --force is
passed.

`cut_by_predict` is true when done_reason is "length": generation stopped at
the --predict token limit, so the answer may be incomplete. This does not
change the exit code.

Exit codes:
  0  ok
  2  usage or configuration error (no ceiling for the model, bad arguments,
     unreadable input file, num-ctx <= 0)
  3  cannot reach the server, HTTP error, timeout, or invalid JSON reply
  4  truncated or unverified result, or preflight refusal

See docs/context-window-pitfalls.md in the repository for why these checks
exist.
"""
import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.request

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_PORT = "11434"

# Single source of truth for per-model context ceilings. Fill this in with
# the ceilings you measured on your own machine using
# benchmark/benchmark_model.py. Past a model's ceiling, generation can slow
# down dramatically without any error. Keep any documentation table in sync
# with this dict.
MODEL_CTX = {
    # "<your-model-name>": <safe-num-ctx-from-benchmark>,
}

# Rough chars-per-token used only for the preflight size estimate. Not exact.
CHARS_PER_TOKEN = 3.5
PREFLIGHT_FRACTION = 0.9

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_UNREACHABLE = 3
EXIT_TRUNCATED = 4


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


def preflight_refuses(prompt, num_ctx):
    """True when the estimated prompt size exceeds 90% of the window."""
    return len(prompt) / CHARS_PER_TOKEN > PREFLIGHT_FRACTION * num_ctx


def tokens_per_second(tokens, duration_ns):
    """Tokens per second, or None when the duration is missing or zero."""
    if not duration_ns or duration_ns <= 0 or tokens is None:
        return None
    return round(tokens / (duration_ns / 1e9), 1)


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


def call_ollama(host, model, prompt, num_ctx, num_predict, timeout=600):
    """POST to Ollama /api/generate. Raises RuntimeError for HTTP and
    connection errors; timeouts and bad JSON propagate as TimeoutError,
    socket.timeout, or json.JSONDecodeError (all handled by main)."""
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


def force_utf8():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def main(argv=None):
    force_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="model name as known to Ollama")
    ap.add_argument("--predict", type=int, default=400, help="max output tokens")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="path to a UTF-8 text file holding the full prompt")
    src.add_argument("--stdin", action="store_true", help="read the full prompt from stdin")
    ap.add_argument("--num-ctx", type=int, default=None, help="override the model's configured context window")
    ap.add_argument("--host", default=None, help="Ollama base URL (default: $OLLAMA_HOST or http://localhost:11434)")
    ap.add_argument("--timeout", type=float, default=600, help="HTTP timeout in seconds (default 600)")
    ap.add_argument("--force", action="store_true", help="skip the preflight size refusal")
    args = ap.parse_args(argv)  # argparse exits with code 2 on bad arguments

    num_ctx = args.num_ctx if args.num_ctx is not None else MODEL_CTX.get(args.model)
    if num_ctx is None:
        print(
            f"No configured context ceiling for '{args.model}'. Either pass --num-ctx "
            "explicitly, or add an entry to MODEL_CTX in this file after benchmarking "
            "the model with benchmark/benchmark_model.py.",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if not isinstance(num_ctx, int) or num_ctx <= 0:
        print(f"Invalid context window {num_ctx!r}: must be a positive integer.", file=sys.stderr)
        return EXIT_USAGE

    try:
        if args.stdin:
            prompt = sys.stdin.read()
        else:
            with open(args.file, encoding="utf-8") as fh:
                prompt = fh.read()
    except (OSError, ValueError) as e:
        print(f"Cannot read the prompt input: {e}", file=sys.stderr)
        return EXIT_USAGE

    if not args.force and preflight_refuses(prompt, num_ctx):
        print(
            f"Refusing to call: the prompt (~{round(len(prompt) / CHARS_PER_TOKEN)} estimated tokens) "
            f"is above {int(PREFLIGHT_FRACTION * 100)}% of num_ctx={num_ctx}, so the runtime would "
            "likely drop part of it. Shrink the input, raise --num-ctx (after re-checking the "
            "speed cliff with the benchmark), or pass --force to send it anyway.",
            file=sys.stderr,
        )
        return EXIT_TRUNCATED

    host = normalize_host(args.host) if args.host else default_host()
    try:
        result = call_ollama(host, args.model, prompt, num_ctx, args.predict, args.timeout)
    except (RuntimeError, TimeoutError, socket.timeout, json.JSONDecodeError, ValueError, OSError) as e:
        print(f"Call failed: {e}", file=sys.stderr)
        return EXIT_UNREACHABLE

    prompt_tokens = result.get("prompt_eval_count") or 0
    gen_tokens = result.get("eval_count") or 0
    status = assess_truncation(prompt_tokens, num_ctx)
    done_reason = result.get("done_reason")

    out = {
        "response": result.get("response", ""),
        "prompt_tokens": prompt_tokens,
        "gen_tokens": gen_tokens,
        "prompt_tok_s": tokens_per_second(prompt_tokens, result.get("prompt_eval_duration")),
        "gen_tok_s": tokens_per_second(gen_tokens, result.get("eval_duration")),
        "num_ctx": num_ctx,
        "truncated": status != "ok",
        "truncation_status": status,
        "done_reason": done_reason,
        "cut_by_predict": done_reason == "length",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status == "truncated":
        print(
            f"WARNING: input truncated: prompt_tokens={prompt_tokens} fills num_ctx={num_ctx}, so the runtime "
            "probably dropped part of the input. Raise --num-ctx (after re-checking the speed "
            "cliff) or shrink the input.",
            file=sys.stderr,
        )
        return EXIT_TRUNCATED
    if status == "unverified":
        print(
            "WARNING: the runtime reported no prompt-token count, so truncation cannot be "
            "verified. Treat the answer as unverified.",
            file=sys.stderr,
        )
        return EXIT_TRUNCATED
    if out["cut_by_predict"]:
        print(
            "NOTE: generation stopped at the --predict limit; the answer may be incomplete.",
            file=sys.stderr,
        )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
