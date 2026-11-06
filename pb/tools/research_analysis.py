#!/usr/bin/env python3
"""
research_analysis.py — every number a UX study reports, computed from recorded session evidence.

`analyze(study, sessions)` takes the study and its stored `pb-session` files and returns the `study.analysis`
object (contract §6): success rates with adjusted-Wald intervals, time on task, lostness, SEQ and SUS for a
usability test; success, directness and first click for a tree test; the similarity matrix, average-linkage
clusters and category agreement for a card sort; hit rate and click points for a first-click test; the tally
of the plain pre/post answers; and, from the synthesis, each issue's participants / frequency / priority and
each tag's affinity counts. Nothing here reads a file, a clock or the registry, and nothing is random, so the
same inputs give byte-identical JSON (dump with sort_keys) on Python 3.9 and 3.11.

    analyze(study, sessions)       sessions = [(evidence row, parsed session)] -> the analysis dict
    resolve(analysis, dotted)      the value at "usability.tasks.t1.success.rate"; KeyError when absent
    verify_ref(ref, analysis)      None, or why {"analysis": dotted, "value": n} no longer holds
    issue_metrics(study, analysis) {issue id: {participants, frequency, priority}}
    affinity(study)                {"tags": {tag: {observations, participants, tasks}}}
    allowed_numbers(analysis)      the numbers a refill or a report may cite

The answer keys (a task's `optimalPath`, a tree test's `correct`, a first-click `rect` / `target`, the post-task
question ids) are read from the STUDY's instrument, never from the session file, which omits them on purpose.
`research.py` is imported lazily inside the functions that need it (it imports this module), so loading this
module imports no `research`.
"""
import hashlib
import math
import re

import research_stats as S
import research_session as RS

LOST_THRESHOLD = 0.4          # a path with lostness above this counts as "lost"
SORT_THRESHOLD = 0.5          # card sort: clusters are cut at this similarity
TOP_PATHS = 5
KNOWN_OUTCOMES = ("success", "fail", "abandoned", "timeout", "skipped")   # anything else (e.g. "answered") is unknown here


# ── small helpers ────────────────────────────────────────────────────────────

def _R():
    import research
    return research


def _dict(x):
    return x if isinstance(x, dict) else {}


def _list(x):
    return x if isinstance(x, list) else []


def _str(x):
    return x if isinstance(x, str) else ""


def _num(v):
    """A finite float from an int / float / numeric string; None otherwise (a bool is not a number)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, str):
        try:
            f = float(v.strip().replace(",", "."))
        except ValueError:
            return None
        return f if math.isfinite(f) else None
    return None


def _mean(vals):
    return sum(vals) / len(vals) if vals else None


def _r4all(x):
    """Every float in `x` through r4 (ints, bools and strings untouched); returns a new structure."""
    if isinstance(x, bool):
        return x
    if isinstance(x, float):
        return S.r4(x)
    if isinstance(x, dict):
        return {k: _r4all(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_r4all(v) for v in x]
    return x


def _norm_name(s):
    return re.sub(r"\s+", " ", _str(s)).strip().casefold()


def _questions(study):
    """[(section, question)] of the study's instrument with templates expanded (SUS -> ten items, etc.)."""
    inst = _dict(_dict(study).get("instrument"))
    try:
        inst = _R().expand_templates(inst)
    except Exception:
        pass
    out = []
    for sec in _list(inst.get("sections")):
        if isinstance(sec, dict):
            for q in _list(sec.get("questions")):
                if isinstance(q, dict):
                    out.append((sec, q))
    return out


def _task_questions(study, key):
    """[question] in instrument order whose `key` ("task" | "tree" | "click") is an object."""
    return [q for _s, q in _questions(study) if isinstance(q.get("id"), str) and isinstance(q.get(key), dict)]


def _seq_qid(study, tid):
    """Id of the first post-task question with template "seq" after task question `tid` in its section."""
    inst = _dict(_dict(study).get("instrument"))
    try:
        inst = _R().expand_templates(inst)
    except Exception:
        pass
    for sec in _list(inst.get("sections")):
        qs = [q for q in _list(_dict(sec).get("questions")) if isinstance(q, dict)]
        ids = [q.get("id") for q in qs]
        if tid in ids:
            for q in qs[ids.index(tid) + 1:]:
                if q.get("template") == "seq" and isinstance(q.get("id"), str):
                    return q["id"]
            return None
    return None


