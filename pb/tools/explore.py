#!/usr/bin/env python3
"""
explore.py — the executable form of /pb:explore (v2.1.0). Stdlib only.

/pb:explore used to be prose: "render a standalone preview on a temporary copy of registry.json",
"look at each one", "collect the scores as a markdown table". Nothing ran any of it, so a session
could stop at three loose HTML files on a second port, with no compare page and no scores. This
tool is the part that must not be skipped. Every exploration is one manifest,

    memory/explore/<target>.json

and one scratch tree, render/_candidates/<target>/<slot>/…, and the /pb:preview server
(serve.py) shows it at /explore/<target> on the SAME port — options side by side, rated in the
page, scores written back here.

Subcommands (all take --registry PATH, default ./registry.json):

  init <target> [--options N] [--host SCREEN] [--files A,B] [--intent TEXT] [--goal | --ia | --pages] [--force]
        Write the manifest and seed each slot's candidate files with a copy of the live bodies.
        A slot's `overlay` maps each real renderSrc → its candidate copy, so one option may
        change several bodies (a card AND the two screens that list it). `baseline` records the
        sha256 of every real body, which is what `promote` checks. --goal makes text-only slots
        for Mode B's approaches (no bodies to render). --ia makes an IA round (mode "ia"): no
        overlays, no host — the coordinator writes one structure per slot at
        memory/explore/<target>/<slot>.ia.json, and the rubric is the IA one. --pages makes a
        page round (mode "pages") for a subject that is no registry body — the tool's own
        templates, a standalone mockup: each slot is a folder, memory/explore/<target>/<slot>/,
        and its `page` (default <slot>/index.html) is what the compare page frames.
  slot <target> <slot> [--label TEXT]
        Add a slot — e.g. `opt-merge` when a pick mixes two options. It is rated like the
        others before it can be promoted; a merge never goes live on a sentence. A slot added
        here is marked `merge`, so the distance gates (below) do not compare it with its parents.
  check <target> [--shots] [--url URL] [--converge 0.85]
        Validate the manifest; every candidate exists, differs from the live body, lints, and
        RENDERS (in memory, against the real registry). Every pair of options must differ on
        ≥ 4 of the 7 axes (a problem, not a warning; goal mode only warns). --shots also
        screenshots each option at desktop and phone width into memory/explore/<target>/shots/
        (Playwright; absent → exit 3, blocked — never a pass) and fails any pair whose rendered
        structure is ≥ --converge alike: the same layout in different colours. Warns when the
        direction brief or a slot's execution plan is missing. IA mode validates the structures
        instead (job coverage, hub targets, parent chain, ≥ 3 of 5 IA axes apart) and writes nothing.
  gate <target>
        Exit 0 only when every rubric criterion × option has a 1–5 score. The scoring step is
        a gate now, not a suggestion: presenting a verdict before this passes is the failure.
  promote <target> <slot> [--force]
        Refuse unless the gate passes, the slot is a single option, and every live body still
        matches its baseline hash (someone else edited it mid-explore → refuse; --force
        overrides). Backs up the live bodies, copies the overlay over them, archives the manifest.
        IA mode: backs up registry.json, then writes ia.jobs[].screens[], ia.layers[],
        meta.navHub and ia.populated — never screens[] / components[]. Page mode: records the
        pick and archives the round — nothing goes live; the pick is built at G-DESIGN.
  reject <target>
        Nothing was chosen. Print the notes and what each option taught (for /pb:clarify to turn
        into ia.rules[]), discard the scratch, archive the manifest.
  link <target> [--open]
        The browser link the user compares and rates at — http://127.0.0.1:<port>/explore/<target>.
        Finds this project's /pb:preview server (each one records itself in .preview/server.json
        next to the registry and answers GET /__pb_health with its registry path), starts one in
        the background when none is running, and confirms the compare page and every option frame
        answer on it before printing the URL. --open also opens it in the browser. Every stop that
        shows options ends with this URL; a file path or an editor link is not a way to compare.
  list [--stale-days N]
        The open explorations — each with its age in days, and STALE once it is older than --stale-days
        (default 3): a round nobody finished is a direction the next one silently inherits. --json
        adds `ageDays` and `stale` to every entry.

Promote and reject also name the rounds still open (`stillOpen` in --json; one line otherwise), so a
round left behind is seen at the moment another one closes.

Promote and reject archive the manifest as memory/explore/_closed/<target>-<stamp>.json, move the
direction brief beside it (<target>-<stamp>.brief.md), and move the whole working folder
memory/explore/<target>/ (plans/, shots/, structures) to _closed/<target>-<stamp>/ — except a
PROMOTED IA round, whose folder lands at the stable _closed/<ia-id>/ (so /pb:plan can read the
picked <slot>.ia.json; an earlier one there is kept as _closed/<ia-id>-superseded-<stamp>/).

Exit: 0 ok · 1 refused / a check failed · 2 usage or missing input · 3 cannot run (no Playwright)
"""
import argparse
import datetime
import difflib
import hashlib
import html.parser
import importlib
import json
import os
import pathlib
import re
import shutil
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render  # noqa: E402
# Every headless browser pb opens goes through here — the machine-wide limit (see browser.py).
import browser as pbbrowser  # noqa: E402
# The registry's write path (advisory lock + atomic write). importlib because `import slice` would
# shadow the builtin of the same name in this module — serve.py does the same.
pbslice = importlib.import_module("slice")

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_CANNOT_RUN = 0, 1, 2, 3

EXPLORE_DIR = os.path.join("memory", "explore")
CANDIDATES_DIR = os.path.join("render", "_candidates")
# Where a running /pb:preview server records itself (serve.py writes it, `link` reads it). The
# project's .gitignore block already ignores .preview/ — runtime state, never a source.
SERVER_FILE = os.path.join(".preview", "server.json")
SERVER_LOG = os.path.join(".preview", "server.log")
LOG_MAX = 1024 * 1024        # server.log is appended forever; past this much, a start keeps only its tail
LOG_KEEP = 256 * 1024
STALE_DAYS = 3               # an open round older than this is STALE
_ID = re.compile(r"^[a-z0-9][a-z0-9-]*\Z")
_PBUSE = re.compile(r"pbUse\(\s*['\"]([a-z0-9][a-z0-9-]*)['\"]")

# ref-design-compare §4 — the ten criteria. /pb:explore swaps in or adds 1–2 for the brief.
DEFAULT_RUBRIC = [
    {"id": "hierarchy", "label": "Hierarchy", "prompt": "Can you name the one most important thing in 3 seconds?"},
    {"id": "navigation", "label": "Navigation clarity", "prompt": "Do you know where you are and how to get to the other areas?"},
    {"id": "density", "label": "Layout and density fit", "prompt": "Is the amount of information per screen right for its user?"},
    {"id": "components", "label": "Component choice", "prompt": "Are the controls the right tool for each job?"},
    {"id": "motion", "label": "Motion feel", "prompt": "Does motion show what changed, at the right speed, and nothing more?"},
    {"id": "legibility", "label": "Contrast and legibility", "prompt": "Can you read everything at a glance, including secondary text?"},
    {"id": "breathing", "label": "Breathing", "prompt": "Is there air where the eye rests, and grouping you can see with a squint?"},
    {"id": "consistency", "label": "Consistency and rhythm", "prompt": "Do repeated elements look and behave the same?"},
    {"id": "category-fit", "label": "Category fit", "prompt": "Would its intended user recognise it as made for them?"},
    {"id": "ship", "label": "Ship verdict", "prompt": "Would you present this as the direction? 1 no, 5 yes as is."},
]
DEVICES = {"desktop": (1280, 832, "laptop"), "phone": (429, 926, "mobile")}

# ref-design-compare §1 — the seven divergence axes, and the threshold every PAIR must clear.
# think-direction records free axes only, so a locked (absent) axis counts as equal — which is
# exactly what it is in every slot.
AXES = ("mental-model", "layout", "navigation", "component-set", "motion", "hierarchy", "contrast")
AXIS_MIN = 4
DEFAULT_CONVERGE = 0.85   # rendered-structure similarity at or above this = the same page twice

# IA mode — N groupings of the same approved jobs (hosted by /pb:clarify, run on this engine).
IA_AXES = ("scheme", "hub-shape", "depth", "layer0", "secondary")
IA_AXIS_MIN = 3
IA_SCHEMES = ("task", "role", "object", "time", "frequency")
IA_HUB_SHAPES = ("bottom-tabs", "sidebar", "hub-spoke", "stream")
IA_RUBRIC = [
    {"id": "job-coverage", "label": "Job coverage", "prompt": "Does every approved job have a screen that serves it — or a stated reason it is left out?"},
    {"id": "p1-reach", "label": "P1 jobs within 2 taps", "prompt": "Can every P1 job be started within two taps of the hub?"},
    {"id": "hub-load", "label": "Hub load", "prompt": "Does the hub carry few enough items to scan at a glance — five or fewer for bottom tabs?"},
    {"id": "label-clarity", "label": "Label clarity", "prompt": "Would a first-time user know what is behind each label before opening it?"},
    {"id": "no-orphans", "label": "No orphan screens", "prompt": "Does every screen serve a job and have a way in from the hub?"},
    {"id": "role-fit", "label": "Role fit", "prompt": "Does each role meet its own jobs first, without wading through another role's?"},
    # /pb:clarify writes 2–3 probe P1 jobs into this prompt, in this same phrasing, before sharing.
    {"id": "findability", "label": "Findability probe", "prompt": "Where would <role> tap first to <want>?"},
]


