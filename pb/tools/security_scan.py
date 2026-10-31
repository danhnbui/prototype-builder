#!/usr/bin/env python3
"""
pb-security-scan — a stdlib-only secrets & PII scanner for a Product Builder project.

A prototype's registry.json + its render bodies + its mock/example data are shipped in
hand-offs (prototype.html, --context bundles) and pushed to Figma. A pasted-in API key or
a real customer email leaks the moment the prototype leaves the machine. This scan is the
guard: it reads the registry and every file it points at — render bodies (renderSrc, resolved
exactly like lint_registry.py / render.py), runtime modules (runtime[].src), stylesheets
(styleSrc), spec and logic sidecars (specSrc / logicSrc) and every file under
render/_candidates/ — plus the seeded example data (erd.mock rows, erd.table examples — every
string/number leaf in the registry) and flags:

  ERROR (R-SEC-KEY):   hardcoded secrets — provider tokens (OpenAI sk-…, AWS AKIA…, GitHub ghp_…
                       / github_pat_…, GitLab glpat-…, Slack xox…-, Google AIza…, Stripe live
                       keys, Figma figd_…), JWTs, credentials inside a URL, a literal Bearer
                       token, PEM private-key headers, a generic api_key/secret/token/password
                       assigned a non-placeholder literal, and long high-entropy hex/base64 blobs.
  WARN  (R-SEC-EMAIL): real-looking emails (obvious placeholders — example.com/.org, test,
                       localhost, foo, acme, … — are ignored).
  WARN  (R-SEC-PII):   phone numbers (E.164, US, VN mobile — one row per country in
                       _PHONE_PATTERNS), national IDs, and Luhn-valid card numbers / SSNs.

Design-tool keys (a Figma component key under dsMatch / $extensions), data: URIs, SVG path data
and design-token references are not secrets and are not flagged.

Pure stdlib (NS4); read-only — it never writes the registry or the render.

Severity -> exit code (mirrors lint_registry.py):
  0  clean (no findings)
  1  warnings only
  2  at least one error

Each finding prints as:  <SEVERITY> [<CODE>] <location>: <message>

Usage:  python3 security_scan.py <registry.json>
        python3 security_scan.py --dir <folder>     every text file under a folder (a hand-off)
"""
import json
import math
import os
import re
import sys

ERROR, WARN = "ERROR", "WARN"
MAX_BYTES = 5 * 1024 * 1024   # a file past this is skipped with a note, never read

