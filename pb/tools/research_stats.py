#!/usr/bin/env python3
"""
research_stats.py — the pure statistics behind /pb:research's UX methods. Stdlib only, no I/O.

Every function takes plain numbers or lists and returns plain dicts, lists, floats or None. Nothing
here reads a file, a clock or the registry, so the same input gives the same output on every run and
on Python 3.9 and 3.11. The functions return raw floats; whoever stores a number passes it through
`r4` (4 decimals, None-safe) so the stored JSON is byte-stable.

    adjusted_wald(x, n, conf)   a success rate with an Agresti-Coull ("adjusted Wald") interval
    t_crit(df, conf)            two-sided Student t critical value from a printed table
    mean_ci(values, conf)       mean, sample sd and a t interval
    geo_mean_ci(values, conf)   geometric mean with a t interval taken on the logs (time on task)
    median(values)              middle value, None when empty
    percentile(values, p)       linear interpolation, the same as numpy's default
    sus_grade(score)            the Sauro-Lewis curved grade letter for a SUS score
    lostness(total, distinct, required)    Smith (1996) lostness, 0 = perfect, ~1 = lost
    similarity(sorts, cards)    card-sort co-occurrence fraction per pair of cards
    average_linkage(cards, sim) UPGMA merges of the cards, deterministic
    clusters_at(cards, merges, threshold)  the clusters left when you stop merging at a similarity
    r4(x)                       round to 4 decimals

Conventions
  * "Missing" is None, never NaN and never 0. An empty or too-small sample returns None for what it
    cannot compute and still reports `n`.
  * Non-numeric entries in a values list (None, bool, str, NaN, inf) are dropped before anything is
    counted; `n` is the count of what was kept.
  * An unsupported `conf` (not 0.90 / 0.95 / 0.99 for a t interval) gives None bounds, not a guess.
"""
import math
from statistics import NormalDist

Z95 = 1.959963984540054

# Two-sided critical values of Student's t: conf -> list of (df, value), df ascending, last row = infinity
# (the normal distribution). Standard published table values to three decimals.
_T_ROWS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
           21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 40, 60, 120]
_T_TABLE = {
    0.90: [6.314, 2.920, 2.353, 2.132, 2.015, 1.943, 1.895, 1.860, 1.833, 1.812,
           1.796, 1.782, 1.771, 1.761, 1.753, 1.746, 1.740, 1.734, 1.729, 1.725,
           1.721, 1.717, 1.714, 1.711, 1.708, 1.706, 1.703, 1.701, 1.699, 1.697,
           1.684, 1.671, 1.658],
    0.95: [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
           2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
           2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042,
           2.021, 2.000, 1.980],
    0.99: [63.657, 9.925, 5.841, 4.604, 4.032, 3.707, 3.499, 3.355, 3.250, 3.169,
           3.106, 3.055, 3.012, 2.977, 2.947, 2.921, 2.898, 2.878, 2.861, 2.845,
           2.831, 2.819, 2.807, 2.797, 2.787, 2.779, 2.771, 2.763, 2.756, 2.750,
           2.704, 2.660, 2.617],
}
_T_INF = {0.90: 1.6448536269514722, 0.95: Z95, 0.99: 2.5758293035489004}

# Sauro-Lewis curved grading scale for the System Usability Scale: (lowest score, grade), best first.
_SUS_GRADES = [(84.1, "A+"), (80.8, "A"), (78.9, "A-"), (77.2, "B+"), (74.1, "B"), (72.6, "B-"),
               (71.1, "C+"), (65.0, "C"), (62.7, "C-"), (51.7, "D")]

_EPS = 1e-9   # float noise allowed when comparing similarities


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _clean(values):
    """The finite numbers of `values` as floats (a missing or bad list is empty)."""
    if not values:
        return []
    return [float(v) for v in values if _is_num(v)]


def _conf_key(conf):
    """0.90 / 0.95 / 0.99 when `conf` is one of them (float noise tolerated), else None."""
    if not _is_num(conf):
        return None
    for k in _T_TABLE:
        if abs(conf - k) < 1e-9:
            return k
    return None


def _z(conf):
    """Two-sided normal critical value for any conf in (0, 1); None otherwise."""
    if not _is_num(conf) or not 0 < conf < 1:
        return None
    if abs(conf - 0.95) < 1e-12:
        return Z95
    return NormalDist().inv_cdf(0.5 + conf / 2.0)


def r4(x):
    """Round to 4 decimals for storage. None, NaN, inf and non-numbers give None; an int stays an int;
    -0.0 becomes 0.0."""
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, int):
        return x
    if not _is_num(x):
        return None
    return round(float(x), 4) + 0.0


