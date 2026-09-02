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

from conftest import REPO, SKILL_DIR

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


def test_install_script_installs_everything_the_runtime_needs():
    """The skill's scripts and schemas must survive a full install."""
    install = (REPO / "install.sh").read_text()
    for needed in ("agent-presets/rigorquant", "env", "mcp"):
        assert needed in install, "install.sh never installs %s" % needed
    assert "schemas" not in install or "agent-presets" in install


def test_native_agent_options_floor_is_declared_and_enforced():
    """The native reasoning field cannot be installed into an older DSH."""
    floor = "0.1.2-alpha.1"
    install = (REPO / "install.sh").read_text()
    assert "MIN_DSH_VERSION=\"%s\"" % floor in install
    assert "version_at_least" in install
    for path in (REPO / "README.md", REPO / "README.zh-CN.md"):
        assert floor in path.read_text(), "%s omits the DSH floor" % path.name


def test_installer_rejects_an_older_dsh_before_copying_files(tmp_path):
    """A pre-0.1.2 CLI must not receive a preset using reasoningEffort."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_dsh = fake_bin / "dsh"
    fake_dsh.write_text("#!/bin/sh\nprintf '0.1.1-rc.2\\n'\n")
    fake_dsh.chmod(0o755)
    dsh_home = tmp_path / "dsh-home"
    env = os.environ.copy()
    env["PATH"] = "%s:%s" % (fake_bin, env.get("PATH", ""))
    env["DSH_HOME"] = str(dsh_home)
    result = subprocess.run(
        [str(REPO / "install.sh"), "--profile", "upgrade-test"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "requires dsh >= 0.1.2-alpha.1" in result.stderr
    assert not dsh_home.exists(), "the old runtime guard must run before copying"


def test_installer_accepts_the_minimum_dsh_version(tmp_path):
    """The prerelease floor itself is supported, not merely later stable tags."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_dsh = fake_bin / "dsh"
    fake_dsh.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then printf '0.1.2-alpha.1\\n'; fi\n"
    )
    fake_dsh.chmod(0o755)
    dsh_home = tmp_path / "dsh-home"
    env = os.environ.copy()
    env["PATH"] = "%s:%s" % (fake_bin, env.get("PATH", ""))
    env["DSH_HOME"] = str(dsh_home)
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


def test_architecture_record_matches_the_preset_composition():
    """docs/architecture.md described maxDepth: 0, which blocks all delegation."""
    preset = (REPO / "agent-presets/rigorquant/agent.cordis.yml").read_text()
    depths = set(re.findall(r"^\s*maxDepth:\s*(\S+)", preset, re.MULTILINE))
    arch = (REPO / "docs/architecture.md").read_text()
    claims = re.findall(r"each `maxDepth:\s*(\S+?)`", arch)
    assert claims, "architecture.md no longer states the delegation depth"
    for claimed in claims:
        assert claimed in depths, (
            "architecture.md claims maxDepth: %s but the preset uses %s" % (claimed, depths))


def _preset_blocks(preset):
    """Yield (id, block) for every row of the preset composition."""
    for match in re.finditer(r"^\s{4}- id: (\S+)\n((?:\s{6,}.*\n|\n)*)", preset, re.MULTILINE):
        yield match.group(1), match.group(2)


def test_every_role_persona_carries_its_router_tag():
    """The model router identifies roles by [[rq:role=X]] in the persona.

    A persona that loses its tag silently falls back to the session model —
    the DoubleChecker running on flash is exactly the failure this pins out.
    """
    roles = {
        "tool-subagent-explorer": "explorer",
        "tool-subagent-offgrid": "offgrid",
        "tool-subagent-double-checker": "doublechecker",
        "tool-subagent-adversary": "adversary",
        "tool-subagent-lit-line": "lit-line",
        "tool-subagent-lit-adversary": "lit-adversary",
        "tool-subagent-doc-adversary": "doc-adversary",
    }
    preset = (REPO / "agent-presets/rigorquant/agent.cordis.yml").read_text()
    blocks = dict(_preset_blocks(preset))
    for row_id, role in roles.items():
        block = blocks.get(row_id)
        assert block is not None, "preset lost the %s row" % row_id
        assert "[[rq:role=%s]]" % role in block, (
            "%s must carry the routing tag [[rq:role=%s]]" % (row_id, role))
        # No stray tags: a copy-pasted persona would route under the wrong role.
        for _, other in roles.items():
            if other != role:
                assert "[[rq:role=%s]]" % other not in block, (
                    "%s carries the wrong tag [[rq:role=%s]]" % (row_id, other))