def _sus_base(study):
    """Ordered item ids of the first complete SUS set in the instrument, or None."""
    groups = {}
    order = []
    for _s, q in _questions(study):
        it = q.get("templateItem")
        if q.get("template") == "sus" and isinstance(it, int) and isinstance(q.get("id"), str):
            base = q["id"].rsplit("-", 1)[0]
            if base not in groups:
                groups[base] = {}
                order.append(base)
            groups[base][it] = q["id"]
    for base in order:
        if sorted(groups[base]) == list(range(1, 11)):
            return [groups[base][i] for i in range(1, 11)]
    return None


def _outcome_of(obj, tid):
    """The recorded outcome of task `tid` in session `obj`, or None."""
    return next((t.get("outcome") for t in _list(_dict(obj).get("tasks")) if isinstance(t, dict) and t.get("id") == tid), None)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── which sessions count ─────────────────────────────────────────────────────

def _select(study, sessions):
    """(kept [(row, obj)], excluded {eid: reason}). Dropped rows, pilots and unreadable sessions are skipped."""
    kept, excluded = [], {}
    method = study.get("method") if isinstance(study.get("method"), str) else None
    seen = set()
    for pair in sessions or []:
        row, obj = (pair[0], pair[1]) if isinstance(pair, (tuple, list)) and len(pair) == 2 else ({}, None)
        eid = _str(_dict(row).get("id")) or "?"
        seen.add(eid)
        if _dict(row).get("dropped"):
            excluded[eid] = "dropped"
        elif not isinstance(obj, dict):
            excluded[eid] = "invalid: not a session object"
        elif obj.get("pilot") is True:
            excluded[eid] = "pilot"
        elif obj.get("format") not in (None, RS.FORMAT):
            excluded[eid] = "invalid: format %r" % obj.get("format")
        elif method in RS.SESSION_METHODS and obj.get("method") not in (None, method):
            excluded[eid] = "invalid: method %r, study is %r" % (obj.get("method"), method)
        else:
            kept.append((row, obj))
    for e in _list(study.get("evidence")):          # dropped session rows the caller did not pass
        if isinstance(e, dict) and e.get("kind") == "session" and e.get("dropped") and _str(e.get("id")) not in seen:
            excluded[e["id"]] = "dropped"
    return kept, excluded


# ── usability ────────────────────────────────────────────────────────────────

def _time_block(secs, with_median=True):
    g = S.geo_mean_ci(secs)
    out = {"n": g["n"], "geoMean": g["geoMean"], "low": g.get("low"), "high": g.get("high")}
    if with_median:
        out["median"] = S.median(secs)
    return out


