#!/usr/bin/env python3
"""
pb-check — the contract validator (refit plan Phase 1, T1.1).

Machine-checks a registry.json against the data contract the playbook promises, so
violations are caught before render / hand-off instead of compiled silently. Pure
stdlib (NS4); a validator is not a render, so the token levers (NS2/NS3) are untouched.

Severity → exit code:
  0  clean (no findings)
  1  warnings only
  2  at least one error

--strict promotes the "strict" rules below from WARN to ERROR (default is WARN so existing
projects don't hard-break — NS6, a migration path). Other rules are fixed severity.

Each finding prints as:  <SEVERITY> [<CODE>] <location>: <message>

Rules (severity · default → under --strict):
  R-IO R-JSON R-SHAPE R-KEBAB R-DUPID R-RENDERFN R-LEVEL R-SCRIPT R-SPECSRC R-NEST
  R-ORGID R-RENDERSRC(missing file) R-DTCG-TYPE(bad $type)
  R-LEVEL-ORDER(an atom composes)                                           ERROR · always
  R-HEX · R-PX                       raw hex / px in a body                 WARN → ERROR
  R-COMPOSE · R-COMPOSE-MATCH(declared, not composed)
  R-LEVEL-ORDER(composes its own level or higher)
                                     the component-first / atomic law       WARN → ERROR
  R-PROP-DECLARED                    a component body reads props.X that properties[]
                                     does not declare (wiring props — dataX, ariaX, onX,
                                     id, className, full, layout keys — are skipped)  WARN → ERROR
  R-PROP-USED                        a properties[].options[] value the body never renders
                                     (no branch, literal, lookup key or pass-through)
                                     · the `state` property — a fake interactive state  WARN → ERROR
                                     · any other property                   WARN · always
  R-COMPOSE-TEXT R-COMPOSE-MATCH(composed, not declared) R-LEVEL-ORDER(composes nothing)
  R-NEST-HINT R-PROPTYPE R-RENDERSRC(both set) R-DTCG-TYPE(legacy shape)
  R-TOKENREF R-DANGER R-FLOW R-ERD                                          WARN · always
  R-EXEC (--exec only)               a body throws, returns a non-string or '' when run
                                     with {} and once per `state` option   ERROR · always
  R-NEST-FIGMA (--figma only)        a declared nested global has no Figma instance  ERROR

Usage:  python3 lint_registry.py [--strict] [--exec] [--report] [--sync-elements] <registry.json>
        python3 lint_registry.py --figma <registry.json> <figma-transfer.json>
        python3 lint_registry.py --help

--exec          also RUN every render body in node (R-EXEC): components once with {} and
                once per `state` option on their default props, screens once with {};
                pbUse is stubbed so each body is judged alone. Opt-in. No node on PATH →
                one line saying no body was executed (skipped, not passed) and the static
                verdict alone; node is an isolated exception to the stdlib-only core.
--report        rank, never gate: a histogram by code, the items carrying the most, the
                shape metrics, and a "fix first" list. ALWAYS exits 0 — at 87 findings on a
                real project a flat list is unreadable, and the ordering is the product.
                Thresholds from an optional memory/doctor.json beside the registry. Also a
                `resources` block — the registry's largest keys, backups, open and closed explore
                rounds, .preview/server.log, the preview server — ranked with the command that fixes it.
--sync-elements APPEND a screens[].elements[] entry per composed-but-undeclared component.
                Append-only and idempotent; never edits, reorders or removes an entry. Takes the
                registry lock (exit 2 with a message naming the holder if it is held) and writes
                atomically; every other mode is read-only and takes no lock.
"""
import glob
import importlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tokens as _tok  # noqa: E402  (sibling module; the W3C DTCG token resolver)
pbslice = importlib.import_module("slice")  # the registry write path: lock + atomic write (`import slice` shadows the builtin)
from logic_extract import strip_comments  # noqa: E402  (quote-aware; the props scans read code, not prose)
import spec_parts as _parts  # noqa: E402  (anatomy parts from either sidecar shape: parts[] or schema-13 instanceOf)

# Tokens the shell's runtime references by name; absence is a latent Principle-1 gap.
RUNTIME_REQUIRED_TOKENS = ("danger",)

_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_PX = re.compile(r"\b\d+(?:\.\d+)?px\b")
_SCRIPT_CLOSE = re.compile(r"</\s*script", re.IGNORECASE)

# Atomic-design levels + their composition rank (higher composes lower). `foundation` = tokens;
# a screen is implicitly `page`. Component-first / atomic law: only atoms emit raw primitives;
# every level above composes lower-level components via pbUse() (mirrors the shell runtime).
LEVEL_ENUM = {"atom", "molecule", "organism", "template", "page"}
LEVEL_RANK = {"foundation": 0, "atom": 1, "molecule": 2, "organism": 3, "template": 4, "page": 5}
_CONTROL_TAGS = ("button", "input", "select", "textarea", "a", "form", "img", "video", "canvas", "iframe")
_TEXT_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "label", "small", "strong", "em")
_CONTROL_RE = re.compile(r"<(" + "|".join(_CONTROL_TAGS) + r")(?=[\s/>])", re.IGNORECASE)
_TEXT_RE = re.compile(r"<(" + "|".join(_TEXT_TAGS) + r")(?=[\s/>])", re.IGNORECASE)
_PBUSE = re.compile(r"pbUse\(\s*['\"]([a-z0-9][a-z0-9-]*)['\"]")

ERROR, WARN = "ERROR", "WARN"

# Set by the last check() run: how many var(--…) references were composed at runtime and so
# could not be verified statically. --report prints it under information; it is never a finding.
_TOKENREF_DYNAMIC = [0]


class Finding:
    __slots__ = ("severity", "code", "where", "msg")

    def __init__(self, severity, code, where, msg):
        self.severity = severity
        self.code = code
        self.where = where
        self.msg = msg

    def line(self):
        return f"{self.severity} [{self.code}] {self.where}: {self.msg}"


def pascal(id_):
    return "".join(part[:1].upper() + part[1:] for part in str(id_).split("-") if part)


# A part name that is PROSE, not a label: it carries sentence punctuation. R-NEST-HINT skips
# these outright. Measured: 6 of the 12 hints on a real project came from matching a word
# inside a description like "Toolbar — search + three filter comboboxes + download" (→ combobox)
# or "Hidden input carrying the value" (→ input). A substring/token test cannot tell those from
# a real label, so the discriminator is the punctuation that marks it as a sentence.
_PROSE_NAME = re.compile(r"[—–,:;+()/]|\.\s|\S\s+\S+\s+\S+\s+\S+")
_WORDS = re.compile(r"[a-z0-9]+")


def _hint_component(name, ids_by_len):
    """The component id a part NAME most likely refers to, or None (R-NEST-HINT).

    Whole-token, longest-match, prose-rejecting — in that order. The old rule was a bare
    substring test (`g in name.lower()`), which fired on any id appearing anywhere in a
    10-word description. `ids_by_len` is the component-id list sorted longest-first so
    'Department Tag Select' resolves to 'department-tag-select', not 'select', and
    'Label Wrap' to 'label-wrap', not 'label' — the specific answer, not the first one.
    """
    raw = str(name or "").strip()
    if not raw or _PROSE_NAME.search(raw):
        return None
    toks = _WORDS.findall(raw.lower())
    if not toks or len(toks) > 4:
        return None
    joined = "-".join(toks)
    for cid in ids_by_len:                     # longest id first → most specific wins
        parts = cid.split("-")
        n = len(parts)
        if n > len(toks):
            continue
        if joined == cid:
            return cid
        # the id's words as a CONSECUTIVE run of the name's words
        if any(toks[i:i + n] == parts for i in range(len(toks) - n + 1)):
            return cid
    return None


# A `default` that is a STRING but opens like a collection literal. `'[]'` is not an empty
# list — it is a two-character string, and `'[]'.map` is not a function.
_COLLECTION_LITERAL = re.compile(r"^\s*[\[{]")


# A `var(--name)` reference in a render body. Group 1 is the name, group 2 whatever follows
# inside the parens — a fallback, or nothing. Names are captured loosely on purpose so a
# runtime-composed one still matches and can be recognised as such rather than missed.
_VAR_REF = re.compile(r"var\(\s*--([A-Za-z0-9_$\-]*(?:\$\{[^}]*\}[A-Za-z0-9_$\-]*)*)\s*(,[^)]*)?\)")
# A name built by interpolation — `var(--bg-${tone}-muted)`, `var(--space-${size})`. Its real
# value is only known at runtime, so it is counted and reported as information, never a finding.
_VAR_DYNAMIC = re.compile(r"\$\{|\$\{?[A-Za-z_]")


_CUSTOM_PROP = re.compile(r"(?m)^\s*--([A-Za-z0-9_-]+)\s*:")
# The same, anywhere in a body — inline `style="--x:…"` and a generated <style> alike.
_CUSTOM_PROP_ANY = re.compile(r"--([A-Za-z0-9_-]+)\s*:")
_SHELL_PROPS_CACHE = []


def _shell_custom_props():
    """The custom properties the shipped shell declares in its own <style> — the OTHER producer
    of `var(--x)`, beside the project's tokens. Returns None when the shell cannot be read, which
    switches R-TOKENREF off rather than letting it report every shell variable as missing."""
    if _SHELL_PROPS_CACHE:
        return _SHELL_PROPS_CACHE[0]
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "template", "prototype.html")
    try:
        with open(path, encoding="utf-8") as f:
            html = f.read()
    except OSError:
        _SHELL_PROPS_CACHE.append(None)
        return None
    props = set()
    for style in re.findall(r"<style[^>]*>(.*?)</style>", html, re.S):
        props |= set(_CUSTOM_PROP.findall(style))
    _SHELL_PROPS_CACHE.append(props or None)
    return _SHELL_PROPS_CACHE[0]


