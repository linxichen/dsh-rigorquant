"""Consistency between documents, and between a document and the filesystem.

docs/repository-review.md closed with the observation that every finding this
repository has ever produced came from a reader, not from anything executable,
and that the defect class is unenforced consistency between files. These are
those checks.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

from conftest import CORDIS, REPO, SKILL_DIR, composition_rows, is_disabled, top_level_rows

SKILL_SCRIPTS = ("rq_check.py", "provision-lean.sh")
ROUTER_PROBE = REPO / "tests/router_probe.cjs"


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line]


def docs():
    return [REPO / f for f in tracked_files()
            if f.endswith(".md") and not f.startswith("docs/repository-review")]


def test_exactly_one_validator_is_shipped():
    """Two copies of rq_check.py drifted into two different programs once."""
    copies = [f for f in tracked_files() if f.endswith("rq_check.py")]
    assert copies == ["agent-presets/rigorquant/skills/rigorquant/scripts/rq_check.py"], copies


def test_schemas_live_next_to_the_validator():
    """The validator loads ../schemas/ relative to itself; nothing else may."""
    schemas = [f for f in tracked_files() if f.endswith(".schema.json")]
    assert schemas, "no schemas tracked"
    for s in schemas:
        assert s.startswith("agent-presets/rigorquant/skills/rigorquant/schemas/"), s


def test_documented_skill_script_invocations_are_anchored():
    """A repo-relative script path resolves nowhere once the preset is installed.

    Only invocation lines are checked -- a layout listing may name a file
    without spelling out where to run it from.
    """
    offenders = []
    for doc in docs():
        for n, line in enumerate(doc.read_text().splitlines(), 1):
            for script in SKILL_SCRIPTS:
                if script not in line:
                    continue
                invocation = "--study" in line or line.lstrip().startswith(
                    ("python3", "bash", "RQ_ALLOW_PROVISION"))
                if not invocation:
                    continue
                if "<skill-dir>/scripts/%s" % script not in line and \
                        "<this skill's dir>/scripts/%s" % script not in line:
                    offenders.append("%s:%d: %s" % (doc.relative_to(REPO), n, line.strip()))
    assert not offenders, "un-anchored skill-script invocations:\n" + "\n".join(offenders)


def test_package_files_all_exist():
    manifest = json.loads((REPO / "package.json").read_text())
    missing = [entry for entry in manifest["files"]
               if not (REPO / entry.rstrip("/")).exists()]
    assert not missing, "package.json ships paths that do not exist: %s" % missing


def test_the_package_and_lane_version_stamps_agree():
    """A release bumps both stamps; the 0.4.1 release commit did it by hand.

    The lane stamp is what rq-preset-sync keys its replace-vs-keep decision
    on, so a release that bumps one stamp and not the other ships a preset
    the profiles keep stale (upgrade-0.1.6.md §3.7, finding 1).
    """
    manifest = json.loads((REPO / "package.json").read_text())
    stamp = re.search(r'^version = "([^"]+)"',
                      (REPO / "env" / "pyproject.toml").read_text(), re.M)
    assert stamp, "env/pyproject.toml states no version"
    assert stamp.group(1) == manifest["version"], (
        "package.json says %s but env/pyproject.toml says %s -- a release "
        "must bump both" % (manifest["version"], stamp.group(1)))


def test_install_script_installs_everything_the_runtime_needs():
    """The skill's scripts and schemas must survive a full install."""
    install = (REPO / "install.sh").read_text()
    for needed in ("agent-presets/rigorquant", "env", "mcp"):
        assert needed in install, "install.sh never installs %s" % needed
    assert "schemas" not in install or "agent-presets" in install


def test_native_agent_options_floor_is_declared_and_enforced():
    """The mount-time floor cannot be installed into an older DSH.

    The binding constraint is no longer `agentOptions.reasoningEffort`
    (0.1.2-alpha.1): 0.1.3-alpha.2 replaced the persona row's single `text` key
    with a required `prefix`, and a row whose config fails rejects the WHOLE
    preset mount. 0.1.6-alpha.2 is where the routing card's slot and the
    `deepseek-flash` fallback both hold — on 0.1.5 this release's card renders
    nothing, and its fallback lane has no model to route to.

    One floor, stated in six places: a reader who finds an older number in
    any of them learns the wrong minimum. `dsh/sync.js` is in the list
    because the bundle install path (`dsh plugin add`) runs it INSTEAD of
    `install.sh` and so never reaches the runtime check — that path can only
    state the floor, never enforce it.
    """
    floor = "0.1.6-alpha.2"
    install = (REPO / "install.sh").read_text()
    assert "MIN_DSH_VERSION=\"%s\"" % floor in install
    assert "version_at_least" in install
    stale = "0.1.5-alpha.2"
    for path in (REPO / "README.md", REPO / "README.zh-CN.md",
                 REPO / "agent-presets/rigorquant/agent.cordis.yml",
                 REPO / "dsh/sync.js"):
        text = path.read_text()
        assert floor in text, "%s omits the DSH floor" % path.name
        assert stale not in text, (
            "%s still states the superseded floor %s" % (path.name, stale))
    # The decision record is where a reader looks for WHY the floor moved, so
    # its own statement of the floor is pinned to the enforced one. Older
    # versions may appear there as history; this sentence may not.
    stated = re.findall(r"required floor is (?:now )?`DSH \u2265 (\S+?)`",
                        (REPO / "docs/architecture.md").read_text())
    assert stated == [floor], (
        "docs/architecture.md states the floor as %s; install.sh enforces %s"
        % (stated, floor))


def test_preset_persona_row_uses_the_prefix_suffix_split():
    """0.1.3-alpha.2 renamed the persona config; the old key is unmountable.

    `dsh-persona`'s schema requires `prefix` and knows nothing of `text`, so a
    preset still written with the single-text key fails validation and takes the
    entire mount down (not just the persona) — and discovery's health check only
    resolves module names, so the picker still shows it as healthy.
    """
    composition = (REPO / "agent-presets/rigorquant/agent.cordis.yml").read_text()
    assert "name: '@deepseek-ai/dsh-persona'" in composition
    assert "    prefix: >-" in composition
    assert "text: >-" not in composition
    # dsh/team.js (not dsh/index.js — the router stopped reading persona
    # sections in issue #11) writes a teammate's persona to this same slot.
    team = (REPO / "dsh/team.js").read_text()
    assert "const PERSONA_PREFIX_SECTION = 'deployment:persona-prefix'" in team


FLOOR = "0.1.6-alpha.2"


