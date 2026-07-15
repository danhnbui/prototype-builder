#!/usr/bin/env python3
"""
pb-security-scan — a stdlib-only secrets & PII scanner for a Product Builder project.

A prototype's registry.json + its render bodies + its mock/example data are shipped in
hand-offs (prototype.html, --context bundles) and pushed to Figma. A pasted-in API key or
a real customer email leaks the moment the prototype leaves the machine. This scan is the
guard: it reads the registry and every render/**/*.js body it references (via renderSrc,
resolved exactly like check.py / render.py) plus the seeded example data (erd.mock rows,
erd.table examples — every string/number leaf in the registry) and flags:

  ERROR (R-SEC-KEY):   hardcoded secrets — OpenAI sk-… keys, AWS AKIA… ids, PEM private-key
                       headers, a generic api_key/secret/token/password assigned a
                       non-placeholder literal, and long high-entropy hex/base64 blobs.
  WARN  (R-SEC-EMAIL): real-looking emails (obvious placeholders — example.com/.org, test,
                       localhost, foo, acme, … — are ignored).
  WARN  (R-SEC-PII):   phone numbers and long digit runs that look like a card / SSN.

Pure stdlib (NS4); read-only — it never writes the registry or the render.

Severity -> exit code (mirrors check.py):
  0  clean (no findings)
  1  warnings only
  2  at least one error

Each finding prints as:  <SEVERITY> [<CODE>] <location>: <message>

Usage:  python3 security_scan.py <registry.json>
"""
import json
import math
import os
import re
import sys

ERROR, WARN = "ERROR", "WARN"

# ── secret detectors ─────────────────────────────────────────────────────────
_PEM = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")
_OPENAI = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
_AWS_AKIA = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
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

# ── PII detectors ────────────────────────────────────────────────────────────
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# obvious placeholder/test emails — never real PII.
_EMAIL_PLACEHOLDER = re.compile(
    r"(?i)(example\.(?:com|org|net)|@example\.|\btest\b|localhost|@foo|foo\.|acme"
    r"|@sample|sample\.|dummy|no[-_]?reply|@email\.|yourdomain|domain\.(?:com|net)"
    r"|\.invalid|\.local|@test\.|@acme)")
# a formatted phone (a separator/paren/plus is required so bare id-like digit runs don't hit).
_PHONE = re.compile(
    r"(?<![\w.])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{3}\)[\s.-]?|\d{3}[\s.-])\d{3}[\s.-]?\d{4}(?![\w])")
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
# candidate card-like run: 13–19 digits, optionally grouped by single spaces/dashes.
_CARD_CAND = re.compile(r"(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d-])")


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


def _is_placeholder(val):
    """True when a secret-keyed literal is a template/placeholder rather than a real secret."""
    s = val.strip()
    if len(s) < 6:
        return True
    if s.lower() in _DUMMY_EXACT:
        return True
    if _DUMMY_SUB.search(s):
        return True
    return False


def _digits(s):
    return re.sub(r"\D", "", s)


