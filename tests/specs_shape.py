#!/usr/bin/env python3
"""
specs_shape.py — schema 12 → 13 (migration 0011): component spec sidecars in the Specs-plugin shape.

  1. Pure mode: a structured anatomy.parts[] / spec.stack[] becomes anatomy{part:{type}} + layout +
     elements; orgId → instance + instanceOf; required:false → visibleWhen (optional is derived from
     its presence); anchor kept on the element; the whole original kept under `legacy`.
  2. Prose strings become anatomyNote / specNote, verbatim.
  3. down() restores the legacy keys exactly; up→down→up is stable; up is idempotent.
  4. A measurement written after the migration survives down→up (parked under `schema13`).
  5. File mode rewrites only component sidecars, only when something changes; screens untouched.
  6. The runner: dry-run writes nothing; --apply converts and stamps 13; --to 12 restores the
     sidecars byte-for-byte.
  7. 0011 is in the chain, the chain reaches CURRENT_SCHEMA, the template carries it — and a schema-12
     registry still gets its gap banner (from_v < CURRENT_SCHEMA, the pending describe() line).
  8. No silent skip after migrating: the readers of the old shape read the new one too.
     lint R-COMPOSE-MATCH still FAILS a migrated sidecar whose instanceOf set mismatches the body's
     pbUse calls (and passes a matching one); R-NEST still catches an instanceOf naming nothing;
     logic_check L-ANATOMY fires on the same mismatch; registry_to_figma lowers the instances.

  9. up→down→up is LOSSLESS for a sidecar that already carries new-shape keys (any subset of them)
     beside a legacy `spec.stack` / `anatomy.parts[]`: the derivation never overwrites or adds to a
     sidecar that has a new key, and down() parks the whole new-shape set unless up() would rebuild
     exactly it.
 10. The runner backs up and restores the spec sidecars (round 3). `--apply` snapshots
     `spec/components` + `spec/screens` next to the registry backup; `--rollback` puts them back with
     the registry; a failed chain, a failed validation, a failed registry write and a failed
     prototype.html write each leave registry.json AND every sidecar byte-identical to before (files a
     migration created are removed); a second writer holding the registry lock is refused before
     anything — not even a backup — is written.

Usage: python3 tests/specs_shape.py  ·  Exit 0 = all passed · 1 = a failure.
"""
import contextlib
import copy
import importlib.util
import io
import itertools
import json
import os
import subprocess
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGDIR = os.path.join(ROOT, "pb", "migrations")
RUNNER = os.path.join(MIGDIR, "migrate_runner.py")
TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem, os.path.join(MIGDIR, stem + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mig = _load("0011_specs_shape")
man = _load("manifest")

CARD_ANATOMY = {"renderProps": {"title": "Sign in"}, "parts": [
    {"n": 2, "name": "Subtitle", "anchor": ".card__sub", "orgId": "paragraph", "required": False},
    {"n": 1, "name": "Title", "anchor": ".card__title", "orgId": "heading", "required": True},
    {"n": 3, "name": "Close icon", "anchor": ".card__x", "required": True,
     "token": {"name": "--ink", "value": "#111", "kind": "color"}}]}
CARD_SPEC = {"renderProps": {}, "marginX": 0, "legend": [{"color": "#f97316", "label": "Element height"}],
             "stack": [{"name": "Title", "anchor": ".card__title"}, {"name": "Footer", "anchor": ".card__foot"}]}


def fixture():
    return {"meta": {"schemaVersion": 12}, "components": [
        {"id": "login-card", "level": "organism", "anatomy": copy.deepcopy(CARD_ANATOMY),
         "spec": copy.deepcopy(CARD_SPEC), "usage": {"example": {"title": "Sign in"}}},
        {"id": "button", "level": "atom", "anatomy": "A pressable action.", "spec": "44px tall."},
        {"id": "plain", "level": "atom"}],
        "screens": [{"id": "home", "anatomy": {"parts": [{"name": "Hero"}]}}]}


print("1 · pure mode: structured legacy → the new shape")
up = mig.up(fixture())
card = next(c for c in up["components"] if c["id"] == "login-card")
check(up["meta"]["schemaVersion"] == 13, "stamps schemaVersion 13")
check(card["anatomy"]["root"] == {"type": "container"}, "a root container part is added")
check(card["anatomy"]["title"] == {"type": "instance", "instanceOf": "heading"}, "orgId → instance + instanceOf")
check(card["anatomy"]["close-icon"]["type"] == "glyph", "an icon part is typed glyph")
check(card["layout"] == [{"root": ["title", "subtitle", "close-icon", "footer"]}],
      "layout follows n, then spec.stack names anatomy did not have")
check("visibleWhen" in card["elements"]["subtitle"] and "visibleWhen" not in card["elements"]["title"],
      "required:false → visibleWhen; required:true has none (optional is derived from presence)")
check(card["elements"]["title"].get("anchor") == ".card__title", "the anchor is kept on the element")
check(card["legacy"] == {"anatomy": CARD_ANATOMY, "spec": CARD_SPEC}, "the whole legacy objects kept under `legacy`")
check("spec" not in card and card["usage"] == {"example": {"title": "Sign in"}}, "spec moved out; other keys untouched")

print("2 · prose strings become notes")
btn = next(c for c in up["components"] if c["id"] == "button")
check(btn.get("anatomyNote") == "A pressable action." and btn.get("specNote") == "44px tall.", "anatomyNote / specNote verbatim")
check("anatomy" not in btn and "spec" not in btn and "legacy" not in btn, "no empty new-shape keys invented")
check(next(c for c in up["components"] if c["id"] == "plain") == {"id": "plain", "level": "atom"}, "a component with nothing is untouched")
check(up["screens"] == fixture()["screens"], "screens are not converted")

print("3 · down restores; up→down→up stable; idempotent")
down = mig.down(copy.deepcopy(up))
check(down == fixture(), "down(up(x)) == x")
check(mig.up(mig.down(mig.up(fixture()))) == up, "up→down→up is stable")
check(mig.up(copy.deepcopy(up)) == up, "up on an already-converted registry changes nothing but the stamp")

print("4 · a later measurement survives a round trip")
measured = copy.deepcopy(up)
c = next(x for x in measured["components"] if x["id"] == "login-card")
c["elements"]["root"]["styles"] = {"padding": {"top": 16, "right": 16, "bottom": 16, "left": 16, "token": "space-4"}}
c["shape"] = "card"
d = mig.down(copy.deepcopy(measured))
dc = next(x for x in d["components"] if x["id"] == "login-card")
check(dc["anatomy"] == CARD_ANATOMY and dc["spec"] == CARD_SPEC, "down still restores the legacy keys")
check("schema13" in dc and dc["schema13"].get("shape") == "card", "the measurement is parked under `schema13`")
check(mig.up(d) == measured, "and up() brings it back unchanged")
fresh = {"meta": {"schemaVersion": 13}, "components": [{"id": "x", "anatomy": {"root": {"type": "container"}},
                                                       "layout": [{"root": []}], "elements": {"root": {"parent": None}}}]}
check(mig.up(mig.down(copy.deepcopy(fresh))) == fresh, "a sidecar born at 13 (no legacy) round-trips too")

print("5 · file mode: only component sidecars, only when changed")
with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, "spec", "components"))
    os.makedirs(os.path.join(tmp, "spec", "screens"))
    reg = {"meta": {"schemaVersion": 12}, "components": [
        {"id": "login-card", "specSrc": "spec/components/login-card.json"},
        {"id": "button", "specSrc": "spec/components/button.json"},
        {"id": "gone", "specSrc": "spec/components/gone.json"}],
        "screens": [{"id": "home", "specSrc": "spec/screens/home.json"}]}
    side = {"login-card": {"anatomy": CARD_ANATOMY, "spec": CARD_SPEC, "usage": {"example": {"title": "Sign in"}}},
            "button": {"usage": {"example": {"label": "Go"}}}}
    raw = {}
    for cid, body in side.items():
        p = os.path.join(tmp, "spec", "components", cid + ".json")
        raw[cid] = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
        open(p, "w", encoding="utf-8").write(raw[cid])
    scr = json.dumps({"anatomy": {"parts": [{"name": "Hero"}]}}, indent=2) + "\n"
    open(os.path.join(tmp, "spec", "screens", "home.json"), "w").write(scr)
    out = mig.up(copy.deepcopy(reg), base_dir=tmp)
    lc = json.load(open(os.path.join(tmp, "spec", "components", "login-card.json"), encoding="utf-8"))
    check("elements" in lc and lc["legacy"]["anatomy"] == CARD_ANATOMY, "the component sidecar is converted on disk")
    check(open(os.path.join(tmp, "spec", "components", "button.json"), encoding="utf-8").read() == raw["button"],
          "a sidecar with nothing to convert is not rewritten")
    check(open(os.path.join(tmp, "spec", "screens", "home.json")).read() == scr, "a screen sidecar is not touched")
    check(out["components"] == reg["components"], "the registry entries are not changed (a missing sidecar is skipped)")
    mig.down(out, base_dir=tmp)
    check(json.load(open(os.path.join(tmp, "spec", "components", "login-card.json"), encoding="utf-8")) == side["login-card"],
          "down rewrites the sidecar back to its legacy content")