def _stub_dsh_env(tmp_path, version=FLOOR):
    """A `dsh` on PATH answering `--version`, and the env that finds it.

    Every `dsh` subcommand other than `--version` prints nothing and exits 0,
    which is what makes this a stub: `dsh plugin ... add` looks like it
    worked, so the installer takes its normal path without a real harness.
    Returns (env, dsh_home); dsh_home does not exist yet.
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_dsh = fake_bin / "dsh"
    fake_dsh.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then printf '%s\\n'; fi\n" % version
    )
    fake_dsh.chmod(0o755)
    dsh_home = tmp_path / "dsh-home"
    env = os.environ.copy()
    env["PATH"] = "%s:%s" % (fake_bin, env.get("PATH", ""))
    env["DSH_HOME"] = str(dsh_home)
    return env, dsh_home


def test_installer_rejects_an_older_dsh_before_copying_files(tmp_path):
    """A pre-0.1.6 CLI must not receive the preset at all.

    The stub answers with the PREVIOUS floor: the check has to reject the
    harness this release moved off, not merely some ancient tag.
    """
    env, dsh_home = _stub_dsh_env(tmp_path, version="0.1.5-alpha.2")
    result = subprocess.run(
        [str(REPO / "install.sh"), "--profile", "upgrade-test"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "requires dsh >= %s" % FLOOR in result.stderr
    assert not dsh_home.exists(), "the old runtime guard must run before copying"


def test_installer_accepts_the_minimum_dsh_version(tmp_path):
    """The prerelease floor itself is supported, not merely later stable tags."""
    env, dsh_home = _stub_dsh_env(tmp_path)
    result = subprocess.run(
        [str(REPO / "install.sh"), "--profile", "upgrade-test"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Installed preset" in result.stdout
    assert (dsh_home / ".agent-presets/rigorquant/agent.cordis.yml").is_file()


# ── the Agent Teams bundles: enabling, the cap override, uninstall ─────────
#
# 0.4.2 (the classic release) only detected the two optional bundles the
# harness ships as the Beta "Agent Teams" and "Agent Teams Web UI" cards.
# 0.5.0 runs team-only, so install.sh enables both and raises the team
# service's lifetime member cap under a marker in the profile's user patch
# (Decision 24, docs/adr/0001-rigorquant-on-agent-teams.md); the full
# enable/idempotent/uninstall/no-dsh coverage lives in
# tests/test_installer_agent_teams.py.


def test_the_cap_override_ships_in_the_bundle_patch_too():
    """Decision 24: the override rides along whichever route enables Teams.

    install.sh writes the override into the PROFILE's user patch; a profile
    that instead enables Agent Teams by bundle order alone (no ./install.sh
    run, e.g. a plugin-only install per Decision 22) still needs the raised
    cap once dsh-rigorquant is mounted after the Team layer, so the exact
    same row config is restated in this package's own bundle patch.
    """
    patch = (REPO / "cordis.patch.yml").read_text()
    assert "- id: agent-team" in patch, "cordis.patch.yml carries no agent-team override"
    tail = patch.split("- id: agent-team", 1)[1]
    for line in ("maxMembers: 64", "maxTasks: 256",
                 "maxPendingMessagesPerMember: 64", "maxMessageBytes: 65536",
                 "disposalTimeoutMs: 5000"):
        assert line in tail, "cordis.patch.yml's agent-team override omits %s" % line
    # A non-insert entry (no `insert:` key here) so cordis-plugin-include
    # replaces the row's `config` wholesale by id, rather than adding a
    # sibling row -- see install.sh's matching write for the same contract.
    assert "insert" not in patch.split("- id: agent-team", 1)[1].split("\n", 1)[0]


def test_architecture_record_matches_the_preset_composition():
    """Decision 8 once described `maxDepth: 0`, which blocks all delegation.

    Under Decision 24 no enabled row sets a depth at all: depth one holds
    by construction because no teammate can create teammates, and Decision 8
    must carry that amendment rather than a depth the preset no longer sets.
    """
    preset = CORDIS.read_text()
    numeric = [row_id for row_id, body in composition_rows(preset)
               if re.search(r"^\s*maxDepth:\s*\d", body, re.MULTILINE)
               and not is_disabled(body)]
    assert not numeric, "enabled rows still set a delegation depth: %s" % numeric
    arch = (REPO / "docs/architecture.md").read_text()
    d8 = arch[arch.index("8. **Multi-agent mechanism**"):arch.index("9. **Model routing**")]
    assert "Amended by Decision 24" in d8 and "by construction" in d8, (
        "Decision 8 does not record the Decision 24 amendment")


def test_installer_usage_states_the_floor_without_running_anything():
    """`--help` is the one screen that states the floor to a human.

    The usage text is an UNQUOTED heredoc, so a backtick in it is command
    substitution: the line naming the floor used to run `--skill-only` as a
    command, print "command not found" to stderr, and then state the floor
    with a hole where the flag should be.
    """
    result = subprocess.run(
        [str(REPO / "install.sh"), "--help"],
        cwd=REPO, capture_output=True, text=True, check=True,
    )
    assert result.stderr == "", (
        "install.sh --help writes to stderr: %r" % result.stderr)
    assert FLOOR in result.stdout
    assert "--skill-only does not" in result.stdout


def test_the_disabled_workflow_row_names_a_package_that_exists():
    """0.1.6 replaced the workflow engine; the old row can never resolve.

    `@deepseek-ai/dsh-workflow-worker-thread` is gone, renamed to
    `workflow-ptc`. A disabled row is never imported, so this is honesty
    rather than a mount fix — but the harness probe reports it UNRESOLVED and
    a reader cannot tell a deliberate stub from a typo. The row stays
    DISABLED for the reason it always was (untagged, unscopeable children);
    enabled and unresolvable it would be fatal, because discovery marks the
    whole preset "Failed to load" and the picker hides it.
    """
    composition = CORDIS.read_text()
    rows = dict(composition_rows(composition))
    assert "workflow-worker-thread" not in rows, (
        "the retired engine still has a row")
    assert "workflow-ptc" in rows, "no workflow row replaced the retired one"
    body = rows["workflow-ptc"]
    assert "name: '@deepseek-ai/dsh-workflow-ptc'" in body
    assert re.search(r"^\s+disabled: true\s*$", body, re.MULTILINE), (
        "workflow-ptc must stay disabled: it mints untagged children")
    assert "provider: spawn" in body
    # Prose may recount the rename; a `name:` key may not, because that is the
    # one occurrence the loader resolves.
    named = [line for line in composition.splitlines()
             if re.match(r"\s*name:", line) and "workflow-worker-thread" in line]
    assert not named, "a row still names the retired package: %s" % named


def test_disabled_external_agent_rows_track_the_shipped_background_mode():
    """The disabled rows are documentation; stale keys document a dead API.

    0.1.6's standard preset moved the external-agent rows from
    `enableRunInBackground: false` to `backgroundMode: one-shot`. Both keys
    still exist in `tool-subagent`'s Config, so nothing fails — which is
    exactly why a copy left on the old key drifts unnoticed until someone
    enables the row.
    """
    rows = dict(composition_rows(CORDIS.read_text()))
    for row_id in ("tool-subagent-codex", "tool-subagent-claude-code"):
        body = rows[row_id]
        assert "backgroundMode: one-shot" in body, (
            "%s does not carry the shipped background mode" % row_id)
        assert "enableRunInBackground" not in body, (
            "%s still carries the superseded key" % row_id)


def test_no_delegation_row_offers_caller_selectable_models():
    """Decision 16 routes models by ROLE, not by the caller's choice.

    0.1.6's standard preset turned `modelSelectionSettings` on for
    `tool-subagent`. RigorQuant keeps it off: a model the orchestrator picks
    per call would override the role's routed tier and the DoubleChecker
    could silently run on flash.
    """
    assert "modelSelectionSettings" not in CORDIS.read_text()


def test_the_procedure_states_the_live_children_pool_rule():
    """Fan-out is bounded by the host, and the bound has a retry trap.

    The host allows eight live children per root (`maxActiveSubagents`,
    default 8). Over that, a spawn throws `ACTIVATION_LIMIT_REACHED` — which
    reads like a transient error and is not one: nothing clears it but a
    child settling. An orchestrator that retries burns the budget on the
    error path, so both the step that fans out and the delegation discipline
    say to wait instead.
    """
    documents = (("SKILL.md", SKILL_DIR / "SKILL.md"),
                 ("protocol.md", SKILL_DIR / "references/protocol.md"))
    for name, path in documents:
        # Prose wraps; the rule is what is pinned, not the line breaks.
        text = " ".join(path.read_text().split())
        assert "maxActiveSubagents" in text, (
            "%s does not name the host setting that bounds fan-out" % name)
        assert "eight" in text, "%s does not state the pool size" % name
        assert "ACTIVATION_LIMIT_REACHED" in text, (
            "%s does not name the error the bound raises" % name)
        assert "never retry in a loop" in text, (
            "%s does not forbid retrying the activation limit" % name)


def test_every_document_that_names_the_pool_states_the_same_bound():
    """The number is the part that drifts, and it is now in five files.

    The same argument as the floor: a reader who finds "twelve" in the README
    and "eight" in the skill has learned nothing. Any tracked file naming the
    host setting has to state the bound, and the bound is one number.
    """
    offenders = []
    for name in tracked_files():
        path = REPO / name
        text = " ".join(path.read_text(errors="ignore").split())
        if "maxActiveSubagents" not in text:
            continue
        # Written as a word in prose, as a digit in the setting's default and
        # in the Chinese README's "8 个存活子代理".
        if "eight" not in text and not re.search(r"\b8\b", text):
            offenders.append(name)
    assert not offenders, (
        "these name maxActiveSubagents without stating the bound: %s"
        % offenders)


def test_deprecated_synchronous_history_reads_are_fully_migrated():
    """0.1.6 deprecated the synchronous session-event reads (`ownEvents()` /
    `snapshotEvents()`), upstream policy "existing logic may remain
    unmigrated for now, but new calls are prohibited".

    Issue #11 finished the migration on the router's side (role identity
    moved to the teammate name); dsh/activity.js — the classic activity
    monitor and the last caller, carrying the deferral note — is deleted
    outright under issue #13 (Phase 3). No tracked source file may read
    either accessor any more: the deferral note itself is now moot repo-wide,
    not just satisfied.
    """
    assert not (REPO / "dsh/activity.js").exists(), (
        "dsh/activity.js was deleted under issue #13; a regression here "
        "means it (or an equivalent) came back")
    offenders = []
    for name in tracked_files():
        if not name.endswith((".js", ".cjs")):
            continue
        source = (REPO / name).read_text()
        if re.search(r"session\??\.(?:ownEvents|snapshotEvents)\(", source) or "ownEventsOf" in source:
            offenders.append(name)
    assert not offenders, (
        "these files still read the deprecated synchronous session-event "
        "accessors, which have no caller left to justify the deferral: %s"
        % offenders)


def test_router_resolves_role_from_team_membership_only():
    """Issue #11: the router's only source of role identity is the team
    plugin's membership — never a persona tag, an assembled prompt, or a
    session event.

    A regression here would be a role silently resolving again from prompt
    text or history, exactly the drift Decision 24's "identity by name"
    retired.
    """
    router = (REPO / "dsh/index.js").read_text()
    assert "tryMembership" in router, (
        "dsh/index.js must resolve role through the team plugin's membership")
    assert "agentTeams" in router, (
        "dsh/index.js must reach the team service by its duck-typed name"
    )
    for gone in ("[[rq:role=", "TAG.exec", "systemPrompt.assemble", "PERSONA_SECTION"):
        assert gone not in router, (
            "dsh/index.js still names %r; role identity must come only from "
            "the Team membership name" % gone)


CLASSIC_ROWS = (
    "tool-subagent-control", "tool-subagent-list-agents", "tool-subagent-fork",
    "tool-subagent-explorer", "tool-subagent-offgrid",
    "tool-subagent-double-checker", "tool-subagent-adversary",
    "tool-subagent-lit-line", "tool-subagent-lit-adversary",
    "tool-subagent-doc-adversary",
)


def test_the_preset_carries_no_classic_delegation_rows():
    """Decision 24: team-only. The Team tools replace the legacy controls.

    `@deepseek-ai/dsh-experimental-tool-agent-team` registers `send_message`,
    `list_agents` and `interrupt_agent` under the legacy names, so a
    composition that keeps the classic control rows mounts two tools per
    name; and any enabled spawn row is a second, unguarded way to create a
    child. With none left, depth-one delegation holds by construction.
    """
    preset = CORDIS.read_text()
    rows = dict(composition_rows(preset))
    present = sorted(r for r in CLASSIC_ROWS if r in rows)
    assert not present, "classic delegation rows still in the preset: %s" % present
    for row_id, body in rows.items():
        if is_disabled(body):
            continue
        assert "dsh-tool-subagent" not in body, (
            "%s mounts a classic delegation tool" % row_id)
        assert "toolFilter" not in body and "persona: >-" not in body, (
            "%s still carries a role persona or tool filter; those live in "
            "dsh/personas/ and dsh/team.js now" % row_id)
    for gone in ("[[rq:role=", "agentOptions:"):
        assert gone not in preset, "the preset still carries %r" % gone


def test_the_kept_delegation_rows_stay_disabled_and_the_checker_lane_pinned():
    """What the classic cut keeps: external agents off, the checker lane off
    and pinned, and `present` on."""
    preset = CORDIS.read_text()
    rows = dict(composition_rows(preset))
    top = top_level_rows(preset)
    rows.update(top)
    for row_id in ("tool-subagent-codex", "tool-subagent-claude-code", "mcp-jacobian"):
        assert row_id in rows, "the preset lost %s" % row_id
        assert is_disabled(rows[row_id]), "%s must stay disabled" % row_id
    assert "jacobian@0.12.0" in rows["mcp-jacobian"], "the checker lane lost its pin"
    assert "present" in top, "the `present` row left the preset"
    assert not is_disabled(top["present"]), "the `present` row must stay on"


def _persona_prefix():
    preset = CORDIS.read_text()
    m = re.search(r"prefix: >-\n(.*?)\n    suffix:", preset, re.DOTALL)
    assert m, "the persona row lost its prefix"
    return " ".join(m.group(1).split())


def test_the_persona_isolation_paragraph_describes_the_team_mechanism():
    """Role by name, tool budget by scope, topology by guard — and still no
    network wall (Decision 24; the guard denies network verbs at the call,
    but context isolation remains the only wall)."""
    prefix = _persona_prefix()
    isolation = prefix[prefix.index("ISOLATION"):prefix.index("UNATTENDED")]
    for phrase in ("role by name", "tool budget by scope", "topology by guard",
                   "not a network wall"):
        assert phrase in isolation, "ISOLATION lost %r" % phrase
    assert "subagent_" not in prefix, "the persona still names a classic tool"


def test_the_persona_owns_the_team_request_and_the_armed_guard():
    """The Team policy creates teammates only on an explicit request; a study
    is that request — but only while the plugin's guard is armed."""
    prefix = _persona_prefix()
    assert "explicit request" in prefix
    assert "RigorQuant team guard: armed" in prefix, (
        "the persona must quote the exact line dsh/team.js registers")
    team = (REPO / "dsh/team.js").read_text()
    assert "GUARD_TEXT = 'RigorQuant team guard: armed'" in team
    assert re.search(r"absent[^.]*do not spawn", prefix, re.IGNORECASE), (
        "the persona must forbid spawning when the armed line is absent")


