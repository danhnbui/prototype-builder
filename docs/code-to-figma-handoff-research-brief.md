# Why Code→Figma Handoff Fails — and How Others Fix It

*A tool-agnostic research brief. Compiled June 2026.*

Scope: why AI / LLM-driven code-to-Figma handoff routinely loses **auto-layout, images, graphics, alignment, components, and variants** — the root cause of each, and the techniques the ecosystem uses to solve them. Closes with the practical question: *can the same fixes be delivered as documents or skills?* (Short answer: yes — that is already the ecosystem's delivery mechanism.)

---

## TL;DR

The problem is not that the model is weak. It is that **code and Figma are two structurally different representations**, and unless something translates layout *intent* into Figma's typed node tree, the Figma Plugin API silently defaults to the lowest-fidelity option at every branch: no auto-layout, flattened variants, no image bytes, raw frames instead of components. Every tool that does this well inserts the same two things between the code and the canvas — **a structured intermediate representation** and **design-system context**.

---

## Summary table

| Failure mode | Root cause (why it happens) | How the ecosystem fixes it |
|---|---|---|
| **Auto-layout missing** | Plugin API `layoutMode` defaults to `NONE`; the model replicates coordinates instead of translating Flexbox/Grid intent | Parse Flexbox/Grid → set `layoutMode` + padding + `itemSpacing`; enforce "auto-layout on every frame" |
| **Components flattened** | The model has no design-system context — it doesn't know which components or props exist | Component mapping + `search_design_system` + Code Connect to bind to existing components |
| **Variants lost** | Plugin API **cannot add `VARIANT` properties directly**; variants only exist if layer names follow `prop=value` and are combined into a set | Generate variant layers by naming convention, then `combineAsVariants` / `appendChild` into a ComponentSet |
| **Images missing** | `createImage` takes raw PNG/JPEG/GIF bytes ≤4096px; `createImageAsync(url)` needs `allowedDomains` + must clear CORS; an image is a *fill on a shape*, not a layer | Asset pipeline: fetch → encode / whitelist domain → create shape → apply `ImagePaint` fill |
| **Graphics / SVG / icons lost** | Figma **cannot use a vector as a fill**; SVG must be imported via `createNodeFromSvg`; complex art needs rasterizing | Route icons through `createNodeFromSvg`; rasterize illustrations to image fills |
| **Alignment / spacing off** | Spacing is pixel-visual, not token-semantic; coordinates ≠ tokens; no constraints or sizing rules | Map `align-items` / `justify-content`, snap to the spacing scale, use hug/fill sizing bound to tokens |

---

## The core reason: a representation gap, not a model failure

An LLM is fluent in text and code. Figma is **not** text — it is a typed tree of nodes (frames, components, variables, paints) with strict rules about how layout, fills, and variants may be expressed. Going from code to Figma is therefore a *translation between two heterogeneous representations*, and that is exactly the class of problem where naive LLM output is known to be buggy.

Research on LLM code translation is blunt about this: models "produce buggy code translations" when asked to go straight from source to target, and translation quality improves measurably when you insert an **intermediate representation** — a natural-language summary or an abstract syntax tree — between the two. One study ("NL in the Middle") found chain-of-thought with an intermediate summary lifted successful translations by **6–14%**. The same principle underpins compiler design: LLVM's IR decouples source languages from target machines so each side only has to map to the middle, not to every other endpoint.

Code→Figma has the identical shape. The tools that win insert that middle layer. The tools that fail hand the model raw HTML (or, worse, a screenshot) and ask it to emit Figma API calls directly — at which point every ambiguous decision resolves to the Plugin API's low-fidelity default.

**Every robust solution carries two ingredients:**

1. **A structured intermediate representation** — not a screenshot, not raw markup, but a typed description that explicitly names layout direction, spacing tokens, component references, and variant axes.
2. **Design-system context** — knowledge of which components, tokens, and variants *already exist*, so the output **binds to them** instead of reinventing them as ad-hoc frames and hard-coded hex values.

The six failure modes below are all symptoms of one or both ingredients being absent.

---

## The six failure modes in detail

### 1. Auto-layout missing

**What you see:** elements land at absolute X/Y coordinates; nothing reflows; resizing the frame breaks everything.

**Root cause:** in the Figma Plugin API a frame's `layoutMode` **defaults to `NONE`**, which means absolute positioning. Auto-layout only happens if something explicitly sets `layoutMode` to `HORIZONTAL`/`VERTICAL` and fills in `itemSpacing`, padding, and alignment. When the model works from pixel coordinates it has nothing to translate *into* those properties, so it leaves them at the default. Figma's own guidance is explicit that absolute-positioned frames "produce absolute positioning in code — rarely what you want."

**How others fix it:** treat Flexbox/Grid as the source of truth and map it across. Figma Auto Layout is deliberately a near-one-to-one mirror of Flexbox — `flex-direction` → `layoutMode`, `gap` → `itemSpacing`, `padding` → padding, `align-items`/`justify-content` → the alignment matrix. Importers like html.to.design parse the page's Flexbox during import and emit auto-layout frames automatically. The operative rule everyone repeats: **auto-layout on every frame, no absolute children.**

### 2. Components not reused (flattened to raw frames)

**What you see:** a button that should be one instance of your design-system Button is rebuilt as a naked rectangle + text, with hard-coded color and padding.

**Root cause:** the model has no idea your design system exists. As one widely-cited post-mortem put it, "the model had no understanding of what the design system actually was — which components existed, which props were valid, which tokens had to be used." With no library to bind to, it manufactures primitives.

**How others fix it:** give the model the library and force binding. Builder.io's Visual Copilot adds **component mapping** — it matches reusable elements to components that already exist and emits instances of them. The Figma MCP server exposes `search_design_system` so an agent can look up the real component before building. **Code Connect** closes the loop the other way, linking published Figma components to their code implementations so the mapping is durable rather than guessed each run.

### 3. Variants flattened

**What you see:** Button/Primary, Button/Hover, Button/Disabled arrive as three unrelated components instead of one component set with a `state` property.

**Root cause:** this one is a hard API constraint, not just missing context. The Figma Plugin API **does not allow you to add component properties of type `VARIANT` directly.** Variants exist only because Figma *parses layer names*: you must name each variant `property=value` (e.g. `state=hover, size=md`) and then combine them into a `ComponentSetNode` (via `combineAsVariants`, or `createComponent` + `appendChild`). A model that doesn't know this naming-and-combining ritual produces a pile of standalone components, and the variant axes vanish.

**How others fix it:** encode the convention deliberately — generate each variant as a properly named component, then assemble the set programmatically. Importers that "convert hover states as components" are doing exactly this under the hood. The corollary safety rule most pipelines adopt: **never auto-invent a new variant axis** — surface it for human confirmation, because a wrong axis silently corrupts the set.

### 4. Images missing

**What you see:** `<img>` elements and background images come through as empty grey boxes.

**Root cause:** images in Figma are not layers — they are a **paint (`ImagePaint`) applied as a fill to a shape**, so the model must (a) create a shape and (b) attach an image fill, which is non-obvious. The byte path, `createImage`, only accepts **raw PNG/JPEG/GIF bytes, max 4096×4096px** — it will not take a URL. There *is* a URL path, `createImageAsync(url)`, but it only works if the domain is whitelisted in the plugin's `networkAccess.allowedDomains` **and** the host clears CORS (plugin iframes have a null origin, so they can only fetch from servers sending `Access-Control-Allow-Origin: *`). Miss any of these and the image silently never lands.

**How others fix it:** build an explicit **asset pipeline** as a first-class step: collect every image reference, fetch or read the bytes (whitelisting domains / handling CORS), encode to a supported format and downscale to ≤4096px, create the host shape, and apply the `ImagePaint` fill — then record the reference so re-runs don't duplicate it.

### 5. Graphics / SVG / icons lost

**What you see:** inline SVG icons and vector illustrations disappear or turn into broken boxes.

**Root cause:** related to #4 but worse — Figma **cannot use a vector as an image fill at all** (a long-standing, documented limitation). SVG cannot ride the `createImage`/`ImagePaint` path. Vectors have to be imported through a different door, `figma.createNodeFromSvg(svgString)`, which builds a real vector node from SVG markup. Anything too complex to express as a clean vector network (detailed illustrations, gradients-on-gradients) has to be **rasterized** first and then treated as an image. A pipeline that only knows the image path drops everything vector.

**How others fix it:** branch by asset type. Icons and simple line art → `createNodeFromSvg` so they stay crisp and editable; complex artwork → rasterize to PNG and route through the image-fill path from #4. Cleaning/flattening the SVG before import (one path set, no redundant groups) markedly improves the result.

### 6. Alignment / spacing off

**What you see:** everything is *almost* right — off by a few pixels, inconsistent gutters, ragged edges.

**Root cause:** in most source designs spacing is **visual, not semantic** — a designer nudged things until they looked right, so there is no `8px` token underneath, just a coordinate. As the token-vs-coordinate critique puts it: "pixel accuracy does not come from coordinates; it comes from tokens." When the bridge replicates coordinates, it inherits all the visual drift and has no spacing scale to snap to, and no sizing constraints (hug/fill) to keep things aligned as content changes.

**How others fix it:** make spacing semantic. Map CSS alignment (`align-items`, `justify-content`) onto Figma's alignment matrix, **snap measured gaps to the nearest step on the design system's spacing scale**, and express sizing as hug/fill bound to tokens rather than fixed pixel values. The alignment then survives content and breakpoint changes instead of being a one-time pixel match.

---

## Three cross-cutting causes worth calling out

These sit underneath all six modes:

- **Missing design-system context — the big one.** Without a list of real components, tokens, and variant axes, the model cannot bind, so it reinvents. Most of the perceived "AI is bad at this" is actually "the AI was never shown the system." Well-structured systems push code-gen fidelity to roughly *90% there* precisely because the model can read real spacing, type, and radii from the source.

- **Token-budget blowups.** Pulling design context is not free. The Figma MCP `get_design_context` response can blow past the **25,000-token** limit some clients impose, and a single complex page has been reported to return **350,000+ tokens**. When the context is truncated, the layout/variant/token data needed to do the job correctly is the first thing lost — so robust workflows **scope to one frame/section at a time** and structure files to keep payloads small.

- **One-way blindness.** The agent "has no visibility into the final, rendered output of its own code" — it cannot see that a fill didn't land or a frame didn't auto-lay-out, so it cannot self-correct. Mature pipelines add a verification pass (re-read the node tree, screenshot-and-compare) to close that loop.

---

## Can we do the same with documents or skills?

**Yes — and that is already exactly how the ecosystem ships these fixes.** Three concrete, document-shaped mechanisms:

1. **Skills (`SKILL.md`).** Figma's own answer to code↔design is a set of **markdown skill files** — `figma-use` (the foundational "how to write frames, components, variables, layouts to canvas"), `figma-generate-design`, and `figma-code-connect`. A skill is "a predefined, reusable set of markdown instructions and supporting files that teaches an MCP client how to complete a specific task." In other words, the cure for "the model defaults to the dumb option" is a document that spells out the non-obvious rituals: *auto-layout on every frame; variants via `prop=value` naming then combine; images are a fill on a shape; icons go through `createNodeFromSvg`.* The model stops guessing because the procedure is written down.

2. **A structured intermediate representation as a contract.** This is the "NL/AST in the middle" research finding applied to design: instead of handing over raw HTML, hand over a **typed description** of each screen — nodes, the token each property resolves to, which existing component an element maps to, and the explicit variant axes. A JSON/spec document like this *is* the IR that the translation research shows lifts fidelity. It also keeps payloads small, which directly addresses the token-budget problem.

3. **The design system as a scannable document.** A compact component-and-token **index** is the cheapest way to supply the missing DS context. Binding-not-reinventing only becomes possible once the model can see "here are the components that exist and the tokens you must use." A markdown DS reference plus a tokens map is enough to flip most of the failure modes.

The throughline: **none of these are bespoke applications.** They are documents — instruction skills, an IR contract, and a DS index — which is precisely why this approach is reproducible in a markdown-native, skills-based setup rather than requiring a custom plugin.

---

## Sources

- [Why "Figma to Code with AI" Keeps Failing (And the System That Finally Works) — Medium](https://medium.com/@forgiving_dust_cat_355/why-figma-to-code-with-ai-keeps-failing-and-the-system-that-finally-works-7d10081f392c)
- [How to structure Figma files for MCP and AI-powered code generation — LogRocket](https://blog.logrocket.com/ux-design/design-to-code-with-figma-mcp/)
- [Guide to the Figma MCP server — Figma Help Center](https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Figma-MCP-server)
- [Design to Code with the Figma MCP Server — Builder.io](https://www.builder.io/blog/figma-mcp-server)
- [Figma skills for MCP — Figma Help Center](https://help.figma.com/hc/en-us/articles/39166810751895-Figma-skills-for-MCP)
- [Create skills for the Figma MCP server — Figma Developer Docs](https://developers.figma.com/docs/figma-mcp-server/create-skills/)
- [figma/mcp-server-guide — figma-use SKILL.md (GitHub)](https://github.com/figma/mcp-server-guide/blob/main/skills/figma-use/SKILL.md)
- [html.to.design — Convert any website into fully editable Figma designs](https://html.to.design/home/)
- [From web to Figma with full auto layout, font mapping and more — Medium](https://medium.com/@to.design/from-web-to-figma-with-full-auto-layout-font-mapping-and-more-a14a3c86c250)
- [Introducing Visual Copilot: A Better Figma-to-Code Workflow — Builder.io](https://www.builder.io/blog/figma-to-code-visual-copilot)
- [ComponentSetNode — Figma Plugin API](https://developers.figma.com/docs/plugins/api/ComponentSetNode/)
- [layoutMode — Figma Plugin API](https://developers.figma.com/docs/plugins/api/properties/nodes-layoutmode/)
- [Working with Images — Figma Plugin API](https://developers.figma.com/docs/plugins/working-with-images/)
- [createImageAsync — Figma Plugin API](https://www.figma.com/plugin-docs/api/properties/figma-createimageasync/)
- [Integrating Flexbox Principles with Figma Auto Layout — PROS / Ascend UX](https://pros.com/ascend/integrating-flexbox-principles-with-figma-auto-layout/)
- [NL in the Middle: Code Translation with LLMs and Intermediate Representations (arXiv)](https://arxiv.org/pdf/2507.08627)
- [How We Use AI to Turn Figma Designs into Production Code — monday engineering](https://engineering.monday.com/how-we-use-ai-to-turn-figma-designs-into-production-code/)
