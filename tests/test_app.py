from pathlib import Path

from textual.widgets import Checkbox, DataTable, Input

from vheist.app import TargetListPanel, VhostHeist
from vheist.config import Config


def make_test_config(tmp_path: Path, domains: list[str] | None = None, ips: list[str] | None = None) -> Config:
    return Config(
        path=tmp_path / "test-config.json",
        domains=domains if domains is not None else [],
        ips=ips if ips is not None else [],
        timeout=1.0,
    )


async def test_app_starts_empty(tmp_path: Path):
    cfg = make_test_config(tmp_path)
    app = VhostHeist(cfg)
    async with app.run_test() as pilot:
        dom_panel = app.query_one("#domains-panel", TargetListPanel)
        ip_panel = app.query_one("#ips-panel", TargetListPanel)
        assert len(dom_panel.items) == 0
        assert len(ip_panel.items) == 0
        table = app.query_one("#results", DataTable)
        assert table.row_count == 0


async def test_add_domain_autosaves(tmp_path: Path):
    cfg = make_test_config(tmp_path)
    app = VhostHeist(cfg)
    async with app.run_test() as pilot:
        inp = app.query_one("#domains-panel Input", Input)
        inp.value = "internal-api.example.com"
        inp.focus()
        await pilot.press("enter")
        await pilot.pause()

        assert cfg.domains == ["internal-api.example.com"]
        saved = Config.load(cfg.path)
        assert saved.domains == ["internal-api.example.com"]


async def test_add_cidr_ip_expands_and_autosaves(tmp_path: Path):
    cfg = make_test_config(tmp_path)
    app = VhostHeist(cfg)
    async with app.run_test() as pilot:
        inp = app.query_one("#ips-panel Input", Input)
        inp.value = "192.168.10.0/30"
        inp.focus()
        await pilot.press("enter")
        await pilot.pause()

        assert cfg.ips == ["192.168.10.1", "192.168.10.2"]
        saved = Config.load(cfg.path)
        assert saved.ips == ["192.168.10.1", "192.168.10.2"]


async def test_delete_selected_autosaves(tmp_path: Path):
    cfg = make_test_config(tmp_path, domains=["site1.test", "site2.test"])
    app = VhostHeist(cfg)
    async with app.run_test() as pilot:
        panel = app.query_one("#domains-panel", TargetListPanel)
        panel.options.focus()
        panel.options.highlighted = 0
        await pilot.press("delete")
        await pilot.pause()

        assert cfg.domains == ["site2.test"]
        saved = Config.load(cfg.path)
        assert saved.domains == ["site2.test"]


async def test_settings_inputs_and_checkboxes_autosave(tmp_path: Path):
    cfg = make_test_config(tmp_path)
    app = VhostHeist(cfg)
    async with app.run_test() as pilot:
        timeout_inp = app.query_one("#timeout", Input)
        timeout_inp.value = "8.5"
        port_http = app.query_one("#port_http", Input)
        port_http.value = "8080"
        cb_https = app.query_one("#https", Checkbox)
        cb_https.value = False
        await pilot.pause()

        saved = Config.load(cfg.path)
        assert saved.timeout == 8.5
        assert saved.port_http == 8080
        assert saved.https is False


async def test_filter_results(tmp_path: Path):
    cfg = make_test_config(tmp_path)
    app = VhostHeist(cfg)
    async with app.run_test() as pilot:
        from vheist.models import Result

        r1 = Result("secret.test", "10.0.0.1", 80, "http", 200, 100, 0.1, title="Secret Admin")
        r2 = Result("public.test", "10.0.0.2", 80, "http", 404, 50, 0.1, title="Not Found")
        app._on_result_received(r1)
        app._on_result_received(r2)
        await pilot.pause()

        table = app.query_one("#results", DataTable)
        assert table.row_count == 2

        # Apply filter
        filter_inp = app.query_one("#input-filter", Input)
        filter_inp.value = "secret"
        await pilot.pause()

        assert table.row_count == 1


async def test_inspect_modal_displays_curl(tmp_path: Path):
    cfg = make_test_config(tmp_path)
    app = VhostHeist(cfg)
    async with app.run_test() as pilot:
        from vheist.models import Result
        from vheist.widgets.modals import InspectorModal

        res = Result("corp.test", "10.0.0.1", 443, "https", 200, 500, 0.05, title="Corp Portal")
        app._on_result_received(res)
        await pilot.pause()

        # Press enter to inspect
        table = app.query_one("#results", DataTable)
        table.focus()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, InspectorModal)
        assert "curl" in app.screen.res.curl_cmd
        await pilot.press("escape")
        await pilot.pause()


async def test_help_modal(tmp_path: Path):
    cfg = make_test_config(tmp_path)
    app = VhostHeist(cfg)
    async with app.run_test() as pilot:
        from vheist.widgets.modals import HelpModal

        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpModal)
        await pilot.press("escape")
        await pilot.pause()

