#!/usr/bin/env python3
"""PreToolUse / PostToolUse / PostToolUseFailure hook: send pb's usage rules down the safe path at call time.

One script, dispatched on `hook_event_name` + `tool_name`. Inside a pb project only (a folder with
`registry.json` beside `render/` or `memory/constitution.md`, in the working folder, its `.prototype/`
or one of its immediate child folders; path-based rules walk up from the target file):

  1  Agent/Task with no `model` and no pb agent -> set `model` (haiku for Explore, else sonnet) through
     `updatedInput` (a full copy of tool_input); in permission_mode "auto" the auto-mode classifier
     blocks a rewritten call, so there it only advises. A "fork" ignores model: advice only.
  2  Bash that parses registry.json inline (python -c / heredoc / jq / cat) -> `slice.py find|get --fields`.
  3  Bash `grep -r`, `rg`, `sed -n`, `cat` of a file over 256 KB -> the Grep / Read tools with a limit.
     (2 and 3 speak on the first occurrence in a session and then every 10th.)
  4  Registry write guard. Before a Bash write of registry.json, or an Edit/Write/MultiEdit of it, the
     current bytes are stashed in the per-user temp folder (keyed by session_id + tool_use_id, skipped
     over 20 MB); PostToolUse validates the file (parses, top level an object, no top-level key lost,
     no NEW duplicate id in components/screens) and, when it is broken, restores the stash atomically
     and says so. The stash is always deleted; with no stash nothing happens.
     A call that FAILS (a Bash write that raises half-way and exits non-zero) fires PostToolUseFailure
     instead of PostToolUse, so route.py is registered for both and both take the same path. Whatever
     the harness does, a second net runs at the start of EVERY route.py run: a stash of this session
     older than 5 s that nothing has validated is validated then (one line of additionalContext, then
     deleted). It leaves a stash alone while the registry is untouched or was written in the last 2 s,
     so a command that is still running is never restored over, and it puts back only a registry that
     no longer parses (a half-written file): which call wrote it is unknown, and the stash may predate
     other legitimate writes, so a lost key or a duplicate id is left to the Post / failure event.
  5  Edit/Write/MultiEdit/NotebookEdit on a file in a different pb project or git work tree (or under
     CLAUDE_PLUGIN_ROOT) than the session's -> `permissionDecision: "ask"`, until the user lets an edit
     in that (session, root) through: PreToolUse only records a pending (session, root, tool_use_id),
     and the PostToolUse of that tool_use_id turns it into the "asked" mark. A denied call fires no
     Post event, and a failed one fires only PostToolUseFailure, so neither leaves a mark and the next
     edit asks again. Edits issued in one parallel batch each ask (none has been answered yet).
     Scratch folders (the temp folder, /private/tmp, /tmp) never trigger it.
  6  `touch ...registry.json` -> the preview reloads on its own.
  7  Read of registry.json / prototype.html / design-system.html with no `limit` -> `slice.py get`.

Mode: `<project>/memory/doctor.json` key "enforce": "route" (default) | "advise" | "off"; the environment
variable PB_ENFORCE overrides it. "advise" turns every rewrite, ask and restore into an
additionalContext line; "off" does nothing at all. Test-only knob: PB_ROUTE_SCRATCH (os.pathsep list of
folders) replaces the default scratch folders of rule 5.

What it never does: refuse a call (no exit 2, no "deny"), or approve one (it never prints
permissionDecision "allow", which would skip the user's permission prompt; the only decision it can
print is "ask"). Commands that run a pb tool (`.../tools/<x>.py`) are never advised or rewritten. Any
error, bad stdin or no match prints nothing and exits 0. When `<project>/.preview/` exists every action
is logged as one JSON line to `.preview/route.log` (trimmed to its last 128 KB once it passes 256 KB;
never written through a symlink or to anything but a regular file).
Stdlib only (run as `python3 -S -B`), Python 3.7+.
"""
import json
import os
import re
import stat
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bash_advice import is_project, pb_projects  # noqa: E402  (shared: one definition of "a pb project")

