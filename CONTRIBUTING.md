# Contributing

Thanks for helping. Keep contributions small and focused.

## Scope

This project is about one pattern: offloading mechanical, big-input /
small-output subtasks to a local model, with a cloud model (or a human)
deciding what to delegate and verifying every result. Changes that push it
toward complex reasoning tasks or toward a general-purpose router are out of
scope.

## Running the tests

```
python3 -m unittest discover -s tests -v
```

Python 3.8+, standard library only: do not add dependencies. Tests must be
pure (no network, no running Ollama). On Windows, `python3` may be `python`
or `py -3`. For the shell scripts, `bash -n hardware/*.sh` and `shellcheck`
are run in CI.

## Ground rules

- `adapters/claude-code/ask_local.py` must stay standalone: no imports from
  this repository. It intentionally duplicates call logic from
  `benchmark/benchmark_model.py`; when you change one, change the other and
  keep the tests for both passing.
- Write a failing test first for any behavior change.
- No personal configuration in docs or scripts (your hardware, specific
  model recommendations, private workflows). Anecdotal measurements must be
  labeled as such.
- Docs must be correct for any OS, any local model, and any coding agent.

## Adapters for other agents

Adapter contributions are welcome. An adapter has the same shape as the
existing one: a dispatcher (a script or instruction file that tells the
agent when and how to call the local model) plus a mandatory verification
step. Put it under `adapters/<agent-name>/` with its own README.

## Other backends

Only Ollama's `/api/generate` is supported today. Support for
OpenAI-compatible servers (`/v1/chat/completions`, `usage.prompt_tokens`)
is a welcome contribution; see "Limitations" in the README.
