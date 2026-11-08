/* research-replay.js — the session replay player (research UX extension, §8.4).
 *
 * Inlined before </body> of a rendered prototype page by the /research/<id>/replay/<eid> route, after
 * `window.PB_RS_REPLAY = {study, eid, session, media:[{eid,url,mime,startT?}], withheld:[eid…]}`
 * (`withheld`: this session's recordings a hand-off left out; absent or empty means none). It re-plays a recorded
 * `pb-session` on the prototype: the screens the participant visited, a dot for every click (a warning
 * colour for dead and rage clicks), small labels for errors, toasts, notes and typed input, and a
 * bottom timeline with task bands. When the session has a screen video, it plays in a draggable
 * picture-in-picture and is kept in step with the timeline.
 *
 * Time model. One number drives everything: T, ms since the session began (the `t` of every event).
 *   - Seeking to T resets to the session's first screen and applies every nav (and task-start and reset)
 *     event with t <= T, in one repaint with no animation, then draws the click dots from the last
 *     DOT_MS before T.
 *   - Playing advances T by real time x speed. If a video is loaded and playing inside its range, the
 *     video's own clock is the master (T = media.startT + currentTime*1000), so picture and sound never
 *     drift; outside that range, or while the video buffers, the wall clock drives and the video is
 *     nudged back in line when it is more than SYNC_SLACK_S away.
 *   - video time = (T - media.startT) / 1000.
 *
 * Plain ES2019 classic script. Inert without a document. No libraries, no network beyond a same-origin
 * fetch of the media url. Tool chrome only: `pb-rs-rp-*` classes, `--pb-*` tokens from chrome.css, its own
 * <style id="pb-rs-replay-css">, appended to <body>, never inside .pb-product. All text goes in through
 * textContent. Exposes window.pbRsReplay for tests and for the host page.
 */