def test_the_persona_reads_a_spilled_result_back_by_its_locator():
    prefix = _persona_prefix()
    assert "spill" in prefix and "locator" in prefix and "re-run" in prefix


def _protocol():
    return " ".join((SKILL_DIR / "references/protocol.md").read_text().split())


def test_hard_lesson_l3_keeps_freeze_and_hash_and_adopts_the_brief_rule():
    """L3 as Decision 24 amends it: freeze-and-hash verbatim; the settled-agent
    rule becomes the new-brief rule; the native no-resend rule replaces the
    old discard rule."""
    text = _protocol()
    assert ("An artifact under adversarial review is read-only until the "
            "verdict lands, and the verdict records the audited snapshot's "
            "SHA-256.") in text, "L3 lost its freeze-and-hash half"
    assert ("a reused teammate only ever receives a new hash-bound brief, "
            "never a follow-up about an artifact under audit, and only while "
            "the roster shows it idle or inactive") in text.lower(), (
        "L3 lacks the new-brief rule")
    assert "if it is running, wait on it first" in text
    assert "a queued message is already stored; never resend it" in text
    for gone in ("discarded without action", "never message an in-flight",
                 "Do not send follow-up messages to a settled"):
        assert gone not in text, "L3 still carries the retired rule %r" % gone


