#!/usr/bin/env python3
"""
ds_serve.py — a storybook-style preview server for a cloned design system (R1, v1.6).

`/pb:pull-ds` clones a DS into `registry.json` tokens + `design-system/<name>/.source.json`.
This serves a browsable reference of that clone: the token **foundations** rendered as visual
swatches (colors, space, radius, type, …) plus a **component catalog** from the clone's metadata.
It is the DS analogue of `/pb:preview` (which previews the prototype).

It re-reads the registry + snapshot on every request, so editing a token and refreshing shows the
change immediately. Stdlib only — no pip install (matches serve.py / render.py).

Usage:
  python3 ds_serve.py [registry.json] [--name DS] [--port N] [--host H] [--no-open]
"""
import argparse
import html
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_COLOR_KINDS = {"color"}
_BAR_KINDS = {"space", "size", "radius"}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pick_ds(registry_path, name):
    """Resolve which design-system/<name>/ to show: explicit --name, else meta, else first found."""
    root = os.path.dirname(os.path.abspath(registry_path))
    dsroot = os.path.join(root, "design-system")
    if name:
        return name
    try:
        reg = _load(registry_path)
        m = reg.get("meta", {}).get("designSystem", {}).get("name")
        if m and os.path.isdir(os.path.join(dsroot, m)):
            return m
    except (OSError, json.JSONDecodeError):
        pass
    if os.path.isdir(dsroot):
        for d in sorted(os.listdir(dsroot)):
            if os.path.isfile(os.path.join(dsroot, d, ".source.json")):
                return d
    return None


def _swatch(name, tok):
    kind, val = tok.get("kind", "other"), html.escape(str(tok.get("value", "")))
    label = f"<code>--{html.escape(name)}</code><span class='v'>{val}</span>"
    if kind in _COLOR_KINDS:
        return (f"<div class='sw'><div class='chip' style='background:var(--{html.escape(name)})'></div>"
                f"<div class='meta'>{label}</div></div>")
    if kind in _BAR_KINDS:
        return (f"<div class='sw'><div class='bar' style='width:var(--{html.escape(name)});"
                f"{'border-radius:var(--'+html.escape(name)+')' if kind=='radius' else ''}'></div>"
                f"<div class='meta'>{label}</div></div>")
    if kind in ("type", "font", "fontSize"):
        return (f"<div class='sw'><div class='type' style='font-family:var(--{html.escape(name)});"
                f"font-size:var(--{html.escape(name)})'>Ag</div><div class='meta'>{label}</div></div>")
    return f"<div class='sw'><div class='meta'>{label}</div></div>"


