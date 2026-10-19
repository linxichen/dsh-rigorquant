---
status: accepted
date: 2026-10-19
---

# RigorQuant moves to DSH 0.2.1-rc.2, closes a false-green ceiling, and pins five native limits

DSH 0.2.1-rc.2's compatibility gate matches a declared range with
`includePrerelease`, so the old band `>=0.2.0-rc.2 <0.2.1` **already admitted
0.2.1-rc.2**: `<0.2.1` excludes 0.2.1 stable, not a prerelease of 0.2.1.
RigorQuant 0.7.0 therefore mounted on the new core without ever claiming it —
the ceiling that was supposed to keep 0.2.1 out was the ceiling that let its
release candidates in. From 0.8.0 RigorQuant requires
`>=0.2.1-rc.2 <0.2.2-0`: the floor rises to the first 0.2.1 release
candidate, and the ceiling uses semver's `-0` sentinel so every 0.2.2
prerelease is excluded too, not only 0.2.2 stable. On this core `engines.dsh`
is the enforced field — the gate reads it alone and ignores
`peerDependencies` — so the manifest, the installer and the tests state that
one band, and `peerDependencies` stays equal to it. **0.7.0 is the last
release for the 0.2.0-rc.2 line**, and nothing is backported. Alongside the
band, the release deletes two config keys that 0.2.1 dropped from schemas the
preset writes, denies the new host-plane `working_directory` tool to
teammates, corrects the Team message contract in the skill, and pins five
native token limits the host already serves. Recorded as Decision 27 in
`docs/architecture.md`.

## Why

- **The old ceiling was a false green, not a guard.** Every previous cutover
  in this repo was justified by the same mechanism: the loader skips a bundle
  whose range the running core does not satisfy, so a wrong range means no
  preset, no router, no team guard, and no error a user can see. With
  `<0.2.1` that never fired on 0.2.1-rc.2 — prereleases participate in every
  range comparison the gate makes — so 0.7.0 ran on a core it was never
  validated against and reported nothing. The host differential for this hop
  recorded that as its first seam (S1), checked with the **installed**
  harness's own `evaluatePluginCompatibility` rather than a second range
  matcher. This release is the validation, not a fix for a broken mount.
- **On 0.2.1-rc.2 the gate reads `engines.dsh` alone.** When a manifest
  declares `engines.dsh`, the 0.2.1 gate evaluates that range and ignores
  `peerDependencies`; the issue object it returns also renamed its field from
  `peers` to `requirements` (S2). Two consequences shaped the code half: a
  one-sided edit of either manifest field silently changes what the loader
  enforces, so a test now asserts the two are equal; and the shared harness
  locator reads `issue.requirements ?? issue.peers`, so a refusal against
  either core names the range it actually read instead of `(undefined)`.
- **`-0` is the sentinel that makes the ceiling mean what it says.** `<=0.2.1`
  and `<0.2.2` would both admit `0.2.2-rc.1` under `includePrerelease` — the
  same bug one minor version up. `<0.2.2-0` is the smallest possible 0.2.2
  prerelease, so everything at or above it is excluded while 0.2.1 stable and
  every 0.2.1 prerelease are admitted. The release pins that shape with a
  verdict test over the installed gate (accepts `0.2.1-rc.2` and `0.2.1`;
  refuses `0.2.2-rc.1`, `0.2.2`, and `0.2.0-rc.2`), because a string-equality
  test of the band cannot catch a prerelease-ordering mistake.
- **Two keys the preset wrote are gone from their schemas.** `agentTeams`'s
  `Config` no longer has `maxPendingMessagesPerMember` (the mailbox moved onto
  the journal/session projection); schemastery preserves an unknown key, so
  the preset's row mounted with a silent no-op instead of failing (S3). The
  two **disabled** `tool-subagent` rows still carried `backgroundMode:
  one-shot` after 0.2.1 dropped `backgroundMode`, `enableRunInBackground`,
  `persona` and `toolFilter` and added `agentPreset`/`allowedAgentPresets`
  (S4). A disabled row is never imported, so neither was a mount failure —
  exactly why a stale key here drifts unnoticed until someone enables the
  row. This repo's rule is that whatever a migration makes dead is deleted in
  the same release, and so are the tests that pin it.
- **A new host-plane tool crossed the isolation boundary.** 0.2.1's base
  bundle mounts `working_directory`, a model-facing tool that changes the
  session's working directory. RigorQuant's per-teammate scratch directory is
  part of its brief and its evidence contract, and a teammate that switches
  cwd can write outside the directory its validator checks; no pre-0.2.1
  teammate ever had the tool, and none may acquire it by upgrading the host
  (S7). It joins `EVERY_TEAMMATE_DENY` beside the goal, todo and
  unattended-contract tools.
- **The team message contract changed under the skill.** 0.2.1's
  `send_message` returns `{sent: true}` (was
  `{messageId, status: "accepted" | "queued"}`), awaits durable admission,
  and carries teammate identity in a required `team:identity` runtime context
  instead of a `<system-reminder>` prefixed to the initial prompt; the
  `spawn_teammate` request is unchanged (S14). The skill's L3 rule was
  rewritten to the new observable contract without weakening it: a failed
  send is an error, a successful result means stored rather than processed,
  and a message is never resent. No plugin code changed for this — the
  guards read the same tool names and arguments they always did.
- **Five native limits are the measured cutover slice.** The 0.2.1 host
  already serves every one of them as row configuration; landing them with
  the band bump costs no plugin code and no new mechanism. They are the
  cutover-safe part of the token-efficiency survey: the always-on savings are
  small because this framework is already lean, and the large wins
  (compaction, transcript structure) need a real study to measure before they
  can be defaults. `docs/token-efficiency.md` records the adopted limits with
  their measured basis, the deferred follow-ups, and the native mechanisms
  considered and rejected.