def test_the_brief_contract_names_task_snapshot_and_role_only_description():
    text = _protocol()
    contract = text[text.index("Brief contract"):]
    for needle in ("task id", "snapshot", "SHA-256", "role label"):
        assert needle in contract, "the brief contract omits %r" % needle


def test_the_skill_round_loop_runs_on_the_team_tools():
    """SKILL Step 3: create / wait / message and the task DAG."""
    skill = (SKILL_DIR / "SKILL.md").read_text()
    step3 = " ".join(skill[skill.index("## Step 3"):skill.index("**Stage order")].split())
    for needle in ("spawn_teammate", "wait_agent", "send_message",
                   "team_task_create", "blocked_by", "`<role>-<n>`",
                   "list_agents", "BUDGET", "lifetime", "eight"):
        assert needle in step3, "SKILL Step 3 omits %r" % needle
    for gone in ("subagent_", "settled agent"):
        assert gone not in skill, "SKILL.md still names %r" % gone


def test_the_roster_policy_is_stated_once_and_consistently():
    """Fresh blank-context roles per brief; audit and literature roles reused
    by message, only while idle or inactive."""
    text = _protocol()
    policy = text[text.index("Roster policy"):]
    for fresh in ("explorer-<n>", "offgrid-<n>", "doublechecker-<n>"):
        assert fresh in policy[:policy.index("Reused across rounds")], (
            "%s is not listed as fresh per brief" % fresh)
    for reused in ("adversary-<n>", "lit-adversary-<n>", "doc-adversary-<n>", "lit-line-<n>"):
        assert reused in policy, "%s is not listed as reused" % reused
    assert "idle or inactive" in policy


def test_skill_text_uses_the_glossary_vocabulary():
    """CONTEXT.md: "study" is the assignment, "task" a board item, "move" the
    loop position, "stage" a validity stage."""
    skills = REPO / "agent-presets/rigorquant/skills"
    corpus = "\n".join(p.read_text() for p in skills.rglob("*.md"))
    flat = " ".join(corpus.split())
    for word in ("study", "task", "move", "stage"):
        assert re.search(r"\b%s\b" % word, flat), "the skill never says %r" % word
    for banned in ("rigorquant task", "five-move stage", "for the whole task"):
        assert banned not in flat.lower(), "skill text still says %r" % banned
    step3 = flat[flat.index("## Step 3"):flat.index("**Stage order")]
    for move in ("Promise", "Fan out", "Ground-truth", "Attack", "Certify"):
        assert move in step3, "Step 3 does not name the %s move" % move


def _section(text, heading, level=2):
    """The body of `heading`, up to the next heading of the same or higher level.

    A README claim is pinned by the section that carries it: a sentence that
    drifts into another section, or a section that keeps the old wording
    beside the new, is exactly the inconsistency this suite exists to catch.

    Headings are read OUTSIDE fenced code blocks. Both Install sections carry
    column-0 `# npx dsh-rigorquant ...` comment lines inside a shell fence, and
    a naive scan ends the section at the first of them -- pinning a prefix of
    the section and passing while the rest drifts unchecked.
    """
    lines = text.splitlines()
    start = None
    fenced = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if start is None:
            if re.match(r"^%s %s\b" % ("#" * level, re.escape(heading)), line):
                start = index + 1
        elif re.match(r"^#{1,%d} " % level, line):
            return "\n".join(lines[start:index])
    assert start is not None, "no %s heading %r" % ("#" * level, heading)
    return "\n".join(lines[start:])


def _pin_section_words(name, heading, words, level=2):
    """Every word must appear in `name`'s `heading` section, and return the body.

    One concept is stated in two languages: the Chinese and English sections
    are pinned by the same call shape so neither can be quietened alone.
    """
    body = _section((REPO / name).read_text(), heading, level=level)
    for word in words:
        assert word.lower() in body.lower(), (
            "%s's %r section never says %r" % (name, heading, word))
    return body


def test_tracked_documents_speak_the_glossary_vocabulary():
    """CONTEXT.md's two collisions, spelled out, may not come back (issue #15).

    A move is a loop position and a stage is one of a claim's validity stages,
    so "five-move stage" names one concept twice; a study is the assignment,
    so "rigorquant task" hands the board's word to the study's. The glossary
    is the one document allowed to spell both -- it lists them under
    `_Avoid_` -- so those lines are exempt; every other tracked document,
    English or Chinese, may not.

    Dated records are exempt the same way `docs/upgrade-*.md` is exempt from
    the retired-model pin: a released changelog entry, a point-in-time study
    and the repository review quote the vocabulary of their era, and editing
    them would falsify what was said then. The sweep therefore covers the
    documents that describe the system as it is now.
    """
    banned = (
        re.compile(r"five[- ]move\s+stage", re.IGNORECASE),
        re.compile(r"rigorquant\s+(?:task|任务)", re.IGNORECASE),
    )
    dated = re.compile(r"^(CHANGELOG\.md|docs/upgrade-[\d.]+\.md|docs/repository-review\.md)$")
    offenders = []
    for rel in tracked_files():
        if not rel.endswith((".md", ".html")) or dated.match(rel):
            continue
        try:
            text = (REPO / rel).read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("_Avoid_"):
                continue
            if any(pattern.search(line) for pattern in banned):
                offenders.append("%s:%d: %s" % (rel, number, line.strip()[:100]))
    assert not offenders, (
        "one concept, two names (CONTEXT.md is the arbiter):\n" + "\n".join(offenders))


def test_both_readmes_describe_the_team_through_the_native_surface():
    """Issue #15: what a reader of either README will actually see running.

    Issue #13 retired the custom activity panel for the harness's own team
    view, so the section that used to describe the `rq-activity` host half and
    its `shell.overlay` floater must describe the four native things a
    researcher looks at -- the roster and the task board in the session
    header, a teammate opened as an ordinary conversation, and the move pill
    -- and must keep the hub-and-spoke figure as the picture of the topology
    the per-call guards enforce. The retired implementation may not be named:
    not the host half, not the overlay slot, not the floater/悬浮件. The
    upstream *design* may still be credited -- the figure is adapted from it.
    """
    for name, heading, words in (
        ("README.md", "The team, live",
         ("roster", "task board", "move pill", "session header", "hub-and-spoke",
          "enforce", "docs/figs/agent-team-activity.svg")),
        ("README.zh-CN.md", "团队实时视图",
         ("花名册", "任务看板", "胶囊", "会话头部", "枢纽", "强制",
          "docs/figs/agent-team-activity.svg")),
    ):
        body = _pin_section_words(name, heading, words, level=3)
        for retired in ("rq-activity", "shell.overlay", "floater", "悬浮件", "悬浮条"):
            assert retired not in body, (
                "%s's team section still describes the retired %r" % (name, retired))


def test_both_readmes_install_sections_carry_the_beta_toggle_and_the_cap():
    """Issue #15: the Install section answers "what will this do to my profile".

    The floor is pinned elsewhere; what a reader cannot infer is that the
    Agent Teams bundles are the two Beta cards on the Plugins page under
    Official, that a full install turns them on and raises the lifetime member
    cap through a marked block in the profile's user patch, and that the whole
    release rests on an experimental bundle and an alpha harness.
    """
    for name, heading, words in (
        ("README.md", "Install", ("Beta", "Official", "cordis.patch.yml",
                                  "member cap to 64", "experimental",
                                  "0.1.6-alpha.2")),
        ("README.zh-CN.md", "安装", ("Beta", "官方", "cordis.patch.yml",
                                    "提高到 64", "实验性", "0.1.6-alpha.2")),
    ):
        _pin_section_words(name, heading, words)


