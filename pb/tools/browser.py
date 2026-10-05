#!/usr/bin/env python3
"""
browser.py — the one door pb opens a headless browser through. Stdlib only.

A headless Chromium costs about 0.6 GB, and pb used to launch one per test mode, per screenshot
round and per hand-written script — on a measured project up to four ran at once. Every launch now
goes through `open_browser`, which holds a machine-wide counting semaphore around the browser's
life, so at most LIMIT of them run at once however many pb commands are working.

  browser_slot(who, limit, wait)   context manager — hold one slot for the `with` body
  open_browser(p, who)             a slot + `p.chromium.launch()`; the slot is released when the browser
                                   is closed (or the process ends, whichever comes first)
  find_preview(reg_path)           the URL of THIS project's running preview, else None

The semaphore is `limit` files, slot-<i>.lock, in a per-user directory under the temp dir
(mode 0700, the uid in its name). A slot is taken with a non-blocking `fcntl.flock`, polled every
0.25s, and the KERNEL frees it when its holder dies — so there is never a stale slot to clean up.
Like `slice.registry_lock`, a slot file is opened with O_NOFOLLOW and must be a regular file: a
symlink (or anything else) planted at a slot path is refused — never followed, never truncated.

  PB_BROWSER_SLOTS   the limit; default 3; an integer >= 1; 0 = no limit
  PB_BROWSER_WAIT    seconds to wait for a slot before going ahead anyway; default 120
  PB_BROWSER_TRACE   a file; one line `<iso time> <pid> <who>` is appended per browser launched

The limit is a courtesy to the machine and never a reason a test cannot run, so it FAILS OPEN:
after the wait expires (or when the slot directory cannot be trusted) one `note:` line says the limit
was not honoured and the browser starts. Where `fcntl` is missing (Windows) a slot is a no-op.
"""
import contextlib
import datetime
import errno
import os
import stat
import sys
import tempfile
import time
import urllib.parse

try:
    import fcntl
except ImportError:          # Windows: no advisory lock — the limit is simply not enforced
    fcntl = None

DEFAULT_SLOTS = 3
DEFAULT_WAIT = 120.0
POLL = 0.25
_LOOPBACK = ("127.0.0.1", "localhost", "::1")


class SlotUnsafe(Exception):
    """A slot file (or the slot directory) is not what it must be — a symlink, a directory, a file of
    another user. Nothing was written to or truncated at that path."""


def slot_limit(limit=None):
    """How many browsers may run at once: `limit`, else PB_BROWSER_SLOTS, else 3. 0 = no limit.
    A value that is not a whole number >= 0 is ignored (the default stands)."""
    if limit is None:
        raw = os.environ.get("PB_BROWSER_SLOTS", "").strip()
        if not raw:
            return DEFAULT_SLOTS
        try:
            limit = int(raw)
        except ValueError:
            return DEFAULT_SLOTS
    return limit if isinstance(limit, int) and limit >= 0 else DEFAULT_SLOTS


def slot_wait(wait=None):
    """Seconds to wait for a slot: `wait`, else PB_BROWSER_WAIT, else 120."""
    if wait is None:
        raw = os.environ.get("PB_BROWSER_WAIT", "").strip()
        if not raw:
            return DEFAULT_WAIT
        try:
            wait = float(raw)
        except ValueError:
            return DEFAULT_WAIT
    return float(wait) if wait >= 0 else DEFAULT_WAIT


def slot_dir():
    """The per-user directory the slot files live in (not created here)."""
    return os.path.join(tempfile.gettempdir(), "pb-browser-slots-%d" % os.getuid())


def _ensure_dir(path):
    """Create the slot directory 0700 and make sure it is a real directory, ours, and private. A
    symlink, a file, or another user's directory is refused (SlotUnsafe) — a shared /tmp is where
    somebody else could have put one."""
    try:
        os.makedirs(path, mode=0o700, exist_ok=True)
        st = os.lstat(path)
    except OSError as e:
        raise SlotUnsafe("cannot use %s (%s)" % (path, e.strerror or e))
    if not stat.S_ISDIR(st.st_mode):
        raise SlotUnsafe("%s is not a directory" % path)
    if st.st_uid != os.getuid():
        raise SlotUnsafe("%s belongs to another user" % path)
    if st.st_mode & 0o077:
        try:
            # Tightens to owner-only; 0o700 is the narrowest mode a directory can be used with.
            os.chmod(path, 0o700)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
        except OSError:
            raise SlotUnsafe("%s is open to other users and cannot be tightened" % path)


def _open_slot(path):
    """Open one slot file and hand back its descriptor — only if it is a regular file of ours. The
    holder's note is written into it and truncated on release, so a symlink planted here would make
    the next holder write through it: O_NOFOLLOW refuses the open, O_NONBLOCK keeps a FIFO from
    waiting for a peer, and fstat on the DESCRIPTOR (not the path, which could change between the
    check and the open) turns away anything that is not a regular file before a byte is written."""
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    name = os.path.basename(path)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as e:
        if e.errno in (errno.ELOOP, errno.EISDIR, errno.ENXIO, errno.EMLINK):
            raise SlotUnsafe("%s is not a regular file (a symlink or another kind of file is in its "
                             "place) — refusing to lock or write through it" % name) from None
        raise SlotUnsafe("cannot open %s (%s)" % (name, e.strerror or e)) from None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            raise SlotUnsafe("%s is not a regular file of this user — refusing to lock or write through it" % name)
    except BaseException:
        os.close(fd)
        raise
    return fd


