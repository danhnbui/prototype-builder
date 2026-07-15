#!/usr/bin/env python3
"""
render_budget.py — performance regression guard for the deterministic render.

Builds a synthetic registry at 50 components / 20 screens and asserts build_html()
stays under the 100 ms budget (baseline: 32 ms at 3/3). Pure in-process timing — no
subprocess, no file I/O — so it measures the render, not Python startup.

Usage:  python3 tests/render_budget.py
Exit:   0 = within budget · 1 = over budget
"""
import importlib.util
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUDGET_MS = 100.0
N_COMPONENTS = 50
N_SCREENS = 20
ITERATIONS = 7


def _load_render():
    path = os.path.join(ROOT, "pb", "tools", "render.py")
    spec = importlib.util.spec_from_file_location("render", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def synthetic_registry():
    tokens = {
        "brand": {"value": "#4f46e5", "kind": "color"},
        "surface": {"value": "#ffffff", "kind": "color"},
        "space-4": {"value": "16px", "kind": "space"},
        "radius-small": {"value": "8px", "kind": "radius"},
        "text-sm": {"value": "14px", "kind": "fontSize"},
    }
    components = []
    for i in range(N_COMPONENTS):
        pascal = "Cmp%02d" % i
        components.append({
            "id": "cmp-%02d" % i,
            "name": pascal,
            "renderFn": "renderCmp%s" % pascal,
            "scope": "global" if i % 2 else "local",
            "level": "atom",
            "properties": [],
            "render": ("return '<div style=\"padding:var(--space-4);"
                       "background:var(--surface);border-radius:var(--radius-small);"
                       "color:var(--brand);font-size:var(--text-sm)\">cmp %d</div>';" % i),
        })
    screens = []
    for i in range(N_SCREENS):
        pascal = "Scr%02d" % i
        screens.append({
            "id": "scr-%02d" % i,
            "name": pascal,
            "renderFn": "renderScreen%s" % pascal,
            "layout": {"type": "stack", "gap": 16, "maxWidth": 720, "padding": 32},
            "elements": [{"id": "e", "label": "el", "orgId": "cmp-%02d" % (i % N_COMPONENTS),
                          "tokens": ["--brand"], "state": "default"}],
            "logicNotes": [],
            "render": ("return '<div style=\"padding:var(--space-4);"
                       "background:var(--surface)\">screen %d</div>';" % i),
        })
    return {
        "meta": {"name": "Budget Synthetic", "schemaVersion": 3, "device": "desktop"},
        "tokens": tokens, "components": components, "screens": screens,
        "staleness": {}, "flow": {"populated": False}, "erd": {"populated": False},
    }


def main():
    render = _load_render()
    reg = synthetic_registry()
    shell = open(os.path.join(ROOT, "pb", "template", "prototype.html"), encoding="utf-8").read()

    times = []
    for _ in range(ITERATIONS):
        t0 = time.perf_counter()
        html, _missing = render.build_html(reg, shell)
        times.append((time.perf_counter() - t0) * 1000.0)
    best = min(times)
    median = sorted(times)[len(times) // 2]
    print("render budget: %d components / %d screens" % (N_COMPONENTS, N_SCREENS))
    print("  best=%.1f ms  median=%.1f ms  budget=%.0f ms  (output %d bytes)"
          % (best, median, BUDGET_MS, len(html)))
    if best > BUDGET_MS:
        print("::error::render over budget (%.1f ms > %.0f ms)" % (best, BUDGET_MS))
        raise SystemExit(1)
    print("✓ within budget")


if __name__ == "__main__":
    main()