def test_both_readmes_carry_the_deployment_notes():
    """Issue #15: three deployment facts, none of them this repo's machinery.

    The harness enables the DeepSeek session log by default, so a research
    deployment needs the row overlay that turns it off; the goal-round driver
    is host-mounted (the 0.1.5 study's "mount it" is superseded -- there is
    nothing to add); and the workspace-changes turn card is the human-visible
    witness of an edit after certification (Decision 19's frozen-write rule),
    while the validator keeps reading the study record rather than the session.
    """
    for name, heading in (("README.md", "Deployment notes"),
                          ("README.zh-CN.md", "部署须知")):
        _pin_section_words(name, heading, ("session-log-deepseek", "enabled: false",
                                           "goal-round-driver", "workspace-changes",
                                           "cordis.patch.yml"))


def test_agent_teams_geometry_attribution_keeps_the_upstream_mit_notice():
    notice = (REPO / "THIRD_PARTY_NOTICES").read_text()
    assert "dsh-agent-teams" in notice
    assert "Copyright (c) 2026 程序员阿江(Relakkes)" in notice
    assert "The above copyright notice and this permission notice" in notice


def test_effort_select_uses_the_models_real_supported_levels():
    """Only a model's real effort surfaces may be selectable — anywhere.

    A model with no reasoning metadata takes no explicit effort at all, so the
    card must not fall back to a generic [high, max] vocabulary there: that is
    how a route like zai/glm-5.3-flash got saved with an effort and every turn
    on it died in UNSUPPORTED_REASONING_EFFORT. Switching models must keep an
    effort only when the new surface lists it, and the host router must drop a
    stored effort the exact route refuses — falling back to the model's
    default level — because the LLM service rejects such a request before any
    provider I/O, so the failure never reaches agent/request-error.
    """
    client = (REPO / "dsh" / "client.js").read_text()
    # The catalog keeps each model's reasoning effort surface.
    assert "efforts: (model.reasoning?.efforts ?? [])" in client, (
        "the card drops model reasoning efforts instead of keeping them")
    # No generic vocabulary: a model with no surfaces offers "Default" only.
    assert "const EFFORTS" not in client, (
        "the hard-coded effort vocabulary must not come back")
    assert "const supported = efforts ?? []" in client
    # A stored effort the chosen model no longer lists stays visible but
    # disabled — honest display, never re-selectable.
    assert "const stale = stored !== ''" in client
    assert "disabled: true" in client
    # Switching models requires exact membership on the target surface.
    assert "targetEfforts.some((effort) => effort.id === choice?.reasoningEffort)" in client, (
        "switching models must discard an effort the new route does not list")
    # The host router consults the route's real effort metadata and demotes a
    # refused effort to the model default level.
    host = (REPO / "dsh" / "index.js").read_text()
    assert "resolveModelInfo" in host, (
        "the router must consult the model's real effort metadata")
    assert "falling back to the model default level" in host, (
        "the demotion must be diagnosable in the host log")


def test_team_guard_enforces_the_same_hub_and_spoke_the_pillbox_map_draws():
    """Decision 24 ("topology by guard"): the pillbox map is now a picture of
    what dsh/team.js's per-call guard actually enforces on the Team tools
    `tools.restrict` cannot mask. The one legal `send_message` target for
    every teammate must be the Lead, by the literal name the Team tool's own
    prompt teaches ('lead') — no other quoted string may ever appear as an
    allowed message target in the guard.
    """
    team = (REPO / "dsh" / "team.js").read_text()
    assert "tools.guard(" in team, (
        "dsh/team.js must register a per-call guard — tools.restrict cannot "
        "mask the scoped Team tools (send_message, list_agents, "
        "team_task_list, team_task_get, team_task_update, spawn_teammate)")
    hub_target = re.search(r"const LEAD_TARGET = '([a-z]+)'", team)
    assert hub_target, "the guard's one legal message target must be a named constant"
    assert hub_target.group(1) == "lead", (
        "hub-and-spoke's only legal send_message target must be the Lead")
    send_message_guard = re.search(
        r"execution\.name === 'send_message'.*?\n(.*?\n){0,4}", team)
    assert send_message_guard and "LEAD_TARGET" in send_message_guard.group(0), (
        "the send_message guard must gate on the one hub-and-spoke target "
        "constant, not a separately spelled-out condition")
    # Roster and board blindness are unconditional — no role tier may narrow
    # the deny set to fewer than these two scoped tools.
    assert "ROSTER_BLIND_TOOLS = new Set(['list_agents', 'team_task_list'])" in team, (
        "list_agents and team_task_list must be denied for every teammate, "
        "with no tier exception")


def test_router_native_defaults_overrides_and_fallback_round_trip():
    """The host router resolves roles by Team membership and routes the
    shipped tier matrix, a user override, and the fallback lane correctly."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the router probe")
    out = subprocess.run(
        [node, str(ROUTER_PROBE), str(REPO / "dsh/index.js")],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    verdict = json.loads(out.stdout)
    assert verdict["ok"] is True
    # The effort fallback must be exercised end to end: a stored effort the
    # exact route refuses is demoted to the model's default level (zai/
    # glm-5.3-flash is the deployment that died in UNSUPPORTED_REASONING_
    # EFFORT), and the demotion is diagnosable once per route.
    demotions = [line for line in verdict["logs"] if "falling back to the model default level" in line]
    assert any("zai/glm-5.3-flash does not support reasoning effort" in line for line in demotions), (
        "the probe no longer covers the refused-effort demotion")
    assert any("stub-provider/stub-model" in line for line in demotions), (
        "the passthrough route must be sanitized too")


def test_team_roles_pin_persona_files_the_name_regex_and_the_router_roles():
    """dsh/team.js's TEAMMATE_ROLES, dsh/personas/*.md, and dsh/index.js's
    ROLES (minus 'root') must name exactly the same seven roles.

    Drift in any one silently strands a teammate without composition (a
    role dsh/team.js doesn't know) or a persona file nobody reads (a role
    dsh/team.js knows but no file backs). This is also the router's own
    identity contract since issue #11: role resolution comes from the
    teammate NAME now, not a preset tag, so this name↔persona identity check
    is what pins the router's ROLES list correct (replacing the former
    tag↔row identity test against the preset's `[[rq:role=…]]` tags).
    """
    router = (REPO / "dsh" / "index.js").read_text()
    router_match = re.search(r"export const ROLES = \[([^\]]*)\]", router)
    assert router_match, "dsh/index.js no longer exports its ROLES list"
    router_roles = set(re.findall(r"'([a-z-]+)'", router_match.group(1))) - {"root"}

    team = (REPO / "dsh" / "team.js").read_text()
    team_match = re.search(r"export const TEAMMATE_ROLES = \[([^\]]*)\]", team)
    assert team_match, "dsh/team.js no longer exports TEAMMATE_ROLES"
    team_roles = set(re.findall(r"'([a-z-]+)'", team_match.group(1)))

    persona_dir = REPO / "dsh" / "personas"
    persona_roles = {p.stem for p in persona_dir.glob("*.md")}

    assert router_roles == team_roles == persona_roles, (
        "role drift: router=%s team=%s personas=%s"
        % (sorted(router_roles), sorted(team_roles), sorted(persona_roles)))

    for role in persona_roles:
        text = (persona_dir / f"{role}.md").read_text()
        assert text.lstrip().startswith(f"# Role: {role}"), (
            f"{role}.md must state its own role name up front")


def test_move_pill_role_badges_pin_the_same_seven_roles():
    """dsh/client.js's ROLE_BADGE is a fourth, browser-side copy of the same
    role set (the client bundle is standalone and cannot `require` the
    host-side dsh/team.js). A role dropped or added there without a matching
    update here would silently mislabel or drop a running teammate's badge
    on the move pill.
    """
    team = (REPO / "dsh" / "team.js").read_text()
    team_match = re.search(r"export const TEAMMATE_ROLES = \[([^\]]*)\]", team)
    assert team_match, "dsh/team.js no longer exports TEAMMATE_ROLES"
    team_roles = set(re.findall(r"'([a-z-]+)'", team_match.group(1)))

    client = (REPO / "dsh" / "client.js").read_text()
    badge_match = re.search(r"const ROLE_BADGE = \{(.*?)\n\}", client, re.DOTALL)
    assert badge_match, "dsh/client.js no longer declares ROLE_BADGE"
    badge_roles = set(re.findall(r"^\s*'?([a-z-]+)'?:\s*\[", badge_match.group(1), re.MULTILINE))

    assert badge_roles == team_roles, (
        "role drift: dsh/client.js's ROLE_BADGE=%s vs dsh/team.js's TEAMMATE_ROLES=%s"
        % (sorted(badge_roles), sorted(team_roles)))


def _shipped_route(slot):
    """The router's DEFAULT_<slot> route as (model, effort), read off dsh/index.js."""
    router = (REPO / "dsh/index.js").read_text()
    match = re.search(
        r"const DEFAULT_%s = Object\.freeze\(\{[^}]*"
        r"model:\s*'([^']+)'[^}]*reasoningEffort:\s*'([^']+)'" % slot,
        router,
    )
    assert match, "dsh/index.js no longer declares DEFAULT_%s" % slot
    return match.group(1), match.group(2)


