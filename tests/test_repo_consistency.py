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