## What moved

- **The band.** `engines.dsh` and `peerDependencies["@deepseek-ai/dsh"]` are
  both `>=0.2.1-rc.2 <0.2.2-0`; `install.sh` carries `MIN_DSH_VERSION` /
  `MAX_DSH_VERSION` for the same pair and still consults both bounds before
  copying anything. The floor moves with the ceiling because one range is
  evaluated against one running core: this release is validated on
  0.2.1-rc.2, and 0.7.0 remains installable for 0.2.0-rc.2.
- **Dead keys deleted.** `maxPendingMessagesPerMember` is gone from the
  bundle patch's `agent-team` row, from the installer's marked block, and
  from the tests that pinned it; the row keeps `maxMembers: 64`,
  `maxTasks: 256`, `maxMessageBytes: 65536` and `disposalTimeoutMs: 5000`.
  `backgroundMode: one-shot` is gone from the two disabled
  `tool-subagent-codex` / `tool-subagent-claude-code` rows, which keep
  `provider`, `toolName` and `maxDepth` and stay disabled. The external-agent
  rows were never the delegation path — Agent Teams' `spawn_teammate` is —
  and the new `agentPreset`/`allowedAgentPresets` pair is the native preset
  mechanism if that path is ever revived.
- **The teammate deny list.** `working_directory` joins `create_goal`,
  `update_goal`, `get_goal`, `todo_write`, `ask_user_question` and
  `exit_plan_mode`. The Lead keeps the tool: cwd changes are an orchestrator
  decision, not a teammate capability.
- **The skill's send rule.** `references/protocol.md` (L3) and the sentence
  that cites it in `SKILL.md` now describe the 0.2.1 result. The never-resend
  rule is unchanged; what changed is the evidence a resend decision rests on.
- **Five native configs in the preset.** `tool-skill` caps catalog
  descriptions at 160 characters; `tool-fs` caps a read at 24,576 bytes and
  1,200 lines; `tool-fs-search` caps a glob at 60 results and a grep at 120
  matches (keeping `sampleOverCapGlobResults: false`); `tool-goal` pins
  `blockedAfterConsecutiveRounds: 3`; `agent-instructions` caps injected
  workspace instructions at 8,192 bytes and reads `AGENTS.md` only. Each is
  pinned by a test, so a future host default cannot silently move it.
- **The compatibility suite.** Alongside the verdict regression, the suite
  asserts `engines.dsh` equals the peer range, the new band in both manifest
  fields, the installer pair, the removed keys' absence, the five configs,
  and the teammate deny set. The refusal-path fix in the harness locator
  clears the one pre-existing failure the target harness produced.

## Considered and rejected

- **Staying on `>=0.2.0-rc.2 <0.2.1`.** It never excluded 0.2.1's release
  candidates, so it is the same false contract the new band replaces, and it
  refuses 0.2.1 stable once it ships.
- **Widening the ceiling without raising the floor (`>=0.2.0-rc.2 <0.2.2-0`).**
  One range is evaluated against one running core, and this release is
  validated only on 0.2.1-rc.2: the dead-key removals, the teammate deny and
  the message-contract wording are all 0.2.1 facts. Keeping 0.2.0-rc.2 in the
  same manifest would claim support for the core the key removal makes stale,
  which is the mistake the previous cutovers refused to make.
- **`<=0.2.1` or `<0.2.2` as the ceiling.** Both admit 0.2.2 prereleases
  under `includePrerelease`, which is the exact failure this release exists
  to close. The `-0` sentinel costs one character and excludes them.
- **Keeping the dead keys as harmless extras.** A key the schema does not
  declare is not a contract; it is a promise the files cannot keep, and it
  makes the next reader look for a cap that no longer exists.
- **Taking up the survey's larger native mechanisms in this cutover.**
  Compaction right-sizing and spill tightening need a live A/B on a real
  study; `SKILL.md`/persona slimming is a content migration that moves pinned
  prose; PTC presentation rewrites the whole operating procedure and is not a
  universal reduction per the host's own documentation. All four are
  deferred with reasons in `docs/token-efficiency.md`. The native schedule
  bundle, session search, hooks/webhooks, workflow/ralph fan-out and the
  classic subagent fork stay rejected for the contract reasons Decision 26
  recorded, and 0.2.1 adds none of them to the shipped inventory in a form
  that changes that answer.

## Consequences

- `install.sh` refuses a core below 0.2.1-rc.2 or at/above 0.2.2-0 before
  copying anything, and both READMEs carry the operator sequence for the
  cutover. An operator on any 0.5.x–0.7.x release upgrades straight to this
  one: the installer keeps the migrations those releases needed (the retired
  web bundle, the `settings.yaml` route port, the pre-0.6.0 directory preset)
  and re-pins the Agent Teams bundle to the running core's version.
- A profile that already ran 0.7.0 on 0.2.1-rc.2 is unchanged in behavior
  except for the intentional ones: the five limits, the teammate deny, and
  the message wording. Its saved routes and preset default carry over.
- The harness probe validates every row against the 0.2.1-rc.2 packages and
  judges the core with the harness's own gate, so this release cannot repeat
  the false green: a target core outside the new band refuses in the probe,
  the installer and the loader alike.
- The token limits are configuration only. The deferred proposals stay
  proposals until a measured study says otherwise; nothing in the plugin's
  code depends on the numbers.
