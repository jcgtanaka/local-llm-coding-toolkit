# Model-tier routing: the local-vs-cloud split is the bottom rung

## The ladder, not a single split

The rest of this repo treats "local model vs. cloud model" as a single
decision: is this subtask mechanical and big-input/small-output enough to
hand to a local model, or does it need a capable cloud model to actually
reason about it?

That framing is correct but incomplete. Most cloud providers do not ship one
model; they ship a lineup of tiers at different capability, speed, and cost
points, typically something like:

- A fast, cheap tier built for high-volume, low-judgment work.
- A mid tier built for standard implementation work.
- A top tier built for deep reasoning, architecture, and high-stakes
  decisions.

The same principle this repo already uses to decide "local or cloud" applies
again one level up, inside the cloud provider's own lineup: route each task
to the cheapest tier that can actually be trusted with it, and no cheaper.
Local-vs-cloud and tier-vs-tier are the same question asked at two different
altitudes.

## A generic complexity ladder

This ladder is illustrative. It names no vendor and no specific model, on
purpose: model names and generations change constantly, and a document that
hardcodes them goes stale fast.

| Task shape | Route to |
|---|---|
| Mechanical, repetitive, no judgment required (extract fields, tag items, sort a list) | Local model |
| Small, well-defined, low-risk work (a simple rename, a small well-specified function, formatting cleanup) | Fast/cheap cloud tier |
| Standard implementation with moderate ambiguity (most day-to-day feature work, typical bug fixes) | Mid cloud tier |
| Architecture, security-sensitive work, high ambiguity, or any decision where a wrong answer is expensive to undo | Top cloud tier |

The columns on the right get more capable and more expensive as you go down
the table. The rows on the left get more ambiguous and higher-stakes. The
rule is to match the row to the column, not to default to one column for
everything.

## Verification does not disappear as you go up

`docs/verification-before-trust.md` states the non-negotiable rule for the
local-vs-cloud boundary: a local model's output is never trusted without a
spot-check. That discipline does not stop applying once you move into cloud
tiers. Every tier, including the top one, can be confidently wrong. Moving up
a tier generally lowers the *risk* of an ungrounded or wrong answer; it does
not eliminate it, and it does not remove the obligation to verify important
output before it ships.

What changes as you move up is the odds, not the obligation. That is exactly
why critical decisions, architecture calls, security-relevant choices,
anything expensive to get wrong, belong at the top tier regardless of its
cost. The token or dollar savings from using a cheaper tier are trivial next
to the cost of a wrong architecture or security decision that has to be
unwound later.

## Keeping the ladder current as models change

Model lineups change faster than documentation does. Two things keep this
pattern from going stale:

- **Tiers are defined by role, not by a model name.** "Fast/cheap," "mid,"
  and "top" describe a cost/capability/risk profile, not a specific model.
  When a provider ships a new generation, re-map which of their current
  models fills each role; the ladder itself does not change.
- **Verify placement against your own real tasks, not marketing claims.**
  The same discipline this repo uses for local models (benchmark on your
  own hardware, do not trust a spec sheet) applies here too: when a new
  model appears, or an existing one is upgraded, re-check it against the
  kind of task you route to that tier before assuming it belongs there.
  A model that was "mid tier" work last year can become this year's "fast
  tier" as capability shifts; do not assume a name keeps its old meaning
  forever, especially once a provider reuses or renames a tier.

## Concrete example: Claude Code

`adapters/claude-code/model-routing.md` documents how this ladder maps onto
Claude Code mechanisms (see that file for which ones are named and which are
described only loosely): a session-wide default model, per-subagent model
pinning via frontmatter, and per-call overrides. Treat it as the worked example of everything above; the
principle here is agent-agnostic, but Claude Code is the one implementation
this repo currently documents in full.
