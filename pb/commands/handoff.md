---
description: The one hand-off command. Asks what you are handing off — (1) everything, including Product Builder itself, so the recipient can keep building; (2) engineering, as prototype.html + design-system.html + logic.md + rules.md; (3) Figma, written through the Figma MCP. Replaces /pb:handoff-close, /pb:handoff-dev and the hand-off half of /pb:build-figma-handoff as the entry point; all three still work and still do the work.
---

# /pb:handoff

One entry point for every hand-off. It asks **who is receiving this and what they need to do
with it**, because that — not a flag — is what decides which files to write.

## User input
```text
$ARGUMENTS
```

| Flag | Default | Effect |
|---|---|---|
| `--mode=1\|2\|3` | **ask** | Skip the question (also accepts `all` · `dev` · `figma`) |
| `--out <dir>` | per mode | Where to write |
| `--tier=host\|scaffold` | ask, in mode 2 | Also emit a runnable app (delegates to `/pb:handoff-dev`) |
| `--scope=components\|screens\|both` | ask, in mode 3 | What to push |
| `--bridge` | — | Mode 3: emit node JSON instead of writing through the MCP |

## 0 · Ask (skip only when `--mode` is given)

Ask **once**, as a single question with three options, and wait for the answer. Do not guess
from context — the same project hands off to all three audiences at different times, and the
cost of guessing wrong is a folder the recipient cannot use.

> **What are you handing off?**
> 1. **Everything, including Product Builder** — the recipient continues the work: the
>    prototype, the full portable bundle, and a vendored copy of the plugin so `/pb:*` works
>    for them on day one, with no install.
> 2. **For engineering** — `prototype.html` to run, `design-system.html` as the component
>    usage reference, and the logic + rules as Markdown they can read, review and diff.
> 3. **For Figma** — push components and screens into a Figma file.

## 1 · Contract gate (fail-closed — runs first, every mode)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/lint_registry.py" --strict registry.json
```
Non-zero (any `ERROR`) → **STOP**. Print the findings, tell the user to `/pb:build` and retry.
Never hand off a registry that violates the contract (NS6). Then `/pb:build --render` — never
hand off a stale render.

---

## Mode 1 · Everything, including Product Builder

Execute [`handoff-close.md`](handoff-close.md) in its **default** (unnarrowed) mode — the
view-only `prototype.html`, the portable `bundle/`, and the recipient `AGENTS.md`. Then add
the plugin itself:

```
handoff/
  prototype.html            # view-only, self-documenting
  AGENTS.md                 # orients the recipient
  bundle/                   # registry + render/ spec/ logic/ runtime/ design-system/ memory/
  pb/                       # ← a copy of ${CLAUDE_PLUGIN_ROOT}
  .claude-plugin/
    marketplace.json        # ← points at ./pb, so the recipient installs from the folder
```

Copy `${CLAUDE_PLUGIN_ROOT}` to `handoff/pb/`, **excluding** `.venv/`, `__pycache__/`,
`node_modules/`, `.reference/` and `fixtures/` — dev weight the recipient does not need.
Rewrite `marketplace.json`'s source path to `./pb`.

Append to the recipient `AGENTS.md`: that the plugin travels with the folder, the exact
install line, and that `/pb:init --import bundle` is the first command to run.

> **Why vendor rather than link.** A hand-off that depends on the recipient finding and
> installing the right plugin version is a hand-off that stops working the moment either
> moves. The folder is self-contained or it is not a hand-off. Say the size out loud when you
> report — it roughly doubles the folder.

## Mode 2 · For engineering

Write to `handoff-dev/` (or `--out`):

```
handoff-dev/
  prototype.html            # the running prototype — NOT view-only; engineers need the real thing
  design-system.html        # every component: live demo + variant grid — the usage reference
  logic.md                  # per screen/component: handlers, writes[], affordances + why, seam
  rules.md                  # ia.rules, jobs, layers
  constitution.md           # the Stack Lock + DS Lock, copied verbatim
```

1. Render both sites — `/pb:build --render` writes `prototype.html` and `design-system.html`.
   Copy both. **Do not set `config.viewOnly`**: that hides the authoring affordances, and an
   engineer reading the prototype needs to see them.
2. Emit the two Markdown docs:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/handoff_docs.py" . --out handoff-dev
   ```
   Deterministic and byte-stable — no timestamp — so next month's regeneration diffs cleanly
   against this one. It reads the derived logic graph plus the authored half of each contract
   (`writes[]`, `affordances[].why`); it never writes back to `logic/`.
3. Copy `memory/constitution.md` to `handoff-dev/constitution.md`.
4. **Ask whether they also want runnable source.** If yes, delegate to
   [`handoff-dev.md`](handoff-dev.md) at the chosen `--tier` (`host` = a Vite/Next wrapper
   around the single file; `scaffold` = a deterministic React + Tailwind app). If they only
   wanted something to read, do not build it — a scaffold nobody asked for is the most
   expensive file in the folder.

> **`design-system.html` is the component usage doc.** It already carries, per component, a
> live clickable demo, the full variant grid (the cartesian product of its enum properties),
> and the token foundations. Writing a separate usage page would duplicate it and go stale.

## Mode 3 · For Figma

Delegate to [`build-figma-handoff.md`](build-figma-handoff.md) — its clarify gates G-FP0–G-FP5
and its offline G-FP6 audit apply unchanged. One difference: **this mode writes through the
Figma MCP** rather than handing you node JSON to paste.

1. Run the clarify pass (G-FP0–G-FP5) to settle scope, the target file, and the DS match.
2. `registry_to_figma.py` lowers the registry to the node tree — deterministic, ~0 model
   tokens. This runs either way; it is the source of truth for what gets written.
3. Write it into Figma with the MCP, page by page, then re-read what landed
   (`get_metadata` / `get_screenshot`) and report what was created against what was planned.
4. Run the G-FP6 audit on the emitted JSON regardless of path.

> **State the trade-off before writing, once.** pb's default is the DS Bridge plugin
> (`--bridge`): the lowering is deterministic and offline, the plugin rebuilds real **linked
> INSTANCES**, and pb never depends on a live connection. Driving the MCP instead costs model
> tokens proportional to the node count, needs the connection to hold for the whole push, and
> is the one path where a partial failure leaves a half-built file. It is the right choice
> when the user wants it done rather than handed to them — which is what this mode is for.
> If the MCP is unavailable or the push fails partway, **fall back to `--bridge`**, emit the
> JSON, and say exactly which frames landed before the fallback.

---

## 2 · Report
State the mode, the output path, the file count and the total size. For mode 1, say that the
plugin is vendored and what that added. For mode 3, say which frames were created and whether
anything fell back to the bridge.

## NEVER
- NEVER hand off a stale render — `--render` first, every mode.
- NEVER hand off a registry with an `ERROR` finding (NS6, fail-closed).
- NEVER set `config.viewOnly` in mode 2 — engineers need the authoring surface.
- NEVER omit `constitution.md` / `decisions*.md` from a mode-1 bundle. **Never narrow that
  glob to `decisions.md`** — rotation moves older entries to dated siblings, and a bare
  filename drops that history silently.
- NEVER hand-edit anything under the output folder — regenerate by re-running `/pb:handoff`.
- NEVER write to Figma without completing the clarify pass first.

> **Skill degrade (NS6).** If a step's tool, skill or template fails to load, say so
> explicitly and proceed with its core intent — never silently skip it.
