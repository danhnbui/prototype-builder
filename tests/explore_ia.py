#!/usr/bin/env python3
"""
explore_ia.py — `explore.py --ia`: N groupings of the SAME approved jobs, on the explore engine.

/pb:clarify hosts the IA round (its G-IA gate); this pins the engine half of that contract:

  * init --ia makes mode "ia" slots with no overlays and no host, and the IA rubric
  * check validates each slot's memory/explore/<id>/<slot>.ia.json: it parses; every
    ia.jobs[].id is served by a screen or listed unhandled; every hub item's screen exists;
    parents exist; depth steps by one down the parent chain; every pair ≥ 3 of 5 IA axes
    apart — and check writes nothing
  * the compare page gets each slot's parsed structure and the approved jobs
  * promote backs up registry.json, then writes ia.jobs[].screens[] (appended, deduped),
    ia.layers[] (replaced), meta.navHub (set as-is when the structure names a hub component,
    built or not — `tab-bar` here exists nowhere), ia.populated — and leaves screens[] /
    components[] exactly as they were
  * `slot <ia-id> opt-merge` works in IA mode and is exempt from the distance gate
  * a promoted round's folder lands at the stable _closed/<ia-id>/ (what /pb:plan §2 reads the
    picked <slot>.ia.json from); a reject is stamped like the manifest

Usage:  python3 tests/explore_ia.py
Exit:   0 = pass · 1 = a failure
"""
import copy
import glob
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))

import explore  # noqa: E402
import serve    # noqa: E402

SHELL = os.path.join(ROOT, "pb", "template", "prototype.html")
COMPARE = os.path.join(ROOT, "pb", "template", "explore-compare.html")
RUNTIME = os.path.join(ROOT, "pb", "template", "runtime.js")
FAIL = []

JOBS = [
    {"id": "track-order", "roles": ["shopper"], "priority": "P1", "when": "a parcel is on its way",
     "want": "see where it is", "so": "plan to be home", "screens": ["home"]},
    {"id": "pay-cod", "roles": ["shopper"], "priority": "P1", "when": "the courier arrives",
     "want": "pay cash on delivery", "so": "the parcel is released", "screens": []},
    {"id": "file-report", "roles": ["ops"], "priority": "P2", "when": "a delivery fails",
     "want": "file what went wrong", "so": "the hub can reschedule", "screens": []},
    {"id": "invite-team", "roles": ["ops"], "priority": "P3", "when": "a new dispatcher joins",
     "want": "invite them", "so": "they can work the queue", "screens": []},
]


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def build(project):
    reg = {
        "meta": {"schemaVersion": 12, "name": "IA fixture", "devices": ["laptop", "mobile"],
                 "roles": [{"id": "shopper", "name": "Shopper"}, {"id": "ops", "name": "Ops"}]},
        "screens": [{"id": "home", "name": "Home", "renderSrc": "render/screens/home.js",
                     "renderFn": "renderScreenHome"}],
        "components": [],
        "ia": {"populated": False, "jobs": copy.deepcopy(JOBS),
               "layers": [{"depth": 0, "name": "Old", "purpose": "to be replaced"}], "rules": []},
    }
    write(os.path.join(project, "registry.json"), json.dumps(reg, indent=2))
    write(os.path.join(project, "render/screens/home.js"), "return '<main>Home</main>';\n")