HERE = os.path.dirname(os.path.abspath(__file__))
EVERY = 10                       # rules 2 and 3 speak on the 1st use in a session, then every 10th
BIG_FILE = 256 * 1024            # rule 3: `cat` of a file larger than this
MAX_STASH = 20 * 1024 * 1024     # rule 4: no stash of a registry larger than this
LATE_AGE = 5.0                   # rule 4: a stash this old (seconds) with no Post event is validated by the next run
LATE_QUIET = 2.0                 #   ...unless the registry itself was written within this many seconds
# The only reasons the lazy check acts on: the registry exists but cannot be read (a half-written file).
HARD_BREAKS = ("not valid JSON", "the top level is not an object")
LOG_MAX = 256 * 1024
LOG_KEEP = 128 * 1024
MODES = ("route", "advise", "off")
# pb/agents/*.md; tests/hook_route.py keeps this list equal to the folder.
PB_AGENTS = frozenset((
    "pb-builder", "pb-clarifier", "pb-data", "pb-design-system", "pb-explorer",
    "pb-flow", "pb-planner", "pb-reviewer", "pb-tester"))
# The built-in subagent types that have no model of their own (None = subagent_type omitted). "fork" is
# here so it gets its advice line; every other named agent is left alone (see rule_agent).
GENERIC_AGENTS = frozenset((None, "", "general-purpose", "Explore", "Plan", "claude", "fork"))
PB_TOOLS_FALLBACK = (
    "agents_install", "browser", "check", "clean", "clone_ds", "decisions_rotate", "ds_serve", "explore",
    "lint_registry", "logic_check", "logic_extract", "logic_shape", "orchestrate", "preview_register",
    "registry_to_figma", "render", "report", "research", "resolve_frame", "security_scan", "serve", "shot",
    "slice", "spec_measure", "spec_parts", "test_run", "ticket", "tokens")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
POST_TOOLS = ("Bash",) + EDIT_TOOLS   # the tools hooks.json sends to PostToolUse / PostToolUseFailure
POST_EVENTS = ("PostToolUse", "PostToolUseFailure")
HTML_OUTPUT = ("prototype.html", "design-system.html")

ADVICE_FORK = ("pb: a fork ignores model and runs on the session model; for routine work use a named "
               "subagent_type with model sonnet (haiku to search).")
ADVICE_AUTO = ("pb: set model on Agent calls (sonnet; haiku for Explore) "
               "— this one runs on the session model")
ADVICE_PARSE = ("pb: do not parse registry.json inline: `slice.py find <text>` locates a line and "
                "`slice.py get <kind> <id> --fields a,b` reads one slice (output is capped there).")
ADVICE_SEARCH = ("pb: search with the Grep tool (head_limit) and read a long file with the Read tool "
                 "(offset + limit), not grep -r / rg / sed -n / cat of a big file.")
ADVICE_TOUCH = ("pb: not needed — the preview reloads on registry.json, render/, runtime/, spec/ "
                "and logic/ changes.")
ADVICE_WRITE = ("pb: do not write registry.json by hand (it bypasses the registry lock): "
                "patch one slice with `slice.py set <kind> <id>`.")
ADVICE_WRITE_ROUTE = ADVICE_WRITE[:-1] + "; the previous version is restored if the result is invalid."
ADVICE_READ_REGISTRY = ("pb: do not read registry.json whole: `slice.py find <text>` locates a line, "
                        "`slice.py get <kind> <id> --fields a,b` reads one slice (or pass limit to Read).")
ADVICE_READ_HTML = ("pb: %s is rendered output, never read it whole: read the slice with "
                    "`slice.py get <kind> <id> --fields a,b` or the body under render/ (or pass limit to Read).")

# ---- Bash command shapes ------------------------------------------------------------------------
JSON_DUMP = re.compile(r"\bjson\.dump\(")
OPEN_W = re.compile(r"open\([^)]*registry\.json[^)]*['\"][wa]")
WRITE_TEXT = re.compile(r"\.write_text\(")
REDIRECT = re.compile(r">>?\s*['\"]?[\w./-]*registry\.json|\btee\b[^|;&\n]*registry\.json")
INLINE_PY = re.compile(r"\bpython[\d.]*\b[^\n|;&]*?(?:\s-c\b|\s-\s*<<|\s<<)")
JQ = re.compile(r"(?:^|[\s;&|(])jq\s")
CAT_REGISTRY = re.compile(r"(?:^|[;&|(\n])\s*cat\s+[^|;&\n]*registry\.json")
JSON_LOAD_OPEN = re.compile(r"json\.load\(\s*open\([^)]*registry\.json")
TOUCH = re.compile(r"(?:^|[;&|(\n])\s*touch\s+[^;&|\n]*registry\.json")
GREP_R = re.compile(r"(?:^|[;&|(\n]|\$\()\s*[ef]?grep\b[^;&|\n]*\s(?:-[A-Za-z]*[rR][A-Za-z]*|--recursive|--dereference-recursive)\b")
RG = re.compile(r"(?:^|[;&|(\n]|\$\()\s*rg\b")
SED_N = re.compile(r"(?:^|[;&|(\n]|\$\()\s*sed\s+(?:-[A-Za-z]+\s+)*-[A-Za-z]*n")
CAT_ARGS = re.compile(r"(?:^|[;&|(\n])\s*cat\s+([^|;&<>\n]+)")
REG_TOKEN = re.compile(r"""[^\s'"=<>|;&()`]*registry\.json""")
_PB_TOOL = []


