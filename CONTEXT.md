# RigorQuant

The vocabulary of a RigorQuant study: an unattended, multi-agent piece of
empirical or computational mathematics run inside one DeepSeek Harness
session. Decisions live as numbered entries in `docs/architecture.md`; from
24 on each is also an ADR in `docs/adr/`.

## Language

### The work

**Study**:
The user's assignment — one question worked in one directory with the standard
layout, from Promise to Certify.
_Avoid_: task, rigorquant task, job, project

**Study goal**:
The single goal that keeps the orchestrator returning round after round until
the study reaches a lifecycle outcome.
_Avoid_: task-level goal

**Round**:
One pass of the orchestrator through the five moves.
_Avoid_: iteration, cycle, loop

**Move**:
Where a round is in the loop: Promise, Fan out, Ground-truth, Attack, Certify.
_Avoid_: stage, phase, step

**Stage**:
How far a claim's validity has been established: reference-case,
generalization, domain-scale.
_Avoid_: level, phase, move

**Track**:
One of the two independent lines of evidence on a claim: the method track
(open, may use existing results) and the ground-truth track (re-derived blind).
_Avoid_: lane (reserved for compute and literature lanes), branch

**Study record**:
The committed evidence of a study — `study.json`, registry, journal,
derivations, audits — and the only thing certification reads.
_Avoid_: board, coordination state, session history

### The team

**Orchestrator**:
The session's root agent, which runs the rounds and is the only member every
teammate talks to. DeepSeek Harness calls it the Lead.
_Avoid_: Lead (except when quoting harness mechanics), root, main agent

**Teammate**:
A role agent the orchestrator creates for one study's team; it lives for the
study and holds its name for life.
_Avoid_: subagent, child, worker, member

**Role**:
The job a teammate holds, which fixes its persona, tool budget and model tier:
Explorer, OffGridThinker, DoubleChecker, Adversary, Literature line, Literature
adversary, Document adversary.
_Avoid_: persona (that is what a role *has*), agent type

**Teammate name**:
The durable `<role>-<n>` name that identifies a teammate and carries its role.
_Avoid_: agent id, role tag

**Blind role**:
A role that sees no web, no skills and nobody's draft: OffGridThinker,
DoubleChecker.
_Avoid_: isolated role, sandboxed role

**Web-denied role**:
A role without web access: the blind roles plus the Adversary and Document
adversary.

**Hub-and-spoke**:
The team's topology: every message goes to or from the orchestrator; teammates
never talk to each other.
_Avoid_: mesh, peer messaging

**Brief**:
The message that hands a teammate an assignment — its first prompt or a later
message — naming the snapshot hash of anything it is to judge.
_Avoid_: prompt, instruction, follow-up

**Verdict**:
The structured PASS or NEEDS-EDITS outcome an audit ends with, bound to the
hash of the snapshot it judged.
_Avoid_: result, status, opinion

**Task**:
An item on the team's shared task board coordinating one piece of a round's
work; coordination, never evidence.
_Avoid_: ticket, todo, job, study (the assignment)
