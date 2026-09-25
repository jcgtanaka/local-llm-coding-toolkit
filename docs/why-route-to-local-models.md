# Why (and when) to route work to a local model

## The core economics

Offloading a subtask to a local model only saves cloud tokens when the
**input is large and the output is small**. That is the whole rule.

Here is why: whatever the local model produces still has to be read by the
cloud model to be useful, which means it enters the cloud model's context
window as input tokens. If you send a local model 8,000 tokens of raw log
text and it comes back with a 400-token summary, you have replaced an
8,000-token cloud-input cost with a 400-token one: a real win. If instead you
send a local model 200 tokens describing a small code edit and it comes back
with 300 tokens of modified code, you have not saved anything: writing the
prompt costs about as much as just doing the edit directly, and now you also
have to verify the local model's work, which costs more cloud tokens on top.

So the question to ask before delegating anything is not "can a local model
do this at all" but "is the input meaningfully bigger than the output here,
and would the cloud model otherwise have to hold that full input in its own
context to do the same job."

## Good vs. bad candidate tasks

| Task shape | Verdict | Why |
|---|---|---|
| Extract a handful of fields (dates, names, values) from a long document | Good | Large input, tiny output |
| Summarize a large log file or dataset into a few bullet points | Good | Large input, small output |
| Tag or classify many short items in bulk (label each of 200 lines) | Good | Large input, compact structured output |
| Sort or bucket a large list by an obvious, unambiguous criterion | Good | Large input, small output, low judgment |
| First-pass draft of something the cloud model will rewrite anyway | Good, with caveats | Large-ish input, output is a draft, not final; cloud model still reviews it fully |
| A small, surgical code edit | Bad | Output is nearly as large as input; needs judgment |
| Any code change that requires understanding intent, side effects, or correctness | Bad | Requires reasoning, not extraction |
| A task with real ambiguity where guessing wrong is costly | Bad | A small model can guess through ambiguity and sound confident while being wrong |
| Anything touching production, live trading, financial logic, or safety-relevant code | Bad, always | The verification cost and risk outweigh any token savings; see `verification-before-trust.md` |
| A short input (a sentence, a small config block) | Bad | Writing and sending the prompt costs as much as doing the task directly |

## The rule of thumb

If you can't clearly say the input is much bigger than the output, don't
delegate it. When in doubt, do the task directly with the cloud model: the
token cost of doing it yourself is usually smaller than the token cost of
writing a careful delegation prompt plus verifying a questionable result.
