# jacobian escalation lane

[jacobian](https://github.com/morluto/jacobian) (MIT, pre-stable 0.11.0) is an
MCP server giving agents exact, independently-verified mathematics: SymPy,
NetworkX, Z3, Python-FLINT, cvc5 backends, SAT/SMT proof artifacts, and a
pinned-Lean formal-check lane. Its model is "a producer cannot certify its own
output" — the same principle as this framework's walled tracks.

## Install

```sh
npx jacobian setup          # or: npm install -g jacobian && jacobian doctor
```

Requires Node 18+ and CPython 3.12/3.13 (or `uv`). Then enable the lane by
removing `disabled: true` from the `mcp-jacobian` row in
`agent-presets/rigorquant/agent.cordis.yml`.

## What the model sees

- `mcp__jacobian__math_find` — discover typed operations in the active catalog
- `mcp__jacobian__math_run` — execute one selected operation (exact results)

Use for escalation claims: exact symbolic identities, SAT/SMT feasibility and
proof artifacts, convexity certificates, and its `verify` lanes. Before
claiming coverage read `operation://catalog` — the catalog, not marketing,
decides what it can check. Keep it as the ESCALATION lane: the default gate is
the local check battery; jacobian fires when correctness hinges on an unproven
claim (see the `rigorquant` skill's references/escalation.md).
