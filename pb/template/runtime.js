/* pb shared runtime — the token resolver + composition + interaction helpers that BOTH sites
 * (prototype.html and design-system.html) need to render registry components identically.
 * render.py injects this into each template's runtime marker. Kept verbatim in sync
 * with the shell; edit HERE (the single source), not the inlined copy.
 *
 * Callers must provide, in the same script scope: a `PB_REGISTRY` global (with `.components`,
 * `.tokens`) and a `pbEscape(s)` function (hoisted). The emitted `window[renderCmp*]` functions
 * (from render.py) are what `pbUse` dispatches to.
 */
    var PB_KIND_TO_TYPE = { color:'color', radius:'dimension', space:'dimension', size:'dimension',
      fontSize:'dimension', breakpoint:'dimension', type:'fontFamily', font:'fontFamily',
      fontWeight:'fontWeight', shadow:'shadow', border:'border', opacity:'number', zIndex:'number',
      duration:'duration', cubicBezier:'cubicBezier' };
    function pbKindToType(kind) { return PB_KIND_TO_TYPE[kind] || null; }
    function pbTokenIsAlias(v) { return typeof v === 'string' && v.length >= 2 && v.charAt(0) === '{' && v.charAt(v.length - 1) === '}'; }
    function pbDisplayKind(name, type) {
      if (type === 'color') return 'color';
      if (type === 'fontFamily') return 'font';
      if (type === 'fontWeight') return 'fontWeight';
      if (type === 'shadow') return 'shadow';
      if (type === 'dimension') {
        var n = (name || '').toLowerCase();
        if (n.indexOf('radius') === 0 || n.indexOf('-radius') !== -1) return 'radius';
        if (n.indexOf('space') === 0 || n.indexOf('gap') === 0 || n.indexOf('pad') === 0 || n.indexOf('-space') !== -1 || n.indexOf('-gap') !== -1) return 'space';
        if (n.indexOf('text') === 0 || n.indexOf('font-size') === 0 || n.indexOf('fontsize') === 0) return 'fontSize';
        return 'size';
      }
      return 'other';
    }
    function pbWalkTokens(doc, prefix, inheritedType, out) {
      if (!doc || typeof doc !== 'object') return;
      var gt = (doc['$type'] != null) ? doc['$type'] : inheritedType;
      Object.keys(doc).forEach(function (k) {
        if (k.charAt(0) === '$') return;
        var node = doc[k];
        if (!node || typeof node !== 'object') return;
        var path = prefix ? (prefix + '-' + k) : k;
        var hasDtcg = ('$value' in node);
        var hasLegacy = ('value' in node) && (typeof node.value !== 'object');
        if (hasDtcg || hasLegacy) {
          out.push({ name: path,
            value: hasDtcg ? node['$value'] : node.value,
            type: hasDtcg ? (node['$type'] != null ? node['$type'] : gt) : pbKindToType(node.kind) });
        } else {
          pbWalkTokens(node, path, gt, out);
        }
      });
    }
    function pbResolveTokens(doc) {
      var list = []; pbWalkTokens(doc, '', null, list);
      var byPath = {}; list.forEach(function (t) { byPath[t.name] = t; });
      function res(v, seen) {
        if (!pbTokenIsAlias(v)) return v;
        var ref = v.slice(1, -1).split('.').join('-');
        if (!byPath[ref] || (seen && seen[ref])) return v;
        seen = seen || {}; seen[ref] = 1;
        return res(byPath[ref].value, seen);
      }
      var flat = {}, byName = {};
      list.forEach(function (t) {
        var rv = res(t.value);
        if (typeof rv === 'string' || typeof rv === 'number') flat[t.name] = rv;
        byName[t.name] = { value: rv, type: t.type, displayKind: pbDisplayKind(t.name, t.type) };
      });
      return { flat: flat, byName: byName };
    }
    // Memoized byName view of the registry tokens (keyed by CSS-var name, no leading --).
    var PB_TOKENS_RESOLVED = null;
    function pbTokensByName() {
      if (!PB_TOKENS_RESOLVED) {
        PB_TOKENS_RESOLVED = pbResolveTokens((typeof PB_REGISTRY !== 'undefined' && PB_REGISTRY && PB_REGISTRY.tokens) || {});
      }
      return PB_TOKENS_RESOLVED.byName;
    }

    // Apply registry design tokens to the PRODUCT — never to the tool.
    //
    // They used to land on :root, so every surface of the tool inherited the project's `--brand`:
    // an orange project got an orange tab strip. Now they are scoped to `.pb-product` (everything
    // a project renders sits inside one; the tool's chrome never does), and the tool speaks in its
    // own `--pb-*` vocabulary (chrome.css). A project can be any colour and the tool does not move.
    //
    //  - Written through the CSSOM, not by concatenating a stylesheet: `style.setProperty` sanitises
    //    a value, so a hostile token like `red;} body{display:none` stays an invalid value instead
    //    of becoming a rule. (The :root version had that property for free; keep it.)
    //  - `pb-*` is reserved for the tool. A registry cannot overwrite it.
    //  - The tool may opt in to a project value on purpose (the browser mock's favicon is the
    //    project's colour, because in real Chrome the site supplies it): every token is also
    //    published as `--prj-<name>` on :root. Nothing reads those by accident.
    function applyRegistryTokens(reg) {
      if (!reg || !reg.tokens) return;
      const resolved = pbResolveTokens(reg.tokens);
      const names = Object.keys(resolved.flat).filter(function (n) { return n.indexOf('pb-') !== 0; });
      let el = document.getElementById('pb-project-tokens');
      if (!el) {
        el = document.createElement('style');
        el.id = 'pb-project-tokens';
        document.head.appendChild(el);
      }
      const sheet = el.sheet;
      if (sheet) {
        while (sheet.cssRules.length) sheet.deleteRule(0);
        sheet.insertRule('.pb-product{}', 0);
        const decl = sheet.cssRules[0].style;
        names.forEach(function (name) { decl.setProperty('--' + name, resolved.flat[name]); });
      }
      const root = document.documentElement;
      names.forEach(function (name) { root.style.setProperty('--prj-' + name, resolved.flat[name]); });
    }

    // ── Composition runtime (component-first / atomic design) ───────────────────────────
    // Every render body above the atom level is a COMPOSITION TREE: it emits layout
    // containers + pbUse() calls to lower-level components — never raw controls. This is
    // what lint's R-COMPOSE enforces and what the Figma bridge lowers 1:1 to an INSTANCE tree.
    var PB_ORG_BY_ID_CACHE = null;
    function pbOrgById() {
      if (!PB_ORG_BY_ID_CACHE) {
        PB_ORG_BY_ID_CACHE = {};
        ((typeof PB_REGISTRY !== 'undefined' && PB_REGISTRY && PB_REGISTRY.components) || [])
          .forEach(function (c) { if (c && c.id) PB_ORG_BY_ID_CACHE[c.id] = c; });
      }
      return PB_ORG_BY_ID_CACHE;
    }
    // Render a child component by its registry id, returning its HTML string. A missing target
    // is a VISIBLE marker (never a silent empty) so a broken composition is obvious in preview.
    function pbUse(orgId, props) {
      var c = pbOrgById()[orgId];
      var fn = c && c.renderFn;
      // The child's root is stamped with the id it was composed from, so the design-system site
      // (and spec_measure.py) can find an `instance` part on a live specimen.
      // A FUNCTION replacer, not a replacement string: `$&`, `$1` or `$'` in a component id would
      // otherwise be expanded by String.replace into the markup it is stamped onto.
      if (fn && typeof window[fn] === 'function') return String(window[fn](props || {})).replace(/^(\s*<[a-zA-Z][\w-]*)/, function (m, open) { return open + ' data-cmp="' + pbEscape(orgId) + '"'; });
      if (typeof console !== 'undefined' && console.warn) console.warn('pbUse: no render for component', orgId);
      return '<span data-pb-missing="' + pbEscape(orgId) + '" style="display:inline-block;padding:2px 6px;outline:1px dashed var(--danger);color:var(--danger);font:11px monospace">?' + pbEscape(orgId) + '</span>';
    }
    // Named-content passthrough (a slot value that may be null/undefined).
    function pbSlot(html) { return html == null ? '' : String(html); }
    // A token-styled auto-layout container (a layout <div>, allowed above the atom level).
    // spec: { dir:'row'|'col', gap, padding, align, justify, maxWidth, grow } — gap/padding/
    // maxWidth are token names (CSS-var names without --). Children is an array of HTML strings.
    function pbFrame(spec, children) {
      spec = spec || {};
      var s = ['display:flex', 'flex-direction:' + (spec.dir === 'row' ? 'row' : 'column')];
      if (spec.gap) s.push('gap:var(--' + spec.gap + ')');
      if (spec.padding) s.push('padding:var(--' + spec.padding + ')');
      if (spec.align) s.push('align-items:' + spec.align);
      if (spec.justify) s.push('justify-content:' + spec.justify);
      if (spec.maxWidth) s.push('max-width:var(--' + spec.maxWidth + ')', 'width:100%');
      if (spec.grow) s.push('flex:1 1 auto');
      return '<div class="pb-frame" style="' + s.join(';') + '">' + (children || []).join('') + '</div>';
    }

    // ── Reusable declarative interactions (any component opts in via onclick=) ──────────
    // A custom checkbox toggles its own visual state; a header checkbox toggles a whole
    // table's rows; a [data-sort] header sorts its table by that column (numeric-aware,
    // direction-toggling). Pure DOM — no app state, so a click never dirties registry.json.
    function pbToggleCheck(el) {
      var c = el.getAttribute('data-checked') !== 'true';
      el.setAttribute('data-checked', c ? 'true' : 'false');
      el.style.background = c ? 'var(--color-brand-primary)' : 'var(--color-bg-surface)';
      el.style.borderColor = c ? 'var(--color-brand-primary)' : 'var(--color-border)';
      el.textContent = c ? '✓' : '';
    }
    function pbToggleAll(header) {
      var on = header.getAttribute('data-checked') !== 'true';
      pbToggleCheck(header);
      var tbl = header.closest('table'); if (!tbl) return;
      Array.prototype.forEach.call(tbl.querySelectorAll('tbody [data-checkbox]'), function (x) {
        if ((x.getAttribute('data-checked') === 'true') !== on) pbToggleCheck(x);
      });
    }
    function pbSortTable(th) {
      var tbl = th.closest('table'); if (!tbl || !tbl.tBodies[0]) return;
      var body = tbl.tBodies[0];
      var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
      var asc = th.getAttribute('data-dir') !== 'asc';
      Array.prototype.forEach.call(th.parentNode.children, function (h) {
        h.removeAttribute('data-dir');
        var c = h.querySelector('[data-caret]'); if (c) c.textContent = '↕';
      });
      th.setAttribute('data-dir', asc ? 'asc' : 'desc');
      var car = th.querySelector('[data-caret]'); if (car) car.textContent = asc ? '↑' : '↓';
      var rows = Array.prototype.slice.call(body.rows);
      rows.sort(function (p, q) {
        var pc = p.cells[idx], qc = q.cells[idx];
        var x = pc ? (pc.getAttribute('data-sortval') || pc.textContent).trim() : '';
        var y = qc ? (qc.getAttribute('data-sortval') || qc.textContent).trim() : '';
        var nx = parseFloat(x), ny = parseFloat(y);
        var r = (!isNaN(nx) && !isNaN(ny)) ? (nx - ny) : String(x).localeCompare(String(y));
        return asc ? r : -r;
      });
      rows.forEach(function (r) { body.appendChild(r); });
    }

    /* ── data-preserve — keep what the user did across a re-render ──────────────────────
     * Re-rendering a screen throws away everything the user typed, checked, scrolled or
     * opened underneath it. The imperative fix is for every caller to pass a list of
     * element ids to restore; measured on a real project, 24 call sites carried such a
     * list, each kept in step with the markup by hand, and the first version of it
     * restored `checked` only — so a search box came back empty and the surface came
     * back fully unfiltered. Declarative instead: the ELEMENT says it is worth keeping.
     *   data-preserve                  keep whatever suits the element
     *   data-preserve="value scroll"   keep only these (value · checked · scroll · open · active · disc)
     *   data-preserve-key="<k>"        identity across the re-render (default: id, then position)
     * Usage: pbPreserve(function () { renderMyScreen(); });
     *
     * STATE, NEVER THE CARET. Focus and selection are deliberately NOT restored (D-26): putting
     * focus back mid-edit destroys an in-flight IME composition, which on a Vietnamese keyboard
     * is most of the typing. This verb is for a re-render the user triggered by clicking
     * something else — a save, a filter apply. A surface that repaints WHILE they type must
     * render its input once and repaint only the hosts around it. tests/verbs_browser.py §3
     * pins the boundary in a real browser, so adding focus-restore has to come past that line.
     */
    var PB_PRESERVE_DEFAULT = { INPUT: 'value', SELECT: 'value', TEXTAREA: 'value', DETAILS: 'open' };
    function pbPreserveKey(el, i) {
      return el.getAttribute('data-preserve-key') || el.id || ('pb-preserve-' + i);
    }
    function pbPreserveWhat(el) {
      var raw = (el.getAttribute('data-preserve') || '').trim();
      if (raw) return raw.split(/\s+/);
      if (el.tagName === 'INPUT' && (el.type === 'checkbox' || el.type === 'radio')) return ['checked'];
      if (el.hasAttribute('data-checkbox') || el.hasAttribute('data-checked')) return ['checked'];
      return [PB_PRESERVE_DEFAULT[el.tagName] || 'scroll'];
    }
    function pbPreserveIsNative(el) { return el.type === 'checkbox' || el.type === 'radio'; }
    function pbPreserveCapture(root) {
      var snap = {};
      Array.prototype.forEach.call((root || document).querySelectorAll('[data-preserve]'), function (el, i) {
        var rec = {};
        pbPreserveWhat(el).forEach(function (w) {
          if (w === 'value') rec.value = el.value;
          else if (w === 'checked') rec.checked = pbPreserveIsNative(el) ? !!el.checked : el.getAttribute('data-checked') === 'true';
          else if (w === 'scroll') { rec.scrollTop = el.scrollTop; rec.scrollLeft = el.scrollLeft; }
          else if (w === 'open') rec.open = !!el.open;
          else if (w === 'active') rec.active = el.classList.contains('active');
          else if (w === 'disc') rec.disc = el.classList.contains('is-open');   // a pbDisclosure root
        });
        snap[pbPreserveKey(el, i)] = rec;
      });
      return snap;
    }
    function pbPreserveFire(el) {
      ['input', 'change'].forEach(function (name) {
        var ev;
        try { ev = new Event(name, { bubbles: true }); }
        catch (e) { ev = document.createEvent('Event'); ev.initEvent(name, true, false); }
        el.dispatchEvent(ev);
      });
    }
    function pbPreserveRestore(root, snap) {
      var changed = [];
      Array.prototype.forEach.call((root || document).querySelectorAll('[data-preserve]'), function (el, i) {
        var rec = snap[pbPreserveKey(el, i)];
        if (!rec) return;
        if ('value' in rec && el.value !== rec.value) { el.value = rec.value; changed.push(el); }
        if ('checked' in rec) {
          if (pbPreserveIsNative(el)) { if (el.checked !== rec.checked) { el.checked = rec.checked; changed.push(el); } }
          else if ((el.getAttribute('data-checked') === 'true') !== rec.checked) { pbToggleCheck(el); changed.push(el); }
        }
        if ('open' in rec) el.open = rec.open;
        if ('active' in rec) el.classList.toggle('active', rec.active);
        if ('disc' in rec) pbDiscSet(el.getAttribute('data-pb-disc'), rec.disc, true);   // quiet: a restore is not a toggle
        if ('scrollTop' in rec) { el.scrollTop = rec.scrollTop; el.scrollLeft = rec.scrollLeft; }
      });
      // Restore everything FIRST, notify SECOND. A control's own change handler usually
      // recomputes against its siblings (a composed filter reads every criterion at once),
      // so firing as we go would compose against controls not yet put back.
      changed.forEach(pbPreserveFire);
      return changed.length;
    }
    function pbPreserve(rerender, root) {
      var snap = pbPreserveCapture(root);
      rerender();
      return pbPreserveRestore(root, snap);
    }

    /* ── data-machine / data-step — one wizard, declared once ───────────────────────────
     * Four copies of one six-state wizard on a real project carried 63 bespoke
     * `data-<prefix>-state` attributes and a per-copy CSS block to show the matching pane.
     * The states differ per project; the MACHINE does not.
     *   [data-machine="<name>"]        the root
     *   [data-step="<state>"]          its current state, reflected — CSS may select on it
     *   [data-step-pane="<state>"]     a pane, shown only while the root is in <state>
     *   [data-step-go="<state>"]       a control that moves the machine on click
     *   [data-step-initial="<state>"]  where to start (default: the first pane)
     *   [data-step-dot="<state>"]      a progress marker; gets data-current="true|false"
     * pbSetStep(x, state) is the escape hatch for a transition a click cannot express —
     * an upload that validates and then lands on either 'preview' or 'invalid'.
     */
    function pbMachine(x) {
      if (!x) return null;
      if (x.nodeType === 1) return x.closest('[data-machine]');
      return document.querySelector('[data-machine="' + String(x).replace(/"/g, '\\"') + '"]');
    }
    function pbStep(x) {
      var root = pbMachine(x);
      if (!root) return null;
      var cur = root.getAttribute('data-step') || root.getAttribute('data-step-initial');
      if (cur) return cur;
      var first = root.querySelector('[data-step-pane]');
      return first ? first.getAttribute('data-step-pane') : null;
    }
    function pbSyncSteps(x) {
      var root = pbMachine(x);
      if (!root) return null;
      var cur = pbStep(root);
      Array.prototype.forEach.call(root.querySelectorAll('[data-step-pane]'), function (p) {
        if (pbMachine(p) !== root) return;                 // a nested machine owns its own panes
        p.hidden = p.getAttribute('data-step-pane') !== cur;
      });
      Array.prototype.forEach.call(root.querySelectorAll('[data-step-dot]'), function (d) {
        if (pbMachine(d) !== root) return;
        d.setAttribute('data-current', d.getAttribute('data-step-dot') === cur ? 'true' : 'false');
      });
      return cur;
    }
    function pbSetStep(x, state) {
      var root = pbMachine(x);
      if (!root) return null;
      root.setAttribute('data-step', state);
      return pbSyncSteps(root);
    }
    function pbSyncMachines(host) {
      Array.prototype.forEach.call((host || document).querySelectorAll('[data-machine]'), function (root) {
        if (!root.getAttribute('data-step')) {
          var s = pbStep(root);
          if (s) root.setAttribute('data-step', s);
        }
        pbSyncSteps(root);
      });
    }
    function pbStepClick(target) {
      var go = (target && target.closest) ? target.closest('[data-step-go]') : null;
      if (!go) return false;
      pbSetStep(go, go.getAttribute('data-step-go'));
      return true;
    }

    /* =====================================================================================
     * THE TOOL'S OWN CHROME, shared by both sites (wave 2 of tool-chrome r2).
     * The project button and its menu, the Project settings dialog, the tool toast and the ⌘K
     * palette. One copy here so the prototype and the design-system site mount the same thing.
     * Everything below is a function declaration or an inert literal: this file is also executed
     * in a bare node vm by lint_registry.py, where there is no document — nothing runs until a
     * shell calls pbUiInstall().
     * Styles live in chrome.css (.pb-pj, .pb-menu, .pb-dlg, .pb-seg, .pb-toast, .pb-cmdk).
     * ===================================================================================== */
    var PB_UI_ICONS = {
      chevron: '<path d="M6 9l6 6 6-6"/>',
      chevronR: '<path d="M9 6l6 6-6 6"/>',
      sliders: '<path d="M4 7h9M18 7h2M4 17h3M12 17h8"/><circle cx="15.5" cy="7" r="2.2"/><circle cx="9.5" cy="17" r="2.2"/>',
      sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.5 1.5M17.2 17.2l1.5 1.5M5.3 18.7l1.5-1.5M17.2 6.8l1.5-1.5"/>',
      moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
      auto: '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17"/><path d="M12 3.5a8.5 8.5 0 0 1 0 17z" fill="currentColor"/>',
      search: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
      hourglass: '<path d="M6.5 3h11M6.5 21h11"/><path d="M8 3v3.2a4 4 0 0 0 1.5 3.1L12 11.5l2.5-2.2A4 4 0 0 0 16 6.2V3"/><path d="M8 21v-3.2a4 4 0 0 1 1.5-3.1L12 12.5l2.5 2.2a4 4 0 0 1 1.5 3.1V21"/>',
      pin: '<path d="M12 16v5.5M8 3h8M9 3.5l.6 5.7L6.5 13v2.5h11V13l-3.1-3.8.6-5.7"/>',
      pinOff: '<path d="M12 16v5.5M8 3h8M9 3.5l.6 5.7L6.5 13v2.5h11V13l-3.1-3.8.6-5.7"/><path d="M4 4l16 16"/>',
      x: '<path d="M6 6l12 12M18 6L6 18"/>',
      play: '<path d="M7.5 5v14l11-7z"/>',
      playAll: '<path d="M4.5 5v14l9-7zM18 5v14"/>',
      pass: '<circle cx="12" cy="12" r="9"/><path d="M8 12.3l2.7 2.7L16 9.5"/>',
      fail: '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
      blocked: '<circle cx="12" cy="12" r="9"/><path d="M5.6 5.6l12.8 12.8"/>',
      pending: '<circle cx="12" cy="12" r="8"/>',
      stale: '<path d="M20 12a8 8 0 1 1-2.4-5.7M20 4v5h-5"/>',
      manual: '<rect x="4.5" y="4.5" width="15" height="15" rx="2.5"/>',
      running: '<path d="M12 3a9 9 0 1 0 9 9"/>',
      copy: '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.5a2 2 0 0 0 2 2h2.5"/>',
      reload: '<path d="M20 12a8 8 0 1 1-2.4-5.7M20 4v5h-5"/>',
      flag: '<path d="M6 21V4M6 4h11l-2 4 2 4H6"/>',
      list: '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
      users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6"/>',
      layers: '<path d="M12 3.5l9 4.8-9 4.8-9-4.8z"/><path d="M3 12.6l9 4.8 9-4.8M3 16.8l9 4.8 9-4.8"/>',
      phone: '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
      check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
      cmd: '<path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z"/>',
      arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
      book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/>'
    };
    function pbUiEsc(s) {
      return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
    }
    /* A tool glyph: 24-unit grid, 1.75 stroke, sized by its class (16px inline, 20px in an
       icon-only control — chrome.css .pb-ico / .pb-ico--lg). Always aria-hidden: the control names it. */
    function pbUiIcon(name, cls) {
      return '<svg class="pb-ico' + (cls ? ' ' + cls : '') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
        + ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (PB_UI_ICONS[name] || '') + '</svg>';
    }
    /* Per-viewer conveniences only (a pin, a theme). Storage can be blocked or empty; nothing
       here may depend on it. */
    function pbUiStore(key, value) {
      try {
        if (arguments.length < 2) return window.localStorage.getItem(key);
        if (value == null) window.localStorage.removeItem(key); else window.localStorage.setItem(key, String(value));
      } catch (e) { /* blocked storage: the default applies */ }
      return null;
    }
    function pbUiTyping(t) {
      return !!(t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable));
    }
    /* Something modal is up: a <dialog>, the ⌘K palette, or the shell's older dialog backdrop.
       Single-key shortcuts (S, R) stand down while one is. */
    function pbUiModalOpen() {
      return !!document.querySelector('dialog[open], .pb-cmdk, .pb-dialog-backdrop');
    }

    /* ---- theme: System · Light · Dark (the head bootstrap owns the attribute; this is the control) */
    function pbUiTheme() {
      var t = document.documentElement.getAttribute('data-theme');
      return t === 'light' || t === 'dark' ? t : 'system';
    }
    function pbUiSetTheme(v) {
      if (typeof window.pbSetTheme === 'function') window.pbSetTheme(v);
      var cur = pbUiTheme();
      Array.prototype.forEach.call(document.querySelectorAll('[data-pb-theme]'), function (b) {
        b.setAttribute('aria-checked', String(b.getAttribute('data-pb-theme') === cur));
      });
    }
    function pbUiThemeLabel(v) { return v === 'light' ? 'Light' : v === 'dark' ? 'Dark' : 'System'; }
    /* The 3-way toggle, in the project menu and in the settings dialog — one control, two places.
       `role` is menuitemradio inside the menu and radio inside the dialog. */
    function pbUiThemeSeg(role) {
      var cur = pbUiTheme();
      return '<div class="pb-seg" role="' + (role === 'radio' ? 'radiogroup' : 'group') + '" aria-label="Theme">'
        + ['system', 'light', 'dark'].map(function (v) {
          return '<button type="button" class="pb-seg-btn" role="' + (role || 'radio') + '" data-pb-theme="' + v + '"'
            + ' aria-checked="' + (v === cur) + '"' + (role === 'menuitemradio' ? ' data-pb-menu-item' : '') + '>'
            + pbUiIcon(v === 'system' ? 'auto' : v === 'light' ? 'sun' : 'moon') + '<span>' + pbUiThemeLabel(v) + '</span></button>';
        }).join('') + '</div>';
    }
    function pbUiCycleTheme() {
      var order = ['system', 'light', 'dark'], n = order[(order.indexOf(pbUiTheme()) + 1) % 3];
      pbUiSetTheme(n);
      pbUiToast('Theme: ' + pbUiThemeLabel(n));
    }

    /* ---- the tool toast: bottom-right, themed. The PRODUCT has its own (pbToast in the prototype
       shell, bottom-centre of the stage, in the project's tokens) — a tool message never goes through it.
       pbUiToast(msg, { note, tone }): `note` is a second, smaller line; `tone` is 'default' (ink) ·
       'pass' · 'fail'. A bare string as the second argument is the note (the pre-round-3 signature). */
    function pbUiToast(msg, opts) {
      if (typeof opts === 'string') opts = { note: opts };
      opts = opts || {};
      var note = opts.note, tone = opts.tone === 'pass' || opts.tone === 'fail' ? opts.tone : 'default';
      var el = document.getElementById('pb-ui-toast');
      if (!el) {
        el = document.createElement('div'); el.id = 'pb-ui-toast'; el.className = 'pb-toast';
        el.setAttribute('role', 'status'); el.setAttribute('aria-live', 'polite');
        document.body.appendChild(el);
      }
      el.classList.remove('pb-toast--pass', 'pb-toast--fail');
      if (tone !== 'default') el.classList.add('pb-toast--' + tone);
      el.innerHTML = pbUiEsc(msg) + (note ? '<small>' + pbUiEsc(note) + '</small>' : '');
      void el.offsetWidth;
      el.classList.add('is-on');
      clearTimeout(el._t);
      el._t = setTimeout(function () { el.classList.remove('is-on'); }, note ? 5200 : 2400);
    }
    function pbUiCopy(text, label, note) {   // `note` replaces the echoed text under the toast ('' = none): a long block is not echoed
      var done = function () { pbUiToast(label || 'Copied', note === undefined ? text : note); };
      try {
        if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(text).then(done, done); return; }
      } catch (e) { /* fall through */ }
      var ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); } catch (e) { /* the toast still shows the text */ }
      ta.remove(); done();
    }

    /* ---- the project button (bar, far left) + its menu ---------------------------------- */
    function pbUiShortName(name) {
      var n = String(name || '').trim();
      var i = n.indexOf(' — ');
      return i > 0 ? n.slice(0, i) : n;
    }
    function pbUiInitials(name) {
      var words = pbUiShortName(name).split(/[\s\-_.]+/).filter(Boolean);
      var s = words.length > 1 ? words[0].charAt(0) + words[1].charAt(0) : (words[0] || 'pb').slice(0, 2);
      return s.toUpperCase();
    }
    function pbUiProjectButtonHTML(meta, version) {
      var full = (meta && meta.name) || 'Untitled project';
      return '<div class="pb-pj-wrap">'
        + '<button type="button" class="pb-pj" id="pb-pj" aria-haspopup="menu" aria-expanded="false" aria-controls="pb-pj-menu"'
        + ' title="' + pbUiEsc(full) + '" aria-label="Project: ' + pbUiEsc(full) + '">'
        + '<span class="pb-pj-sq" aria-hidden="true">' + pbUiEsc(pbUiInitials(full)) + '</span>'
        + '<span class="pb-pj-nm">' + pbUiEsc(pbUiShortName(full)) + '</span>' + pbUiIcon('chevron', 'pb-pj-car') + '</button>'
        + '<div class="pb-menu" id="pb-pj-menu" role="menu" aria-label="Project" hidden>'
        + '<button type="button" class="pb-menu-it" role="menuitem" data-pb-menu-item data-pb-act="settings">'
        + pbUiIcon('sliders') + '<span>Project settings…</span></button>'
        + '<div class="pb-menu-row"><span class="pb-menu-lbl" id="pb-pj-theme-l">Theme</span>' + pbUiThemeSeg('menuitemradio') + '</div>'
        + '<div class="pb-menu-sep" role="separator"></div>'
        + '<span class="pb-menu-ver">pb v' + pbUiEsc(version || '') + '</span>'
        + '</div></div>';
    }
    /* opts: { meta, version, onSettings() } — returns nothing; the menu wires itself. */
    function pbUiMountProjectButton(host, opts) {
      if (!host) return;
      host.innerHTML = pbUiProjectButtonHTML(opts.meta, opts.version);
      var btn = host.querySelector('#pb-pj'), menu = host.querySelector('#pb-pj-menu');
      var items = function () {
        return Array.prototype.filter.call(menu.querySelectorAll('[data-pb-menu-item]'), function (n) { return n.offsetParent !== null; });
      };
      function close(refocus) {
        if (menu.hidden) return;
        menu.hidden = true; btn.setAttribute('aria-expanded', 'false');
        document.removeEventListener('mousedown', outside, true);
        if (refocus) btn.focus();
      }
      function outside(e) { if (!host.contains(e.target)) close(false); }
      function open(focusLast) {
        menu.hidden = false; btn.setAttribute('aria-expanded', 'true');
        document.addEventListener('mousedown', outside, true);
        var list = items(); if (list.length) list[focusLast ? list.length - 1 : 0].focus();
      }
      btn.addEventListener('click', function () { if (menu.hidden) open(false); else close(true); });
      btn.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); open(e.key === 'ArrowUp'); }
      });
      menu.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(true); return; }
        if (e.key === 'Tab') { close(false); return; }
        var list = items(), i = list.indexOf(document.activeElement), n = null;
        if (e.key === 'ArrowDown') n = list[(i + 1) % list.length];
        else if (e.key === 'ArrowUp') n = list[(i - 1 + list.length) % list.length];
        else if (e.key === 'Home') n = list[0];
        else if (e.key === 'End') n = list[list.length - 1];
        else if ((e.key === 'ArrowRight' || e.key === 'ArrowLeft') && document.activeElement.hasAttribute('data-pb-theme')) {
          var seg = Array.prototype.slice.call(menu.querySelectorAll('[data-pb-theme]')), j = seg.indexOf(document.activeElement);
          n = seg[(j + (e.key === 'ArrowRight' ? 1 : -1) + seg.length) % seg.length];
        }
        if (n) { e.preventDefault(); n.focus(); }
      });
      menu.addEventListener('click', function (e) {
        var t = e.target.closest('button'); if (!t) return;
        if (t.hasAttribute('data-pb-theme')) { pbUiSetTheme(t.getAttribute('data-pb-theme')); return; }
        if (t.getAttribute('data-pb-act') === 'settings') { close(false); if (opts.onSettings) opts.onSettings(btn); }
      });
    }

    /* ---- Project settings: the one place a project's name and its design system are set ----
       opts: { meta, viewOnly, onSaved(meta), returnFocus }.
       Editable only when /pb:preview served the page (window.PB_PREVIEW, injected by serve.py)
       over http. A shared file shows the same fields read-only, with a prompt to paste into Claude Code for each. */
    var PB_UI_FIGMA_RE = /^https:\/\/(www\.)?figma\.com\/(file|design)\/\S+$/i;
    function pbUiCanSaveMeta(viewOnly) {
      return !viewOnly && /^https?:$/.test(location.protocol) && !!(window.PB_PREVIEW && window.PB_PREVIEW.meta);
    }
    function pbUiOpenSettings(opts) {
      var meta = (opts && opts.meta) || {};
      var ds = (meta.designSystem && typeof meta.designSystem === 'object') ? meta.designSystem : {};
      var edit = pbUiCanSaveMeta(opts && opts.viewOnly);
      var old = document.getElementById('pb-settings'); if (old) old.remove();
      var d = document.createElement('dialog');
      d.className = 'pb-dlg'; d.id = 'pb-settings'; d.setAttribute('aria-labelledby', 'pb-settings-t');
      var ro = edit ? '' : ' readonly aria-readonly="true"';
      var field = function (id, label, note, value, extra, help) {
        return '<div class="pb-fld"><label for="' + id + '">' + label + (note ? '<span class="pb-fld-note">' + note + '</span>' : '') + '</label>'
          + '<input id="' + id + '" autocomplete="off" spellcheck="false" value="' + pbUiEsc(value || '') + '" aria-describedby="' + id + '-m"' + ro + (extra || '') + '>'
          + '<div class="pb-fld-m" id="' + id + '-m">' + (help || '') + '</div></div>';
      };
      // The read-only dialog hands the viewer a plain sentence to paste into Claude Code, one per field it
      // shows. A value sits in double quotes: a backslash and a double quote inside it are escaped, so a name
      // like `The "Final" app` cannot end the quoted part early.
      var q = function (v) { return String(v == null ? '' : v).replace(/\\/g, '\\\\').replace(/"/g, '\\"'); };
      var cmds = [
        ['project name', 'Set this project\'s name to "' + q(meta.name || '<name>') + '"'],
        ['design system name', 'Set this project\'s design system name to "' + q(ds.name || '<name>') + '"'],
        ['Figma file', 'Set this project\'s Figma file link to "' + q(ds.designLink || '<figma link>') + '"']
      ];
      d.innerHTML = '<div class="pb-dlg-h"><h2 id="pb-settings-t">Project settings</h2>'
        + '<button type="button" class="pb-ib" data-pb-close title="Close" aria-label="Close">' + pbUiIcon('x', 'pb-ico--lg') + '</button></div>'
        + '<form class="pb-dlg-b" method="dialog" novalidate>'
        + field('pb-set-name', 'Project name', 'required', meta.name, ' required', 'Named on the bar and in every hand-off.')
        + field('pb-set-ds', 'Design system name', 'required', ds.name, ' required',
                'Shown in hand-off files and as the Figma library name.')
        + field('pb-set-fig', 'Figma file for this project', 'optional', ds.designLink, ' inputmode="url" placeholder="https://www.figma.com/design/…"',
                'A figma.com/file/… or figma.com/design/… link.')
        + '<div class="pb-fld"><span class="pb-fld-l" id="pb-set-theme-l">Theme</span>' + pbUiThemeSeg('radio')
        + '<div class="pb-fld-m">Yours only — kept in this browser, not in the project.</div></div>'
        + (edit ? '' : '<div class="pb-dlg-ro"><p>Open through <code>/pb:preview</code> to edit. Or paste one of these into Claude Code:</p>'
            + cmds.map(function (c) {
                return '<span class="pb-cmd"><code>' + pbUiEsc(c[1]) + '</code><button type="button" class="pb-ib pb-ib--sm" data-pb-copy="' + pbUiEsc(c[1])
                  + '" title="Copy the ' + pbUiEsc(c[0]) + ' prompt" aria-label="Copy the ' + pbUiEsc(c[0]) + ' prompt">' + pbUiIcon('copy') + '</button></span>';
              }).join('')
            + '</div>')
        + '<p class="pb-fld-err" id="pb-set-err" role="alert" hidden></p>'
        + '</form>'
        + '<div class="pb-dlg-f">' + (edit
            ? '<button type="button" class="pb-btn" data-pb-close>Cancel</button><button type="button" class="pb-btn pb-btn--solid" id="pb-set-save">Save</button>'
            : '<button type="button" class="pb-btn" data-pb-close>Close</button>') + '</div>';
      document.body.appendChild(d);
      var $ = function (s) { return d.querySelector(s); };
      var name = $('#pb-set-name'), dsn = $('#pb-set-ds'), fig = $('#pb-set-fig'), err = $('#pb-set-err');
      var helpDs = 'Shown in hand-off files and as the Figma library name.', helpFig = 'A figma.com/file/… or figma.com/design/… link.';
      function mark(inp, msg, help, warn) {
        var m = d.querySelector('#' + inp.id + '-m');
        if (!warn) inp.setAttribute('aria-invalid', String(!!msg));
        m.className = 'pb-fld-m' + (msg ? (warn ? ' is-warn' : ' is-err') : '');
        m.innerHTML = msg ? pbUiIcon('flag') + '<span>' + pbUiEsc(msg) + '</span>' : pbUiEsc(help || '');
        return !msg;
      }
      var vName = function () { return mark(name, name.value.trim() ? '' : 'Required', 'Named on the bar and in every hand-off.'); };
      var vDs = function () { return mark(dsn, dsn.value.trim() ? '' : 'Required — hand-off and Figma push need it', helpDs); };
      // A non-Figma link the project already carries is a warning (kept as it is), not a blocker; a changed one must be a Figma link.
      var figOrig = String(ds.designLink || '').trim();
      var vFig = function () {
        var v = fig.value.trim();
        if (v && !PB_UI_FIGMA_RE.test(v)) {
          if (v === figOrig) {
            fig.setAttribute('aria-invalid', 'false');
            mark(fig, 'Not a figma.com/file/… or figma.com/design/… link — kept as it is; hand-off and the Figma push will not use it', helpFig, true);
            return true;
          }
          return mark(fig, 'Must be a figma.com/file/… or figma.com/design/… link', helpFig);
        }
        return mark(fig, '', helpFig);
      };
      // A missing design-system name is a real gap in the project, so it is said on open — in an
      // editable dialog as the field's error, in a read-only one as a note.
      if (edit) { vDs(); name.addEventListener('input', vName); dsn.addEventListener('input', vDs); fig.addEventListener('input', vFig); }
      else if (!String(ds.name || '').trim()) mark(dsn, 'Not set — hand-off and Figma push need it', helpDs, true);
      d.addEventListener('click', function (e) {
        if (e.target === d || e.target.closest('[data-pb-close]')) { d.close(); return; }
        var c = e.target.closest('[data-pb-copy]'); if (c) { pbUiCopy(c.getAttribute('data-pb-copy'), 'Copied the prompt'); return; }
        var t = e.target.closest('[data-pb-theme]'); if (t) pbUiSetTheme(t.getAttribute('data-pb-theme'));
      });
      d.addEventListener('keydown', function (e) {
        var t = e.target;
        if ((e.key === 'ArrowRight' || e.key === 'ArrowLeft') && t.hasAttribute && t.hasAttribute('data-pb-theme')) {
          var seg = Array.prototype.slice.call(d.querySelectorAll('[data-pb-theme]')), j = seg.indexOf(t);
          var n = seg[(j + (e.key === 'ArrowRight' ? 1 : -1) + seg.length) % seg.length];
          e.preventDefault(); n.focus(); pbUiSetTheme(n.getAttribute('data-pb-theme'));
        }
        if (e.key === 'Enter' && t.tagName === 'INPUT') { e.preventDefault(); if (edit) save(); }
      });
      d.addEventListener('close', function () {
        d.remove();
        var r = opts && opts.returnFocus; if (r && r.isConnected) r.focus();
      });
      function save() {
        var a = vName(), b = vDs(), c = vFig();
        if (!a) { name.focus(); return; } if (!b) { dsn.focus(); return; } if (!c) { fig.focus(); return; }
        var body = { name: name.value.trim(), designSystem: { name: dsn.value.trim(), designLink: fig.value.trim() } };
        var btn = $('#pb-set-save'); btn.disabled = true; err.hidden = true;
        fetch(window.PB_PREVIEW.meta, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
          .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
          .then(function (res) {
            btn.disabled = false;
            if (!res.ok || !res.j || !res.j.ok) {
              var msg = (res.j && res.j.error) || 'The preview server refused the change.';
              if (/^designSystem\.name/.test(msg)) mark(dsn, msg.replace(/^designSystem\.name:\s*/, ''), helpDs);
              else if (/^designSystem\.designLink/.test(msg)) mark(fig, msg.replace(/^designSystem\.designLink:\s*/, ''), helpFig);
              else if (/^name:/.test(msg)) mark(name, msg.replace(/^name:\s*/, '').replace(/^required$/i, 'Required'), 'Named on the bar and in every hand-off.');
              else { err.textContent = msg; err.hidden = false; }
              return;
            }
            d.close();
            if (opts && opts.onSaved) opts.onSaved(res.j.meta);
            var w = res.j.warnings && res.j.warnings[0];
            pbUiToast(w ? 'Saved — ' + String(w).replace(/^designSystem\.designLink:\s*/, '') : 'Saved to registry.json');
          }, function () {
            btn.disabled = false;
            err.textContent = 'Could not reach /pb:preview — is it still running?'; err.hidden = false;
          });
      }
      if (edit) $('#pb-set-save').addEventListener('click', save);
      d.showModal();
      (edit ? name : d.querySelector('[data-pb-close]')).focus();
    }

    /* ---- ⌘K: one search across every tab, plus the commands --------------------------------
       getItems() → [{ g: group, t: title, s: sub, x: extra words to match, mono, act() }].
       Empty query shows the Commands and Go to groups; typing ranks every group, best first. */
    var PB_UI_CMDK_ICON = { Commands: 'cmd', 'Go to': 'arrow', Rules: 'list', Jobs: 'users', Components: 'layers',
      Screens: 'phone', 'Test cases': 'check', 'Content terms': 'book', 'Component tabs': 'layers', Foundations: 'layers' };
    function pbUiCmdkOpen() { return !!document.querySelector('.pb-cmdk'); }
    /* opts (optional): { label, placeholder, foot } — what this site searches. The prototype's
       wording is the default; the design-system site names its own (components, tabs, foundations). */
    function pbUiOpenCmdk(getItems, opts) {
      opts = opts || {};
      var cur = document.querySelector('.pb-cmdk');
      if (cur) { cur._close(); return; }
      var back = document.activeElement, all = getItems() || [], sel = 0, shown = [];
      var scrim = document.createElement('div'); scrim.className = 'pb-cmdk-scrim';
      var d = document.createElement('div');
      d.className = 'pb-cmdk'; d.setAttribute('role', 'dialog'); d.setAttribute('aria-modal', 'true'); d.setAttribute('aria-label', 'Search and commands');
      d.innerHTML = '<div class="pb-cmdk-in">' + pbUiIcon('search', 'pb-ico--lg')
        + '<input type="text" role="combobox" aria-expanded="true" aria-controls="pb-cmdk-list" aria-autocomplete="list"'
        + ' aria-label="' + pbUiEsc(opts.label || 'Search rules, jobs, screens, components, test cases, terms and commands') + '"'
        + ' placeholder="' + pbUiEsc(opts.placeholder || 'Search rules, jobs, screens, components, test cases, commands') + '" autocomplete="off" spellcheck="false">'
        + '<span class="pb-kbd">esc</span></div>'
        + '<div class="pb-cmdk-list" id="pb-cmdk-list" role="listbox" aria-label="Results"></div>'
        + '<div class="pb-cmdk-f"><span><span class="pb-kbd">↑</span><span class="pb-kbd">↓</span> move</span><span><span class="pb-kbd">↵</span> open</span><span class="pb-cmdk-f-r">' + pbUiEsc(opts.foot || 'Searches every tab') + '</span></div>';
      document.body.appendChild(scrim); document.body.appendChild(d);
      var inp = d.querySelector('input'), list = d.querySelector('.pb-cmdk-list');
      function score(it, toks) {
        var t = String(it.t).toLowerCase(), hay = (it.t + ' ' + (it.s || '') + ' ' + it.g + ' ' + (it.x || '')).toLowerCase(), sc = 0;
        for (var i = 0; i < toks.length; i++) {
          var k = toks[i]; if (hay.indexOf(k) < 0) return -1;
          sc += t.indexOf(k) === 0 ? 3 : t.indexOf(k) > -1 ? 2 : 1;
        }
        return sc;
      }
      function hl(text, toks) {
        var s = String(text), i = toks.length ? s.toLowerCase().indexOf(toks[0]) : -1;
        if (i < 0) return pbUiEsc(s);
        return pbUiEsc(s.slice(0, i)) + '<mark>' + pbUiEsc(s.slice(i, i + toks[0].length)) + '</mark>' + pbUiEsc(s.slice(i + toks[0].length));
      }
      function paint() {
        var q = inp.value.trim().toLowerCase(), toks = q ? q.split(/\s+/) : [], groups = {}, order = [], lim = toks.length ? 8 : 6;
        shown = [];
        all.forEach(function (it) {
          var s = toks.length ? score(it, toks) : (it.g === 'Commands' || it.g === 'Go to' ? 0 : -1);
          if (s < 0) return;
          (groups[it.g] = groups[it.g] || []).push({ it: it, s: s });
          if (order.indexOf(it.g) < 0) order.push(it.g);
        });
        if (toks.length) {
          var best = {}; order.forEach(function (g) { best[g] = Math.max.apply(null, groups[g].map(function (o) { return o.s; })); });
          order = order.map(function (g, i) { return { g: g, i: i }; })
            .sort(function (a, b) { return best[b.g] - best[a.g] || a.i - b.i; }).map(function (o) { return o.g; });
        }
        var html = '', idx = 0;
        order.forEach(function (g) {
          var arr = groups[g].sort(function (a, b) { return b.s - a.s; }).slice(0, lim);
          html += '<div class="pb-cmdk-g" role="presentation">' + pbUiEsc(g)
            + (groups[g].length > lim ? ' <span>' + lim + ' of ' + groups[g].length + '</span>' : '') + '</div>';
          arr.forEach(function (o) {
            shown.push(o.it);
            html += '<div class="pb-cmdk-it" role="option" id="pb-cmdk-' + idx + '" data-i="' + idx + '" aria-selected="false">'
              + pbUiIcon(PB_UI_CMDK_ICON[g] || 'arrow') + '<span class="pb-cmdk-t">' + hl(o.it.t, toks) + '</span>'
              + '<span class="pb-cmdk-s' + (o.it.mono ? ' is-mono' : '') + '">' + pbUiEsc(o.it.s || '') + '</span></div>';
            idx++;
          });
        });
        if (!shown.length) html = '<div class="pb-cmdk-none">Nothing matches “' + pbUiEsc(inp.value.trim()) + '”. '
          + (opts.hint || 'Try a rule id, a screen name, or <code>theme</code>.') + '</div>';
        list.innerHTML = html; sel = Math.min(sel, Math.max(0, shown.length - 1)); mark();
      }
      function mark() {
        Array.prototype.forEach.call(list.querySelectorAll('.pb-cmdk-it'), function (el) {
          var on = +el.getAttribute('data-i') === sel; el.setAttribute('aria-selected', String(on));
          if (on) { inp.setAttribute('aria-activedescendant', el.id); el.scrollIntoView({ block: 'nearest' }); }
        });
      }
      function close(keepFocus) {
        scrim.remove(); d.remove();
        if (!keepFocus && back && back.isConnected && back.focus) back.focus();
      }
      function run(i) { var it = shown[i]; if (!it) return; close(true); it.act(); }
      d._close = close;
      inp.addEventListener('input', function () { sel = 0; paint(); });
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, shown.length - 1); mark(); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); mark(); }
        else if (e.key === 'Enter') { e.preventDefault(); run(sel); }
        else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); }
        else if (e.key === 'Tab') { e.preventDefault(); }
      });
      list.addEventListener('mousemove', function (e) {
        var el = e.target.closest('.pb-cmdk-it'); if (el && +el.getAttribute('data-i') !== sel) { sel = +el.getAttribute('data-i'); mark(); }
      });
      list.addEventListener('click', function (e) { var el = e.target.closest('.pb-cmdk-it'); if (el) run(+el.getAttribute('data-i')); });
      scrim.addEventListener('click', function () { close(); });
      paint(); inp.focus();
    }

    /* Install the shared keys once per page: ⌘K / Ctrl+K anywhere opens the palette. */
    function pbUiInstall(opts) {
      if (typeof document === 'undefined' || window.__pbUiInstalled) return;
      window.__pbUiInstalled = true;
      document.addEventListener('keydown', function (e) {
        if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && String(e.key).toLowerCase() === 'k') {
          e.preventDefault();
          if (document.querySelector('dialog[open]')) return;
          pbUiOpenCmdk(opts.items, opts.cmdk);
        }
      }, true);
    }

    /* =====================================================================================
     * SHARED PRIMITIVES (round 3 · wave A) — one implementation each, composed by every page of
     * both shells. Same rule as the chrome above: function declarations plus inert or guarded
     * top-level code (this file also runs in a bare node vm with no `document`); the delegated
     * listeners install themselves the first time a primitive's HTML is built, and never in a vm.
     * Styles live in chrome.css (.pb-disc*, .pb-fbar*, .pb-chip, .pb-pop, .pb-rt, .pb-head*, .pb-toast*).
     *
     *   pbDiscHTML({id, summary, body, open, level, group, cls, attrs})   an expand/collapse
     *   pbDiscSet(id, open) · pbDiscToggle(id) · pbDiscIsOpen(id) · pbDiscAll(group, open)
     *   pbDiscGroupBarHTML(group) · pbDiscSync(group)           "Expand all / Collapse all"
     *   pbFilterBar(cfg) · pbFilterNoneHTML(id) · pbFilterApply(id, items) · pbFilterClear(id)
     *   pbFilterState(id) · pbFilterApplyAll() · pbFilterPopIsOpen()      the filter bar
     *   pbUiToast(msg, {note, tone})                                      (above) the tool toast
     *   pbCanvasPalette() · pbThemeIsDark()   + window event `pb:themechange`     diagram colours
     *   pbRichText(str, opts)                                             prose → safe, structured HTML
     *   pbHeadHTML({title, meta, sub, actions, tag, flush})               a page's title block
     * Events (all bubble from the element that owns them; listen on `document`, `pb:themechange` on `window`):
     *   pb:disclosure {id, open, root, body} · pb:filter {id, visible, total, state} · pb:themechange {theme, dark}
     * ===================================================================================== */
    function pbAttrSel(attr, val) { return '[' + attr + '="' + String(val).replace(/["\\]/g, '\\$&') + '"]'; }
    function pbEmit(target, name, detail) {
      var ev;
      try { ev = new CustomEvent(name, { bubbles: true, detail: detail }); }
      catch (e) { ev = document.createEvent('CustomEvent'); ev.initCustomEvent(name, true, false, detail); }
      (target || document).dispatchEvent(ev);
    }
    function pbEls(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

    /* ---- pbDisclosure ---------------------------------------------------------------------
     * ONE expand/collapse for rows, cards and sections. MULTI-OPEN: nothing here closes a sibling.
     *   summary, body   HTML strings the caller has already escaped (like pbFrame's children).
     *   id              required; the key the open state is remembered under. A slug (word chars, - ).
     *   open            the initial state — used only until the viewer has toggled it once.
     *   level           'row' (a line in a list: hairline, washed when open) | 'section' (a bold heading).
     *   group           an id shared by a list of them: arrows move between its triggers, and
     *                   pbDiscAll / pbDiscGroupBarHTML act on it.
     *   cls, attrs      extra classes on the root; attrs = {name: value} → extra attributes on it.
     * The viewer's choice outlives a re-render (PB_DISC_STATE, and the data-preserve verb: the root
     * carries data-preserve="disc"). Enter / Space toggle (the trigger is a <button>); ↑ ↓ Home End
     * move between triggers. A `pb:disclosure` event follows every change, so a lazy body can fill
     * itself the first time it opens. */
    var PB_DISC_STATE = new Map();     // id → true | false: what the viewer chose (a Map, not a Set: "closed" must be remembered too)
    var PB_DISC_SOON = false;
    function pbDiscIsOpen(id, dflt) { id = String(id); return PB_DISC_STATE.has(id) ? PB_DISC_STATE.get(id) : !!dflt; }
    function pbDiscHTML(o) {
      o = o || {};
      var id = String(o.id == null ? '' : o.id), sid = id.replace(/[^\w-]/g, '_');
      var open = pbDiscIsOpen(id, o.open), tid = 'pb-disc-' + sid + '-t', bid = 'pb-disc-' + sid + '-b';
      var extra = '';
      if (o.attrs) Object.keys(o.attrs).forEach(function (k) { extra += ' ' + pbUiEsc(k) + '="' + pbUiEsc(o.attrs[k]) + '"'; });
      pbDiscInstall(); pbDiscSyncSoon();
      return '<div class="pb-disc pb-disc--' + (o.level === 'section' ? 'section' : 'row') + (open ? ' is-open' : '') + (o.cls ? ' ' + pbUiEsc(o.cls) : '') + '"'
        + ' data-pb-disc="' + pbUiEsc(id) + '"' + (o.group ? ' data-pb-disc-group="' + pbUiEsc(o.group) + '"' : '')
        + ' data-preserve="disc" data-preserve-key="pb-disc:' + pbUiEsc(id) + '"' + extra + '>'
        + '<button type="button" class="pb-disc-t" id="' + tid + '" aria-expanded="' + open + '" aria-controls="' + bid + '">'
        + pbUiIcon('chevronR', 'pb-ico--lg pb-disc-ch') + '<span class="pb-disc-s">' + (o.summary == null ? '' : o.summary) + '</span></button>'
        + '<div class="pb-disc-b" id="' + bid + '"' + (open ? '' : ' hidden') + '>' + (o.body == null ? '' : o.body) + '</div></div>';
    }
    function pbDiscChild(root, cls) {
      for (var i = 0; i < root.children.length; i++) if (root.children[i].classList.contains(cls)) return root.children[i];
      return null;
    }
    function pbDiscApply(root, open) {
      var t = pbDiscChild(root, 'pb-disc-t'), b = pbDiscChild(root, 'pb-disc-b');
      root.classList.toggle('is-open', open);
      if (t) t.setAttribute('aria-expanded', String(open));
      if (b) b.hidden = !open;
    }
    function pbDiscSet(id, open, quiet) {
      id = String(id); open = !!open;
      PB_DISC_STATE.set(id, open);
      if (typeof document === 'undefined') return open;
      pbEls('.pb-disc' + pbAttrSel('data-pb-disc', id)).forEach(function (r) {
        var was = r.classList.contains('is-open');
        pbDiscApply(r, open);
        if (was !== open && !quiet) pbEmit(r, 'pb:disclosure', { id: id, open: open, root: r, body: pbDiscChild(r, 'pb-disc-b') });
      });
      if (!quiet) pbDiscSync();
      return open;
    }
    function pbDiscToggle(id) {
      var r = typeof document === 'undefined' ? null : document.querySelector('.pb-disc' + pbAttrSel('data-pb-disc', id));
      return pbDiscSet(id, !(r ? r.classList.contains('is-open') : pbDiscIsOpen(id)));
    }
    /* the members of a group a viewer can see: a row a filter hid (or one inside a closed body) is not one */
    function pbDiscMembers(group) {
      return pbEls('.pb-disc' + pbAttrSel('data-pb-disc-group', group)).filter(function (r) { return !r.closest('[hidden]'); });
    }
    function pbDiscAll(group, open) {
      open = !!open;
      var n = 0;
      pbDiscMembers(group).forEach(function (r) {
        var id = r.getAttribute('data-pb-disc'), was = r.classList.contains('is-open');
        PB_DISC_STATE.set(id, open);
        if (was === open) return;
        pbDiscApply(r, open); n++;
        pbEmit(r, 'pb:disclosure', { id: id, open: open, root: r, body: pbDiscChild(r, 'pb-disc-b') });
      });
      pbDiscSync(group);
      return n;
    }
    /* "Expand all" / "Collapse all": the label names what a click will do, from what is on screen now.
       Build the group's rows BEFORE the bar if you can; either way it settles one tick after the HTML
       is inserted (and after every toggle). Call pbDiscSync(group) yourself if you insert later. */
    function pbDiscGroupBarHTML(group) {
      pbDiscInstall(); pbDiscSyncSoon();
      return '<button type="button" class="pb-btn pb-btn--ghost pb-btn--sm pb-disc-all" data-pb-disc-all="' + pbUiEsc(group) + '" data-fb-all'
        + ' title="Expand or collapse every item in the list">Expand all</button>';
    }
    function pbDiscSync(group) {
      if (typeof document === 'undefined') return;
      pbEls('[data-pb-disc-all]').forEach(function (b) {
        var g = b.getAttribute('data-pb-disc-all');
        if (group != null && String(group) !== g) return;
        var ms = pbDiscMembers(g), all = ms.length > 0 && ms.every(function (r) { return r.classList.contains('is-open'); });
        b.textContent = all ? 'Collapse all' : 'Expand all';
        b.disabled = ms.length === 0;
      });
    }
    function pbDiscSyncSoon() {
      if (typeof document === 'undefined' || PB_DISC_SOON) return;
      PB_DISC_SOON = true;
      setTimeout(function () { PB_DISC_SOON = false; pbDiscSync(); }, 0);
    }
    function pbDiscTriggers(root) {
      var g = root.getAttribute('data-pb-disc-group');
      var roots = g ? pbDiscMembers(g) : Array.prototype.filter.call(root.parentElement ? root.parentElement.children : [], function (n) {
        return n.classList.contains('pb-disc') && !n.hidden;
      });
      return roots.map(function (r) { return pbDiscChild(r, 'pb-disc-t'); }).filter(Boolean);
    }
    function pbDiscInstall() {
      if (typeof document === 'undefined' || window.__pbDiscInstalled) return;
      window.__pbDiscInstalled = true;
      document.addEventListener('click', function (e) {
        var t = e.target && e.target.closest ? e.target.closest('.pb-disc-t, [data-pb-disc-all]') : null;
        if (!t) return;
        if (t.hasAttribute('data-pb-disc-all')) {
          var g = t.getAttribute('data-pb-disc-all'), ms = pbDiscMembers(g);
          pbDiscAll(g, !(ms.length && ms.every(function (r) { return r.classList.contains('is-open'); })));
          return;
        }
        var root = t.parentElement;
        if (root && root.hasAttribute('data-pb-disc')) pbDiscSet(root.getAttribute('data-pb-disc'), !root.classList.contains('is-open'));
      });
      document.addEventListener('keydown', function (e) {
        var k = e.key;
        if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
        if (k !== 'ArrowDown' && k !== 'ArrowUp' && k !== 'Home' && k !== 'End') return;
        var t = e.target && e.target.closest ? e.target.closest('.pb-disc-t') : null;
        if (!t || !t.parentElement) return;
        var list = pbDiscTriggers(t.parentElement), i = list.indexOf(t);
        var n = k === 'Home' ? list[0] : k === 'End' ? list[list.length - 1] : list[i + (k === 'ArrowDown' ? 1 : -1)];
        if (n) { e.preventDefault(); n.focus(); }
      });
    }

    /* ---- pbFilterBar ----------------------------------------------------------------------
     * search · chips (multi-select popovers) · quick toggles · Clear · spacer · "N of M" · slot.
     *   cfg = { id, placeholder, label, countLabel, chips, quick, slot, off }
     *     chips  [{ id, label, options: [{ value, label, count }] }]   OR within a chip, AND across chips
     *     quick  [{ id, label, count }]                                aria-pressed toggles, AND-ed
     *     countLabel  the noun after the count ("12 of 43 rules") and in the empty message
     *     slot   HTML at the far right (an Expand all button, say)
     *     off    a reason string: the bar is drawn disabled, with that reason beneath it
     * pbFilterApply(id, items) filters the page and returns the visible count. items = an array — or a
     * function returning one, which is re-run on every keystroke so a page that rebuilds its rows never
     * hands over stale elements — of { el, text, facets: {chipId: value | [values]}, quick: {quickId: bool} }.
     * An `el` is shown or hidden with its `hidden` attribute (give it [hidden]{display:none} if it sets
     * its own display). Call it once after the bar and the rows are in the DOM: that is what restores the
     * remembered filter. State is per bar id and outlives a re-render. Fires `pb:filter`. Put
     * pbFilterNoneHTML(id) under the list for the "nothing matches" message. */
    var PB_FB_STATE = new Map();     // bar id → { q, sel: {chipId: [values]}, quick: {id: true} }
    var PB_FB_ITEMS = new Map();     // bar id → items | () => items
    var PB_FB_OPEN = null;           // the chip button whose popover is open
    function pbFbLive(id) {
      id = String(id);
      var s = PB_FB_STATE.get(id);
      if (!s) { s = { q: '', sel: {}, quick: {} }; PB_FB_STATE.set(id, s); }
      return s;
    }
    function pbFbDirty(st) {
      return !!String(st.q).trim() || Object.keys(st.sel).some(function (k) { return st.sel[k].length; })
        || Object.keys(st.quick).some(function (k) { return st.quick[k]; });
    }
    function pbFilterState(id) {
      var st = pbFbLive(id), sel = {}, quick = {};
      Object.keys(st.sel).forEach(function (k) { if (st.sel[k].length) sel[k] = st.sel[k].slice(); });
      Object.keys(st.quick).forEach(function (k) { if (st.quick[k]) quick[k] = true; });
      return { q: st.q, sel: sel, quick: quick };
    }
    function pbFilterBar(cfg) {
      cfg = cfg || {};
      var id = String(cfg.id || 'filter'), st = pbFbLive(id), off = cfg.off ? String(cfg.off) : '';
      var noun = cfg.countLabel ? String(cfg.countLabel) : '', ph = cfg.placeholder || 'Search', e = pbUiEsc;
      var dis = off ? ' aria-disabled="true" title="' + e(off) + '"' : '';
      var chips = (cfg.chips || []).map(function (c) {
        var picked = st.sel[c.id] || [];
        return '<span class="pb-fbar-wrap"><button class="pb-chip' + (picked.length ? ' is-on' : '') + '" type="button" data-pb-chip="' + e(c.id) + '" data-label="' + e(c.label) + '"'
          + ' aria-haspopup="true" aria-expanded="false"' + (off ? dis : ' title="Filter by ' + e(String(c.label).toLowerCase()) + '"') + '>'
          + '<span class="cl">' + e(c.label) + (picked.length ? ' · ' + picked.length : '') + '</span>' + pbUiIcon('chevron') + '</button>'
          + '<div class="pb-pop" role="group" aria-label="' + e(c.label) + '" hidden>'
          + (c.options || []).map(function (o) {
              return '<label class="pb-pop-opt"><input type="checkbox" data-pb-opt="' + e(c.id) + '" value="' + e(o.value) + '"' + (picked.indexOf(String(o.value)) !== -1 ? ' checked' : '') + '>'
                + '<span>' + e(o.label == null ? o.value : o.label) + '</span>' + (o.count != null ? '<span class="n">' + e(o.count) + '</span>' : '') + '</label>';
            }).join('')
          + '</div></span>';
      }).join('');
      var quick = (cfg.quick || []).map(function (q) {
        var on = !!st.quick[q.id];
        return '<button class="pb-chip pb-chip--q' + (on ? ' is-on' : '') + '" type="button" data-pb-quick="' + e(q.id) + '" aria-pressed="' + on + '"' + dis + '>'
          + '<span class="cl">' + e(q.label) + '</span>' + (q.count != null ? '<span class="n">' + e(q.count) + '</span>' : '') + '</button>';
      }).join('');
      pbFilterInstall();
      return '<div class="pb-fbar' + (off ? ' is-off' : '') + '" role="search" aria-label="' + e(cfg.label || ph) + '" data-fbar="' + e(id) + '" data-noun="' + e(noun || 'items') + '" data-count-label="' + e(noun) + '">'
        + '<label class="pb-fbar-q"' + (off ? ' title="' + e(off) + '"' : '') + '>' + pbUiIcon('search')
        + '<input type="search" data-pb-fq value="' + e(st.q) + '" placeholder="' + e(ph) + '" aria-label="' + e(ph) + '" autocomplete="off" spellcheck="false"' + (off ? ' disabled' : '') + '></label>'
        + chips + quick
        + '<button class="pb-btn pb-btn--ghost pb-btn--sm pb-fbar-clear" type="button" data-pb-fclear="' + e(id) + '" title="Clear the search and every filter"' + (pbFbDirty(st) ? '' : ' hidden') + '>Clear</button>'
        + '<span class="pb-fbar-grow"></span>'
        + '<span class="pb-fbar-cnt" aria-live="polite">' + (off ? '0 of 0' : '') + '</span>'
        + (cfg.slot && !off ? cfg.slot : '')
        + (off ? '<span class="pb-fbar-why">' + e(off) + '</span>' : '')
        + '</div>';
    }
    function pbFilterNoneHTML(id) {
      return '<div class="pb-fbar-none" data-pb-fnone="' + pbUiEsc(id) + '" role="status" hidden></div>';
    }
    function pbFilterApply(id, items) {
      id = String(id);
      if (items !== undefined) PB_FB_ITEMS.set(id, items);
      var bar = document.querySelector('.pb-fbar' + pbAttrSel('data-fbar', id));
      if (bar && bar.classList.contains('is-off')) return 0;
      var src = PB_FB_ITEMS.get(id), list = typeof src === 'function' ? src() : src;
      list = Array.isArray(list) ? list : [];
      var st = pbFbLive(id), toks = String(st.q).trim().toLowerCase().split(/\s+/).filter(Boolean);
      var picked = Object.keys(st.sel).filter(function (k) { return st.sel[k].length; });
      var quick = Object.keys(st.quick).filter(function (k) { return st.quick[k]; });
      var n = 0;
      list.forEach(function (it) {
        if (!it) return;
        var hay = String(it.text == null ? '' : it.text).toLowerCase();
        var ok = toks.every(function (t) { return hay.indexOf(t) !== -1; })
          && picked.every(function (k) {
            var v = it.facets ? it.facets[k] : null, vs = Array.isArray(v) ? v : (v == null ? [] : [v]);
            return vs.some(function (x) { return st.sel[k].indexOf(String(x)) !== -1; });
          })
          && quick.every(function (k) { return !!(it.quick && it.quick[k]); });
        if (it.el) it.el.hidden = !ok;
        if (ok) n++;
      });
      var noun = bar ? (bar.getAttribute('data-count-label') || '') : '', dirty = pbFbDirty(st);
      if (bar) {
        var cnt = bar.querySelector('.pb-fbar-cnt'), clr = bar.querySelector('[data-pb-fclear]'), inp = bar.querySelector('input[data-pb-fq]');
        if (cnt) cnt.textContent = n + ' of ' + list.length + (noun ? ' ' + noun : '');
        if (clr) clr.hidden = !dirty;
        if (inp && inp.value !== st.q) inp.value = st.q;
        pbEls('[data-pb-chip]', bar).forEach(function (c) {
          var k = c.getAttribute('data-pb-chip'), on = (st.sel[k] || []).length, lab = c.querySelector('.cl');
          if (lab) lab.textContent = c.getAttribute('data-label') + (on ? ' · ' + on : '');
          c.classList.toggle('is-on', !!on);
        });
        pbEls('[data-pb-quick]', bar).forEach(function (b) {
          var on = !!st.quick[b.getAttribute('data-pb-quick')];
          b.setAttribute('aria-pressed', String(on)); b.classList.toggle('is-on', on);
        });
        pbEls('input[data-pb-opt]', bar).forEach(function (cb) {
          var want = (st.sel[cb.getAttribute('data-pb-opt')] || []).indexOf(cb.value) !== -1;
          if (cb.checked !== want) cb.checked = want;
        });
      }
      var none = document.querySelector(pbAttrSel('data-pb-fnone', id));
      if (none) {
        var empty = n === 0 && list.length > 0, nn = (bar && bar.getAttribute('data-noun')) || 'items', q = String(st.q).trim();
        none.hidden = !empty;
        none.innerHTML = empty ? 'No ' + pbUiEsc(nn) + ' match ' + (q ? '“' + pbUiEsc(q) + '”' + (picked.length || quick.length ? ' and these filters' : '') : 'these filters') + '.<br>'
          + '<button class="pb-btn pb-btn--sm" type="button" data-pb-fclear="' + pbUiEsc(id) + '">Clear filters</button>' : '';
      }
      pbEmit(bar || document, 'pb:filter', { id: id, visible: n, total: list.length, state: pbFilterState(id) });
      return n;
    }
    function pbFilterApplyAll() {
      pbEls('.pb-fbar[data-fbar]').forEach(function (b) { pbFilterApply(b.getAttribute('data-fbar')); });
    }
    function pbFilterClear(id) {
      id = String(id);
      PB_FB_STATE.set(id, { q: '', sel: {}, quick: {} });
      if (typeof document === 'undefined') return;
      var bar = document.querySelector('.pb-fbar' + pbAttrSel('data-fbar', id));
      if (bar) { var inp = bar.querySelector('input[data-pb-fq]'); if (inp) inp.value = ''; }
      pbFilterApply(id);
    }
    /* the chip popovers: one open at a time; Esc closes and returns focus; arrows walk the boxes */
    function pbFilterPopIsOpen() {
      // a popover whose bar was re-rendered away is not open: forget it, so a page-level Esc is not held hostage
      if (PB_FB_OPEN && !PB_FB_OPEN.isConnected) { PB_FB_OPEN = null; document.removeEventListener('mousedown', pbFilterPopOutside, true); }
      return !!PB_FB_OPEN;
    }
    function pbFilterPopClose(refocus) {
      if (!PB_FB_OPEN) return;
      var c = PB_FB_OPEN; PB_FB_OPEN = null;
      c.setAttribute('aria-expanded', 'false');
      var pop = c.nextElementSibling; if (pop) pop.hidden = true;
      document.removeEventListener('mousedown', pbFilterPopOutside, true);
      if (refocus) c.focus();
    }
    function pbFilterPopOutside(e) { if (PB_FB_OPEN && !PB_FB_OPEN.parentElement.contains(e.target)) pbFilterPopClose(false); }
    function pbFilterPopOpen(c) {
      if (c.getAttribute('aria-disabled') === 'true') return;
      if (PB_FB_OPEN === c) { pbFilterPopClose(true); return; }
      pbFilterPopClose(false);
      var pop = c.nextElementSibling; if (!pop) return;
      pop.hidden = false; c.setAttribute('aria-expanded', 'true'); PB_FB_OPEN = c;
      document.addEventListener('mousedown', pbFilterPopOutside, true);
      var first = pop.querySelector('input'); if (first) first.focus();
    }
    function pbFilterInstall() {
      if (typeof document === 'undefined' || window.__pbFilterInstalled) return;
      window.__pbFilterInstalled = true;
      var barOf = function (n) { var b = n.closest('.pb-fbar'); return b ? b.getAttribute('data-fbar') : null; };
      document.addEventListener('input', function (e) {
        var t = e.target;
        if (!t || !t.matches || !t.matches('input[data-pb-fq]')) return;
        var id = barOf(t); if (id == null) return;
        pbFbLive(id).q = t.value; pbFilterApply(id);
      });
      document.addEventListener('change', function (e) {
        var t = e.target;
        if (!t || !t.matches || !t.matches('input[data-pb-opt]')) return;
        var id = barOf(t); if (id == null) return;
        var st = pbFbLive(id), k = t.getAttribute('data-pb-opt');
        var cur = st.sel[k] = (st.sel[k] || []).filter(function (x) { return x !== t.value; });
        if (t.checked) cur.push(t.value);
        pbFilterApply(id);
      });
      document.addEventListener('click', function (e) {
        var t = e.target, el = t && t.closest ? t.closest('[data-pb-chip], [data-pb-quick], [data-pb-fclear]') : null;
        if (!el) return;
        if (el.hasAttribute('data-pb-fclear')) { pbFilterPopClose(false); pbFilterClear(el.getAttribute('data-pb-fclear')); return; }
        if (el.getAttribute('aria-disabled') === 'true') return;
        if (el.hasAttribute('data-pb-chip')) { pbFilterPopOpen(el); return; }
        var id = barOf(el); if (id == null) return;
        var st = pbFbLive(id), k = el.getAttribute('data-pb-quick');
        st.quick[k] = !st.quick[k];
        pbFilterApply(id);
      });
      // capture phase, so a popover's Esc is spent here and never reaches a page-level Esc handler
      document.addEventListener('keydown', function (e) {
        var t = e.target;
        if (!t || !t.closest) return;
        var chip = t.closest('[data-pb-chip]'), pop = t.closest('.pb-pop');
        if (chip && e.key === 'ArrowDown' && PB_FB_OPEN !== chip) { e.preventDefault(); pbFilterPopOpen(chip); return; }
        if (!pbFilterPopIsOpen() || !(pop || chip) || !PB_FB_OPEN.parentElement.contains(t)) return;
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); pbFilterPopClose(true); return; }
        if (e.key === 'Tab') { pbFilterPopClose(false); return; }
        if (pop && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
          var boxes = pbEls('input', pop), i = boxes.indexOf(document.activeElement);
          e.preventDefault();
          boxes[(i + (e.key === 'ArrowDown' ? 1 : -1) + boxes.length) % boxes.length].focus();
        }
      }, true);
    }

    /* ---- canvas colours + the theme event -------------------------------------------------
     * chrome.css holds the diagram tokens as light-dark() pairs; a JS painter (Mermaid restyling, an SVG
     * stroke) cannot read a pair back from getComputedStyle — a custom property is returned unresolved —
     * so pbCanvasPalette() resolves each through a probe element and returns plain colour strings:
     *   { dark, canvas:{bg,grid,ink,ink2}, edge:{def,yes,no,label},
     *     node:{start,process,decision,screen,external}   each {fill,stroke,text},
     *     erd:{fill,rowAlt,stroke,head,headText,text,line} }
     * The five node keys are the legend's names; the pre-round-3 palette called them startEnd / input / action / sub.
     * Call it once per paint, not once per node. Repaint on `pb:themechange` (window): fired after
     * window.pbSetTheme(), and when the OS scheme flips while the theme is System. */
    function pbThemeIsDark() {
      var t = document.documentElement.getAttribute('data-theme');
      if (t === 'dark') return true;
      if (t === 'light') return false;
      return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    }
    function pbCanvasPalette() {
      var root = document.documentElement, probe = document.createElement('i');
      probe.setAttribute('aria-hidden', 'true'); probe.style.display = 'none';
      root.appendChild(probe);
      var c = function (n) { probe.style.color = 'var(--pb-' + n + ')'; return getComputedStyle(probe).color; };
      var pal = { dark: pbThemeIsDark(), canvas: { bg: c('canvas-bg'), grid: c('canvas-grid'), ink: c('ink'), ink2: c('ink-2') },
        edge: { def: c('edge-def'), yes: c('edge-yes'), no: c('edge-no'), label: c('edge-label') }, node: {},
        erd: { fill: c('erd-fill'), rowAlt: c('erd-row-alt'), stroke: c('erd-stroke'), head: c('erd-head'),
               headText: c('erd-head-text'), text: c('erd-text'), line: c('erd-line') } };
      ['start', 'process', 'decision', 'screen', 'external'].forEach(function (k) {
        pal.node[k] = { fill: c('node-' + k + '-fill'), stroke: c('node-' + k + '-stroke'), text: c('node-' + k + '-text') };
      });
      probe.remove();
      return pal;
    }
    function pbThemeEmit() { pbEmit(window, 'pb:themechange', { theme: pbUiTheme(), dark: pbThemeIsDark() }); }
    function pbThemeWatch() {
      if (typeof document === 'undefined' || window.__pbThemeWatch) return;
      window.__pbThemeWatch = true;
      var orig = window.pbSetTheme;     // the <head> bootstrap's; wrapped here once so all three shells share one event
      if (typeof orig === 'function') window.pbSetTheme = function () { var r = orig.apply(this, arguments); pbThemeEmit(); return r; };
      try {
        var mq = window.matchMedia('(prefers-color-scheme: dark)'), on = function () { if (pbUiTheme() === 'system') pbThemeEmit(); };
        if (mq.addEventListener) mq.addEventListener('change', on); else if (mq.addListener) mq.addListener(on);
      } catch (err) { /* no matchMedia: only an explicit pbSetTheme() announces itself */ }
    }
    pbThemeWatch();

    /* ---- pbRichText(str, opts) -------------------------------------------------------------
     * Prose from a registry (an insight, a note, a rule's body) → safe HTML with structure. The text is
     * escaped FIRST, so nothing in it can become a tag; every mark is then a class, never a style.
     *   blocks   blank line = paragraph · lines starting · - • ▪ – or "* " = <ul> · "1." / "1)" = <ol>
     *   inline   `code` (opaque) · **bold** · *em* / _em_ · ==highlight== · {+positive+} · {-negative-}
     *   numbers  98.7% · 11,042 · 500.000 ₫ · $12.50 · 24px · 3s … → <b class="pb-num"> (opts.numbers:false opts out)
     * A mark that never closes renders literally; snake_case_words and "2 * 3 * 4" are left alone.
     * opts: { numbers: true, inline: false, cls: '' } — inline:true skips the blocks and the wrapper and
     * returns marked-up text for use inside an element you own. Otherwise: <div class="pb-rt">…</div>.
     * pbEmph / pbProseHTML (prototype shell) are NOT delegates: they bold ALL-CAPS runs and split long
     * notes at their section headings, which this does not. */
    var PB_RT_NUM = /(?<![\p{L}\p{N}_.,\uE000])(?<!&#)(?:[$€£¥]\s?\d+(?:[.,]\d+)*(?![\p{L}\p{N}])|[+\-−]?\d+(?:[.,]\d+)*(?:\s?(?:%|₫|[$€£¥])|\s?(?:VNĐ|VND|USD|EUR|đ)(?![\p{L}\p{N}_])|(?:px|rem|em|pt|ms|min|sec|hr|kb|mb|gb|tb|kg|km|cm|mm|fps|dp|vh|vw|k|s|h)(?![\p{L}\p{N}_]))|\d{1,3}(?:[.,]\d{3})+(?![\p{L}\p{N}]))/gu;
    var PB_RT_MARKS = [
      [/\*\*(?=\S)(.+?)(?<=\S)\*\*/gu, '<strong>', '</strong>'],
      [/(?<![\p{L}\p{N}*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\p{L}\p{N}*])/gu, '<em>', '</em>'],
      [/(?<![\p{L}\p{N}_])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\p{L}\p{N}_])/gu, '<em>', '</em>'],
      [/==(?=\S)(.+?)(?<=\S)==/gu, '<mark class="pb-hl">', '</mark>'],
      [/\{\+(.+?)\+\}/gu, '<span class="pb-pos">', '</span>'],
      [/\{-(.+?)-\}/gu, '<span class="pb-neg">', '</span>']
    ];
    /* a mark wraps only what is already well-formed, so overlapping marks (`***x***`) stay literal
       instead of producing misnested tags */
    function pbRtBalanced(s) {
      var st = [], re = /<(\/?)([a-z]+)[^>]*>/g, m;
      while ((m = re.exec(s))) { if (m[1]) { if (st.pop() !== m[2]) return false; } else st.push(m[2]); }
      return st.length === 0;
    }
    function pbRichText(str, opts) {
      opts = opts || {};
      var src = (str == null ? '' : String(str)).replace(/\r\n?/g, '\n').replace(/[\uE000\uE001]/g, '');
      if (!src.trim()) return '';
      var esc = typeof pbEscape === 'function' ? pbEscape : pbUiEsc;
      var codes = [];
      var text = esc(src).replace(/`([^`\n]+)`/g, function (m, c) { codes.push(c); return '\uE000' + (codes.length - 1) + '\uE001'; });
      var inline = function (s) {
        PB_RT_MARKS.forEach(function (mk) { s = s.replace(mk[0], function (m, c) { return pbRtBalanced(c) ? mk[1] + c + mk[2] : m; }); });
        if (opts.numbers !== false) s = s.replace(PB_RT_NUM, '<b class="pb-num">$&</b>');
        return s.replace(/\uE000(\d+)\uE001/g, function (m, i) { return '<code>' + codes[+i] + '</code>'; });
      };
      var lines = function (block) { return block.split('\n').map(inline).join('<br>'); };
      if (opts.inline) return lines(text.trim());
      var out = [];
      text.trim().split(/\n[ \t]*\n+/).forEach(function (block) {
        var para = [], list = null;
        var flushPara = function () { if (para.length) { out.push('<p>' + para.map(inline).join('<br>') + '</p>'); para = []; } };
        var flushList = function () {
          if (!list) return;
          out.push('<' + list.tag + (list.tag === 'ol' && list.start !== 1 ? ' start="' + list.start + '"' : '') + '>'
            + list.items.map(function (it) { return '<li>' + inline(it) + '</li>'; }).join('') + '</' + list.tag + '>');
          list = null;
        };
        block.split('\n').forEach(function (ln) {
          var ul = /^\s*(?:[·•▪]\s*|[–*-]\s+)(\S.*)$/.exec(ln), ol = ul ? null : /^\s*(\d{1,3})[.)]\s+(\S.*)$/.exec(ln);
          if (ul || ol) {
            var tag = ul ? 'ul' : 'ol';
            flushPara();
            if (list && list.tag !== tag) flushList();
            if (!list) list = { tag: tag, start: ol ? +ol[1] : 1, items: [] };
            list.items.push(ul ? ul[1] : ol[2]);
          } else if (list && /^\s{2,}\S/.test(ln)) {
            list.items[list.items.length - 1] += ' ' + ln.trim();
          } else if (ln.trim()) {
            flushList(); para.push(ln.trim());
          }
        });
        flushPara(); flushList();
      });
      return '<div class="pb-rt' + (opts.cls ? ' ' + pbUiEsc(opts.cls) : '') + '">' + out.join('') + '</div>';
    }

    /* ---- pbHeadHTML — the title block of a page (and of the design-system component page) --------
     *   { title (text), meta (HTML: badges / labels), sub (text: a mono id), actions (HTML),
     *     tag ('h1' default … 'h6'), flush (true inside a column that already has its own gutter) }
     * → <header class="pb-head"><div class="pb-head-main"><h1 class="pb-head-t">… .pb-head-meta .pb-head-sub</div>
     *   <div class="pb-head-act">…</div></header>. Spacing and type are chrome.css's (.pb-head*). */
    function pbHeadHTML(o) {
      o = o || {};
      var tag = /^h[1-6]$/.test(o.tag) ? o.tag : 'h1';
      return '<header class="pb-head' + (o.flush ? ' pb-head--flush' : '') + '"><div class="pb-head-main">'
        + '<' + tag + ' class="pb-head-t">' + pbUiEsc(o.title) + '</' + tag + '>'
        + (o.meta ? '<div class="pb-head-meta">' + o.meta + '</div>' : '')
        + (o.sub ? '<div class="pb-head-sub">' + pbUiEsc(o.sub) + '</div>' : '')
        + '</div>' + (o.actions ? '<div class="pb-head-act">' + o.actions + '</div>' : '') + '</header>';
    }

    /* =====================================================================================
     * SPEC ENGINE (round 3 · wave B5) — the layers a component's LIVE render can wear.
     *
     *   pbSpecMount(host, comp, props, opts)  put the engine on a host: the design-system demo stage, a
     *                                         variant cell, an anatomy specimen. It adds an overlay over the
     *                                         live render and, into opts.layersSlot, the Layers control.
     *                                         Safe to call again: it only refreshes what it already has.
     *   pbSpecUpdate(host, props, opts)       re-measure after a prop / variant change (the overlay also follows
     *                                         the DOM on its own). opts.html (markup) or opts.render (true) morphs
     *                                         the new render into the host's .ds-fit in place, so the product's own
     *                                         CSS transitions play instead of the demo being replaced.
     *   pbSpecLayersHTML() · pbSpecLayers() · pbSpecSetLayer(id, on)     the Layers control and its state
     *   pbSpecRedrawAll()                     every visible overlay again (resize, theme, fonts do this themselves)
     *   pbSpecHostAttrs(kind, cid, props)     the attributes a markup builder puts on a host (kind 'cell' | 'specimen')
     *                                         so the engine mounts it by itself once it reaches the DOM
     *   pbSpecPartList(comp) · pbSpecTok(kind, value, hint) · pbSpecMorph(parent, html)
     *
     * Layers. ANATOMY: an outline and a numbered marker per part. SPEC: MARGIN · PADDING · GAP bands, each
     * its own --pb-spec-* colour, labelled with the registry token whose value it is, else px.
     * Every box is MEASURED from the live DOM (getBoundingClientRect + getComputedStyle, margin included).
     * The spec sidecar supplies names, types, required/optional and token hints — never geometry.
     * A transform on the render (the stage scales a wide device down) is divided out, so bands match boxes.
     * Labels. The bands are always drawn; their labels are drawn too (placed once, against every other label, so
     * none overlaps) but SHOWN only for the part being read: hovered, keyboard-focused or tapped in the live render
     * or (a table row with data-part-row inside the same card) in its legend. The Labels toggle, off by default,
     * shows every label at once, for a screenshot. A tap on touch pins a part's labels; a second tap on it lets go.
     *   pbSpecHot(host, name, src?)           show a part's labels (src 'link' by default); name null lets go
     *   pbSpecPin(host, name)                 the tap: pin that part's labels, or unpin when it is the pinned one
     * Events: `pb:specdraw` on the host when what a draw shows changed (detail {cid, parts, extra, rows}),
     * `pb:speclayers` on document when a toggle moves.
     * ===================================================================================== */
    var PB_SPEC_STORE = 'pb-spec-layers';
    var PB_SPEC_LAYERS = { anatomy: false, spec: false, margin: true, padding: true, gap: true, labels: false };
    var PB_SPEC_KINDS = [['margin', 'Margin'], ['padding', 'Padding'], ['gap', 'Gap']];
    var PB_SPEC_RECS = [];          // every host the engine is on
    var PB_SPEC_PROPS = {};         // key → props, for markup builders (an attribute cannot carry a props object)
    var PB_SPEC_N = 0;
    var PB_SPEC_UP = false;
    var PB_SPEC_PT = '';             // the pointer type of the press a click came from ('' for the keyboard)
    var PB_SPEC_RO = null;
    var PB_SPEC_TOKS = null;
    var PB_SPEC_PROBE = null;

    function pbSpecR(n) { return Math.round(n * 100) / 100; }
    function pbSpecPx(n) { return pbSpecR(n) + 'px'; }
    function pbSpecAt(b) {
      return 'left:' + pbSpecPx(b.x) + ';top:' + pbSpecPx(b.y) + ';width:' + pbSpecPx(Math.max(0, b.w)) + ';height:' + pbSpecPx(Math.max(0, b.h));
    }

    /* ---- the Layers control + its state ------------------------------------------------------ */
    function pbSpecLayers() {
      var o = {};
      Object.keys(PB_SPEC_LAYERS).forEach(function (k) { o[k] = PB_SPEC_LAYERS[k]; });
      return o;
    }
    function pbSpecLayersHTML() {
      pbSpecInstall();
      var L = PB_SPEC_LAYERS;
      function chip(id, label, title, kind) {
        return '<button type="button" class="pb-chip pb-chip--q pb-layer' + (kind ? ' pb-layer--' + kind : '') + (L[id] ? ' is-on' : '') + '"'
          + ' data-pb-layer="' + id + '" aria-pressed="' + (L[id] ? 'true' : 'false') + '" title="' + pbUiEsc(title) + '">'
          + (kind ? '<i class="pb-layer-sw" aria-hidden="true"></i>' : '') + label + '</button>';
      }
      return '<div class="pb-layers" role="group" aria-label="Layers" data-pb-layers><span class="pb-layers-l">Layers</span>'
        + chip('anatomy', 'Anatomy', 'Outline every part and number it')
        + chip('spec', 'Spec', 'Measure margin, padding and gap — hover or tap a part to read its values')
        + '<span class="pb-layers-sub" role="group" aria-label="Spec layers"' + (L.spec ? '' : ' hidden') + '>'
        + PB_SPEC_KINDS.map(function (k) { return chip(k[0], k[1], 'Show the ' + k[0], k[0]); }).join('')
        + chip('labels', 'Labels', 'Show every value at once, for a screenshot. Off: hover or tap a part to read its values.') + '</span></div>';
    }
    function pbSpecSyncControls() {
      pbEls('[data-pb-layer]').forEach(function (b) {
        var on = !!PB_SPEC_LAYERS[b.getAttribute('data-pb-layer')];
        b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.classList.toggle('is-on', on);
      });
      pbEls('.pb-layers-sub').forEach(function (s) { s.hidden = !PB_SPEC_LAYERS.spec; });
    }
    function pbSpecSetLayer(id, on) {
      if (!Object.prototype.hasOwnProperty.call(PB_SPEC_LAYERS, id)) return;
      PB_SPEC_LAYERS[id] = !!on;
      if (typeof document === 'undefined') return;
      pbUiStore(PB_SPEC_STORE, JSON.stringify(PB_SPEC_LAYERS));
      pbSpecSyncControls();
      pbSpecRedrawAll();
      pbEmit(document, 'pb:speclayers', pbSpecLayers());
    }

    /* ---- values → registry tokens (the page's own token map; spec_measure.py's rule: first by name wins) ---- */
    function pbSpecLen(v) {
      if (typeof v === 'number') return pbSpecR(v);
      var m = String(v == null ? '' : v).match(/^\s*(-?[\d.]+)\s*(px|rem)?\s*$/);
      return m ? pbSpecR(parseFloat(m[1]) * (m[2] === 'rem' ? 16 : 1)) : null;
    }
    function pbSpecProbe() {
      if (!PB_SPEC_PROBE || !PB_SPEC_PROBE.isConnected) {
        PB_SPEC_PROBE = document.createElement('i');
        PB_SPEC_PROBE.setAttribute('aria-hidden', 'true');
        PB_SPEC_PROBE.style.display = 'none';
        document.body.appendChild(PB_SPEC_PROBE);
      }
      return PB_SPEC_PROBE;
    }
    /* any CSS colour → '#rrggbb' / '#rrggbbaa' (lowercase), the form the sidecar stores; null when it is not one */
    function pbSpecNormColor(css, deep) {
      if (css == null) return null;
      var v = String(css).trim().toLowerCase(), m;
      if (v === 'white') v = '#ffffff'; else if (v === 'black') v = '#000000';
      if ((m = v.match(/^#([0-9a-f]{3,8})$/))) {
        var h = m[1];
        if (h.length === 3 || h.length === 4) h = h.split('').map(function (ch) { return ch + ch; }).join('');
        if (h.length === 8 && h.slice(6) === 'ff') h = h.slice(0, 6);
        return (h.length === 6 || h.length === 8) ? '#' + h : null;
      }
      m = v.match(/^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:\s*[,\/]\s*([\d.]+%?))?\s*\)$/);
      if (!m) {
        if (deep || typeof document === 'undefined' || !document.body) return null;
        var p = pbSpecProbe();
        p.style.color = ''; p.style.color = v;
        return p.style.color ? pbSpecNormColor(getComputedStyle(p).color, true) : null;
      }
      var hex = [m[1], m[2], m[3]].map(function (x) {
        var n = Math.max(0, Math.min(255, Math.round(parseFloat(x))));
        return (n < 16 ? '0' : '') + n.toString(16);
      }).join('');
      var a = m[4], alpha = a == null ? 1 : (a.slice(-1) === '%' ? parseFloat(a) / 100 : parseFloat(a));
      if (alpha >= 1) return '#' + hex;
      var ab = Math.round(alpha * 255);
      return '#' + hex + (ab < 16 ? '0' : '') + ab.toString(16);
    }
    function pbSpecTokIndex() {
      if (PB_SPEC_TOKS) return PB_SPEC_TOKS;
      var by = pbTokensByName(), idx = { by: by, dims: {}, colors: {} };
      Object.keys(by).sort().forEach(function (name) {
        if (name.indexOf('pb-') === 0) return;
        var t = by[name], v = t.value;
        if (t.type === 'color' || (t.type == null && pbSpecNormColor(v))) {
          var c = pbSpecNormColor(v);
          if (c && idx.colors[c] === undefined) idx.colors[c] = name;
        } else if (t.type === 'dimension' || t.type == null) {
          var px = pbSpecLen(v);
          if (px !== null) {
            var b = pbDisplayKind(name, 'dimension');
            idx.dims[b] = idx.dims[b] || {};
            if (idx.dims[b][px] === undefined) idx.dims[b][px] = name;
          }
        }
      });
      return (PB_SPEC_TOKS = idx);
    }
    /* The registry token whose value is `value`: kind 'space' (padding, margin, gap) · 'radius' · 'color'.
       `hint` is the sidecar's own token for it, honoured when it still holds that value (two tokens can
       share one). Zero never names a token. → the name, or null. */
    function pbSpecTok(kind, value, hint) {
      var ix = pbSpecTokIndex();
      if (kind === 'color') {
        var c = pbSpecNormColor(value);
        if (!c) return null;
        if (hint && ix.by[hint] && pbSpecNormColor(ix.by[hint].value) === c) return hint;
        return ix.colors[c] || null;
      }
      var v = typeof value === 'number' ? pbSpecR(value) : pbSpecLen(value);
      if (!(v > 0)) return null;
      if (hint && ix.by[hint] && pbSpecLen(ix.by[hint].value) === v) return hint;
      var bk = kind === 'radius' ? ['radius'] : ['space', 'size'];
      for (var i = 0; i < bk.length; i++) {
        var hit = ix.dims[bk[i]] && ix.dims[bk[i]][v];
        if (hit) return hit;
      }
      return null;
    }
    function pbSpecLabel(kind, v, hint) { return pbSpecTok(kind, v, hint) || (pbSpecR(v) + 'px'); }

    /* ---- the sidecar's parts (names, types, optional) — the same list the Anatomy table is numbered by ---- */
    function pbSpecAnatomyMap(c) {
      var a = c && c.anatomy;
      if (!a || typeof a !== 'object' || Array.isArray(a) || 'parts' in a || 'renderProps' in a) return null;
      var ks = Object.keys(a);
      if (!ks.length) return null;
      for (var i = 0; i < ks.length; i++) if (!a[ks[i]] || typeof a[ks[i]] !== 'object' || !('type' in a[ks[i]])) return null;
      return a;
    }
    function pbSpecLayoutOrder(layout) {
      var out = [];
      (function walk(node) {
        if (typeof node === 'string') out.push(node);
        else if (Array.isArray(node)) node.forEach(walk);
        else if (node && typeof node === 'object') Object.keys(node).forEach(function (k) {
          out.push(k); (Array.isArray(node[k]) ? node[k] : []).forEach(walk);
        });
      })(layout);
      return out;
    }
    /* → [{n, name, type, instanceOf, el, required}] in spec_parts.parts() order (the layout's, root excluded,
       then any part it does not place, sorted); null when the component has no measured anatomy */
    function pbSpecPartList(c) {
      var a = pbSpecAnatomyMap(c);
      if (!a) return null;
      var els = (c.elements && typeof c.elements === 'object') ? c.elements : {};
      var order = [], seen = {};
      pbSpecLayoutOrder(c.layout).forEach(function (k) { if (a[k] && k !== 'root' && !seen[k]) { seen[k] = 1; order.push(k); } });
      Object.keys(a).sort().forEach(function (k) { if (k !== 'root' && !seen[k]) { seen[k] = 1; order.push(k); } });
      return order.map(function (name, i) {
        var el = (els[name] && typeof els[name] === 'object') ? els[name] : {};
        return { n: i + 1, name: name, type: a[name].type, instanceOf: a[name].instanceOf, el: el, required: !('visibleWhen' in el) };
      });
    }

    /* ---- the live parts of a render, named exactly as spec_measure.py names them: a data-part, or a
       pbUse'd child's data-cmp (an instance — its insides are its own), a repeated name numbered in
       document order. A sidecar anchor tags a part the body never marked. → { name: element } ---- */
    function pbSpecLive(root, c) {
      var els = (c && c.elements && typeof c.elements === 'object') ? c.elements : {};
      Object.keys(els).sort().forEach(function (name) {
        var sel = els[name] && els[name].anchor;
        if (!sel) return;
        if (root.querySelector('[data-part="' + (window.CSS && CSS.escape ? CSS.escape(name) : name) + '"]')) return;
        var el = null;
        try { el = root.matches(sel) ? root : root.querySelector(sel); } catch (e) { /* a bad anchor names nothing */ }
        if (el && el !== root && !el.hasAttribute('data-part')) el.setAttribute('data-part', name);
      });
      var parts = [];
      (function walk(el, parent) {
        var isRoot = el === root, cmp = el.getAttribute('data-cmp'), named = el.getAttribute('data-part'), me = parent;
        if (isRoot || named || cmp) {
          var inst = !!cmp && !isRoot;
          parts.push({ base: isRoot ? 'root' : (inst ? cmp : named), parent: parent, el: el });
          me = parts.length - 1;
          if (inst) return;
        }
        Array.prototype.forEach.call(el.children, function (ch) { walk(ch, me); });
      })(root, null);
      var count = {}, seen = {}, out = {};
      parts.forEach(function (p) { count[p.base] = (count[p.base] || 0) + 1; });
      parts.forEach(function (p) {
        var name;
        if (p.base === 'root' && p.parent === null) name = 'root';
        else if (count[p.base] > 1 || p.base === 'root') { seen[p.base] = (seen[p.base] || 0) + 1; name = p.base + '-' + seen[p.base]; }
        else name = p.base;
        out[name] = p.el;
      });
      return out;
    }
    function pbSpecRoot(host) {
      var fit = host.querySelector('.ds-fit');
      if (fit) return fit.querySelector('[data-part="root"]') || fit.firstElementChild;
      for (var i = 0; i < host.children.length; i++) {
        var ch = host.children[i];
        if (!ch.classList.contains('pb-spec-ovl') && !ch.classList.contains('pb-spec-bar')) return ch;
      }
      return null;
    }

    /* ---- measure: one model of the live render — boxes in the overlay's own coordinates, CSS lengths ---- */
    function pbSpecMetrics(el) {
      var cs = getComputedStyle(el);
      function n(p) { var v = parseFloat(cs[p]); return v > 0 || v < 0 ? v : 0; }
      function rad(p) { var s = String(cs[p]); return s.indexOf('%') > -1 ? s.split(' ')[0] : n(p); }
      return {
        pd: [n('paddingTop'), n('paddingRight'), n('paddingBottom'), n('paddingLeft')],
        mg: [n('marginTop'), n('marginRight'), n('marginBottom'), n('marginLeft')],
        bw: [n('borderTopWidth'), n('borderRightWidth'), n('borderBottomWidth'), n('borderLeftWidth')],
        gx: n('columnGap'), gy: n('rowGap'),
        rad: [rad('borderTopLeftRadius'), rad('borderTopRightRadius'), rad('borderBottomRightRadius'), rad('borderBottomLeftRadius')],
        disp: cs.display, fill: cs.backgroundColor, ink: cs.color
      };
    }
    function pbSpecModel(rec) {
      var host = rec.host, root = pbSpecRoot(host), ovl = rec.ovl;
      if (!root || !ovl) return null;
      var c = rec.comp || {}, list = pbSpecPartList(c), live = pbSpecLive(root, c);
      var orc = ovl.getBoundingClientRect(), k = ovl.offsetWidth ? orc.width / ovl.offsetWidth : 1;
      if (!(k > 0)) k = 1;
      var rr = root.getBoundingClientRect(), ks = root.offsetWidth ? rr.width / root.offsetWidth : k, s = ks / k;
      if (!(s > 0)) s = 1;
      function box(el) {
        var r = el.getBoundingClientRect();
        return { x: (r.left - orc.left) / k, y: (r.top - orc.top) / k, w: r.width / k, h: r.height / k };
      }
      var meta = {}, names = ['root'], extra = [];
      if (list) {
        list.forEach(function (p) { meta[p.name] = p; names.push(p.name); });
        Object.keys(live).forEach(function (nm) { if (nm !== 'root' && !meta[nm]) extra.push(nm); });
      } else {
        Object.keys(live).forEach(function (nm, i) { if (nm !== 'root') { meta[nm] = { n: names.length, type: null }; names.push(nm); } });
      }
      var parts = names.concat(extra).map(function (name) {
        var el = live[name], mt = meta[name] || {};
        var P = { name: name, n: name === 'root' ? 0 : (mt.n || 0), type: name === 'root' ? 'container' : mt.type, instanceOf: mt.instanceOf, el: el || null, shown: false };
        if (el) {
          if (!P.type) P.type = (el !== root && el.getAttribute('data-cmp')) ? 'instance' : null;
          if (P.type === 'instance' && !P.instanceOf) P.instanceOf = el.getAttribute('data-cmp') || '';
          P.box = box(el);
          P.shown = P.box.w > 0 || P.box.h > 0;
          if (P.shown) {
            P.m = pbSpecMetrics(el);
            P.hasText = P.type !== 'instance' && Array.prototype.some.call(el.childNodes, function (nd) { return nd.nodeType === 3 && /\S/.test(nd.nodeValue); });
          }
        }
        return P;
      });
      return { k: k, s: s, root: parts[0], parts: parts, extra: extra, box: box, ow: ovl.offsetWidth, oh: ovl.offsetHeight };
    }
    /* the sidecar's own token for a value, when it recorded one — a hint, never a source of geometry */
    function pbSpecHint(c, name, key, side) {
      var st = c && c.elements && c.elements[name] && c.elements[name].styles, e = st && st[key];
      if (!e || typeof e !== 'object') return null;
      return (side && e.tokens && e.tokens[side]) || e.token || null;
    }
    var PB_SPEC_SIDES = ['top', 'right', 'bottom', 'left'];
    /* one row of facts about a part, for a table: lengths as {v, tok}; null where the part has none */
    function pbSpecRow(P, c) {
      var r = { name: P.name, type: P.type || '', instanceOf: P.instanceOf || '', shown: P.shown };
      if (!P.shown) return r;
      var m = P.m;
      function len(v, kind, hint) { return { v: pbSpecR(v), tok: pbSpecTok(kind, v, hint) }; }
      r.mg = m.mg.map(function (v, i) { return len(v, 'space', null); });
      if (P.type === 'instance') return r;
      r.pd = m.pd.map(function (v, i) { return len(v, 'space', pbSpecHint(c, P.name, 'padding', PB_SPEC_SIDES[i])); });
      r.gap = (/flex|grid/.test(m.disp) && (m.gx > 0 || m.gy > 0))
        ? [len(m.gy, 'space', pbSpecHint(c, P.name, 'itemSpacing')), len(m.gx, 'space', pbSpecHint(c, P.name, 'itemSpacing'))] : null;
      r.rad = m.rad.map(function (v) { return typeof v === 'string' ? { v: v, tok: null } : len(v, 'radius', pbSpecHint(c, P.name, 'cornerRadius')); });
      var fill = pbSpecNormColor(m.fill);
      r.fill = (fill && !(fill.length === 9 && fill.slice(7) === '00')) ? { v: fill, tok: pbSpecTok('color', fill, pbSpecHint(c, P.name, 'backgroundColor')) } : null;
      var ink = P.hasText ? pbSpecNormColor(m.ink) : null;
      r.text = ink ? { v: ink, tok: pbSpecTok('color', ink, pbSpecHint(c, P.name, 'textColor')) } : null;
      return r;
    }

    /* ---- draw ---- */
    function pbSpecHit(a, b) { return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h; }
    function pbSpecFree(box, placed) {
      for (var i = 0; i < placed.length; i++) if (pbSpecHit(box, placed[i])) return false;
      return true;
    }
    /* markers on one side, spread so none overlaps, each kept over its own part */
    function pbSpecSpread(arr) {
      arr.sort(function (a, b) { return a.want - b.want; });
      var prev = -1e9;
      arr.forEach(function (m) {
        m.pos = Math.max(m.want, prev + 26);
        m.pos = Math.min(m.pos, Math.max(m.lo, m.hi));
        prev = m.pos;
      });
    }
    function pbSpecLead(x, y, w, h, kind, name) {
      return '<i class="pb-sp-ld pb-sp-ll" data-kind="' + kind + '" data-for="' + pbUiEsc(name) + '" style="left:' + pbSpecPx(x) + ';top:' + pbSpecPx(y)
        + ';width:' + pbSpecPx(Math.max(0, w)) + ';height:' + pbSpecPx(Math.max(0, h)) + '"></i>';
    }
    /* A band's label: centred in the band when it fits, else outside by a leader — to the right or left of
       its owner for a thin horizontal band, above or below for a thin vertical one — and never on top of
       a label or marker already placed (it tries the next spot; the first is the fallback). */
    function pbSpecPlace(r, text, owner, kind, name, placed) {
      var W = text.length * 6.6 + 10, H = 16, cx = r.x + r.w / 2, cy = r.y + r.h / 2, t = pbUiEsc(text), nm = pbUiEsc(name), cand = [];
      function lab(x, y, cls, box, lead) {
        return { box: box, html: (lead || '') + '<span class="pb-sp-lab' + (cls ? ' ' + cls : '') + '" data-kind="' + kind + '" data-for="' + nm + '"'
          + ' style="left:' + pbSpecPx(x) + ';top:' + pbSpecPx(y) + '">' + t + '</span>' };
      }
      if (r.w >= W && r.h >= H - 2) cand.push(lab(cx, cy, '', { x: cx - W / 2, y: cy - H / 2, w: W, h: H }));
      if (r.h > r.w && r.w >= H - 4 && r.h >= W) cand.push(lab(cx, cy, 'is-v', { x: cx - H / 2, y: cy - W / 2, w: H, h: W }));
      // a label stepped aside to clear the others (j ≠ 0) keeps its leader: an elbow, so it still reaches the band
      function ld(x, y, w, h) { return pbSpecLead(x, y, w, h, kind, name); }
      var STEPS = [0, 1, -1, 2, -2, 3, -3];
      if (r.w >= r.h) {
        STEPS.forEach(function (j) {
          var x = owner.x + owner.w + 6, y = cy + j * (H + 2);
          cand.push(lab(x, y, 'is-r', { x: x, y: y - H / 2, w: W, h: H },
            ld(r.x + r.w, cy - 0.5, x - r.x - r.w, 1) + (j ? ld(x - 0.5, Math.min(cy, y), 1, Math.abs(y - cy)) : '')));
        });
        STEPS.forEach(function (j) {
          var x = owner.x - 6, y = cy + j * (H + 2);
          cand.push(lab(x, y, 'is-l', { x: x - W, y: y - H / 2, w: W, h: H },
            ld(x, cy - 0.5, r.x - x, 1) + (j ? ld(x - 0.5, Math.min(cy, y), 1, Math.abs(y - cy)) : '')));
        });
      } else {
        STEPS.forEach(function (j) {
          var y = owner.y - 6, x = cx + j * (W + 4);
          cand.push(lab(x, y, 'is-u', { x: x - W / 2, y: y - H, w: W, h: H },
            ld(cx - 0.5, y, 1, r.y - y) + (j ? ld(Math.min(cx, x), y - 0.5, Math.abs(x - cx), 1) : '')));
        });
        STEPS.forEach(function (j) {
          var y = owner.y + owner.h + 6, x = cx + j * (W + 4);
          cand.push(lab(x, y, 'is-d', { x: x - W / 2, y: y, w: W, h: H },
            ld(cx - 0.5, r.y + r.h, 1, y - r.y - r.h) + (j ? ld(Math.min(cx, x), y - 0.5, Math.abs(x - cx), 1) : '')));
        });
      }
      // last resorts, for a band with no room beside it (the render fills its host): the label over the band's own end
      if (r.w >= r.h) {
        cand.push(lab(r.x + r.w - 2, cy, 'is-l', { x: r.x + r.w - 2 - W, y: cy - H / 2, w: W, h: H }));
        cand.push(lab(r.x + 2, cy, 'is-r', { x: r.x + 2, y: cy - H / 2, w: W, h: H }));
      } else {
        cand.push(lab(cx, r.y + 2, 'is-d', { x: cx - W / 2, y: r.y + 2, w: W, h: H }));
        cand.push(lab(cx, r.y + r.h - 2, 'is-u', { x: cx - W / 2, y: r.y + r.h - 2 - H, w: W, h: H }));
      }
      // a spot inside the overlay and clear of the others; else one inside it; else one clear of the others; else the first
      function inside(b) { return !placed.W || (b.x >= 0 && b.y >= 0 && b.x + b.w <= placed.W && b.y + b.h <= placed.H); }
      var pick = null, i;
      for (i = 0; i < cand.length && !pick; i++) if (inside(cand[i].box) && pbSpecFree(cand[i].box, placed)) pick = cand[i];
      for (i = 0; i < cand.length && !pick; i++) if (inside(cand[i].box)) pick = cand[i];
      for (i = 0; i < cand.length && !pick; i++) if (pbSpecFree(cand[i].box, placed)) pick = cand[i];
      pick = pick || cand[0];
      if (!pick) return '';
      placed.push(pick.box);
      return pick.html;
    }
    function pbSpecBand(kind, name, r) {
      return '<i class="pb-sp-band" data-kind="' + kind + '" data-for="' + pbUiEsc(name) + '" style="' + pbSpecAt(r) + '"></i>';
    }
    /* ANATOMY → { under, over }: outlines + leaders, then the numbered markers */
    function pbSpecDrawAnatomy(M, placed) {
      var rb = M.root.box, under = '', over = '', left = [], top = [];
      M.parts.forEach(function (p) {
        if (!p.n || !p.shown || p === M.root) return;
        var b = p.box;
        under += '<i class="pb-sp-rc" data-for="' + pbUiEsc(p.name) + '" style="' + pbSpecAt(b) + '"></i>';
        // a part that spans the component (a stacked row) is marked from the left; a narrow one from above
        if (b.w > rb.w * 0.6) left.push({ p: p, b: b, want: b.y + b.h / 2, lo: b.y + 4, hi: b.y + b.h - 4 });
        else top.push({ p: p, b: b, want: b.x + b.w / 2, lo: b.x + 4, hi: b.x + b.w - 4 });
      });
      pbSpecSpread(left); pbSpecSpread(top);
      left.forEach(function (m) {
        var x = Math.max(rb.x - 22, 11), y = m.pos, nm = pbUiEsc(m.p.name);
        under += '<i class="pb-sp-ld" data-for="' + nm + '" style="left:' + pbSpecPx(x + 11) + ';top:' + pbSpecPx(y - 0.75) + ';width:'
          + pbSpecPx(Math.max(0, m.b.x - x - 11)) + ';height:1.5px"></i>';
        over += '<span class="pb-sp-mk" data-for="' + nm + '" style="left:' + pbSpecPx(x) + ';top:' + pbSpecPx(y) + '">' + m.p.n + '</span>';
        placed.push({ x: x - 11, y: y - 11, w: 22, h: 22 });
      });
      top.forEach(function (m) {
        var x = m.pos, y = Math.max(rb.y - 22, 11), nm = pbUiEsc(m.p.name);
        under += '<i class="pb-sp-ld" data-for="' + nm + '" style="left:' + pbSpecPx(x - 0.75) + ';top:' + pbSpecPx(y + 11) + ';width:1.5px;height:'
          + pbSpecPx(Math.max(0, m.b.y - y - 11)) + '"></i>';
        over += '<span class="pb-sp-mk" data-for="' + nm + '" style="left:' + pbSpecPx(x) + ';top:' + pbSpecPx(y) + '">' + m.p.n + '</span>';
        placed.push({ x: x - 11, y: y - 11, w: 22, h: 22 });
      });
      return { under: under, over: over };
    }
    /* SPEC → { bands, labels }: margin (a ring outside the border box) · padding (inside it) · gap (between children) */
    function pbSpecDrawSpec(M, L, c, placed) {
      var bands = '', labels = '', s = M.s;
      M.parts.forEach(function (P) {
        if (!P.shown) return;
        var b = P.box, m = P.m, inst = P.type === 'instance', nm = P.name;
        if (L.margin) {
          var mt = m.mg[0] * s, mr = m.mg[1] * s, mb = m.mg[2] * s, ml = m.mg[3] * s;
          var ring = { x: b.x - Math.max(ml, 0), y: b.y - Math.max(mt, 0), w: b.w + Math.max(ml, 0) + Math.max(mr, 0), h: b.h + Math.max(mt, 0) + Math.max(mb, 0) };
          [['top', { x: ring.x, y: ring.y, w: ring.w, h: mt }, m.mg[0]], ['bottom', { x: ring.x, y: b.y + b.h, w: ring.w, h: mb }, m.mg[2]],
           ['left', { x: ring.x, y: b.y, w: ml, h: b.h }, m.mg[3]], ['right', { x: b.x + b.w, y: b.y, w: mr, h: b.h }, m.mg[1]]].forEach(function (sd) {
            if (!(sd[2] > 0) || sd[1].w <= 0 || sd[1].h <= 0) return;
            bands += pbSpecBand('margin-' + sd[0], nm, sd[1]);
            labels += pbSpecPlace(sd[1], pbSpecLabel('space', sd[2], null), ring, 'margin', nm, placed);
          });
        }
        if (inst) return;                           // an instance's insides are its own
        var bt = m.bw[0] * s, br = m.bw[1] * s, bb = m.bw[2] * s, bl = m.bw[3] * s;
        var pt = m.pd[0] * s, pr = m.pd[1] * s, pb = m.pd[2] * s, pl = m.pd[3] * s;
        if (L.padding) {
          var innerH = b.h - bt - bb - pt - pb;
          [['top', { x: b.x + bl, y: b.y + bt, w: b.w - bl - br, h: pt }],
           ['bottom', { x: b.x + bl, y: b.y + b.h - bb - pb, w: b.w - bl - br, h: pb }],
           ['left', { x: b.x + bl, y: b.y + bt + pt, w: pl, h: innerH }],
           ['right', { x: b.x + b.w - br - pr, y: b.y + bt + pt, w: pr, h: innerH }]].forEach(function (sd, i) {
            var v = m.pd[[0, 2, 3, 1][i]];
            if (!(v > 0) || sd[1].w <= 0 || sd[1].h <= 0) return;
            bands += pbSpecBand('padding-' + sd[0], nm, sd[1]);
            labels += pbSpecPlace(sd[1], pbSpecLabel('space', v, pbSpecHint(c, nm, 'padding', sd[0])), b, 'padding', nm, placed);
          });
        }
        if (L.gap && /flex|grid/.test(m.disp)) {
          var kids = Array.prototype.filter.call(P.el.children, function (ch) {
            var cs = getComputedStyle(ch);
            return cs.position !== 'absolute' && cs.position !== 'fixed' && cs.display !== 'none' && cs.display !== 'contents';
          }).map(function (ch) {
            var cs = getComputedStyle(ch), q = function (p) { return (parseFloat(cs[p]) || 0) * s; };
            return { b: M.box(ch), mt: q('marginTop'), mr: q('marginRight'), mb: q('marginBottom'), ml: q('marginLeft') };
          }).filter(function (q) { return q.b.w > 0 || q.b.h > 0; });
          var cx0 = b.x + bl + pl, cx1 = b.x + b.w - br - pr, cy0 = b.y + bt + pt, cy1 = b.y + b.h - bb - pb, done = {};
          for (var i = 0; i + 1 < kids.length; i++) {
            var A = kids[i], B = kids[i + 1], r = null, g = 0;
            if (B.b.y >= A.b.y + A.b.h - 0.5) {          // the next one starts below: a vertical gap
              var y0 = A.b.y + A.b.h + A.mb, y1 = B.b.y - B.mt;
              if (y1 - y0 >= 0.5) { r = { x: cx0, y: y0, w: cx1 - cx0, h: y1 - y0 }; g = m.gy; }
            } else if (B.b.x >= A.b.x + A.b.w - 0.5) {   // the next one starts to the right: a horizontal gap
              var x0 = A.b.x + A.b.w + A.mr, x1 = B.b.x - B.ml;
              if (x1 - x0 >= 0.5) { r = { x: x0, y: cy0, w: x1 - x0, h: cy1 - cy0 }; g = m.gx; }
            }
            if (!r || r.w <= 0 || r.h <= 0) continue;
            var key = [r.x, r.y, r.w, r.h].map(pbSpecR).join(',');
            if (done[key]) continue;
            done[key] = 1;
            var d = (r.w < r.h ? r.w : r.h) / s, near = g > 0 && Math.abs(d - g) <= 0.6;
            bands += pbSpecBand('gap', nm, r);
            labels += pbSpecPlace(r, near ? pbSpecLabel('space', g, pbSpecHint(c, nm, 'itemSpacing')) : 'auto', b, 'gap', nm, placed);
          }
        }
      });
      return { bands: bands, labels: labels };
    }
    function pbSpecEff(rec) { return rec.layers || PB_SPEC_LAYERS; }
    function pbSpecEnsureOvl(rec) {
      var o = rec.ovl;
      if (!o || o.parentNode !== rec.host) {
        o = null;
        for (var i = 0; i < rec.host.children.length; i++) if (rec.host.children[i].classList.contains('pb-spec-ovl')) o = rec.host.children[i];
        if (!o) {
          o = document.createElement('div');
          o.className = 'pb-spec-ovl'; o.setAttribute('aria-hidden', 'true');
          rec.host.appendChild(o);
        }
        rec.ovl = o; rec.last = '';
      }
      return o;
    }
    function pbSpecWatch(rec, root) {
      if (rec.watched === root || !PB_SPEC_RO) return;
      if (rec.watched) { try { PB_SPEC_RO.unobserve(rec.watched); } catch (e) { /* gone */ } rec.watched.__pbSpecOf = null; }
      rec.watched = root; root.__pbSpecOf = rec;
      PB_SPEC_RO.observe(root);
    }
    /* Draw one host. → true when what it shows changed. Hidden hosts (a tab nobody is on) draw nothing. */
    function pbSpecDraw(rec) {
      var host = rec.host;
      if (!host.isConnected || !host.getClientRects().length) return false;
      var L = pbSpecEff(rec), want = !!(L.anatomy || L.spec), ovl;
      host.classList.toggle('is-anat', !!L.anatomy);
      ovl = pbSpecEnsureOvl(rec);
      ovl.classList.toggle('is-labels', !!L.labels);
      if (!want && !rec.rows && !rec.listen) {
        rec.parts = [];
        if (!rec.last) return false;
        ovl.innerHTML = ''; rec.last = '';
        return true;
      }
      var M = pbSpecModel(rec);
      if (!M) { rec.parts = []; if (rec.last) { ovl.innerHTML = ''; rec.last = ''; } return false; }
      pbSpecWatch(rec, M.root.el);
      var live = M.parts.filter(function (p) { return p.el && p.shown; });
      rec.parts = live.map(function (p) {      // each with the part that holds it, for pbSpecApplyHot's fallback
        var up = null;
        for (var n = p.el.parentNode; n && n !== host && !up; n = n.parentNode) {
          for (var i = 0; i < live.length; i++) if (live[i].el === n) { up = live[i].name; break; }
        }
        return { name: p.name, el: p.el, up: up };
      });
      var html = '';
      if (want && M.root.shown) {
        var placed = []; placed.W = M.ow; placed.H = M.oh;
        var an = L.anatomy ? pbSpecDrawAnatomy(M, placed) : { under: '', over: '' };
        var sp = L.spec ? pbSpecDrawSpec(M, L, rec.comp || {}, placed) : { bands: '', labels: '' };
        html = sp.bands + an.under + sp.labels + an.over;
      }
      var changed = html !== rec.last;
      if (changed) { ovl.innerHTML = html; rec.last = html; pbSpecApplyHot(rec); }
      var info = {
        cid: (rec.comp && rec.comp.id) || '',
        parts: M.parts.filter(function (p) { return p !== M.root; }).map(function (p) { return { name: p.name, n: p.n, shown: p.shown, type: p.type || '', instanceOf: p.instanceOf || '' }; }),
        extra: M.extra
      };
      if (rec.rows) info.rows = M.parts.map(function (p) { return pbSpecRow(p, rec.comp || {}); });
      var sig = JSON.stringify(info);
      if (sig !== rec.sig) {
        rec.sig = sig; changed = true;
        info.host = host;
        pbEmit(host, 'pb:specdraw', info);
      }
      return changed;
    }
    /* Redraw every frame until the boxes stop moving (the product's own CSS transitions run for ≤ ~600ms). */
    function pbSpecSettle(rec) {
      if (typeof requestAnimationFrame === 'undefined' || !rec.host.isConnected || !rec.host.getClientRects().length) return;
      rec.t0 = Date.now(); rec.stable = 0;
      if (rec.raf) return;
      rec.raf = requestAnimationFrame(function step() {
        rec.raf = 0;
        rec.stable = pbSpecDraw(rec) ? 0 : rec.stable + 1;
        if (rec.stable < 4 && Date.now() - rec.t0 < 600) rec.raf = requestAnimationFrame(step);
      });
    }
    function pbSpecRedrawAll() {
      PB_SPEC_RECS = PB_SPEC_RECS.filter(function (r) {
        if (r.host.isConnected) return true;
        if (r.watched && PB_SPEC_RO) { try { PB_SPEC_RO.unobserve(r.watched); } catch (e) { /* gone */ } }
        try { PB_SPEC_RO.unobserve(r.host); } catch (e2) { /* gone */ }
        return false;
      });
      PB_SPEC_RECS.forEach(pbSpecSettle);
    }

    /* ---- which part is being read: its labels show, its bands and outline are emphasised ----
       rec.hot holds one name per source — hover, focus, link (a legend row, from pbSpecHot) and pin (a tap);
       the part read is the first of pin · link · hover · focus. It lives as an `is-hot` class on the overlay's
       own nodes (matched by data-for), so reading a part never redraws anything. A part on the render that has
       nothing of its own drawn (a bare text inside a padded card) reads as the part that holds it — what
       surrounds it; a legend row never does: its row already says the part has none. */
    function pbSpecApplyHot(rec) {
      var ovl = rec.ovl; if (!ovl) return;
      var nodes = ovl.querySelectorAll('[data-for]'), have = {}, h = rec.hot || {}, name = null, up = {};
      Array.prototype.forEach.call(nodes, function (n) { have[n.getAttribute('data-for')] = 1; });
      (rec.parts || []).forEach(function (p) { up[p.name] = p.up; });
      var src = h.pin ? 'pin' : h.link ? 'link' : h.hover ? 'hover' : h.focus ? 'focus' : null;
      name = src ? h[src] : null;
      if (src && src !== 'link') for (var i = 0; name && !have[name] && i < 16; i++) name = up[name] || null;
      var any = false;
      Array.prototype.forEach.call(nodes, function (n) {
        var on = !!name && n.getAttribute('data-for') === name;
        any = any || on;
        n.classList.toggle('is-hot', on);
      });
      ovl.classList.toggle('has-hot', any);
    }
    function pbSpecHot(host, name, src) {
      var rec = host && host.__pbSpec; if (!rec) return;
      src = src || 'link';
      rec.hot = rec.hot || {};
      if ((rec.hot[src] || null) === (name || null)) return;
      rec.hot[src] = name || null;
      pbSpecApplyHot(rec);
    }
    function pbSpecPin(host, name) {
      var rec = host && host.__pbSpec; if (!rec) return;
      rec.hot = rec.hot || {};
      rec.hot.pin = (name && rec.hot.pin !== name) ? name : null;
      pbSpecApplyHot(rec);
    }
    /* the part under a node: the deepest of the host's measured parts that contains it (null: the host's own padding) */
    function pbSpecPartAt(rec, t) {
      var list = rec.parts || [];
      for (var n = t; n && n.nodeType === 1 && n !== rec.host; n = n.parentNode) {
        for (var i = 0; i < list.length; i++) if (list[i].el === n) return list[i].name;
      }
      return null;
    }
    function pbSpecHostAt(t) {
      var h = t && t.closest ? t.closest('.pb-spec-host') : null;
      return h && h.__pbSpec ? h : null;
    }
    /* a legend row ([data-part-row="<part>"]) → { host, name }: the host is the first one found going up from the
       row, so a row reads the specimen or the variant cell of its own card */
    function pbSpecRowAt(t) {
      var row = t && t.closest ? t.closest('[data-part-row]') : null;
      if (!row) return null;
      for (var a = row.parentNode; a && a.querySelector; a = a.parentNode) {
        var h = a.querySelector('.pb-spec-host');
        if (h) return h.__pbSpec ? { host: h, name: row.getAttribute('data-part-row') } : null;
      }
      return null;
    }

    /* ---- mount · update · morph ---- */
    function pbSpecHostAttrs(kind, cid, props, layers) {
      pbSpecInstall();
      var key = 'p' + (++PB_SPEC_N);
      PB_SPEC_PROPS[key] = props || {};
      return ' data-pb-spec="' + pbUiEsc(kind) + '" data-pb-cid="' + pbUiEsc(cid) + '" data-pb-props="' + key + '"'
        + (layers ? ' data-pb-layers="' + pbUiEsc(layers) + '"' : '');
    }
    function pbSpecScan(root) {
      if (!root || !root.querySelectorAll) return;
      var sel = '[data-pb-spec]:not([data-pb-spec-on])', list = pbEls(sel, root);
      if (root.matches && root.matches(sel)) list.unshift(root);
      list.forEach(function (h) {
        var c = pbOrgById()[h.getAttribute('data-pb-cid')];
        if (c) pbSpecMount(h, c, PB_SPEC_PROPS[h.getAttribute('data-pb-props')] || {}, { kind: h.getAttribute('data-pb-spec') });
      });
    }
    function pbSpecMount(host, comp, props, o) {
      if (!host || typeof document === 'undefined' || host.nodeType !== 1) return null;
      o = o || {};
      pbSpecInstall();
      var rec = host.__pbSpec;
      if (!rec) {
        var kind = o.kind || host.getAttribute('data-pb-spec') || 'stage', forced = o.layers || host.getAttribute('data-pb-layers');
        rec = host.__pbSpec = { host: host, kind: kind, comp: null, props: null, ovl: null, last: '', sig: '', raf: 0, t0: 0, stable: 0,
          rows: kind === 'cell', listen: kind !== 'stage', layers: null, watched: null };
        if (forced) rec.layers = { anatomy: forced === 'anatomy', spec: forced === 'spec', margin: true, padding: true, gap: true };
        host.classList.add('pb-spec-host');
        host.setAttribute('data-pb-spec-on', '');
        PB_SPEC_RECS.push(rec);
        if (PB_SPEC_RO) PB_SPEC_RO.observe(host);
      }
      if (comp) rec.comp = comp;
      if (props) rec.props = props;
      if (o.rows != null) rec.rows = !!o.rows;
      pbSpecEnsureOvl(rec);
      var slot = typeof o.layersSlot === 'string' ? document.querySelector(o.layersSlot) : o.layersSlot;
      if (slot && !slot.querySelector('[data-pb-layers]')) slot.insertAdjacentHTML('beforeend', pbSpecLayersHTML());
      pbSpecSettle(rec);
      return { host: host, redraw: function () { pbSpecSettle(rec); }, update: function (p, oo) { pbSpecUpdate(host, p, oo); } };
    }
    function pbSpecUpdate(host, props, o) {
      var rec = host && host.__pbSpec;
      if (!rec) return null;
      o = o || {};
      if (props) rec.props = props;
      var html = o.html;
      if (html == null && o.render && rec.comp && typeof window[rec.comp.renderFn] === 'function') {
        try { html = window[rec.comp.renderFn](rec.props || {}); } catch (e) { html = null; }
      }
      if (html != null) {
        var fit = host.querySelector('.ds-fit');
        if (fit) pbSpecMorph(fit, String(html));
      }
      pbSpecEnsureOvl(rec);
      pbSpecSettle(rec);
      return rec;
    }
    /* Patch `parent`'s children into `html` in place — same element, new attributes — so a CSS transition on the
       product's own styles runs between the two renders. Positional: an element that changes tag is replaced. */
    function pbSpecMorph(parent, html) {
      var tpl = document.createElement('template');
      tpl.innerHTML = html;
      pbSpecMorphKids(parent, tpl.content);
    }
    function pbSpecMorphKids(a, b) {
      var i, x, y;
      for (i = 0; i < b.childNodes.length; i++) {
        x = a.childNodes[i]; y = b.childNodes[i];
        if (!x) { a.appendChild(y.cloneNode(true)); continue; }
        if (x.nodeType !== y.nodeType || (x.nodeType === 1 && x.nodeName !== y.nodeName)) { a.replaceChild(y.cloneNode(true), x); continue; }
        if (x.nodeType !== 1) { if (x.nodeValue !== y.nodeValue) x.nodeValue = y.nodeValue; continue; }
        pbSpecMorphAttrs(x, y);
        pbSpecMorphKids(x, y);
      }
      while (a.childNodes.length > b.childNodes.length) a.removeChild(a.lastChild);
    }
    function pbSpecMorphAttrs(x, y) {
      Array.prototype.slice.call(x.attributes).forEach(function (at) {
        if (!y.hasAttribute(at.name) && at.name !== 'data-part') x.removeAttribute(at.name);
      });
      Array.prototype.forEach.call(y.attributes, function (at) {
        if (x.getAttribute(at.name) !== at.value) x.setAttribute(at.name, at.value);
      });
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(x.nodeName)) {
        if ('value' in y && x.value !== y.value) x.value = y.value;
        if ('checked' in y && x.checked !== y.checked) x.checked = y.checked;
      }
    }

    /* ---- the page-wide wiring: one click listener, one ResizeObserver, one MutationObserver ---- */
    function pbSpecMutations(recs) {
      var hit = [], added = [];
      recs.forEach(function (m) {
        var t = m.target.nodeType === 1 ? m.target : m.target.parentNode;
        if (!t || t.nodeType !== 1 || (t.closest && t.closest('.pb-spec-ovl'))) return;
        if (m.type === 'childList') {
          var real = false, j;
          for (j = 0; j < m.addedNodes.length; j++) {
            var n = m.addedNodes[j];
            if (n.nodeType === 1 && !n.classList.contains('pb-spec-ovl')) { real = true; added.push(n); }
            else if (n.nodeType !== 1) real = true;
          }
          for (j = 0; j < m.removedNodes.length; j++) {
            if (!(m.removedNodes[j].nodeType === 1 && m.removedNodes[j].classList.contains('pb-spec-ovl'))) real = true;
          }
          if (!real) return;
        }
        var h = t.closest && t.closest('.pb-spec-host');
        if (h && h.__pbSpec && hit.indexOf(h.__pbSpec) < 0) hit.push(h.__pbSpec);
      });
      added.forEach(pbSpecScan);
      hit.forEach(pbSpecSettle);
    }
    function pbSpecInstall() {
      if (PB_SPEC_UP || typeof document === 'undefined' || typeof window === 'undefined' || !document.body) return;
      PB_SPEC_UP = true;
      try {
        var saved = JSON.parse(pbUiStore(PB_SPEC_STORE) || 'null');
        if (saved && typeof saved === 'object') Object.keys(PB_SPEC_LAYERS).forEach(function (k) { if (typeof saved[k] === 'boolean') PB_SPEC_LAYERS[k] = saved[k]; });
      } catch (e) { /* the defaults apply */ }
      document.addEventListener('click', function (e) {
        var pt = PB_SPEC_PT; PB_SPEC_PT = '';
        var b = e.target && e.target.closest && e.target.closest('[data-pb-layer]');
        if (b) { pbSpecSetLayer(b.getAttribute('data-pb-layer'), !PB_SPEC_LAYERS[b.getAttribute('data-pb-layer')]); return; }
        // a tap (no hover on touch): the part tapped keeps its labels until it is tapped again; a tap elsewhere lets go
        if ((pt === 'touch' || pt === 'pen') && !(e.target.closest && e.target.closest('[data-pb-layers]'))) {
          var th = pbSpecHostAt(e.target), tr = pbSpecRowAt(e.target), host = th || (tr && tr.host);
          PB_SPEC_RECS.forEach(function (r) { if (r.host !== host && r.hot && r.hot.pin) { r.hot.pin = null; pbSpecApplyHot(r); } });
          if (host) pbSpecPin(host, th ? pbSpecPartAt(th.__pbSpec, e.target) : tr.name);
        }
      });
      document.addEventListener('pointerdown', function (e) { PB_SPEC_PT = e.pointerType || ''; }, true);
      document.addEventListener('keydown', function () { PB_SPEC_PT = ''; }, true);
      // hover (a mouse or a pen — touch has no hover): the part under the pointer, and the legend row under it
      var over = null, linked = null;
      function letGo() {
        if (over) pbSpecHot(over, null, 'hover');
        if (linked) pbSpecHot(linked, null, 'link');
        over = linked = null;
      }
      document.addEventListener('pointerover', function (e) {
        if (e.pointerType === 'touch') return;
        var h = pbSpecHostAt(e.target), row = pbSpecRowAt(e.target);
        if (over && over !== h) pbSpecHot(over, null, 'hover');
        over = h;
        if (h) pbSpecHot(h, pbSpecPartAt(h.__pbSpec, e.target), 'hover');
        if (linked && (!row || linked !== row.host)) pbSpecHot(linked, null, 'link');
        linked = row ? row.host : null;
        if (row) pbSpecHot(row.host, row.name, 'link');
      });
      document.addEventListener('pointerout', function (e) { if (!e.relatedTarget) letGo(); });
      // keyboard focus (never the focus a click leaves behind): a part's own control, or a control in its legend row
      document.addEventListener('focusin', function (e) {
        var t = e.target, vis = true;
        try { vis = t.matches(':focus-visible'); } catch (err) { /* an old engine: any focus counts */ }
        if (!vis) return;
        var h = pbSpecHostAt(t), row = pbSpecRowAt(t);
        if (h) pbSpecHot(h, pbSpecPartAt(h.__pbSpec, t), 'focus');
        if (row) pbSpecHot(row.host, row.name, 'focus');
      });
      document.addEventListener('focusout', function (e) {
        var h = pbSpecHostAt(e.target), row = pbSpecRowAt(e.target);
        if (h) pbSpecHot(h, null, 'focus');
        if (row) pbSpecHot(row.host, null, 'focus');
      });
      if (window.ResizeObserver) {
        PB_SPEC_RO = new ResizeObserver(function (entries) {
          entries.forEach(function (en) { var r = en.target.__pbSpec || en.target.__pbSpecOf; if (r) pbSpecSettle(r); });
        });
      }
      if (window.MutationObserver) {
        new MutationObserver(pbSpecMutations).observe(document.documentElement, { subtree: true, childList: true, attributes: true, characterData: true });
      }
      window.addEventListener('resize', pbSpecRedrawAll);
      window.addEventListener('pb:themechange', pbSpecRedrawAll);
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(pbSpecRedrawAll);
      pbSpecScan(document);
    }
