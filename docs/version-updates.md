# Version Updates — Product Builder

Registry schema versioning for Product Builder. Keeps existing projects in contract
with newer plugin code without breaking existing workflows.

## schemaVersion vs plugin SemVer

`meta.schemaVersion` (an integer in `registry.json`) is intentionally independent of
the plugin's SemVer in `pb/.claude-plugin/plugin.json`:

| Version field | Bumps when |
|---|---|
| `meta.schemaVersion` | The registry or template **contract** changes — a new required field, a shape change, a renamed key |
| Plugin SemVer | Any release: features, fixes, docs, refactors |

**Current schema: 4** — defined as `CURRENT_SCHEMA` in `pb/migrations/manifest.py`.
An unstamped registry (no `meta.schemaVersion`) is treated as schema 2 (the v1.2 contract).

## When to bump CURRENT_SCHEMA

Bump `CURRENT_SCHEMA` only when you change the registry/template contract in a way
that would make the new plugin code incompatible with an old registry:
- Adding a field that the plugin now requires but old registries don't have.
- Changing the shape of an existing field (e.g. string → structured dict).
- Renaming a key.

Do **not** bump for: cosmetic command changes, new commands, docs updates, or changes
that don't alter what `registry.json` must contain.

## Authoring a version update

1. Increment `CURRENT_SCHEMA` in `pb/migrations/manifest.py`.
2. Create `pb/migrations/000N_slug.py` (next in numeric sequence):

   ```python
   FROM = N - 1
   TO = N

   def up(reg, base_dir=None):   # base_dir = the registry's dir, for sidecar files (e.g. render/*.js)
       import copy
       reg = copy.deepcopy(reg)
       # ... additive changes; set meta.schemaVersion last ...
       reg.setdefault("meta", {})["schemaVersion"] = TO
       return reg

   def down(reg, base_dir=None):
       import copy
       reg = copy.deepcopy(reg)
       # ... best-effort reversal ...
       reg.get("meta", {})["schemaVersion"] = FROM
       return reg

   def describe():
       return "vX.Y → vX.Z: <one-line summary of what changed>."

   def memory_notes():
       return None  # or an advisory string for the user to apply to constitution.md
   ```

3. Add `(FROM, TO, "000N_slug")` to `_REGISTRY` in `pb/migrations/manifest.py`.
4. Verify against a representative registry with `/pb:update-version` in dry-run mode (then
   `--apply` / `--rollback`) — confirm the round-trip restores the original.

### Authoring rules

| Rule | Detail |
|---|---|
| **Idempotent `up()`** | Running `up()` twice must produce the same result as once. |
| **Deep copy** | Both `up()` and `down()` operate on `copy.deepcopy(reg)` — never mutate the input. |
| **Stamp `schemaVersion`** | `up()` sets `meta.schemaVersion = TO`; `down()` sets it back to `FROM`. |
| **Memory rule** | `memory_notes()` is advisory only — surfaced to the user, never auto-written to `memory/`. |
| **Stdlib-only** | No new dependencies. Match the style of `render.py` and `serve.py`. |
| **No principle edits** | Version updates NEVER auto-edit `memory/constitution.md`, the Stack Lock, or the DS Lock. |

## dry-run / apply / rollback flow

```bash
# See the plan — writes nothing:
/pb:update-version

# Apply version updates:
/pb:update-version --apply

# Roll back to the latest backup:
/pb:update-version --rollback

# Target a specific version:
/pb:update-version --apply --to 3

# Operate on a non-default registry:
/pb:update-version --registry path/to/registry.json --apply
```

The runner (`pb/migrations/migrate_runner.py`) follows this sequence on `--apply`:

1. Read `meta.schemaVersion` (absent → 2).
2. If already at `CURRENT_SCHEMA`: print `✓ Already on schema N.` and stop.
3. Back up `registry.json` → `.pb-backups/registry.<from>.<ISO-ts>.json`.
4. Run the version-update chain **in memory** (no writes yet).
5. Validate: call `render.py`'s `build_html` on the result — if it raises, abort (nothing written).
6. Write `registry.json` once.
7. Re-render `prototype.html`.
8. Print a summary; surface any `memory_notes()` as an advisory block.

On failure **before** step 6: nothing written; backup preserved.
On failure **after** step 6: restore from backup; then report.

On `--rollback`: find the latest `.pb-backups/` entry (ISO timestamps → newest first),
restore it, re-render, confirm. **Backups are never deleted.**

## The advisory memory rule

Version updates NEVER auto-edit `memory/constitution.md`, the Stack Lock, or the DS Lock.

If a schema change implies a rule change (e.g. a new naming convention or a new
required field the user must populate), the version update's `memory_notes()` returns an
advisory string. The runner surfaces it at `--apply` time under an "Advisory" banner.
The user applies it by hand.

## Changelog convention

Each schema-bumping release should include a "Version updates" subsection in `changelog.md`:

```markdown
### Version updates
- `CURRENT_SCHEMA` → N: <brief summary of contract change>
- Version update `000N_slug`: <describe() text>
```

## Phase 3–4 non-goals (deferred — do not build now)

The following are out of scope for the current implementation. Note them here to
avoid re-debating them:

| Non-goal | Why deferred |
|---|---|
| **`init --import` auto-running the version update** | Needs UX decision on silent vs. interactive update at import time |
| **Richer lossy `down()` reversal** | Current `down()` is best-effort — it removes additive fields but does not strip structured data added in a newer schema (v1.2 code ignores unknown keys, so the registry remains usable) |

These become Phase 3–4 tasks.
