---
status: accepted
date: 2026-11-16
---

# RigorQuant moves to DSH 0.2.2-rc.3 on an open floor, and leaves Agent Teams to the base bundle

DSH 0.2.2-rc.3 announced RigorQuant 0.8.0 as unusable — `Plugin
dsh-rigorquant@0.8.0 is incompatible with dsh 0.2.2-rc.3: requirements
{"engines.dsh":">=0.2.1-rc.2 <0.2.2-0"}` — and the bundle stayed installed
while profile startup denied it until the operator granted an exact-version
exemption and accepted a warning about crashes and data loss. The announcement
was wrong about the fix and right about the core: 0.8.0 does not work there.
From 0.8.1 `engines.dsh` is `>=0.2.2-rc.3` — an **open floor**, with no ceiling
and no restated peer range. The floor names the core the release was exercised
on; every core at or above it is admitted, and the floor moves only when a
release is validated on a newer one. When a manifest declares `engines.dsh` the
gate reads that field alone, so no future core can reproduce the
incompatibility announcement. The release also stops managing Agent Teams:
0.2.2-rc.3 folds the Team bundle into its base bundle, so the installer no
longer adds, pins, enables or configures one, and the team plugin arms Team
**per Session** for a RigorQuant Session. Delegation follows the surviving
contract — the Orchestrator creates a Teammate with the standard `subagent`
tool and an explicit `<role>-<n>` name, and the guards and the skill address
teammates by that name. A study's capacity is 12 live teammates and no
lifetime cap. **0.8.0 is the last release for the 0.2.1-rc.2 line**, and
nothing is backported. The version is a patch, deliberately — a recorded semver
exception. Recorded as Decision 28 in `docs/architecture.md`.

## Why

- **The ceiling was the incompatibility announcement.** On 0.2.1-rc.2 the gate
  already read `engines.dsh` alone; 0.8.0's ceiling, `<0.2.2-0`, is the
  smallest 0.2.2 prerelease, so it excludes every 0.2.2 prerelease as well as
  0.2.2 stable. That was the right shape for a release that was only validated
  on 0.2.1-rc.2, and it is the wrong policy for a release that admits the
  core's future: the same warning returns at *every* later core, identical in
  wording, each time requiring an operator to grant a risk exemption for a
  plugin the gate calls unsafe. A warning that fires on every upgrade stops
  being a signal and becomes a toll. The floor keeps the refusal that protects
  an operator on an older core; the ceiling is gone by policy, not by
  accident, and no future core draws the announcement.
- **The Team bundle was renamed into the base bundle.** The bundle 0.5.0
  enabled, `@deepseek-ai/dsh-experimental-agent-team-profile`, is published
  only through 0.2.2-rc.1. `@deepseek-ai/dsh-agent-team` exists from
  0.2.2-rc.2, and the base bundle mounts `agent-team` (`maxTasks: 256`) and
  `tool-agent-team` itself. So a fresh `./install.sh` tried to enable a package
  the registry does not serve at this core and reported a warning and a
  profile missing Team; a profile that still lists the retired package cannot
  resolve it at all. The rename is one of the shipped upgrade guide's subjects
  (`v0.2.1-rc.2/session-team-mode`, which also says profile loading removes the
  retired bundle selection).
- **The `agentTeams` config the installer wrote now throws.** 0.2.1-rc.2's
  `agentTeams` config accepted `{maxMembers, maxTasks, maxMessageBytes,
  disposalTimeoutMs}`. 0.2.2-rc.3's is `{maxTasks, defaultEnabled}`, and the
  constructor throws `TEAM_INVALID_CONFIG` naming `maxMembers`,
  `maxMessageBytes` and `disposalTimeoutMs` when they are present — the three
  keys the installer wrote and the bundle patch overrode — so the team service
  does not mount at all. Schemastery preserves unknown keys, which is why
  0.8.0 mounted on 0.2.1 with the keys inert and nothing noticed; the mount
  seam pins the removal in both directions so the migration cannot be "tested"
  against the friendly old schema. `maxMembers` was the lifetime member cap, so
  there is no lifetime cap left to raise.
