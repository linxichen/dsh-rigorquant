---
status: accepted
date: 2026-09-24
---

# RigorQuant declares its preset on DSH 0.1.7, and the escalation lane mounts at runtime

DSH 0.1.7 ignores `$DSH_HOME/.agent-presets`. It builds a preset from a
declared `@deepseek-ai/dsh-agent-preset` row, and a bundle's patch can
declare one. Settings are now owned by the profile, and the Team service
has no browser Remotes left. From 0.6.0 RigorQuant requires
`>=0.1.7-rc.2 <0.1.8`. It declares its `rigorquant` preset in its own
bundle patch and keeps no compatibility with 0.1.6. The escalation lane is
no longer a disabled preset row: the orchestrator mounts it at runtime
through a host tool. Recorded as Decision 25 in `docs/architecture.md`.

## Why

- The old and new harnesses have no period in which both work. A declared
  preset cannot load on `0.1.6-alpha.2`, because the package does not exist
  there. A directory preset is dead on 0.1.7. So the release is a single
  cutover that the operator installs together with the harness upgrade,
  before the first 0.1.7 boot. 0.5.0 stays the last release for alpha.2.
- On a declared preset a single child row cannot be patched, and child rows
  are evaluated once, when the preset activates. Flipping `mcp-jacobian`
  in the installed copy, which is what 0.5.0 did, is no longer possible. An
  environment variable plus a restart would work, but the orchestrator
  could no longer decide on escalation partway through a study. A host
  plugin, by contrast, can mount `@deepseek-ai/dsh-mcp-client` into one
  agent's scope; upstream's `mountSessionMcp` is the precedent. rc.2's
  dynamic tool updates then announce the new tools on the next request.
- The version range is capped below 0.1.8. The compatibility gate then
  refuses an untested harness with a stated reason, instead of mounting half
  of the bundle.

## Considered and rejected

- **`RQ_JACOBIAN=1` plus a restart.** The orchestrator can't act on it
  partway through a study, and Desktop users can't easily set it.
- **The row always on, with its tools hidden by `tools.restrict`.** Every
  boot would start an `npx jacobian` process for every agent.
- **Deferred tool loading.** The model has no tool to load a deferred tool.
- **A second preset with the lane enabled.** The lane would have to be
  chosen when the study starts, not when a claim needs it.
- **Keeping a 0.5.x line for alpha.2.** Two harness generations would each
  need their own tests, for a dependency that was already experimental.

## Consequences

- `rq_escalate` can be called only by the orchestrator. It mounts the lane
  into the orchestrator itself or into a teammate it names, with
  `failOnStartupError: true`, so a failed mount becomes an error the
  orchestrator can act on. The lane stays on until the session ends. After a
  restart the orchestrator mounts it again if the journal shows an
  escalation still open. The orchestrator switches the lane on without
  asking. Installing jacobian and setting up Lean still ask the user.
- Blind roles may receive the lane, but only to check a derivation they have
  already made, never to find or search.
- The boot-time sync keeps only the compute lane and is renamed. The
  installer adds only the single Team bundle, always removes the old web
  bundle, and moves saved routing overrides into the router's profile
  config.
- Anything this migration makes dead is deleted in the same release, and so
  are the tests that pin it. The earlier upgrade studies and the repository
  review are deleted; this record and git history keep their reasons.
