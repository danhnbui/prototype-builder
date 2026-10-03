#!/usr/bin/env python3
"""
serve_meta.py — POST /api/meta, the Project settings dialog's save, on the /pb:preview server.

The dialog edits three registry fields (meta.name, meta.designSystem.name,
meta.designSystem.designLink) and the preview server is the only thing allowed to write them
from a page. A write endpoint on a dev server is a door, so most of this file is about who can
NOT walk through it:

  1. a peer that is not this machine           → 403 (unit: the check itself, with a LAN address)
  2. a request whose Host is not loopback      → 403 (DNS rebinding)
  3. a request with no Origin / another Origin → 403 (any other page open in the same browser)
  4. a body that is not JSON / not the shape   → 400, with the message the dialog shows
  5. a good request round-trips: registry.json holds the new values, every other key under meta
     and meta.designSystem is kept, the response returns what was saved, and the next render of
     the page says the new name. An emptied Figma link removes the key.
  6. the served page carries window.PB_PREVIEW (how the dialog knows it may save); a rendered
     prototype.html on disk never does.
  7. hardening (round 3): a Content-Length that is not a plain number, a body too large, JSON nested
     until the parser gives up, a number too long for it, a lone surrogate — every one a 400 with a
     message, the server still answering, and no traceback in its output; a control / format /
     surrogate character in any of the three values is refused.
  8. a link that is not a Figma file link and is ALREADY in the registry is a warning (the name and the
     design-system name still save, the response carries `warnings`); a NEW non-Figma link is still refused.
  9. the write is atomic (a new inode, no temp file left, mode kept) and under the registry lock: a
     second writer is refused with 503 and a message naming the holder, the registry untouched; a symlink
     (or anything but a regular file) planted at registry.json.lock is refused, never followed or truncated.
 10. an existing non-Figma link carrying an invisible character is kept (with the warning) when sent back
     unchanged, so the names still save; a CHANGED or new link carrying one is still refused.

Stdlib only (no browser). Usage:  python3 tests/serve_meta.py   Exit: 0 pass · 1 fail
"""
import http.client
import json
import os
import shutil
import socket
import stat
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
from e2e_smoke import GOLDEN, Server  # noqa: E402  (same harness: boots serve.py on a registry)
import serve  # noqa: E402

_fail = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _fail.append(msg)


def post(url, body, headers=None, raw=None):
    host = url.split("//", 1)[1].rstrip("/")
    conn = http.client.HTTPConnection(host, timeout=10)
    data = raw if raw is not None else json.dumps(body).encode("utf-8")
    h = {"Content-Type": "application/json", "Origin": "http://" + host, "Host": host}
    h.update(headers or {})
    h = {k: v for k, v in h.items() if v is not None}
    conn.request("POST", "/api/meta", body=data, headers=h)
    r = conn.getresponse()
    out = r.read().decode("utf-8")
    conn.close()
    try:
        return r.status, json.loads(out)
    except json.JSONDecodeError:
        return r.status, {"raw": out}


def raw_post(url, head_lines, body=b""):
    """A POST to /api/meta written by hand on a socket, for the requests http.client will not send
    (a Content-Length that is not a number). → (status, parsed JSON or {"raw": …}, connection_closed)."""
    host = url.split("//", 1)[1].rstrip("/")
    h, port = host.rsplit(":", 1)
    sock = socket.create_connection((h, int(port)), timeout=10)
    lines = ["POST /api/meta HTTP/1.1", "Host: " + host, "Origin: http://" + host,
             "Content-Type: application/json"] + list(head_lines)
    sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body)
    buf = b""
    try:
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        status = int(head.split(b" ", 2)[1]) if head else 0
        clen = 0
        for ln in head.split(b"\r\n")[1:]:
            if ln.lower().startswith(b"content-length:"):
                clen = int(ln.split(b":", 1)[1])
        while len(rest) < clen:
            chunk = sock.recv(65536)
            if not chunk:
                break
            rest += chunk
        closes = b"connection: close" in head.lower()
        sock.settimeout(1)
        try:
            closed = closes and sock.recv(1) == b""
        except (socket.timeout, OSError):
            closed = False
    finally:
        sock.close()
    try:
        return status, json.loads(rest.decode("utf-8")), closed
    except (ValueError, UnicodeDecodeError):
        return status, {"raw": rest[:200]}, closed


