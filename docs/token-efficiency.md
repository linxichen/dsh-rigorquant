# Token efficiency — what 0.8.0 adopts, and what stays a measured follow-up

This note records the token-efficiency work behind 0.8.0: the five native
limits the preset now pins, why each one matters, and what was deliberately
left for a later, measured release. It is the written half of Decision 27;
the mechanism inventory lives in `docs/architecture.md` and the decision
record in `docs/adr/0004-rigorquant-on-dsh-0.2.1.md`.

The survey behind it was run against the live DSH 0.2.1-rc.2 host, on this
framework's own rows, and every adopted config was validated by
`tests/preset_harness_probe.cjs` on that host before it landed. No number
below is invented where a measurement exists.

## How the numbers were measured

- **Request envelope.** One real session on the 0.2.1-rc.2 host recorded
  `request/header` with **57 tools = 49,673 bytes of tool JSON ≈ 12,418
  tokens** in every request. Per-tool bytes used below are that session's
  actual schemas (`bash` ≈ 575 tokens, `read` ≈ 109, `glob` ≈ 187, `grep` ≈
  175, `skill` ≈ 83, `spawn_teammate` ≈ 156, `send_message` ≈ 115, and so on).
- **Preset catalogs**, composed from those per-tool measurements: the Lead's
  catalog ≈ **18.1 KB ≈ 4,531 tokens**; a teammate's ≈ **13.8 KB ≈ 3,453
  tokens** (goal/todo/ask/exit-plan are removed by `tools.restrict`; the Team
  tools stay because scoped registrations cannot be restricted).
- **Always-on text.** The root persona renders 3,809 chars ≈ **952 tokens**
  for every Lead request. The `rigorquant` skill body is **34,928 bytes ≈
  8,732 tokens**, loaded once at study start and retained for the run.
- **≈ 4 chars/token** is used only where the byte count is the measurement;
  `request/header` and the catalog figures above are token counts already.

The framework is already lean in what it mounts always-on. The large
opportunities are dynamic — how much a single tool result may inject, and how
much conversation has to be replayed before compaction — so the cutover adopts
the bounded-result limits and defers the structural changes.

## Adopted in 0.8.0 (cutover-safe, config only)

| Limit | Native mechanism | Measured basis | Purpose |
|---|---|---|---|
| Skill-catalog descriptions ≤ 160 chars | `tool-skill.catalogDescriptionMaxLength` (default 500) | rendered catalog 1,423 chars ≈ 356 tokens at 500; 538 chars at 160 → ≈ −221 tokens per skill-visible agent (6 of 8) | shrinks a durable message every later request replays |
| `read` ≤ 24,576 bytes, ≤ 1,200 lines | `tool-fs.readMaxBytes` / `readLimit` (defaults 51,200 / 2,000) | one read could inject ≈ 12.8 k tokens; spill **skips** `read` and the pruner only runs after a compaction trigger → the largest read loses ≈ 6.7 k tokens | the main evidence-reading tool is otherwise unbounded until compaction |
| `glob` ≤ 60 results, `grep` ≤ 120 matches | `tool-fs-search.globMaxResults` / `grepMaxMatches` (defaults 100 / 250) | ≈ 40–52 % fewer search-result bytes | exploration fan-out returns pages, not dumps |
| `blockedAfterConsecutiveRounds: 3` | `tool-goal.blockedAfterConsecutiveRounds` (default 3) | correctness pin, ≈ 0 tokens saved directly | makes the documented blocked rule explicit instead of a host default |
| Instructions ≤ 8,192 bytes, `AGENTS.md` only | `agent-instructions.maxBytes` / `instructionFileCandidates` / `localInstructionFileCandidates` (were 65,536 and the default candidate list) | worst case 64 KiB ≈ 16 k tokens injected into **all eight** members; typical 0 with no large repo guide | bounds a research repo's agent guide; drops `CLAUDE*` variant duplication |

Each limit is a row config in `agent-presets/rigorquant.patch.yml`; none needs
plugin code. Their combined always-on effect is small (≈ 0.3–0.5 k tokens per
request), which is the honest finding: the interesting savings are per-result
and per-compaction, not in the catalog.

## Deferred — measure on a real study first

