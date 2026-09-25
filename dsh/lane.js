// RigorQuant escalation lane — the `rq_escalate` host tool.
//
// The jacobian MCP server is not a preset row any more (Decision 25,
// docs/adr/0002-declared-preset-on-dsh-0.1.7.md): a declared preset cannot
// be edited per study, and an enabled `@deepseek-ai/dsh-mcp-client` row would
// spawn jacobian on every mount. Instead the orchestrator calls `rq_escalate`
// when a claim meets the escalation trigger, and this module mounts one
// `dsh-mcp-client` instance into the target agent's own scope — the caller's,
// or a named teammate's. rc.2 announces the new tools on that agent's next
// request, so no restart is needed. Precedent: `browser-use-runtime/src/mcp.ts`
// at `dsh-v0.1.7-rc.2`, which mounts the same client per agent scope with
// `failOnStartupError: true`.
//
// The lane lives until the agent's scope is disposed; there is no off switch.
// A restart disposes it, and the skill tells the orchestrator to mount it
// again while the journal shows an escalation still open.
//
// The client package is loaded through the harness's own loader, which
// resolves specifiers from the profile, the same way the preset row that
// used to carry it did. This package never imports it.

import { join } from 'node:path'
import { homedir } from 'node:os'

export const ESCALATE_TOOL = 'rq_escalate'
const LANE_SERVER_NAME = 'rigorquant-jacobian'
const MCP_CLIENT = '@deepseek-ai/dsh-mcp-client'
const JACOBIAN = 'jacobian@0.12.0'

/** The install step a failed mount leads into; it still asks the user. */
const INSTALL_HINT =
  `Ask the user before installing: \`npx -y ${JACOBIAN} upgrade\`, then ` +
  `\`npx -y ${JACOBIAN} doctor --json\`, then call ${ESCALATE_TOOL} again ` +
  '(references/escalation.md).'

/**
 * The stdio server config for one jacobian lane. `JACOBIAN_LEAN_RUNTIME`
 * pins the Mathlib runtime `lean.check` needs (mcp/jacobian.md), and elan's
 * bin dir is appended to the child PATH so a toolchain provisioned mid-study
 * resolves at call time.
 * @param cwd - the target agent's working directory, when it has one.
 */
export function laneServerConfig(cwd) {
  const home = process.env.HOME || homedir()
  return {
    transport: 'stdio',
    serverName: LANE_SERVER_NAME,
    command: 'npx',
    args: ['-y', JACOBIAN, 'mcp'],
    env: {
      JACOBIAN_LEAN_RUNTIME: process.env.JACOBIAN_LEAN_RUNTIME || join(home, '.local', 'share', 'jacobian', 'lean'),
      PATH: `${process.env.PATH ?? ''}:${join(home, '.elan', 'bin')}`,
    },
    ...cwd === undefined ? {} : { cwd },
    toolCallTimeoutMs: 120_000,
    failOnStartupError: true,
  }
}

const OUTPUT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    target: { type: 'string' },
    status: { type: 'string', enum: ['mounted', 'already-mounted'] },
  },
  required: ['target', 'status'],
}

/**
 * Every agent's lane, mounted or in flight. It is module state, not plugin
 * state: the lane lives in the agent's scope and outlives an rq-team reload
 * (the Plugins-page toggle), and mounting a second client there would be
 * refused by name. Keyed weakly, so a disposed agent takes its entry along.
 */
const mounts = new WeakMap() // agent -> Promise<void>

/**
 * The mounter. Each agent gets at most one lane; a mount in flight is shared,
 * and a failed mount is forgotten so a retry after the install step starts
 * afresh.
 * @param ctx - the rq-team plugin context (for the loader).
 */
export function createLane(ctx) {

  const loadClient = async () => {
    const loader = ctx.get('loader')
    if (loader === undefined) throw new Error('the plugin loader is unavailable')
    return loader.unwrapExports(await loader.import(MCP_CLIENT))
  }

  const mountInto = async (agent) => {
    const client = await loadClient()
    const fiber = agent.ctx.plugin(client, client.Config(laneServerConfig(agent.session?.header?.cwd)))
    try {
      await fiber
    } catch (error) {
      await fiber.dispose?.()
      throw error
    }
  }

  /** @returns 'mounted' or 'already-mounted'; rejects when the lane cannot start. */
  const mount = async (agent) => {
    const existing = mounts.get(agent)
    if (existing !== undefined) {
      await existing
      return 'already-mounted'
    }
    const pending = mountInto(agent)
    mounts.set(agent, pending)
    try {
      await pending
    } catch (error) {
      mounts.delete(agent)
      throw error
    }
    return 'mounted'
  }

  return { mount }
}

/**
 * The `rq_escalate` tool definition for one Lead.
 * @param lane - the registry from {@link createLane}.
 * @param lead - the exact Lead agent the tool is registered on.
 * @param teams - the `agentTeams` service, for the roster read.
 * @param agents - the `agents` service, for the teammate's live agent.
 */
export function escalationTool(lane, lead, teams, agents) {
  const resolveTarget = (teammate) => {
    if (teammate === undefined) return { name: 'lead', agent: lead }
    const member = teams.listMembers(lead).find((row) => row.name === teammate && row.role === 'teammate')
    if (member === undefined) {
      throw new Error(`${ESCALATE_TOOL}: no teammate named '${teammate}' is on the roster`)
    }
    const agent = agents?.get(member.id)
    if (agent === undefined) {
      throw new Error(
        `${ESCALATE_TOOL}: teammate '${teammate}' is not loaded (${member.status}); ` +
        'grant the lane while it is running, or brief a new teammate and grant it then')
    }
    return { name: teammate, agent }
  }

  return {
    name: ESCALATE_TOOL,
    description:
      'Mount the jacobian escalation lane (exact computation and independent ' +
      `verification, tools mcp__${LANE_SERVER_NAME}__*) into your own scope, or ` +
      'into one named running teammate. The tools appear on that agent\'s next ' +
      'request and stay until the session ends. Idempotent per agent.',
    parameters: {
      type: 'object',
      properties: {
        teammate: {
          type: 'string',
          description: 'A running teammate to give the lane to, e.g. doublechecker-2. Omit to mount it for yourself.',
        },
      },
    },
    output: {
      schema: OUTPUT_SCHEMA,
      render: (_args, value) => [{
        type: 'text',
        text: value.status === 'mounted'
          ? `Escalation lane mounted for ${value.target}: the mcp__${LANE_SERVER_NAME}__* tools appear on its next request.`
          : `Escalation lane already mounted for ${value.target}.`,
      }],
    },
    async execute(args) {
      const teammate = args && typeof args === 'object' ? args.teammate : undefined
      if (teammate !== undefined && typeof teammate !== 'string') {
        throw new Error(`${ESCALATE_TOOL}: teammate must be a teammate name`)
      }
      const target = resolveTarget(teammate)
      try {
        return { target: target.name, status: await lane.mount(target.agent) }
      } catch (error) {
        const cause = error instanceof Error ? error.message : String(error)
        const detail = error instanceof Error && error.cause instanceof Error ? ` (${error.cause.message})` : ''
        throw new Error(
          `${ESCALATE_TOOL}: the jacobian lane failed to start for ${target.name}: ${cause}${detail}. ${INSTALL_HINT}`)
      }
    },
  }
}
