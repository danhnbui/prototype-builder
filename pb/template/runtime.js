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