def test_readme_routing_tables_carry_the_shipped_tier_matrix():
    """Both READMEs' routing tables repeat the router's DEFAULT_PRIMARY/FALLBACK.

    The fixed-tier rows (DoubleChecker, Adversary) end in "| `<primary>` @
    <effort> | `<fallback>` @ <effort> |". The cells are compared against the
    router constants, not literals, so a retarget cannot leave a README behind.
    """
    cells = "| `%s` @ %s | `%s` @ %s |" % (
        *_shipped_route("PRIMARY"), *_shipped_route("FALLBACK"))
    for path in (REPO / "README.md", REPO / "README.zh-CN.md"):
        rows = [line for line in path.read_text().splitlines()
                if re.match(r"\|\s*(DoubleChecker|Adversary|双重复核|对抗审计)\b", line)]
        assert len(rows) == 2, "%s lost a fixed-tier routing row" % path.name
        for row in rows:
            assert row.rstrip().endswith(cells), (
                "%s tier row must end in %s: %s" % (path.name, cells, row))


def test_no_shipped_file_names_the_retired_fallback_model():
    """The V4 Flash id left the default DeepSeek catalog in 0.1.6.

    Break B3 of the 0.1.6 upgrade study: an unlisted id fails only once the
    fallback lane is entered, so the miss is silent until a primary fails
    (Decision 16 records the shipped routes). The name may survive only where
    it is history — the upgrade studies. The id is assembled here so this file
    is not exempt from its own pin; the retired vision-exp id (same prefix,
    `-vision-exp` suffix) is a different model and not this pin's concern.
    """
    retired = re.compile(r"(?<![\w-])%s(?![\w-])" % "-".join(("deepseek", "v4", "flash")))
    history = re.compile(r"^docs/upgrade-[\d.]+\.md$")
    offenders = []
    for rel in tracked_files():
        if history.match(rel) or rel.endswith((".png", ".pdf", ".lock")):
            continue
        try:
            text = (REPO / rel).read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if retired.search(line):
                offenders.append("%s:%d: %s" % (rel, number, line.strip()[:100]))
    assert not offenders, "retired fallback model still named:\n" + "\n".join(offenders)


def test_bundle_patch_mounts_the_model_router():
    """The router rows travel with the dsh plugin add bundle."""
    patch = (REPO / "cordis.patch.yml").read_text()
    assert "rq-model-router" in patch, "cordis.patch.yml no longer mounts the model router"
    assert "name: 'dsh-rigorquant'" in patch or 'name: "dsh-rigorquant"' in patch, (
        "the router row must load this package (name: dsh-rigorquant)")


def test_every_role_has_a_description_and_frequency_in_both_locales():
    """The settings card explains each role and how often it is invoked.

    A role that loses its copy row renders an empty left column (the badge
    silently falls back to 'low'), which is exactly the drift this pins out.
    """
    import pathlib

    router = (pathlib.Path(__file__).resolve().parents[1] / "dsh" / "index.js").read_text()
    match = re.search(r"export const ROLES = \[([^\]]*)\]", router)
    assert match, "dsh/index.js no longer exports its ROLES list"
    roles = re.findall(r"'([a-z-]+)'", match.group(1))
    client = (REPO / "dsh" / "client.js").read_text()
    # Both locale sections of every copy block live inside the factory
    # closure: first the settings card (the one that carries role copy), then
    # the move pill. Each must be bilingual — a monolingual block is a
    # language that silently falls back to the other's strings.
    sections = re.findall(r"^\s{2}(en|zh): \{", client, re.MULTILINE)
    assert sections[:2] == ["en", "zh"], "the card copy sections moved; update this test"
    assert sections[2:] == ["en", "zh"], "the move-pill copy is not bilingual"
    vocabulary = {"en": {"Frequent", "Common", "Rare"}, "zh": {"频繁", "常见", "少见"}}
    for role in roles:
        for locale in ("en", "zh"):
            block = client[client.index(f"{locale}: {{"):]
            block = block[:block.index("\n  },")]
            for key in (f"'roleDesc.{role}':", f"'roleFreq.{role}':"):
                assert key in block, (
                    "client.js %s copy lacks %s for role %s" % (locale, key, role))
            label = re.search(r"'roleFreq\.%s': '([^']+)'" % role, block)
            assert label is not None, "roleFreq.%s missing in %s copy" % (role, locale)
            assert label.group(1) in vocabulary[locale], (
                "roleFreq.%s in %s copy is %r; expected one of %s"
                % (role, locale, label.group(1), sorted(vocabulary[locale])))


def test_no_document_claims_more_enforcement_tiers_than_it_lists():
    text = (SKILL_DIR / "references/deliverables.md").read_text()
    m = re.search(r"\*\*Enforcement at PASS \((\w+) tiers?\)\.\*\*(.*?)\n\n##", text, re.DOTALL)
    assert m, "the enforcement-tier block moved; update this test"
    words = {"one": 1, "two": 2, "three": 3, "four": 4}
    listed = len(re.findall(r"^- \*", m.group(2), re.MULTILINE))
    assert words[m.group(1)] == listed, (
        "deliverables.md announces %s tiers but lists %d" % (m.group(1), listed))


def test_every_reference_linked_from_the_skill_exists():
    text = (SKILL_DIR / "SKILL.md").read_text()
    for target in set(re.findall(r"\((references/[\w.-]+)\)", text)):
        assert (SKILL_DIR / target).exists(), "SKILL.md links missing %s" % target


def test_readme_layout_block_lists_only_real_paths():
    """A layout block that lists deleted directories is how drift starts."""
    readme = (REPO / "README.md").read_text()
    block = re.search(r"## Repository layout\n\n```\n(.*?)```", readme, re.DOTALL)
    assert block, "README repository-layout block moved; update this test"
    missing = []
    for line in block.group(1).splitlines():
        if not line[:1].strip():  # a wrapped continuation of the line above
            continue
        entry = line.split()[0]
        if entry == "studies/":  # documented as not shipped
            continue
        if not (REPO / entry.rstrip("/")).exists():
            missing.append(entry)
    assert not missing, "README lists paths that do not exist: %s" % missing


