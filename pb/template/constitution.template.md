# Constitution — {project-name}

> Durable rules for this prototype. The build loop reads this before any **trio** write
> (a screen, a component, or logic). Keep it lean — rules only, no governance ceremony.

## Principles

<!-- Numbered, falsifiable rules the drift gate checks each trio write against.
     One line each. Examples: -->
1. Error states show BOTH a danger border AND error text — never border alone.
2. One primary action per screen.
3. Every interactive element has a visible focus state.
4. All color / space / radius / shadow come from **W3C DTCG** tokens (`{ $value, $type }`) — no raw hex or arbitrary px.
5. **Component-first / atomic (enforced, ERROR under `--strict`).** Every component carries a required
   atomic `level` (`atom | molecule | organism | template`; screens are `page`). ONLY `level:atom`
   render bodies may emit raw HTML primitives — molecules/organisms/screens are **pure composition** via
   `pbUse('<child-id>', props)` of lower-level components, never inlined one-off markup. Compose upward
   and reuse before you build (R0/R1). **DS-granularity rule:** a component that maps to a single DS
   component (`dsMatch`) is an `atom` even if visually composite (it lowers to one Figma INSTANCE) — don't
   decompose it.

## Stack Lock

- **Language:** {language}
- **Framework:** {framework}

Locked at `/pb:init`. A switch requires explicit approval **and** a `decisions.md` entry.

> The Stack Lock records the **intended production** language/framework — it guides design decisions and
> component thinking. It does **not** change the prototype artifact: the prototype is always rendered
> **HTML** (`prototype.html` from `registry.json`), regardless of the lock. `/pb:validate` wraps that single
> file in a runnable reference build; it does not emit framework-specific component source (NS9).

## Design System Lock

- **Name:** {design-system-name}
- **Source:** {git-url | local-path | built-in}
- **Reference:** `design-system/{name}/{name}.md`

No style outside the DS tokens / components without a logged override (see `decisions.md`).

## Preview

One source of truth (`registry.json`), two derived sites served by the one live `/pb:preview` server:
the **prototype** (`prototype.html` at `/` — flows/screens) and the **design system**
(`design-system.html` at `/design-system` — the component workbench). Neither HTML file is a second
preview or ever hand-edited; both are deterministic renders, and a component edit re-renders both.
`/pb:preview` keeps exactly one `.claude/launch.json` entry for this project (`pb-preview · <folder>`,
one server / two routes); duplicates are pruned automatically.

## Figma Hand-off

Every export to Figma goes through `/pb:build-figma-handoff` — never hand-draw prototype frames into
Figma directly. Default is **BRIDGE mode**: `registry_to_figma.py` lowers the registry to **GHN DS
Bridge node JSON** (INSTANCE-by-key + token refs, auto-layout on every frame), which is pasted into the
plugin's *Code → Figma* tab and rebuilt as linked instances. The Figma MCP is a read-only **context**
provider (match/enrich at G-FP3/G-FP4), never the writer. The **offline G-FP6 audit** must pass on the
emitted JSON before hand-off — auto-layout everywhere · 0 absolute children · every screen element an
INSTANCE-by-key (component-first) · nested globals instanced (not baked) · variant/token coverage —
`tests/r4_figma_bridge.py` asserts it. An unmatched component/token is a flagged **gap** (local build /
numeric fallback), never a fabricated reference. One-way only.
