#!/usr/bin/env python3
"""
slice.py — read/write ONE slice of registry.json by id (token lever #1, at scale).

The build loop's core promise is "read/edit only the touched slice" (CLAUDE.md rule #1).
On a small registry that's free; on a big one (a real project can reach 8–10k lines) the
only way to *locate* a component/screen slice is to load the whole file — which drags the
entire registry into model context on every tweak and defeats the lever.

This tool closes that gap. It loads the whole file internally (unavoidable in Python) but
**emits / accepts only the one slice**, so the model's context stays a slice-sized. That is
where the token cost lives, not in the Python process.

  get   — print one slice as JSON (no whole-file read into context; capped at 8,000 chars, --full lifts it)
  find  — locate a word across the registry (one line per hit) before you `get` anything
  set   — merge a patch into one slice, write the file back, everything else untouched
  list  — enumerate ids so the loop can find a target without loading bodies

Kinds:
  components | screens — a list of entries keyed by `id`; <id> selects one entry. `set` on an id no
                         entry has appends the patch as a new entry when the patch carries that same
                         `"id"`; without it the "no component/screen with id" error stands (a typo
                         creates nothing).
  tokens | meta        — a nested dict; <id> is a **dotted key path BELOW the kind** (e.g.
                         `get meta name`, `get tokens brand`, `get tokens color.bg`).
  ia                   — same dotted-key form (`get ia rules`, `get ia jobs`, `get ia layers`).
  flow | erd           — same dotted-key form (`flow mermaid`, `erd table`). D-29: the
                         auto-sync in /pb:build reads `flow mermaid` (~15 lines) to place a
                         node without dragging every story's scenarios[] into context.
  content              — same dotted-key form (`content terms`, `content strings.<id>`).

The kind is NOT part of the path: `set ia jobs`, not `set ia ia.jobs`. A leading segment equal to the
kind is dropped (so `set ia ia.jobs` means `set ia jobs`, and no stray `ia.ia` key is made), unless the
slice really has a key with that name.

A path segment that lands on a LIST selects the element whose `id` equals it, so one entry of a
list slice is reachable: `get ia rules.<id>` · `set ia jobs.<id>` · `get flow stories.<id>` ·
`get content terms.<id>`. An element without an id can be indexed by a numeric segment (`stories.3`). `set`
on such a path merges the patch into that element and touches no other element. A missing element
is an error — unless the patch carries the same `id`, which appends it. A missing list is not created
by default (`ia.rules`, `ia.jobs`, `ia.layers`, `flow.stories`, `content.terms`, `content.strings`);
`set --create-list` creates it (and its parent object) and then appends — use it for the first term,
story or string on a project whose template predates the seeded lists.

Projection (D-17, `get` only — never `set`/`list`; shapes what's PRINTED, never writes):
  --no-prose        — drop logicNotes/uiLogic/anatomy/spec/usage from the printed slice.
                       At real-project scale these prose fields are the majority of a
                       screen slice's bytes (logicNotes alone: ~70% of one screen) — the
                       build loop reads/edits structure, not prose, so it shouldn't have
                       to pull prose into context just to reach a sibling key.
  --fields a,b,c    — emit ONLY these top-level keys, in the order given (not the slice's
                       internal order — the caller's order is the stable one: the same
                       --fields list produces the same shape from any entry). Every named
                       field must exist on the resolved slice or `get` exits non-zero
                       (a typo'd field name fails loudly rather than silently printing a
                       partial or empty object).
  Both together: --fields selects first, then --no-prose drops any prose key that
  survived the selection.
  Output cap: `get` prints at most 8,000 chars. Past that it prints the first 8,000 and a last line
  `… truncated (<N> chars). Use --fields a,b or --full.` The cut text is deliberately NOT valid JSON, so a
  parser fails loudly; anything that parses `get` output must pass `--full` (no cap).

Read cheaply (so nothing needs an inline script over registry.json):
  find <text>       — case-insensitive search over ids, names/titles and every string value, in every kind
                       (or one: --kind K). One line per hit: `<kind> <id> <field>: <≤80-char snippet>`, where
                       <id> is the owning element's path (`button`, `rules.r1`; for a dict kind it is what
                       `get <kind> <id>` takes) and <field> is the dotted field inside it. Kind order, then
                       document order; --limit N (default 20; 0 = all) with a final
                       `… <N> more hits (raise --limit)` line; no hit prints `0 hits` (exit 0). --json prints a
                       list of {kind,id,path,snippet} (`path` = the string's full dotted path below the kind;
                       the truncation notice goes to stderr). A token also matches on its key path (`$name`).
  list <kind> [path] --fields a,b
                     — id plus those fields, one compact line each: `id  a=…  b=…` (`-` when absent). Needs a
                       list: components, screens, or a list path (`list ia rules --fields title,status`).

Writes use the canonical registry format — `json.dumps(indent=2, ensure_ascii=False)` + a
trailing newline — so an empty-patch `set` is byte-identical (idempotent). Pure stdlib (NS4).

Writes are atomic and serialised. `_write` goes through a temp file in the same directory and
`os.replace`, so a reader (the preview watcher, a render) sees the old file or the new one and
a crash leaves the old one. A writer of registry.json takes the advisory lock around its whole
read-modify-write — `registry_lock(path, who)`: an `fcntl.flock` on `<registry>.lock`, polled for
a short time (5s; `PB_LOCK_TIMEOUT` overrides) and then refused with a message that names the
holder. EVERY writer takes it: `slice.py set`, the preview server's `POST /api/meta`,
`spec_measure.py --write`, the version-update runner (apply and rollback), `logic_extract.py
--contracts`, `lint_registry.py --sync-elements`, `resolve_frame.py`, `clone_ds.py`, `explore.py
promote` (the IA slice) and `test_run.py --functional` (the `lastResult` verdicts). Each loads the
registry INSIDE the lock, so what it writes back is what the registry held when it got the lock — and
none holds it across slow work: `test_run.py` runs the whole browser session first and takes the
lock only for the write, merging just the `lastResult` of the scenarios that ran into a fresh read.
A new writer joins this list or it is a lost update waiting for a concurrent edit.

The kernel drops the lock when its process exits, so a crashed writer never leaves a stale one; the
file itself is just an anchor (empty whenever nobody holds it) and is kept. The anchor is opened with
O_NOFOLLOW and must be a regular file: a symlink or any other kind of file at `<registry>.lock` is
refused (`LockFileUnsafe`), never followed and never truncated, because the holder's note is written
into it.

Line by line (v2.6, `pb/docs/canon.md` § *Line by line*). While a command is authoring, each job, term, sitemap node,
rule, story, scenario, wording and ERD row is saved by its own call as soon as it is written, so the open preview
fills in place as the work goes (about 2.5 s a line, a tool call each):
  set ... --draft    — the same path syntax, but the patch goes to `.preview/drafts.json` (under the registry's lock),
                       never to registry.json. A draft is a line nobody has approved yet: the preview folds it into what
                       it shows with a Draft chip, and `render.py` and every file on disk never see it. A real `set`
                       writes the approved line; `drafts --clear` empties the file once they are all written.
  append             — add ONE element to a list that has no ids to select by (`content strings` with a `key`,
                       `erd table` rows, a story's `scenarios`): the list is created if it is missing, `--key a,b` makes
                       a repeat of the same line a merge instead of a duplicate. `--draft` works here too.
  drafts             — `--clear` empties the drafts, `--list` prints what they hold.

Usage:
  python3 slice.py get  <kind> <id> [--registry PATH] [--no-prose] [--fields a,b,c] [--full]
  python3 slice.py find <text> [--registry PATH] [--kind K] [--limit 20] [--json]   # --registry is an option, after the subcommand
  python3 slice.py set  <kind> <id> [--registry PATH] [--patch FILE] [--create-list] [--draft]   # patch from FILE or stdin
  python3 slice.py append <kind> <path> [--registry PATH] [--patch FILE] [--key a,b] [--draft]  # one element, from FILE or stdin
  python3 slice.py drafts [--registry PATH] [--clear | --list]
  python3 slice.py list <kind> [path] [--registry PATH] [--fields a,b]   # no path: top-level keys; a list path: its ids

Exit: 0 on success; non-zero with a message on error (unknown kind, missing id/key,
unknown --fields name, bad JSON).
"""
import argparse
import contextlib
import copy
import errno
import json
import os
import re
import stat
import sys
import tempfile
import time

