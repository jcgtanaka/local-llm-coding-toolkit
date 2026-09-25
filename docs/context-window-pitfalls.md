# Context window pitfalls

## The single most important operational lesson

A runtime serving a local model (Ollama, specifically tested here, and
likely true of others) will **silently truncate a prompt that exceeds the
configured context window and still return a confident, wrong answer**.
There is no error. There is no warning. The response looks exactly like a
normal, successful answer.

This was reproduced directly: an 8B model was given roughly 8,500 tokens of
input with the context window (`num_ctx`) capped at 2,048 tokens. Ollama
silently kept only the portion of the input that fit inside that window,
dropping a fact that had been stated at the very start of the prompt. The
model then confidently answered a question about that dropped fact, and got
it wrong, with nothing in the response indicating that anything had been
cut.

If you only look at whether the call "succeeded" and whether the answer
"looks reasonable," you will not catch this. The failure mode is
indistinguishable from a normal answer unless you specifically check for it.

## The mitigation

1. **Always explicitly set the context window size (`num_ctx`) for the task
   at hand.** Do not rely on a model's default; defaults are often smaller
   than they look, and the "right" size depends on your actual input length
   plus safety margin.
2. **Cross-check the runtime's reported prompt-token count against your own
   rough estimate of the input size.** A simple, conservative
   characters-per-token ratio (roughly 3.5-4 characters per token for
   English text) is good enough to catch a large mismatch. If the reported
   prompt-token count is much lower than your estimate, and your estimated
   size is close to or above `num_ctx`, treat that as truncation, not as a
   coincidence.
3. **Treat a detected mismatch as a failed call, not a partial answer to
   salvage.** Do not try to use "most of" a truncated response. Increase
   `num_ctx` (after checking the GPU-offload cliff below), or shrink the
   input, and re-run the call.

The `benchmark/benchmark_model.py` script in this repo implements exactly
this check, and the adapter's `ask_local.py` dispatcher in
`adapters/claude-code/` carries the same check into real usage: it compares
the model's reported prompt-token count against an estimate from the raw
input length and flags a probable truncation instead of silently returning
the result.

## The GPU-offload speed cliff

Raising `num_ctx` "just in case" is not free. On a real test machine (a
single consumer GPU in the 10GB VRAM class, for example a 10GB-class card
such as an RTX 3080), each model tested had a specific context-window
ceiling. Below that ceiling, the whole model and its context stayed resident
on the GPU. Past it, Ollama silently began spilling part of the model or its
KV cache from GPU memory to system RAM and CPU compute, and generation
speed collapsed by roughly **10 to 20 times**, with no error or warning
displayed anywhere.

This means the safe context window for a given model on a given machine is
not a property of the model alone: it is a property of the model plus the
specific hardware plus the context size, and it has to be measured, not
assumed. A ceiling that works fine on one GPU can be far too high on
another with less VRAM.

## The practical rule

Before relying on any (model, context-size) combination for real work:

1. Run `benchmark/benchmark_model.py` against a range of context sizes on
   your own hardware.
2. Note the context size where generation speed drops sharply: that is your
   safe ceiling for that model on that machine.
3. Set `num_ctx` at or below that ceiling for real calls, with enough margin
   above your actual expected input size to avoid truncation.
4. Re-benchmark whenever you change hardware, change the model, or change
   Ollama's version, since the ceiling is not guaranteed to stay the same.