# ── responsive: styleSrc sheets + meta.responsive ──────────────────────────────────────────
# The device frames are <div>s in one document, so a width/height @media rule answers the
# BROWSER WINDOW, never the frame — a 429px phone frame on a 1440px monitor matches
# `min-width: 1024px`. Responsive rules are `@container pb-screen (…)` (pb/template/product.css).
_DEVICE_CLASS = {"mobile": "compact", "tablet": "medium", "laptop": "expanded",
                 "monitor": "expanded", "desktop": "expanded"}
_MEDIA_SIZE = re.compile(r"@media[^{]*\b(?:min-|max-)?(?:width|height|device-width|aspect-ratio)\b")
_CONTAINER_PRELUDE = re.compile(r"@container[^{]*\{")
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_CSS_PRELUDE = re.compile(r"([^{};]+)\{")
_R_UTIL = re.compile(r"(?<![\w-])r-(?:compact|medium-up|expanded-up|below-expanded|cols)(?![\w-])")
_ADAPTS = re.compile(r"@container\b")


def _size_classes(meta):
    devs = meta.get("devices") if isinstance(meta.get("devices"), list) else []
    return {_DEVICE_CLASS[d] for d in devs if d in _DEVICE_CLASS}


def _style_of(item, base_dir):
    src = item.get("styleSrc")
    if not src or base_dir is None:
        return None
    try:
        with open(os.path.normpath(os.path.join(base_dir, src)), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _check_styles(add, meta, components, screens, comp_by_id, base_dir, hex_px_sev, strict):
    """styleSrc sheets are scoped, token-only and use container queries; and when the project
    says it is responsive, every screen can reach a rule that adapts it."""
    for kind, items in (("component", components), ("screen", screens)):
        for i, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("styleSrc"):
                continue
            where = f"{kind}s[{i}] id={item.get('id', '')!r}"
            css = _style_of(item, base_dir)
            if css is None:
                if base_dir is not None:
                    add(ERROR, "R-STYLESRC", where, f"styleSrc file not found: {item['styleSrc']}")
                continue
            css = _CSS_COMMENT.sub("", css)
            if _MEDIA_SIZE.search(css):
                add(ERROR if strict else WARN, "R-STYLE-MEDIA", where,
                    "a size @media rule answers the browser window, not the device frame — "
                    "use @container pb-screen (min-width: …) (see pb/template/product.css)")
            scope = (".c-" if kind == "component" else ".s-") + item.get("id", "")
            for pre in _CSS_PRELUDE.findall(css):
                pre = pre.strip()
                if not pre or pre.startswith("@") or re.fullmatch(r"(from|to|[\d.]+%)(\s*,\s*(from|to|[\d.]+%))*", pre):
                    continue
                for sel in (x.strip() for x in pre.split(",")):
                    if sel and not re.match(re.escape(scope) + r"(?![\w-])", sel):
                        add(WARN, "R-STYLE-SCOPE", where,
                            f"selector {sel!r} is not scoped to {scope} — a sheet styles its own "
                            f"root class and what is inside it, never another item")
                        break
            body = _CONTAINER_PRELUDE.sub("{", css)
            for m in dict.fromkeys(_HEX.findall(body)):
                add(hex_px_sev, "R-HEX", where, f"raw hex {m} in styleSrc — use a token (Principle 2)")
            for m in dict.fromkeys(_PX.findall(body)):
                add(hex_px_sev, "R-PX", where, f"raw px {m} in styleSrc — use a token (Principle 2)")

    classes = _size_classes(meta)
    responsive = meta.get("responsive")
    if len(classes) < 2:
        return
    if responsive is None:
        # An older project that was never asked. Asking is /pb:build §1b's job, before its next
        # screen/component write — an additive field must not turn an existing project's CI red.
        return
    if responsive is False:
        add(WARN, "R-RESPONSIVE", "meta.responsive",
            f"meta.responsive is false but meta.devices spans {len(classes)} size classes — the "
            "other frames show an unadapted layout; trim meta.devices to the primary device")
        return

    texts = {}

    def text_of(item):
        key = id(item)
        if key not in texts:
            texts[key] = (_body_of(item, base_dir) or "") + "\n" + (_style_of(item, base_dir) or "")
        return texts[key]

    for i, scr in enumerate(screens):
        if not isinstance(scr, dict):
            continue
        seen, stack, adapts = set(), [scr], False
        while stack and not adapts:
            it = stack.pop()
            t = text_of(it)
            if _ADAPTS.search(t) or _R_UTIL.search(t):
                adapts = True
                break
            for oid in _PBUSE.findall(t):
                if oid not in seen and isinstance(comp_by_id.get(oid), dict):
                    seen.add(oid)
                    stack.append(comp_by_id[oid])
        if not adapts:
            add(WARN, "R-RESPONSIVE", f"screens[{i}] id={scr.get('id', '')!r}",
                f"meta.responsive is true across {', '.join(sorted(classes))} but nothing this screen "
                "renders adapts — no @container rule and no r-* size-class utility in its body, its "
                "styleSrc, or any component it composes")


def _check_token_refs(add, reg, components, screens, base_dir, resolved):
    """R-TOKENREF — a render body asks for a custom property that nothing will ever set.

    The inverse of the unused-token count in --report, and the one that actually breaks a screen:
    an unresolvable `var(--x)` makes the browser drop the whole declaration, silently, with no
    console error. It happens when a token is renamed or retired and consumers still say the old
    name, when a `$value` aliases something missing, or when a `$value` is a composite (shadow,
    typography) that a single custom property cannot hold.

    WHAT COUNTS AS A PRODUCER — getting this wrong is what makes a rule like this useless. Three
    things legitimately set a custom property, and the first draft of this rule knew only the first:
      1. the project's tokens (alias-resolved; composites are skipped, so they read as absent)
      2. the SHELL, which declares 58 of its own (`--border`, `--font-body`, `--bg-soft`, …)
      3. a render body, for a component-scoped property it sets and reads itself
         (`--pb-stat-tone-bg`) or that a parent sets inline on its root (`--pb-tt-max`)
    Resolving against (1) alone reported every golden component and both demo screens — all false.

    AND A FALLBACK CHANGES THE QUESTION. `var(--x, y)` is a deliberate statement that `--x` may be
    unset, so an absent name there is the design working, not a defect. It has exactly one failure
    mode, and it is the nastiest in this whole class: if `--x` EXISTS but resolves to nothing, the
    fallback does NOT apply — the declaration is invalid and is dropped. So:

        no fallback + no producer      -> a finding
        fallback    + resolves empty   -> a finding (the trap)
        fallback    + simply absent    -> not a finding, ever

    A name composed at runtime (`var(--bg-${tone}-muted)`) is not a name until it runs; those are
    counted and reported as information. With no shell to read the rule does not run at all — a
    check that cannot see one of its three producers is worse than no check.

    Returns the count of runtime-composed references, which --report prints as information.
    """
    shell_vars = _shell_custom_props()
    if shell_vars is None:
        return 0

    bodies = {}
    for kind, items in (("component", components), ("screen", screens)):
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            body = _body_of(item, base_dir)
            if body and "--" in body:
                bodies[(kind, i)] = body
    # Producer 3, collected across ALL bodies: the component that SETS `--pb-tt-max` on a root is
    # usually not the one that reads it.
    body_vars = set()
    for body in bodies.values():
        body_vars |= set(_CUSTOM_PROP_ANY.findall(body))
    producers = set(resolved) | shell_vars | body_vars
    empty = {n for n, v in resolved.items() if isinstance(v, str) and not v.strip()}

    dynamic = 0
    for (kind, i), body in bodies.items():
        if "var(--" not in body:
            continue
        dangling, trapped = set(), set()
        for m in _VAR_REF.finditer(body):
            name, fallback = m.group(1), bool(m.group(2))
            if not name or _VAR_DYNAMIC.search(name):
                dynamic += 1
            elif name in empty:
                trapped.add(name)
            elif not fallback and name not in producers:
                dangling.add(name)
        if not dangling and not trapped:
            continue
        item = (components if kind == "component" else screens)[i]
        where = f"{kind}s[{i}] id={item.get('id', '')!r}"
        if dangling:
            add(WARN, "R-TOKENREF", where,
                "body references var(--%s) with no fallback, and nothing sets %s — not the token "
                "document, not the shell, not any render body. The declaration is dropped silently."
                % ("), var(--".join(sorted(dangling)), "it" if len(dangling) == 1 else "them"))
        if trapped:
            add(WARN, "R-TOKENREF", where,
                "token(s) %s exist but resolve to nothing, so var(--…, fallback) does NOT fall "
                "back — a fallback applies only when a property is UNSET. Give them a value or "
                "remove them." % ", ".join(sorted(trapped)))
    return dynamic


def _check_prop_types(add, comp, where):
    """R-PROPTYPE — a collection prop whose declared type and default disagree (D-26).

    Two shapes, both measured on a real project and both wrong in the hand-off bundle a
    developer receives:
      1. type array/object, default a string   — `{"type":"array","default":"[{name:'…'}]"}`
      2. type string, default a collection lit — `{"type":"string","default":"[]"}`

    Why it matters beyond documentation: the design-system site builds a demo from
    `default`, so a component whose body does `props.rows.map(...)` gets the STRING `'[]'`
    and throws. 11 of 133 components on the real project fail exactly this way. The
    prototype is unaffected — there a parent passes real props via pbUse and the default
    never fires — which is why nothing caught it until the second site existed.
    """
    for j, pr in enumerate(comp.get("properties") or []):
        if not isinstance(pr, dict):
            continue
        typ, dflt, pid = pr.get("type"), pr.get("default"), pr.get("id", f"#{j}")
        if typ in ("array", "object") and isinstance(dflt, str):
            add(WARN, "R-PROPTYPE", f"{where} properties[{pid!r}]",
                f"type {typ!r} but default is a string ({dflt[:40]!r}…) — a demo built from "
                f"this default gets a string, not a {typ}; use a real {typ} literal")
        elif typ == "string" and isinstance(dflt, str) and _COLLECTION_LITERAL.match(dflt):
            add(WARN, "R-PROPTYPE", f"{where} properties[{pid!r}]",
                f"default {dflt[:40]!r} looks like a collection but type is 'string' — "
                f"declare \"type\":\"array\" (or \"object\") and give a real literal")


# ── the props contract: R-PROP-DECLARED · R-PROP-USED ───────────────────────────────────
# `properties[]` is what three consumers believe a component takes: the design-system site
# builds its demo and its variant grid from it, and the Figma and React hand-offs lower it
# into component properties. A body that reads a prop nobody declared, or a declared option
# the body never renders, makes all three describe a component that does not exist.
#
# WIRING props are skipped by R-PROP-DECLARED: runtime attributes a parent hands an atom to
# pass straight through (`dataNav`, `dataAction`, `id`, `className`, `full`, …). Three sources,
# none invented here: the set registry_to_figma.instance_props drops as "prototype-runtime
# attrs, not DS properties"; the id / class props logic_extract counts as DOM-handle producers
# (`idPrefix`, `cls`, `wrapClass`, `rowClass`); and the DOM's own wiring attributes (`htmlFor`,
# `href`, `tabIndex`, `roles` → data-roles). Measured: without this guard every button in the
# golden fixture and 9 of the 10 reads one real project's button makes are reported, none a variant.
_WIRING_PROP = re.compile(
    r"^(?:data[A-Z_$][\w$]*|data-[\w-]+|aria[A-Z][\w$]*|aria-[\w-]+|on[A-Z][\w$]*"
    r"|id|idPrefix|key|className|class|cls|wrapClass|rowClass|htmlFor|href|tabIndex|roles"
    r"|full|dir|gap|padding|maxWidth|grow|align|justify)$")
_OBJECT_PROTO = {"hasOwnProperty", "toString", "toLocaleString", "valueOf", "constructor",
                 "isPrototypeOf", "propertyIsEnumerable"}
# `var p = props || {};` — the body reads its props through another name.
_PROPS_ALIAS = re.compile(r"\b(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=\s*props\s*"
                          r"(?:\|\|\s*\{\s*\}\s*)?(?=[;,\n)])")
# `var { tone, size: sz, state = 'default', ...rest } = props;`
_PROPS_DESTRUCT = re.compile(r"\b(?:var|let|const)\s*\{([^}]*)\}\s*=\s*(?:props|\(\s*props\b)")
_CALL_KEYWORD_TAIL = re.compile(r"(?:^|[^\w$])(?:if|while|for|switch|catch|return|typeof|void|in|of)\s*$")
_MEMBERSHIP_TESTS = {"if", "while", "switch", "indexOf", "lastIndexOf", "includes", "has",
                     "hasOwnProperty", "test", "match", "search", "startsWith", "endsWith"}


def _blank_strings(code):
    """`code` with the inside of every '…' and "…" literal blanked to spaces, quotes kept — so a
    read scan never mistakes markup text (`'<i>props.tone</i>'`) for a read. Template literals
    are left whole: their `${…}` holes are code. Run on comment-stripped text."""
    out, i, n, q = [], 0, len(code), None
    while i < n:
        c = code[i]
        if q:
            if c == "\\" and i + 1 < n:
                out.append("  ")
                i += 2
                continue
            if c == q or c == "\n":
                q = None
                out.append(c)
            else:
                out.append(" ")
            i += 1
            continue
        if c in ("'", '"'):
            q = c
        elif c == "`":                         # copy the template through untouched
            j = i + 1
            while j < n and code[j] != "`":
                j += 2 if code[j] == "\\" else 1
            out.append(code[i:j + 1])
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _props_names(text):
    """The names `props` is read through in a body: `props` itself plus any plain alias."""
    names = {"props"}
    names |= {m.group(1) for m in _PROPS_ALIAS.finditer(text)}
    return names


def _prop_reads(text, names):
    """Every prop name a (comment-stripped) body reads: `props.x`, `props?.x`, `props['x']`, an
    alias's `p.x`, and destructured keys. Object-prototype names are not props."""
    alt = "|".join(re.escape(n) for n in sorted(names))
    rx = re.compile(r"(?<![\w$.])(?:%s)\s*(?:\?\.|\.)\s*([A-Za-z_$][\w$]*)"
                    r"|(?<![\w$.])(?:%s)\s*\[\s*(['\"])([^'\"\\]+)\2\s*\]" % (alt, alt))
    reads = set()
    for m in rx.finditer(text):
        reads.add(m.group(1) or m.group(3))
    for m in _PROPS_DESTRUCT.finditer(text):
        for part in m.group(1).split(","):
            key = re.split(r"[:=]", part, 1)[0].strip()
            if key and not key.startswith("..."):
                reads.add(key.strip("'\""))
    return reads - _OBJECT_PROTO


def _props_escape_whole(text, names):
    """True when the whole props object leaves the body — handed to a call (`helper(props)`,
    `pbUse('x', props)`, `Object.assign({}, props)`) or spread (`...props`). Its values may then
    be rendered somewhere this scan cannot see, so R-PROP-USED stays silent rather than guess."""
    alt = "|".join(re.escape(n) for n in sorted(names))
    if re.search(r"\.\.\.\s*(?:%s)\b" % alt, text):
        return True
    for m in re.finditer(r"(\(|,)\s*(?:%s)\s*(?=[,)])" % alt, text):
        before = text[:m.start()].rstrip()
        if re.match(r"[^)]*\)\s*(?:=>|\{)", text[m.end():]) or \
                re.search(r"\bfunction\s*[\w$]*\s*\([^)]*$", text[:m.end()]):
            continue              # a parameter list — `function renderCmpX(props) {`, `(props) =>`
        if m.group(1) == "(":
            if not before or not re.search(r"[\w$\])]$", before) or _CALL_KEYWORD_TAIL.search(before):
                continue          # `if (props)` is a test, not a hand-off
        return True
    return False


def _prop_passes_through(text, pid, names):
    """True when the prop's value flows into output or a child UNBRANCHED — concatenated into
    markup (`'btn--' + props.tone`, `${props.tone}`), set as an object value (`tone: props.tone`,
    a pbUse child's prop), or passed to a call. Every value then reaches the DOM, so which of
    them are styled is a question for CSS this scan cannot read; the rule stays silent."""
    alt = "|".join(re.escape(n) for n in sorted(names))
    ref = r"(?:(?:%s)\s*(?:\?\.|\.)\s*%s(?![\w$])|(?:%s)\s*\[\s*['\"]%s['\"]\s*\])" % (
        alt, re.escape(pid), alt, re.escape(pid))
    fallback = r"(?:\s*(?:\|\||\?\?)\s*(?:'[^'\n]*'|\"[^\"\n]*\"|[\w$.]+))?"

    def flows(r):
        # A value, not a test: `+ (props.state === 'x' ? …)` compares the prop, it does not
        # hand it on, so a comparison or `&&` / `?` straight after the reference disqualifies it.
        v = r + r"(?!\s*(?:[=!]==?|[<>]=?|&&|\?(?![?.])))"
        if any(re.search(p, text) for p in (
                r"\+\s*\(?\s*" + v,                              # '…' + props.x
                r + fallback + r"\s*\)?\s*\+",                   # props.x + '…'
                r"\$\{\s*" + v,                                  # `${props.x}`
                r"[\w$'\"\]]\s*:\s*\(?\s*" + v)):                # { tone: props.x } · a : props.x
            return True
        # helper(props.x) — but a membership TEST is not a hand-off: `STATES.indexOf(props.state)`
        # whitelists the value and the branch after it still decides what renders. Counting it
        # hid a real project's programme card, whose declared 'joined' state falls back to 'live'.
        for m in re.finditer(r"([\w$]+)\s*\(\s*" + r + fallback + r"\s*[,)]", text):
            if m.group(1) not in _MEMBERSHIP_TESTS:
                return True
        return False

    if flows(ref):
        return True
    # one hop through a local that HOLDS the value (any fallback after it, but not a comparison):
    # `var tone = props.tone || 'default';` · `, state = props.state || (…);` then `'x--' + tone`
    for m in re.finditer(r"(?:\b(?:var|let|const)\s+|,\s*)([A-Za-z_$][\w$]*)\s*=\s*\(?\s*" + ref
                         + r"\s*(?:\|\||\?\?|\)|[;,\n])", text):
        if flows(r"(?<![\w$.])%s(?![\w$])" % re.escape(m.group(1))):
            return True
    return False


def _option_rendered(text, pid, value, default, names):
    """Whether the body can render option `value` of prop `pid` — the R-PROP-USED test.

    Five ways a value counts as rendered, each a false-positive guard measured on a real body:
      1. it is the prop's `default` — the fall-through every `=== 'other'` branch leaves
         (golden `button`: `props.state === 'disabled'`; `'default'` is never written). With no
         `default` declared the FIRST option is the fall-through (a `ds-link` with options
         link · brand, whose body tests 'brand' only);
      2. it appears as a quoted literal anywhere in the code — a branch, a whitelist, a case;
      3. it is an object KEY — a lookup table (`var TONE = { muted: … }; TONE[props.tone]`);
      4. a boolean option (`true`/`false`, JSON or string) on a prop the body tests for
         truthiness or against a bare boolean (`if (props.dots)`, `!!props.caret`,
         `props.coverage !== false`);
      5. the prop passes through unbranched (see _prop_passes_through — checked by the caller).
    """
    v = _js_value(value)
    if default is not None and _js_value(default) == v:
        return True
    ev = re.escape(v)
    if re.search(r"(['\"`])%s\1" % ev, text):
        return True
    if re.search(r"(?:(?<![\w$.-])%s|(['\"])%s\1)\s*:(?!:)" % (ev, ev), text):
        return True
    if v in ("true", "false"):
        alt = "|".join(re.escape(n) for n in sorted(names))
        ref = r"(?:%s)\s*\.\s*%s(?![\w$])" % (alt, re.escape(pid))
        if re.search(ref + r"\s*(?:&&|\|\||\?(?![?.])|\)|[=!]==?\s*(?:true|false)\b)", text) or \
           re.search(r"!\s*" + ref, text):
            return True
    return False


def _js_value(value):
    """An option value as the body would write it: JSON booleans are `true`/`false` (Python's
    `str(True)` is 'True', which no JS body ever compares against)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _check_props(add, comp, where, body, strict):
    """R-PROP-DECLARED + R-PROP-USED for one component. Comments are stripped first, so a
    header that mentions `props.legacy` or a retired option is not read as code."""
    if not isinstance(body, str) or not body.strip():
        return
    text = strip_comments(body)          # literals kept: an option is matched against them
    bare = _blank_strings(text)          # literals blanked: markup text is never a read
    names = _props_names(bare)
    declared = {}
    for pr in comp.get("properties") or []:
        if isinstance(pr, dict):
            pid = pr.get("id") or pr.get("name")
            if isinstance(pid, str) and pid:
                declared[pid] = pr

    reads = _prop_reads(bare, names)
    undeclared = sorted(n for n in reads - set(declared)
                        if not _WIRING_PROP.match(n))
    if undeclared:
        add(ERROR if strict else WARN, "R-PROP-DECLARED", where,
            "body reads %s, which properties[] does not declare — the design-system demo and "
            "variant grid, and the Figma / React hand-offs, cannot see %s; declare each (type + "
            "default) or stop reading it" % (", ".join("props." + n for n in undeclared),
                                             "it" if len(undeclared) == 1 else "them"))

    if _props_escape_whole(bare, names):
        return
    for pid, pr in declared.items():
        opts = pr.get("options")
        if not isinstance(opts, list) or not opts or _prop_passes_through(bare, pid, names):
            continue
        default = pr.get("default")
        if default is None:
            first = opts[0].get("value") if isinstance(opts[0], dict) else opts[0]
            default = first if not isinstance(first, (dict, list)) else None
        missing = []
        for o in opts:
            val = o.get("value") if isinstance(o, dict) else o
            if val is None or isinstance(val, (dict, list)):
                continue
            if not _option_rendered(text, pid, val, default, names):
                missing.append(_js_value(val))
        if not missing:
            continue
        is_state = pid == "state"
        how = ("the body never reads props.%s at all" % pid if pid not in reads else
               "no branch, literal or lookup names %s" % ("it" if len(missing) == 1 else "them"))
        add(ERROR if (strict and is_state) else WARN, "R-PROP-USED", f"{where} properties[{pid!r}]",
            "declares %s but the body never renders %s — %s, so that cell of the variant grid "
            "paints the default%s"
            % (", ".join(repr(m) for m in missing), "it" if len(missing) == 1 else "them", how,
               " (a declared state nothing renders is a fake interactive state: branch on it, "
               "or drop the option)" if is_state else "; branch on it or drop the option"))


def check(reg, strict=False, base_dir=None):
    """Return a list of Finding for the registry dict. strict promotes hex/px to errors.

    base_dir (the registry's directory) lets the validator resolve `renderSrc` body files
    so it scans the real bodies — exactly what render.py compiles.
    """
    findings = []
    hex_px_sev = ERROR if strict else WARN
    # Component-first / atomic law: enforced (ERROR) under the strict contract (r0_hygiene / CI),
    # WARN otherwise so an un-migrated project isn't hard-broken mid-flight (NS6). R-LEVEL is
    # always ERROR — `level` is a required field like renderFn (schema 9).
    compose_sev = ERROR if strict else WARN

    def add(sev, code, where, msg):
        findings.append(Finding(sev, code, where, msg))

    # ── shape sanity ─────────────────────────────────────────────────────────
    if not isinstance(reg, dict):
        add(ERROR, "R-SHAPE", "<root>", "registry must be a JSON object")
        return findings
    for key, typ, label in (("components", list, "array"),
                            ("screens", list, "array"),
                            ("tokens", dict, "object"),
                            ("meta", dict, "object")):
        if key in reg and not isinstance(reg[key], typ):
            add(ERROR, "R-SHAPE", key, f"{key} must be a JSON {label}")

    # Re-inline anatomy/spec/usage/uiLogic from specSrc sidecars (schema 10) before the
    # anatomy-dependent checks read them; mutates `reg` in place so the loops below see them.
    _resolve_specs(add, reg, base_dir)

    components = reg.get("components") if isinstance(reg.get("components"), list) else []
    screens = reg.get("screens") if isinstance(reg.get("screens"), list) else []
    tokens = reg.get("tokens") if isinstance(reg.get("tokens"), dict) else {}

    comp_ids = set()
    comp_by_id = {}

    # ── components: kebab id, uniqueness, renderFn, render-body scans ─────────
    seen_comp = {}
    for i, c in enumerate(components):
        if not isinstance(c, dict):
            add(ERROR, "R-SHAPE", f"components[{i}]", "component must be an object")
            continue
        cid = c.get("id", "")
        where = f"components[{i}] id={cid!r}"
        if not _KEBAB.match(str(cid)):
            add(ERROR, "R-KEBAB", where, "component id must be kebab-case")
        if cid in seen_comp:
            add(ERROR, "R-DUPID", where,
                f"duplicate component id (also components[{seen_comp[cid]}]) — "
                f"ids must be unique across global+local (R4)")
        else:
            seen_comp[cid] = i
        comp_ids.add(cid)
        comp_by_id.setdefault(cid, c)
        _check_renderfn(add, c, "renderCmp", where)
        if c.get("level") not in LEVEL_ENUM:
            add(ERROR, "R-LEVEL", where,
                f"level {c.get('level')!r} missing or not in {sorted(LEVEL_ENUM)} — required (schema 9)")
        _check_prop_types(add, c, where)
        cbody = _resolve_body(add, c, where, base_dir)
        _scan_body(add, cbody, where, hex_px_sev)
        _check_props(add, c, where, cbody, strict)

    # ── anatomy nesting: declared globals must be instanced (R-NEST / R-NEST-HINT) ──
    # Mirrors screens[].elements[].orgId (R-ORGID): a component anatomy part that IS a
    # reused global declares it via `orgId`, so the Figma hand-off nests an INSTANCE of
    # the global instead of baking a copy (constitution Principle 10). The hand-off can't
    # infer reuse from the render JS, so the registry must make it explicit. The matching
    # terms are DERIVED from the registry's actual global ids — no hardcoded names.
    global_ids = {cid for cid, c in comp_by_id.items()
                  if isinstance(c, dict) and c.get("scope") == "global"}
    # R-NEST-HINT stays scoped to GLOBALS. D-10 makes a local orgId legal, but the hint's job
    # is DS instance reuse in the Figma hand-off, which is a global concern; widening it to
    # every component turned 12 hints into 64 on a real project — precise, and exactly the
    # noise D-22 exists to remove. The local-child case is served by making it legal (above)
    # and by --sync-elements for the screen half.
    # Sorted longest-first so the most specific id wins (see _hint_component).
    all_ids_by_len = sorted((cid for cid in comp_by_id if isinstance(cid, str)),
                            key=lambda s: (-len(s.split("-")), -len(s), s))
    for i, c in enumerate(components):
        if not isinstance(c, dict):
            continue
        cid = c.get("id", "")
        # Either shape: legacy anatomy.parts[] or the schema-13 measured anatomy, whose
        # `instance` parts carry their component as `instanceOf` (read here as orgId).
        new_shape = _parts.label(c) != "anatomy.parts[]"
        for p in _parts.parts(c):
            where = f"components[{i}] id={cid!r} part#{p.get('n')}" + (f" ({p.get('name')})" if new_shape else "")
            org = p.get("orgId")
            if org is not None:
                # D-10: an orgId may reference ANY registry component, local or global.
                # The old rule ERRORed on a local target, which contradicted R-COMPOSE-MATCH
                # by construction: on a real project non-atom components compose 132
                # local-child edges, so of 57 components carrying the composed-not-declared
                # warning only 4 could be cleared by declaring globals — 39 were blocked
                # outright. registry_to_figma.py already lowers a non-DS child as a FRAME
                # from anatomy, so the restriction guarded nothing. The Figma publish-key
                # concern stays with R-NEST-FIGMA.
                if comp_by_id.get(org) is None:
                    add(ERROR, "R-NEST", where,
                        f"part {'instanceOf' if new_shape else 'orgId'} {org!r} resolves to no component")
            elif c.get("scope") != "global":
                # drift detector: a part that LOOKS like a component but doesn't declare it
                # Resolve against EVERY component, then emit only when the best match is a
                # global. A part named 'Toggle Input' resolves to the local `toggle-input`,
                # not the global `input` — and now that a local orgId is legal (D-10),
                # suggesting `input` there would be wrong advice. A check that would print a
                # wrong answer stays quiet instead (D-08).
                hit = _hint_component(p.get("name"), all_ids_by_len)
                if hit and hit in global_ids:
                    fix = (f"is not an instance of it — compose it with pbUse('{hit}') and re-measure "
                           f"(spec_measure.py)" if new_shape else f"has no orgId — add \"orgId\":\"{hit}\"")
                    add(WARN, "R-NEST-HINT", where,
                        f"part name {p.get('name')!r} looks like the component {hit!r} "
                        f"but {fix} to force instance reuse in the Figma hand-off")

    # ── screens: kebab id, uniqueness, renderFn, orgId refs, render-body ──────
    seen_screen = {}
    for i, s in enumerate(screens):
        if not isinstance(s, dict):
            add(ERROR, "R-SHAPE", f"screens[{i}]", "screen must be an object")
            continue
        sid = s.get("id", "")
        where = f"screens[{i}] id={sid!r}"
        if not _KEBAB.match(str(sid)):
            add(ERROR, "R-KEBAB", where, "screen id must be kebab-case")
        if sid in seen_screen:
            add(ERROR, "R-DUPID", where,
                f"duplicate screen id (also screens[{seen_screen[sid]}])")
        else:
            seen_screen[sid] = i
        _check_renderfn(add, s, "renderScreen", where)
        _scan_body(add, _resolve_body(add, s, where, base_dir), where, hex_px_sev)
        for j, el in enumerate(s.get("elements", []) or []):
            if not isinstance(el, dict):
                continue
            org = el.get("orgId")
            if org is not None and org not in comp_ids:
                add(ERROR, "R-ORGID", f"{where} elements[{j}]",
                    f"orgId {org!r} resolves to no component")

    # ── composition law: only atoms emit primitives; molecules+ compose via pbUse() ─────
    # R-COMPOSE (no inlined controls above atom level), R-COMPOSE-TEXT (prefer text atoms),
    # R-COMPOSE-MATCH (the pbUse tree matches declared elements[]/anatomy.parts[] orgIds),
    # R-LEVEL-ORDER (compose strictly lower levels; atoms are leaves). This is what lowers
    # 1:1 to a clean Figma INSTANCE tree in the bridge.
    def _declared_orgids(kind, item):
        if kind == "screen":
            return {el.get("orgId") for el in (item.get("elements") or [])
                    if isinstance(el, dict) and el.get("orgId")}
        return {p.get("orgId") for p in _parts.parts(item) if p.get("orgId")}

    for kind, items in (("component", components), ("screen", screens)):
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            where = f"{kind}s[{i}] id={item.get('id', '')!r}"
            lvl = item.get("level") or ("page" if kind == "screen" else None)
            rank = LEVEL_RANK.get(lvl)
            body = _body_of(item, base_dir)
            composed = set(_PBUSE.findall(body or ""))
            declared = _declared_orgids(kind, item)
            if lvl == "atom":
                if composed:
                    add(ERROR, "R-LEVEL-ORDER", where,
                        f"an atom composes {sorted(composed)} via pbUse — atoms are leaves; only molecules+ compose")
                continue
            if lvl is None:
                continue  # component missing level already flagged by R-LEVEL
            ctl = sorted({m.lower() for m in _CONTROL_RE.findall(body or "")})
            if ctl:
                add(compose_sev, "R-COMPOSE", where,
                    f"non-atom ({lvl}) body inlines raw control tag(s) <{'>, <'.join(ctl)}> — compose a component via pbUse() instead")
            txt = sorted({m.lower() for m in _TEXT_RE.findall(body or "")})
            if txt:
                add(WARN, "R-COMPOSE-TEXT", where,
                    f"non-atom body inlines raw text tag(s) <{'>, <'.join(txt)}> — prefer a heading/paragraph atom")
            missing = declared - composed
            extra = composed - declared
            if missing:
                add(compose_sev, "R-COMPOSE-MATCH", where,
                    f"declared component(s) {sorted(missing)} are not composed (pbUse) in the render body")
            if extra:
                add(WARN, "R-COMPOSE-MATCH", where,
                    f"body composes {sorted(extra)} not declared in "
                    f"{'elements[]' if kind == 'screen' else _parts.label(item)}")
            if rank is not None:
                for oid in sorted(composed):
                    child = comp_by_id.get(oid)
                    crank = LEVEL_RANK.get(child.get("level")) if isinstance(child, dict) else None
                    if crank is not None and crank >= rank:
                        add(compose_sev, "R-LEVEL-ORDER", where,
                            f"composes {oid!r} at level {child.get('level')!r} (>= its own {lvl!r}) — compose strictly lower levels")
                if lvl in ("molecule", "organism", "template") and not composed:
                    add(WARN, "R-LEVEL-ORDER", where,
                        f"{lvl} composes no lower-level component (no pbUse) — inlining markup that should be a component?")

    _check_styles(add, reg.get("meta") if isinstance(reg.get("meta"), dict) else {},
                  components, screens, comp_by_id, base_dir, hex_px_sev, strict)

    # ── tokens: W3C DTCG $type validity + legacy-shape + runtime-required presence ──
    # tokens is a DTCG document (flat or nested-with-aliases). Validate each token's $type
    # against the DTCG type set; flag any surviving legacy {value, kind} token; and confirm
    # the runtime-required tokens resolve (by CSS-var name, so nesting is handled).
    for name, t in tokens.items():
        if isinstance(name, str) and name.startswith("$"):
            continue
        if isinstance(t, dict) and "$value" not in t and "value" in t and "kind" in t:
            add(WARN, "R-DTCG-TYPE", f"tokens.{name}",
                "legacy {value, kind} token — run /pb:update-version to convert to DTCG {$value, $type}")
    for row in _tok.to_list(tokens):
        typ = row.get("type")
        if typ is not None and typ not in _tok.DTCG_TYPES:
            add(ERROR, "R-DTCG-TYPE", f"tokens.{'.'.join(row['path'])}",
                f"$type {typ!r} is not a W3C DTCG type ({', '.join(sorted(_tok.DTCG_TYPES))})")
    resolved = _tok.resolve(tokens)
    for req in RUNTIME_REQUIRED_TOKENS:
        if req not in resolved:
            add(WARN, "R-DANGER", "tokens",
                f"runtime-required token {req!r} is missing — the error runtime styles "
                f"with var(--{req}); add it or fresh submits show no danger border")

    # The other direction, and the one that actually breaks a screen: a body asking for a
    # custom property the token document cannot supply. R-DANGER above checks four names pb's
    # own runtime needs; this checks every name the PROJECT's bodies reference.
    _TOKENREF_DYNAMIC[0] = _check_token_refs(add, reg, components, screens, base_dir, resolved)

    # ── flow / erd shape sanity when populated ────────────────────────────────
    flow = reg.get("flow") or {}
    if isinstance(flow, dict) and flow.get("populated"):
        if not isinstance(flow.get("mermaid"), str) or not flow.get("mermaid"):
            add(WARN, "R-FLOW", "flow", "populated flow needs a non-empty mermaid string")
        if not isinstance(flow.get("stories"), list):
            add(WARN, "R-FLOW", "flow", "populated flow needs a stories[] array")
    erd = reg.get("erd") or {}
    if isinstance(erd, dict) and erd.get("populated"):
        if not isinstance(erd.get("mermaid"), str) or not erd.get("mermaid"):
            add(WARN, "R-ERD", "erd", "populated erd needs a non-empty mermaid string")
        if not isinstance(erd.get("table"), list):
            add(WARN, "R-ERD", "erd", "populated erd needs a table[] array")

    return findings


def check_nesting_figma(reg, transfer):
    """Verify every anatomy part that declares a nested global (`orgId`) has a recorded
    INSTANCE in figma-transfer.json — proof the hand-off reused the global instead of
    baking a local copy (G-FP6 invariant #7 / constitution Principle 10). Runs over the
    two committed contracts, so CI asserts it without needing the Figma plugin.

    Returns a list of Finding (R-NEST-FIGMA)."""
    findings = []

    def add(sev, code, where, msg):
        findings.append(Finding(sev, code, where, msg))

    components = reg.get("components") if isinstance(reg.get("components"), list) else []
    comp_by_id = {}
    for c in components:
        if isinstance(c, dict):
            comp_by_id.setdefault(c.get("id", ""), c)
    tcomps = transfer.get("components", {}) if isinstance(transfer, dict) else {}

    for i, c in enumerate(components):
        if not isinstance(c, dict):
            continue
        cid = c.get("id", "")
        for p in _parts.parts(c):
            org = p.get("orgId")
            if not org:
                continue
            where = f"components[{i}] id={cid!r} part#{p.get('n')} -> {org!r}"
            parent = tcomps.get(cid) or {}
            nested = (parent.get("nestedInstances") or {}) if isinstance(parent, dict) else {}
            rec = nested.get(org)
            if not isinstance(rec, dict) or not rec.get("instanceId"):
                add(ERROR, "R-NEST-FIGMA", where,
                    f"declared nested global {org!r} has no recorded instance in "
                    f"figma-transfer.components.{cid}.nestedInstances — the hand-off baked "
                    f"it in instead of instancing the global")
                continue
            # the nested instance must reuse the SAME published DS component as the global
            want = ((tcomps.get(org) or {}).get("dsMatch") or {}).get("componentKey")
            got = rec.get("componentKey")
            if want and got and want != got:
                add(ERROR, "R-NEST-FIGMA", where,
                    f"nested instance componentKey {got!r} != the global {org!r}'s DS key "
                    f"{want!r} — it instances a different component than the global reuses")
    return findings


# ── R-EXEC (--exec): run every body once, the way the page will ──────────────────────────
# `--strict` is static, so a body that throws, returns nothing, or declares a function nobody
# calls passes it (on one real project a header comment above `function renderX(){}` shipped
# past seven builders and a clean --strict, rendering `undefined`, and the project had to run its own
# node gate by hand: "run your body and assert it returns a non-empty string").
#
# The harness is node's `vm`, fed on stdin — no temp file, no shell, so a project path with
# glob syntax in it (`[HR] Project`) cannot break it. Each body is wrapped by render.py's own
# _render_fn_bodies, so the gate sees exactly the wrap decision the page gets, the comment case included.
# The shared runtime (pbFrame, pbSlot, …) loads as shipped; then pbUse is stubbed to a marker so
# a body is judged alone — a broken child fails the child, not every parent that composes it.
_EXEC_PRELUDE = r"""
var window = this, self = this;
function pbEscape(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
var __pbNoop = function () {};
var setTimeout = function () { return 0; }, clearTimeout = __pbNoop, setInterval = setTimeout,
    clearInterval = __pbNoop, requestAnimationFrame = setTimeout, cancelAnimationFrame = __pbNoop;
"""
_EXEC_STUBS = r"""
pbUse = function (id) { return '<pb-use data-id="' + pbEscape(id) + '"></pb-use>'; };
"""
_EXEC_HARNESS = r"""
'use strict';
const vm = require('vm');
const job = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const msg = (e) => String((e && e.message) || e).split('\n')[0].slice(0, 160);
const quiet = { log() {}, info() {}, warn() {}, error() {}, debug() {} };
const ctx = vm.createContext({ console: quiet });
const run = (code, name) => vm.runInContext(code, ctx, { timeout: job.ms, filename: name });
const notes = [];
run(job.prelude + '\nvar PB_REGISTRY = ' + job.registry + ';', 'pb-exec-prelude.js');
try { run(job.runtime, 'runtime.js'); } catch (e) { notes.push(['runtime.js', msg(e)]); }
run(job.stubs, 'pb-exec-stubs.js');
for (const m of job.modules) { try { run(m.js, m.src); } catch (e) { notes.push([m.src, msg(e)]); } }
const results = [];
for (const b of job.bodies) {
  const r = { key: b.key, runs: [] };
  try { run(b.js, b.src); } catch (e) { r.compile = msg(e); results.push(r); continue; }
  for (const p of b.runs) {
    try {
      const out = run('window[' + JSON.stringify(b.fn) + '](JSON.parse(' + JSON.stringify(p.props) + '))', b.src);
      r.runs.push({ label: p.label, type: out === null ? 'null' : typeof out,
                    empty: typeof out === 'string' && !out.trim() });
    } catch (e) { r.runs.push({ label: p.label, error: msg(e) }); }
  }
  results.push(r);
}
process.stdout.write(JSON.stringify({ notes, results }));
"""


def check_exec(reg, base_dir, node=None, ms=2000):
    """R-EXEC — execute every render body in Node and fail on a throw, a non-string or an empty
    string. Components run once with `{}` and once per `state` option (on their default props,
    as the design-system grid paints that cell); screens run once with `{}`.

    Opt-in (`--exec`). Node is an isolated exception to the stdlib-only core (DESIGN.md
    constraint 2), so with no `node` on PATH this returns no findings and one note saying the
    bodies were NOT executed — skipped, never passed. Returns (findings, notes)."""
    import shutil
    import subprocess
    node = node or shutil.which("node")
    if not node:
        return [], ["R-EXEC skipped — node not found on PATH; no render body was executed "
                    "(not a pass)"]
    import render as _render  # noqa: E402  (sibling; lazy — the static lint never needs it)

    findings = []

    def add(sev, code, where, msg):
        findings.append(Finding(sev, code, where, msg))

    _resolve_specs(lambda *a: None, reg, base_dir)   # usage.example feeds the state runs
    bodies, raw = [], {}
    for kind, key in (("component", "components"), ("screen", "screens")):
        items = reg.get(key) if isinstance(reg.get(key), list) else []
        for i, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("renderFn"):
                continue
            src = item.get("renderSrc")
            if src and not os.path.isfile(os.path.join(base_dir or ".", src)):
                continue                                  # R-RENDERSRC already says so
            body = _body_of(item, base_dir)
            if not src and not body:
                continue
            where = f"{kind}s[{i}] id={item.get('id', '')!r}"
            js, _missing = _render._render_fn_bodies(
                {"components": [{"renderFn": item["renderFn"], "render": body}]})
            runs = [{"label": "{}", "props": "{}"}]
            for pr in (item.get("properties") or []) if kind == "component" else []:
                if isinstance(pr, dict) and pr.get("id") == "state":
                    for o in pr.get("options") or []:
                        val = o.get("value") if isinstance(o, dict) else o
                        if val is None:
                            continue
                        props = dict(_render._default_props(item))
                        props["state"] = val
                        runs.append({"label": f"state={val}",
                                     "props": json.dumps(props, ensure_ascii=False)})
            bodies.append({"key": where, "fn": item["renderFn"], "src": src or where,
                           "js": js, "runs": runs})
            raw[where] = body
    modules = []
    for entry in reg.get("runtime") or []:
        if isinstance(entry, dict) and entry.get("src"):
            js, _tags, _miss = _render.load_runtime({"runtime": [entry]}, base_dir or ".")
            if js:
                modules.append({"src": entry["src"], "js": js})
    slim = {"meta": reg.get("meta") or {}, "tokens": reg.get("tokens") or {},
            "components": [{k: c.get(k) for k in ("id", "renderFn", "level", "scope", "properties")}
                           for c in reg.get("components") or [] if isinstance(c, dict)],
            "screens": [{k: s.get(k) for k in ("id", "renderFn", "roles")}
                        for s in reg.get("screens") or [] if isinstance(s, dict)]}
    job = {"ms": ms, "prelude": _EXEC_PRELUDE, "stubs": _EXEC_STUBS, "modules": modules,
           "runtime": _render.load_shared_runtime(), "bodies": bodies,
           "registry": json.dumps(slim, ensure_ascii=False).replace("</", "<\\/")}
    budget = 30 + sum(len(b["runs"]) for b in bodies) * ms / 1000.0
    try:
        p = subprocess.run([node, "-e", _EXEC_HARNESS], input=json.dumps(job, ensure_ascii=False),
                           capture_output=True, text=True, encoding="utf-8", timeout=budget)
        out = json.loads(p.stdout) if p.returncode == 0 else None
    except subprocess.TimeoutExpired:
        add(ERROR, "R-EXEC", "<exec>", f"node did not finish within {budget:.0f}s — blocked, not passed")
        return findings, []
    except (OSError, ValueError) as e:
        out, p = None, None
        err = str(e)
    if out is None:
        err = (p.stderr.strip().splitlines() or ["no output"])[-1] if p is not None else err
        add(ERROR, "R-EXEC", "<exec>", f"the execution gate could not run ({err[:160]}) — blocked, not passed")
        return findings, []

    notes = ["R-EXEC note: %s did not load under node (%s) — a body that calls it may fail here "
             "for that reason, not its own" % (src, why) for src, why in out.get("notes") or []]
    for r in out.get("results") or []:
        where = r.get("key", "?")
        if r.get("compile"):
            add(ERROR, "R-EXEC", where,
                f"body does not compile ({r['compile']}) — every render body shares one script in "
                f"the page, so this one takes all the others down with it")
            continue
        bad = []
        for run in r.get("runs") or []:
            if run.get("error"):
                bad.append(f"{run['label']} threw {run['error']}")
            elif run.get("type") != "string":
                bad.append(f"{run['label']} returned {run.get('type')}, not a string")
            elif run.get("empty"):
                bad.append(f"{run['label']} returned an empty string")
        if not bad:
            continue
        hint = ""
        body = raw.get(where, "")
        if "{} returned an empty string" in bad:
            hint = (" — a body that renders nothing to give helpers a scope belongs in "
                    "registry.runtime[] (runtime/*.js), not in a component")
        if any("returned undefined" in b for b in bad) and not body.lstrip().startswith("function ") \
                and strip_comments(body).lstrip().startswith("function "):
            hint = (" — the file opens with a comment, then declares `function …`: render.py wraps it "
                    "as a function BODY, so the named function is declared and never called. "
                    "Write the body as bare statements")
        add(ERROR, "R-EXEC", where, "; ".join(bad) + hint)
    return findings, notes


def _resolve_specs(add, reg, base_dir):
    """Re-inline anatomy/spec/usage/uiLogic from `specSrc` sidecars (schema 10) so the anatomy
    checks (R-NEST/R-ORGID/R-COMPOSE-MATCH) see the real parts. Mirrors render.load_specs but,
    like _resolve_body, emits an ERROR finding on a missing sidecar rather than raising."""
    if base_dir is None:
        return
    for kind in ("components", "screens"):
        items = reg.get(kind)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            src = item.get("specSrc")
            if not src:
                continue
            where = f"{kind}[id={item.get('id')!r}]"
            path = os.path.normpath(os.path.join(base_dir, src))
            try:
                with open(path, encoding="utf-8") as f:
                    for k, v in json.load(f).items():
                        item[k] = v
            except FileNotFoundError:
                add(ERROR, "R-SPECSRC", where, f"specSrc file not found: {src}")
            except json.JSONDecodeError as e:
                add(ERROR, "R-SPECSRC", where, f"specSrc is invalid JSON: {src} ({e.msg})")


def _resolve_body(add, item, where, base_dir):
    """Return the render body to scan, resolving renderSrc (v1.4 schema 4).

    Precedence: renderSrc > legacy render. Both present -> WARN (R-RENDERSRC). A
    renderSrc pointing at a missing file -> ERROR (mirrors render.py failing closed).
    """
    src = item.get("renderSrc")
    legacy = item.get("render", "")
    if not src:
        return legacy
    if legacy:
        add(WARN, "R-RENDERSRC", where,
            "both renderSrc and a legacy render string are present — renderSrc wins; "
            "remove the inline render")
    if base_dir is None:
        return legacy  # can't resolve without a path; skip body scan
    path = os.path.normpath(os.path.join(base_dir, src))
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        add(ERROR, "R-RENDERSRC", where, f"renderSrc file not found: {src}")
        return ""


def _body_of(item, base_dir):
    """Read a render body WITHOUT emitting findings — the compose pass re-reads bodies the
    id/renderFn loops already resolved (via _resolve_body), so this avoids double warnings."""
    src = item.get("renderSrc")
    if src and base_dir is not None:
        try:
            with open(os.path.normpath(os.path.join(base_dir, src)), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""
    return item.get("render", "") or ""


def _check_renderfn(add, item, prefix, where):
    fn = item.get("renderFn")
    expected = prefix + pascal(item.get("id", ""))
    if not fn:
        add(ERROR, "R-RENDERFN", where, f"missing renderFn (expected {expected!r})")
    elif fn != expected:
        add(ERROR, "R-RENDERFN", where,
            f"renderFn {fn!r} breaks the naming contract (expected {expected!r})")


def _scan_body(add, body, where, hex_px_sev):
    """Scan a render-body string for the page-killer and raw hex/px."""
    if not isinstance(body, str) or not body:
        return
    if _SCRIPT_CLOSE.search(body):
        add(ERROR, "R-SCRIPT", where,
            "render body contains a literal '</script>' — it kills the page; "
            "emit it split (e.g. '<\\/scr'+'ipt>') or via the </ -> <\\/ render escape")
    for m in dict.fromkeys(_HEX.findall(body)):  # de-dup, preserve order
        add(hex_px_sev, "R-HEX", where, f"raw hex {m} in render body — use a token (Principle 2)")
    for m in dict.fromkeys(_PX.findall(body)):
        add(hex_px_sev, "R-PX", where, f"raw px {m} in render body — use a token (Principle 2)")


def _load_json(path):
    """Load a JSON file, failing closed with a one-line R-IO/R-JSON message (no traceback)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR [R-IO] {path}: file not found", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR [R-JSON] {path}: invalid JSON (line {e.lineno}, column {e.colno}): {e.msg}",
              file=sys.stderr)
        sys.exit(2)


def _report(findings, label, ok_msg):
    """Print findings, then exit 0 (clean) / 1 (warnings) / 2 (any error)."""
    errors = [f for f in findings if f.severity == ERROR]
    warns = [f for f in findings if f.severity == WARN]
    for f in findings:
        print(f.line())
    if not findings:
        print(f"✓ {label}: {ok_msg}")
        sys.exit(0)
    print(f"{label}: {len(errors)} error(s), {len(warns)} warning(s)")
    sys.exit(2 if errors else 1)


def sync_elements(reg, path, base_dir):
    """--sync-elements (D-11): APPEND a screens[].elements[] entry per composed-but-undeclared
    component. Returns (added, undeclared_report).

    Append-only, and every rule here is load-bearing:
      * never edit, reorder or remove an existing entry — on a real project the 208 existing
        entries carry hand-written labels averaging 345 chars (111 with a date) plus token
        lists; regenerating them destroys authoring nobody can reproduce;
      * declared-but-not-composed is REPORTED, never deleted (it may be a not-yet-built part);
      * idempotent — a second run is a byte-for-byte no-op.
    Measured on a real project: 66 composed-but-undeclared, 0 declared-but-not-composed, so
    append-only clears the screen half of R-COMPOSE-MATCH completely.

    A read-modify-write of registry.json: the CALLER holds `slice.registry_lock` and loaded `reg`
    inside it (main does), and the write here is atomic.
    """
    added, stale = [], []
    for s in reg.get("screens") or []:
        if not isinstance(s, dict):
            continue
        body = _body_of(s, base_dir) or ""
        composed = set(_PBUSE.findall(body))
        els = s.setdefault("elements", [])
        declared = {e.get("orgId") for e in els if isinstance(e, dict) and e.get("orgId")}
        for oid in sorted(composed - declared):
            els.append({"id": oid, "label": f"(auto) composed {oid}",
                        "orgId": oid, "state": "default"})
            added.append((s.get("id"), oid))
        for oid in sorted(declared - composed):
            stale.append((s.get("id"), oid))
    if added:
        pbslice._write(path, reg)       # atomic; the caller holds the registry lock (see main)
    return added, stale


def _pascal_calls(text, cid):
    """True when `text` reaches component `cid` other than through pbUse — i.e. a direct
    `renderCmpX(...)` or `window['renderCmpX'](...)`. The sidebar is reached exactly this
    way from header-footer-app, and missing it is what made a naive orphan check report 36
    orphans on a project that has none."""
    return f"renderCmp{pascal(cid)}" in text


def _th(th, key, default):
    """A threshold as a number: a hand-edited memory/doctor.json value that is not one falls back to the default."""
    try:
        v = float(th.get(key, default))
    except (TypeError, ValueError):
        return float(default)
    return v if v == v else float(default)


def _resources(reg, path, base_dir, th, flag):
    """--report's `resources` block: what the project has piled up, ranked, with the fix named.

    Prints its rows and returns the "fix first" lines it earned. Measured by clean.py (the tool that
    prunes it), so the number here and the number there are one measurement. Never raises for a
    project that has no memory/, no explore/ or no .preview/ — each is just zero."""
    import clean as _clean
    base_dir = base_dir or "."
    rank = []

    # registry weight: which top-level key (and which key under meta) holds the bytes
    total = max(1, len(json.dumps(reg, ensure_ascii=False)))
    top = sorted(((len(json.dumps(v, ensure_ascii=False)), k) for k, v in reg.items()), reverse=True)
    if top:
        size, key = top[0]
        share = size / total
        # a key of a few KB is never the problem, however large its share of a small registry
        heavy = share > _th(th, "registry_key_share", 0.35) and size / 1024 > _th(th, "slice_kb", 20)
        print(f"  largest key         {key} ({size / 1024:.0f} KB, {share:.0%} of registry){flag(heavy)}")
        if heavy:
            rank.append(f"registry key '{key}' is {size / 1024:.0f} KB — {share:.0%} of registry.json, which every "
                        f"command loads; move the bulk to a sidecar (renderSrc / specSrc / logicSrc for a component "
                        f"or screen); slice.py reads one slice at a time")
    meta = reg.get("meta")
    if isinstance(meta, dict) and meta:
        msize, mkey = max((len(json.dumps(v, ensure_ascii=False)), k) for k, v in meta.items())
        print(f"  largest meta key    meta.{mkey} ({msize / 1024:.0f} KB, {msize / total:.0%} of registry)")

    data = _clean.scan(os.path.abspath(base_dir), os.path.abspath(path))
    mb = 1024 * 1024
    places = data["backups"]
    n_back = sum(v["count"] for v in places.values())
    b_bytes = sum(v["bytes"] for v in places.values())
    over_b = n_back > _th(th, "backups_count", 20) or b_bytes / mb > _th(th, "backups_mb", 50)
    print(f"  backups             {n_back:5d} ({places['memory/backups']['count']} in memory/backups/ · "
          f"{places['.pb-backups']['count']} in .pb-backups/)  {b_bytes / mb:.1f} MB{flag(over_b)}")
    if over_b:
        rank.append(f"{n_back} backups, {b_bytes / mb:.0f} MB — nothing prunes them on its own; keep the newest 10 in each place: "
                    f"clean.py --apply --keep-backups 10 (run `clean.py` first to see what it would delete)")

    op = data["open"]
    oldest = max(op, key=lambda r: r["ageDays"], default=None)
    over_o = bool(oldest) and oldest["ageDays"] > _th(th, "explore_open_days", 3)
    print(f"  explore open        {len(op):5d}" + (f"  (oldest {oldest['target']}, {oldest['ageDays']:.1f} days)" if oldest else "")
          + flag(over_o))
    if over_o:
        old = [r for r in op if r["ageDays"] > _th(th, "explore_open_days", 3)]
        rank.append(f"{len(old)} explore round(s) open more than {_th(th, 'explore_open_days', 3):g} days "
                    f"(oldest: {oldest['target']}, {oldest['ageDays']:.0f} days) — decide it, or drop it: "
                    f"explore.py reject {oldest['target']}")

    c = data["closed"]
    over_c = c["bytes"] / mb > _th(th, "explore_closed_mb", 50)
    print(f"  explore closed      {c['count']:5d} round(s)  {c['bytes'] / mb:.1f} MB{flag(over_c)}")
    if over_c:
        rank.append(f"closed explore rounds take {c['bytes'] / mb:.0f} MB in {c['count']} round(s) — keep the newest 5: "
                    f"clean.py --apply --keep-closed 5")

    log_kb = data["serverLog"]["bytes"] / 1024
    over_l = log_kb > _th(th, "server_log_kb", 1024)
    print(f"  server.log          {log_kb:8.0f} KB{flag(over_l)}")
    if over_l:
        rank.append(f".preview/server.log is {log_kb:.0f} KB — clean.py --apply trims it to its last 256 KB")

    orph = data["candidates"]["orphans"]
    if orph:
        print(f"  candidate folders   {len(orph):5d} with no open round  ⚠")
        rank.append(f"{len(orph)} render/_candidates/ folder(s) belong to no open round "
                    f"({', '.join(o['target'] for o in orph[:4])}) — clean.py --apply removes them")

    sv = data["server"]
    if sv.get("running"):
        idle = sv.get("idleSeconds")
        idle_min = idle / 60.0 if isinstance(idle, (int, float)) else None
        stuck = idle_min is not None and idle_min >= _th(th, "preview_idle_min", 60)
        print(f"  preview server      running at {sv['url']}"
              + (f", idle {idle_min:.0f} min" if idle_min is not None else "") + flag(stuck))
        if stuck:
            rank.append(f"the preview server has sat idle for {idle_min:.0f} min — serve.py --stop "
                        f"(a current server stops itself when idle; this one predates that, or was started with --idle-exit 0)")
    else:
        print("  preview server      not running")
    return rank


def report(reg, path, base_dir, findings):
    """--report (D-22): rank, never gate. Always exits 0.

    lint emits 87 flat warnings on a real project — accurate and unreadable. The product
    here is the ORDERING: which code dominates, which item carries the most, and what the
    shape metrics say. Thresholds come from an optional memory/doctor.json beside the
    registry (absent → the measured defaults below), which is what keeps this at schema 10.
    """
    import collections
    th = {"body_lines_warn": 500, "body_lines_high": 1000, "registry_kb": 500,
          "slice_kb": 20, "decisions_kb": 500,
          # the resources block (clean.py's pile): how much a project may accumulate before it is ranked
          "backups_mb": 50, "backups_count": 20, "explore_open_days": 3, "explore_closed_mb": 50,
          "server_log_kb": 1024, "registry_key_share": 0.35, "preview_idle_min": 60}
    cfg = os.path.join(base_dir or ".", "memory", "doctor.json")
    if os.path.isfile(cfg):
        try:
            th.update(json.load(open(cfg, encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            print("note: memory/doctor.json unreadable — using defaults")

    comps = reg.get("components") or []
    screens = reg.get("screens") or []
    items = [x for x in comps + screens if isinstance(x, dict)]
    bodies = {}
    for it in items:
        b = _body_of(it, base_dir)
        if b:
            bodies[it.get("id")] = b
    joined = "\n".join(bodies.values())

    print("── findings by code " + "─" * 40)
    by_code = collections.Counter(f.code for f in findings)
    for code, n in by_code.most_common():
        sev = "ERROR" if any(f.severity == ERROR for f in findings if f.code == code) else "warn"
        print(f"  {n:5d}  {code:<18s} {sev}")
    if not findings:
        print("  (none)")

    print("\n── items carrying the most " + "─" * 33)
    per_item = collections.Counter(
        m.group(1) for f in findings for m in [re.search(r"id='([^']+)'", f.where)] if m)
    for iid, n in per_item.most_common(8):
        print(f"  {n:5d}  {iid}")
    if not per_item:
        print("  (none)")

    print("\n── shape " + "─" * 51)
    reg_kb = os.path.getsize(path) / 1024 if os.path.isfile(path) else 0
    # Count each BODY FILE once. Three screens can share one renderSrc (they do on a real
    # project), and counting it per screen would report 16 oversized bodies where there are 14.
    by_src = {}
    for it in items:
        src = it.get("renderSrc") or it.get("id")
        if it.get("id") in bodies:
            by_src.setdefault(src, (it.get("id"), bodies[it["id"]]))
    lines = {ident: text.count("\n") + 1 for ident, text in by_src.values()}
    over = sorted((n, k) for k, n in lines.items() if n > th["body_lines_warn"])
    high = [x for x in over if x[0] > th["body_lines_high"]]
    biggest = max(lines.items(), key=lambda kv: kv[1], default=("—", 0))
    slices = sorted(((len(json.dumps(it, ensure_ascii=False)), it.get("id")) for it in items),
                    reverse=True)
    def flag(cond):
        return "  ⚠" if cond else ""
    print(f"  registry            {reg_kb:8.0f} KB{flag(reg_kb > th['registry_kb'])}")
    print(f"  components/screens  {len(comps):5d} / {len(screens)}")
    print(f"  tokens              {len(reg.get('tokens') or {}):5d}")
    print(f"  bodies > {th['body_lines_warn']:<4d} lines {len(over):5d}{flag(over)}"
          f"   > {th['body_lines_high']} lines: {len(high)}")
    print(f"  largest body        {biggest[0]} ({biggest[1]} lines)")
    if slices:
        print(f"  largest slice       {slices[0][1]} ({slices[0][0] / 1024:.0f} KB)"
              f"{flag(slices[0][0] / 1024 > th['slice_kb'])}")
    dec = os.path.join(base_dir or ".", "memory", "decisions.md")
    d_kb = 0
    if os.path.isfile(dec):
        d_kb = os.path.getsize(dec) / 1024
        sibs = len(glob.glob(os.path.join(glob.escape(base_dir or "."), "memory", "decisions-*.md")))
        rotated = f"  (+{sibs} rotated sibling{'s' if sibs != 1 else ''})" if sibs else ""
        print(f"  decisions log       {d_kb:8.0f} KB{flag(d_kb > th['decisions_kb'])}{rotated}")

    print("\n── resources " + "─" * 47)
    try:
        res_rank = _resources(reg, path, base_dir, th, flag)
    except Exception as e:      # rank, never gate — and never crash on a project that lacks a folder
        res_rank = []
        print(f"  (resources unavailable: {type(e).__name__}: {e})")

    print("\n── information (never a finding) " + "─" * 27)
    # Orphans. GUARDED: a component is reached by pbUse OR by a direct renderCmp* call.
    # Without the second clause this reports 36 on a project whose true count is 0.
    used = set(_PBUSE.findall(joined))
    orphans = [c.get("id") for c in comps if isinstance(c, dict)
               and c.get("id") not in used and not _pascal_calls(joined, c.get("id", ""))]
    print(f"  components reached by nothing      {len(orphans)}"
          + (f"  {orphans[:6]}" if orphans else ""))
    # Unused tokens. INFORMATION by decision: a design system ships full ramps, so an
    # unreferenced token is not a defect. Runtime-composed names are honoured.
    names = []
    _tok_walk(reg.get("tokens") or {}, "", names)
    dyn = set(re.findall(r"var\(--([a-z0-9-]*)'\s*\+", joined)) | \
          set(re.findall(r"'--([a-z0-9-]*)'\s*\+", joined))
    unref = [n for n in names
             if f"--{n}" not in joined and not any(p and n.startswith(p) for p in dyn)]
    print(f"  tokens never referenced            {len(unref)} of {len(names)}"
          f"   (a DS ships full ramps — not a defect)")
    st = reg.get("staleness")
    if isinstance(st, dict) and st and all(
            all(v == 0 for v in g.values()) for g in st.values() if isinstance(g, dict)):
        print("  staleness                          present but all zero — nothing writes it (deprecated)")

    print("\n── fix first " + "─" * 47)
    rank = []
    if any(f.severity == ERROR for f in findings):
        rank.append(f"{sum(1 for f in findings if f.severity == ERROR)} error(s) — these block --strict")
    if by_code.get("R-COMPOSE-MATCH"):
        # --sync-elements only writes screens[].elements[]; components declare theirs by hand.
        # Recommending it once the screen half is already clear sends the reader in a circle.
        screen_half = sum(1 for f in findings
                          if f.code == "R-COMPOSE-MATCH" and f.where.startswith("screens["))
        rank.append(f"{by_code['R-COMPOSE-MATCH']} R-COMPOSE-MATCH — run --sync-elements to clear "
                    f"the screen half ({screen_half})" if screen_half else
                    f"{by_code['R-COMPOSE-MATCH']} R-COMPOSE-MATCH, all on components — the screen "
                    f"half is clear; declare each component's elements[] by hand or drop the claim")
    if by_code.get("R-PROPTYPE"):
        rank.append(f"{by_code['R-PROPTYPE']} R-PROPTYPE — each one is a component that cannot demo, and wrong docs in the hand-off")
    if high:
        rank.append(f"{len(high)} body/bodies over {th['body_lines_high']} lines — use slice.py --no-prose to keep context small")
    if d_kb > th["decisions_kb"]:
        rank.append(f"decisions log at {d_kb:.0f} KB — rotate it: "
                    f"decisions_rotate.py memory/decisions.md --apply "
                    f"(whole entries, by date, verified lossless)")
    rank.extend(res_rank)
    for i, r in enumerate(rank, 1):
        print(f"  {i}. {r}")
    if not rank:
        print("  nothing ranked — clean")
    print()


def _tok_walk(node, trail, out):
    for k, v in node.items():
        if isinstance(k, str) and k.startswith("$"):
            continue
        name = f"{trail}-{k}" if trail else k
        if isinstance(v, dict) and "$value" in v:
            out.append(name)
        elif isinstance(v, dict):
            _tok_walk(v, name, out)


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__.strip())
        sys.exit(0)
    strict = "--strict" in args
    figma = "--figma" in args
    do_report = "--report" in args
    do_sync = "--sync-elements" in args
    do_exec = "--exec" in args
    args = [a for a in args if a not in ("--strict", "--figma", "--report", "--sync-elements", "--exec")]

    # --figma: cross-check the registry against figma-transfer.json (nested-global reuse).
    if figma:
        if len(args) != 2:
            sys.exit("usage: lint_registry.py --figma <registry.json> <figma-transfer.json>")
        reg = _load_json(args[0])
        transfer = _load_json(args[1])
        _report(check_nesting_figma(reg, transfer),
                "lint_registry.py --figma", f"clean — {args[0]} × {args[1]}")
        return

    if len(args) != 1:
        sys.exit("usage: lint_registry.py [--strict] [--exec] [--report] [--sync-elements] <registry.json>"
                 "  |  lint_registry.py --figma <registry.json> <figma-transfer.json>"
                 "  |  lint_registry.py --help")
    path = args[0]
    base_dir = os.path.dirname(os.path.abspath(path))

    # --sync-elements: an append-only registry write, then stop. Never combined with a report
    # run, so the numbers a report prints always describe the file as it is on disk. The registry
    # is loaded INSIDE the lock — a copy read before it could be seconds old and the write would
    # undo whatever another writer saved in between — and a held lock is refused, not ignored.
    if do_sync:
        if not os.path.isfile(path):
            _load_json(path)            # exits 2 with the R-IO line; no lock file is created for nothing
        try:
            with pbslice.registry_lock(path, "lint_registry --sync-elements"):
                added, stale = sync_elements(_load_json(path), path, base_dir)
        except pbslice.RegistryLocked as e:
            print(f"ERROR [R-LOCK] {path}: {e}", file=sys.stderr)
            sys.exit(2)
        for sid, oid in added:
            print(f"  + screens[{sid!r}].elements[]: {oid}")
        for sid, oid in stale:
            print(f"  ? screens[{sid!r}] declares {oid!r} but the body does not compose it "
                  f"— left in place; remove it by hand if it is stale")
        print(f"lint_registry.py --sync-elements: {len(added)} appended, "
              f"{len(stale)} declared-but-not-composed, 0 removed — {path}")
        sys.exit(0)

    reg = _load_json(path)
    findings = check(reg, strict=strict, base_dir=base_dir)

    # --exec: run every body in node (R-EXEC). No node → one line that says nothing ran.
    if do_exec:
        ran, notes = check_exec(reg, base_dir)
        findings += ran
        for n in notes:
            print(n)

    # --report: ranks and never gates (D-22). Always exit 0, whatever the findings say.
    if do_report:
        report(reg, path, base_dir, findings)
        sys.exit(0)

    _report(findings, "lint_registry.py --strict" if strict else "lint_registry.py", f"clean — {path}")


if __name__ == "__main__":
    main()
