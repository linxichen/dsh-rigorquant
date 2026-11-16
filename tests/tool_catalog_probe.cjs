#!/usr/bin/env node
'use strict'
// Fail when the installed core ships a model-facing tool that RigorQuant has
// neither classified for a Teammate nor explicitly excluded.
//
// The specification's user story 24 asks for exactly this: isolation is
// enforced by structure, not by remembering. The team plugin's tier tables
// are an allow classification (`dsh/team.js`'s `TEAMMATE_ALLOW_BY_TIER`), so a
// tool the core newly mounts is invisible to a teammate — but nothing would
// tell a maintainer that a new tool exists and nobody decided about it. This
// probe reads the installed `@deepseek-ai/dsh` package's shipped
// `docs/tool-catalog.md` (a generated page whose "Tool Package Map" lists every
// model-visible name a shipped tool package contributes), enumerates those
// names, and requires each one to be in a tier or in the explicit exclusion
// table below with its reason.
//
// Exit codes follow ./harness_locator.cjs: 0 = every catalog tool decided,
// 1 = a real problem (an undecided or contradictory name), 2 = the installed
// core is refused, 3 = no harness to validate against. The Python side skips
// on 2 and 3 and never reads the wording.
//
// Input: argv[2] is the path to dsh/team.js (the classification under test).

const { readFileSync } = require('node:fs')
const { dirname, join } = require('node:path')
const { pathToFileURL } = require('node:url')

const {
  EXIT_PROBLEM, exitNoHarness, harnessRequireFor, requireSupportedCore, resolveHarness,
} = require('./harness_locator.cjs')

const PREFIX = 'tool_catalog_probe'
const CATALOG_PACKAGE = '@deepseek-ai/dsh'

/**
 * Model-facing tools the installed catalog names that RigorQuant deliberately
 * does not put in any Teammate tier. Each group is a decision with the section
 * of the record that makes it; a new catalog name missing here fails the probe
 * so the next maintainer decides rather than inherits a wider scope.
 */
const EXCLUDED = {
  'orchestrator-owned study state (Decisions 10 and 27)': [
    'working_directory', 'create_goal', 'update_goal', 'get_goal', 'todo_write',
    'ask_user_question', 'exit_plan_mode', 'propose_action',
  ],
  'roster, board listing and interruption (Decision 24)': [
    'list_agents', 'team_task_list', 'interrupt_agent',
  ],
  'delegation belongs to the Orchestrator alone (Decision 24)': [
    'subagent', 'subagent_oar', 'list_subagent_models',
  ],
  'operator host maintenance, not study work': [
    'plugin_manager', 'plugin_market', 'cordis_inspect_list', 'cordis_inspect_query',
    'create_worktree', 'load_workspace_dependencies',
  ],
  'session history: a teammate works from its brief, not earlier sessions': [
    'session_event_read', 'session_event_search', 'session_event_trace',
    'session_search', 'session_trace',
  ],
  'unattended scheduling is out of scope for 0.8.1 (issue #41)': [
    'schedule_create', 'schedule_edit', 'schedule_list', 'schedule_view',
  ],
  'interactive terminals: this preset composes one-shot bash and background jobs': [
    'terminal_close', 'terminal_list', 'terminal_open', 'terminal_read',
    'terminal_send', 'terminal_signal', 'user_terminal_list', 'user_terminal_read',
  ],
  'plugin-optional tool packages this distribution does not install for a study': [
    'apply_patch', 'str_replace_editor', 'lsp', 'ralph', 'workflow', 'run_code',
    'office_convert', 'office_recalculate', 'office_render',
    'stagehand_act', 'stagehand_extract', 'stagehand_navigate', 'stagehand_observe',
    'stagehand_screenshot', 'stagehand_tabs',
    'list_mcp_resource_templates', 'list_mcp_resources', 'read_mcp_resource',
  ],
}