def runs_pb_tool(cmd):
    """True when the command runs one of pb's own tools (`.../tools/<x>.py`): never advised, never rewritten."""
    if not _PB_TOOL:
        names = set(PB_TOOLS_FALLBACK)
        try:
            for f in os.listdir(os.path.join(os.path.dirname(HERE), "tools")):
                if f.endswith(".py") and f[:-3].isidentifier():
                    names.add(f[:-3])
        except OSError:
            pass
        _PB_TOOL.append(re.compile(r"(?<![\w-])tools/(?:%s)\.py\b" % "|".join(re.escape(n) for n in sorted(names))))
    return bool(_PB_TOOL[0].search(cmd))


def is_write(cmd):
    return bool(JSON_DUMP.search(cmd) or OPEN_W.search(cmd) or REDIRECT.search(cmd) or WRITE_TEXT.search(cmd))


def parses_inline(cmd):
    return bool(INLINE_PY.search(cmd) or JQ.search(cmd) or CAT_REGISTRY.search(cmd) or JSON_LOAD_OPEN.search(cmd))


# ---- paths ---------------------------------------------------------------------------------------
def real(path):
    return os.path.realpath(path)


def absolute(path, cwd):
    p = os.path.expandvars(os.path.expanduser(path))
    return real(p if os.path.isabs(p) else os.path.join(cwd, p))


def inside(path, base):
    return path == base or path.startswith(base.rstrip(os.sep) + os.sep)


def owning_project(path):
    """The nearest folder at or above `path` that is a pb project (walks up from the file), or None."""
    d = os.path.dirname(path)
    for _ in range(40):
        if is_project(d):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


def tmp_root():
    for key in ("TMPDIR", "TEMP", "TMP"):
        d = os.environ.get(key)
        if d and os.path.isdir(d) and os.access(d, os.W_OK | os.X_OK):
            return d
    for d in ("/tmp", "/var/tmp", "/usr/tmp"):
        if os.path.isdir(d) and os.access(d, os.W_OK | os.X_OK):
            return d
    return None


def scratch_dirs():
    env = os.environ.get("PB_ROUTE_SCRATCH")
    if env is not None:
        return [real(d) for d in env.split(os.pathsep) if d]
    dirs = [d for d in (tmp_root(), "/private/tmp", "/tmp") if d]
    return [real(d) for d in dirs]


# ---- per-user temp state (counters, ask-once marks, stashes) -------------------------------------
def state_dir(create=True):
    """<tmp>/pb-hooks-<uid> (the folder browser_advice.py uses), owned by us and not a link; None when unusable."""
    root = tmp_root()
    if not root:
        return None
    uid = os.getuid() if hasattr(os, "getuid") else "u"
    d = os.path.join(root, "pb-hooks-%s" % uid)
    try:
        if create:
            os.makedirs(d, mode=0o700, exist_ok=True)
        st = os.lstat(d)
    except OSError:
        return None
    if os.path.islink(d) or not os.path.isdir(d):
        return None
    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        return None
    return d


def safe(text):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)[:80] or "x"


def state_path(sid, name, create=True):
    d = state_dir(create)
    return os.path.join(d, "route-%s-%s" % (safe(sid), name)) if d else None


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def bump(sid, name):
    """Add one to this session's counter `name` and return it; None when it cannot be kept."""
    try:
        path = state_path(sid, name + ".count")
        if not path:
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                n = int(f.read().strip() or "0")
        except (OSError, ValueError):
            n = 0
        n += 1
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(n))
        return n
    except OSError:
        return None


