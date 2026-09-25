"""install.sh on DSH 0.1.7-rc.2 (Decisions 24 and 25; issues #12 and #30).

Full install must: enable the ONE Team bundle rc.2 publishes
(`@deepseek-ai/dsh-experimental-agent-team-profile`, pinned to the core) when
it is absent; always remove the retired web bundle when a profile still has
it, saying why, and fail hard if that removal fails; append a `maxMembers: 64`
cap override under a `dsh-rigorquant` marker in the profile's user patch
(`cordis.patch.yml`), printing every line it wrote; and write nothing under
`$DSH_HOME/.agent-presets` (the preset is declared now). A second run must
write nothing new. `--uninstall` must remove the marker, disable only the
bundle the installer itself turned on, and still clean up an old install's
`.agent-presets/rigorquant`. With no `dsh` on PATH the installer must warn
and continue (this is what keeps CI's install smoke test green).

The saved-routes port (Decision 25) is covered here too: the harness's one-time
`settings.yaml` import drops the `rigorquant-models` section and the legacy
`agent-presets:` default, so the installer ports them into the profile patch
itself, from `settings.yaml` or, after an early boot, `settings.yaml.imported`.

The stub `dsh` here is a real subprocess (prior art: the validator subprocess
runner in tests/conftest.py, and test_repo_consistency.py's own `_stub_dsh_env`
for the version-floor checks). Unlike that stub -- which swallows `plugin`
subcommands -- this one answers `--version` AND actually reconciles a
profile's `package.json` (`dsh.profile.bundles`) on `plugin ... add|remove`,
the same way the real CLI does, so the installer's idempotency and uninstall
logic run against real state instead of a no-op. Like pnpm, an `add` naming a
version npm does not have fails the WHOLE call and changes nothing. Every
invocation is also logged, so a test can assert exactly which packages were
(or were not) added.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

from conftest import REPO

FLOOR = "0.1.7-rc.2"
TEAM_BUNDLE = "@deepseek-ai/dsh-experimental-agent-team-profile"
# Retired in 0.1.7: the harness removed this package from its workspace, and
# npm has no build of it for any 0.1.7 core.
WEB_BUNDLE = "@deepseek-ai/dsh-experimental-agent-team-web-profile"
# What npm really holds for the web bundle (dist-tags on 2026-09-24).
WEB_BUNDLE_PUBLISHED = ("0.1.5-alpha.2", "0.1.5-rc.3", "0.1.6-alpha.2")

PATCH_TEMPLATE = (
    "# Your patch layer for this dsh profile, applied after every bundle layer:\n"
    "# a top-level YAML array of loader patch entries (id-targeted config\n"
    "# overrides, disables, and insert lists; `!!js` expressions allowed).\n"
    "[]\n"
)

# A minimal stand-in for `dsh`: answers `--version`, and for `plugin --profile
# <p> add|remove <pkg...>` actually mutates <DSH_HOME>/profiles/<p>/package.json
# the way the real CLI's reconcile step does (lazily initializing the profile).
# `RQ_STUB_FAIL_REMOVE` names a package whose removal fails.
FAKE_DSH_JS = r"""
const { existsSync, readFileSync, writeFileSync, mkdirSync, appendFileSync } = require('node:fs')
const { join } = require('node:path')

const WEB = '@deepseek-ai/dsh-experimental-agent-team-web-profile'
const WEB_PUBLISHED = %s

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