def _usability(study, kept):
    metrics = [(row, obj, RS.task_metrics(obj)) for row, obj in kept]
    questions = {q["id"]: q for q in _task_questions(study, "task")}
    tids = list(questions)
    for _r, _o, tm in metrics:
        for tid in tm:
            if tid not in tids:
                tids.append(tid)
    tasks = {}
    tot_x = tot_n = 0
    for tid in tids:
        attempts = [tm[tid] for _r, _o, tm in metrics if tid in tm and tm[tid].get("outcome") != "skipped"]
        n = len(attempts)
        succ = [a for a in attempts if a.get("outcome") == "success" and not a.get("assisted")]
        x = len(succ)
        tot_x += x
        tot_n += n
        t = {"n": n, "success": S.adjusted_wald(x, n),
             "assisted": sum(1 for a in attempts if a.get("assisted")),
             "abandoned": sum(1 for a in attempts if a.get("outcome") == "abandoned"),
             "timeouts": sum(1 for a in attempts if a.get("outcome") == "timeout"),
             "unknownOutcome": sum(1 for a in attempts if a.get("outcome") not in KNOWN_OUTCOMES)}
        t["time"] = _time_block([a["ms"] / 1000.0 for a in succ if isinstance(a.get("ms"), int)])
        t["timeAll"] = _time_block([a["ms"] / 1000.0 for a in attempts if isinstance(a.get("ms"), int)])
        t["clicks"] = {"mean": _mean([a["clicks"] for a in attempts])}
        t["deadClicks"] = {"mean": _mean([a["dead"] for a in attempts]), "total": sum(a["dead"] for a in attempts)}
        t["rageClicks"] = sum(a["rage"] for a in attempts)
        t["errors"] = {"mean": _mean([a["errors"] for a in attempts]), "total": sum(a["errors"] for a in attempts)}
        opt = _list(_dict(_dict(questions.get(tid)).get("task")).get("optimalPath"))
        opt = [p for p in opt if isinstance(p, str)]
        if opt:
            ls = []
            for a in attempts:
                scr = _list(a.get("screens"))
                v = S.lostness(len(scr), len(set(scr)), len(opt))
                if v is not None:
                    ls.append(v)
            t["lostness"] = {"n": len(ls), "mean": _mean(ls),
                             "lostShare": (sum(1 for v in ls if v > LOST_THRESHOLD) / len(ls)) if ls else None}
        sq = _seq_qid(study, tid)
        if sq:
            vals = []
            for _r, obj, tm in metrics:
                if tid in tm and tm[tid].get("outcome") != "skipped":
                    v = _num(_dict(tm[tid].get("answers")).get(sq))
                    if v is not None:
                        vals.append(v)
            m = S.mean_ci(vals)
            t["seq"] = {"n": m["n"], "mean": m["mean"], "low": _clamp(m["low"], 1, 7), "high": _clamp(m["high"], 1, 7)}
        counts = {}
        for a in attempts:
            scr = tuple(_list(a.get("screens")))
            if scr:
                counts[scr] = counts.get(scr, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], list(kv[0])))[:TOP_PATHS]
        t["paths"] = [{"path": list(p), "count": c} for p, c in ranked]
        tasks[tid] = t
    out = {"tasks": tasks, "sus": _sus(study, kept), "overall": {"success": S.adjusted_wald(tot_x, tot_n)}}
    return out


def _sus(study, kept):
    ids = _sus_base(study)
    if not ids:
        return None
    scores = []
    for _row, obj in kept:
        ans = _dict(obj.get("answers"))
        vals = [_num(ans.get(i)) for i in ids]
        s = _R().sus_respondent(vals)
        if s is not None:
            scores.append(s)
    if not scores:
        return None
    m = S.mean_ci(scores)
    # A t interval at small n can run past the scale's ends; a SUS above 100 is not a score, so clamp it.
    return {"n": m["n"], "mean": m["mean"], "sd": m["sd"], "low": _clamp(m["low"], 0, 100),
            "high": _clamp(m["high"], 0, 100), "grade": S.sus_grade(m["mean"])}


def _clamp(x, lo, hi):
    """x held inside the scale [lo, hi]; None stays None."""
    return None if x is None else max(lo, min(hi, x))


# ── tree test ────────────────────────────────────────────────────────────────

def _tree_parent(study, kept):
    nodes = _list(_dict(study.get("instrument")).get("tree"))
    if not nodes:
        for _r, obj in kept:
            nodes = _list(_dict(obj.get("config")).get("tree"))
            if nodes:
                break
    return {n["id"]: n.get("parent") for n in nodes if isinstance(n, dict) and isinstance(n.get("id"), str)}


def _lineage(node, parent):
    """`node` and its ancestors up to the root (cycle-safe)."""
    out, seen = [], set()
    while isinstance(node, str) and node not in seen:
        seen.add(node)
        out.append(node)
        node = parent.get(node)
    return out


def _tree_test(study, kept):
    parent = _tree_parent(study, kept)
    questions = {q["id"]: q for q in _task_questions(study, "tree")}
    results = [(obj, RS.tree_results(obj)) for _r, obj in kept]
    tids = list(questions)
    for _o, res in results:
        for tid in res:
            if tid not in tids:
                tids.append(tid)
    tasks = {}
    for tid in tids:
        correct = [c for c in _list(_dict(_dict(questions.get(tid)).get("tree")).get("correct")) if isinstance(c, str)]
        on_path = set()
        for c in correct:
            on_path.update(_lineage(c, parent))
        rows, timed = [], []
        for obj, res in results:
            outcome = _outcome_of(obj, tid)
            if tid not in res and outcome is None:
                continue
            # a skipped task is an attempt that did not succeed (it stays in n); it has no time worth reporting
            r = res.get(tid) or {"chosen": None, "path": [], "firstNode": None, "ms": None, "backtracked": False}
            rows.append(r)
            if outcome != "skipped":
                timed.append(r)
        n = len(rows)
        ok = [r for r in rows if r.get("chosen") in correct]
        direct = [r for r in ok if not r.get("backtracked")]
        first = [r for r in rows if r.get("firstNode") in on_path]
        secs = [r["ms"] / 1000.0 for r in timed if isinstance(r.get("ms"), int)]
        dest = {}
        for r in rows:
            if isinstance(r.get("chosen"), str):
                dest[r["chosen"]] = dest.get(r["chosen"], 0) + 1
        tasks[tid] = {"n": n, "success": S.adjusted_wald(len(ok), n), "direct": S.adjusted_wald(len(direct), n),
                      "firstClick": S.adjusted_wald(len(first), n),
                      "time": {"n": len(secs), "median": S.median(secs), "geoMean": S.geo_mean_ci(secs)["geoMean"]},
                      "destinations": [{"node": k, "count": v} for k, v in sorted(dest.items(), key=lambda kv: (-kv[1], kv[0]))]}
    return {"tasks": tasks}


