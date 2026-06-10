#!/usr/bin/env python3
"""
Self-test for the Product Builder migration framework.

Runs the full dry-run → apply → rollback cycle on the
_selftest/registry.v12.json fixture and asserts correct outcomes at each step.

Stdlib-only. Usage: python3 pb/migrations/selftest.py
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_FIXTURE = os.path.join(_HERE, "_selftest", "registry.v12.json")
_RUNNER = os.path.join(_HERE, "migrate_runner.py")


def _load(path):
    with open(path) as f:
        return json.load(f)


def _assert(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)


def _run(reg_path, *extra_args, expect_rc=0):
    cmd = [sys.executable, _RUNNER, "--registry", reg_path] + list(extra_args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != expect_rc:
        sys.stderr.write(r.stderr)
        print(f"FAIL: expected exit code {expect_rc}, got {r.returncode}")
        sys.exit(1)
    return r


def main():
    _assert(os.path.exists(_FIXTURE), f"Fixture not found: {_FIXTURE}")
    _assert(os.path.exists(_RUNNER), f"Runner not found: {_RUNNER}")

    with tempfile.TemporaryDirectory() as tmpdir:
        reg_path = os.path.join(tmpdir, "registry.json")
        shutil.copy2(_FIXTURE, reg_path)
        original = _load(_FIXTURE)

        # ── Step 1: dry-run must write nothing ──────────────────────────────────
        print("Step 1: dry-run …")
        _run(reg_path)
        _assert(
            _load(reg_path) == original,
            "dry-run must not modify registry.json",
        )
        _assert(
            not os.path.isdir(os.path.join(tmpdir, ".pb-backups")),
            "dry-run must not create .pb-backups/",
        )
        print("  ✓ dry-run wrote nothing\n")

        # ── Step 2: --apply must migrate and stamp ───────────────────────────────
        print("Step 2: --apply …")
        _run(reg_path, "--apply")
        after_apply = _load(reg_path)

        _assert(
            after_apply.get("meta", {}).get("schemaVersion") == 3,
            "after --apply, meta.schemaVersion must be 3",
        )
        _assert(
            after_apply.get("meta", {}).get("device") == "desktop",
            "after --apply, meta.device must be 'desktop'",
        )
        # components[].scope: button has no dsMatch → 'local'; input has dsMatch → 'global'
        comps = {c["id"]: c for c in after_apply.get("components", [])}
        _assert(
            comps.get("button", {}).get("scope") == "local",
            "button (no dsMatch) scope must be 'local'",
        )
        _assert(
            comps.get("input", {}).get("scope") == "global",
            "input (has dsMatch) scope must be 'global'",
        )
        # Legacy flow.html/erd.html preserved
        _assert(
            "html" in after_apply.get("flow", {}),
            "legacy flow.html must be preserved after migration",
        )
        _assert(
            "html" in after_apply.get("erd", {}),
            "legacy erd.html must be preserved after migration",
        )

        bdir = os.path.join(tmpdir, ".pb-backups")
        _assert(os.path.isdir(bdir), ".pb-backups/ must be created by --apply")
        backups = [f for f in os.listdir(bdir) if f.endswith(".json")]
        _assert(len(backups) >= 1, "at least one backup must exist in .pb-backups/")

        # Validate render.py can build HTML from the migrated registry
        render_path = os.path.abspath(os.path.join(_HERE, "..", "tools", "render.py"))
        shell_path = os.path.abspath(
            os.path.join(_HERE, "..", "template", "prototype.html")
        )
        if os.path.exists(render_path) and os.path.exists(shell_path):
            rspec = importlib.util.spec_from_file_location("render", render_path)
            rmod = importlib.util.module_from_spec(rspec)
            rspec.loader.exec_module(rmod)
            with open(shell_path) as f:
                shell = f.read()
            html, missing = rmod.build_html(after_apply, shell)
            _assert(
                isinstance(html, str) and len(html) > 100,
                "render.py build_html must return non-trivial HTML",
            )
            print(f"  ✓ render.py build_html succeeded (missing fn bodies: {missing})")
        else:
            print("  ⚠ render.py or prototype.html not found — render validation skipped")

        print("  ✓ apply migrated to schema 3, backup created\n")

        # ── Step 3: --rollback must restore pre-apply state ─────────────────────
        print("Step 3: --rollback …")
        _run(reg_path, "--rollback")
        after_rollback = _load(reg_path)
        _assert(
            after_rollback == original,
            "after --rollback, registry.json must exactly match the pre-apply fixture",
        )
        _assert(
            os.path.isdir(bdir),
            ".pb-backups/ must still exist after rollback (NEVER delete backups)",
        )
        print("  ✓ rollback restored pre-apply state; backups preserved\n")

        # ── Step 4: re-apply after rollback must succeed (idempotency check) ────
        print("Step 4: re-apply after rollback (idempotency) …")
        _run(reg_path, "--apply")
        after_reapply = _load(reg_path)
        _assert(
            after_reapply.get("meta", {}).get("schemaVersion") == 3,
            "re-apply must stamp schemaVersion 3",
        )
        backups2 = [f for f in os.listdir(bdir) if f.endswith(".json")]
        _assert(
            len(backups2) >= 2,
            "each --apply must create a new backup (NEVER overwrite)",
        )
        print("  ✓ re-apply succeeded; second backup created\n")

    print("✓ All selftest steps passed.")


if __name__ == "__main__":
    main()