// A scoped name's leading '@' is not a version separator, so the search is
// for the LAST '@' past position 0.
const split = (raw) => {
  const at = raw.lastIndexOf('@')
  return at > 0 ? [raw.slice(0, at), raw.slice(at + 1)] : [raw, undefined]
}
if (action === 'add') {
  for (const raw of pkgs) {
    const [name, version] = split(raw)
    if (name === WEB && version !== undefined && !WEB_PUBLISHED.includes(version)) {
      process.stderr.write(`ERR_PNPM_NO_MATCHING_VERSION No matching version found for ${raw}\n`)
      process.exit(1)
    }
  }
}
if (action === 'remove' && pkgs.includes(process.env.RQ_STUB_FAIL_REMOVE)) {
  process.stderr.write(`ERR_PNPM_REMOVE failed to remove ${process.env.RQ_STUB_FAIL_REMOVE}\n`)
  process.exit(1)
}

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
manifest.dependencies = manifest.dependencies || {}
const bundles = Array.isArray(manifest.dsh.profile.bundles) ? manifest.dsh.profile.bundles : []
for (const raw of pkgs) {
  // `dsh plugin add <pkg>` records BOTH the bare name in dsh.profile.bundles
  // and the resolved version in dependencies.
  const [name, version] = split(raw)
  const index = bundles.indexOf(name)
  if (action === 'add') {
    if (index === -1) bundles.push(name)
    if (version !== undefined) manifest.dependencies[name] = version
  }
  if (action === 'remove') {
    if (index !== -1) bundles.splice(index, 1)
    delete manifest.dependencies[name]
  }
}
manifest.dsh.profile.bundles = bundles
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n')
""" % json.dumps(list(WEB_BUNDLE_PUBLISHED))


def _path_without_dsh():
    """The current PATH with every directory that resolves `dsh` removed.

    A real `dsh` may already be on PATH, so simply NOT prepending a fake one
    is not enough to test the no-CLI branch.
    """
    dirs = [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    return os.pathsep.join(d for d in dirs if not shutil.which("dsh", path=d))


def _harness_yaml():
    """The `yaml` package an installed harness ships, or None.

    The installer reads YAML with the CLI's own `yaml` package (resolved from
    the real path of `dsh`), so this repository adds no dependency. The stub
    borrows the same package; without a harness to borrow it from, the port
    tests skip.
    """
    candidates = []
    modules = os.environ.get("RQ_HARNESS_MODULES")
    if modules:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(modules)), "yaml"))
    bin_path = shutil.which("dsh")
    if bin_path:
        root = os.path.dirname(os.path.dirname(os.path.realpath(bin_path)))
        candidates.append(os.path.join(root, "node_modules", "yaml"))
    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, "package.json")):
            return candidate
    return None


def _stub_dsh_env(tmp_path, version=FLOOR, with_yaml=True):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    stub_js = tmp_path / "fake_dsh.js"
    stub_js.write_text(FAKE_DSH_JS)
    fake_dsh = fake_bin / "dsh"
    fake_dsh.write_text("#!/bin/sh\nexec node %s \"$@\"\n" % stub_js)
    fake_dsh.chmod(0o755)
    yaml_dir = _harness_yaml() if with_yaml else None
    if yaml_dir is not None:
        # The installer resolves `yaml` from the real path of `dsh`; for the
        # stub that walks up from <tmp>/bin to <tmp>/node_modules.
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "yaml").symlink_to(yaml_dir)
    dsh_home = tmp_path / "dsh-home"
    log_path = tmp_path / "dsh-calls.log"
    env = os.environ.copy()
    env["PATH"] = "%s%s%s" % (fake_bin, os.pathsep, env.get("PATH", ""))
    env["DSH_HOME"] = str(dsh_home)
    env["RQ_STUB_LOG"] = str(log_path)
    env["RQ_STUB_VERSION"] = version
    env["RQ_STUB_PATCH_TEMPLATE"] = PATCH_TEMPLATE
    return env, dsh_home, log_path


def _needs_yaml():
    if _harness_yaml() is None:
        pytest.skip("no installed harness to borrow the `yaml` package from")


def _seed_profile(dsh_home, profile, bundles, dependencies=None, patch=PATCH_TEMPLATE):
    profile_dir = dsh_home / "profiles" / profile
    profile_dir.mkdir(parents=True)
    manifest = {"name": "dsh-profile-%s" % profile, "private": True,
                "dsh": {"profile": {"bundles": list(bundles)}}}
    if dependencies is not None:
        manifest["dependencies"] = dict(dependencies)
    (profile_dir / "package.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (profile_dir / "cordis.patch.yml").write_text(patch)
    return profile_dir


def _manifest_dependencies(dsh_home, profile):
    manifest = dsh_home / "profiles" / profile / "package.json"
    return json.loads(manifest.read_text()).get("dependencies", {})


def _copy_installer_tree(tmp_path, name):
    """A standalone copy of the tree the installer runs from.

    The real checkout cannot be used for the `.git` cases: this repository is
    itself a worktree, and the point of those cases is what the installer does
    when `$HERE/.git` is a directory, a file, or absent.
    """
    dest = tmp_path / name
    shutil.copytree(
        REPO, dest,
        ignore=shutil.ignore_patterns(
            ".git", ".uv-cache", ".venv", "__pycache__", ".pytest_cache",
            ".coverage*", "node_modules"),
        symlinks=True,
    )
    return dest


def _install(env, profile, *extra_args, here=REPO):
    return subprocess.run(
        [str(here / "install.sh"), "--profile", profile, *extra_args],
        cwd=here, env=env, capture_output=True, text=True,
    )


def _manifest_bundles(dsh_home, profile):
    manifest = dsh_home / "profiles" / profile / "package.json"
    return json.loads(manifest.read_text())["dsh"]["profile"]["bundles"]


def _patch_text(dsh_home, profile):
    return (dsh_home / "profiles" / profile / "cordis.patch.yml").read_text()


def _patch_rows(tmp_path, dsh_home, profile):
    """The profile patch parsed by the harness's own `yaml` package, as JSON.

    `!!js` scalars come back as their source text, the way the harness's
    ConfigEditor reads them.
    """
    script = (
        "const YAML = require(process.argv[1]);"
        "const text = require('node:fs').readFileSync(process.argv[2], 'utf8');"
        "const doc = YAML.parseDocument(text, { customTags: [{ tag: 'tag:yaml.org,2002:js', resolve: (v) => v }] });"
        "if (doc.errors.length) { console.error(String(doc.errors[0])); process.exit(1) }"
        "process.stdout.write(JSON.stringify(doc.toJS()))"
    )
    path = dsh_home / "profiles" / profile / "cordis.patch.yml"
    out = subprocess.run(["node", "-e", script, str(tmp_path / "node_modules" / "yaml"), str(path)],
                         capture_output=True, text=True)
    assert out.returncode == 0, "the profile patch is not valid YAML:\n%s\n%s" % (out.stderr, path.read_text())
    return json.loads(out.stdout)


def _config_row(rows, row_id):
    matches = [r for r in rows if isinstance(r, dict) and r.get("id") == row_id and "insert" not in r]
    return matches[-1] if matches else None


def _log_lines(log_path):
    return log_path.read_text().splitlines() if log_path.exists() else []


def _team_bundle_calls(log_path, action):
    """Log lines for `plugin ... <action> <pkg>` naming a Team bundle.

    `install_plugin()` also calls `dsh plugin ... add` for the main
    `dsh-rigorquant` package itself on every run; filtering by bundle name
    keeps that unrelated call out of these assertions.
    """
    return [l for l in _log_lines(log_path) if l.startswith("%s " % action)
            and (TEAM_BUNDLE in l or WEB_BUNDLE in l)]


# --- the one Team bundle ----------------------------------------------------


def test_the_stub_rejects_the_two_bundle_add_the_way_rc2_does(tmp_path):
    """0.5.0's call -- host AND web bundle, both pinned to the core -- fails
    on rc.2 with ERR_PNPM_NO_MATCHING_VERSION and enables neither (live rc.2,
    B2). The stub must reproduce that, or the one-bundle test below proves
    nothing."""
    env, dsh_home, _ = _stub_dsh_env(tmp_path, with_yaml=False)
    _seed_profile(dsh_home, "rq-team", ["@deepseek-ai/dsh-base"])
    out = subprocess.run(
        ["dsh", "plugin", "--profile", "rq-team", "add",
         "%s@%s" % (TEAM_BUNDLE, FLOOR), "%s@%s" % (WEB_BUNDLE, FLOOR)],
        env=env, capture_output=True, text=True)
    assert out.returncode != 0
    assert "ERR_PNPM_NO_MATCHING_VERSION" in out.stderr
    assert _manifest_bundles(dsh_home, "rq-team") == ["@deepseek-ai/dsh-base"]


def test_full_install_enables_only_the_team_bundle_and_writes_every_line_of_the_cap_override(tmp_path):
    env, dsh_home, log_path = _stub_dsh_env(tmp_path)
    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr

    assert "Enabled the Agent Teams bundle '%s'" % TEAM_BUNDLE in result.stdout
    bundles = _manifest_bundles(dsh_home, "rq-team")
    assert TEAM_BUNDLE in bundles
    assert WEB_BUNDLE not in bundles

    patch = _patch_text(dsh_home, "rq-team")
    assert "# >>> dsh-rigorquant BEGIN" in patch
    assert "# <<< dsh-rigorquant END <<<" in patch
    assert re.search(r"^# rq-enabled-bundles: %s$" % re.escape(TEAM_BUNDLE), patch, re.M), patch
    for line in ("- id: agent-team", "maxMembers: 64", "maxTasks: 256",
                 "maxPendingMessagesPerMember: 64", "maxMessageBytes: 65536",
                 "disposalTimeoutMs: 5000"):
        assert line in patch
        # "prints every line it wrote": each written line must reach stdout too.
        assert line in result.stdout, "installer wrote %r but never printed it" % line

    add_calls = _team_bundle_calls(log_path, "add")
    assert add_calls == ["add rq-team %s@%s" % (TEAM_BUNDLE, FLOOR)], add_calls
    assert _manifest_dependencies(dsh_home, "rq-team").get(TEAM_BUNDLE) == FLOOR


def test_full_install_leaves_an_already_enabled_team_bundle_alone(tmp_path):
    env, dsh_home, log_path = _stub_dsh_env(tmp_path)
    _seed_profile(dsh_home, "rq-team", ["@deepseek-ai/dsh-base", TEAM_BUNDLE])
    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr

    assert "Enabled the Agent Teams bundle" not in result.stdout, (
        "the installer claimed to enable a bundle that was already on")
    assert _team_bundle_calls(log_path, "add") == []
    patch = _patch_text(dsh_home, "rq-team")
    assert re.search(r"^# rq-enabled-bundles: *$", patch, re.M), patch


def test_a_stale_team_bundle_is_repinned_to_the_cores_version(tmp_path):
    """A profile pinning the Team bundle at another core's version fails to
    boot ("parameter codec has no create() factory"); re-running repairs it,
    once."""
    stale = "0.1.6-alpha.2"
    env, dsh_home, log_path = _stub_dsh_env(tmp_path)
    _seed_profile(dsh_home, "rq-team", ["@deepseek-ai/dsh-base", TEAM_BUNDLE],
                  dependencies={TEAM_BUNDLE: stale})

    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr
    assert "Re-pinned the Agent Teams bundle '%s' to %s" % (TEAM_BUNDLE, FLOOR) in result.stdout
    assert _team_bundle_calls(log_path, "add") == ["add rq-team %s@%s" % (TEAM_BUNDLE, FLOOR)]
    assert _manifest_dependencies(dsh_home, "rq-team")[TEAM_BUNDLE] == FLOOR

    log_path.unlink()
    second = _install(env, "rq-team")
    assert second.returncode == 0, second.stderr
    assert "Re-pinned" not in second.stdout
    assert _team_bundle_calls(log_path, "add") == [], "the repair ran twice"


# --- the retired web bundle -------------------------------------------------


@pytest.mark.parametrize("recorded", [True, False], ids=["installer-enabled", "operator-enabled"])
def test_the_web_bundle_is_always_removed_with_one_line_saying_why(tmp_path, recorded):
    """A 0.5.0 profile lists the web bundle (the installer enabled it, or the
    operator did). On rc.2 it is gone from the harness, so it is removed
    either way -- not only when our marker recorded it."""
    env, dsh_home, log_path = _stub_dsh_env(tmp_path)
    patch = PATCH_TEMPLATE
    if recorded:
        patch = (
            "# >>> dsh-rigorquant BEGIN (managed by ./install.sh; see docs/adr/0001-rigorquant-on-agent-teams.md) >>>\n"
            "# rq-enabled-bundles: %s %s\n"
            "- id: agent-team\n  config:\n    maxMembers: 64\n"
            "# <<< dsh-rigorquant END <<<\n" % (TEAM_BUNDLE, WEB_BUNDLE))
    _seed_profile(dsh_home, "rq-team", ["@deepseek-ai/dsh-base", TEAM_BUNDLE, WEB_BUNDLE],
                  dependencies={TEAM_BUNDLE: "0.1.6-alpha.2", WEB_BUNDLE: "0.1.6-alpha.2"},
                  patch=patch)

    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr
    lines = [l for l in result.stdout.splitlines() if WEB_BUNDLE in l]
    assert len(lines) == 1, result.stdout
    assert lines[0].startswith("Removed the retired Agent Teams web bundle"), lines
    assert "0.1.7" in lines[0], "the line must say why: %s" % lines[0]

    assert WEB_BUNDLE not in _manifest_bundles(dsh_home, "rq-team")
    assert _team_bundle_calls(log_path, "remove") == ["remove rq-team %s" % WEB_BUNDLE]
    assert not any(WEB_BUNDLE in l for l in _team_bundle_calls(log_path, "add"))
    # The marker's record no longer names a bundle the profile does not have.
    assert WEB_BUNDLE not in _patch_text(dsh_home, "rq-team")


def test_a_failed_web_bundle_removal_is_a_hard_error(tmp_path):
    """A profile that keeps the web bundle cannot boot on rc.2 cleanly, and
    the operator is about to start it: stop and say so."""
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    env["RQ_STUB_FAIL_REMOVE"] = WEB_BUNDLE
    _seed_profile(dsh_home, "rq-team", ["@deepseek-ai/dsh-base", WEB_BUNDLE])

    result = _install(env, "rq-team")
    assert result.returncode != 0
    assert "error:" in result.stderr and WEB_BUNDLE in result.stderr, result.stderr
    assert WEB_BUNDLE in _manifest_bundles(dsh_home, "rq-team")


def test_a_profile_without_the_web_bundle_is_not_asked_to_remove_it(tmp_path):
    env, _, log_path = _stub_dsh_env(tmp_path)
    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr
    assert _team_bundle_calls(log_path, "remove") == []
    assert WEB_BUNDLE not in result.stdout


# --- the declared preset ----------------------------------------------------


def test_full_install_writes_nothing_under_agent_presets(tmp_path):
    """rc.2 ignores $DSH_HOME/.agent-presets; the preset is a declared row."""
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr
    assert not (dsh_home / ".agent-presets").exists()
    assert ".agent-presets" not in result.stdout
    assert (dsh_home / "share" / "rigorquant" / "env" / "pyproject.toml").is_file()


def test_uninstall_still_removes_an_old_installs_agent_presets_copy(tmp_path):
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    old = dsh_home / ".agent-presets" / "rigorquant"
    old.mkdir(parents=True)
    (old / "preset.yml").write_text("id: rigorquant\n")
    result = _install(env, "rq-team", "--uninstall")
    assert result.returncode == 0, result.stderr
    assert not old.exists()


# --- git checkout vs fetched copy -------------------------------------------


def test_a_git_worktree_installs_the_tree_not_the_published_package(tmp_path):
    """In a linked worktree `.git` is a FILE, so `[ -d "$HERE/.git" ]` is false.

    The installer then installs the published package instead of `file:$HERE`.
    """
    here = _copy_installer_tree(tmp_path, "worktree")
    (here / ".git").write_text("gitdir: /nonexistent/.git/worktrees/rq\n")
    env, _, _ = _stub_dsh_env(tmp_path)

    result = _install(env, "rq-team", here=here)
    assert result.returncode == 0, result.stderr
    assert "Installed the plugin (file:%s)" % here in result.stdout, result.stdout


def test_a_plain_copy_installs_the_published_package(tmp_path):
    """The control for the worktree case: no `.git` at all is a fetched copy."""
    here = _copy_installer_tree(tmp_path, "fetched")
    env, _, _ = _stub_dsh_env(tmp_path)

    result = _install(env, "rq-team", here=here)
    assert result.returncode == 0, result.stderr
    assert "Installed the plugin (dsh-rigorquant@" in result.stdout, result.stdout


# --- idempotency and uninstall ----------------------------------------------


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


def test_uninstall_removes_the_marker_and_disables_the_bundle_it_enabled(tmp_path):
    env, dsh_home, log_path = _stub_dsh_env(tmp_path)
    install_result = _install(env, "rq-team")
    assert install_result.returncode == 0, install_result.stderr

    log_path.unlink()
    result = _install(env, "rq-team", "--uninstall")
    assert result.returncode == 0, result.stderr

    patch = _patch_text(dsh_home, "rq-team")
    assert "dsh-rigorquant" not in patch, "the marker block survived --uninstall"
    assert patch.strip().endswith("[]"), "an emptied user patch must stay valid YAML"
    assert TEAM_BUNDLE not in _manifest_bundles(dsh_home, "rq-team")
    assert _team_bundle_calls(log_path, "remove") == ["remove rq-team %s" % TEAM_BUNDLE]


def test_uninstall_leaves_a_team_bundle_the_operator_enabled(tmp_path):
    env, dsh_home, log_path = _stub_dsh_env(tmp_path)
    _seed_profile(dsh_home, "rq-team", ["@deepseek-ai/dsh-base", TEAM_BUNDLE])
    assert _install(env, "rq-team").returncode == 0

    log_path.unlink()
    result = _install(env, "rq-team", "--uninstall")
    assert result.returncode == 0, result.stderr
    assert TEAM_BUNDLE in _manifest_bundles(dsh_home, "rq-team"), (
        "uninstall disabled a bundle the OPERATOR had enabled before install")
    assert _team_bundle_calls(log_path, "remove") == []


def test_no_dsh_warns_and_continues(tmp_path):
    """CI's install smoke test has no `dsh` on PATH; the install must still succeed."""
    env = os.environ.copy()
    env["PATH"] = _path_without_dsh()
    env["DSH_HOME"] = str(tmp_path / "dsh-home")
    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr
    assert "warning: dsh is not on PATH" in result.stderr
    assert "Agent Teams" in result.stderr
    assert TEAM_BUNDLE in result.stderr and WEB_BUNDLE not in result.stderr
    assert "Installed compute lane" in result.stdout
    assert not (tmp_path / "dsh-home" / "profiles").exists(), (
        "no profile should be touched when dsh cannot enable or locate one")


