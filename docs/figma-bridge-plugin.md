# GHN DS Bridge — plugin patch for the pb code→Figma bridge

`/pb:build-figma-handoff` (bridge mode) emits **GHN DS Bridge node JSON** via
`pb/tools/registry_to_figma.py`; you paste it into the plugin's **Code → Figma** tab and it rebuilds
linked instances. Two **targeted, additive** fixes to the plugin's `code.js` make the rebuild honor
pb's token contract. Both are backward-compatible — existing JSON/scripts keep working.

Why they matter: pb's Figma gate **G-FP6 invariant #3** requires every space / radius to be **bound to
a variable**, not a raw number. Today the builder drops token-valued spacing and only sets numeric
`cornerRadius`, and binds variables by id/key only. Until these land, the bridge emits the numeric
fallback (renders correctly) but such a push is flagged a known-limitation gap (not "done").

pb's transformer emits, for every spacing/radius, **the resolved number PLUS a `<prop>Token`
sidecar** `{ token: "<css-name>", id, key }` — so the same output upgrades to true variable binding
the moment this patch ships (graceful degrade, NS6). It also emits token refs by **name** (the DTCG
CSS-var name), so name resolution is required when a file's variable ids/keys aren't known ahead of time.

## Fix 1 — bind spacing / padding / radius variables (replaces the `n()` drop in `applyLayout`)

Add two helpers and rewrite `applyLayout` to bind a variable when a token ref is present, else set the
number (today's behavior):

```js
// Resolve a token ref { token(name), id, key } → a Variable (by id, then key, then NAME).
async function resolveVarRef(ref) {
  if (!ref || typeof ref !== "object") return null;
  try {
    if (ref.id) { var byId = await figma.variables.getVariableByIdAsync(ref.id); if (byId) return byId; }
  } catch (e) {}
  try {
    if (ref.key) { var byKey = await figma.variables.importVariableByKeyAsync(ref.key); if (byKey) return byKey; }
  } catch (e) {}
  if (ref.token) return await findLocalVariableByName(ref.token);   // Fix 2
  return null;
}

// Set an auto-layout numeric field, binding its Variable when a ref is available.
// `val` may be a number (numeric fallback) OR a { token,id,key } object (serialize round-trip);
// `tokenRef` is pb's explicit `<prop>Token` sidecar. Numeric is set first so nothing is ever dropped.
async function bindOrNum(node, prop, val, tokenRef) {
  if (typeof val === "number") { try { node[prop] = val; } catch (e) {} }
  var ref = tokenRef || (val && typeof val === "object" && (val.token || val.id || val.key) ? val : null);
  if (ref) {
    var v = await resolveVarRef(ref);
    if (v) { try { node.setBoundVariable(prop, v); } catch (e) {} }
  }
}

async function applyLayout(node, L) {
  node.layoutMode = L.mode;
  await bindOrNum(node, "itemSpacing",  L.itemSpacing,  L.itemSpacingToken);
  await bindOrNum(node, "paddingTop",   L.paddingTop,   L.paddingTopToken);
  await bindOrNum(node, "paddingRight", L.paddingRight, L.paddingRightToken);
  await bindOrNum(node, "paddingBottom",L.paddingBottom,L.paddingBottomToken);
  await bindOrNum(node, "paddingLeft",  L.paddingLeft,  L.paddingLeftToken);
  if (L.primaryAxisAlignItems) node.primaryAxisAlignItems = L.primaryAxisAlignItems;
  if (L.counterAxisAlignItems) node.counterAxisAlignItems = L.counterAxisAlignItems;
  if (L.primaryAxisSizingMode) node.primaryAxisSizingMode = L.primaryAxisSizingMode;
  if (L.counterAxisSizingMode) node.counterAxisSizingMode = L.counterAxisSizingMode;
  if (L.layoutWrap) node.layoutWrap = L.layoutWrap;
}
```

And in `buildNode`, accept a token-bound corner radius (today it is set only when numeric):

```js
// was: if (spec.cornerRadius !== undefined && typeof spec.cornerRadius === "number") node.cornerRadius = spec.cornerRadius;
if (typeof spec.cornerRadius === "number") node.cornerRadius = spec.cornerRadius;
if (spec.cornerRadiusToken || (spec.cornerRadius && typeof spec.cornerRadius === "object")) {
  var rv = await resolveVarRef(spec.cornerRadiusToken || spec.cornerRadius);
  if (rv) { try { node.setBoundVariable("topLeftRadius", rv); node.setBoundVariable("topRightRadius", rv);
                  node.setBoundVariable("bottomLeftRadius", rv); node.setBoundVariable("bottomRightRadius", rv); } catch (e) {} }
}
```

## Fix 2 — resolve a token ref by NAME (new helper)

So pb can emit portable DTCG-named refs (`{ token: "space-4" }`) without knowing a target file's
variable ids. Matches a local variable by exact name, then by the DTCG path with `-`↔`/` normalized
(a nested DS group `color/brand` ⇄ the CSS-var name `color-brand`):

```js
var _localVarCache = null;
async function findLocalVariableByName(name) {
  if (!name) return null;
  if (!_localVarCache) {
    try { _localVarCache = await figma.variables.getLocalVariablesAsync(); } catch (e) { _localVarCache = []; }
  }
  var want = String(name).toLowerCase();
  var wantSlash = want.replace(/-/g, "/");
  for (var i = 0; i < _localVarCache.length; i++) {
    var vn = String(_localVarCache[i].name || "").toLowerCase();
    if (vn === want || vn === wantSlash || vn.replace(/\//g, "-") === want) return _localVarCache[i];
  }
  return null;
}
```

> Bind paints already work (via `bindPaint`'s `tokenId`/`tokenKey`); optionally give `bindPaint` the same
> name fallback by calling `findLocalVariableByName(p.token)` when `tokenId`/`tokenKey` miss.

## After patching

Re-run the round-trip: **Figma → Code** serialize a frame, edit or author node JSON, **Code → Figma**
build. Spacing, padding, and radius should now show as **bound variables** (not raw numbers) in Figma's
inspector — which is what makes a pb bridge push satisfy G-FP6 invariant #3. Reopen the plugin after
editing `code.js` (it does not hot-reload).