print("6 · the runner: dry-run, apply, --to 12")
with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, "spec", "components"))
    reg = {"meta": {"name": "t", "schemaVersion": 12}, "tokens": {}, "screens": [],
           "components": [{"id": "login-card", "level": "organism", "specSrc": "spec/components/login-card.json"}]}
    rp = os.path.join(tmp, "registry.json")
    json.dump(reg, open(rp, "w"), indent=2)
    sp = os.path.join(tmp, "spec", "components", "login-card.json")
    before = json.dumps({"anatomy": CARD_ANATOMY, "spec": CARD_SPEC}, indent=2, ensure_ascii=False) + "\n"
    open(sp, "w", encoding="utf-8").write(before)
    r = subprocess.run([sys.executable, RUNNER, "--registry", rp], capture_output=True, text=True)
    check(r.returncode == 0 and "0011_specs_shape" in r.stdout, "dry-run names 0011")
    check("schema 12 → %d" % man.CURRENT_SCHEMA in r.stdout and mig.describe() in r.stdout,
          "dry-run on a schema-12 registry with a legacy sidecar prints the plan and the pending describe()")
    # The gap banner itself is printed by the write-path commands (CLAUDE.md § Schema compatibility),
    # from exactly these inputs: meta.schemaVersion < CURRENT_SCHEMA and the pending update's describe().
    pending = man.chain(json.load(open(rp))["meta"]["schemaVersion"], man.CURRENT_SCHEMA)
    banner = "⚠ Schema gap (v12 → v%d): %s. Run /pb:update-version." % (man.CURRENT_SCHEMA, pending[0].describe())
    check(pending and pending[0].FROM == 12 and "\n" not in banner, "a schema-12 registry yields a one-line gap banner: " + banner[:60] + "…")
    check(open(sp, encoding="utf-8").read() == before and json.load(open(rp))["meta"]["schemaVersion"] == 12,
          "dry-run writes nothing")
    r = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--apply"], capture_output=True, text=True)
    check(r.returncode == 0 and json.load(open(rp))["meta"]["schemaVersion"] == 13, "--apply stamps 13")
    check("elements" in json.load(open(sp, encoding="utf-8")), "--apply converts the sidecar")
    check("re-measures" in r.stdout, "the advisory says /pb:build re-measures")
    r = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--apply", "--to", "12"], capture_output=True, text=True)
    check(r.returncode == 0 and json.load(open(rp))["meta"]["schemaVersion"] == 12, "--to 12 stamps 12")
    check(open(sp, encoding="utf-8").read() == before, "--to 12 restores the sidecar byte-for-byte")