# --- saved routes and the saved default (Decision 25) -----------------------

# 0.5.0's settings.yaml, as the alpha.2 settings file wrote it: flow-style
# routes, a stale role key from an older release, and the legacy default.
LEGACY_SETTINGS = """\
ui-theme:
  preference: system
agent-presets:
  default: %(default)s
rigorquant-models:
  {
    rootPrimary: { provider: deepseek-official, model: deepseek-flash },
    novelPrimary: { provider: linxicloud, model: dspark, reasoningEffort: high },
    doublecheckerPrimary:
      {
        provider: deepseek-official,
        model: deepseek-v4-pro,
        reasoningEffort: high
      },
    doublecheckerFallback: { provider: deepseek-official, model: deepseek-flash, reasoningEffort: low },
    lit-adversaryPrimary: { provider: zai, model: glm-5.3-flash }
  }
"""

PORTED_ROUTES = {
    "rootPrimary": {"provider": "deepseek-official", "model": "deepseek-flash"},
    "doublecheckerPrimary": {"provider": "deepseek-official", "model": "deepseek-v4-pro",
                             "reasoningEffort": "high"},
    "doublecheckerFallback": {"provider": "deepseek-official", "model": "deepseek-flash",
                              "reasoningEffort": "low"},
    "lit-adversaryPrimary": {"provider": "zai", "model": "glm-5.3-flash"},
}