def test_fixed_tier_roles_delegate_their_primary_to_native_agent_options():
    """The native 0.1.2 child route owns shipped primary defaults.

    The host router still owns live overrides and fallback retries, but a normal
    DoubleChecker/adversary request must be able to use the tool row's
    agentOptions without an unconditional agent/request rewrite.
    """
    preset = (REPO / "agent-presets/rigorquant/agent.cordis.yml").read_text()
    blocks = dict(_preset_blocks(preset))
    for row_id in ("tool-subagent-double-checker", "tool-subagent-adversary"):
        block = blocks.get(row_id)
        assert block is not None, "preset lost the fixed-tier row %s" % row_id
        assert re.search(
            r"agentOptions:\s+provider:\s+deepseek-official\s+"
            r"model:\s+deepseek-v4-pro\s+reasoningEffort:\s+high",
            block,
        ), "%s must declare the native 0.1.2 primary" % row_id
        assert "maxTokens:" not in block, "%s must not impose a proof-output cap" % row_id
        assert "modelSelectionSettings:" not in block, (
            "%s must keep caller-selected model routes disabled" % row_id)


def test_activity_floater_binds_the_sessions_service_lazily():
    """An immediately-materialized bundle must not sample ctx.get() once.

    dsh/client.js materializes immediately. Its required `sessions` injection
    gates normal activation, while the lazy binding handles replacement and
    must be initialized before the first poll. The previous ordering called
    tick() inside the lexical TDZ, so its first fetch always rejected.
    """
    client = (REPO / "dsh" / "client.js").read_text()
    assert "bindSessionList" in client, "the lazy sessions binding was removed"
    assert "const sessions = ctx.get('sessions')" not in client, (
        "a one-shot service sample at boot is the 0.1.2 boot-order regression")
    tick = client[client.index("const tick = async () =>"):]
    tick = tick[:tick.index("\n  }")]
    assert "bindSessionList()" in tick, "tick() must re-check the sessions service"
    assert client.index("const bindSessionList") < client.index("void tick()"), (
        "the initial poll must not enter the sessions-binding TDZ")
    assert "request.abort()" in client, "poll cleanup must abort its live request"
    assert "activityState.openOwner === activityState.currentSessionId" in client, (
        "a docked panel must not leave conversation padding after route changes")


def test_agent_teams_geometry_attribution_keeps_the_upstream_mit_notice():
    notice = (REPO / "THIRD_PARTY_NOTICES").read_text()
    assert "dsh-agent-teams" in notice
    assert "Copyright (c) 2026 程序员阿江(Relakkes)" in notice
    assert "The above copyright notice and this permission notice" in notice


def test_effort_select_uses_the_models_real_supported_levels():
    """The effort dropdown must not hard-code [high, max] globally.

    A model that does not support a given reasoning effort (e.g. some routes
    reject "high") must not be offered that level, and switching to such a
    model must not carry a now-invalid effort forward.
    """
    client = (REPO / "dsh" / "client.js").read_text()
    # The catalog keeps each model's reasoning effort surface.
    assert "efforts: (model.reasoning?.efforts ?? [])" in client, (
        "the card drops model reasoning efforts instead of keeping them")
    assert "defaultEffort: model.reasoning?.defaultEffort" in client
    # The effort select filters on the chosen model's surfaces, not a constant.
    assert "const supported = (efforts?.length ?? 0) > 0" in client
    assert "targetEfforts.some((effort) => effort.id" in client, (
        "switching models must discard an effort the new route rejects")


def test_activity_hub_map_is_hub_and_spoke():
    """The pillbox role map must be a hub-and-spoke, not a stage DAG.

    The root orchestrator is the only hub: every child role is a spoke
    connected to it, and there are no role-to-role edges (reports flow through
    the root). The literature advisor is a spoke distinct from the literature
    lane.
    """
    host = (REPO / "dsh" / "activity.js").read_text()
    client = (REPO / "dsh" / "client.js").read_text()
    # Roster (host) keeps the full name; the narrow hub-map node uses a compact
    # one.
    assert "'lit-adversary': { label: 'Literature adversary'" in host
    assert "'lit-adversary': { label: 'Lit adversary'" in client
    # Hub-and-spoke topology: one hub, seven spokes, one line per spoke, and
    # no handoff edges between spokes.
    assert "const RQ_HUB = 'root'" in client
    spokes = re.search(r"const RQ_SPOKES = \[(.*?)\]", client, re.DOTALL)
    assert spokes, "the hub map lost its spoke list"
    spoke_roles = re.findall(r"'([a-z-]+)'", spokes.group(1))
    assert len(spoke_roles) == 7 and "root" not in spoke_roles, spoke_roles
    assert spoke_roles == sorted(set(spoke_roles), key=spoke_roles.index), \
        "a spoke is listed twice"
    assert "RQ_SPOKES.map((role)" in client, "spokes must render from the list"
    assert "RQ_LEVELS" not in client and "RQ_PIPELINE_EDGES" not in client, (
        "the stage DAG survived the hub-and-spoke rewrite")


