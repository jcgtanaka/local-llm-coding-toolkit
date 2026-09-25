# Model-tier routing in Claude Code

This is the concrete Claude Code implementation of the general principle in
`../../docs/model-tier-routing.md`: route each task to the cheapest model
tier that can actually be trusted with it, whether that tier is a local
model, a fast cloud tier, a mid cloud tier, or the top cloud tier.

Everything below is a real, independently verifiable Claude Code mechanism.
Nothing here is speculative.

## 1. Setting a session-wide default model

Claude Code reads a global default model from its `settings.json` (a `model`
field). This is the model the main conversation uses unless you override it.

You can also switch the main conversation's model interactively at any time
with the `/model` slash command, without editing any file.

## 2. Defining per-subagent tiers

Custom subagent definitions live in `.claude/agents/*.md`. Each file has YAML
frontmatter, and that frontmatter can set its own `model:` field. Because
each agent file is independent, different agent files can each pin a
different model tier: one agent for deep reasoning, a different agent for
routine implementation, another for purely mechanical work.

Three minimal, illustrative examples. The model identifiers below are
generic placeholders, not real model names, so this stays usable regardless
of which exact models you have access to and does not go stale when model
names change.

Deep-reasoning / architecture tier:

```markdown
---
name: architecture-reviewer
description: Use for architecture decisions, security-sensitive changes, and anything expensive to get wrong.
model: <top-tier-model>
---

You review and decide on architecture, security, and high-ambiguity
questions. Favor correctness and explicit tradeoffs over speed.
```

Standard-implementation tier:

```markdown
---
name: feature-implementer
description: Use for standard implementation work with moderate ambiguity.
model: <mid-tier-model>
---

You implement well-specified features and fixes. Follow existing patterns
in the codebase and ask when a requirement is ambiguous.
```

Repetitive/mechanical tier:

```markdown
---
name: cleanup-worker
description: Use for renames, reformatting, and other mechanical, low-judgment edits.
model: <fast-tier-model>
---

You perform mechanical edits only: renames, reformatting, and other
changes with a single obviously correct outcome. Do not make judgment
calls; flag anything ambiguous instead of guessing.
```

There is also a configurable default model specifically for subagents,
distinct from the main conversation's model, settable in `settings.json`.
Any subagent file that does not set its own `model:` field falls back to
that subagent default rather than to the main conversation's model.

### New models do not require editing these files

Claude Code's `model:` field accepts a tier alias (a short name like
`<top-tier-model>` above stands in for one), not a pinned model version. An
alias resolves to the provider's current model in that tier. When a new
model generation ships, an agent file that already points at the top-tier
alias automatically starts using the new model; there is nothing to edit.
The re-mapping work described in `../../docs/model-tier-routing.md`
("keeping the ladder current") is about periodically re-checking that a
tier's alias still fits the kind of task you route to it, not about
rewriting these agent files every time a provider ships an update.

## 3. Per-call override

When the main assistant delegates a task to a subagent, it can pass an
optional model override for that one call. That override supersedes the
subagent's own default model for that single invocation only; it does not
change the subagent file, and the next call to that same subagent goes back
to its normal pinned tier unless overridden again.

This is the mechanism that lets you say, in effect, "for this one task,
route to the top tier even though this subagent's default is the mid tier,"
without maintaining a second copy of the subagent definition.

## Worked example: refactoring a module

A "refactor this module" task is not one job at one tier; it is several
sub-steps, each with a different risk and complexity profile:

1. **Extract every call site of the module's public functions.** Large
   input (the whole codebase), small output (a list of locations). This is
   exactly the local-model pattern from the rest of this repo: the bottom
   rung of the ladder, not a Claude Code mechanism at all. See
   `../../docs/why-route-to-local-models.md`.
2. **Decide the new module boundaries and interface.** This is an
   architecture decision: getting it wrong is expensive to undo once the
   rest of the refactor is built on it. Route to the top cloud tier
   (the `architecture-reviewer`-style subagent above), or a per-call
   override to that tier if the default subagent for this role is normally
   set lower.
3. **Rewrite the bulk of the module to the new interface.** Standard
   implementation work with moderate ambiguity. Route to the mid cloud tier
   (the `feature-implementer`-style subagent).
4. **Rename variables and reformat to match the new interface's
   conventions.** Small, well-defined, low-risk cleanup. Route to the fast
   cloud tier (the `cleanup-worker`-style subagent).

Steps 2 through 4 sit on the same cloud-tier ladder as `model-tier-routing.md`
describes; step 1 sits below all of them, on the local-model rung this whole
repo is built around.

## Caution: this is a cost/speed optimization, not a substitute for judgment

Routing to a faster or cheaper tier saves time and money when the task
actually fits that tier. It is not a substitute for judgment about what the
task requires. When you are unsure whether a task is simple enough for a
lower tier, route up, not down: the cost of a wrong architecture or security
decision vastly exceeds whatever a cheaper tier would have saved. The
verification discipline in `../../docs/verification-before-trust.md` applies
at every tier, including the top one; a more capable model lowers the odds
of an ungrounded answer, it does not remove the need to check important
output before it ships.