def test_lifecycle_schema_mirror_matches_the_shipped_schema():
    """lifecycle.md shows study.json by hand; the schema is what runs.

    The two disagreed on `broad_criterion`, `deliverables`, `validity_stages`
    and the sub-problem `stage` -- every study the skill mandated was invalid
    against the repo's own schema.
    """
    text = (SKILL_DIR / "references/lifecycle.md").read_text()
    mirror = re.search(r"## study\.json schema.*?```json\n(.*?)```", text, re.DOTALL)
    assert mirror, "the study.json mirror moved; update this test"
    documented = set(re.findall(r'^  "(\w+)":', mirror.group(1), re.MULTILINE))
    schema = json.loads((SKILL_DIR / "schemas/study.schema.json").read_text())
    allowed = set(schema["properties"])
    assert documented <= allowed, (
        "lifecycle.md documents fields the schema rejects: %s" % sorted(documented - allowed))
    assert set(schema["required"]) <= documented, (
        "the schema requires fields lifecycle.md never shows: %s"
        % sorted(set(schema["required"]) - documented))


def test_validator_does_not_carry_a_private_required_field_list():
    """Required fields belong to the schema. A second list is how they diverge."""
    source = (SKILL_DIR / "scripts/rq_check.py").read_text()
    assert "REQUIRED_STUDY_FIELDS" not in source


def test_no_study_specific_notation_is_hard_coded_in_the_validator():
    """Domain notation belongs in the audience spec, not in a general framework."""
    source = (SKILL_DIR / "scripts/rq_check.py").read_text()
    m = re.search(r"DEFAULT_SYMBOLS = \{(.*?)\n\}", source, re.DOTALL)
    assert m, "DEFAULT_SYMBOLS moved; update this test"
    for leaked in ("S^{d-1}", "Unif", "R/r", "subgradient"):
        assert leaked not in m.group(1), (
            "%r is convex-sampling notation; it belongs in an audience spec" % leaked)


def test_package_manifest_ships_the_test_suite():
    """The README documents pytest; the package must actually ship tests/."""
    manifest = json.loads((REPO / "package.json").read_text())
    assert "tests/" in manifest["files"], "package.json.files must include tests/"


def test_npm_ignore_excludes_python_bytecode():
    """Generated __pycache__/*.pyc must not leak into the npm artifact."""
    for n in (SKILL_DIR / "scripts" / ".npmignore", REPO / "tests" / ".npmignore"):
        assert n.exists(), "missing %s (bytecode would ship)" % n
        text = n.read_text()
        assert "__pycache__" in text and "*.pyc" in text


def test_no_document_calls_an_isolation_boundary_a_wall():
    """Decision 14: shipped text may not over-claim enforcement.

    Only web + delegation are tool-enforced; bash-curl and cross-lane filesystem
    reads are procedural. Every mention of the word must therefore be a denial.
    """
    negations = ("never", "not ", "no ", "n't")
    context = r"isolat|blind|enforce|procedural|separation|membrane"
    claims = ("bit-level isolation", "fully isolated", "sandboxed lane",
              "cannot reach the network")
    offenders = []
    for doc in docs() + [REPO / "agent-presets/rigorquant/agent.cordis.yml"]:
        # Paragraph scope: the denial routinely sits a line away from the word.
        for block in re.split(r"\n\s*\n", doc.read_text()):
            low = block.lower()
            if not re.search(context, low):
                continue
            if any(w in low for w in negations):
                continue
            hit = re.search(r"\bwalls?\b", low) or next(
                (c for c in claims if c in low), None)
            if hit:
                offenders.append("%s: %s" % (doc.relative_to(REPO),
                                             " ".join(block.split())[:120]))
    assert not offenders, "isolation over-claims:\n" + "\n".join(offenders)


def test_no_reference_to_a_docs_file_dangles():
    """A retired document must take its inbound references with it.

    Prose references (a docs path followed by a section number) outnumber
    markdown links here and are
    shipped inside skills and the composition, where a dangling path sends a
    model looking for a file that is not installed. Every `docs/` path with a
    known extension counts, not only `.md`: the READMEs point a reader at the
    figure generator, the ADR and the layout files the same way.
    """
    referenced = {}
    for rel in tracked_files():
        if rel.endswith((".png", ".pdf", ".lock")):
            continue
        try:
            text = (REPO / rel).read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for hit in re.findall(r"docs/[\w./-]*\.(?:md|html|js|svg|png|json|yml|yaml|tex|sh)", text):
            referenced.setdefault(hit, []).append(rel)
    missing = {t: sorted(set(src)) for t, src in referenced.items()
               if not (REPO / t).exists()}
    assert not missing, "references to documents that do not exist:\n" + "\n".join(
        "  %s <- %s" % (t, ", ".join(src)) for t, src in sorted(missing.items()))


def _decision_numbers():
    arch = (REPO / "docs/architecture.md").read_text()
    listed = set(re.findall(r"^\s*(\d+)\.\s+\*\*", arch, re.MULTILINE))
    headed = set(re.findall(r"^## Decision (\d+)", arch, re.MULTILINE))
    return listed | headed


def test_every_decision_reference_resolves():
    """A cited `Decision N` that architecture.md never records is drift.

    The Chinese README cites the same decisions in its own words -- `决策 N`
    and `第 N 条` -- so both forms are resolved, not just the English one; a
    translation that cites a clause nobody wrote is the same drift.
    """
    known = _decision_numbers()
    assert known, "architecture.md records no decisions; update this test"
    offenders = []
    sources = docs() + [REPO / f for f in tracked_files() if f.startswith("tests/")]
    for src in sources:
        for n, line in enumerate(src.read_text().splitlines(), 1):
            for num in re.findall(r"(?:[Dd]ecision|决策) (\d+)|第 (\d+) 条", line):
                num = num[0] or num[1]
                if num not in known:
                    offenders.append("%s:%d: Decision %s" % (src.relative_to(REPO), n, num))
    assert not offenders, (
        "references to decisions architecture.md never records:\n" + "\n".join(offenders))


def test_the_shipped_procedure_names_every_teammate_role():
    """A role nothing routes work to is enforcement no one can reach.

    `subagent_offgrid` once existed in the composition while every shipped
    procedure still told the orchestrator to re-use the open explorer under
    the novelty toggle — the role was unreachable by instruction. Under
    Teams the role is the teammate name, so the procedure must name each
    `<role>-<n>` it creates.
    """
    team = (REPO / "dsh/team.js").read_text()
    roles = re.findall(r"'([a-z-]+)'", re.search(
        r"export const TEAMMATE_ROLES = \[([^\]]*)\]", team).group(1))
    skills = REPO / "agent-presets/rigorquant/skills"
    corpus = "\n".join(p.read_text() for p in skills.rglob("*.md"))
    missing = [r for r in roles if "%s-<n>" % r not in corpus]
    assert not missing, (
        "the team composes roles no shipped skill instructs anyone to create: %s" % missing)


def test_schemas_are_valid_json():
    """A schema that does not parse breaks every study the gate loads it for."""
    for s in (SKILL_DIR / "schemas").glob("*.schema.json"):
        json.loads(s.read_text())  # raises on malformed JSON



