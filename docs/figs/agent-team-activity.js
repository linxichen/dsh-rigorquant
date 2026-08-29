// Builds docs/figs/agent-team-activity.svg — a self-contained reproduction of
// the dsh-agent-teams live activity panel (the picture in its README:
// https://github.com/NanmiCoder/dsh-agent-teams/blob/main/assets/ui.png),
// adapted to the RigorQuant research team.
//
// The role portraits from docs/figs/ are embedded as base64 data URIs so
// the one SVG file renders anywhere (GitHub, local browser) with no external
// references. To regenerate:
//
//   node docs/figs/agent-team-activity.js
//
// Design credit: activity-panel design adapted from dsh-agent-teams
// © NanmiCoder (程序员阿江 / Relakkes), MIT License. Portraits © RigorQuant
// docs/figs.
//
// No build step, no deps: plain Node string assembly. ESM on purpose — the
// repository is "type": "module"; run it with `node docs/figs/agent-team-activity.js`.

import fs from 'node:fs'
import path from 'node:path'

const HERE = path.dirname(new URL(import.meta.url).pathname)
const FIG = (name) => path.join(HERE, name)
const PNG = (name) => fs.readFileSync(FIG(name)).toString('base64')

// ---------------------------------------------------------------- palette
const C = {
  panel: '#0B1626',
  border: '#20334C',
  borderL2: '#2B4567',
  text: '#F4F8FF',
  text2: '#AFC4E0',
  text3: '#7F98BB',
  blue: '#4F8CFF',
  green: '#35D5A4',
  amber: '#F2BD62',
  node: '#101F33',
  track: '#14273F',
  pill: '#102642',
  pillBorder: '#315D91',
  pillText: '#BBD5FF',
  quota: '#5E7595',
  mono: 'Menlo, Consolas, monospace',
  sans: 'Helvetica Neue, Arial, sans-serif',
}

const esc = (text) => text
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')

/**
 * An avatar portrait cropped to its character. The doc PNGs carry the role
 * name/subtitle at their bottom edge; the image is drawn at its true aspect
 * ratio (square) inside a shorter clip box, so that label is cut off.
 */
function avatar(id, x, y, w, h, rx, png) {
  return [
    `<clipPath id="${id}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}"/></clipPath>`,
    `<image x="${x}" y="${y}" width="${w}" height="${w}" preserveAspectRatio="xMidYMid slice" ` +
      `clip-path="url(#${id})" href="data:image/png;base64,${png}"/>`,
  ].join('\n')
}

/** One member roster row starting at (16, top); the row is 50px tall. */
function memberRow(id, top, m) {
  const nameX = 84
  const nameY = top + 17
  const statusY = top + 33
  const toolX = nameX + 9 + 7.1 * m.name.length + 7
  return `
  <g>
    ${avatar(id, 16, top, 56, 42, 8, PNG(m.png))}
    <circle cx="${nameX}" cy="${nameY - 4}" r="3" fill="${m.busy ? C.blue : C.amber}"/>
    <text x="${nameX + 9}" y="${nameY}" font-family="${C.sans}" font-size="12.5" font-weight="600" fill="${C.text}">${esc(m.name)}</text>
    <text x="${toolX.toFixed(1)}" y="${nameY - 1}" font-family="${C.sans}" font-size="11" font-weight="400" fill="${C.text3}">· ${esc(m.tool)}</text>
    <text x="${nameX}" y="${statusY}" font-family="${C.sans}" font-size="11" fill="${C.text3}">${esc(m.status)}</text>
    <rect x="368" y="${top + 2}" width="40" height="18" rx="9" fill="${m.busy ? '#173A33' : '#16304F'}" stroke="${m.busy ? '#2E7368' : '#284D7C'}"/>
    <text x="388" y="${top + 14.5}" text-anchor="middle" font-family="${C.mono}" font-size="10.5" font-weight="600" fill="${m.busy ? '#9AE8CF' : '#9CC4FF'}">${esc(m.tag)}</text>
    <text x="408" y="${statusY}" text-anchor="end" font-family="${C.mono}" font-size="10.5" fill="${C.quota}">0/1</text>
  </g>`
}

/** One task-DAG node: mono TASK label + bold title. */
function dagNode(x, y, label, title, accent, titleFill) {
  return `
  <g>
    <rect x="${x}" y="${y}" width="118" height="48" rx="10" fill="${C.node}" stroke="${accent === C.green ? '#2E7368' : C.borderL2}"/>
    <circle cx="${x + 16}" cy="${y + 16}" r="4" fill="${accent}"/>
    <text x="${x + 26}" y="${y + 20}" font-family="${C.mono}" font-size="10" fill="${accent === C.green ? '#75B8AC' : C.text3}">${esc(label)}</text>
    <text x="${x + 12}" y="${y + 39}" font-family="${C.sans}" font-size="12.5" font-weight="700" fill="${titleFill}">${esc(title)}</text>
  </g>`
}

const arrow = (d) =>
  `<path d="${d}" fill="none" stroke="${C.blue}" stroke-width="1.6" marker-end="url(#arrow)"/>`