print("7 · chain + template")
check(man.CURRENT_SCHEMA >= 13, "CURRENT_SCHEMA is at least 13 (0011's target)")
check((12, 13, "0011_specs_shape") in man._REGISTRY, "0011 registered in the chain")
check(max(t for _f, t, _s in man._REGISTRY) == man.CURRENT_SCHEMA, "the chain reaches CURRENT_SCHEMA")
check(json.load(open(TEMPLATE))["meta"]["schemaVersion"] == man.CURRENT_SCHEMA, "template schemaVersion == CURRENT_SCHEMA")
check(len(mig.describe().splitlines()) == 1, "describe() is one line")

print("8 · the readers of the old shape read the new one (no silent skip)")
LINT = os.path.join(ROOT, "pb", "tools", "lint_registry.py")
R2F = os.path.join(ROOT, "pb", "tools", "registry_to_figma.py")
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import logic_check as LC  # noqa: E402


def project(tmp, instance_of):
    os.makedirs(os.path.join(tmp, "render", "components"))
    os.makedirs(os.path.join(tmp, "spec", "components"))
    bodies = {"item": "var props = props || {};\nreturn '<button type=\"button\" data-part=\"root\">' + pbEscape(props.label) + '</button>';",
              "other": "return '<span data-part=\"root\">o</span>';",
              "bar": "var props = props || {};\nreturn '<nav data-part=\"root\">' + pbUse('item', { label: 'A' }) + pbUse('item', { label: 'B' }) + '</nav>';"}
    comps = []
    for cid, body in bodies.items():
        open(os.path.join(tmp, "render", "components", cid + ".js"), "w").write(body)
        comps.append({"id": cid, "name": cid, "scope": "local", "level": "molecule" if cid == "bar" else "atom",
                      "renderSrc": "render/components/%s.js" % cid, "renderFn": "renderCmp" + cid.capitalize()})
    comps[0]["properties"] = [{"id": "label", "type": "string", "default": "Item"}]
    comps[2]["specSrc"] = "spec/components/bar.json"
    side = {"anatomy": {"root": {"type": "container"}},
            "layout": [{"root": ["%s-%d" % (instance_of, i) for i in (1, 2)]}],
            "elements": {"root": {"parent": None}}, "measured": {"by": "spec_measure.py", "props": {}}}
    for i in (1, 2):
        side["anatomy"]["%s-%d" % (instance_of, i)] = {"type": "instance", "instanceOf": instance_of}
        side["elements"]["%s-%d" % (instance_of, i)] = {"parent": "root"}
    json.dump(side, open(os.path.join(tmp, "spec", "components", "bar.json"), "w"), indent=2)
    reg = {"meta": {"name": "readers", "schemaVersion": 13}, "tokens": {"danger": {"$type": "color", "$value": "#d00"}},
           "components": comps, "screens": []}
    rp = os.path.join(tmp, "registry.json")
    json.dump(reg, open(rp, "w"), indent=2)
    return rp


