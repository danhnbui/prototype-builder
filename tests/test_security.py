#!/usr/bin/env python3
"""
test_security.py — unit tests for pb/tools/security_scan.py.

Pure Python: asserts the scanner flags a seeded hardcoded key + real-looking email in
fixtures/security_bad/, masks the secret (never re-leaks it), stays clean (exit 0) on the
committed golden, keeps its exit codes and line format — and then runs a table of positive and
negative cases through scan_text for every detector and every false-positive guard, the files
scan() reads beyond the render bodies, and the --dir mode.

Every fake credential below is built by runtime concatenation (`"ghp_" + "…"`): this repo's history
is scanned by a secret scanner, and a literal token-shaped string would fail it.

Usage:  python3 tests/test_security.py
Exit:   0 = all passed · 1 = a failure
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN = os.path.join(ROOT, "pb", "tools", "security_scan.py")
BAD = os.path.join(ROOT, "fixtures", "security_bad", "registry.json")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")
LEAKED_VALUE = "sk-abc123DEF456ghi789JKL012mno345"  # the literal seeded in the bad fixture

_spec = importlib.util.spec_from_file_location("security_scan", SCAN)
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)

_failures = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _failures.append(msg)


def run(*args):
    return subprocess.run([sys.executable, SCAN, *args], capture_output=True, text=True)


def findings(text, where="note.text"):
    out = []
    ss.scan_text(lambda sev, code, w, msg: out.append((sev, code, w, msg)), text, where)
    return out


def kinds(text, where="note.text"):
    return sorted({(f[0], f[1]) for f in findings(text, where)})


# ── fake credentials, assembled at run time ──────────────────────────────────
B36 = "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"      # 36 chars: a GitHub token body
B20 = "aB3dE5fG7hJ9kL1mN3pQ"                      # 20 chars
RND40 = "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5bC7d"  # 40 chars, mixed case + digits
HEX40 = "9f86d081884c7d65" + "9a2feaa0c55ad015a3bf4f1b"
JWT = ("eyJ" + "hbGciOiJIUzI1NiJ9" + "." + "eyJ" + "zdWIiOiJ1MTIzNDU2In0" + "." + "dBjftJeZ4CVPmB92K27uhbUJU1p1r")
assert len(B36) == 36 and len(B20) == 20 and len(RND40) == 40 and len(HEX40) == 40

SHAPE_CASES = [
    # (label, text before the secret, the secret, text after it, the words the message must carry)
    ("GitHub classic ghp_", "t = ", "ghp_" + B36, "", "GitHub token"),
    ("GitHub gho_", "t = ", "gho_" + B36, "", "GitHub token"),
    ("GitHub ghu_", "t = ", "ghu_" + B36, "", "GitHub token"),
    ("GitHub ghs_", "t = ", "ghs_" + B36, "", "GitHub token"),
    ("GitHub ghr_", "t = ", "ghr_" + B36, "", "GitHub token"),
    ("GitHub fine-grained", "t = ", "github_pat_" + "11AB1CD2E0" + "_" + B36 + B20, "", "GitHub token"),
    ("GitLab PAT", "t = ", "glpat-" + B20, "", "GitLab token"),
    ("Slack bot token", "t = ", "xox" + "b-" + "123456789012-1234567890123-" + B20, "", "Slack token"),
    ("Slack user token", "t = ", "xox" + "p-" + "123456789012-" + B20, "", "Slack token"),
    ("Google API key", "k = ", "AIza" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q", "", "Google API key"),
    ("Stripe live secret", "k = ", "sk_" + "live_" + "4eC39HqLyjWDarjtT1zdp7dc", "", "Stripe live key"),
    ("Stripe live restricted", "k = ", "rk_" + "live_" + "4eC39HqLyjWDarjtT1zdp7dc", "", "Stripe live key"),
    ("Figma PAT", "k = ", "figd_" + RND40, "", "Figma token"),
    ("JWT", "t = ", JWT, "", "JWT"),
    ("credentials in a URL", "u = https://alice:", "Zk39dkP2qa", "@db.internal.net/app", "URL carries a password"),
    ("Authorization: Bearer", "Authorization: Bearer ", B20, "", "Bearer token"),
    ("bare Bearer", "send Bearer ", B20, " back", "Bearer token"),
]

QUIET_CASES = [
    # a placeholder or look-alike that must stay silent, whole stop
    ("Bearer ${token}", "headers: { Authorization: `Bearer ${token}` }"),
    ("Bearer <token>", "Authorization: Bearer <token>"),
    ("Bearer {token}", "Authorization: Bearer {token}"),
    ("Bearer env", "Authorization: Bearer ${process.env.API_TOKEN}"),
    ("Bearer prose", "Use the Bearer authentication scheme for this endpoint."),
    ("Bearer concatenation", "'Bearer ' + session.accessToken"),
    ("URL with user:password@example.com", "https://user:password@example.com"),
    ("URL with ${} credentials", "https://${DB_USER}:${DB_PASS}@db.internal.net/app"),
    ("URL without credentials", "postgres://localhost:5432/app and https://example.com/a/b"),
    ("process.env.X", "const k = process.env.GITHUB_TOKEN;"),
    ("placeholder GitHub token", "t = " + "ghp_" + "x" * 36),
    ("placeholder Stripe key", "k = " + "sk_" + "live_" + "x" * 24),
    ("sk_test is not live", "k = " + "sk_" + "test_" + "4eC39HqLyjWDarjtT1zdp7dc"),
]

PII_CASES = [
    # (label, text, country tag in the message)
    ("VN bare", "call 0912345678 now", "VN"),
    ("VN spaced 4-3-3", "call 0912 345 678 now", "VN"),
    ("VN spaced 3-3-4", "call 091 234 5678 now", "VN"),
    ("VN dotted", "call 0912.345.678 now", "VN"),
    ("VN dashed", "call 091-234-5678 now", "VN"),
    ("VN +84 spaced", "call +84 912 345 678 now", "VN"),
    ("VN +84 bare", "call +84912345678 now", "VN"),
    ("VN +84 dotted", "call +84.912.345.678 now", "VN"),
    ("VN (+84) form", "call (+84) 912 345 678 now", "VN"),
    ("VN 03x prefix", "call 0321234567 now", "VN"),
    ("VN 05x prefix", "call 0561234567 now", "VN"),
    ("VN 07x prefix", "call 0771234567 now", "VN"),
    ("VN 08x prefix", "call 0881234567 now", "VN"),
    ("US dotted", "call 415.555.0134 now", "US"),
    ("US parens", "call (415) 555-0134 now", "US"),
    ("US dashed", "call 415-555-0134 now", "US"),
    ("US +1", "call +1 415 555 0134 now", "US"),
    ("E.164 bare", "call +442071838750 now", "E.164"),
    ("E.164 spaced", "call +44 20 7183 8750 now", "E.164"),
    ("E.164 short groups", "call +33 1 42 68 53 00 now", "E.164"),
    ("VN national ID", "id 079201012345 on file", "national ID"),
    ("test card, bare", "card 4242424242424242", "card"),
    ("test card, grouped", "card 4111 1111 1111 1111", "card"),
    ("test card, dashed", "card 4111-1111-1111-1111", "card"),
    ("SSN", "ssn 123-45-6789", "SSN"),
]

QUIET_PII = [
    ("coordinate 106.7123456", "lng 106.7123456"),
    ("coordinate 999.9999999", "lat 999.9999999"),
    ("lat,lng pair", "10.7769,106.7009"),
    ("epoch ms", "ts 1700000000000"),
    ("numeric id (fails Luhn)", "order 20240512123456"),
    ("16 digits, not Luhn", "id 1234567890123456"),
    ("two 7-digit ids", "pair 1234567-7654321"),
    ("version 1.2.3", "v 1.2.3.4567"),
    ("not a VN prefix", "n 0112345678"),
    ("mixed separators", "n 415.555-0134"),
    ("date", "d 2024-05-12"),
]

FP_CASES = [
    # a value that used to be an ERROR and is not one
    ("data: URI payload",
     "background:url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==)"),
    ("SVG path data",
     '<path d="M10.5 20.25 L30 40 C 100 200 300 400 500 600 700 800 900 1000 1100 1200 L 4111 1111 1111 1111"/>'),
    ("Figma file path", "https://www.figma.com/design/" + "AbCdEf0123456789GhIjKlMnOp" + "/Project-Name"),
    ("camelCase identifier", "renderScreenOrderSummary2DetailCard3VariantPrimary9AltLayout"),
    ("token key: --var", '{"token": "--color-brand-primary"}'),
    ("token key: dotted", "token: 'color.brand.500'"),
    ("token key: {ref}", 'token="{color.brand.500}"'),
    ("token key: hyphenated", 'token: "brand-primary-hover"'),
    ("git commit id", '{"reviewCommit":"' + HEX40 + '"}'),
]

DESIGN_KEY_WHERE = [
    "components[3].dsMatch.figmaSetKey",
    "components[3].dsMatch.figmaComponentKey",
    "components[3].dsMatch.componentKey",
    "components[3].dsMatch.setKey",
    "components[3].dsMatch.styleKey",
    "components[3].dsMatch.key",
    "tokens.radius.md.$extensions.com.figma.key",
    "tokens.space.2.$extensions.com.figma.key.gap",
]


def project(files, registry=None):
    """A temp project folder holding `files` ({relative path: text}) and a registry.json."""
    d = tempfile.mkdtemp(prefix="pb-sec-")
    reg = registry if registry is not None else {"meta": {"name": "T"}, "components": [], "screens": []}
    files = dict(files)
    files["registry.json"] = json.dumps(reg)
    for rel, text in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
    return d


def scan_project(d):
    with open(os.path.join(d, "registry.json"), encoding="utf-8") as f:
        return ss.scan(json.load(f), d)


def main():
    print("security_scan.py:")

    p = run(BAD)
    out = p.stdout + p.stderr
    check(p.returncode == 2, f"seeded-secret fixture -> exit 2 (got {p.returncode})")
    check("R-SEC-KEY" in out, "flags the hardcoded API key (R-SEC-KEY)")
    check("R-SEC-EMAIL" in out or "R-SEC-PII" in out, "flags the real-looking email / PII")
    check(LEAKED_VALUE not in out, "masks the secret in output (never re-leaks the literal)")

    p = run(GOLDEN)
    check(p.returncode == 0,
          f"clean golden -> exit 0 (got {p.returncode}; out={(p.stdout + p.stderr).strip()[:240]})")

    print("\nexit codes and line format are the contract other tools read:")
    lines = [ln for ln in run(BAD).stdout.splitlines() if ln.startswith(("ERROR", "WARN"))]
    shape = re.compile(r"^(ERROR|WARN) \[R-SEC-(KEY|EMAIL|PII)\] \S+: \S.*$")
    check(lines and all(shape.match(ln) for ln in lines),
          f"every finding is `<SEVERITY> [<CODE>] <location>: <message>` ({len(lines)} lines)")
    check(run(BAD).stdout.rstrip().splitlines()[-1].startswith("security_scan.py: "),
          "the last line is the `security_scan.py: N error(s), M warning(s)` summary")
    warn_only = project({}, {"meta": {"name": "T"}, "note": "reach me at jane.doe.customer@gmail.com"})
    p = run(os.path.join(warn_only, "registry.json"))
    check(p.returncode == 1 and "WARN [R-SEC-EMAIL]" in p.stdout, f"warnings only -> exit 1 (got {p.returncode})")
    check(run(os.path.join(warn_only, "nope.json")).returncode == 2, "a missing registry -> exit 2")
    check(run().returncode != 0 and run("a", "b").returncode != 0, "wrong arguments -> usage, non-zero")
    check(callable(ss.scan) and callable(ss.scan_text) and callable(ss.iter_leaves) and ss.Finding,
          "scan, scan_text, iter_leaves and Finding are still importable")
    check(ss.scan({"meta": {}}, ".") == [], "scan(reg, base_dir) still takes a registry dict")

    print("\nsecret detectors (R-SEC-KEY, ERROR, masked):")
    for label, before, lit, after, words in SHAPE_CASES:
        fs = findings(before + lit + after)
        errs = [f for f in fs if f[0] == ss.ERROR and f[1] == "R-SEC-KEY"]
        check(any(words in f[3] for f in errs), f"fires: {label}")
        check(not any(lit in f[3] for f in fs), f"  and masks it: {label}")
    for label, text in QUIET_CASES:
        check(findings(text) == [], f"silent: {label}")

    print("\nPII (R-SEC-PII, WARN, never ERROR):")
    for label, text, tag in PII_CASES:
        fs = findings(text)
        check(any(f[0] == ss.WARN and f[1] == "R-SEC-PII" and tag in f[3] for f in fs),
              f"warns: {label}")
        check(not any(f[0] == ss.ERROR for f in fs), f"  and is not an error: {label}")
    for label, text in QUIET_PII:
        check(findings(text) == [], f"silent: {label}")
    nid = findings("id 079201012345 on file")
    check(nid and "079201012345" not in nid[0][3], "a national ID is masked in the message")
    check([f[1] for f in findings("call +84 912 345 678 now")] == ["R-SEC-PII"],
          "one number is one finding (VN row wins over E.164)")
    check(("WARN", "R-SEC-EMAIL") in kinds("jane.doe.customer@gmail.com")
          and kinds("user@example.com") == [], "email: real warns, placeholder is silent")

    print("\nfalse-positive guards:")
    for label, text in FP_CASES:
        check(findings(text) == [], f"silent: {label}")
    for where in DESIGN_KEY_WHERE:
        check(findings(HEX40, where) == [], f"design-tool key is safe under {where}")
    check(findings(HEX40, "components[3].name") != [], "...but the same hex under another key still fires")
    check(findings(HEX40.upper(), "components[3].dsMatch.figmaSetKey") != [],
          "...a different shape (uppercase hex) under a design key still fires")
    check(findings(HEX40 + "ab", "components[3].dsMatch.figmaSetKey") != [],
          "...a longer hex under a design key still fires")
    check(findings(RND40, "components[3].dsMatch.figmaSetKey") != [],
          "...a base64-looking secret under a design key still fires")
    check(any(f[1] == "R-SEC-KEY" for f in findings("ghp_" + B36, "components[3].dsMatch.figmaSetKey")),
          "...a provider token under a design key still fires")
    check(findings("figmaSetKey: '" + HEX40 + "'", "render/components/a.js") == [],
          "design key written in a render body is safe")
    check(findings("note: '" + HEX40 + "'", "render/components/a.js") != [],
          "...the same hex under another name in a render body fires")
    check(findings('password: "color.brand.500"') != [], "the token-reference pass is for `token` only")
    check(findings('token: "a3f9-2b7c-91de-44aa-77be"') != [],
          "a hyphenated token that is not a name (a3f9-2b7c-…) still fires")
    check(findings('token: "' + RND40 + '"') != [], "a random value under `token` still fires")
    reg = {"meta": {}, "ia": {"rules": [{"blocks": [{"items": [{"token": "color.brand.500"}]}]}]}}
    check(ss.scan(reg, ".") == [], "a `token` leaf holding a design-token name is not a secret")
    reg = {"meta": {}, "ia": {"rules": [{"blocks": [{"items": [{"token": RND40}]}]}]}}
    check(any(f.code == "R-SEC-KEY" for f in ss.scan(reg, ".")), "a `token` leaf holding a random value is")
    check(len(ss.scan({"meta": {}, "apiKey": "ghp_" + B36}, ".")) == 1,
          "a leaf the scan already flagged is not flagged twice by its key name")
    check(any(f.code == "R-SEC-KEY" for f in ss.scan({"meta": {}, "password": "Zk39dkP2qaLm"}, ".")),
          "a secret-named key holding a literal still fires")
    check(findings("data:image/png;base64," + RND40 * 4 + " ghp_" + B36) != [],
          "a real token next to a data: URI still fires")

    print("\nwhat scan() reads beyond the render bodies:")
    fake_value = "ghp_" + B36
    cases = [
        ("runtime[].src", {"runtime/seed.js": "const k = '" + fake_value + "';"},
         {"runtime": [{"id": "seed", "src": "runtime/seed.js"}]}, "runtime/seed.js"),
        ("styleSrc", {"render/styles/a.css": "/* " + fake_value + " */"},
         {"components": [{"id": "a", "level": "atom", "styleSrc": "render/styles/a.css"}]},
         "render/styles/a.css"),
        ("specSrc", {"spec/components/a.json": json.dumps({"usage": {"note": fake_value}})},
         {"components": [{"id": "a", "level": "atom", "specSrc": "spec/components/a.json"}]},
         "spec/components/a.json"),
        ("logicSrc", {"logic/screens/s.json": json.dumps({"notes": [{"text": fake_value}]})},
         {"screens": [{"id": "s", "logicSrc": "logic/screens/s.json"}]}, "logic/screens/s.json"),
        ("render/_candidates", {"render/_candidates/r1/a/slot1.js": "return '" + fake_value + "';"},
         {}, "render/_candidates/r1/a/slot1.js"),
        ("renderSrc (as before)", {"render/components/a.js": "return '" + fake_value + "';"},
         {"components": [{"id": "a", "level": "atom", "renderSrc": "render/components/a.js"}]},
         "render/components/a.js"),
    ]
    for label, files, extra, where in cases:
        reg = {"meta": {"name": "T"}, "components": [], "screens": []}
        reg.update(extra)
        d = project(files, reg)
        fs = scan_project(d)
        check(any(f.severity == ss.ERROR and f.code == "R-SEC-KEY" and f.where.startswith(where) for f in fs),
              f"a secret only in {label} fires")
        clean = project({k: "nothing here" if not k.endswith(".json") else "{}" for k in files}, reg)
        check(scan_project(clean) == [], f"...and the same file without it is clean ({label})")
    reg = {"meta": {}, "components": [{"id": "a", "level": "atom", "specSrc": "spec/none.json",
                                       "styleSrc": "render/styles/none.css"}], "runtime": [{"src": "runtime/none.js"}]}
    check(ss.scan(reg, tempfile.mkdtemp(prefix="pb-sec-")) == [], "a missing referenced file is skipped, not an error")
    d = project({"spec/components/a.json": json.dumps({"elements": {"x": {"figmaSetKey": HEX40}}})},
                {"meta": {}, "components": [{"id": "a", "level": "atom", "specSrc": "spec/components/a.json"}]})
    check(scan_project(d) == [], "a sidecar's design-tool key is read by its key name too")

    print("\n--dir <folder>:")
    d = project({
        "notes.md": "token " + fake_value,
        "prototype.html": "<p>" + fake_value + "</p>",
        "design-system.html": "<p>" + fake_value + "</p>",
        "pb/tools/x.js": "const k = '" + fake_value + "';",
        "node_modules/a/index.js": "const k = '" + fake_value + "';",
        ".git/config.json": json.dumps({"k": fake_value}),
        "deep/a.txt": "ok",
    })
    p = run("--dir", d)
    err = [ln for ln in p.stdout.splitlines() if ln.startswith("ERROR")]
    check(p.returncode == 2, f"a folder holding a secret -> exit 2 (got {p.returncode})")
    check(len(err) == 1 and "notes.md" in err[0], f"only notes.md is reported ({len(err)} error line(s))")
    check(fake_value not in p.stdout + p.stderr, "the secret is masked in --dir output")
    check(re.match(r"^ERROR \[R-SEC-KEY\] notes\.md: ", err[0]) is not None, "--dir keeps the line format")
    for name in ("sub/config.json", ".env", ".env.local", "prod.env", "a.yml", "b.yaml", "c.css", "d.js",
                 "e.md", "f.txt", "g.html"):
        d = project({name: json.dumps({"k": fake_value}) if name.endswith(".json") else "KEY=" + fake_value})
        os.remove(os.path.join(d, "registry.json"))
        check(run("--dir", d).returncode == 2, f"--dir reads {name}")
    d = project({"clean.md": "# hello"})
    check(run("--dir", d).returncode == 0, "a clean folder -> exit 0")
    d = project({"people.md": "call +84 912 345 678"})
    check(run("--dir", d).returncode == 1, "a folder with only PII -> exit 1")
    d = project({"blob.json": "\0\0" + fake_value, "pic.png": fake_value})
    check(run("--dir", d).returncode == 0, "a binary file (NUL bytes) and a non-text extension are skipped")
    d = project({"big.txt": "a" * (5 * 1024 * 1024 + 1)})
    p = run("--dir", d)
    check(p.returncode == 0 and "note:" in p.stderr and "big.txt" in p.stderr,
          "a file over 5 MB is skipped with a note")
    d = project({"ok.md": "x"})
    check(run("--dir", os.path.join(d, "missing")).returncode == 2, "a folder that does not exist -> exit 2")
    check(run("--dir").returncode != 0, "--dir without a folder -> usage, non-zero")
    d = project({"sub/pb/keep.md": "t " + fake_value})
    check(run("--dir", d).returncode == 0, "a pb/ folder below the root is skipped")
    pb_root = os.path.join(d, "sub", "pb")
    check(run("--dir", pb_root).returncode == 2, "...but pb/ named as the root itself is scanned")

    print()
    if _failures:
        print(f"✗ {len(_failures)} security assertion(s) failed.")
        sys.exit(1)
    print("✓ All security assertions passed.")


if __name__ == "__main__":
    main()
