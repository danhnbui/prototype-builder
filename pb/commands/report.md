---
description: Scan this project's memory, decisions log and context, and write one retrospective report of what its history says Product Builder should change in the next release. Read-only on the project; the report is the only file written.
---

# /pb:report [--since <date>] [--sessions] [--out <file>]

Turn one project's history into evidence for the **next pb release**. The reader is the Product
Builder maintainer, not the project owner. The question is never "what should this prototype do
next". It is "what did pb make this project do twice, by hand, or around it".

A tool gathers the facts: counts and `file:line` evidence over the decisions log, `memory/`, the
backups, the explore manifests, the render bodies, the registry and, when asked, the session
transcripts. You read those facts and write the proposals. **Read-only on the project.** The
report is the one file written.

> Why a tool and not a read-through: the logs this was built for run 3,000 to 10,000 lines, out of
> date order, beside 40 backup folders. Counting that by eye is slow and comes out different each
> time (DESIGN.md I-6 (c)). Interpreting the counts is not arithmetic, so that part stays here.

## 0 · Flags

| Flag | Does |
|---|---|
| *(none)* | Every fact over the whole history → `memory/reports/pb-report-<YYYY-MM-DD>.md` |
| `--since <YYYY-MM-DD>` | Window the dated facts: decisions entries, backups, explore rounds, sessions. Shape, performance, tests and hygiene always describe the project as it is now |
| `--sessions [<dir>]` | Also scan the Claude Code session transcripts for this folder, `~/.claude/projects/<slug>/*.jsonl`, where the slug is the project path with every non-alphanumeric character turned into `-`. Give `<dir>` when the sessions ran from another folder, such as the repo root of an adopt-in-place `.prototype/`. **Opt-in.** Counts and sequences only |
| `--out <file>` | Write the report somewhere else. A second run on the same day overwrites the default path, so pass `--out` to keep both |

The tool also takes `--json` (the facts on stdout, for machine use). This command does not need it.

## 1 · Gather the facts

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/report.py" --project . --out memory/reports/pb-report-<YYYY-MM-DD>.md [--since <date>] [--sessions [<dir>]]
```

Pass through the flags the user gave. Exit 2 means there is no `registry.json` here: say so and
stop, and do not go looking for one elsewhere. The tool finds an adopt-in-place `.prototype/` by
itself.

It writes ten sections, always in this order, each one `(none)` when empty:

| § | Facts | The pb question behind them |
|---|---|---|
| 1 Project shape | schema vs `CURRENT_SCHEMA`, DS source, counts, body and sidecar trees, every `memory/` entry with its owner | Did the project need context files no command writes? |
| 2 Decisions log | entries per week, undated entries, date-order breaks, size vs the 500 KB rotation threshold, back-and-forth vocabulary per term, empty `Alternatives:` and `Rule:`, recurring topics | What was decided twice? Which decisions skipped their alternatives? |
| 3 Commands, flags, skills | every `/pb:*` and flag named in `memory/`, retired and unknown names, skills never assigned in `tasks.md`, degrade and gate notices, command chains | Which names or flags did people reach for that pb does not have? |
| 4 Explore | rounds, options, scores, unscored cells, leftover `render/_candidates/`, decisions that name a rejection | Did exploring produce a pick, or another round? |
| 5 Backups | `memory/backups/` count and size, the `pre-*` cadence | How often did a write feel risky enough to snapshot first? |
| 6 Performance | render stages timed in process against DESIGN.md's budgets, registry size by key, `lint_registry.py --strict` counts | Is the loop still fast at this project's size? |
| 7 Tests | runnable vs prose scenarios, last results, stale and undated verdicts | Are the verdicts evidence, or old? |
| 8 Sessions | runs per command, typed vs invoked, run sequences, human turns between builds, compactions, interrupts, `touch registry.json` rituals, plugin tool runs | Which jobs took several commands, or a ritual? |
| 9 Hygiene | candidate headers left after a promote, comment-dated layers in bodies | What does a promote or a long edit leave behind? |
| 10 Workarounds | hand-written memory files, the project's own script folders, backup copies, zero-byte files, rituals named in decisions | What did the project build around pb? |

Every number is a deterministic count over the files, except the timings in §6, which the file
labels as measured.

## 2 · Read the facts, then write the proposals

Read the whole facts file. Then **append** two sections to it, below the `<!-- facts end -->`
marker. Never edit the facts above it.

### `## Reading`
Five to ten lines on what this project's history says about pb, in the maintainer's terms. Name the
facts that cluster: a recurring topic whose entries also carry `revert`, or a `pre-*` backup a day in
the same week as twenty explore entries. Name the facts that are only this project's taste. When a
count alone could mislead, open the evidence lines it cites (a `wrong` in an entry about a wrong
Figma node is not pb's fault), and say which lines you checked.

### `## Proposals for the next pb release`
A numbered list, **ranked by cost to this project**, most expensive first. Each proposal has four
parts:

1. **Observed.** The pattern, citing the fact by section and value (`§5: 39 pre-* backups over 7 days`)
   and at least one evidence line (`memory/decisions.md:751`).
2. **Cost here.** What it cost this project: rework, a wrong "done", a ritual, a file nobody owns.
3. **Change.** The pb change, concrete enough to file: a tool fix (file and function), a command or
   flag change, a skill contract, a schema addition (additive, AGENTS.md §3), or a docs fix.
4. **Tag.** One or more of `[tool]` `[command]` `[skill]` `[schema]` `[docs]`.

Judge cost from the facts. Repeated work ranks first (recurring topics carrying back-and-forth
terms, explore rounds without a pick). Work that misled comes next (stale verdicts, candidate
headers, an unknown command named as if it ran). Friction comes last (rituals, hand-written context
files, multi-command chains). A proposal with no fact behind it stays out of the list. If the
project owner raised it, put it on a final **Unbacked** line, labelled as such.

Before writing a proposal, check it against what already shipped: `changelog.md` under
`[Unreleased]`, and the command files. When pb already made the change, the finding is that the fix
did not reach this project (an old plugin version, a schema behind `CURRENT_SCHEMA`). Say that
instead of proposing it again.

End with one line naming the two proposals that would have saved this project the most.

## 3 · Where it lands

`memory/reports/pb-report-<YYYY-MM-DD>.md`, beside the memory it reads. It is a project-level
artifact and stays in the project. `/pb:handoff` mode 1 (everything) can carry it in the bundle
beside `memory/constitution.md` and `memory/decisions*.md`, which is how a report from someone
else's project reaches the maintainer. Mode 1's bundle list names only those two today, so when the
report should travel, say so at hand-off time. Print the path and the top three proposals, one line
each.

## NEVER
- NEVER write anywhere but `--out`. Not the registry, not a render body, not another file in `memory/`.
- NEVER edit `registry.json` or a render body to fix what the report found. The report is for the
  maintainer; fixing the project is `/pb:build`.
- NEVER quote session message text: not a prompt, not a command argument, not a paraphrase of one.
  Sessions contribute counts and sequences only.
- NEVER turn a project-owner complaint into a pb proposal without the fact behind it.
- NEVER rewrite or reorder the facts above the `<!-- facts end -->` marker. The proposals cite them by
  section and value, and an edited fact breaks the citation.
- NEVER pass `--sessions` unless the user asked for it.
