#!/usr/bin/env python3
"""
research_stats.py (test) — pins every function of pb/tools/research_stats.py, the pure statistics
behind /pb:research's UX methods. No fixtures, no files: each expectation is either the formula worked
out below in plain arithmetic, or a published table value (Student t, the Sauro-Lewis SUS grade
cut-offs).

Usage:  python3 tests/research_stats.py
Exit:   0 = pass · 1 = a failure
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import research_stats as s  # noqa: E402

FAILS = []
CHECKS = [0]


def check(name, ok, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILS.append(name)
        print("FAIL  %s %s" % (name, detail))


def eq(name, got, want):
    check(name, got == want, "got %r, want %r" % (got, want))


def near(name, got, want, tol=1e-9):
    ok = got is not None and want is not None and abs(got - want) <= tol
    check(name, ok, "got %r, want %r (tol %g)" % (got, want, tol))


Z = 1.959963984540054

# ---------------------------------------------------------------- r4
eq("r4 None", s.r4(None), None)
eq("r4 rounds", s.r4(0.123456), 0.1235)
eq("r4 rounds down", s.r4(2.00004), 2.0)
eq("r4 int stays int", s.r4(3), 3)
eq("r4 nan -> None", s.r4(float("nan")), None)
eq("r4 inf -> None", s.r4(float("inf")), None)
eq("r4 bool -> None", s.r4(True), None)
eq("r4 str -> None", s.r4("x"), None)
check("r4 -0.0 normalised", str(s.r4(-0.00001)) == "0.0", str(s.r4(-0.00001)))

# ---------------------------------------------------------------- adjusted_wald
# z^2 = 1.959963984540054^2; n' = n + z^2; p' = (x + z^2/2) / n'; half = z * sqrt(p'(1-p')/n')


def wald(x, n):
    z2 = Z * Z
    n2 = n + z2
    p2 = (x + z2 / 2) / n2
    half = Z * math.sqrt(p2 * (1 - p2) / n2)
    return p2 - half, p2 + half


w = s.adjusted_wald(0, 5)
eq("wald 0/5 keys", sorted(w), ["high", "low", "n", "rate", "x"])
eq("wald 0/5 rate", w["rate"], 0.0)
eq("wald 0/5 low clamped to 0", w["low"], 0.0)
near("wald 0/5 high", w["high"], wald(0, 5)[1])
# worked by hand: n' = 8.84146, p' = 1.92073/8.84146 = 0.21724, half = 1.96*sqrt(0.21724*0.78276/8.84146) = 0.2718
near("wald 0/5 high by hand", w["high"], 0.4891, 5e-4)

w = s.adjusted_wald(5, 5)
eq("wald 5/5 rate", w["rate"], 1.0)
eq("wald 5/5 high clamped to 1", w["high"], 1.0)
near("wald 5/5 low", w["low"], wald(5, 5)[0])
near("wald 5/5 low is the mirror of 0/5 high", w["low"], 1 - s.adjusted_wald(0, 5)["high"])

w = s.adjusted_wald(4, 5)
near("wald 4/5 rate is x/n, not p'", w["rate"], 0.8)
near("wald 4/5 low", w["low"], wald(4, 5)[0])
near("wald 4/5 high", w["high"], wald(4, 5)[1])
check("wald 4/5 bounds bracket the rate", w["low"] < 0.8 < w["high"])
eq("wald 4/5 echoes x, n", (w["x"], w["n"]), (4, 5))

w = s.adjusted_wald(0, 0)
eq("wald 0/0", w, {"x": 0, "n": 0, "rate": None, "low": None, "high": None})
eq("wald None n", s.adjusted_wald(3, None)["rate"], None)
eq("wald negative n", s.adjusted_wald(0, -2)["rate"], None)
eq("wald x clamped above n", s.adjusted_wald(9, 5)["x"], 5)
eq("wald x clamped below 0", s.adjusted_wald(-1, 5)["x"], 0)
# conf 0.90 uses z = 1.6448536...; the interval is narrower than 0.95
w90, w95 = s.adjusted_wald(3, 10, 0.90), s.adjusted_wald(3, 10, 0.95)
check("wald 0.90 narrower than 0.95", (w90["high"] - w90["low"]) < (w95["high"] - w95["low"]))
eq("wald bad conf keeps rate, no bounds", (s.adjusted_wald(3, 10, 1.5)["rate"], s.adjusted_wald(3, 10, 1.5)["low"]),
   (0.3, None))

# ---------------------------------------------------------------- t_crit
eq("t df=10 conf .95", s.t_crit(10), 2.228)
eq("t df=4 conf .95", s.t_crit(4, 0.95), 2.776)
eq("t df=1 conf .95", s.t_crit(1), 12.706)
eq("t df=2 conf .95", s.t_crit(2), 4.303)
eq("t df=30 conf .99", s.t_crit(30, 0.99), 2.750)
eq("t df=1 conf .99", s.t_crit(1, 0.99), 63.657)
eq("t df=5 conf .90", s.t_crit(5, 0.90), 2.015)
eq("t df=40 conf .95", s.t_crit(40), 2.021)
eq("t df=60 conf .95", s.t_crit(60), 2.000)
eq("t df=120 conf .95", s.t_crit(120), 1.980)
eq("t df=120 conf .90", s.t_crit(120, 0.90), 1.658)
# between rows: the next LOWER row
eq("t df=35 -> 30 row", s.t_crit(35), 2.042)
eq("t df=39 -> 30 row", s.t_crit(39), 2.042)
eq("t df=100 -> 60 row", s.t_crit(100), 2.000)
eq("t df=500 -> 120 row", s.t_crit(500), 1.980)
eq("t df=2.9 -> 2 row", s.t_crit(2.9), 4.303)
eq("t df=10.0 float is the row", s.t_crit(10.0), 2.228)
near("t inf conf .95", s.t_crit(float("inf")), 1.96, 1e-3)
near("t inf conf .90", s.t_crit(float("inf"), 0.90), 1.645, 1e-3)
near("t inf conf .99", s.t_crit(float("inf"), 0.99), 2.576, 1e-3)
eq("t df=0 -> None", s.t_crit(0), None)
eq("t df=0.5 -> None", s.t_crit(0.5), None)
eq("t df=-3 -> None", s.t_crit(-3), None)
eq("t df=None -> None", s.t_crit(None), None)
eq("t df=nan -> None", s.t_crit(float("nan")), None)
eq("t conf .80 -> None", s.t_crit(10, 0.80), None)
eq("t conf None -> None", s.t_crit(10, None), None)
# monotone: more df never raises the critical value
for conf in (0.90, 0.95, 0.99):
    seq = [s.t_crit(d, conf) for d in list(range(1, 31)) + [40, 60, 120, float("inf")]]
    check("t table non-increasing at %.2f" % conf, all(a >= b for a, b in zip(seq, seq[1:])), str(seq))
    check("t table has 34 rows at %.2f" % conf, len(seq) == 34 and None not in seq)

# ---------------------------------------------------------------- mean_ci
# values 1..5: mean 3, sample variance = (4+1+0+1+4)/4 = 2.5, sd = sqrt(2.5)
# margin = t(4) * sd / sqrt(5) = 2.776 * sqrt(2.5/5) = 2.776 * sqrt(0.5)
m = s.mean_ci([1, 2, 3, 4, 5])
eq("mean_ci keys", sorted(m), ["high", "low", "mean", "n", "sd"])
eq("mean_ci n", m["n"], 5)
near("mean_ci mean", m["mean"], 3.0)
near("mean_ci sd", m["sd"], math.sqrt(2.5))
near("mean_ci low", m["low"], 3 - 2.776 * math.sqrt(0.5))
near("mean_ci high", m["high"], 3 + 2.776 * math.sqrt(0.5))
# conf 0.99 at df 4 = 4.604
near("mean_ci .99 high", s.mean_ci([1, 2, 3, 4, 5], 0.99)["high"], 3 + 4.604 * math.sqrt(0.5))
# two values 10, 20: mean 15, sd = sqrt(50) ; margin = 12.706 * sqrt(50)/sqrt(2) = 12.706 * 5
near("mean_ci n=2 high", s.mean_ci([10, 20])["high"], 15 + 12.706 * 5)
eq("mean_ci empty", s.mean_ci([]), {"n": 0, "mean": None, "sd": None, "low": None, "high": None})
eq("mean_ci None input", s.mean_ci(None)["n"], 0)
eq("mean_ci n=1", s.mean_ci([7]), {"n": 1, "mean": 7.0, "sd": None, "low": None, "high": None})
eq("mean_ci identical values: sd 0", (s.mean_ci([4, 4, 4])["sd"], s.mean_ci([4, 4, 4])["low"]), (0.0, 4.0))
eq("mean_ci drops junk", s.mean_ci([1, None, "x", True, float("nan"), 3])["n"], 2)
eq("mean_ci bad conf -> None bounds", (s.mean_ci([1, 2, 3], 0.8)["mean"], s.mean_ci([1, 2, 3], 0.8)["low"]), (2.0, None))

# ---------------------------------------------------------------- geo_mean_ci
# values e^1 .. e^5: ln = 1..5, so the log interval is 3 +/- 2.776*sqrt(0.5); the geo mean is e^3
e = math.exp
g = s.geo_mean_ci([e(1), e(2), e(3), e(4), e(5)])
eq("geo keys", sorted(g), ["geoMean", "high", "low", "n"])
eq("geo n", g["n"], 5)
near("geo mean", g["geoMean"], e(3))
near("geo low", g["low"], e(3 - 2.776 * math.sqrt(0.5)))
near("geo high", g["high"], e(3 + 2.776 * math.sqrt(0.5)))
check("geo mean below arithmetic mean", g["geoMean"] < sum([e(1), e(2), e(3), e(4), e(5)]) / 5)
# non-positive values and junk are ignored, and not counted in n
g2 = s.geo_mean_ci([e(1), 0, e(2), -5, e(3), e(4), None, e(5), "x"])
eq("geo ignores <= 0: n", g2["n"], 5)
near("geo ignores <= 0: same mean", g2["geoMean"], g["geoMean"])
near("geo ignores <= 0: same high", g2["high"], g["high"])
# 4 and 9: ln 4 + ln 9 = ln 36, mean = ln 6, so the geometric mean is 6
near("geo of 4 and 9", s.geo_mean_ci([4, 9])["geoMean"], 6.0)
eq("geo empty", s.geo_mean_ci([]), {"n": 0, "geoMean": None, "low": None, "high": None})
eq("geo all non-positive", s.geo_mean_ci([0, -1])["n"], 0)
g1 = s.geo_mean_ci([12])
eq("geo n=1: n", g1["n"], 1)
near("geo n=1: mean", g1["geoMean"], 12.0)
eq("geo n=1: no interval", (g1["low"], g1["high"]), (None, None))

# ---------------------------------------------------------------- median / percentile
eq("median odd", s.median([3, 1, 2]), 2.0)
eq("median even", s.median([4, 1, 3, 2]), 2.5)
eq("median one", s.median([9]), 9.0)
eq("median empty", s.median([]), None)
eq("median None", s.median(None), None)
eq("median ignores junk", s.median([1, None, 3, "a"]), 2.0)
eq("percentile empty", s.percentile([], 50), None)
eq("percentile p None", s.percentile([1, 2], None), None)
eq("percentile p=0 is min", s.percentile([5, 1, 3], 0), 1.0)
eq("percentile p=100 is max", s.percentile([5, 1, 3], 100), 5.0)
eq("percentile p=50 odd", s.percentile([5, 1, 3], 50), 3.0)
eq("percentile p=50 even = median", s.percentile([1, 2, 3, 4], 50), s.median([1, 2, 3, 4]))
# position = p/100 * (n-1). [10,20,30,40]: p=25 -> 0.75 -> 10 + 0.75*10 = 17.5 ; p=90 -> 2.7 -> 30 + 0.7*10 = 37
near("percentile p=25 even", s.percentile([10, 20, 30, 40], 25), 17.5)
near("percentile p=90 even", s.percentile([10, 20, 30, 40], 90), 37.0)
near("percentile p=25 of 1..5 lands on a rank", s.percentile([1, 2, 3, 4, 5], 25), 2.0)
eq("percentile one value", s.percentile([7], 80), 7.0)
eq("percentile p clamped high", s.percentile([1, 2, 3], 250), 3.0)
eq("percentile p clamped low", s.percentile([1, 2, 3], -10), 1.0)

# ---------------------------------------------------------------- sus_grade
CUTS = [(84.1, "A+"), (80.8, "A"), (78.9, "A-"), (77.2, "B+"), (74.1, "B"), (72.6, "B-"),
        (71.1, "C+"), (65.0, "C"), (62.7, "C-"), (51.7, "D")]
LOWER = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]
for (cut, grade), below in zip(CUTS, LOWER):
    eq("sus %.1f is %s" % (cut, grade), s.sus_grade(cut), grade)
    eq("sus just under %.1f is %s" % (cut, below), s.sus_grade(round(cut - 0.01, 2)), below)
eq("sus 100", s.sus_grade(100), "A+")
eq("sus 0", s.sus_grade(0), "F")
eq("sus 68 (the usual average) is C", s.sus_grade(68), "C")
eq("sus 70 is C", s.sus_grade(70), "C")
eq("sus None", s.sus_grade(None), None)
eq("sus str", s.sus_grade("80"), None)
eq("sus nan", s.sus_grade(float("nan")), None)

# ---------------------------------------------------------------- lostness
# Smith: L = sqrt((N/S - 1)^2 + (R/N - 1)^2), S = screens visited counting revisits, N = distinct, R = required
eq("lostness perfect path", s.lostness(3, 3, 3), 0.0)
eq("lostness perfect one-screen task", s.lostness(1, 1, 1), 0.0)
# S=5, N=3, R=3: (3/5 - 1)^2 = 0.16 ; (3/3 - 1)^2 = 0 ; sqrt(0.16) = 0.4
near("lostness revisits only", s.lostness(5, 3, 3), 0.4)
# S=6, N=4, R=3: (4/6 - 1)^2 = 1/9 ; (3/4 - 1)^2 = 1/16 ; sqrt(25/144) = 5/12
near("lostness revisits and a detour", s.lostness(6, 4, 3), 5.0 / 12.0)
# S=N=4, R=2: no revisits, (2/4 - 1)^2 = 0.25 -> 0.5
near("lostness wandered, no revisits", s.lostness(4, 4, 2), 0.5)
eq("lostness total 0", s.lostness(0, 0, 0), None)
eq("lostness distinct 0", s.lostness(3, 0, 2), None)
eq("lostness required 0", s.lostness(3, 3, 0), None)
eq("lostness distinct > total", s.lostness(2, 3, 2), None)
eq("lostness None", s.lostness(None, 1, 1), None)

# ---------------------------------------------------------------- similarity / average_linkage / clusters_at
CARDS = ["a", "b", "c", "d"]
SORTS = [
    [["a", "b"], ["c", "d"]],        # P1
    [["a", "b", "c"], ["d"]],        # P2
    [["a", "c"], ["b", "d"]],        # P3
]
# pair   P1 P2 P3  fraction
# a|b    1  1  0   2/3
# a|c    0  1  1   2/3
# a|d    0  0  0   0
# b|c    0  1  0   1/3
# b|d    0  0  1   1/3
# c|d    1  0  0   1/3
sim = s.similarity(SORTS, CARDS)
eq("similarity keys, cards order", list(sim), ["a|b", "a|c", "a|d", "b|c", "b|d", "c|d"])
near("sim a|b", sim["a|b"], 2 / 3)
near("sim a|c", sim["a|c"], 2 / 3)
near("sim a|d", sim["a|d"], 0.0)
near("sim b|c", sim["b|c"], 1 / 3)
near("sim b|d", sim["b|d"], 1 / 3)
near("sim c|d", sim["c|d"], 1 / 3)
# key order follows `cards`, not the alphabet
eq("similarity key order follows cards", list(s.similarity([[["z", "y"]]], ["z", "y"])), ["z|y"])
eq("similarity reversed cards -> reversed key", list(s.similarity([[["z", "y"]]], ["y", "z"])), ["y|z"])

# UPGMA by hand (ties go to the lowest first-card pair):
#  step 1: max is 2/3, shared by a|b and a|c -> the pair (a, b) comes first          merge [a]+[b] at 2/3
#  step 2: sim([a,b],c) = (a|c + b|c)/2 = (2/3 + 1/3)/2 = 1/2 ; sim([a,b],d) = (0 + 1/3)/2 = 1/6 ;
#          sim(c,d) = 1/3                                                              merge [a,b]+[c] at 1/2
#  step 3: sim([a,b,c],d) = (0 + 1/3 + 1/3)/3 = 2/9                                    merge at 2/9
merges = s.average_linkage(CARDS, sim)
eq("linkage merge count", len(merges), 3)
eq("linkage step 1 members", (merges[0]["a"], merges[0]["b"]), (["a"], ["b"]))
near("linkage step 1 sim", merges[0]["sim"], 2 / 3)
eq("linkage step 2 members", (merges[1]["a"], merges[1]["b"]), (["a", "b"], ["c"]))
near("linkage step 2 sim", merges[1]["sim"], 0.5)
eq("linkage step 3 members", (merges[2]["a"], merges[2]["b"]), (["a", "b", "c"], ["d"]))
near("linkage step 3 sim", merges[2]["sim"], 2 / 9)
eq("linkage merge keys", sorted(merges[0]), ["a", "b", "sim"])
check("linkage similarities never rise", all(x["sim"] >= y["sim"] - 1e-12 for x, y in zip(merges, merges[1:])))
eq("linkage is deterministic", s.average_linkage(CARDS, sim), merges)

eq("clusters thr .9 -> singletons", s.clusters_at(CARDS, merges, 0.9), [["a"], ["b"], ["c"], ["d"]])
eq("clusters thr .6 -> a+b", s.clusters_at(CARDS, merges, 0.6), [["a", "b"], ["c"], ["d"]])
eq("clusters thr 2/3 exactly includes the 2/3 merge", s.clusters_at(CARDS, merges, 2 / 3), [["a", "b"], ["c"], ["d"]])
eq("clusters thr .5 exactly includes the .5 merge", s.clusters_at(CARDS, merges, 0.5), [["a", "b", "c"], ["d"]])
eq("clusters thr .3", s.clusters_at(CARDS, merges, 0.3), [["a", "b", "c"], ["d"]])
eq("clusters thr .2 -> one cluster", s.clusters_at(CARDS, merges, 0.2), [["a", "b", "c", "d"]])
eq("clusters thr 0 -> one cluster", s.clusters_at(CARDS, merges, 0), [["a", "b", "c", "d"]])
eq("clusters no merges", s.clusters_at(CARDS, [], 0.5), [["a"], ["b"], ["c"], ["d"]])

# the denominator is the participants who placed BOTH cards:
#  P1 places a,b,c ; P2 places a,c only (b left unsorted)
#  a|b: only P1 placed both -> 1/1 ; a|c: P1 apart, P2 together -> 1/2 ; b|c: only P1, apart -> 0/1
sim2 = s.similarity([[["a", "b"], ["c"]], [["a", "c"]]], ["a", "b", "c"])
near("denominator: a|b", sim2["a|b"], 1.0)
near("denominator: a|c", sim2["a|c"], 0.5)
near("denominator: b|c", sim2["b|c"], 0.0)
# a pair nobody placed both of has no entry (no data), and a card nobody placed is in no pair
sim3 = s.similarity([[["a", "b"]]], ["a", "b", "e"])
eq("no-data pairs are omitted", list(sim3), ["a|b"])
eq("no participants", s.similarity([], ["a", "b"]), {})
eq("no cards", s.similarity(SORTS, []), {})
eq("duplicate cards collapse", list(s.similarity([[["a", "b"]]], ["a", "a", "b"])), ["a|b"])
# a card named twice by one participant counts in its first group: a in g0 and g1, b in g1 -> apart
near("card in two groups: first wins", s.similarity([[["a"], ["a", "b"]]], ["a", "b"])["a|b"], 0.0)

# missing pairs count as 0 in linkage; with no similarity at all, merge order is the card order
m0 = s.average_linkage(["a", "b", "c", "d"], {})
eq("no sim: merge 1", (m0[0]["a"], m0[0]["b"], m0[0]["sim"]), (["a"], ["b"], 0.0))
eq("no sim: merge 2", (m0[1]["a"], m0[1]["b"]), (["a", "b"], ["c"]))
eq("no sim: merge 3", (m0[2]["a"], m0[2]["b"]), (["a", "b", "c"], ["d"]))
# a tie not involving card 0: b|c = c|d = 1, all else 0 -> (b,c) is merged first (lower first-card index)
m1 = s.average_linkage(["a", "b", "c", "d"], {"b|c": 1.0, "c|d": 1.0})
eq("tie: lowest pair first", (m1[0]["a"], m1[0]["b"], m1[0]["sim"]), (["b"], ["c"], 1.0))
# then [b,c] vs d = (0 + 1)/2 = 1/2 beats a vs [b,c] = 0 and a vs d = 0
eq("tie: next merge", (m1[1]["a"], m1[1]["b"]), (["b", "c"], ["d"]))
near("tie: next sim", m1[1]["sim"], 0.5)
eq("tie: last merge", (m1[2]["a"], m1[2]["b"]), (["a"], ["b", "c", "d"]))
# a cluster's ids come out in `cards` order even when merged out of order
m2 = s.average_linkage(["x", "y", "z"], {"x|z": 1.0})
eq("out-of-order merge, cards order", (m2[0]["a"], m2[0]["b"]), (["x"], ["z"]))
eq("then the remaining card", (m2[1]["a"], m2[1]["b"]), (["x", "z"], ["y"]))
eq("linkage no cards", s.average_linkage([], {}), [])
eq("linkage one card", s.average_linkage(["a"], {}), [])
eq("clusters one card", s.clusters_at(["a"], [], 0.5), [["a"]])
eq("clusters no cards", s.clusters_at([], [], 0.5), [])
# clusters in `cards` order, listed by first card
eq("clusters ordered by first card", s.clusters_at(["x", "y", "z"], m2, 0.9), [["x", "z"], ["y"]])

# ---------------------------------------------------------------- done
if FAILS:
    print("FAIL: %d of %d checks failed: %s" % (len(FAILS), CHECKS[0], ", ".join(FAILS)))
    sys.exit(1)
print("PASS: research_stats — %d checks" % CHECKS[0])
sys.exit(0)
