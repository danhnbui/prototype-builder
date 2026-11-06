"""
0012_others_out — schema 13 → schema 14.

`meta.others` was the free-form bucket behind the old "Others" sub-tab of Project Summary. D-33
retired the sub-tab and left the field: nothing reads it, nothing writes it, no schema describes it
(`lint_registry.py` warns R-RETIRED). On a project that used the bucket it can be most of the file —
one real registry carried about a third of its bytes in it — and, with the sub-tab gone, nobody can
read it any more either. This migration moves the content out of `registry.json` into a file a
person can open: `<project>/memory/others.md`.

What the section holds
----------------------
`up()` APPENDS one section to `memory/others.md` (creating the file and its folder if need be):

    ## meta.others (moved by migration 0012, <YYYY-MM-DD>)

      - a readable rendering — a dict is one `### <key>` per key, a list is one `### Item <n>` per
        entry, a string is printed as it is; a value that is not a string (a number, a nested
        object or list) is a fenced ```json block;
      - then a marker line and a fenced ```json block holding the EXACT original value. The
        readable half is for people; the JSON half is what `down()` reads, so the rollback never
        depends on parsing prose. Backticks inside the JSON are written as the `\\u0060` escape
        (still the same JSON value) so a value that contains a code fence cannot close this one.

Why it is lossless and reversible
---------------------------------
  - Nothing is emptied until the file write has succeeded; a failed write raises, the runner
    reports "Nothing written" and `registry.json` stays as it was.
  - Non-empty data with no `base_dir` cannot be written anywhere, so `up()` raises rather than
    drop it. (The runner always passes `base_dir`; pure in-memory callers with an EMPTY field are
    unaffected.)
  - Idempotent: if `memory/others.md` already holds a 0012 block whose JSON equals the value, it
    is not appended again (a re-run after a failed later step, or after `down()`, adds nothing).
  - `down()` restores the exact JSON from the LAST 0012 block, but only into an EMPTY field — it
    never overwrites `meta.others` someone has filled since. It does not delete the section or the
    file (it may have been edited or extended by hand); `up()` then recognises the block again.

The field is EMPTIED, not deleted (`AGENTS.md` §3: add, deprecate, let a major do the removing),
and keeps its type: `{}` for an object, `[]` for a list, `""` for a string. A bare number or
boolean (which no project has authored) becomes `null`.

up(reg, base_dir):
  - non-empty meta.others → memory/others.md (readable + exact JSON), then emptied in place
  - stamp meta.schemaVersion = 14
down(reg, base_dir):
  - empty meta.others and a 0012 block in memory/others.md → the exact original value restored
  - stamp meta.schemaVersion = 13
"""
import datetime
import json
import os
import re

FROM = 13
TO = 14

_MARKER = "<!-- pb:migration-0012 original-json (do not edit: `down` reads it) -->"
_HEADING = "## meta.others (moved by migration 0012, %s)"
_BLOCK = re.compile(re.escape(_MARKER) + r"\s*\n```json\n(.*?)\n```", re.S)


def _is_empty(value):
    return value is None or value == {} or value == [] or value == ""


def _empty_like(value):
    if isinstance(value, dict):
        return {}
    if isinstance(value, list):
        return []
    if isinstance(value, str):
        return ""
    return None


def _dump(value):
    # ` is a backtick: same JSON value, but it can never close the surrounding code fence.
    return json.dumps(value, indent=2, ensure_ascii=False).replace("`", "\\u0060")


def _fenced(value):
    return "```json\n%s\n```" % json.dumps(value, indent=2, ensure_ascii=False)


def _piece(value):
    """One value, readable: a string as it is, anything else as a fenced json block."""
    return value if isinstance(value, str) else _fenced(value)


def _readable(value):
    if isinstance(value, dict):
        parts = ["### %s\n\n%s" % (k, _piece(v)) for k, v in value.items()]
        return "\n\n".join(parts)
    if isinstance(value, list):
        parts = ["### Item %d\n\n%s" % (i, _piece(v)) for i, v in enumerate(value, 1)]
        return "\n\n".join(parts)
    return _piece(value)


def _path(base_dir):
    return os.path.join(base_dir, "memory", "others.md")


def _read(base_dir):
    try:
        with open(_path(base_dir), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _blocks(text):
    """Every parseable original-json block in the file, oldest first."""
    out = []
    for m in _BLOCK.finditer(text):
        try:
            out.append(json.loads(m.group(1)))
        except ValueError:
            continue
    return out


def _section(value, today):
    return "\n".join([
        _HEADING % today,
        "",
        _readable(value),
        "",
        _MARKER,
        "```json",
        _dump(value),
        "```",
        "",
    ])


def up(reg, base_dir=None):
    meta = reg.setdefault("meta", {})
    value = meta.get("others")
    if not _is_empty(value):
        if base_dir is None:
            raise ValueError(
                "meta.others holds data and no project folder was given, so there is nowhere to "
                "move it (memory/others.md). Refusing to drop it. Run the update through "
                "/pb:update-version, or pass base_dir.")
        existing = _read(base_dir)
        if not any(b == value for b in _blocks(existing)):
            os.makedirs(os.path.join(base_dir, "memory"), exist_ok=True)
            today = datetime.date.today().isoformat()
            lead = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
            if not existing:
                lead = "# Others\n\nContent moved out of `registry.json` (`meta.others`, retired with its Project Summary sub-tab).\n\n"
            with open(_path(base_dir), "a", encoding="utf-8") as f:
                f.write(lead + _section(value, today))
            # Read it back before the field is emptied: the copy on disk must equal the original.
            if value not in _blocks(_read(base_dir)):
                raise ValueError("memory/others.md did not read back the moved meta.others; "
                                 "registry.json left unchanged.")
        meta["others"] = _empty_like(value)          # emptied, never removed — AGENTS.md §3
    meta["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    meta = reg.setdefault("meta", {})
    if _is_empty(meta.get("others")) and base_dir is not None:
        blocks = _blocks(_read(base_dir))
        if blocks:
            meta["others"] = blocks[-1]
    meta["schemaVersion"] = FROM
    return reg


def describe():
    return ("v1 schema 13 → 14: a non-empty meta.others (retired free-form data) moves out of "
            "registry.json into memory/others.md — readable text plus the exact JSON — and the "
            "field is emptied, not removed; rollback restores it from that file.")