def build_html(registry_path, name):
    reg = _load(registry_path)
    tokens = reg.get("tokens", {})
    ds = _pick_ds(registry_path, name)
    snap = {}
    if ds:
        sp = os.path.join(os.path.dirname(os.path.abspath(registry_path)), "design-system", ds, ".source.json")
        if os.path.isfile(sp):
            snap = _load(sp)
    title = ds or reg.get("meta", {}).get("designSystem", {}).get("name") or "design system"
    plat = snap.get("platform") or reg.get("meta", {}).get("platform", "web")
    src = reg.get("meta", {}).get("dsSource") or {}
    src_line = f"{src.get('type','?')} · {html.escape(str(src.get('ref','—')))}" if src else "not cloned"

    root_vars = ";".join(f"--{html.escape(n)}:{html.escape(str(t.get('value','')))}" for n, t in tokens.items())

    # foundations grouped by kind
    by_kind = {}
    for n, t in sorted(tokens.items()):
        by_kind.setdefault(t.get("kind", "other"), []).append((n, t))
    found = []
    for kind in sorted(by_kind):
        chips = "".join(_swatch(n, t) for n, t in by_kind[kind])
        found.append(f"<h3>{html.escape(kind)} <span class='n'>{len(by_kind[kind])}</span></h3><div class='grid'>{chips}</div>")
    found_html = "".join(found) or "<p class='empty'>No tokens yet — run <code>/pb:pull-ds</code>.</p>"

    comps = snap.get("components", [])
    cards = "".join(
        f"<div class='card'><div class='cid'><code>{html.escape(str(c.get('id','?')))}</code>"
        f"<span class='lvl'>{html.escape(str(c.get('level','')))}</span></div>"
        f"<div class='purpose'>{html.escape(str(c.get('purpose','')))}</div>"
        f"<div class='variants'>{''.join('<span>'+html.escape(str(v))+'</span>' for v in c.get('variants',[])) or '<em>no variants</em>'}</div></div>"
        for c in comps)
    cat_html = f"<div class='cards'>{cards}</div>" if comps else "<p class='empty'>No components in the clone metadata.</p>"

    return f"""<!doctype html><html><head><meta charset="utf-8"><title>DS · {html.escape(title)}</title>
<style>
:root{{{root_vars};--_bg:#fff;--_fg:#111;--_mut:#666;--_line:#e5e7eb}}
@media(prefers-color-scheme:dark){{:root{{--_bg:#0b0b0c;--_fg:#f3f4f6;--_mut:#9ca3af;--_line:#26262b}}}}
*{{box-sizing:border-box}}body{{margin:0;font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--_bg);color:var(--_fg)}}
header{{padding:20px 28px;border-bottom:1px solid var(--_line)}}header h1{{margin:0 0 4px;font-size:18px}}header .sub{{color:var(--_mut);font-size:12px}}
main{{padding:24px 28px;max-width:1100px}}h2{{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--_mut);margin:28px 0 12px}}
h3{{font-size:13px;margin:20px 0 8px}}h3 .n{{color:var(--_mut);font-weight:400}}
.grid{{display:flex;flex-wrap:wrap;gap:14px}}.sw{{display:flex;flex-direction:column;gap:6px;min-width:120px}}
.chip{{width:120px;height:56px;border:1px solid var(--_line);border-radius:8px}}
.bar{{height:24px;min-width:8px;background:var(--_fg);opacity:.85}}.type{{height:40px;line-height:40px}}
.meta{{font-size:11px;color:var(--_mut);display:flex;flex-direction:column}}.meta code{{color:var(--_fg)}}.meta .v{{color:var(--_mut)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}}
.card{{border:1px solid var(--_line);border-radius:10px;padding:14px}}.cid{{display:flex;justify-content:space-between;align-items:center}}
.lvl{{font-size:10px;text-transform:uppercase;letter-spacing:.04em;color:var(--_mut);border:1px solid var(--_line);border-radius:99px;padding:1px 8px}}
.purpose{{color:var(--_mut);font-size:12px;margin:8px 0}}.variants{{display:flex;flex-wrap:wrap;gap:6px}}
.variants span{{font-size:11px;background:color-mix(in srgb,var(--_fg) 8%,transparent);border-radius:6px;padding:1px 7px}}
.variants em{{color:var(--_mut);font-size:11px}}.empty{{color:var(--_mut)}}code{{font-family:ui-monospace,Menlo,monospace}}
</style></head><body>
<header><h1>{html.escape(title)} <span style="font-weight:400;color:var(--_mut)">· {html.escape(plat)}</span></h1>
<div class="sub">source: {src_line} · {len(tokens)} tokens · {len(comps)} components — <code>ds_serve.py</code></div></header>
<main>
<h2>Foundations</h2>{found_html}
<h2>Component catalog</h2>{cat_html}
</main></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    registry_path = "registry.json"
    ds_name = None

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_response(204)
            self.end_headers()
            return
        try:
            body = build_html(self.registry_path, self.ds_name).encode("utf-8")
            self.send_response(200)
        except (OSError, json.JSONDecodeError) as e:
            body = f"<pre>ds_serve error: {html.escape(str(e))}</pre>".encode("utf-8")
            self.send_response(500)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(argv=None):
    p = argparse.ArgumentParser(prog="ds_serve.py")
    p.add_argument("registry", nargs="?", default="registry.json")
    p.add_argument("--name", default=None, help="which design-system/<name>/ to show")
    p.add_argument("--port", type=int, default=5174)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--print", action="store_true", help="print the HTML and exit (no server)")
    args = p.parse_args(argv)
    if not os.path.isfile(args.registry):
        sys.exit(f"ds_serve: no registry at {args.registry}")
    if args.print:
        sys.stdout.write(build_html(args.registry, args.name))
        return 0
    _Handler.registry_path = args.registry
    _Handler.ds_name = args.name
    port = args.port
    for _ in range(20):  # find a free port
        try:
            httpd = ThreadingHTTPServer((args.host, port), _Handler)
            break
        except OSError:
            port += 1
    else:
        sys.exit("ds_serve: no free port")
    url = f"http://{args.host}:{port}/"
    print(f"pb-ds-serve · design system → {url}  (Ctrl-C to stop)", flush=True)
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\npb-ds-serve · stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