- **The delegation and identity API was removed.** `spawn_teammate` is gone.
  The standard `subagent` tool creates teammates and, since 0.2.2-alpha.3,
  accepts an optional `name`; `send_message` and `interrupt_agent` take
  `agent`, not `agent_id`; `list_agents` rows are `{name, status,
  description}`; Team task ownership is `owner`, a name. `ctx.agentTeams` lost
  its creation, messaging, roster and membership surface: `tryMembership` and
  `listMembers` are removed, and identity is the live subagent tree
  (`subagents.rootOf` / `namesOf`). The plugin was written against the removed
  names — the role-name guard hooked `spawn_teammate`, so the surviving
  `subagent` tool reached no guard; the hub-and-spoke guard read `args.target`,
  so it never saw the `agent` argument — and the probe half was worse than the
  code half: the router and lane probes **stubbed** `tryMembership` and
  `listMembers`, so the suite stayed green while a live core threw
  `teams.listMembers is not a function`. A study on 0.2.2-rc.3 would then lose
  the mechanism that gives a Teammate its Role — every teammate mounting with
  the root persona and the full catalog, exactly the failure the framework
  exists to prevent — and no error would say so.
- **Agent Teams ownership belongs to the base bundle; per-Session arming is
  the plugin's job.** Team now ships with base-backed profiles, defaults to
  off, and saves the root Session's selection in the Team projection
  (`v0.2.1-rc.2/session-team-mode`). Installing RigorQuant must not change what
  an operator's other presets do, and a study must not depend on a menu toggle
  the operator may not know about. So on agent creation, for a root Session
  composed as `rigorquant`, the plugin calls the service's
  `setEnabled(agent, true, signal)` and publishes the guard-armed runtime
  context only when `isEnabled` confirms the selection; a non-RigorQuant root
  is never touched, a teammate is never armed by its own request, and the
  service stays optional and duck-typed so a core without it disarms instead
  of failing.
- **Capacity is live concurrency, not lifetime membership.** The base
  subagent service defaults to 8 live children per root; the bundle patch
  overrides the `subagent` row with `maxActiveSubagents: 12` and restates
  `maxDepth: 1` because an id-targeted patch replaces the row's config
  wholesale. There is no lifetime cap: once a teammate settles, another may
  take its slot. Over the pool a spawn raises `ACTIVATION_LIMIT_REACHED`,
  which nothing but a settling teammate clears, so an exhausted pool is a
  BUDGET-class outcome — checkpoint and end the turn, never retry in a loop.
- **The visible tool set is a classification, not a deny list.** 0.2.2 mounts
  tools a short every-teammate deny list cannot anticipate (`lsp`, `ralph`,
  `workflow`, and `apply_patch`, which the filesystem package and the base
  both default off). The team plugin now names, per Role tier, every tool a
  teammate may see, and anything not classified is denied. The classification
  is data, so adding a Role or a tool is a one-line change and a test failure,
  never a silent leak: a test fails when the installed core gains a model-facing
  tool nobody classified. `apply_patch` is not adopted. Interruption is not
  restored either: the base and Web presets set `tool-subagent-control`'s
  `interrupt: false`, so a Team session never sees `interrupt_agent`
  (`v0.2.2-rc.1/subagent-interrupt-default`), and the framework's round loop
  never depended on interrupting a teammate.
- **A patch release raising the floor is an explicit semver exception.** Every
  prior band move in this repository was a minor because the band move *was*
  the release's headline. Here the headline is "0.8.0 does not work on the
  current core", a fix; the floor rise is a consequence, not a feature.
  0.9.0 was considered and rejected: it would read as "a new line of support
  started" instead of "your current plugin is broken here", and it would invite
  dual-support questions for a line that will not be supported. So 0.8.1 is a
  patch, 0.8.0 is the last release for 0.2.1-rc.2, and nothing is backported.

## What moved

- **The band.** `package.json` declares `engines.dsh: ">=0.2.2-rc.3"` and no
  `@deepseek-ai/dsh` peer dependency. `install.sh` keeps
  `MIN_DSH_VERSION = 0.2.2-rc.3` for the refusal and replaces
  `MAX_DSH_VERSION` with `VALIDATED_DSH_VERSION`, the same version; a core
  above it prints an advisory naming the validated core and continues, a core
  below it refuses before copying anything, and `--skill-only` bypasses both.
  The gate probe judges the real manifest with the installed
  `evaluatePluginCompatibility`: accepted on the live core and on every
  version above the floor (including a 0.3.0 the registry does not serve),
  refused on 0.2.1-rc.2 and 0.2.2-rc.2 with the refusal naming the floor. It
  is the compatibility suite's only range test; no test replaces it with a
  string comparison.