@pytest.mark.parametrize("source", ["settings.yaml", "settings.yaml.imported"])
def test_saved_routes_and_the_saved_default_are_ported_into_the_profile_patch(tmp_path, source):
    """Before the first rc.2 boot the routes sit in settings.yaml; after an
    early boot the harness has renamed it to settings.yaml.imported and
    dropped both sections. Re-running the installer recovers both."""
    _needs_yaml()
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    dsh_home.mkdir()
    (dsh_home / source).write_text(LEGACY_SETTINGS % {"default": "rigorquant"})

    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr

    rows = _patch_rows(tmp_path, dsh_home, "rq-team")
    router = _config_row(rows, "rq-model-router")
    assert router is not None, rows
    assert router["name"] == "dsh-rigorquant"
    assert router["config"] == PORTED_ROUTES
    registry = _config_row(rows, "agent-preset-registry")
    assert registry == {"id": "agent-preset-registry",
                        "name": "@deepseek-ai/dsh-agent-preset-registry",
                        "config": {"default": "standard", "selectedDefault": "rigorquant"}}
    # The Team cap block is still there, untouched.
    assert _config_row(rows, "agent-team")["config"]["maxMembers"] == 64
    assert "# >>> dsh-rigorquant BEGIN" in _patch_text(dsh_home, "rq-team")

    assert "Ported 4 saved routes from %s" % (dsh_home / source) in result.stdout, result.stdout
    assert "novelPrimary" in result.stdout, "a dropped route must be named"
    assert "selectedDefault: rigorquant" in result.stdout


