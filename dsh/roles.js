// The teammate role vocabulary the two host modules share.
//
// dsh/client.js's browser bundle carries its own copy: a classic <script>
// bundle structurally cannot import a Node module, so that surface owns its
// copy and the settings card pins it. These two are plain Node modules in one
// package, so they share this file (issue #50).

/** Every routable role, in card order. `root` is the Lead-only role. */
export const ROLES = ['root', 'explorer', 'offgrid', 'doublechecker', 'adversary', 'lit-line', 'lit-adversary', 'doc-adversary']
/** Every teammate role: `ROLES` minus the Lead-only `root`. */
export const TEAMMATE_ROLES = ROLES.filter((role) => role !== 'root')

/** Teammate name convention: `<role>-<suffix>`, e.g. `doublechecker-1`. */
const NAME_PATTERN = new RegExp(`^(${TEAMMATE_ROLES.join('|')})-.+$`)

/** Parse a teammate's role from its subagent-tree name, or `null` when it
 *  doesn't parse (an unparseable name should already have been refused at
 *  `subagent` by dsh/team.js's Lead guard; this is defense in depth, not the
 *  enforcement point). */
export function roleFromName(teammateName) {
  const match = typeof teammateName === 'string' ? NAME_PATTERN.exec(teammateName) : null
  return match !== null ? match[1] : null
}
