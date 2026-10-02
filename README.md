# Local LLM Coding Toolkit

A small pattern (plus the docs and scripts to run it) for offloading minor,
mechanical subtasks in an AI coding workflow to a local model served by
[Ollama](https://ollama.com), while a cloud model (Claude, GPT, Gemini, or
anything else) stays the "thinker": the one that decides what to delegate,
writes the prompt, and verifies every local-model output before trusting it.

This is not a library or a service. It is documentation plus a handful of
standalone scripts you copy, read, and adapt to your own machine and your own
coding agent.

## Why do this

Token savings are the obvious motivation, but they are not the only one, and
often not even the strongest one:

- **Data locality and privacy.** Large chunks of a file, a log, or a dataset
  never have to leave your machine if a local model can do the extraction or
  summarization step first.
- **Avoiding rate limits.** Bulk, repetitive subtasks (tagging a hundred
  items, summarizing many small files) can burn through cloud API rate limits
  fast. A local model has no such limit.
- **Latency and offline resilience.** A local call has no network round trip
  and keeps working if your internet or the cloud provider is down.
- **Reducing vendor lock-in.** The pattern itself (a thinker model that
  delegates and verifies) does not depend on any single cloud provider, and
  the local half of it runs on hardware you already own.
- **Token savings, when the shape of the task fits.** Offloading only saves
  tokens when the input is large and the output is small; see
  `docs/why-route-to-local-models.md` for why this matters.

## What this is NOT

- Not a router or a proxy: nothing here automatically decides what to send
  where. A capable model (or a human) still has to make that call.
- Not a packaged CLI or an installable tool. It is scripts you read, copy,
  and adapt.
- Not a claim that local models can do complex reasoning. Every script and
  document here assumes the local model handles mechanical, low-judgment
  work only, and that its output is always verified before use.

## Requirements

- Python 3.8 or newer. The scripts use the standard library only.
- [Ollama](https://ollama.com), reachable over HTTP (default
  `http://localhost:11434`, or set `OLLAMA_HOST`). Use a recent Ollama: the
  scripts send the `think` option and automatically retry without it if the
  runtime rejects it.

## Quickstart

1. Install [Ollama](https://ollama.com) for your OS.
2. Pull a model that fits your VRAM/RAM:
   ```
   ollama pull <model-name>
   ```
   This repo does not endorse a specific model. The hardware scan below
   helps you judge what fits.
3. Run the hardware scan for your OS (read-only):
   ```
   bash hardware/scan-linux.sh      # Linux
   bash hardware/scan-macos.sh      # macOS
   powershell -ExecutionPolicy Bypass -File hardware/scan-windows.ps1   # Windows
   ```
4. Run the benchmark to find your machine's real context-window ceiling for
   that model, instead of guessing:
   ```
   python3 benchmark/benchmark_model.py --model <model-name> --ctx 4096,8192,16384,32768
   ```
   (On Windows, `python3` may be `python` or `py -3`.)
5. Wire the pattern into your coding agent. This repo ships one adapter, for
   Claude Code, under `adapters/claude-code/`. For any other agent see
   "Using it with another agent" below.

A worked example of one offload, end to end, is in
[`examples/README.md`](examples/README.md).

## Using it with another agent

Any agent that can run a shell command can use the pattern. Put something
like this in `AGENTS.md` (or your agent's equivalent instructions file):

```
## Local model offload
- Delegate to the local model only mechanical tasks where the input is large
  and the output is small (extract, tag, sort, summarize a large file or
  log). Never delegate code changes, judgment calls, or high-stakes work.
- Call it with: python3 path/to/ask_local.py --model <name> --predict 400 --file prompt.txt
  and read the JSON on stdout. Exit code 0 is ok; 2 config error; 3 server
  unreachable or timeout; 4 truncated, unverified, or input too large.
- Verification is mandatory: check the exit code and the "truncated" flag,
  then spot-check the answer against the source before using it. If the
  task had any ambiguity, do it yourself instead.
```

Copy `adapters/claude-code/ask_local.py` (it is a standalone file) and edit
its `MODEL_CTX` table with the ceilings you measured.

## Limitations

- **Ollama only today.** The scripts call Ollama's `/api/generate`
  endpoint. Other local servers (llama.cpp server, LM Studio, vLLM) expose
  an OpenAI-compatible `/v1/chat/completions` API that returns
  `usage.prompt_tokens`, so they could be supported by adapting
  `call_ollama` (and the response fields it reads). That is not implemented;
  contributions are welcome, see [CONTRIBUTING.md](CONTRIBUTING.md).
- The truncation check detects a saturated window, not wrong answers. Always
  verify output.
- Anecdotal measurements in the docs come from the author's machine and will
  differ on yours.

## Troubleshooting

- **Connection refused / cannot reach Ollama** (exit code 3): start Ollama
  (`ollama serve` or the desktop app), and check `--host` or `OLLAMA_HOST`.
- **Model not found** (HTTP 404, exit code 3): run `ollama pull <model-name>`
  and use the exact name shown by `ollama list`.
- **`ollama` not on PATH**: the scripts talk to the HTTP API and do not need
  the CLI, but you need it to pull models. Reinstall or fix your PATH.
- **Windows "running scripts is disabled"**: run the scan with
  `powershell -ExecutionPolicy Bypass -File hardware/scan-windows.ps1`.
- **`python3` not found on Windows**: use `python` or `py -3`.
- **`truncated` flag set (exit code 4)**: the prompt filled the context
  window (so input was probably dropped), or the runtime gave no token count
  so it cannot be verified. Shrink the input or raise `--num-ctx`, then
  re-check speed with the benchmark. See
  `docs/context-window-pitfalls.md`.
- **Input too large (preflight refusal, exit code 4)**: the estimated prompt
  is above 90% of the window. Shrink it, raise `--num-ctx`, or pass
  `--force` if you accept the risk.

## Read next

- `docs/why-route-to-local-models.md`: the economics of when offloading
  actually saves anything.
- `docs/model-tier-routing.md`: extending the same routing principle to a
  cloud provider's own model tiers, not just local vs. cloud.
- `docs/verification-before-trust.md`: the non-negotiable verification rule,
  and why bigger local models are not automatically safer.
- `docs/context-window-pitfalls.md`: the most important operational
  lesson (prompts that exceed the context window, and the GPU-offload speed
  cliff).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run the tests with
`python3 -m unittest discover -s tests`.

## Disclaimer

This project is provided as-is, with no warranty of any kind. Use it at your
own risk. It is not officially affiliated with, endorsed by, or sponsored by
Ollama, Anthropic, or any other model, tool, or company named in these docs;
all trademarks belong to their respective owners. Measurements mentioned in
the docs were observed on the author's machine: real results depend on your
hardware, model, quantization and runtime version, so re-run the benchmark
on your own machine before relying on any figure.

## License

MIT. See `LICENSE`.