def speaks(n):
    return n is not None and (n == 1 or n % EVERY == 0)


def asked_roots(sid):
    """The roots this session was already asked about (or advised on); None when the marks cannot be kept."""
    path = state_path(sid, "asked")
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(f.read().split("\n"))
    except (OSError, ValueError):
        return set()


def remember_asked(sid, root):
    """Add `root` to the session's asked marks. True when it is there afterwards."""
    try:
        known = asked_roots(sid)
        if known is None:
            return False
        if root in known:
            return True
        path = state_path(sid, "asked")
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "ab") as f:
            f.write((root + "\n").encode("utf-8"))
        return True
    except (OSError, ValueError):
        return False


def mark_asked(sid, root):
    """True the first time (session, root) is seen; False when it was seen before or cannot be kept."""
    known = asked_roots(sid)
    return known is not None and root not in known and remember_asked(sid, root)


def note_pending(sid, tuid, root):
    """Rule 5: the user has not answered yet. Keep (session, tool_use_id) -> root; PostToolUse success promotes it."""
    if not isinstance(tuid, str) or not tuid:
        return False
    try:
        path = state_path(sid, safe(tuid) + ".pend")
        if not path:
            return False
        write_private(path, json.dumps({"sid": sid, "root": root}).encode("utf-8"))
        return True
    except OSError:
        return False


def settle_pending(c):
    """The pending ask of this call: a successful call (PostToolUse) means the user let it through, so the root
    becomes an asked mark; a failed call (PostToolUseFailure) leaves none. A denied call fires neither, so its
    pending file just ages out (sweep) and the next edit asks again."""
    tuid = c.data.get("tool_use_id")
    if not isinstance(tuid, str) or not tuid:
        return
    path = state_path(c.sid, safe(tuid) + ".pend", create=False)
    if not path:
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return
    try:
        root = doc.get("root") if isinstance(doc, dict) and doc.get("sid") == c.sid else None
        if c.event == "PostToolUse" and isinstance(root, str) and root:
            remember_asked(c.sid, root)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def sweep(folder):
    """Drop stashes and pending asks older than an hour (a denied call never reaches Post; a failed one may not
    reach the hook) and counters / asked marks older than a week."""
    now = time.time()
    try:
        for name in os.listdir(folder):
            if not name.startswith("route-"):
                continue
            path = os.path.join(folder, name)
            age = now - os.lstat(path).st_mtime
            if (name.endswith((".stash", ".meta", ".pend")) and age > 3600) \
                    or (name.endswith((".count", "-asked")) and age > 7 * 86400):
                os.unlink(path)
    except OSError:
        pass


# ---- the call ------------------------------------------------------------------------------------
class Call(object):
    def __init__(self, data):
        self.data = data
        self.event = data.get("hook_event_name")
        self.tool = data.get("tool_name")
        ti = data.get("tool_input")
        self.ti = ti if isinstance(ti, dict) else {}
        cwd = data.get("cwd")
        self.cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
        sid = data.get("session_id")
        self.sid = sid if isinstance(sid, str) and sid else "p%d" % os.getppid()   # the Claude Code process, per session
        self.lines = []
        self.ask = None
        self.updated = None
        self.actions = []
        self._sessions = None
        self._modes = {}

    @property
    def sessions(self):
        if self._sessions is None:
            self._sessions = pb_projects(self.cwd)
        return self._sessions

    @property
    def session(self):
        return self.sessions[0] if self.sessions else None

    @property
    def lone_session(self):
        """The session's pb project when there is exactly one (several children = ambiguous = none)."""
        return self.sessions[0] if len(self.sessions) == 1 else None

    def mode(self, proj):
        if proj not in self._modes:
            self._modes[proj] = enforce_mode(proj)
        return self._modes[proj]

    def say(self, text):
        if text not in self.lines:
            self.lines.append(text)

    def act(self, proj, rule, action, detail=""):
        self.actions.append((proj, rule, action, detail))


def enforce_mode(proj):
    env = os.environ.get("PB_ENFORCE", "").strip().lower()
    if env in MODES:
        return env
    try:
        with open(os.path.join(proj, "memory", "doctor.json"), encoding="utf-8") as f:
            value = json.load(f).get("enforce")
    except (OSError, ValueError, AttributeError):
        return "route"
    value = value.strip().lower() if isinstance(value, str) else ""
    return value if value in MODES else "route"


