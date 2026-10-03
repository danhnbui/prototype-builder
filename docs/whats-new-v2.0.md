# Product Builder 2.0

**Describe a product. Get a prototype people can click, and a design system they can read.**
One `registry.json` — Python renders both sites. No model tokens spent drawing HTML.

## Why it's different

- **Your prototype is data, not a 3,600-line HTML file.** The build loop edits tens of lines of JSON. Measured **3–5× cheaper** across a build session.
- **Tests that never saw the design.** `/pb:test` writes a yes/no plan, then hands it to agents with no idea what you intended — so a verdict isn't written by the thing being graded. A `no` can't be overturned.
- **Bring your own design system.** Nothing is hardcoded. Clone from a DS MCP, a Figma link, or a code library; pb has no taste of its own to impose.
- **One screen, two devices, side by side.** At their real widths, sharing one session — click in either frame and both follow.
- **Hand off three ways.** A link for stakeholders. Runnable code for engineers. Real components for Figma.

## New in 2.0

- **24 commands became 12.** Flags instead of near-duplicates. `/pb:handoff` just asks who's receiving the work.
- **Delegated test grading** — the headline above.
- **Content segment** — one home for every word your product says, and the words it never says.
- **Trade-offs are rules now**, stored with the decision that produced them, next to the logic they constrain.
- **Flow and data stay in sync** on their own after a structural change. No Sync button.
- **Real browser chrome** — a Chrome window at Chrome's metrics on desktop; an actual phone browser on mobile.

## Try it

```
/plugin marketplace add danhnbui/prototype-builder
/plugin install pb@product-builder
```

Restart Claude Code, then `/pb:init`. Python 3 is the only requirement — no `pip install`.

Upgrading from 1.x? → [upgrade-to-2.0.md](upgrade-to-2.0.md) · Full detail → [changelog](../changelog.md)
