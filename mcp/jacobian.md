# jacobian escalation lane

[jacobian](https://github.com/morluto/jacobian) (MIT, pre-stable 0.12.0) is an
MCP server giving agents exact, independently-verified mathematics: SymPy,
NetworkX, Z3, Python-FLINT, cvc5 backends, SAT/SMT proof artifacts, and a
pinned-Lean formal-check lane. Its model is "a producer cannot certify its own
output" — the same principle as this framework's track split.

## Wiring — opt-in, not mount-time

The `mcp-jacobian` row is **disabled by default** and must be enabled in the
composition before use. This is deliberate: the MCP client connects during
preset activation, so an enabled row would run its command on every mount. The
row spawns a **pinned** launcher:

```text
npx -y jacobian@0.12.0 mcp
```

`serverName` is `rigorquant-jacobian`, so the model sees
`mcp__rigorquant-jacobian__math_find` and `mcp__rigorquant-jacobian__math_run`.

To enable the lane: remove `disabled: true` from the `mcp-jacobian` row in
`agent.cordis.yml` and restart the session.

## Install — explicit, one-time

The runtime is installed on first escalation, **after the user approves** (the
framework asks first; it is not automatic). It is a one-time setup:

```sh
npx -y jacobian@0.12.0 upgrade       # install the pinned Python runtime (~160 MB)
npx -y jacobian@0.12.0 doctor --json # verify: handshake ok, math.find + math.run
```

`jacobian setup` is for jacobian's own client targets (claude, cursor,
opencode, codex, gemini) and refuses without one — DSH is not one of them,
because this preset's `mcp-jacobian` row already IS the DSH client config.

Requires Node 18+ and CPython 3.12/3.13 (or `uv`).

## Lean lane (lean.check) — approval-gated provisioning

`<skill-dir>` below is the directory containing the rigorquant `SKILL.md` —
under a preset install that is
`$DSH_HOME/.agent-presets/rigorquant/skills/rigorquant`. A repo-relative path
does not resolve once the preset is installed.

The Lean lane is provisioned on demand, but **never unattended**: the framework
asks the user before running the bundled script, then runs it with the approval
gate set:

```sh
RQ_ALLOW_PROVISION=1 bash <skill-dir>/scripts/provision-lean.sh
```

It installs elan + the pinned toolchain (`leanprover/lean4:v4.31.0`), and
builds jacobian's pinned Mathlib runtime at `~/.local/share/jacobian/lean`
(the preset's `mcp-jacobian` row exports `JACOBIAN_LEAN_RUNTIME` there and
appends `~/.elan/bin` to the lane's child PATH, so the toolchain resolves at
call time with no dsh restart). It does **not** mutate shell rc files unless
`RQ_MODIFY_SHELL_RC=1` is also set. First run takes minutes (`lake update`
pulls Mathlib's prebuilt olean cache); it is safe to re-run.
`LEAN_TOOLCHAIN`/`JACOBIAN_TAG` env overrides re-pin the script if jacobian's
versions move. Keep the two versions in sync with the pinned MCP row:
`jacobian@0.12.0` ↔ `JACOBIAN_TAG=jacobian-v0.12.0`.

What each lane needs:

- `lean.statement.propose`, `lean.statement.compare`,
  `lean.proof_state.inspect` — pinned toolchain only.
- `lean.check` (CORE profile) — pinned toolchain.
- `lean.check` (MATHLIB profile) — toolchain + Mathlib runtime.

The manual commands the script wraps (for reference): elan-init install,
`elan toolchain install leanprover/lean4:v4.31.0`, then download the 5-file
Lean project from `morluto/jacobian` at the installed version tag and
`lake update && lake build`.

## What the model sees

- `mcp__rigorquant-jacobian__math_find` — discover typed operations in the active catalog
- `mcp__rigorquant-jacobian__math_run` — execute one selected operation (exact results)

Use for escalation claims: exact symbolic identities, SAT/SMT feasibility and
proof artifacts, convexity certificates, and its `verify` lanes. Before
claiming coverage read `operation://catalog` — the catalog, not marketing,
decides what it can check. Keep it as the ESCALATION lane: the default gate is
the local check battery; jacobian fires when correctness hinges on an unproven
claim (see the `rigorquant` skill's references/escalation.md).