# ---- rule 1: subagent calls set a model ----------------------------------------------------------
def rule_agent(c):
    ti = c.ti
    if not ti or ti.get("model"):
        return
    st = ti.get("subagent_type")
    if isinstance(st, str) and (st.startswith("pb:") or st in PB_AGENTS):
        return
    # Only the built-in generic types run on the session model by default. A named agent (a plugin's
    # `x:y`, or a project's own .claude/agents/<name>.md) may pin its model in frontmatter, which an
    # injected `model` would override — so it is left alone.
    if st not in GENERIC_AGENTS:
        return
    proj = c.session
    if not proj:
        return
    mode = c.mode(proj)
    if mode == "off":
        return
    if st == "fork":
        c.say(ADVICE_FORK)
        c.act(proj, 1, "advise", "fork")
        return
    model = "haiku" if st == "Explore" else "sonnet"
    if mode == "route" and c.data.get("permission_mode") != "auto":
        new = dict(ti)                      # updatedInput replaces the whole tool_input: copy every field
        new["model"] = model
        c.updated = new
        c.say("pb: this subagent call had no model; set model=%s (haiku for Explore, sonnet otherwise)." % model)
        c.act(proj, 1, "rewrite", "model=" + model)
    else:
        c.say(ADVICE_AUTO)
        c.act(proj, 1, "advise", "auto" if c.data.get("permission_mode") == "auto" else mode)


# ---- rules 2, 3, 4, 6: Bash ---------------------------------------------------------------------
def big_cat(cmd, cwd):
    for m in CAT_ARGS.finditer(cmd):
        for tok in m.group(1).split()[:8]:
            if tok.startswith("-"):
                continue
            try:
                path = absolute(tok.strip("'\""), cwd)
                if os.path.isfile(path) and os.path.getsize(path) > BIG_FILE:
                    return True
            except (OSError, ValueError):
                continue
    return False


def registry_targets(cmd, cwd, session):
    """(real registry path, project folder) for the registry.json files this command names (at most 3)."""
    out, seen = [], set()
    for tok in REG_TOKEN.findall(cmd)[:6]:
        path = absolute(tok, cwd)
        if not os.path.isfile(path) and session:
            path = real(os.path.join(session, "registry.json"))      # a bare name, run from a folder above it
        if path in seen or not os.path.isfile(path) or not is_project(os.path.dirname(path)):
            continue
        seen.add(path)
        out.append((path, os.path.dirname(path)))
    return out[:3]


def stash_registries(c, targets):
    """Rule 4, before the write: keep the bytes of each registry in the per-user temp folder.
    Returns how many were kept (0 when there is no tool_use_id, no usable temp folder or the file is too big)."""
    tuid = c.data.get("tool_use_id")
    if not isinstance(tuid, str) or not tuid:
        return 0
    try:
        folder = state_dir()
        if not folder:
            return 0
        sweep(folder)
        items = []
        for i, (path, proj) in enumerate(targets):
            if os.path.getsize(path) > MAX_STASH:
                continue
            with open(path, "rb") as f:
                data = f.read()
            st = os.stat(path)
            name = "route-%s-%s-%d.stash" % (safe(c.sid), safe(tuid), i)
            write_private(os.path.join(folder, name), data)
            items.append({"path": path, "stash": name, "proj": proj, "size": st.st_size, "mtime": st.st_mtime})
            c.act(proj, 4, "stash", "%d bytes" % len(data))
        if items:
            write_private(os.path.join(folder, "route-%s-%s.meta" % (safe(c.sid), safe(tuid))),
                          json.dumps({"sid": c.sid, "items": items}).encode("utf-8"))
        return len(items)
    except OSError:
        return 0