def lint(rp):
    r = subprocess.run([sys.executable, LINT, "--strict", rp], capture_output=True, text=True)
    return r.returncode, [l for l in r.stdout.splitlines() if "id='bar'" in l or "id=\'bar\'" in l]


with tempfile.TemporaryDirectory() as tmp:
    rp = project(tmp, "other")            # the sidecar says `other`; the body composes `item`
    rc, lines = lint(rp)
    check(rc != 0, "lint --strict FAILS a migrated sidecar whose instanceOf set mismatches pbUse (rc=%d)" % rc)
    check(any("ERROR" in l and "R-COMPOSE-MATCH" in l and "['other']" in l for l in lines),
          "R-COMPOSE-MATCH ERROR: declared ['other'] is not composed")
    check(any("R-COMPOSE-MATCH" in l and "['item']" in l and "anatomy (instanceOf)" in l for l in lines),
          "and the composed-but-undeclared ['item'] names the schema-13 field")
    graph = {"items": [{"id": "bar", "kind": "component", "composes": ["item"]}]}
    reg = LC._load_registry_with_specs(tmp)
    f = LC.check_anatomy(graph, reg)
    check(any(x.code == "L-ANATOMY" and "other" in x.msg for x in f), "logic_check L-ANATOMY fires on the mismatch")
with tempfile.TemporaryDirectory() as tmp:
    rp = project(tmp, "item")             # matching
    rc, lines = lint(rp)
    check(rc == 0, "the same project with a MATCHING sidecar passes lint --strict (rc=%d) — the failure above is the mismatch" % rc)
    check(not any("R-COMPOSE-MATCH" in l or "R-NEST" in l for l in lines),
          "a matching migrated sidecar raises no R-COMPOSE-MATCH / R-NEST (got %r)" % lines)
    reg = LC._load_registry_with_specs(tmp)
    check(LC.check_anatomy({"items": [{"id": "bar", "kind": "component", "composes": ["item"]}]}, reg) == [],
          "and no L-ANATOMY")
    r = subprocess.run([sys.executable, R2F, rp, "--scope", "components", "--component", "bar"], capture_output=True, text=True)
    out = json.loads(r.stdout) if r.returncode == 0 else {}
    bar = next((n for n in out.get("roots", []) if n.get("name") == "bar"), {})
    gaps = [g for g in out.get("gaps", []) if g.get("where") == "bar"]
    # `item` has no DS key in this fixture, so the transformer records it as a gap rather than an
    # INSTANCE — which proves it READ the instance part (before, the CLI never opened the sidecar).
    check(r.returncode == 0 and bar.get("type") == "FRAME" and [g["ref"] for g in gaps] == ["item"],
          "registry_to_figma reads the sidecar and resolves the instance parts to `item` (got %r)" % gaps)
with tempfile.TemporaryDirectory() as tmp:
    rp = project(tmp, "ghost")            # instanceOf names no component
    rc, lines = lint(rp)
    check(any("ERROR" in l and "R-NEST" in l and "instanceOf 'ghost'" in l for l in lines),
          "R-NEST catches an instanceOf that resolves to no component")


