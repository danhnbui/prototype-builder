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
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUDGET_MS = 100.0
# The whole pipeline on this synthetic fixture. Generous next to build_html's 100 ms
# because load_logic genuinely scans every render body — but far under the 3.7 s a
# quadratic lookup cost before anyone measured it.
PIPELINE_BUDGET_MS = 1500.0
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



def _write_pipeline_fixture(d, reg):
    """Materialise the synthetic registry on disk as a real pb project.

    load_specs and load_logic both read FILES, so the in-memory registry the build_html
    budget uses cannot exercise them — they need renderSrc bodies that exist.
    """
    import copy as _copy
    out = _copy.deepcopy(reg)
    for kind, sub in (("components", "components"), ("screens", "screens")):
        for item in out.get(kind, []) or []:
            body = item.pop("render", "") or ""
            rel = "render/%s/%s.js" % (sub, item["id"])
            item["renderSrc"] = rel
            full = os.path.join(d, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(body if body.strip() else
                        "function %s(props) { return ''; }\n" % item.get("renderFn", "renderCmpX"))
    with open(os.path.join(d, "registry.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)


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
    over = best > BUDGET_MS
    if over:
        print("::error::render over budget (%.1f ms > %.0f ms)" % (best, BUDGET_MS))
    else:
        print("✓ within budget")

    # ---- the WHOLE pipeline, not just build_html ------------------------------------
    # build_html was the only step measured, and it was never the slow one. Measured on a
    # real project (133 components): build_html 21 ms, load_specs 29 ms, load_bodies 24 ms,
    # and load_logic — which no test watched — 3,746 ms, because its call-site lookup was
    # quadratic in (handlers x files). A preview server re-renders on every save, so that
    # went unnoticed by every green test while making the tool unusable. Inverting the
    # index took it to ~370 ms. This budget exists so the next such step cannot hide.
    import tempfile
    pipeline_ms = None
    with tempfile.TemporaryDirectory() as d:
        _write_pipeline_fixture(d, reg)
        t0 = time.perf_counter()
        r = render.load_bodies(json.load(open(os.path.join(d, "registry.json"), encoding="utf-8")), d)
        r = render.load_specs(r, d)
        logic = render.load_logic(d, r)
        render.build_html(r, shell, "test", logic=logic)
        pipeline_ms = (time.perf_counter() - t0) * 1000.0
    print("  pipeline (load_bodies + load_specs + load_logic + build_html):"
          " %.1f ms  budget=%.0f ms" % (pipeline_ms, PIPELINE_BUDGET_MS))
    if pipeline_ms > PIPELINE_BUDGET_MS:
        print("::error::render pipeline over budget (%.1f ms > %.0f ms)"
              % (pipeline_ms, PIPELINE_BUDGET_MS))
        over = True
    if over:
        raise SystemExit(1)
    print("✓ within budget (build_html and the whole pipeline)")


if __name__ == "__main__":
    main()
