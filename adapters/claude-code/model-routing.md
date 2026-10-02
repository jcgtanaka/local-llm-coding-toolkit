# Model-tier routing in Claude Code

This is the concrete Claude Code implementation of the general principle in
`../../docs/model-tier-routing.md`: route each task to the cheapest model
tier that can actually be trusted with it, whether that tier is a local
model, a fast cloud tier, a mid cloud tier, or the top cloud tier.

> **Optional reading.** This file is about routing between CLOUD model
> tiers inside Claude Code. It has nothing to do with local-model offload
> and is not needed to use `ask_local.py`.

Details of Claude Code's configuration can change between versions, so check
the official Claude Code documentation for the current settings. This file
only names mechanisms that are stable and widely documented, and describes
the rest loosely.

## 1. Setting a session-wide default model

You can switch the main conversation's model interactively at any time with
the `/model` slash command. Claude Code also lets you configure a default
model in its settings; consult the official documentation for the exact
key and scope for your version.

## 2. Defining per-subagent tiers

Custom subagent definitions live in `.claude/agents/*.md`. Each file has YAML
frontmatter, and that frontmatter can set its own `model:` field, which
accepts the aliases `opus`, `sonnet`, `haiku`, or `inherit` (use the main
conversation's model), or a full model ID. Because each agent file is
independent, different agent files can pin different tiers.

Three minimal, illustrative examples. The agent names
(`architecture-reviewer`, `feature-implementer`, `cleanup-worker`) are only
examples; name yours however you like. The `model:` values below are
placeholders for whichever alias you choose (for example `opus`, `sonnet`,
`haiku`).

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

A subagent file that does not set `model:` follows Claude Code's default
subagent behavior; see the official documentation for what that default is
in your version.

### New models and aliases

An alias such as `sonnet` is intended to point at a model family tier rather
than a pinned version, so an agent file using an alias generally does not
need editing when a new generation ships. Check the documentation for how
aliases resolve in your version. Separately, periodically re-check that a
tier still fits the kind of task you route to it (see
`../../docs/model-tier-routing.md`, "keeping the ladder current").

## 3. Per-call override

Depending on your Claude Code version, the tool the main assistant uses to
delegate to a subagent may accept an optional model override for a single
call. Where available, it supersedes the subagent's own model for that one
invocation only. Check the current documentation to confirm it exists in
your version before relying on it.

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
   (an `architecture-reviewer`-style subagent as above), or a per-call
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
