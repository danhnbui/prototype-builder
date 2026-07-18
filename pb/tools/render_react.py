#!/usr/bin/env python3
"""
render_react.py — the SCAFFOLD export tier (R2, v1.7): deterministic registry → React + Vite.

pb's export tiers, cheapest first:
  host      — the runnable single-file prototype (/pb:validate). No code export.
  scaffold  — THIS: a deterministic, self-contained React+Vite app that faithfully reuses each
              registry render body, with the design tokens as CSS vars + a Tailwind theme.
  hardened  — idiomatic, DS-integrated per-component JSX (MCP-resolved, repo-matched, reviewed).

Why a wrapper, not idiomatic JSX: render bodies are JS that runs client-side; pb tools are
stdlib-Python with no JS runtime, so we can't execute them to synthesize idiomatic JSX. The
scaffold instead emits, per component/screen, a React component that renders that entity's own
body via `dangerouslySetInnerHTML`, styled by `tokens.css`. It is deterministic, self-contained,
runnable (`npm i && npm run dev`), and lints clean — and it is honest about being mechanical.
Turning a wrapper into idiomatic Tailwind JSX is the hardened tier's job.

Pure stdlib. Deterministic (no timestamps in emitted code).

Usage:
  python3 render_react.py [registry.json] --out DIR [--screen ID | --component ID]
"""
import argparse
import json
import os
import re
import sys

_FN_RE = re.compile(r"function\s+([A-Za-z_$][\w$]*)\s*\(")
# token kind → tailwind theme bucket
_TW_BUCKET = {"color": "colors", "space": "spacing", "size": "spacing", "radius": "borderRadius",
              "fontSize": "fontSize", "type": "fontFamily", "font": "fontFamily", "shadow": "boxShadow"}


def _pascal(kebab):
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[-_ ]+", str(kebab)) if w) or "Component"


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _read_body(base_dir, item):
    rel = item.get("renderSrc")
    if not rel:
        return None
    p = os.path.normpath(os.path.join(base_dir, rel))
    if not os.path.isfile(p):
        return None
    return open(p, encoding="utf-8").read()


def _module(body):
    """Turn a render body (defines `function renderX(props){…}`) into an ESM default export."""
    m = _FN_RE.search(body)
    fn = m.group(1) if m else None
    if not fn:
        return None
    return body.rstrip() + f"\n\nexport default {fn};\n"


def _wrapper(pascal, kind_dir):
    return (f"import render from './{pascal}.render.js';\n"
            f"import '../tokens.css';\n\n"
            f"// SCAFFOLD wrapper — reuses the registry render body verbatim. The hardened tier\n"
            f"// replaces this with idiomatic Tailwind JSX.\n"
            f"export default function {pascal}(props = {{}}) {{\n"
            f"  return <div className=\"pb-{kind_dir[:-1]}\" dangerouslySetInnerHTML={{{{ __html: render(props) }}}} />;\n"
            f"}}\n")


def _tokens_css(tokens):
    lines = [":root {"]
    for name, t in sorted(tokens.items()):
        lines.append(f"  --{name}: {t.get('value', '')};")
    lines += ["}", ""]
    return "\n".join(lines)


def _tailwind_config(tokens):
    buckets = {}
    for name, t in sorted(tokens.items()):
        bucket = _TW_BUCKET.get(t.get("kind", "other"))
        if bucket:
            buckets.setdefault(bucket, {})[name] = f"var(--{name})"
    extend = json.dumps(buckets, indent=6).replace('"var(', "'var(").replace(')"', ")'")
    return ("/** Deterministic Tailwind theme — every design token mapped to a utility scale,\n"
            " *  so you can restyle with Tailwind utilities that resolve to the DS tokens. */\n"
            "export default {\n"
            "  content: ['./index.html', './src/**/*.{jsx,js}'],\n"
            f"  theme: {{ extend: {extend} }},\n"
            "  plugins: [],\n"
            "};\n")


def _static(name):
    return {
        "package.json": json.dumps({
            "name": _slug(name) + "-scaffold", "private": True, "version": "0.0.0", "type": "module",
            "scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
            "dependencies": {"react": "^18.3.1", "react-dom": "^18.3.1"},
            "devDependencies": {"@vitejs/plugin-react": "^4.3.1", "vite": "^5.4.0"},
        }, indent=2) + "\n",
        "vite.config.js": ("import { defineConfig } from 'vite';\n"
                           "import react from '@vitejs/plugin-react';\n\n"
                           "export default defineConfig({ plugins: [react()] });\n"),
        "index.html": ("<!doctype html>\n<html><head><meta charset=\"utf-8\">\n"
                       f"<title>{name} — scaffold</title></head>\n"
                       "<body><div id=\"root\"></div>\n"
                       "<script type=\"module\" src=\"/src/main.jsx\"></script></body></html>\n"),
        "src/main.jsx": ("import React from 'react';\nimport { createRoot } from 'react-dom/client';\n"
                         "import App from './App.jsx';\n\ncreateRoot(document.getElementById('root')).render(<App />);\n"),
    }


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-") or "pb"


