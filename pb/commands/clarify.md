---
description: Capture User Insights + UI Logic Trade-offs into the Project Summary tab, and append each trade-off to memory/decisions.md. Replaces the v0.4.0 after_clarify hook (folded into this command body).
---

# /pb:clarify

Capture **User Insights** + **UI Logic Trade-offs**. Writes the Project-Summary tab and the decision log
**from this body — no hook**.

## 1 · User Insights
Invoke `ref-blueprint` (screen-level JTBD thinking). Capture — from the user, research, or stated
assumptions:
- `quantitative` — any numbers (conversion, drop-off, survey n).
- `researchSummary` — what users said / did.
- `executiveSummary` — the one-paragraph takeaway.

## 2 · UI Logic Trade-offs
For each contested UI decision capture `{ title, question, options, decision, why, tabsAffected }`.

## 3 · Write Tab 2 (fold the sync — no hook)
Write into `registry.json`:
- `meta.userInsights` = `{ quantitative, researchSummary, executiveSummary }`
- `meta.tradeoffs` = the array of trade-off objects

(Replaces the v0.4.0 `after_clarify` → `sync-tab2` hook.)

## 4 · Append to the decision log

**Read before you write.** For each trade-off, first grep `memory/decisions*.md` for its subject.
If a past entry already decided it, show that entry and ask whether this trade-off supersedes it —
then say so explicitly in the new entry. A log that is written by three commands and read by none
accumulates contradictions nobody notices; on a real project that produced entries marked
SUPERSEDED the same day they were written. Use `decisions*.md`, not `decisions.md`: rotation moves
older entries to dated siblings and a bare name skips them.

Then append one entry per trade-off in the template's shape, **field names exactly as written** so a
later grep can rely on them:

```markdown
## <date> — <title>
- **Decision:** <decision>
- **Why:** <why>
- **Alternatives:** <options not chosen>
- **Affects:** <tabsAffected>
```

## Result
Tab 2 (User Insights + Trade-offs) synced; one `decisions.md` entry per trade-off. **Do not render.**

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