def test_ported_rows_sit_outside_the_marker_block(tmp_path):
    """The marker block's END line is a trailing comment, so a row appended
    to the sequence lands inside it, and --uninstall would delete the user's
    routes with the block."""
    _needs_yaml()
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    dsh_home.mkdir()
    (dsh_home / "settings.yaml").write_text(LEGACY_SETTINGS % {"default": "rigorquant"})
    assert _install(env, "rq-team").returncode == 0
    patch = _patch_text(dsh_home, "rq-team")
    block = patch[patch.index("# >>> dsh-rigorquant BEGIN"):patch.index("# <<< dsh-rigorquant END")]
    assert "rq-model-router" not in block and "agent-preset-registry" not in block, patch

    result = _install(env, "rq-team", "--uninstall")
    assert result.returncode == 0, result.stderr
    rows = _patch_rows(tmp_path, dsh_home, "rq-team")
    assert _config_row(rows, "rq-model-router")["config"] == PORTED_ROUTES
    assert _config_row(rows, "agent-team") is None


def test_a_saved_default_other_than_rigorquant_is_not_ported(tmp_path):
    _needs_yaml()
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    dsh_home.mkdir()
    (dsh_home / "settings.yaml").write_text(LEGACY_SETTINGS % {"default": "standard"})

    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr
    rows = _patch_rows(tmp_path, dsh_home, "rq-team")
    assert _config_row(rows, "agent-preset-registry") is None
    assert _config_row(rows, "rq-model-router")["config"] == PORTED_ROUTES
    assert "selectedDefault" not in result.stdout


