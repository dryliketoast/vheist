"""Main Textual application for vheist."""

from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Checkbox, DataTable, Footer, Header, Input, Label, OptionList

from .config import Config, normalize_domain, normalize_ip_or_cidr, normalize_port
from .export import export_results
from .models import Result, ScanStats
from .probe import ProbeRunner, jobs
from .widgets import (
    BulkImportModal,
    ExportModal,
    HelpModal,
    InspectorModal,
    StatsBar,
    TargetListPanel,
)


def style_for(res: Result) -> str:
    """Return Rich style name based on HTTP status code or error state."""
    if res.error or not res.code:
        return "red"
    return {2: "bold green", 3: "bold cyan", 4: "yellow", 5: "bold red"}.get(res.code // 100, "")


class VhostHeist(App):
    """vheist TUI: fast vhost discovery, live filtering, and target configuration."""

    TITLE = "vheist"
    SUB_TITLE = "Virtual Host Discovery & Prober"

    CSS = """
    #sidebar {
        width: 44;
        height: 1fr;
    }
    TargetListPanel {
        border: round $primary;
        height: 1fr;
    }
    TargetListPanel:focus-within {
        border: round $accent;
    }
    TargetListPanel OptionList {
        height: 1fr;
        border: none;
        background: transparent;
    }
    .panel-actions {
        height: 1;
        align: right middle;
        padding-right: 1;
        margin-top: 1;
    }
    .panel-actions Button {
        height: 1;
        min-width: 8;
        padding: 0 1;
        border: none;
    }
    #main-panel {
        height: 1fr;
        width: 1fr;
    }
    #filter-bar {
        height: 3;
        background: $surface;
        padding: 0 1;
        align: left middle;
    }
    #input-filter {
        width: 1fr;
        margin-right: 2;
    }
    #results {
        border: round $primary;
        height: 1fr;
    }
    #results:focus {
        border: round $accent;
    }
    #settings-bar {
        height: 3;
        background: $surface;
        align: left middle;
        padding: 0 1;
        border-top: solid $primary;
    }
    #settings-bar Label {
        padding: 0 1;
        text-style: bold;
    }
    #settings-bar Input {
        width: 8;
        margin-right: 1;
    }
    #settings-bar Checkbox {
        border: none;
        padding: 0 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("r", "run", "Run"),
        Binding("s", "stop", "Stop"),
        Binding("p", "pause_resume", "Pause"),
        Binding("c", "clear", "Clear"),
        Binding("f", "toggle_failures", "Failures"),
        Binding("b", "toggle_baseline", "Baseline"),
        Binding("i", "import_targets", "Import"),
        Binding("e", "export_results", "Export"),
        Binding("delete", "delete_target", "Delete"),
        Binding("enter", "inspect_result", "Inspect"),
        Binding("question_mark", "help", "Help"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.results: list[Result] = []
        self.stats = ScanStats()
        self.runner: ProbeRunner | None = None
        self.is_scanning = False
        self.filter_query = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatsBar(id="stats-bar")
        with Horizontal():
            with Vertical(id="sidebar"):
                yield TargetListPanel(
                    "Domains",
                    self.cfg.domains,
                    normalize_domain,
                    "add domain (e.g. dev.site.com)",
                    on_change=self.save_config,
                    id="domains-panel",
                )
                yield TargetListPanel(
                    "Endpoint IPs / CIDRs",
                    self.cfg.ips,
                    normalize_ip_or_cidr,
                    "add IP or /29 (e.g. 10.0.0.1)",
                    on_change=self.save_config,
                    id="ips-panel",
                )
            with Vertical(id="main-panel"):
                with Horizontal(id="filter-bar"):
                    yield Input(placeholder="Search / filter (e.g. 200, admin, nginx)...", id="input-filter")
                    yield Checkbox("hide failures", self.cfg.hide_failures, id="hide_failures")
                    yield Checkbox("hide baseline", self.cfg.hide_baseline, id="hide_baseline")
                yield DataTable(id="results", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="settings-bar"):
            yield Label("Timeout")
            yield Input(str(self.cfg.timeout), id="timeout", type="number")
            yield Label("Parallel")
            yield Input(str(self.cfg.concurrency), id="concurrency", type="integer")
            yield Checkbox("http", self.cfg.http, id="http")
            yield Input(str(self.cfg.port_http), id="port_http", type="integer")
            yield Checkbox("https", self.cfg.https, id="https")
            yield Input(str(self.cfg.port_https), id="port_https", type="integer")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results", DataTable)
        table.add_columns(
            "Domain",
            "IP",
            "Port",
            "Proto",
            "Status",
            "Title",
            "Server",
            "Size",
            "Time",
            "Redirect",
        )
        self.sub_title = str(self.cfg.path)
        self._refresh_stats()

    def save_config(self) -> None:
        """Autosave active configuration to disk."""
        self.cfg.save()

    # --- Settings Events ----------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "input-filter":
            self.filter_query = event.value.strip().lower()
            self._rebuild_table()
            return

        try:
            if event.input.id == "timeout":
                self.cfg.timeout = max(0.5, float(event.value))
            elif event.input.id == "concurrency":
                self.cfg.concurrency = max(1, int(event.value))
            elif event.input.id == "port_http":
                p = normalize_port(event.value)
                if p:
                    self.cfg.port_http = p
            elif event.input.id == "port_https":
                p = normalize_port(event.value)
                if p:
                    self.cfg.port_https = p
            else:
                return
        except ValueError:
            return  # incomplete number input

        self.save_config()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id in ("hide_failures", "hide_baseline"):
            setattr(self.cfg, event.checkbox.id, event.value)
            self.save_config()
            self._rebuild_table()
        elif event.checkbox.id in ("http", "https"):
            setattr(self.cfg, event.checkbox.id, event.value)
            self.save_config()

    # --- Actions / Keybindings ----------------------------------------------

    def action_run(self) -> None:
        """Start or restart probing scan."""
        self.action_stop()
        self.action_clear()

        total_jobs = sum(1 for _ in jobs(self.cfg))
        if total_jobs == 0:
            self.notify(
                "Nothing to probe: add at least one domain, IP, and enable HTTP or HTTPS",
                severity="warning",
            )
            return

        self.runner = ProbeRunner(self.cfg)
        self.is_scanning = True
        self.run_worker(self._run_probes(), group="probe", exclusive=True)
        self._refresh_stats()

    async def _run_probes(self) -> None:
        try:
            if self.runner:
                await self.runner.run(self._on_result_received, self.stats)
        finally:
            self.is_scanning = False
            self._refresh_stats()

    def action_stop(self) -> None:
        """Cancel the active probe worker."""
        if self.runner:
            self.runner.stop()
        self.workers.cancel_group(self, "probe")
        self.is_scanning = False
        self._refresh_stats()

    def action_pause_resume(self) -> None:
        """Pause or resume running probes."""
        if not self.runner or not self.is_scanning:
            return
        if self.runner.is_paused:
            self.runner.resume()
            self.notify("Scan resumed", severity="information")
        else:
            self.runner.pause()
            self.notify("Scan paused", severity="information")
        self._refresh_stats()

    def action_clear(self) -> None:
        """Clear all scan results and reset statistics."""
        self.results.clear()
        self.stats = ScanStats()
        self.query_one("#stats-bar", StatsBar).reset()
        self._rebuild_table()

    def action_toggle_failures(self) -> None:
        cb = self.query_one("#hide_failures", Checkbox)
        cb.value = not cb.value

    def action_toggle_baseline(self) -> None:
        cb = self.query_one("#hide_baseline", Checkbox)
        cb.value = not cb.value

    def action_import_targets(self) -> None:
        """Open bulk target import modal."""
        def on_import(choice: tuple[str, list[str]] | None) -> None:
            if not choice:
                return
            target_type, items = choice
            panel_id = "#domains-panel" if target_type == "domains" else "#ips-panel"
            panel = self.query_one(panel_id, TargetListPanel)
            added = panel.add_bulk(items)
            self.notify(f"Added {added} {target_type}", severity="success")

        self.push_screen(BulkImportModal(), on_import)

    def action_export_results(self) -> None:
        """Open export modal."""
        if not self.results:
            self.notify("No results to export", severity="warning")
            return

        def on_export(choice: tuple[str, str] | None) -> None:
            if not choice:
                return
            path_str, fmt = choice
            try:
                out_path = export_results(self.results, path_str, fmt)
                self.notify(f"Exported {len(self.results)} results to {out_path}", severity="success")
            except Exception as e:
                self.notify(f"Export failed: {e}", severity="error")

        self.push_screen(ExportModal(), on_export)

    def action_delete_target(self) -> None:
        """Delete highlighted item in the focused target panel."""
        if isinstance(self.focused, OptionList):
            for panel_id in ("#domains-panel", "#ips-panel"):
                panel = self.query_one(panel_id, TargetListPanel)
                if panel.options is self.focused:
                    panel.delete_highlighted()
                    return

    def action_inspect_result(self) -> None:
        """Open detailed inspector for currently selected result row."""
        table = self.query_one("#results", DataTable)
        if not table.has_focus and not isinstance(self.focused, DataTable):
            # Focus table if not already focused
            table.focus()

        row_idx = table.cursor_row
        if row_idx is None or row_idx < 0:
            return

        # Map display row back to matching Result
        visible_results = [r for r in self.results if self._matches_filter(r)]
        if 0 <= row_idx < len(visible_results):
            self.push_screen(InspectorModal(visible_results[row_idx]))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_idx = event.cursor_row
        visible_results = [r for r in self.results if self._matches_filter(r)]
        if 0 <= row_idx < len(visible_results):
            self.push_screen(InspectorModal(visible_results[row_idx]))

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    # --- Results & Table Rendering ------------------------------------------

    def _matches_filter(self, res: Result) -> bool:
        if self.cfg.hide_failures and not res.ok:
            return False
        if self.cfg.hide_baseline and res.is_baseline:
            return False
        if not self.filter_query:
            return True

        q = self.filter_query
        return (
            q in res.domain.lower()
            or q in res.ip.lower()
            or q in str(res.code)
            or q in res.title.lower()
            or q in res.server.lower()
            or q in res.redirect.lower()
            or q in res.error.lower()
        )

    def _on_result_received(self, res: Result) -> None:
        self.results.append(res)
        if self._matches_filter(res):
            self._add_row(res)
        self._refresh_stats()

    def _add_row(self, res: Result) -> None:
        st = style_for(res)
        status_text = Text(res.status, style=st)
        table = self.query_one("#results", DataTable)
        table.add_row(
            res.domain,
            res.ip,
            str(res.port),
            res.scheme.upper(),
            status_text,
            res.title[:35],
            res.server[:20],
            "" if res.error else f"{res.size}B",
            "" if res.error else f"{res.seconds:.2f}s",
            res.redirect[:40],
        )

    def _rebuild_table(self) -> None:
        table = self.query_one("#results", DataTable)
        table.clear()
        for res in self.results:
            if self._matches_filter(res):
                self._add_row(res)
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        if not self.is_mounted:
            return
        is_paused = self.runner.is_paused if self.runner else False
        self.query_one("#stats-bar", StatsBar).update_stats(self.stats, self.is_scanning, is_paused)
        ans = self.stats.succeeded
        total = self.stats.total
        table = self.query_one("#results", DataTable)
        table.border_title = f"Results ({len(table.rows)} displayed, {ans} responded)" if total else "Results"