- **The installer's contract.** A full install no longer manages Agent Teams:
  it adds, pins and enables no Team bundle, writes no `agent-team` row into the
  profile's user patch, and prints no Beta-card instructions. It does clean up
  after 0.8.0: it removes the retired Team bundle (and the retired web bundle)
  from a profile that still lists either, with one line saying why; it migrates
  a marked 0.8.0 block by deleting the three rejected keys inside its
  `agent-team` row and keeping everything else, including a `maxTasks` the
  operator saved from the Plugins page; a block that then carries nothing but
  the enabled-bundles record is removed with it, and the record is retained
  while any older block still needs removal because `--uninstall` reads it. A
  re-run changes nothing, and `--uninstall` removes only what an installer
  wrote. With no `dsh` on the path the step warns and is skipped, which keeps
  CI's install smoke test green.
- **Agent Teams, armed per Session.** The bundle patch drops the `agent-team`
  override; the base bundle's shipped `maxTasks` is the value. `dsh/team.js`
  keeps its composition half — persona, tool budget, model tier and the
  "RigorQuant team guard: armed" line by name — and adds the per-Session
  `setEnabled` arming described above, on both `agent/created` and the late
  `agent-preset/selected` switch, with the armed context published only when
  the service reports the selection enabled. Composition has a **third
  trigger**: a teammate has no tree identity during its own `agent/created`
  (the subagent manager records the activation only after the child is
  created), so its persona, budget and guard are applied on
  **`subagent/start`**, the creation edge published after that residency step
  and after the child is a live Agent. Without it, every teammate mounted with
  the root persona and the full catalog — the exact failure the framework
  exists to prevent. A teammate does not need the Lead's
  `agent-preset/selected` path: it joins its parent's composition in the
  creation window.
- **Delegation, by name.** The role-name guard hooks the standard `subagent`
  tool: a spawn whose `name` does not parse as `<role>-<n>` is refused, and
  `subagent_fork` is refused outright. The hub-and-spoke guard reads
  `send_message`'s `agent` argument (a name or a Session id), resolves it to
  the root `lead` through the subagent catalog and refuses anything else with a
  message naming the legal target. Roster and board guards keep using names:
  `list_agents` rows are `{name, status, description}`, and Team task ownership
  is `owner`. Role, persona, tool budget, model tier and fresh-versus-reused
  policy are unchanged; they always keyed on the name, and the name is now
  chosen by the Orchestrator instead of by a removed tool. The skill teaches
  the same calls and treats `inactive` as not-done.
- **Capacity, restated as what it now is.** 12 live teammates per study, no
  lifetime cap, in the bundle patch, the skill's Step 3, the protocol's roster
  and BUDGET rules, both READMEs and the architecture record.
- **Classification and interruption.** `dsh/team.js`'s scope is the per-tier
  allow classification alone (`blind` and `web-denied` keep their existing
  semantics: `skill` denied only to blind roles, web denied to blind and
  adversary roles). The old exported every-teammate deny list is deleted, not
  kept beside the tiers: a global deny mask cannot reach the scope-registered
  Team tools, and two exported scope sources invite a reader or a test to audit
  the wrong one. `interrupt_agent` is absent from every tier, matching the
  shipped configurations. The tool-catalog probe pins the classification
  against the installed core's shipped `tool-catalog.md` page (under its
  own `docs/`), so a new
  model-facing tool fails a test instead of widening a teammate's scope.
- **The skill and the static pins.** `SKILL.md` and `references/` teach
  `subagent` + `name`, `send_message({agent, message})`, `list_agents` rows and
  the board's `owner`; no teaching document names `spawn_teammate`,
  `agent_id`, `target` or `ownerId`. The static suite pins the open-floor
  policy, the last-release statement, the Decision 28 references, the
  repo-wide live-teammate pool, and the absence of the retired delegation
  names from every current document.
- **The client half.** No change. The only plugin-manager surface that moved
  is the bundle update-state field (`BundleInfo.update` replaces
  `BundleInfo.updatable`, `v0.2.2-rc.1/plugin-update-method`), and the routing
  card never read it.

## The upgrade guides this hop cites

The 0.2.2-rc.3 package ships `docs/upgrade-guide/`, one directory per release
and one guide per migration. This hop cites those guides rather than
re-deriving a seam ledger against an installed tree: the core maintains them,
they name the migration steps in order, and ADR 0004's line-cited ledger dates
itself the moment the package is republished. Paths below are relative to the
0.2.2-rc.3 package's `docs/upgrade-guide/`; every claim in this ADR was also
read from the installation itself, and each guide below is a statement of the
same contract.