def test_the_port_runs_once(tmp_path):
    """A second run -- or a route the user already saved on rc.2 -- wins over
    the legacy file."""
    _needs_yaml()
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    dsh_home.mkdir()
    (dsh_home / "settings.yaml").write_text(LEGACY_SETTINGS % {"default": "rigorquant"})
    assert _install(env, "rq-team").returncode == 0
    after_first = _patch_text(dsh_home, "rq-team")

    second = _install(env, "rq-team")
    assert second.returncode == 0, second.stderr
    assert "Ported" not in second.stdout and "selectedDefault" not in second.stdout
    assert _patch_text(dsh_home, "rq-team") == after_first


def test_routes_cleared_on_rc2_do_not_come_back(tmp_path):
    """One time means one time: settings.yaml.imported stays on disk, so an
    operator who clears every route on 0.1.7 and re-runs the installer must
    not get the 0.5.0 routes back."""
    _needs_yaml()
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    dsh_home.mkdir()
    (dsh_home / "settings.yaml.imported").write_text(LEGACY_SETTINGS % {"default": "rigorquant"})
    assert _install(env, "rq-team").returncode == 0
    patch_path = dsh_home / "profiles" / "rq-team" / "cordis.patch.yml"
    text = patch_path.read_text()
    start = text.index("- id: rq-model-router")
    end = text.index("# >>> dsh-rigorquant BEGIN")
    patch_path.write_text(text[:start] + text[end:])

    second = _install(env, "rq-team")
    assert second.returncode == 0, second.stderr
    assert "Ported" not in second.stdout
    assert _config_row(_patch_rows(tmp_path, dsh_home, "rq-team"), "rq-model-router") is None


