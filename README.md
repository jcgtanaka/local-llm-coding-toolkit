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

## Quickstart

1. Install [Ollama](https://ollama.com) for your OS.
2. Pull a small model to start with, for example an 8B-class model:
   ```
   ollama pull <model-name>
   ```
   (pick any model in the 7-9B parameter range that Ollama serves; this repo
   does not endorse a specific one).
3. Run the hardware scan for your OS to see what you are working with:
   ```
   bash hardware/scan-linux.sh      # Linux
   bash hardware/scan-macos.sh      # macOS
   powershell hardware/scan-windows.ps1   # Windows
   ```
4. Run the benchmark to find your machine's real context-window ceiling for
   that model, instead of guessing:
   ```
   python3 benchmark/benchmark_model.py --model <model-name> --ctx 4096,8192,16384,32768
   ```
5. Wire the pattern into your coding agent. This repo currently ships one
   adapter, for Claude Code, under `adapters/claude-code/`. Other agents
   (Cursor, Aider, plain scripts) can follow the same shape: a dispatcher
   script plus a verification step, with no adapter-specific magic required.

## Read next

- `docs/why-route-to-local-models.md`: the economics of when offloading
  actually saves anything.
- `docs/model-tier-routing.md`: extending the same routing principle to a
  cloud provider's own model tiers, not just local vs. cloud.
- `docs/verification-before-trust.md`: the non-negotiable verification rule,
  and why bigger local models are not automatically safer.
- `docs/context-window-pitfalls.md`: the single most important operational
  lesson, silent truncation, and the GPU-offload speed cliff.

## Disclaimer

This project is provided as-is, with no warranty of any kind. Use it at your
own risk. It is not officially affiliated with, endorsed by, or sponsored by
Ollama, Anthropic, or any other model, tool, or company named in these docs;
all trademarks belong to their respective owners. Benchmark numbers shown as
examples are illustrative: real results depend on your specific hardware,
model, and quantization, and you should re-run the benchmark on your own
machine before relying on any figure.

## License

MIT. See `LICENSE`.
