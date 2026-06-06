---
description: The cheap build loop. Apply a targeted patch to the touched registry.json slice, trio-gated (drift/Stack/DS gate only when a screen/component/logic changes), and NEVER re-render prototype.html per tweak. Use --render to regenerate the HTML.
---

# /pb-build — (Phase 1 skeleton)

**Status:** stub — full behavior lands in **Phase 3**.
**Purpose:** per prompt, read only the touched `registry.json` slice, apply a targeted patch, do NOT re-render per tweak. `--render` regenerates `prototype.html` deterministically.

When invoked now, state that this is a Phase-1 stub and print the purpose above. Honor the three loop rules in the [router](../../CLAUDE.md).