def adjusted_wald(x, n, conf=0.95):
    """Success rate x/n with an adjusted-Wald (Agresti-Coull) interval, good for the small samples of
    a usability test. With z = the two-sided normal value for `conf`: n' = n + z^2,
    p' = (x + z^2/2) / n', interval p' +/- z * sqrt(p'(1-p')/n'), clamped to [0, 1].

    Returns {"x","n","rate","low","high"}; `rate` is the plain x/n. n <= 0 (or no/bad input) gives
    rate/low/high None. x is clamped into 0..n; an unsupported `conf` gives None bounds, rate kept."""
    if not _is_num(x) or not _is_num(n) or n <= 0:
        return {"x": x if _is_num(x) else None, "n": n if _is_num(n) else None,
                "rate": None, "low": None, "high": None}
    n = int(n)
    x = min(max(int(x), 0), n)
    rate = x / n
    z = _z(conf)
    if z is None:
        return {"x": x, "n": n, "rate": rate, "low": None, "high": None}
    n2 = n + z * z
    p2 = (x + z * z / 2.0) / n2
    half = z * math.sqrt(p2 * (1.0 - p2) / n2)
    return {"x": x, "n": n, "rate": rate,
            "low": min(max(p2 - half, 0.0), 1.0), "high": min(max(p2 + half, 0.0), 1.0)}


def t_crit(df, conf=0.95):
    """Two-sided Student t critical value from a printed table: df 1..30, 40, 60, 120 and infinity,
    conf 0.90, 0.95 or 0.99.

    A df that is not a table row (35, 100, 2.5 ...) uses the next LOWER row (35 -> 30, 100 -> 60,
    2.5 -> 2): a slightly larger value, so the interval errs wide, never narrow. Any df >= 120 that is
    finite uses the 120 row; float("inf") uses the normal value. df < 1, None or NaN, or a conf outside
    the three, gives None."""
    k = _conf_key(conf)
    if k is None or df is None or isinstance(df, bool):
        return None
    try:
        d = float(df)
    except (TypeError, ValueError):
        return None
    if d != d or d < 1:
        return None
    if d == float("inf"):
        return _T_INF[k]
    row = _T_ROWS[0]
    for r in _T_ROWS:
        if r <= d:
            row = r
        else:
            break
    return _T_TABLE[k][_T_ROWS.index(row)]


def mean_ci(values, conf=0.95):
    """Mean with the sample sd (n - 1) and a t interval mean +/- t * sd / sqrt(n), df = n - 1.

    Returns {"n","mean","sd","low","high"}. No values: all None except n = 0. One value: mean only
    (sd/low/high None, since one point has no spread). An unsupported `conf` gives None bounds."""
    v = _clean(values)
    n = len(v)
    if n == 0:
        return {"n": 0, "mean": None, "sd": None, "low": None, "high": None}
    mean = sum(v) / n
    if n < 2:
        return {"n": n, "mean": mean, "sd": None, "low": None, "high": None}
    sd = math.sqrt(sum((a - mean) ** 2 for a in v) / (n - 1))
    t = t_crit(n - 1, conf)
    if t is None:
        return {"n": n, "mean": mean, "sd": sd, "low": None, "high": None}
    half = t * sd / math.sqrt(n)
    return {"n": n, "mean": mean, "sd": sd, "low": mean - half, "high": mean + half}


def geo_mean_ci(values, conf=0.95):
    """Geometric mean with a t interval taken on ln(values) and exponentiated back: the usual summary
    for task times, which are skewed. Values <= 0 (and non-numbers) are ignored; `n` counts the rest.

    Returns {"n","geoMean","low","high"}. None left: n = 0 and all None. One value: geoMean only."""
    logs = [math.log(v) for v in _clean(values) if v > 0]
    n = len(logs)
    if n == 0:
        return {"n": 0, "geoMean": None, "low": None, "high": None}
    ci = mean_ci(logs, conf)
    return {"n": n, "geoMean": math.exp(ci["mean"]),
            "low": math.exp(ci["low"]) if ci["low"] is not None else None,
            "high": math.exp(ci["high"]) if ci["high"] is not None else None}


def median(values):
    """The middle value (mean of the two middle ones when the count is even); None when empty."""
    v = sorted(_clean(values))
    n = len(v)
    if n == 0:
        return None
    mid = n // 2
    return v[mid] if n % 2 else (v[mid - 1] + v[mid]) / 2.0