/** A backticked model-visible tool name in the map's second column. */
const TOOL_NAME = /`([a-z][a-z0-9_]*)`/g
/** One row of the "Tool Package Map" table. */
const TABLE_ROW = /^\| `(@deepseek-ai\/[^`]+)` \| ([^|]*) \|/gm

/** The explicit exclusion table as one name → reason map (reasons are the
 * group keys); a duplicate across groups is itself a contradiction. */
function excludedReasons() {
  const reasons = new Map()
  for (const [reason, names] of Object.entries(EXCLUDED)) {
    for (const name of names) reasons.set(name, reason)
  }
  return reasons
}

/** Every model-visible tool name the installed catalog's map lists. */
function catalogNames(markdown) {
  const names = new Set()
  for (const row of markdown.matchAll(TABLE_ROW)) {
    for (const name of row[2].matchAll(TOOL_NAME)) names.add(name[1])
  }
  return [...names].sort()
}

/** The installed package's shipped catalog page, or a real failure: a core
 * this package supports ships the generated page, so its absence is not
 * "nothing to validate" but a broken claim about what the release reads. */
function installedCatalog(harnessRequire) {
  const manifest = harnessRequire.resolve(`${CATALOG_PACKAGE}/package.json`)
  const path = join(dirname(manifest), 'docs', 'tool-catalog.md')
  try {
    return { path, markdown: readFileSync(path, 'utf8') }
  } catch (error) {
    process.stderr.write(
      `${PREFIX}: cannot read the installed ${CATALOG_PACKAGE}'s shipped docs/tool-catalog.md`
      + ` (${String(error?.message ?? error)}); the classification cannot be audited\n`)
    process.exit(EXIT_PROBLEM)
  }
}

async function main() {
  const [, , modulePath] = process.argv
  const harness = resolveHarness(undefined)
  if (harness === undefined) {
    exitNoHarness(PREFIX, 'cannot locate an installed harness; there is no shipped tool catalog to audit')
  }
  const harnessRequire = harnessRequireFor(harness, PREFIX)
  const coreVersion = await requireSupportedCore(harnessRequire, PREFIX)
  const { path: catalogPath, markdown } = installedCatalog(harnessRequire)
  const catalog = catalogNames(markdown)
  if (catalog.length === 0) {
    process.stderr.write(`${PREFIX}: parsed no model-visible names from ${catalogPath};`
      + ' the shipped catalog format moved and this probe must be updated\n')
    process.exit(EXIT_PROBLEM)
  }

  const mod = await import(pathToFileURL(modulePath).href)
  const tiers = mod.TEAMMATE_ALLOW_BY_TIER
  if (tiers === undefined) {
    process.stderr.write(`${PREFIX}: dsh/team.js exports no TEAMMATE_ALLOW_BY_TIER\n`)
    process.exit(EXIT_PROBLEM)
  }
  const classified = [...new Set(Object.values(tiers).flat())].sort()
  const excluded = excludedReasons()

  const unclassified = catalog.filter((tool) => !classified.includes(tool) && !excluded.has(tool))
  const overlap = classified.filter((tool) => excluded.has(tool))
  const stale = classified.filter((tool) => !catalog.includes(tool))
  const unsupported = [...excluded.keys()].filter((tool) => !catalog.includes(tool))

  const problems = []
  if (unclassified.length > 0) {
    problems.push(
      `the installed core (${coreVersion}) names model-facing tools no classification decides: `
      + `${unclassified.join(', ')}; classify each in ${modulePath} for the Role tiers that may see it,`
      + ' or list it in the probe\'s EXCLUDED table with the decision that excludes it')
  }
  if (overlap.length > 0) {
    problems.push(`tools both classified and excluded: ${overlap.join(', ')}`)
  }
  if (stale.length > 0) {
    problems.push(`the classification names tools the installed catalog does not ship: ${stale.join(', ')}`)
  }
  if (unsupported.length > 0) {
    problems.push(`the exclusion table names tools the installed catalog does not ship: ${unsupported.join(', ')}`)
  }
  if (problems.length > 0) {
    process.stderr.write(problems.map((problem) => `${PREFIX}: ${problem}\n`).join(''))
  }

  process.stdout.write(JSON.stringify({
    coreVersion,
    catalogPath,
    catalogCount: catalog.length,
    classified,
    excluded: [...excluded.keys()].sort(),
    unclassified,
    overlap,
    stale,
  }))
  process.exit(problems.length === 0 ? 0 : EXIT_PROBLEM)
}

main().catch((error) => {
  process.stderr.write(`${PREFIX}: ${String(error?.stack ?? error)}\n`)
  process.exit(EXIT_PROBLEM)
})
