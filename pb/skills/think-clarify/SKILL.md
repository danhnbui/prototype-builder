---
name: think-clarify
description: Decide what genuinely needs a human answer vs what can proceed on a sensible default. Use when a PRD, brief, or task is ambiguous in Product Builder — loaded by /pb:init — to ask the few high-leverage questions and assume the rest, so building isn't blocked by over-asking or derailed by wrong guesses. Not for critiquing the requirements (use think-critique-prd) or parsing them (use ref-prd).
---

# think-clarify

Knowing *when* to ask is a skill. Ask too much and you stall; assume too much and you build the wrong
thing. This skill triages ambiguity into **ask** vs **assume-and-state**.

## The test for each unknown
Ask the user **only** when ALL hold:
- The answer **changes what you build** (different screens, data, or flow — not just a label).
- You **can't infer** it from the PRD, the DS, or a strong convention.
- Guessing wrong is **expensive** to undo later.

Otherwise: pick the sensible default, **state it out loud**, and proceed.

## How to ask
- Batch the genuine questions; ask the highest-leverage ones first, one idea at a time.
- Offer a recommended default with each question so the user can just confirm.
- Cap it — a prototype intake rarely needs more than 3–5 real questions.

## Output
A short list of **questions to ask** (each with a recommended default) and a list of **assumptions taken**
(stated so the user can correct them). Defaults that shape the trio (a screen, a component, logic) should be
recorded as trade-offs via `/pb:clarify`.

## Rules
- **Never block on a question you can answer with a stated default.**
- **Never silently assume** something that changes the build — state every assumption.
