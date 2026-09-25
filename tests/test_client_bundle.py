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
    # `slots` is provided by ui-renderer's SlotRegistry. The old
    # @deepseek-ai/dsh-client-runtime name does not exist in 0.1.5.
    "slots": "@deepseek-ai/dsh-client-ui-renderer",
    "locale": "@deepseek-ai/dsh-client-locale",
    "remote": "@deepseek-ai/dsh-api-remotes",
    # Sub-namespaces are gated: Cordis throws without an explicit inject entry.
    "remote.session": "@deepseek-ai/dsh-api-session-controller",
    "remote.settings": "@deepseek-ai/dsh-api-remotes",
    # `configForms` replaced the settings scope service on DSH 0.1.7.
    "configForms": "@deepseek-ai/dsh-client-ui-settings",
}
# The card registers into the Plugins page's `plugins.bundle.config` ring,
# keyed by this bundle's package name. 0.1.6 retired `settings.plugin.item`:
# a card registered there renders nowhere, silently.
RINGS = ["plugins.bundle.config"]
CARDS = [PLUGIN_ID]
RETIRED_RING = "settings.plugin.item"
RING_OWNERS = ["@deepseek-ai/dsh-client-ui-plugin-manager"]
# The router row's entry id: `configForms` serves the row's config under it.
ROUTER_ROW = "rq-model-router"


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
    assert verdict["modelCatalogCalls"] >= 1
    client = (REPO / manifest()["exports"]["./client"]).read_text()
    assert "this.ctx.remote?.session" in client
    assert "await session.modelCatalog()" in client
    assert "this.ctx.get('remote')" not in client


def test_card_declares_the_remote_sub_namespaces_in_inject(verdict):
    """Cordis gates sub-namespace access and throws without an inject entry.

    The card reads `remote.session.modelCatalog()` and
    `remote.settings.describe()`. The probe models `remote` as a Proxy that only
    exposes namespaces declared in the module's `inject`; if a sub-namespace is
    accessed but not declared, apply() throws and the mount fails. A passing
    mount proves both are declared.
    """
    assert "mountError" not in verdict, verdict.get("mountError")
    assert "remote" in verdict["inject"]
    assert "remote.session" in verdict["inject"]
    assert "remote.settings" in verdict["inject"]
    assert verdict["modelCatalogCalls"] >= 1


def test_card_waits_for_session_remote_before_failing(verdict):
    """Immediate boot can precede remote.session mounting; the card must retry.

    In the probe the session Remote is absent at apply time and mounts a few
    retry windows later. The controller must converge to 'ready' instead of
    declaring the catalog failed on a bootstrap-batch boot race.
    """
    assert "delayedCatalogError" not in verdict, verdict.get("delayedCatalogError")
    assert verdict["delayedCatalogStatus"] == "ready", verdict
    assert verdict["delayedCatalogCalls"] >= 1


def test_apply_mounts_the_card_ring(verdict):
    """Registering is necessary, not sufficient: apply must survive mount.

    The plugin contributes one thing, the routing card
    (plugins.bundle.config). Decision 25 removed everything else: the Team
    service has no browser Remotes left to read the board through.
    """
    assert "mountError" not in verdict, verdict.get("mountError")
    assert verdict["mounted"]
    assert verdict["mountedRings"] == RINGS
    assert verdict["cards"] == CARDS


def test_card_registers_on_the_bundle_config_slot_keyed_by_the_package(verdict):
    """The Plugins page finds a bundle's form by slot name and key.

    `plugins.bundle.config` is keyed by the bundle's package name and rendered
    on the bundle's page between its description and its rows
    (ui-plugin-manager slot-contract). The key must be the same name the
    bundle registered with the loader: any other key is an entry the page
    never asks for.
    """
    assert verdict["cardSlot"] == "plugins.bundle.config"
    assert verdict["cardKey"] == verdict["id"] == PLUGIN_ID


def test_the_retired_settings_slot_is_gone(verdict):
    """0.1.6 retired `settings.plugin.item`; a registration there is silent.

    Nothing renders the ring any more, so the failure is a card that simply
    never appears. The ring must be absent from what apply mounts AND from the
    source, so it cannot come back behind a feature check.
    """
    assert RETIRED_RING not in verdict["mountedRings"]
    assert verdict["retiredSettingsSlotReferences"] == 0


def test_card_edits_the_router_rows_config_form(verdict):
    """The card reads and writes the router row's own profile config.

    `configForms.get(<entry id>)` serves one Host plugin entry's config; the
    id must be the router row's id in the bundle patch, which is also the
    router's plugin name.
    """
    assert verdict["configFormIds"] == [ROUTER_ROW]
    assert "- id: %s\n" % ROUTER_ROW in (REPO / "cordis.patch.yml").read_text()
    assert "const name = '%s'" % ROUTER_ROW in (REPO / "dsh/index.js").read_text()


def test_a_refused_save_is_shown_and_keeps_the_draft(verdict):
    """`set`/`unset` resolve `false` when the Host refuses a write.

    A refusal is not a rejection, so a save that only caught throws would
    report success while nothing was stored. It must show the failure and
    keep the staged edit for another try.
    """
    refused = verdict["draft"]["refused"]
    assert refused["ops"] == ["set:explorerPrimary"]
    assert refused["failed"] == "write"
    assert refused["stillDirty"] is True
    assert refused["stored"] is False


