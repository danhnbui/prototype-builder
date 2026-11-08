#!/usr/bin/env python3
"""
research_handoff.py — the sample target is ONE number, and `research.py bundle` hands a project's research
files over WITHOUT the participants' recordings. Stdlib only, no browser, hermetic (a temp dir built from
fixtures/research/; every command is the real CLI; nothing is a hand-made row where the tool can make it).

Everything here is TEST DATA: the sessions are the fixtures under fixtures/research/ux/, and the "recordings" are
a few bytes behind an EBML header, not video of anybody.

What it proves:

  1. one target     `brief` participants.n sets audience.targetN · `plan` audience.targetN sets plan
                    participants.n · a plan file with two different numbers is refused (2) · a bad number is refused
                    (2) · once the study holds evidence a CHANGED target is refused (1) through brief and through
                    plan, and the same value is accepted · `check` says W-TARGET on a hand-desynced study
  2. bundle         default: no video file anywhere in the output (any case, any depth), recording rows and pilots
                    marked `withheld` in the BUNDLE's registry only, the source tree and registry byte-identical
                    before and after, evidence still 0444, `.incoming/` and symlinks left out and reported,
                    HANDOFF.md lists each left-out file with its sha256
  3. verify         on the bundle: W-WITHHELD, no V-EVIDENCE, the same verdict as on the source · the file put
                    back at its path: no W-WITHHELD · a tampered file put back: V-EVIDENCE · show / list / analyze /
                    affinity / report / drop-evidence do not error on a withheld row
  4. with recordings the video is carried and no row is marked
  5. re-run         replaces its own output (0444 files and all), also switching mode both ways
  6. refusals       a foreign existing folder (1), no registry.json in --out (2), --out in the project or its
                    memory/ (1); a project with no memory/research/ is "nothing to carry" (0) and no HANDOFF.md
  7. replay         the replay page's config lists a withheld, absent recording in `withheld`, not in `media`

Usage:  python3 tests/research_handoff.py
Exit:   0 = pass · 1 = a failure
"""
import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
TOOL = os.path.join(TOOLS, "research.py")
FIX = os.path.join(ROOT, "fixtures", "research")
UX = os.path.join(FIX, "ux")
sys.path.insert(0, TOOLS)
import research as R  # noqa: E402
import research_session as RS  # noqa: E402

fails = []
TMP = tempfile.mkdtemp(prefix="pb-research-handoff-")
_n = [0]
CHECKS = [0]


def check(cond, msg):
    CHECKS[0] += 1
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def section(title):
    print("\n" + title)


def ux(name):
    return os.path.join(UX, name)


def jload(name):
    with open(ux(name), encoding="utf-8") as f:
        return json.load(f)


def codes(items):
    return sorted({i["code"] for i in items})


def sha(b):
    return hashlib.sha256(b).hexdigest()


def rmtree(path):
    def onerror(func, p, _exc):
        os.chmod(p, 0o700)
        func(p)
    shutil.rmtree(path, onerror=onerror)


def run_at(reg, cwd, *a):
    p = subprocess.run([sys.executable, TOOL, "--registry", reg, "--json"] + list(a), capture_output=True, text=True, cwd=cwd)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        out = {}
    return p.returncode, out, p.stderr