def by_task():
    return {
        "label": "Four tabs by task", "bet": "a shopper on the move, one thumb",
        "scheme": "task",
        "axes": {"scheme": "task", "hub-shape": "bottom-tabs", "depth": "flat", "layer0": "tasks", "secondary": "overlay"},
        "hub": {"shape": "bottom-tabs", "component": "tab-bar",
                "items": [{"label": "Track", "screen": "home"}, {"label": "Pay", "screen": "pay"},
                          {"label": "Report", "screen": "report"}, {"label": "Team", "screen": "team"}]},
        "screens": [
            {"id": "home", "name": "Track", "depth": 0, "parent": None, "jobs": ["track-order"], "purpose": "where is it"},
            {"id": "pay", "name": "Pay", "depth": 0, "parent": None, "jobs": ["pay-cod"], "purpose": "settle"},
            {"id": "report", "name": "Report", "depth": 0, "parent": None, "jobs": ["file-report"], "purpose": "what failed"},
            {"id": "team", "name": "Team", "depth": 0, "parent": None, "jobs": [], "purpose": "people"},
            {"id": "invite", "name": "Invite", "depth": "overlay", "parent": "team", "jobs": ["invite-team"], "purpose": "add one"},
        ],
        "layers": [{"depth": 0, "name": "Tabs", "purpose": "one tab per task"},
                   {"depth": "overlay", "name": "Sheets", "purpose": "quick actions over a tab"}],
        "unhandled": [],
    }


def by_role():
    return {
        "label": "A sidebar per role", "bet": "ops at a desk; invite-team waits for the admin console",
        "scheme": "role",
        "axes": {"scheme": "role", "hub-shape": "sidebar", "depth": "layered", "layer0": "roles", "secondary": "page"},
        "hub": {"shape": "sidebar", "component": None,
                "items": [{"label": "My parcels", "screen": "parcels"}, {"label": "Operations", "screen": "ops"}]},
        "screens": [
            {"id": "parcels", "name": "My parcels", "depth": 0, "parent": None, "jobs": [], "purpose": "a shopper's home"},
            {"id": "home", "name": "Parcel", "depth": 1, "parent": "parcels", "jobs": ["track-order", "pay-cod"], "purpose": "one parcel"},
            {"id": "ops", "name": "Operations", "depth": 0, "parent": None, "jobs": [], "purpose": "an ops home"},
            {"id": "report", "name": "Failed delivery", "depth": 1, "parent": "ops", "jobs": ["file-report"], "purpose": "file it"},
        ],
        "layers": [{"depth": 0, "name": "Role homes", "purpose": "one home per role"},
                   {"depth": 1, "name": "Records", "purpose": "one parcel or one report"}],
        "unhandled": ["invite-team"],
    }


def put(project, slot, obj):
    write(os.path.join(project, explore.ia_structure_rel("nav-ia", slot)), json.dumps(obj, indent=2))


def res_path(project, slot):
    return os.path.relpath(os.path.join(project, "memory", "explore", "_closed", "nav-ia", slot + ".ia.json"), project)


def problems_of(reg_path):
    return explore.cmd_check(reg_path, "nav-ia")[0]


def score_all(project, target):
    man = explore.load_manifest(project, target)
    explore.apply_scores(man, {"scores": {"%s:%s" % (c["id"], o["slot"]): 4
                                          for c in man["rubric"] for o in man["options"]}})
    explore.save_manifest(project, man)


