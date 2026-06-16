#!/usr/bin/env python3
"""
shell_version.py — guards the shell version-stamping feature (upgrade-coherence).

Asserts (render side — Task 1; Task 2 appends shipped-shell wiring checks at the marker):
  1. render.plugin_version() returns the SemVer in pb/.claude-plugin/plugin.json (not 'unknown').
  2. render._version_from() falls back to 'unknown' for missing / garbled / version-less files,
     and never raises (a bad plugin.json must not crash a render).
  3. build_html() replaces the {{PB_SHELL_VERSION}} placeholder with the passed version
     (checked against a synthetic shell so Task 1 is green independent of the template); default -> 'unknown'.
  4. render_file() writes a `<!-- pb-shell vX · rendered <ISO> -->` stamp right after the DOCTYPE.

Usage:  python3 tests/shell_version.py
Exit:   0 = clean · 1 = a failure
"""
import importlib.util
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, "pb", "template", "prototype.html")
PLUGIN_JSON = os.path.join(ROOT, "pb", ".claude-plugin", "plugin.json")

_fail = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _fail.append(msg)


def _load_render():
    path = os.path.join(ROOT, "pb", "tools", "render.py")
    spec = importlib.util.spec_from_file_location("render", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _minimal_registry():
    return {
        "meta": {"name": "Version Test", "schemaVersion": 4, "device": "desktop"},
        "tokens": {"brand": {"value": "#4f46e5", "kind": "color"}},
        "components": [], "screens": [],
        "staleness": {}, "flow": {"populated": False}, "erd": {"populated": False},
    }


def _synthetic_shell():
    """A minimal shell carrying exactly the anchors build_html needs + the version placeholder,
    so the version replace can be tested independent of whether the shipped template is wired yet.
    The PB_DATA line must match build_html's anchor verbatim (4-space indent)."""
    return (
        "<!DOCTYPE html>\n<html><head><title>t</title></head><body>\n"
        "<script>\n"
        "const PB_REGISTRY = /*__PB_REGISTRY_START__*/ null /*__PB_REGISTRY_END__*/;\n"
        'const PB_SHELL_VERSION = "{{PB_SHELL_VERSION}}";\n'
        "    const PB_DATA = adaptRegistryToPBData(PB_REGISTRY);\n"
        "</script>\n</body></html>\n"
    )


def main():
    render = _load_render()
    real_version = json.load(open(PLUGIN_JSON, encoding="utf-8"))["version"]

    # 1 — plugin_version() reads the real SemVer
    pv = render.plugin_version()
    check(pv == real_version, f"plugin_version() == plugin.json version ({pv!r} == {real_version!r})")
    check(pv != "unknown", "plugin_version() is not the 'unknown' fallback")

    # 2 — _version_from fallback is total (never raises, always a str)
    with tempfile.TemporaryDirectory() as tmp:
        good = os.path.join(tmp, "good.json")
        json.dump({"version": "2.0.0"}, open(good, "w"))
        check(render._version_from(good) == "2.0.0", "_version_from reads a valid version")

        garbled = os.path.join(tmp, "garbled.json")
        open(garbled, "w").write("{ not json")
        check(render._version_from(garbled) == "unknown", "_version_from('garbled') -> 'unknown'")

        nover = os.path.join(tmp, "nover.json")
        json.dump({"name": "pb"}, open(nover, "w"))
        check(render._version_from(nover) == "unknown", "_version_from(version-less) -> 'unknown'")

        missing = os.path.join(tmp, "nope.json")
        check(render._version_from(missing) == "unknown", "_version_from(missing) -> 'unknown'")

    # 3 — build_html replaces the placeholder (synthetic shell -> Task-1-independent)
    syn = _synthetic_shell()
    html_default, _ = render.build_html(_minimal_registry(), syn)
    check("{{PB_SHELL_VERSION}}" not in html_default,
          "build_html removes the {{PB_SHELL_VERSION}} placeholder")
    check('PB_SHELL_VERSION = "unknown"' in html_default,
          "build_html default version is 'unknown'")
    html_v, _ = render.build_html(_minimal_registry(), syn, "9.9.9-test")
    check('PB_SHELL_VERSION = "9.9.9-test"' in html_v,
          "build_html injects the passed version into PB_SHELL_VERSION")

    # 4 — render_file stamps the on-disk artifact, right after the DOCTYPE (real shell)
    with tempfile.TemporaryDirectory() as tmp:
        reg_path = os.path.join(tmp, "registry.json")
        out_path = os.path.join(tmp, "prototype.html")
        json.dump(_minimal_registry(), open(reg_path, "w"))
        render.render_file(reg_path, SHELL, out_path)
        out = open(out_path, encoding="utf-8").read()
        m = re.search(r"<!-- pb-shell v(\S+) · rendered (\S+) -->", out)
        check(m is not None, "prototype.html carries a pb-shell stamp comment")
        if m:
            check(m.group(1) == real_version, f"stamp version == plugin version ({m.group(1)})")
            check(re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", m.group(2)) is not None,
                  f"stamp timestamp is ISO-8601 Zulu ({m.group(2)})")
            check(0 <= out.index("<!DOCTYPE html>") < out.index("<!-- pb-shell") < 200,
                  "stamp sits right after the DOCTYPE (near the top)")

    # 4b — stamp() is idempotent (re-stamping replaces, never accumulates)
    once = render.stamp("<!DOCTYPE html>\n<html></html>", "1.0.0")
    twice = render.stamp(once, "2.0.0")
    check(twice.count("<!-- pb-shell v") == 1, "stamp() is idempotent (one stamp after re-stamp)")
    check("v2.0.0" in twice and "v1.0.0" not in twice, "stamp() keeps the newest version on re-stamp")

    # 5 — the shipped shell carries the wiring + fills its const (Task 2)
    shell = open(SHELL, encoding="utf-8").read()
    check("{{PB_SHELL_VERSION}}" in shell, "shipped shell exposes the {{PB_SHELL_VERSION}} placeholder")
    check('class="meta-version"' in shell, "shipped shell renders the .meta-version badge")
    built, _ = render.build_html(_minimal_registry(), shell, "7.7.7-shipped")
    check('PB_SHELL_VERSION = "7.7.7-shipped"' in built,
          "shipped shell's PB_SHELL_VERSION const receives the version")

    print()
    if _fail:
        print(f"✗ {len(_fail)} shell-version failure(s).")
        sys.exit(1)
    print("✓ shell-version clean.")


if __name__ == "__main__":
    main()
