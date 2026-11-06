#!/usr/bin/env python3
"""
explore_promote.py — /pb:explore's promote with no scoring gate, and the manifests it must survive.

The failure this pins: promote refused until every rubric cell was scored (0 of 2,213 cells were
ever scored in 61 rounds), a hand-edited manifest whose `verdict` was a bare string crashed
promote and reject, and a candidate's own header comment (CANDIDATE / opt-N) went live byte for byte.

  * promote with zero scores succeeds (target, IA and pages rounds), and still records scores
    when there are some
  * `--why "<line>"` is stored as verdict.why in the archived manifest; without it, the why the
    compare page saved is kept
  * a manifest whose verdict is a string (or null, or a list) promotes and rejects — _verdict()
    always hands back a dict, and never mutates the manifest it read
  * the candidate-header comment lines at the top of a promoted body are stripped; everything else
    in the body is byte-identical (CRLF included); a body without headers is copied unchanged
  * the `gate` subcommand only reports unscored cells (exit 0)

Usage:  python3 tests/explore_promote.py
Exit:   0 = pass · 1 = a failure
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))

import explore  # noqa: E402
import report   # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def build(project):
    reg = {
        "meta": {"name": "Promote fixture", "devices": ["laptop", "mobile"]},
        "screens": [{"id": "home", "name": "Home", "renderSrc": "render/screens/home.js",
                     "renderFn": "renderScreenHome"}],
        "components": [{"id": "card", "level": "atom", "renderSrc": "render/components/card.js",
                        "renderFn": "renderCmpCard"}],
    }
    write(os.path.join(project, "registry.json"), json.dumps(reg, indent=2))
    write(os.path.join(project, "render/components/card.js"),
          "return '<div class=\"card\">' + pbEscape(props.title || 'Card') + '</div>';\n")
    write(os.path.join(project, "render/screens/home.js"),
          "return '<main>' + pbUse('card', { title: 'Live' }) + '</main>';\n")


def open_round(reg_path, project, target, body):
    """A target round whose slot opt-2 holds `body` in the card candidate."""
    man = explore.cmd_init(reg_path, target, options=2, intent="a calmer card")
    write(os.path.join(project, man["options"][1]["overlay"]["render/components/card.js"]), body)
    return man


def set_verdict(project, target, value):
    man = explore.load_manifest(project, target)
    man["verdict"] = value
    explore.save_manifest(project, man)


def archived(project, res):
    with open(os.path.join(project, res["archived"]), encoding="utf-8") as f:
        return json.load(f)


def main():
    tmp = tempfile.mkdtemp()
    project = os.path.join(tmp, "project")
    reg_path = os.path.join(project, "registry.json")
    live = os.path.join(project, "render/components/card.js")
    try:
        build(project)

        print("_verdict — always a dict")
        check(explore._verdict({}) == {"pick": None, "why": "", "taught": {}}, "no verdict → the empty verdict")
        check(explore._verdict({"verdict": None}) == {"pick": None, "why": "", "taught": {}}, "a null verdict → the empty verdict")
        check(explore._verdict({"verdict": "too busy"}) == {"pick": None, "why": "too busy", "taught": {}},
              "a string verdict → its text becomes the why")
        check(explore._verdict({"verdict": ["x"]}) == {"pick": None, "why": "", "taught": {}}, "a list verdict → the empty verdict")
        keep = {"pick": "opt-1", "why": "w", "taught": {"opt-2": "t"}}
        man = {"verdict": keep}
        check(explore._verdict(man) is keep, "a dict verdict is returned as it is")
        man = {"verdict": "s"}
        explore._verdict(man)
        check(man["verdict"] == "s", "_verdict does not mutate the manifest")

        print("promote with zero scores")
        body = "return '<div class=\"card card--2\">' + pbEscape(props.title || 'Card') + '</div>';\n"
        open_round(reg_path, project, "card", body)
        man = explore.load_manifest(project, "card")
        check(man["scores"] == {} and len(explore.missing_scores(man)) == len(man["rubric"]) * 2,
              "nothing is scored")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = explore.main(["--registry", reg_path, "gate", "card"])
        check(code == explore.EXIT_OK and "unscored" in out.getvalue(), "gate reports the unscored cells and exits 0")
        res = explore.cmd_promote(reg_path, "card", "opt-2")
        check(res["promoted"] == "opt-2" and read_bytes(live).decode("utf-8") == body, "the pick goes live with no score at all")
        arch = archived(project, res)
        check(arch["status"] == "promoted" and arch["verdict"]["pick"] == "opt-2" and arch["verdict"]["why"] == "",
              "the archived manifest records the pick and an empty why")

        print("--why")
        open_round(reg_path, project, "card", body)
        res = explore.cmd_promote(reg_path, "card", "opt-2", why="calmer, and one line shorter")
        check(archived(project, res)["verdict"]["why"] == "calmer, and one line shorter", "why= is stored as verdict.why")
        open_round(reg_path, project, "card", body)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = explore.main(["--registry", reg_path, "promote", "card", "opt-2", "--why", "from the CLI"])
        check(code == explore.EXIT_OK, "promote --why runs from the CLI (rc %s)" % code)
        closed = sorted(p for p in os.listdir(os.path.join(project, "memory/explore/_closed")) if p.endswith(".json"))
        with open(os.path.join(project, "memory/explore/_closed", closed[-1]), encoding="utf-8") as f:
            check(json.load(f)["verdict"]["why"] == "from the CLI", "…and lands in the archived manifest")

        print("a page-saved why and scores survive a promote without --why")
        man = open_round(reg_path, project, "card", body)
        man = explore.load_manifest(project, "card")
        explore.apply_scores(man, {"scores": {"%s:opt-2" % man["rubric"][0]["id"]: 5},
                                   "verdict": {"pick": None, "why": "from the page", "taught": {"opt-1": "too quiet"}}})
        explore.save_manifest(project, man)
        res = explore.cmd_promote(reg_path, "card", "opt-2")
        arch = archived(project, res)
        check(arch["verdict"]["why"] == "from the page" and arch["verdict"]["taught"] == {"opt-1": "too quiet"}
              and arch["verdict"]["pick"] == "opt-2", "the page's why and taught stay; the pick is set")
        check(list(arch["scores"].values()) == [5], "a partial score sheet is recorded as it stands")

        print("a string verdict promotes and rejects")
        open_round(reg_path, project, "card", body)
        set_verdict(project, "card", "the second one, but quieter")
        res = explore.cmd_promote(reg_path, "card", "opt-2")
        v = archived(project, res)["verdict"]
        check(v["pick"] == "opt-2" and v["why"] == "the second one, but quieter" and v["taught"] == {},
              "promote over a string verdict keeps its text as the why")
        open_round(reg_path, project, "card", body)
        set_verdict(project, "card", "not this")
        lessons = explore.cmd_reject(reg_path, "card")
        check(lessons["why"] == "not this" and lessons["taught"] == {}, "reject over a string verdict reads it as the why")
        open_round(reg_path, project, "card", body)
        set_verdict(project, "card", None)
        check(explore.cmd_reject(reg_path, "card")["why"] == "", "reject over a null verdict does not crash")
        open_round(reg_path, project, "card", body)
        set_verdict(project, "card", "typed by hand")
        man = explore.load_manifest(project, "card")
        explore.apply_scores(man, {"verdict": {"pick": "opt-1", "why": "now structured", "taught": {}}})
        check(man["verdict"]["pick"] == "opt-1", "apply_scores over a string verdict writes a dict")
        explore.cmd_reject(reg_path, "card")

        print("candidate headers are stripped, the rest is byte-identical")
        rest = ("const t = props.title || 'Card';\r\n"
                "// a real comment inside the body, mentions nothing special\r\n"
                "return '<div class=\"card\">' + pbEscape(t) + '</div>'; // CANDIDATE here is not a header\r\n")
        header = ("// CANDIDATE opt-2 — dense list\r\n"
                  "// Keeps renderCmpCard and its props. Tokens only.\r\n"
                  "// registry.opt-2 is the slot this was built for\r\n")
        write(live, "return '<div class=\"card\">' + pbEscape(props.title || 'Card') + '</div>';\n")
        open_round(reg_path, project, "card", header + rest)
        res = explore.cmd_promote(reg_path, "card", "opt-2")
        want = ("// Keeps renderCmpCard and its props. Tokens only.\r\n" + rest)
        check(read_bytes(live).decode("utf-8") == want,
              "only the header lines naming the candidate are removed; the other comment lines and the body are byte-identical")
        check(res["headerLinesStripped"] == {"render/components/card.js": 2}, "the result says how many lines went (%s)" % res["headerLinesStripped"])

        write(live, "return '<div class=\"card\"></div>';\n")
        block = "/* CANDIDATE opt-2\n   a block header */\nconst x = 1;\nreturn '<i>' + x + '</i>';\n"
        open_round(reg_path, project, "card", block)
        explore.cmd_promote(reg_path, "card", "opt-2")
        check(read_bytes(live).decode("utf-8") == "const x = 1;\nreturn '<i>' + x + '</i>';\n", "a /* … */ header block is stripped whole")

        print("a header comment never takes code with it")
        shs = explore.strip_candidate_header
        check(shs("/* CANDIDATE opt-2 */ function renderCmpX(p){...}\nvar y=1;\n")
              == ("function renderCmpX(p){...}\nvar y=1;\n", 1),
              "code after `*/` on the comment's line is kept")
        check(shs("/*\n CANDIDATE opt-3\n*/ var q = 1;\n")[0] == "var q = 1;\n",
              "code on a multi-line header's closing line is kept")
        unterminated = "/* start of notes\nfunction a(){}\n// opt-1 mention\n"
        check(shs(unterminated) == (unterminated, 0), "an unterminated /* strips nothing")
        check(shs("/* CANDIDATE opt-2\r\n   x */\r\nconst x = 1;\r\n")[0] == "const x = 1;\r\n",
              "a header whose closing line is blank after `*/` is dropped whole (CRLF kept)")
        check(shs("/* keep me */ a();\n// CANDIDATE opt-1\n") == ("/* keep me */ a();\n// CANDIDATE opt-1\n", 0),
              "a non-matching block comment with code after it ends the header run")
        check(shs("/* CANDIDATE */ /* opt-1 */\ncode();\n")[0] == "code();\n", "two header comments on one line both go")
        write(live, "return '<div class=\"card\"></div>';\n")
        open_round(reg_path, project, "card", "/* CANDIDATE opt-2 */ const k = 2;\nreturn '<b>' + k + '</b>';\n")
        explore.cmd_promote(reg_path, "card", "opt-2")
        check(read_bytes(live).decode("utf-8") == "const k = 2;\nreturn '<b>' + k + '</b>';\n",
              "promote keeps the code that shared a line with the header")

        write(live, "return '<div class=\"card\"></div>';\n")
        late ="const a = 1;\n// CANDIDATE opt-2 — a comment below the code is not a header\nreturn '<b>' + a + '</b>';\n"
        open_round(reg_path, project, "card", late)
        res = explore.cmd_promote(reg_path, "card", "opt-2")
        check(read_bytes(live).decode("utf-8") == late and res["headerLinesStripped"] == {},
              "a comment that is not in the leading run is left alone")

        print("a body without headers is unchanged")
        plain = "// Card — title only.\r\nreturn '<div>' + pbEscape(props.title) + '</div>';\r\n\xe2\x9c\x93 no trailing newline".replace("\xe2\x9c\x93", "✓")
        write(live, "return '<div class=\"card\"></div>';\n")
        open_round(reg_path, project, "card", plain)
        cand = os.path.join(project, explore.load_manifest(project, "card")["options"][1]["overlay"]["render/components/card.js"])
        before = read_bytes(cand)
        explore.cmd_promote(reg_path, "card", "opt-2")
        check(read_bytes(live) == before, "bytes in == bytes out (CRLF, non-ASCII, no final newline)")
        check(explore.strip_candidate_header("") == ("", 0) and explore.strip_candidate_header("/* open") == ("/* open", 0),
              "an empty body and an unterminated comment do not crash")

        print("IA and pages rounds promote with zero scores")
        iaproj = os.path.join(tmp, "ia")
        build(iaproj)
        ia_reg = os.path.join(iaproj, "registry.json")
        with open(ia_reg, encoding="utf-8") as f:
            reg = json.load(f)
        reg["ia"] = {"jobs": [{"id": "track-order", "roles": ["shopper"], "priority": "P1", "when": "w",
                               "want": "x", "so": "y", "screens": []}]}
        write(ia_reg, json.dumps(reg, indent=2))
        explore.cmd_init(ia_reg, "nav-ia", options=2, ia=True, intent="where jobs live")
        struct = {"screens": [{"id": "home", "name": "Home", "jobs": ["track-order"], "parent": None, "depth": 0}],
                  "layers": [{"id": "l1", "name": "Home", "purpose": "start"}], "hub": {}}
        write(os.path.join(iaproj, "memory/explore/nav-ia/opt-1.ia.json"), json.dumps(struct))
        man = explore.load_manifest(iaproj, "nav-ia")
        set_verdict(iaproj, "nav-ia", "a string here too")
        try:
            res = explore.cmd_promote(ia_reg, "nav-ia", "opt-1", force=True, why="fewest taps")
            arch = archived(iaproj, res)
            check(res["mode"] == "ia" and arch["verdict"]["pick"] == "opt-1" and arch["verdict"]["why"] == "fewest taps",
                  "an IA round promotes unscored (string verdict and all), and stores --why")
        except explore.ExploreError as e:
            check("scor" not in str(e).lower(), "an IA round is never refused for missing scores (%s)" % str(e)[:120])

        pages = os.path.join(tmp, "pg")
        build(pages)
        pg_reg = os.path.join(pages, "registry.json")
        explore.cmd_init(pg_reg, "chrome", options=2, pages=True, intent="a calmer tool")
        write(os.path.join(pages, "memory/explore/chrome/opt-1/index.html"), "<!doctype html><p>a</p>")
        res = explore.cmd_promote(pg_reg, "chrome", "opt-1", why="reads better")
        check(res["mode"] == "pages" and archived(pages, res)["verdict"] == {"pick": "opt-1", "why": "reads better", "taught": {}},
              "a pages round promotes unscored and stores --why")

        print("/pb:report survives a bad manifest and counts pre-rollback backups")
        rp = os.path.join(tmp, "rp")
        build(rp)
        open_round(os.path.join(rp, "registry.json"), rp, "card", body)
        set_verdict(rp, "card", "typed by hand")
        write(os.path.join(rp, "memory/explore/broken.json"), json.dumps({"target": "broken", "options": [None, 3],
                                                                          "rubric": "nope", "scores": []}))
        write(os.path.join(rp, "memory/explore/garbage.json"), "{not json")
        rounds = report.facts_explore(rp, None, [])["rounds"]
        by = {r.get("target") or r.get("id") or r.get("file"): r for r in rounds}
        check(by["card"]["pick"] is None and by["card"]["status"] == "open", "a string-verdict round is listed (pick None)")
        check(len(rounds) == 3 and any(r.get("status") == "unreadable" for r in rounds),
              "a manifest that is not valid JSON, or has the wrong shape, is a row and not a crash (%d rows)" % len(rounds))
        write(os.path.join(rp, ".pb-backups/pre-rollback.20261105T101500Z/registry.json"), "{}")
        write(os.path.join(rp, ".pb-backups/registry.20261105T101000Z.json"), "{}")
        b = report.facts_backups(rp, None)
        check(b["pre"] == [".pb-backups/pre-rollback.20261105T101500Z"] and b["preFirst"] == "2026-11-05",
              ".pb-backups/pre-rollback.* counts as a pre-* backup (%s)" % b["pre"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAIL:
        print("\n✗ %d failure(s)" % len(FAIL))
        sys.exit(1)
    print("\n✓ /pb:explore promote: no scoring gate, a string verdict survives, candidate headers do not go live")


if __name__ == "__main__":
    main()
