# Upgrade study: DSH v0.1.2-alpha.1

Companion to the release study task. Target:
[`deepseek-ai/deepseek-harness` releases](https://github.com/deepseek-ai/deepseek-harness/releases),
release **`dsh-v0.1.2-alpha.1`** (2026-08-27). The dev environment currently runs
**0.1.1-rc.2**.

Method: shallow-cloned the `dsh-v0.1.2-alpha.1` tag and verified every Host
event, Host service, Client slot, Client service, and settings seam that
`dsh-rigorquant` actually calls against the 0.1.2 source, instead of trusting
the release notes.

---

## 1. Incompatibilities to fix

### Verdict: the existing API surface is compatible, but the upgraded preset now requires DSH ≥ 0.1.2-alpha.1.

The 0.1.2 release notes call out several *breaking* changes upstream, and none
of them touches what this distribution uses. The implementation does consume
one new 0.1.2 schema field (`agentOptions.reasoningEffort`), so an older DSH
must be rejected rather than allowed to install a preset that cannot mount:

| 0.1.2 breaking change (notes) | Impact on dsh-rigorquant |
|---|---|
| Old `ApiProxy` interface removed; use `@Remote` gateway | None — this repo never used `apiProxy`. Router/interop is via `agent/request` events only. |
| Conversation-view code split into focused modules | None — host plugins listen to events; the `dsh/client.js` card binds to slots/services, not internal UI modules. |
| Apps now launched through `dsh` profiles (Python SDK, ACP) | None — the compute lane (`env/`) is a standalone uv venv, not the DSH Python SDK. |
| One-time token in launch URL for network web access | None — access is local `127.0.0.1`; no network-URL workflow in README/docs. |
| "Code Mode" renamed to "PTC mode" | None — this repo uses `dsh-plan-mode`, unrelated. |
| `agentOptions.reasoningEffort` added to `dsh-tool-subagent` | **Required floor:** the upgraded preset now uses this field for oracle/adversary native defaults; the installer rejects DSH < 0.1.2-alpha.1. |
| Public WebFetch enabled by default (SSRF-guarded, no per-request approval) | **Behavior change, not a break** — this repo already uses the builtin `dsh-tool-web`; the change only relaxes gating. |

### Verified-compatible surface (checked against `dsh-v0.1.2-alpha.1` source)

Everything below still exists in 0.1.2 with the same contract the code relies on:

**`dsh/index.js` (rq-model-router)**
- `agent/request` waterfall — still emitted in `packages/core/agent-loop/src/agent.ts:476-482`, resolves to `LlmCallConfig { provider, model, reasoningEffort, ... }`.
- `agent/request-error` waterfall — `agent.ts:390-405`; payload still `{ turn, step, provider, failure, retryPolicy, signal }`; `failure.code`/`failure.status` present (used in `routeFatal`).
- `agent-preset/selected(sessionId, agentPreset)`, `session/event`, `session/disposed`, `agent/disposed` — all present (`packages/preset/agent-presets/src/index.ts:285-286` and core session).
- `settings.register(NS, schema, { base, applies: 'live' })` — unchanged service;
  `settings.describe()` still exposes detached raw `user` layers, and
  `settings/document-updated` still signals edits/resets (the native-default
  overlay uses both).

**`dsh/client.js` (settings card)**
- `settings.plugin.item` slot, `settings.plugins.tab` — present (`packages/client/ui-settings-plugins/src/client/index.ts`).
- `settingsSchema.rehydrate` service — present (`packages/client/ui-settings/src/client/schema.ts:50`).
- `locale.register(NS, { zh, en })` — present (`packages/client/locale/src/client/index.ts:368`).
- Already dual-versioned for `>= 0.1.1-rc.2` (both 0.1.1-rc.2 and 0.1.2-alpha.1 ship the `rehydrate` name) — no change needed.

**`dsh/activity.js` (rq-activity)**
- `webServer` internal service + `internal/service` event — present; `register({ path, ... })` used by webhook and client modules.
- `agents` registry (`list()`/`get(id).status`), `agent/created`, `agent/status { agent, status }`, `agentPresets.composedPreset`, `sessions`, `sessionTitle`.
- Client floater geometry: `shell.overlay` list slot and `[data-shell-overlay]` (`packages/client/ui-layout/src/client/AppFrame.tsx:210-211`) and `[data-phase='active']` must still exist — **verified present** in 0.1.2.

> Implementation: the preset now uses native `agentOptions` for its fixed-tier
> oracle/adversary primaries, while the router remains the live override and
> fallback overlay. `README.md`, `README.zh-CN.md`, and `install.sh` now pin and
> enforce DSH >= 0.1.2-alpha.1; the direct `dsh plugin add` path documents the
> same preflight because it does not invoke `install.sh`. The new host probe plus
> the existing activity, client-bundle, preset-sync, and consistency tests are
> the smoke check.

---

## 2. New builtin features to utilize (stop reinventing the wheel)

### 2.1 ★ Subagent model selection

> Correction to an earlier reading: `agentOptions` is **not** new in 0.1.2. The
> runtime we already run (0.1.1-rc.2) has `@deepseek-ai/dsh-tool-subagent`
> `agentOptions: { provider, model, maxTokens }`, and it already flows to the
> child (`packages/subagent/tool-subagent/src/index.ts:390` passes it into
> `ctx.subagents.start`). The per-role "which model" default was **already
> builtin** — this repo's `agent/request` rewrite + full Settings card reinvent
> it. 0.1.2 *extends* that builtin, it does not introduce it.

What **is** genuinely new in 0.1.2 (`packages/subagent/tool-subagent/src/model-selection.ts`,
`model-selection-settings.ts`, `model-selection-state.ts`, `list-models.ts`):

- **`agentOptions.reasoningEffort`** — the field that was missing before.
  `agentOptions` is now `{ provider, model, reasoningEffort, maxTokens }`.
  (`provider`/`model`/`maxTokens` already existed in 0.1.1-rc.2; only
  `reasoningEffort` is new.)
- **`modelSelectionSettings: true`** — opt into the Host-owned
  `subagent-model-selection` user setting (`{ enabled, allowedModels[] }`
  allow-list), so a caller/agent may choose provider+model *within
  authorization*; default **off**.
- Delegation model-request policy (`assertAllowedModelSelection`,
  `preflightChildLlmRoute`, `requestedAgentOptions`) — a requested route is
  validated against the allow-list before the child starts.
- A `list-models` tool so the model can enumerate the allowed routes.

**Implementation in this repository:**
1. `tool-subagent-ground-truth` and `tool-subagent-adversary` now declare
   `agentOptions.provider/model/reasoningEffort` in
   `agent-presets/rigorquant/agent.cordis.yml`. The router reads the raw settings
   user layer and leaves those native primary requests unchanged when there is
   no explicit override.
2. The router still owns what the builtin does not: live per-deployment primary
   overrides, one fallback per role, terminal-failure retry, and root-role
   handling. A static `agentOptions` model has no fallback, while enabling the
   builtin allow-list would let a caller choose a route and undermine the
   forced tier matrix, so `modelSelectionSettings` remains intentionally off.
3. The existing Settings card is now documented and worded as the explicit
   override/fallback surface rather than the source of the shipped primary.
   `maxTokens` remains omitted from the native defaults deliberately; the
   provider's own output ceiling is safer for proof-heavy reports.

The installer and both READMEs now enforce the 0.1.2 floor. `tests/router_probe.cjs`
proves native pass-through, explicit override, reset, fallback retry, and
restoration after fallback success.

### 2.2 Public WebFetch with SSRF protection, no per-request approval

Already uses the builtin `dsh-tool-web` (`fetch: true`). The 0.1.2 change
relaxes public fetches (no per-request approval, SSRF-guarded). Nothing to
build — but two notes:
- Re-confirm that removing per-request approval does not loosen the
  architectural "blind lane" policy; the per-role `deny: [web_search, web_fetch, …]`
  lists in `agent.cordis.yml` already firewall blind roles at the tool level,
  so the approval change does not widen isolation. Document this as the
  enforcement point.

### 2.3 Plugins can add provider sign-in controls to Models settings

New capability (`before`-style additions to the Models settings tab). Only
relevant if rigorquant wants to manage `deepseek-official` credentials from
inside its own card — currently out of scope, but worth a note so we do not
build a credential UI by hand later.

### 2.4 i18n of UI languages; exact token usage per answered message

- Third-party UI language support is builtin; rigorquant already ships
  `locale.register(NS, { zh, en })` — nothing reinvented, just stay aligned.
- Exact per-answer token usage is now shown in the conversation stream.
  Rigorquant does **not** maintain its own cost meter: `agent.cordis.yml`
  states the host-plane token meter is *consumed, never re-registered*, and
  `docs/architecture.md` "Cost" is budget policy (`max_cost_usd`), not a UI
  readout. So this is a builtin we already lean on, and the 0.1.2 display
  removes any remaining reason to build a custom token readout.

### 2.5 Headless stderr/stdout split

0.1.2 streams progress to stderr and keeps stdout to the final result in
headless runs. If any rigorquant script parses headless stdout today, verify it
now only sees the final result.

---

## Summary

- **Implemented incompatibility fix:** require and enforce DSH ≥ 0.1.2-alpha.1,
  because the preset now uses native `agentOptions.reasoningEffort`.
- **Implemented de-duplication:** native `agentOptions` owns fixed-tier primary
  defaults; the custom router only handles explicit live overrides, fallback
  retries, and root handling. Public WebFetch and per-answer token display
  remain builtin capabilities already consumed by the preset. The native
  `maxTokens` field remains available but intentionally unset rather than
  imposing an arbitrary proof-output cap.
