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

    // Apply registry design tokens onto :root (overrides the static fallbacks in <style>).
    function applyRegistryTokens(reg) {
      if (!reg || !reg.tokens) return;
      const root = document.documentElement;
      const resolved = pbResolveTokens(reg.tokens);
      Object.keys(resolved.flat).forEach(function (name) {
        root.style.setProperty('--' + name, resolved.flat[name]);
      });
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
      if (fn && typeof window[fn] === 'function') return window[fn](props || {});
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
     *   data-preserve="value scroll"   keep only these (value · checked · scroll · open · active)
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
