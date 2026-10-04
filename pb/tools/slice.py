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

  get   — print one slice as JSON (no whole-file read into context)
  set   — merge a patch into one slice, write the file back, everything else untouched
  list  — enumerate ids so the loop can find a target without loading bodies

Kinds:
  components | screens — a list of entries keyed by `id`; <id> selects one entry.
  tokens | meta        — a nested dict; <id> is a **dotted key path** (e.g. `meta.name`,
                         `tokens.brand`, `tokens.color.bg`).
  flow | erd           — same dotted-key form (`flow.mermaid`, `erd.table`). D-29: the
                         auto-sync in /pb:build reads `flow mermaid` (~15 lines) to place a
                         node without dragging every story's scenarios[] into context.

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

Usage:
  python3 slice.py get  <kind> <id> [--registry PATH] [--no-prose] [--fields a,b,c]
  python3 slice.py set  <kind> <id> [--registry PATH] [--patch FILE]   # patch from FILE or stdin
  python3 slice.py list <kind>      [--registry PATH]

Exit: 0 on success; non-zero with a message on error (unknown kind, missing id/key,
unknown --fields name, bad JSON).
"""
import argparse
import contextlib
import errno
import json
import os
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
DICT_KINDS = ("tokens", "meta", "flow", "erd", "content")   # dotted-key dicts
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


def _dotted_get(reg, kind, key):
    """Resolve a dotted key path under a DICT_KIND. Exit if any segment is missing."""
    node = reg.get(kind, {})
    trail = kind
    for seg in key.split("."):
        if not isinstance(node, dict) or seg not in node:
            sys.exit(f"slice: no key {trail}.{seg!r}")
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


def cmd_get(args):
    reg = _load(args.registry)
    if args.kind in LIST_KINDS:
        entry = _find_entry(reg, args.kind, args.id)
    else:
        entry = _dotted_get(reg, args.kind, args.id)
    entry = _project(entry, _parse_fields(args.fields), args.no_prose)
    print(json.dumps(entry, indent=2, ensure_ascii=False))


def _apply_set(args, patch):
    """The read-modify-write of `set`, run with the registry lock held. Returns the one-line
    result. Exits (non-zero) on a bad patch before anything is written."""
    reg = _load(args.registry)

    if args.kind in LIST_KINDS:
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
        # DICT_KIND dotted set: merge dicts, otherwise replace the leaf.
        parts = args.id.split(".")
        parent = reg.setdefault(args.kind, {})
        for seg in parts[:-1]:
            parent = parent.setdefault(seg, {})
            if not isinstance(parent, dict):
                sys.exit(f"slice: {args.kind}.{seg} is not an object")
        leaf = parts[-1]
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

    _write(args.registry, reg)
    target = args.id if args.kind in DICT_KINDS else f"{args.kind[:-1]} {args.id}"
    return f"{'✓ patched' if changed else '· no change'} {target}" + (f"  ({keys})" if changed else "")


def cmd_set(args):
    if not os.path.isfile(args.registry):            # before the lock: no .lock file for a typo'd path
        sys.exit(f"slice: no registry at {args.registry}")
    patch = _read_patch(args.patch)
    try:
        with registry_lock(args.registry, "slice set"):
            line = _apply_set(args, patch)
    except RegistryLocked as e:
        sys.exit(f"slice: {e}")
    print(line)


def cmd_list(args):
    reg = _load(args.registry)
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
        walk(reg.get("tokens", {}), "")
    else:  # meta | flow | erd — a plain dict: its top-level keys
        for k in reg.get(args.kind, {}):
            print(k)


def main():
    p = argparse.ArgumentParser(prog="slice.py", description="Read/write one registry.json slice by id.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp, with_id=True):
        sp.add_argument("kind", choices=KINDS)
        if with_id:
            sp.add_argument("id", help="entry id (components/screens) or dotted key (tokens/meta/flow/erd)")
        sp.add_argument("--registry", default="registry.json", help="path to registry.json")

    g = sub.add_parser("get", help="print one slice as JSON")
    add_common(g)
    g.add_argument("--no-prose", action="store_true",
                    help="drop logicNotes/uiLogic/anatomy/spec/usage from the printed slice")
    g.add_argument("--fields",
                    help="comma-separated top-level keys to emit, in that order "
                         "(combine with --no-prose to also drop any prose key that survives)")
    g.set_defaults(func=cmd_get)

    s = sub.add_parser("set", help="merge a patch into one slice (patch from --patch FILE or stdin)")
    add_common(s)
    s.add_argument("--patch", help="JSON patch file (default: read stdin)")
    s.set_defaults(func=cmd_set)

    l = sub.add_parser("list", help="enumerate ids/keys for a kind")
    add_common(l, with_id=False)
    l.set_defaults(func=cmd_list)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