# ── secret detectors ─────────────────────────────────────────────────────────
_PEM = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")
_OPENAI = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
_AWS_AKIA = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
# provider tokens, one row each: (what it is, pattern). A new provider is one line here.
_PROVIDERS = (
    ("GitHub token", re.compile(
        r"(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255})")),
    ("GitLab token", re.compile(r"(?<![A-Za-z0-9])glpat-[A-Za-z0-9_-]{20,}")),
    ("Slack token", re.compile(r"(?<![A-Za-z0-9])xox[abeoprs]-[A-Za-z0-9-]{10,}")),
    ("Google API key", re.compile(r"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])")),
    ("Stripe live key", re.compile(r"(?<![A-Za-z0-9])[sr]k_live_[0-9A-Za-z]{16,}")),
    ("Figma token", re.compile(r"(?<![A-Za-z0-9])figd_[A-Za-z0-9_-]{20,}")),
    ("JWT", re.compile(
        r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
)
# scheme://user:pass@host — the scheme run is anchored so a long word is tried once, not per letter.
_URL_CRED = re.compile(
    r"(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]*://([^\s:/@\"'<>]+):([^\s/@\"'<>]+)@([^\s/\"'<>]+)")
# `Bearer <literal>`: 16+ chars of token alphabet; a `${…}` / `<…>` / `{…}` stops the run at once.
_BEARER = re.compile(r"(?i)\bbearer[ \t]+([A-Za-z0-9._~+/=-]{16,})")
# key/value assignment: <secret-word> [:=] "<literal>"  (JSON or JS/HTML attribute form).
# `token` is last so the longer access-/auth-/client-/private- forms win the alternation.
_ASSIGN_SECRET = re.compile(
    r"(?i)\b("
    r"api[_-]?key|secret(?:[_-]?key)?|access[_-]?token|auth[_-]?token"
    r"|client[_-]?secret|private[_-]?key|passwd|password|pwd|token"
    r")\b\s*[:=]\s*[\"']([^\"']{1,300})[\"']")
_HEX_BLOB = re.compile(r"\b[0-9a-fA-F]{32,}\b")
_B64_BLOB = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}")

# a secret assignment whose literal is one of these is a template/placeholder, not a leak.
_DUMMY_EXACT = {
    "", "null", "none", "n/a", "na", "test", "string", "value", "foo", "bar", "baz",
    "abc", "123", "1234", "12345", "changeme", "secret", "password", "token",
    "pass", "pwd", "xxx", "todo", "fixme", "true", "false",
}
_DUMMY_SUB = re.compile(
    r"(?i)(example|placeholder|your[-_ ]?|change[-_ ]?me|dummy|sample|redact"
    r"|xxxx|to[-_ ]?do|fixme|process\.env|os\.environ|getenv|import\.meta"
    r"|\{\{|\}\}|\$\{|<[a-z/])")

# ── false-positive guards ────────────────────────────────────────────────────
# A design tool's component/style key is a 40-hex id, public by design. It is exempt only when the
# KEY names one (below) AND the whole value is exactly that shape, so a real secret pasted under
# such a key (any other length or alphabet) still fires.
_DESIGN_KEY_VALUE = re.compile(r"[0-9a-f]{40}")
_DESIGN_KEY_NAMES = {"componentkey", "setkey", "stylekey", "variablekey"}
# bytes that are data, not text: a data: URI payload, and SVG geometry attributes.
_DATA_URI = re.compile(r"data:[\w.+/-]*(?:;[\w=.+-]+)*;base64,[A-Za-z0-9+/=_-]*")
_SVG_DATA = re.compile(
    r"""(?<![\w-])(?:d|points|viewBox|transform|stroke-dasharray)=\\?(["'])[^"'<>\\]*\\?\1""")
# a `token` key that holds a design-token name: --x, {a.b}, or a lowercase hyphenated/dotted name
# (each part a word with a short number, so a random "a3f9-2b7c" still reads as a secret).
_TOKEN_REF = re.compile(
    r"--[a-z0-9][a-z0-9-]*|\{[A-Za-z0-9_.-]+\}"
    r"|(?:[a-z]+\d{0,4}|\d{1,4}[a-z]{0,3})(?:[-.](?:[a-z]+\d{0,4}|\d{1,4}[a-z]{0,3}))+")

# ── PII detectors ────────────────────────────────────────────────────────────
# the lookbehind makes a long run without an @ cost one attempt, not one per character
_EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# obvious placeholder/test emails — never real PII.
_EMAIL_PLACEHOLDER = re.compile(
    r"(?i)(example\.(?:com|org|net)|@example\.|\btest\b|localhost|@foo|foo\.|acme"
    r"|@sample|sample\.|dummy|no[-_]?reply|@email\.|yourdomain|domain\.(?:com|net)"
    r"|\.invalid|\.local|@test\.|@acme)")
# Phone shapes, tried in order, one row per country: (country, pattern, what it is). A match that
# overlaps an earlier row's is dropped, so put the specific rows first and E.164 last. Separators
# must agree within a number (all spaces, all dots or all dashes), which keeps a coordinate such
# as 106.7123456 from reading as a phone. To add a country, add one line.
_VN_MOBILE = re.compile(
    r"(?<![\w.])(?:(?:\+84|0084)\)?[ .-]?|0)"
    r"(?:[35789]\d{8}|[35789]\d{2}([ .-])\d{3}\1\d{3}|[35789]\d([ .-])\d{3}\2\d{4})(?![\w]|[.-]\d)")
_US_PHONE = re.compile(
    r"(?<![\w.])(?:\+\d{1,3}[ .-]?)?(?:\(\d{3}\)[ .-]?\d{3}[ .-]?\d{4}|\d{3}([ .-])\d{3}\1\d{4})(?![\w])")
_E164 = re.compile(
    r"(?<![\w+])\+(?=(?:[ .-]?\d){8,15}(?![ .-]?\d))"
    r"(?:\d{8,15}|\d{1,3}([ .-])\d{1,6}(?:\1\d{1,6}){1,4})(?![\w])")
_PHONE_PATTERNS = (
    ("VN", _VN_MOBILE, "a Vietnamese mobile number"),
    ("US", _US_PHONE, "a phone number"),
    ("E.164", _E164, "an international phone number"),
)
# national ID numbers, one row per country: (country, pattern, what it is). Always masked in output.
_NATIONAL_IDS = (
    ("VN", re.compile(r"(?<![\w.,-])0(?:0[1-9]|[1-8]\d|9[0-6])\d{9}(?![\w]|[.,-]\d)"),
     "a 12-digit national ID"),
)
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
# candidate card number: 13–19 bare digits, or the printed groupings (4-4-4-4…, 4-6-5) joined by one
# consistent space/dash. It must also pass Luhn, so a pair of numeric ids ("1234567-7654321") is not a card.
_CARD_CAND = re.compile(
    r"(?<![\w.-])(?:\d{13,19}|\d{4}([ -])\d{4}\1\d{4}\1\d{1,7}|\d{4}([ -])\d{6}\2\d{4,5})(?![\w-]|\.\d)")


class Finding:
    __slots__ = ("severity", "code", "where", "msg")

    def __init__(self, severity, code, where, msg):
        self.severity = severity
        self.code = code
        self.where = where
        self.msg = msg

    def line(self):
        return f"{self.severity} [{self.code}] {self.where}: {self.msg}"


def _normalize_key(key):
    """Lowercase a key and strip separators so api_key / apiKey / API-KEY all collapse to
    `apikey`. Used to spot secret-named JSON keys (a plural like `tokens` stays `tokens`,
    so the design-`tokens` slice is never mistaken for a secret)."""
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


_SECRET_KEYS = {
    "apikey", "secret", "secretkey", "accesstoken", "authtoken", "clientsecret",
    "privatekey", "passwd", "password", "pwd", "token",
}


def _entropy(s):
    """Shannon entropy (bits/char) — high for random keys, low for words/repeats."""
    if not s:
        return 0.0
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _is_placeholder(val, min_len=6):
    """True when a secret-keyed literal is a template/placeholder rather than a real secret."""
    s = val.strip()
    if len(s) < min_len:
        return True
    if s.lower() in _DUMMY_EXACT:
        return True
    if _DUMMY_SUB.search(s):
        return True
    return False


def _is_token_ref(val):
    """True when the value of a key named `token` is a design-token name, not a credential."""
    return _TOKEN_REF.fullmatch(val.strip()) is not None


def _where_keys(where):
    """The path segments of a finding location (`components[3].dsMatch.figmaSetKey` ->
    components, 3, dsMatch, figmaSetKey), so a rule can ask which key a value sits under."""
    return [seg for seg in re.split(r"[.\[\]:/]+", where) if seg]


def _key_before(body, start):
    """The key a quoted value at `start` is written under in source text (`figmaSetKey: '…'`,
    `"reviewCommit":"…"`), or None when the value is not a quoted `key: value`."""
    if start == 0 or body[start - 1] not in "\"'":
        return None
    m = re.search(r"([A-Za-z_$][\w$-]*)[\"']?\s*[:=]\s*$", body[max(0, start - 80):start - 1])
    return m.group(1) if m else None


def _is_design_key(where, text, key=None):
    """A Figma-style component/set/style key (or a git commit id): the key's name says so AND the
    value is 40 hex. `key` is the name a text body wrote it under; a JSON leaf's is in `where`."""
    if _DESIGN_KEY_VALUE.fullmatch(text.strip()) is None:
        return False
    segs = _where_keys(where) + ([key] if key else [])
    if not segs:
        return False
    last = _normalize_key(segs[-1])
    if (last.startswith("figma") and last.endswith("key")) or last in _DESIGN_KEY_NAMES:
        return True
    if last.endswith(("commit", "commitsha", "gitsha")) or last == "sha":
        return True   # a git object id is public, not a credential
    if "dsMatch" in segs[:-1] and last == "key":
        return True
    # tokens.<name>.$extensions.<vendor>.key[.<mode>] — the key itself, or a per-mode map under it
    if "$extensions" in segs:
        after = segs[segs.index("$extensions") + 1:]
        return "key" in after
    return False


def _wordy(blob):
    """True when most of a blob is made of words (an identifier or a path), not random bytes."""
    words = sum(len(w) for w in re.findall(r"[A-Z]?[a-z]{4,}", blob))
    return words * 10 >= len(blob) * 6


def _path_like(blob):
    """A `design/<id>/Name`-shaped run: slashes between short lowercase words, not base64."""
    parts = blob.split("/")
    return len(parts) >= 3 and any(re.fullmatch(r"[a-z]{2,16}", p) for p in parts)


def _luhn(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _digits(s):
    return re.sub(r"\D", "", s)


def _strip_data(text):
    """Blank out data: URIs and SVG geometry attributes — payload, not prose — before the blob
    and digit rules read the text. Secrets and emails are still read from the original."""
    return _SVG_DATA.sub(" ", _DATA_URI.sub(" ", text))


def scan_text(add, text, where):
    """Scan a text blob (a render body or a single registry leaf) for secrets + PII.

    De-dups within the blob: the same literal is reported once, and the broad
    hex/base64 blob rules skip anything already flagged by a specific secret rule.
    Returns how many R-SEC-KEY errors it added, so a caller can tell whether it spoke."""
    if not text:
        return 0
    seen = set()          # (code, matched-literal) already reported for this `where`
    secret_hits = []      # concrete secret strings, so blob rules don't double-report them
    n_key = [0]

    def report(sev, code, matched, msg):
        key = (code, matched)
        if key in seen:
            return
        seen.add(key)
        if code == "R-SEC-KEY":
            n_key[0] += 1
        add(sev, code, where, msg)

    def known(lit):
        return any(lit in s or s in lit for s in secret_hits)

    # ── secrets (ERROR) ──
    for m in _PEM.finditer(text):
        secret_hits.append(m.group(0))
        report(ERROR, "R-SEC-KEY", m.group(0),
               "PEM private-key header in content — remove the embedded private key")
    for m in _OPENAI.finditer(text):
        secret_hits.append(m.group(0))
        report(ERROR, "R-SEC-KEY", m.group(0),
               f"looks like an OpenAI-style secret key ({_mask(m.group(0))}) — use a placeholder")
    for m in _AWS_AKIA.finditer(text):
        secret_hits.append(m.group(0))
        report(ERROR, "R-SEC-KEY", m.group(0),
               f"looks like an AWS access-key id ({_mask(m.group(0))}) — use a placeholder")
    for label, rx in _PROVIDERS:
        for m in rx.finditer(text):
            if _is_placeholder(m.group(0)):
                continue
            secret_hits.append(m.group(0))
            report(ERROR, "R-SEC-KEY", m.group(0),
                   f"looks like a {label} ({_mask(m.group(0))}) — use a placeholder")
    url_spans = []        # `pass@host` of a URL looks like an email; the URL rule already spoke
    for m in _URL_CRED.finditer(text):
        pw = m.group(2)
        if _is_placeholder(pw, 4) or _DUMMY_SUB.search(m.group(3)):
            continue
        url_spans.append((m.start(), m.end()))
        secret_hits.append(pw)
        report(ERROR, "R-SEC-KEY", pw,
               f"a URL carries a password ({_mask(pw)}) — drop the credentials from the URL")
    for m in _BEARER.finditer(text):
        lit = m.group(1)
        if (known(lit) or _is_placeholder(lit) or not re.search(r"[0-9]", lit)
                or not re.search(r"[A-Za-z]", lit)):
            continue
        secret_hits.append(lit)
        report(ERROR, "R-SEC-KEY", lit,
               f"a Bearer token is written out ({_mask(lit)}) — use a placeholder")
    for m in _ASSIGN_SECRET.finditer(text):
        keyword, literal = m.group(1), m.group(2)
        if _is_placeholder(literal) or known(literal):
            continue
        if keyword.lower() == "token" and _is_token_ref(literal):
            continue
        secret_hits.append(literal)
        report(ERROR, "R-SEC-KEY", literal,
               f"{keyword!r} is assigned a hardcoded literal ({_mask(literal)}) — "
               f"use a placeholder / env reference, never a real secret")

    # the blob and digit rules read the text without its data: URIs and SVG geometry
    body = _strip_data(text)
    for m in _HEX_BLOB.finditer(body):
        blob = m.group(0)
        if known(blob):
            continue
        if len(blob) == 40:
            whole = body.strip() == blob
            quoted = (not whole and m.start() > 0 and body[m.start() - 1] in "\"'"
                      and body[m.end():m.end() + 1] == body[m.start() - 1])
            if (whole or quoted) and _is_design_key(
                    where, blob, None if whole else _key_before(body, m.start())):
                continue
        has_letter = re.search(r"[a-fA-F]", blob) is not None
        has_digit = re.search(r"[0-9]", blob) is not None
        if has_letter and has_digit and _entropy(blob) >= 3.0:
            secret_hits.append(blob)
            report(ERROR, "R-SEC-KEY", blob,
                   f"long high-entropy hex blob ({_mask(blob)}) — looks like a key/hash/secret")
    for m in _B64_BLOB.finditer(body):
        blob = m.group(0)
        if known(blob) or _path_like(blob) or _wordy(blob):
            continue
        if (re.search(r"[a-z]", blob) and re.search(r"[A-Z]", blob)
                and re.search(r"[0-9]", blob) and _entropy(blob) >= 4.0):
            report(ERROR, "R-SEC-KEY", blob,
                   f"long high-entropy base64 blob ({_mask(blob)}) — looks like a token/secret")

    # ── PII (WARN) ──
    for m in _EMAIL.finditer(text):
        email = m.group(0)
        if _EMAIL_PLACEHOLDER.search(email) or any(s <= m.start() < e for s, e in url_spans):
            continue
        report(WARN, "R-SEC-EMAIL", email,
               f"real-looking email {email!r} — use a placeholder (e.g. user@example.com)")
    taken = []            # spans a phone row already claimed
    for country, rx, what in _PHONE_PATTERNS:
        for m in rx.finditer(body):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            phone = m.group(0).strip()
            report(WARN, "R-SEC-PII", phone,
                   f"looks like {what} [{country}] ({phone!r}) — use fictional data")
    for country, rx, what in _NATIONAL_IDS:
        for m in rx.finditer(body):
            report(WARN, "R-SEC-PII", m.group(0),
                   f"looks like {what} [{country}] ({_mask(m.group(0))}) — use fictional data")
    for m in _SSN.finditer(body):
        report(WARN, "R-SEC-PII", m.group(0),
               f"looks like an SSN ({m.group(0)!r}) — use fictional data")
    for m in _CARD_CAND.finditer(body):
        cand = m.group(0)
        digits = _digits(cand)
        if 13 <= len(digits) <= 19 and len(set(digits)) > 1 and _luhn(digits):
            report(WARN, "R-SEC-PII", cand,
                   f"long digit run ({_mask(cand)}) looks like a card number — use fictional data")
    return n_key[0]


def _mask(s):
    """Redact the middle of a value so the finding never re-leaks it in full."""
    s = s.strip()
    if len(s) <= 8:
        return s[:2] + "…"
    return f"{s[:4]}…{s[-2:]} (len {len(s)})"


def iter_leaves(node, path="", key=None):
    """Yield (path, parent_key, value) for every scalar leaf, tracking a JSON-ish path
    (`erd.table[1].example`) and the dict key the value was stored under. List items
    inherit their list's key so a `passwords: [...]` array still checks against it."""
    if isinstance(node, dict):
        for k, v in node.items():
            child = f"{path}.{k}" if path else str(k)
            yield from iter_leaves(v, child, k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from iter_leaves(v, f"{path}[{i}]", key)
    else:
        yield path, key, node


def _scan_leaves(add, doc, prefix=""):
    """Scan every scalar leaf of a parsed JSON document; `prefix` names the file it came from."""
    for path, key, val in iter_leaves(doc):
        where = (prefix + path) or "<root>"
        if isinstance(val, str):
            spoke = scan_text(add, val, where)
            if (not spoke and key is not None and _normalize_key(key) in _SECRET_KEYS
                    and not _is_placeholder(val)
                    and not (str(key).lower() == "token" and _is_token_ref(val))):
                add(ERROR, "R-SEC-KEY", where,
                    f"key {key!r} holds a hardcoded secret literal ({_mask(val)}) — "
                    f"use a placeholder / env reference")
        elif isinstance(val, (int, float)) and not isinstance(val, bool):
            scan_text(add, repr(val) if isinstance(val, float) else str(val), where)


def _read_text(file_path, label):
    """The text of a file, or None when it is missing, binary, not UTF-8, or past MAX_BYTES
    (the last prints one `note:` on stderr so the skip is never silent)."""
    try:
        size = os.path.getsize(file_path)
        if size > MAX_BYTES:
            print(f"note: {label}: skipped, {size / 1048576:.1f} MB is over the "
                  f"{MAX_BYTES // 1048576} MB limit", file=sys.stderr)
            return None
        with open(file_path, "rb") as f:
            raw = f.read()
    except (FileNotFoundError, IsADirectoryError, OSError):
        return None
    if b"\0" in raw[:8192]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _scan_file(add, file_path, label):
    """Scan one file: a .json is walked leaf by leaf (so a key's name counts), the rest as text."""
    text = _read_text(file_path, label)
    if text is None:
        return
    if label.lower().endswith(".json"):
        try:
            doc = json.loads(text)
        except (ValueError, RecursionError):
            doc = None
        if doc is not None:
            _scan_leaves(add, doc, prefix=label + ":")
            return
    scan_text(add, text, label)


def scan(reg, base_dir):
    """Scan a registry dict (incl. mock/example leaves) + every file it references.

    base_dir (the registry's directory) resolves each entry's renderSrc / styleSrc / specSrc /
    logicSrc and each runtime[].src exactly like lint_registry.py / render.py, so the real files
    are scanned; every file under render/_candidates/ is scanned too (an explore round's
    candidates are never in the registry). Returns a list of Finding."""
    findings = []

    def add(sev, code, where, msg):
        findings.append(Finding(sev, code, where, msg))

    if not isinstance(reg, dict):
        add(ERROR, "R-SEC-KEY", "<root>", "registry must be a JSON object")
        return findings

    # 1) every registry leaf — covers tokens, erd.mock rows, erd.table examples, meta, flow…
    _scan_leaves(add, reg)

    # 2) referenced files. renderSrc wins over a legacy inline `render` string; the inline form,
    #    if present, is already covered by the leaf walk above. A missing file is lint_registry.py's
    #    concern (R-RENDERSRC …); nothing to scan here.
    done = set()

    def scan_ref(src):
        if not isinstance(src, str) or not src:
            return
        file_path = os.path.normpath(os.path.join(base_dir, src))
        if file_path in done:
            return
        done.add(file_path)
        _scan_file(add, file_path, src)

    for kind in ("components", "screens"):
        for item in reg.get(kind, []) or []:
            if isinstance(item, dict):
                for field in ("renderSrc", "styleSrc", "specSrc", "logicSrc"):
                    scan_ref(item.get(field))
    for item in reg.get("runtime", []) or []:
        if isinstance(item, dict):
            scan_ref(item.get("src"))

    # 3) explore candidates: render/_candidates/<round>/<slot>… — whatever text is there
    cand_root = os.path.join(base_dir, "render", "_candidates")
    for dirpath, dirnames, filenames in os.walk(cand_root):
        dirnames.sort()
        for name in sorted(filenames):
            file_path = os.path.normpath(os.path.join(dirpath, name))
            if file_path in done or os.path.islink(file_path):
                continue
            done.add(file_path)
            _scan_file(add, file_path, os.path.relpath(file_path, base_dir).replace(os.sep, "/"))

    return findings


# ── directory mode (a hand-off) ──────────────────────────────────────────────
_DIR_EXTS = {".md", ".json", ".js", ".css", ".html", ".txt", ".yml", ".yaml",
             ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".svg"}
_DIR_SKIP_DIRS = {"pb", ".git", "node_modules"}
_DIR_SKIP_FILES = {"prototype.html", "design-system.html"}   # derived from what was already scanned


def _dir_wants(name):
    lower = name.lower()
    if lower.startswith(".env") or lower.endswith(".env"):
        return True
    return os.path.splitext(lower)[1] in _DIR_EXTS


def scan_dir(root):
    """Scan every text file under `root` (a folder about to be handed off). Skips the two derived
    HTML files, any pb/, .git/ and node_modules/ folder below the root, symlinks, binary files and
    files over MAX_BYTES. Returns a list of Finding."""
    findings = []

    def add(sev, code, where, msg):
        findings.append(Finding(sev, code, where, msg))

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _DIR_SKIP_DIRS)
        for name in sorted(filenames):
            if name in _DIR_SKIP_FILES or not _dir_wants(name):
                continue
            file_path = os.path.join(dirpath, name)
            if os.path.islink(file_path):
                continue
            _scan_file(add, file_path, os.path.relpath(file_path, root).replace(os.sep, "/"))
    return findings


def _load_json(file_path):
    """Load a JSON file, failing closed with a one-line R-IO/R-JSON message (no traceback)."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR [R-IO] {file_path}: file not found", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR [R-JSON] {file_path}: invalid JSON (line {e.lineno}, column {e.colno}): {e.msg}",
              file=sys.stderr)
        sys.exit(2)
    except RecursionError:
        print(f"ERROR [R-JSON] {file_path}: JSON nesting too deep to parse safely", file=sys.stderr)
        sys.exit(2)
    except UnicodeDecodeError:
        print(f"ERROR [R-JSON] {file_path}: not valid UTF-8 text", file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        print(f"ERROR [R-IO] {file_path}: {e.strerror or e}", file=sys.stderr)
        sys.exit(2)


def _report(findings, label, ok_msg):
    """Print findings, then exit 0 (clean) / 1 (warnings) / 2 (any error)."""
    errors = [f for f in findings if f.severity == ERROR]
    warns = [f for f in findings if f.severity == WARN]
    for f in findings:
        print(f.line())
    if not findings:
        print(f"✓ {label}: {ok_msg}")
        sys.exit(0)
    print(f"{label}: {len(errors)} error(s), {len(warns)} warning(s)")
    sys.exit(2 if errors else 1)


def main():
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--dir":
        root = args[1]
        if not os.path.isdir(root):
            print(f"ERROR [R-IO] {root}: not a folder", file=sys.stderr)
            sys.exit(2)
        _report(scan_dir(root), "security_scan.py", f"clean — {root}")
    if len(args) != 1 or args[0].startswith("--"):
        sys.exit("usage: security_scan.py <registry.json> | security_scan.py --dir <folder>")
    reg_path = args[0]
    reg = _load_json(reg_path)
    findings = scan(reg, base_dir=os.path.dirname(os.path.abspath(reg_path)))
    _report(findings, "security_scan.py", f"clean — {reg_path}")


if __name__ == "__main__":
    main()
