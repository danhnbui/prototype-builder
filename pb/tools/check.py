#!/usr/bin/env python3
"""
check.py — deprecated compatibility shim.

The contract validator was renamed to **lint_registry.py** in v1.5.1. This module
re-exports it so nothing breaks:

  • `import check` / `from check import ...`  → still resolve (import-compat)
  • `python3 tools/check.py [--strict|--figma] ...` → still runs (CLI-compat)

Prefer `lint_registry.py`. This shim will be removed in a future major release.
"""
from lint_registry import *  # noqa: F401,F403  — re-export the public API
from lint_registry import main  # explicit, so the CLI path works even if * is restricted

if __name__ == "__main__":
    main()
