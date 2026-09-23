"""install.sh's Agent Teams half (Decision 24, issue #12).

Full install must: enable both optional Team bundles on the target profile
when they are absent, and append a `maxMembers: 64` cap override under a
`dsh-rigorquant` marker in the profile's user patch (`cordis.patch.yml`),
printing every line it wrote. A second run must write nothing new.
`--uninstall` must remove the marker and disable only the bundles the
installer itself turned on -- never one the operator already had enabled.
With no `dsh` on PATH the installer must warn and continue (this is what
keeps CI's install smoke test green).

The stub `dsh` here is a real subprocess (prior art: the validator subprocess
runner in tests/conftest.py, and test_repo_consistency.py's own `_stub_dsh_env`
for the version-floor checks). Unlike that stub -- which swallows `plugin`
subcommands -- this one answers `--version` AND actually reconciles a
profile's `package.json` (`dsh.profile.bundles`) on `plugin ... add|remove`,
the same way the real CLI does, so the installer's idempotency and uninstall
logic run against real state instead of a no-op. Every invocation is also
logged, so a test can assert exactly which packages were (or were not) added.
"""

import json
import os
import shutil
import subprocess

from conftest import REPO

FLOOR = "0.1.6-alpha.2"
TEAM_BUNDLE_HOST = "@deepseek-ai/dsh-experimental-agent-team-profile"
TEAM_BUNDLE_WEB = "@deepseek-ai/dsh-experimental-agent-team-web-profile"

PATCH_TEMPLATE = (
    "# Your patch layer for this dsh profile, applied after every bundle layer:\n"
    "# a top-level YAML array of loader patch entries (id-targeted config\n"
    "# overrides, disables, and insert lists; `!!js` expressions allowed).\n"
    "[]\n"
)

# A minimal stand-in for `dsh`: answers `--version`, and for `plugin --profile
# <p> add|remove <pkg...>` actually mutates <DSH_HOME>/profiles/<p>/package.json
# the way the real CLI's reconcile step does (lazily initializing the profile,
# same shape `dsh plugin add` produces against the real 0.1.6-alpha.2 CLI).
FAKE_DSH_JS = r"""
const { existsSync, readFileSync, writeFileSync, mkdirSync, appendFileSync } = require('node:fs')
const { join } = require('node:path')

const args = process.argv.slice(2)
if (args[0] === '--version') {
  process.stdout.write((process.env.RQ_STUB_VERSION || '') + '\n')
  process.exit(0)
}
if (args[0] !== 'plugin') process.exit(0)

let profile = null
let action = null
const pkgs = []
for (let i = 1; i < args.length; i += 1) {
  const a = args[i]
  if (a === '--profile') { profile = args[(i += 1)]; continue }
  if (a === 'add' || a === 'remove') { action = a; continue }
  pkgs.push(a)
}
if (process.env.RQ_STUB_LOG) {
  appendFileSync(process.env.RQ_STUB_LOG, `${action} ${profile} ${pkgs.join(' ')}\n`)
}
if (!profile || (action !== 'add' && action !== 'remove')) process.exit(0)

const dir = join(process.env.DSH_HOME, 'profiles', profile)
const manifestPath = join(dir, 'package.json')
let manifest
if (existsSync(manifestPath)) {
  manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
} else {
  mkdirSync(dir, { recursive: true })
  manifest = { name: `dsh-profile-${profile}`, private: true, dependencies: {},
               dsh: { profile: { bundles: ['@deepseek-ai/dsh-base'] } } }
  writeFileSync(join(dir, 'cordis.patch.yml'), process.env.RQ_STUB_PATCH_TEMPLATE)
}
manifest.dsh = manifest.dsh || {}
manifest.dsh.profile = manifest.dsh.profile || {}
const bundles = Array.isArray(manifest.dsh.profile.bundles) ? manifest.dsh.profile.bundles : []
for (const pkg of pkgs) {
  const at = bundles.indexOf(pkg)
  if (action === 'add' && at === -1) bundles.push(pkg)
  if (action === 'remove' && at !== -1) bundles.splice(at, 1)
}
manifest.dsh.profile.bundles = bundles
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n')
"""


