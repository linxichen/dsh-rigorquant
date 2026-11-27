---
status: accepted
date: 2026-11-16
---

# Distribution is the plugin manager

RigorQuant 0.8.1 ships without `install.sh`. The operator decision
(2026-11-16) is that the DSH plugin manager is the **only** install and
uninstall mechanism: install with `dsh plugin add dsh-rigorquant` or the
**Plugins** page, uninstall with `dsh plugin remove dsh-rigorquant`. The file
is deleted outright — no shim, no deprecation stub, no "run this instead"
script — and its `bin` and `files` entries leave the package manifest with it.
The decision was taken before 0.8.1 was released, so 0.8.1 is the first
release that never had an installer.

The four duties the script still carried are each dropped or native now:

| Duty | Fate |
| --- | --- |
| Profile migrations (0.8.0 marked block, retired Team/web bundles, saved routes) | **Dropped.** No migration for releases ≤0.8.0. |
| Uninstall | **Native.** `dsh plugin remove`; the shared lane stays. |
| The skills-only distribution path (`--skill-only`) | **Dropped.** The bundle's skill row is the one path. |
| A pre-flight version gate (floor refusal plus above-floor advisory) | **Dropped.** The loader's own compatibility gate is the gate. |

**Migrations are dropped because there is nothing left to migrate on the
supported path.** 0.8.1 is unreleased: the 0.8.0 installer's fixtures
described a profile no operator of this release has to keep, and the
installer itself was the only code that wrote foreign rows into a profile's
user patch. An operator on 0.8.0 or earlier upgrades by removing and adding
the plugin: the core removes the retired Agent Teams bundle selection at
profile load, saved routes on a 0.8.0 profile live in the profile patch and
stay, and a marked block a 0.8.0 installer wrote is the operator's to clear —
one edit, deleting the block between its `BEGIN` and `END` markers, said
plainly in both READMEs and the changelog. A route saved on an older release
in `settings.yaml` is not ported; it is re-selected on the routing card. The
alternative — porting the two migration engines (`test_installer_agent_teams`
alone was 958 lines of shadow-profile harness) for a profile population of
zero releases — would keep a second writer of profile state alive for a
transition that never shipped.

**Uninstall is native, and the lane is not plugin state.** DSH's plugin CLI
has no uninstall hook: `dsh plugin remove` is pnpm delete plus a manifest
reconcile, and code that no longer exists cannot run. The installer's
`--uninstall` existed because the installer wrote rows and files; with no
writes there is nothing to unwind. The one artifact the plugin does land, the
shared compute lane at `$DSH_HOME/share/rigorquant`, **remains** on uninstall
because it is study evidence, not plugin state: a study's `study.json` records
that path, and deleting it would silently detach a finished study from the lane
it ran on. The lane's `.rq-sync.json` marker keeps ownership discoverable, and
the ADR states the rule so a future reader does not "fix" it into a removal
hook.

**There is one skill distribution path.** The bundle's skill row serves the
package's skills directory (`agent-presets/rigorquant/skills`) at a custom
root, so rigorquant and the two literature skills arrive with the plugin. A
second copy in `$DSH_HOME/skills` under `--skill-only` added a rank/shadowing
story (custom root 300 beats `$DSH_HOME/skills` 400) to defend a duplicate
that no longer has a reason to exist. The skill row is the path; a machine
that already has those skills in `$DSH_HOME/skills` keeps them, shadowed.

**The loader's gate is the only gate.** When a manifest declares
`engines.dsh` the installed `evaluatePluginCompatibility` reads that field
alone (`includePrerelease` matching), refuses a core below the floor, and
admits every core above it. A pre-flight check in the installer was a second
band: it disagreed with the gate when it was stale, and its above-floor
advisory existed only because a script thought it had a policy. The floor
now lives in exactly one place — `package.json`'s `engines.dsh` — and the
release states the core it was exercised on in prose. The gate probe still
judges the real manifest against the installed gate, so a range edit fails a
test rather than an install.

## What replaces the script

- **CI** runs `tests/package_shape_smoke.py`, a stdlib-only Python script that
  needs no `dsh`: every `dsh.bundle.patch` file exists, every `exports` entry
  resolves, the lane template directories the boot sync copies (`env/`,
  `mcp/`, read from `dsh/sync.js`'s `MANAGED_DIRS`) are present with the
  lane anchor, and no current package file references a removed installer.
  The install smoke step is gone with the script.
- **The static suite** pins the distribution claims: both READMEs state
  `dsh plugin add`/`remove` and the lane-stays rule, the changelog's `0.8.1`
  `### Removed` entry names the installer, the Decision-29 section and this ADR
  exist, and a repo-wide sweep fails any current file that still names the
  removed installer, `--skill-only` or an installer-driven migration. The
  changelog, `docs/architecture.md` and the ADRs are exempt as history — this
  ADR must name what it retired.
- **The boot sync** (`dsh/sync.js`) lands the lane and its files as before;
  only its comments changed. The runtime halves — router, team, lane sync,
  client card — are untouched.

## Considered and rejected

- **A shim or deprecation stub.** A script that only prints "use `dsh plugin
  add`" is a door that opens onto nothing: it keeps the `bin` entry, the npm
  surface and the support question alive to serve no operation. Delete it.
- **Keeping the installer but warning on use.** Same surface, plus a second
  thing that has to track the plugin manager's spec syntax.
- **Keeping the installer's version gate without the rest.** The gate would
  still be a second band, and the loader already refuses a core below the
  floor before the bundle mounts. Two refusals can disagree; one cannot.
- **Keeping `--skill-only`.** It is a second distribution path with its own
  duplication and ranking rules, for skills the bundle already serves.
- **Migrating 0.8.0 profiles.** Code that edits an operator's profile patch is
  the thing this decision removes; the one-time edit is small, one release
  old, and documented where the operator reads the upgrade.
- **An uninstall hook for the lane.** DSH has no hook to run one, and the lane
  must survive the plugin by design (study evidence).

## Consequences

- The documented commands are `dsh plugin add dsh-rigorquant` (or the Plugins
  page) and `dsh plugin remove dsh-rigorquant`. The package ships no `bin`.
- A machine with no `dsh` can still prove the package's shape in CI, which is
  what the installer smoke used to approximate while needing a `dsh`-free
  path of its own.
- Upgrading from 0.8.0 is: stop dsh, install a core the registry serves, remove
  and add the plugin, clear a leftover 0.8.0 profile block by hand, restart.
  Saved routes on that profile stay; an older release's are re-selected.
- Uninstalling leaves `$DSH_HOME/share/rigorquant` in place, deliberately.
  Re-installing resumes from the same lane; the sync is idempotent.
- The release stays 0.8.1: removing the installer changes how the same
  artifact is delivered, not what the plugin does.

Amends:

- **20:** the floor is enforced by the loader's gate alone; the installer's
  pre-flight refusal is gone.
- **22:** removal of the lane no longer has an explicit command — it stays,
  because it is study evidence.
- **24:** the installer's Team cleanup and enabled-bundles record are gone with
  the installer; the base bundle and the per-Session arming are the whole
  story.
- **28:** that Decision's installer contract is superseded within the same
  release (the amendment is recorded on it).