class ExploreError(Exception):
    def __init__(self, msg, code=EXIT_FAIL):
        super().__init__(msg)
        self.code = code


# ── paths + io ───────────────────────────────────────────────────────────────────

def manifest_path(base_dir, target):
    return os.path.join(base_dir, EXPLORE_DIR, target + ".json")


def brief_path(base_dir, target):
    """The direction the user approved at G-DIRECTION (think-direction §5)."""
    return os.path.join(base_dir, EXPLORE_DIR, target + ".brief.md")


def plan_path(base_dir, target, slot):
    """One slot's execution plan — the whole brief one pb-explorer executes."""
    return os.path.join(base_dir, EXPLORE_DIR, target, "plans", slot + ".md")


def ia_structure_rel(target, slot):
    return os.path.join(EXPLORE_DIR, target, slot + ".ia.json")


def page_file(base_dir, target, page):
    """A page round's option → the file its `page` names, or None when the path leaves the round's
    folder memory/explore/<target>/. A `?query` or `#hash` is the browser's, not part of the file."""
    rel = re.split(r"[?#]", page or "", 1)[0]
    root = os.path.realpath(os.path.join(base_dir, EXPLORE_DIR, target))
    path = os.path.realpath(os.path.join(root, rel))
    if path != root and not path.startswith(root + os.sep):
        return None
    return os.path.join(path, "index.html") if os.path.isdir(path) else path


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)   # atomic: the preview server may be reading it


