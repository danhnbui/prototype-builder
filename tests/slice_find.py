#!/usr/bin/env python3
"""
slice_find.py — guards the read side of pb/tools/slice.py that keeps agents from parsing registry.json
with inline scripts:

  1. find  — case-insensitive search over ids, names and every string value, across kinds or one (--kind);
             one line per hit `<kind> <id> <field>: <snippet ≤ 80>`, deterministic order, --limit with a final
             `… N more hits (raise --limit)` line, `0 hits` (exit 0) when nothing matches, --json shape.
  2. get   — output capped at 8,000 chars with a final `… truncated (N chars)` line; --full lifts the cap;
             a small slice is untouched.
  3. list  — `--fields a,b` prints id plus those fields, one compact line each.

Hermetic: the registry is built in a temp directory here.

Usage:  python3 tests/slice_find.py
Exit:   0 = clean · 1 = a regression
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLICE = os.path.join(ROOT, "pb", "tools", "slice.py")
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def run(*args):
    return subprocess.run([sys.executable, SLICE, *args], capture_output=True, text=True)


def registry():
    long_note = "Padding " * 40 + "the needle sits deep inside a long note " + "and keeps going " * 20
    return {
        "meta": {"name": "Acme Demo", "objective": "Help people find the Needle quickly"},
        "tokens": {"color": {"brand": {"$value": "#ff6600", "$type": "color"}}},
        "components": [
            {"id": "button", "name": "Button", "level": "atom", "purpose": "A needle-free action"},
            {"id": "card", "name": "Card", "level": "molecule", "logicNotes": long_note,
             "parts": [{"id": "title", "label": "Card title"}]},
            {"id": "big", "name": "Big", "level": "organism", "logicNotes": "x" * 12000},
        ],
        "screens": [
            {"id": "home", "name": "Home", "elements": [{"id": "cta", "label": "Press the BUTTON"}]},
            {"id": "settings", "name": "Settings"},
        ],
        "flow": {"stories": [{"id": "s1", "title": "Find a needle", "scenarios": [{"id": "a", "name": "happy"}]},
                             {"title": "An id-less story about buttons"}]},
        "erd": {"table": [{"entity": "User", "field": "email"}]},
        "content": {"terms": [{"id": "t1", "term": "Order", "means": "a parcel request"}], "strings": []},
        "ia": {"jobs": [{"id": "j1", "title": "Track a parcel"}],
               "rules": [{"id": "r1", "title": "Button order", "status": "approved"},
                         {"id": "r2", "title": "Empty state", "status": "draft"}]},
    }


with tempfile.TemporaryDirectory() as d:
    reg = os.path.join(d, "registry.json")
    with open(reg, "w", encoding="utf-8") as f:
        json.dump(registry(), f, indent=2, ensure_ascii=False)
        f.write("\n")
    R = ["--registry", reg]
    before = open(reg, "rb").read()

    print("find — hits across kinds")
    r = run("find", "button", *R)
    lines = r.stdout.splitlines()
    check(r.returncode == 0, "find exits 0")
    check("components button id: button" in lines, "an id match is reported as `<kind> <id> id: <value>`")
    check("components button name: Button" in lines and not any(" purpose:" in l for l in lines),
          "a name match is a hit on its field")
    check(any(l.startswith("screens home elements.cta.label: Press the BUTTON") for l in lines),
          "case-insensitive; a nested part stays a field of its screen")
    check(any(l.startswith("ia rules.r1 title: Button order") for l in lines),
          "a dict kind reports the owning element's path (`rules.r1`) and the field")
    check(any(l.startswith("flow stories.1 title: An id-less story about buttons") for l in lines),
          "an element without an id is reached by position")
    kinds = [l.split(" ", 1)[0] for l in lines]
    check(kinds == sorted(kinds, key=lambda k: ["components", "screens", "tokens", "meta", "flow", "erd", "content", "ia", "research"].index(k)),
          "hits come in kind order")
    check(run("find", "button", *R).stdout == r.stdout, "the same query prints the same output (deterministic)")
    check(all(len(l.split(": ", 1)[1]) <= 80 for l in lines), "every snippet is at most 80 chars")
    t = run("find", "brand", "--kind", "tokens", *R).stdout
    check("tokens color.brand $name: color.brand" in t, "a token is found by its key path")

    print("find — --kind")
    r = run("find", "button", "--kind", "ia", *R)
    check(r.stdout.splitlines() == ["ia rules.r1 title: Button order"], "--kind narrows to one kind")
    check(run("find", "button", "--kind", "nope", *R).returncode != 0, "an unknown --kind is refused")

    print("find — snippet")
    r = run("find", "needle", "--kind", "components", *R)
    deep = [l for l in r.stdout.splitlines() if l.startswith("components card logicNotes:")]
    check(len(deep) == 1, "a hit deep in a long string is found")
    snip = deep[0].split(": ", 1)[1] if deep else ""
    check(0 < len(snip) <= 80 and "needle" in snip.lower() and snip.startswith("…") and snip.endswith("…"),
          "the snippet is a window around the match with ellipses on the cut sides")
    check(not any("\n" in l for l in r.stdout.splitlines()) and "\t" not in r.stdout, "whitespace is collapsed to one line")

    print("find — --limit")
    r = run("find", "e", "--limit", "3", *R)
    lines = r.stdout.splitlines()
    full = run("find", "e", "--limit", "0", *R).stdout.splitlines()
    n = len(full)
    check(n > 3 and len(lines) == 4, "--limit 3 prints 3 hits and a trailer")
    check(lines[-1] == f"… {n - 3} more hits (raise --limit)", "the last line counts the hits left out")
    check(lines[:3] == full[:3] and not any(l.startswith("…") for l in full), "--limit 0 prints every hit, no trailer")
    check(not any(l.startswith("…") for l in run("find", "button", "--limit", "50", *R).stdout.splitlines()),
          "no trailer when nothing was cut")

    print("find — no hit")
    r = run("find", "zzzqqq", *R)
    check(r.returncode == 0 and r.stdout.strip() == "0 hits", "no hit prints `0 hits` and exits 0")
    r = run("find", "zzzqqq", "--json", *R)
    check(r.returncode == 0 and json.loads(r.stdout) == [], "--json with no hit is an empty list")

    print("find — --json")
    r = run("find", "button", "--json", *R)
    data = json.loads(r.stdout)
    check(isinstance(data, list) and data and all(set(h) == {"kind", "id", "path", "snippet"} for h in data),
          "--json is a list of {kind,id,path,snippet}")
    check({"kind": "ia", "id": "rules.r1", "path": "rules.r1.title", "snippet": "Button order"} in data,
          "a dict-kind hit carries the element path and the full path to the string")
    check({"kind": "components", "id": "button", "path": "button.name", "snippet": "Button"} in data,
          "a list-kind hit carries the entry id and `<id>.<field>`")
    r = run("find", "e", "--json", "--limit", "2", *R)
    check(len(json.loads(r.stdout)) == 2 and "more hits" in r.stderr, "--json honours --limit and says so on stderr")

    print("get — output cap")
    r = run("get", "components", "button", *R)
    check(r.returncode == 0 and json.loads(r.stdout)["id"] == "button", "a small slice is printed whole, valid JSON")
    r = run("get", "components", "big", *R)
    out = r.stdout
    last = out.rstrip("\n").splitlines()[-1]
    total = len(json.dumps(json.loads(run("get", "components", "big", *R, "--full").stdout), indent=2, ensure_ascii=False))
    check(r.returncode == 0 and last == f"… truncated ({total} chars). Use --fields a,b or --full.",
          "an oversize slice ends with the `… truncated (N chars)` line")
    check(out.startswith('{\n  "id": "big"') and len(out) < 8200, "the first 8,000 chars are printed, then the notice")
    r = run("get", "components", "big", *R, "--full")
    check(len(json.loads(r.stdout)["logicNotes"]) == 12000, "--full prints everything and parses as JSON")
    r = run("get", "components", "big", *R, "--fields", "id,name")
    check(json.loads(r.stdout) == {"id": "big", "name": "Big"}, "--fields keeps the output under the cap")
    r = run("get", "components", "big", *R, "--no-prose")
    check(r.returncode == 0 and "truncated" not in r.stdout and "logicNotes" not in json.loads(r.stdout),
          "--no-prose brings an oversize slice under the cap")

    print("list — --fields")
    r = run("list", "components", "--fields", "name,level", *R)
    check(r.stdout.splitlines() == ["button  name=Button  level=atom", "card  name=Card  level=molecule",
                                    "big  name=Big  level=organism"], "id plus the named fields, one line each")
    r = run("list", "components", "--fields", "name,purpose", *R)
    check(r.stdout.splitlines()[0] == "button  name=Button  purpose=A needle-free action"
          and r.stdout.splitlines()[1] == "card  name=Card  purpose=-", "a missing field prints `-`")
    r = run("list", "ia", "rules", "--fields", "title,status", *R)
    check(r.stdout.splitlines() == ["r1  title=Button order  status=approved", "r2  title=Empty state  status=draft"],
          "--fields works on a list path of a dict kind")
    r = run("list", "components", "--fields", "logicNotes", *R)
    check(all(len(l) < 100 for l in r.stdout.splitlines()), "a long value is cut to keep the line compact")
    r = run("list", "meta", "--fields", "name", *R)
    check(r.returncode != 0 and r.stdout == "", "--fields on a non-list is refused")
    check([l for l in run("list", "components", *R).stdout.splitlines()][0] == "button  Button  [atom]",
          "list without --fields is unchanged")

    check(open(reg, "rb").read() == before, "none of these reads wrote the registry")

if fails:
    print(f"FAIL — {len(fails)} regression(s)")
    sys.exit(1)
print("OK — slice find / get cap / list --fields")