// -------------------------------------------------------- vertical layout
const HEADER_H = 45
const TEAM_H = 106
const PROG_H = 72
const MEMBER_ROW = 50

const membersHeadY = HEADER_H + TEAM_H + PROG_H + 6 // head text baseline
const membersTop = membersHeadY + 26 // first row avatar top

const MEMBERS = [
  { png: 'avatar-explorer.png', name: 'Explorer', tool: 'subagent', status: 'working · t2 — candidate methods, parallel batches', tag: 't2', busy: true },
  { png: 'avatar-literature.png', name: 'Literature', tool: 'subagent_lit_line', status: 'working · t2 — citation-graph sweep, both ways', tag: 't2', busy: true },
  { png: 'avatar-oracle.png', name: 'Oracle', tool: 'subagent_ground_truth', status: 'on standby · t3 — blind re-derivation, two ways', tag: 't3', busy: false },
  { png: 'avatar-adversary.png', name: 'Adversary', tool: 'subagent_adversary', status: 'on standby · t4 — battery + counterexamples', tag: 't4', busy: false },
  { png: 'avatar-document-adversary.png', name: 'Document', tool: 'subagent_document_adversary', status: 'on standby · t5 — self-completeness audit', tag: 't5', busy: false },
  { png: 'avatar-validator.png', name: 'Validator', tool: 'rq_check.py', status: 'on standby · t5 — evidence gate / PASS', tag: 't5', busy: false },
]

const membersSvg = MEMBERS.map((m, i) => {
  const row = membersTop + i * MEMBER_ROW
  const hairline = i === 0
    ? ''
    : `<line x1="16" y1="${row - 5}" x2="414" y2="${row - 5}" stroke="#16273E"/>`
  return hairline + memberRow(`ap${i}`, row, m)
}).join('\n')

const membersBottom = membersTop + MEMBERS.length * MEMBER_ROW
const dagHeadY = membersBottom + 14 // head text baseline
const dagTop = dagHeadY + 10 // svg top (nodes already padded inside)
const DAG_SVG_H = 172
const noteTop = dagTop + DAG_SVG_H + 8
const NOTE_H = 36
const footerTop = noteTop + NOTE_H + 10
const PANEL_H = footerTop + 42

const svg = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="430" height="${PANEL_H}" viewBox="0 0 430 ${PANEL_H}" role="img" aria-label="RigorQuant agent team activity view: team progress, member roster, and task dependency graph">
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
      <path d="M0 0L8 4L0 8Z" fill="${C.blue}"/>
    </marker>
    <linearGradient id="badgeGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${C.blue}"/>
      <stop offset="1" stop-color="${C.green}"/>
    </linearGradient>
  </defs>

  <!-- panel -->
  <rect x="0" y="0" width="430" height="${PANEL_H}" rx="14" fill="${C.panel}" stroke="${C.border}" stroke-width="1"/>

  <!-- header -->
  <rect x="16" y="14" width="18" height="18" rx="5" fill="url(#badgeGrad)"/>
  <text x="42" y="28" font-family="${C.sans}" font-size="15" font-weight="650" fill="${C.text}">RigorQuant Activity</text>
  <rect x="380" y="16" width="13" height="11" rx="2" fill="none" stroke="${C.text3}" stroke-width="1.4"/>
  <rect x="399" y="16" width="13" height="11" rx="2" fill="none" stroke="${C.text3}" stroke-width="1.4"/>
  <path d="M401.5 21.5h6" stroke="${C.text3}" stroke-width="1.6"/>
  <path d="M414 31l6-6" stroke="${C.text3}" stroke-width="1.6" fill="none"/>
  <line x1="0" y1="${HEADER_H}" x2="430" y2="${HEADER_H}" stroke="${C.border}"/>

  <!-- team card -->
  <text x="16" y="${HEADER_H + 26}" font-family="${C.sans}" font-size="16" font-weight="700" fill="${C.text}">rigorquant research lab</text>
  <text x="414" y="${HEADER_H + 25}" text-anchor="end" font-family="${C.sans}" font-size="11.5" fill="${C.text3}">7 members · 0/5 phases · 0 messages</text>
  <g>
    ${avatar('cap', 16, HEADER_H + 40, 76, 56, 10, PNG('avatar-orchestrator.png'))}
    <circle cx="106" cy="${HEADER_H + 48}" r="3" fill="${C.blue}"/>
    <text x="115" y="${HEADER_H + 52}" font-family="${C.sans}" font-size="13" font-weight="600" fill="${C.text}">CAPTAIN · Orchestrator</text>
    <text x="106" y="${HEADER_H + 71}" font-family="${C.sans}" font-size="11" fill="${C.text3}">root persona — dispatched 5 rounds to 7 members</text>
    <rect x="336" y="${HEADER_H + 38}" width="78" height="21" rx="10.5" fill="${C.pill}" stroke="${C.pillBorder}"/>
    <text x="375" y="${HEADER_H + 52}" text-anchor="middle" font-family="${C.sans}" font-size="11" font-weight="600" fill="${C.pillText}">2 in progress</text>
  </g>
  <line x1="0" y1="${HEADER_H + TEAM_H}" x2="430" y2="${HEADER_H + TEAM_H}" stroke="${C.border}"/>

  <!-- progress -->
  <text x="16" y="${HEADER_H + TEAM_H + 22}" font-family="${C.sans}" font-size="11.5" fill="${C.text2}">TOTAL PROGRESS</text>
  <text x="414" y="${HEADER_H + TEAM_H + 22}" text-anchor="end" font-family="${C.sans}" font-size="11.5" fill="${C.text3}">phase 0/5</text>
  <rect x="16" y="${HEADER_H + TEAM_H + 30}" width="398" height="8" rx="4" fill="${C.track}" stroke="#1C3250"/>
  <rect x="17" y="${HEADER_H + TEAM_H + 31}" width="148" height="6" rx="3" fill="${C.blue}"/>
  <rect x="167" y="${HEADER_H + TEAM_H + 31}" width="234" height="6" rx="3" fill="${C.amber}"/>
  <rect x="403" y="${HEADER_H + TEAM_H + 31}" width="10" height="6" rx="3" fill="${C.green}"/>
  <circle cx="23" cy="${HEADER_H + TEAM_H + 51}" r="3.5" fill="${C.blue}"/>
  <text x="31" y="${HEADER_H + TEAM_H + 55}" font-family="${C.sans}" font-size="11" fill="${C.text3}">in progress · 2</text>
  <circle cx="152" cy="${HEADER_H + TEAM_H + 51}" r="3.5" fill="${C.amber}"/>
  <text x="160" y="${HEADER_H + TEAM_H + 55}" font-family="${C.sans}" font-size="11" fill="${C.text3}">waiting · 3</text>
  <circle cx="282" cy="${HEADER_H + TEAM_H + 51}" r="3.5" fill="${C.green}"/>
  <text x="290" y="${HEADER_H + TEAM_H + 55}" font-family="${C.sans}" font-size="11" fill="${C.text3}">delivered · 0</text>

  <!-- members -->
  <text x="16" y="${membersHeadY}" font-family="${C.sans}" font-size="13" font-weight="650" fill="${C.text}">Members · 6</text>
  <text x="414" y="${membersHeadY}" text-anchor="end" font-family="${C.sans}" font-size="11" fill="${C.text3}">collapse</text>
  <path d="M390 ${membersHeadY - 7}l3.5 3.5 3.5 -3.5" fill="none" stroke="${C.text3}" stroke-width="1.4"/>
