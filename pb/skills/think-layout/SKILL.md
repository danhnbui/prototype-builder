---
name: think-layout
description: Decide how a Product Builder screen or component is built and arranged — the job it serves, which design-system component fills each region, how much text it may carry, then flex vs grid, spacing rhythm, responsive behavior and layering — and look at the rendered result before hand-back. Use when structuring a screen or component — loaded by /pb:build when a screen/component changes. ref-blueprint is the "why this screen" reasoning it applies. Not for business logic (use think-logic) or cross-screen navigation (use craft-connect-flow).
user-invocable: false
---

# think-layout

A first design fails in two ways the rest of the loop does not catch: a component picked by habit
instead of by the question it answers, and a screen that explains itself in prose instead of showing
controls and data. This skill makes both decisions on the record before any markup, arranges the
result, and then looks at it. A render body is the `.js` file at `renderSrc`; it returns an HTML
string built with tokens only.

## 1 · Job
- Read the `ia.jobs[]` entry whose `screens[]` holds this screen — for a component, the host screen
  it is built for. Its `when / want / so` line and its **one primary action** open the header (§2).
- The reasoning — one job per screen, every element kept, demoted or cut against it, one primary
  action — is `ref-blueprint` §1–§3. Apply it; do not restate it.
- No job names the screen → say so (`/pb:build` §4's `⚠ no declared job is served by <id>`) and build
  what was asked. Never invent a job to justify a layout.

## 2 · Component fit before markup
Split the target into regions (header · content · actions · feedback). Each region answers the
decision point it raises — the questions `think-direction` §2 lists:

| The region holds | Ask | Answers |
|---|---|---|
| a collection | one focal item, or comparable ones? how many attributes? | list · table · cards |
| an interruption | must they act first? one field or the page? | dialog · sheet · banner · inline |
| a choice | how many options, one or many, now or on submit? | switch · segmented · radio · chips · select |
| a wait | how long? | < 100 ms state · ≤ 1 s spinner · ≤ 10 s skeleton · then background |

Then name the component id that fills it, in `/pb:build` §3a order: reuse → variant → local
(`design-component-build`). Write one line per region at the top of the body file:

```js
// job: when returning, a member wants to sign in, so they reach the dashboard — primary: Sign in
// form: two fields, checked on submit → inline errors · text-input (reuse)
// actions: one primary, one way out → button (reuse) + button variant=link (variant)
// wait: submit ≤ 1 s → spinner · button state=loading (variant)
```

A region with no line was decided by accident. Name components by id, never as a tag (a `<button>`
in a comment trips R-COMPOSE today). The body is bare statements (`design-component-build` §3), so a
header is safe there; the lines say what the body does, never the round that produced it.

## 3 · Density budget
A prototype shows controls and data, not explanation. Each rule is checkable in the rendered DOM:
- **Two lines, then copy.** No text block runs past 2 lines at compact width unless
  `content.strings[]` or the spec carries that exact copy.
- **Six words per element.** Per region, words ≤ (interactive + data elements) × **6** — a card with a
  title, a figure and one button gets 18. Over budget → cut prose, not elements. State the count per
  region in the hand-back; it is a rule of thumb the linter can later measure.
- **3–4 rows per phone screen.** A list shows at least 3–4 items in one compact viewport; fewer means
  the rows carry prose.
- **Title ≤ 24px at compact.** The token behind a page title resolves to 24px or less on the phone.
- **One primary action per view** — never one per row; a row's action is secondary, or the row itself.
- **No caption for what is visible.** A paragraph that explains what the UI already shows is cut.
- **Real content only.** Every label and figure comes from the seeds (`erd.mock`), the spec or
  `content.strings[]` — test with the longest label and the empty seed. One with no source is a named
  gap in the hand-back, never a sentence written to fill the space.

## 4 · Arrange
- **Flex** for one-dimensional runs, **grid** for two dimensions or explicit tracks. `gap` between
  siblings, `padding` inside containers, no margin hacks; one spacing scale.
- **Composition.** Above the atom level, layout containers (a flex/grid `div`, or `pbFrame`) may wrap
  `pbUse` calls — molecules included — and never inline a control or a text tag (R-COMPOSE).
- **Text shrinks.** A single-track grid holding text is `minmax(0, 1fr)`, never a bare `1fr` (its
  min-content floor pushes past the frame); a flex child holding text gets `min-width: 0`.
- **Responsive.** Only when `meta.responsive` is `true` (`false` → one layout at `meta.device`; `null`
  with several size classes → `/pb:build` §1b asks first). Mobile first; each size class in
  `meta.devices` — **compact** < 600px (mobile) · **medium** 600–1023px (tablet) · **expanded** ≥ 1024px
  (laptop, monitor) — answers for itself: layout shape, navigation, swaps (table → cards, dialog →
  sheet). "The same, smaller" — or the phone column stretched to 1280px — is not an answer. Typical
  answers: bottom tabs (compact) → a sidebar rail (expanded); one column → `r-cols`; a full-width
  list → list + detail side by side; content capped by `r-measure` instead of running 1920px wide.
  **How it is written:** inline `style=""` cannot hold a breakpoint, so the item gets a `styleSrc`
  sheet (`render/styles/<id>.css`): the body puts `c-<id>` / `s-<id>` on its root, and the sheet uses
  `@container pb-screen (min-width: 600px | 1024px)` — **never `@media`**: the frames are `<div>`s in
  one document, so `@media` answers the browser window, not the frame (`R-STYLE-MEDIA`). Keep every
  property that changes out of the inline style. For a plain show/hide swap, the utilities in
  `pb/template/product.css` need no sheet: `r-compact` · `r-medium-up` · `r-expanded-up` ·
  `r-below-expanded`.
- **Layering.** `z-index` from four levels only: base · sticky · overlay · toast.
- **Wrap and truncation are decisions.** `flex-wrap` on any run that can overflow. Truncate only where
  the full text stays reachable — an ellipsis that hides what a title is for is a defect.

## 5 · Look at it
Before hand-back, render — in memory through `/pb:preview`, or `render.py` — screenshot the target at
**every** `meta.devices` width (one per size class at minimum; just `meta.device` when
`meta.responsive` is `false`), and check:
- **Nothing clipped or overflowing.** Run this check against every element (on one real project
  three of four defects in one pass were overflow, none visible in the source):
  `el.scrollWidth - el.clientWidth > 1 && (overflow hidden || text-overflow ellipsis)` — and no element
  wider than the frame.
- **Icon-only controls are square** — width equals height.
- **Text at compact** is within §3's caps: title ≤ 24px, no block past 2 lines.
- **The primary action is visible without scrolling** at the compact width.
- **Each size class looks designed for it** (responsive projects): the expanded frame is not the
  compact layout stretched — navigation, columns and density changed where the width allows.

Tools: an explore candidate has `explore.py check <id> --shots` (both widths, into
`memory/explore/<id>/shots/`). The live screen: **`shot.py`** — one command, every width, through the
project's running preview (or one it boots for the run):
`python3 "${CLAUDE_PLUGIN_ROOT}/tools/shot.py" registry.json --screen <id> --viewport 390x844 --viewport 834x1112 --viewport 1440x900 [--role <id>] [--console]`
writes one PNG per width under `.preview/shots/` and prints each path — open them. The overflow check
above is `--eval`: `--eval "<expression>"` prints its JSON result per width. Never a hand-written
Playwright script (`CLAUDE.md` § *pb bounds its own footprint*); `/pb:test` then runs the scenarios on
the same preview. No Playwright, or `shot.py` exits 3 → report "not looked at — blocked", never "passed".

## Output
The header lines (§1–§2), the word count per region, the container model, spacing tokens, responsive
plan and layering, and the §5 verdict with its screenshots — or the line saying why it is blocked.
Markup goes to `design-component-build`; state logic to `think-logic`.

## Rules
- **Tokens only** — every size, space, radius and colour; add a local token before inlining a value.
- **Component-first** — every region is a DS component id (reuse → variant → local), composed by `pbUse`.
- **The density caps hold** — 2 lines, 6 words per element, one primary action, real content only.
- **Measured beats described** — a screen nobody screenshotted at both widths is not done.
