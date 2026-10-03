#!/usr/bin/env python3
"""
r3_figma_entry.py — the R3 "Figma-frame entry" acceptance, fixture-driven (no real Figma / MCP):

  1. resolve_frame.py maps a frame-export's layers to DS components that already exist and emits a
     registry screen patch: mapped layers → elements with `orgId`; unmapped layers → labeled
     placeholders + a gaps.md entry. Sets meta.entry = "figma".
  2. DS fidelity at entry: every emitted `orgId` is a KNOWN component id — nothing is invented. Every
     unmapped layer is accounted for (placeholder element AND a gaps.md line), never silently dropped.
  3. Migration 0005 adds meta.entry (schema 6→7), is up→down reversible, and the template tracks CURRENT_SCHEMA.

Usage:  python3 tests/r3_figma_entry.py
Exit:   0 = clean · 1 = a regression
"""
import importlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOLVE = os.path.join(ROOT, "pb", "tools", "resolve_frame.py")
FRAME = os.path.join(ROOT, "fixtures", "frame-export.json")
TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")
KNOWN = {"button", "text-input"}  # the DS components present in the test project
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem, os.path.join(ROOT, "pb", "migrations", stem + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


with tempfile.TemporaryDirectory() as d:
    reg = os.path.join(d, "registry.json")
    data = json.load(open(TEMPLATE))
    data["meta"]["name"] = "FrameTest"
    data["components"] = [{"id": "button"}, {"id": "text-input"}]  # the known DS components
    json.dump(data, open(reg, "w"))
    shutil.copy(FRAME, os.path.join(d, "frame.json"))

    print("1 · resolve maps layers → screen patch")
    r = subprocess.run([sys.executable, RESOLVE, "--from", os.path.join(d, "frame.json"), "--registry", reg],
                       capture_output=True, text=True)
    check(r.returncode == 0, f"resolve_frame exits 0 ({r.stderr.strip()[:60]})")
    out = json.load(open(reg))
    screens = out.get("screens", [])
    check(len(screens) == 1 and screens[0]["id"] == "checkout", "one screen 'checkout' emitted")
    check(out["meta"].get("entry") == "figma", "meta.entry set to figma")
    els = screens[0]["elements"]
    mapped = [e for e in els if e.get("orgId")]
    placeholders = [e for e in els if e.get("placeholder")]
    check(len(els) == 4 and len(mapped) == 2 and len(placeholders) == 2,
          f"4 layers → 2 mapped + 2 placeholders (got {len(mapped)}/{len(placeholders)})")
    check(screens[0].get("figmaFrameId") == "10:5", "screen keeps the Figma frame id")

    print("2 · DS fidelity — nothing invented, nothing dropped")
    orgids = {e["orgId"] for e in mapped}
    check(orgids <= KNOWN, f"every orgId is a known DS component (got {orgids})")
    check(all("orgId" not in e for e in placeholders), "placeholders carry NO orgId (not invented)")
    gaps_path = os.path.join(d, "gaps.md")
    check(os.path.isfile(gaps_path), "gaps.md written")
    gaps = open(gaps_path).read() if os.path.isfile(gaps_path) else ""
    check("Promo Banner" in gaps and "Live Chat Bubble" in gaps, "both unmapped layers logged to gaps.md")
    check(gaps.count("\n- ") == 2, "exactly the 2 unmapped layers are logged (none extra, none missing)")

print("2b · resolve_frame is a locked, atomic read-modify-write (L3)")
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
pbslice = importlib.import_module("slice")        # `import slice` would shadow the builtin
with tempfile.TemporaryDirectory() as d:
    reg = os.path.join(d, "registry.json")
    data = json.load(open(TEMPLATE))
    data["meta"]["name"] = "Dự án Ví — 日本語"
    data["components"] = [{"id": "button"}, {"id": "text-input"}]
    json.dump(data, open(reg, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    os.chmod(reg, 0o640)
    frame = os.path.join(d, "frame.json")
    shutil.copy(FRAME, frame)
    cmd = [sys.executable, RESOLVE, "--from", frame, "--registry", reg]
    with pbslice.registry_lock(reg, "a test holding the lock"):
        held = open(reg, "rb").read()
        r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, PB_LOCK_TIMEOUT="0.4"))
        check(r.returncode == 2 and "being written" in r.stderr and "a test holding the lock" in r.stderr
              and "Traceback" not in r.stderr, "a held registry lock refuses resolve_frame, naming the holder (exit %d)" % r.returncode)
        check(open(reg, "rb").read() == held and not os.path.exists(os.path.join(d, "gaps.md")),
              "…registry.json is byte-identical and no gaps.md was written")
    waiter = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              env=dict(os.environ, PB_LOCK_TIMEOUT="30"))
    with pbslice.registry_lock(reg, "a test holding the lock again"):
        time.sleep(1.5)
        waiting = waiter.poll() is None
        mid = json.load(open(reg, encoding="utf-8"))
        mid["meta"]["editedWhileLocked"] = "yes"
        pbslice._write(reg, mid)
        ino = os.stat(reg).st_ino
    out, err = waiter.communicate(timeout=60)
    after = json.load(open(reg, encoding="utf-8"))
    check(waiting, "a writer that finds the lock held WAITS for it (an unlocked one would already have finished)")
    check(waiter.returncode == 0 and after["meta"].get("editedWhileLocked") == "yes",
          "…then reads the registry afresh: the edit saved meanwhile is not overwritten (%s)" % err.strip()[:80])
    check(after["meta"].get("entry") == "figma" and [s["id"] for s in after["screens"]] == ["checkout"],
          "…and its own change (the screen, meta.entry) is there too")
    check(os.stat(reg).st_ino != ino and stat.S_IMODE(os.stat(reg).st_mode) == 0o640
          and [f for f in os.listdir(d) if f.endswith(".tmp")] == [],
          "the write replaced the file (a new inode), kept its mode, and left no temp file")
    raw = open(reg, "rb").read().decode("utf-8")
    check("Dự án Ví — 日本語" in raw and "\\u" not in raw and raw.endswith("}\n"),
          "it writes the registry's own format: non-ASCII kept as typed (not \\uXXXX-escaped), one trailing newline")
    check(os.path.isfile(os.path.join(d, "gaps.md")) and open(os.path.join(d, "gaps.md"), encoding="utf-8").read().count("\n- ") == 2,
          "gaps.md is still written")

print("3 · migration 0005 + schema")
man = _load("manifest")
m5 = _load("0005_entry")
v6 = {"meta": {"name": "X", "schemaVersion": 6}, "tokens": {}, "components": [], "screens": []}
up = m5.up(v6)
check(up["meta"].get("entry") == "prd" and up["meta"]["schemaVersion"] == 7, "up adds entry=prd, stamps 7")
check(m5.down(up) == v6, "down is reversible")
tmpl = json.load(open(TEMPLATE))
check(tmpl["meta"]["schemaVersion"] == man.CURRENT_SCHEMA, "template schemaVersion == CURRENT_SCHEMA")
check(tmpl["meta"].get("entry") == "prd", "template carries entry=prd")

print()
if fails:
    print(f"✗ {len(fails)} R3 figma-entry check(s) failed")
    sys.exit(1)
print("✓ R3 figma-entry clean")
