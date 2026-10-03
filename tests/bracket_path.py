#!/usr/bin/env python3
"""
bracket_path.py — every tool finds the project's files when its folder name holds glob syntax,
and the site map comes from `meta.navHub`.

A real project lived in a folder named `[HR] …`. `glob.glob` reads `[HR]` as a character class,
so the preview stopped watching render bodies, the logic cache never missed, the extractor saw
no bodies (blank site map) and logic_check passed over zero files — all silently. This builds a tiny project in a folder named `[x] proj` and asserts each consumer sees it.

It also pins the site-map half of the fix: a hub named by `meta.navHub` (here a mobile bottom bar,
not a sidebar.js) gives layer 0, and a page that names its target as a nav-atom PROP — the only
way R-COMPOSE lets a page do it — produces an edge.

Usage:  python3 tests/bracket_path.py
Exit:   0 = pass · 1 = a failure
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))

import logic_check   # noqa: E402
import logic_extract  # noqa: E402
import render         # noqa: E402
import serve          # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build(project):
    reg = {
        "meta": {"schemaVersion": 12, "navHub": "bottom-nav"},
        "screens": [
            {"id": "home", "name": "Home", "renderSrc": "render/screens/home.js", "renderFn": "renderScreenHome"},
            {"id": "detail", "name": "Detail", "renderSrc": "render/screens/detail.js", "renderFn": "renderScreenDetail"},
            {"id": "profile", "name": "Profile", "renderSrc": "render/screens/profile.js", "renderFn": "renderScreenProfile"},
        ],
        "components": [
            {"id": "nav-item", "level": "atom", "renderSrc": "render/components/nav-item.js", "renderFn": "renderCmpNavItem"},
            {"id": "bottom-nav", "level": "organism", "renderSrc": "render/components/bottom-nav.js", "renderFn": "renderCmpBottomNav"},
        ],
    }
    write(os.path.join(project, "registry.json"), json.dumps(reg, indent=2))
    write(os.path.join(project, "render/components/nav-item.js"),
          "return '<button data-nav=\"' + pbEscape(props.screen) + '\">' + pbEscape(props.label) + '</button>';\n")
    write(os.path.join(project, "render/components/bottom-nav.js"),
          "var TABS = [\n  { icon: 'home', label: 'Home', screen: 'home' },\n"
          "  { icon: 'person', label: 'Profile', screen: 'profile' }\n];\n"
          "return TABS.map(function (t) { return pbUse('nav-item', { label: t.label, screen: t.screen }); }).join('');\n")
    write(os.path.join(project, "render/screens/home.js"),
          "return pbUse('nav-item', { label: 'Open detail', screen: 'detail' }) + pbUse('bottom-nav', {});\n")
    write(os.path.join(project, "render/screens/detail.js"),
          "return pbUse('nav-item', { label: '‹ Home', screen: 'home' }) + pbUse('bottom-nav', {});\n")
    write(os.path.join(project, "render/screens/profile.js"), "return pbUse('bottom-nav', {});\n")


def main():
    tmp = tempfile.mkdtemp()
    project = os.path.join(tmp, "[x] proj")
    try:
        build(project)
        print(f"project: {project}")

        graph = logic_extract.extract(project)
        files = {it.get("file") for it in graph.get("items", [])}
        check("render/screens/home.js" in files, "logic_extract sees the render bodies")

        nav = graph.get("nav", {})
        check(nav.get("hubSource") == "meta.navHub", "the hub comes from meta.navHub")
        check([h["key"] for h in nav.get("hubs", [])] == ["home", "profile"],
              "the bottom bar's tabs are layer 0, in order (screen: key, any field order)")
        check(nav.get("depth", {}).get("detail") == 1,
              "a nav-atom prop (pbUse('nav-item', {screen: 'detail'})) is an edge")
        check(["home", "profile"] not in nav.get("edges", []),
              "the hub's own tabs are not edges between each other")
        check(["detail", "home"] in nav.get("edges", []) and "home" not in nav.get("children", {}).get("detail", []),
              "a back link is an edge, but never hangs a tab under its own child in the tree")
        check(nav.get("reason") is None, "no blank-map reason when the map draws")

        st = serve.State(os.path.join(project, "registry.json"), None, None, False)
        check(len(st.body_files) == 5, "serve.py watches every render body")

        key = render._logic_key(project)
        check(key is not None and sum("render" in p for p, *_ in key) == 5,
              "render.py's logic cache key covers every body")

        findings = logic_check.check_has_rules(project)
        check(isinstance(findings, list), "logic_check scans the bodies without error")

        # No hub at all → an explicit reason, not a silent blank.
        reg_path = os.path.join(project, "registry.json")
        with open(reg_path, encoding="utf-8") as f:
            reg = json.load(f)
        reg["meta"].pop("navHub")
        with open(reg_path, "w", encoding="utf-8") as f:
            json.dump(reg, f)
        check(logic_extract.extract(project)["nav"].get("reason") == "no-hub",
              "with no navHub and no sidebar.js the map says why it is blank")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAIL:
        print(f"\n✗ {len(FAIL)} failure(s)")
        sys.exit(1)
    print("\n✓ bracket-safe paths + navHub site map")


if __name__ == "__main__":
    main()
