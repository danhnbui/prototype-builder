/* research-session.js — the browser side of a usability session on a pb prototype.
   Inlined just before </body> of a participant page (page "session" | "kit"), or of the small observer page
   (page "observer"), by pb/tools/research_session.py build_page. It reads window.PB_RS_SESSION (set in <head>)
   and defines window.pbRsSession SYNCHRONOUSLY; the flow starts on setTimeout(start, 0), so research-methods.js,
   loaded right after this file, can register its runners first. Inert (no throw) where `document` is undefined
   or where there is no PB_RS_SESSION.

   What it does, in the order a participant meets it:
     setup (participant code) -> consent (+ optional screen/voice recording) -> warm-up questions ->
     runners[method].run(ctx) (core registers "usability") -> closing questions -> sink (POST to the preview
     server, or download).
   What it records, from the first consent on: screens, clicks named by component, dead and rage clicks, masked
   field input (the LENGTH, never the value), submits, validation errors, toasts, wizard steps, role changes,
   scroll, tab visibility, answers, and the tasks. Only isTrusted DOM events are recorded (Compare mode and the
   sandbox runner produce synthetic ones). Format: the `pb-session` v1 file (research-ux-spec.md §3).

   Tool chrome only: class prefix pb-rs-, --pb-* tokens (chrome.css), appended to <body>, never inside
   .pb-product. ES2019, no libraries, no network except same-origin fetch/XHR to config.post. Every storage
   access is guarded. Plain buttons, aria-live for status, prefers-reduced-motion respected, usable at 429px. */
