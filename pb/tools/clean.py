#!/usr/bin/env python3
"""
clean.py — see what a project has piled up, and prune it only when told to (/pb:clean).

Everything pb leaves behind grows with use: closed explore rounds, backups, `.preview/server.log`,
screenshots, scratch candidate folders. Nothing expires on its own, and pb never deletes a backup
without being asked. This tool shows the pile and removes the part that is safe — or the part you
name with a keep flag. Stdlib only.

  clean.py [registry.json]                               dry run: what exists, what each flag would do
  clean.py [registry.json] --apply                       only the always-safe set (below)
  clean.py [registry.json] --apply --keep-backups 10     also keep the newest 10 backups in EACH place
  clean.py [registry.json] --apply --keep-closed 5       also keep the newest 5 closed explore rounds
  clean.py [registry.json] --apply --keep-patches 10     also keep the newest 10 .pb-patches/ task folders
  clean.py [registry.json] --apply --rotate-decisions    also run decisions_rotate.py on memory/decisions.md
  clean.py [registry.json] --json                        the same facts, machine-readable

A dry run is the default. A keep flag without --apply is a preview: it lists what it WOULD delete and
deletes nothing. The registry argument defaults to ./registry.json, then ./.prototype/registry.json
(adopt-in-place); a project folder is accepted too. Everything is measured relative to the folder
that holds the registry.

The always-safe set — what a bare --apply does:
  · render/_candidates/<target>/ folders with no open round (/pb:explore scratch nobody will read)
  · .preview/server.log trimmed to its last 256 KB when it is over 1 MB (in place, so a running
    server keeps writing to it)
  · .preview/shots/ deleted (the shot.py screenshots; they are regenerated on demand)
It NEVER deletes a backup or a closed round on its own.

The keep flags are the only way pb ever deletes a backup or a closed round, and N must be >= 1:
  --keep-backups N   keeps the newest N by modification time in memory/backups/ AND the newest N in
                     .pb-backups/ AND the newest N in memory/.pb-backups/ (the copies
                     decisions_rotate.py takes) — N in each place, not N in total. A
                     `registry.<v>.<ts>.json` and its `spec.<v>.<ts>/` snapshot are one backup — they
                     restore together.
  --keep-closed N    keeps the newest N closed explore rounds. A round is its manifest
                     `_closed/<name>.json`, its `<name>.brief.md` and its `<name>/` folder, deleted
                     together. The newest PROMOTED information-architecture round of each id is
                     never deleted and does not count toward N — /pb:plan reads its stable
                     `_closed/<ia-id>/` folder. A folder with no manifest of the same name
                     (`<ia-id>-superseded-<stamp>/`) is never deleted either.
  --keep-patches N   keeps the newest N task folders in `.pb-patches/` (what /pb:orchestrate writes:
                     `<TASK-ID>/{patch.json,check/,files/,shots/,REPORT.md}`), by modification time,
                     and deletes the rest. Files at the top of `.pb-patches/` (`BRIEF*.md`) are never
                     deleted. A task folder that is a symlink is refused, whatever it leads to.

One more flag does not delete, it moves:
  --rotate-decisions runs decisions_rotate.py on memory/decisions.md (whole entries, by date, verified
                     lossless; its own threshold is 500 KB). Under the threshold it says "nothing to do"
                     and that is success; a failed lossless check is reported, exit 1, and the original
                     stays. The row shows the log's size against that threshold either way.

Report only: `.claude/worktrees/*` (count and size). Never deleted here, by any flag.

Never touched, by any flag: an OPEN round (memory/explore/<target>.json, its folder, its candidates)
and the running preview server (stop it with `serve.py --stop`). Every path is checked to resolve to
somewhere inside the project folder immediately before it is deleted; a symlink that leads outside
is refused, and nothing outside is ever followed or removed.

Exit: 0 ok (a dry run, or everything asked for was done) · 1 at least one path was refused or could
not be removed, or a rotation failed (the rest was still done) · 2 usage (a keep flag below 1, no
registry.json).
"""
import argparse
import datetime
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Same places explore.py names (EXPLORE_DIR, CANDIDATES_DIR, SERVER_FILE, SERVER_LOG, LOG_MAX,
# LOG_KEEP, STALE_DAYS); tests/clean_tool.py asserts they have not drifted apart. Kept local so the
# health report can import this file without importing the explore engine (and render.py with it).
EXPLORE_DIR = os.path.join("memory", "explore")
CANDIDATES_DIR = os.path.join("render", "_candidates")
SERVER_FILE = os.path.join(".preview", "server.json")
SERVER_LOG = os.path.join(".preview", "server.log")
SHOTS_DIR = os.path.join(".preview", "shots")
# memory/.pb-backups/ is where decisions_rotate.py keeps the copy it takes before it moves anything.
BACKUP_PLACES = (os.path.join("memory", "backups"), ".pb-backups", os.path.join("memory", ".pb-backups"))
PATCHES_DIR = ".pb-patches"
DECISIONS_FILE = os.path.join("memory", "decisions.md")
DECISIONS_KB = 500            # decisions_rotate.DEFAULT_THRESHOLD_KB; tests/clean_tool.py asserts they match
ROTATE_TOOL = os.path.join(HERE, "decisions_rotate.py")
WORKTREES_DIR = os.path.join(".claude", "worktrees")
LOG_MAX = 1024 * 1024
LOG_KEEP = 256 * 1024
STALE_DAYS = 3
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


# ── measuring ────────────────────────────────────────────────────────────────────

def _lsize(path):
    """(bytes, files) under `path`, never following a symlink — a link counts as itself."""
    try:
        st = os.lstat(path)
    except OSError:
        return 0, 0
    if not stat.S_ISDIR(st.st_mode):
        return st.st_size, 1
    total = n = 0
    for cur, dirs, files in os.walk(path):          # followlinks=False: a linked dir is listed, not entered
        for f in files + [d for d in dirs if os.path.islink(os.path.join(cur, d))]:
            try:
                total += os.lstat(os.path.join(cur, f)).st_size
                n += 1
            except OSError:
                pass
    return total, n


def _mtime(path):
    try:
        return os.lstat(path).st_mtime
    except OSError:
        return 0.0


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _when(man, path):
    """When a manifest's round happened, as a timestamp: `closedAt`, else `createdAt`, else the file's mtime."""
    for key in ("closedAt", "createdAt"):
        raw = (man or {}).get(key)
        if raw:
            try:
                made = datetime.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                return made.timestamp()
            except (ValueError, TypeError, OverflowError, OSError):
                pass
    return _mtime(path)


def fmt_bytes(n):
    if n < 1024:
        return "%d B" % n
    if n < 1024 * 1024:
        return "%.0f KB" % (n / 1024.0)
    return "%.1f MB" % (n / (1024.0 * 1024.0))


def _rel(base_dir, path):
    return os.path.relpath(path, base_dir).replace(os.sep, "/")


def open_rounds(base_dir, now=None):
    """Every top-level manifest in memory/explore/ — an OPEN round — with its age. An unreadable one
    still counts (and protects its folders): not being able to read a round is no reason to touch it."""
    root = os.path.join(base_dir, EXPLORE_DIR)
    now = now or datetime.datetime.now().timestamp()
    out = []
    if not os.path.isdir(root):
        return out
    for f in sorted(os.listdir(root)):
        p = os.path.join(root, f)
        if not f.endswith(".json") or not os.path.isfile(p):
            continue
        man = _load(p) or {}
        target = str(man.get("target") or f[:-5])
        age = max(0.0, (now - _when(dict(man, closedAt=None), p)) / 86400.0)
        out.append({"target": target, "file": f[:-5], "ageDays": round(age, 1),
                    "stale": age > STALE_DAYS, "status": man.get("status", "open")})
    return out


def closed_rounds(base_dir):
    """The closed rounds in memory/explore/_closed/, newest first: [{name, when, bytes, pinned, paths}].
    `paths` is [(path, bytes)] — the folder and the brief first, the manifest last."""
    closed = os.path.join(base_dir, EXPLORE_DIR, "_closed")
    rounds = []
    if not os.path.isdir(closed):
        return rounds
    for f in sorted(os.listdir(closed)):
        p = os.path.join(closed, f)
        if not f.endswith(".json") or not (os.path.isfile(p) or os.path.islink(p)):
            continue
        name = f[:-5]
        man = _load(p) or {}
        paths = []
        for extra in (os.path.join(closed, name), os.path.join(closed, name + ".brief.md")):
            if os.path.lexists(extra):
                paths.append((extra, _lsize(extra)[0]))
        paths.append((p, _lsize(p)[0]))
        rounds.append({"name": name, "target": str(man.get("target") or name), "mode": man.get("mode"),
                       "status": man.get("status"), "when": _when(man, p), "pinned": False,
                       "paths": paths, "bytes": sum(b for _p, b in paths)})
    # The newest promoted IA round of each id is what /pb:plan reads (its folder is the stable
    # _closed/<ia-id>/): it is pinned — kept, and not counted toward --keep-closed.
    newest = {}
    for r in rounds:
        if r["mode"] == "ia" and r["status"] == "promoted":
            if r["target"] not in newest or r["when"] > newest[r["target"]]["when"]:
                newest[r["target"]] = r
    for target, r in newest.items():
        if os.path.lexists(os.path.join(closed, target)):
            r["pinned"] = True
    rounds.sort(key=lambda r: (r["when"], r["name"]), reverse=True)
    return rounds


_PAIR = (re.compile(r"^registry\.(.+)\.json$"), re.compile(r"^spec\.(.+)$"))


def backups_in(d):
    """The backups in one folder, newest first: [{name, mtime, bytes, paths}]. Every entry (a file or a
    folder) is one backup, except that `registry.<v>.<ts>.json` and its `spec.<v>.<ts>/` snapshot —
    which the migration runner writes as a pair and restores as a pair — are one."""
    groups = {}
    if not os.path.isdir(d):
        return []
    for name in os.listdir(d):
        if name == ".DS_Store":
            continue
        key = name
        for pat in _PAIR:
            m = pat.match(name)
            if m:
                key = "pair:" + m.group(1)
                break
        p = os.path.join(d, name)
        g = groups.setdefault(key, {"name": name, "mtime": 0.0, "bytes": 0, "paths": []})
        size = _lsize(p)[0]
        g["paths"].append((p, size))
        g["bytes"] += size
        g["mtime"] = max(g["mtime"], _mtime(p))
        if name.startswith("registry."):
            g["name"] = name
    out = list(groups.values())
    out.sort(key=lambda g: (g["mtime"], g["name"]), reverse=True)
    return out


def orphan_candidates(base_dir, opened):
    """render/_candidates/<target>/ folders with no manifest for <target> — scratch nobody reads."""
    root = os.path.join(base_dir, CANDIDATES_DIR)
    held = {r["target"] for r in opened} | {r["file"] for r in opened}
    out, in_use = [], 0
    if not os.path.isdir(root):
        return out, in_use
    for t in sorted(os.listdir(root)):
        p = os.path.join(root, t)
        if not (os.path.isdir(p) or os.path.islink(p)):
            continue
        if t in held:
            in_use += 1
            continue
        out.append({"target": t, "path": p, "bytes": _lsize(p)[0], "files": _lsize(p)[1]})
    return out, in_use


def preview_status(base_dir, reg_path, timeout=2):
    """Is THIS project's preview server running? {running, url, pid, idleSeconds, clients, startedAt}.
    Reads .preview/server.json and asks the recorded loopback URL who it is (explore._ours): a stale
    record, or another project's server on the same port, is "not running". Never signals anything."""
    out = {"running": False, "url": None, "pid": None, "idleSeconds": None, "clients": None, "startedAt": None}
    if not os.path.isfile(os.path.join(base_dir, SERVER_FILE)):
        return out
    try:
        import explore
        rec = explore.server_record(base_dir)
        if not rec:
            return out
        url = rec["url"].rstrip("/")
        if urllib.parse.urlparse(url).hostname not in _LOOPBACK:
            return out
        if not explore._ours(url, reg_path):
            return out
        out.update(running=True, url=url + "/", pid=rec.get("pid"))
        code, body = explore._get(url + "/__pb_health", timeout=timeout)
        if code == 200:
            health = json.loads(body)
            out.update(pid=health.get("pid", out["pid"]), idleSeconds=health.get("idleSeconds"),
                       clients=health.get("clients"), startedAt=health.get("startedAt"))
    except Exception:           # a health probe must never take the caller down with it
        pass
    return out


def patch_tasks(base_dir):
    """`.pb-patches/` (written by /pb:orchestrate): the task folders newest first, and the loose files at
    its top (BRIEF*.md …), which are counted in the size but are never a candidate for deletion.
    → {path, link, tasks: [{name, path, mtime, bytes, files, link}], count, bytes, loose: {files, bytes}}.
    A `.pb-patches` that is itself a symlink is reported and never listed or entered."""
    root = os.path.join(base_dir, PATCHES_DIR)
    out = {"path": root, "link": os.path.islink(root), "tasks": [], "count": 0, "bytes": 0,
           "loose": {"files": 0, "bytes": 0}}
    if out["link"] or not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        is_link = os.path.islink(p)
        if is_link or os.path.isdir(p):
            if is_link and not os.path.isdir(p):          # a link to a file or to nothing: just a loose entry
                out["loose"]["files"] += 1
                out["loose"]["bytes"] += _lsize(p)[0]
                continue
            size, files = _lsize(p)
            out["tasks"].append({"name": name, "path": p, "mtime": _mtime(p), "bytes": size,
                                 "files": files, "link": is_link})
        else:
            out["loose"]["files"] += 1
            out["loose"]["bytes"] += _lsize(p)[0]
    out["tasks"].sort(key=lambda t: (t["mtime"], t["name"]), reverse=True)
    out["count"] = len(out["tasks"])
    out["bytes"] = sum(t["bytes"] for t in out["tasks"]) + out["loose"]["bytes"]
    return out


def decisions_log(base_dir):
    """memory/decisions.md against decisions_rotate.py's threshold: {path, exists, bytes, kb, thresholdKb,
    over, siblings}. `siblings` are the already-rotated `decisions-*.md` files beside it."""
    path = os.path.join(base_dir, DECISIONS_FILE)
    exists = os.path.isfile(path)
    size = os.lstat(path).st_size if exists else 0
    mem = os.path.dirname(path)
    sibs = [f for f in os.listdir(mem) if re.fullmatch(r"decisions-[^.]+\.md", f)] if os.path.isdir(mem) else []
    return {"path": path, "exists": exists, "bytes": size, "kb": size / 1024.0, "thresholdKb": DECISIONS_KB,
            "over": size > DECISIONS_KB * 1024, "siblings": len(sibs)}


def worktrees(base_dir):
    """`.claude/worktrees/*` — report only. Looked for beside the registry and, in an adopt-in-place
    project (`<repo>/.prototype/`), at the repo root. → {places, entries: [{name, bytes}], count, bytes}."""
    places = [os.path.join(base_dir, WORKTREES_DIR)]
    if os.path.basename(base_dir) == ".prototype":
        places.append(os.path.join(os.path.dirname(base_dir), WORKTREES_DIR))
    seen, entries = set(), []
    for root in places:
        if os.path.islink(root) or not os.path.isdir(root) or os.path.realpath(root) in seen:
            continue
        seen.add(os.path.realpath(root))
        for name in sorted(os.listdir(root)):
            p = os.path.join(root, name)
            if os.path.isdir(p) or os.path.islink(p):
                entries.append({"name": name, "path": p, "bytes": _lsize(p)[0]})
    return {"entries": entries, "count": len(entries), "bytes": sum(e["bytes"] for e in entries)}


def scan(base_dir, reg_path=None, probe=True):
    """Everything pb has piled up under `base_dir`, measured and never changed."""
    reg_path = reg_path or os.path.join(base_dir, "registry.json")
    opened = open_rounds(base_dir)
    closed = closed_rounds(base_dir)
    closed_dir = os.path.join(base_dir, EXPLORE_DIR, "_closed")
    orphans, in_use = orphan_candidates(base_dir, opened)
    backups = {}
    for place in BACKUP_PLACES:
        groups = backups_in(os.path.join(base_dir, place))
        backups[place.replace(os.sep, "/")] = {"entries": groups, "count": len(groups),
                                               "bytes": sum(g["bytes"] for g in groups)}
    log = os.path.join(base_dir, SERVER_LOG)
    log_bytes = _lsize(log)[0] if os.path.lexists(log) else 0
    shots = os.path.join(base_dir, SHOTS_DIR)
    shot_bytes, shot_files = _lsize(shots) if os.path.lexists(shots) else (0, 0)
    return {
        "root": base_dir,
        "open": opened,
        "closed": {"rounds": closed, "count": len(closed), "bytes": _lsize(closed_dir)[0] if os.path.isdir(closed_dir) else 0,
                   "pinned": sum(1 for r in closed if r["pinned"])},
        "backups": backups,
        "candidates": {"orphans": orphans, "bytes": sum(o["bytes"] for o in orphans), "inUse": in_use},
        "serverLog": {"path": log, "bytes": log_bytes, "trim": log_bytes > LOG_MAX},
        "shots": {"path": shots, "files": shot_files, "bytes": shot_bytes},
        "patches": patch_tasks(base_dir),
        "decisions": decisions_log(base_dir),
        "worktrees": worktrees(base_dir),
        "server": preview_status(base_dir, reg_path) if probe else {"running": None},
    }


# ── planning ─────────────────────────────────────────────────────────────────────

def plan(data, keep_closed=None, keep_backups=None, keep_patches=None, rotate_decisions=False):
    """What would be done: [{cat, label, kind, paths: [(path, bytes)], bytes}]. A pure function of the
    scan — it never lists an open round, a pinned IA round, an unpaired closed folder or an in-use candidate,
    a loose file in .pb-patches/, or a worktree. kind is delete | trim | rotate."""
    acts = []
    for o in data["candidates"]["orphans"]:
        acts.append({"cat": "candidates", "label": o["target"], "kind": "delete",
                     "paths": [(o["path"], o["bytes"])], "bytes": o["bytes"]})
    if data["serverLog"]["trim"]:
        acts.append({"cat": "serverLog", "label": SERVER_LOG.replace(os.sep, "/"), "kind": "trim",
                     "paths": [(data["serverLog"]["path"], data["serverLog"]["bytes"])],
                     "bytes": max(0, data["serverLog"]["bytes"] - LOG_KEEP)})
    if data["shots"]["files"] or os.path.lexists(data["shots"]["path"]):
        acts.append({"cat": "shots", "label": SHOTS_DIR.replace(os.sep, "/") + "/", "kind": "delete",
                     "paths": [(data["shots"]["path"], data["shots"]["bytes"])], "bytes": data["shots"]["bytes"]})
    if keep_closed is not None:
        ranked = [r for r in data["closed"]["rounds"] if not r["pinned"]]
        for r in ranked[keep_closed:]:
            acts.append({"cat": "closed", "label": r["name"], "kind": "delete", "paths": r["paths"], "bytes": r["bytes"]})
    if keep_backups is not None:
        for place, info in data["backups"].items():
            for g in info["entries"][keep_backups:]:
                acts.append({"cat": "backups:" + place, "label": g["name"], "kind": "delete",
                             "paths": g["paths"], "bytes": g["bytes"]})
    if keep_patches is not None:
        for t in data["patches"]["tasks"][keep_patches:]:
            acts.append({"cat": "patches", "label": t["name"], "kind": "delete", "noLinks": True,
                         "paths": [(t["path"], t["bytes"])], "bytes": t["bytes"]})
    if rotate_decisions and data["decisions"]["exists"]:
        d = data["decisions"]
        acts.append({"cat": "decisions", "label": DECISIONS_FILE.replace(os.sep, "/"), "kind": "rotate",
                     "paths": [(d["path"], d["bytes"])], "bytes": 0})
    return acts


# ── removing ─────────────────────────────────────────────────────────────────────

def _inside(path, root):
    """The ONE containment check: `path` resolves (links followed) to somewhere strictly inside `root`."""
    return os.path.realpath(path).startswith(root + os.sep)


def _remove(path, root):
    """Delete one path → (ok, why). The realpath check runs immediately before the delete. A symlink is
    only ever removed itself — and only when it leads somewhere inside the project; one that leads
    outside is refused, so nothing outside is followed. rmtree does not follow a link inside a tree."""
    if not _inside(path, root):
        return False, "resolves outside the project"
    # belt and braces: an OPEN round lives in memory/explore/ outside _closed/ — never ours to delete
    real = os.path.realpath(path)
    explore_root = os.path.realpath(os.path.join(root, EXPLORE_DIR))
    if (real == explore_root or real.startswith(explore_root + os.sep)) \
            and not real.startswith(os.path.join(explore_root, "_closed") + os.sep):
        return False, "belongs to an open explore round"
    try:
        if os.path.islink(path):
            os.unlink(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except OSError as e:
        return False, str(e.strerror or e)
    return True, ""


def _trim_log(path, root):
    """Keep only the last LOG_KEEP bytes of the server log, from a line start, IN PLACE: a running
    server holds the file open for append and must keep writing to the same file."""
    if not _inside(path, root):
        return 0, "resolves outside the project"
    try:
        with open(path, "r+b") as f:
            size = f.seek(0, os.SEEK_END)
            if size <= LOG_MAX:
                return 0, ""
            f.seek(size - LOG_KEEP)
            tail = f.read()
            cut = tail.find(b"\n")
            if cut != -1 and cut + 1 < len(tail):
                tail = tail[cut + 1:]
            f.seek(0)
            f.write(tail)
            f.truncate()
            return size - len(tail), ""
    except OSError as e:
        return 0, str(e.strerror or e)


def _rotate_decisions(path, root):
    """Run decisions_rotate.py --apply on the log → (ok, why, output, rotated). A real invocation: its
    exit code is the answer. 0 is success, "under the threshold, nothing to do" included; 2 means it
    aborted (a failed lossless check restores the original itself) and is reported, never swallowed."""
    if not _inside(path, root):
        return False, "resolves outside the project", "", False
    before = os.lstat(path).st_size
    try:
        p = subprocess.run([sys.executable, "-B", ROTATE_TOOL, path, "--apply"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, "decisions_rotate.py could not run (%s)" % (getattr(e, "strerror", None) or e), "", False
    out = (p.stdout + p.stderr).strip()
    if p.returncode != 0:
        last = (out.splitlines() or ["no output"])[-1]
        return False, "rotation failed (exit %d) — the original stays: %s" % (p.returncode, last.strip()), out, False
    moved = before - os.lstat(path).st_size
    return True, "", out, moved > 0


def apply_actions(base_dir, acts):
    """Do the plan. → {removed: [{cat,label,path,bytes,kind}], refused: [{cat,path,why}], freedBytes,
    rotated: [{path, rotated, movedBytes, output}]}"""
    root = os.path.realpath(base_dir)
    removed, refused, freed, rotated = [], [], 0, []
    for a in acts:
        if a["kind"] == "rotate":
            for path, size in a["paths"]:
                ok, why, out, did = _rotate_decisions(path, root)
                if ok:
                    rotated.append({"path": _rel(base_dir, path), "rotated": did,
                                    "movedBytes": size - os.lstat(path).st_size if did else 0, "output": out})
                else:
                    refused.append({"cat": a["cat"], "path": _rel(base_dir, path), "why": why})
                    rotated.append({"path": _rel(base_dir, path), "rotated": False, "movedBytes": 0, "output": out})
            continue
        if a["kind"] == "delete" and len(a["paths"]) > 1:
            # a round / a backup pair goes whole or not at all: one path that leaves the project keeps the rest
            bad = [p for p, _b in a["paths"] if not _inside(p, root)]
            if bad:
                for p, _b in a["paths"]:
                    refused.append({"cat": a["cat"], "path": _rel(base_dir, p),
                                    "why": "resolves outside the project" if p in bad
                                    else "kept — %s has a path that resolves outside the project" % a["label"]})
                continue
        for path, size in a["paths"]:
            rel = _rel(base_dir, path)
            if a.get("noLinks") and os.path.islink(path):
                refused.append({"cat": a["cat"], "path": rel, "why": "is a symlink — never followed or removed here"})
                continue
            if a["kind"] == "trim":
                gone, why = _trim_log(path, root)
                ok = not why
            else:
                ok, why = _remove(path, root)
                gone = size if ok else 0
            if ok:
                freed += gone
                if a["kind"] == "delete" or gone:
                    removed.append({"cat": a["cat"], "label": a["label"], "path": rel, "bytes": gone, "kind": a["kind"]})
            else:
                refused.append({"cat": a["cat"], "path": rel, "why": why})
    # _archive() drops an emptied render/_candidates/ — do the same, through the same check
    cand = os.path.join(base_dir, CANDIDATES_DIR)
    if any(a["cat"] == "candidates" for a in acts) and os.path.isdir(cand) and not os.listdir(cand) \
            and _inside(cand, root):
        try:
            os.rmdir(cand)
        except OSError:
            pass
    return {"removed": removed, "refused": refused, "freedBytes": freed, "rotated": rotated}


# ── reporting ────────────────────────────────────────────────────────────────────

def rows(data, acts, keep_closed, keep_backups, result=None, keep_patches=None, rotate_decisions=False):
    """The table, as data: [{what, count, bytes, action, detail}]. `result` is apply_actions' answer, or None for a dry run."""
    done = result is not None
    gone_by_cat, refused_cats = {}, {}
    for r in (result or {}).get("removed", []):          # items, not paths: a closed round is three paths
        gone_by_cat.setdefault(r["cat"], set()).add(r["label"])
    for r in (result or {}).get("refused", []):
        refused_cats[r["cat"]] = refused_cats.get(r["cat"], 0) + 1

    def verb(cat, n, past, future, count=True):
        if not n:
            return None
        text = past if done else future
        if count:
            text += " %d" % (len(gone_by_cat.get(cat, ())) if done else n)
        if refused_cats.get(cat):
            text += " (%d refused)" % refused_cats[cat]
        return text

    out = []
    op = data["open"]
    oldest = max((r["ageDays"] for r in op), default=0)
    stale = sum(1 for r in op if r["stale"])
    out.append({"what": "open explore rounds", "count": len(op), "bytes": None,
                "action": "never touched" + (" — oldest %.1f d%s" % (oldest, ", %d STALE" % stale if stale else "") if op else ""),
                "detail": [{"target": r["target"], "ageDays": r["ageDays"], "stale": r["stale"]} for r in op]})
    c = data["closed"]
    kept_note = " (+%d pinned IA)" % c["pinned"] if c["pinned"] else ""
    if keep_closed is None:
        action = "kept — --apply --keep-closed N deletes all but the newest N"
    else:
        n_del = sum(1 for a in acts if a["cat"] == "closed")
        action = (verb("closed", n_del, "deleted", "would delete") or "nothing older than the newest %d" % keep_closed) \
            + ", keeping the newest %d" % keep_closed
    out.append({"what": "closed explore rounds" + kept_note, "count": c["count"], "bytes": c["bytes"], "action": action,
                "detail": [r["name"] + (" (pinned)" if r["pinned"] else "") for r in c["rounds"]]})
    for place, info in data["backups"].items():
        if keep_backups is None:
            action = "kept — --apply --keep-backups N deletes all but the newest N"
        else:
            n_del = sum(1 for a in acts if a["cat"] == "backups:" + place)
            action = (verb("backups:" + place, n_del, "deleted", "would delete") or "nothing older than the newest %d" % keep_backups) \
                + ", keeping the newest %d here" % keep_backups
        out.append({"what": place + "/", "count": info["count"], "bytes": info["bytes"], "action": action,
                    "detail": [g["name"] for g in info["entries"]]})
    pt = data["patches"]
    if pt["link"]:
        action = "is a symlink — not listed, never touched"
    elif keep_patches is None:
        action = "kept — --apply --keep-patches N deletes all but the newest N task folders"
        if pt["loose"]["files"]:
            action += " (the %d file(s) at its top stay)" % pt["loose"]["files"]
    else:
        n_del = sum(1 for a in acts if a["cat"] == "patches")
        action = (verb("patches", n_del, "deleted", "would delete") or "nothing older than the newest %d" % keep_patches) \
            + ", keeping the newest %d" % keep_patches
        if pt["loose"]["files"]:
            action += " (the %d file(s) at its top stay)" % pt["loose"]["files"]
    out.append({"what": PATCHES_DIR + "/ task folders", "count": pt["count"], "bytes": pt["bytes"], "action": action,
                "detail": [t["name"] + (" (symlink)" if t["link"] else "") for t in pt["tasks"]]})
    dl = data["decisions"]
    dname = DECISIONS_FILE.replace(os.sep, "/")
    if not dl["exists"]:
        action = "none"
    else:
        share = "%.0f KB of %d KB" % (dl["kb"], dl["thresholdKb"])
        sib = " (+%d rotated)" % dl["siblings"] if dl["siblings"] else ""
        rot = [r for r in (result or {}).get("rotated", [])]
        if done and rot:
            if refused_cats.get("decisions"):
                action = "%s — rotation FAILED, the original stays (see below)" % share
            elif rot[0]["rotated"]:
                action = "%s — rotated: %s moved into decisions-<year>.md, verified lossless" % (share, fmt_bytes(rot[0]["movedBytes"]))
            else:
                action = "%s — under the threshold, nothing to do" % share
        elif rotate_decisions:
            action = ("%s — OVER the threshold, would rotate (lossless, by date)" if dl["over"]
                      else "%s — under the threshold, rotating would do nothing") % share
        elif dl["over"]:
            action = "%s — OVER the threshold; --apply --rotate-decisions moves old entries out, losslessly" % share
        else:
            action = "%s — under the threshold; --apply --rotate-decisions only acts past it" % share
        action += sib
    out.append({"what": dname, "count": None, "bytes": dl["bytes"] if dl["exists"] else None, "action": action, "detail": []})
    wt = data["worktrees"]
    out.append({"what": WORKTREES_DIR.replace(os.sep, "/") + "/", "count": wt["count"], "bytes": wt["bytes"],
                "action": "report only — never deleted here" + ("; each is a git worktree: remove it with git, if you want it gone" if wt["count"] else ""),
                "detail": [e["name"] for e in wt["entries"]]})
    log = data["serverLog"]
    if log["trim"]:
        action = ("trimmed to the last %d KB" % (LOG_KEEP // 1024)) if done and not refused_cats.get("serverLog") \
            else "would trim to the last %d KB" % (LOG_KEEP // 1024)
        if refused_cats.get("serverLog"):
            action = "not trimmed (refused)"
    else:
        action = "kept (under %d MB)" % (LOG_MAX // (1024 * 1024))
    out.append({"what": SERVER_LOG.replace(os.sep, "/"), "count": 1 if log["bytes"] else 0, "bytes": log["bytes"],
                "action": action, "detail": []})
    sh = data["shots"]
    n = 1 if os.path.lexists(sh["path"]) else 0
    out.append({"what": SHOTS_DIR.replace(os.sep, "/") + "/", "count": sh["files"], "bytes": sh["bytes"],
                "action": verb("shots", n, "deleted", "would delete", count=False) or "nothing to delete",
                "detail": []})
    cd = data["candidates"]
    out.append({"what": "render/_candidates/ with no round", "count": len(cd["orphans"]), "bytes": cd["bytes"],
                "action": (verb("candidates", len(cd["orphans"]), "deleted", "would delete") or "nothing to delete")
                          + ("  (%d in use by an open round — kept)" % cd["inUse"] if cd["inUse"] else ""),
                "detail": [o["target"] for o in cd["orphans"]]})
    sv = data["server"]
    if sv.get("running"):
        idle = sv.get("idleSeconds")
        text = "running at %s%s — never stopped here: serve.py --stop" % (
            sv["url"], (", idle %.0f min" % (idle / 60.0)) if isinstance(idle, (int, float)) else "")
    elif sv.get("running") is False:
        text = "not running"
    else:
        text = "not checked"
    out.append({"what": "preview server", "count": None, "bytes": None, "action": text, "detail": []})
    return out


def _fmt_row(r, w):
    count = "" if r["count"] is None else str(r["count"])
    size = "" if r["bytes"] is None else fmt_bytes(r["bytes"])
    return "  %-*s %5s %9s   %s" % (w, r["what"], count, size, r["action"])


def print_table(table, header, applied, result, acts, keep_closed, keep_backups, base_dir, keep_patches=None):
    print(header)
    print()
    w = max(len(r["what"]) for r in table)
    print("  %-*s %5s %9s   %s" % (w, "what", "count", "size", "action"))
    for r in table:
        print(_fmt_row(r, w))
    if keep_backups is not None:
        print("\n  --keep-backups %d keeps the newest %d in memory/backups/ AND the newest %d in .pb-backups/ AND the newest %d "
              "in memory/.pb-backups/ (per place, not in total; a registry backup and its spec snapshot count as one)"
              % (keep_backups, keep_backups, keep_backups, keep_backups))
    if keep_closed is not None:
        print("\n  --keep-closed %d keeps the newest %d closed rounds (manifest + brief + folder go together); "
              "the newest promoted IA round of each id is pinned and not counted"
              % (keep_closed, keep_closed))
    if keep_patches is not None:
        print("\n  --keep-patches %d keeps the newest %d task folders in .pb-patches/ by modification time; "
              "files at the top of .pb-patches/ (BRIEF*.md) are never deleted" % (keep_patches, keep_patches))
    if not applied:
        print("\n(Dry run — nothing was changed. %s)" % (
            "Pass --apply to do the above." if acts else "There is nothing to remove with the flags given."))
        return
    print()
    for r in result["removed"]:
        print("  removed  %-9s %s  (%s)" % (r["kind"] == "trim" and "trimmed" or "deleted", r["path"], fmt_bytes(r["bytes"])))
    for r in result.get("rotated", []):
        print("  rotate   %s — decisions_rotate.py says:" % r["path"])
        for line in (r["output"] or "(no output)").splitlines():
            print("             " + line)
    for r in result["refused"]:
        print("  REFUSED  %s — %s" % (r["path"], r["why"]))
    print("\n✓ freed %s across %d path(s)%s" % (
        fmt_bytes(result["freedBytes"]), len(result["removed"]),
        "; %d refused" % len(result["refused"]) if result["refused"] else ""))


# ── cli ──────────────────────────────────────────────────────────────────────────

def _keep(text):
    try:
        n = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("%r is not a whole number" % text)
    if n < 1:
        raise argparse.ArgumentTypeError(
            "must be at least 1 (got %d) — a keep flag that keeps nothing would delete every backup or round" % n)
    return n


def resolve_registry(arg):
    """The registry to work on → a path, or None. No argument: ./registry.json, then the adopt-in-place
    ./.prototype/registry.json (the way report.py finds it). A folder is searched the same way."""
    if arg is None:
        cands = ["registry.json", os.path.join(".prototype", "registry.json")]
    elif os.path.isdir(arg):
        cands = [os.path.join(arg, "registry.json"), os.path.join(arg, ".prototype", "registry.json")]
    elif os.path.basename(arg) == "registry.json":
        cands = [arg, os.path.join(os.path.dirname(arg), ".prototype", "registry.json")]
    else:
        cands = [arg]
    for c in cands:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return None


def _jsonable(data):
    """The scan with its path tuples flattened, for --json."""
    c = data["closed"]
    return {
        "open": data["open"],
        "closed": {"count": c["count"], "bytes": c["bytes"], "pinned": c["pinned"],
                   "rounds": [{"name": r["name"], "bytes": r["bytes"], "pinned": r["pinned"]} for r in c["rounds"]]},
        "backups": {k: {"count": v["count"], "bytes": v["bytes"],
                        "entries": [{"name": g["name"], "bytes": g["bytes"]} for g in v["entries"]]}
                    for k, v in data["backups"].items()},
        "candidates": {"orphans": [{"target": o["target"], "bytes": o["bytes"]} for o in data["candidates"]["orphans"]],
                       "inUse": data["candidates"]["inUse"], "bytes": data["candidates"]["bytes"]},
        "serverLog": {"bytes": data["serverLog"]["bytes"], "trim": data["serverLog"]["trim"]},
        "shots": {"files": data["shots"]["files"], "bytes": data["shots"]["bytes"]},
        "patches": {"count": data["patches"]["count"], "bytes": data["patches"]["bytes"], "link": data["patches"]["link"],
                    "loose": data["patches"]["loose"],
                    "tasks": [{"name": t["name"], "bytes": t["bytes"], "files": t["files"], "link": t["link"]}
                              for t in data["patches"]["tasks"]]},
        "decisions": {k: data["decisions"][k] for k in ("exists", "bytes", "thresholdKb", "over", "siblings")},
        "worktrees": {"count": data["worktrees"]["count"], "bytes": data["worktrees"]["bytes"],
                      "entries": [{"name": e["name"], "bytes": e["bytes"]} for e in data["worktrees"]["entries"]]},
        "server": data["server"],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="clean.py", description="See what a project has piled up, and prune it only when told to. "
        "Dry run by default.")
    ap.add_argument("registry", nargs="?", help="registry.json or a project folder (default ./registry.json, then ./.prototype/registry.json)")
    ap.add_argument("--apply", action="store_true", help="do it (default is a dry run)")
    ap.add_argument("--keep-closed", type=_keep, metavar="N", help="keep the newest N closed explore rounds, delete the rest (N >= 1; needs --apply to delete)")
    ap.add_argument("--keep-backups", type=_keep, metavar="N", help="keep the newest N backups in memory/backups/, in .pb-backups/ AND in memory/.pb-backups/, delete the rest (N >= 1; needs --apply to delete)")
    ap.add_argument("--keep-patches", type=_keep, metavar="N", help="keep the newest N task folders in .pb-patches/ (top-level files stay), delete the rest (N >= 1; needs --apply to delete)")
    ap.add_argument("--rotate-decisions", action="store_true", help="run decisions_rotate.py on memory/decisions.md (lossless; a no-op under its 500 KB threshold; needs --apply to run)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)           # a bad --keep-* value exits 2 here

    reg = resolve_registry(args.registry)
    if not reg:
        print("clean.py: no registry.json found (looked in %s)" % (args.registry or "./ and ./.prototype/"), file=sys.stderr)
        return 2
    base_dir = os.path.dirname(reg)

    data = scan(base_dir, reg)
    acts = plan(data, args.keep_closed, args.keep_backups, args.keep_patches, args.rotate_decisions)
    result = apply_actions(base_dir, acts) if args.apply else None
    table = rows(data, acts, args.keep_closed, args.keep_backups, result, args.keep_patches, args.rotate_decisions)
    code = 1 if result and result["refused"] else 0

    if args.json:
        doc = {"root": base_dir, "apply": bool(args.apply), "keepClosed": args.keep_closed,
               "keepBackups": args.keep_backups, "keepPatches": args.keep_patches,
               "rotateDecisions": bool(args.rotate_decisions), "found": _jsonable(data),
               "table": [{k: v for k, v in r.items() if k != "detail"} for r in table],
               "planned": [{"cat": a["cat"], "label": a["label"], "kind": a["kind"], "bytes": a["bytes"],
                            "paths": [_rel(base_dir, p) for p, _b in a["paths"]]} for a in acts],
               "removed": result["removed"] if result else [], "refused": result["refused"] if result else [],
               "rotated": result["rotated"] if result else [],
               "freedBytes": result["freedBytes"] if result else 0, "exit": code}
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        return code

    header = "clean.py — %s%s" % (base_dir, "" if args.apply else "   (dry run)")
    print_table(table, header, bool(args.apply), result, acts, args.keep_closed, args.keep_backups, base_dir,
                args.keep_patches)
    return code


if __name__ == "__main__":
    sys.exit(main())