def rule_bash(c):
    cmd = c.ti.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        return
    named = "registry.json" in cmd
    write = named and "slice.py" not in cmd and is_write(cmd)
    touch = named and bool(TOUCH.search(cmd))
    parse = named and not write and parses_inline(cmd)
    search = bool(GREP_R.search(cmd) or RG.search(cmd) or SED_N.search(cmd))
    maybe_cat = bool(CAT_ARGS.search(cmd))
    if not (write or touch or parse or search or maybe_cat) or runs_pb_tool(cmd):
        return
    if write:                                         # rule 4 needs no session project: the file decides
        targets = registry_targets(cmd, c.cwd, c.session)
        if targets:
            proj = targets[0][1]
            mode = c.mode(proj)
            if mode != "off":
                kept = stash_registries(c, targets)
                c.say(ADVICE_WRITE_ROUTE if (mode == "route" and kept) else ADVICE_WRITE)
                c.act(proj, 4, "advise", "write")
    proj = c.session
    if not proj or c.mode(proj) == "off":
        return
    if touch:
        c.say(ADVICE_TOUCH)
        c.act(proj, 6, "advise", "touch")
    if parse and speaks(bump(c.sid, "parse")):
        c.say(ADVICE_PARSE)
        c.act(proj, 2, "advise", "parse")
    if not parse and (search or (maybe_cat and big_cat(cmd, c.cwd))) and speaks(bump(c.sid, "search")):
        c.say(ADVICE_SEARCH)
        c.act(proj, 3, "advise", "search")


# ---- rule 4 (Edit/Write/MultiEdit) and rule 5: file edits ---------------------------------------
def rule_edit(c):
    path = c.ti.get("file_path") or c.ti.get("notebook_path")
    if not isinstance(path, str) or not path:
        return
    target = absolute(path, c.cwd)
    if c.tool != "NotebookEdit" and os.path.basename(target) == "registry.json" \
            and os.path.isfile(target) and is_project(os.path.dirname(target)):
        proj = os.path.dirname(target)
        if c.mode(proj) != "off":
            stash_registries(c, [(target, proj)])
    rule_cross(c, target)


def other_root(target):
    """The root `target` belongs to: CLAUDE_PLUGIN_ROOT, else its pb project, else its git work tree, else None."""
    plugin = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin:
        plugin = real(plugin)
        if inside(target, plugin):
            return plugin
    d = os.path.dirname(target)
    for _ in range(40):
        if is_project(d) or os.path.exists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


def rule_cross(c, target):
    sess = c.lone_session
    if not sess:
        return
    mode = c.mode(sess)
    if mode == "off":
        return
    sess_real = real(sess)
    if inside(target, sess_real) or any(inside(target, s) for s in scratch_dirs()):
        return
    root = other_root(target)
    if not root or inside(sess_real, root):             # the session's own tree (e.g. the repo around `.prototype/`)
        return
    reason = "pb: this edits %s from %s" % (root, sess_real)
    if mode == "route":
        # Ask until an edit in this root has actually gone through: the mark is made by the PostToolUse of
        # this tool_use_id (settle_pending), not here, so a denied or failed call asks again next time.
        known = asked_roots(c.sid)
        if known is None or root in known:              # marks cannot be kept (fail open), or already let through
            return
        note_pending(c.sid, c.data.get("tool_use_id"), root)
        c.ask = reason
        c.act(sess, 5, "ask", root)
    else:
        if not mark_asked(c.sid, root):                 # advise: nothing to answer, so one line per root is enough
            return
        c.say(reason)
        c.act(sess, 5, "advise", root)


# ---- rule 7: Read --------------------------------------------------------------------------------
def rule_read(c):
    path = c.ti.get("file_path")
    if not isinstance(path, str) or not path or c.ti.get("limit") is not None:
        return
    name = os.path.basename(path)
    if name != "registry.json" and name not in HTML_OUTPUT:
        return
    target = absolute(path, c.cwd)
    proj = owning_project(target)
    if not proj or c.mode(proj) == "off":
        return
    c.say(ADVICE_READ_REGISTRY if name == "registry.json" else ADVICE_READ_HTML % name)
    c.act(proj, 7, "advise", name)


# ---- PostToolUse: validate the stashed registry --------------------------------------------------
def duplicate_ids(doc):
    out = set()
    for key in ("components", "screens"):
        items = doc.get(key)
        if not isinstance(items, list):
            continue
        seen = set()
        for e in items:
            i = e.get("id") if isinstance(e, dict) else None
            if isinstance(i, str):
                if i in seen:
                    out.add("%s:%s" % (key, i))
                seen.add(i)
    return out