def scan_text(add, text, where):
    """Scan a text blob (a render body or a single registry leaf) for secrets + PII.

    De-dups within the blob: the same literal is reported once, and the broad
    hex/base64 blob rules skip anything already flagged by a specific secret rule."""
    if not text:
        return
    seen = set()          # (code, matched-literal) already reported for this `where`
    secret_hits = []      # concrete secret strings, so blob rules don't double-report them

    def report(sev, code, matched, msg):
        key = (code, matched)
        if key in seen:
            return
        seen.add(key)
        add(sev, code, where, msg)

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
    for m in _ASSIGN_SECRET.finditer(text):
        keyword, literal = m.group(1), m.group(2)
        if _is_placeholder(literal):
            continue
        secret_hits.append(literal)
        report(ERROR, "R-SEC-KEY", literal,
               f"{keyword!r} is assigned a hardcoded literal ({_mask(literal)}) — "
               f"use a placeholder / env reference, never a real secret")
    for m in _HEX_BLOB.finditer(text):
        blob = m.group(0)
        if any(blob in s or s in blob for s in secret_hits):
            continue
        has_letter = re.search(r"[a-fA-F]", blob) is not None
        has_digit = re.search(r"[0-9]", blob) is not None
        if has_letter and has_digit and _entropy(blob) >= 3.0:
            secret_hits.append(blob)
            report(ERROR, "R-SEC-KEY", blob,
                   f"long high-entropy hex blob ({_mask(blob)}) — looks like a key/hash/secret")
    for m in _B64_BLOB.finditer(text):
        blob = m.group(0)
        if any(blob in s or s in blob for s in secret_hits):
            continue
        if (re.search(r"[a-z]", blob) and re.search(r"[A-Z]", blob)
                and re.search(r"[0-9]", blob) and _entropy(blob) >= 4.0):
            report(ERROR, "R-SEC-KEY", blob,
                   f"long high-entropy base64 blob ({_mask(blob)}) — looks like a token/secret")

    # ── PII (WARN) ──
    for m in _EMAIL.finditer(text):
        email = m.group(0)
        if _EMAIL_PLACEHOLDER.search(email):
            continue
        report(WARN, "R-SEC-EMAIL", email,
               f"real-looking email {email!r} — use a placeholder (e.g. user@example.com)")
    for m in _PHONE.finditer(text):
        phone = m.group(0).strip()
        report(WARN, "R-SEC-PII", phone,
               f"looks like a phone number ({phone!r}) — use fictional data")
    for m in _SSN.finditer(text):
        report(WARN, "R-SEC-PII", m.group(0),
               f"looks like an SSN ({m.group(0)!r}) — use fictional data")
    for m in _CARD_CAND.finditer(text):
        cand = m.group(0)
        n = len(_digits(cand))
        if 13 <= n <= 19:
            report(WARN, "R-SEC-PII", cand,
                   f"long digit run ({_mask(cand)}) looks like a card number — use fictional data")


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


def scan(reg, base_dir):
    """Scan a registry dict (incl. mock/example leaves) + its referenced render bodies.

    base_dir (the registry's directory) resolves each entry's renderSrc exactly like
    check.py / render.py, so the real bodies are scanned. Returns a list of Finding."""
    findings = []

    def add(sev, code, where, msg):
        findings.append(Finding(sev, code, where, msg))

    if not isinstance(reg, dict):
        add(ERROR, "R-SEC-KEY", "<root>", "registry must be a JSON object")
        return findings

    # 1) every registry leaf — covers tokens, erd.mock rows, erd.table examples, meta, flow…
    for path, key, val in iter_leaves(reg):
        if isinstance(val, str):
            scan_text(add, val, path or "<root>")
            if key is not None and _normalize_key(key) in _SECRET_KEYS and not _is_placeholder(val):
                add(ERROR, "R-SEC-KEY", path or "<root>",
                    f"key {key!r} holds a hardcoded secret literal ({_mask(val)}) — "
                    f"use a placeholder / env reference")
        elif isinstance(val, (int, float)) and not isinstance(val, bool):
            scan_text(add, repr(val) if isinstance(val, float) else str(val), path or "<root>")

    # 2) referenced render bodies (renderSrc wins over a legacy inline `render` string;
    #    the inline form, if present, is already covered by the leaf walk above).
    for kind in ("components", "screens"):
        for i, item in enumerate(reg.get(kind, []) or []):
            if not isinstance(item, dict):
                continue
            src = item.get("renderSrc")
            if not src:
                continue
            where = src
            path = os.path.normpath(os.path.join(base_dir, src))
            try:
                with open(path, encoding="utf-8") as f:
                    body = f.read()
            except (FileNotFoundError, IsADirectoryError, OSError):
                # A missing renderSrc is check.py's concern (R-RENDERSRC); nothing to scan here.
                continue
            scan_text(add, body, where)

    return findings


def _load_json(path):
    """Load a JSON file, failing closed with a one-line R-IO/R-JSON message (no traceback)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR [R-IO] {path}: file not found", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR [R-JSON] {path}: invalid JSON (line {e.lineno}, column {e.colno}): {e.msg}",
              file=sys.stderr)
        sys.exit(2)
    except RecursionError:
        print(f"ERROR [R-JSON] {path}: JSON nesting too deep to parse safely", file=sys.stderr)
        sys.exit(2)
    except UnicodeDecodeError:
        print(f"ERROR [R-JSON] {path}: not valid UTF-8 text", file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        print(f"ERROR [R-IO] {path}: {e.strerror or e}", file=sys.stderr)
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
    if len(args) != 1:
        sys.exit("usage: security_scan.py <registry.json>")
    path = args[0]
    reg = _load_json(path)
    findings = scan(reg, base_dir=os.path.dirname(os.path.abspath(path)))
    _report(findings, "security_scan.py", f"clean — {path}")


if __name__ == "__main__":
    main()