| Follow-up | Native mechanism | Estimated saving (ESTIMATE) | Why deferred |
|---|---|---|---|
| Compaction right-sizing | `compaction-basic.thresholdRatio`, `retainTokens` | `0.6 → 0.32` + `retainTokens: 32768` on a 1 M-token window: trigger ≈ 600 k → ≈ 320 k, verbatim tail ≈ 154 k → 32 k → **≈ 280 k–430 k fewer input tokens per request after the first compaction** | the largest win, but earlier/cheaper compaction can summarize away a detail a checker needed; requires an A/B on one real study with re-derivation rounds counted |
| Spill cap tightening | `spill-policy.maxInlineTokens` (host value 12,500) | ≈ −6.5 k tokens per oversized non-read result; heavy validation rounds produce 1–4 | needs a probe of the host-then-preset policy ordering; `read` is skipped by the policy, so read-back by locator still works |
| `SKILL.md` slimmed by progressive disclosure | none — content migration onto the host's on-demand resource loading | 34,928 B → ≈ 12–14 KB: **≈ −5 k tokens on every request after the load** | moves prose that repo-consistency tests pin; must move the pinned phrases with it |
| Root-persona slimming | none — authored text in the `dsh-persona` row | 3.8 KB → ≈ 2.6 KB: **≈ −300 tokens per Lead request** | load-bearing for an unattended run; must land together with the skill migration so the moved text has a home |
| PTC presentation | `agent-tool-presentation.mode: ptc` per preset | transcript **−30–60 %**, catalog −1.5–2 k tokens — but the SDK text is itself always-on | rewrites the whole operating procedure; Team tools inside a program are untested; needs a spike preset, not the cutover |

## Rejected native mechanisms

| Native feature in 0.2.1 | Why rejected |
|---|---|
| Native schedule (`dsh-tool-schedule`, four tools; host `dsh-schedule` service) | measured **1,492 tokens always-on**; it would only avoid idle polling or restart rounds across a session boundary, which is exactly what the unattended contract forbids (crossing a session boundary disarms the goal) |
| Session search (`dsh-tool-session-query`, `dsh-experimental-session-search`) | ≈ **993 tokens** of schemas plus fixed guidance; this framework's cross-round memory is deliberately file-based (`journal.md`, `registry.json`), not session history |
| Hooks / webhooks (`dsh-hook-protocol`, `dsh-hooks-claude-code`, `dsh-hooks-codex`, `dsh-webhook*`) | not shipped in 0.2.1 at all — nothing to adopt |
| Workflow-script fan-out (`tool-workflow`, `workflow-ptc`) and ralph | unchanged in 0.2.1: neither gives a child a per-role persona or tool budget, so the untagged-child problem that disabled them stands |
| Classic subagent fork (`subagent_fork`, `tool-subagent-control`) | fork inherits the Lead conversation, breaking the producer ≠ checker isolation that is the only harness-enforced wall; fresh spawn loses the roster, board and `wait_agent` durability the round loop needs |
| Native terminal (`dsh-tool-terminal`, five tools) | measured ≈ **671 tokens** always-on; bash plus background jobs already cover the compute lane, and the uv lane is invoked non-interactively |
| `working_directory` for teammates | ≈ 90 tokens and no saving in this absolute-path workflow; it also breaks the teammate scratch-directory contract, so it is denied rather than adopted |
| Token-meter / telemetry exposure | host-plane projections already serve the UI; no model tokens to save |

## Already native — no change needed

The declared preset, the persona prefix/suffix split, skills progressive
disclosure, the compaction group isolation plus tool-result pruner, the timed
`ask_user_question`, the goal tools and the host round driver, `present`,
background jobs, manifest display metadata (locale + icon), the
`configForms`-backed routing card, the `rq_escalate` MCP lane, the Agent Teams
composition, and the token meter are already the host's native mechanisms for
their jobs. 0.8.0 adds no custom replacement for any of them.

## Verification

Every adopted limit is probe-validated on the 0.2.1-rc.2 host (27 preset rows,
0 hard failures) and pinned by a repo test, so a future host default cannot
silently move it. The deferred items have no test pin on purpose: they are
proposals until a measured study says otherwise, and landing them means
adding the pin together with the measured result.
