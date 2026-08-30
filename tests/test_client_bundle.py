"""The browser half must be a loader bundle, not ESM source.

The DSH web shell fetches `exports["./client"]` as a CLASSIC <script> and
requires it to self-register via `window.__ModuleLoader__.load({id, factory})`
(packages/client/modules/src/client/system.ts). A bundle that loads without
registering is a hard boot failure for the whole loader entry:

    failed to import loader entry <hash> (dsh-rigorquant): client-modules:
    bundle /plugins/dsh-rigorquant/client.js?rev=... loaded without
    registering "dsh-rigorquant" via __ModuleLoader__.load

Nothing in this repository could catch that before: the client half is only
ever executed by a browser. These tests execute it the way the shell does.
"""

import json
import re
import shutil
import subprocess

import pytest

from conftest import REPO

PLUGIN_ID = "dsh-rigorquant"
PROBE = REPO / "tests/client_bundle_probe.cjs"

# ctx services the card injects -> the client package that provides each.
# The exported `inject` is what gates fiber activation; this map is the reason
# the package-name edge list below has the entries it has.
SERVICE_PROVIDERS = {
    "slots": "@deepseek-ai/dsh-client-runtime",
    "locale": "@deepseek-ai/dsh-client-locale",
    "remote": "@deepseek-ai/dsh-api-remotes",
    "settingsScope": "@deepseek-ai/dsh-client-ui-settings",
    "sessions": "@deepseek-ai/dsh-api-session-controller",
}
# The card registers into the `settings.plugin.item` ring, which this package
# declares; the activity floater registers into the root-scoped `shell.overlay`
# ring declared by ui-layout (both additive seats — a replacement would shadow
# the shell).
RINGS = ["settings.plugin.item", "shell.overlay"]
CARDS = ["rigorquant-models", "rigorquant-activity"]
RING_OWNER = "@deepseek-ai/dsh-client-ui-settings-plugins"


def manifest():
    return json.loads((REPO / "package.json").read_text())