(function () {
  'use strict';
  if (typeof document === 'undefined' || typeof window === 'undefined') return;
  var CFG = window.PB_RS_SESSION;
  if (!CFG || typeof CFG !== 'object' || window.pbRsSession) return;

  /* ============================================================================================
     0 · constants, small helpers
     ============================================================================================ */
  var PAGE = CFG.page === 'observer' ? 'observer' : (CFG.page === 'kit' ? 'kit' : 'session');
  var INST = CFG.instrument && typeof CFG.instrument === 'object' ? CFG.instrument : {};
  var SECTIONS = Array.isArray(INST.sections) ? INST.sections.filter(isObj) : [];
  var MODERATOR = CFG.moderator && typeof CFG.moderator === 'object' ? CFG.moderator : {};
  var MAX_EVENTS = 50000, SESSION_MAX_BYTES = 16 * 1024 * 1024;
  var OUTCOMES = ['success', 'fail', 'abandoned', 'timeout', 'skipped', 'answered'];   // 'answered': a tree-test choice made without an answer key on the page
  var MARKABLE = ['success', 'fail', 'abandoned', 'timeout', 'skipped'];                // what the observer offers as a facilitator override
  var SOURCES = ['criteria', 'self', 'facilitator'];
  var ESSENTIAL = { 'session-start': 1, 'session-end': 1, consent: 1, 'task-start': 1, 'task-end': 1, criteria: 1, answer: 1,
    note: 1, assist: 1, mark: 1, 'media-start': 1, 'media-stop': 1, 'tt-open': 1, 'tt-choose': 1, 'cs-group': 1, 'cs-move': 1, 'fc-click': 1 };
  var INTERACTIVE = 'a,button,input,select,textarea,label,summary,[data-nav],[data-back],[data-action],[data-step-go],[onclick],'
    + '[role=button],[role=link],[tabindex]:not([tabindex="-1"])';

  function isObj(x) { return !!x && typeof x === 'object' && !Array.isArray(x); }
  function safe(fn, dflt) { try { return fn(); } catch (e) { return dflt; } }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function squash(s) { return String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); }
  function cut(s, n) { s = String(s == null ? '' : s); return s.length > n ? s.slice(0, n) : s; }
  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
  function r4(v) { return Math.round(v * 10000) / 10000; }
  function perfNow() { return (window.performance && typeof performance.now === 'function') ? performance.now() : Date.now(); }
  function rnd36(n) {
    var s = '', i;
    try { var a = new Uint8Array(n); window.crypto.getRandomValues(a); for (i = 0; i < n; i++) s += (a[i] % 36).toString(36); }
    catch (e) { s = ''; for (i = 0; i < n; i++) s += Math.floor(Math.random() * 36).toString(36); }
    return s;
  }
  function st() { try { return state; } catch (e) { return null; } }   // the shell's lexical `state`, absent on the observer page
  function curScreen() { var s = st(); return s && s.protoScreenId != null ? String(s.protoScreenId) : null; }
  function protoBox() { return document.getElementById('proto-frame') || document.querySelector('.proto-screen'); }
  function isTaskQ(q) { return isObj(q) && (isObj(q.task) || isObj(q.tree) || isObj(q.click)); }
  function fileSafe(s) { return String(s == null ? '' : s).replace(/[^A-Za-z0-9._-]+/g, '-'); }
  function h(tag, props, kids) {
    var n = document.createElement(tag);
    if (props) Object.keys(props).forEach(function (k) {
      var v = props[k];
      if (v == null || v === false) return;
      if (k === 'class') n.className = v;
      else if (k === 'text') n.textContent = v;
      else if (k === 'html') n.innerHTML = v;
      else if (k.slice(0, 2) === 'on' && typeof v === 'function') n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? '' : String(v));
    });
    if (kids != null) (Array.isArray(kids) ? kids : [kids]).forEach(function (c) {
      if (c != null) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return n;
  }

  /* SHA-256 of a string's UTF-8 bytes, synchronous and dependency-free (crypto.subtle is absent on plain-http pages). */
  function sha256hex(str) {
    var K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01,
      0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
      0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
      0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
      0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08,
      0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
      0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
    var H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    var bytes = [], i, j;
    var u;
    try { u = unescape(encodeURIComponent(String(str))); }
    catch (e) { u = unescape(encodeURIComponent(String(str).replace(/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/g, '\uFFFD'))); }
    for (i = 0; i < u.length; i++) bytes.push(u.charCodeAt(i));
    var bitLen = bytes.length * 8;
    bytes.push(0x80);
    while (bytes.length % 64 !== 56) bytes.push(0);
    var hi = Math.floor(bitLen / 0x100000000), lo = bitLen >>> 0;
    bytes.push((hi >>> 24) & 255, (hi >>> 16) & 255, (hi >>> 8) & 255, hi & 255, (lo >>> 24) & 255, (lo >>> 16) & 255, (lo >>> 8) & 255, lo & 255);
    function rotr(x, n) { return (x >>> n) | (x << (32 - n)); }
    var w = new Array(64);
    for (i = 0; i < bytes.length; i += 64) {
      for (j = 0; j < 16; j++) w[j] = ((bytes[i + j * 4] << 24) | (bytes[i + j * 4 + 1] << 16) | (bytes[i + j * 4 + 2] << 8) | bytes[i + j * 4 + 3]) | 0;
      for (j = 16; j < 64; j++) {
        var s0 = rotr(w[j - 15], 7) ^ rotr(w[j - 15], 18) ^ (w[j - 15] >>> 3);
        var s1 = rotr(w[j - 2], 17) ^ rotr(w[j - 2], 19) ^ (w[j - 2] >>> 10);
        w[j] = (w[j - 16] + s0 + w[j - 7] + s1) | 0;
      }
      var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], hh = H[7];
      for (j = 0; j < 64; j++) {
        var S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25), ch = (e & f) ^ (~e & g);
        var t1 = (hh + S1 + ch + K[j] + w[j]) | 0;
        var S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22), mj = (a & b) ^ (a & c) ^ (b & c);
        var t2 = (S0 + mj) | 0;
        hh = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
      }
      H[0] = (H[0] + a) | 0; H[1] = (H[1] + b) | 0; H[2] = (H[2] + c) | 0; H[3] = (H[3] + d) | 0;
      H[4] = (H[4] + e) | 0; H[5] = (H[5] + f) | 0; H[6] = (H[6] + g) | 0; H[7] = (H[7] + hh) | 0;
    }
    return H.map(function (x) { return ('00000000' + (x >>> 0).toString(16)).slice(-8); }).join('');
  }

  /* The words the page itself says. English; a study may override any of them with instrument.ui. */
  var T = {
    setupTitle: 'Before we begin', code: 'Participant code',
    codeHint: 'Type the code you were given, for example P01. Please do not type your name or contact details.',
    codeErr: 'Enter a code like P01 (the letter P and two or three digits).',
    pilot: 'This is a practice run (a pilot). It is saved apart and is not analysed.',
    howTitle: 'How this works',
    how1: 'We are testing the design, not you. There are no wrong answers.',
    how2: 'You will get a few tasks to try on a prototype. It is a sketch, so some things may not work.',
    thinkAloud: 'Please think aloud: say what you are looking at, what you expect and what you are trying to do.',
    next: 'Continue', back: 'Back',
    consentTitle: 'Taking part',
    consentDefault: 'Your actions on this page are saved without your name, together with your answers. You can stop at any time by closing this page. Nothing is shared outside the research team.',
    agree: 'I agree to take part', decline: 'I do not agree',
    recordScreen: 'Also record my screen', recordScreenVoice: 'Also record my screen and my voice',
    recordNote: 'The recording is optional. You can take part without it.',
    noRecord: 'This browser cannot record the screen, so the session will go ahead without a recording.',
    mustAgree: 'Tick the box to take part, or choose "I do not agree".',
    declined: 'No problem. Nothing was saved. You can close this page.',
    recFailTitle: 'Recording did not start', recFail: 'The recording could not start',
    recRetry: 'Try again', recSkip: 'Continue without recording',
    recVoiceFail: 'The microphone was not available, so only the screen is recorded.',
    recOn: 'Recording', recOnVoice: 'Recording screen and voice', recEnded: 'Screen sharing stopped. The session continues without recording.',
    required: 'Please answer this question.', fixAnswers: 'Some answers are missing.',
    taskOf: function (i, n) { return 'Task ' + i + ' of ' + n; },
    start: 'Start task', done: "I'm done", giveUp: 'Give up', timeUp: 'Time is up for this task', timeUpBody: "Let's move on.",
    aboutTask: 'About this task', expand: 'Show the whole task', collapse: 'Show less', reminder: 'Please say out loud what you are thinking.',
    noRunner: 'This kind of study cannot run in this page.', save: 'Save what was recorded',
    doneTitle: 'Thank you', saving: 'Saving…', saved: 'Saved', savedAs: function (e) { return 'Saved as ' + e + '.'; },
    savedPilot: 'Saved as a practice run (not analysed).', replay: 'Open the replay',
    uploading: function (p) { return 'Uploading the recording… ' + p + '%'; }, uploaded: 'The recording was uploaded.',
    saveFail: function (m) { return 'The session could not be saved: ' + m; }, mediaFail: function (m) { return 'The recording could not be uploaded: ' + m; },
    retry: 'Try again', downloadInstead: 'Download instead', downloadCopy: 'Download a copy',
    dlSession: 'Download the session file', dlMedia: 'Download the recording',
    dlHow: 'Please send the file or files below to the person who invited you. Nothing has been sent from this page.',
    interruptedTitle: 'An earlier session was interrupted',
    interrupted: 'This tab holds a session that did not finish. You can save what was recorded, or start again.',
    startNew: 'Start a new session'
  };
  if (isObj(INST.ui)) Object.keys(INST.ui).forEach(function (k) { if (typeof INST.ui[k] === 'string' && typeof T[k] === 'string') T[k] = INST.ui[k]; });

  /* ============================================================================================
     1 · the session object and the clock
     ============================================================================================ */
  var taskQs = [];
  SECTIONS.forEach(function (sec) { (Array.isArray(sec.questions) ? sec.questions : []).forEach(function (q) { if (isTaskQ(q)) taskQs.push(q); }); });
  var firstTaskSec = -1;
  SECTIONS.forEach(function (sec, i) { if (firstTaskSec < 0 && sec.purpose === 'task') firstTaskSec = i; });

  var session = {
    format: 'pb-session', version: 1, study: CFG.study || null, method: CFG.method || 'usability',
    sessionId: 's-' + Date.now().toString(36) + '-' + rnd36(4),
    participant: typeof CFG.participant === 'string' ? CFG.participant : null,
    mode: CFG.mode === 'unmoderated' ? 'unmoderated' : 'moderated', pilot: !!CFG.pilot,
    startedAt: null, endedAt: null, durationMs: 0,
    env: { viewport: [0, 0], device: null, sink: CFG.sink === 'download' ? 'download' : 'server', shell: CFG.shell || null },
    consent: null,
    config: { tasks: JSON.parse(JSON.stringify(taskQs)) },
    tasks: [], answers: {}, events: [], media: []
  };
  if (Array.isArray(CFG.tree)) session.config.tree = JSON.parse(JSON.stringify(CFG.tree));
  if (Array.isArray(CFG.cards)) session.config.cards = JSON.parse(JSON.stringify(CFG.cards));
  if (isObj(CFG.sort)) session.config.sort = JSON.parse(JSON.stringify(CFG.sort));
  if (session.method === 'card-sort') session.result = { 'card-sort': { groups: [], unsorted: [] } };
  else if (session.method === 'tree-test' || session.method === 'first-click') { session.result = {}; session.result[session.method] = {}; }

  var started = false, finished = false, active = false;   // started: the clock runs · active: the recorder is on · finished: serialised
  var t0 = 0, epoch = 0, lastT = 0, mute = 0, curRow = null, droppedEvents = 0;
  var overrides = {};                                         // task id -> facilitator outcome, applied when the task ends
  var channel = null;
  try { if (typeof BroadcastChannel === 'function' && CFG.channel) channel = new BroadcastChannel(String(CFG.channel)); } catch (e) { channel = null; }
  function post(msg) { if (channel) { try { channel.postMessage(msg); } catch (e) { /* closed channel */ } } }

  function now() { return started ? Math.max(lastT, Math.floor(perfNow() - t0)) : 0; }
  function isoZ(ms) { return new Date(ms).toISOString(); }

  function push(type, fields) {
    if (!started) return null;
    if (session.events.length >= MAX_EVENTS - 200 && !ESSENTIAL[type]) { droppedEvents++; return null; }
    var t = now(); lastT = t;
    var ev = { t: t, type: type, task: curRow ? curRow.id : null, screen: curScreen() };
    if (fields) Object.keys(fields).forEach(function (k) { if (k !== 't' && k !== 'type') ev[k] = fields[k]; });
    session.events.push(ev);
    return ev;
  }
  function announce(ev, i) {
    persist();
    post({ kind: 'event', event: ev, i: i, sessionId: session.sessionId, participant: session.participant, pilot: session.pilot, epoch: epoch });
  }
  function emit(type, fields) {
    var ev = push(type, fields);
    if (ev) announce(ev, session.events.length - 1);
    return ev;
  }

  /* ---- a snapshot in sessionStorage (guarded): the only thing that survives an accidental reload ---- */
  var SNAP_KEY = 'pb-rs:snap:' + (CFG.study || '') + ':' + PAGE, persistTimer = 0;
  function persist(now_) {
    if (PAGE === 'observer' || !started || finished) return;
    if (persistTimer && !now_) return;
    clearTimeout(persistTimer);
    persistTimer = setTimeout(function () {
      persistTimer = 0;
      try { sessionStorage.setItem(SNAP_KEY, JSON.stringify({ savedAt: Date.now(), epoch: epoch, session: session })); } catch (e) { /* blocked or full */ }
    }, now_ ? 0 : Math.min(15000, 1500 + Math.floor(session.events.length / 8)));
  }
  function dropSnapshot() { clearTimeout(persistTimer); persistTimer = 0; try { sessionStorage.removeItem(SNAP_KEY); } catch (e) { /* ignore */ } }

  /* ============================================================================================
     2 · tasks
     ============================================================================================ */
  function taskRow(id) {
    for (var i = session.tasks.length - 1; i >= 0; i--) if (session.tasks[i].id === id) return session.tasks[i];
    return null;
  }
  var task = {
    current: function () { return curRow ? curRow.id : null; },
    begin: function (q) {
      if (!started) return null;
      var id = String(q && q.id != null ? q.id : 'task');
      if (curRow) task.end('abandoned', 'self');           // a runner that forgot to end the last one
      curRow = { id: id, startT: now(), endT: null, outcome: null, outcomeSource: null, criteriaT: null, selfReport: null, assisted: false, answers: {} };
      session.tasks.push(curRow);
      emit('task-start', { task: id });
      return curRow;
    },
    end: function (outcome, source, extra) {
      var row = curRow;
      if (!row) return null;
      if (OUTCOMES.indexOf(outcome) < 0) outcome = 'fail';
      if (SOURCES.indexOf(source) < 0) source = 'self';
      if (overrides[row.id]) { outcome = overrides[row.id]; source = 'facilitator'; }
      row.endT = now(); row.outcome = outcome; row.outcomeSource = source;
      if (isObj(extra)) {
        if (extra.selfReport === 'done' || extra.selfReport === 'gave-up') row.selfReport = extra.selfReport;
        if (extra.assisted) row.assisted = true;
      }
      emit('task-end', { task: row.id, outcome: outcome, source: source });
      curRow = null;
      return row;
    }
  };

  function postTask(q) {
    var qid = q && q.id;
    for (var s = 0; s < SECTIONS.length; s++) {
      var list = Array.isArray(SECTIONS[s].questions) ? SECTIONS[s].questions : [];
      for (var i = 0; i < list.length; i++) {
        if (list[i] && list[i].id === qid) {
          var out = [];
          for (var j = i + 1; j < list.length && !isTaskQ(list[j]); j++) out.push(list[j]);
          return out;
        }
      }
    }
    return [];
  }

  /* ============================================================================================
     3 · styles (one injected sheet) and the UI primitives
     ============================================================================================ */
  var CSS = [
    '.pb-rs{--rs-bg:var(--pb-page,#fbfbfc);--rs-surface:var(--pb-surface,#fff);--rs-raised:var(--pb-raised,#fff);--rs-wash:var(--pb-wash,#eceef2);',
    '--rs-hair:var(--pb-hair,#e4e6ea);--rs-hair2:var(--pb-hair-2,#c9cdd4);--rs-ink:var(--pb-ink,#23262d);--rs-ink2:var(--pb-ink-2,#4a505b);',
    '--rs-ink3:var(--pb-ink-3,#626874);--rs-on:var(--pb-on-ink,#fbfbfc);--rs-fail:var(--pb-fail,#c42b2b);--rs-fail-bg:var(--pb-fail-bg,#fdecec);',
    '--rs-pass:var(--pb-pass,#177443);--rs-warn:var(--pb-warn,#8a5b00);--rs-warn-bg:var(--pb-warn-bg,#fbf3df);--rs-info:var(--pb-info,#175cd3);',
    '--rs-scrim:var(--pb-scrim,rgb(35 38 45 / .35));--rs-font:var(--pb-font,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif);',
    '--rs-mono:var(--pb-mono,ui-monospace,Menlo,Consolas,monospace);color-scheme:light dark}',
    '.pb-rs,.pb-rs *{box-sizing:border-box}',
    '#pb-rs-root{position:fixed;inset:0;z-index:10000;pointer-events:none;font:400 1rem/1.5 var(--rs-font);color:var(--rs-ink)}',
    /* pointer-events is inherited: a layer another script (research-methods.js) appends to the root must still take clicks */
    '#pb-rs-root > *{pointer-events:auto}',
    '#pb-rs-root > .pb-rs-foot,#pb-rs-root > .pb-rs-live{pointer-events:none}',
    /* the tool's own chrome never reaches a participant: the bar, the activity strip, the Sandbox, and the Structure panel (its rows are jumps to any screen) */
    'body.pb-rs-on #meta-nav,body.pb-rs-on #pb-agent,body.pb-rs-on .pb-insp,body.pb-rs-on #pb-insp,body.pb-rs-on #proto-struct-panel{display:none!important}',
    ':root.pb-rs-page{--pb-bar-h:0px;--pb-agent-h:0px}',
    'html.pb-rs-observer,html.pb-rs-observer body{margin:0;background:var(--pb-page,#fbfbfc);color:var(--pb-ink,#23262d);font:400 .9375rem/1.5 var(--pb-font,system-ui,sans-serif)}',
    '.pb-rs :focus-visible{outline:2px solid var(--rs-info);outline-offset:2px}',
    '.pb-rs-live{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}',
    '.pb-rs-full{position:absolute;inset:0;overflow:auto;background:var(--rs-bg);pointer-events:auto;display:none;padding:1rem}',
    '.pb-rs-full.is-on{display:block}',
    '.pb-rs-full-in{min-height:100%;display:flex;align-items:center;justify-content:center}',
    '.pb-rs-layer{position:absolute;inset:0;display:none;align-items:center;justify-content:center;padding:1rem;background:var(--rs-scrim);pointer-events:auto;overflow:auto}',
    '.pb-rs-layer.is-on{display:flex}',
    '.pb-rs-card{width:min(34rem,100%);max-height:calc(100vh - 2rem);max-height:calc(100dvh - 2rem);display:flex;flex-direction:column;margin:auto;background:var(--rs-raised);',
    'color:var(--rs-ink);border:1px solid var(--rs-hair);border-radius:.5rem;box-shadow:var(--pb-shadow,0 .625rem 1.875rem rgb(35 38 45 / .14))}',
    '.pb-rs-full .pb-rs-card{max-height:none;width:min(40rem,100%);box-shadow:none}',
    '.pb-rs-card[hidden]{display:none}',
    '.pb-rs-card-h{padding:1rem 1.25rem .25rem}',
    '.pb-rs-card-t{margin:0;font-size:1.25rem;line-height:1.25;font-weight:600}',
    '.pb-rs-card-t:focus{outline:none}',
    '.pb-rs-card-b{padding:.5rem 1.25rem 1rem;overflow:auto;min-height:0}',
    '.pb-rs-card-f{display:flex;flex-wrap:wrap;gap:.5rem;justify-content:flex-end;padding:.75rem 1.25rem 1rem;border-top:1px solid var(--rs-hair)}',
    '.pb-rs-card-f:empty{display:none}',
    '.pb-rs-lead{margin:.25rem 0 .75rem;white-space:pre-line;color:var(--rs-ink2)}',
    '.pb-rs-text{margin:.25rem 0 .75rem;white-space:pre-line}',
    '.pb-rs-scn{margin:.25rem 0 .5rem;white-space:pre-line;font-size:1.0625rem}',
    '.pb-rs-note{margin:.5rem 0;color:var(--rs-ink2);font-size:.9375rem}',
    '.pb-rs-list{margin:.25rem 0 .75rem;padding-left:1.25rem;color:var(--rs-ink2)}',
    '.pb-rs-list li{margin:.25rem 0}',
    '.pb-rs-btn{min-height:2.5rem;padding:0 1rem;border:1px solid var(--rs-hair2);border-radius:.375rem;background:var(--rs-surface);color:var(--rs-ink);font:600 .9375rem/1 var(--rs-font);cursor:pointer}',
    '.pb-rs-btn:hover:not(:disabled){background:var(--rs-wash)}',
    '.pb-rs-btn:disabled{opacity:.5;cursor:default}',
    '.pb-rs-btn--solid{background:var(--rs-ink);border-color:var(--rs-ink);color:var(--rs-on)}',
    '.pb-rs-btn--solid:hover:not(:disabled){background:var(--rs-ink);opacity:.88}',
    '.pb-rs-btn--quiet{border-color:transparent;background:none;color:var(--rs-ink2)}',
    '.pb-rs-btn--quiet:hover:not(:disabled){color:var(--rs-ink);background:var(--rs-wash)}',
    '.pb-rs-btn--sm{min-height:2rem;padding:0 .625rem;font-size:.8125rem}',
    '.pb-rs-fld{display:grid;gap:.25rem;margin:.5rem 0 .75rem}',
    '.pb-rs-fld label,.pb-rs-lbl{font-weight:600}',
    '.pb-rs-in{width:100%;min-height:2.5rem;padding:.375rem .625rem;border:1px solid var(--rs-ink3);border-radius:.375rem;background:var(--rs-surface);color:var(--rs-ink);font:inherit}',
    'textarea.pb-rs-in{resize:vertical;min-height:5rem}',
    '.pb-rs-in[aria-invalid="true"]{border-color:var(--rs-fail);box-shadow:0 0 0 1px var(--rs-fail)}',
    '.pb-rs-hint{margin:0;color:var(--rs-ink3);font-size:.875rem}',
    '.pb-rs-err{margin:.25rem 0 0;color:var(--rs-fail);font-size:.875rem}',
    '.pb-rs-err[hidden]{display:none}',
    '.pb-rs-chk{display:flex;gap:.625rem;align-items:flex-start;margin:.5rem 0;cursor:pointer}',
    '.pb-rs-chk input{flex:none;width:1.125rem;height:1.125rem;margin:.2rem 0 0;accent-color:var(--rs-ink)}',
    '.pb-rs-form{display:grid;gap:1rem}',
    '.pb-rs-q{margin:0;padding:0;border:0;min-width:0}',
    '.pb-rs-q-t{padding:0;margin:0 0 .375rem;font-weight:600;white-space:pre-line}',
    '.pb-rs-req{color:var(--rs-fail);margin-left:.125rem}',
    '.pb-rs-q.is-bad .pb-rs-q-t{color:var(--rs-fail)}',
    '.pb-rs-opt{display:flex;gap:.625rem;align-items:flex-start;margin:.375rem 0 0;padding:.5rem .75rem;border:1px solid var(--rs-hair);border-radius:.375rem;cursor:pointer}',
    '.pb-rs-opt input{flex:none;width:1.125rem;height:1.125rem;margin:.2rem 0 0;accent-color:var(--rs-ink)}',
    '.pb-rs-opt:has(input:checked){border-color:var(--rs-ink);background:var(--rs-wash)}',
    '.pb-rs-scale{display:grid;grid-template-columns:repeat(var(--rs-n,5),minmax(0,1fr));gap:.375rem}',
    '.pb-rs-scale.is-many{grid-template-columns:repeat(auto-fill,minmax(2.5rem,1fr))}',
    '.pb-rs-pt{position:relative;display:block}',
    '.pb-rs-pt input{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer}',
    '.pb-rs-pt span{display:grid;place-items:center;min-width:0;height:2.5rem;padding:0 .25rem;border:1px solid var(--rs-hair2);border-radius:.375rem;background:var(--rs-surface);font-variant-numeric:tabular-nums}',
    '.pb-rs-pt input:checked + span{background:var(--rs-ink);border-color:var(--rs-ink);color:var(--rs-on);font-weight:600}',
    '.pb-rs-pt input:focus-visible + span{outline:2px solid var(--rs-info);outline-offset:2px}',
    '.pb-rs-scale-l{display:flex;justify-content:space-between;gap:1rem;margin-top:.25rem;color:var(--rs-ink3);font-size:.8125rem}',
    '.pb-rs-bar{position:absolute;top:0;left:0;right:0;display:none;align-items:center;gap:.5rem .75rem;flex-wrap:wrap;padding:.5rem .75rem;background:var(--rs-raised);border-bottom:1px solid var(--rs-hair);pointer-events:auto}',
    '.pb-rs-bar.is-on{display:flex}',
    /* wide: label · task text (one line, tap to open) · buttons. narrow: label · buttons, then the text on its own row (two lines, tap to open) */
    '.pb-rs-bar-n{order:1;flex:none;font-size:.75rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--rs-ink3)}',
    '.pb-rs-bar-txt{order:2;flex:1 1 12rem;min-width:0;padding:0;border:0;background:none;color:var(--rs-ink);font:inherit;text-align:left;cursor:pointer;',
    'display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:1;line-clamp:1;overflow:hidden}',
    '.pb-rs-bar-txt::after{content:" \\25BE";color:var(--rs-ink3)}',
    '.pb-rs-bar-txt[aria-expanded="true"]{-webkit-line-clamp:unset;line-clamp:unset;display:block}',
    '.pb-rs-bar-txt[aria-expanded="true"]::after{content:" \\25B4"}',
    '.pb-rs-bar-a{order:3;display:flex;gap:.375rem;flex:none;margin-left:auto}',
    '@media (max-width:36rem){.pb-rs-bar-a{order:2}.pb-rs-bar-txt{order:3;flex:1 1 100%;-webkit-line-clamp:2;line-clamp:2}}',
    'body.pb-rs-on{padding-top:var(--pb-bar-h,0px)}',
    '.pb-rs-foot{position:absolute;left:.75rem;bottom:.75rem;display:grid;gap:.375rem;justify-items:start;max-width:calc(100% - 1.5rem);pointer-events:none}',
    '.pb-rs-chip{display:inline-flex;align-items:center;gap:.375rem;padding:.25rem .625rem;border-radius:62rem;background:var(--rs-raised);border:1px solid var(--rs-hair2);font-size:.8125rem;color:var(--rs-ink)}',
    '.pb-rs-chip[hidden]{display:none}',
    '.pb-rs-dot{width:.5625rem;height:.5625rem;border-radius:50%;background:var(--rs-fail)}',
    '.pb-rs-sink{margin-top:.75rem;display:grid;gap:.5rem}',
    '.pb-rs-sink-s{margin:0}',
    '.pb-rs-sink-s.is-err{color:var(--rs-fail)}',
    '.pb-rs-sink-a{display:flex;flex-wrap:wrap;gap:.5rem}',
    '.pb-rs-link{color:var(--rs-info);text-underline-offset:.15em}',
    /* observer */
    '.pb-rs-ob{max-width:70rem;margin:0 auto;padding:1rem}',
    '.pb-rs-ob-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:.5rem 1rem;margin-bottom:1rem}',
    '.pb-rs-ob-h h1{margin:0;font-size:1.25rem}',
    '.pb-rs-ob-conn{margin:0;color:var(--rs-ink2)}',
    '.pb-rs-ob-grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:1rem;align-items:start}',
    '@media (max-width:56rem){.pb-rs-ob-grid{grid-template-columns:minmax(0,1fr)}}',
    '.pb-rs-ob-sec{background:var(--rs-surface);border:1px solid var(--rs-hair);border-radius:.5rem;padding:.75rem 1rem;margin-bottom:1rem}',
    '.pb-rs-ob-sec h2{margin:0 0 .5rem;font-size:.75rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--rs-ink3)}',
    '.pb-rs-ob-row{display:flex;flex-wrap:wrap;gap:.375rem;align-items:center}',
    '.pb-rs-ob-task{margin:.25rem 0;font-size:1.0625rem;white-space:pre-line}',
    '.pb-rs-ob-meta{margin:.25rem 0;color:var(--rs-ink2);font-size:.875rem}',
    '.pb-rs-ob-timer{font:600 1.5rem/1 var(--rs-mono);font-variant-numeric:tabular-nums}',
    '.pb-rs-badge{display:inline-block;padding:.0625rem .5rem;border-radius:62rem;border:1px solid var(--rs-hair2);font-size:.75rem;color:var(--rs-ink2)}',
    '.pb-rs-badge--ok{color:var(--rs-pass);border-color:var(--rs-pass)}',
    '.pb-rs-badge--bad{color:var(--rs-fail);border-color:var(--rs-fail);background:var(--rs-fail-bg)}',
    '.pb-rs-badge--warn{color:var(--rs-warn);border-color:var(--rs-warn);background:var(--rs-warn-bg)}',
    '.pb-rs-feed{list-style:none;margin:0;padding:0;max-height:28rem;overflow:auto;font-size:.8125rem}',
    '.pb-rs-feed li{display:flex;gap:.5rem;padding:.25rem 0;border-bottom:1px solid var(--rs-hair)}',
    '.pb-rs-feed time{flex:none;width:3.25rem;color:var(--rs-ink3);font-family:var(--rs-mono);font-variant-numeric:tabular-nums}',
    '.pb-rs-feed b{flex:none;width:5.5rem;font-weight:600;overflow:hidden;text-overflow:ellipsis}',
    '.pb-rs-feed span{min-width:0;overflow-wrap:anywhere;color:var(--rs-ink2)}',
    '.pb-rs-feed li.is-warn b{color:var(--rs-warn)}',
    '.pb-rs-feed li.is-bad b{color:var(--rs-fail)}',
    '.pb-rs-guide details{border-top:1px solid var(--rs-hair);padding:.375rem 0}',
    '.pb-rs-guide summary{cursor:pointer;font-weight:600}',
    '.pb-rs-guide ul{margin:.25rem 0 .5rem;padding-left:1.25rem;color:var(--rs-ink2)}',
    '.pb-rs-guide .is-now{background:var(--rs-wash);border-radius:.25rem;padding:.125rem .375rem}',
    '@media (max-width:30rem){.pb-rs-card-h{padding:.875rem 1rem .25rem}.pb-rs-card-b{padding:.5rem 1rem .875rem}.pb-rs-card-f{padding:.75rem 1rem .875rem}',
    '.pb-rs-full{padding:.5rem}.pb-rs-layer{padding:.5rem}.pb-rs-btn{min-height:2.75rem}.pb-rs-pt span{height:2.75rem}}',
    '@media (prefers-reduced-motion:no-preference){.pb-rs-card{animation:pb-rs-in .14s ease-out}@keyframes pb-rs-in{from{opacity:0;transform:translateY(.375rem)}to{opacity:1;transform:none}}}'
  ].join('\n');
  function injectCss() {
    if (document.getElementById('pb-rs-session-css')) return;
    var s = h('style', { id: 'pb-rs-session-css' });
    s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }

  var rootEl = null, fullEl = null, fullIn = null, layerEl = null, barEl = null, liveEl = null, footEl = null, recChip = null, hintChip = null;
  var fullOn = false, cardUid = 0, statusTimer = 0;
  function getRoot() {
    if (rootEl && rootEl.parentNode) return rootEl;
    injectCss();
    rootEl = h('div', { id: 'pb-rs-root', class: 'pb-rs' });
    fullIn = h('div', { class: 'pb-rs-full-in' });
    fullEl = h('div', { class: 'pb-rs-full' }, fullIn);
    layerEl = h('div', { class: 'pb-rs-layer' });
    barEl = h('div', { class: 'pb-rs-bar', role: 'region', 'aria-label': 'Current task' });
    liveEl = h('div', { class: 'pb-rs-live', role: 'status', 'aria-live': 'polite', 'aria-atomic': 'true' });
    recChip = h('span', { class: 'pb-rs-chip', hidden: true }, [h('span', { class: 'pb-rs-dot', 'aria-hidden': 'true' }), h('span', { class: 'pb-rs-rec-t' })]);
    hintChip = h('span', { class: 'pb-rs-chip', hidden: true });
    footEl = h('div', { class: 'pb-rs-foot' }, [hintChip, recChip]);
    [fullEl, barEl, layerEl, footEl, liveEl].forEach(function (n) { rootEl.appendChild(n); });
    (document.body || document.documentElement).appendChild(rootEl);
    return rootEl;
  }
  function setFull(on) {
    getRoot();
    fullOn = !!on;
    fullEl.classList.toggle('is-on', fullOn);
    if (fullOn) fullEl.scrollTop = 0;
  }
  function status(text, ms) {
    getRoot();
    clearTimeout(statusTimer);
    liveEl.textContent = '';
    var t = String(text == null ? '' : text);
    setTimeout(function () { liveEl.textContent = t; }, 30);
    if (t) { hintChip.hidden = false; hintChip.textContent = t; statusTimer = setTimeout(function () { hintChip.hidden = true; }, ms || 4000); }
    else hintChip.hidden = true;
  }
  function focusables(root) {
    return Array.prototype.filter.call(root.querySelectorAll('a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])'), function (n) {
      return !n.disabled && !n.hidden && n.getClientRects().length > 0;
    });
  }
  function card(opts) {
    opts = opts || {};
    getRoot();
    var tid = 'pb-rs-t' + (++cardUid);
    var hasTitle = opts.title != null && String(opts.title) !== '';
    var title = hasTitle ? h('h2', { id: tid, class: 'pb-rs-card-t', tabindex: '-1' }, String(opts.title)) : null;
    var bodyEl = h('div', { class: 'pb-rs-card-b' });
    if (opts.body instanceof Node) bodyEl.appendChild(opts.body);
    else if (opts.body != null) bodyEl.innerHTML = String(opts.body);
    var foot = h('div', { class: 'pb-rs-card-f' });
    var sec = h('section', { class: 'pb-rs-card', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': hasTitle ? tid : null, 'aria-label': hasTitle ? null : (opts.label || 'Questions'), tabindex: hasTitle ? null : '-1' },
      [hasTitle ? h('header', { class: 'pb-rs-card-h' }, title) : null, bodyEl, foot]);
    var host = fullOn ? fullIn : layerEl;
    var prev = document.activeElement;
    var btns = [];
    (opts.actions || []).forEach(function (a) {
      var kind = a.kind === 'primary' ? ' pb-rs-btn--solid' : a.kind === 'quiet' ? ' pb-rs-btn--quiet' : '';
      var b = h('button', { type: 'button', class: 'pb-rs-btn' + kind + (a.small ? ' pb-rs-btn--sm' : ''), id: a.id || null }, a.label == null ? '' : String(a.label));
      if (a.disabled) b.disabled = true;
      b.addEventListener('click', function (ev) { if (typeof a.onClick === 'function') a.onClick(ev, handle); });
      foot.appendChild(b); btns.push(b);
    });
    // only the newest card of a host shows
    Array.prototype.forEach.call(host.children, function (c) { c.hidden = true; });
    host.appendChild(sec);
    if (host === layerEl) layerEl.classList.add('is-on');
    sec.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab') return;
      var f = focusables(sec);
      if (!f.length) { e.preventDefault(); return; }
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === sec || document.activeElement === title)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
    var closed = false;
    var handle = {
      el: sec, body: bodyEl, buttons: btns,
      close: function () {
        if (closed) return; closed = true;
        var hostNow = sec.parentNode;
        if (hostNow) hostNow.removeChild(sec);
        if (hostNow) { var last = hostNow.lastElementChild; if (last) last.hidden = false; }
        if (layerEl && !layerEl.children.length) layerEl.classList.remove('is-on');
        if (prev && prev.focus && document.contains(prev) && !(rootEl && rootEl.contains(prev))) safe(function () { prev.focus({ preventScroll: true }); });
      },
      setBusy: function (on) { sec.setAttribute('aria-busy', on ? 'true' : 'false'); btns.forEach(function (b) { b.disabled = !!on; }); }
    };
    setTimeout(function () {
      if (closed) return;
      var target = null;
      if (opts.focus === 'first') target = sec.querySelector('input:not([type=hidden]),textarea,select,button.pb-rs-btn--solid');
      else if (typeof opts.focus === 'string' && opts.focus) target = sec.querySelector(opts.focus);
      if (!hasTitle && !target) target = sec.querySelector('input:not([type=hidden]),textarea,select,button');
      (target || title || sec).focus({ preventScroll: true });
    }, 0);
    return handle;
  }

  /* The task bar: a strip at the very top that takes its height from --pb-bar-h, so the prototype is laid out
     BELOW it and nothing the participant needs is covered. */
  var barObs = null;
  function setBarH() {
    var hgt = barEl && barEl.classList.contains('is-on') ? Math.ceil(barEl.getBoundingClientRect().height) : 0;
    var rs = document.documentElement.style;
    if (hgt) rs.setProperty('--pb-bar-h', hgt + 'px'); else rs.removeProperty('--pb-bar-h');
    safe(function () { window.dispatchEvent(new Event('resize')); });
  }
  function pill(opts) {
    opts = opts || {};
    getRoot();
    barEl.innerHTML = '';
    var txt = h('button', { type: 'button', class: 'pb-rs-bar-txt', 'aria-expanded': 'false', title: T.expand }, opts.text == null ? '' : String(opts.text));
    txt.addEventListener('click', function () {
      var open = txt.getAttribute('aria-expanded') !== 'true';
      txt.setAttribute('aria-expanded', open ? 'true' : 'false'); txt.title = open ? T.collapse : T.expand; setBarH();
    });
    var acts = h('div', { class: 'pb-rs-bar-a' });
    (opts.actions || []).forEach(function (a) {
      var b = h('button', { type: 'button', class: 'pb-rs-btn pb-rs-btn--sm' + (a.kind === 'primary' ? ' pb-rs-btn--solid' : ''), id: a.id || null }, String(a.label));
      b.addEventListener('click', function (ev) { if (typeof a.onClick === 'function') a.onClick(ev, handle); });
      acts.appendChild(b);
    });
    barEl.appendChild(h('span', { class: 'pb-rs-bar-n' }, opts.label == null ? '' : String(opts.label)));
    barEl.appendChild(txt);
    barEl.appendChild(acts);
    barEl.classList.add('is-on');
    try { if (typeof ResizeObserver === 'function') { if (barObs) barObs.disconnect(); barObs = new ResizeObserver(setBarH); barObs.observe(barEl); } } catch (e) { barObs = null; }
    setBarH();
    var handle = {
      el: barEl,
      close: function () {
        barEl.classList.remove('is-on'); barEl.innerHTML = '';
        if (barObs) { barObs.disconnect(); barObs = null; }
        setBarH();
      }
    };
    return handle;
  }
  function showRec(on, voice) {
    getRoot();
    recChip.hidden = !on;
    recChip.querySelector('.pb-rs-rec-t').textContent = voice ? T.recOnVoice : T.recOn;
  }

  /* ---- the question form (ask) ---- */
  function qType(q) {
    var t = q.type;
    if (t === 'single' || t === 'multi' || t === 'scale' || t === 'number' || t === 'text') return t;
    if (Array.isArray(q.options) && q.options.length) return 'single';
    if (isObj(q.scale)) return 'scale';
    return 'text';
  }
  function renderQuestion(q, qi, uid) {
    var type = qType(q), name = 'pb-rs-q' + uid + '-' + qi, req = q.required !== false;
    var fs = h('fieldset', { class: 'pb-rs-q', 'data-qi': qi });
    var lg = h('legend', { class: 'pb-rs-q-t' }, String(q.text == null ? '' : q.text));
    if (req) lg.appendChild(h('span', { class: 'pb-rs-req', 'aria-hidden': 'true' }, ' *'));
    fs.appendChild(lg);
    var i;
    if (type === 'single' || type === 'multi') {
      (Array.isArray(q.options) ? q.options : []).forEach(function (o, oi) {
        fs.appendChild(h('label', { class: 'pb-rs-opt' }, [h('input', { type: type === 'single' ? 'radio' : 'checkbox', name: name, value: oi }), h('span', { text: String(o) })]));
      });
    } else if (type === 'scale') {
      var sc = isObj(q.scale) ? q.scale : {}, lo = isFinite(sc.min) ? +sc.min : 1, hi = isFinite(sc.max) ? +sc.max : 5;
      if (hi < lo) hi = lo;
      var npts = Math.min(21, hi - lo + 1);
      var row = h('div', { class: 'pb-rs-scale' + (npts > 7 ? ' is-many' : ''), style: '--rs-n:' + npts, role: 'radiogroup', 'aria-label': String(q.text == null ? '' : q.text) });
      for (i = lo; i <= hi && i - lo < 21; i++) row.appendChild(h('label', { class: 'pb-rs-pt' }, [h('input', { type: 'radio', name: name, value: i }), h('span', { text: String(i) })]));
      fs.appendChild(row);
      if (sc.minLabel || sc.maxLabel) fs.appendChild(h('div', { class: 'pb-rs-scale-l' }, [h('span', { text: sc.minLabel || '' }), h('span', { text: sc.maxLabel || '' })]));
    } else if (type === 'number') {
      fs.appendChild(h('input', { type: 'number', class: 'pb-rs-in', name: name, inputmode: 'decimal', 'aria-label': String(q.text == null ? '' : q.text) }));
    } else {
      fs.appendChild(h('textarea', { class: 'pb-rs-in', name: name, rows: 3, maxlength: 1000, 'aria-label': String(q.text == null ? '' : q.text) }));
    }
    fs.appendChild(h('p', { class: 'pb-rs-err', role: 'alert', hidden: true }));
    return fs;
  }
  function readQuestion(q, fs) {
    var type = qType(q), req = q.required !== false, opts = Array.isArray(q.options) ? q.options : [], v;
    if (type === 'single') {
      v = fs.querySelector('input:checked');
      return v ? { has: true, value: String(opts[+v.value]) } : { has: false, missing: req };
    }
    if (type === 'multi') {
      var picked = Array.prototype.map.call(fs.querySelectorAll('input:checked'), function (c) { return String(opts[+c.value]); });
      return picked.length ? { has: true, value: picked } : { has: false, missing: req };
    }
    if (type === 'scale') {
      v = fs.querySelector('input:checked');
      return v ? { has: true, value: +v.value } : { has: false, missing: req };
    }
    if (type === 'number') {
      v = fs.querySelector('input');
      var n = v && v.value !== '' ? Number(v.value) : NaN;
      return isFinite(n) ? { has: true, value: n } : { has: false, missing: req };
    }
    v = fs.querySelector('textarea');
    var s = v ? v.value.trim() : '';
    return s ? { has: true, value: cut(s, 1000) } : { has: false, missing: req };
  }
  /* ask(questions, opts) -> Promise<answers>. opts: {title, submitLabel, task: <task id: store the answers on that
     task's row instead of session.answers>}. Emits one `answer` event per answered question. */
  function ask(questions, opts) {
    opts = opts || {};
    var qs = (Array.isArray(questions) ? questions : []).filter(function (q) { return isObj(q) && q.id != null; });
    if (!qs.length) return Promise.resolve({});
    return new Promise(function (resolve) {
      var uid = ++cardUid, form = h('form', { class: 'pb-rs-form', novalidate: true }), handle;
      qs.forEach(function (q, qi) { form.appendChild(renderQuestion(q, qi, uid)); });
      function submit(ev) {
        if (ev && ev.preventDefault) ev.preventDefault();
        var out = {}, bad = null;
        qs.forEach(function (q, qi) {
          var fs = form.querySelector('[data-qi="' + qi + '"]'), r = readQuestion(q, fs), err = fs.querySelector('.pb-rs-err');
          if (r.missing) { err.textContent = T.required; err.hidden = false; fs.classList.add('is-bad'); if (!bad) bad = fs; }
          else { err.hidden = true; fs.classList.remove('is-bad'); if (r.has) out[q.id] = r.value; }
        });
        if (bad) { status(T.fixAnswers); var f = bad.querySelector('input,textarea'); if (f) f.focus(); return; }
        var row = opts.task ? taskRow(opts.task) : null;
        Object.keys(out).forEach(function (qid) {
          if (row) row.answers[qid] = out[qid]; else session.answers[qid] = out[qid];
          var fields = { q: qid, value: out[qid] };
          if (opts.task) fields.task = opts.task;
          emit('answer', fields);
        });
        handle.close();
        resolve(out);
      }
      form.addEventListener('submit', submit);
      form.addEventListener('keydown', function (e) { if (e.key === 'Enter' && e.target && e.target.tagName === 'INPUT' && e.target.type !== 'radio' && e.target.type !== 'checkbox') submit(e); });
      handle = card({ title: opts.title != null ? opts.title : (opts.task ? T.aboutTask : ''), body: form, actions: [{ label: opts.submitLabel || T.next, kind: 'primary', onClick: function () { submit(); } }], focus: 'first' });
    });
  }

  var ui = { root: getRoot, card: card, full: setFull, status: status, pill: pill };

  /* ============================================================================================
     4 · the recorder (session pages only)
     ============================================================================================ */
  var lastScreen = null, pendingBack = false, lastDown = null, clickTrail = [], rage = null;
  var lastInput = null, lastScrollAt = 0, scrollTimer = 0, scrollPending = null, toastLog = [];
  var critTimer = 0, critActive = null, critInterval = 0;

  function recOn() { return active && !mute && started && !finished; }
  function inUi(n) { return !!(rootEl && n && rootEl.contains(n)); }
  function pickOrSpacing() {
    return !!(safe(function () { return window.pbPickOn; }, false) || safe(function () { return window.pbSpacingOn; }, false));
  }
  function clean(s) { return squash(s); }

  function pathOf(el) {
    var i = safe(function () { return window.pbInspectName(el); }, null);
    if (i && i.path) return String(i.path);
    var tag = (el.tagName || 'node').toLowerCase(), cls = el.classList && el.classList.length ? '.' + el.classList[0] : '';
    return 'screen:' + (curScreen() || '') + ' › ' + tag + cls;
  }
  function cmpOf(el) {
    var c = safe(function () { return window.pbInspectComponent(el); }, null);
    return c ? cut(c.name || c.id || '', 80) || null : null;
  }
  function fieldName(el) {
    var s = '';
    try { if (el.labels && el.labels.length) s = el.labels[0].textContent; } catch (e) { s = ''; }
    if (!clean(s)) { var f = el.closest && el.closest('.field'); var lb = f && f.querySelector('.field__label'); if (lb) s = lb.textContent; }
    if (!clean(s)) s = (el.getAttribute && (el.getAttribute('aria-label') || el.getAttribute('placeholder'))) || el.name || el.id || (el.tagName || '').toLowerCase();
    return cut(clean(s), 80);
  }
  function fieldNameOfWrap(field) {
    if (!field) return '';
    var lb = field.querySelector && field.querySelector('.field__label, label');
    var s = lb ? lb.textContent : '';
    if (!clean(s)) { var inp = field.querySelector('input,textarea,select'); s = inp ? (inp.name || inp.id || inp.getAttribute('aria-label') || '') : ''; }
    return cut(clean(s), 80);
  }

  function onPointerDown(e) { if (e.isTrusted) lastDown = { target: e.target, x: e.clientX, y: e.clientY }; }
  function onClick(e) {
    if (!recOn() || !e.isTrusted || pickOrSpacing()) return;
    var t = e.target;
    if (!(t instanceof Element) || inUi(t)) return;
    var box = protoBox();
    if (!box) return;
    if (!document.contains(t) && lastDown && lastDown.target && document.contains(lastDown.target)) t = lastDown.target;   // a mousedown handler re-rendered the target
    if (!box.contains(t)) return;
    var r = box.getBoundingClientRect(), cx = e.clientX, cy = e.clientY;
    if (e.detail === 0 && !cx && !cy) { var tr = t.getBoundingClientRect(); cx = tr.left + tr.width / 2; cy = tr.top + tr.height / 2; }   // a keyboard activation
    var x = r4(clamp((cx - r.left) / (r.width || 1), 0, 1)), y = r4(clamp((cy - r.top) / (r.height || 1), 0, 1));
    var a = t.closest(INTERACTIVE), interactive = !!(a && a !== box && box.contains(a));
    emit('click', { x: x, y: y, target: cut(pathOf(t), 200), cmp: cmpOf(t), interactive: interactive, dead: !interactive });
    // rage: >= 3 trusted clicks within 1000 ms and 30 px
    var nowMs = perfNow();
    clickTrail = clickTrail.filter(function (c) { return nowMs - c.at <= 1000; });
    clickTrail.push({ at: nowMs, x: e.clientX, y: e.clientY });
    var near = clickTrail.filter(function (c) { return Math.abs(c.x - e.clientX) <= 30 && Math.abs(c.y - e.clientY) <= 30; }).length;
    if (near >= 3) {
      if (rage && nowMs - rage.at <= 1000 && rage.ev && session.events.indexOf(rage.ev) >= 0) { rage.ev.count = near; rage.at = nowMs; }
      else { var ev = emit('rage', { x: x, y: y, count: near }); rage = { ev: ev, at: nowMs }; }
    } else rage = null;
    schedCriteria();
  }
  function textLike(el) {
    if (!el || !el.tagName) return false;
    if (el.tagName === 'TEXTAREA') return true;
    if (el.isContentEditable) return true;
    if (el.tagName !== 'INPUT') return false;
    return ['checkbox', 'radio', 'range', 'file', 'color', 'button', 'submit', 'reset', 'image', 'hidden'].indexOf((el.type || 'text').toLowerCase()) < 0;
  }
  function onInput(e) {
    if (!recOn() || !e.isTrusted) return;
    var el = e.target;
    if (!(el instanceof Element) || inUi(el) || !textLike(el)) return;
    var box = protoBox();
    if (!box || !box.contains(el)) return;
    var len = el.isContentEditable ? (el.textContent || '').length : String(el.value == null ? '' : el.value).length;   // the LENGTH; the value is never read into an event
    var tail = session.events[session.events.length - 1];
    if (lastInput && lastInput.el === el && lastInput.ev === tail && perfNow() - lastInput.at < 1500) { lastInput.ev.len = len; lastInput.at = perfNow(); }
    else { var ev = emit('input', { field: fieldName(el), len: len }); lastInput = { el: el, ev: ev, at: perfNow() }; }
    schedCriteria();
  }
  function onChange(e) {
    if (!recOn() || !e.isTrusted) return;
    var el = e.target;
    if (!(el instanceof Element) || inUi(el)) return;
    var box = protoBox();
    if (!box || !box.contains(el) || textLike(el)) { schedCriteria(); return; }
    var tag = el.tagName, len = 0;
    if (tag === 'INPUT' && (el.type === 'checkbox' || el.type === 'radio')) len = el.checked ? 1 : 0;
    else if (tag === 'SELECT') len = String(el.value == null ? '' : el.value).length;
    else if (tag === 'INPUT') len = String(el.value == null ? '' : el.value).length;
    else return;
    emit('input', { field: fieldName(el), len: len });
    schedCriteria();
  }
  function scrollY(el) {
    var max = (el.scrollHeight || 0) - (el.clientHeight || 0);
    return max > 0 ? r4(clamp((el.scrollTop || 0) / max, 0, 1)) : 0;
  }
  function emitScroll() { if (scrollPending && recOn()) { emit('scroll', { y: scrollPending.y }); lastScrollAt = perfNow(); } scrollPending = null; scrollTimer = 0; }
  function onScroll(e) {
    if (!recOn()) return;
    var el = e.target, box = protoBox();
    if (!box || !(el instanceof Element) || inUi(el) || !(el === box || box.contains(el))) return;
    scrollPending = { y: scrollY(el) };
    if (perfNow() - lastScrollAt >= 1000 && !scrollTimer) emitScroll();
    else if (!scrollTimer) scrollTimer = setTimeout(emitScroll, Math.max(0, 1000 - (perfNow() - lastScrollAt)));
  }
  function onVisibility() { if (active && started && !finished) emit('visibility', { hidden: !!document.hidden }); }
  var inErr = false;
  function onError(e) {
    if (!active || !started || finished || inErr) return;
    if (!e || (e.target && e.target !== window && !e.message)) return;   // a resource that failed to load is not a script error
    inErr = true;
    try { emit('error', { msg: cut(squash(e.message || (e.error && e.error.message) || 'error'), 200) }); } finally { inErr = false; }
  }
  function onRejection(e) {
    if (!active || !started || finished || inErr) return;
    inErr = true;
    try { var r = e && e.reason; emit('error', { msg: cut(squash(r && r.message ? r.message : String(r)), 200) }); } finally { inErr = false; }
  }

  function wrap(name, make) {
    var orig = window[name];
    if (typeof orig !== 'function' || orig.__pbRs) return;
    var w = make(orig);
    w.__pbRs = true; w.__pbRsOrig = orig;
    try { window[name] = w; } catch (e) { /* not writable: the events that depend on it are simply missing */ }
  }
  function checkScreen() {
    var cur = curScreen();
    if (cur !== lastScreen) {
      var from = lastScreen; lastScreen = cur;
      if (recOn()) emit('nav', { from: from, to: cur == null ? '' : cur, back: !!pendingBack });
      schedCriteria();
    }
  }
  function machineOf(x) {
    if (!x) return null;
    if (x.closest) return x.closest('[data-machine]');
    if (typeof x === 'string') return safe(function () { return document.querySelector('[data-machine="' + x.replace(/["\\]/g, '\\$&') + '"]'); }, null);
    return null;
  }
  var submitErrs = null;
  function installWrappers() {
    wrap('setProtoScreen', function (orig) {
      return function (id, fromBack) {
        pendingBack = !!fromBack;
        try { return orig.apply(this, arguments); } finally { checkScreen(); pendingBack = false; }
      };
    });
    wrap('renderPrototype', function (orig) {
      return function () { try { return orig.apply(this, arguments); } finally { checkScreen(); } };
    });
    wrap('pbProtoSubmit', function (orig) {
      return function (btn) {
        if (!recOn()) return orig.apply(this, arguments);
        var ev = push('submit', { ok: true, errors: 0 }), i = session.events.length - 1, outer = submitErrs;
        submitErrs = 0;
        try { return orig.apply(this, arguments); }
        finally {
          if (ev) { ev.errors = submitErrs; ev.ok = submitErrs === 0; announce(ev, i); }
          submitErrs = outer; schedCriteria();
        }
      };
    });
    wrap('pbFieldError', function (orig) {
      return function (field, msg) {
        if (msg && recOn()) {
          if (submitErrs != null) submitErrs++;
          emit('field-error', { field: fieldNameOfWrap(field), msg: cut(squash(msg), 200) });
          schedCriteria();
        }
        return orig.apply(this, arguments);
      };
    });
    wrap('pbToast', function (orig) {
      return function (msg) {
        if (recOn()) { toastLog.push(String(msg)); emit('toast', { msg: cut(squash(msg), 200) }); schedCriteria(); }
        return orig.apply(this, arguments);
      };
    });
    wrap('pbSetStep', function (orig) {
      return function (x, s) {
        var root = machineOf(x), prev = root ? root.getAttribute('data-step') : null;
        var r = orig.apply(this, arguments);
        if (recOn() && root && prev !== String(s)) {
          emit('step', { machine: cut(squash(root.getAttribute('data-machine') || root.id || 'machine'), 80) || 'machine', step: cut(squash(s), 80) });
          schedCriteria();
        }
        return r;
      };
    });
    window.addEventListener('pb:rolechange', function (e) { if (recOn()) emit('role', { role: e && e.detail && e.detail.role != null ? String(e.detail.role) : null }); });
    window.addEventListener('pb:reset', function () { if (recOn()) { emit('reset', {}); } });
  }
  /* The shell's single-key shortcuts (R resets the sandbox, S/I/M open tools) must not fire in a session: a
     participant who presses R would wipe the task. They already ignore typing in a field; we stop the rest. */
  function onKeyGuard(e) {
    var t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName || ''))) return;
    var k = String(e.key).toLowerCase(), plain = !e.ctrlKey && !e.metaKey && !e.altKey;
    if ((plain && (k === 'r' || k === 's' || k === 'i' || k === 'm')) || ((e.metaKey || e.ctrlKey) && k === 'k')) e.stopImmediatePropagation();
  }
  function installRecorder() {
    var cap = true;
    document.addEventListener('pointerdown', onPointerDown, cap);
    document.addEventListener('click', onClick, cap);
    document.addEventListener('input', onInput, cap);
    document.addEventListener('change', onChange, cap);
    document.addEventListener('scroll', onScroll, cap);
    document.addEventListener('visibilitychange', onVisibility, cap);
    document.addEventListener('keyup', function (e) { if (recOn() && e.isTrusted) schedCriteria(); }, cap);
    window.addEventListener('error', onError, cap);
    window.addEventListener('unhandledrejection', onRejection, cap);
    window.addEventListener('keydown', onKeyGuard, cap);
    installWrappers();
  }

  /* ---- the task's success criteria, polled after trusted actions (debounced 150 ms) ---- */
  function evalOwn(exp) {
    var box = protoBox();
    if (!isObj(exp) || !box) return false;
    if ('screen' in exp) return curScreen() === String(exp.screen);
    if ('text' in exp) return String(box.innerText || box.textContent || '').indexOf(String(exp.text)) >= 0;
    if ('toast' in exp) return toastLog.some(function (t) { return t.indexOf(String(exp.toast)) >= 0; });
    var k = 'present' in exp ? 'present' : ('absent' in exp ? 'absent' : null);
    if (k) {
      var n;
      try { n = box.querySelectorAll(String(exp[k])).length; } catch (e) { return false; }
      return k === 'present' ? n > 0 : n === 0;
    }
    return false;
  }
  function holds(exp) {
    if (isObj(exp) && 'toast' in exp) return evalOwn(exp);
    if (typeof window.pbRunExpect === 'function') {
      try { var r = window.pbRunExpect(exp); return !!r && r.status === 'pass'; } catch (e) { /* fall through to our own */ }
    }
    return evalOwn(exp);
  }
  function checkCriteria() {
    critTimer = 0;
    if (!curRow || curRow.criteriaT != null || !critActive || !critActive.length || !started) return;
    for (var i = 0; i < critActive.length; i++) if (!holds(critActive[i])) return;
    curRow.criteriaT = now();
    emit('criteria', { met: true });
  }
  function schedCriteria() {
    if (!critActive || !critActive.length) return;
    clearTimeout(critTimer);
    critTimer = setTimeout(checkCriteria, 150);
  }

  /* ============================================================================================
     5 · moving the prototype (quietly: none of this is a participant's action)
     ============================================================================================ */
  function quietly(fn) { mute++; try { fn(); } finally { mute--; } lastScreen = curScreen(); }
  function reset(spec) {
    spec = isObj(spec) ? spec : {};
    quietly(function () {
      if (typeof window.pbResetSandbox === 'function') window.pbResetSandbox();
      if (spec.entry && typeof window.pbApplyEntry === 'function') window.pbApplyEntry(String(spec.entry));
      if (spec.role && typeof window.setProtoRole === 'function') window.setProtoRole(String(spec.role));
      if (spec.screen && typeof window.setProtoScreen === 'function' && curScreen() !== String(spec.screen)) window.setProtoScreen(String(spec.screen));
    });
  }
  function ensureChrome() {
    var s = st();
    document.body.classList.add('pb-embed', 'pb-rs-on');
    document.documentElement.classList.add('pb-rs-page');
    if (!s) return;
    safe(function () { if (s.metaView !== 'prototype') window.setMetaView('prototype'); });
    s.protoDeviceB = null;
    safe(function () { if (window.pbPickOn) window.pbPickSet(false); });
    safe(function () { if (window.pbSpacingOn) window.pbSpacingSet(false); });
    safe(function () { window.pbSandboxClose(false); });
    var dev = INST.device;
    safe(function () {
      var ok = typeof dev === 'string' && dev && PROTO_DEVICES.some(function (d) { return d.id === dev; });
      var supported = ((window.PB_REGISTRY || PB_REGISTRY).meta || {}).devices;
      if (ok && (!Array.isArray(supported) || !supported.length || supported.indexOf(dev) >= 0)) window.setProtoDevice(dev);
      else window.renderPrototype();
    });
  }

  /* ============================================================================================
     6 · recording (opt-in; screen + voice -> one MediaRecorder)
     ============================================================================================ */
  var rec = { recorder: null, chunks: [], stream: null, startT: 0, startedAt: 0, on: false, voice: false, blob: null, stopP: null, mime: 'video/webm' };
  function canRecord() {
    return !!(navigator.mediaDevices && typeof navigator.mediaDevices.getDisplayMedia === 'function' && typeof window.MediaRecorder === 'function');
  }
  function pickMime() {
    var c = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];
    for (var i = 0; i < c.length; i++) if (safe(function () { return MediaRecorder.isTypeSupported(c[i]); }, false)) return c[i];
    return '';
  }
  function startRecording(wantVoice) {
    var md = navigator.mediaDevices, display, mic = null, voice = false;
    return md.getDisplayMedia({ video: true, audio: false, preferCurrentTab: true })
      .then(function (d) {
        display = d;
        if (!wantVoice) return null;
        return md.getUserMedia({ audio: true }).then(function (m) { mic = m; voice = true; }, function () { status(T.recVoiceFail, 7000); });
      })
      .then(function () {
        var tracks = display.getVideoTracks().concat(mic ? mic.getAudioTracks() : []);
        var stream = new MediaStream(tracks), mime = pickMime(), o = { videoBitsPerSecond: 1000000, audioBitsPerSecond: 64000 };
        if (mime) o.mimeType = mime;
        var r = new MediaRecorder(stream, o);
        rec.recorder = r; rec.stream = stream; rec.chunks = []; rec.voice = voice; rec.display = display; rec.mic = mic;
        r.ondataavailable = function (e) { if (e.data && e.data.size) rec.chunks.push(e.data); };
        return new Promise(function (resolve, reject) {
          r.onstart = function () {
            rec.on = true; rec.startT = now(); rec.startedAt = perfNow();
            emit('media-start', { kind: 'screen' });
            showRec(true, voice);
            resolve();
          };
          r.onerror = function (e) { reject((e && e.error) || new Error('recorder error')); };
          var vt = display.getVideoTracks()[0];
          if (vt) vt.addEventListener('ended', function () { if (rec.on) { status(T.recEnded, 8000); stopRecording(); } });
          r.start(5000);
        });
      })
      .catch(function (err) {
        [display, mic].forEach(function (s) { if (s) safe(function () { s.getTracks().forEach(function (t) { t.stop(); }); }); });
        throw err;
      });
  }
  function stopRecording() {
    if (rec.stopP) return rec.stopP;
    if (!rec.on || !rec.recorder) return Promise.resolve(null);
    rec.stopP = new Promise(function (resolve) {
      var r = rec.recorder;
      r.onstop = function () {
        rec.on = false;
        [rec.display, rec.mic].forEach(function (s) { if (s) safe(function () { s.getTracks().forEach(function (t) { t.stop(); }); }); });
        var dur = Math.max(0, Math.round(perfNow() - rec.startedAt));
        rec.blob = new Blob(rec.chunks, { type: 'video/webm' });
        rec.chunks = [];
        emit('media-stop', { kind: 'screen' });
        showRec(false);
        session.media.push({ kind: 'screen', mime: 'video/webm', startT: rec.startT, durationMs: dur, file: fileBase() + '-screen.webm' });
        resolve(rec.blob);
      };
      try { if (r.state !== 'inactive') r.stop(); else r.onstop(); } catch (e) { r.onstop(); }
    });
    return rec.stopP;
  }
  function fileBase() { return [fileSafe(session.study), fileSafe(session.participant || 'P00'), fileSafe(session.sessionId)].join('-'); }

  /* ============================================================================================
     7 · the flow: setup -> consent -> questions -> runner -> questions -> sink
     ============================================================================================ */
  function qsOf(sec) { return Array.isArray(sec.questions) ? sec.questions.filter(isObj) : []; }
  function groupsBefore() {
    var out = [];
    SECTIONS.forEach(function (sec, i) {
      if (sec.purpose === 'task') {
        var orphans = [];
        qsOf(sec).some(function (q) { if (isTaskQ(q)) return true; orphans.push(q); return false; });
        if (orphans.length) out.push({ title: sec.title, questions: orphans });
        return;
      }
      if (sec.purpose === 'screener' || sec.purpose === 'warmup' || (sec.purpose === 'main' && firstTaskSec >= 0 && i < firstTaskSec)) out.push({ title: sec.title, questions: qsOf(sec) });
    });
    return out;
  }
  function groupsAfter() {
    var out = [];
    SECTIONS.forEach(function (sec, i) {
      if (sec.purpose === 'task' || sec.purpose === 'screener' || sec.purpose === 'warmup') return;
      if (sec.purpose === 'main' && firstTaskSec >= 0 && i < firstTaskSec) return;
      out.push({ title: sec.title, questions: qsOf(sec) });
    });
    return out;
  }
  function askGroups(groups) {
    return groups.reduce(function (p, g) { return p.then(function () { return g.questions.length ? ask(g.questions, { title: g.title }) : null; }); }, Promise.resolve());
  }

  function stepSetup() {
    return new Promise(function (resolve) {
      var q = safe(function () { return new URLSearchParams(window.location.search); }, null);
      var pre = String(session.participant || (q && q.get('p')) || '').toUpperCase();
      var pilot = !!CFG.pilot || !!(q && /^(1|true|yes)$/i.test(q.get('pilot') || ''));
      var showPilot = PAGE === 'session' && session.mode === 'moderated';
      var body = h('div');
      if (INST.intro) body.appendChild(h('p', { class: 'pb-rs-lead', text: String(INST.intro) }));
      if (session.method === 'usability') {
        var ul = h('ul', { class: 'pb-rs-list' }, [h('li', { text: T.how1 }), h('li', { text: T.how2 })]);
        if (INST.thinkAloud) ul.appendChild(h('li', { text: T.thinkAloud }));
        body.appendChild(h('p', { class: 'pb-rs-lbl', text: T.howTitle })); body.appendChild(ul);
      }
      var inp = h('input', { id: 'pb-rs-pcode', class: 'pb-rs-in', type: 'text', value: pre, maxlength: 4, autocomplete: 'off', autocapitalize: 'characters', spellcheck: 'false', placeholder: 'P01', 'aria-describedby': 'pb-rs-pcode-h pb-rs-pcode-e' });
      var err = h('p', { id: 'pb-rs-pcode-e', class: 'pb-rs-err', role: 'alert', hidden: true, text: T.codeErr });
      body.appendChild(h('div', { class: 'pb-rs-fld' }, [h('label', { for: 'pb-rs-pcode', text: T.code }), inp, h('p', { id: 'pb-rs-pcode-h', class: 'pb-rs-hint', text: T.codeHint }), err]));
      var pilotBox = null;
      if (showPilot) {
        pilotBox = h('input', { id: 'pb-rs-pilot', type: 'checkbox' });
        pilotBox.checked = pilot;
        body.appendChild(h('label', { class: 'pb-rs-chk', for: 'pb-rs-pilot' }, [pilotBox, h('span', { text: T.pilot })]));
      }
      function go() {
        var code = inp.value.trim().toUpperCase();
        if (!/^P[0-9]{2,3}$/.test(code)) { inp.setAttribute('aria-invalid', 'true'); err.hidden = false; inp.focus(); return; }
        session.participant = code;
        session.pilot = pilotBox ? pilotBox.checked : pilot;
        c.close(); resolve(true);
      }
      inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); go(); } });
      inp.addEventListener('input', function () { inp.removeAttribute('aria-invalid'); err.hidden = true; });
      var c = card({ title: T.setupTitle, body: body, actions: [{ label: T.next, kind: 'primary', onClick: go }], focus: '#pb-rs-pcode' });
    });
  }

  function stepConsent() {
    return new Promise(function (resolve) {
      var text = INST.consent ? String(INST.consent) : T.consentDefault;
      var wantScreen = !!(INST.recording && INST.recording.screen), wantVoice = !!(INST.recording && INST.recording.voice);
      var can = wantScreen && canRecord();
      var body = h('div');
      body.appendChild(h('p', { class: 'pb-rs-text', text: text }));
      var agree = h('input', { id: 'pb-rs-agree', type: 'checkbox' });
      body.appendChild(h('label', { class: 'pb-rs-chk', for: 'pb-rs-agree' }, [agree, h('span', { text: T.agree })]));
      var recBox = null;
      if (can) {
        recBox = h('input', { id: 'pb-rs-rec', type: 'checkbox' });
        body.appendChild(h('label', { class: 'pb-rs-chk', for: 'pb-rs-rec' }, [recBox, h('span', { text: wantVoice ? T.recordScreenVoice : T.recordScreen })]));
        body.appendChild(h('p', { class: 'pb-rs-hint', text: T.recordNote }));
      } else if (wantScreen) body.appendChild(h('p', { class: 'pb-rs-hint', text: T.noRecord }));
      var err = h('p', { class: 'pb-rs-err', role: 'alert', hidden: true, text: T.mustAgree });
      body.appendChild(err);
      function yes() {
        if (!agree.checked) { err.hidden = false; agree.focus(); return; }
        c.close();
        resolve({ recording: !!(recBox && recBox.checked), voice: wantVoice, text: text });
      }
      function no() { c.close(); resolve(null); }
      var c = card({ title: T.consentTitle, body: body, actions: [{ label: T.decline, kind: 'quiet', onClick: no }, { label: T.next, kind: 'primary', onClick: yes }] });
    });
  }

  function stepRecording(want) {
    return new Promise(function (resolve) {
      function attempt() {
        startRecording(want.voice).then(resolve, function (err) {
          var why = err && err.name === 'NotAllowedError' ? 'Permission was not given.' : (err && err.message ? cut(String(err.message), 120) : '');
          var c = card({
            title: T.recFailTitle, body: '<p class="pb-rs-text">' + esc(T.recFail + (why ? ' (' + why + ')' : '') + '.') + '</p>',
            actions: [{ label: T.recSkip, kind: 'quiet', onClick: function () { c.close(); resolve(); } },
              { label: T.recRetry, kind: 'primary', onClick: function () { c.close(); attempt(); } }]
          });
        });
      }
      attempt();
    });
  }

  /* ---- usability runner ---- */
  function runUsabilityTask(q, idx, total) {
    return new Promise(function (resolve) {
      var T0 = isObj(q.task) ? q.task : {};
      var criteria = Array.isArray(T0.criteria) ? T0.criteria.filter(isObj) : [];
      var limitTimer = 0, bar = null, row = null, ended = false;
      var body = h('div');
      body.appendChild(h('p', { class: 'pb-rs-scn', text: String(q.text == null ? '' : q.text) }));
      if (INST.thinkAloud) body.appendChild(h('p', { class: 'pb-rs-note', text: T.reminder }));
      var c = card({ title: T.taskOf(idx + 1, total), body: body, actions: [{ label: T.start, kind: 'primary', onClick: begin }] });
      function begin() {
        c.close();
        reset(T0);
        row = task.begin(q);
        critActive = criteria;
        clearInterval(critInterval); critInterval = setInterval(function () { if (curRow && critActive && critActive.length) checkCriteria(); }, 1000);
        bar = pill({ label: T.taskOf(idx + 1, total), text: q.text, actions: [
          { label: T.done, kind: 'primary', id: 'pb-rs-done', onClick: function () { end('done'); } },
          { label: T.giveUp, id: 'pb-rs-giveup', onClick: function () { end('gave-up'); } }] });
        var limit = +T0.timeLimitSec;
        if (limit > 0) limitTimer = setTimeout(function () { end('timeout'); }, limit * 1000);
        schedCriteria();
      }
      function end(kind) {
        if (ended || !row) return;
        ended = true;
        clearTimeout(limitTimer); clearTimeout(critTimer); clearInterval(critInterval);
        checkCriteria();
        var met = row.criteriaT != null, outcome, source = 'self', extra = {};
        if (kind === 'gave-up') { outcome = 'abandoned'; extra.selfReport = 'gave-up'; }
        else if (kind === 'timeout') { outcome = met ? 'success' : 'timeout'; if (met) source = 'criteria'; }
        else {
          extra.selfReport = 'done';
          if (criteria.length) { outcome = met ? 'success' : 'fail'; source = 'criteria'; } else outcome = 'success';
        }
        task.end(outcome, source, extra);
        critActive = null;
        bar.close();
        var after = function () { return api.ask(api.postTask(q), { task: q.id, title: T.aboutTask }); };
        if (kind === 'timeout') {
          var n = card({ title: T.timeUp, body: '<p class="pb-rs-text">' + esc(T.timeUpBody) + '</p>', actions: [{ label: T.next, kind: 'primary', onClick: function () { n.close(); after().then(resolve); } }] });
        } else after().then(resolve);
      }
    });
  }
  var runners = {
    usability: {
      run: function (ctx) {
        var list = (ctx && ctx.tasks) || taskQs, total = list.length;
        return list.reduce(function (p, q, i) { return p.then(function () { return runUsabilityTask(q, i, total); }); }, Promise.resolve());
      }
    }
  };

  function ctxFor() {
    var list = taskQs.filter(function (q) { return q && q.id != null; });
    return { config: CFG, session: session, api: api, tasks: list, sections: SECTIONS.filter(function (s) { return s.purpose === 'task'; }), instrument: INST, mode: session.mode };
  }

  /* ---- finishing ---- */
  function download(blob, name) {
    var url = URL.createObjectURL(blob), a = h('a', { href: url, download: name, style: 'display:none' });
    document.body.appendChild(a); a.click();
    setTimeout(function () { if (a.parentNode) a.parentNode.removeChild(a); URL.revokeObjectURL(url); }, 15000);
  }
  function serialise() {
    var json = JSON.stringify(session);
    if (json.length > SESSION_MAX_BYTES) {          // drop the noisiest events first, never the facts
      session.events = session.events.filter(function (e) { return e.type !== 'scroll' && e.type !== 'visibility'; });
      json = JSON.stringify(session);
    }
    return json;
  }
  function readJson(res) {
    return res.text().then(function (t) {
      var d = null; try { d = JSON.parse(t); } catch (e) { d = null; }
      if (!res.ok || !d || d.ok === false) throw new Error((d && d.error) || ('HTTP ' + res.status));
      return d;
    });
  }
  function uploadMedia(blob, onProgress) {
    return new Promise(function (resolve, reject) {
      var x = new XMLHttpRequest(), url = CFG.post.media + '?session=' + encodeURIComponent(session.sessionId) + '&kind=screen';
      x.open('POST', url); x.setRequestHeader('Content-Type', 'video/webm');
      x.upload.onprogress = function (e) { if (e.lengthComputable && onProgress) onProgress(Math.round(100 * e.loaded / e.total)); };
      x.onload = function () {
        var d = null; try { d = JSON.parse(x.responseText); } catch (e) { d = null; }
        if (x.status >= 200 && x.status < 300 && d && d.ok !== false) resolve(d); else reject(new Error((d && d.error) || ('HTTP ' + x.status)));
      };
      x.onerror = function () { reject(new Error('network error')); };
      x.send(blob);
    });
  }

  function finish(recovered) {
    if (finished) return Promise.resolve();
    return stopRecording().then(function (blob) {
      if (!recovered) emit('session-end', {});     // a recovered file keeps no session-end: the validator then says it was cut short
      active = false;
      finished = true;
      session.endedAt = isoZ(epoch + now());
      session.durationMs = now();
      clearTimeout(persistTimer);
      window.removeEventListener('beforeunload', onUnload);
      if (droppedEvents) session.droppedEvents = droppedEvents;
      return showSink(blob);
    });
  }
  function showSink(blob) {
    var json = serialise(), jsonBlob = new Blob([json], { type: 'application/json' }), base = fileBase();
    ui.full(true);
    if (barEl) barEl.classList.remove('is-on');
    setBarH();
    var body = h('div');
    if (INST.closing) body.appendChild(h('p', { class: 'pb-rs-text', text: String(INST.closing) }));
    var sink = h('div', { class: 'pb-rs-sink' }), line = h('p', { class: 'pb-rs-sink-s', role: 'status', 'aria-live': 'polite' }), acts = h('div', { class: 'pb-rs-sink-a' });
    sink.appendChild(line); sink.appendChild(acts); body.appendChild(sink);
    var c = card({ title: T.doneTitle, body: body, actions: [] });
    function setLine(t, bad) { line.textContent = t; line.classList.toggle('is-err', !!bad); }
    function btn(label, kind, fn) { var b = h('button', { type: 'button', class: 'pb-rs-btn' + (kind === 'primary' ? ' pb-rs-btn--solid' : ''), text: label }); b.addEventListener('click', fn); acts.appendChild(b); return b; }
    function downloads() {
      acts.innerHTML = '';
      btn(T.dlSession + ' (' + base + '.pbsession.json)', 'primary', function () { download(jsonBlob, base + '.pbsession.json'); });
      if (blob && blob.size) btn(T.dlMedia + ' (' + base + '-screen.webm)', 'primary', function () { download(blob, base + '-screen.webm'); });
    }
    function viaDownload(note) {
      setLine((note ? note + ' ' : '') + T.dlHow);
      downloads();
      dropSnapshot();
    }
    if (session.env.sink !== 'server' || !CFG.post || !CFG.post.session) { viaDownload(''); return Promise.resolve(); }
    var saved = null, ok = false;
    function link(res) {
      var eid = res.pilot ? 'pilot-' + session.sessionId : res.evidence;
      if (!eid) return;
      acts.appendChild(h('a', { class: 'pb-rs-link', href: '/research/' + encodeURIComponent(session.study) + '/replay/' + encodeURIComponent(eid), target: '_blank', rel: 'noopener', text: T.replay }));
    }
    function attempt() {
      acts.innerHTML = '';
      ok = false;
      setLine(T.saving);
      var p = saved ? Promise.resolve(saved) : fetch(CFG.post.session, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin', body: json }).then(readJson);
      return p.then(function (res) {
        saved = res; ok = true;
        setLine(res.pilot ? T.savedPilot : T.savedAs(res.evidence || res.sessionId));
        dropSnapshot();
        if (blob && blob.size && session.consent && session.consent.recording && CFG.post.media) {
          setLine((res.pilot ? T.savedPilot : T.savedAs(res.evidence || res.sessionId)) + ' ' + T.uploading(0));
          return uploadMedia(blob, function (pc) { setLine((res.pilot ? T.savedPilot : T.savedAs(res.evidence || res.sessionId)) + ' ' + T.uploading(pc)); })
            .then(function () { setLine((res.pilot ? T.savedPilot : T.savedAs(res.evidence || res.sessionId)) + ' ' + T.uploaded); link(res); status(T.saved); });
        }
        link(res); status(T.saved);
      }).catch(function (err) {
        var msg = err && err.message ? err.message : 'unknown error';
        ok = false;
        setLine(saved ? T.mediaFail(msg) : T.saveFail(msg), true);
        acts.innerHTML = '';
        btn(T.retry, 'primary', attempt);
        btn(T.downloadInstead, '', function () { viaDownload(''); });
      });
    }
    // a copy is always one click away, whatever the server says
    return attempt().then(function () { if (ok) btn(T.downloadCopy, '', function () { download(jsonBlob, base + '.pbsession.json'); if (blob && blob.size) download(blob, base + '-screen.webm'); }); });
  }

  function onUnload(e) { if (active && !finished) { e.preventDefault(); e.returnValue = ''; return ''; } }

  /* ---- an interrupted session left in this tab's sessionStorage ---- */
  function readSnapshot() {
    var raw = null; try { raw = sessionStorage.getItem(SNAP_KEY); } catch (e) { raw = null; }
    if (!raw) return null;
    try {
      var d = JSON.parse(raw);
      if (d && d.session && d.session.consent && !d.session.endedAt && Date.now() - (d.savedAt || 0) < 12 * 3600 * 1000 && d.session.study === session.study) return d;
    } catch (e) { /* unreadable */ }
    dropSnapshot();
    return null;
  }
  function stepRecover() {
    var snap = readSnapshot();
    if (!snap) return Promise.resolve(false);
    return new Promise(function (resolve) {
      var c = card({
        title: T.interruptedTitle, body: '<p class="pb-rs-text">' + esc(T.interrupted) + '</p>',
        actions: [
          { label: T.startNew, kind: 'quiet', onClick: function () { dropSnapshot(); c.close(); resolve(false); } },
          { label: T.save, kind: 'primary', onClick: function () {
            c.close();
            Object.keys(session).forEach(function (k) { delete session[k]; });
            Object.keys(snap.session).forEach(function (k) { session[k] = snap.session[k]; });
            epoch = snap.epoch || Date.parse(session.startedAt) || Date.now();
            started = true; t0 = perfNow() - (session.events.length ? session.events[session.events.length - 1].t : 0); lastT = now();
            if (session.tasks.length && session.tasks[session.tasks.length - 1].endT == null) {
              var row = session.tasks[session.tasks.length - 1]; row.endT = lastT; row.outcome = 'abandoned'; row.outcomeSource = 'self';
            }
            curRow = null; active = true;
            finish(true); resolve(true);
          } }]
      });
    });
  }

  function run() {
    ensureChrome();
    getRoot();
    return stepRecover().then(function (recovered) {
      if (recovered) return null;
      ui.full(true);
      return stepSetup().then(function () {
        // the clock starts here
        t0 = perfNow(); epoch = Date.now(); started = true;
        session.startedAt = isoZ(epoch);
        session.env.viewport = [window.innerWidth || 0, window.innerHeight || 0];
        session.env.device = (st() && st().protoDevice) || INST.device || null;
        lastScreen = curScreen();
        emit('session-start', {});
        persist(true);
        return stepConsent();
      }).then(function (cons) {
        if (!cons) {
          started = false; session.events.length = 0;
          dropSnapshot();
          return card({ title: T.doneTitle, body: '<p class="pb-rs-text">' + esc(T.declined) + '</p>', actions: [] }) && null;
        }
        session.consent = { session: true, recording: cons.recording, at: isoZ(Date.now()), textSha256: sha256hex(cons.text) };
        active = true;
        window.addEventListener('beforeunload', onUnload);
        emit('consent', { recording: cons.recording });
        return (cons.recording ? stepRecording(cons) : Promise.resolve()).then(function () {
          return askGroups(groupsBefore());
        }).then(function () {
          ui.full(false);
          var runner = runners[session.method];
          if (!runner || typeof runner.run !== 'function') {
            return new Promise(function (resolve) {
              var c = card({ title: T.doneTitle, body: '<p class="pb-rs-text">' + esc(T.noRunner) + '</p>', actions: [{ label: T.next, kind: 'primary', onClick: function () { c.close(); resolve(); } }] });
            });
          }
          return Promise.resolve(runner.run(ctxFor()));
        }).then(function () {
          ui.full(true);
          return askGroups(groupsAfter());
        }).then(function () { return finish(); });
      });
    });
  }

  /* ============================================================================================
     8 · messages from the observer window, applied to the session as events
     ============================================================================================ */
  function lastRow() { return session.tasks.length ? session.tasks[session.tasks.length - 1] : null; }
  function onObserverMessage(m) {
    var d = m && m.data;
    if (!isObj(d)) return;
    if (d.kind === 'hello' && d.from === 'observer') {
      if (!started) return;
      var from = Math.max(0, session.events.length - 3000);
      for (var i = from; i < session.events.length; i++) post({ kind: 'event', event: session.events[i], i: i, sessionId: session.sessionId, participant: session.participant, pilot: session.pilot, epoch: epoch });
      return;
    }
    if (!started || finished || (d.sessionId && d.sessionId !== session.sessionId)) return;
    if (d.kind === 'note') {
      var text = cut(String(d.text == null ? '' : d.text).trim(), 1000);
      if (text) emit('note', { text: text, by: 'facilitator' });
    } else if (d.kind === 'assist') {
      var row = curRow || lastRow();
      if (row) { row.assisted = true; emit('assist', { task: row.id }); }
    } else if (d.kind === 'mark' && OUTCOMES.indexOf(d.outcome) >= 0) {
      if (curRow) { overrides[curRow.id] = d.outcome; emit('mark', { outcome: d.outcome }); }
      else { var lr = lastRow(); if (lr) { lr.outcome = d.outcome; lr.outcomeSource = 'facilitator'; emit('mark', { task: lr.id, outcome: d.outcome }); } }
    }
  }

  /* ============================================================================================
     9 · the observer page
     ============================================================================================ */
  function summarise(ev) {
    var f = function (k) { return ev[k] == null ? '' : String(ev[k]); };
    switch (ev.type) {
      case 'nav': return f('from') + ' → ' + f('to') + (ev.back ? ' (back)' : '');
      case 'click': return (ev.cmp ? ev.cmp + ' · ' : '') + f('target').replace(/^screen:[^›]*› ?/, '') + (ev.dead ? ' · dead click' : '');
      case 'rage': return 'rage click ×' + f('count');
      case 'input': return 'typed in ' + f('field') + ' (' + f('len') + ' characters)';
      case 'submit': return ev.ok ? 'submitted' : 'submitted with ' + f('errors') + ' error(s)';
      case 'field-error': return f('field') + ': ' + f('msg');
      case 'toast': return f('msg');
      case 'step': return f('machine') + ' → ' + f('step');
      case 'role': return f('role');
      case 'scroll': return 'scrolled to ' + Math.round((+ev.y || 0) * 100) + '%';
      case 'visibility': return ev.hidden ? 'tab hidden' : 'tab visible';
      case 'answer': return f('q') + ' = ' + (Array.isArray(ev.value) ? ev.value.join(', ') : f('value'));
      case 'note': return f('text');
      case 'task-start': return f('task');
      case 'task-end': return f('task') + ' · ' + f('outcome') + ' (' + f('source') + ')';
      case 'criteria': return 'criteria met';
      case 'mark': return f('task') + ' · ' + f('outcome');
      case 'assist': return f('task') + ' marked assisted';
      case 'consent': return ev.recording ? 'agreed, recording on' : 'agreed, no recording';
      case 'error': return f('msg');
      default: return '';
    }
  }
  function mmss(ms) { var s = Math.max(0, Math.floor(ms / 1000)); return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }
  function critText(c) {
    if (!isObj(c)) return '';
    if ('screen' in c) return 'on screen ' + c.screen;
    if ('text' in c) return 'screen shows "' + c.text + '"';
    if ('present' in c) return c.present + ' is present';
    if ('absent' in c) return c.absent + ' is absent';
    if ('toast' in c) return 'toast "' + c.toast + '"';
    return JSON.stringify(c);
  }

  function startObserver() {
    injectCss();
    document.documentElement.classList.add('pb-rs-observer');
    var tasks = taskQs.filter(function (q) { return q && q.id != null; });
    var root = h('div', { class: 'pb-rs pb-rs-ob' });
    root.innerHTML = [
      '<header class="pb-rs-ob-h"><h1>Observer</h1><p id="pb-rs-ob-conn" class="pb-rs-ob-conn" role="status" aria-live="polite">Waiting for a session. Open the participant page in another window.</p></header>',
      '<div class="pb-rs-ob-grid"><main>',
      '<section class="pb-rs-ob-sec" aria-labelledby="pb-rs-ob-now-h"><h2 id="pb-rs-ob-now-h">Now</h2><div id="pb-rs-ob-now"><p class="pb-rs-ob-meta">No task running.</p></div></section>',
      '<section class="pb-rs-ob-sec" aria-labelledby="pb-rs-ob-mark-h"><h2 id="pb-rs-ob-mark-h">Mark</h2>',
      '<div class="pb-rs-ob-row" role="group" aria-label="Mark the task"><button type="button" class="pb-rs-btn pb-rs-btn--sm" id="pb-rs-ob-assist" disabled>Assisted</button></div>',
      '<p class="pb-rs-ob-meta" id="pb-rs-ob-outl">Set the outcome (replaces what the participant or the criteria say)</p>',
      '<div class="pb-rs-ob-row" role="group" aria-labelledby="pb-rs-ob-outl" id="pb-rs-ob-outcomes"></div></section>',
      '<section class="pb-rs-ob-sec" aria-labelledby="pb-rs-ob-note-h"><h2 id="pb-rs-ob-note-h">Note</h2>',
      '<div class="pb-rs-fld"><label for="pb-rs-ob-note">Add a note to the session</label><textarea id="pb-rs-ob-note" class="pb-rs-in" rows="3" maxlength="1000" disabled></textarea></div>',
      '<div class="pb-rs-ob-row"><button type="button" class="pb-rs-btn pb-rs-btn--solid pb-rs-btn--sm" id="pb-rs-ob-send" disabled>Add note</button><span class="pb-rs-hint">Ctrl or Command + Enter also adds it.</span></div></section>',
      '<section class="pb-rs-ob-sec pb-rs-guide" aria-labelledby="pb-rs-ob-guide-h"><h2 id="pb-rs-ob-guide-h">Guide</h2><div id="pb-rs-ob-guide"></div></section>',
      '</main><aside class="pb-rs-ob-sec" aria-labelledby="pb-rs-ob-feed-h"><h2 id="pb-rs-ob-feed-h">Events</h2>',
      '<label class="pb-rs-chk"><input type="checkbox" id="pb-rs-ob-all"><span>Show scroll events</span></label><ol class="pb-rs-feed" id="pb-rs-ob-feed" aria-label="Event feed"></ol></aside></div>'
    ].join('');
    document.body.appendChild(root);
    var $ = function (id) { return document.getElementById(id); };
    var ob = { sessionId: null, participant: null, pilot: false, epoch: 0, events: [], cur: null, curStart: 0, ended: false, criteriaT: null, outcome: null, over: false, seen: {} };

    // the guide: every section's questions, each task with its success description, every probe
    var guide = '';
    SECTIONS.forEach(function (sec, si) {
      var items = qsOf(sec).map(function (q) {
        var probes = (MODERATOR.probes && MODERATOR.probes[q.id]) || [];
        var succ = MODERATOR.tasks && MODERATOR.tasks[q.id] && MODERATOR.tasks[q.id].success;
        var crit = isObj(q.task) && Array.isArray(q.task.criteria) ? q.task.criteria.map(critText).filter(Boolean) : [];
        return '<li data-q="' + esc(q.id) + '">' + esc(q.text) + (succ ? '<br><em>Success: ' + esc(succ) + '</em>' : '')
          + (crit.length ? '<br><em>Criteria: ' + esc(crit.join('; ')) + '</em>' : '')
          + (probes.length ? '<ul>' + probes.map(function (p) { return '<li>Probe: ' + esc(p) + '</li>'; }).join('') + '</ul>' : '') + '</li>';
      }).join('');
      guide += '<details data-sec="' + si + '"' + (sec.purpose === 'task' ? ' open' : '') + '><summary>' + esc(sec.title || sec.purpose || 'Section') + '</summary><ul>' + items + '</ul></details>';
    });
    $('pb-rs-ob-guide').innerHTML = guide || '<p class="pb-rs-ob-meta">No guide in this study.</p>';

    var outBox = $('pb-rs-ob-outcomes');
    MARKABLE.forEach(function (o) {
      var b = h('button', { type: 'button', class: 'pb-rs-btn pb-rs-btn--sm', 'data-outcome': o, disabled: true, text: o.charAt(0).toUpperCase() + o.slice(1) });
      b.addEventListener('click', function () { if (ob.sessionId) post({ kind: 'mark', outcome: o, sessionId: ob.sessionId }); });
      outBox.appendChild(b);
    });
    $('pb-rs-ob-assist').addEventListener('click', function () { if (ob.sessionId) post({ kind: 'assist', sessionId: ob.sessionId }); });
    function sendNote() {
      var ta = $('pb-rs-ob-note'), text = ta.value.trim();
      if (!text || !ob.sessionId) return;
      post({ kind: 'note', text: text, sessionId: ob.sessionId });
      ta.value = ''; ta.focus();
    }
    $('pb-rs-ob-send').addEventListener('click', sendNote);
    $('pb-rs-ob-note').addEventListener('keydown', function (e) { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); sendNote(); } });
    $('pb-rs-ob-all').addEventListener('change', drawFeed);

    function enable() {
      var on = !!ob.sessionId && !ob.over;
      ['pb-rs-ob-assist', 'pb-rs-ob-send', 'pb-rs-ob-note'].forEach(function (id) { $(id).disabled = !on; });
      Array.prototype.forEach.call(outBox.children, function (b) { b.disabled = !on; });
    }
    function drawConn() {
      var t;
      if (!ob.sessionId) t = 'Waiting for a session. Open the participant page in another window.';
      else t = (ob.pilot ? 'Practice run' : 'Session') + ' ' + (ob.participant || '') + ' · ' + ob.sessionId + (ob.over ? ' · ended' : ' · live');
      var el = $('pb-rs-ob-conn'); if (el.textContent !== t) el.textContent = t;
    }
    function drawNow() {
      var now_ = $('pb-rs-ob-now');
      if (!ob.cur) { now_.innerHTML = '<p class="pb-rs-ob-meta">' + (ob.over ? 'The session has ended.' : 'No task running.') + '</p>'; return; }
      var idx = tasks.findIndex(function (q) { return q.id === ob.cur; }), q = idx >= 0 ? tasks[idx] : null;
      var succ = MODERATOR.tasks && MODERATOR.tasks[ob.cur] && MODERATOR.tasks[ob.cur].success;
      var crit = q && isObj(q.task) && Array.isArray(q.task.criteria) ? q.task.criteria.map(critText).filter(Boolean) : [];
      var running = !ob.ended, el = running ? Date.now() - (ob.epoch + ob.curStart) : 0;
      var badge = running ? '<span class="pb-rs-badge pb-rs-badge--warn">running</span>' : '<span class="pb-rs-badge ' + (ob.outcome === 'success' ? 'pb-rs-badge--ok' : 'pb-rs-badge--bad') + '">' + esc(ob.outcome || 'ended') + '</span>';
      now_.innerHTML = '<div class="pb-rs-ob-row"><strong>' + esc(idx >= 0 ? T.taskOf(idx + 1, tasks.length) : ob.cur) + '</strong> ' + badge
        + (ob.criteriaT != null ? ' <span class="pb-rs-badge pb-rs-badge--ok">criteria met at ' + mmss(ob.criteriaT - ob.curStart) + '</span>' : '')
        + '</div>' + (running ? '<p class="pb-rs-ob-timer" id="pb-rs-ob-timer" aria-hidden="true">' + mmss(el) + '</p>' : '')
        + '<p class="pb-rs-ob-task">' + esc(q ? q.text : '') + '</p>'
        + (succ ? '<p class="pb-rs-ob-meta">Success: ' + esc(succ) + '</p>' : '')
        + (crit.length ? '<p class="pb-rs-ob-meta">Criteria: ' + esc(crit.join('; ')) + '</p>' : '');
      Array.prototype.forEach.call($('pb-rs-ob-guide').querySelectorAll('li[data-q]'), function (li) { li.classList.toggle('is-now', li.getAttribute('data-q') === ob.cur); });
    }
    function drawFeed() {
      var all = $('pb-rs-ob-all').checked, feed = $('pb-rs-ob-feed'), html = '', shown = 0;
      for (var i = ob.events.length - 1; i >= 0 && shown < 200; i--) {
        var ev = ob.events[i];
        if (!ev || (!all && ev.type === 'scroll')) continue;
        var cls = ev.type === 'rage' || ev.type === 'error' || ev.type === 'field-error' ? ' class="is-bad"' : (ev.type === 'click' && ev.dead ? ' class="is-warn"' : '');
        html += '<li' + cls + '><time>' + mmss(ev.t) + '</time><b>' + esc(ev.type) + '</b><span>' + esc(summarise(ev)) + '</span></li>';
        shown++;
      }
      feed.innerHTML = html;
    }
    function apply(env) {
      var ev = env.event;
      if (ob.sessionId !== env.sessionId) {
        ob = { sessionId: env.sessionId, participant: env.participant, pilot: !!env.pilot, epoch: env.epoch || Date.now(), events: [], cur: null, curStart: 0, ended: false, criteriaT: null, outcome: null, over: false, seen: {} };
      }
      if (env.participant && !ob.participant) ob.participant = env.participant;
      if (typeof env.i !== 'number' || ob.seen[env.i]) return;
      ob.seen[env.i] = 1; ob.events[env.i] = ev;
      var say = '';
      if (ev.type === 'task-start') { ob.cur = ev.task; ob.curStart = ev.t; ob.ended = false; ob.criteriaT = null; ob.outcome = null; say = 'Task started: ' + ev.task; }
      else if (ev.type === 'task-end') { ob.ended = true; ob.outcome = ev.outcome; say = 'Task ended: ' + ev.outcome; }
      else if (ev.type === 'criteria') { ob.criteriaT = ev.t; say = 'Criteria met'; }
      else if (ev.type === 'mark' && ev.task === ob.cur) { ob.outcome = ev.outcome; if (ob.ended) say = 'Outcome set to ' + ev.outcome; }
      else if (ev.type === 'rage') say = 'Rage click';
      else if (ev.type === 'session-end') { ob.over = true; ob.cur = null; say = 'Session ended'; }
      drawConn(); drawNow(); drawFeed(); enable();
      if (say) status(say);
    }
    if (channel) {
      channel.onmessage = function (m) {
        var d = m && m.data;
        if (!isObj(d)) return;
        if (d.kind === 'event' && isObj(d.event)) apply(d);
        else if (d.kind === 'hello' && d.from === 'session') post({ kind: 'hello', from: 'observer' });
      };
      post({ kind: 'hello', from: 'observer' });
    } else $('pb-rs-ob-conn').textContent = 'This browser cannot link the two windows (no BroadcastChannel).';
    setInterval(function () {
      var t = $('pb-rs-ob-timer');
      if (t && ob.cur && !ob.ended) t.textContent = mmss(Date.now() - (ob.epoch + ob.curStart));
    }, 500);
    getRoot();   // the live region
  }

  /* ============================================================================================
     10 · the public API, then the start
     ============================================================================================ */
  var api = window.pbRsSession = {
    config: CFG,
    session: session,
    now: now,
    emit: emit,
    task: task,
    ask: ask,
    ui: ui,
    runners: runners,
    postTask: postTask,
    esc: esc,
    // additions (not in §8.2): reset a task's start state quietly, and the pieces research-methods.js may reuse
    reset: reset,
    channel: channel,
    version: 1
  };

  if (PAGE !== 'observer') {
    installRecorder();
    if (channel) channel.onmessage = onObserverMessage;
    setTimeout(function () {
      injectCss();
      post({ kind: 'hello', from: 'session' });
      run().catch(function (err) {
        // the page must never be left blank: say so, and when the participant had consented, offer what was recorded
        status('Something went wrong: ' + (err && err.message ? err.message : 'unknown error'), 10000);
        if (session.consent && !finished) {
          if (curRow) task.end('abandoned', 'self');
          emit('error', { msg: cut(squash('runner failed: ' + (err && err.message ? err.message : 'unknown error')), 200) });
          finish().catch(function () { /* nothing more to try */ });
        }
      });
    }, 0);
  } else {
    setTimeout(startObserver, 0);
  }
})();
