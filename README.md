# dsh-rigorquant

Unattended, long-running **empirical/computational mathematics research** for
[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) — economics,
finance, portfolio construction/optimization, simulation, computational
econ/finance.

RigorQuant is an agent preset + bundled skill that turns one DSH session into a
walled multi-agent research lab:

- **Parallel explorers** propose candidate methods (`subagent`, blank context).
- A **walled ground-truth track** re-derives the analytic closed forms,
  invariants, and bounds for simplified cases — twice, by different means.
- An **adversary** eliminates routes by counterexample only.
- A **four-part check battery** (closed-form equality, exact invariants,
  analytic bounds, statistical hardening) runs BEFORE numerical implementation.
- **Fixed-seed + LLN** conventions for stochastic work.
- A **jacobian MCP escalation lane** (and Lean as the last resort) settles
  proof-critical claims before implementation.
- **PASS → auto-implement and proceed; BLOCKED → 3 rounds of the same gap →
  strongest derivation + exact gap; BUDGET → 5 rounds → checkpoint + report.**

The operating pattern adapts Shanmu Jin's Crouzeix-conjecture run
([prompt](https://github.com/jinshanmu/CrouzeixConjecture/blob/main/crouzeix_conjecture_prompt.txt),
[Lean audit](https://github.com/jinshanmu/CrouzeixConjecture/tree/main/Lean))
and Terence Tao's blueprint/equational-theories projects to numerical work.
Full design record: [docs/architecture.md](docs/architecture.md).

## Install

```sh
git clone https://github.com/<you>/dsh-rigorquant
cd dsh-rigorquant
./install.sh                    # installs the RigorQuant preset into $DSH_HOME
# ./install.sh --skill-only     # or just the rigorquant skill, for any preset
```

Start a new DSH session and pick the **RigorQuant** preset. Then:

> rigorquant: derive and validate a method for [problem], simplified cases
> first, before any numerical implementation.

## Compute lane (one-time)

```sh
uv sync --project env            # creates env/uv.lock — commit it
```

The jacobian escalation lane is already wired and self-provisioning
(`npx -y jacobian mcp`). On first escalation the agent offers the one-time
runtime install (`npx -y jacobian upgrade`) for you — see
[mcp/jacobian.md](mcp/jacobian.md).

## Repository layout

```
agent-presets/rigorquant/   preset composition + persona + bundled skill
env/                        pinned uv compute lane (sympy/cvxpy/hypothesis/…)
mcp/jacobian.md             escalation lane wiring
docs/architecture.md        grilled decision record + sources
```

## Publishing

This repo is a community DSH plugin distribution (preset + skill form).
Tag it [`dsh-plugin`](https://github.com/topics/dsh-plugin) when publishing;
see [dsh-find-plugins](https://github.com/Nagi-ovo/dsh-find-plugins) and the
[awesome-deepseek-harness](https://github.com/0xsline/awesome-deepseek-harness)
list for the ecosystem conventions.

MIT License.
