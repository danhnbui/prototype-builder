# Figma Push — Integration Brief

**Target version**: `spec-kit-extension-prototype-builder@v0.4.0` (next minor bump)
**Status**: v1 scope, one-way (PB_DATA → Figma)
**Owner**: Danh

This brief explains how to add the `/speckit-prototype-builder-figma-push` command to your existing extension repo. Order matters — don't skip the smoke test.

## What's in the bundle

| File | Where it goes in your repo |
|---|---|
| `commands/figma-push.md` | `commands/figma-push.md` (alongside `build.md`, `handoff.md`) |
| `figma-transfer.template.json` | `assets/figma-transfer.template.json` (a new asset folder entry) |
| `figma-tokens.template.json` | `assets/figma-tokens.template.json` |

## Step 1 — Wire into `extension.yml`

Add this entry under `provides.commands:`:

```yaml
- name: "speckit.prototype-builder.figma-push"
  file: "commands/figma-push.md"
  description: "Push PB_DATA components and screens to a target Figma file via the Figma MCP. One command, three scopes (--scope=components|screens|both). Runs a 5-gate clarify pass before any irreversible write."
```

Bump the extension version to `0.4.0` in the same file. No new hooks — the command is manual-only.

## Step 2 — Extend `PB_DATA` in `assets/template.html`

Add three nullable keys to the existing organism + screen shapes. **Backwards-compatible** — pre-v0.4.0 PB_DATA without these keys works fine (they just get populated on first push).

In `PB_DATA.handoff.organisms[N]`:

```js
{
  // ...existing keys (id, name, renderFn, meta, properties, codeLayout, code, anatomy, spec, uiLogic, usage)
  figmaId: null,                    // string | null — set after first push
  figmaComponentSetId: null,         // string | null — set after first push
  dsMatch: null                      // { library, componentId, matchedAt, matchedBy } | null
}
```

In `PB_DATA.handoff.screens[N]`:

```js
{
  // ...existing keys (id, name, renderFn, elements, logicNotes)
  figmaFrameId: null                 // string | null — set after first push
}
```

No render-function changes needed — the existing `pbRenderHandoff*` helpers don't read these fields. They're purely identity for the push command.

## Step 3 — Extend `commands/scaffold.md`

At the end of scaffold (after step 8 confirms to user, before the final "Next steps" block), add a new step:

```markdown
### Step 9 — Seed Figma push contracts

Copy the templates from the extension's `assets/` folder into the project root:

\`\`\`bash
cp ./.specify/extensions/prototype-builder/assets/figma-transfer.template.json ./figma-transfer.json
cp ./.specify/extensions/prototype-builder/assets/figma-tokens.template.json   ./figma-tokens.json
\`\`\`

These files start empty. The first run of `/speckit-prototype-builder-figma-push` will prompt for the target Figma file URL and populate them.
```

This is opt-in for now — users who never push to Figma still get a clean working `template.html`. Their `figma-*.json` files just sit there unused.

## Step 4 — Add a CTA in template.html Tab 4-Screen

Match the v0.3.5 copy-popover pattern. In `pbRenderHandoffScreen()`, alongside the existing `Sync now` button, add:

```js
<button class="sync-button" onclick="openCopyPopover('/speckit-prototype-builder-figma-push --scope=screens', this)">
  Push to Figma
</button>
```

And in Tab 4-Component, alongside any existing CTAs:

```js
<button class="sync-button" onclick="openCopyPopover('/speckit-prototype-builder-figma-push --scope=components', this)">
  Push components to Figma
</button>
```

## Step 5 — Smoke test BEFORE committing

This is the critical gate. Do NOT publish the v0.4.0 tag until this passes.

1. Create a throwaway Figma file in your personal account. Get the URL.
2. In a fresh project (or a clone of one of your existing prototype repos), run scaffold + build to populate PB_DATA with a tiny example (1 organism, 1 screen).
3. Manually drop the three new files from this bundle into the extension folder under `.specify/extensions/prototype-builder/`. Update `extension.yml`.
4. Run `/speckit-prototype-builder-figma-push --scope=both --dry-run`. Verify:
   - G-FP0 asks for scope (or skips if you passed --scope)
   - G-FP1 catches the missing figma-transfer.json and prompts for the file URL
   - G-FP3 proposes token mappings against HIVE
   - G-FP4 proposes DS matches against HIVE
   - G-FP5 shows the full plan
   - The push EXITS at G-FP5 because `--dry-run` is set
5. Re-run without `--dry-run`. Approve at G-FP5. Confirm:
   - The Figma file now has the components + screens
   - `figma-transfer.json` was written with node IDs
   - `template.html` was edited with new `figmaId` fields, and is still parseable JS
   - The push log exists at `.specify/memory/figma-pushes/<timestamp>.log`
6. Run the same command AGAIN with no PB_DATA changes. Confirm G-FP1.5 fires:
   - `✓ No changes since last push. Nothing to do.`
7. Edit one organism in PB_DATA (add a variant). Re-run. Confirm:
   - G-FP2 surfaces the change as `axis-change`
   - The push updates the existing component, doesn't duplicate
   - Re-running again is a no-op

If all 7 pass → tag v0.4.0, push to your repo.

If any step fails → file the issue in your task list, fix the command body, re-run.

## Known limitations of v1 (documented constraints)

These are intentional. v2 / v3 / v4 deferred per the progressive-enhancement plan.

- **One way only**: Figma → PB_DATA reverse is NOT in v1. If a designer edits a pushed node in Figma, the next code-driven push will overwrite. The command surfaces this at G-FP5 (`figmaModifiedAt` check) with a warning but doesn't merge.
- **No library publishing**: The command writes to the file you point it at, never publishes to the team library. That step stays manual in the Figma UI.
- **No multi-breakpoint frames**: One responsive breakpoint per push. To push mobile + desktop versions, run twice with different `--screen=` args.
- **No auto-layout repair**: If PB_DATA's `sizing` is missing/incomplete, the heuristic defaults to `hug-V, fill-H`. The command doesn't try to infer auto-layout from the rendered HTML.
- **No image asset transfer**: SVG icons render as Figma vectors if they're inline SVG in the template. Raster images (PNG, JPG) are out of scope — replace them with inline SVG or HIVE-library icons before pushing.
- **No animation / interaction transfer**: PB_DATA's `uiLogic` is for documentation, not for Figma interactions. Prototype interactions in Figma still need manual wiring.

## When to upgrade beyond v1

If you find yourself wanting any of these, that's the trigger to start v2 planning:

- Designer edits in Figma > 30% of the time → need reverse direction
- Pushing to >1 file per project → need a multi-target contract
- Pushing same components to multiple Figma libraries → need library-aware routing
- Pushing more than ~50 organisms or ~20 screens → need a sharded push protocol
- Stakeholders editing the pushed file directly (not just designers) → need a stronger ownership boundary

Each of those is a separate small project, not a v1 retrofit. Build v1, ship it, see what actually breaks.

## Next concrete actions

1. Review the three files in this bundle.
2. Run the Step 5 smoke test against a throwaway Figma file.
3. If it passes, drop the files into your extension, bump to v0.4.0, tag.
4. If anything in the command body is unclear or doesn't work in practice, file what needs revising and I'll iterate.

I'm happy to also draft: the Tab 4 CTA additions in `template.html`, a worked example of what a single-organism push produces in Figma, or the scaffold.md Step 9 extension. Ask if you want any of those.