${membersSvg}

  <!-- task DAG -->
  <text x="16" y="${dagHeadY}" font-family="${C.sans}" font-size="13" font-weight="650" fill="${C.text}">Task dependencies</text>
  <text x="414" y="${dagHeadY}" text-anchor="end" font-family="${C.sans}" font-size="11" fill="${C.text3}">hover to highlight · click to pin</text>
  <g transform="translate(16, ${dagTop})">
    ${arrow('M118 40H139')}
    ${arrow('M257 40H278')}
    ${arrow('M298 64C298 88 187 88 187 118')}
    ${arrow('M187 142H238')}
    ${dagNode(0, 16, 'TASK t1', 'PROMISE', C.blue, C.text)}
    ${dagNode(139, 16, 'TASK t2', 'FAN OUT', C.blue, C.text)}
    ${dagNode(278, 16, 'TASK t3', 'GROUND TRUTH', C.blue, C.text)}
    ${dagNode(69, 118, 'TASK t4', 'ATTACK', C.blue, C.text)}
    ${dagNode(238, 118, 'TASK t5', 'CERTIFY', C.green, '#9AF0D9')}
  </g>

  <!-- selected-node note -->
  <rect x="16" y="${noteTop}" width="398" height="${NOTE_H}" rx="8" fill="#102A29" stroke="#2E7368"/>
  <text x="28" y="${noteTop + 14}" font-family="${C.sans}" font-size="10.5" fill="#9AD9C6">
    <tspan font-weight="600" fill="#CFF5E7">t3 GROUND TRUTH</tspan> · owner oracle · requires t2 (in progress) · unlocks t4 — two
  </text>
  <text x="28" y="${noteTop + 27}" font-family="${C.sans}" font-size="10.5" fill="#9AD9C6">independent re-derivations, then <tspan font-weight="600" fill="#CFF5E7">t5 CERTIFY</tspan> passes the validator gate.</text>

  <!-- footer -->
  <text x="215" y="${footerTop + 14}" text-anchor="middle" font-family="${C.sans}" font-size="10" fill="${C.quota}">Design adapted from dsh-agent-teams © NanmiCoder (MIT)</text>
  <text x="215" y="${footerTop + 27}" text-anchor="middle" font-family="${C.sans}" font-size="10" fill="${C.quota}">RigorQuant role portraits: docs/figs</text>
</svg>
`

fs.writeFileSync(FIG('agent-team-activity.svg'), `<!-- Generated by docs/figs/agent-team-activity.js — do not hand-edit -->
${svg}
`)
console.log(`wrote agent-team-activity.svg (${svg.length} bytes, panel ${PANEL_H}px tall)`)