(function () {
  'use strict';
  if (typeof document === 'undefined' || typeof window === 'undefined') return;
  var CFG = window.PB_RS_REPLAY;
  if (!CFG || typeof CFG !== 'object' || !CFG.session || typeof CFG.session !== 'object') return;
  if (window.pbRsReplay) return;

  var DOT_MS = 1500;          // a click dot stays this long before T
  var CAP_MS = 3500;          // a label (error, toast, input…) stays this long
  var NOTE_MS = 6000;         // a note stays longer
  var SYNC_SLACK_S = 0.3;     // video drift tolerated before it is re-seeked
  var STEP_MS = 5000;         // arrow keys
  var SPEEDS = [1, 2, 4];

  var S = CFG.session;
  var method = typeof S.method === 'string' ? S.method : 'usability';
  var conf = (S.config && typeof S.config === 'object') ? S.config : {};
  var cfgTasks = Array.isArray(conf.tasks) ? conf.tasks : [];
  var tasks = Array.isArray(S.tasks) ? S.tasks.filter(function (t) { return t && typeof t === 'object'; }) : [];
  var events = (Array.isArray(S.events) ? S.events : []).filter(function (e) {
    return e && typeof e === 'object' && typeof e.t === 'number' && isFinite(e.t) && typeof e.type === 'string';
  }).slice().sort(function (a, b) { return a.t - b.t; });

  var reduceMotion = false;
  try { reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { /* none */ }

  /* ---------------------------------------------------------------- small helpers */
  function num(v, d) { return typeof v === 'number' && isFinite(v) ? v : d; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function str(v) { return v == null ? '' : String(v); }
  function trunc(s, n) { s = str(s); return s.length > n ? s.slice(0, n - 1) + '…' : s; }
  function fmt(ms) {
    var s = Math.max(0, Math.round(ms / 1000));
    return Math.floor(s / 60) + ':' + (s % 60 < 10 ? '0' : '') + (s % 60);
  }
  function h(tag, cls, text, attrs) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    if (attrs) for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k) && attrs[k] != null) n.setAttribute(k, attrs[k]);
    return n;
  }
  function svg(path, label) {
    var s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('viewBox', '0 0 16 16'); s.setAttribute('width', '16'); s.setAttribute('height', '16');
    s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false');
    var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', path); p.setAttribute('fill', 'currentColor'); s.appendChild(p);
    return s;
  }
  var ICON_PLAY = 'M4 2.5v11l9.5-5.5z';
  var ICON_PAUSE = 'M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z';
  function byId(list, id) { for (var i = 0; i < list.length; i++) if (list[i] && list[i].id === id) return list[i]; return null; }
  function lowerBound(arr, t) {       // first index whose .t > t
    var lo = 0, hi = arr.length;
    while (lo < hi) { var mid = (lo + hi) >> 1; if (arr[mid].t <= t) lo = mid + 1; else hi = mid; }
    return lo;
  }

  /* ---------------------------------------------------------------- the session, indexed */
  var lastEventT = events.length ? events[events.length - 1].t : 0;
  var dur = Math.max(1000, num(S.durationMs, 0), lastEventT);
  tasks.forEach(function (t) { dur = Math.max(dur, num(t.endT, 0), num(t.startT, 0)); });

  var DOT_TYPES = { click: 1, rage: 1, 'fc-click': 1 };
  var dotEvents = events.filter(function (e) { return DOT_TYPES[e.type] && typeof e.x === 'number' && typeof e.y === 'number'; });
  var capEvents = events.filter(function (e) { return capText(e) != null; });
  var stepEvents = events.filter(function (e) { return e.type === 'step' && e.machine; });
  var roleEvents = events.filter(function (e) { return e.type === 'role' && e.role; });

  function firstScreenId() {
    for (var i = 0; i < events.length; i++) if (events[i].type === 'session-start' && events[i].screen) return events[i].screen;
    for (var j = 0; j < events.length; j++) if (events[j].type === 'nav' && events[j].from) return events[j].from;
    for (var k = 0; k < cfgTasks.length; k++) if (cfgTasks[k] && cfgTasks[k].task && cfgTasks[k].task.screen) return cfgTasks[k].task.screen;
    try {
      var sc = PB_DATA.handoff.screens; if (sc && sc.length) return sc[0].id;
    } catch (e) { /* none */ }
    return null;
  }
  var firstScreen = firstScreenId();
  // the screen after each event that moves it: nav → `to`, task-start → its screen, reset → the first screen
  var screenTimeline = [{ t: -1, screen: firstScreen }];
  events.forEach(function (e) {
    if (e.type === 'nav' && e.to) screenTimeline.push({ t: e.t, screen: e.to });
    else if (e.type === 'task-start' && e.screen) screenTimeline.push({ t: e.t, screen: e.screen });
    else if (e.type === 'reset') screenTimeline.push({ t: e.t, screen: firstScreen });
  });
  function screenEntryAt(T) { var i = lowerBound(screenTimeline, T) - 1; return screenTimeline[Math.max(0, i)]; }

  function activeTaskAt(T) {     // the task in progress, else the one most recently started, else the first
    var cur = null;
    for (var i = 0; i < tasks.length; i++) if (num(tasks[i].startT, Infinity) <= T) cur = tasks[i];
    return cur || tasks[0] || null;
  }
  function cfgTaskOf(id) { return byId(cfgTasks, id); }

  /* ---------------------------------------------------------------- describing events */
  function describe(e) {
    switch (e.type) {
      case 'nav': return (e.back ? 'Back to ' : 'Went to ') + str(e.to);
      case 'click': return 'Click' + (e.dead ? ' (dead)' : '') + (e.cmp ? ' on ' + trunc(e.cmp, 40) : (e.target ? ' on ' + trunc(e.target, 40) : ''));
      case 'rage': return 'Rage click x' + num(e.count, 3);
      case 'fc-click': return 'First click ' + (e.hit ? '(hit)' : '(miss)');
      case 'input': return 'Typed ' + num(e.len, 0) + ' character' + (num(e.len, 0) === 1 ? '' : 's') + (e.field ? ' in ' + trunc(e.field, 40) : '');
      case 'submit': return e.ok ? 'Submitted' : 'Submit failed' + (num(e.errors, 0) ? ' (' + num(e.errors, 0) + ' error' + (num(e.errors, 0) === 1 ? '' : 's') + ')' : '');
      case 'field-error': return 'Error' + (e.field ? ' in ' + trunc(e.field, 40) : '') + ': ' + trunc(e.msg, 120);
      case 'toast': return 'Toast: ' + trunc(e.msg, 120);
      case 'note': return 'Note: ' + trunc(e.text, 200);
      case 'error': return 'Page error: ' + trunc(e.msg, 120);
      case 'assist': return 'Marked as assisted';
      case 'mark': return 'Outcome set: ' + str(e.outcome);
      case 'criteria': return 'Success criteria met';
      case 'step': return 'Step: ' + trunc(e.machine, 30) + ' > ' + trunc(e.step, 30);
      case 'role': return 'Role: ' + str(e.role);
      case 'reset': return 'Session reset';
      case 'task-start': return 'Task ' + str(e.task) + ' started';
      case 'task-end': return 'Task ' + str(e.task) + ' ended' + (e.outcome ? ': ' + str(e.outcome) : '');
      case 'visibility': return e.hidden ? 'Tab hidden' : 'Tab visible';
      case 'tt-open': return 'Opened ' + str(e.node);
      case 'tt-choose': return 'Chose ' + str(e.node);
      case 'cs-group': return 'Group: ' + trunc(e.name, 60);
      case 'cs-move': return 'Moved ' + str(e.card);
      default: return null;
    }
  }
  function capText(e) {       // which events also appear as a small label while they are fresh
    switch (e.type) {
      case 'input': case 'field-error': case 'toast': case 'note': case 'error': case 'assist': case 'mark':
      case 'criteria': case 'role': case 'reset': case 'task-start': case 'task-end': return describe(e);
      case 'submit': return e.ok ? null : describe(e);
      case 'visibility': return e.hidden ? describe(e) : null;
      default: return null;
    }
  }
  function capClass(e) {
    if (e.type === 'field-error' || e.type === 'error' || (e.type === 'submit' && !e.ok)) return 'is-err';
    if (e.type === 'note' || e.type === 'assist' || e.type === 'mark') return 'is-note';
    if (e.type === 'criteria') return 'is-pass';
    return '';
  }

  /* ---------------------------------------------------------------- the styles */
  var CSS = [
    'html.pb-rs-replay{--pb-bar-h:0px;--pb-agent-h:0px}',
    'body.pb-rs-replay #meta-nav,body.pb-rs-replay #pb-agent,body.pb-rs-replay #pb-insp,body.pb-rs-replay .pb-cmdk-scrim,body.pb-rs-replay .pb-cmdk{display:none!important}',
    'body.pb-rs-replay .pb-page--viewport{height:calc(100vh - var(--pb-top) - var(--pb-rs-rp-h,7.5rem))!important;min-height:0!important}',
    'body.pb-rs-replay{padding-bottom:var(--pb-rs-rp-h,7.5rem)}',
    /* the bar */
    '.pb-rs-rp-bar{position:fixed;left:0;right:0;bottom:0;z-index:1500;background:var(--pb-surface);color:var(--pb-ink);border-top:var(--pb-hair-w) solid var(--pb-hair);font:var(--pb-w-reg) var(--pb-t-md)/var(--pb-lh) var(--pb-font);padding:var(--pb-s2) max(var(--pb-s4),env(safe-area-inset-right)) calc(var(--pb-s2) + env(safe-area-inset-bottom)) max(var(--pb-s4),env(safe-area-inset-left));display:flex;flex-direction:column;gap:var(--pb-s2);box-sizing:border-box;color-scheme:light dark}',
    '.pb-rs-rp-bar *{box-sizing:border-box}',
    '.pb-rs-rp-bar [hidden],.pb-rs-rp-pip [hidden]{display:none!important}',
    '.pb-rs-rp-row{display:flex;align-items:center;gap:var(--pb-s3);flex-wrap:wrap;min-width:0}',
    '.pb-rs-rp-title{flex:1 1 8rem;min-width:0;font-weight:var(--pb-w-bold);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '.pb-rs-rp-title span{font-weight:var(--pb-w-reg);color:var(--pb-ink-3)}',
    '.pb-rs-rp-btn{min-width:var(--pb-hit);height:var(--pb-hit);padding:0 var(--pb-s3);display:inline-flex;align-items:center;justify-content:center;gap:var(--pb-s1);background:var(--pb-surface);color:var(--pb-ink);border:var(--pb-hair-w) solid var(--pb-hair-2);border-radius:var(--pb-r-md);font:inherit;cursor:pointer}',
    '.pb-rs-rp-btn:hover{background:var(--pb-wash)}.pb-rs-rp-btn:active{background:var(--pb-press)}',
    '.pb-rs-rp-btn:focus-visible,.pb-rs-rp-track:focus-visible,.pb-rs-rp-pip-h:focus-visible{outline:var(--pb-rule-w) solid var(--pb-info);outline-offset:2px}',
    '.pb-rs-rp-btn[aria-pressed="true"]{background:var(--pb-ink);color:var(--pb-on-ink);border-color:var(--pb-ink)}',
    '.pb-rs-rp-play{background:var(--pb-ink);color:var(--pb-on-ink);border-color:var(--pb-ink);width:var(--pb-hit);padding:0}',
    '.pb-rs-rp-play:hover{background:var(--pb-ink-2)}',
    '.pb-rs-rp-seg{display:inline-flex}.pb-rs-rp-seg .pb-rs-rp-btn{border-radius:0;margin-left:-1px;padding:0 var(--pb-s2);min-width:2.25rem}',
    '.pb-rs-rp-seg .pb-rs-rp-btn:first-child{border-radius:var(--pb-r-md) 0 0 var(--pb-r-md);margin-left:0}.pb-rs-rp-seg .pb-rs-rp-btn:last-child{border-radius:0 var(--pb-r-md) var(--pb-r-md) 0}',
    '.pb-rs-rp-time{font:var(--pb-w-reg) var(--pb-t-md) var(--pb-mono);color:var(--pb-ink-2);white-space:nowrap}',
    '.pb-rs-rp-now{flex:1 1 10rem;min-width:0;color:var(--pb-ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    /* the timeline */
    '.pb-rs-rp-track{position:relative;height:3.25rem;background:var(--pb-wash);border-radius:var(--pb-r-md);overflow:hidden;cursor:pointer;touch-action:none;user-select:none;-webkit-user-select:none}',
    '.pb-rs-rp-band{position:absolute;top:0;height:1.25rem;min-width:2px;padding:0 var(--pb-s1);font-size:var(--pb-t-sm);line-height:1.25rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;background:var(--pb-press);color:var(--pb-ink);border-left:var(--pb-rule-w) solid var(--pb-ink-3);pointer-events:none}',
    '.pb-rs-rp-band.is-success{background:var(--pb-pass-bg);color:var(--pb-pass);border-left-color:var(--pb-pass)}',
    '.pb-rs-rp-band.is-bad{background:var(--pb-fail-bg);color:var(--pb-fail);border-left-color:var(--pb-fail)}',
    '.pb-rs-rp-band.is-skip{background:var(--pb-wash);color:var(--pb-ink-3)}',
    '.pb-rs-rp-lane{position:absolute;left:0;right:0;top:1.375rem;bottom:0;pointer-events:none}',
    '.pb-rs-rp-mk{position:absolute;transform:translateX(-50%)}',
    '.pb-rs-rp-mk--nav{bottom:0;width:2px;height:55%;background:var(--pb-ink-3)}',
    '.pb-rs-rp-mk--click{top:50%;width:.3125rem;height:.3125rem;margin-top:-.15rem;border-radius:50%;background:var(--pb-info)}',
    '.pb-rs-rp-mk--warn{top:50%;width:.5625rem;height:.5625rem;margin-top:-.28rem;border-radius:50%;background:var(--pb-warn);box-shadow:0 0 0 2px var(--pb-warn-bg)}',
    '.pb-rs-rp-mk--err,.pb-rs-rp-mk--note,.pb-rs-rp-mk--toast{top:0;bottom:0;width:2px}',
    '.pb-rs-rp-mk--err{background:var(--pb-fail)}.pb-rs-rp-mk--note{background:var(--pb-info)}.pb-rs-rp-mk--toast{background:var(--pb-ink-3);opacity:.6}',
    '.pb-rs-rp-mk--err::before,.pb-rs-rp-mk--note::before{content:"";position:absolute;top:0;left:0;width:.5rem;height:.4375rem;background:inherit}',
    '.pb-rs-rp-head{position:absolute;top:0;bottom:0;width:2px;margin-left:-1px;background:var(--pb-ink);pointer-events:none;z-index:2}',
    '.pb-rs-rp-head::before{content:"";position:absolute;top:0;left:-4px;width:10px;height:6px;background:var(--pb-ink);clip-path:polygon(0 0,100% 0,50% 100%)}',
    /* the overlay on the product */
    '.pb-rs-rp-box{position:fixed;z-index:1400;pointer-events:auto;color-scheme:light;cursor:default;font-family:var(--pb-font)}',
    '.pb-rs-rp-box[hidden]{display:none}',
    '.pb-rs-rp-rect{position:absolute;border:var(--pb-rule-w) dashed var(--pb-info);background:rgb(23 92 211/.08);pointer-events:none}',
    '.pb-rs-rp-dot{--c:var(--pb-info);position:absolute;width:1.125rem;height:1.125rem;border-radius:50%;border:var(--pb-rule-w) solid var(--c);background:color-mix(in srgb,var(--c) 30%,transparent);transform:translate(-50%,-50%);pointer-events:none;box-shadow:0 0 0 1px #fff}',
    '.pb-rs-rp-dot::after{content:"";position:absolute;inset:-2px;border-radius:50%;border:var(--pb-rule-w) solid var(--c);animation:pb-rs-rp-rip .7s ease-out 1 both}',
    '.pb-rs-rp-dot.is-warn{--c:var(--pb-warn);background:color-mix(in srgb,var(--c) 35%,transparent)}',
    '.pb-rs-rp-dot.is-rage{--c:var(--pb-fail);width:1.625rem;height:1.625rem}',
    '.pb-rs-rp-dot.is-hit{--c:var(--pb-pass)}.pb-rs-rp-dot.is-miss{--c:var(--pb-fail)}',
    '.pb-rs-rp-dot.is-held{box-shadow:0 0 0 1px #fff,0 0 0 4px color-mix(in srgb,var(--c) 25%,transparent)}',
    '.pb-rs-rp-dot i{position:absolute;left:calc(100% + .25rem);top:50%;transform:translateY(-50%);font:var(--pb-w-bold) var(--pb-t-sm)/1 var(--pb-font);font-style:normal;white-space:nowrap;background:var(--c);color:#fff;padding:.1875rem .375rem;border-radius:var(--pb-r)}',
    '@keyframes pb-rs-rp-rip{from{transform:scale(1);opacity:.9}to{transform:scale(2.6);opacity:0}}',
    '.pb-rs-rp-caps{position:fixed;z-index:1450;left:max(var(--pb-s3),env(safe-area-inset-left));bottom:calc(var(--pb-rs-rp-h,7.5rem) + var(--pb-s2));display:flex;flex-direction:column;align-items:flex-start;gap:var(--pb-s1);max-width:min(26rem,calc(100vw - 2*var(--pb-s3)));pointer-events:none}',
    '.pb-rs-rp-cap{background:var(--pb-ink);color:var(--pb-on-ink);padding:var(--pb-s1) var(--pb-s2);border-radius:var(--pb-r-md);font:var(--pb-w-reg) var(--pb-t-sm)/1.35 var(--pb-font);overflow-wrap:anywhere;box-shadow:var(--pb-shadow-sm);animation:pb-rs-rp-in .15s ease-out}',
    '.pb-rs-rp-cap.is-err{background:var(--pb-fail);color:#fff}.pb-rs-rp-cap.is-note{background:var(--pb-info);color:#fff}.pb-rs-rp-cap.is-pass{background:var(--pb-pass);color:#fff}',
    '@keyframes pb-rs-rp-in{from{opacity:0;transform:translateY(.25rem)}to{opacity:1;transform:none}}',
    /* picture-in-picture video */
    '.pb-rs-rp-pip{position:fixed;z-index:1600;right:var(--pb-s3);bottom:calc(var(--pb-rs-rp-h,7.5rem) + var(--pb-s3));width:min(15rem,42vw);background:var(--pb-surface);border:var(--pb-hair-w) solid var(--pb-hair-2);border-radius:var(--pb-r-lg);box-shadow:var(--pb-shadow);overflow:hidden}',
    '.pb-rs-rp-pip[hidden]{display:none}',
    '.pb-rs-rp-pip-h{display:flex;align-items:center;justify-content:space-between;gap:var(--pb-s2);padding:var(--pb-s1) var(--pb-s2);font-size:var(--pb-t-sm);color:var(--pb-ink-2);cursor:grab;touch-action:none;user-select:none;-webkit-user-select:none;background:var(--pb-wash)}',
    '.pb-rs-rp-pip video{display:block;width:100%;max-height:40vh;background:#000;object-fit:contain}',
    '.pb-rs-rp-pip-s{padding:var(--pb-s2);font-size:var(--pb-t-sm);color:var(--pb-ink-3)}',
    '.pb-rs-rp-note{flex:1 1 14rem;min-width:0;font-size:var(--pb-t-sm);color:var(--pb-ink-2);overflow-wrap:anywhere}',
    /* result views */
    '.pb-rs-rp-result{position:fixed;z-index:1300;left:0;right:0;top:0;bottom:var(--pb-rs-rp-h,7.5rem);overflow:auto;background:var(--pb-page);color:var(--pb-ink);font:var(--pb-w-reg) var(--pb-t-md)/var(--pb-lh) var(--pb-font);padding:var(--pb-s4) var(--pb-s4) var(--pb-s5)}',
    '.pb-rs-rp-result[hidden]{display:none}',
    '.pb-rs-rp-res-in{max-width:46rem;margin:0 auto}',
    '.pb-rs-rp-res-h{margin:0 0 var(--pb-s1);font-size:var(--pb-t-lg);line-height:var(--pb-lh-tight);font-weight:var(--pb-w-bold)}',
    '.pb-rs-rp-res-s{margin:0 0 var(--pb-s4);color:var(--pb-ink-3)}',
    '.pb-rs-rp-card{border:var(--pb-hair-w) solid var(--pb-hair);border-radius:var(--pb-r-lg);background:var(--pb-surface);padding:var(--pb-s3) var(--pb-s4);margin:0 0 var(--pb-s3)}',
    '.pb-rs-rp-card.is-active{border-color:var(--pb-ink);box-shadow:0 0 0 1px var(--pb-ink)}',
    '.pb-rs-rp-card h3{margin:0 0 var(--pb-s1);font-size:var(--pb-t-md);font-weight:var(--pb-w-bold)}',
    '.pb-rs-rp-card p{margin:0 0 var(--pb-s1)}',
    '.pb-rs-rp-path{display:flex;flex-wrap:wrap;align-items:center;gap:var(--pb-s1);list-style:none;margin:var(--pb-s1) 0;padding:0}',
    '.pb-rs-rp-node{background:var(--pb-wash);border-radius:var(--pb-r);padding:.125rem var(--pb-s2)}',
    '.pb-rs-rp-sep{color:var(--pb-ink-3)}',
    '.pb-rs-rp-node.is-chosen{background:var(--pb-ink);color:var(--pb-on-ink)}',
    '.pb-rs-rp-tag{display:inline-block;padding:.0625rem var(--pb-s2);border-radius:var(--pb-r-pill);font-size:var(--pb-t-sm);background:var(--pb-wash);color:var(--pb-ink-2)}',
    '.pb-rs-rp-tag.is-pass{background:var(--pb-pass-bg);color:var(--pb-pass)}.pb-rs-rp-tag.is-fail{background:var(--pb-fail-bg);color:var(--pb-fail)}',
    '.pb-rs-rp-trail{margin:var(--pb-s1) 0 0;color:var(--pb-ink-2);font-size:var(--pb-t-sm)}',
    '.pb-rs-rp-groups{display:grid;grid-template-columns:repeat(auto-fill,minmax(13rem,1fr));gap:var(--pb-s3)}',
    '.pb-rs-rp-groups .pb-rs-rp-card{margin:0}',
    '.pb-rs-rp-groups ul{margin:var(--pb-s1) 0 0;padding-left:var(--pb-s4)}',
    '.pb-rs-rp-fc{position:fixed;z-index:1450;top:var(--pb-s2);left:max(var(--pb-s2),env(safe-area-inset-left));max-width:min(18rem,calc(100vw - 2*var(--pb-s2)));background:var(--pb-surface);color:var(--pb-ink);border:var(--pb-hair-w) solid var(--pb-hair-2);border-radius:var(--pb-r-lg);box-shadow:var(--pb-shadow-sm);font:var(--pb-w-reg) var(--pb-t-sm)/1.4 var(--pb-font);color-scheme:light dark}',
    '.pb-rs-rp-fc summary{cursor:pointer;padding:var(--pb-s2) var(--pb-s3);font-weight:var(--pb-w-bold)}',
    '.pb-rs-rp-fc ul{list-style:none;margin:0;padding:0 var(--pb-s3) var(--pb-s2)}',
    '.pb-rs-rp-fc li button{all:unset;display:block;width:100%;box-sizing:border-box;cursor:pointer;padding:var(--pb-s1) 0;overflow-wrap:anywhere}',
    '.pb-rs-rp-fc li button:focus-visible{outline:var(--pb-rule-w) solid var(--pb-info)}',
    '.pb-rs-rp-fc li.is-active{font-weight:var(--pb-w-bold)}',
    '@media (max-width:30rem){.pb-rs-rp-bar{padding-left:var(--pb-s3);padding-right:var(--pb-s3);gap:var(--pb-s1)}.pb-rs-rp-row{gap:var(--pb-s2)}.pb-rs-rp-now{flex-basis:100%;order:5}.pb-rs-rp-result{padding:var(--pb-s3)}}',
    '@media (prefers-reduced-motion:reduce){.pb-rs-rp-dot::after{animation:none;opacity:0}.pb-rs-rp-cap{animation:none}}'
  ].join('\n');

  /* ---------------------------------------------------------------- the UI */
  var P = { t: 0, playing: false, speed: 1, last: 0, raf: 0, scrubbing: false };
  var UI = {};
  var dotEls = {}, capEls = {};
  var applied = { screen: null, role: null, steps: '' };
  var resultView = null;
  var video = null, vState = 'none', vStart = 0;   // none | loading | ready | error

  function ensureProto() {
    if (typeof state === 'undefined') return false;
    try {
      if (state.metaView !== 'prototype' || !document.querySelector('.proto-screen')) {
        state.metaView = 'prototype';
        if (typeof render === 'function') render();
      }
    } catch (e) { return false; }
    return true;
  }

  function prepShell() {
    document.body.classList.add('pb-rs-replay');
    document.documentElement.classList.add('pb-rs-replay');
    try { if (typeof pbPickSet === 'function') pbPickSet(false); } catch (e) { /* none */ }
    try { if (typeof pbSpacingSet === 'function') pbSpacingSet(false); } catch (e) { /* none */ }
    if (typeof state === 'undefined') return;
    try {
      state.protoDeviceB = null;
      var dev = S.env && S.env.device;
      if (dev && typeof pbNormalizeDeviceList === 'function') {
        var sup = pbNormalizeDeviceList(((PB_REGISTRY || {}).meta || {}).devices);
        if (sup.indexOf(dev) !== -1) state.protoDevice = dev;
      }
    } catch (e) { /* the project's default device stays */ }
  }

  function build() {
    var style = h('style'); style.id = 'pb-rs-replay-css'; style.textContent = CSS;
    document.body.appendChild(style);

    // the overlay that sits exactly on the .proto-screen box and holds the click dots
    UI.box = h('div', 'pb-rs-rp-box', null, { 'aria-hidden': 'true' });
    document.body.appendChild(UI.box);
    UI.caps = h('div', 'pb-rs-rp-caps', null, { 'aria-live': 'polite' });
    document.body.appendChild(UI.caps);

    var bar = h('div', 'pb-rs-rp-bar', null, { role: 'region', 'aria-label': 'Session replay controls' });
    UI.bar = bar;
    var r1 = h('div', 'pb-rs-rp-row');
    var title = h('div', 'pb-rs-rp-title');
    title.appendChild(document.createTextNode('Replay '));
    var meta = [S.participant, method, S.mode, S.pilot ? 'pilot' : null].filter(Boolean).join(' · ');
    title.appendChild(h('span', null, meta ? '· ' + meta : ''));
    r1.appendChild(title);
    UI.vbtn = h('button', 'pb-rs-rp-btn', 'Video', { type: 'button', 'aria-pressed': 'true' });
    UI.vbtn.hidden = true;
    UI.vbtn.addEventListener('click', function () { var on = UI.pip.hidden; UI.pip.hidden = !on; UI.vbtn.setAttribute('aria-pressed', String(on)); });
    r1.appendChild(UI.vbtn);
    UI.r1 = r1;
    bar.appendChild(r1);

    var r2 = h('div', 'pb-rs-rp-row');
    UI.play = h('button', 'pb-rs-rp-btn pb-rs-rp-play', null, { type: 'button', 'aria-label': 'Play', title: 'Play / pause (Space)' });
    UI.play.appendChild(svg(ICON_PLAY));
    UI.play.addEventListener('click', toggle);
    r2.appendChild(UI.play);
    var seg = h('div', 'pb-rs-rp-seg', null, { role: 'group', 'aria-label': 'Speed' });
    UI.speeds = SPEEDS.map(function (s) {
      var b = h('button', 'pb-rs-rp-btn', s + '×', { type: 'button', 'aria-pressed': String(s === P.speed), 'data-speed': s });
      b.addEventListener('click', function () { setSpeed(s); });
      seg.appendChild(b); return b;
    });
    r2.appendChild(seg);
    UI.time = h('span', 'pb-rs-rp-time', '0:00 / ' + fmt(dur));
    r2.appendChild(UI.time);
    UI.now = h('span', 'pb-rs-rp-now', '');
    r2.appendChild(UI.now);
    bar.appendChild(r2);

    var track = h('div', 'pb-rs-rp-track', null, {
      role: 'slider', tabindex: '0', 'aria-label': 'Session timeline', 'aria-valuemin': '0',
      'aria-valuemax': String(Math.round(dur / 1000)), 'aria-valuenow': '0', 'aria-valuetext': '0:00'
    });
    UI.track = track;
    buildTrack(track);
    UI.head = h('div', 'pb-rs-rp-head');
    track.appendChild(UI.head);
    bar.appendChild(track);
    document.body.appendChild(bar);

    var onDown = function (ev) {
      if (ev.button != null && ev.button > 0) return;
      P.scrubbing = true;
      try { track.setPointerCapture(ev.pointerId); } catch (e) { /* none */ }
      seekFromPointer(ev); track.focus({ preventScroll: true }); ev.preventDefault();
    };
    track.addEventListener('pointerdown', onDown);
    track.addEventListener('pointermove', function (ev) { if (P.scrubbing) seekFromPointer(ev); });
    var up = function () { P.scrubbing = false; };
    track.addEventListener('pointerup', up); track.addEventListener('pointercancel', up);

    if (typeof ResizeObserver === 'function') {
      new ResizeObserver(syncBarHeight).observe(bar);
    }
    syncBarHeight();
  }

  function syncBarHeight() {
    if (!UI.bar) return;
    document.documentElement.style.setProperty('--pb-rs-rp-h', UI.bar.offsetHeight + 'px');
    place();
  }

  function buildTrack(track) {
    tasks.forEach(function (t) {
      var s = clamp(num(t.startT, 0), 0, dur), e = clamp(num(t.endT, dur), s, dur);
      var o = String(t.outcome || '');
      var cls = 'pb-rs-rp-band' + (o === 'success' ? ' is-success' : (o === 'skipped' ? ' is-skip' : (o ? ' is-bad' : '')));
      var label = str(t.id) + (o ? ' · ' + o : '');
      var b = h('div', cls, label, { title: label + ' (' + fmt(s) + '–' + fmt(e) + ')' });
      b.style.left = (s / dur * 100) + '%'; b.style.width = Math.max(0, (e - s) / dur * 100) + '%';
      track.appendChild(b);
    });
    var lane = h('div', 'pb-rs-rp-lane');
    var seen = {};
    events.forEach(function (e) {
      var kind = null;
      if (e.type === 'nav') kind = 'nav';
      else if (e.type === 'click' || e.type === 'fc-click') kind = e.dead ? 'warn' : 'click';
      else if (e.type === 'rage') kind = 'warn';
      else if (e.type === 'field-error' || e.type === 'error' || (e.type === 'submit' && !e.ok)) kind = 'err';
      else if (e.type === 'note' || e.type === 'assist' || e.type === 'mark') kind = 'note';
      else if (e.type === 'toast') kind = 'toast';
      if (!kind) return;
      var key = kind + ':' + Math.round(e.t / dur * 400);     // at most 400 markers per kind
      if (seen[key]) { seen[key].n++; seen[key].el.title = seen[key].first + (seen[key].n > 1 ? ' (+' + (seen[key].n - 1) + ' more)' : ''); return; }
      var d = describe(e) || kind;
      var el = h('i', 'pb-rs-rp-mk pb-rs-rp-mk--' + kind, null, { title: fmt(e.t) + ' ' + d });
      el.style.left = clamp(e.t / dur * 100, 0, 100) + '%';
      lane.appendChild(el);
      seen[key] = { el: el, n: 1, first: fmt(e.t) + ' ' + d };
    });
    track.appendChild(lane);
  }

  function seekFromPointer(ev) {
    var r = UI.track.getBoundingClientRect();
    if (!r.width) return;
    seek(clamp((ev.clientX - r.left) / r.width, 0, 1) * dur);
  }

  /* ---------------------------------------------------------------- placing the overlay on .proto-screen */
  function place() {
    if (!UI.box) return;
    var ps = document.querySelector('.proto-screen');
    if (!ps || method === 'tree-test' || method === 'card-sort') { UI.box.hidden = true; return; }
    var r = ps.getBoundingClientRect();
    if (!r.width || !r.height) { UI.box.hidden = true; return; }
    UI.box.hidden = false;
    var st = UI.box.style;
    st.left = r.left + 'px'; st.top = r.top + 'px'; st.width = r.width + 'px'; st.height = r.height + 'px';
    if (typeof ResizeObserver === 'function' && UI.psObserved !== ps) {
      if (!UI.ro) UI.ro = new ResizeObserver(function () { place(); });
      else UI.ro.disconnect();
      UI.ro.observe(ps); UI.psObserved = ps;
    }
  }

  /* ---------------------------------------------------------------- applying time T */
  function roleAt(T) {
    var i = lowerBound(roleEvents, T) - 1;
    return i >= 0 ? roleEvents[i].role : null;
  }

  function stepsAt(T, since) {
    var map = {};
    for (var i = 0; i < stepEvents.length && stepEvents[i].t <= T; i++) if (stepEvents[i].t >= since) map[stepEvents[i].machine] = stepEvents[i].step;
    return map;
  }

  function wantedScreen(T) {
    var sc = screenEntryAt(T).screen;
    if (method === 'first-click') {
      var at = activeTaskAt(T), ct = at && cfgTaskOf(at.id);
      if (ct && ct.click && ct.click.screen) sc = ct.click.screen;
    }
    return sc;
  }

  function applyProduct(T) {
    if (typeof state === 'undefined' || method === 'tree-test' || method === 'card-sort') return;
    if (!ensureProto()) return;
    var sc = wantedScreen(T), role = roleAt(T), force = false;
    if (role != null && role !== applied.role) {
      applied.role = role;
      try { state.activeRole = role; force = true; } catch (e) { /* none */ }
    }
    var changed = false;
    if (sc && (state.protoScreenId !== sc)) {
      state.protoHistory = []; state.protoCtxStack = [];
      try { setProtoScreen(sc); changed = true; } catch (e) { /* an unknown screen stays where it was */ }
      if (changed && state.protoScreenId !== sc) changed = inferRole(sc) || changed;
    } else if (force && typeof renderPrototype === 'function') {
      try { renderPrototype(); changed = true; } catch (e) { /* none */ }
    }
    if (changed) applied.steps = '\u0000';
    var steps = stepsAt(T, screenEntryAt(T).t);
    var sig = JSON.stringify(steps);
    if (sig !== applied.steps && typeof pbSetStep === 'function') {
      applied.steps = sig;
      for (var m in steps) if (Object.prototype.hasOwnProperty.call(steps, m)) { try { pbSetStep(m, steps[m]); } catch (e) { /* none */ } }
    }
    applied.screen = state.protoScreenId;
  }

  /* The shell sends a role that may not see a screen to the first one it can see. The participant did see
     this screen, so when no `role` event says which role it was, take the first declared role that may. */
  function inferRole(sc) {
    try {
      var scr = byId((PB_DATA.handoff && PB_DATA.handoff.screens) || [], sc);
      var roles = ((PB_REGISTRY || {}).meta || {}).roles || [];
      if (!scr || typeof pbScreenAllowsRole !== 'function') return false;
      for (var i = 0; i < roles.length; i++) {
        if (pbScreenAllowsRole(scr, roles[i].id)) {
          state.activeRole = roles[i].id; applied.role = roles[i].id;
          state.protoHistory = []; state.protoCtxStack = [];
          setProtoScreen(sc);
          return state.protoScreenId === sc;
        }
      }
    } catch (e) { /* the shell's own fallback screen stays */ }
    return false;
  }

  function dotClass(e) {
    if (e.type === 'rage') return 'pb-rs-rp-dot is-rage';
    if (e.type === 'fc-click') return 'pb-rs-rp-dot ' + (e.hit ? 'is-hit' : 'is-miss');
    return 'pb-rs-rp-dot' + (e.dead ? ' is-warn' : '');
  }
  function dotLabel(e) { return e.type === 'rage' ? 'Rage ×' + num(e.count, 3) : (e.dead ? 'Dead click' : null); }

  function mkDot(e, held) {
    var d = h('div', dotClass(e) + (held ? ' is-held' : ''), null, { title: describe(e) || '' });
    d.style.left = clamp(e.x, 0, 1) * 100 + '%'; d.style.top = clamp(e.y, 0, 1) * 100 + '%';
    var lb = dotLabel(e);
    if (lb) d.appendChild(h('i', null, lb));
    return d;
  }

  function syncDots(T) {
    if (!UI.box) return;
    var want = {}, i, e;
    var hi = lowerBound(dotEvents, T);
    for (i = hi - 1; i >= 0; i--) {
      e = dotEvents[i];
      if (T - e.t > DOT_MS) break;
      want[i] = e;
    }
    // first-click: the choice made for the task on show stays on the screen once it is made
    var held = {};
    if (method === 'first-click') {
      var at = activeTaskAt(T);
      if (at) for (i = 0; i < hi; i++) if (dotEvents[i].type === 'fc-click' && dotEvents[i].task === at.id) { held[i] = dotEvents[i]; want[i] = dotEvents[i]; }
      if (at && !Object.keys(held).length) {
        var res = S.result && S.result['first-click'] && S.result['first-click'][at.id];
        if (res && typeof res.x === 'number' && T >= num(at.endT, 0)) {      // no event recorded: show the stored point once the task is over
          held.res = { type: 'fc-click', x: res.x, y: res.y, hit: !!res.hit }; want.res = held.res;
        }
      }
    }
    var k;
    for (k in dotEls) if (!want[k] || dotEls[k].held !== !!held[k]) { if (dotEls[k].el.parentNode) dotEls[k].el.parentNode.removeChild(dotEls[k].el); delete dotEls[k]; }
    for (k in want) {
      if (!dotEls[k]) { dotEls[k] = { el: mkDot(want[k], !!held[k]), held: !!held[k] }; UI.box.appendChild(dotEls[k].el); }
      dotEls[k].el.style.opacity = held[k] ? '1' : String(Math.max(0.25, 1 - Math.max(0, T - want[k].t) / DOT_MS * 0.75));
    }
    syncRect(T);
  }

  function syncRect(T) {
    if (!UI.box) return;
    var rect = null;
    if (method === 'first-click') {
      var at = activeTaskAt(T), ct = at && cfgTaskOf(at.id);
      if (ct && ct.click && ct.click.rect) rect = ct.click.rect;
    }
    var key = rect ? [rect.x, rect.y, rect.w, rect.h].join(',') : '';
    if (UI.rectKey === key) return;
    UI.rectKey = key;
    if (UI.rectEl && UI.rectEl.parentNode) UI.rectEl.parentNode.removeChild(UI.rectEl);
    UI.rectEl = null;
    if (rect) {
      var r = h('div', 'pb-rs-rp-rect', null, { title: 'Target area' });
      r.style.left = num(rect.x, 0) * 100 + '%'; r.style.top = num(rect.y, 0) * 100 + '%';
      r.style.width = num(rect.w, 0) * 100 + '%'; r.style.height = num(rect.h, 0) * 100 + '%';
      UI.box.insertBefore(r, UI.box.firstChild); UI.rectEl = r;
    }
  }

  function syncCaps(T) {
    var want = {}, shown = 0, i;
    var hi = lowerBound(capEvents, T);
    for (i = hi - 1; i >= 0 && shown < 4; i--) {
      var e = capEvents[i], life = e.type === 'note' ? NOTE_MS : CAP_MS;
      if (T - e.t > life) { if (e.type === 'note' || T - e.t > NOTE_MS) break; else continue; }
      want[i] = e; shown++;
    }
    var k;
    for (k in capEls) if (!want[k]) { if (capEls[k].parentNode) capEls[k].parentNode.removeChild(capEls[k]); delete capEls[k]; }
    var order = Object.keys(want).map(Number).sort(function (a, b) { return a - b; });
    order.forEach(function (idx) {
      if (!capEls[idx]) {
        var c = h('div', 'pb-rs-rp-cap ' + capClass(want[idx]), capText(want[idx]));
        capEls[idx] = c; UI.caps.appendChild(c);
      }
    });
  }

  var lastSecond = -1;
  function syncBar(T) {
    UI.head.style.left = (T / dur * 100) + '%';
    var sec = Math.floor(T / 1000);
    if (sec !== lastSecond || !P.playing) {
      lastSecond = sec;
      UI.time.textContent = fmt(T) + ' / ' + fmt(dur);
      UI.track.setAttribute('aria-valuenow', String(sec));
      var at = activeTaskAt(T), sc = (typeof state !== 'undefined' && state.protoScreenId) || screenEntryAt(T).screen;
      var ct = at && cfgTaskOf(at.id);
      var now = at ? ('Task ' + str(at.id) + (ct && ct.text ? ': ' + trunc(ct.text, 70) : '')) : '';
      if (method === 'usability' || method === 'first-click') now += (now ? ' · ' : '') + 'screen ' + str(sc);
      UI.now.textContent = now; UI.now.title = now;
      UI.track.setAttribute('aria-valuetext', fmt(T) + ' of ' + fmt(dur) + (at ? ', task ' + str(at.id) : ''));
    }
  }

  function apply(T) {
    applyProduct(T);
    place();
    syncDots(T);
    syncCaps(T);
    if (resultView) resultView.update(T);
    syncBar(T);
  }

  /* ---------------------------------------------------------------- transport */
  function setPlayIcon() {
    UI.play.textContent = '';
    UI.play.appendChild(svg(P.playing ? ICON_PAUSE : ICON_PLAY));
    UI.play.setAttribute('aria-label', P.playing ? 'Pause' : 'Play');
  }
  function seek(t) {
    P.t = clamp(num(t, 0), 0, dur);
    apply(P.t);
    syncVideo(true);
    P.last = performance.now();
  }
  function play() {
    if (P.playing) return;
    if (P.t >= dur) P.t = 0;
    P.playing = true; P.last = performance.now(); setPlayIcon();
    P.raf = requestAnimationFrame(tick);
    syncVideo(true);
  }
  function pause() {
    if (!P.playing) return;
    P.playing = false; setPlayIcon();
    if (P.raf) cancelAnimationFrame(P.raf); P.raf = 0;
    if (video) { try { video.pause(); } catch (e) { /* none */ } }
  }
  function toggle() { if (P.playing) pause(); else play(); }
  function setSpeed(s) {
    if (SPEEDS.indexOf(s) === -1) return;
    P.speed = s;
    UI.speeds.forEach(function (b) { b.setAttribute('aria-pressed', String(Number(b.getAttribute('data-speed')) === s)); });
    if (video) { try { video.playbackRate = s; } catch (e) { /* none */ } }
  }
  function tick(now) {
    if (!P.playing) return;
    var vt = videoRange(P.t);
    if (video && vt != null && !video.paused && !video.seeking && video.readyState >= 2) {
      P.t = vStart + video.currentTime * 1000;          // the video is the master clock while it plays
    } else {
      P.t += (now - P.last) * P.speed;
    }
    P.last = now;
    if (P.t >= dur) {
      P.t = dur; apply(P.t); pause(); return;
    }
    apply(P.t);
    syncVideo(false);
    P.raf = requestAnimationFrame(tick);
  }

  /* ---------------------------------------------------------------- the video */
  function vdur() {
    if (!video) return 0;
    if (isFinite(video.duration) && video.duration > 0) return video.duration;
    var m = S.media && S.media[0];
    return m && num(m.durationMs, 0) ? m.durationMs / 1000 : 0;
  }
  function videoRange(T) {            // video time for timeline T, or null when T is outside the picture
    if (!video || vState !== 'ready') return null;
    var vt = (T - vStart) / 1000;
    return vt >= 0 && vt <= vdur() ? vt : null;
  }
  function syncVideo(hard) {
    if (!video || vState !== 'ready') return;
    var vt = videoRange(P.t);
    try {
      if (vt == null) {                                       // before the recording began, or after it ended
        if (!video.paused) video.pause();
        var edge = clamp((P.t - vStart) / 1000, 0, vdur());
        if (hard || Math.abs(video.currentTime - edge) > 0.05) video.currentTime = edge;
        return;
      }
      if (hard || Math.abs(video.currentTime - vt) > SYNC_SLACK_S) video.currentTime = vt;
      if (video.playbackRate !== P.speed) video.playbackRate = P.speed;
      if (P.playing && video.paused) {
        var p = video.play();
        if (p && p.catch) p.catch(function () { video.muted = true; video.play().catch(function () { /* the clock carries on alone */ }); });
      } else if (!P.playing && !video.paused) video.pause();
    } catch (e) { /* the timeline does not depend on the picture */ }
  }

  function fixDuration(v, done) {
    var finished = false;
    function fin() { if (finished) return; finished = true; try { v.currentTime = 0; } catch (e) { /* none */ } done(); }
    function ok() { return isFinite(v.duration) && v.duration > 0; }
    function onMeta() {
      if (ok()) { fin(); return; }
      var dc = function () { if (ok()) { v.removeEventListener('durationchange', dc); fin(); } };
      v.addEventListener('durationchange', dc);
      try { v.currentTime = 1e101; } catch (e) { fin(); }       // MediaRecorder's WebM has no duration: seeking to the end makes the browser find it
      setTimeout(fin, 5000);
    }
    if (v.readyState >= 1) onMeta(); else v.addEventListener('loadedmetadata', onMeta, { once: true });
  }

  function loadVideo() {
    var list = Array.isArray(CFG.media) ? CFG.media : [];
    var m = null;
    for (var i = 0; i < list.length; i++) if (list[i] && list[i].url && (!list[i].mime || /^video\//.test(list[i].mime))) { m = list[i]; break; }
    if (!m) {
      /* The hand-off left the recording out on purpose: say so once, in plain text, in the bar. The timeline and events play on without it. */
      if (Array.isArray(CFG.withheld) && CFG.withheld.length && UI.r1) {
        UI.r1.insertBefore(h('span', 'pb-rs-rp-note', 'The screen recording was left out of this hand-off.', { role: 'note' }), UI.vbtn);
        syncBarHeight();
      }
      return;
    }
    var sm = Array.isArray(S.media) ? S.media[0] : null;
    vStart = num(m.startT, sm ? num(sm.startT, 0) : 0);
    vState = 'loading';
    var pip = h('div', 'pb-rs-rp-pip', null, { role: 'group', 'aria-label': 'Screen recording' });
    var hd = h('div', 'pb-rs-rp-pip-h', 'Screen recording', { tabindex: '0', title: 'Drag to move (arrow keys when focused)' });
    var hide = h('button', 'pb-rs-rp-btn', 'Hide', { type: 'button', 'aria-label': 'Hide video' });
    hide.style.height = '1.5rem'; hide.style.minWidth = '0'; hide.style.padding = '0 .5rem';
    hide.addEventListener('click', function () { pip.hidden = true; UI.vbtn.setAttribute('aria-pressed', 'false'); });
    hide.addEventListener('pointerdown', function (ev) { ev.stopPropagation(); });
    hd.appendChild(hide);
    var status = h('div', 'pb-rs-rp-pip-s', 'Loading video…');
    pip.appendChild(hd); pip.appendChild(status);
    document.body.appendChild(pip);
    UI.pip = pip; UI.vbtn.hidden = false;
    dragify(pip, hd);

    fetch(m.url).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.blob();
    }).then(function (blob) {
      if (!blob.type && m.mime) blob = new Blob([blob], { type: m.mime });
      var v = document.createElement('video');
      v.setAttribute('playsinline', ''); v.preload = 'auto'; v.playsInline = true;
      v.src = URL.createObjectURL(blob);
      v.addEventListener('error', function () { vState = 'error'; status.textContent = 'This video could not be played.'; status.hidden = false; });
      v.addEventListener('waiting', function () { /* the clock carries on */ });
      pip.appendChild(v);
      fixDuration(v, function () {
        video = v; vState = 'ready'; status.hidden = true;
        syncVideo(true);
      });
    }).catch(function () {
      vState = 'error'; status.textContent = 'The video could not be loaded. The replay runs without it.';
    });
  }

  function dragify(box, handle) {
    var drag = null;
    function toTopLeft() {
      var r = box.getBoundingClientRect();
      box.style.left = r.left + 'px'; box.style.top = r.top + 'px'; box.style.right = 'auto'; box.style.bottom = 'auto';
    }
    function move(x, y) {
      var r = box.getBoundingClientRect();
      box.style.left = clamp(x, 0, Math.max(0, window.innerWidth - r.width)) + 'px';
      box.style.top = clamp(y, 0, Math.max(0, window.innerHeight - r.height)) + 'px';
    }
    handle.addEventListener('pointerdown', function (ev) {
      if (ev.button != null && ev.button > 0) return;
      toTopLeft();
      var r = box.getBoundingClientRect();
      drag = { dx: ev.clientX - r.left, dy: ev.clientY - r.top };
      try { handle.setPointerCapture(ev.pointerId); } catch (e) { /* none */ }
      ev.preventDefault();
    });
    handle.addEventListener('pointermove', function (ev) { if (drag) move(ev.clientX - drag.dx, ev.clientY - drag.dy); });
    var end = function () { drag = null; };
    handle.addEventListener('pointerup', end); handle.addEventListener('pointercancel', end);
    handle.addEventListener('keydown', function (ev) {
      var d = { ArrowLeft: [-16, 0], ArrowRight: [16, 0], ArrowUp: [0, -16], ArrowDown: [0, 16] }[ev.key];
      if (!d) return;
      toTopLeft(); var r = box.getBoundingClientRect(); move(r.left + d[0], r.top + d[1]);
      ev.preventDefault(); ev.stopPropagation();
    });
  }

  /* ---------------------------------------------------------------- result views (tree-test, card-sort, first-click) */
  function labelIn(list, id) { var n = byId(list || [], id); return n && n.label ? String(n.label) : str(id); }

  function buildTreeResult() {
    var tree = Array.isArray(conf.tree) ? conf.tree : [];
    var res = (S.result && S.result['tree-test']) || {};
    var root = h('div', 'pb-rs-rp-res-in');
    root.appendChild(h('h2', 'pb-rs-rp-res-h', 'Tree test: where each task ended'));
    root.appendChild(h('p', 'pb-rs-rp-res-s', 'The path the participant took through the tree, and the place they chose.'));
    var rows = [];
    var ids = cfgTasks.map(function (t) { return t && t.id; }).filter(Boolean);
    Object.keys(res).forEach(function (k) { if (ids.indexOf(k) === -1) ids.push(k); });
    if (!ids.length) root.appendChild(h('p', null, 'No tree-test result was recorded.'));
    ids.forEach(function (id) {
      var r = res[id] || null, ct = cfgTaskOf(id), st = byId(tasks, id);
      var card = h('div', 'pb-rs-rp-card'); card.setAttribute('data-task', id);
      card.appendChild(h('h3', null, str(id) + (ct && ct.text ? ': ' + ct.text : '')));
      var path = (r && Array.isArray(r.path)) ? r.path : [];
      if (path.length) {
        var ul = h('ol', 'pb-rs-rp-path', null, { 'aria-label': 'Path' });
        path.forEach(function (n, i) {
          if (i) ul.appendChild(h('li', 'pb-rs-rp-sep', '›', { 'aria-hidden': 'true' }));
          ul.appendChild(h('li', 'pb-rs-rp-node' + (r.chosen === n ? ' is-chosen' : ''), labelIn(tree, n)));
        });
        card.appendChild(ul);
      }
      var correct = ct && ct.tree && Array.isArray(ct.tree.correct) ? ct.tree.correct : null;
      var line = h('p');
      if (r && r.chosen) {
        line.appendChild(document.createTextNode('Chose: ' + labelIn(tree, r.chosen) + ' '));
        if (correct) line.appendChild(h('span', 'pb-rs-rp-tag ' + (correct.indexOf(r.chosen) !== -1 ? 'is-pass' : 'is-fail'), correct.indexOf(r.chosen) !== -1 ? 'Correct' : 'Not the expected place'));
      } else {
        line.appendChild(document.createTextNode('No place chosen '));
        line.appendChild(h('span', 'pb-rs-rp-tag', st && st.outcome ? str(st.outcome) : 'skipped'));
      }
      card.appendChild(line);
      var trail = h('p', 'pb-rs-rp-trail'); card.appendChild(trail);
      root.appendChild(card); rows.push({ id: id, card: card, trail: trail });
    });
    return { root: root, update: function (T) {
      var at = activeTaskAt(T), aid = at && at.id;
      rows.forEach(function (row) {
        var on = row.id === aid;
        row.card.classList.toggle('is-active', on);
        var txt = '';
        if (on) {
          var bits = [];
          for (var i = 0; i < events.length && events[i].t <= T; i++) {
            var e = events[i];
            if (e.task === row.id && (e.type === 'tt-open' || e.type === 'tt-choose')) bits.push((e.type === 'tt-open' ? 'Opened ' : 'Chose ') + labelIn(tree, e.node));
          }
          txt = bits.length ? 'So far: ' + bits.join(' › ') : 'So far: nothing opened yet';
        }
        if (row.trail.textContent !== txt) row.trail.textContent = txt;
      });
    } };
  }

  function buildSortResult() {
    var cards = Array.isArray(conf.cards) ? conf.cards : [];
    var cats = (conf.sort && Array.isArray(conf.sort.categories)) ? conf.sort.categories : [];
    var res = (S.result && S.result['card-sort']) || null;
    var root = h('div', 'pb-rs-rp-res-in');
    root.appendChild(h('h2', 'pb-rs-rp-res-h', 'Card sort: the final groups'));
    var kind = conf.sort && conf.sort.kind ? conf.sort.kind : 'open';
    var sub = h('p', 'pb-rs-rp-res-s', kind + ' sort · ' + cards.length + ' cards');
    root.appendChild(sub);
    if (!res) { root.appendChild(h('p', null, 'No card-sort result was recorded.')); return { root: root, update: function () {} }; }
    var grid = h('div', 'pb-rs-rp-groups');
    (Array.isArray(res.groups) ? res.groups : []).forEach(function (g) {
      var card = h('div', 'pb-rs-rp-card');
      card.appendChild(h('h3', null, str(g.name) || 'Group'));
      if (g.category) card.appendChild(h('p', null, 'Category: ' + labelIn(cats, g.category)));
      var ul = h('ul');
      (Array.isArray(g.cards) ? g.cards : []).forEach(function (c) { ul.appendChild(h('li', null, labelIn(cards, c))); });
      card.appendChild(ul); grid.appendChild(card);
    });
    var uns = Array.isArray(res.unsorted) ? res.unsorted : [];
    if (uns.length) {
      var card = h('div', 'pb-rs-rp-card'); card.appendChild(h('h3', null, 'Unsorted'));
      var u = h('ul'); uns.forEach(function (c) { u.appendChild(h('li', null, labelIn(cards, c))); });
      card.appendChild(u); grid.appendChild(card);
    }
    root.appendChild(grid);
    var moves = events.filter(function (e) { return e.type === 'cs-move' || e.type === 'cs-group'; });
    var prog = h('p', 'pb-rs-rp-trail'); root.appendChild(prog);
    return { root: root, update: function (T) {
      var n = lowerBoundAny(moves, T);
      var txt = 'Moves and new groups so far: ' + n + ' of ' + moves.length;
      if (prog.textContent !== txt) prog.textContent = txt;
    } };
  }
  function lowerBoundAny(arr, T) { return lowerBound(arr, T); }

  function buildFirstClickPanel() {
    var res = (S.result && S.result['first-click']) || {};
    var ids = cfgTasks.map(function (t) { return t && t.id; }).filter(Boolean);
    Object.keys(res).forEach(function (k) { if (ids.indexOf(k) === -1) ids.push(k); });
    var det = h('details', 'pb-rs-rp-fc');
    if (window.innerWidth >= 900) det.open = true;
    det.appendChild(h('summary', null, 'First-click results'));
    var ul = h('ul'), rows = [];
    ids.forEach(function (id) {
      var r = res[id], ct = cfgTaskOf(id), st = byId(tasks, id);
      var li = h('li'), b = h('button', null, null, { type: 'button' });
      b.textContent = str(id) + (ct && ct.text ? ': ' + trunc(ct.text, 60) : '') + ' · ' + (r ? (r.hit ? 'hit' : 'miss') + (typeof r.ms === 'number' ? ' in ' + (r.ms / 1000).toFixed(1) + ' s' : '') : 'no click');
      b.addEventListener('click', function () { if (st) seek(num(st.startT, 0) + 1); });
      li.appendChild(b); ul.appendChild(li); rows.push({ id: id, li: li });
    });
    if (!ids.length) ul.appendChild(h('li', null, 'No first-click result was recorded.'));
    det.appendChild(ul);
    return { root: det, update: function (T) {
      var at = activeTaskAt(T);
      rows.forEach(function (r) { r.li.classList.toggle('is-active', !!at && r.id === at.id); });
    } };
  }

  function buildResult() {
    var v = null;
    if (method === 'tree-test') v = buildTreeResult();
    else if (method === 'card-sort') v = buildSortResult();
    else if (method === 'first-click') {
      v = buildFirstClickPanel();
      document.body.appendChild(v.root);
      return v;
    }
    if (!v) return null;
    var wrap = h('div', 'pb-rs-rp-result', null, { role: 'region', 'aria-label': 'Session result' });
    wrap.appendChild(v.root);
    document.body.appendChild(wrap);
    return v;
  }

  /* ---------------------------------------------------------------- keys */
  function onKey(ev) {
    var t = ev.target, tag = t && t.tagName ? t.tagName : '';
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(tag) || (t && t.isContentEditable);
    var mod = ev.metaKey || ev.ctrlKey || ev.altKey;
    // keep the shell's own shortcuts (R reset, S sandbox, I pick, M spacing, Cmd+K search) off this page
    if (!typing && ((!mod && /^[rsimRSIM]$/.test(ev.key)) || ((ev.metaKey || ev.ctrlKey) && /^[kK]$/.test(ev.key)))) { ev.stopImmediatePropagation(); ev.preventDefault(); return; }
    if (typing || mod) return;
    var onControl = /^(BUTTON|A|SUMMARY)$/.test(tag);
    if (ev.key === ' ' || ev.key === 'Spacebar') {
      if (onControl) return;                // the focused button handles its own Space
      toggle(); ev.preventDefault(); ev.stopImmediatePropagation();
    } else if (ev.key === 'ArrowLeft' || ev.key === 'ArrowRight') {
      if (tag === 'SUMMARY' || (t && t.classList && t.classList.contains('pb-rs-rp-pip-h'))) return;
      seek(P.t + (ev.key === 'ArrowLeft' ? -STEP_MS : STEP_MS)); ev.preventDefault(); ev.stopImmediatePropagation();
    } else if (ev.key === 'Home') { seek(0); ev.preventDefault(); }
    else if (ev.key === 'End') { seek(dur); ev.preventDefault(); }
  }

  /* ---------------------------------------------------------------- start */
  var started = false;
  function start() {
    if (started) return; started = true;
    prepShell();
    build();
    resultView = buildResult();
    ensureProto();
    seek(0);
    loadVideo();
    window.addEventListener('keydown', onKey, true);
    window.addEventListener('resize', function () { place(); });
    var app = document.getElementById('app');
    if (app && typeof MutationObserver === 'function') {
      var pending = false;
      new MutationObserver(function () {
        if (pending) return; pending = true;
        requestAnimationFrame(function () { pending = false; place(); });
      }).observe(app, { childList: true });
    }
    // the shell may finish a late repaint of its own (fonts, saved place); put the screen back and re-measure
    window.addEventListener('load', function () { applied.screen = null; apply(P.t); });
    document.addEventListener('visibilitychange', function () { if (document.hidden) pause(); });
  }

  window.pbRsReplay = {
    seek: seek, play: play, pause: pause, toggle: toggle, setSpeed: setSpeed,
    time: function () { return P.t; }, duration: function () { return dur; },
    playing: function () { return P.playing; }, speed: function () { return P.speed; },
    video: function () { return video; }, videoState: function () { return vState; }, videoStart: function () { return vStart; },
    screenAt: wantedScreen
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else setTimeout(start, 0);
})();
