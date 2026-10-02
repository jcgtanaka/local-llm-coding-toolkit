# Context window pitfalls

This is the single place in the repo that explains the two operational
problems below. Other documents link here instead of repeating it.

## Pitfall 1: prompts that do not fit the context window

A runtime serving a local model can drop the part of a prompt that does not
fit in the configured context window (`num_ctx`) and still return a
confident answer. Whether you see a warning depends on the runtime and its
version: observed on the author's machine with Ollama, the response looked
like a normal success and nothing in the API reply said anything had been
cut. Results vary by hardware, model, quantization and runtime version, and
newer runtimes may log a server-side warning (which an HTTP client calling
the API never sees). Do not rely on that: check explicitly.

Observed example: an 8B-class model was given roughly 8,500 tokens of input
with `num_ctx` capped at 2,048. Only the portion that fit was kept, a fact
stated at the very start of the prompt was dropped, and the model answered a
question about it confidently and wrongly.

### The rule the scripts implement

1. **Always set `num_ctx` explicitly** for the task. Do not rely on a
   model's default.
2. **Post-call check.** After the call, compare the runtime's reported
   `prompt_tokens` with `num_ctx`. When the runtime had to drop input, the
   prompt fills the window, so the count lands at (or just under) `num_ctx`.
   Both scripts flag a result as truncated when
   `prompt_tokens >= num_ctx - margin`, where
   `margin = max(8, 1% of num_ctx)`.
3. **Unverified results.** If the runtime reports no prompt-token count (0 or
   missing), truncation cannot be ruled out. The scripts report this as
   `unverified`, never as OK. This can also happen when a runtime reuses a
   cached prompt prefix and does not re-count it.
4. **Preflight (ask_local.py only).** Before calling, the adapter script
   estimates the prompt size from its character count (about 3.5 characters
   per token, deliberately rough) and refuses to send a prompt estimated
   above 90% of `num_ctx`, unless `--force` is passed.
5. **Treat a flag as a failed call**, not a partial answer to salvage.
   Shrink the input or raise `num_ctx` (after checking pitfall 2) and re-run.

The check is a window-saturation test, not a proof of correctness: a prompt
that ends just under the margin can still be fine, and a prompt below the
margin is assumed intact. Spot-check the answer anyway (see
`verification-before-trust.md`).

The benchmark sizes its prompt to 85% of each context by default. Pass
`--fill 1.0` or higher to overflow the window on purpose and watch the
truncation flag fire.

## Pitfall 2: the GPU-offload speed cliff

Raising `num_ctx` "just in case" is not free. A larger context needs more
memory for the KV cache, on top of the model weights. When everything no
longer fits in GPU memory, a runtime can place part of the model or cache in
system RAM and run it on the CPU, and generation gets much slower.

Observed on the author's machine (a single consumer GPU), crossing a
model's ceiling slowed generation by roughly 10 to 20 times with no error
or warning. The exact numbers, and where the ceiling sits, vary with
hardware, model, quantization and runtime version, so they have to be
measured on your own machine, not assumed. A ceiling that works on one GPU
can be far too high on another with less memory.

### The practical rule

Before relying on any (model, context-size) combination for real work:

1. Run `benchmark/benchmark_model.py` over a range of context sizes on your
   own hardware.
2. Note the context size where generation speed drops sharply, or where the
   `gpu_split` column stops reading as fully on GPU: that is your ceiling
   for that model on that machine.
3. Set `num_ctx` at or below that ceiling for real calls, with enough room
   above your expected input size to avoid pitfall 1.
4. Re-benchmark when you change hardware, model, quantization, or the
   runtime version.
