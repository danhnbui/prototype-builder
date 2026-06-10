---
name: think-critique-prd
description: Push back on a PRD or feature brief before building — surface unclear goals, missing personas, assumption gaps, unrealistic scope, and missing edge cases. Use when reviewing requirements in Product Builder — loaded by /pb:init and /pb:specify — so the prototype is built on solid intent, not silent assumptions. Not for parsing the PRD into context (use ref-prd) or deciding what to ask the user (use think-clarify).
---

# think-critique-prd

Adversarial review of the requirements. The goal is to catch weak intent *before* it becomes screens and
components that have to be rebuilt. Be specific and constructive — every critique points at a fix.

## The lenses (run all five)
1. **Goal clarity** — is the objective measurable? Could two people read it and build different things?
2. **Personas** — is it clear who each screen serves? Any screen with no obvious user is a smell.
3. **Assumption gaps** — what is taken for granted (data exists, user is logged in, network is up)?
4. **Scope realism** — is the screen/feature count plausible for a prototype? Flag gold-plating.
5. **Edge cases** — empty, error, loading, locked-out, rate-limited, offline, double-submit. Which are unspecified?

## Output
A short list: each item is `<lens> · <the gap> · <suggested resolution>`. Mark each **blocking**
(must resolve before building) or **note** (can proceed with a stated assumption). Feed blocking items to
`think-clarify` to ask the user; record resolved trade-offs via `/pb:clarify` into `decisions.md`.

## Rules
- **Critique the brief, not the person.** Frame everything as a question or a fix.
- **Don't redesign.** Surface the gap; let the user decide the direction.
- **Never silence a real edge case** because it seems minor — list it; the user judges severity.