def test_router_native_defaults_overrides_and_fallback_round_trip():
    """The host router leaves native defaults alone but keeps its policy overlay."""
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


def test_router_roles_cover_the_tagged_roles_exactly():
    """dsh/index.js ROLES must match the roles the preset can tag.

    The router routes a tag it does not know nowhere, and a role it names but
    no persona tags is a silent dead setting — both are drift this catches.
    """
    import pathlib

    router = (pathlib.Path(__file__).resolve().parents[1] / "dsh" / "index.js").read_text()
    match = re.search(r"export const ROLES = \[([^\]]*)\]", router)
    assert match, "dsh/index.js no longer exports its ROLES list"
    declared = set(re.findall(r"'([a-z-]+)'", match.group(1)))
    preset = (REPO / "agent-presets/rigorquant/agent.cordis.yml").read_text()
    tagged = set(re.findall(r"\[\[rq:role=([a-z-]+)\]\]", preset))
    assert declared == tagged | {"root"}, (
        "router ROLES %s != tagged roles %s + root" % (sorted(declared), sorted(tagged)))


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
    # the activity floater. Each must be bilingual — a monolingual block is a
    # language that silently falls back to the other's strings.
    sections = re.findall(r"^\s{2}(en|zh): \{", client, re.MULTILINE)
    assert sections[:2] == ["en", "zh"], "the card copy sections moved; update this test"
    assert sections[2:] == ["en", "zh"], "the activity copy is not bilingual"
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
    model looking for a file that is not installed.
    """
    referenced = {}
    for rel in tracked_files():
        if rel.endswith((".png", ".pdf", ".lock")):
            continue
        try:
            text = (REPO / rel).read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for hit in re.findall(r"docs/[\w./-]*\.md", text):
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
    """A cited `Decision N` that architecture.md never records is drift."""
    known = _decision_numbers()
    assert known, "architecture.md records no decisions; update this test"
    offenders = []
    sources = docs() + [REPO / f for f in tracked_files() if f.startswith("tests/")]
    for src in sources:
        for n, line in enumerate(src.read_text().splitlines(), 1):
            for num in re.findall(r"[Dd]ecision (\d+)", line):
                if num not in known:
                    offenders.append("%s:%d: Decision %s" % (src.relative_to(REPO), n, num))
    assert not offenders, (
        "references to decisions architecture.md never records:\n" + "\n".join(offenders))


def _spawned_role_tool_names():
    """Model-facing tool names of the enabled spawn-provider delegation rows."""
    text = (REPO / "agent-presets/rigorquant/agent.cordis.yml").read_text()
    names = []
    for part in re.split(r"\n    - id: ", text)[1:]:
        if re.search(r"^\s*disabled: true", part, re.MULTILINE):
            continue
        if "provider: spawn" not in part:
            continue
        m = re.search(r"toolName:\s*(\S+)", part)
        if m:
            names.append(m.group(1))
    return names


def test_the_shipped_procedure_names_every_delegation_role():
    """A walled role nothing routes work to is enforcement no one can reach.

    `subagent_offgrid` existed in the composition while every shipped procedure
    still told the orchestrator to re-use the open explorer under the novelty
    toggle -- the role was unreachable by instruction.
    """
    skills = REPO / "agent-presets/rigorquant/skills"
    corpus = "\n".join(p.read_text() for p in skills.rglob("*.md"))
    missing = [n for n in _spawned_role_tool_names() if n not in corpus]
    assert not missing, (
        "the composition defines roles no shipped skill instructs anyone to use: %s" % missing)


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
    `file:` spec would leave the profile pointing at nothing.
    """
    script = (REPO / "install.sh").read_text()
    assert 'if [ -d "$HERE/.git" ]' in script, "install.sh no longer distinguishes checkout from fetched copy"
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
