// Subagent identity — the one copy of the 0.2.2 tree reads.
//
// 0.2.2 removed the Agent Teams service's membership/roster API
// (`tryMembership`, `listMembers`): a member's identity is now its position
// in the live subagent tree. `subagents.rootOf` selects that tree's root
// (model-facing name `lead`); `subagents.namesOf` returns the member's
// model-facing name (`lead`, a `<role>-<n>` path, or a Session id for unnamed
// history). Both are synchronous and read the live tree, so a per-request
// router or a per-call guard decides at call time without an async catalog
// walk.
//
// One copy for the three readers — the router (a role per request), the team
// module (a persona and guard per agent), and the escalation lane (a
// teammate name to its live Agent) — so a future identity change is one edit
// and one failing test, never three copies drifting apart.
//
// `subagents` is optional at every call site: the helpers answer `undefined`
// instead of throwing, so a core that does not mount the service disarms the
// feature rather than failing a request or a tool call.

/**
 * One live agent's tree identity.
 * @param subagents - the `subagents` service, or undefined when absent.
 * @param agent - the exact live Agent.
 * @returns `{ root, name, isRoot }`, or `undefined` when the service is
 *   absent or the agent has no live tree owner (e.g. an externally resumed
 *   child missing its root).
 */
function identityOf(subagents, agent) {
  if (subagents === undefined || subagents === null) return undefined
  try {
    const root = subagents.rootOf(agent)
    const names = subagents.namesOf(agent)
    return { root, name: names.self, isRoot: root === agent }
  } catch {
    return undefined
  }
}

/**
 * The live roster: every registered agent's model-facing name and turn
 * status. `agents.list()` holds the live Agents (an idle teammate is
 * resident, an unloaded one simply absent), which is the same source the
 * harness's own `list_agents` uses for `running`/`inactive`. A name that is
 * not on the roster is left to the tool's own error.
 * @param subagents - the `subagents` service, or undefined when absent.
 * @param agents - the `agents` service, or undefined when absent.
 */
function liveRoster(subagents, agents) {
  const roster = []
  for (const member of agents?.list() ?? []) {
    try {
      const names = subagents.namesOf(member)
      roster.push({ name: names.self, status: member.status ?? 'inactive' })
    } catch {
      // An agent whose tree link is gone cannot be named; leave it off.
    }
  }
  return roster
}

/**
 * The live Agent a Lead's `rq_escalate({ teammate })` names: a live
 * descendant of THAT Lead's tree carrying the model-facing name. Filtering
 * by root keeps a same-named path in another Session's tree out of reach.
 * @param subagents - the `subagents` service, or undefined when absent.
 * @param agents - the `agents` service, or undefined when absent.
 * @param lead - the exact Lead agent the lane tool is registered on.
 * @param teammateName - the model-supplied teammate name.
 * @returns the live Agent, or `undefined` when no such live member exists.
 */
function teammateAgent(subagents, agents, lead, teammateName) {
  if (typeof teammateName !== 'string' || teammateName.length === 0) return undefined
  for (const member of agents?.list() ?? []) {
    const identity = identityOf(subagents, member)
    if (identity === undefined || identity.isRoot) continue
    if (identity.root?.id !== lead.id) continue
    if (identity.name === teammateName) return member
  }
  return undefined
}

export { identityOf, liveRoster, teammateAgent }