def load_registry(reg_path):
    try:
        with open(reg_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ExploreError("registry not found: %s" % reg_path, EXIT_USAGE)


def load_manifest(base_dir, target):
    if not _ID.match(target or ""):
        raise ExploreError("not an exploration id: %r" % target, EXIT_USAGE)
    path = manifest_path(base_dir, target)
    real = os.path.realpath(path)
    if not real.startswith(os.path.realpath(os.path.join(base_dir, EXPLORE_DIR)) + os.sep):
        raise ExploreError("not an exploration id: %r" % target, EXIT_USAGE)
    try:
        with open(real, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ExploreError("no open exploration %r (expected %s)" % (target, os.path.relpath(path, base_dir)), EXIT_USAGE)


def save_manifest(base_dir, man):
    _write_json(manifest_path(base_dir, man["target"]), man)


def _open_manifests(base_dir):
    """[(manifest, path)] for every open exploration, by name."""
    root = os.path.join(base_dir, EXPLORE_DIR)
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(root, name)
        try:
            with open(path, encoding="utf-8") as f:
                man = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(man, dict) or man.get("status", "open") != "open" \
                or not _ID.match(str(man.get("target", ""))):
            continue
        out.append((man, path))
    return out


def sessions(base_dir):
    """Every open exploration, summarised — what serve.py injects as PB_EXPLORE."""
    return [{"target": man["target"], "kind": man.get("kind"), "host": man.get("host"),
             "mode": man.get("mode", "target"),
             "slots": [{"slot": o.get("slot"), "label": o.get("label") or o.get("slot")}
                       for o in man.get("options", [])]}
            for man, _path in _open_manifests(base_dir)]


def _age_days(man, path, now=None):
    """How long this round has been open, in days (a float): from `createdAt`, else the manifest file's
    own mtime. Never negative."""
    now = now or datetime.datetime.now()
    try:
        made = datetime.datetime.fromisoformat(str(man.get("createdAt")).replace("Z", "+00:00"))
        if made.tzinfo is not None:
            made = made.astimezone().replace(tzinfo=None)
    except (ValueError, TypeError):
        try:
            made = datetime.datetime.fromtimestamp(os.path.getmtime(path))
        except OSError:
            return 0.0
    return max(0.0, (now - made).total_seconds() / 86400.0)


def open_rounds(base_dir, stale_days=STALE_DAYS):
    """The open explorations with their age: [{target, mode, slots, ageDays, stale}] — `sessions()` plus
    how long each has been open. `stale` is True once a round is older than `stale_days`."""
    now = datetime.datetime.now()
    out = []
    for (man, path), row in zip(_open_manifests(base_dir), sessions(base_dir)):
        age = _age_days(man, path, now)
        row.update({"ageDays": round(age, 1), "stale": age > stale_days})
        out.append(row)
    return out


def still_open(base_dir, stale_days=STALE_DAYS):
    """[{target, ageDays, stale}] — what promote and reject report is still open after they close one."""
    return [{"target": r["target"], "ageDays": r["ageDays"], "stale": r["stale"]}
            for r in open_rounds(base_dir, stale_days)]


def _age_text(ageDays):
    return ("%dd" % round(ageDays)) if ageDays >= 1 else "today"


# ── registry lookups ─────────────────────────────────────────────────────────────

def _items(reg):
    for kind in ("screens", "components"):
        for it in reg.get(kind) or []:
            if isinstance(it, dict) and it.get("id"):
                yield kind[:-1], it


def find_item(reg, item_id):
    return next(((k, it) for k, it in _items(reg) if it["id"] == item_id), (None, None))


def _body(base_dir, src):
    try:
        with open(os.path.join(base_dir, src), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def host_screen(reg, base_dir, comp_id):
    """The first screen that composes `comp_id`, directly or through other components — where a
    component candidate is seen in context. Breadth-first, in registry order: deterministic."""
    users = {}
    for _k, it in _items(reg):
        if it.get("renderSrc"):
            for used in set(_PBUSE.findall(_body(base_dir, it["renderSrc"]))):
                users.setdefault(used, []).append(it["id"])
    screens = [s["id"] for s in reg.get("screens") or [] if isinstance(s, dict)]
    seen, frontier = {comp_id}, [comp_id]
    while frontier:
        nxt = []
        for cid in frontier:
            for parent in users.get(cid, []):
                if parent in screens:
                    return parent
                if parent not in seen:
                    seen.add(parent)
                    nxt.append(parent)
        frontier = nxt
    return screens[0] if screens else None


def candidate_path(target, slot, src):
    rel = os.path.normpath(src)
    parts = rel.split(os.sep)
    if parts and parts[0] == "render":
        parts = parts[1:]
    return os.path.join(CANDIDATES_DIR, target, slot, *parts)


# ── init / slot ──────────────────────────────────────────────────────────────────

def cmd_init(reg_path, target, options=3, host=None, files=None, intent="", goal=False, force=False,
             ia=False, pages=False):
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    reg = load_registry(reg_path)
    if not _ID.match(target or ""):
        raise ExploreError("an exploration id is kebab-case: %r" % target, EXIT_USAGE)
    if goal + ia + pages > 1:
        raise ExploreError("--goal, --ia and --pages are different rounds — pick one", EXIT_USAGE)
    if os.path.exists(manifest_path(base_dir, target)) and not force:
        raise ExploreError("an exploration of %r is already open — finish it (promote / reject) "
                           "or pass --force to start over" % target)
    if not 2 <= options <= 6:
        raise ExploreError("--options must be 2–6", EXIT_USAGE)

    kind, item = find_item(reg, target)
    srcs = []
    if ia:
        if host or files:
            raise ExploreError("an IA round has no host and no bodies — drop --host / --files", EXIT_USAGE)
        kind, host = "ia", None
        os.makedirs(os.path.join(base_dir, EXPLORE_DIR, target), exist_ok=True)
    elif pages:
        if host or files:
            raise ExploreError("a page round has no host and no bodies — drop --host / --files", EXIT_USAGE)
        kind, host = "pages", None
    elif goal:
        kind = "goal"
    else:
        if not item:
            raise ExploreError("%r is not a screen or component id — a goal sentence is "
                               "`/pb:explore \"<goal>\"`, Mode B (explore.py init --goal)" % target, EXIT_USAGE)
        if not item.get("renderSrc"):
            raise ExploreError("%r has no renderSrc body to diverge" % target, EXIT_USAGE)
        srcs.append(os.path.normpath(item["renderSrc"]))
        for extra in files or []:
            _k, other = find_item(reg, extra)
            src = os.path.normpath(other["renderSrc"]) if other and other.get("renderSrc") else os.path.normpath(extra)
            if not os.path.isfile(os.path.join(base_dir, src)):
                raise ExploreError("--files: %r is neither an item with a body nor a body file" % extra, EXIT_USAGE)
            if src not in srcs:
                srcs.append(src)
        if not host:
            host = target if kind == "screen" else host_screen(reg, base_dir, target)

    scratch = os.path.join(base_dir, CANDIDATES_DIR, target)
    if force and os.path.isdir(scratch):
        shutil.rmtree(scratch)

    opts = []
    for k in range(1, options + 1):
        slot = "opt-%d" % k
        if ia:
            opts.append({"slot": slot, "label": "", "bet": "", "axes": {},
                         "structure": ia_structure_rel(target, slot)})
            continue
        if pages:
            os.makedirs(os.path.join(base_dir, EXPLORE_DIR, target, slot), exist_ok=True)
            opts.append({"slot": slot, "label": "", "bet": "", "axes": {}, "page": slot + "/index.html"})
            continue
        overlay = {}
        for src in srcs:
            cand = candidate_path(target, slot, src)
            os.makedirs(os.path.dirname(os.path.join(base_dir, cand)), exist_ok=True)
            shutil.copyfile(os.path.join(base_dir, src), os.path.join(base_dir, cand))
            overlay[src] = cand
        opts.append({"slot": slot, "label": "", "bet": "", "axes": {}, "overlay": overlay,
                     **({"approach": ""} if goal else {})})

    man = {
        "version": 1, "target": target, "kind": kind,
        "mode": "ia" if ia else "goal" if goal else "pages" if pages else "target",
        "host": host, "intent": intent, "createdAt": _now(), "status": "open",
        "baseline": {src: _sha(os.path.join(base_dir, src)) for src in srcs},
        "options": opts, "rubric": [dict(r) for r in (IA_RUBRIC if ia else DEFAULT_RUBRIC)],
        "scores": {}, "notes": {}, "verdict": {"pick": None, "why": "", "taught": {}},
    }
    save_manifest(base_dir, man)
    return man


def cmd_slot(reg_path, target, slot, label=""):
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    man = load_manifest(base_dir, target)
    if not _ID.match(slot):
        raise ExploreError("a slot id is kebab-case: %r" % slot, EXIT_USAGE)
    if any(o["slot"] == slot for o in man["options"]):
        raise ExploreError("slot %r already exists" % slot)
    # `merge`: a slot added after the round opened refines rated options (a mixed pick), so it is
    # meant to sit close to its parents — the distance gates compare the divergent bets only.
    if man.get("mode") == "ia":
        man["options"].append({"slot": slot, "label": label, "bet": "", "axes": {}, "merge": True,
                               "structure": ia_structure_rel(target, slot)})
        save_manifest(base_dir, man)
        return man
    if man.get("mode") == "pages":
        os.makedirs(os.path.join(base_dir, EXPLORE_DIR, target, slot), exist_ok=True)
        man["options"].append({"slot": slot, "label": label, "bet": "", "axes": {}, "merge": True,
                               "page": slot + "/index.html"})
        save_manifest(base_dir, man)
        return man
    overlay = {}
    for src in man.get("baseline", {}):
        cand = candidate_path(target, slot, src)
        os.makedirs(os.path.dirname(os.path.join(base_dir, cand)), exist_ok=True)
        shutil.copyfile(os.path.join(base_dir, src), os.path.join(base_dir, cand))
        overlay[src] = cand
    man["options"].append({"slot": slot, "label": label, "bet": "", "axes": {}, "overlay": overlay,
                           "merge": True, **({"approach": ""} if man.get("mode") == "goal" else {})})
    save_manifest(base_dir, man)
    return man


# ── render (shared with serve.py) ────────────────────────────────────────────────

def option_of(man, slot):
    opt = next((o for o in man.get("options", []) if o.get("slot") == slot), None)
    if not opt:
        raise ExploreError("no slot %r in exploration %r" % (slot, man.get("target")), EXIT_USAGE)
    return opt


def render_option(reg_path, shell_path, man, slot, runtime_path=None):
    """The full prototype with one option's overlay swapped in — in memory, against the REAL
    registry and its real folder. Returns the html. Raises render.RenderError on a broken body."""
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    opt = option_of(man, slot)
    reg = load_registry(reg_path)
    with open(shell_path, encoding="utf-8") as f:
        shell = f.read()
    reg = render.load_bodies(reg, base_dir, overrides=opt.get("overlay") or {})
    reg = render.load_specs(reg, base_dir)
    logic = render.load_logic(base_dir, reg)
    rt_js, rt_deps, _missing = render.load_runtime(reg, base_dir)
    html, _m = render.build_html(reg, shell, render.plugin_version(), logic=logic,
                                 runtime_js=render.load_shared_runtime(runtime_path),
                                 project_js=rt_js, project_deps=rt_deps)
    return html


# ── check ────────────────────────────────────────────────────────────────────────

def _lint_overlay(reg, base_dir, opt):
    """lint_registry over the registry with this option's bodies swapped in; only findings on the
    items the overlay touches. Reuses the real linter rather than a second copy of its rules."""
    try:
        import lint_registry
    except ImportError:
        return []
    swap = {os.path.normpath(k): v for k, v in (opt.get("overlay") or {}).items()}
    reg = json.loads(json.dumps(reg))
    touched = set()
    for _k, it in _items(reg):
        src = it.get("renderSrc")
        if src and os.path.normpath(src) in swap:
            it["renderSrc"] = swap[os.path.normpath(src)]
            touched.add(it["id"])
    out = []
    for f in lint_registry.check(reg, strict=False, base_dir=base_dir):
        if f.severity == lint_registry.ERROR and any(t in f.where for t in touched):
            out.append("%s %s: %s" % (f.code, f.where, f.msg))
    return out


def _axis_value(axes, key):
    v = (axes or {}).get(key)
    return str(v).strip().lower() if v is not None else ""


def axis_distance(a, b, keys=AXES):
    """How many of `keys` two axis assignments differ on → (n, [differing keys]). Values compare
    lowercase and trimmed; an axis missing (or blank) on EITHER side counts as equal — a
    difference nobody recorded is not a difference."""
    diff = [k for k in keys
            if _axis_value(a, k) and _axis_value(b, k) and _axis_value(a, k) != _axis_value(b, k)]
    return len(diff), diff


def close_pairs(options, keys=AXES, minimum=AXIS_MIN):
    """Every pair of divergent slots (merge slots excluded) closer than `minimum` axes →
    [(slot_a, slot_b, n, differing)]."""
    bets = [o for o in options if not o.get("merge")]
    out = []
    for i, a in enumerate(bets):
        for b in bets[i + 1:]:
            n, diff = axis_distance(a.get("axes"), b.get("axes"), keys)
            if n < minimum:
                out.append((a.get("slot", "?"), b.get("slot", "?"), n, diff))
    return out


def _unknown_axes(options, keys):
    out = []
    for o in options:
        for k in sorted((o.get("axes") or {})):
            if k not in keys:
                out.append("%s: axes key %r is not one of %s — it counts for nothing"
                           % (o.get("slot", "?"), k, " · ".join(keys)))
    return out


class _Signature(html.parser.HTMLParser):
    """Tag names + class tokens in document order. Between <!--pbx:start--> / <!--pbx:end-->
    markers only, when any are present — that is the candidate's own subtree."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.all, self.marked, self.depth, self.seen_marker = [], [], 0, False

    def _emit(self, tag, attrs):
        toks = [tag] + ["." + c for c in sorted(set((dict(attrs).get("class") or "").split()))]
        self.all.extend(toks)
        if self.depth:
            self.marked.extend(toks)

    def handle_starttag(self, tag, attrs):
        self._emit(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._emit(tag, attrs)

    def handle_comment(self, data):
        if data.strip() == "pbx:start":
            self.depth += 1
            self.seen_marker = True
        elif data.strip() == "pbx:end" and self.depth:
            self.depth -= 1


def structure_signature(markup):
    """The structural signature of rendered markup: the sequence of tag names and class tokens,
    text and inline styles ignored — so two options that differ only in colour, copy or token
    values produce the same signature."""
    p = _Signature()
    p.feed(markup or "")
    p.close()
    return p.marked if p.seen_marker else p.all


def structure_similarity(sig_a, sig_b):
    return difflib.SequenceMatcher(None, sig_a, sig_b, autojunk=False).ratio()


def converged_pairs(signatures, threshold=DEFAULT_CONVERGE, skip=()):
    """{slot: signature} → [(a, b, ratio)] for every pair at or above `threshold`."""
    slots = [s for s in signatures if s not in set(skip)]
    out = []
    for i, a in enumerate(slots):
        for b in slots[i + 1:]:
            r = structure_similarity(signatures[a], signatures[b])
            if r >= threshold:
                out.append((a, b, r))
    return out


# ── IA mode ──────────────────────────────────────────────────────────────────────

def ia_jobs(reg):
    """The approved jobs, in the shape the compare page draws (prototype-builder.md `ia.jobs[]`)."""
    out = []
    for j in ((reg.get("ia") or {}).get("jobs") or []):
        if isinstance(j, dict) and j.get("id"):
            out.append({k: j.get(k) for k in ("id", "when", "want", "so", "roles", "priority")})
    return out


def load_ia_structure(base_dir, man, slot):
    """→ (structure dict | None, error str | None)."""
    opt = option_of(man, slot)
    rel = opt.get("structure") or ia_structure_rel(man["target"], slot)
    try:
        with open(os.path.join(base_dir, rel), encoding="utf-8") as f:
            obj = json.load(f)
    except FileNotFoundError:
        return None, "no structure at %s — the coordinator writes one per slot" % rel
    except ValueError as e:
        return None, "%s does not parse — %s" % (rel, e)
    if not isinstance(obj, dict):
        return None, "%s is not a JSON object" % rel
    return obj, None


def _is_depth(d):
    return d == "overlay" or (isinstance(d, int) and not isinstance(d, bool) and d >= 0)


def validate_ia(struct, job_ids, opt=None):
    """One IA structure against the approved jobs → (problems, warnings), unprefixed."""
    opt = opt or {}
    problems, warnings = [], []
    if not (struct.get("label") or opt.get("label") or "").strip():
        problems.append("no label — one line on what this grouping is")
    bet = (struct.get("bet") or opt.get("bet") or "").strip()
    if not bet:
        warnings.append("no bet — whose user and context is this grouping for?")
    if struct.get("scheme") not in IA_SCHEMES:
        warnings.append("scheme %r is not one of %s" % (struct.get("scheme"), " · ".join(IA_SCHEMES)))

    screens = struct.get("screens")
    if not isinstance(screens, list) or not screens:
        problems.append("no screens[]")
        screens = []
    by_id = {}
    for s in screens:
        sid = s.get("id") if isinstance(s, dict) else None
        if not isinstance(sid, str) or not _ID.match(sid):
            problems.append("a screen without a kebab-case id: %r" % (s,))
            continue
        if sid in by_id:
            problems.append("screen %r is defined twice" % sid)
        by_id[sid] = s
    known_jobs = set(job_ids)
    served = set()
    for sid, s in by_id.items():
        if not (s.get("name") or "").strip():
            warnings.append("screen %r has no name" % sid)
        depth, parent = s.get("depth"), s.get("parent")
        if not _is_depth(depth):
            problems.append("screen %r: depth %r is not 0, 1, 2 or \"overlay\"" % (sid, depth))
        elif parent not in (None, "") and parent not in by_id:
            problems.append("screen %r: parent %r does not exist in this structure" % (sid, parent))
        elif depth == 0 and parent not in (None, ""):
            problems.append("screen %r: depth 0 is a hub destination and has no parent (got %r)" % (sid, parent))
        elif depth == "overlay" and parent in (None, ""):
            problems.append("screen %r: an overlay opens over a screen — name its parent" % sid)
        elif isinstance(depth, int) and depth > 0:
            pd = (by_id.get(parent) or {}).get("depth") if parent else None
            if not parent:
                problems.append("screen %r: depth %d needs a parent at depth %d" % (sid, depth, depth - 1))
            elif pd != depth - 1:
                problems.append("screen %r: depth %d but its parent %r is at depth %r — the chain must step by one"
                                % (sid, depth, parent, pd))
            elif depth > 2:
                warnings.append("screen %r sits at depth %d — deeper than 2 is rarely found" % (sid, depth))
        jobs = s.get("jobs") or []
        if not isinstance(jobs, list):
            problems.append("screen %r: jobs must be a list of ia.jobs[] ids" % sid)
            jobs = []
        for j in jobs:
            if j not in known_jobs:
                problems.append("screen %r serves %r, which is not an approved job" % (sid, j))
        served.update(j for j in jobs if j in known_jobs)
        if not jobs:
            warnings.append("screen %r serves no job — an orphan, or a job nobody named" % sid)

    hub = struct.get("hub")
    if not isinstance(hub, dict):
        problems.append("no hub{} — the top-level navigation is the point of an IA option")
        hub = {}
    items = hub.get("items") if isinstance(hub.get("items"), list) else []
    if not items:
        problems.append("hub has no items")
    if hub.get("shape") not in IA_HUB_SHAPES:
        warnings.append("hub shape %r is not one of %s" % (hub.get("shape"), " · ".join(IA_HUB_SHAPES)))
    if hub.get("shape") == "bottom-tabs" and len(items) > 5:
        warnings.append("bottom tabs carry %d items — five is the most a tab bar holds" % len(items))
    on_hub = set()
    for it in items:
        it = it if isinstance(it, dict) else {}
        if not (it.get("label") or "").strip():
            problems.append("a hub item has no label: %r" % (it,))
        sc = it.get("screen")
        if sc not in by_id:
            problems.append("hub item %r points at screen %r, which this structure does not define"
                            % (it.get("label"), sc))
        elif by_id[sc].get("depth") != 0:
            warnings.append("hub item %r opens %r at depth %r — a hub destination is depth 0"
                            % (it.get("label"), sc, by_id[sc].get("depth")))
        on_hub.add(sc)
    for sid, s in by_id.items():
        if s.get("depth") == 0 and sid not in on_hub:
            warnings.append("screen %r is at depth 0 but no hub item opens it" % sid)

    for layer in struct.get("layers") or []:
        if not isinstance(layer, dict) or not _is_depth(layer.get("depth")):
            problems.append("layer %r: depth must be 0, 1, 2 or \"overlay\"" % (layer,))
        elif not (layer.get("purpose") or "").strip():
            warnings.append("layer %r has no purpose sentence" % layer.get("name", layer.get("depth")))

    unhandled = struct.get("unhandled") or []
    if not isinstance(unhandled, list):
        problems.append("unhandled must be a list of ia.jobs[] ids")
        unhandled = []
    for j in unhandled:
        if j not in known_jobs:
            problems.append("unhandled lists %r, which is not an approved job" % j)
        elif j in served:
            warnings.append("job %r is listed unhandled AND served by a screen" % j)
    if unhandled and not bet:
        problems.append("leaves %d job(s) unhandled (%s) with no bet saying why"
                        % (len(unhandled), ", ".join(map(str, unhandled))))
    for j in job_ids:
        if j not in served and j not in unhandled:
            problems.append("job %r is served by no screen and not listed in unhandled" % j)
    return problems, warnings


def _check_ia(base_dir, reg, man):
    problems, warnings = [], []
    job_ids = [j["id"] for j in ia_jobs(reg)]
    if not job_ids:
        problems.append("registry.json has no ia.jobs[] — /pb:clarify captures and approves the jobs "
                        "before an IA round; never invent them")
    axes = []
    for opt in man.get("options", []):
        slot = opt.get("slot", "?")
        struct, err = load_ia_structure(base_dir, man, slot)
        if err:
            problems.append("%s: %s" % (slot, err))
            continue
        p, w = validate_ia(struct, job_ids, opt)
        problems += ["%s: %s" % (slot, m) for m in p]
        warnings += ["%s: %s" % (slot, m) for m in w]
        axes.append({"slot": slot, "merge": opt.get("merge"),
                     "axes": struct.get("axes") if isinstance(struct.get("axes"), dict) else opt.get("axes")})
    warnings += _unknown_axes(axes, IA_AXES)
    for a, b, n, diff in close_pairs(axes, IA_AXES, IA_AXIS_MIN):
        problems.append("%s and %s differ on only %d of %d IA axes (%s) — two groupings that close are "
                        "one choice; sharpen one or replace it" % (a, b, n, len(IA_AXES), ", ".join(diff) or "none"))
    return problems, warnings


def ia_page(base_dir, reg, man):
    """What the compare page needs for mode "ia": every slot's parsed structure, and the approved
    jobs + roles it draws them against. Label / bet / axes fall back to the structure's own."""
    options = []
    for opt in man.get("options", []):
        struct, err = load_ia_structure(base_dir, man, opt.get("slot"))
        o = dict(opt, structure=struct, structureError=err)
        for k in ("label", "bet"):
            if not (o.get(k) or "").strip() and struct and struct.get(k):
                o[k] = struct[k]
        if not o.get("axes") and struct and isinstance(struct.get("axes"), dict):
            o["axes"] = struct["axes"]
        options.append(o)
    roles = [{"id": r.get("id"), "name": r.get("name") or r.get("id")}
             for r in ((reg.get("meta") or {}).get("roles") or []) if isinstance(r, dict) and r.get("id")]
    return {"options": options, "jobs": ia_jobs(reg), "roles": roles}


def _check_page(base_dir, man, opt):
    """One page-round option: its `page` names a file inside memory/explore/<target>/ that exists."""
    slot, page = opt.get("slot", "?"), (opt.get("page") or "").strip()
    if not page:
        return ["%s: no page — the file the compare page frames, relative to %s/" % (slot, os.path.join(EXPLORE_DIR, man["target"]))]
    f = page_file(base_dir, man["target"], page)
    if f is None:
        return ["%s: page %r leaves %s/ — an option's files live in its round's folder"
                % (slot, page, os.path.join(EXPLORE_DIR, man["target"]))]
    if not os.path.isfile(f):
        return ["%s: page missing: %s" % (slot, os.path.relpath(f, os.path.realpath(base_dir)))]
    return []


def cmd_check(reg_path, target, shell_path=None, shots=False, url=None, converge=DEFAULT_CONVERGE):
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    man = load_manifest(base_dir, target)
    reg = load_registry(reg_path)
    shell_path = shell_path or os.path.join(os.path.dirname(HERE), "template", "prototype.html")
    problems, warnings = [], []

    if not man.get("options") or len(man["options"]) < 2:
        problems.append("fewer than two options — there is nothing to compare")
    if man.get("mode") == "ia":
        p, w = _check_ia(base_dir, reg, man)
        return problems + p, warnings + w, []

    if not os.path.isfile(brief_path(base_dir, target)):
        warnings.append("no direction brief at %s — think-direction writes it, and the user approves it "
                        "at G-DIRECTION, before anything is built" % os.path.relpath(brief_path(base_dir, target), base_dir))
    for opt in man.get("options", []):
        if man.get("mode") != "goal" and not os.path.isfile(plan_path(base_dir, target, opt.get("slot", "?"))):
            warnings.append("%s: no execution plan at %s — its pb-explorer had nothing to build to"
                            % (opt.get("slot", "?"), os.path.relpath(plan_path(base_dir, target, opt.get("slot", "?")), base_dir)))
    for opt in man.get("options", []):
        slot = opt.get("slot", "?")
        if not (opt.get("label") or "").strip():
            problems.append("%s: no label — one line on what this take is" % slot)
        if not (opt.get("bet") or "").strip():
            warnings.append("%s: no bet — whose user and context is this built for?" % slot)
        if man.get("mode") == "goal":
            if not (opt.get("approach") or "").strip():
                problems.append("%s: no approach text" % slot)
            continue
        if man.get("mode") == "pages":
            problems += _check_page(base_dir, man, opt)
            continue
        overlay = opt.get("overlay") or {}
        if not overlay:
            problems.append("%s: empty overlay — nothing to render" % slot)
        changed = False
        for src, cand in overlay.items():
            cpath = os.path.join(base_dir, cand)
            if not os.path.isfile(cpath):
                problems.append("%s: candidate missing: %s" % (slot, cand))
                continue
            if _sha(cpath) != man.get("baseline", {}).get(src):
                changed = True
        if overlay and not changed:
            problems.append("%s: identical to the live body — an option that changes nothing is not an option" % slot)
        problems += ["%s: %s" % (slot, m) for m in _lint_overlay(reg, base_dir, opt)]
        try:
            render_option(reg_path, shell_path, man, slot)
        except (render.RenderError, OSError, ValueError) as e:
            problems.append("%s: does not render — %s" % (slot, e))

    opts = man.get("options", [])
    if man.get("mode") == "pages":
        files = {}
        for opt in opts:
            f = page_file(base_dir, target, opt.get("page"))
            if f and os.path.isfile(f):
                files.setdefault(_sha(f), []).append(opt["slot"])
        problems += ["%s are the same page, byte for byte — an option that repeats another is not an option"
                     % " and ".join(slots) for slots in files.values() if len(slots) > 1]

    # ref-design-compare §1 — every PAIR of bets ≥ 4 of 7 apart. Body and page mode fail on it; goal
    # mode (text approaches, nothing rendered) only warns.
    warnings += _unknown_axes(opts, AXES)
    for a, b, n, diff in close_pairs(opts):
        msg = ("%s and %s differ on only %d of 7 axes (%s) — ref-design-compare §1 wants ≥ %d: merge them "
               "and spend the freed slot on a different bet" % (a, b, n, ", ".join(diff) or "none", AXIS_MIN))
        (warnings if man.get("mode") == "goal" else problems).append(msg)

    shot_paths = []
    if shots and not problems and man.get("mode") != "goal":
        # page mode reuses the same loop: its pages load from disk (or --url), and the signature is
        # the whole body — a page round has no host chrome shared between options to fence off.
        shot_paths, markup = _screenshots(reg_path, shell_path, man, url)   # may raise EXIT_CANNOT_RUN
        sigs = {slot: structure_signature(m) for slot, m in markup.items() if m is not None}
        merges = [o["slot"] for o in opts if o.get("merge")]
        for a, b, r in converged_pairs(sigs, converge, skip=merges):
            problems.append("%s and %s are structurally the same page — same layout in different colours "
                            "(structure %.2f alike, threshold %.2f)" % (a, b, r, converge))
    return problems, warnings, shot_paths


# Evaluated in each rendered option: the host screen's markup, with the target's own output
# fenced by <!--pbx:start/end--> so the signature is the candidate's subtree, not the host chrome
# every option shares. `whole` = the option rewrote the host itself → the whole screen is the
# candidate. Anything unexpected falls back to the rendered frame.
_STRUCTURE_JS = """([host, target, whole]) => {
  try {
    const R = (typeof PB_REGISTRY !== 'undefined' && PB_REGISTRY) || null;
    const all = R ? [].concat(R.screens || [], R.components || []) : [];
    const find = id => all.find(x => x && x.id === id);
    const h = find(host), t = find(target);
    if (h && typeof window[h.renderFn] === 'function') {
      if (!whole && t && t !== h && typeof window[t.renderFn] === 'function') {
        const fn = t.renderFn, orig = window[fn];
        window[fn] = function () { return '<!--pbx:start-->' + orig.apply(this, arguments) + '<!--pbx:end-->'; };
        try {
          const out = String(window[h.renderFn]());
          if (out.indexOf('<!--pbx:start-->') !== -1) return out;
        } finally { window[fn] = orig; }
      }
      return String(window[h.renderFn]());
    }
  } catch (e) {}
  const f = document.getElementById('proto-frame');
  return f ? f.innerHTML : document.body.innerHTML;
}"""


def _screenshots(reg_path, shell_path, man, url):
    """Screenshot every option at both widths → (paths, {slot: host-screen markup}). The markup is
    read from the desktop render and feeds the structural-convergence check."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ExploreError("Playwright not installed — pip install playwright && playwright install chromium. "
                           "The screenshot gate is BLOCKED, not passed.", EXIT_CANNOT_RUN)
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    out_dir = os.path.join(base_dir, EXPLORE_DIR, man["target"], "shots")
    os.makedirs(out_dir, exist_ok=True)
    paths, markup = [], {}
    reg = load_registry(reg_path)
    srcs = {os.path.normpath(s) for o in man["options"] for s in (o.get("overlay") or {})}
    rewritten = {it["id"] for _k, it in _items(reg) if it.get("renderSrc") and os.path.normpath(it["renderSrc"]) in srcs}
    whole = man.get("host") == man["target"] or man.get("host") in rewritten
    pages = man.get("mode") == "pages"
    with sync_playwright() as p:
        try:
            browser = pbbrowser.open_browser(p, "explore")      # the machine-wide limit applies
        except Exception as e:  # noqa: BLE001 — any launch failure means we cannot look
            raise ExploreError("could not launch Chromium (%s) — playwright install chromium" % e, EXIT_CANNOT_RUN)
        for opt in man["options"]:
            for name, (w, h, device) in DEVICES.items():
                page = browser.new_page(viewport={"width": w, "height": h})
                q = "?embed=1&device=%s%s" % (device, "&screen=" + man["host"] if man.get("host") else "")
                if pages and url:
                    page.goto(url.rstrip("/") + "/explore/%s/%s" % (man["target"], opt["page"].lstrip("/")))
                elif pages:
                    entry = page_file(base_dir, man["target"], opt["page"])
                    page.goto(pathlib.Path(entry).as_uri() + re.match(r"[^?#]*(.*)", opt["page"]).group(1))
                elif url:
                    page.goto(url.rstrip("/") + "/explore/%s/%s%s" % (man["target"], opt["slot"], q))
                else:
                    html = render_option(reg_path, shell_path, man, opt["slot"])
                    page.goto("about:blank" + q)
                    page.set_content(html)
                page.wait_for_timeout(400)
                path = os.path.join(out_dir, "%s-%s.png" % (opt["slot"], name))
                page.screenshot(path=path)
                paths.append(os.path.relpath(path, base_dir))
                if name == "desktop":
                    try:
                        markup[opt["slot"]] = (page.evaluate("() => document.body ? document.body.innerHTML : ''") if pages
                                               else page.evaluate(_STRUCTURE_JS, [man.get("host"), man["target"], whole]))
                    except Exception:  # noqa: BLE001 — no markup means no convergence verdict, not a crash
                        markup[opt["slot"]] = None
                page.close()
        browser.close()
    return paths, markup


# ── gate / promote / reject ──────────────────────────────────────────────────────

def missing_scores(man):
    out = []
    for crit in man.get("rubric", []):
        for opt in man.get("options", []):
            v = (man.get("scores") or {}).get("%s:%s" % (crit["id"], opt["slot"]))
            if not (isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5):
                out.append("%s × %s" % (crit.get("label", crit["id"]), opt["slot"]))
    return out


def averages(man):
    avg = {}
    for opt in man.get("options", []):
        vals = [(man.get("scores") or {}).get("%s:%s" % (c["id"], opt["slot"])) for c in man.get("rubric", [])]
        vals = [v for v in vals if isinstance(v, int) and not isinstance(v, bool)]
        avg[opt["slot"]] = round(sum(vals) / len(vals), 2) if vals else None
    return avg


def apply_scores(man, payload):
    """Merge a {scores, notes, verdict} payload from the compare page into the manifest,
    validating every key against the manifest's own rubric and slots. Returns the manifest."""
    slots = {o["slot"] for o in man.get("options", [])}
    crits = {c["id"] for c in man.get("rubric", [])}
    scores = dict(man.get("scores") or {})
    for key, val in (payload.get("scores") or {}).items():
        crit, _, slot = str(key).partition(":")
        if crit not in crits or slot not in slots:
            raise ExploreError("unknown score key %r" % key, EXIT_USAGE)
        if val is None:
            scores.pop(key, None)
        elif isinstance(val, int) and not isinstance(val, bool) and 1 <= val <= 5:
            scores[key] = val
        else:
            raise ExploreError("score %r must be an integer 1–5" % key, EXIT_USAGE)
    notes = dict(man.get("notes") or {})
    for key, val in (payload.get("notes") or {}).items():
        if key not in crits:
            raise ExploreError("unknown note key %r" % key, EXIT_USAGE)
        notes[key] = str(val)[:2000]
    verdict = dict(man.get("verdict") or {})
    v = payload.get("verdict")
    if isinstance(v, dict):
        pick = v.get("pick")
        if pick not in (None, "", "none") and pick not in slots:
            raise ExploreError("verdict pick %r is not a slot" % pick, EXIT_USAGE)
        verdict["pick"] = pick or None
        verdict["why"] = str(v.get("why") or "")[:4000]
        verdict["taught"] = {k: str(t)[:1000] for k, t in (v.get("taught") or {}).items() if k in slots}
    man["scores"], man["notes"], man["verdict"] = scores, notes, verdict
    man["scoredAt"] = _now()
    return man


def closed_work_dir(base_dir, man, stamp):
    """Where a closed round's working folder (plans/, shots/, *.ia.json, *.approach.md) lands.
    A PROMOTED IA round lands at the stable memory/explore/_closed/<ia-id>/ — /pb:plan §2 reads
    the picked structure from there, so that path always holds the grouping the registry carries.
    Every other close is stamped, like the manifest: <target>-<stamp>/."""
    closed = os.path.join(base_dir, EXPLORE_DIR, "_closed")
    if man.get("mode") == "ia" and man.get("status") == "promoted":
        return os.path.join(closed, man["target"])
    return os.path.join(closed, "%s-%s" % (man["target"], stamp))


def _archive(base_dir, man, status):
    """Close the round: the manifest goes to memory/explore/_closed/<target>-<stamp>.json, the
    direction brief beside it as <target>-<stamp>.brief.md, and the whole working folder
    memory/explore/<target>/ (plans/, shots/, structures) to closed_work_dir() — a brief or a
    plan left open is a direction the next round silently inherits."""
    man["status"] = status
    man["closedAt"] = _now()
    stamp = man["closedAt"].replace(":", "").replace("-", "")
    closed = os.path.join(base_dir, EXPLORE_DIR, "_closed")
    name = "%s-%s" % (man["target"], stamp)
    dest = os.path.join(closed, name + ".json")
    _write_json(dest, man)
    os.remove(manifest_path(base_dir, man["target"]))
    if os.path.isfile(brief_path(base_dir, man["target"])):
        shutil.move(brief_path(base_dir, man["target"]), os.path.join(closed, name + ".brief.md"))
    work = os.path.join(base_dir, EXPLORE_DIR, man["target"])
    if os.path.isdir(work):
        to = closed_work_dir(base_dir, man, stamp)
        if os.path.exists(to):   # an earlier promoted IA round of the same id — keep it, stamped
            shutil.move(to, os.path.join(closed, "%s-superseded-%s" % (man["target"], stamp)))
        shutil.move(work, to)
    scratch = os.path.join(base_dir, CANDIDATES_DIR, man["target"])
    if os.path.isdir(scratch):
        shutil.rmtree(scratch)
    root = os.path.join(base_dir, CANDIDATES_DIR)
    if os.path.isdir(root) and not os.listdir(root):
        os.rmdir(root)
    return dest


def _promote_ia(reg_path, man, slot, force=False):
    """Write the picked grouping into the IA slice — the authored half only. Membership and
    edges stay derived; planned screens are built later by /pb:plan → /pb:build.

    A read-modify-write of registry.json, so the registry lock is held around ALL of it: the registry
    is read, validated against, backed up and written inside the lock — the backup holds exactly what
    the write replaces, and an edit saved while the grouping was being judged is not overwritten. A
    held lock is refused as an ExploreError naming the holder; the write is atomic (slice._write)."""
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    if not os.path.isfile(reg_path):
        load_registry(reg_path)                 # raises ExploreError; no lock file is made for nothing
    try:
        with pbslice.registry_lock(reg_path, "explore.py promote (ia)"):
            reg = load_registry(reg_path)
            struct, err = load_ia_structure(base_dir, man, slot)
            if err:
                raise ExploreError("%s: %s" % (slot, err))
            problems, _w = validate_ia(struct, [j["id"] for j in ia_jobs(reg)], option_of(man, slot))
            if problems and not force:
                raise ExploreError("%s no longer validates against registry.json — %s%s (re-run check; --force "
                                   "only on the user's say-so)" % (slot, "; ".join(problems[:3]), "…" if len(problems) > 3 else ""))
            stamp = _now().replace(":", "").replace("-", "")
            backup = os.path.join(base_dir, "memory", "backups", "explore-%s-%s" % (man["target"], stamp))
            os.makedirs(backup, exist_ok=True)
            shutil.copyfile(reg_path, os.path.join(backup, os.path.basename(reg_path)))

            ia = reg.setdefault("ia", {})
            added = {}
            for job in ia.setdefault("jobs", []):
                if not isinstance(job, dict) or not job.get("id"):
                    continue
                mine = [s["id"] for s in struct.get("screens") or []
                        if isinstance(s, dict) and job["id"] in (s.get("jobs") or [])]
                have = list(job.get("screens") or [])
                new = [sid for sid in mine if sid not in have]
                if new:
                    job["screens"] = have + new
                    added[job["id"]] = new
            ia["layers"] = [dict(l) for l in struct.get("layers") or [] if isinstance(l, dict)]
            ia["populated"] = True
            hub = (struct.get("hub") or {}).get("component")
            note = ""
            if hub:
                reg.setdefault("meta", {})["navHub"] = hub
            else:
                note = ("the structure names no hub component, so meta.navHub was left as it was (%r) — set it once "
                        "the hub component exists" % (reg.get("meta") or {}).get("navHub"))
            pbslice._write(reg_path, reg)
    except pbslice.RegistryLocked as e:
        raise ExploreError(str(e))
    man["verdict"] = dict(man.get("verdict") or {}, pick=slot)
    archived = _archive(base_dir, man, "promoted")
    structures = os.path.join(base_dir, EXPLORE_DIR, "_closed", man["target"])
    return {"promoted": slot, "mode": "ia", "jobs": added, "layers": len(ia["layers"]),
            "navHub": hub or None, "note": note, "files": [os.path.basename(reg_path)],
            "backup": os.path.relpath(backup, base_dir), "archived": os.path.relpath(archived, base_dir),
            "structure": os.path.relpath(os.path.join(structures, slot + ".ia.json"), base_dir),
            "drift": [], "problems": problems}


def cmd_promote(reg_path, target, slot, force=False):
    """Promote `slot` of `target` (see _promote) → the result dict, plus `stillOpen`: the rounds that
    are still open once this one is archived."""
    res = _promote(reg_path, target, slot, force)
    res["stillOpen"] = still_open(os.path.dirname(os.path.abspath(reg_path)))
    return res


def _promote(reg_path, target, slot, force=False):
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    man = load_manifest(base_dir, target)
    if man.get("mode") == "goal":
        raise ExploreError("a goal exploration has no bodies to promote — its pick feeds /pb:plan (Mode B B5)")
    if re.search(r"[+,&]", slot):
        raise ExploreError("a mixed pick (%s) is not promoted directly: add it as its own slot "
                           "(explore.py slot %s opt-merge), build it, and rate it beside the plain pick" % (slot, target))
    opt = option_of(man, slot)
    gaps = missing_scores(man)
    if gaps:
        raise ExploreError("the scoring gate has not passed — %d cell(s) unscored (%s%s)"
                           % (len(gaps), ", ".join(gaps[:4]), "…" if len(gaps) > 4 else ""))
    if man.get("mode") == "ia":
        return _promote_ia(reg_path, man, slot, force)
    if man.get("mode") == "pages":
        # A page is a mockup of the direction, not a drop-in body: nothing is copied anywhere. The
        # pick is recorded and the round archived; G-DESIGN builds it into the real files.
        man["verdict"] = dict(man.get("verdict") or {}, pick=slot)
        archived = _archive(base_dir, man, "promoted")
        page = os.path.join(archived[:-len(".json")], re.split(r"[?#]", opt.get("page") or "", 1)[0])
        return {"promoted": slot, "mode": "pages", "files": [], "backup": None, "drift": [],
                "page": os.path.relpath(page, base_dir), "archived": os.path.relpath(archived, base_dir)}
    drift = [src for src, h in (man.get("baseline") or {}).items()
             if not os.path.isfile(os.path.join(base_dir, src)) or _sha(os.path.join(base_dir, src)) != h]
    if drift and not force:
        raise ExploreError("the live body changed since this exploration started: %s. Someone else "
                           "edited it — rebase the pick onto the current file, or pass --force to "
                           "overwrite their change" % ", ".join(drift))
    stamp = _now().replace(":", "").replace("-", "")
    backup = os.path.join(base_dir, "memory", "backups", "explore-%s-%s" % (target, stamp))
    for src, cand in (opt.get("overlay") or {}).items():
        live = os.path.join(base_dir, src)
        dest = os.path.join(backup, src)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.isfile(live):
            shutil.copyfile(live, dest)
        shutil.copyfile(os.path.join(base_dir, cand), live)
    man["verdict"] = dict(man.get("verdict") or {}, pick=slot)
    archived = _archive(base_dir, man, "promoted")
    return {"promoted": slot, "files": sorted((opt.get("overlay") or {}).keys()),
            "backup": os.path.relpath(backup, base_dir), "archived": os.path.relpath(archived, base_dir),
            "drift": drift}


def cmd_reject(reg_path, target):
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    man = load_manifest(base_dir, target)
    lessons = {"target": target, "intent": man.get("intent", ""),
               "notes": man.get("notes") or {}, "taught": (man.get("verdict") or {}).get("taught") or {},
               "why": (man.get("verdict") or {}).get("why", ""), "averages": averages(man)}
    archived = _archive(base_dir, man, "rejected")
    lessons["archived"] = os.path.relpath(archived, base_dir)
    lessons["stillOpen"] = still_open(base_dir)
    return lessons


# ── link — the URL the user compares and rates at ────────────────────────────────
# Three rounds in a row ended with an editor link to a hand-built compare.html: the user could not
# open it, asked for "the link", got a file:// path, and asked again. The URL is the tool's to
# produce — found, started if need be, and checked before anyone is handed it.

def server_record(base_dir):
    """What the /pb:preview server last started for this folder wrote about itself, or None."""
    try:
        with open(os.path.join(base_dir, SERVER_FILE), encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) and isinstance(rec.get("url"), str) else None


def _get(url, timeout=5):
    """GET → (status, body); (None, "") when nothing answers."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError, ValueError):
        return None, ""


def _ours(base, reg_path):
    """True when `base` is a /pb:preview server of THIS registry — not a stale record, and not
    another project's server that took the port after ours stopped."""
    code, body = _get(base + "/__pb_health")
    if code != 200:
        return False
    try:
        reg = json.loads(body).get("registry")
    except (ValueError, AttributeError):
        return False
    return isinstance(reg, str) and os.path.realpath(reg) == os.path.realpath(reg_path)


def _claimed_port(base_dir, reg_path):
    """The port this project's own launch.json entry (preview_register.py) gives its preview — so a
    server started here keeps the URL the project already uses, instead of taking the default 8000
    another project may have claimed. None when there is no such entry or the port is busy."""
    try:
        with open(os.path.join(base_dir, ".claude", "launch.json"), encoding="utf-8") as f:
            confs = json.load(f).get("configurations") or []
    except (OSError, ValueError, AttributeError):
        return None
    real = os.path.realpath(reg_path)
    for c in confs:
        if (isinstance(c, dict) and str(c.get("name", "")).startswith("pb-preview")
                and isinstance(c.get("port"), int)
                and any(os.path.realpath(str(a)) == real for a in c.get("runtimeArgs") or [])):
            try:
                with socket.socket() as s:
                    s.bind(("127.0.0.1", c["port"]))
                return c["port"]
            except OSError:
                return None
    return None


def trim_log(path, limit=LOG_MAX, keep=LOG_KEEP):
    """.preview/server.log is appended to by every server start and never rotated. When it is over
    `limit` bytes keep only its last `keep` (from a line boundary) → the bytes dropped, else 0.
    Atomic (a temp file + os.replace); a symlink or anything that is not a regular file is left alone."""
    try:
        st = os.lstat(path)
        if not stat.S_ISREG(st.st_mode) or st.st_size <= limit:
            return 0
        with open(path, "rb") as f:
            f.seek(max(0, st.st_size - keep))
            tail = f.read()
        nl = tail.find(b"\n")
        if nl != -1 and nl + 1 < len(tail):      # the cut fell mid-line: begin at the next whole one
            tail = tail[nl + 1:]
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(tail)
        os.replace(tmp, path)
        return st.st_size - len(tail)
    except OSError:
        return 0


def _start_server(reg_path, wait=30.0):
    """Start serve.py for this registry in its own session (it outlives this command) and wait
    until it answers as ours. Its output goes to .preview/server.log (trimmed to its last 256 KB
    first when it has grown past 1 MB)."""
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    log_path = os.path.join(base_dir, SERVER_LOG)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    trim_log(log_path)
    port = _claimed_port(base_dir, reg_path)
    with open(log_path, "ab") as log:
        proc = subprocess.Popen([sys.executable, os.path.join(HERE, "serve.py"), reg_path, "--no-open"]
                                + (["--port", str(port)] if port else []),
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                cwd=base_dir, start_new_session=True)
    deadline = time.time() + wait
    while time.time() < deadline:
        if proc.poll() is not None:
            raise ExploreError("the preview server exited as it started (code %s) — see %s"
                               % (proc.returncode, SERVER_LOG), EXIT_CANNOT_RUN)
        rec = server_record(base_dir)
        if rec and rec.get("pid") == proc.pid and _ours(rec["url"].rstrip("/"), reg_path):
            return rec
        time.sleep(0.2)
    proc.terminate()
    raise ExploreError("the preview server did not answer within %ds — see %s" % (wait, SERVER_LOG),
                       EXIT_CANNOT_RUN)


def option_urls(base, man):
    """slot → the URL its frame on the compare page loads (none for goal and IA rounds: text and trees)."""
    t = urllib.parse.quote(man["target"])
    if man.get("mode") == "pages":
        return {o["slot"]: "%s/explore/%s/%s" % (base, t, (o.get("page") or "").lstrip("/"))
                for o in man.get("options", [])}
    if man.get("mode") in ("goal", "ia"):
        return {}
    q = "?embed=1" + ("&screen=" + urllib.parse.quote(man["host"]) if man.get("host") else "")
    return {o["slot"]: "%s/explore/%s/%s%s" % (base, t, urllib.parse.quote(o["slot"]), q)
            for o in man.get("options", [])}


def cmd_link(reg_path, target, open_browser=False):
    """→ {url, started, pid, options, problems}. A non-empty `problems` means the link is not ready."""
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    man = load_manifest(base_dir, target)
    rec, started = server_record(base_dir), False
    if not (rec and _ours(rec["url"].rstrip("/"), reg_path)):
        rec, started = _start_server(reg_path), True
    base = rec["url"].rstrip("/")
    url = "%s/explore/%s" % (base, urllib.parse.quote(target))
    problems = []
    code, body = _get(url, timeout=30)
    # the compare page inlines the manifest — its target and createdAt say it is THIS round
    marks = ['"target":%s' % json.dumps(target)] + (
        ['"createdAt":%s' % json.dumps(man["createdAt"])] if man.get("createdAt") else [])
    if code != 200 or not all(m in body for m in marks):
        problems.append("the compare page did not answer at %s (HTTP %s)" % (url, code))
    frames = option_urls(base, man)
    for slot, u in frames.items():
        c, b = _get(u.split("#", 1)[0], timeout=30)
        if c != 200 or "<title>pb-serve · render error</title>" in b:
            problems.append("%s: its frame does not load at %s (HTTP %s%s)"
                            % (slot, u, c, ", a render error" if c == 200 else ""))
    if open_browser and not problems:
        webbrowser.open(url)
    return {"url": url, "started": started, "pid": rec.get("pid"), "options": frames, "problems": problems}


# ── cli ──────────────────────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description="The executable half of /pb:explore.")
    ap.add_argument("--registry", default="registry.json")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("target")
    p.add_argument("--options", type=int, default=3)
    p.add_argument("--host")
    p.add_argument("--files", default="")
    p.add_argument("--intent", default="")
    p.add_argument("--goal", action="store_true")
    p.add_argument("--ia", action="store_true", help="an IA round: N groupings of the approved jobs")
    p.add_argument("--pages", action="store_true",
                   help="a page round: each option is a page under memory/explore/<target>/<slot>/ (a subject that is no registry body)")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("slot")
    p.add_argument("target")
    p.add_argument("slot")
    p.add_argument("--label", default="")
    p = sub.add_parser("check")
    p.add_argument("target")
    p.add_argument("--shots", action="store_true")
    p.add_argument("--url")
    p.add_argument("--shell")
    p.add_argument("--converge", type=float, default=DEFAULT_CONVERGE,
                   help="fail two options whose rendered structure is at least this alike (default %.2f)" % DEFAULT_CONVERGE)
    p = sub.add_parser("gate")
    p.add_argument("target")
    p = sub.add_parser("promote")
    p.add_argument("target")
    p.add_argument("slot")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("reject")
    p.add_argument("target")
    p = sub.add_parser("link", help="the browser URL of the compare-and-rate page, checked live")
    p.add_argument("target")
    p.add_argument("--open", action="store_true", dest="open_browser", help="also open it in the browser")
    p = sub.add_parser("list")
    p.add_argument("--stale-days", type=float, default=STALE_DAYS, dest="stale_days",
                   help="mark an open round STALE once it is older than this many days (default %d)" % STALE_DAYS)
    a = ap.parse_args(argv)
    reg_path = os.path.abspath(a.registry)
    base_dir = os.path.dirname(reg_path)

    def emit(obj, text):
        print(json.dumps(obj, ensure_ascii=False, indent=2) if a.json else text)

    def open_line(res):
        """The one line naming the rounds still open after a promote or reject (nothing when none)."""
        if not a.json and res.get("stillOpen"):
            print("  still open: %s — promote or reject each once it is decided" % ", ".join(
                "%s (%s%s)" % (r["target"], _age_text(r["ageDays"]), ", STALE" if r.get("stale") else "")
                for r in res["stillOpen"]))

    try:
        if a.cmd == "init":
            man = cmd_init(reg_path, a.target, a.options, a.host,
                           [f for f in a.files.split(",") if f.strip()], a.intent, a.goal, a.force, a.ia, a.pages)
            if man["mode"] == "ia":
                emit(man, "✓ IA round %r: %d slots (%s)\n  manifest   %s\n  structures %s\n"
                          "  next: write one structure per slot, then `explore.py check %s`" % (
                              a.target, len(man["options"]), ", ".join(o["slot"] for o in man["options"]),
                              os.path.relpath(manifest_path(base_dir, a.target), base_dir),
                              ", ".join(o["structure"] for o in man["options"]), a.target))
                return EXIT_OK
            emit(man, "✓ exploration %r: %d slots (%s)%s\n  manifest  %s\n  candidates %s\n"
                      "  next: write the brief, pass G-DIRECTION, write plans/<slot>.md, dispatch one "
                      "pb-explorer per plan, then `explore.py check %s`" % (
                          a.target, len(man["options"]), ", ".join(o["slot"] for o in man["options"]),
                          ", host screen " + man["host"] if man.get("host") else "",
                          os.path.relpath(manifest_path(base_dir, a.target), base_dir),
                          os.path.join(CANDIDATES_DIR, a.target) if man["mode"] == "target"
                          else "— (text-only slots)" if man["mode"] == "goal"
                          else "%s/<slot>/index.html — one page per slot (set `page` to name another file)"
                          % os.path.join(EXPLORE_DIR, a.target),
                          a.target))
        elif a.cmd == "slot":
            cmd_slot(reg_path, a.target, a.slot, a.label)
            emit({"slot": a.slot}, "✓ slot %s added to %s — build it, then rate it beside the others" % (a.slot, a.target))
        elif a.cmd == "check":
            if not 0 < a.converge <= 1:
                raise ExploreError("--converge is a similarity ratio in (0, 1]", EXIT_USAGE)
            problems, warnings, shots = cmd_check(reg_path, a.target, a.shell, a.shots, a.url, a.converge)
            mode = load_manifest(base_dir, a.target).get("mode")
            ok = ("✓ every %s — next: `explore.py link %s --open`, and give the user the URL it prints"
                  % ({"ia": "structure validates", "pages": "option's page is in place"}.get(mode, "option renders"),
                     a.target))
            emit({"problems": problems, "warnings": warnings, "shots": shots},
                 "\n".join(["✗ " + m for m in problems] + ["⚠ " + m for m in warnings] + ["  shot " + s for s in shots]
                           + [ok if not problems else "✗ %d problem(s) — fix them before presenting anything" % len(problems)]))
            return EXIT_FAIL if problems else EXIT_OK
        elif a.cmd == "gate":
            man = load_manifest(base_dir, a.target)
            gaps = missing_scores(man)
            emit({"missing": gaps, "averages": averages(man)},
                 ("✗ scoring gate: %d of %d cells unscored — the user rates them at the URL `explore.py link %s` prints\n  %s" % (
                     len(gaps), len(man["rubric"]) * len(man["options"]), a.target, "\n  ".join(gaps[:12])))
                 if gaps else "✓ scoring gate passed — averages %s" % averages(man))
            return EXIT_FAIL if gaps else EXIT_OK
        elif a.cmd == "promote":
            res = cmd_promote(reg_path, a.target, a.slot, a.force)
            if res.get("mode") == "ia":
                emit(res, "✓ promoted %s → registry.json ia slice\n  jobs     %s\n  layers   %d (replaced)\n"
                          "  navHub   %s\n  backup   %s\n  archived %s\n  picked   %s%s\n"
                          "  next: /pb:plan builds the planned screens — screens[] was not touched" % (
                              res["promoted"],
                              "; ".join("%s += %s" % (j, ", ".join(s)) for j, s in sorted(res["jobs"].items())) or "no new screens",
                              res["layers"], res["navHub"] or "unchanged", res["backup"], res["archived"],
                              res["structure"], "\n  note     " + res["note"] if res["note"] else ""))
                open_line(res)
                return EXIT_OK
            if res.get("mode") == "pages":
                emit(res, "✓ picked %s — nothing went live: a page round's pick is built into the real files "
                          "after G-DESIGN\n  page     %s\n  archived %s" % (res["promoted"], res["page"], res["archived"]))
                open_line(res)
                return EXIT_OK
            emit(res, "✓ promoted %s → %s\n  backup   %s\n  archived %s%s" % (
                res["promoted"], ", ".join(res["files"]), res["backup"], res["archived"],
                "\n  ⚠ overwrote a concurrent edit (--force): %s" % ", ".join(res["drift"]) if res["drift"] else ""))
            open_line(res)
        elif a.cmd == "reject":
            res = cmd_reject(reg_path, a.target)
            emit(res, "✓ nothing promoted; scratch discarded, manifest archived at %s\n"
                      "  lessons for /pb:clarify → ia.rules[]:\n%s" % (
                          res["archived"], json.dumps({k: res[k] for k in ("notes", "taught", "why")},
                                                      ensure_ascii=False, indent=2)))
            open_line(res)
        elif a.cmd == "link":
            res = cmd_link(reg_path, a.target, a.open_browser)
            n = len(res["options"])
            emit(res, "\n".join(
                [res["url"]] + ["  ✗ " + m for m in res["problems"]]
                + (["✗ the link is not ready — fix the above and run link again; never hand the user a file path instead"]
                   if res["problems"] else
                   ["  ✓ the compare page%s answer%s on the /pb:preview server (pid %s%s)%s" % (
                       " and %d option frame%s" % (n, "s" if n != 1 else "") if n else "", "" if n else "s",
                       res["pid"], ", started now in the background" if res["started"] else "",
                       " · opened in the browser" if a.open_browser else ""),
                    "  give the user this URL on its own line — it is where they compare and rate"])))
            return EXIT_FAIL if res["problems"] else EXIT_OK
        elif a.cmd == "list":
            ss = open_rounds(base_dir, a.stale_days)
            emit(ss, "\n".join("%s  %s  %s  · open %s%s" % (
                s["target"], s["mode"], " · ".join(o["slot"] for o in s["slots"]),
                _age_text(s["ageDays"]), " · STALE" if s["stale"] else "") for s in ss) or "no open explorations")
    except ExploreError as e:
        print("✗ " + str(e), file=sys.stderr)
        return e.code
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
