"""Consistency between documents, and between a document and the filesystem.

docs/repository-review.md closed with the observation that every finding this
repository has ever produced came from a reader, not from anything executable,
and that the defect class is unenforced consistency between files. These are
those checks.
"""

import json
import re
import subprocess

from conftest import REPO, SKILL_DIR

SKILL_SCRIPTS = ("rq_check.py", "provision-lean.sh")


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

    `subagent_novel` existed in the composition while every shipped procedure
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


def test_install_script_installs_literature_skills():
    """Decision 15: arxiv + academic-paper-search ship to $DSH_HOME/skills/."""
    install = (REPO / "install.sh").read_text()
    for skill in ("arxiv", "academic-paper-search"):
        assert ('$DSH_HOME/skills/%s"' % skill) in install or \
               ('$DSH_HOME/skills/%s ' % skill) in install, \
               "install.sh never installs %s globally" % skill


def test_j_space_is_bundled_installed_and_uninstallable():
    """The J-Space integration must be self-contained and removable."""
    assert (REPO / "agent-presets/rigorquant/skills/j-space/SKILL.md").exists()
    install = (REPO / "install.sh").read_text()
    assert "$DSH_HOME/skills/j-space" in install, \
        "install.sh never installs j-space globally"
    assert 'rm -rf "$DSH_HOME/skills/j-space"' in install, \
        "install.sh --uninstall never removes j-space"