class Proj:
    """A fresh temp copy of the fixture, and a way to run the tool against it."""

    def __init__(self):
        _n[0] += 1
        self.dir = os.path.join(TMP, "p%d" % _n[0])
        shutil.copytree(FIX, self.dir)
        self.reg = os.path.join(self.dir, "registry.json")

    def run(self, *a):
        return run_at(self.reg, self.dir, *a)

    def data(self):
        with open(self.reg, encoding="utf-8") as f:
            return json.load(f)

    def study(self, sid):
        return next(s for s in self.data()["research"]["studies"] if s["id"] == sid)

    def edit(self, sid, fn):
        d = self.data()
        fn(next(s for s in d["research"]["studies"] if s["id"] == sid))
        with open(self.reg, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
            f.write("\n")

    def raw(self):
        with open(self.reg, "rb") as f:
            return f.read()

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def write(self, name, obj):
        p = self.path(name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        return p

    def write_bytes(self, name, data):
        p = self.path(name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        return p


def tree_hash(root):
    """Every path under root with its type, mode and content (a symlink: its target), as one digest and a listing."""
    rows = []
    for d, dirs, files in os.walk(root, followlinks=False):
        for n in sorted(dirs + files):
            p = os.path.join(d, n)
            rel = os.path.relpath(p, root)
            st = os.lstat(p)
            if stat.S_ISLNK(st.st_mode):
                rows.append((rel, "link", os.readlink(p)))
            elif stat.S_ISDIR(st.st_mode):
                rows.append((rel, "dir", stat.S_IMODE(st.st_mode)))
            else:
                with open(p, "rb") as f:
                    rows.append((rel, "file", stat.S_IMODE(st.st_mode), sha(f.read())))
    rows.sort(key=lambda r: r[0])
    return sha(json.dumps(rows).encode()), rows


def videos_under(root):
    out = []
    for d, _dirs, files in os.walk(root):
        for n in files:
            if os.path.splitext(n)[1].lower() in (".webm", ".mp4", ".mov", ".mkv"):
                out.append(os.path.join(d, n))
    return out


SID = "rs-pay-test"
WEBM = b"\x1a\x45\xdf\xa3" + bytes(range(256)) * 4
PILOT_WEBM = WEBM + b"-pilot"
PILOT_SID = "s-ux00pl2"


def review_rows(p, sid):
    rc, out, err = p.run("review-plan", sid)
    assert rc == 0, (rc, out, err)
    path = os.path.join(p.dir, "rows-%s.txt" % sid)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join("%s · yes · the words of the question hold" % i for i in out["items"]) + "\n")
    return path


def usability_approved():
    p = Proj()
    for args in (("init", SID, "--method", "usability", "--scope", "collect", "--question", "Can couriers pay for a parcel?",
                  "--role", "courier", "--target", "screen:pay", "--mode", "moderated"),
                 ("brief", SID, "--file", ux("usability-brief.json")),
                 ("plan", SID, "--file", ux("usability-plan.json"))):
        rc, out, err = p.run(*args)
        assert rc == 0, (args, rc, out, err)
    rc, out, err = p.run("review", SID, "--file", review_rows(p, SID))
    assert rc == 0, (rc, out, err)
    rc, out, err = p.run("approve", SID, "--note", "test data")
    assert rc == 0, (rc, out, err)
    return p


def fielding():
    """Three sessions, a recording of the second, a pilot with its own recording; stray files around the evidence."""
    p = usability_approved()
    for pid in ("P01", "P02", "P03"):
        rc, out, err = p.run("participant", SID, pid, "--status", "scheduled", "--segment", "rural courier", "--role", "courier")
        assert rc == 0, (rc, out, err)
    for s in ("s1", "s2", "s3"):
        rc, out, err = p.run("import", SID, ux("usability-%s.json" % s), "--kind", "session", "--consent", "yes")
        assert rc == 0, (s, rc, out, err)
    rc, out, err = p.run("import", SID, p.write_bytes("in/rec.webm", WEBM), "--kind", "recording", "--session", "s-ux02b2", "--consent", "yes")
    assert rc == 0, (rc, out, err)
    pilot = jload("usability-pilot.json")
    pilot["sessionId"] = PILOT_SID
    pilot["consent"]["recording"] = True
    rc, out, err = p.run("import", SID, p.write("pilot2.json", pilot), "--kind", "session", "--consent", "yes")
    assert rc == 0 and out["pilot"] is True, (rc, out, err)
    rc, out, err = p.run("import", SID, p.write_bytes("in/pilot.webm", PILOT_WEBM), "--kind", "recording", "--session", PILOT_SID, "--consent", "yes")
    assert rc == 0, (rc, out, err)
    return p


def synthesize(p):
    rc, out, err = p.run("analyze", SID)
    assert rc == 0, (rc, out, err)
    syn = {"verdicts": {"h1": {"verdict": "inconclusive", "why": "Three couriers are too few to say."},
                        "h2": {"verdict": "inconclusive", "why": "Three couriers are too few to say."}},
           "observations": [{"id": "o1", "evidence": "e4", "participant": "P02", "t": 5000,
                             "note": "Paused on the pay screen before looking at the total", "tags": ["total-hidden"]}]}
    rc, out, err = p.run("synthesize", SID, "--file", p.write("syn.json", syn))
    assert rc == 0, (rc, out, err)


def strays(p):
    """Files a real project may hold next to the evidence: videos pb never linked, an upload folder, a symlink."""
    base = p.path("memory", "research", SID)
    p.write_bytes("memory/research/%s/kit/demo.MP4" % SID, b"not really an mp4")
    p.write_bytes("memory/research/%s/notes/clip.mov" % SID, b"not really a mov")
    p.write_bytes("memory/research/%s/.incoming/upload.part" % SID, b"half an upload")
    outside = os.path.join(TMP, "outside-%d.txt" % _n[0])
    with open(outside, "w") as f:
        f.write("outside the project")
    os.symlink(outside, os.path.join(base, "link.txt"))


def make_out(p, name):
    out = os.path.join(TMP, name)
    os.makedirs(out)
    shutil.copy(p.reg, os.path.join(out, "registry.json"))
    return out


def bundle(p, out, *extra):
    return p.run("bundle", "--out", out, *extra)


def study_of(reg_path, sid=SID):
    with open(reg_path, encoding="utf-8") as f:
        return next(s for s in json.load(f)["research"]["studies"] if s["id"] == sid)


# ═════════════════════════════════════════════════════════════════════════════
section("1. one sample target")
p = Proj()
rc, out, err = p.run("init", SID, "--method", "usability", "--scope", "collect", "--question", "q?", "--role", "courier", "--mode", "moderated")
check(rc == 0 and p.study(SID)["audience"]["targetN"] == 5, "init: targetN defaults to 5 for usability")
rc, out, err = p.run("brief", SID, "--file", p.write("b1.json", {"objectives": ["Find out x"], "participants": {"criteria": ["a courier"], "n": 7}}))
st = p.study(SID)
check(rc == 0 and st["audience"]["targetN"] == 7 and st["plan"]["participants"]["n"] == 7, "brief participants.n=7 sets audience.targetN to 7 too")
rc, out, err = p.run("plan", SID, "--file", p.write("p1.json", {"audience": {"targetN": 9}}))
st = p.study(SID)
check(rc == 0 and st["audience"]["targetN"] == 9 and st["plan"]["participants"]["n"] == 9, "plan audience.targetN=9 sets plan.participants.n to 9 too")
rc, out, err = p.run("plan", SID, "--file", p.write("p2.json", {"plan": {"participants": {"n": 6}}}))
st = p.study(SID)
check(rc == 0 and st["audience"]["targetN"] == 6 and st["plan"]["participants"]["n"] == 6, "plan with only plan.participants.n=6 sets audience.targetN to 6")
rc, out, err = p.run("plan", SID, "--file", p.write("p3.json", {"audience": {"targetN": 12}, "plan": {"participants": {"n": 12}}}))
st = p.study(SID)
check(rc == 0 and st["audience"]["targetN"] == 12 and st["plan"]["participants"]["n"] == 12, "plan with the same number in both is accepted")
before = p.raw()
rc, out, err = p.run("plan", SID, "--file", p.write("p4.json", {"audience": {"targetN": 4}, "plan": {"participants": {"n": 6}}}))
check(rc == 2 and p.raw() == before and "differ" in out.get("error", ""), "REFUSED (2) a plan file whose audience.targetN and plan.participants.n differ; nothing written")
for bad in (0, -3, True, "5", 2.5, None):
    rc, out, err = p.run("plan", SID, "--file", p.write("p5.json", {"audience": {"targetN": bad}}))
    check(rc == 2 and p.raw() == before, "REFUSED (2) audience.targetN = %r" % (bad,))
rc, out, err = p.run("brief", SID, "--file", p.write("b2.json", {"participants": {"n": 0}}))
check(rc == 2 and p.raw() == before, "REFUSED (2) brief participants.n = 0")
# check: a hand-desynced study
p.edit(SID, lambda s: (s["audience"].update(targetN=3), s["plan"]["participants"].update(n=8)))
rc, out, err = p.run("check", SID)
w = [x for x in out.get("warnings", []) if x["code"] == "W-TARGET"]
check(len(w) == 1 and "3" in w[0]["msg"] and "8" in w[0]["msg"] and "audience.targetN" in w[0]["msg"] and "brief" in w[0]["msg"],
      "check: W-TARGET names both numbers, says which one the tool reads and how to fix it")
p.edit(SID, lambda s: s["plan"]["participants"].update(n=3))
rc, out, err = p.run("check", SID)
check("W-TARGET" not in codes(out.get("warnings", [])), "check: no W-TARGET when the two agree")
p.edit(SID, lambda s: s["plan"]["participants"].update(n=8))
rc, out, err = p.run("brief", SID, "--file", p.write("b3.json", {"participants": {"n": 3}}))
check(rc == 0 and p.study(SID)["plan"]["participants"]["n"] == 3, "brief with the target's own value repairs a desynced plan")

f = fielding()
tn = f.study(SID)["audience"]["targetN"]
before = f.raw()
rc, out, err = f.run("brief", SID, "--file", f.write("b4.json", {"participants": {"n": tn + 4}}))
check(rc == 1 and f.raw() == before and "init" in out.get("error", ""), "REFUSED (1) a changed target through brief once evidence exists; points to `init`")
rc, out, err = f.run("plan", SID, "--file", f.write("p6.json", {"plan": {"participants": {"n": tn + 4}}}))
check(rc == 1 and f.raw() == before, "REFUSED (1) a changed target through plan (plan.participants.n) once evidence exists")
rc, out, err = f.run("plan", SID, "--file", f.write("p7.json", {"audience": {"targetN": tn + 4}}))
check(rc == 1 and f.raw() == before, "REFUSED (1) a changed target through plan (audience.targetN) once evidence exists")
rc, out, err = f.run("brief", SID, "--file", f.write("b5.json", {"participants": {"n": tn}}))
check(rc == 0 and f.study(SID)["audience"]["targetN"] == tn, "brief re-sending the same target after evidence is accepted")
rc, out, err = f.run("plan", SID, "--file", f.write("p8.json", {"audience": {"targetN": tn}}))
check(rc == 0 and f.study(SID)["audience"]["targetN"] == tn, "plan re-sending the same audience.targetN after evidence is accepted")
rc, out, err = f.run("plan", SID, "--file", f.write("p9.json", {"plan": {"participants": {"n": tn}}}))
check(rc == 0 and f.study(SID)["plan"]["participants"]["n"] == tn, "plan re-sending the same plan.participants.n after evidence is accepted")

# ═════════════════════════════════════════════════════════════════════════════
section("2. bundle — the default leaves the recordings out")
src = fielding()
synthesize(src)
strays(src)
rc, out, err = src.run("verify", SID)
src_verify = (rc, out.get("errors"), codes(out.get("warnings", [])))
check(rc == 0 and out["errors"] == [], "the source verifies clean (rc 0) before the hand-off")
e4 = next(e for e in src.study(SID)["evidence"] if e["kind"] == "recording")
pil = next(x for x in src.study(SID)["pilots"] if x["sessionId"] == PILOT_SID)
pil_rel = pil["media"][0]
src_hash_before, src_rows_before = tree_hash(src.dir)
reg_before = src.raw()

out1 = make_out(src, "bundle1")
rc, res, err = bundle(src, out1)
check(rc == 0 and res.get("studies") == 1, "bundle: exit 0, one study carried (%s)" % err.strip()[:80])
dest1 = os.path.join(out1, "memory", "research")
check(videos_under(out1) == [], "bundle: no video file anywhere in the output (.webm .mp4 .mov .mkv, any case, any depth)")
by_file = {w["file"]: w for w in res.get("withheld", [])}
check(set(by_file) == {e4["file"], pil_rel, "memory/research/%s/kit/demo.MP4" % SID, "memory/research/%s/notes/clip.mov" % SID},
      "bundle: left out the linked recording, the pilot's, and the two videos pb never linked (%d)" % len(by_file))
w4 = by_file.get(e4["file"], {})
check(w4.get("id") == "e4" and w4.get("session") == "s-ux02b2" and w4.get("study") == SID and w4.get("bytes") == len(WEBM)
      and w4.get("sha256") == sha(WEBM) == e4["sha256"], "bundle --json: the recording's id, session, bytes and sha256")
wp = by_file.get(pil_rel, {})
check(wp.get("pilot") == PILOT_SID and wp.get("id") is None and wp.get("sha256") == sha(PILOT_WEBM) and wp.get("bytes") == len(PILOT_WEBM),
      "bundle --json: the pilot's recording names its pilot, with the file's own sha256")
check(res.get("manifest") == "memory/research/HANDOFF.md" and os.path.isfile(os.path.join(out1, res["manifest"])), "bundle --json: manifest is the HANDOFF.md path")
check(res["files"] > 0 and res["bytes"] > 0, "bundle --json: counts the files and bytes carried (%d files, %d bytes)" % (res["files"], res["bytes"]))
check(sorted(res["skipped"]["symlinks"]) == ["memory/research/%s/link.txt" % SID]
      and res["skipped"]["incoming"] == ["memory/research/%s/.incoming" % SID], "bundle --json: the symlink and .incoming/ are reported as skipped")
check(not os.path.lexists(os.path.join(dest1, SID, "link.txt")) and not os.path.exists(os.path.join(dest1, SID, ".incoming")),
      "bundle: neither the symlink nor .incoming/ is in the output")
# the bundle's registry carries the marks; the source does not
b_st = study_of(os.path.join(out1, "registry.json"))
b4 = next(e for e in b_st["evidence"] if e["id"] == "e4")
bp = next(x for x in b_st["pilots"] if x["sessionId"] == PILOT_SID)
check(sorted(b4.get("withheld", {})) == ["at", "reason"] and R.ISO_AT.match(b4["withheld"]["at"]) and "consent" in b4["withheld"]["reason"],
      "bundle registry: the recording row is marked withheld {at, reason}")
check(sorted(bp.get("withheld", {})) == ["at", "reason"], "bundle registry: the pilot is marked withheld")
check(b4["sha256"] == e4["sha256"] and b4["file"] == e4["file"] and not any(e.get("withheld") for e in b_st["evidence"] if e["kind"] != "recording"),
      "bundle registry: the row and its sha256 stay; no other row is marked")
check(all("withheld" not in e for e in src.study(SID)["evidence"]) and src.raw() == reg_before, "source registry: no row marked; byte-identical")
h_after, rows_after = tree_hash(src.dir)
check(h_after == src_hash_before, "source tree: byte-identical before and after (tree hash over paths, modes, contents, symlink targets)")
if h_after != src_hash_before:
    print("   changed:", sorted(set(map(tuple, map(str, rows_after))) ^ set(map(tuple, map(str, src_rows_before))))[:6])
# modes kept
modes_ok, n_cmp = True, 0
for d, _dirs, files in os.walk(dest1):
    for n in files:
        if n == "HANDOFF.md":
            continue
        rel = os.path.relpath(os.path.join(d, n), dest1)
        s_path = os.path.join(src.dir, "memory", "research", rel)
        n_cmp += 1
        if stat.S_IMODE(os.stat(s_path).st_mode) != stat.S_IMODE(os.stat(os.path.join(d, n)).st_mode):
            modes_ok = False
ev_file = next(e["file"] for e in b_st["evidence"] if e["kind"] == "session")
check(modes_ok and n_cmp == res["files"] and stat.S_IMODE(os.stat(os.path.join(out1, *ev_file.split("/"))).st_mode) == 0o444,
      "bundle: every file keeps its mode; evidence is still 0444 (%d compared)" % n_cmp)
# a file is byte-equal to its source
with open(os.path.join(out1, *ev_file.split("/")), "rb") as a_, open(os.path.join(src.dir, *ev_file.split("/")), "rb") as b_:
    check(a_.read() == b_.read(), "bundle: a carried evidence file is byte-equal to the source")
with open(os.path.join(dest1, "HANDOFF.md"), encoding="utf-8") as f:
    handoff = f.read()
check(R.BUNDLE_MARKER in handoff.splitlines() and e4["file"] in handoff and e4["sha256"] in handoff and sha(PILOT_WEBM) in handoff
      and "e4" in handoff and "s-ux02b2" in handoff and PILOT_SID in handoff,
      "HANDOFF.md: the marker line, and each recording with its id, session, path and sha256")
check("face" in handoff and "voice" in handoff and "consent" in handoff and "research.py verify" in handoff and "exact path" in handoff,
      "HANDOFF.md: says why, and how to put one back (the exact path, then verify)")
check("%d file(s)" % res["files"] in handoff and "1 study" in handoff, "HANDOFF.md: what was carried (studies, files, bytes)")
print("\n----- HANDOFF.md as produced in this test -----\n" + handoff + "----- end -----\n")

# ═════════════════════════════════════════════════════════════════════════════
section("3. verify on the bundle")
reg1 = os.path.join(out1, "registry.json")
rc, vo, err = run_at(reg1, out1, "verify", SID)
check(rc == src_verify[0] == 0 and vo["errors"] == [] and "V-EVIDENCE" not in codes(vo["errors"]),
      "verify on the bundle: exit 0 like the source, no V-EVIDENCE")
ww = [x for x in vo["warnings"] if x["code"] == "W-WITHHELD"]
check(len(ww) == 1 and ww[0]["where"] == "evidence.e4", "verify on the bundle: W-WITHHELD for the recording (a warning, not an error)")
check(codes(vo["warnings"]) == sorted(set(src_verify[2]) | {"W-WITHHELD"}), "verify on the bundle: no other warning than the source's")
check(R.evidence_file(out1, SID, b4)[0] == "withheld" and R.evidence_file(out1, SID, dict(b4, withheld=None))[0] == "missing"
      and R.evidence_file(out1, SID, dict(b4, kind="notes"))[0] == "missing",
      "evidence_file: withheld only for a marked recording row whose file is absent")
for cmd in (("show", SID), ("list",), ("analyze", SID), ("affinity", SID), ("report", SID)):
    rc, o, err = run_at(reg1, out1, *cmd)
    check(rc == 0, "%s on the bundle with a withheld recording: exit 0 (%s)" % (cmd[0], err.strip()[:80]))
report_md_path = os.path.join(out1, "memory", "research", SID, "report", "report.md")


def report_text():
    with open(report_md_path, encoding="utf-8") as f:
        return f.read()


check("left out of this hand-off" in report_text(), "report on the bundle: a limitation line says the recording was left out")
# put the file back
back = os.path.join(out1, *e4["file"].split("/"))
with open(back, "wb") as f:
    f.write(WEBM)
os.chmod(back, 0o444)
rc, vo, err = run_at(reg1, out1, "verify", SID)
check(rc == 0 and "W-WITHHELD" not in codes(vo["warnings"]) and vo["errors"] == [], "verify with the file put back at its path: no W-WITHHELD, still clean")
rc, o, err = run_at(reg1, out1, "report", SID)
check(rc == 0 and "left out of this hand-off" not in report_text(),
      "report with the file put back: no 'left out' line (the mark stays in the registry, the report reads the disk)")
check(R.is_withheld(next(e for e in study_of(reg1)["evidence"] if e["id"] == "e4")), "the registry keeps the withheld mark")
os.chmod(back, 0o644)
with open(back, "wb") as f:
    f.write(WEBM + b"tampered")
rc, vo, err = run_at(reg1, out1, "verify", SID)
check(rc == 1 and any(e["code"] == "V-EVIDENCE" and "sha256" in e["msg"] for e in vo["errors"]) and "W-WITHHELD" not in codes(vo["warnings"]),
      "verify with a tampered file put back: V-EVIDENCE (the sha256 is still checked)")
os.remove(back)
# drop-evidence on a withheld row: no error, row and hash stay
out_d = make_out(src, "bundle-drop")
rc, _res, err = bundle(src, out_d)
rc, o, err = run_at(os.path.join(out_d, "registry.json"), out_d, "drop-evidence", SID, "e2", "--reason", "withdrew")
dst = study_of(os.path.join(out_d, "registry.json"))
check(rc == 0 and next(e for e in dst["evidence"] if e["id"] == "e4")["dropped"] and o.get("alsoDropped") == ["e4"],
      "drop-evidence of the session takes its withheld recording without error")

# ═════════════════════════════════════════════════════════════════════════════
section("4. --with-recordings")
out2 = make_out(src, "bundle2")
rc, res2, err = bundle(src, out2, "--with-recordings")
v2 = sorted(os.path.basename(v) for v in videos_under(out2))
check(rc == 0 and res2["withheld"] == [] and len(v2) == 4 and any(n.endswith("-screen.webm") for n in v2),
      "--with-recordings: the video files are carried (%s) and nothing is withheld" % ", ".join(v2))
carried = os.path.join(out2, *e4["file"].split("/"))
with open(carried, "rb") as f:
    check(f.read() == WEBM and stat.S_IMODE(os.stat(carried).st_mode) == 0o444, "--with-recordings: the recording is byte-equal and 0444")
b2 = study_of(os.path.join(out2, "registry.json"))
check(not any("withheld" in e for e in b2["evidence"]) and not any("withheld" in x for x in b2["pilots"]), "--with-recordings: no row or pilot is marked withheld")
with open(os.path.join(out2, "memory", "research", "HANDOFF.md"), encoding="utf-8") as f:
    h2 = f.read()
check("ARE in this folder" in h2 and "consent" in h2 and "How to put one back" not in h2, "--with-recordings: HANDOFF.md says the recordings ARE included and the recipient must be covered by consent")
rc, vo, err = run_at(os.path.join(out2, "registry.json"), out2, "verify", SID)
check(rc == 0 and "W-WITHHELD" not in codes(vo["warnings"]), "verify on the --with-recordings bundle: clean, no W-WITHHELD")
check(tree_hash(src.dir)[0] == src_hash_before, "source tree: still byte-identical after the other runs")

# ═════════════════════════════════════════════════════════════════════════════
section("5. a re-run replaces its own output")
with open(os.path.join(dest1, SID, "stale.txt"), "w") as f:
    f.write("left by somebody after the first run")
rc, res3, err = bundle(src, out1)
b_again = study_of(os.path.join(out1, "registry.json"))
check(rc == 0 and res3.get("replaced") is True and not os.path.exists(os.path.join(dest1, SID, "stale.txt")) and videos_under(out1) == []
      and [w["file"] for w in res3["withheld"]] == [w["file"] for w in res["withheld"]],
      "re-run: the previous output (0444 files and a report from `report`) is replaced, nothing stale stays")
check(next(e for e in b_again["evidence"] if e["id"] == "e4").get("withheld") and not os.path.exists(os.path.join(dest1, SID, "report")),
      "re-run: the row is marked again; the report written into the old bundle is gone")
rc, res4, err = bundle(src, out1, "--with-recordings")
b_inc = study_of(os.path.join(out1, "registry.json"))
check(rc == 0 and len(videos_under(out1)) == 4 and not any("withheld" in e for e in b_inc["evidence"]) and not any("withheld" in x for x in b_inc["pilots"]),
      "re-run with --with-recordings over a default bundle: the videos arrive and the withheld marks are removed")
rc, res5, err = bundle(src, out1)
b_back = study_of(os.path.join(out1, "registry.json"))
check(rc == 0 and videos_under(out1) == [] and next(e for e in b_back["evidence"] if e["id"] == "e4").get("withheld"),
      "re-run without it again: the videos leave and the marks come back")

# ═════════════════════════════════════════════════════════════════════════════
section("6. refusals")
foreign = make_out(src, "foreign")
os.makedirs(os.path.join(foreign, "memory", "research"))
with open(os.path.join(foreign, "memory", "research", "mine.txt"), "w") as f:
    f.write("somebody else's")
snap = tree_hash(foreign)[0]
rc, o, err = bundle(src, foreign)
check(rc == 1 and tree_hash(foreign)[0] == snap and "previous" in o.get("error", ""), "REFUSED (1) an existing memory/research that is not a previous bundle; untouched")
nohandoff = make_out(src, "nomarker")
os.makedirs(os.path.join(nohandoff, "memory", "research"))
with open(os.path.join(nohandoff, "memory", "research", "HANDOFF.md"), "w") as f:
    f.write("# my own hand-off notes\n")
rc, o, err = bundle(src, nohandoff)
check(rc == 1 and os.path.isfile(os.path.join(nohandoff, "memory", "research", "HANDOFF.md")), "REFUSED (1) a HANDOFF.md without the marker line")
noreg = os.path.join(TMP, "noreg")
os.makedirs(noreg)
rc, o, err = bundle(src, noreg)
check(rc == 2 and "copy registry.json into" in o.get("error", "") and not os.path.exists(os.path.join(noreg, "memory")),
      "REFUSED (2) an --out with no registry.json: 'copy registry.json into <out> first'; nothing created")
rc, o, err = bundle(src, os.path.join(TMP, "does-not-exist"))
check(rc == 2 and not os.path.exists(os.path.join(TMP, "does-not-exist")), "REFUSED (2) an --out that does not exist")
badreg = os.path.join(TMP, "badreg")
os.makedirs(badreg)
with open(os.path.join(badreg, "registry.json"), "w") as f:
    f.write("{not json")
rc, o, err = bundle(src, badreg)
check(rc == 2 and not os.path.exists(os.path.join(badreg, "memory")), "REFUSED (2) an --out whose registry.json is not JSON")
snap_src = tree_hash(src.dir)[0]
for label, target in (("the project itself", src.dir), ("memory/", src.path("memory")), ("memory/research/", src.path("memory", "research")),
                      ("a new folder in memory/", src.path("memory", "bundle")), ("a folder inside a study", src.path("memory", "research", SID, "x"))):
    rc, o, err = bundle(src, target)
    check(rc == 1 and tree_hash(src.dir)[0] == snap_src, "REFUSED (1) --out = %s; the source is untouched" % label)
link_out = os.path.join(TMP, "link-to-memory")
os.symlink(src.path("memory"), link_out)
rc, o, err = bundle(src, link_out)
check(rc == 1 and tree_hash(src.dir)[0] == snap_src, "REFUSED (1) --out that is a symlink into memory/ (resolved before the check)")
empty = Proj()
out_e = make_out(empty, "bundle-empty")
rc, o, err = bundle(empty, out_e)
check(rc == 0 and o.get("studies") == 0 and o.get("withheld") == [] and not os.path.exists(os.path.join(out_e, "memory")),
      "a project with no memory/research/: exit 0, 'nothing to carry', no HANDOFF.md")
pr = subprocess.run([sys.executable, TOOL, "--registry", empty.reg, "bundle", "--out", out_e], capture_output=True, text=True)
check(pr.returncode == 0 and "nothing to carry" in pr.stdout, "…and says so in words")

# ═════════════════════════════════════════════════════════════════════════════
section("7. the replay page")
stubs = os.path.join(TMP, "stubs")
os.makedirs(stubs)
for name, marker in (("research-session.js", "/*STUB-SESSION*/"), ("research-methods.js", "/*STUB-METHODS*/"),
                     ("research-replay.js", "/*STUB-REPLAY*/")):
    with open(os.path.join(stubs, name), "w", encoding="utf-8") as f:
        f.write(marker + "\n")
RS.TEMPLATE_DIR = stubs


def replay_cfg(reg_path, eid):
    html = RS.build_page(reg_path, SID, "replay", eid=eid)
    m = "window.PB_RS_REPLAY="
    i = html.index(m) + len(m)
    return json.loads(html[i:html.index(";</script>", i)])


rec_row = e4["id"]
c_src = replay_cfg(src.reg, "e2")
check([m["eid"] for m in c_src["media"]] == [rec_row] and c_src["withheld"] == [], "replay of the source: the recording is in media; withheld is an empty list")
check(RS.build_page(src.reg, SID, "replay", eid="e1").count("window.PB_RS_REPLAY=") == 1 and replay_cfg(src.reg, "e1")["withheld"] == [],
      "replay of a session with no recording: withheld is always present, empty")
c_b = replay_cfg(reg1, "e2")
check(c_b["media"] == [] and c_b["withheld"] == [rec_row], "replay of the bundle: the withheld, absent recording is NOT in media, and is listed in withheld")
c_bp = replay_cfg(reg1, "pilot-" + PILOT_SID)
check(c_bp["media"] == [] and c_bp["withheld"] == ["pilot-%s-screen" % PILOT_SID], "replay of the bundle's pilot: skipped and listed too")
check(c_b["session"]["sessionId"] == "s-ux02b2" and c_b["session"]["events"], "replay of the bundle: the session itself is still there")
os.makedirs(os.path.dirname(back), exist_ok=True)
with open(back, "wb") as f:
    f.write(WEBM)
c_back = replay_cfg(reg1, "e2")
check([m["eid"] for m in c_back["media"]] == [rec_row] and c_back["withheld"] == [], "replay with the file put back: it plays again, nothing withheld")
os.remove(back)

print()
if fails:
    print("FAIL: research_handoff — %d of %d check(s) failed (temp dir kept: %s)" % (len(fails), CHECKS[0], TMP))
    for m in fails:
        print("  - " + m)
    sys.exit(1)
rmtree(TMP)
print("PASS: research_handoff (%d checks)" % CHECKS[0])