def test_an_existing_registry_row_without_default_gains_it(tmp_path):
    """`default` is required, and a profile row replaces the bundle's config."""
    _needs_yaml()
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    _seed_profile(dsh_home, "rq-team", ["@deepseek-ai/dsh-base"],
                  patch="- id: agent-preset-registry\n  config: {}\n")
    (dsh_home / "settings.yaml").write_text(LEGACY_SETTINGS % {"default": "rigorquant"})
    assert _install(env, "rq-team").returncode == 0
    registry = _config_row(_patch_rows(tmp_path, dsh_home, "rq-team"), "agent-preset-registry")
    assert registry["config"] == {"default": "standard", "selectedDefault": "rigorquant"}


def test_routes_saved_on_rc2_are_never_overwritten(tmp_path):
    _needs_yaml()
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    saved = (
        "- id: rq-model-router\n"
        "  name: dsh-rigorquant\n"
        "  config:\n"
        "    adversaryPrimary: { provider: deepseek-account, model: deepseek-v4-pro }\n"
        "- id: agent-preset-registry\n"
        "  name: '@deepseek-ai/dsh-agent-preset-registry'\n"
        "  config: { default: standard, selectedDefault: standard }\n"
        "- insert:\n"
        "    - id: my-row\n"
        "      name: my-plugin\n"
        "      config:\n"
        "        root: !!js \"process.env.HOME\"\n"
    )
    _seed_profile(dsh_home, "rq-team", ["@deepseek-ai/dsh-base"], patch=saved)
    (dsh_home / "settings.yaml").write_text(LEGACY_SETTINGS % {"default": "rigorquant"})

    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr
    rows = _patch_rows(tmp_path, dsh_home, "rq-team")
    assert _config_row(rows, "rq-model-router")["config"] == {
        "adversaryPrimary": {"provider": "deepseek-account", "model": "deepseek-v4-pro"}}
    assert _config_row(rows, "agent-preset-registry")["config"]["selectedDefault"] == "standard"
    assert "!!js" in _patch_text(dsh_home, "rq-team"), "a !!js expression lost its tag"
    assert "Ported" not in result.stdout