def main():
    tmp = tempfile.mkdtemp()
    project = os.path.join(tmp, "[ia] project")
    reg_path = os.path.join(project, "registry.json")
    try:
        build(project)
        before = json.loads(read(reg_path))

        print("init --ia")
        code = explore.main(["--registry", reg_path, "init", "nav-ia", "--ia", "--options", "2",
                             "--intent", "group the approved jobs"])
        man = explore.load_manifest(project, "nav-ia")
        check(code == 0 and man["mode"] == "ia" and man["host"] is None, "init --ia opens a mode \"ia\" round with no host")
        check([o["slot"] for o in man["options"]] == ["opt-1", "opt-2"] and not any(o.get("overlay") for o in man["options"]),
              "slots opt-1..N, no overlays")
        check([c["id"] for c in man["rubric"]] == [c["id"] for c in explore.IA_RUBRIC] and len(man["rubric"]) == 7,
              "the IA rubric is set at init (7 criteria)")
        find = next(c for c in man["rubric"] if c["id"] == "findability")
        check(find["prompt"] == "Where would <role> tap first to <want>?",
              "the findability probe is phrased the way /pb:clarify fills it in")
        check(not os.path.exists(os.path.join(project, "render", "_candidates")), "an IA round seeds no candidate bodies")
        check(explore.main(["--registry", reg_path, "init", "x-ia", "--ia", "--goal"]) == explore.EXIT_USAGE,
              "--ia and --goal together is a usage error")

        print("check")
        check(any("no structure at" in p for p in problems_of(reg_path)), "a slot without its .ia.json fails")
        write(os.path.join(project, explore.ia_structure_rel("nav-ia", "opt-1")), "{not json")
        check(any("does not parse" in p for p in problems_of(reg_path)), "a structure that does not parse fails")
        put(project, "opt-1", by_task())
        put(project, "opt-2", by_role())
        snap = (read(reg_path), read(explore.manifest_path(project, "nav-ia")))
        code = explore.main(["--registry", reg_path, "check", "nav-ia"])
        check(code == explore.EXIT_OK, "two valid, distinct groupings pass check (%s)" % problems_of(reg_path))
        check((read(reg_path), read(explore.manifest_path(project, "nav-ia"))) == snap, "check writes nothing")

        missing = by_role()
        missing["screens"][3]["jobs"] = []           # file-report now served by nothing
        put(project, "opt-2", missing)
        check(any("'file-report' is served by no screen and not listed in unhandled" in p for p in problems_of(reg_path)),
              "a job served by no screen and not listed unhandled FAILS")
        broken = by_role()
        broken["hub"]["items"].append({"label": "Ghost", "screen": "nowhere"})
        broken["screens"][3]["parent"] = "parcels-x"
        broken["screens"].append({"id": "deep", "name": "Deep", "depth": 2, "parent": "ops", "jobs": ["file-report"]})
        broken["screens"].append({"id": "pop", "name": "Pop", "depth": "overlay", "parent": None, "jobs": []})
        put(project, "opt-2", broken)
        ps = problems_of(reg_path)
        check(any("points at screen 'nowhere'" in p for p in ps), "a hub item whose screen does not exist FAILS")
        check(any("parent 'parcels-x' does not exist" in p for p in ps), "a parent id that does not exist FAILS")
        check(any("'deep': depth 2 but its parent 'ops' is at depth 0" in p for p in ps), "a depth that skips a level FAILS")
        check(any("'pop': an overlay opens over a screen" in p for p in ps), "an overlay with no parent FAILS")
        unjust = by_role()
        unjust["bet"] = ""
        put(project, "opt-2", unjust)
        check(any("unhandled (invite-team) with no bet" in p for p in problems_of(reg_path)),
              "an unhandled job with no bet justifying it FAILS")
        close = by_role()
        close["axes"] = dict(by_task()["axes"], scheme="role", depth="layered")   # 2 of 5 differ
        put(project, "opt-2", close)
        check(any("differ on only 2 of 5 IA axes" in p for p in problems_of(reg_path)),
              "two groupings < 3 of 5 IA axes apart FAIL")
        put(project, "opt-2", by_role())
        check(problems_of(reg_path) == [], "restored — check is clean again")

        print("the compare page (serve.py)")
        st = serve.State(reg_path, SHELL, None, False, None, RUNTIME, COMPARE)
        serve.Handler.state = st
        httpd = serve.make_server("127.0.0.1", 0, True)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % httpd.server_address[1]
        try:
            with urllib.request.urlopen(base + "/explore/nav-ia") as r:
                page = r.read().decode("utf-8")
            check('"mode":"ia"' in page and '"structure":{"label":"Four tabs by task"' in page,
                  "the page carries each slot's parsed structure")
            check('"jobs":[{"id":"track-order","when":"a parcel is on its way"' in page,
                  "the page carries the approved jobs (id, when / want / so, roles, priority)")
            check('"roles":[{"id":"shopper","name":"Shopper"}' in page, "and the role names")
            data = explore.ia_page(project, json.loads(read(reg_path)), explore.load_manifest(project, "nav-ia"))
            check(data["options"][1]["label"] == "A sidebar per role", "an empty manifest label falls back to the structure's")
            with urllib.request.urlopen(base + "/explore/nav-ia/opt-1") as r:
                check("no bodies to render" in r.read().decode("utf-8"), "an IA slot has no rendered page of its own")
        finally:
            httpd.shutdown()
            httpd.server_close()

        print("gate + promote")
        try:
            explore.cmd_promote(reg_path, "nav-ia", "opt-2")
            check(False, "promote refuses before the gate passes")
        except explore.ExploreError as e:
            check("scoring gate" in str(e), "promote refuses before the gate passes")
        score_all(project, "nav-ia")
        check(explore.main(["--registry", reg_path, "gate", "nav-ia"]) == explore.EXIT_OK, "gate passes once every cell is scored")
        code = explore.main(["--registry", reg_path, "promote", "nav-ia", "opt-1"])
        after = json.loads(read(reg_path))
        backups = glob.glob(os.path.join(glob.escape(project), "memory", "backups", "explore-nav-ia-*", "registry.json"))
        check(code == 0 and len(backups) == 1 and json.loads(read(backups[0])) == before,
              "promote backs registry.json up first, untouched")
        jobs = {j["id"]: j["screens"] for j in after["ia"]["jobs"]}
        check(jobs == {"track-order": ["home"], "pay-cod": ["pay"], "file-report": ["report"], "invite-team": ["invite"]},
              "ia.jobs[].screens[] gets the planned ids, appended and deduped (%s)" % jobs)
        check(after["ia"]["layers"] == by_task()["layers"], "ia.layers[] is replaced with the slot's layers")
        check(after["meta"]["navHub"] == "tab-bar" and after["ia"]["populated"] is True,
              "meta.navHub = the hub component; ia.populated = true")
        check(after["screens"] == before["screens"] and after["components"] == before["components"],
              "screens[] and components[] are untouched — planned screens are /pb:plan's to build")
        stable = os.path.join(project, "memory", "explore", "_closed", "nav-ia")
        check(os.path.isfile(os.path.join(stable, "opt-1.ia.json")) and os.path.isfile(os.path.join(stable, "opt-2.ia.json"))
              and res_path(project, "opt-1") == os.path.join("memory", "explore", "_closed", "nav-ia", "opt-1.ia.json"),
              "a promoted IA round lands its whole folder at the stable _closed/<ia-id>/ (what /pb:plan reads)")
        check(not os.path.exists(explore.manifest_path(project, "nav-ia"))
              and not os.path.exists(os.path.join(project, "memory", "explore", "nav-ia")),
              "the manifest is archived and no working folder is left open")

        print("a merge slot, and a hub with no component")
        explore.cmd_init(reg_path, "nav-ia", options=2, ia=True)
        put(project, "opt-1", by_task())
        put(project, "opt-2", by_role())
        code = explore.main(["--registry", reg_path, "slot", "nav-ia", "opt-merge", "--label", "tabs with role homes"])
        merge = explore.option_of(explore.load_manifest(project, "nav-ia"), "opt-merge")
        check(code == 0 and merge.get("merge") and merge["structure"].endswith("nav-ia/opt-merge.ia.json"),
              "slot opt-merge works in IA mode — its own structure file, marked merge")
        check(any("opt-merge: no structure at" in p for p in problems_of(reg_path)), "a merge slot needs its own .ia.json")
        put(project, "opt-merge", dict(by_task(), label="Tabs with role homes"))   # same axes as opt-1
        check(problems_of(reg_path) == [], "a merge slot is not held to the IA distance gate against its parents")
        score_all(project, "nav-ia")
        res = explore.cmd_promote(reg_path, "nav-ia", "opt-2")
        check(os.path.isfile(os.path.join(stable, "opt-merge.ia.json"))
              and glob.glob(os.path.join(glob.escape(project), "memory", "explore", "_closed", "nav-ia-superseded-*", "opt-1.ia.json")),
              "a second promoted round takes the stable path; the earlier one is kept, stamped")
        after2 = json.loads(read(reg_path))
        check(after2["meta"]["navHub"] == "tab-bar" and "left as it was" in res["note"],
              "hub.component null leaves meta.navHub and says so")
        check({j["id"]: j["screens"] for j in after2["ia"]["jobs"]}["pay-cod"] == ["pay", "home"],
              "a second promote appends without duplicating")

        print("reject")
        explore.cmd_init(reg_path, "nav-ia", options=2, ia=True)
        put(project, "opt-1", by_task())
        lessons = explore.cmd_reject(reg_path, "nav-ia")
        check(os.path.isfile(os.path.join(project, lessons["archived"][:-len(".json")], "opt-1.ia.json"))
              and explore.sessions(project) == [], "reject archives the round and its structures")
        check(json.loads(read(reg_path)) == after2, "reject writes nothing to the registry")

        print("promote — a locked, atomic read-modify-write (L3)")
        explore.cmd_init(reg_path, "nav-ia", options=2, ia=True)
        put(project, "opt-1", by_task())
        put(project, "opt-2", by_role())
        score_all(project, "nav-ia")
        nbackups = lambda: len(glob.glob(os.path.join(glob.escape(project), "memory", "backups", "explore-nav-ia-*")))
        n0 = nbackups()
        os.environ["PB_LOCK_TIMEOUT"] = "0.4"
        try:
            with serve.pbslice.registry_lock(reg_path, "a test holding the lock"):
                held = read(reg_path)
                try:
                    explore.cmd_promote(reg_path, "nav-ia", "opt-1")
                    check(False, "a held registry lock refuses promote")
                except explore.ExploreError as e:
                    check("being written" in str(e) and "a test holding the lock" in str(e),
                          "a held registry lock refuses promote as an ExploreError naming the holder (%s)" % str(e)[:70])
                code = explore.main(["--registry", reg_path, "promote", "nav-ia", "opt-1"])
                check(code == explore.EXIT_FAIL, "…and the CLI exits %d (a refusal, not a crash)" % explore.EXIT_FAIL)
                check(read(reg_path) == held and nbackups() == n0 and os.path.isfile(explore.manifest_path(project, "nav-ia")),
                      "…registry.json is byte-identical, no backup was made, and the round is still open")
        finally:
            os.environ.pop("PB_LOCK_TIMEOUT", None)
        os.environ["PB_LOCK_TIMEOUT"] = "30"
        outcome = {}

        def do_promote():
            try:
                outcome["res"] = explore.cmd_promote(reg_path, "nav-ia", "opt-1")
            except BaseException as e:           # noqa: BLE001 — reported by the checks below
                outcome["err"] = e
        worker = threading.Thread(target=do_promote)
        try:
            with serve.pbslice.registry_lock(reg_path, "a test holding the lock again"):
                worker.start()
                time.sleep(1.0)
                waiting = worker.is_alive()
                mid = json.loads(read(reg_path))
                mid["meta"]["editedWhileLocked"] = "yes"
                serve.pbslice._write(reg_path, mid)
            worker.join(30)
        finally:
            os.environ.pop("PB_LOCK_TIMEOUT", None)
        done = json.loads(read(reg_path))
        check(waiting, "a promote that finds the lock held WAITS for it (an unlocked one would already have finished)")
        check("err" not in outcome and done["meta"].get("editedWhileLocked") == "yes",
              "…then reads the registry afresh: the edit saved meanwhile is NOT overwritten (%s)" % outcome.get("err", ""))
        check(done["ia"]["populated"] is True and done["meta"]["navHub"] == "tab-bar",
              "…and its own change (the IA slice, meta.navHub) is there too")
        newest = sorted(glob.glob(os.path.join(glob.escape(project), "memory", "backups", "explore-nav-ia-*", "registry.json")))[-1]
        check(json.loads(read(newest)).get("meta", {}).get("editedWhileLocked") == "yes",
              "the backup it took holds the registry it replaced — the one with the meanwhile edit")
        check([f for f in os.listdir(project) if f.endswith(".tmp")] == [], "the registry write left no temp file")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAIL:
        print("\n✗ %d failure(s)" % len(FAIL))
        sys.exit(1)
    print("\n✓ explore.py --ia: N groupings of the approved jobs, validated, rated, and promoted into the IA slice only")


if __name__ == "__main__":
    main()