def _path_without_dsh():
    """The current PATH with every directory that resolves `dsh` removed.

    A real `dsh` (this machine's installed 0.1.6-alpha.2) may already be on
    PATH, so simply NOT prepending a fake one is not enough to test the
    no-CLI branch.
    """
    dirs = [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    return os.pathsep.join(d for d in dirs if not shutil.which("dsh", path=d))


def _stub_dsh_env(tmp_path, version=FLOOR):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    stub_js = tmp_path / "fake_dsh.js"
    stub_js.write_text(FAKE_DSH_JS)
    fake_dsh = fake_bin / "dsh"
    fake_dsh.write_text("#!/bin/sh\nexec node %s \"$@\"\n" % stub_js)
    fake_dsh.chmod(0o755)
    dsh_home = tmp_path / "dsh-home"
    log_path = tmp_path / "dsh-calls.log"
    env = os.environ.copy()
    env["PATH"] = "%s%s%s" % (fake_bin, os.pathsep, env.get("PATH", ""))
    env["DSH_HOME"] = str(dsh_home)
    env["RQ_STUB_LOG"] = str(log_path)
    env["RQ_STUB_VERSION"] = version
    env["RQ_STUB_PATCH_TEMPLATE"] = PATCH_TEMPLATE
    return env, dsh_home, log_path


def _seed_profile(dsh_home, profile, bundles):
    profile_dir = dsh_home / "profiles" / profile
    profile_dir.mkdir(parents=True)
    (profile_dir / "package.json").write_text(json.dumps(
        {"name": "dsh-profile-%s" % profile, "private": True,
         "dsh": {"profile": {"bundles": list(bundles)}}}, indent=2) + "\n")
    (profile_dir / "cordis.patch.yml").write_text(PATCH_TEMPLATE)
    return profile_dir


def _install(env, profile, *extra_args):
    return subprocess.run(
        [str(REPO / "install.sh"), "--profile", profile, *extra_args],
        cwd=REPO, env=env, capture_output=True, text=True,
    )


def _manifest_bundles(dsh_home, profile):
    manifest = dsh_home / "profiles" / profile / "package.json"
    return json.loads(manifest.read_text())["dsh"]["profile"]["bundles"]


def _patch_text(dsh_home, profile):
    return (dsh_home / "profiles" / profile / "cordis.patch.yml").read_text()


def _log_lines(log_path):
    return log_path.read_text().splitlines() if log_path.exists() else []


def _team_bundle_calls(log_path, action):
    """Log lines for `plugin ... <action> <pkg>` naming a TEAM bundle.

    `install_plugin()` also calls `dsh plugin ... add` for the main
    `dsh-rigorquant` package itself on every run; filtering by bundle name
    keeps that unrelated call out of these assertions.
    """
    return [l for l in _log_lines(log_path) if l.startswith("%s " % action)
            and (TEAM_BUNDLE_HOST in l or TEAM_BUNDLE_WEB in l)]


def test_full_install_enables_both_bundles_and_writes_every_line_of_the_cap_override(tmp_path):
    env, dsh_home, log_path = _stub_dsh_env(tmp_path)
    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr

    for bundle in (TEAM_BUNDLE_HOST, TEAM_BUNDLE_WEB):
        assert "Enabled the Agent Teams bundle '%s'" % bundle in result.stdout
    bundles = _manifest_bundles(dsh_home, "rq-team")
    assert TEAM_BUNDLE_HOST in bundles and TEAM_BUNDLE_WEB in bundles

    patch = _patch_text(dsh_home, "rq-team")
    assert "# >>> dsh-rigorquant BEGIN" in patch
    assert "# <<< dsh-rigorquant END <<<" in patch
    assert "# rq-enabled-bundles: %s %s" % (TEAM_BUNDLE_HOST, TEAM_BUNDLE_WEB) in patch
    for line in ("- id: agent-team", "maxMembers: 64", "maxTasks: 256",
                 "maxPendingMessagesPerMember: 64", "maxMessageBytes: 65536",
                 "disposalTimeoutMs: 5000"):
        assert line in patch
        # "prints every line it wrote": each written line must reach stdout too.
        assert line in result.stdout, "installer wrote %r but never printed it" % line

    add_calls = _team_bundle_calls(log_path, "add")
    assert len(add_calls) == 1, add_calls
    assert TEAM_BUNDLE_HOST in add_calls[0] and TEAM_BUNDLE_WEB in add_calls[0]


def test_full_install_leaves_an_already_enabled_bundle_alone(tmp_path):
    """Half the pair pre-enabled: only the missing half is added, and recorded."""
    env, dsh_home, log_path = _stub_dsh_env(tmp_path)
    _seed_profile(dsh_home, "rq-team", ["@deepseek-ai/dsh-base", TEAM_BUNDLE_HOST])
    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr

    assert "Enabled the Agent Teams bundle '%s'" % TEAM_BUNDLE_WEB in result.stdout
    assert "Enabled the Agent Teams bundle '%s'" % TEAM_BUNDLE_HOST not in result.stdout, (
        "the installer claimed to enable a bundle that was already on")
    bundles = _manifest_bundles(dsh_home, "rq-team")
    assert TEAM_BUNDLE_HOST in bundles and TEAM_BUNDLE_WEB in bundles
    patch = _patch_text(dsh_home, "rq-team")
    assert ("# rq-enabled-bundles: %s" % TEAM_BUNDLE_WEB) in patch
    assert TEAM_BUNDLE_HOST not in patch.split("rq-enabled-bundles:", 1)[1].splitlines()[0]

    add_calls = _team_bundle_calls(log_path, "add")
    assert not any(TEAM_BUNDLE_HOST in l for l in add_calls), (
        "installer re-added a bundle that was already enabled: %s" % add_calls)


def test_second_run_writes_nothing_new(tmp_path):
    env, dsh_home, log_path = _stub_dsh_env(tmp_path)
    first = _install(env, "rq-team")
    assert first.returncode == 0, first.stderr
    patch_after_first = _patch_text(dsh_home, "rq-team")

    log_path.unlink()
    second = _install(env, "rq-team")
    assert second.returncode == 0, second.stderr

    assert "Enabled the Agent Teams bundle" not in second.stdout
    assert "Wrote the Agent Teams maxMembers override" not in second.stdout
    assert _patch_text(dsh_home, "rq-team") == patch_after_first
    assert _team_bundle_calls(log_path, "add") == [], (
        "a no-op run must not call `dsh plugin ... add` for a Team bundle again")


def test_uninstall_removes_the_marker_and_disables_only_what_it_enabled(tmp_path):
    env, dsh_home, log_path = _stub_dsh_env(tmp_path)
    _seed_profile(dsh_home, "rq-team", ["@deepseek-ai/dsh-base", TEAM_BUNDLE_HOST])
    install_result = _install(env, "rq-team")
    assert install_result.returncode == 0, install_result.stderr

    log_path.unlink()
    result = _install(env, "rq-team", "--uninstall")
    assert result.returncode == 0, result.stderr

    patch = _patch_text(dsh_home, "rq-team")
    assert "dsh-rigorquant" not in patch, "the marker block survived --uninstall"
    assert patch.strip().endswith("[]"), "an emptied user patch must stay valid YAML"

    bundles = _manifest_bundles(dsh_home, "rq-team")
    assert TEAM_BUNDLE_HOST in bundles, (
        "uninstall disabled a bundle the OPERATOR had enabled before install")
    assert TEAM_BUNDLE_WEB not in bundles, (
        "uninstall left a bundle enabled that only the installer had turned on")

    remove_calls = _team_bundle_calls(log_path, "remove")
    assert any(TEAM_BUNDLE_WEB in l for l in remove_calls)
    assert not any(TEAM_BUNDLE_HOST in l for l in remove_calls)


def test_no_dsh_warns_and_continues(tmp_path):
    """CI's install smoke test has no `dsh` on PATH; the install must still succeed."""
    env = os.environ.copy()
    env["PATH"] = _path_without_dsh()
    env["DSH_HOME"] = str(tmp_path / "dsh-home")
    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr
    assert "warning: dsh is not on PATH" in result.stderr
    assert "Agent Teams" in result.stderr
    assert "Installed preset" in result.stdout
    assert not (tmp_path / "dsh-home" / "profiles").exists(), (
        "no profile should be touched when dsh cannot enable or locate one")