def test_nothing_reads_a_current_session_field(verdict):
    """`SessionListState.current` is gone; a read of it is silently undefined.

    The pin is on the member name in the source (the behavioural check above
    is what proves the replacement works). It is deliberately blunt: a future
    `ref.current` in the bundle would trip it too, and would be the moment to
    narrow it to the session-list read.
    """
    assert verdict["currentFieldReads"] == 0, (
        "dsh/client.js still reads a `.current` member; the sessions list has "
        "no such field on 0.1.6 and the read is silent")


def test_fiber_unload_runs_every_disposer_cleanly(verdict):
    """A fiber unload must not throw, even with nothing left to clean up.

    `ctx.effect` runs its body at once and keeps what the body RETURNS as the
    disposer. The retired activity floater's docked-panel dodge stylesheet was
    the only DOM side effect this bundle ever mounted; nothing replaces it, so
    this just proves running every collected disposer in reverse cannot throw.
    """
    assert "disposeError" not in verdict, verdict.get("disposeError")


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


def test_card_renders_the_two_views_the_plugins_page_asks_for(verdict):
    """`summary` is one line of text; `page` is the form with its own Save.

    The page draws the title, icon and crumb itself and asks the entry for
    `view: 'summary'` (the one-liner under the title) and `view: 'page'` (the
    form). The page view is a plain block — the bundle's page wraps it in its
    own section, so the old `<li>` card frame would nest a list item in a
    section — and only a save writes: no Discard control, no unsaved marker.
    """
    assert "renderError" not in verdict, verdict.get("renderError")
    assert isinstance(verdict["summaryView"], str) and verdict["summaryView"], verdict.get("summaryView")
    assert verdict["rootType"] == "div", verdict.get("rootType")
    assert verdict["pageButtons"] == ["save"], verdict["pageButtons"]
    assert "discard" not in verdict["pageText"]
    assert "pending" not in verdict["pageText"]


def test_card_uses_the_settings_draft_model(verdict):
    """The card edits through the `settingsSchema` service — the only one left.

    The standalone @deepseek-ai/dsh-client-schema-form package was deleted
    upstream (0.1.1-rc.2 folded its helpers into the service) and is absent from
    the browser's frozen module table, so the probe refuses to answer it. The
    card must resolve the service; a residual require would throw inside the
    controller's construction and take the whole bundle entry down.

    `required` records every specifier the bundle asked the module table for, so
    the absence of the deleted name proves the fallback is gone; the mount and
    draft assertions below prove the service path actually runs.
    """
    assert "@deepseek-ai/dsh-client-schema-form" not in verdict["required"], verdict["required"]
    source = (REPO / manifest()["exports"]["./client"]).read_text()
    # The name may appear in prose; a REQUIRE of it is what would throw.
    assert "require('@deepseek-ai/dsh-client-schema-form')" not in source
    assert "this.ctx.get('settingsSchema')" in source


def test_staging_records_an_override_and_discard_drops_it(verdict):
    draft = verdict["draft"]
    assert draft["start"] is False
    assert draft["afterStage"]["overridden"] is True
    assert draft["afterStage"]["dirty"] is True
    assert draft["afterStage"]["choice"] == {"provider": "deepseek", "model": "v4-flash"}
    assert draft["afterDiscard"] is False


def test_a_cleared_field_reports_what_it_falls_back_to(verdict):
    """Roles the plugin ships a base default for must not read as empty."""
    assert verdict["draft"]["inheritedDoubleChecker"] == {"provider": "deepseek", "model": "v4-pro"}


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


def test_effort_dropdown_offers_only_the_models_real_surfaces(verdict):
    """Every effort select renders exactly what the chosen model supports.

    The probe's one catalog model carries no reasoning metadata, so every
    effort select (8 roles x 2 slots, on the page view) must offer only "Default" — never a
    generic [off, high, max] vocabulary, which is how a route with no
    reasoning surface once got saved with an effort every turn on it refused.
    A stored effort the model does not list stays visible but disabled.
    """
    assert "effortDropdownError" not in verdict, verdict.get("effortDropdownError")
    assert verdict["effortSelectCount"] == 16, verdict.get("effortSelectCount")
    assert verdict["effortSelectsDefaultOnly"] is True
    stale = verdict["staleEffortOptions"]
    assert stale is not None, "a stored unsupported effort must stay visible (disabled)"
    assert stale[0] == {"value": "", "label": "effortInherit", "disabled": False}
    assert stale[1] == {
        "value": "high", "label": "high · effortUnsupported", "disabled": True,
    }


def test_model_select_flags_an_override_its_provider_does_not_list(verdict):
    """A stored model its provider does not declare is marked, not hidden.

    Issue #22: `explorerPrimary: linxicloud/deepseek-v4-flash-dspark` named a
    model missing from its provider's catalog, and every teammate on it died
    with UNKNOWN_MODEL. The select had no option for the stored value, so the
    row read as "Inherit". The card now renders that value as a disabled
    `provider name · model · modelUndeclared` option. A provider the catalog does
    not list at all is left unflagged: its listing may have failed.
    """
    assert "effortDropdownError" not in verdict, verdict.get("effortDropdownError")
    assert verdict["undeclaredModelOption"] == {
        "value": "deepseek::v4-flash-dspark",
        "label": "DeepSeek · v4-flash-dspark · modelUndeclared",
        "disabled": True,
    }
    assert verdict["unlistedProviderOption"] is None
    assert verdict["flaggedModelOptions"] == ["deepseek::v4-flash-dspark"]


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


def test_graph_edges_cover_the_slot_ring_owners():
    declared = set(manifest()["dsh"]["client"]["inject"])
    missing = sorted(set(RING_OWNERS) - declared)
    assert not missing, "unfetched ring owners: %s" % missing