def broken_reason(before, after):
    """Why `after` (bytes) is not an acceptable registry.json given the `before` bytes; None when it is fine."""
    try:
        doc = json.loads(after.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return "not valid JSON"
    if not isinstance(doc, dict):
        return "the top level is not an object"
    try:
        old = json.loads(before.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        old = None
    if isinstance(old, dict):
        lost = [k for k in old if k not in doc]
        if lost:
            return "top-level key lost: " + ", ".join(sorted(lost)[:5])
    dup = duplicate_ids(doc) - (duplicate_ids(old) if isinstance(old, dict) else set())
    if dup:
        return "duplicate id in components/screens: " + ", ".join(sorted(dup)[:5])
    return None


def restore(path, data):
    """Replace `path` with `data` atomically (temp file in the same folder, then os.replace)."""
    tmp = os.path.join(os.path.dirname(path), ".registry.restore.%d.tmp" % os.getpid())
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        except OSError:
            os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_or_none(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def load_meta(meta):
    """The stash index written by stash_registries, or None when it is unreadable."""
    try:
        with open(meta, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def untouched(it, path):
    """True while the registry still has the size and mtime it had when it was stashed (nothing wrote to it)."""
    try:
        st = os.stat(path)
    except OSError:
        return False
    return it.get("size") == st.st_size and it.get("mtime") == st.st_mtime


def settling(path):
    """True when the file was written in the last LATE_QUIET seconds: a command may still be writing it."""
    try:
        return time.time() - os.stat(path).st_mtime < LATE_QUIET
    except OSError:
        return False


def settle(c, meta, doc, late=False):
    """Validate every registry a stash index guards, restore the broken ones, then delete the stash files.
    late=True is the lazy check of a stash no Post event came for: while its call may still be running (the
    registry is untouched, or was written within LATE_QUIET seconds) the stash is kept for a later run."""
    folder = os.path.dirname(meta)
    items = doc.get("items") if isinstance(doc.get("items"), list) else []
    keep = False
    try:
        for it in items:
            if not isinstance(it, dict):
                continue
            path, name, proj = it.get("path"), it.get("stash"), it.get("proj")
            if not (isinstance(path, str) and isinstance(name, str) and isinstance(proj, str)):
                continue
            mode = c.mode(proj)
            if mode == "off":
                continue
            if late and (untouched(it, path) or settling(path)):
                keep = True
                continue
            with open(os.path.join(folder, os.path.basename(name)), "rb") as f:
                before = f.read()
            after = read_or_none(path)
            if after == before:
                if late:
                    keep = True
                continue
            reason = "file missing" if after is None else broken_reason(before, after)
            if late and reason not in HARD_BREAKS:
                # Nothing says which call wrote it, and the stash may predate other legitimate writes (a call
                # the user denied leaves one too): only a registry that cannot be read at all is put back.
                c.act(proj, 4, "verified", "late")
                continue
            if not reason:
                c.act(proj, 4, "verified")
                continue
            if mode == "route":
                try:
                    now = read_or_none(path)            # read again: restore only what is still broken
                    reason = "file missing" if now is None else broken_reason(before, now)
                    if reason and not (late and reason not in HARD_BREAKS):
                        restore(path, before)
                        c.say("pb: registry.json was invalid after this write (%s); restored the previous "
                              "version. Use slice.py set." % reason)
                        c.act(proj, 4, "restore", reason + (" (late)" if late else ""))
                except OSError:
                    c.say("pb: registry.json was invalid after this write (%s) and could not be restored; "
                          "fix it with slice.py set." % reason)
                    c.act(proj, 4, "report", reason + " (restore failed)")
            else:
                c.say("pb: registry.json is invalid after this write (%s); not restored (enforce=advise). "
                      "Use slice.py set." % reason)
                c.act(proj, 4, "report", reason)
    finally:
        if not keep:
            for it in items:
                name = it.get("stash") if isinstance(it, dict) else None
                if isinstance(name, str):
                    try:
                        os.unlink(os.path.join(folder, os.path.basename(name)))
                    except OSError:
                        pass
            try:
                os.unlink(meta)
            except OSError:
                pass


def post_registry(c):
    """PostToolUse / PostToolUseFailure of a call that stashed a registry: validate it, restore it if broken."""
    tuid = c.data.get("tool_use_id")
    if not isinstance(tuid, str) or not tuid:
        return
    meta = state_path(c.sid, safe(tuid) + ".meta", create=False)
    if not meta or not os.path.isfile(meta):
        return                                          # no stash: nothing to do
    doc = load_meta(meta)
    if doc is None:
        try:
            os.unlink(meta)
        except OSError:
            pass
        return
    settle(c, meta, doc)


def recover(c):
    """The second net, at the start of every run: a stash of THIS session older than LATE_AGE seconds that no Post
    event has settled (the harness sent a failure event we never saw, or none at all) is validated now.
    Costs one stat of the state folder and one listing when this session has no stash."""
    folder = state_dir(create=False)
    if not folder:
        return
    prefix = "route-%s-" % safe(c.sid)
    try:
        names = [n for n in os.listdir(folder) if n.startswith(prefix) and n.endswith(".meta")]
    except OSError:
        return
    if not names:
        return
    tuid = c.data.get("tool_use_id")
    own = "%s%s.meta" % (prefix, safe(tuid)) if isinstance(tuid, str) and tuid and c.event in POST_EVENTS else None
    now = time.time()
    for name in sorted(names):
        if name == own:
            continue                                    # this very call: post_registry settles it
        meta = os.path.join(folder, name)
        try:
            if now - os.lstat(meta).st_mtime <= LATE_AGE:
                continue                                # a call that is probably still running
            doc = load_meta(meta)
            if doc is None or doc.get("sid") != c.sid:  # unreadable, or another session whose id shares the prefix
                continue
            settle(c, meta, doc, late=True)
        except Exception:  # noqa: BLE001  one bad stash must not stop the others, nor the call's own rules
            continue


# ---- output and log ------------------------------------------------------------------------------
def write_log(c):
    by_project = {}
    for proj, rule, action, detail in c.actions:
        by_project.setdefault(proj, []).append(json.dumps(
            {"t": round(time.time(), 3), "sid": c.sid, "event": c.event, "tool": c.tool,
             "rule": rule, "action": action, "detail": detail}, separators=(",", ":")))
    for proj, lines in by_project.items():
        folder = os.path.join(proj, ".preview")
        if not os.path.isdir(folder):
            continue
        path = os.path.join(folder, "route.log")
        try:
            size = append_log(path, ("\n".join(lines) + "\n").encode("utf-8"))
            if size is not None and size > LOG_MAX:
                trim_log(path)
        except OSError:
            pass


def append_log(path, data):
    """Append `data` to `path` only when it is a regular file that is not a link (a planted symlink or a FIFO is
    never written through). -> the size afterwards, or None when it was refused."""
    if os.path.islink(path):
        return None
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags, 0o644)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return None
        with os.fdopen(fd, "ab") as f:
            fd = None
            f.write(data)
        return st.st_size + len(data)
    finally:
        if fd is not None:
            os.close(fd)


def trim_log(path):
    """Keep the last LOG_KEEP bytes of the log, whole lines, replacing it atomically."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            return
        f.seek(-LOG_KEEP, os.SEEK_END)
        tail = f.read()
    tail = tail[tail.find(b"\n") + 1:]                  # drop the cut line
    tmp = path + ".%d.tmp" % os.getpid()
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
        with os.fdopen(fd, "wb") as f:
            f.write(tail)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def emit(c):
    if not (c.lines or c.ask or c.updated is not None):
        return
    hso = {"hookEventName": c.event}
    if c.lines:
        hso["additionalContext"] = " ".join(c.lines)
    if c.ask:
        hso["permissionDecision"] = "ask"               # the only decision this hook can print: never "allow"
        hso["permissionDecisionReason"] = c.ask
    if c.updated is not None:
        hso["updatedInput"] = c.updated
    sys.stdout.write(json.dumps({"hookSpecificOutput": hso}))


def main():
    data = json.loads(sys.stdin.read())
    if not isinstance(data, dict):
        return
    c = Call(data)
    if not isinstance(c.event, str) or not isinstance(c.tool, str):
        return
    if c.event != "PreToolUse" and c.event not in POST_EVENTS:
        return
    try:
        recover(c)                                      # rule 4's second net: runs first, on every event
    except Exception:  # noqa: BLE001
        pass
    if c.event == "PreToolUse":
        if c.tool in ("Agent", "Task"):
            rule_agent(c)
        elif c.tool == "Bash":
            rule_bash(c)
        elif c.tool == "Read":
            rule_read(c)
        elif c.tool in EDIT_TOOLS:
            rule_edit(c)
    elif c.tool in POST_TOOLS:                          # PostToolUse (the call went through) or PostToolUseFailure
        settle_pending(c)
        if c.tool != "NotebookEdit":
            post_registry(c)
    emit(c)
    write_log(c)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # a broken hook must never get in the way
        pass
    sys.exit(0)