class Slot:
    """One held slot — or a no-op stand-in when the limit is off, unenforceable, or timed out
    (`held` is False). `release()` is idempotent; closing the descriptor is what frees the flock."""

    def __init__(self, fd=None, index=None):
        self.fd = fd
        self.index = index

    @property
    def held(self):
        return self.fd is not None

    def release(self):
        fd, self.fd = self.fd, None
        if fd is None:
            return
        with contextlib.suppress(OSError):
            os.ftruncate(fd, 0)
        with contextlib.suppress(OSError):
            os.close(fd)


def _note(msg):
    print("note: " + msg, file=sys.stderr, flush=True)


def acquire_slot(who="pb", limit=None, wait=None):
    """Take a browser slot, waiting up to `wait` seconds; ALWAYS returns a Slot (never raises for a
    full house or an untrustworthy directory — it fails open with a one-line note)."""
    limit, wait = slot_limit(limit), slot_wait(wait)
    if limit == 0 or fcntl is None:
        return Slot()
    d = slot_dir()
    try:
        _ensure_dir(d)
    except SlotUnsafe as e:
        _note("the browser limit is not honoured — %s" % e)
        return Slot()
    deadline = time.monotonic() + wait
    told, last_unsafe = False, ""
    while True:
        busy = unsafe = 0
        for i in range(limit):
            try:
                fd = _open_slot(os.path.join(d, "slot-%d.lock" % i))
            except SlotUnsafe as e:
                unsafe += 1
                last_unsafe = str(e)
                continue
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                busy += 1
                os.close(fd)
                continue
            try:
                os.ftruncate(fd, 0)
                os.pwrite(fd, ("%s pid=%d\n" % (who, os.getpid())).encode("utf-8"), 0)
            except OSError:
                pass
            return Slot(fd, i)
        if unsafe >= limit:      # not one usable slot: waiting cannot help
            _note("the browser limit is not honoured — %s" % last_unsafe)
            return Slot()
        if not told and wait > 0:
            print("waiting for a browser slot (%d in use) …" % busy, file=sys.stderr, flush=True)
            told = True
        if time.monotonic() >= deadline:
            _note("no browser slot was free after %gs (limit %d) — the limit is not honoured; "
                  "starting the browser anyway" % (wait, limit))
            return Slot()
        time.sleep(max(0.0, min(POLL, deadline - time.monotonic())))


@contextlib.contextmanager
def browser_slot(who="pb", limit=None, wait=None):
    """Hold one browser slot for the `with` body. A counting semaphore across processes: with a limit
    of N, the N+1th holder waits until one lets go (or dies). Yields the Slot."""
    slot = acquire_slot(who, limit, wait)
    try:
        yield slot
    finally:
        slot.release()


def _trace(who):
    path = os.environ.get("PB_BROWSER_TRACE", "").strip()
    if not path:
        return
    line = "%s %d %s\n" % (datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           os.getpid(), who)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def open_browser(p, who="pb", **launch):
    """A slot, then `p.chromium.launch(**launch)`. The slot is released when the browser is closed,
    when it disconnects, or — at the latest — when this process ends (the kernel does that). A launch
    that fails gives its slot back before the error propagates, so callers keep their own handling."""
    slot = acquire_slot(who)
    try:
        browser = p.chromium.launch(**launch)
    except BaseException:
        slot.release()
        raise
    _trace(who)
    if slot.held:
        with contextlib.suppress(Exception):
            browser.on("disconnected", lambda *_a: slot.release())
        try:
            real_close = browser.close

            def close(*a, **k):
                try:
                    return real_close(*a, **k)
                finally:
                    slot.release()
            browser.close = close
        except Exception:        # an object that will not take the attribute: disconnect/exit frees it
            pass
    return browser


def is_loopback_url(url):
    """True only for an http:// URL on this machine (127.0.0.1, localhost, ::1), no credentials —
    these are tools for pb previews, not a general browser."""
    try:
        u = urllib.parse.urlparse(url or "")
        return (u.scheme == "http" and u.hostname in _LOOPBACK and u.username is None
                and (u.port is None or u.port > 0))
    except ValueError:
        return False


def find_preview(reg_path):
    """The URL (with a trailing "/") of THIS project's running /pb:preview server, else None.

    Reads `.preview/server.json` next to the registry and then asks the server who it is
    (GET /__pb_health): only a server whose health answer names THIS registry counts, so a stale
    record, or another project's server that took the port, is never reused. It never probes ports
    and never follows a record to a host that is not this machine."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import explore                      # lazy: explore itself reaches back here only inside a function
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    rec = explore.server_record(base_dir)
    if not rec or not is_loopback_url(rec["url"]):
        return None
    base = rec["url"].rstrip("/")
    return base + "/" if explore._ours(base, reg_path) else None