# ── card sort ────────────────────────────────────────────────────────────────

def _card_sort(study, kept, threshold=SORT_THRESHOLD):
    inst = _dict(study.get("instrument"))
    card_list = _list(inst.get("cards"))
    if not card_list:
        for _r, obj in kept:
            card_list = _list(_dict(obj.get("config")).get("cards"))
            if card_list:
                break
    cards = []
    for c in card_list:
        if isinstance(c, dict) and isinstance(c.get("id"), str) and c["id"] not in cards:
            cards.append(c["id"])
    sort = _dict(inst.get("sort"))
    kind = sort.get("kind") if sort.get("kind") in ("open", "closed", "hybrid") else "open"
    labels = {c["id"]: _str(c.get("label")) for c in _list(sort.get("categories")) if isinstance(c, dict) and isinstance(c.get("id"), str)}
    results = [RS.sort_result(obj) for _r, obj in kept]
    sorts = [[g["cards"] for g in r["groups"] if g["cards"]] for r in results]
    sim = S.similarity(sorts, cards)
    merges = S.average_linkage(cards, sim)
    clusters = S.clusters_at(cards, merges, threshold)
    # category agreement: per category, how many participants used it and, of those, who put each card in it
    cats = {}
    for r in results:
        mine = {}
        for g in r["groups"]:
            if kind != "open" and g["category"]:
                k, raw = g["category"], labels.get(g["category"], g["category"])
            else:
                k, raw = _norm_name(g["name"]), g["name"].strip()
                if not k:
                    k, raw = "(unnamed)", "(unnamed)"
            ent = mine.setdefault(k, {"label": raw, "cards": set()})
            ent["cards"].update(c for c in g["cards"] if c in cards)
        for k, ent in mine.items():
            c = cats.setdefault(k, {"count": 0, "cards": {}, "labels": {}})
            c["count"] += 1
            c["labels"][ent["label"]] = c["labels"].get(ent["label"], 0) + 1
            for cid in ent["cards"]:
                c["cards"][cid] = c["cards"].get(cid, 0) + 1
    categories = {}
    for k in sorted(cats):
        c = cats[k]
        label = sorted(c["labels"].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        categories[k] = {"count": c["count"], "label": label,
                         "cards": {cid: c["cards"][cid] / c["count"] for cid in cards if cid in c["cards"]}}
    return {"n": len(results), "kind": kind, "cards": cards, "similarity": sim,
            "merges": [{"a": m["a"], "b": m["b"], "sim": m["sim"]} for m in merges],
            "clusters": clusters, "threshold": threshold, "categories": categories}


# ── first click ──────────────────────────────────────────────────────────────

def _rect_hit(rect, x, y):
    r = _dict(rect)
    vals = [_num(r.get(k)) for k in ("x", "y", "w", "h")]
    if any(v is None for v in vals) or _num(x) is None or _num(y) is None:
        return None
    rx, ry, rw, rh = vals
    return rx <= x <= rx + rw and ry <= y <= ry + rh


def _first_click(study, kept):
    questions = {q["id"]: q for q in _task_questions(study, "click")}
    results = [RS.click_results(obj) for _r, obj in kept]
    tids = list(questions)
    for res in results:
        for tid in res:
            if tid not in tids:
                tids.append(tid)
    tasks = {}
    for tid in tids:
        click = _dict(_dict(questions.get(tid)).get("click"))
        has_rect = isinstance(click.get("rect"), dict) and _rect_hit(click["rect"], 0, 0) is not None
        has_target = bool(_str(click.get("target")))
        rows = [res[tid] for res in results if tid in res]
        unknown = sum(1 for (_r, obj), res in zip(kept, results) if tid in res and _outcome_of(obj, tid) == "answered")
        # an "answered" outcome should not occur here: it is not a success, whatever hit was recorded
        hits = sum(1 for (_r, obj), res in zip(kept, results)
                   if tid in res and res[tid]["hit"] and _outcome_of(obj, tid) != "answered")
        mismatch = 0
        for r in rows:
            if not has_rect:
                continue
            rh = _rect_hit(click["rect"], r.get("x"), r.get("y"))
            # a recorded hit may come from the target selector, which a rect cannot re-test: with a target set,
            # only "recorded miss, rect hit" is a certain disagreement; rect-only, any difference is one
            if rh is None:
                continue
            if r["hit"] != rh and (not has_target or rh):
                mismatch += 1
        n = len(rows)
        secs = [r["ms"] / 1000.0 for r in rows if isinstance(r.get("ms"), int)]
        g = S.geo_mean_ci(secs)
        tasks[tid] = {"n": n, "success": S.adjusted_wald(hits, n), "unknownOutcome": unknown,
                      "time": {"n": len(secs), "median": S.median(secs), "geoMean": g["geoMean"]},
                      "clicks": [[r.get("x"), r.get("y"), r["hit"]] for r in rows],
                      "hitMismatch": mismatch}
    return {"tasks": tasks}


# ── pre/post answers ─────────────────────────────────────────────────────────

def _cell(v):
    if isinstance(v, bool) or v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return ";".join(_cell(x) for x in v if _cell(x))
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else repr(v)
    return str(v)


def _answers(study, kept):
    rows, mapped = [], set()
    for _r, obj in kept:
        row = {}
        for qid, v in _dict(obj.get("answers")).items():
            c = _cell(v)
            if isinstance(qid, str) and c.strip():
                row[qid] = c
        if row:
            rows.append(row)
            mapped.update(row)
    if not rows:
        return {}
    tmp = dict(study)
    inst = _dict(study.get("instrument"))
    try:
        tmp["instrument"] = _R().expand_templates(inst)
    except Exception:
        tmp["instrument"] = inst
    return _R().tally_questions(tmp, rows, mapped)


# ── the public API ───────────────────────────────────────────────────────────

def analyze(study, sessions):
    """The `study.analysis` object for `sessions` = [(evidence row, parsed session)]. Dropped and pilot sessions are
    skipped and listed in `excluded` with the reason."""
    study = _dict(study)
    kept, excluded = _select(study, sessions)
    method = study.get("method") if study.get("method") in RS.SESSION_METHODS else None
    if method is None and kept:
        method = _str(kept[0][1].get("method")) or None
    inputs = [_str(r.get("id")) for r, _o in kept]
    ihash = _sha("\n".join("%s:%s" % (_str(r.get("id")), _str(r.get("sha256"))) for r, _o in kept))
    a = {"method": method, "inputs": inputs, "inputsHash": ihash, "n": len(kept), "excluded": excluded}
    if method == "usability":
        a["usability"] = _usability(study, kept)
    elif method == "tree-test":
        a["treeTest"] = _tree_test(study, kept)
    elif method == "card-sort":
        a["cardSort"] = _card_sort(study, kept)
    elif method == "first-click":
        a["firstClick"] = _first_click(study, kept)
    a["answers"] = _answers(study, kept)
    a["issues"] = issue_metrics(study, a)
    a["affinity"] = affinity(study)
    return _r4all(a)


def resolve(analysis, dotted):
    """The value at a dotted path. A key that itself holds a dot is matched by joining segments. KeyError if absent."""
    parts = _str(dotted).split(".")
    if not parts or parts == [""]:
        raise KeyError(dotted)

    def walk(node, i):
        if i == len(parts):
            return node
        if isinstance(node, dict):
            for j in range(i + 1, len(parts) + 1):
                k = ".".join(parts[i:j])
                if k in node:
                    try:
                        return walk(node[k], j)
                    except KeyError:
                        continue
            raise KeyError(dotted)
        if isinstance(node, list) and re.match(r"^[0-9]+\Z", parts[i]):
            idx = int(parts[i])
            if idx < len(node):
                return walk(node[idx], i + 1)
        raise KeyError(dotted)

    return walk(analysis, 0)


def verify_ref(ref, analysis):
    """None when `ref` = {"analysis": dotted, "value": number} still matches the analysis, else a message.
    Floats compare after r4; two ints compare exactly."""
    if not isinstance(ref, dict) or not isinstance(ref.get("analysis"), str):
        return "analysis reference needs an \"analysis\" path"
    path, want = ref["analysis"], ref.get("value")
    if isinstance(want, bool) or not isinstance(want, (int, float)):
        return "analysis %s: \"value\" must be a number" % path
    try:
        got = resolve(analysis, path)
    except KeyError:
        return "analysis %s does not exist (the analysis was recomputed, or the path is wrong)" % path
    if isinstance(got, bool) or not isinstance(got, (int, float)):
        return "analysis %s is not a number" % path
    if isinstance(got, int) and isinstance(want, int):
        same = got == want
    else:
        same = S.r4(float(got)) == S.r4(float(want))
    return None if same else "analysis %s is %s, not %s" % (path, got, want)


def _participant_of(study, obs):
    p = obs.get("participant")
    if isinstance(p, str) and p:
        return p
    for e in _list(study.get("evidence")):
        if isinstance(e, dict) and e.get("id") == obs.get("evidence") and isinstance(e.get("participant"), str):
            return e["participant"]
    return None


def issue_metrics(study, analysis):
    """{issue id: {participants, frequency, priority}}. participants = distinct participants over the observations the
    issue cites; frequency = participants / analysis.n; priority = severity x frequency (r4). An issue citing no
    known observation has 0 participants."""
    study = _dict(study)
    n = _dict(analysis).get("n")
    n = n if isinstance(n, int) and not isinstance(n, bool) else 0
    obs = {o["id"]: o for o in _list(study.get("observations")) if isinstance(o, dict) and isinstance(o.get("id"), str)}
    out = {}
    for iss in _list(study.get("issues")):
        if not isinstance(iss, dict) or not isinstance(iss.get("id"), str):
            continue
        who = set()
        for oid in _list(iss.get("observations")):
            o = obs.get(oid)
            if o is not None:
                p = _participant_of(study, o)
                if p:
                    who.add(p)
        sev = iss.get("severity")
        sev = sev if isinstance(sev, int) and not isinstance(sev, bool) and 0 <= sev <= 4 else 0
        freq = len(who) / n if n else None
        out[iss["id"]] = {"participants": len(who), "frequency": S.r4(freq),
                          "priority": S.r4(sev * freq) if freq is not None else None}
    return out


def affinity(study):
    """{"tags": {tag: {observations, participants, tasks}}}: observations carrying the tag, the distinct participants
    behind them, and the tasks they were made in (sorted)."""
    study = _dict(study)
    tags = {}
    for o in _list(study.get("observations")):
        if not isinstance(o, dict):
            continue
        who = _participant_of(study, o)
        for tag in {t for t in _list(o.get("tags")) if isinstance(t, str) and t}:
            e = tags.setdefault(tag, {"obs": 0, "who": set(), "tasks": set()})
            e["obs"] += 1
            if who:
                e["who"].add(who)
            if isinstance(o.get("task"), str) and o["task"]:
                e["tasks"].add(o["task"])
    return {"tags": {t: {"observations": e["obs"], "participants": len(e["who"]), "tasks": sorted(e["tasks"])}
                     for t, e in sorted(tags.items())}}


def allowed_numbers(analysis):
    """The numbers a refill / report may cite: every number in the analysis, each float also at 4, 1 and 0 decimals,
    and every value in 0..1 as a percentage at 0 and 1 decimals (0.8 -> 80, 80.0)."""
    out = set()

    def add(v):
        out.add(v)
        if isinstance(v, float):
            out.add(S.r4(v))
            for d in (1, 0):
                out.add(round(v, d))
                out.add(float("%.*f" % (d, v)))
        if 0 <= v <= 1:
            p = float(v) * 100.0
            for d in (1, 0):
                out.add(round(p, d))
                out.add(float("%.*f" % (d, p)))

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            if isinstance(x, float) and not math.isfinite(x):
                return
            add(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(analysis)
    return out