| Shipped guide | What it settles here |
| --- | --- |
| `v0.2.1-rc.2/agent-team-subagents` | `spawn_teammate` and the Team-scoped controls are removed; the standard subagent tools and Session ids take over; `list_agents` takes no scope; Team supplies four task tools; `agent-team` rejects `maxMembers`, `maxMessageBytes` and `disposalTimeoutMs`; `tryMembership` is replaced by `rootOf` and `listMembers` by `listDescendants` |
| `v0.2.1-rc.2/session-team-mode` | Team defaults off, the root Session's selection controls its tree, the selection survives restart, and profile loading removes the retired Team bundle selection (keep the row overrides) |
| `v0.2.2-alpha.3/subagent-names` | The optional `name`, `send_message({agent})` / `interrupt_agent({agent})` replacing `agent_id`, `list_agents` rows of `{name, status, description}`, `owner` replacing `ownerId` on Team tasks, and the subagent catalog moving to payload version 3 |
| `v0.2.2-rc.1/subagent-interrupt-default` | Built-in configurations set `interrupt: false` on `tool-subagent-control`, so `interrupt_agent` is not registered for Team mode |
| `v0.2.2-rc.1/plugin-update-method` | `BundleInfo.update` replaces `BundleInfo.updatable`; the routing card reads neither |
| `v0.2.2-alpha.2/fs-observation-policy-default-off` | `apply_patch` ships off from the filesystem package and the base bundle; this release does not adopt it |

## Considered and rejected

- **0.9.0.** Recorded under *Why*: the headline is a fix, not a new line of
  support, and 0.8.0's own release says which harness it is the last for.
- **Keeping the ceiling and adding a release per core.** Every later core
  would need a new plugin release to lift the announcement, and the operator
  would install an exemption in between. That manufactures the risk the
  exemption warns about; the open floor removes it.
- **Dual support for 0.2.1-rc.2.** Two Team ownership models in one code path
  — a plugin-installed bundle and its four config keys on one core, a
  base-mounted service and per-Session selection on the other — for a line
  whose bundle is no longer published on the new core. The installer would have
  to branch on the core's minor, which is the dual-version trap every prior
  cutover refused. 0.8.0 stays the last release for that line.
- **Re-registering `spawn_teammate` as a plugin tool.** It would have to
  recreate identity, messaging and the task board that the subagent tree now
  owns, and it would teach a call the core no longer has. The standard
  `subagent` tool is the contract.
- **Restoring `interrupt_agent` for Team.** The shipped base and Web presets
  disable it, the round loop never depended on it, and enabling it would add a
  tool every other agent in the profile lacks.
- **Adopting `apply_patch`.** Both the filesystem package and the base set it
  off; the preset needs no change and this release adds no tool.
- **Keeping a deny list and denying the known-bad names.** A tool the core
  newly mounts would silently extend a teammate's scope; an explicit
  classification fails a test instead.
- **Letting the installer keep configuring Team for older profiles.** It
  cannot: the bundle is not published for this core and the keys are rejected
  by the service. The base bundle supplies both, so the installer's job is
  removal and migration.

## Consequences

- An operator on 0.2.2-rc.3, or on any later core, installs and mounts
  RigorQuant without an exemption and without an incompatibility warning. A
  core above the validated one gets an advisory naming 0.2.2-rc.3 and the
  install continues; a core below the floor is refused before anything is
  copied.
- Upgrading a 0.8.0 profile is stop dsh → install a core the registry serves,
  named explicitly (`@0.2.2-rc.3` or the `next` tag: npm's `latest` dist-tag
  still points at 0.2.2-rc.1) → re-run `./install.sh`. The installer removes
  the retired Team bundle and web bundle, migrates the marked block, carries
  saved routes over, and leaves a re-run with nothing to do. An operator on
  any earlier release upgrades straight to 0.8.1.
- Resuming a session started on the previous core is not promised: the
  subagent catalog persists payload version 3, and releases before that change
  cannot open Sessions that create subagents after upgrading. Finish or
  archive studies in progress before the cutover.
- A profile running 0.8.0 keeps its saved routes, its preset and its
  behaviour, with the intentional differences: Team armed per Session instead
  of profile-wide, a 12-live-teammate pool instead of a 64-lifetime cap, an
  explicit tool classification instead of a deny list, and no
  `interrupt_agent`.
- A future core is admitted by declaration and judged by use. The release says
  which core it was exercised on; the installer says so too; the operator
  decides how much to trust a long study on a core nobody has measured.
