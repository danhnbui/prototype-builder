#!/usr/bin/env python3
"""
tool_cli.py — the registry-taking tools accept the registry BOTH positionally and via --registry.

The command docs (pull-ds.md, check-drift.md §5, init.md 6c) invoke clone_ds.py / resolve_frame.py
with the registry as a positional arg; other tools (render_react.py, ds_serve.py) already
did. This guards that uniform CLI so a doc-vs-tool mismatch can't silently reappear.

It also guards the write tools the build loop calls from its docs (round 3): the command line
build.md §3a gives for spec_measure.py uses only flags the tool has, a registry that is not there is
a one-line message from slice.py / spec_measure.py / the migration runner and never a traceback, and
a tool that takes the registry lock leaves no `.lock` file behind for a read.

Usage:  python3 tests/tool_cli.py
Exit:   0 = clean · 1 = a regression
"""
import json
import os
import stat
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
DS_EXPORT = os.path.join(ROOT, "fixtures", "ds-export.json")
FRAME = os.path.join(ROOT, "fixtures", "frame-export.json")
TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def run(*args, cwd):
    return subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True).returncode


with tempfile.TemporaryDirectory() as d:
    reg = os.path.join(d, "registry.json")
    json.dump(json.load(open(TEMPLATE)), open(reg, "w"))
    clone = os.path.join(TOOLS, "clone_ds.py")
    resolve = os.path.join(TOOLS, "resolve_frame.py")

    print("clone_ds.py — positional and --registry both accepted")
    check(run(clone, "--from", DS_EXPORT, "registry.json", cwd=d) == 0, "clone_ds --from … registry.json (positional, the doc form)")
    check(run(clone, "--drift", DS_EXPORT, "--registry", reg, cwd=d) == 0, "clone_ds --drift … --registry PATH (flag form)")

    print("resolve_frame.py — positional and --registry both accepted")
    check(run(resolve, "--from", FRAME, "registry.json", cwd=d) == 0, "resolve_frame --from … registry.json (positional, the doc form)")
    check(run(resolve, "--from", FRAME, "--registry", reg, cwd=d) == 0, "resolve_frame --from … --registry PATH (flag form)")

print("the write tools — doc form, missing registry, no stray lock")
import re  # noqa: E402

build_md = open(os.path.join(ROOT, "pb", "commands", "build.md"), encoding="utf-8").read()
m = re.search(r"spec_measure\.py\"?\s+((?:--[\w-]+(?:\s+(?!--)\S+)?\s*)+)", build_md)
doc_flags = sorted(set(re.findall(r"--[\w-]+", m.group(1)))) if m else []
helptext = subprocess.run([sys.executable, os.path.join(TOOLS, "spec_measure.py"), "--help"], capture_output=True, text=True).stdout
check(doc_flags and all(f in helptext for f in doc_flags),
      "build.md §3a's spec_measure.py command uses only flags the tool has (%s)" % ", ".join(doc_flags))
