---
name: figma-use
description: Foundational skill for writing to a Figma canvas via the Figma MCP (use_figma, create_new_file, upload_assets). MANDATORY before any Figma write performed by /pb:build-figma-handoff Step 6. Encodes the fail-closed rituals that prevent the common code-to-Figma failures — auto-layout on every frame, token/variable binding (no raw hex/px), variants via prop=value naming combined into a ComponentSet, images as fills on shapes, icons via createNodeFromSvg — plus a post-write read-back self-check. DS-neutral, never hardcoding a design-system name. Use whenever creating or updating frames, components, variants, variables, or image/vector assets in Figma.
---

# figma-use

The foundational write-to-Figma procedure. **Load this before every `use_figma` / `create_new_file` / `upload_assets` call** in `/pb:build-figma-handoff` Step 6. It reads from `registry.json` (`components[]` / `screens[]`) and the contracts `figma-transfer.json` + `figma-tokens.json`.

This skill is the **guided** layer (skill-only). It does not replace the command's gates; it tells you exactly *how* to write each node so the six known failure modes never occur. The hard, fail-closed equivalents (a pre-flight-contract gate and a verification gate inside the command) are a separate, later step.

## The one rule

**Fail-closed, never fall back.** Every ritual below has a *forbidden default* that Figma's API silently falls into. If you cannot satisfy a ritual from the registry, **STOP and surface it** — never emit the degraded version (absolute positioning, raw hex, a standalone variant, an empty image box). There is no "do it badly" branch.

## DS-neutral rule

Never write a literal design-system name. Read it from `memory/constitution.md` → Design System Lock, mirrored as `figma-transfer.json.dsMatch.library`. Everywhere this skill writes `{DS}`, substitute that value.

---

## Pre-write contract (confirm before any write)

For the in-scope slice, confirm the registry **declares** all of the following. Any missing field → STOP, do not guess:

- **Layout** — every frame/screen has a layout intent (direction + spacing) expressible as auto-layout.
- **Token** — every color, spacing, radius, and type value resolves to a token name (`component.anatomy.parts[].token.name`, `component.spec.stack[]`, `screen.elements[].tokens[]`, **and any `var(--name)` in the `render` bodies**), already mapped in `figma-tokens.json` or queued for G-FP3.
- **Binding** — every element has a component binding: a `dsMatch.figmaComponentId` (instance) **or** an explicit `create-local` decision.
- **Variant axes** — every multi-state component declares its axes in `properties[]`.
- **Asset** — every image/graphic has a descriptor (source, format, intended node type).

---

## Rituals (per node type)

### 1. Frames & layout — auto-layout on every frame (R3)
- Set `layoutMode` to `HORIZONTAL` or `VERTICAL` on **every** created frame.
- Set `paddingLeft/Right/Top/Bottom` and `itemSpacing` from spacing tokens — never ad-hoc pixels.
- Sizing: default **hug-V / fill-H** (`figma-transfer.json.decisions.defaultSizing`); use explicit `sizing.width`/`sizing.height` when present (`primaryAxisSizingMode` / `counterAxisSizingMode`).
- Map alignment from the source: `align-items` → counter-axis align, `justify-content` → primary-axis align.
- **NEVER** leave `layoutMode = NONE`. **NEVER** position a child absolutely. A child that can't be expressed as auto-layout is a **HARD FAIL**, not an absolute-position fallback.

### 2. Tokens & variables — bind everything
- Bind every fill, stroke, spacing, radius, and typography property to its Figma **variable** (`figma-tokens.json` VariableID).
- Unmapped token → **pause at G-FP3**; default a no-match to a local variable in the `Prototype tokens` collection — never to a raw value.
- **NEVER** write a raw hex or raw px when a token exists or could be created.

### 3. Components — build from anatomy, reuse the library
- Build each `create-local` component from `anatomy.parts[]` + `spec.stack[]` + `properties[]`, **with auto-layout** (ritual 1).
- A `dsMatch.figmaComponentId` element is inserted as an **instance** of the `{DS}` component — never a re-built local copy.
- **NEVER** flatten a component into a raw frame when a binding exists.

### 4. Variants — name then combine
- Name each variant by convention: `prop=value, prop2=value2` (e.g. `state=hover, size=md`), exactly matching the axes in `properties[]`.
- Combine the named variants into one `ComponentSetNode` (`combineAsVariants`, or `createComponent` + `appendChild`). The Plugin API cannot add VARIANT properties directly — the naming **is** the mechanism.
- **NEVER** emit standalone, unrelated components for states. **NEVER** auto-add a new axis — surface it as `axis-change` (G-FP2) for confirmation.

### 5. Images — a fill on a shape, never a layer
- An image is an `ImagePaint` **fill applied to a shape** — create the shape first, then attach the fill.
- Bytes you already have → `figma.createImage(bytes)` (PNG/JPEG/GIF, **≤ 4096×4096px** — downscale first if larger).
- Remote URL → `figma.createImageAsync(url)`; the host domain **must** be in `manifest.networkAccess.allowedDomains` and clear CORS (plugin iframes are null-origin, so the server must send `Access-Control-Allow-Origin: *`).
- **NEVER** skip a declared image silently. Missing/blocked bytes = **HARD FAIL**, not an empty box.

### 6. Graphics / icons / SVG — branch by asset type
- Icon or simple vector → `figma.createNodeFromSvg(svgString)` so it stays crisp and editable.
- Complex illustration → **rasterize** to PNG (≤ 4096px) and route through ritual 5. Figma cannot use a vector as a fill.
- Declare the branch per asset in the descriptor; **NEVER** attempt vector-as-fill.

---

## Read-back self-check (after every write)

You are blind to your own rendered output unless you re-read it. After each `use_figma` write, re-read the node tree for what you just created and assert:

- Every created frame has `layoutMode != NONE` and **0** absolutely-positioned children.
- **0** raw hex / raw px — every fill, stroke, spacing, radius, and type value is bound to a variable.
- Every multi-state component resolved into a `ComponentSetNode` carrying the expected axes from `properties[]`.
- Every declared image node has a **non-empty `ImagePaint` fill**; every declared icon is a vector node.
- Every `dsMatch` element is an **instance** of the `{DS}` component, not a local copy.

Any assertion fails → **STOP, report which one, log it.** Do not declare the push successful.

---

## NEVER (forbidden fallbacks)

- NEVER position a frame child absolutely — auto-layout on every frame, or HARD FAIL.
- NEVER inline a raw hex/px when a token is missing — pause, don't degrade.
- NEVER emit standalone components for variant states — name `prop=value` and combine, or stop.
- NEVER drop a declared image — missing bytes is a failure, not an empty box.
- NEVER rasterize an icon that can be a clean vector, and NEVER vector-import a complex illustration.
- NEVER declare success without the read-back self-check.
- NEVER advance past a missing pre-write-contract field by guessing.
- NEVER hardcode a design-system name — always resolve `{DS}` from config.
- NEVER reconcile Figma → registry here; this skill writes one way only.

---

## Order of operations (mirrors command Step 6)

1. Tokens — create/confirm local variables; record VariableIDs.
2. Components (skip if scope = screens) — build `create-local` with auto-layout; record `componentSetId`/`componentId`; DS-matched → record binding only.
3. Screens (skip if scope = components) — frame per screen in `rootFrameId`; each element a child **with auto-layout**; DS-matched elements as **instances**; record `frameId` + element map.
4. Token bindings — bind each computed property to its VariableID.
5. Instance bindings — point each instance at the correct `{DS}` component.
6. **Read-back self-check** (above) before reporting done.