print("9 · up→down→up is lossless for a sidecar that already has new keys AND legacy keys")
STACK_ONLY = {"stack": [{"name": "Title", "anchor": ".t"}, {"name": "Foot", "anchor": ".f"}], "marginX": 0}
NEW = {"anatomy": {"root": {"type": "container"}, "x": {"type": "text"}}, "layout": [{"root": ["x"]}],
       "elements": {"root": {"parent": None}, "x": {"parent": "root"}}, "shape": "card",
       "measured": {"by": "spec_measure.py", "props": {}}}
cases = bad = 0
for r in range(len(NEW) + 1):
    for keys in itertools.combinations(NEW, r):
        for legacy in ({"spec": STACK_ONLY}, {"anatomy": CARD_ANATOMY}, {"anatomy": CARD_ANATOMY, "spec": CARD_SPEC}, {"spec": "44px tall."}):
            x = {"usage": {"example": {"a": 1}}}
            x.update({k: copy.deepcopy(NEW[k]) for k in keys})
            if "anatomy" in keys and "anatomy" in legacy:
                continue                               # one `anatomy` key can only hold one shape
            x.update(copy.deepcopy(legacy))
            cases += 1
            u, _ = mig.convert(x)
            d, _ = mig.revert(copy.deepcopy(u))
            u2, _ = mig.convert(copy.deepcopy(d))
            kept = all(u.get(k) == NEW[k] for k in keys)                   # no new key was overwritten
            added = not keys or set(u) - set(x) <= {"legacy", "anatomyNote", "specNote"}   # …or added to
            restored = all(d.get(k) == legacy[k] for k in legacy)          # down gives the legacy keys back
            if not (u2 == u and mig.convert(copy.deepcopy(u))[0] == u and kept and added and restored):
                bad += 1
                print("    ✗ keys=%s legacy=%s: up→down→up %s · idempotent %s · kept %s · added-to %s · legacy back %s"
                      % (list(keys), list(legacy), u2 == u, mig.convert(copy.deepcopy(u))[0] == u, kept, added, restored))
check(cases > 50 and bad == 0, "%d combinations of (new keys) × (legacy keys): none loses or invents a key (%d bad)" % (cases, bad))
sx = {"anatomy": copy.deepcopy(NEW["anatomy"]), "spec": copy.deepcopy(STACK_ONLY), "usage": {"example": {"a": 1}}}
u, _ = mig.convert(sx)
check(u["anatomy"] == NEW["anatomy"] and "layout" not in u and "elements" not in u and u["legacy"] == {"spec": STACK_ONLY},
      "the case from the review: new anatomy + legacy spec.stack → NO derived layout/elements injected")
sl_ = {"layout": [{"root": ["mine"]}], "spec": copy.deepcopy(STACK_ONLY)}
u, _ = mig.convert(sl_)
check(u["layout"] == [{"root": ["mine"]}] and "anatomy" not in u and "elements" not in u,
      "a hand-typed layout beside a legacy stack is not replaced by the derived one")
check(mig.up(mig.down(mig.up({"meta": {"schemaVersion": 12}, "components": [sx]}))) == mig.up({"meta": {"schemaVersion": 12}, "components": [sx]}),
      "…and at the registry level, up→down→up == up")

print("10 · the runner backs up, restores and locks")
RUNNER_MOD = _load("migrate_runner")


def runner_project(tmp, extra_components=()):
    os.makedirs(os.path.join(tmp, "spec", "components"))
    os.makedirs(os.path.join(tmp, "spec", "screens"))
    reg = {"meta": {"name": "t", "schemaVersion": 12}, "tokens": {}, "screens": [
        {"id": "home", "specSrc": "spec/screens/home.json"}],
        "components": [{"id": "login-card", "level": "organism", "specSrc": "spec/components/login-card.json"}]
        + list(extra_components)}
    rp = os.path.join(tmp, "registry.json")
    json.dump(reg, open(rp, "w"), indent=2)
    files = {"spec/components/login-card.json": json.dumps({"anatomy": CARD_ANATOMY, "spec": CARD_SPEC}, indent=2, ensure_ascii=False) + "\n",
             "spec/screens/home.json": json.dumps({"anatomy": {"parts": [{"name": "Hero"}]}}, indent=2) + "\n"}
    for rel, text in files.items():
        open(os.path.join(tmp, rel), "w", encoding="utf-8").write(text)
    return rp, files


def tree(tmp):
    out = {}
    for d, _dirs, fs in os.walk(tmp):
        if ".pb-backups" in d or "__pycache__" in d:
            continue
        for f in fs:
            if f.endswith(".lock") or f == "prototype.html":
                continue
            out[os.path.relpath(os.path.join(d, f), tmp)] = open(os.path.join(d, f), "rb").read()
    return out