def percentile(values, p):
    """The p-th percentile (p in 0..100, clamped) by linear interpolation between the closest ranks,
    position = p/100 * (n - 1): numpy's default. None when empty or p is not a number."""
    v = sorted(_clean(values))
    if not v or not _is_num(p):
        return None
    pos = min(max(float(p), 0.0), 100.0) / 100.0 * (len(v) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def sus_grade(score):
    """The Sauro-Lewis curved grade letter for a SUS score (0..100): A+ >= 84.1, A >= 80.8,
    A- >= 78.9, B+ >= 77.2, B >= 74.1, B- >= 72.6, C+ >= 71.1, C >= 65.0, C- >= 62.7, D >= 51.7,
    else F. None for a missing or non-numeric score. A boundary score takes the higher grade."""
    if not _is_num(score):
        return None
    for low, grade in _SUS_GRADES:
        if score >= low:
            return grade
    return "F"


def lostness(total, distinct, required):
    """Smith's (1996) lostness: L = sqrt((N/S - 1)^2 + (R/N - 1)^2) with S = `total` screens visited
    counting every revisit, N = `distinct` screens visited, R = `required` (the shortest path's
    screens). 0 is a perfect path; the usual reading is < 0.3 not lost, > 0.5 clearly lost.

    None when any of the three is below 1, not a number, or distinct > total (impossible)."""
    if not (_is_num(total) and _is_num(distinct) and _is_num(required)):
        return None
    if total < 1 or distinct < 1 or required < 1 or distinct > total:
        return None
    return math.sqrt((distinct / total - 1.0) ** 2 + (required / distinct - 1.0) ** 2)


def _order(cards):
    """`cards` without repeats, in order."""
    seen, out = set(), []
    for c in cards or []:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def similarity(sorts, cards):
    """Card-sort similarity: for each pair (a, b), a before b in `cards`, the fraction of
    participants who put the two cards in the same group.

    `sorts` is one entry per participant, each a list of groups, each a list of card ids. Denominator
    rule: only participants who placed BOTH cards in some group count (a participant who left either
    card unsorted says nothing about the pair). A pair no participant placed both of is left OUT of
    the result (no data), which `average_linkage` reads as 0. A card listed in two groups of one
    participant counts in the first. Returns {"a|b": fraction}, keys in `cards` order."""
    cards = _order(cards)
    placed = []
    for sort in sorts or []:
        where = {}
        for gi, group in enumerate(sort or []):
            for c in group or []:
                where.setdefault(c, gi)
        placed.append(where)
    out = {}
    for i, a in enumerate(cards):
        for b in cards[i + 1:]:
            denom = together = 0
            for where in placed:
                if a in where and b in where:
                    denom += 1
                    if where[a] == where[b]:
                        together += 1
            if denom:
                out[a + "|" + b] = together / denom
    return out


def average_linkage(cards, sim):
    """Agglomerative clustering by average linkage (UPGMA) on a similarity matrix: start with one
    cluster per card, repeatedly merge the two clusters with the highest mean pairwise similarity (a
    pair absent from `sim` counts as 0) until one is left.

    Returns [{"a": [ids], "b": [ids], "sim": float}] in merge order (n - 1 merges; [] for fewer than
    two cards); each id list is in `cards` order and `a` is the cluster that holds the lower first-card
    index. Deterministic: clusters are kept ordered by their first card's index, pairs are scanned in
    that order, and only a strictly higher similarity (beyond float noise) replaces the current best,
    so a tie goes to the pair with the lowest first-card indices."""
    cards = _order(cards)
    sim = sim or {}
    index = {c: i for i, c in enumerate(cards)}

    def pair(a, b):
        return sim.get(a + "|" + b, 0.0) if index[a] < index[b] else sim.get(b + "|" + a, 0.0)

    def link(ca, cb):
        return sum(pair(a, b) for a in ca for b in cb) / float(len(ca) * len(cb))

    clusters = [[c] for c in cards]
    merges = []
    while len(clusters) > 1:
        best, bi, bj = None, 0, 1
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                s = link(clusters[i], clusters[j])
                if best is None or s > best + _EPS:
                    best, bi, bj = s, i, j
        a, b = clusters[bi], clusters[bj]
        merges.append({"a": list(a), "b": list(b), "sim": best})
        merged = sorted(a + b, key=lambda c: index[c])
        clusters = [c for k, c in enumerate(clusters) if k not in (bi, bj)] + [merged]
        clusters.sort(key=lambda c: index[c[0]])
    return merges


def clusters_at(cards, merges, threshold):
    """The clusters you get by applying only the merges whose similarity is >= `threshold` (float
    noise tolerated). Each cluster lists its cards in `cards` order; clusters are ordered by their
    first card. Every card appears once; a threshold above every merge gives all singletons."""
    cards = _order(cards)
    index = {c: i for i, c in enumerate(cards)}
    parent = {c: c for c in cards}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    for m in merges or []:
        s = m.get("sim")
        if not _is_num(s) or not _is_num(threshold) or s < threshold - _EPS:
            continue
        ids = [c for c in list(m.get("a") or []) + list(m.get("b") or []) if c in index]
        for c in ids[1:]:
            ra, rb = find(ids[0]), find(c)
            if ra != rb:
                parent[rb] = ra
    groups = {}
    for c in cards:
        groups.setdefault(find(c), []).append(c)
    return sorted(groups.values(), key=lambda g: index[g[0]])
