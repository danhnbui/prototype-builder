---
name: ref-prd
description: Parse a product requirements doc (a file the user points at, or a short Q&A) into structured project context for Product Builder. Use at the start of a prototype — loaded by /pb:init and /pb:specify — to turn a PRD or feature brief into a clean objective, personas, key screens, and success criteria the rest of the /pb:* commands consume. Not for critiquing the PRD (use think-critique-prd) or deciding what to ask (use think-clarify).
---

# ref-prd

Turn a raw PRD (a markdown file, a pasted brief, or a quick Q&A) into the structured project context
Product Builder builds from. Output is data, not prose — it feeds `memory/prd.md` and the registry's
`meta.overview`.

## Inputs
- A file path the user gave (e.g. `docs/prd/*.md`), or
- A short Q&A when there is no doc (see `/pb:init` step 1).

## Produce this shape
1. **Objective** — one sentence: what the product/feature lets a user accomplish, and the bar for success.
2. **Personas** — who it is for (1–3), each a line: role · primary goal · context of use.
3. **Key screens** — 3–8 screens, each: name · the one job it does · the main inputs/outputs.
4. **Core flows** — the 1–3 journeys that matter (e.g. sign-up → dashboard), as ordered screen lists.
5. **Success criteria** — measurable, testable statements (e.g. "reach the dashboard in < 60 s").
6. **Open questions** — anything the PRD leaves ambiguous (hand these to `think-clarify`).

## Rules
- **Never invent scope.** If the PRD doesn't say it, list it under Open questions — don't assume a feature.
- **Screens map to reality.** Each key screen should become a `screens[]` entry later; name them so they do.
- **Stay lean.** This is a structured summary, not a rewrite of the PRD.

## Output
Write the summary to `memory/prd.md` and seed `meta.overview.objectives` (the Objective line). Hand the
Open questions to `think-clarify` and the risks to `think-critique-prd`.
