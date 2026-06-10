"""
pb/migrations/manifest.py — Schema version constant + migration chain.

CURRENT_SCHEMA = 3 is the single source of truth for the v1.3 registry contract.
It is intentionally decoupled from the plugin's SemVer in plugin.json:
  - Plugin SemVer bumps on any release (features, fixes, docs, refactors).
  - CURRENT_SCHEMA bumps ONLY when the registry/template contract changes
    (a new required field, a shape change, a renamed key).

Migration module contract — each 000N_slug.py must export:
  FROM: int           — schema version this migration reads
  TO: int             — schema version this migration produces
  up(reg) -> dict     — upgrade; idempotent where feasible; return the modified dict
  down(reg) -> dict   — best-effort rollback; caveats documented per module
  describe() -> str   — one-line human summary shown in the dry-run plan
  memory_notes() -> str | None  — (optional) advisory text surfaced to the user at
                        --apply for rule changes they must apply by hand to
                        memory/constitution.md. NEVER auto-written by the engine.

Phase 3–4 non-goals (see docs/migrations.md):
  - Shell-drift detection via a template version marker
  - init --import auto-running migrate
  - Richer lossy down() reversal
"""

import importlib.util
import os

CURRENT_SCHEMA = 3

# Ordered registry: (FROM, TO, filename_stem).
# Add a new tuple here when authoring a new migration.
_REGISTRY = [
    (2, 3, "0001_v12_to_v13"),
]


def _load(stem):
    """Load a migration module by filename stem, resolved relative to this file."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), stem + ".py")
    spec = importlib.util.spec_from_file_location(stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def chain(from_v: int, to_v: int):
    """Return an ordered list of migration modules for the from_v → to_v path.

    Forward (up):   from_v < to_v — modules in ascending FROM order.
    Backward (down): from_v > to_v — modules in descending TO order.
    Returns [] when from_v == to_v.
    Raises ValueError if no contiguous path exists in _REGISTRY.
    """
    if from_v == to_v:
        return []

    result = []
    cur = from_v

    if from_v < to_v:
        while cur < to_v:
            found = False
            for f, t, stem in _REGISTRY:
                if f == cur and t == cur + 1:
                    result.append(_load(stem))
                    cur += 1
                    found = True
                    break
            if not found:
                raise ValueError(
                    f"No forward migration step from schema {cur} to {cur + 1}. "
                    f"Add it to pb/migrations/_REGISTRY in manifest.py."
                )
    else:
        while cur > to_v:
            found = False
            for f, t, stem in _REGISTRY:
                if t == cur and f == cur - 1:
                    result.append(_load(stem))
                    cur -= 1
                    found = True
                    break
            if not found:
                raise ValueError(
                    f"No backward migration step from schema {cur} to {cur - 1}. "
                    f"Add it to pb/migrations/_REGISTRY in manifest.py."
                )

    return result
