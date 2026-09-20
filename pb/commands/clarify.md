---
description: Capture User Insights into the Project Summary tab and the rules behind contested UI decisions into UX Design -> Logic, and append each decision to memory/decisions.md. Replaces the v0.4.0 after_clarify hook (folded into this command body).
---

# /pb:clarify

Capture **User Insights** + the **rules** a contested UI decision produces. Insights land in the
Project-Summary tab; each rule lands in **UX Design → Logic → Rules**, carrying the decision it was
made by (D-33). Both write the registry and the decision log **from this body — no hook**.

## 1 · User Insights
Invoke `ref-blueprint` (screen-level JTBD thinking). Capture — from the user, research, or stated
assumptions:
- `quantitative` — any numbers (conversion, drop-off, survey n).
- `researchSummary` — what users said / did.
- `executiveSummary` — the one-paragraph takeaway.

## 2 · The rule, and the decision it was made by

There is no separate trade-off record (D-33). **A trade-off is a rule**: what you settled on is the
rule, and the question, the options and the reason are how it got settled. Capture them together.

For each contested UI decision, write one `ia.rules[]` entry:

```json
{ "id": "<kebab>", "title": "<what the rule is about>", "kind": "decision",
  "summary": "<the rule in one line — what now holds>",
  "decision": { "question": "<what was being decided>",
                "options": ["<chosen>", "<what lost>"],
                "chose": "<what won>", "why": "<the reason>",
                "affects": "<tabs / screens it reaches>" } }
```

- **`options[]` carries what LOST.** That is the one thing a rule cannot say for itself, and the
  only reason this was ever a separate record. Never drop the losing branch.
- **`kind`** is `decision` while the rule is only a decision. The moment it is expressible as a
  `state-machine`, a `matrix` or a `constraint`, change the kind and add that kind's fields — the
  decision block stays and keeps rendering. A decision that never grows into one of those is fine;
  it is still a rule.
- **Superseding** — set `decision.status: "superseded"` (and `supersededOn`) rather than deleting.
  The card dims and keeps its place. Do not write `[SUPERSEDED …]` into the title; that was the
  convention from before the field existed.
- **A rule that already exists** takes the decision block on itself. Do not create a second rule
  saying the same thing in other words.

## 3 · Write the registry (fold the sync — no hook)
- `meta.userInsights` = `{ quantitative, researchSummary, executiveSummary }`
- `ia.rules[]` — append each new rule; update in place when the decision refines one already there.

(Replaces the v0.4.0 `after_clarify` → `sync-tab2` hook.)

## 4 · Append to the decision log

**Read before you write.** For each decision, first grep `memory/decisions*.md` for its subject.
If a past entry already decided it, show that entry and ask whether this one supersedes it —
then say so explicitly in the new entry, and set `decision.status: "superseded"` on the rule it
replaces. A log that is written by three commands and read by none accumulates contradictions
nobody notices; on a real project that produced entries marked SUPERSEDED the same day they were
written. Use `decisions*.md`, not `decisions.md`: rotation moves older entries to dated siblings
and a bare name skips them.

Then append one entry per decision in the template's shape, **field names exactly as written** so a
later grep can rely on them:

```markdown
## <date> — <title>
- **Decision:** <decision.chose>
- **Why:** <decision.why>
- **Alternatives:** <the options not chosen>
- **Affects:** <decision.affects>
- **Rule:** <ia.rules[].id>
```

## Result
User Insights synced to Tab 2, one rule per decision in UX Design → Logic → Rules; one
`decisions.md` entry each, pointing back at the rule id. **Do not render.**

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