def test_a_profile_row_with_other_router_config_gains_the_routes(tmp_path):
    """A hand-written router row (say, a shorter degrade TTL) keeps its
    fields: an id-targeted row replaces the whole config, so the port merges
    into it rather than appending a second row that would drop them."""
    _needs_yaml()
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    _seed_profile(dsh_home, "rq-team", ["@deepseek-ai/dsh-base"],
                  patch="- id: rq-model-router\n  config:\n    degradeTtlMs: 1000\n")
    (dsh_home / "settings.yaml").write_text(LEGACY_SETTINGS % {"default": "standard"})

    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr
    rows = _patch_rows(tmp_path, dsh_home, "rq-team")
    routers = [r for r in rows if isinstance(r, dict) and r.get("id") == "rq-model-router"]
    assert len(routers) == 1, routers
    assert routers[0]["config"] == {"degradeTtlMs": 1000, **PORTED_ROUTES}


def test_no_legacy_settings_means_no_port(tmp_path):
    _needs_yaml()
    env, dsh_home, _ = _stub_dsh_env(tmp_path)
    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr
    rows = _patch_rows(tmp_path, dsh_home, "rq-team")
    assert _config_row(rows, "rq-model-router") is None
    assert _config_row(rows, "agent-preset-registry") is None


def test_without_a_yaml_reader_the_port_warns_and_names_the_file(tmp_path):
    """The installer borrows the CLI's `yaml` package; a CLI it cannot borrow
    from must not fail the install, but the operator must hear what was not
    carried over."""
    env, dsh_home, _ = _stub_dsh_env(tmp_path, with_yaml=False)
    dsh_home.mkdir()
    (dsh_home / "settings.yaml").write_text(LEGACY_SETTINGS % {"default": "rigorquant"})
    result = _install(env, "rq-team")
    assert result.returncode == 0, result.stderr
    assert "warning:" in result.stderr and "settings.yaml" in result.stderr, result.stderr
    assert "rq-model-router" not in _patch_text(dsh_home, "rq-team")


def test_the_installers_route_roles_match_the_router(tmp_path):
    """install.sh ports only keys the router's Config declares; its role list
    is a copy of dsh/index.js's ROLES, pinned equal here."""
    router = (REPO / "dsh/index.js").read_text()
    roles = re.search(r"export const ROLES = \[([^\]]*)\]", router).group(1)
    router_roles = re.findall(r"'([^']+)'", roles)
    installer = (REPO / "install.sh").read_text()
    match = re.search(r'^RQ_ROUTE_ROLES="([^"]*)"$', installer, re.M)
    assert match, "install.sh no longer declares RQ_ROUTE_ROLES"
    assert match.group(1).split() == router_roles
