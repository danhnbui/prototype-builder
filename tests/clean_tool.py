#!/usr/bin/env python3
"""
clean_tool.py — /pb:clean's tool (pb/tools/clean.py): see the pile, prune it only when told to.

A tool that deletes backups has to be provably unable to delete the wrong thing, so these are the
properties, each on a project built in a temp copy of fixtures/golden:

  1. the folders and files clean.py names are the ones explore.py names (they cannot drift apart)
  2. a dry run changes nothing — byte for byte — and lists every category with a count and a size;
     a keep flag without --apply is the same dry run
  3. bare --apply removes the orphan candidates, trims a >1 MB server.log to <= 256 KB keeping its
     tail, deletes .preview/shots/ — and leaves every backup and every closed round alone
  4. --apply --keep-backups 2 keeps exactly the newest 2 in memory/backups/ AND in .pb-backups/
     (a registry backup and its spec snapshot are one backup)
  5. --apply --keep-closed 1 keeps the newest closed round (manifest + brief + folder) and removes the
     others together; the newest promoted IA round and its stable folder stay
  6. an OPEN round — manifest, working folder, candidates, even an unreadable manifest — is never
     touched by any flag combination
  7. a keep flag of 0, a negative or a non-number is a usage error (exit 2) and deletes nothing
  8. a symlink inside the project that leads outside is never followed: the outside folder and files
     survive, the refusal is reported and the exit code is 1; a link that leads inside is removed
     as a link and its target survives
  9. the registry is found as ./registry.json, as a project folder, and under .prototype/ (adopt-in-place);
     no registry is exit 2; --json is valid JSON with the same facts

Pure stdlib, no browser. Usage: python3 tests/clean_tool.py · Exit 0/1.
"""
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "pb", "tools", "clean.py")
GOLDEN = os.path.join(ROOT, "fixtures", "golden")

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def write(path, text="x", mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def touch_tree(path, mtime):
    """Set the mtime of a folder after its children are written (writing a child changes it)."""
    os.utime(path, (mtime, mtime))


def tree_hash(root):
    """Names, kinds, link targets and file bytes under root — never following a link."""
    h = hashlib.sha256()
    for cur, dirs, files in os.walk(root):
        dirs.sort()
        files.sort()
        h.update(("D " + os.path.relpath(cur, root) + "\n").encode())
        for name in files + [d for d in dirs if os.path.islink(os.path.join(cur, d))]:
            p = os.path.join(cur, name)
            if os.path.islink(p):
                h.update(("L %s -> %s\n" % (name, os.readlink(p))).encode())
            else:
                with open(p, "rb") as f:
                    h.update(("F %s " % name).encode() + hashlib.sha256(f.read()).digest())
    return h.hexdigest()


def names(path):
    return sorted(os.listdir(path)) if os.path.isdir(path) else None


def run(*args, cwd=None):
    r = subprocess.run([sys.executable, TOOL] + list(args), cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


BASE = datetime.datetime(2026, 1, 1).timestamp()
DAY = 86400


def iso(ts):
    return datetime.datetime.fromtimestamp(ts).replace(microsecond=0).isoformat()


def closed_round(proj, name, target, ts, mode="target", status="rejected", folder=True, brief=True):
    closed = os.path.join(proj, "memory", "explore", "_closed")
    write(os.path.join(closed, name + ".json"),
          json.dumps({"target": target, "mode": mode, "status": status, "closedAt": iso(ts)}), ts)
    if brief:
        write(os.path.join(closed, name + ".brief.md"), "# brief\n" * 50, ts)
    if folder:
        write(os.path.join(closed, name, "plans", "p.md"), "plan\n" * 400, ts)
        write(os.path.join(closed, name, "shots", "s.png"), "p" * 3000, ts)
        touch_tree(os.path.join(closed, name), ts)


def build(base):
    """A project with every kind of pile. Returns (project_dir, outside_dir)."""
    proj = os.path.join(base, "proj")
    shutil.copytree(GOLDEN, proj, ignore=shutil.ignore_patterns(".preview"))
    outside = os.path.join(base, "outside")
    write(os.path.join(outside, "precious.txt"), "keep me")
    write(os.path.join(outside, "sub", "deeper.txt"), "keep me too")

    ex = os.path.join(proj, "memory", "explore")
    # two OPEN rounds: one well-formed and old, one with an unreadable manifest
    write(os.path.join(ex, "alpha.json"), json.dumps({"target": "alpha", "status": "open", "mode": "target",
                                                      "createdAt": iso(datetime.datetime.now().timestamp() - 5 * DAY)}))
    write(os.path.join(ex, "alpha.brief.md"), "# direction\n")
    write(os.path.join(ex, "alpha", "plans", "a.md"), "plan\n")
    write(os.path.join(ex, "broken.json"), "{ not json")
    write(os.path.join(ex, "broken", "plans", "b.md"), "plan\n")
    write(os.path.join(proj, "render", "_candidates", "alpha", "opt-a", "body.js"), "// candidate\n" * 100)
    write(os.path.join(proj, "render", "_candidates", "broken", "opt-a", "body.js"), "// candidate\n" * 100)
    # scratch with no round at all
    write(os.path.join(proj, "render", "_candidates", "ghost", "opt-a", "body.js"), "// scratch\n" * 500)
    write(os.path.join(proj, "render", "_candidates", "ghost2", "x.js"), "// scratch\n" * 100)

    # closed rounds: three ordinary (old, mid, new) + a promoted IA round with its stable folder and an older superseded one
    closed_round(proj, "old-20260101T000000", "old", BASE)
    closed_round(proj, "mid-20260201T000000", "mid", BASE + 31 * DAY)
    closed_round(proj, "new-20260301T000000", "new", BASE + 59 * DAY)
    closed_round(proj, "nav-20260105T000000", "nav", BASE + 4 * DAY, mode="ia", status="promoted", folder=False)
    write(os.path.join(ex, "_closed", "nav", "a.ia.json"), '{"layers": []}', BASE + 4 * DAY)
    write(os.path.join(ex, "_closed", "nav-superseded-20260105T000000", "a.ia.json"), '{"layers": []}', BASE)

    # backups: 5 in memory/backups, 5 groups in .pb-backups (two of them registry+spec pairs)
    for i in range(5):
        p = os.path.join(proj, "memory", "backups", "explore-x-%d" % i)
        write(os.path.join(p, "registry.json"), "{}" * 200, BASE + i * DAY)
        touch_tree(p, BASE + i * DAY)
    pb = os.path.join(proj, ".pb-backups")
    for i, stamp in enumerate(("T1", "T2")):
        t = BASE + i * DAY
        write(os.path.join(pb, "registry.12.%s.json" % stamp), "{}" * 300, t)
        write(os.path.join(pb, "spec.12.%s" % stamp, "components", "c.json"), "{}", t)
        touch_tree(os.path.join(pb, "spec.12.%s" % stamp), t)
    write(os.path.join(pb, "registry.12.T3.json"), "{}" * 300, BASE + 2 * DAY)
    write(os.path.join(pb, "decisions.T4.md"), "# log\n" * 100, BASE + 3 * DAY)
    write(os.path.join(pb, "pre-rollback.T5", "registry.json"), "{}", BASE + 4 * DAY)
    touch_tree(os.path.join(pb, "pre-rollback.T5"), BASE + 4 * DAY)

    # preview leftovers: a 1.3 MB log with a recognisable tail, screenshots
    lines = ["line %06d %s\n" % (i, "." * 40) for i in range(25000)]
    write(os.path.join(proj, ".preview", "server.log"), "".join(lines) + "LAST-LINE-MARKER\n")
    write(os.path.join(proj, ".preview", "shots", "a-1440x900.png"), "p" * 5000)
    write(os.path.join(proj, ".preview", "shots", "a-390x844.png"), "p" * 5000)
    return proj, outside


def open_state(proj):
    """The hash of everything that belongs to an open round."""
    ex = os.path.join(proj, "memory", "explore")
    parts = []
    for rel in ("alpha.json", "alpha.brief.md", "broken.json"):
        with open(os.path.join(ex, rel), "rb") as f:
            parts.append(hashlib.sha256(f.read()).hexdigest())
    for rel in (os.path.join("memory", "explore", "alpha"), os.path.join("memory", "explore", "broken"),
                os.path.join("render", "_candidates", "alpha"), os.path.join("render", "_candidates", "broken")):
        parts.append(tree_hash(os.path.join(proj, rel)))
    return parts


tmp = tempfile.mkdtemp(prefix="pb-clean-")
try:
    # ── 1 ────────────────────────────────────────────────────────────────────────
    print("1 · the names clean.py uses are the ones explore.py uses")
    sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
    import clean as C  # noqa: E402
    import explore as E  # noqa: E402
    check((C.EXPLORE_DIR, C.CANDIDATES_DIR, C.SERVER_FILE, C.SERVER_LOG) ==
          (E.EXPLORE_DIR, E.CANDIDATES_DIR, E.SERVER_FILE, E.SERVER_LOG),
          "EXPLORE_DIR / CANDIDATES_DIR / SERVER_FILE / SERVER_LOG match explore.py")
    check((C.LOG_MAX, C.LOG_KEEP) == (E.LOG_MAX, E.LOG_KEEP), "the log limits (1 MB, keep 256 KB) match explore.py's")

    # ── 2 ────────────────────────────────────────────────────────────────────────
    print("2 · a dry run changes nothing and lists every category")
    proj, outside = build(os.path.join(tmp, "t2"))
    before = tree_hash(proj)
    rc, out, err = run(os.path.join(proj, "registry.json"))
    check(rc == 0, "exit 0 (rc=%d)" % rc)
    check(tree_hash(proj) == before, "the project tree hashes the same afterwards")
    for label in ("open explore rounds", "closed explore rounds", "memory/backups/", ".pb-backups/",
                  ".preview/server.log", ".preview/shots/", "render/_candidates/", "preview server"):
        check(label in out, "the table has a row for %s" % label)
    check("Dry run" in out, "it says it was a dry run")
    rc, out, err = run(os.path.join(proj, "registry.json"), "--keep-backups", "2", "--keep-closed", "1")
    check(rc == 0 and tree_hash(proj) == before, "a keep flag without --apply is a preview — still nothing changed")
    check("would delete" in out, "…and says what it would delete")
    rc, out, err = run(os.path.join(proj, "registry.json"), "--json")
    doc = json.loads(out)
    f = doc["found"]
    check(len(f["open"]) == 2 and any(r["target"] == "alpha" and r["stale"] for r in f["open"]),
          "--json: 2 open rounds, the 5-day-old one STALE")
    check(f["closed"]["count"] == 4 and f["closed"]["bytes"] > 0 and f["closed"]["pinned"] == 1,
          "--json: 4 closed rounds with a size, 1 pinned IA")
    check(f["backups"]["memory/backups"]["count"] == 5 and f["backups"][".pb-backups"]["count"] == 5,
          "--json: 5 backups in each place (a registry backup and its spec snapshot count once)")
    check([o["target"] for o in f["candidates"]["orphans"]] == ["ghost", "ghost2"] and f["candidates"]["inUse"] == 2,
          "--json: 2 orphan candidate folders, 2 in use by open rounds")
    check(f["serverLog"]["trim"] and f["serverLog"]["bytes"] > 1024 * 1024, "--json: server.log over 1 MB, marked for trimming")
    check(f["shots"]["files"] == 2 and f["shots"]["bytes"] == 10000, "--json: 2 screenshots, 10000 bytes")
    check(f["server"]["running"] is False, "--json: no preview server (no record)")
    check(doc["apply"] is False and doc["removed"] == [] and doc["exit"] == 0, "--json: nothing removed on a dry run")

    # ── 3 ────────────────────────────────────────────────────────────────────────
    print("3 · bare --apply: the always-safe set only")
    open_before = open_state(proj)
    closed_before = tree_hash(os.path.join(proj, "memory", "explore", "_closed"))
    backups_before = (tree_hash(os.path.join(proj, "memory", "backups")), tree_hash(os.path.join(proj, ".pb-backups")))
    rc, out, err = run(os.path.join(proj, "registry.json"), "--apply")
    check(rc == 0, "exit 0 (rc=%d)" % rc)
    cand = os.path.join(proj, "render", "_candidates")
    check(names(cand) == ["alpha", "broken"], "orphan candidates removed, the open rounds' kept (%s)" % names(cand))
    log = os.path.join(proj, ".preview", "server.log")
    size = os.path.getsize(log)
    with open(log, encoding="utf-8") as fh:
        content = fh.read()
    check(size <= 256 * 1024, "server.log trimmed to <= 256 KB (%d bytes)" % size)
    check(content.endswith("LAST-LINE-MARKER\n") and content.startswith("line "), "…keeping the tail, from a line start")
    check(not os.path.exists(os.path.join(proj, ".preview", "shots")), ".preview/shots/ deleted")
    check(tree_hash(os.path.join(proj, "memory", "explore", "_closed")) == closed_before, "every closed round untouched")
    check((tree_hash(os.path.join(proj, "memory", "backups")), tree_hash(os.path.join(proj, ".pb-backups"))) == backups_before,
          "every backup untouched")
    check(open_state(proj) == open_before, "the open rounds untouched")
    check("freed" in out and "removed" in out, "it prints what it removed and the bytes freed")
    rc2, out2, _ = run(os.path.join(proj, "registry.json"), "--apply")
    check(rc2 == 0 and "freed 0 B" in out2, "a second run has nothing left to do")

    # ── 4 ────────────────────────────────────────────────────────────────────────
    print("4 · --apply --keep-backups 2: the newest 2 in EACH place")
    rc, out, err = run(os.path.join(proj, "registry.json"), "--apply", "--keep-backups", "2")
    check(rc == 0, "exit 0 (rc=%d)" % rc)
    check(names(os.path.join(proj, "memory", "backups")) == ["explore-x-3", "explore-x-4"],
          "memory/backups keeps exactly the newest 2 (%s)" % names(os.path.join(proj, "memory", "backups")))
    check(names(os.path.join(proj, ".pb-backups")) == ["decisions.T4.md", "pre-rollback.T5"],
          ".pb-backups keeps exactly the newest 2 — pairs deleted whole (%s)" % names(os.path.join(proj, ".pb-backups")))
    check(tree_hash(os.path.join(proj, "memory", "explore", "_closed")) == closed_before, "…and no closed round was touched")
    check("in each place" in out.lower() or "AND the newest 2 in .pb-backups" in out,
          "the output states that N applies to each place")

    # ── 5 ────────────────────────────────────────────────────────────────────────
    print("5 · --apply --keep-closed 1: the newest round, whole")
    closed = os.path.join(proj, "memory", "explore", "_closed")
    rc, out, err = run(os.path.join(proj, "registry.json"), "--apply", "--keep-closed", "1")
    check(rc == 0, "exit 0 (rc=%d)" % rc)
    left = names(closed)
    check(all(n.startswith("new-20260301T000000") for n in left if n.startswith(("new", "old", "mid"))) and
          {"new-20260301T000000", "new-20260301T000000.json", "new-20260301T000000.brief.md"} <= set(left),
          "the newest round keeps its manifest, brief and folder")
    check(not any(n.startswith(("old-", "mid-")) for n in left), "the older rounds are gone together — no orphan brief or folder (%s)" % left)
    check({"nav", "nav-20260105T000000.json", "nav-superseded-20260105T000000"} <= set(left),
          "the promoted IA round, its stable folder and the superseded folder stay")
    check(open(os.path.join(closed, "nav", "a.ia.json")).read() == '{"layers": []}', "/pb:plan's structure file is intact")
    check(open_state(proj) == open_before, "the open rounds are still untouched")

    # ── 6 ────────────────────────────────────────────────────────────────────────
    print("6 · an open round survives every flag combination")
    proj6, _o = build(os.path.join(tmp, "t6"))
    open6 = open_state(proj6)
    reg6 = os.path.join(proj6, "registry.json")
    for flags in (["--apply"], ["--apply", "--keep-closed", "1"], ["--apply", "--keep-backups", "1"],
                  ["--apply", "--keep-closed", "1", "--keep-backups", "1"], ["--keep-closed", "1", "--keep-backups", "1"]):
        rc, out, err = run(reg6, *flags)
        check(rc == 0 and open_state(proj6) == open6, "open rounds intact after %s" % " ".join(flags))

    # ── 7 ────────────────────────────────────────────────────────────────────────
    print("7 · a keep flag of 0 (or worse) is refused")
    proj7, _o = build(os.path.join(tmp, "t7"))
    h7 = tree_hash(proj7)
    reg7 = os.path.join(proj7, "registry.json")
    for flags in (["--keep-backups", "0"], ["--keep-closed", "0"], ["--apply", "--keep-backups", "0"],
                  ["--apply", "--keep-closed", "0"], ["--apply", "--keep-closed", "-3"], ["--apply", "--keep-backups", "many"]):
        rc, out, err = run(reg7, *flags)
        check(rc == 2 and tree_hash(proj7) == h7, "%s → exit 2, nothing deleted (rc=%d)" % (" ".join(flags), rc))
    check("at least 1" in run(reg7, "--apply", "--keep-backups", "0")[2], "the message says why")

    # ── 8 ────────────────────────────────────────────────────────────────────────
    print("8 · a symlink out of the project is never followed")
    proj8, outside8 = build(os.path.join(tmp, "t8"))
    out_hash = tree_hash(outside8)
    outside_log = os.path.join(os.path.dirname(outside8), "outside-big.log")
    write(outside_log, "z" * (1024 * 1024 + 4096))
    # an OLD backup that is a link to a folder outside; a candidate folder that is a link; a link INSIDE a
    # candidate folder; shots as a link; server.log as a link to a big file outside; a closed-round folder link
    os.symlink(outside8, os.path.join(proj8, "memory", "backups", "aaa-evil"))
    os.utime(os.path.join(proj8, "memory", "backups", "aaa-evil"), (BASE - DAY, BASE - DAY), follow_symlinks=False)
    os.symlink(outside8, os.path.join(proj8, "render", "_candidates", "linked"))
    os.symlink(outside8, os.path.join(proj8, "render", "_candidates", "ghost", "inner-link"))
    shutil.rmtree(os.path.join(proj8, ".preview", "shots"))
    os.symlink(outside8, os.path.join(proj8, ".preview", "shots"))
    os.remove(os.path.join(proj8, ".preview", "server.log"))
    os.symlink(outside_log, os.path.join(proj8, ".preview", "server.log"))
    closed8 = os.path.join(proj8, "memory", "explore", "_closed")
    shutil.rmtree(os.path.join(closed8, "old-20260101T000000"))
    os.symlink(outside8, os.path.join(closed8, "old-20260101T000000"))
    # a link that leads INSIDE the project: removed as a link, its target survives
    os.symlink(os.path.join(proj8, "registry.json"), os.path.join(proj8, "memory", "backups", "aab-inner"))
    os.utime(os.path.join(proj8, "memory", "backups", "aab-inner"), (BASE - DAY, BASE - DAY), follow_symlinks=False)
    reg_hash = hashlib.sha256(open(os.path.join(proj8, "registry.json"), "rb").read()).hexdigest()
    outside_log_before = open(outside_log, "rb").read()

    rc, out, err = run(os.path.join(proj8, "registry.json"), "--apply", "--keep-backups", "1", "--keep-closed", "1")
    check(rc == 1, "exit 1 — something was refused (rc=%d)" % rc)
    check(tree_hash(outside8) == out_hash and os.path.exists(os.path.join(outside8, "precious.txt")),
          "the outside folder and everything in it survive")
    check(open(outside_log, "rb").read() == outside_log_before, "the outside log was not trimmed")
    check("REFUSED" in out and "outside the project" in out, "the refusal is reported")
    check(os.path.islink(os.path.join(proj8, "memory", "backups", "aaa-evil")), "the escaping backup link was left alone")
    check(os.path.islink(os.path.join(proj8, "render", "_candidates", "linked")), "the escaping candidate link was left alone")
    check(not os.path.exists(os.path.join(proj8, "render", "_candidates", "ghost")),
          "a real candidate folder holding a link out was deleted — without following the link")
    check(os.path.islink(os.path.join(proj8, ".preview", "shots")), "the shots link was left alone")
    check(not os.path.lexists(os.path.join(proj8, "memory", "backups", "aab-inner")), "a link that stays inside was removed as a link")
    check(hashlib.sha256(open(os.path.join(proj8, "registry.json"), "rb").read()).hexdigest() == reg_hash,
          "…and the file it pointed at is intact")
    check(os.path.islink(os.path.join(closed8, "old-20260101T000000"))
          and os.path.exists(os.path.join(closed8, "old-20260101T000000.json"))
          and os.path.exists(os.path.join(closed8, "old-20260101T000000.brief.md")),
          "a closed round whose folder is a link out is kept whole — manifest, brief and link")
    n_trim, why = C._trim_log(os.path.join(proj8, ".preview", "server.log"), os.path.realpath(proj8))
    check(n_trim == 0 and why and open(outside_log, "rb").read() == outside_log_before,
          "trimming a log that is a link to a big file outside is refused by its own check too")
    rc, out, err = run(os.path.join(proj8, "registry.json"), "--apply", "--json")
    check(rc == 1 and json.loads(out)["refused"], "--json lists the refusals")
    check(tree_hash(outside8) == out_hash, "a second run still leaves the outside folder alone")

    # ── 9 ────────────────────────────────────────────────────────────────────────
    print("9 · finding the registry")
    proj9, _o = build(os.path.join(tmp, "t9"))
    rc, out, err = run(cwd=proj9)
    check(rc == 0 and "closed explore rounds" in out, "no argument: ./registry.json in the cwd")
    rc, out, err = run(proj9)
    check(rc == 0 and "closed explore rounds" in out, "a project folder is accepted")
    adopt = os.path.join(tmp, "adopt")
    os.makedirs(adopt)
    shutil.copytree(proj9, os.path.join(adopt, ".prototype"))
    write(os.path.join(adopt, "unrelated.txt"), "not ours")
    rc, out, err = run(cwd=adopt)
    check(rc == 0 and ".prototype" in out and "closed explore rounds" in out, "adopt-in-place: ./.prototype/registry.json from the repo root")
    rc, out, err = run("--apply", "--keep-backups", "1", cwd=adopt)
    check(rc == 0 and len(os.listdir(os.path.join(adopt, ".prototype", ".pb-backups"))) == 1 and
          open(os.path.join(adopt, "unrelated.txt")).read() == "not ours",
          "…and --apply works inside .prototype/ without touching the repo around it")
    empty = os.path.join(tmp, "empty")
    os.makedirs(empty)
    rc, out, err = run(cwd=empty)
    check(rc == 2 and "no registry.json" in err, "no registry: exit 2 with a message (rc=%d)" % rc)
    rc, out, err = run(os.path.join(empty, "nope.json"))
    check(rc == 2 and "Traceback" not in err, "a missing registry path is exit 2, no traceback")

    # a stale server record is "not running" and nothing is signalled
    write(os.path.join(proj9, ".preview", "server.json"), json.dumps({"url": "http://127.0.0.1:9/", "pid": 1}))
    rc, out, err = run(os.path.join(proj9, "registry.json"), "--json")
    check(rc == 0 and json.loads(out)["found"]["server"]["running"] is False, "a stale server record reads as not running")
    write(os.path.join(proj9, ".preview", "server.json"), json.dumps({"url": "http://example.invalid/", "pid": 1}))
    rc, out, err = run(os.path.join(proj9, "registry.json"), "--json")
    check(rc == 0 and json.loads(out)["found"]["server"]["running"] is False, "a non-loopback record is never probed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
if fails:
    print("✗ %d clean_tool failure(s):" % len(fails))
    for m in fails:
        print("  " + m)
    sys.exit(1)
print("✓ clean_tool — the pile is shown, and pruned only on request")
