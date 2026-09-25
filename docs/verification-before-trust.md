# Verification before trust

## The non-negotiable rule

The cloud model (the "thinker") always:

1. Decides what gets delegated to the local model.
2. Writes the prompt sent to the local model.
3. **Verifies the local model's output before using it for anything
   downstream.**

The local model never ships unverified output directly into code, into a
document that will be published, or into any decision. It is a cheap worker
producing a first draft or an extraction that the thinker checks, not a
peer whose word is trusted.

Verification means, at minimum:

- **Spot-check against the source.** If the local model claims a count, a
  quote, or an extracted value, check at least one or two of those claims
  against the original input directly.
- **Check for truncation.** See `context-window-pitfalls.md`. A truncated
  response can look perfectly confident and completely wrong, with no error
  from the runtime.
- **Never trust the output when the task had real ambiguity.** If a
  reasonable person could have answered the task two different ways, assume
  the local model guessed, and do not use its answer without checking it
  yourself.

## Why this matters: bigger is not automatically better

It is tempting to assume that a larger local model is simply safer to trust.
Real testing on this exact setup showed otherwise. An 8-9B class model
performed acceptably on a plain extraction task once its context window was
sized correctly for the input. A 30B-class model tested in the same setup,
on the same kind of task, **failed a plain factual-recall test from its own
input twice in a row**, while also running far slower. Larger parameter
count did not translate into more reliable recall, and it cost noticeably
more time per call.

The takeaway is not "always use a smaller model." It is: never assume model
size correlates with trustworthiness, and never skip verification because a
model is "supposed to be" more capable. Test the specific model on the
specific task shape you plan to use it for, using the benchmark in
`benchmark/`, and verify every real call regardless of what the benchmark
suggested.

## What to never do

Never let unverified local-model output touch:

- Production or live code of any kind.
- Safety-relevant or financial-logic-relevant changes.
- Anything that will be published or acted on without a human or the cloud
  model reviewing the actual content first.

If a task's failure mode is expensive, the token savings from offloading it
are not worth the risk. Keep those tasks with the cloud model, or do them
yourself.