@pytest.fixture(scope="module")
def verdict():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the client bundle")
    client = REPO / manifest()["exports"]["./client"]
    out = subprocess.run([node, str(PROBE), str(client), PLUGIN_ID],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.fixture(scope="module")
def verdict_rc2():
    """The same bundle against a 0.1.1-rc.2 runtime surface.

    In rc.2 the standalone draft-model package is deleted and the
    `settingsSchema` service replaces it; the probe removes the package from
    the module table and serves the service, so any residual legacy require
    throws and fails the mount.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the client bundle")
    client = REPO / manifest()["exports"]["./client"]
    out = subprocess.run([node, str(PROBE), str(client), PLUGIN_ID, "rc2"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_client_export_points_at_a_shipped_file():
    client = manifest()["exports"]["./client"]
    assert (REPO / client).is_file(), client


def test_bundle_executes_as_a_classic_script(verdict):
    """An ESM `export` in a classic script is a SyntaxError: nothing runs."""
    assert "executionError" not in verdict, verdict.get("executionError")


def test_bundle_registers_itself_with_the_module_loader(verdict):
    assert verdict["registered"], (
        "bundle loaded without calling window.__ModuleLoader__.load — "
        "this is the exact boot failure the shell reports"
    )


def test_registration_is_keyed_by_the_package_name(verdict):
    assert verdict["id"] == PLUGIN_ID


def test_factory_returns_the_cordis_plugin_surface(verdict):
    assert "factoryError" not in verdict, verdict.get("factoryError")
    assert verdict["factoryIsFunction"]
    assert verdict["applyIsFunction"]
    assert verdict["inject"] == list(SERVICE_PROVIDERS)


def test_factory_only_requires_platform_modules(verdict):
    """The frozen module table answers platform seed words and nothing else."""
    assert "factoryError" not in verdict, verdict.get("factoryError")


def test_card_uses_the_current_session_model_catalog_remote(verdict):
    """DSH 0.1.2 removed the old connection.api.llm.models facade."""
    assert verdict["modelCatalogCalls"] == 1
    client = (REPO / manifest()["exports"]["./client"]).read_text()
    assert "this.ctx.remote.session.modelCatalog()" in client
    assert "this.ctx.get('remote')" not in client


def test_apply_mounts_both_rings(verdict):
    """Registering is necessary, not sufficient: apply must survive mount.

    The plugin contributes the settings card (settings.plugin.item) AND the
    live activity floater (shell.overlay). Both are additive list/keyed seats.
    """
    assert "mountError" not in verdict, verdict.get("mountError")
    assert verdict["mounted"]
    assert verdict["mountedRings"] == RINGS
    assert verdict["cards"] == CARDS


def test_activity_floater_renders_null_while_no_lab_runs(verdict):
    """The floater is a second registration; it must mount and render hidden.

    With an empty host snapshot (no RigorQuant session running), the panel
    renders null — no phantom widget — and must not crash at render time.
    """
    assert verdict["overlayRendered"] is True
    assert "overlayRenderError" not in verdict, verdict.get("overlayRenderError")
    assert verdict["overlayTree"] is None


def test_activity_floater_scopes_to_the_current_session(verdict):
    """The floater follows the current session, never other sessions' labs.

    With two labs in the store but a current session that is not one of them,
    the panel renders null; when the current session is a lab, it renders.
    """
    assert verdict["scopeMismatchNull"] is True
    assert verdict["scopeMatchRendered"] is True


def test_card_renders_with_framework_composed_props(verdict):
    """Mounting is not rendering: the `hooks` compartment is reserved.

    A registrant supplies observable sources under `hooks`; the slot framework
    strips that key and hands the component a bound `use<Name>` selector hook
    per source (ui-slots InjectFace). A component reaching for `props.hooks`
    registers fine and then crashes on first paint -- the card silently never
    appears, and the ring reports "slot entry crashed".
    """
    assert "renderError" not in verdict, verdict.get("renderError")
    assert verdict["rendered"]


def test_component_receives_the_bound_selector_hook(verdict):
    assert "useRqCard" in verdict["renderProps"], verdict["renderProps"]
    assert "hooks" not in verdict["renderProps"]


def test_card_root_is_a_list_item(verdict):
    """`settings.plugin.item` renders its entries into a <ul>.

    A card whose root is a bare <div> escapes the card frame and renders flush
    at the section's root level instead of inside its own titled, collapsible
    box like the Shell and Agent Loop cards.
    """
    assert verdict["rootType"] == "li", verdict.get("rootType")


def test_card_uses_the_settings_draft_model(verdict):
    """The card edits through the settings draft model (rc.7 surface).

    On pre-rc.2 harnesses that is the standalone
    @deepseek-ai/dsh-client-schema-form module. Using it is what keeps this
    card's override/reset semantics from drifting from the seam's.
    """
    assert "@deepseek-ai/dsh-client-schema-form" in verdict["required"]


def test_card_mounts_on_rc2_settings_schema_service(verdict_rc2):
    """The rc.2 blocker: the legacy draft-model package is deleted.

    The card must resolve the settingsSchema service instead — the probe
    removes the legacy package from the module table, so a residual require
    would throw and fail the mount. Absence of the specifier from `required`
    proves the bundle never touched the deleted module.
    """
    assert verdict_rc2["mode"] == "rc2"
    assert "factoryError" not in verdict_rc2, verdict_rc2.get("factoryError")
    assert "mountError" not in verdict_rc2, verdict_rc2.get("mountError")
    assert verdict_rc2["mounted"]
    assert verdict_rc2["cards"] == CARDS
    assert "@deepseek-ai/dsh-client-schema-form" not in verdict_rc2["required"]


def test_staging_records_an_override_and_discard_drops_it(verdict):
    draft = verdict["draft"]
    assert draft["start"] is False
    assert draft["afterStage"]["overridden"] is True
    assert draft["afterStage"]["dirty"] is True
    assert draft["afterStage"]["choice"] == {"provider": "deepseek", "model": "v4-flash"}
    assert draft["afterDiscard"] is False


def test_a_cleared_field_reports_what_it_falls_back_to(verdict):
    """Roles the plugin ships a base default for must not read as empty."""
    assert verdict["draft"]["inheritedOracle"] == {"provider": "deepseek", "model": "v4-pro"}


def test_save_turns_the_draft_into_scope_path_ops(verdict):
    draft = verdict["draft"]
    assert draft["ops"] == ["set:explorerPrimary"]
    assert draft["afterSaveDirty"] is False
    assert draft["persistedOverride"] is True


def test_clearing_an_override_unsets_rather_than_writing_a_blank(verdict):
    """deletePath semantics on the wire: the field falls back to base+defaults."""
    draft = verdict["draft"]
    assert draft["resetOps"] == ["unset:explorerPrimary"]
    assert draft["afterReset"] is False


def test_settings_namespace_is_writable_by_the_host():
    """dsh brands namespaces with /^[a-z][a-z0-9-]*$/ — kebab-case, no dots.

    `ctx.settings.register` takes a raw string and accepts anything, and
    `settings.describe` will happily list an illegal name, so the card looks
    fine right up to the first Save: the wire path brands the namespace and
    rejects every write with `settings-rejected`. A dotted namespace therefore
    produces a card that can display but can never persist a choice.
    """
    pattern = re.compile(r"^[a-z][a-z0-9-]*$")
    host = (REPO / "dsh/index.js").read_text()
    ns = re.search(r"const NS = '([^']+)'", host)
    assert ns, "dsh/index.js no longer declares its settings namespace"
    assert pattern.match(ns.group(1)), (
        "settings namespace %r is unwritable: dsh requires %s" % (ns.group(1), pattern.pattern))


def test_card_key_equals_the_served_namespace():
    """The keyed slot dispatches on namespace: the key must BE the namespace."""
    host = re.search(r"const NS = '([^']+)'", (REPO / "dsh/index.js").read_text()).group(1)
    card = re.search(r"const CARD_KEY = '([^']+)'", (REPO / "dsh/client.js").read_text()).group(1)
    assert card == host, "card key %r != served namespace %r" % (card, host)


def test_graph_edges_cover_every_service_the_card_injects():
    """`dsh.client.inject` is the package-name edge list, not cordis DI.

    The host copies it into the boot graph row, where it is informational
    (preflight display, HMR diffing) -- activation waiting is driven by the
    module's exported `inject`. It is still required to agree with what the
    card actually reaches for: a stale edge list misreports the graph.
    """
    declared = set(manifest()["dsh"]["client"]["inject"])
    missing = sorted(set(SERVICE_PROVIDERS.values()) - declared)
    assert not missing, "unfetched service providers: %s" % missing


def test_graph_edges_cover_the_slot_ring_owner():
    declared = set(manifest()["dsh"]["client"]["inject"])
    assert RING_OWNER in declared
