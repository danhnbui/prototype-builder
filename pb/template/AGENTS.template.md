# {{PROJECT_NAME}} — prototype hand-off

> {{SUMMARY}}

This folder is a **Product Builder** hand-off, produced `{{DATE}}` (registry schema
`v{{SCHEMA_VERSION}}`, mode: `{{MODE}}`). It is self-contained — everything needed to view
or continue the prototype is here.

## What's in this folder

- **`prototype.html`** — the prototype as a single, view-only, self-documenting page. Open it
  in any browser. It is a **derived snapshot** — do not hand-edit it; your edits would be lost
  the next time it's regenerated from the source.
- **`bundle/`** — the actual source of truth: `registry.json` (the state), `render/` (the
  render body files), `design-system/`, and `memory/` (the constitution + decision log).

## If you're here to *view* it

Open `prototype.html`. Nothing to install.

## If you're here to *continue building* it

You need Product Builder (the `pb` plugin) and Python 3. Then, in a fresh directory:

```
/pb:init --import bundle
```

That ingests the bundle into a new project you can drive with `/pb:build`, `/pb:preview`,
and the rest of the `/pb:*` commands. `--import` checks the registry's schema version and
tells you to run `/pb:update-version` if this bundle predates your installed pb.

### The rules that keep it cheap and correct

1. **State lives in `registry.json`.** Edit only the touched slice. `prototype.html` is never
   the source of truth and is never hand-edited.
2. **Render is deterministic and batched.** `prototype.html` is regenerated from the registry
   by `render.py` — on `/pb:build --render` and automatically at hand-off. Never write it by hand.
3. **The gate runs only on trio changes** — a screen, a component, or logic. Pure cosmetic
   tweaks skip it.

The `render/` tree is required — without it the registry's `renderSrc` references dangle and
nothing renders. Keep `bundle/` intact when you copy it.