def run_in_process(args):
    """The runner's run() with its output captured → (exit code, text). Exit is 0 when it returns."""
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try:
            RUNNER_MOD.run(args)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
    return code, buf.getvalue()


with tempfile.TemporaryDirectory() as tmp:
    rp, files = runner_project(tmp)
    orig = tree(tmp)
    r = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--apply"], capture_output=True, text=True)
    check(r.returncode == 0 and "elements" in json.load(open(os.path.join(tmp, "spec/components/login-card.json"))), "--apply converts the sidecar")
    snaps = [d for d in os.listdir(os.path.join(tmp, ".pb-backups")) if d.startswith("spec.")]
    check(len(snaps) == 1 and snaps[0].startswith("spec.12."), "a spec snapshot sits beside the registry backup (%s)" % snaps)
    snap = os.path.join(tmp, ".pb-backups", snaps[0])
    check(open(os.path.join(snap, "components", "login-card.json"), encoding="utf-8").read() == files["spec/components/login-card.json"]
          and open(os.path.join(snap, "screens", "home.json"), encoding="utf-8").read() == files["spec/screens/home.json"],
          "…holding spec/components AND spec/screens, byte for byte")
    check("spec sidecar" in r.stdout, "the run says so")
    r = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--rollback"], capture_output=True, text=True)
    check(r.returncode == 0 and "Restored spec sidecars" in r.stdout, "--rollback restores the sidecars too (%s)" % r.stdout.strip().splitlines()[-2:])
    check(tree(tmp) == orig, "…and registry.json + every sidecar are byte-identical to before the apply")
    r = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--apply"], capture_output=True, text=True)
    snaps = sorted(d for d in os.listdir(os.path.join(tmp, ".pb-backups")) if d.startswith("spec."))
    check(len(snaps) == 2 and snaps[0] != snaps[1], "a same-second re-apply gets its own snapshot (the suffix rule of the registry backup)")
    shutil_rm = __import__("shutil").rmtree
    shutil_rm(os.path.join(tmp, ".pb-backups", snaps[-1]))             # a backup made before sidecars were snapshotted
    r = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--rollback"], capture_output=True, text=True)
    check(r.returncode == 0 and "No sidecar snapshot" in r.stdout, "a backup with no snapshot says so and leaves spec/ alone")

