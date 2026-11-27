#!/usr/bin/env python3
"""Package-shape smoke: what a release must ship, checked without DSH.

Distribution is the plugin manager (Decision 29), so CI no longer runs an
installer to prove the package is installable. What CI can prove on a machine
with no `dsh` installed is the shape the plugin manager and the boot sync
consume:

- every ``dsh.bundle.patch`` file the manifest names exists;
- every ``exports`` entry resolves (a wildcard entry resolves to at least one
  file);
- the lane template directories the boot sync copies (``env/``, ``mcp/``,
  read from ``dsh/sync.js``) are present, with the compute lane's anchor
  files;
- no current package file references the installer 0.8.1 removed -- the
  script, its skills-only mode, a migration performed by the installer, or its
  `npx` entry point. The changelog, the architecture record and the ADRs are
  history and exempt.

Standard library only, no network, no ``dsh``: run it from the repository root
or from anywhere (paths resolve from this file). CI runs:

    python3 tests/package_shape_smoke.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "package.json"

# Assembled so this file does not match its own installer sweep.
RETIRED_DISTRIBUTION = ("".join(("install", ".sh")),
                        "".join(("--skill", "-only")),
                        "".join(("installer-driven", " migration")),
                        "".join(("npx dsh-", "rigorquant")))
# The historical record keeps the old names on purpose.
HISTORY = ("CHANGELOG.md", "docs/architecture.md")
HISTORY_PREFIXES = ("docs/adr/",)
SKIP_SUFFIXES = (".png", ".pdf", ".lock")


def fail(message):
    print("package shape: FAIL: %s" % message, file=sys.stderr)
    raise SystemExit(1)


def package_files(manifest):
    """Every file the npm package ships (the `files` list plus the manifest)."""
    files = [MANIFEST]
    for entry in manifest.get("files", []):
        path = ROOT / entry
        if entry.endswith("/"):
            if not path.is_dir():
                fail("package.json ships %r, which is not a directory" % entry)
            files.extend(p for p in path.rglob("*") if p.is_file())
        else:
            files.append(path)
    return files


def check_patch_files(manifest):
    patch = manifest.get("dsh", {}).get("bundle", {}).get("patch")
    if not patch:
        fail("the manifest declares no dsh.bundle.patch")
    for entry in patch:
        if not (ROOT / entry).is_file():
            fail("dsh.bundle.patch names a missing file: %s" % entry)
    return patch


def check_exports(manifest):
    exports = manifest.get("exports")
    if not exports:
        fail("the manifest declares no exports")
    for key, target in exports.items():
        if "*" in target:
            if not any(ROOT.glob(target)):
                fail("exports[%r] matches no file: %s" % (key, target))
        elif not (ROOT / target).is_file():
            fail("exports[%r] points at a missing file: %s" % (key, target))
    return exports


def check_lane_templates():
    """The directories rq-lane-sync copies into $DSH_HOME/share/rigorquant.

    Read from the engine itself: a directory added to (or dropped from)
    MANAGED_DIRS without shipping the template fails here rather than at the
    first profile boot.
    """
    sync = (ROOT / "dsh" / "sync.js").read_text()
    managed = re.findall(r"\['([^']+)',\s*join\(", sync)
    if not managed:
        fail("dsh/sync.js declares no MANAGED_DIRS")
    for name in managed:
        path = ROOT / name
        if not path.is_dir():
            fail("the boot sync copies %r but the package does not ship it" % name)
        if not any(p.is_file() for p in path.rglob("*")):
            fail("the boot sync copies %r but it is empty" % name)
    for anchor in ("env/pyproject.toml", "env/uv.lock"):
        if not (ROOT / anchor).is_file():
            fail("the compute lane anchor is missing: %s" % anchor)
    return managed


def check_no_installer_reference(manifest):
    offenders = []
    for path in package_files(manifest):
        rel = path.relative_to(ROOT).as_posix()
        if rel in HISTORY or rel.startswith(HISTORY_PREFIXES):
            continue
        if rel.endswith(SKIP_SUFFIXES):
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for name in RETIRED_DISTRIBUTION:
                if name in line:
                    offenders.append("%s:%d: %s" % (rel, number, line.strip()[:100]))
    if offenders:
        fail("the package still references a removed installer:\n" + "\n".join(offenders))
    return len(offenders)


def main():
    manifest = json.loads(MANIFEST.read_text())
    patch = check_patch_files(manifest)
    exports = check_exports(manifest)
    lane = check_lane_templates()
    check_no_installer_reference(manifest)
    print("package shape: OK (no DSH required)")
    print("  dsh.bundle.patch: %s" % ", ".join(patch))
    print("  exports: %d resolve" % len(exports))
    print("  lane templates: %s" % ", ".join(lane))
    print("  removed installer: 0 references")


if __name__ == "__main__":
    main()