with tempfile.TemporaryDirectory() as d:
    gone = os.path.join(d, "nope.json")
    for label, argv, bad_rc in [
        ("slice.py get", [os.path.join(TOOLS, "slice.py"), "get", "meta", "name", "--registry", gone], None),
        ("slice.py set", [os.path.join(TOOLS, "slice.py"), "set", "meta", "name", "--registry", gone], None),
        ("spec_measure.py", [os.path.join(TOOLS, "spec_measure.py"), "--registry", gone], 4),
        ("migrate_runner.py", [os.path.join(ROOT, "pb", "migrations", "migrate_runner.py"), "--registry", gone, "--apply"], 1),
        ("migrate_runner.py --rollback", [os.path.join(ROOT, "pb", "migrations", "migrate_runner.py"), "--registry", gone, "--rollback"], 1),
        ("clone_ds.py", [os.path.join(TOOLS, "clone_ds.py"), "--from", DS_EXPORT, "--registry", gone], 2),
        ("resolve_frame.py", [os.path.join(TOOLS, "resolve_frame.py"), "--from", FRAME, "--registry", gone], None),
        ("lint_registry.py --sync-elements", [os.path.join(TOOLS, "lint_registry.py"), "--sync-elements", gone], 2),
    ]:
        r = subprocess.run([sys.executable] + argv, input='"x"', capture_output=True, text=True)
        text = r.stdout + r.stderr
        check(r.returncode != 0 and "Traceback" not in text and text.strip() and (bad_rc is None or r.returncode == bad_rc),
              "%s on a missing registry: a message, exit %d, no traceback" % (label, r.returncode))
    check(os.listdir(d) == [], "…and none of them left a file (a lock, a backup, a temp file) behind")
    reg = os.path.join(d, "registry.json")
    json.dump(json.load(open(TEMPLATE)), open(reg, "w"))
    subprocess.run([sys.executable, os.path.join(TOOLS, "slice.py"), "get", "meta", "name", "--registry", reg], capture_output=True)
    subprocess.run([sys.executable, os.path.join(TOOLS, "slice.py"), "list", "meta", "--registry", reg], capture_output=True)
    check(sorted(os.listdir(d)) == ["registry.json"], "a read (get / list) takes no lock and leaves no .lock file")
    subprocess.run([sys.executable, os.path.join(TOOLS, "lint_registry.py"), reg], capture_output=True)
    subprocess.run([sys.executable, os.path.join(TOOLS, "lint_registry.py"), "--report", reg], capture_output=True)
    subprocess.run([sys.executable, os.path.join(TOOLS, "logic_extract.py"), d, "--contracts", "--dry-run"], capture_output=True)
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "logic_extract.py"), d, "--contracts"], capture_output=True, text=True)
    check(r.returncode == 0 and sorted(os.listdir(d)) == ["registry.json"],
          "lint (plain, --report) and logic_extract (--dry-run, or --contracts with nothing to point) take no lock and leave none behind")

print("test_run.py — lastResult verdicts are saved under the registry lock, on a fresh read, never during the run (L3)")
import copy  # noqa: E402
import importlib  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

sys.path.insert(0, TOOLS)
TR = importlib.import_module("test_run")          # playwright is imported lazily, so this needs no browser
pbslice = importlib.import_module("slice")        # `import slice` would shadow the builtin


def scen(text, expect="a"):
    return {"text": text, "test": {"start": "home", "steps": [], "expect": [{"screen": expect}]}}


