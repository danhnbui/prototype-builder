# Product Builder / Test `figma-use` skill + `/pb:build-figma-handoff` (safe dry-run, no Figma writes)

> Paste everything below the line into Claude Code, running inside this repo. Fill in `{{FIGMA_FILE_URL}}` with a **throwaway** Figma file (never a production or published-library file). This plan is read-only + dry-run; it must not write anything to Figma.

---

You are testing two things in this repo: the new skill `pb/skills/figma-use/SKILL.md` and the command `pb/commands/build-figma-handoff.md` (invoked as `/pb:build-figma-handoff`). This is a **safe behavioral test**: prove the wiring and the plan are correct **without writing to Figma**. Work through the phases in order. After each phase, print a short PASS/FAIL line. If a phase fails or hits a HARD FAIL, **stop and report — do not work around it**.

## Hard constraints (do not violate)

- **NEVER write to Figma.** Read-only Figma tools only: `whoami`, `get_metadata`, `get_screenshot`, `get_design_context`, `get_variable_defs`, `search_design_system`. **Forbidden this run:** `use_figma`, `create_new_file`, `upload_assets`, `add_code_connect_map`, `send_code_connect_mappings`, or any create/update of a node, variable, component, or file.
- **NEVER run past Gate G-FP5.** Stop at the printed push plan.
- **NEVER use `--force`.** Do not skip the no-op or batch guards by force.
- **NEVER edit a project file** (registry.json, figma-transfer.json, the command, the skill, the templates) **except** in Phase 2, and there only after showing me the diff and getting an explicit "yes".
- **NEVER auto-add a variant axis** or invent data to make a gate pass.
- If a Figma call would write, cost money, or touch a file other than the throwaway, **stop and ask first**.

## Preconditions

1. Restart Claude Code first so the plugin picks up the new `figma-use` skill (plugin skills load at startup).
2. Confirm the Figma MCP is connected and on a Dev seat (MCP access). Run `whoami`; if it fails, stop — the test can't proceed.
3. Throwaway Figma file: `{{FIGMA_FILE_URL}}`.
4. Test fixture: the `selftest/` project (DS = `calm-ds`, 3 components, 2 screens). Do not use `demo-auth`/`demo-import`/`handoff-bundle` — their registries are empty and will HARD FAIL at G-FP1.

---

## Phase 1 — Static validation (no Figma)

1. **Skill discoverable:** list available skills and confirm `figma-use` is present. Print its `name` + first line of `description`.
2. **YAML frontmatter valid:** parse the frontmatter block of `pb/skills/figma-use/SKILL.md` with a real YAML parser (e.g. `python3 -c "import yaml,recat..."`). Assert it loads as a mapping with non-empty `name` and `description`, and that the `description` contains **no `": "` (colon-space)** sequence. Print OK or the exact error.
3. **Field-consistency:** for every registry field the skill references (`anatomy.parts[].token.name`, `spec.stack[]`, `screen.elements[].tokens[]`, `properties[]`, `dsMatch.*`, `decisions.defaultSizing`, the local-token collection name, `rootFrameId`), grep `pb/commands/build-figma-handoff.md` and `pb/template/figma-*.json` and confirm each exists with a matching name. **Explicitly check** whether `dsMatch.figmaComponentId` (command) vs `dsMatch.componentId` (transfer template) still disagree.

**Expected:** skill loads; YAML parses; one known mismatch (`dsMatch` key name) unless already fixed.

## Phase 2 — Fix known findings (optional, gated by my approval)

Only if I say "fix findings". For each, show a diff and wait for "yes" before writing:

- **#5 `dsMatch` key:** pick one name and make `build-figma-handoff.md`, `figma-transfer.template.json`, and `figma-use/SKILL.md` agree.
- **#2 raw-px spacing:** in `selftest/registry.json`, the screen `layout.gap`/`layout.padding` values (18/32/12/48) are raw px, not tokens. Propose mapping them to `calm-ds` spacing tokens (or document the exception).
- **#3 variant smell:** `components[].properties[].value {0,4}` is demo state modeled as a variant axis. Decide with me whether `value` is a real variant axis or should move out of `properties[]` so it doesn't mint `value=0`/`value=4` variants.

If I don't say "fix findings", **skip this phase** and test the raw behavior as-is.

## Phase 3 — Dry-run behavioral test (read-only Figma)

Run: `/pb:build-figma-handoff --scope=both --dry-run --batch` against `selftest/`.

Walk every gate and record actual-vs-expected:

| Gate | Expected |
|---|---|
| G-FP1 | `whoami` ok; no `figma-transfer.json` → prompts for the Figma URL and seeds it with `dsMatch.library = calm-ds`; asks for page + root frame |
| G-FP2 | audit = **3 new components**, **2 new screens**, **3 axis-change** (`value`); batch guard satisfied by `--batch` |
| G-FP3 | proposes matches for **`--brand`, `--radius-small`, `--font-heading`** via `search_design_system` (read-only) |
| G-FP4 | proposes `calm-ds` matches for the 3 components; NO-MATCH → "create-local" in the plan |
| G-FP5 | prints the full push plan **and stops** — the plan must state auto-layout on every frame, token binding (no raw hex/px), `prop=value` variant naming, and instances (not copies) for matched components |

Then **prove no writes happened**: confirm the throwaway Figma file is unchanged (no new nodes/variables) and `git status` shows no project files modified (beyond any Phase-2 edits I approved).

## Phase 4 — Read-back rituals (on paper)

A dry-run writes nothing, so confirm the **plan text** asserts the skill's read-back invariants: `layoutMode ≠ NONE`, 0 absolute children, 0 raw px, variants collapsed into a ComponentSet, matched elements as instances. Confirm the **raw-px spacing** (finding #2) is flagged by the plan.

## Phase 5 — Report

Print a table: `skill loaded`, `YAML valid`, `fields consistent`, each gate `behaved per spec?`, `zero Figma writes confirmed`, plus any findings. End with a one-line **go / no-go** for a live (writing) push, and the smallest next step if go.

---

## Optional Phase 6 — first real write (opt-in, separate, irreversible)

Do **not** start this unless I explicitly say "do the live write". Then, on the throwaway file only: `--scope=components --organism=primary-button` (one component), pause at G-FP5, and **wait for my "yes" on the plan** before the single write. Verify the created ComponentSet has auto-layout + the `value` variants, then stop.