with tempfile.TemporaryDirectory() as tmp:        # L4 — a rollback must not destroy what was edited after the update
    rp, files = runner_project(tmp)
    orig = tree(tmp)
    r = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--apply"], capture_output=True, text=True)
    check(r.returncode == 0, "(setup) the update applies")
    edited = json.load(open(rp, encoding="utf-8"))
    edited["meta"]["editedAfterUpdate"] = "a day of work"
    json.dump(edited, open(rp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(os.path.join(tmp, "spec", "components", "login-card.json"), "w", encoding="utf-8").write('{"edited": "after the update"}\n')
    open(os.path.join(tmp, "spec", "components", "made-later.json"), "w", encoding="utf-8").write('{"new": true}\n')
    now_reg = open(rp, "rb").read()
    now_tree = tree(tmp)
    r = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--rollback"], capture_output=True, text=True)
    pres = sorted(d for d in os.listdir(os.path.join(tmp, ".pb-backups")) if d.startswith("pre-rollback."))
    check(r.returncode == 0 and len(pres) == 1 and ".pb-backups/" + pres[0] in r.stdout and "recoverable" in r.stdout,
          "--rollback snapshots the current state first, and says where (%s)" % r.stdout.strip().splitlines()[:1])
    pre = os.path.join(tmp, ".pb-backups", pres[0]) if pres else tmp
    check(open(os.path.join(pre, "registry.json"), "rb").read() == now_reg,
          "…registry.json there is byte-identical to what was on disk just before the rollback (the edit is in it)")
    check(open(os.path.join(pre, "spec", "components", "login-card.json"), encoding="utf-8").read() == '{"edited": "after the update"}\n'
          and os.path.isfile(os.path.join(pre, "spec", "components", "made-later.json"))
          and os.path.isfile(os.path.join(pre, "spec", "screens", "home.json")),
          "…and so are the spec sidecars: the edited one, the one made later, and the untouched one")
    check(tree(tmp) == orig, "…while the rollback itself still restores the registry and sidecars to before the update")
    check(any(f.startswith("registry.12.") for f in os.listdir(os.path.join(tmp, ".pb-backups"))),
          "the update's own backup is still there (a rollback never deletes one)")
    r = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--rollback"], capture_output=True, text=True)
    pres2 = sorted(d for d in os.listdir(os.path.join(tmp, ".pb-backups")) if d.startswith("pre-rollback."))
    check(r.returncode == 0 and len(pres2) == 2 and pres2[0] != pres2[1] and "Restored from backup: registry.12." in r.stdout,
          "a second rollback gets its own pre-rollback snapshot, and the pre-rollback directory is never mistaken for a backup")
    # the snapshot cannot be made → nothing is restored
    edited2 = json.load(open(rp, encoding="utf-8"))
    edited2["meta"]["editedAgain"] = "yes"
    json.dump(edited2, open(rp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    before = tree(tmp)
    real_snap = RUNNER_MOD._snapshot_before_rollback
    def no_space(_registry_path):
        raise OSError("disk full (simulated)")
    RUNNER_MOD._snapshot_before_rollback = no_space
    try:
        code, out = run_in_process(["--registry", rp, "--rollback"])
    finally:
        RUNNER_MOD._snapshot_before_rollback = real_snap
    check(code == 1 and "disk full" in out and "Nothing restored" in out and tree(tmp) == before,
          "if the snapshot cannot be saved the rollback stops with nothing restored — it never overwrites unsaved edits")

with tempfile.TemporaryDirectory() as tmp:
    rp, files = runner_project(tmp, extra_components=[
        {"id": "ghost", "level": "atom", "renderFn": "renderCmpGhost", "renderSrc": "render/components/ghost.js"}])
    orig = tree(tmp)
    r = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--apply"], capture_output=True, text=True)
    check(r.returncode == 1 and "Pre-write render validation failed" in r.stdout and "Nothing written" in r.stdout,
          "a pre-write validation failure exits 1 and says nothing was written")
    check(tree(tmp) == orig, "…registry.json and BOTH sidecars are byte-identical to before (0011 had already rewritten one)")
    check(os.path.isdir(os.path.join(tmp, ".pb-backups")) and any(f.startswith("registry.") for f in os.listdir(os.path.join(tmp, ".pb-backups"))),
          "…and the backup is kept")

with tempfile.TemporaryDirectory() as tmp:
    rp, files = runner_project(tmp)
    orig = tree(tmp)
    sl_mod = RUNNER_MOD._slice()
    real = sl_mod.atomic_write_text
    def boom(path, text):
        if os.path.basename(path) == "registry.json":
            raise OSError("disk full (simulated)")
        return real(path, text)
    sl_mod.atomic_write_text = boom
    try:
        code, out = run_in_process(["--registry", rp, "--apply"])
    finally:
        sl_mod.atomic_write_text = real
    check(code == 1 and "Write failed" in out and "disk full" in out, "a failed registry write exits 1 and reports it")
    check(tree(tmp) == orig, "…registry.json and both sidecars are back to what they were (the sidecars had been converted)")

    # a failure in prototype.html after the registry is written: restore the registry too
    real_open = open
    def deny_html(path, *a, **k):
        if str(path).endswith("prototype.html") and "w" in (a[0] if a else k.get("mode", "r")):
            raise OSError("read-only (simulated)")
        return real_open(path, *a, **k)
    RUNNER_MOD.open = deny_html
    try:
        code, out = run_in_process(["--registry", rp, "--apply"])
    finally:
        del RUNNER_MOD.open
    check(code == 1 and "Post-write render failed" in out, "a failed prototype.html write exits 1 and reports it")
    check(tree(tmp) == orig, "…after the registry WAS written: registry.json and both sidecars are restored")

with tempfile.TemporaryDirectory() as tmp:
    rp, files = runner_project(tmp)
    orig = tree(tmp)
    os.makedirs(os.path.join(tmp, "spec", "extra"))                  # outside components/screens: never touched
    open(os.path.join(tmp, "spec", "extra", "keep.json"), "w").write("{}")
    orig["spec/extra/keep.json"] = b"{}"
    fake = types.ModuleType("0099_fake")
    fake.FROM, fake.TO = 12, 13
    def up(reg, base_dir=None):
        side = os.path.join(base_dir, "spec", "components", "login-card.json")
        open(side, "w").write('{"rewritten": true}')                                  # change one
        os.remove(os.path.join(base_dir, "spec", "screens", "home.json"))             # delete one
        open(os.path.join(base_dir, "spec", "components", "made.json"), "w").write("{}")   # create one
        os.makedirs(os.path.join(base_dir, "spec", "fresh"), exist_ok=True)
        raise RuntimeError("the chain dies half-way (simulated)")
    fake.up = up
    fake.describe = lambda: "fake"
    real_manifest = RUNNER_MOD._load_manifest
    class FakeManifest:
        CURRENT_SCHEMA = 13
        @staticmethod
        def chain(a, b):
            return [fake]
    RUNNER_MOD._load_manifest = lambda: FakeManifest
    try:
        code, out = run_in_process(["--registry", rp, "--apply"])
    finally:
        RUNNER_MOD._load_manifest = real_manifest
    check(code == 1 and "failed at [0099_fake]" in out and "Nothing written" in out, "a chain that dies half-way exits 1 and names the step")
    now = tree(tmp)
    check({k: v for k, v in now.items() if not k.startswith("spec/fresh")} == orig,
          "…a changed sidecar is put back, a deleted one is back, a created one is gone, registry.json untouched, spec/extra left alone")

with tempfile.TemporaryDirectory() as tmp:
    rp, files = runner_project(tmp)
    sl_mod = RUNNER_MOD._slice()
    before = tree(tmp)
    with sl_mod.registry_lock(rp, "a test holding the lock"):
        os.environ["PB_LOCK_TIMEOUT"] = "0.4"
        try:
            r = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--apply"], capture_output=True, text=True)
            r2 = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--rollback"], capture_output=True, text=True)
        finally:
            os.environ.pop("PB_LOCK_TIMEOUT", None)
    check(r.returncode == 1 and "being written" in r.stdout and "a test holding the lock" in r.stdout and "Traceback" not in r.stderr,
          "--apply is refused while another writer holds the lock, naming it (%s)" % r.stdout.strip()[:100])
    check(tree(tmp) == before and not os.path.exists(os.path.join(tmp, ".pb-backups")), "…and nothing was written, not even a backup")
    r3 = subprocess.run([sys.executable, RUNNER, "--registry", rp], capture_output=True, text=True)
    check(r3.returncode == 0 and "Dry-run" in r3.stdout, "a dry-run needs no lock")
    victim = os.path.join(tmp, "victim.txt")
    open(victim, "w").write("do not touch\n")
    with contextlib.suppress(FileNotFoundError):
        os.unlink(rp + ".lock")
    os.symlink(victim, rp + ".lock")
    before = tree(tmp)
    r4 = subprocess.run([sys.executable, RUNNER, "--registry", rp, "--apply"], capture_output=True, text=True)
    check(r4.returncode == 1 and "not a regular file" in r4.stdout and "Traceback" not in r4.stderr,
          "--apply with a symlink planted at registry.json.lock is refused with a message (%s)" % r4.stdout.strip()[:80])
    check(open(victim).read() == "do not touch\n" and tree(tmp) == before and not os.path.exists(os.path.join(tmp, ".pb-backups")),
          "…the file it pointed at is not touched, and nothing else was written, not even a backup")
    os.unlink(rp + ".lock")

with tempfile.TemporaryDirectory() as tmp:        # the helpers on their own
    os.makedirs(os.path.join(tmp, "spec", "components"))
    open(os.path.join(tmp, "spec", "components", "a.json"), "w").write("A")
    snap = os.path.join(tmp, "snap")
    check(RUNNER_MOD._snapshot_specs(tmp, snap) == 1, "the snapshot copies what is there")
    open(os.path.join(tmp, "spec", "components", "a.json"), "w").write("changed")
    open(os.path.join(tmp, "spec", "components", "b.json"), "w").write("new")
    check(RUNNER_MOD._restore_specs(tmp, snap) == (1, 1), "restore puts one file back and removes one")
    check(RUNNER_MOD._restore_specs(tmp, snap) == (0, 0), "…and is idempotent")
    check(open(os.path.join(tmp, "spec", "components", "a.json")).read() == "A" and not os.path.exists(os.path.join(tmp, "spec", "components", "b.json")),
          "…leaving exactly the snapshot")
    snap2 = os.path.join(tmp, "snap2")
    os.makedirs(os.path.join(tmp, "empty"))
    RUNNER_MOD._snapshot_specs(os.path.join(tmp, "empty"), snap2)              # a project with no spec/ at all
    os.makedirs(os.path.join(tmp, "empty", "spec", "components"))
    open(os.path.join(tmp, "empty", "spec", "components", "made.json"), "w").write("{}")
    RUNNER_MOD._restore_specs(os.path.join(tmp, "empty"), snap2)
    check(not os.path.exists(os.path.join(tmp, "empty", "spec")), "a spec/ the migration created is removed when it was not there before")

print()
if fails:
    print("FAIL — %d check(s)" % len(fails))
    sys.exit(1)
print("PASS")
