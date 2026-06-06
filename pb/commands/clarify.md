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
For **each** trade-off, append an entry to `memory/decisions.md` in the template's shape:
`## <date> — <title>` · **Decision** `<decision>` · **Why** `<why>` · **Alternatives** `<options not chosen>`
· **Affects** `<tabsAffected>`.

## Result
Tab 2 (User Insights + Trade-offs) synced; one `decisions.md` entry per trade-off. **Do not render.**