with tempfile.TemporaryDirectory() as d:
    reg = {"meta": {"name": "Dự án Ví"}, "tokens": {}, "components": [], "screens": [],
           "flow": {"populated": True, "stories": [
               {"id": "s1", "title": "Story one", "scenarios": [
                   scen("same text"), scen("same text", "b"), scen("will be edited"), scen("will be removed"),
                   {"text": "manual, no test block"}]},
               {"title": "Story two", "scenarios": [scen("other")]}]}}
    path = os.path.join(d, "registry.json")
    pbslice._write(path, reg)
    os.chmod(path, 0o640)
    keys = TR._scenario_keys(reg)
    check(len(keys) == 5 and len({k for k, _s, _t in keys}) == 5,
          "every runnable scenario gets its own key, duplicates of one text included (%d)" % len(keys))
    verdicts = {k: (copy.deepcopy(t), {"status": "pass", "ranAt": "2026-10-03T00:00:00Z", "detail": "ran"}) for k, _s, t in keys}
    k_same2, k_edit, k_gone = keys[1][0], keys[2][0], keys[3][0]

    os.environ["PB_LOCK_TIMEOUT"] = "0.4"
    try:
        with pbslice.registry_lock(path, "a test holding the lock"):
            held = open(path, "rb").read()
            try:
                TR._save_verdicts(path, verdicts)
                check(False, "a held registry lock refuses the verdict write")
            except pbslice.RegistryLocked as e:
                check("being written" in str(e) and "a test holding the lock" in str(e),
                      "a held registry lock refuses the verdict write, naming the holder")
            check(open(path, "rb").read() == held, "…and registry.json is byte-identical")
    finally:
        os.environ.pop("PB_LOCK_TIMEOUT", None)

    os.environ["PB_LOCK_TIMEOUT"] = "30"
    outcome = {}

    def save():
        try:
            outcome["r"] = TR._save_verdicts(path, verdicts)
        except BaseException as e:       # noqa: BLE001 — reported below
            outcome["e"] = e
    worker = threading.Thread(target=save)
    try:
        with pbslice.registry_lock(path, "a test holding the lock again"):
            worker.start()
            time.sleep(1.0)
            waiting = worker.is_alive()
            mid = json.load(open(path, encoding="utf-8"))
            mid["meta"]["editedWhileLocked"] = "yes"                                  # someone else's edit
            mid["flow"]["stories"].insert(0, {"id": "new", "title": "A story added meanwhile", "scenarios": [scen("fresh")]})
            st1 = next(s for s in mid["flow"]["stories"] if s.get("id") == "s1")
            st1["scenarios"][2]["test"]["expect"] = [{"screen": "changed"}]           # a scenario's test edited
            del st1["scenarios"][3]                                                    # a scenario removed
            st1["scenarios"].append(scen("appended meanwhile"))
            pbslice._write(path, mid)
            ino = os.stat(path).st_ino   # after it: ext4 hands a freed inode straight back out
        worker.join(30)
    finally:
        os.environ.pop("PB_LOCK_TIMEOUT", None)
    done = json.load(open(path, encoding="utf-8"))
    check(waiting, "the verdict write WAITS for a held lock (an unlocked one would already have finished)")
    saved, skipped = outcome.get("r", (None, None))
    check("e" not in outcome and saved == 3 and sorted(skipped) == sorted([k_edit, k_gone]),
          "…then saves the 3 verdicts that still apply and skips the two whose scenario changed or went (%s)" % str(outcome.get("e") or (saved, skipped)))
    st1 = next(s for s in done["flow"]["stories"] if s.get("id") == "s1")
    texts = [(sc["text"], (sc.get("lastResult") or {}).get("status")) for sc in st1["scenarios"]]
    check(texts == [("same text", "pass"), ("same text", "pass"), ("will be edited", None),
                    ("manual, no test block", None), ("appended meanwhile", None)],
          "…each verdict lands on ITS scenario (the second 'same text' too); the edited one carries none (%s)" % texts)
    check(done["meta"].get("editedWhileLocked") == "yes" and done["flow"]["stories"][0].get("id") == "new"
          and next(s for s in done["flow"]["stories"] if s.get("title") == "Story two")["scenarios"][0]["lastResult"]["status"] == "pass",
          "…the edits saved meanwhile (a meta key, a new first story, the appended scenario) are not overwritten")
    check(st1["scenarios"][2]["test"]["expect"] == [{"screen": "changed"}], "…and the edited test block is the edited one")
    raw = open(path, "rb").read().decode("utf-8")
    check(os.stat(path).st_ino != ino and stat.S_IMODE(os.stat(path).st_mode) == 0o640
          and "Dự án Ví" in raw and raw.endswith("}\n") and [f for f in os.listdir(d) if f.endswith(".tmp")] == [],
          "the write is atomic (a new inode, mode kept, no temp file) and in the registry's own format")
    before = open(path, "rb").read()
    check(TR._save_verdicts(path, {k_gone: (verdicts[k_gone][0], verdicts[k_gone][1])}) == (0, [k_gone])
          and open(path, "rb").read() == before,
          "when no verdict applies nothing is written")

print()
if fails:
    print(f"✗ {len(fails)} tool-CLI check(s) failed")
    sys.exit(1)
print("✓ tool-CLI uniform")
