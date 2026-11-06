/* research-methods.js — the in-browser runners for three research methods:
   tree test, card sort and first-click test.

   Loaded right after research-session.js. It registers
     window.pbRsSession.runners["tree-test" | "card-sort" | "first-click"] = { run(ctx) -> Promise }
   and does nothing when window.pbRsSession (or `document`) is missing.

   It consumes only the core API: config, session, now, emit, task.begin/end, ask, postTask,
   ui.root/full/status. ctx = { config, tasks, session }.

   Tool chrome only: class prefix pb-rs-, the --pb-* tokens of chrome.css, one <style id="pb-rs-methods-css">,
   every layer appended to the core's root (or <body>) and never inside .pb-product. All text goes in
   through textContent. Plain ES2019, no libraries. */
(function () {
  'use strict';
  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  var S = window.pbRsSession;
  if (!S) return;
  if (!S.runners) S.runners = {};

  /* ------------------------------------------------------------------ small helpers */

  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    if (attrs) {
      for (var k in attrs) {
        if (!Object.prototype.hasOwnProperty.call(attrs, k)) continue;
        var v = attrs[k];
        if (v == null || v === false) continue;
        if (k === 'class') el.className = v;
        else if (k === 'text') el.textContent = v;
        else if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, v === true ? '' : String(v));
      }
    }
    if (kids) {
      for (var i = 0; i < kids.length; i++) {
        var c = kids[i];
        if (c == null || c === false) continue;
        el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
      }
    }
    return el;
  }

  function cut(s, n) { s = String(s == null ? '' : s); return s.length > n ? s.slice(0, n) : s; }
  function r4(x) { return Math.round(x * 10000) / 10000; }
  function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
  function arr(x) { return Object.prototype.toString.call(x) === '[object Array]' ? x : []; }
  function guard(fn) { try { return fn(); } catch (e) { return undefined; } }

  function host() {
    var r = guard(function () { return S.ui && S.ui.root && S.ui.root(); });
    return r && r.nodeType === 1 ? r : document.body;
  }
  function uiFull(on) { guard(function () { if (S.ui && S.ui.full) S.ui.full(on); }); }
  function uiStatus(t) { guard(function () { if (S.ui && S.ui.status) S.ui.status(t); }); }
  function emit(type, fields) { return guard(function () { return S.emit(type, fields || {}); }); }

  function result(method) {
    var s = S.session;
    if (!s.result || typeof s.result !== 'object') s.result = {};
    if (!s.result[method]) s.result[method] = {};
    return s.result[method];
  }

  function cfgOf(ctx) { return (ctx && ctx.config) || S.config || {}; }
  function pick(cfg, key) {
    if (cfg[key] != null) return cfg[key];
    return cfg.instrument && cfg.instrument[key] != null ? cfg.instrument[key] : null;
  }
  function tasksOf(ctx, key) {
    if (ctx && arr(ctx.tasks).length) return ctx.tasks.slice();
    var out = [], secs = arr(guard(function () { return cfgOf(ctx).instrument.sections; }));
    secs.forEach(function (s) {
      arr(s && s.questions).forEach(function (q) { if (q && q[key]) out.push(q); });
    });
    return out;
  }

  /* One post-task question set per task, after the task has ended (so its time excludes the questions). */
  function afterTask(q) {
    var qs = arr(guard(function () { return S.postTask(q); }));
    if (!qs.length) return Promise.resolve();
    return Promise.resolve(S.ask(qs, { task: q.id })).then(function () {});
  }

  /* A seeded shuffle (mulberry32 over an FNV-1a hash of the session id), so a session's card order can be
     reproduced and is recorded in the result. */
  function hash32(str) {
    var x = 2166136261;
    for (var i = 0; i < str.length; i++) { x ^= str.charCodeAt(i); x = Math.imul(x, 16777619) >>> 0; }
    return x >>> 0;
  }
  function rng(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function shuffle(list, seedStr) {
    var out = list.slice(), rand = rng(hash32(seedStr));
    for (var i = out.length - 1; i > 0; i--) {
      var j = Math.floor(rand() * (i + 1)), t = out[i]; out[i] = out[j]; out[j] = t;
    }
    return out;
  }

  /* ------------------------------------------------------------------ styles */

  var CSS = [
    '.pb-rs-m,.pb-rs-m *{box-sizing:border-box}',
    '.pb-rs-m [hidden]{display:none!important}',
    '.pb-rs-m{position:fixed;inset:0;z-index:2147483000;overflow:auto;background:var(--pb-page);color:var(--pb-ink);',
    'font:var(--pb-w-reg) var(--pb-t-md)/var(--pb-lh) var(--pb-font);-webkit-text-size-adjust:100%}',
    '.pb-rs-m-in{max-width:72rem;margin:0 auto;padding:var(--pb-s5) var(--pb-s4) var(--pb-s6)}',
    '.pb-rs-m-step{margin:0 0 var(--pb-s1);color:var(--pb-ink-3);font-size:var(--pb-t-sm);letter-spacing:var(--pb-track);text-transform:uppercase}',
    '.pb-rs-m-title{margin:0 0 var(--pb-s2);font-size:var(--pb-t-xl);line-height:var(--pb-lh-tight);font-weight:var(--pb-w-bold);overflow-wrap:anywhere}',
    '.pb-rs-m-hint{margin:0 0 var(--pb-s4);color:var(--pb-ink-2);max-width:46rem}',
    '.pb-rs-m-live{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}',
    '.pb-rs-m-btn{display:inline-flex;align-items:center;justify-content:center;gap:var(--pb-s2);min-height:2.5rem;padding:0 var(--pb-s4);',
    'border:var(--pb-hair-w) solid var(--pb-hair-2);border-radius:var(--pb-r);background:var(--pb-surface);color:var(--pb-ink);',
    'font:inherit;cursor:pointer;text-align:center}',
    '.pb-rs-m-btn:hover:not(:disabled){background:var(--pb-wash)}',
    '.pb-rs-m-btn:disabled{opacity:.45;cursor:default}',
    '.pb-rs-m-btn--solid{background:var(--pb-ink);border-color:var(--pb-ink);color:var(--pb-on-ink);font-weight:var(--pb-w-bold)}',
    '.pb-rs-m-btn--solid:hover:not(:disabled){background:var(--pb-ink);opacity:.88}',
    '.pb-rs-m-btn--quiet{border-color:transparent;background:none;color:var(--pb-ink-2)}',
    '.pb-rs-m-btn--quiet:hover:not(:disabled){background:var(--pb-wash);color:var(--pb-ink)}',
    '.pb-rs-m button:focus-visible,.pb-rs-m input:focus-visible,.pb-rs-m select:focus-visible,',
    '.pb-rs-fc-pill button:focus-visible,.pb-rs-m-card button:focus-visible{outline:2px solid var(--pb-info);outline-offset:2px}',
    '.pb-rs-m-foot{display:flex;flex-wrap:wrap;align-items:center;gap:var(--pb-s3);margin-top:var(--pb-s5)}',

    /* tree test */
    '.pb-rs-tt-tools{display:flex;flex-wrap:wrap;align-items:center;gap:var(--pb-s3);margin:0 0 var(--pb-s3);',
    'padding:var(--pb-s2) 0;border-bottom:var(--pb-hair-w) solid var(--pb-hair)}',
    '.pb-rs-tt-crumb{color:var(--pb-ink-3);font-size:var(--pb-t-sm);overflow-wrap:anywhere;min-width:0}',
    '.pb-rs-tt-list{list-style:none;margin:0;padding:0;max-width:44rem}',
    '.pb-rs-tt-list .pb-rs-tt-list{margin-left:var(--pb-s4);padding-left:var(--pb-s3);border-left:var(--pb-hair-w) solid var(--pb-hair-2)}',
    '.pb-rs-tt-row{display:flex;flex-wrap:wrap;align-items:center;gap:var(--pb-s1) var(--pb-s2);min-height:2.75rem}',
    '.pb-rs-tt-node{flex:0 1 auto;min-width:0;max-width:100%;display:flex;align-items:center;gap:var(--pb-s2);min-height:2.75rem;padding:0 var(--pb-s2);',
    'border:0;border-radius:var(--pb-r);background:none;color:var(--pb-ink);font:inherit;text-align:left;cursor:pointer;overflow-wrap:anywhere}',
    '.pb-rs-tt-node:hover{background:var(--pb-wash)}',
    '.pb-rs-tt-row.is-current>.pb-rs-tt-node{background:var(--pb-info-bg);color:var(--pb-info)}',
    '.pb-rs-tt-chev{flex:none;width:1rem;height:1rem;display:inline-block;position:relative;color:var(--pb-ink-3)}',
    '.pb-rs-tt-chev::before{content:"";position:absolute;left:.3rem;top:.3rem;width:.4rem;height:.4rem;',
    'border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(-45deg)}',
    '.pb-rs-tt-node[aria-expanded="true"] .pb-rs-tt-chev::before{transform:rotate(45deg);top:.2rem}',
    '.pb-rs-tt-leaf .pb-rs-tt-chev::before{border:0;width:.3rem;height:.3rem;left:.35rem;top:.35rem;background:currentColor;border-radius:50%;transform:none}',
    '.pb-rs-tt-pick{flex:none;min-height:2.25rem;padding:0 var(--pb-s3);border:var(--pb-hair-w) solid var(--pb-hair-2);border-radius:var(--pb-r);',
    'background:var(--pb-surface);color:var(--pb-ink-2);font:inherit;font-size:var(--pb-t-sm);cursor:pointer}',
    '.pb-rs-tt-pick:hover{background:var(--pb-ink);border-color:var(--pb-ink);color:var(--pb-on-ink)}',

    /* card sort */
    '.pb-rs-cs-bar{position:sticky;top:0;z-index:3;display:flex;flex-wrap:wrap;align-items:center;gap:var(--pb-s2) var(--pb-s3);',
    'margin:0 calc(var(--pb-s4) * -1) var(--pb-s3);padding:var(--pb-s2) var(--pb-s4);background:var(--pb-surface);',
    'border-bottom:var(--pb-hair-w) solid var(--pb-hair-2)}',
    '.pb-rs-cs-bar-t{flex:1 1 12rem;min-width:0;overflow-wrap:anywhere}',
    '.pb-rs-cs-bar.is-sel{background:var(--pb-info-bg);border-color:var(--pb-info)}',
    '.pb-rs-cs-sel{min-height:2.5rem;max-width:100%;padding:0 var(--pb-s2);border:var(--pb-hair-w) solid var(--pb-hair-2);border-radius:var(--pb-r);',
    'background:var(--pb-surface);color:var(--pb-ink);font:inherit}',
    '.pb-rs-cs-board{display:grid;grid-template-columns:minmax(0,1fr);gap:var(--pb-s4);align-items:start}',
    '.pb-rs-cs-pane{min-width:0;border:var(--pb-hair-w) solid var(--pb-hair-2);border-radius:var(--pb-r);background:var(--pb-surface);padding:var(--pb-s3)}',
    '.pb-rs-cs-pane-h{display:flex;align-items:center;gap:var(--pb-s2);margin:0 0 var(--pb-s2);min-width:0}',
    '.pb-rs-cs-pane-t{flex:1 1 auto;min-width:0;margin:0;font-size:var(--pb-t-md);font-weight:var(--pb-w-bold);overflow-wrap:anywhere}',
    '.pb-rs-cs-count{flex:none;color:var(--pb-ink-3);font-size:var(--pb-t-sm)}',
    '.pb-rs-cs-cards{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:var(--pb-s2);min-height:2.75rem}',
    '.pb-rs-cs-groups{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,14rem),1fr));gap:var(--pb-s3);margin-top:var(--pb-s3)}',
    '.pb-rs-cs-groups-bar{display:flex;flex-wrap:wrap;align-items:center;gap:var(--pb-s3)}',
    '.pb-rs-cs-gname{flex:1 1 auto;min-width:0;width:100%;min-height:2.25rem;padding:0 var(--pb-s2);border:var(--pb-hair-w) solid var(--pb-hair-2);',
    'border-radius:var(--pb-r);background:var(--pb-page);color:var(--pb-ink);font:inherit;font-weight:var(--pb-w-bold)}',
    '.pb-rs-cs-card{display:flex;align-items:center;gap:var(--pb-s2);max-width:100%;min-height:2.75rem;padding:0 var(--pb-s3) 0 0;',
    'border:var(--pb-hair-w) solid var(--pb-hair-2);border-radius:var(--pb-r);background:var(--pb-raised);color:var(--pb-ink);',
    'font:inherit;text-align:left;cursor:grab;user-select:none;-webkit-user-select:none;-webkit-user-drag:none;touch-action:manipulation}',
    '.pb-rs-cs-card:hover{border-color:var(--pb-ink-3)}',
    '.pb-rs-cs-card[aria-pressed="true"]{border-color:var(--pb-info);background:var(--pb-info-bg);box-shadow:0 0 0 1px var(--pb-info)}',
    '.pb-rs-cs-card.is-drag{opacity:.35}',
    '.pb-rs-cs-lab{min-width:0;overflow-wrap:anywhere}',
    '.pb-rs-cs-grip{flex:none;align-self:stretch;width:1.75rem;display:flex;align-items:center;justify-content:center;touch-action:none;color:var(--pb-ink-3);',
    'border-right:var(--pb-hair-w) solid var(--pb-hair)}',
    '.pb-rs-cs-grip::before{content:"";width:.5rem;height:.875rem;background:radial-gradient(circle,currentColor 1.2px,transparent 1.5px) 0 0/.5rem .3rem}',
    '.pb-rs-cs-ghost{position:fixed;left:0;top:0;z-index:2147483600;pointer-events:none;max-width:16rem;padding:var(--pb-s2) var(--pb-s3);',
    'border:var(--pb-hair-w) solid var(--pb-info);border-radius:var(--pb-r);background:var(--pb-info-bg);color:var(--pb-ink);box-shadow:var(--pb-shadow);',
    'font:var(--pb-w-reg) var(--pb-t-md)/var(--pb-lh) var(--pb-font);overflow-wrap:anywhere}',
    '.pb-rs-cs-pane.is-over{border-color:var(--pb-info);background:var(--pb-info-bg)}',
    '.pb-rs-cs-empty{margin:0;padding:var(--pb-s2) 0;color:var(--pb-ink-3);font-size:var(--pb-t-sm)}',
    '.pb-rs-cs-actions{display:flex;flex-wrap:wrap;gap:var(--pb-s2);margin-top:var(--pb-s2)}',
    '.pb-rs-m-btn--sm{min-height:2.25rem;padding:0 var(--pb-s3);font-size:var(--pb-t-sm)}',
    '.pb-rs-cs-foot{position:sticky;bottom:0;z-index:3;margin:var(--pb-s4) calc(var(--pb-s4) * -1) 0;padding:var(--pb-s3) var(--pb-s4);',
    'background:var(--pb-surface);border-top:var(--pb-hair-w) solid var(--pb-hair-2);display:flex;flex-wrap:wrap;align-items:center;gap:var(--pb-s3)}',
    '.pb-rs-cs-foot-t{flex:1 1 12rem;min-width:0}',
    '@media (min-width:44rem){',
    '.pb-rs-cs-board{grid-template-columns:minmax(13rem,18rem) minmax(0,1fr)}',
    '.pb-rs-cs-pane--un{position:sticky;top:4.5rem;max-height:calc(100vh - 11rem);overflow:auto}',
    '.pb-rs-cs-pane--un .pb-rs-cs-cards{flex-direction:column;flex-wrap:nowrap}',
    '.pb-rs-cs-pane--un .pb-rs-cs-card{width:100%}',
    '}',

    /* first click */
    '.pb-rs-m-scrim{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;padding:var(--pb-s4);',
    'background:var(--pb-scrim)}',
    '.pb-rs-m-card{width:100%;max-width:28rem;padding:var(--pb-s5);border:var(--pb-hair-w) solid var(--pb-hair-2);border-radius:var(--pb-r);',
    'background:var(--pb-surface);color:var(--pb-ink);box-shadow:var(--pb-shadow);font:var(--pb-w-reg) var(--pb-t-md)/var(--pb-lh) var(--pb-font)}',
    '.pb-rs-m-card .pb-rs-m-title{font-size:var(--pb-t-lg)}',
    '.pb-rs-m-card .pb-rs-m-foot{margin-top:var(--pb-s4)}',
    '.pb-rs-fc-pill{position:fixed;left:50%;transform:translateX(-50%);bottom:var(--pb-s4);z-index:2147483000;display:flex;align-items:center;gap:var(--pb-s2);',
    'width:max-content;max-width:calc(100vw - 2rem);padding:var(--pb-s2) var(--pb-s2) var(--pb-s2) var(--pb-s4);border:var(--pb-hair-w) solid var(--pb-hair-2);',
    'border-radius:999px;background:var(--pb-surface);color:var(--pb-ink);box-shadow:var(--pb-shadow);font:var(--pb-w-reg) var(--pb-t-md)/var(--pb-lh) var(--pb-font)}',
    '.pb-rs-fc-pill.is-top{bottom:auto;top:var(--pb-s4)}',
    '.pb-rs-fc-pill-t{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    '.pb-rs-fc-dot{position:fixed;z-index:2147483100;width:1.25rem;height:1.25rem;margin:-.625rem 0 0 -.625rem;border-radius:50%;',
    'border:2px solid var(--pb-on-ink);background:var(--pb-info);box-shadow:0 0 0 2px var(--pb-info);pointer-events:none}',
    '@media (prefers-reduced-motion:no-preference){',
    '.pb-rs-m-btn,.pb-rs-tt-node,.pb-rs-tt-pick,.pb-rs-cs-card,.pb-rs-cs-pane{transition:background-color .12s,border-color .12s,color .12s}',
    '.pb-rs-fc-dot{animation:pb-rs-fc-pop .25s ease-out}',
    '@keyframes pb-rs-fc-pop{from{transform:scale(.4);opacity:0}to{transform:scale(1);opacity:1}}',
    '}'
  ].join('');

  function ensureStyle() {
    if (document.getElementById('pb-rs-methods-css')) return;
    var st = document.createElement('style');
    st.id = 'pb-rs-methods-css';
    st.textContent = CSS;
    (document.body || document.documentElement).appendChild(st);
  }

  function btn(label, kind, onClick, extra) {
    var a = { type: 'button', class: 'pb-rs-m-btn' + (kind ? ' pb-rs-m-btn--' + kind : ''), text: label };
    if (extra) for (var k in extra) a[k] = extra[k];
    var b = h('button', a);
    if (onClick) b.addEventListener('click', onClick);
    return b;
  }

  function layer(cls, label) {
    var el = h('div', { class: cls, role: 'region', 'aria-label': label || null });
    host().appendChild(el);
    return el;
  }

  function focusSoon(el) {
    if (!el) return;
    setTimeout(function () { guard(function () { el.focus({ preventScroll: true }); }); }, 0);
  }

  function taskOutcome(q, chosen) {
    // The participant's page never carries the answer key (research_session.participant_config strips
    // tree.correct), so a choice is "answered" here and scored by research_analysis against the study.
    var correct = arr(guard(function () { return q.tree.correct; }));
    if (!correct.length) return ['answered', 'self'];
    return [correct.indexOf(chosen) >= 0 ? 'success' : 'fail', 'criteria'];
  }

  /* ================================================================== TREE TEST */

  function treeModel(list) {
    var byId = {}, kids = { '': [] }, order = [];
    arr(list).forEach(function (n) {
      if (!n || n.id == null || byId[n.id]) return;
      byId[n.id] = { id: String(n.id), label: String(n.label == null ? n.id : n.label), parent: n.parent == null ? '' : String(n.parent) };
      order.push(String(n.id));
    });
    order.forEach(function (id) {
      var n = byId[id];
      if (n.parent && !byId[n.parent]) n.parent = '';
      (kids[n.parent] = kids[n.parent] || []).push(id);
    });
    return { byId: byId, kids: kids };
  }

  function treeTask(q, index, total, model) {
    var tid = q.id;
    var chain = [];          // open nodes, root to deepest
    var sel = null;          // a visited leaf
    var path = [];           // every node opened, in order, ending at the choice
    var res = result('tree-test');
    res[tid] = { chosen: null, path: path };

    S.task.begin(q);
    uiStatus('Task ' + (index + 1) + ' of ' + total);

    var wrap = layer('pb-rs-m', 'Tree test, task ' + (index + 1) + ' of ' + total);
    var list = h('div'), crumb = h('span', { class: 'pb-rs-tt-crumb' }), back = btn('Back', null, null, { class: 'pb-rs-m-btn pb-rs-m-btn--sm' });
    var live = h('div', { class: 'pb-rs-m-live', 'aria-live': 'polite' });
    var skip = btn('Skip this task', 'quiet');
    wrap.appendChild(h('div', { class: 'pb-rs-m-in' }, [
      h('p', { class: 'pb-rs-m-step', text: 'Task ' + (index + 1) + ' of ' + total }),
      h('h2', { class: 'pb-rs-m-title', text: q.text || '' }),
      h('p', { class: 'pb-rs-m-hint', text: 'Open the sections to look for it. When you find where it would be, choose \u201CI\u2019d find it here\u201D.' }),
      h('div', { class: 'pb-rs-tt-tools' }, [back, crumb]),
      list,
      h('div', { class: 'pb-rs-m-foot' }, [skip]),
      live
    ]));

    function labelOf(id) { return model.byId[id].label; }
    function parentOf(id) { var p = model.byId[id].parent; return p || null; }
    function ancestors(id) { var out = [], p = parentOf(id); while (p) { out.unshift(p); p = parentOf(p); } return out; }
    function location() { return chain.length ? chain[chain.length - 1] : null; }

    function visit(id, why) {
      path.push(id);
      emit('tt-open', { node: id });
      if (why) live.textContent = why;
    }

    function onNode(id) {
      var hasKids = (model.kids[id] || []).length > 0, at = chain.indexOf(id);
      if (hasKids && at >= 0 && at === chain.length - 1) { collapse(); return; }   // the deepest open node folds shut
      sel = null;
      if (hasKids) chain = ancestors(id).concat([id]);
      else {
        chain = ancestors(id); sel = id;
        if (path[path.length - 1] === id) { paint(id); return; }
      }
      visit(id, hasKids ? labelOf(id) + ' opened' : labelOf(id) + ' selected');
      paint(id);
    }

    function collapse() {
      sel = null;
      var closed = chain.pop(), up = location();
      if (up) visit(up, 'Back to ' + labelOf(up));
      else live.textContent = 'Back to the top level';
      paint(up || closed);
    }

    function goBack() {
      if (sel) {                                  // from a leaf back to where it was found
        sel = null;
        var here = location();
        if (here) visit(here, 'Back to ' + labelOf(here));
        paint(here);
        return;
      }
      if (chain.length) collapse();
    }

    function paint(focusId) {
      var here = location();
      crumb.textContent = chain.length || sel
        ? 'You are in: ' + chain.concat(sel ? [sel] : []).map(labelOf).join(' \u203A ')
        : 'You are at the top level';
      back.disabled = !chain.length && !sel;
      while (list.firstChild) list.removeChild(list.firstChild);
      list.appendChild(level(''));
      if (focusId) {
        var t = list.querySelector('[data-node="' + String(focusId).replace(/["\\]/g, '\\$&') + '"] > .pb-rs-tt-row > .pb-rs-tt-node');
        if (t) focusSoon(t);
      }
      return here;
    }

    function level(parent) {
      var ul = h('ul', { class: 'pb-rs-tt-list' });
      (model.kids[parent] || []).forEach(function (id) {
        var kidIds = model.kids[id] || [], open = chain.indexOf(id) >= 0;
        var node = h('button', {
          type: 'button', class: 'pb-rs-tt-node' + (kidIds.length ? '' : ' pb-rs-tt-leaf'),
          'aria-expanded': kidIds.length ? (open ? 'true' : 'false') : null
        }, [h('span', { class: 'pb-rs-tt-chev', 'aria-hidden': 'true' }, null), h('span', { text: labelOf(id) })]);
        node.addEventListener('click', function () { onNode(id); });
        var pickBtn = h('button', { type: 'button', class: 'pb-rs-tt-pick', text: 'I\u2019d find it here', 'aria-label': 'I\u2019d find it here: ' + labelOf(id) });
        pickBtn.addEventListener('click', function () { done('chosen', id); });
        var row = h('div', { class: 'pb-rs-tt-row' + (sel === id ? ' is-current' : '') }, [node, pickBtn]);
        var li = h('li', { 'data-node': id }, [row]);
        if (open && kidIds.length) li.appendChild(level(id));
        ul.appendChild(li);
      });
      return ul;
    }

    var finish;
    function done(kind, id) {
      if (!finish) return;
      var f = finish; finish = null;
      f({ kind: kind, node: id || null });
    }

    back.addEventListener('click', goBack);
    skip.addEventListener('click', function () { done('skipped'); });
    paint(null);
    focusSoon(list.querySelector('.pb-rs-tt-node') || skip);

    return new Promise(function (resolve) { finish = resolve; }).then(function (r) {
      var outcome, source;
      if (r.kind === 'chosen') {
        if (path[path.length - 1] !== r.node) path.push(r.node);
        res[tid] = { chosen: r.node, path: path };
        emit('tt-choose', { node: r.node });
        var oc = taskOutcome(q, r.node); outcome = oc[0]; source = oc[1];
      } else {
        res[tid] = { chosen: null, path: path };
        outcome = 'skipped'; source = 'self';
      }
      if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
      S.task.end(outcome, source);
      return afterTask(q);
    });
  }

  function runTreeTest(ctx) {
    ensureStyle();
    var cfg = cfgOf(ctx), model = treeModel(pick(cfg, 'tree')), tasks = tasksOf(ctx, 'tree');
    result('tree-test');
    uiFull(true);
    var chain = Promise.resolve();
    tasks.forEach(function (q, i) { chain = chain.then(function () { return treeTask(q, i, tasks.length, model); }); });
    return chain.then(function () { uiFull(false); uiStatus(''); }, function (e) { uiFull(false); uiStatus(''); throw e; });
  }

  /* ================================================================== CARD SORT */

  function runCardSort(ctx) {
    ensureStyle();
    var cfg = cfgOf(ctx);
    var cards = [], seen = {};
    arr(pick(cfg, 'cards')).forEach(function (c) {
      if (c && c.id != null && !seen[c.id]) { seen[c.id] = 1; cards.push({ id: String(c.id), label: String(c.label == null ? c.id : c.label) }); }
    });
    var sortCfg = pick(cfg, 'sort') || {};
    var cats = arr(sortCfg.categories).filter(function (c) { return c && c.id != null; });
    var kind = sortCfg.kind === 'closed' || sortCfg.kind === 'hybrid' ? sortCfg.kind : 'open';
    if (kind !== 'open' && !cats.length) kind = 'open';
    var canCreate = kind !== 'closed';
    var useCats = kind !== 'open';

    var cardById = {};
    cards.forEach(function (c) { cardById[c.id] = c; });
    var order = shuffle(cards.map(function (c) { return c.id; }), String(S.session && S.session.sessionId || Date.now()));
    var res = result('card-sort');
    res.order = order.slice();

    var groups = [];                 // {key,name,category,fixed,cards[],el parts}
    var where = {};                  // card id -> group key | null
    cards.forEach(function (c) { where[c.id] = null; });
    var selected = null, counter = 0, justDragged = false;

    function groupByKey(k) { for (var i = 0; i < groups.length; i++) if (groups[i].key === k) return groups[i]; return null; }
    function unsortedIds() { return order.filter(function (id) { return where[id] == null; }); }
    function sortedCount() { return cards.length - unsortedIds().length; }

    function syncResult() {
      res.groups = groups.filter(function (g) { return g.cards.length; }).map(function (g) {
        return { name: g.name, category: g.category, cards: g.cards.slice() };
      });
      res.unsorted = unsortedIds();
      res.order = order.slice();
    }

    /* ---- DOM ---- */
    var wrap = layer('pb-rs-m', 'Card sort');
    var live = h('div', { class: 'pb-rs-m-live', 'aria-live': 'polite' });
    var barT = h('span', { class: 'pb-rs-cs-bar-t' });
    var barSel = h('select', { class: 'pb-rs-cs-sel', 'aria-label': 'Move the selected card to' });
    var barCancel = btn('Cancel', 'quiet', null, { class: 'pb-rs-m-btn pb-rs-m-btn--quiet pb-rs-m-btn--sm' });
    var bar = h('div', { class: 'pb-rs-cs-bar', role: 'group', 'aria-label': 'Selected card' }, [barT, barSel, barCancel]);
    var unList = h('ul', { class: 'pb-rs-cs-cards', 'data-list': '' });
    var unCount = h('span', { class: 'pb-rs-cs-count' });
    var unEmpty = h('p', { class: 'pb-rs-cs-empty', text: 'Every card has a group.' });
    var unPut = btn('Put here', null, null, { class: 'pb-rs-m-btn pb-rs-m-btn--sm' });
    var unPane = h('section', { class: 'pb-rs-cs-pane pb-rs-cs-pane--un', 'data-drop': '', 'aria-label': 'Unsorted cards' }, [
      h('div', { class: 'pb-rs-cs-pane-h' }, [h('h3', { class: 'pb-rs-cs-pane-t', text: 'Unsorted' }), unCount, unPut]),
      unList, unEmpty
    ]);
    var groupsEl = h('div', { class: 'pb-rs-cs-groups' });
    var addBtn = canCreate ? btn('New group', null, function () { addGroup(); }, { class: 'pb-rs-m-btn pb-rs-m-btn--sm' }) : null;
    var groupsPane = h('div', { class: 'pb-rs-cs-groups-wrap', style: 'min-width:0' }, [
      h('div', { class: 'pb-rs-cs-groups-bar' }, [
        h('h3', { class: 'pb-rs-cs-pane-t', text: kind === 'closed' ? 'Groups' : 'Your groups' }), addBtn
      ]),
      groupsEl
    ]);
    var footT = h('span', { class: 'pb-rs-cs-foot-t' });
    var doneBtn = btn('Done', 'solid', null);
    var foot = h('div', { class: 'pb-rs-cs-foot' }, [footT, doneBtn]);

    var hintText = kind === 'open'
      ? 'Put the cards into groups that make sense to you. Make as many groups as you like and give each a name.'
      : kind === 'closed'
        ? 'Put each card into the group where you would expect to find it.'
        : 'Put each card into the group where you would expect to find it. If none fits, make a group of your own.';
    wrap.appendChild(h('div', { class: 'pb-rs-m-in' }, [
      h('p', { class: 'pb-rs-m-step', text: 'Card sort' }),
      h('h2', { class: 'pb-rs-m-title', text: 'Sort the cards' }),
      h('p', { class: 'pb-rs-m-hint', text: hintText + ' Drag a card into a group, or choose a card and then choose a group.' }),
      bar,
      h('div', { class: 'pb-rs-cs-board' }, [unPane, groupsPane]),
      foot,
      live
    ]));

    var cardEl = {};
    cards.forEach(function (c) {
      var grip = h('span', { class: 'pb-rs-cs-grip', 'aria-hidden': 'true' }, null);
      var b = h('button', { type: 'button', class: 'pb-rs-cs-card', 'data-card': c.id, 'aria-pressed': 'false' }, [
        grip, h('span', { class: 'pb-rs-cs-lab', text: c.label })
      ]);
      cardEl[c.id] = b;
    });

    /* ---- groups ---- */
    function uniqueKey(base) { var k = base; while (groupByKey(k)) k += '_'; return k; }

    function addGroup(name, category, fixed) {
      var custom = !fixed;
      counter += custom ? 1 : 0;
      var g = {
        key: uniqueKey(fixed ? 'c-' + category : 'g' + counter),
        name: cut(name || ('Group ' + counter), 80), category: category || null, fixed: !!fixed, cards: []
      };
      var list = h('ul', { class: 'pb-rs-cs-cards', 'data-list': g.key, style: 'flex-direction:column;flex-wrap:nowrap' });
      var empty = h('p', { class: 'pb-rs-cs-empty', text: 'Drop cards here' });
      var count = h('span', { class: 'pb-rs-cs-count' });
      var put = btn('Put here', null, function () { if (selected) placeSelected(g.key); }, { class: 'pb-rs-m-btn pb-rs-m-btn--sm' });
      var head, nameEl;
      if (fixed) {
        nameEl = h('h3', { class: 'pb-rs-cs-pane-t', text: g.name });
        head = h('div', { class: 'pb-rs-cs-pane-h' }, [nameEl, count, put]);
      } else {
        nameEl = h('input', { type: 'text', class: 'pb-rs-cs-gname', value: g.name, maxlength: 80, 'aria-label': 'Group name', autocomplete: 'off', spellcheck: 'false' });
        nameEl.addEventListener('change', function () { renameGroup(g, nameEl.value); });
        nameEl.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); nameEl.blur(); } });
        head = h('div', { class: 'pb-rs-cs-pane-h' }, [count, put]);
      }
      var del = custom ? btn('Delete', 'quiet', function () { deleteGroup(g); }, { class: 'pb-rs-m-btn pb-rs-m-btn--quiet pb-rs-m-btn--sm', 'aria-label': 'Delete group ' + g.name }) : null;
      var pane = h('section', { class: 'pb-rs-cs-pane', 'data-drop': g.key, 'aria-label': 'Group ' + g.name }, [
        custom ? h('div', { class: 'pb-rs-cs-pane-h' }, [nameEl]) : null,
        head, list, empty, del ? h('div', { class: 'pb-rs-cs-actions' }, [del]) : null
      ]);
      g.pane = pane; g.list = list; g.empty = empty; g.count = count; g.put = put; g.nameEl = nameEl; g.del = del;
      groups.push(g);
      groupsEl.appendChild(pane);
      emit('cs-group', { group: g.key, name: g.name, category: g.category });
      render();
      if (custom && arguments.length === 0) { guard(function () { nameEl.focus(); nameEl.select(); }); live.textContent = 'Group added. Type a name.'; }
      return g;
    }

    function renameGroup(g, v) {
      v = cut(String(v || '').replace(/^\s+|\s+$/g, ''), 80);
      if (!v) { g.nameEl.value = g.name; return; }
      if (v === g.name) return;
      g.name = v;
      g.nameEl.value = v;
      g.pane.setAttribute('aria-label', 'Group ' + v);
      if (g.del) g.del.setAttribute('aria-label', 'Delete group ' + v);
      emit('cs-group', { group: g.key, name: g.name, category: g.category });
      syncResult(); fillSelect();
    }

    function deleteGroup(g) {
      var i = groups.indexOf(g);
      if (i < 0) return;
      g.cards.slice().forEach(function (id) { moveCard(id, null, true); });
      groups.splice(i, 1);
      if (g.pane.parentNode) g.pane.parentNode.removeChild(g.pane);
      emit('cs-group', { group: g.key, name: '', category: g.category, removed: true });
      live.textContent = 'Group ' + g.name + ' deleted. Its cards are unsorted.';
      syncResult(); render();
      focusSoon(addBtn || doneBtn);
    }

    /* ---- moving ---- */
    function moveCard(id, key, quiet) {
      var from = where[id] == null ? null : where[id];
      if (from === key) return false;
      if (from != null) { var og = groupByKey(from); if (og) og.cards.splice(og.cards.indexOf(id), 1); }
      if (key != null) groupByKey(key).cards.push(id);
      where[id] = key;
      syncResult();
      emit('cs-move', { card: id, group: key });
      if (!quiet) live.textContent = cardById[id].label + ' moved to ' + (key == null ? 'Unsorted' : groupByKey(key).name) + '. ' + unsortedIds().length + ' cards left.';
      render();
      return true;
    }

    function placeSelected(key) {
      var id = selected;
      if (!id) return;
      var changed = moveCard(id, key);
      select(null);
      var next = unsortedIds()[0];
      focusSoon(changed && next ? cardEl[next] : (changed ? doneBtn : cardEl[id]));
    }

    function select(id) {
      selected = id;
      Object.keys(cardEl).forEach(function (k) { cardEl[k].setAttribute('aria-pressed', k === id ? 'true' : 'false'); });
      render();
    }

    function fillSelect() {
      while (barSel.firstChild) barSel.removeChild(barSel.firstChild);
      barSel.appendChild(h('option', { value: '', text: 'Choose a group\u2026' }));
      barSel.appendChild(h('option', { value: '\u0000un', text: 'Unsorted' }));
      groups.forEach(function (g) { barSel.appendChild(h('option', { value: g.key, text: g.name })); });
      barSel.value = '';
    }

    barSel.addEventListener('change', function () {
      var v = barSel.value;
      if (!v) return;
      placeSelected(v === '\u0000un' ? null : v);
    });
    barCancel.addEventListener('click', function () { var id = selected; select(null); focusSoon(id && cardEl[id]); });
    unPut.addEventListener('click', function () { if (selected) placeSelected(null); });

    /* ---- render: move existing nodes, only when the order differs, so focus is kept ---- */
    var liEl = {};
    cards.forEach(function (c) { liEl[c.id] = h('li', null, [cardEl[c.id]]); });
    function fill(list, ids) {
      var same = list.children.length === ids.length;
      if (same) for (var i = 0; i < ids.length; i++) if (list.children[i] !== liEl[ids[i]]) { same = false; break; }
      if (same) return;
      var active = document.activeElement;
      ids.forEach(function (id) { list.appendChild(liEl[id]); });
      if (active && active !== document.activeElement && document.contains(active)) guard(function () { active.focus({ preventScroll: true }); });
    }

    function render() {
      var un = unsortedIds();
      fill(unList, un);
      unCount.textContent = String(un.length);
      unEmpty.hidden = un.length > 0;
      groups.forEach(function (g) {
        fill(g.list, g.cards);
        g.count.textContent = String(g.cards.length);
        g.empty.hidden = g.cards.length > 0;
        g.put.hidden = !selected || where[selected] === g.key;
        g.put.setAttribute('aria-label', 'Put the selected card in ' + g.name);
      });
      unPut.hidden = !selected || where[selected] == null;
      if (selected) {
        bar.className = 'pb-rs-cs-bar is-sel';
        barT.textContent = 'Selected: \u201C' + cardById[selected].label + '\u201D. Choose a group.';
        barSel.hidden = false; barCancel.hidden = false;
        fillSelect();
      } else {
        bar.className = 'pb-rs-cs-bar';
        barT.textContent = 'Choose a card to move it, or drag it into a group.';
        barSel.hidden = true; barCancel.hidden = true;
      }
      footT.textContent = sortedCount() + ' of ' + cards.length + ' cards sorted';
    }

    /* ---- click / keyboard selection ---- */
    wrap.addEventListener('click', function (e) {
      var c = e.target.closest ? e.target.closest('.pb-rs-cs-card') : null;
      if (!c) return;
      if (justDragged) { justDragged = false; return; }
      var id = c.getAttribute('data-card');
      select(selected === id ? null : id);     // cards are never re-created, so focus stays where it is
    });
    wrap.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && selected && !drag) { var id = selected; select(null); focusSoon(cardEl[id]); }
    });

    /* ---- pointer drag ---- */
    var drag = null, ghost = null, overPane = null, scrollRaf = 0, lastY = 0;

    function paneAt(x, y) {
      var el = document.elementFromPoint(x, y);
      var p = el && el.closest ? el.closest('[data-drop]') : null;
      return p && wrap.contains(p) ? p : null;
    }
    function setOver(p) {
      if (overPane === p) return;
      if (overPane) overPane.classList.remove('is-over');
      overPane = p;
      if (p) p.classList.add('is-over');
    }
    function autoscroll() {
      scrollRaf = 0;
      if (!drag || !drag.active) return;
      var edge = 56, vh = window.innerHeight, dy = 0;
      if (lastY < edge) dy = -Math.ceil((edge - lastY) / 4);
      else if (lastY > vh - edge) dy = Math.ceil((lastY - (vh - edge)) / 4);
      if (dy) { wrap.scrollTop += dy; scrollRaf = requestAnimationFrame(autoscroll); }
    }
    function endDrag(drop) {
      document.removeEventListener('pointermove', onMove, true);
      document.removeEventListener('pointerup', onUp, true);
      document.removeEventListener('pointercancel', onCancel, true);
      document.removeEventListener('keydown', onDragKey, true);
      var d = drag; drag = null;
      if (ghost && ghost.parentNode) ghost.parentNode.removeChild(ghost);
      ghost = null;
      if (scrollRaf) { cancelAnimationFrame(scrollRaf); scrollRaf = 0; }
      var target = overPane;
      setOver(null);
      if (!d) return;
      d.el.classList.remove('is-drag');
      if (d.active) {
        justDragged = true;
        setTimeout(function () { justDragged = false; }, 0);
        if (drop && target) {
          var key = target.getAttribute('data-drop');
          moveCard(d.id, key === '' ? null : key);
          if (selected === d.id) select(null);
        }
        focusSoon(cardEl[d.id]);
      }
    }
    function onMove(e) {
      if (!drag || e.pointerId !== drag.pid || !e.isTrusted) return;
      lastY = e.clientY;
      if (!drag.active) {
        if (Math.abs(e.clientX - drag.sx) + Math.abs(e.clientY - drag.sy) < 6) return;
        drag.active = true;
        drag.el.classList.add('is-drag');
        ghost = h('div', { class: 'pb-rs-cs-ghost', 'aria-hidden': 'true', text: cardById[drag.id].label });
        wrap.appendChild(ghost);
      }
      ghost.style.transform = 'translate(' + (e.clientX + 12) + 'px,' + (e.clientY + 12) + 'px)';
      setOver(paneAt(e.clientX, e.clientY));
      if (!scrollRaf) scrollRaf = requestAnimationFrame(autoscroll);
      e.preventDefault();
    }
    function onUp(e) { if (drag && e.pointerId === drag.pid) endDrag(true); }
    function onCancel(e) { if (drag && e.pointerId === drag.pid) endDrag(false); }
    function onDragKey(e) { if (e.key === 'Escape' && drag) { e.stopPropagation(); endDrag(false); } }

    wrap.addEventListener('pointerdown', function (e) {
      if (!e.isTrusted || drag || (e.button != null && e.button > 0)) return;
      var c = e.target.closest ? e.target.closest('.pb-rs-cs-card') : null;
      if (!c) return;
      if (e.pointerType === 'touch' && !e.target.closest('.pb-rs-cs-grip')) return;   // a touch elsewhere on the card scrolls the page
      drag = { id: c.getAttribute('data-card'), el: c, sx: e.clientX, sy: e.clientY, pid: e.pointerId, active: false };
      lastY = e.clientY;
      document.addEventListener('pointermove', onMove, true);
      document.addEventListener('pointerup', onUp, true);
      document.addEventListener('pointercancel', onCancel, true);
      document.addEventListener('keydown', onDragKey, true);
    });

    /* ---- finish ---- */
    return new Promise(function (resolve) {
      var confirming = false;

      function finish() {
        syncResult();
        if (drag) endDrag(false);
        if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
        uiFull(false);
        resolve();
      }
      function paintFoot() {
        while (foot.firstChild) foot.removeChild(foot.firstChild);
        foot.removeAttribute('role'); foot.removeAttribute('aria-label');
        if (!confirming) { foot.appendChild(footT); foot.appendChild(doneBtn); return; }
        var n = unsortedIds().length;
        var keep = btn('Keep sorting', null, function () { confirming = false; paintFoot(); render(); focusSoon(doneBtn); });
        var go = btn('Finish anyway', 'solid', finish);
        foot.setAttribute('role', 'alertdialog');
        foot.setAttribute('aria-label', 'Unsorted cards');
        foot.appendChild(h('span', { class: 'pb-rs-cs-foot-t', text: n + (n === 1 ? ' card is' : ' cards are') + ' not in a group yet. Finish anyway?' }));
        foot.appendChild(keep); foot.appendChild(go);
        focusSoon(keep);
      }
      doneBtn.addEventListener('click', function () {
        if (!unsortedIds().length) { finish(); return; }
        confirming = true; paintFoot();
      });

      uiFull(true);
      if (useCats) cats.forEach(function (c) { addGroup(String(c.label == null ? c.id : c.label), String(c.id), true); });
      syncResult();
      render();
      focusSoon(cardEl[order[0]] || doneBtn);
    });
  }

  /* ================================================================== FIRST CLICK */

  function inspectPath(el) {
    var p = guard(function () { return typeof pbInspectName === 'function' ? pbInspectName(el).path : null; });
    if (!p) {
      p = (el.tagName || '').toLowerCase();
      if (el.id) p += '#' + el.id;
    }
    return cut(p, 200);
  }

  function matchesTarget(sel, screenEl, t) {
    if (!sel) return false;
    var found = null;
    try { found = screenEl.querySelectorAll(sel); } catch (e) { found = null; }
    if (found && found.length) {
      for (var i = 0; i < found.length; i++) if (found[i] === t || found[i].contains(t)) return true;
      return false;
    }
    // not a selector that finds anything: match a data-* attribute value (never data-cmp)
    for (var el = t; el && el !== screenEl.parentNode; el = el.parentNode) {
      if (!el.attributes) continue;
      for (var j = 0; j < el.attributes.length; j++) {
        var a = el.attributes[j];
        if (a.name.indexOf('data-') === 0 && a.name !== 'data-cmp' && a.value === sel) return true;
      }
    }
    return false;
  }

  function hitTest(click, screenEl, t, fx, fy) {
    if (!click) return false;
    if (click.target && matchesTarget(String(click.target), screenEl, t)) return true;
    var r = click.rect;
    if (r && typeof r === 'object') {
      var rx = +r.x, ry = +r.y, rw = +r.w, rh = +r.h;
      if (isFinite(rx) && isFinite(ry) && isFinite(rw) && isFinite(rh) && fx >= rx && fx <= rx + rw && fy >= ry && fy <= ry + rh) return true;
    }
    return false;
  }

  function showScreen(id) {
    // The core's quiet reset stages the screen without recording a `reset` + `nav` the participant never made.
    if (typeof S.reset === 'function' && guard(function () { S.reset({ screen: id }); return true; })) return;
    guard(function () { if (typeof pbResetSandbox === 'function') pbResetSandbox(); });
    guard(function () { if (typeof setProtoScreen === 'function' && id) setProtoScreen(id); });
  }

  function clickTask(q, index, total) {
    var tid = q.id, spec = q.click || {};
    var res = result('first-click');
    S.task.begin(q);
    uiStatus('Task ' + (index + 1) + ' of ' + total);

    var scrim = layer('pb-rs-m-scrim', 'First-click task ' + (index + 1) + ' of ' + total);
    var show = btn('Show me', 'solid'), skip = btn('Skip this task', 'quiet');
    var card = h('div', { class: 'pb-rs-m-card', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Task ' + (index + 1) + ' of ' + total }, [
      h('p', { class: 'pb-rs-m-step', text: 'Task ' + (index + 1) + ' of ' + total }),
      h('h2', { class: 'pb-rs-m-title', text: q.text || '' }),
      h('p', { class: 'pb-rs-m-hint', text: 'You will see a screen. Click where you would click first to do this. Nothing will happen when you click.' }),
      h('div', { class: 'pb-rs-m-foot' }, [show, skip])
    ]);
    scrim.appendChild(card);
    focusSoon(show);

    var cleanup = [];
    function tidy() { cleanup.splice(0).forEach(function (f) { guard(f); }); }

    var phase1 = new Promise(function (resolve) {
      show.addEventListener('click', function () { resolve('show'); });
      skip.addEventListener('click', function () { resolve('skip'); });
    });

    return phase1.then(function (which) {
      if (scrim.parentNode) scrim.parentNode.removeChild(scrim);
      if (which === 'skip') return { skipped: true };

      showScreen(spec.screen);
      return new Promise(function (resolve) { requestAnimationFrame(function () { requestAnimationFrame(resolve); }); }).then(function () {
        return new Promise(function (resolve) {
          var shownAt = S.now(), taken = false;
          var pill = h('div', { class: 'pb-rs-fc-pill', role: 'region', 'aria-label': 'First-click task' });
          var pillSkip = btn('Skip', 'quiet', null, { class: 'pb-rs-m-btn pb-rs-m-btn--quiet pb-rs-m-btn--sm' });
          var flip = btn('\u21C5', 'quiet', null, { class: 'pb-rs-m-btn pb-rs-m-btn--quiet pb-rs-m-btn--sm', 'aria-label': 'Move this bar to the top or bottom of the screen', title: 'Move this bar' });
          pill.appendChild(h('span', { class: 'pb-rs-fc-pill-t', text: q.text || 'Click where you would click first.', title: q.text || '' }));
          pill.appendChild(flip);
          pill.appendChild(pillSkip);
          host().appendChild(pill);
          flip.addEventListener('click', function () { pill.classList.toggle('is-top'); });
          pillSkip.addEventListener('click', function () { if (!taken) { taken = true; tidy(); resolve({ skipped: true }); } });
          cleanup.push(function () { if (pill.parentNode) pill.parentNode.removeChild(pill); });

          function onClick(e) {
            if (!e.isTrusted) return;
            var t = e.target;
            var scr = t && t.closest ? t.closest('.proto-screen') : null;
            if (!scr) return;
            e.preventDefault();
            e.stopImmediatePropagation();
            if (taken) return;                 // a double click is swallowed too, never replayed
            taken = true;
            var box = scr.getBoundingClientRect();
            var cx = e.clientX, cy = e.clientY;
            if (!e.detail && !cx && !cy) {       // a keyboard activation has no pointer: use the element's centre
              var tb = t.getBoundingClientRect();
              cx = tb.left + tb.width / 2; cy = tb.top + tb.height / 2;
            }
            var fx = box.width ? clamp01((cx - box.left) / box.width) : 0;
            var fy = box.height ? clamp01((cy - box.top) / box.height) : 0;
            var hit = hitTest(spec, scr, t, fx, fy);
            var out = { x: r4(fx), y: r4(fy), target: inspectPath(t), hit: !!hit, ms: Math.max(0, Math.round(S.now() - shownAt)) };
            res[tid] = out;
            emit('fc-click', { x: out.x, y: out.y, hit: out.hit, target: out.target });
            var dot = h('div', { class: 'pb-rs-fc-dot', 'aria-hidden': 'true', style: 'left:' + cx + 'px;top:' + cy + 'px' });
            host().appendChild(dot);
            cleanup.push(function () { if (dot.parentNode) dot.parentNode.removeChild(dot); });
            if (pill.parentNode) pill.parentNode.removeChild(pill);
            setTimeout(function () { resolve({ out: out }); }, 700);
          }
          document.addEventListener('click', onClick, true);
          cleanup.push(function () { document.removeEventListener('click', onClick, true); });
        });
      });
    }).then(function (r) {
      tidy();
      if (scrim.parentNode) scrim.parentNode.removeChild(scrim);
      if (r.skipped) S.task.end('skipped', 'self');
      else S.task.end(r.out.hit ? 'success' : 'fail', 'criteria');
      return afterTask(q);
    });
  }

  function runFirstClick(ctx) {
    ensureStyle();
    var tasks = tasksOf(ctx, 'click');
    result('first-click');
    var chain = Promise.resolve();
    tasks.forEach(function (q, i) { chain = chain.then(function () { return clickTask(q, i, tasks.length); }); });
    return chain.then(function () { uiStatus(''); }, function (e) { uiStatus(''); throw e; });
  }

  /* ------------------------------------------------------------------ register */

  S.runners['tree-test'] = { run: runTreeTest };
  S.runners['card-sort'] = { run: runCardSort };
  S.runners['first-click'] = { run: runFirstClick };
})();
