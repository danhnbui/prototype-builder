#!/usr/bin/env python3
"""
ticket_tool.py — pb/tools/ticket.py: the front-end ticket builder, linter, indexer and exporter.

The gap this closes: tickets written by hand across several sessions came out in a different shape
every time, and nothing noticed a missing States row, an evidence link that pointed nowhere, or a
decision id the recipient could never look up. The tool exists so those are findings, not surprises.

  1. `new` writes every template section, in order, with States / Acceptance / Document prefilled.
  2. `new` refuses to overwrite without --force, and refuses any id that does not exist (exit 2).
  3. A fresh skeleton fails lint with TK-EMPTY; a fully filled ticket passes (exit 0).
  4. Each of TK-DEP, TK-REF, TK-LOGIC, TK-INTERNAL, TK-TITLE, TK-STATES, TK-DOC (and the structural
     TK-FRONT / TK-ID / TK-SECTION) fires on a targeted mutation, and TK-STALE is a warning.
  5. The digest is deterministic; `stale` sees a render-body change; `refresh` clears it and touches
     the front matter only.
  6. `index` is byte-stable, and deleting a ticket renumbers nothing.
  7. `export --format notion` carries the properties and no placeholders or front matter, and refuses
     while lint has errors.
  8. `mark-published` / `published` notice that the digest moved.
  9. The template is the source of truth: `new`'s sections are the template's `##` sections, and a
     section added to the template appears in the next ticket.
 10. `new --force` twice on the same inputs is byte-identical, and nothing outside
     handoff/tickets/ is ever written.

Self-contained: the fixture is built here, never read from a project. Exit 0/1.
"""
import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "pb", "tools", "ticket.py")
TEMPLATE = os.path.join(ROOT, "pb", "template", "fe-ticket.template.md")
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import ticket as T  # noqa: E402

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def run(d, *args):
    r = subprocess.run([sys.executable, TOOL] + list(args) + ["--project", d],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def make_project(roles=2):
    d = tempfile.mkdtemp(prefix="pb-ticket-")
    write(os.path.join(d, "render/screens/login.js"), "return '<main>login</main>';\n")
    write(os.path.join(d, "render/screens/dashboard.js"), "return '<main>dash</main>';\n")
    write(os.path.join(d, "render/components/button.js"), "return '<button></button>';\n")
    write(os.path.join(d, "logic/screens/login.json"), "{}\n")
    reg = {
        "meta": {"name": "Fixture", "schemaVersion": 13,
                 "roles": [{"id": "admin", "name": "Admin"}, {"id": "member", "name": "Member"}][:roles]},
        "tokens": {},
        "components": [{"id": "button", "name": "Button", "level": "atom", "scope": "local",
                        "renderFn": "renderCmpButton", "renderSrc": "render/components/button.js"}],
        "screens": [{"id": "login", "name": "Login", "level": "page", "renderFn": "renderScreenLogin",
                     "renderSrc": "render/screens/login.js", "logicSrc": "logic/screens/login.json"},
                    {"id": "dashboard", "name": "Dashboard", "level": "page",
                     "renderFn": "renderScreenDashboard", "renderSrc": "render/screens/dashboard.js"}],
        "flow": {"populated": True, "stories": [{
            "title": "Sign in", "priority": "P1",
            "scenarios": [
                {"text": "Valid credentials land on the dashboard.", "category": "function",
                 "test": {"start": "login", "steps": [], "expect": [{"screen": "dashboard"}]}},
                {"text": "The dashboard greets the user.", "category": "ui",
                 "test": {"start": "dashboard", "steps": [], "expect": []}},
                "A plain prose scenario."]}]},
        "ia": {"populated": True, "jobs": [], "layers": [],
               "rules": [{"id": "lockout", "title": "Account lockout", "kind": "constraint"}]},
        "erd": {"populated": False}, "runtime": [],
    }
    write(os.path.join(d, "registry.json"), json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    return d


def snapshot_outside_tickets(d):
    out = {}
    for base, dirs, files in os.walk(d):
        for n in files:
            p = os.path.join(base, n)
            rel = os.path.relpath(p, d)
            if not rel.startswith(os.path.join("handoff", "tickets") + os.sep):
                out[rel] = sha(p)
    return out


SIX = ["Default", "Loading", "Empty", "Error", "Disabled", "No permission"]


def filled_sections(tid, evidence="flow"):
    """A ticket body a person finished: no placeholder anywhere."""
    states = ["| State | Appearance | Behaviour |", "|---|---|---|"]
    states += ["| %s | Shown as designed | Works as described |" % s for s in SIX[:1]]
    states += ["| %s | N/A | N/A |" % s for s in SIX[1:]]
    doc = ["- Prototype: https://example.com/p.html?screen=login", "- Opens at: Login, empty form"]
    if evidence == "flow":
        doc.append("- Hand-off flow: handoff/tickets/%s/flow.html" % tid)
    else:
        doc += ["- Annotation: handoff/tickets/%s/annotation.png" % tid, "",
                "| # | Part | Spec |", "|---|---|---|", "| 1 | Email field | 48px high |"]
    return {
        "Context": "People who already have an account need a way back in.",
        "Scope": "The sign-in form. Password reset is out of scope.",
        "Solution": "The user types an email and a password, then presses Sign in.",
        "States": "\n".join(states),
        "Edge cases": "\n".join([
            "| Case | Preselected | Message | Primary button | Result |", "|---|---|---|---|---|",
            "| Wrong password | Email kept | The password is not right | Try again | Stays on the form |"]),
        "Roles": "| Capability | admin | member |\n|---|---|---|\n| Sign in | Yes | Yes |",
        "Data & logic": "None",
        "Accessibility": "None",
        "Acceptance": "- [ ] A valid sign-in reaches the dashboard",
        "Open": "None",
        "Document": "\n".join(doc),
        "Handoff notes": "None",
    }


def make_filled(d, tid, evidence="flow", args=(), **kw):
    """`new` it, then replace every section with finished prose. Returns the ticket path."""
    rc, out, err = run(d, "new", tid, "--title", "[Auth] Sign in with email", "--feature", "Auth",
                       "--kind", "journey", "--screen", "login", "--evidence", evidence, *args)
    assert rc == 0, err
    path = os.path.join(d, "handoff", "tickets", tid + ".md")
    p = T.parse_ticket(read(path))
    sec = filled_sections(tid, evidence)
    sec.update(kw)
    write(path, T.render_ticket(p["front"], p["front"]["title"], [(s["name"], sec[s["name"]]) for s in p["doc"]["sections"]]))
    if evidence == "flow":
        write(os.path.join(d, "handoff", "tickets", tid, "flow.html"), "<html></html>")
    else:
        write(os.path.join(d, "handoff", "tickets", tid, "annotation.png"), "png")
    return path


def lint_codes(d, tid, *flags):
    rc, out, err = run(d, "lint", tid, *flags)
    return rc, sorted({ln.split()[1] for ln in out.splitlines() if ln.strip()}), out


print("1 · `new` writes every section, in order, with the facts prefilled")
d = make_project()
before = snapshot_outside_tickets(d)
rc, out, err = run(d, "new", "T-base", "--title", "[Auth] Button", "--feature", "Auth",
                   "--kind", "component", "--component", "button", "--order", "5")
check(rc == 0, "creating a dependency ticket succeeds (rc=%s %s)" % (rc, err.strip()))
rc, out, err = run(d, "new", "T-sign-in", "--title", "[Auth] Sign in with email", "--feature", "Auth",
                   "--kind", "journey", "--screen", "login", "--rule", "lockout",
                   "--depends", "T-base", "--base-url", "https://example.com/p.html", "--order", "10")
check(rc == 0, "creating the journey ticket succeeds (rc=%s %s)" % (rc, err.strip()))
path = os.path.join(d, "handoff", "tickets", "T-sign-in.md")
text = read(path)
tpl_names = re.findall(r"^## (.+)$", read(TEMPLATE), re.M)
got_names = re.findall(r"^## (.+)$", text, re.M)
check(got_names == tpl_names and len(got_names) == 12, "12 sections, in the template's order")
check(got_names == ["Context", "Scope", "Solution", "States", "Edge cases", "Roles", "Data & logic",
                    "Accessibility", "Acceptance", "Open", "Document", "Handoff notes"],
      "the names are the canonical English ones")
check(text.startswith("```ticket\n"), "the first block is a fenced `ticket` block")
front = T.parse_ticket(text)["front"]
check(list(front) == sorted(front), "front-matter keys are sorted")
check(set(front) >= {"id", "title", "feature", "kind", "order", "depends", "screens", "components", "rules",
                     "scenarios", "evidence", "prototype", "figma", "jira", "source"}, "all front-matter keys exist")
check(front["depends"] == ["T-base"] and front["order"] == 10 and front["evidence"] == "flow",
      "depends / order / default evidence (flow for a journey)")
check(len(front["source"]["digest"]) == 40, "a sha1 digest is recorded")
states = T.parse_tables(T.parse_doc(text.split("\n```\n", 1)[1])["sections"][3]["body"])[0]
check([r[0] for r in states["rows"]] == SIX and all(c == T.FILL for r in states["rows"] for c in r[1:]),
      "States: the six rows, every other cell a placeholder")
check("| Account lockout | <!-- fill --> |" in text, "Edge cases: one row per --rule, titled by the rule")
check("| Capability | admin | member |" in text, "Roles: one column per role (two roles)")
check("scenario s-sign-in.1" in text and "Valid credentials land on the dashboard." in text,
      "Acceptance: the scenario starting on the covered screen is included")
check("The dashboard greets the user." not in text and front["scenarios"] == ["s-sign-in.1"],
      "and one starting elsewhere is not")
check("- Prototype: https://example.com/p.html?screen=login" in text, "Document: the deep link on the first screen")
check("- Hand-off flow: <!-- fill: handoff/tickets/T-sign-in/flow.html -->" in text, "Document: the flow stub")
rc, out, err = run(d, "new", "T-card", "--title", "[Auth] Card", "--feature", "Auth", "--kind", "component",
                   "--component", "button", "--screen", "dashboard")
ctext = read(os.path.join(d, "handoff", "tickets", "T-card.md"))
check("- Annotation: <!-- fill: handoff/tickets/T-card/annotation.png -->" in ctext
      and "| # | Part | Spec |" in ctext, "a component ticket defaults to annotation evidence, with its table")
check("<!-- fill: prototype url -->?screen=dashboard" in ctext, "no base URL: the placeholder stays")
d1 = make_project(roles=1)
run(d1, "new", "T-solo", "--title", "[A] B", "--feature", "F", "--kind", "region", "--screen", "login")
check("## Roles\n\nNone\n" in read(os.path.join(d1, "handoff", "tickets", "T-solo.md")),
      "one role: Roles says None")

print("2 · `new` refuses to overwrite, and refuses ids that do not exist")
rc, out, err = run(d, "new", "T-sign-in", "--title", "[A] B", "--feature", "F", "--kind", "journey")
check(rc == 2 and "--force" in err, "overwrite without --force: exit 2")
check(read(path) == text, "and the file is untouched")
for flag, val in (("--screen", "nowhere"), ("--component", "nowhere"), ("--rule", "nowhere"),
                  ("--scenario", "nowhere.1"), ("--depends", "T-nowhere")):
    rc, out, err = run(d, "new", "T-x", "--title", "[A] B", "--feature", "F", "--kind", "journey", flag, val)
    check(rc == 2 and val in err, "%s %s: exit 2 naming it" % (flag, val))
rc, out, err = run(d, "new", "t_bad", "--title", "[A] B", "--feature", "F", "--kind", "journey")
check(rc == 2, "a malformed id: exit 2")
rc, out, err = run(d, "new", "T-x", "--title", "[A] B", "--feature", "F", "--kind", "nonsense")
check(rc == 2, "an unknown --kind: exit 2")
check(not os.path.exists(os.path.join(d, "handoff", "tickets", "T-x.md")), "no failed command left a file behind")

print("3 · a skeleton fails lint with TK-EMPTY; a finished ticket passes")
rc, codes, out = lint_codes(d, "T-sign-in")
check(rc == 1 and "TK-EMPTY" in codes, "fresh skeleton: exit 1 with TK-EMPTY (codes %s)" % codes)
check(all(len(ln.split(None, 2)) == 3 and ln.startswith("T-sign-in ") for ln in out.splitlines()),
      "every line reads `<ID> <CODE> <message>`")
check(out.splitlines() == sorted(out.splitlines()), "findings are sorted")
good = make_filled(d, "T-good")
rc, codes, out = lint_codes(d, "T-good")
check(rc == 0 and out == "", "a finished flow ticket is clean (rc=%s %r)" % (rc, out))
goodtext = read(good)
make_filled(d, "T-ann", evidence="annotation")
rc, codes, out = lint_codes(d, "T-ann")
check(rc == 0 and out == "", "a finished annotation ticket is clean (rc=%s %r)" % (rc, out))
rc, out, err = run(d, "lint", "T-nope")
check(rc == 2, "linting an id with no file: exit 2")

print("4 · each code fires on a targeted mutation")


def mutated(label, code, old, new, count=1, flags=(), tid="T-good"):
    t = goodtext.replace(old, new, count)
    assert t != goodtext, label
    write(good, t)
    rc, codes, out = lint_codes(d, tid, *flags)
    check(code in codes and rc == 1, "%s -> %s (rc=%s, got %s)" % (label, code, rc, codes))
    write(good, goodtext)
    return out


mutated("TK-DEP", "TK-DEP", '"depends": []', '"depends": [\n    "T-ghost"\n  ]')
mutated("TK-REF", "TK-REF", '"screens": [\n    "login"\n  ]', '"screens": [\n    "login",\n    "gone"\n  ]')
mutated("TK-INTERNAL decision id", "TK-INTERNAL", "People who", "Per D-12, people who")
mutated("TK-INTERNAL registry path", "TK-INTERNAL", "People who", "See render/screens/login.js. People who")
mutated("TK-INTERNAL lint code", "TK-INTERNAL", "People who", "R-HEX says people who")
mutated("TK-TITLE", "TK-TITLE", "[Auth] Sign in with email", "Sign in with email", count=2)
mutated("TK-STATES (missing row)", "TK-STATES", "| Loading | N/A | N/A |\n", "")
mutated("TK-STATES (extra row)", "TK-STATES", "| Error | N/A | N/A |", "| Error | N/A | N/A |\n| Partial | N/A | N/A |")
mutated("TK-DOC (no deep link)", "TK-DOC", "?screen=login", "")
mutated("TK-DOC (evidence line missing)", "TK-DOC", "- Hand-off flow: handoff/tickets/T-good/flow.html\n", "")
mutated("TK-DOC (evidence file missing)", "TK-DOC", "T-good/flow.html", "T-good/missing.html")
mutated("TK-EMPTY (blank cell)", "TK-EMPTY", "| Loading | N/A | N/A |", "| Loading |  | N/A |")
mutated("TK-EMPTY (empty section)", "TK-EMPTY", "The sign-in form. Password reset is out of scope.", "")
mutated("TK-EMPTY (placeholder)", "TK-EMPTY", "None\n\n## Document", "<!-- fill -->\n\n## Document")
mutated("TK-SECTION (missing)", "TK-SECTION", "## Scope\n\nThe sign-in form. Password reset is out of scope.\n\n", "")
mutated("TK-SECTION (order)", "TK-SECTION", "## Open", "## Handoff notes\n\nNone\n\n## Open", count=1)
mutated("TK-FRONT (not JSON)", "TK-FRONT", '"kind": "journey",', '"kind": "journey"')
mutated("TK-ID (file name)", "TK-ID", '"id": "T-good"', '"id": "T-other"')
none_ok = T._none_word("Không áp dụng") and T._none_word("n/a.") and T._none_word("KHÔNG CÓ") and not T._none_word("None of these")
check(none_ok, "the none words (None, N/A, Không có, Không áp dụng) are whole-body, case-insensitive")
write(good, goodtext.replace("The sign-in form. Password reset is out of scope.", "Không có"))
rc, codes, out = lint_codes(d, "T-good")
check(rc == 0, "a required section that says `Không có` passes (rc=%s %s)" % (rc, codes))
write(good, goodtext)
# annotation: the table needs a filled row
ann = os.path.join(d, "handoff", "tickets", "T-ann.md")
anntext = read(ann)
write(ann, anntext.replace("| 1 | Email field | 48px high |", "| 1 |  |  |"))
rc, codes, out = lint_codes(d, "T-ann")
check(rc == 1 and "TK-DOC" in codes, "annotation without a filled `# | Part | Spec` row -> TK-DOC")
write(ann, anntext.replace("T-ann/annotation.png", "T-ann/gone.png"))
rc, codes, out = lint_codes(d, "T-ann")
check(rc == 1 and "TK-DOC" in codes, "annotation file missing -> TK-DOC")
write(ann, anntext)
# TK-LOGIC: logicSrc points at a file that is not there
os.rename(os.path.join(d, "logic/screens/login.json"), os.path.join(d, "logic/screens/login.json.off"))
rc, codes, out = lint_codes(d, "T-good")
check(rc == 1 and "TK-LOGIC" in codes, "TK-LOGIC when a referenced screen's logic file is gone (got %s)" % codes)
os.rename(os.path.join(d, "logic/screens/login.json.off"), os.path.join(d, "logic/screens/login.json"))
# Roles is required only when the project has more than one role
write(good, goodtext.replace("| Capability | admin | member |\n|---|---|---|\n| Sign in | Yes | Yes |", "<!-- fill -->"))
rc, codes, out = lint_codes(d, "T-good")
check(rc == 1 and "TK-EMPTY" in codes, "two roles: an unfilled Roles section is TK-EMPTY")
write(good, goodtext)
# TK-STALE is a warning
write(os.path.join(d, "render/screens/login.js"), "return '<main>login v2</main>';\n")
rc, codes, out = lint_codes(d, "T-good")
check(rc == 0 and codes == ["TK-STALE"] and "warning:" in out, "TK-STALE alone is a warning: exit 0 (%s)" % codes)
rc, codes, out = lint_codes(d, "T-good", "--strict")
check(rc == 1, "and --strict makes it fail")

print("5 · the digest is deterministic; stale sees a render change; refresh clears it")
rc, out, err = run(d, "stale", "T-good")
check(rc == 1 and out.strip() == "T-good", "stale reports the ticket after a render-body change")
rc, out, err = run(d, "stale", "T-base")
check(rc == 0 and out.strip() == "", "and not a ticket that does not reference that screen")
reg = json.loads(read(os.path.join(d, "registry.json")))
fr = T.parse_ticket(read(good))["front"]
d_a = T.source_digest(d, reg, fr)
d_b = T.source_digest(d, reg, dict(fr, screens=list(reversed(fr["screens"]))))
check(d_a == T.source_digest(d, reg, fr) and d_a == d_b and len(d_a) == 40, "same inputs, same digest, order of ids irrelevant")
before_refresh = read(good)
rc, out, err = run(d, "refresh", "T-good")
after_refresh = read(good)
check(rc == 0 and after_refresh != before_refresh, "refresh rewrites the ticket")
check(after_refresh.split("\n```\n", 1)[1] == before_refresh.split("\n```\n", 1)[1],
      "and only the front matter: the body is byte-identical")
f2 = T.parse_ticket(after_refresh)["front"]
f1 = T.parse_ticket(before_refresh)["front"]
check({k: v for k, v in f1.items() if k != "source"} == {k: v for k, v in f2.items() if k != "source"}
      and f2["source"]["digest"] == d_a, "no other key changed; the digest is the new one")
rc, out, err = run(d, "stale")
check("T-good" not in out.split(), "after refresh the ticket is no longer stale")
goodtext = after_refresh
write(os.path.join(d, "registry.json"), json.dumps(
    dict(reg, ia=dict(reg["ia"], rules=[{"id": "lockout", "title": "Account lockout (new)", "kind": "constraint"}])),
    indent=2, ensure_ascii=False) + "\n")
rc, out, err = run(d, "stale", "T-sign-in")
check(rc == 1, "a changed rule makes the ticket that cites it stale")
write(os.path.join(d, "registry.json"), json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
scen_reg = json.loads(json.dumps(reg))
scen_reg["flow"]["stories"][0]["scenarios"][0]["lastResult"] = {"status": "pass"}
write(os.path.join(d, "registry.json"), json.dumps(scen_reg, indent=2, ensure_ascii=False) + "\n")
rc, out, err = run(d, "stale", "T-sign-in")
check("T-sign-in" in out.split() and "T-good" not in out.split(),
      "a recorded lastResult does not change a digest (only the already-stale ticket is listed)")
write(os.path.join(d, "registry.json"), json.dumps(reg, indent=2, ensure_ascii=False) + "\n")

print("6 · index is byte-stable; deleting a ticket renumbers nothing")
rc, out, err = run(d, "index")
idx = os.path.join(d, "handoff", "tickets", "index.md")
i1 = read(idx)
run(d, "index")
check(rc == 0 and read(idx) == i1, "a second run is byte-identical")
rows = [ln for ln in i1.splitlines() if ln.startswith("| ") and "ID" not in ln.split("|")[2]]
check(len(rows) >= 4, "the index has a row per ticket (%d)" % len(rows))
order_ids = [(int(r.split("|")[1]), r.split("|")[2].strip()) for r in rows]
check(order_ids == sorted(order_ids), "sorted by (order, id): %s" % order_ids)
check("| 10 | T-sign-in | [Auth] Sign in with email | Auth | T-base |" in i1, "a row carries order, id, title, feature, depends")
check(re.search(r"\| T-good \|.*\| ok \|", i1) is not None, "a clean ticket's status is ok")
check(re.search(r"\| T-sign-in \|.*\| \d+ findings \|", i1) is not None, "a skeleton's status counts its findings")
snap = {tid: read(os.path.join(d, "handoff", "tickets", tid + ".md")) for tid in ("T-sign-in", "T-good", "T-ann")}
os.remove(os.path.join(d, "handoff", "tickets", "T-card.md"))
run(d, "index")
i2 = read(idx)
check(all(read(os.path.join(d, "handoff", "tickets", t + ".md")) == s for t, s in snap.items()),
      "deleting a ticket leaves every other file untouched")
check([ln for ln in i1.splitlines() if "T-card" not in ln] == i2.splitlines(),
      "the index lost exactly that row; every other id and order is as before")
rc, out, err = run(d, "lint", "T-sign-in")
check("TK-DEP" not in out, "no dependency broke by it (T-base still there)")

print("7 · export")
rc, out, err = run(d, "export", "T-good", "--format", "notion")
payload = json.loads(out) if rc == 0 else {}
check(rc == 0 and set(payload) == {"properties", "content"}, "notion output is {properties, content} JSON")
props = payload.get("properties", {})
check(props.get("Name") == "[Auth] Sign in with email" and props.get("Ticket ID") == "T-good"
      and props.get("Feature") == "Auth" and props.get("Order") == 0 and props.get("Depends") == ""
      and "Jira" in props, "properties: Name, Ticket ID, Feature, Order, Depends, Jira (%s)" % sorted(props))
content = payload.get("content", "")
check("<!--" not in content and "```ticket" not in content and not content.startswith("# "),
      "content has no placeholders, no front matter, no title line")
check(content.startswith("## Context") and "## Handoff notes" in content, "content starts at the first section")
rc, out, err = run(d, "export", "T-good", "--format", "md")
check(rc == 0 and out.startswith("# [Auth] Sign in with email") and "```ticket" not in out,
      "md: the body without the front-matter block")
rc, out, err = run(d, "export", "T-sign-in", "--format", "notion")
check(rc == 1 and out == "" and "TK-EMPTY" in err, "a ticket with lint errors is refused (exit 1, nothing on stdout)")
rc, out, err = run(d, "export", "T-sign-in", "--format", "md")
check(rc == 1, "for md as well")
partial = filled_sections("T-good")
partial["Data & logic"] = "<!-- fill -->"
write(good, T.render_ticket(T.parse_ticket(goodtext)["front"], "[Auth] Sign in with email",
                            [(n, partial[n]) for n in tpl_names]))
rc, out, err = run(d, "export", "T-good", "--format", "notion")
c2 = json.loads(out)["content"]
check(rc == 0 and "Data & logic" not in c2 and "<!--" not in c2,
      "an optional section left as a placeholder is dropped, not exported empty")
write(good, goodtext)

print("8 · mark-published + published notice a moved digest")
rc, out, err = run(d, "published", "T-good")
check(rc == 0 and "not published" in out, "never published: said so, exit 0")
rc, out, err = run(d, "mark-published", "T-good", "--target", "notion", "--url", "https://notion.example/p1",
                   "--at", "2026-01-02T03:04:05Z")
led = os.path.join(d, "handoff", "tickets", ".published.json")
ledger = json.loads(read(led))
cur = T.parse_ticket(read(good))["front"]["source"]["digest"]
check(rc == 0 and ledger == {"T-good": {"notion": {"url": "https://notion.example/p1", "digest": cur,
                                                    "at": "2026-01-02T03:04:05Z"}}},
      "the ledger holds {ID: {target: {url, digest, at}}}")
check(read(led) == json.dumps(ledger, indent=2, sort_keys=True) + "\n", "and is written sorted, with a trailing newline")
run(d, "mark-published", "T-good", "--target", "jira", "--url", "https://jira.example/X-1", "--at", "2026-01-03T00:00:00Z")
check(sorted(json.loads(read(led))["T-good"]) == ["jira", "notion"], "a second target is added beside the first")
rc, out, err = run(d, "published", "T-good")
check(rc == 0 and out.count("same") == 2, "unchanged: exit 0, both targets same")
write(os.path.join(d, "render/screens/login.js"), "return '<main>login v3</main>';\n")
rc, out, err = run(d, "published", "T-good")
check(rc == 1 and out.count("differs") == 2, "after a render change: exit 1, differs")
run(d, "refresh", "T-good")
rc, out, err = run(d, "published", "T-good")
check(rc == 1, "refreshing the ticket does not hide that what was published is behind")
rc, out, err = run(d, "mark-published", "T-nope", "--target", "notion", "--url", "u")
check(rc == 2, "marking an unknown ticket: exit 2")

print("9 · the template is the source of truth")
check(re.findall(r"^## (.+)$", read(path), re.M) == tpl_names, "new's sections == the template's `##` sections")
tpl_text = read(TEMPLATE)
alt = tempfile.mkdtemp(prefix="pb-ticket-tpl-")
alt_tpl = os.path.join(alt, "t.md")
write(alt_tpl, tpl_text.replace("## Handoff notes", "## Rollout\n\n> **Optional.** How it ships.\n\n## Handoff notes"))
saved = T.TEMPLATE
T.TEMPLATE = alt_tpl
try:
    with contextlib.redirect_stdout(io.StringIO()):
        rc = T.main(["new", "T-tpl", "--title", "[A] B", "--feature", "F", "--kind", "region", "--project", d])
finally:
    T.TEMPLATE = saved
names = re.findall(r"^## (.+)$", read(os.path.join(d, "handoff", "tickets", "T-tpl.md")), re.M)
check(rc == 0 and names == tpl_names[:-1] + ["Rollout", "Handoff notes"],
      "a section added to the template appears in the next ticket, in place")
os.remove(os.path.join(d, "handoff", "tickets", "T-tpl.md"))
check(T.load_template()[3]["name"] == "States" and [s["level"] for s in T.load_template()].count("required") == 8
      and T.load_template()[5]["level"] == "conditional", "levels are read from the template (8 required, Roles conditional)")

print("10 · idempotent, and it never writes outside handoff/tickets/")
args = ["new", "T-twice", "--title", "[Auth] Twice", "--feature", "Auth", "--kind", "journey",
        "--screen", "login", "--screen", "dashboard", "--rule", "lockout", "--depends", "T-base",
        "--base-url", "https://example.com/p.html", "--order", "3", "--force"]
tw = os.path.join(d, "handoff", "tickets", "T-twice.md")
run(d, *args)
s1 = sha(tw)
run(d, *args)
s2 = sha(tw)
check(s1 == s2, "new --force twice: byte-identical (%s)" % s1[:12])
check("\r" not in read(tw) and read(tw).endswith("\n") and not read(tw).endswith("\n\n"), "LF line ends, one final newline")
check(snapshot_outside_tickets(d).keys() >= before.keys()
      and all(snapshot_outside_tickets(d)[k] == v for k, v in before.items() if not k.startswith("render" + os.sep)),
      "registry.json and every project file outside handoff/tickets/ are unchanged")
d3 = make_project()
b3 = snapshot_outside_tickets(d3)
for argv in (["new", "T-a", "--title", "[A] B", "--feature", "F", "--kind", "region", "--screen", "login"],
             ["lint"], ["index"], ["stale"], ["refresh", "T-a"],
             ["mark-published", "T-a", "--target", "jira", "--url", "u", "--at", "2026-01-01T00:00:00Z"],
             ["published", "T-a"]):
    run(d3, *argv)
check(snapshot_outside_tickets(d3) == b3, "after every command, nothing outside handoff/tickets/ changed")
rc = subprocess.run([sys.executable, TOOL, "lint"], cwd=tempfile.mkdtemp(), capture_output=True,
                    text=True).returncode
check(rc == 2, "no registry.json in the project folder: exit 2")

print()
if fails:
    print("FAIL — %d regression(s)" % len(fails))
    sys.exit(1)
print("PASS — ticket.py builds, lints, indexes and exports tickets from the template")