try:
    import fcntl
except ImportError:          # Windows: no advisory lock; the atomic replace still holds
    fcntl = None

LIST_KINDS = ("components", "screens")   # id-keyed lists
# D-29: flow/erd joined the dict kinds so /pb:build's auto-sync can read `flow mermaid`
# (~15 lines) without pulling every story's scenarios[] into context.
DICT_KINDS = ("tokens", "meta", "flow", "erd", "content", "ia", "research")   # dotted-key dicts
# Lists a `set` must never create by accident (a missing one is an error, not a new `{}`).
LIST_PATHS = {"ia": ("jobs", "rules", "layers", "sitemap"), "flow": ("stories",), "content": ("terms", "strings"),
              "research": ("studies",)}
KINDS = LIST_KINDS + DICT_KINDS

# D-17: the prose keys --no-prose drops. Schema-11 may move these out of registry.json
# entirely (a later wave's call) — until then this is the read-side workaround.
PROSE_KEYS = ("logicNotes", "uiLogic", "anatomy", "spec", "usage")


def _load(reg_path):
    if not os.path.isfile(reg_path):
        sys.exit(f"slice: no registry at {reg_path}")
    with open(reg_path, encoding="utf-8") as f:
        return json.load(f)


def atomic_write_bytes(path, data):
    """Replace `path` with `data` all at once: a temp file in the same directory (same filesystem,
    so the rename cannot copy), flushed to disk, then `os.replace`. A reader sees the old file or
    the new one, never half of it, and a failure leaves the old one in place. The mode of an
    existing file is kept, and a symlinked registry is replaced at its target, not unlinked."""
    path = os.path.realpath(path)
    d, base = os.path.split(path)
    fd, tmp = tempfile.mkstemp(prefix="." + base + ".", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        except FileNotFoundError:
            os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def atomic_write_text(path, text):
    """atomic_write_bytes of `text` as UTF-8, with no newline translation."""
    atomic_write_bytes(path, text.encode("utf-8"))


def _write(reg_path, reg):
    # Canonical registry format (matches how pb writes registry.json): 2-space indent,
    # unicode preserved, one trailing newline. Keeps `set` byte-stable / idempotent.
    # Atomic (see atomic_write_text); the caller holds registry_lock around its read-modify-write.
    atomic_write_text(reg_path, json.dumps(reg, indent=2, ensure_ascii=False) + "\n")


# ── drafts (v2.6) — unapproved lines the preview shows and the registry never holds ─────────────────
DRAFTS_FILE = os.path.join(".preview", "drafts.json")


def drafts_path(reg_path):
    """.preview/drafts.json beside the registry — runtime state like server.json, gitignored with the folder."""
    return os.path.join(os.path.dirname(os.path.realpath(reg_path)), DRAFTS_FILE)


def load_drafts(path):
    """The drafts document — {<kind>: {…}} in the registry's own shape, holding only the draft lines — or {}
    when there is none, it is unreadable, or it is not an object. A bad drafts file is no drafts, never an error."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write_drafts(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_text(path, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def _overlay(dst, src):
    """Fold the drafts `src` into `dst` (both mutated-in-place: dst is a private copy). Dicts merge, a list of
    objects merges by `id` (an id that exists is merged into, else the element is appended) and any element without
    an id is appended; every list element a draft touches carries `_draft: true`. A scalar replaces."""
    for k, v in src.items():
        if isinstance(v, dict):
            if isinstance(dst.get(k), dict):
                _overlay(dst[k], v)
            else:
                dst[k] = copy.deepcopy(v)
        elif isinstance(v, list):
            cur = dst.get(k)
            if not isinstance(cur, list):
                cur = dst[k] = []
            for el in v:
                if not isinstance(el, dict):
                    cur.append(copy.deepcopy(el))
                    continue
                i = next((n for n, x in enumerate(cur)
                          if isinstance(x, dict) and "id" in el and x.get("id") == el["id"]), None)
                if i is None:
                    cur.append(dict(copy.deepcopy(el), _draft=True))
                else:
                    _overlay(cur[i], el)
                    cur[i]["_draft"] = True
        else:
            dst[k] = v
    return dst


def overlay_drafts(reg, drafts):
    """A copy of the registry with the drafts folded in (see `_overlay`), each draft list element marked
    `_draft: true`. Pure: nothing is written, `reg` is not changed. No drafts → an equal copy."""
    out = copy.deepcopy(reg)
    return _overlay(out, drafts) if isinstance(drafts, dict) and drafts else out


def draft_summary(drafts):
    """How many draft lines there are (list elements anywhere in the drafts document), for the preview's badge."""
    def count(node):
        if isinstance(node, list):
            return sum(1 + count(el) if isinstance(el, dict) else 1 for el in node)
        if isinstance(node, dict):
            return sum(count(v) for v in node.values())
        return 0
    return {"count": count(drafts) if isinstance(drafts, dict) else 0}


DEFAULT_LOCK_TIMEOUT = 5.0


class RegistryLocked(Exception):
    """Another pb process holds the registry's write lock past the timeout. str() is the
    message to show — it names the holder and what to do."""


class LockFileUnsafe(RegistryLocked):
    """`<registry>.lock` is not a regular file (a symlink, a directory, a FIFO, a device): the lock
    cannot be taken safely, and nothing was written to or truncated at that path. A RegistryLocked,
    so every caller that already stops on a refused lock stops on this one with its message."""


def lock_timeout():
    try:
        return max(0.0, float(os.environ.get("PB_LOCK_TIMEOUT", DEFAULT_LOCK_TIMEOUT)))
    except ValueError:
        return DEFAULT_LOCK_TIMEOUT


def _open_lock(lock_path):
    """Open the lock anchor and hand back its descriptor — only if it is a regular file.

    The holder's note is written into this file and the file is truncated when the holder lets go,
    so a symlink planted at `<registry>.lock` would make the next writer truncate whatever it points
    at. O_NOFOLLOW makes the open itself refuse a symlink; O_NONBLOCK keeps an open of a FIFO from
    waiting for a peer; and fstat on the descriptor (not a stat of the path, which could change
    between the check and the open) turns away anything that is not a regular file before a byte is
    written. Raises LockFileUnsafe; any other OSError (permissions, a missing directory) is the
    caller's, as before."""
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    name = os.path.basename(lock_path)
    try:
        fd = os.open(lock_path, flags, 0o644)
    except OSError as e:
        if e.errno in (errno.ELOOP, errno.EISDIR, errno.ENXIO, errno.EMLINK):
            raise LockFileUnsafe(
                "%s is not a regular file (a symlink or another kind of file is in its place) — "
                "refusing to lock or write through it. Remove it and run the command again." % name) from None
        raise
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise LockFileUnsafe(
                "%s is not a regular file — refusing to lock or write through it. Remove it and "
                "run the command again." % name)
    except BaseException:
        os.close(fd)
        raise
    return fd


@contextlib.contextmanager
def registry_lock(reg_path, who="pb", timeout=None):
    """Hold the registry's advisory write lock for the `with` body.

    `fcntl.flock` on `<registry>.lock`, tried without blocking until `timeout` seconds
    (default `lock_timeout()`), then RegistryLocked. The holder writes `who` and its pid into the
    file so a refusal can say who is in the way. Not re-entrant: one open file description per
    call, so a nested call on the same path waits for the outer one. Take it around the whole
    read-modify-write — never around only the write."""
    timeout = lock_timeout() if timeout is None else timeout
    target = os.path.realpath(reg_path)
    lock_path = target + ".lock"
    if fcntl is None:
        yield
        return
    fd = _open_lock(lock_path)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    try:
                        holder = os.pread(fd, 200, 0).decode("utf-8", "replace").strip()
                    except OSError:
                        holder = ""
                    raise RegistryLocked(
                        "%s is being written by another pb process%s — waited %gs. Try again in a "
                        "moment; the lock clears by itself when that command ends."
                        % (os.path.basename(target), " (%s)" % holder if holder else "", timeout)) from None
                time.sleep(0.05)
        os.ftruncate(fd, 0)
        os.pwrite(fd, ("%s pid=%d\n" % (who, os.getpid())).encode("utf-8"), 0)
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                os.ftruncate(fd, 0)    # empty whenever nobody holds it: a re-run leaves the directory byte-identical
    finally:
        os.close(fd)                   # …and closing the descriptor is what releases the flock


def _find_entry(reg, kind, ident):
    """Return the id-keyed entry for LIST_KINDS, or exit if absent."""
    for item in reg.get(kind, []):
        if item.get("id") == ident:
            return item
    sys.exit(f"slice: no {kind[:-1]} with id {ident!r}")


def _list_index(node, seg):
    """Index of the element of list `node` that segment `seg` names — the element whose `id` is
    `seg`, else (numeric `seg`, and the element at that position carries no id of its own) the position
    — or None. So a list with some ids and some without (stories written before they had ids) is
    reachable by position for the id-less ones, while an element that has an id is reached by it only."""
    for i, el in enumerate(node):
        if isinstance(el, dict) and el.get("id") == seg:
            return i
    if seg.isdigit() and int(seg) < len(node) and not (isinstance(node[int(seg)], dict) and "id" in node[int(seg)]):
        return int(seg)
    return None


def _strip_kind(reg, kind, ident):
    """Drop a redundant leading `<kind>.` from a dotted path: `set ia ia.jobs` means `set ia jobs`.
    Kept when the slice really has a key with the kind's name, and never strips the whole path."""
    if kind not in DICT_KINDS or not ident:
        return ident
    head, dot, rest = ident.partition(".")
    if head != kind or not dot or not rest:
        return ident
    node = reg.get(kind)
    if isinstance(node, dict) and kind in node:
        return ident
    return rest


def _dotted_get(reg, kind, key):
    """Resolve a dotted key path under a DICT_KIND. A segment on a list selects the element by
    id (or position). Exit if any segment is missing."""
    node = reg.get(kind, {})
    trail = kind
    for seg in key.split("."):
        if isinstance(node, list):
            i = _list_index(node, seg)
            if i is None:
                sys.exit(f"slice: no element {seg!r} in {trail} (by id)")
            node = node[i]
        elif not isinstance(node, dict) or seg not in node:
            sys.exit(f"slice: no key {trail}.{seg!r}")
        else:
            node = node[seg]
        trail += "." + seg
    return node


def _deep_merge(dst, patch):
    """Recursively merge patch into dst: dicts merge, everything else (incl. lists) replaces.
    Cannot delete keys — a targeted patch adds/overwrites, matching the build loop's intent."""
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def _parse_fields(raw):
    """Split a `--fields a,b,c` value into a name list. None in, None out (flag unset)."""
    if raw is None:
        return None
    fields = [f.strip() for f in raw.split(",") if f.strip()]
    if not fields:
        sys.exit("slice: --fields needs at least one field name")
    return fields


def _project(entry, fields, no_prose):
    """Shape a slice for PRINTING only — never mutates `entry`, never writes.

    --fields selects (in the caller's order; a missing name is a hard error, not a
    silent drop) and --no-prose then removes any PROSE_KEYS key that survived."""
    if fields is None and not no_prose:
        return entry
    if not isinstance(entry, dict):
        if fields is not None:
            sys.exit(f"slice: --fields needs a dict-shaped slice, got {type(entry).__name__}")
        return entry  # --no-prose on a non-dict (e.g. a scalar token leaf) is a no-op

    result = entry
    if fields is not None:
        missing = [f for f in fields if f not in entry]
        if missing:
            sys.exit(f"slice: --fields unknown key(s): {', '.join(missing)}")
        result = {f: entry[f] for f in fields}
    if no_prose:
        result = {k: v for k, v in result.items() if k not in PROSE_KEYS}
    return result


def _read_patch(patch_file):
    raw = open(patch_file, encoding="utf-8").read() if patch_file else sys.stdin.read()
    if not raw.strip():
        return None  # empty patch → no-op (byte-stable rewrite)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"slice: patch is not valid JSON: {e}")


GET_CAP = 8000   # chars `get` prints before it cuts; --full lifts it


def cmd_get(args):
    reg = _load(args.registry)
    if args.kind in LIST_KINDS:
        entry = _find_entry(reg, args.kind, args.id)
    else:
        entry = _dotted_get(reg, args.kind, _strip_kind(reg, args.kind, args.id))
    entry = _project(entry, _parse_fields(args.fields), args.no_prose)
    text = json.dumps(entry, indent=2, ensure_ascii=False)
    if not args.full and len(text) > GET_CAP:
        # Bash output is the biggest context cost: a whole screen slice can be 100k+ chars. The cut text is
        # NOT valid JSON on purpose (a parser fails loudly instead of reading a partial object); a caller
        # that parses the output passes --full.
        print(text[:GET_CAP])
        print(f"… truncated ({len(text)} chars). Use --fields a,b or --full.")
        return
    print(text)


def _collapse(s):
    return " ".join(str(s).split())


def _snippet(s, m, width=80):
    """≤`width` chars of the (whitespace-collapsed) string `s` around the regex match `m`, an ellipsis on each cut side."""
    if len(s) <= width:
        return s
    avail = width - 2
    left = max(0, m.start() - max(0, avail - (m.end() - m.start())) // 2)
    end = min(len(s), left + avail)
    left = max(0, end - avail)
    return ("…" if left > 0 else "") + s[left:end] + ("…" if end < len(s) else "")


def _walk_strings(node, segs, owner, nest=True):
    """Yield (segs, owner_depth, string) for every string under `node`, in document order. `owner_depth` is how
    many leading segments name the nearest enclosing list element that has an `id` (0 = none). With `nest`
    False only the top-level list's elements own a hit (a component's inner parts stay fields of the component)."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(v, segs + [str(k)], owner, nest)
    elif isinstance(node, list):
        for i, el in enumerate(node):
            if isinstance(el, dict) and isinstance(el.get("id"), (str, int)) and not isinstance(el.get("id"), bool):
                yield from _walk_strings(el, segs + [str(el["id"])], len(segs) + 1 if (nest or not segs) else owner, nest)
            else:
                yield from _walk_strings(el, segs + [str(i)], owner, nest)
    elif isinstance(node, str):
        yield segs, owner, node


def _find_hits(reg, text, kinds):
    """Every hit for `text` (case-insensitive substring) as dicts {kind,id,path,field,snippet}: kind order, then
    document order. `id` is the dotted path (below the kind) of the owning id'd element — the entry id for a
    component/screen, `rules.r1` for a rule — or, with none, the leaf's parent; `path` is the leaf's full dotted
    path below the kind (what `get <kind> <path>` takes for a dict kind); `field` is `path` relative to `id`."""
    rx = re.compile(re.escape(text), re.IGNORECASE)
    hits = []
    for kind in kinds:
        root = reg.get(kind)
        if root is None:
            continue
        for segs, owner, s in _walk_strings(root, [], 0, kind not in LIST_KINDS):
            flat = _collapse(s)
            m = rx.search(flat)
            if not m:
                continue
            if owner:
                oid, field = segs[:owner], segs[owner:]
            else:
                oid, field = (segs[:-1] or segs), segs[-1:]
            hits.append({"kind": kind, "id": ".".join(oid), "path": ".".join(segs),
                         "field": ".".join(field), "snippet": _snippet(flat, m)})
        if kind == "tokens":
            # a token is named by its key path, not by a string value: `find brand` should reach `brand`.
            def walk(node, trail):
                if isinstance(node, dict) and "$value" in node:
                    name = ".".join(trail)
                    m = rx.search(name)
                    if m:
                        hits.append({"kind": kind, "id": name, "path": name, "field": "$name", "snippet": _snippet(name, m)})
                elif isinstance(node, dict):
                    for k, v in node.items():
                        walk(v, trail + [str(k)])
            walk(root, [])
    return hits


def cmd_find(args):
    if not args.text:
        sys.exit("slice: find needs the text to look for")
    if args.limit < 0:
        sys.exit("slice: --limit must be 0 (no limit) or more")
    reg = _load(args.registry)
    hits = _find_hits(reg, args.text, [args.kind] if args.kind else list(KINDS))
    shown = hits if args.limit == 0 else hits[:args.limit]
    more = len(hits) - len(shown)
    if args.json:
        print(json.dumps([{k: h[k] for k in ("kind", "id", "path", "snippet")} for h in shown],
                         indent=2, ensure_ascii=False))
        if more:
            print(f"… {more} more hits (raise --limit)", file=sys.stderr)
        return
    if not hits:
        print("0 hits")
        return
    for h in shown:
        print(f"{h['kind']} {h['id']} {h['field']}: {h['snippet']}")
    if more:
        print(f"… {more} more hits (raise --limit)")


def _apply_set(args, patch, draft=False):
    """The read-modify-write of `set`, run with the registry lock held. Returns the one-line
    result. Exits (non-zero) on a bad patch before anything is written. `draft` runs the very same
    code over `.preview/drafts.json` instead of registry.json: the draft document is registry-shaped
    but holds only the lines nobody has approved, so a list it lacks is always created."""
    if draft:
        if args.kind in LIST_KINDS:
            sys.exit(f"slice: --draft covers {', '.join(DICT_KINDS)} — a {args.kind[:-1]} is built, not drafted")
        out_path = drafts_path(args.registry)
        reg = load_drafts(out_path)
        args.create_list = True
    else:
        out_path = args.registry
        reg = _load(args.registry)
    _write_out = (lambda path, doc: _write_drafts(path, doc)) if draft else _write

    if args.kind in LIST_KINDS:
        if (isinstance(patch, dict) and patch.get("id") == args.id
                and not any(isinstance(it, dict) and it.get("id") == args.id for it in reg.get(args.kind) or [])):
            # no such entry, and the patch carries the same id: append it (the dotted lists' rule).
            # A patch without a matching id falls through to _find_entry's error — a typo makes nothing.
            if not isinstance(reg.get(args.kind), list):
                reg[args.kind] = []
            reg[args.kind].append(patch)
            _write_out(out_path, reg)
            return f"✓ appended {args.kind[:-1]} {args.id}  ({', '.join(patch.keys())})"
        entry = _find_entry(reg, args.kind, args.id)
        if isinstance(patch, dict):
            before = json.dumps(entry, sort_keys=True)
            _deep_merge(entry, patch)
            changed = json.dumps(entry, sort_keys=True) != before
            keys = ", ".join(patch.keys()) if patch else "—"
        elif patch is None:
            changed, keys = False, "—"
        else:
            sys.exit("slice: a component/screen patch must be a JSON object")
    else:
        # DICT_KIND dotted set: merge dicts, otherwise replace the leaf. A segment on a list
        # selects an element by id; the last one merges into it (or appends, see the docstring).
        create = getattr(args, "create_list", False)
        parts = _strip_kind(reg, args.kind, args.id).split(".")
        parent = reg.setdefault(args.kind, {})
        trail = args.kind
        for seg in parts[:-1]:
            if isinstance(parent, list):
                i = _list_index(parent, seg)
                if i is None:
                    sys.exit(f"slice: no element {seg!r} in {trail} (by id)")
                parent = parent[i]
            else:
                if seg not in parent and seg in LIST_PATHS.get(trail, ()):
                    if not create:
                        sys.exit(f"slice: no list {trail}.{seg} to set into (--create-list creates it)")
                    parent[seg] = []
                parent = parent.setdefault(seg, {})
            trail += "." + seg
            if not isinstance(parent, (dict, list)):
                sys.exit(f"slice: {trail} is not an object")
        leaf = parts[-1]
        if isinstance(parent, list):
            i = _list_index(parent, leaf)
            if patch is not None and not isinstance(patch, dict):
                sys.exit("slice: a list-element patch must be a JSON object")
            if i is None:
                if isinstance(patch, dict) and patch.get("id") == leaf:
                    parent.append(patch)
                    changed, keys = True, leaf
                elif patch is None:
                    sys.exit(f"slice: no element {leaf!r} in {trail} (by id)")
                else:
                    sys.exit(f"slice: no element {leaf!r} in {trail}; to append one, the patch must carry \"id\": {leaf!r}")
            else:
                el = parent[i]
                if patch is None:
                    changed, keys = False, "—"
                elif not isinstance(el, dict):
                    sys.exit(f"slice: {trail}.{leaf} is not an object")
                else:
                    before = json.dumps(el, sort_keys=True)
                    _deep_merge(el, patch)
                    changed = json.dumps(el, sort_keys=True) != before
                    keys = ", ".join(patch.keys()) if patch else "—"
        else:
            if leaf in LIST_PATHS.get(trail, ()) and leaf not in parent:
                if not create:
                    sys.exit(f"slice: no list {trail}.{leaf} to create (--create-list creates it)")
                parent[leaf] = []
                if isinstance(patch, dict):          # an element patch: the new list starts with it
                    patch = [patch]
            before = json.dumps(parent.get(leaf), sort_keys=True)
            if patch is None:
                changed, keys = False, "—"
            elif isinstance(patch, dict) and isinstance(parent.get(leaf), dict):
                _deep_merge(parent[leaf], patch)
                changed = json.dumps(parent[leaf], sort_keys=True) != before
                keys = leaf
            else:
                parent[leaf] = patch
                changed = json.dumps(parent.get(leaf), sort_keys=True) != before
                keys = leaf

    _write_out(out_path, reg)
    target = args.id if args.kind in DICT_KINDS else f"{args.kind[:-1]} {args.id}"
    verb = "drafted" if draft else "patched"
    return f"{'✓ ' + verb if changed else '· no change'} {target}" + (f"  ({keys})" if changed else "")


def _apply_append(args, patch, draft=False):
    """The read-modify-write of `append`, run with the registry lock held: add ONE element to the list at
    `path`, creating the list (and any plain object above it) when it is missing. Walks the same dotted paths
    as `set`; a segment on a list selects an element by id. With `--key a,b` an element that already has the
    same values for those fields is merged into instead of duplicated, so repeating a line is harmless."""
    if args.kind in LIST_KINDS:
        sys.exit(f"slice: append adds to a list inside {', '.join(DICT_KINDS)}; use `set {args.kind} <id>` for a {args.kind[:-1]}")
    if not isinstance(patch, dict):
        sys.exit("slice: append takes one JSON object — the element to add")
    if draft:
        out_path = drafts_path(args.registry)
        reg = load_drafts(out_path)
    else:
        out_path = args.registry
        reg = _load(args.registry)
    parts = [p for p in _strip_kind(reg, args.kind, args.path).split(".") if p]
    if not parts:
        sys.exit("slice: append needs the path of a list, e.g. `append content strings`")
    node, trail = reg.setdefault(args.kind, {}), args.kind
    for seg in parts[:-1]:
        if isinstance(node, list):
            i = _list_index(node, seg)
            if i is None:
                hint = (" — a draft path is reached through the elements the drafts already hold; draft the "
                        "parent first") if draft else ""
                sys.exit(f"slice: no element {seg!r} in {trail} (by id){hint}")
            node = node[i]
        elif isinstance(node, dict):
            if seg not in node and seg in LIST_PATHS.get(trail, ()):
                # a list this document does not hold: the next segment names an element of it, and there is none
                hint = (" — a draft path is reached through the elements the drafts already hold; draft the "
                        "parent first") if draft else ""
                sys.exit(f"slice: no list {trail}.{seg} to select an element of{hint}")
            node = node.setdefault(seg, {})
        else:
            sys.exit(f"slice: {trail} is not an object")
        trail += "." + seg
        if not isinstance(node, (dict, list)):
            sys.exit(f"slice: {trail} is not an object")
    leaf = parts[-1]
    if not isinstance(node, dict):
        sys.exit(f"slice: {trail} is a list; name the list inside the element, e.g. `{trail}.<id>.{leaf}`")
    lst = node.setdefault(leaf, [])
    if not isinstance(lst, list):
        sys.exit(f"slice: {trail}.{leaf} is not a list")
    keys = [k.strip() for k in (getattr(args, "key", None) or "").split(",") if k.strip()]
    dup = next((el for el in lst if keys and isinstance(el, dict)
                and all(k in el and k in patch and el[k] == patch[k] for k in keys)), None)
    if dup is not None:
        before = json.dumps(dup, sort_keys=True)
        _deep_merge(dup, patch)
        changed = json.dumps(dup, sort_keys=True) != before
        line = f"{'✓ merged into' if changed else '· no change in'} {trail}.{leaf}[{lst.index(dup)}]"
    else:
        lst.append(patch)
        changed = True
        line = f"✓ {'drafted' if draft else 'appended'} {trail}.{leaf}[{len(lst) - 1}]"
    if changed:
        (_write_drafts if draft else _write)(out_path, reg)
    return line


def cmd_set(args):
    if not os.path.isfile(args.registry):            # before the lock: no .lock file for a typo'd path
        sys.exit(f"slice: no registry at {args.registry}")
    patch = _read_patch(args.patch)
    try:
        with registry_lock(args.registry, "slice set"):
            line = _apply_set(args, patch, draft=getattr(args, "draft", False))
    except RegistryLocked as e:
        sys.exit(f"slice: {e}")
    print(line)


def cmd_append(args):
    if not os.path.isfile(args.registry):
        sys.exit(f"slice: no registry at {args.registry}")
    patch = _read_patch(args.patch)
    try:
        with registry_lock(args.registry, "slice append"):
            line = _apply_append(args, patch, draft=args.draft)
    except RegistryLocked as e:
        sys.exit(f"slice: {e}")
    print(line)


def cmd_drafts(args):
    """`drafts --clear` empties .preview/drafts.json (under the registry's lock), `--list` prints what it holds."""
    if not os.path.isfile(args.registry):
        sys.exit(f"slice: no registry at {args.registry}")
    path = drafts_path(args.registry)
    if args.clear:
        try:
            with registry_lock(args.registry, "slice drafts"):
                n = draft_summary(load_drafts(path))["count"]
                if os.path.exists(path):
                    _write_drafts(path, {})
        except RegistryLocked as e:
            sys.exit(f"slice: {e}")
        print(f"✓ cleared {n} draft line{'' if n == 1 else 's'}" if n else "· no drafts")
        return
    doc = load_drafts(path)
    print(json.dumps(doc, indent=2, ensure_ascii=False) if doc else "· no drafts")


def _compact(v, width=60):
    """One value on one line for `list --fields`: compact JSON (a bare string stays bare), cut at `width`."""
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    s = _collapse(s)
    return s if len(s) <= width else s[:width - 1] + "…"


def _list_fields_line(el, fields):
    bits = [str(el.get("id", "?")) if isinstance(el, dict) else "?"]
    for f in fields:
        bits.append(f"{f}={_compact(el[f]) if isinstance(el, dict) and f in el else '-'}")
    return "  ".join(bits)


def cmd_list(args):
    reg = _load(args.registry)
    fields = _parse_fields(args.fields)
    if fields is not None:
        # id plus the named fields, one compact line per element. Only for a list: components, screens,
        # or a list path (`list ia rules --fields title,status`); a missing field prints `-`.
        if args.kind in LIST_KINDS:
            node = reg.get(args.kind, [])
        elif args.path and args.kind != "tokens":
            node = _dotted_get(reg, args.kind, _strip_kind(reg, args.kind, args.path))
        else:
            node = None
        if not isinstance(node, list):
            sys.exit("slice: list --fields needs a list: components, screens, or a list path such as `list ia rules`")
        for el in node:
            print(_list_fields_line(el, fields))
        return
    if args.kind in LIST_KINDS:
        for item in reg.get(args.kind, []):
            bits = [item.get("id", "?")]
            if item.get("name"):
                bits.append(item["name"])
            if item.get("level"):
                bits.append(f"[{item['level']}]")
            print("  ".join(bits))
    elif args.kind == "tokens":  # print dotted paths of leaves (DTCG leaves carry $value)
        def walk(node, trail):
            if isinstance(node, dict) and "$value" in node:
                print(trail)
                return
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, f"{trail}.{k}" if trail else k)
        walk(_dotted_get(reg, "tokens", args.path) if args.path else reg.get("tokens", {}), args.path or "")
    else:  # meta | flow | erd | content | ia | research — a plain dict: its top-level keys
        node = (_dotted_get(reg, args.kind, _strip_kind(reg, args.kind, args.path)) if args.path
                else reg.get(args.kind, {}))
        if isinstance(node, list):
            for el in node:
                if isinstance(el, dict) and "id" in el:
                    bits = [str(el["id"])]
                    label = el.get("title") or el.get("name")
                    if label:
                        bits.append(str(label))
                    print("  ".join(bits))
                else:
                    print(json.dumps(el, ensure_ascii=False)[:80])
        elif isinstance(node, dict):
            for k in node:
                print(k)
        else:
            sys.exit(f"slice: {args.kind}.{args.path} is not a list or an object")


def main():
    p = argparse.ArgumentParser(prog="slice.py", description="Read/write one registry.json slice by id.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp, with_id=True):
        sp.add_argument("kind", choices=KINDS)
        if with_id:
            sp.add_argument("id", help="entry id (components/screens) or dotted key (tokens/meta/flow/erd/content/ia); a list segment is an element id")
        sp.add_argument("--registry", default="registry.json", help="path to registry.json")

    g = sub.add_parser("get", help="print one slice as JSON")
    add_common(g)
    g.add_argument("--no-prose", action="store_true",
                    help="drop logicNotes/uiLogic/anatomy/spec/usage from the printed slice")
    g.add_argument("--fields",
                    help="comma-separated top-level keys to emit, in that order "
                         "(combine with --no-prose to also drop any prose key that survives)")
    g.add_argument("--full", action="store_true",
                   help=f"print the whole slice; without it output is cut at {GET_CAP} chars with a final "
                        "`… truncated` line (the cut text is not valid JSON — pass --full when parsing it)")
    g.set_defaults(func=cmd_get)

    f = sub.add_parser("find", help="search ids, names and every string value (all kinds, or one with --kind)")
    f.add_argument("text", help="case-insensitive text to look for")
    f.add_argument("--kind", choices=KINDS, help="search only this kind (default: all, in kind order)")
    f.add_argument("--limit", type=int, default=20, help="most hits to print (default 20; 0 = all)")
    f.add_argument("--json", action="store_true", help="print a JSON list of {kind,id,path,snippet}")
    f.add_argument("--registry", default="registry.json", help="path to registry.json")
    f.set_defaults(func=cmd_find)

    s = sub.add_parser("set", help="merge a patch into one slice (patch from --patch FILE or stdin)")
    add_common(s)
    s.add_argument("--patch", help="JSON patch file (default: read stdin)")
    s.add_argument("--create-list", action="store_true",
                   help="create a missing ia.jobs/rules/layers/sitemap, flow.stories or content.terms/strings list "
                        "(and its parent object) and append to it; without it a missing list is refused")
    s.add_argument("--draft", action="store_true",
                   help="write the patch to .preview/drafts.json instead of registry.json: a line nobody has approved "
                        "yet. The open preview shows it with a Draft chip; no render or file on disk ever sees it")
    s.set_defaults(func=cmd_set)

    a = sub.add_parser("append", help="add ONE element to a list that has no ids (content strings, erd table, a story's scenarios)")
    a.add_argument("kind", choices=DICT_KINDS)
    a.add_argument("path", help="dotted path of the list, e.g. `strings`, `table`, `stories.<id>.scenarios` (the kind is not part of it)")
    a.add_argument("--registry", default="registry.json", help="path to registry.json")
    a.add_argument("--patch", help="JSON file holding the one element (default: read stdin)")
    a.add_argument("--key", help="comma-separated fields that identify the element: one that already matches on all of "
                                 "them is merged into, not duplicated (e.g. `--key key` for a wording)")
    a.add_argument("--draft", action="store_true", help="append to .preview/drafts.json instead (see `set --draft`)")
    a.set_defaults(func=cmd_append)

    d = sub.add_parser("drafts", help="empty or print .preview/drafts.json — the unapproved lines")
    d.add_argument("--registry", default="registry.json", help="path to registry.json")
    dm = d.add_mutually_exclusive_group()
    dm.add_argument("--clear", action="store_true", help="empty the drafts (once every line is approved and written for real)")
    dm.add_argument("--list", action="store_true", help="print what the drafts hold (the default)")
    d.set_defaults(func=cmd_drafts)

    l = sub.add_parser("list", help="enumerate ids/keys for a kind")
    add_common(l, with_id=False)
    l.add_argument("path", nargs="?", help="optional dotted path: a list shows its ids, an object its keys")
    l.add_argument("--fields", help="comma-separated fields: one compact line per element, `id  a=…  b=…` "
                                    "(components, screens, or a list path; a missing field prints `-`)")
    l.set_defaults(func=cmd_list)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