def test_pre_commit_hook_enforces_95_percent_validator_coverage():
    """The validator is the honesty boundary; its coverage gate must be hard to weaken.

    rq_check.py runs only as a subprocess, so ordinary pytest-cov module
    selection measures the wrong process. The checked-in hook/CI contract is
    deliberately explicit: RQ_COVERAGE wraps each validator child in coverage
    run --parallel, combine merges the child files, then report applies 95%.
    Pin both the mechanics and the footgun guard -- `.coverage*` would delete
    .coveragerc before the report runs.
    """
    hook = REPO / ".githooks" / "pre-commit"
    assert hook.is_file() and os.access(hook, os.X_OK), (
        "missing executable .githooks/pre-commit coverage gate")
    text = hook.read_text()
    for required in ("RQ_COVERAGE=1", "UV_CACHE_DIR", "coverage combine",
                     "--fail-under=95", "rm -f .coverage .coverage.*"):
        assert required in text, "pre-commit hook lost %r" % required
    assert not re.search(r"^rm -f \.coverage\*$", text, re.MULTILINE), (
        "the broad cleanup glob deletes .coveragerc itself")

    coverage = (REPO / ".coveragerc").read_text()
    assert "parallel = true" in coverage
    assert "source = agent-presets/rigorquant/skills/rigorquant/scripts" in coverage

    lane = (REPO / "env" / "pyproject.toml").read_text()
    assert "coverage>=7.6,<8" in lane, "the pinned lane lacks coverage"
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    assert "RQ_COVERAGE=1" in ci and "--fail-under=95" in ci, (
        "CI must run the same coverage gate as pre-commit")
    install = (REPO / "install.sh").read_text()
    assert "core.hooksPath .githooks" in install, (
        "install.sh must activate the checked-in hook for git checkouts")


def test_install_script_installs_literature_skills():
    """Decision 15: arxiv + academic-paper-search ship to $DSH_HOME/skills/."""
    install = (REPO / "install.sh").read_text()
    for skill in ("arxiv", "academic-paper-search"):
        assert ('$DSH_HOME/skills/%s"' % skill) in install or \
               ('$DSH_HOME/skills/%s ' % skill) in install, \
               "install.sh never installs %s globally" % skill


def test_bundle_patch_keeps_the_skill_provider_off_default_roots():
    """The custom root must stay a custom root, because its RANK is the contract.

    dsh ranks a custom skill root at 300 and $DSH_HOME/skills at 400, and the
    lower rank wins a duplicate name. That is the only reason a machine which
    also ran ./install.sh resolves rigorquant, arxiv, and academic-paper-search
    to the copies shipped here rather than to whatever is in $DSH_HOME/skills.
    Letting this provider include the default roots would put both copies in
    one provider and make the winner registration order instead.
    """
    patch = (REPO / "cordis.patch.yml").read_text()
    assert "includeDefaultRoots: false" in patch, (
        "the rigorquant skill provider must not scan the default roots")


def test_bundle_patch_mounts_the_preset_sync_half():
    """Decision 22: the bundle self-installs the preset and the compute lane.

    The whole point of the rq-preset-sync row is that `dsh plugin add` alone
    leaves a WORKING distribution at the next profile boot. If the row is
    dropped from the patch, plugin-only installs silently regress to a router
    with nothing to route.
    """
    import json as _json

    patch = (REPO / "cordis.patch.yml").read_text()
    assert "rq-preset-sync" in patch, "cordis.patch.yml no longer mounts the boot-sync half"
    assert "'dsh-rigorquant/sync'" in patch, (
        "the sync row must load this package's ./sync export")
    manifest = _json.loads((REPO / "package.json").read_text())
    export = manifest["exports"].get("./sync")
    assert export, "package.json no longer exports ./sync"
    assert (REPO / export).exists(), "exports./sync points at a missing file"


def test_boot_sync_manages_the_preset_and_the_lane_and_never_derived_state():
    """The engine must land every runtime tree and never touch derived state.

    A venv is provisioned lazily inside the lane anchor by the first
    `uv run --frozen`; one prune pass that treats it as an extra would delete a
    provisioned environment mid-study. The behavioral side of this contract is
    executed for real in tests/test_preset_sync.py; this pins the wiring.
    """
    sync = (REPO / "dsh" / "sync.js").read_text()
    for tree in ("agent-presets/rigorquant", "env", "mcp", "docs"):
        assert f"'{tree}'" in sync, f"sync.js does not manage {tree}"
    for derived in (".venv", "__pycache__"):
        assert f"'{derived}'" in sync, f"sync.js does not exclude {derived}"
    assert "install.sh --uninstall" in sync or "--uninstall" in sync, (
        "sync.js must document that removal stays explicit (no uninstall hook)")
    # And the behavioral suite must exist and name the venv hazard.
    behavioral = (REPO / "tests" / "test_preset_sync.py").read_text()
    assert ".venv" in behavioral, "no test executes the venv-survival contract"


def test_every_globally_installed_skill_also_ships_in_the_package():
    """install.sh copies skills into $DSH_HOME/skills; the package must have them.

    These are the skills that end up supplied twice on a machine running both
    the preset and the plugin. The duplication is deliberate and resolves by
    rank, but it is only safe while the packaged copy actually exists -- a
    rename here would leave install.sh copying a directory that is gone.
    """
    installed = re.findall(r"install_dir \"\$HERE/agent-presets/rigorquant/skills/([a-z-]+)\"",
                           (REPO / "install.sh").read_text())
    assert installed, "install.sh no longer installs any skill globally"
    for name in set(installed):
        assert (REPO / "agent-presets/rigorquant/skills" / name).is_dir(), (
            "install.sh installs %s but the package does not ship it" % name)


def test_the_package_is_executable_as_a_one_line_installer():
    """`npx dsh-rigorquant` must reach install.sh.

    The one-line install depends on three things holding together: a bin entry,
    the script shipping in the npm files list, and its executable bit (npm
    preserves mode, and npx runs the bin through its shebang).
    """
    manifest = json.loads((REPO / "package.json").read_text())
    assert manifest.get("bin") == {"dsh-rigorquant": "./install.sh"}, manifest.get("bin")
    assert "install.sh" in manifest["files"]
    assert os.access(REPO / "install.sh", os.X_OK), "install.sh is not executable"


def test_the_installer_installs_the_plugin_by_default():
    """install.sh writing only to $DSH_HOME left the router silently absent."""
    script = (REPO / "install.sh").read_text()
    assert "install_plugin" in script, "install.sh no longer installs the plugin"
    # The default (full) branch must call it -- not just define it.
    full = script.split("if [ \"$mode\" = skill ]", 1)[1]
    assert "install_plugin" in full, "the default install path does not install the plugin"


def test_a_fetched_copy_installs_the_published_version():
    """A checkout installs itself; an npx copy must not use a `file:` spec.

    npx unpacks into a cache directory that disappears after the run, so a
    `file:` spec would leave the profile pointing at nothing. A linked worktree
    counts as a checkout — `.git` is a FILE there — because that is where this
    repository's own agents install from, and reading it as a fetched copy is
    how a worktree profile ended up holding the published 0.4.2 (issue #21).
    """
    script = (REPO / "install.sh").read_text()
    assert re.search(
        r"is_git_checkout\(\)\s*\{[^}]*\[ -d \"\$HERE/\.git\" \][^}]*\[ -f \"\$HERE/\.git\" \]",
        script,
    ), "install.sh no longer recognises a linked worktree (where `.git` is a file)"
    assert "if is_git_checkout; then" in script, (
        "install.sh no longer distinguishes checkout from fetched copy")
    assert 'spec="dsh-rigorquant@${VERSION:-latest}"' in script, (
        "the fetched-copy path must install the published version by name")


def test_agent_team_activity_svg_is_fresh():
    """The committed panel SVG must be exactly what the generator emits.

    The activity view is generated (docs/figs/agent-team-activity.js embeds
    the role portraits as data URIs); a hand-edited SVG is the drift class
    this suite exists to catch -- and an edit here would silently stop
    matching the README's credited source.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to regenerate the activity SVG")
    svg = REPO / "docs/figs/agent-team-activity.svg"
    generator = REPO / "docs/figs/agent-team-activity.js"
    before = svg.read_bytes()
    after = before
    try:
        subprocess.run([node, str(generator)], cwd=REPO, check=True, capture_output=True)
        after = svg.read_bytes()
    finally:
        if after != before:
            svg.write_bytes(before)
    assert after == before, (
        "docs/figs/agent-team-activity.svg is stale; run `node docs/figs/agent-team-activity.js`")