def get(url, path="/"):
    host = url.split("//", 1)[1].rstrip("/")
    conn = http.client.HTTPConnection(host, timeout=10)
    conn.request("GET", path)
    r = conn.getresponse()
    out = r.read().decode("utf-8")
    conn.close()
    return out


class FakeHandler:
    """Just enough of a request for Handler._local_same_origin."""
    def __init__(self, addr, host, origin):
        self.client_address = (addr, 50000)
        self.headers = {"Host": host, "Origin": origin} if origin is not None else {"Host": host}


def main():
    print("1 · the gate, in isolation")
    gate = serve.Handler._local_same_origin
    ok = FakeHandler("127.0.0.1", "127.0.0.1:8000", "http://127.0.0.1:8000")
    check(gate(ok) is None, "loopback peer + loopback Host + its own Origin passes")
    check(gate(FakeHandler("::1", "[::1]:8000", "http://[::1]:8000")) is None, "…on IPv6 loopback too")
    check(gate(FakeHandler("10.0.0.5", "127.0.0.1:8000", "http://127.0.0.1:8000")) is not None,
          "a peer on the LAN is refused even with a perfect Host and Origin")
    check(gate(FakeHandler("127.0.0.1", "evil.example:8000", "http://evil.example:8000")) is not None,
          "a non-loopback Host is refused (DNS rebinding)")
    check(gate(FakeHandler("127.0.0.1", "127.0.0.1:8000", "http://evil.example")) is not None,
          "another site's Origin is refused")
    check(gate(FakeHandler("127.0.0.1", "127.0.0.1:8000", None)) is not None, "no Origin is refused")
    check(gate(FakeHandler("127.0.0.1", "127.0.0.1:8000", "http://localhost:8000")) is not None,
          "an Origin that is a different name for the host is still a different origin")

    print("2 · validation")
    good = {"name": "Acme", "designSystem": {"name": "Acme DS", "designLink": ""}}
    check(serve.validate_meta_payload(good)["designSystem"]["name"] == "Acme DS", "a good payload validates")
    for bad, why in [
        ([], "not an object"),
        ({"name": "", "designSystem": {"name": "x"}}, "an empty project name"),
        ({"name": "A", "designSystem": {"name": "  "}}, "a blank design-system name"),
        ({"name": "A"}, "no designSystem"),
        ({"name": "A", "designSystem": {"name": "x", "designLink": "https://example.com/design/x"}}, "a non-Figma link"),
        ({"name": "A", "designSystem": {"name": "x", "designLink": "https://www.figma.com/proto/x"}}, "a Figma prototype link (not a file)"),
        ({"name": "A", "designSystem": {"name": "x"}, "roles": []}, "a field outside the three"),
        ({"name": "A", "designSystem": {"name": "x", "codeLibrary": "y"}}, "a designSystem key outside the two"),
    ]:
        try:
            serve.validate_meta_payload(bad)
            check(False, f"rejects {why}")
        except serve.MetaError:
            check(True, f"rejects {why}")
    try:
        serve.validate_meta_payload({"name": "A", "designSystem": {"name": "x", "designLink": "https://figma.com/file/abc/Name"}})
        check(True, "accepts figma.com/file/… without www")
    except serve.MetaError as e:
        check(False, f"accepts figma.com/file/… without www ({e})")

    print("2b · control / format / surrogate characters, and the warning for a link the project already has")
    for field, mk in [("name", lambda v: {"name": v, "designSystem": {"name": "x"}}),
                      ("designSystem.name", lambda v: {"name": "A", "designSystem": {"name": v}}),
                      ("designSystem.designLink", lambda v: {"name": "A", "designSystem": {"name": "x", "designLink": "https://figma.com/file/a" + v}})]:
        for label, ch in [("a NUL (Cc)", "\x00"), ("a newline inside (Cc)", "\n"), ("a tab inside (Cc)", "\t"),
                          ("a zero-width space (Cf)", "\u200b"), ("a bidi override (Cf)", "\u202e"),
                          ("a lone surrogate (Cs)", "\ud800")]:
            if field == "designSystem.designLink" and ch in ("\n", "\t"):
                continue                      # a \S+ link already refuses whitespace
            try:
                serve.validate_meta_payload(mk("a" + ch + "b"))
                check(False, f"{field}: rejects {label}")
            except serve.MetaError as e:
                check(str(e).startswith(field + ":") and "control, invisible or invalid" in str(e),
                      f"{field}: rejects {label}, naming the field ({e})")
    try:
        out = serve.validate_meta_payload({"name": "  Acme\n", "designSystem": {"name": "\tAcme DS "}})
        check(out["name"] == "Acme" and out["designSystem"]["name"] == "Acme DS",
              "whitespace at the EDGES is trimmed, not refused (the dialog trims too)")
    except serve.MetaError as e:
        check(False, f"edge whitespace is trimmed, not refused ({e})")
    check(serve.validate_meta_payload({"name": "Dự án Ví — 日本語 🚀", "designSystem": {"name": "Acme DS"}})["name"] == "Dự án Ví — 日本語 🚀",
          "ordinary non-ASCII names (accents, CJK, emoji) are fine")
    gh = "https://github.com/acme/ds"
    warns = []
    out = serve.validate_meta_payload({"name": "A", "designSystem": {"name": "x", "designLink": gh}},
                                      existing_link=gh, warnings=warns)
    check(out["designSystem"]["designLink"] == gh and len(warns) == 1 and "designLink" in warns[0],
          "the project's existing non-Figma link, sent back unchanged, is kept with ONE warning")
    for why, link, existing in [("a NEW non-Figma link", "https://github.com/acme/other", gh),
                                ("a non-Figma link when the project has none", gh, None),
                                ("a non-Figma link when the project has a Figma one", gh, "https://figma.com/file/x")]:
        try:
            serve.validate_meta_payload({"name": "A", "designSystem": {"name": "x", "designLink": link}}, existing_link=existing, warnings=[])
            check(False, f"still refuses {why}")
        except serve.MetaError:
            check(True, f"still refuses {why}")
    warns = []
    serve.validate_meta_payload({"name": "A", "designSystem": {"name": "x", "designLink": "https://figma.com/design/a"}},
                                existing_link="https://figma.com/design/a", warnings=warns)
    check(warns == [], "a Figma link raises no warning")

    print("2c · an existing non-Figma link that carries an invisible character must not block saving the names (L1)")
    for label, ch in [("a zero-width space (Cf)", "\u200b"), ("a bidi override (Cf)", "\u202e"), ("a NUL (Cc)", "\x00")]:
        odd = gh + "/ds" + ch + "x"
        warns = []
        try:
            out = serve.validate_meta_payload({"name": "Renamed", "designSystem": {"name": "Renamed DS", "designLink": odd}},
                                              existing_link=odd, warnings=warns)
            check(out["name"] == "Renamed" and out["designSystem"]["designLink"] == odd and len(warns) == 1,
                  f"the project's own link with {label}, sent back unchanged, is kept as it was with one warning")
        except serve.MetaError as e:
            check(False, f"the project's own link with {label}, sent back unchanged, is kept ({e})")
        try:
            serve.validate_meta_payload({"name": "Renamed", "designSystem": {"name": "Renamed DS", "designLink": odd + "2"}},
                                        existing_link=odd, warnings=[])
            check(False, f"a CHANGED link with {label} is still refused")
        except serve.MetaError as e:
            check(str(e).startswith("designSystem.designLink:") and "control, invisible or invalid" in str(e),
                  f"a CHANGED link with {label} is still refused, naming the field ({e})")
        try:
            serve.validate_meta_payload({"name": "Renamed", "designSystem": {"name": "Renamed DS", "designLink": odd}},
                                        existing_link=None, warnings=[])
            check(False, f"a NEW link with {label} is still refused")
        except serve.MetaError:
            check(True, f"a NEW link with {label} (the project had none) is still refused")
    odd = gh + "/ds\u200bx"
    for field, payload in [("name", {"name": "Re\u200bnamed", "designSystem": {"name": "x", "designLink": odd}}),
                           ("designSystem.name", {"name": "Renamed", "designSystem": {"name": "x\u200by", "designLink": odd}})]:
        try:
            serve.validate_meta_payload(payload, existing_link=odd, warnings=[])
            check(False, f"the exemption is for the link only: {field} with an invisible character is still refused")
        except serve.MetaError as e:
            check(str(e).startswith(field + ":"), f"the exemption is for the link only: {field} with an invisible character is still refused")
    sur = gh + "/ds\ud800"
    try:
        serve.validate_meta_payload({"name": "Renamed", "designSystem": {"name": "x", "designLink": sur}}, existing_link=sur, warnings=[])
        check(False, "a lone surrogate in an unchanged link is still refused (the registry cannot be written with it)")
    except serve.MetaError as e:
        check("U+D800" in str(e), "a lone surrogate in an unchanged link is still refused (the registry cannot be written with it)")
    figma_odd = "https://figma.com/file/a\u200bb"
    try:
        serve.validate_meta_payload({"name": "A", "designSystem": {"name": "x", "designLink": figma_odd}}, existing_link=figma_odd, warnings=[])
        check(False, "an unchanged link that IS a Figma link but carries an invisible character is not the exempted case")
    except serve.MetaError:
        check(True, "an unchanged link that IS a Figma link but carries an invisible character is not the exempted case (refused)")

    print("3 · over HTTP, on the real server")
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(os.path.dirname(GOLDEN), "render"), os.path.join(tmp, "render"))
        reg = json.load(open(GOLDEN, encoding="utf-8"))
        reg.setdefault("meta", {})["designSystem"] = {"name": "Old DS", "codeLibrary": "@acme/ui",
                                                      "designLink": "https://www.figma.com/design/OLD/x"}
        reg_path = os.path.join(tmp, "registry.json")
        json.dump(reg, open(reg_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        before = open(reg_path, encoding="utf-8").read()
        with Server(reg_path) as srv:
            page = get(srv.url)
            check("window.PB_PREVIEW=" in page and '"/api/meta"' in page,
                  "the served page tells the dialog it may save (window.PB_PREVIEW)")

            st, out = post(srv.url, good, headers={"Origin": None})
            check(st == 403 and not out.get("ok"), f"no Origin → 403 ({st})")
            st, out = post(srv.url, good, headers={"Origin": "http://evil.example"})
            check(st == 403, f"a foreign Origin → 403 ({st})")
            st, out = post(srv.url, good, headers={"Host": "evil.example", "Origin": "http://evil.example"})
            check(st == 403, f"a non-loopback Host → 403 ({st})")
            st, out = post(srv.url, None, raw=b"{not json")
            check(st == 400 and "JSON" in out.get("error", ""), f"bad JSON → 400 with a reason ({st} {out})")
            st, out = post(srv.url, {"name": "A", "designSystem": {"name": ""}})
            check(st == 400 and "Required" in out.get("error", ""), f"a missing DS name → 400 naming it ({out})")
            check(open(reg_path, encoding="utf-8").read() == before, "nothing refused touched registry.json")

            want = {"name": "Acme — the renamed project",
                    "designSystem": {"name": "Acme DS", "designLink": "https://www.figma.com/design/NEW123/Acme"}}
            st, out = post(srv.url, want)
            check(st == 200 and out.get("ok"), f"a good request saves ({st} {out})")
            check(out.get("meta") == want, f"…and returns what was saved ({out.get('meta')})")
            disk = json.load(open(reg_path, encoding="utf-8"))
            m = disk.get("meta", {})
            check(m.get("name") == want["name"] and m["designSystem"]["name"] == "Acme DS"
                  and m["designSystem"]["designLink"] == want["designSystem"]["designLink"],
                  "registry.json holds the three new values")
            check(m["designSystem"].get("codeLibrary") == "@acme/ui", "designSystem's other keys are kept")
            check({k for k in reg["meta"]} <= set(m), "every other meta key is kept")
            check(disk.get("screens") == reg.get("screens") and disk.get("components") == reg.get("components"),
                  "and nothing outside meta moved")
            seen = False
            for _ in range(30):
                if "Acme — the renamed project" in get(srv.url):
                    seen = True
                    break
                time.sleep(0.2)
            check(seen, "the next render of the page carries the new name (live reload re-renders it)")

            st, out = post(srv.url, {"name": "Acme", "designSystem": {"name": "Acme DS", "designLink": ""}})
            m = json.load(open(reg_path, encoding="utf-8"))["meta"]
            check(st == 200 and "designLink" not in m["designSystem"] and m["designSystem"].get("codeLibrary") == "@acme/ui",
                  "an emptied Figma link removes the key, and keeps the rest")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("3b · hardening: every bad request is a 400 with a message, never a traceback")
    tmp = tempfile.mkdtemp()
    os.environ["PB_LOCK_TIMEOUT"] = "0.6"          # the server under test inherits it: a refusal comes quickly
    try:
        shutil.copytree(os.path.join(os.path.dirname(GOLDEN), "render"), os.path.join(tmp, "render"))
        reg = json.load(open(GOLDEN, encoding="utf-8"))
        reg.setdefault("meta", {})["designSystem"] = {"name": "Old DS", "designLink": "https://github.com/acme/ds"}
        reg_path = os.path.join(tmp, "registry.json")
        json.dump(reg, open(reg_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        os.chmod(reg_path, 0o640)
        before = open(reg_path, encoding="utf-8").read()
        good2 = {"name": "Acme", "designSystem": {"name": "Acme DS", "designLink": ""}}
        with Server(reg_path) as srv:
            def refused(label, st, out, closed=None, want=None):
                check(st == 400 and out.get("ok") is False and isinstance(out.get("error"), str)
                      and (want is None or want in out["error"]),
                      f"{label} → 400 with a message ({st} {str(out)[:90]})")
            for label, heads, body, want in [
                ("a non-numeric Content-Length", ["Content-Length: abc"], b"{}", "Content-Length"),
                ("a Content-Length with an underscore (Python's int() would accept it)", ["Content-Length: 1_0"], b"{}", "Content-Length"),
                ("a signed Content-Length", ["Content-Length: +2"], b"{}", "Content-Length"),
                ("a negative Content-Length", ["Content-Length: -5"], b"{}", "Content-Length"),
                ("an empty Content-Length", ["Content-Length: "], b"{}", "missing"),
                ("no Content-Length at all", [], b"{}", "missing"),
                ("Content-Length: 0", ["Content-Length: 0"], b"", "missing"),
                ("a Content-Length of 10^30", ["Content-Length: " + "9" * 30], b"{}", "Content-Length"),
                ("a body over the limit", ["Content-Length: %d" % (serve.META_MAX_BYTES + 1)], b"x" * 10, "too large"),
            ]:
                st, out, closed = raw_post(srv.url, heads, body)
                refused(label, st, out, want=want)
                if label == "a body over the limit":
                    check(closed, "a refusal whose body was never read closes the connection (its bytes would be parsed as the next request)")
            t0 = time.time()
            st, out, closed = raw_post(srv.url, ["Content-Length: 99"], b"{}")
            refused("a body that is shorter than its Content-Length (the client stalls)", st, out, want="incomplete")
            check(time.time() - t0 < 8 and closed, "…the handler gives up after a few seconds instead of hanging, and hangs up")
            deep = b"[" * 60000
            st, out, _ = raw_post(srv.url, ["Content-Length: %d" % len(deep)], deep)
            refused("JSON nested 60,000 deep (past JSON_MAX_DEPTH, on every Python)", st, out, want="nested")
            deep = b'{"name":' + b"[" * 30000 + b"]" * 30000 + b"}"
            st, out, _ = raw_post(srv.url, ["Content-Length: %d" % len(deep)], deep)
            refused("a value nested 30,000 deep inside an otherwise valid object", st, out, want="nested")
            big = b'{"name": ' + b"1" * 6000 + b"}"
            st, out, _ = raw_post(srv.url, ["Content-Length: %d" % len(big)], big)
            refused("a 6,000-digit number", st, out)
            bad = b'{"name":"\xff\xfe"}'
            st, out, _ = raw_post(srv.url, ["Content-Length: %d" % len(bad)], bad)
            refused("a body that is not UTF-8", st, out, want="JSON")
            for label, payload, want in [
                ("a lone surrogate in the name", '{"name":"a\\ud800b","designSystem":{"name":"x"}}', "name:"),
                ("a zero-width space in the DS name", '{"name":"A","designSystem":{"name":"x\\u200bY"}}', "designSystem.name:"),
                ("a NUL in the link", '{"name":"A","designSystem":{"name":"x","designLink":"https://figma.com/file/a\\u0000b"}}', "designSystem.designLink:"),
                ("a newline inside the name", '{"name":"A\\nB","designSystem":{"name":"x"}}', "name:")]:
                body = payload.encode("utf-8")
                st, out, _ = raw_post(srv.url, ["Content-Length: %d" % len(body)], body)
                refused(label, st, out, want=want)
            check(open(reg_path, encoding="utf-8").read() == before, "none of those touched registry.json")
            st, out = post(srv.url, good2)
            check(st == 200 and out.get("ok"), f"the server still answers a good request afterwards ({st} {out})")

            print("3c · a link the project already has, that is not a Figma link")
            disk = json.load(open(reg_path, encoding="utf-8"))["meta"]["designSystem"]
            check(disk.get("designLink") is None, "(the good request above emptied it, so put it back by hand)")
            reg2 = json.load(open(reg_path, encoding="utf-8"))
            reg2["meta"]["designSystem"]["designLink"] = "https://github.com/acme/ds"
            json.dump(reg2, open(reg_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            os.chmod(reg_path, 0o640)
            keep = {"name": "Renamed again", "designSystem": {"name": "Acme DS 2", "designLink": "https://github.com/acme/ds"}}
            st, out = post(srv.url, keep)
            check(st == 200 and out.get("ok") and len(out.get("warnings", [])) == 1 and "designLink" in out["warnings"][0],
                  f"saving with the unchanged non-Figma link works and carries a warning ({st} {out})")
            m = json.load(open(reg_path, encoding="utf-8"))["meta"]
            check(m["name"] == "Renamed again" and m["designSystem"]["name"] == "Acme DS 2"
                  and m["designSystem"]["designLink"] == "https://github.com/acme/ds",
                  "…the new names are on disk and the link is untouched")
            st, out = post(srv.url, {"name": "X", "designSystem": {"name": "Y", "designLink": "https://github.com/acme/other"}})
            check(st == 400 and "figma.com" in out.get("error", ""), f"a DIFFERENT non-Figma link is still refused ({st} {out})")
            odd = "https://github.com/acme/ds\u200b?x=1"
            reg2 = json.load(open(reg_path, encoding="utf-8"))
            reg2["meta"]["designSystem"]["designLink"] = odd
            json.dump(reg2, open(reg_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            os.chmod(reg_path, 0o640)
            st, out = post(srv.url, {"name": "Names still save", "designSystem": {"name": "DS still saves", "designLink": odd}})
            m = json.load(open(reg_path, encoding="utf-8"))["meta"]
            check(st == 200 and out.get("ok") and len(out.get("warnings", [])) == 1
                  and m["name"] == "Names still save" and m["designSystem"]["name"] == "DS still saves"
                  and m["designSystem"]["designLink"] == odd,
                  f"an existing link with an invisible character no longer blocks saving the names: saved, warned, link untouched ({st} {out})")
            before_odd = open(reg_path, encoding="utf-8").read()
            st, out = post(srv.url, {"name": "X", "designSystem": {"name": "Y", "designLink": odd + "z"}})
            check(st == 400 and "designLink" in out.get("error", "") and open(reg_path, encoding="utf-8").read() == before_odd,
                  f"…but CHANGING that link to another one with the character is refused, and nothing is written ({st} {out})")
            st, out = post(srv.url, {"name": "Clean", "designSystem": {"name": "Acme DS 2", "designLink": ""}})
            check(st == 200 and "warnings" not in out, "emptying it saves with no warning")

            print("3d · atomic, mode kept, no temp files, and the registry lock")
            ino = os.stat(reg_path).st_ino
            st, out = post(srv.url, {"name": "Atomic", "designSystem": {"name": "Acme DS 2", "designLink": ""}})
            check(st == 200 and os.stat(reg_path).st_ino != ino, "the save replaced the file (a new inode) instead of rewriting it in place")
            check(stat.S_IMODE(os.stat(reg_path).st_mode) == 0o640, "the file's mode is kept")
            check([f for f in os.listdir(tmp) if f.endswith(".tmp")] == [], "no temp file is left behind")
            before = open(reg_path, encoding="utf-8").read()
            with serve.pbslice.registry_lock(reg_path, "a test holding the lock"):
                t0 = time.time()
                st, out = post(srv.url, {"name": "Blocked", "designSystem": {"name": "Acme DS 2", "designLink": ""}})
                waited = time.time() - t0
                check(st == 503 and "being written" in out.get("error", "") and "a test holding the lock" in out.get("error", ""),
                      f"a second writer is refused with 503, naming the holder ({st} {out})")
                check(0.4 < waited < 5, f"…after a short wait, not forever ({waited:.1f}s)")
            check(open(reg_path, encoding="utf-8").read() == before, "…and the registry is untouched")
            st, out = post(srv.url, {"name": "Unblocked", "designSystem": {"name": "Acme DS 2", "designLink": ""}})
            check(st == 200 and out["meta"]["name"] == "Unblocked", "once the lock is free the same save goes through")
            victim = os.path.join(tmp, "victim.txt")
            open(victim, "w").write("do not touch\n")
            os.unlink(reg_path + ".lock")
            os.symlink(victim, reg_path + ".lock")
            before = open(reg_path, encoding="utf-8").read()
            st, out = post(srv.url, {"name": "Via a planted symlink", "designSystem": {"name": "Acme DS 2", "designLink": ""}})
            check(st == 500 and "not a regular file" in out.get("error", "") and "Traceback" not in out.get("error", ""),
                  f"a symlink planted at registry.json.lock is refused with a message, not followed ({st} {out})")
            check(open(victim).read() == "do not touch\n" and open(reg_path, encoding="utf-8").read() == before,
                  "…the file it pointed at is not truncated and the registry is untouched")
            os.unlink(reg_path + ".lock")
            st, out = post(srv.url, {"name": "Lock file ordinary again", "designSystem": {"name": "Acme DS 2", "designLink": ""}})
            check(st == 200 and out["meta"]["name"] == "Lock file ordinary again", "once it is an ordinary file again the same save goes through")
            srv.proc.terminate()
            srv.proc.wait(timeout=5)
            log = srv.proc.stdout.read()
            check("Traceback" not in log and "Error" not in log.replace("render error", ""),
                  "the server's own output holds no traceback from any of it" + ("" if "Traceback" not in log else ": " + log[-300:]))
    finally:
        os.environ.pop("PB_LOCK_TIMEOUT", None)
        shutil.rmtree(tmp, ignore_errors=True)

    print("4 · a rendered file never carries the flag")
    sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
    import render  # noqa: E402
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "p.html")
        render.render_file(GOLDEN, os.path.join(ROOT, "pb", "template", "prototype.html"), out)
        check("window.PB_PREVIEW=" not in open(out, encoding="utf-8").read(),
              "prototype.html on disk has no PB_PREVIEW, so a shared file opens the dialog read-only")

    print()
    if _fail:
        print(f"✗ {len(_fail)} failure(s).")
        sys.exit(1)
    print("✓ /api/meta: local, same-origin, validated, round-trips.")


if __name__ == "__main__":
    main()
