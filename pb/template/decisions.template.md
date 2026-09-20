# Decisions — {project-name}

> The why-log. One entry per decision resolved, gate override, or lock change. Newest first.
> Appended automatically by `/pb:clarify` (one entry per contested UI decision, naming the
> `ia.rules[]` rule it produced) and by the build loop on a drift-gate override — and **read back**
> by both before they append, so a new entry that contradicts an old one says so instead of
> silently superseding it.
>
> **Keep the field names exactly as the template writes them.** They are grepped. A log that
> drifts between `Verified` and `Verification` is a log the next search misses.
>
> **This file rotates by SIZE, not by year.** Past 500 KB, older entries move to a dated sibling
> (`decisions-<YYYY>.md`) — whole entries, chosen by their own date, verified lossless:
> `decisions_rotate.py memory/decisions.md --apply` (dry-run by default; `/pb:test --drift` names it
> once the log crosses the threshold). Anything reading the log must glob `decisions*.md`; a bare
> `decisions.md` silently stops at the last rotation.
> (A real project reached 818 KB across 187 entries in two months, so a calendar rule would
> never have fired.)

<!-- Template entry — copy below this line:

## YYYY-MM-DD — <short title>
- **Decision:** <what was chosen>
- **Why:** <one or two lines>
- **Alternatives:** <what was rejected, and why not>
- **Affects:** <screens / components / tokens / logic>
- **Rule:** <ia.rules[].id, when the decision produced or changed one>

-->