def _app(screen_pascal, component_pascals):
    if screen_pascal:
        return (f"import Screen from './screens/{screen_pascal}.jsx';\n"
                "import './tokens.css';\n\nexport default function App() {\n"
                f"  return <Screen />;\n}}\n")
    imports = "".join(f"import {p} from './components/{p}.jsx';\n" for p in component_pascals)
    gallery = "".join(f"      <section><h3>{p}</h3><{p} /></section>\n" for p in component_pascals)
    return (imports + "import './tokens.css';\n\nexport default function App() {\n"
            "  return (\n    <main style={{ padding: 24, display: 'grid', gap: 24 }}>\n"
            f"{gallery}    </main>\n  );\n}}\n")


def emit(registry_path, out_dir, screen=None, component=None):
    reg = _load(registry_path)
    base = os.path.dirname(os.path.abspath(registry_path))
    tokens = reg.get("tokens", {})
    name = reg.get("meta", {}).get("name") or "pb-app"

    comps = reg.get("components", [])
    screens = reg.get("screens", [])
    want_comp = {component} if component else None
    want_screen = {screen} if screen else None

    written = []

    def _mkdir(*parts):
        d = os.path.join(out_dir, *parts)
        os.makedirs(d, exist_ok=True)
        return d

    _mkdir("src")
    # tokens.css + tailwind
    for rel, content in (("src/tokens.css", _tokens_css(tokens)),
                         ("tailwind.config.js", _tailwind_config(tokens))):
        p = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(content)
        written.append(rel)

    comp_pascals, screen_pascal = [], None
    for kind_dir, items, want in (("components", comps, want_comp), ("screens", screens, want_screen)):
        for item in items:
            iid = item.get("id")
            if want is not None and iid not in want:
                continue
            body = _read_body(base, item)
            mod = _module(body) if body else None
            if not mod:
                print(f"  · skip {kind_dir[:-1]} {iid!r}: no usable renderSrc body", file=sys.stderr)
                continue
            pascal = _pascal(iid)
            _mkdir("src", kind_dir)
            open(os.path.join(out_dir, "src", kind_dir, f"{pascal}.render.js"), "w", encoding="utf-8").write(mod)
            open(os.path.join(out_dir, "src", kind_dir, f"{pascal}.jsx"), "w", encoding="utf-8").write(_wrapper(pascal, kind_dir))
            written += [f"src/{kind_dir}/{pascal}.render.js", f"src/{kind_dir}/{pascal}.jsx"]
            if kind_dir == "components":
                comp_pascals.append(pascal)
            elif screen and iid == screen:
                screen_pascal = pascal
            elif not screen and screen_pascal is None:
                screen_pascal = pascal  # default the app to the first screen when exporting all

    # app + static scaffolding
    open(os.path.join(out_dir, "src", "App.jsx"), "w", encoding="utf-8").write(_app(screen_pascal, comp_pascals))
    written.append("src/App.jsx")
    for rel, content in _static(name).items():
        p = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(content)
        written.append(rel)
    open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8").write(
        f"# {name} — scaffold export (React + Vite)\n\n"
        "Deterministic **scaffold** tier from `/pb:handoff-dev --tier=scaffold`. Each component/screen\n"
        "is a React wrapper that reuses its registry render body; styling is the design tokens\n"
        "(`src/tokens.css` `:root` vars), also mapped into `tailwind.config.js`.\n\n"
        "```\nnpm install\nnpm run dev\n```\n\n"
        "> This is mechanical (wrappers around pb render bodies). Idiomatic per-component Tailwind\n"
        "> JSX, DS-integrated and repo-matched, is the **hardened** tier.\n")
    written.append("README.md")

    print(f"✓ scaffold '{name}' → {os.path.relpath(out_dir)}  ({len(written)} files, "
          f"{len(comp_pascals)} components, {len(tokens)} tokens)")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="render_react.py")
    p.add_argument("registry", nargs="?", default="registry.json")
    p.add_argument("--out", required=True)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--screen", default=None)
    g.add_argument("--component", default=None)
    args = p.parse_args(argv)
    if not os.path.isfile(args.registry):
        sys.exit(f"render_react: no registry at {args.registry}")
    try:
        return emit(args.registry, args.out, args.screen, args.component)
    except (OSError, json.JSONDecodeError) as e:
        print(f"render_react: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
