"""Modal screens for inspector, bulk import, export, and help."""

from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Markdown, RadioButton, RadioSet, TextArea

from ..models import Result


class HelpModal(ModalScreen):
    """Modal displaying quick help, keybindings, and tips."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    #help-dialog {
        width: 75;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #help-actions {
        height: 3;
        align: right middle;
        margin-top: 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    HELP_MARKDOWN = """
# vheist - Virtual Host Discovery & Prober

Probe every subdomain against every endpoint IP using `curl` with `--resolve`, verifying Host headers and TLS SNI.

### Keybindings

| Key | Action |
|-----|--------|
| `r` | Run / restart scan |
| `s` | Stop active scan |
| `p` | Pause / resume active scan |
| `c` | Clear results table |
| `f` | Toggle hiding failed/timed-out probes |
| `i` | Bulk import targets (paste wordlists or CIDRs) |
| `e` | Export results (JSON, CSV, Markdown, Text) |
| `Enter` | Inspect highlighted result row |
| `Delete` | Remove highlighted item in focused list |
| `Tab` | Navigate between lists, inputs, and settings |
| `?` | Show this help dialog |
| `q` | Quit application |

### Probing Logic & Config
- Uses `curl --resolve domain:port:ip scheme://domain:port/`
- Certificate errors are ignored (`-k`)
- Headers, Page Titles, and Server types are automatically extracted
- Configuration autosaves to `~/.config/vheist/config.json`
"""

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            with VerticalScroll():
                yield Markdown(self.HELP_MARKDOWN)
            with Horizontal(id="help-actions"):
                yield Button("Close", variant="primary", id="btn-close-help")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-help":
            self.dismiss()


class InspectorModal(ModalScreen):
    """Modal displaying detailed response information for a single result."""

    DEFAULT_CSS = """
    InspectorModal {
        align: center middle;
    }
    #inspect-dialog {
        width: 85;
        height: 85%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    .field-row {
        height: 2;
        margin-bottom: 0;
    }
    .field-label {
        width: 14;
        text-style: bold;
        color: $accent;
    }
    .field-value {
        width: 1fr;
    }
    .section-title {
        text-style: bold underline;
        margin-top: 1;
        margin-bottom: 1;
        color: $primary;
    }
    #curl-box {
        background: $panel;
        padding: 1;
        border: round $primary;
        height: 5;
    }
    #headers-box {
        background: $panel;
        padding: 1;
        height: 10;
        border: round $primary;
    }
    #snippet-box {
        background: $panel;
        padding: 1;
        height: 10;
        border: round $primary;
    }
    #inspect-actions {
        height: 3;
        align: right middle;
        margin-top: 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    def __init__(self, result: Result, **kwargs) -> None:
        super().__init__(**kwargs)
        self.res = result

    def compose(self) -> ComposeResult:
        with Vertical(id="inspect-dialog"):
            with VerticalScroll():
                with Horizontal(classes="field-row"):
                    yield Label("Target URL:", classes="field-label")
                    yield Label(self.res.url, classes="field-value")

                with Horizontal(classes="field-row"):
                    yield Label("Endpoint IP:", classes="field-label")
                    yield Label(f"{self.res.ip}:{self.res.port}", classes="field-value")

                with Horizontal(classes="field-row"):
                    yield Label("Status:", classes="field-label")
                    st_style = "bold green" if self.res.ok else "bold red"
                    yield Label(Text(self.res.status, style=st_style), classes="field-value")

                with Horizontal(classes="field-row"):
                    yield Label("Metrics:", classes="field-label")
                    yield Label(f"{self.res.size} Bytes | {self.res.seconds:.3f} seconds", classes="field-value")

                if self.res.title:
                    with Horizontal(classes="field-row"):
                        yield Label("HTML Title:", classes="field-label")
                        yield Label(self.res.title, classes="field-value")

                if self.res.server:
                    with Horizontal(classes="field-row"):
                        yield Label("Server:", classes="field-label")
                        yield Label(self.res.server, classes="field-value")

                if self.res.redirect:
                    with Horizontal(classes="field-row"):
                        yield Label("Redirect:", classes="field-label")
                        yield Label(self.res.redirect, classes="field-value")

                yield Label("Reproduce Command:", classes="section-title")
                yield TextArea(self.res.curl_cmd, id="curl-box", read_only=True)

                if self.res.headers:
                    yield Label("HTTP Response Headers:", classes="section-title")
                    headers_txt = "\n".join(f"{k}: {v}" for k, v in self.res.headers.items())
                    yield TextArea(headers_txt, id="headers-box", read_only=True)

                if self.res.body_snippet:
                    yield Label("Body Preview:", classes="section-title")
                    yield TextArea(self.res.body_snippet, id="snippet-box", read_only=True)

            with Horizontal(id="inspect-actions"):
                yield Button("Copy Curl", id="btn-copy-curl", variant="default")
                yield Button("Close", id="btn-close-inspect", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-inspect":
            self.dismiss()
        elif event.button.id == "btn-copy-curl":
            try:
                self.app.copy_to_clipboard(self.res.curl_cmd)
                self.app.notify("Curl command copied to clipboard", severity="information")
            except Exception:
                self.app.notify("Clipboard unavailable in current terminal", severity="warning")


class BulkImportModal(ModalScreen[tuple[str, list[str]] | None]):
    """Modal for importing multiple targets or wordlists at once."""

    DEFAULT_CSS = """
    BulkImportModal {
        align: center middle;
    }
    #import-dialog {
        width: 75;
        height: 75%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #target-choice {
        height: 3;
        margin-bottom: 1;
    }
    #import-area {
        height: 1fr;
        border: round $primary;
    }
    #import-file-row {
        height: 3;
        margin-top: 1;
    }
    #import-file-row Input {
        width: 1fr;
        margin-right: 1;
    }
    #import-actions {
        height: 3;
        align: right middle;
        margin-top: 1;
    }
    #import-actions Button {
        margin-left: 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="import-dialog"):
            yield Label("Select Target Destination:")
            with RadioSet(id="target-choice"):
                yield RadioButton("Domains", value=True, id="radio-domains")
                yield RadioButton("Endpoint IPs / CIDRs", id="radio-ips")

            yield Label("Paste lines or load from a wordlist file:")
            yield TextArea(id="import-area")

            with Horizontal(id="import-file-row"):
                yield Input(placeholder="/path/to/wordlist.txt", id="input-filepath")
                yield Button("Load File", id="btn-load-file")

            with Horizontal(id="import-actions"):
                yield Button("Cancel", id="btn-cancel-import", variant="error")
                yield Button("Import", id="btn-do-import", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-import":
            self.dismiss(None)
        elif event.button.id == "btn-load-file":
            filepath = self.query_one("#input-filepath", Input).value.strip()
            if not filepath:
                self.app.notify("Enter a file path first", severity="warning")
                return
            p = Path(filepath).expanduser()
            if not p.is_file():
                self.app.notify(f"File not found: {filepath}", severity="error")
                return
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                self.query_one("#import-area", TextArea).text = content
                self.app.notify(f"Loaded {len(content.splitlines())} lines", severity="information")
            except Exception as e:
                self.app.notify(f"Error reading file: {e}", severity="error")
        elif event.button.id == "btn-do-import":
            text = self.query_one("#import-area", TextArea).text
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if not lines:
                self.app.notify("Nothing to import", severity="warning")
                return
            radio_domains = self.query_one("#radio-domains", RadioButton)
            target_type = "domains" if radio_domains.value else "ips"
            self.dismiss((target_type, lines))

    def action_cancel(self) -> None:
        self.dismiss(None)


class ExportModal(ModalScreen[tuple[str, str] | None]):
    """Modal for exporting scan results."""

    DEFAULT_CSS = """
    ExportModal {
        align: center middle;
    }
    #export-dialog {
        width: 65;
        height: 22;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #format-choice {
        height: 4;
        margin-bottom: 1;
    }
    #export-actions {
        height: 3;
        align: right middle;
        margin-top: 1;
    }
    #export-actions Button {
        margin-left: 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="export-dialog"):
            yield Label("Export Format:")
            with RadioSet(id="format-choice"):
                yield RadioButton("JSON", value=True, id="fmt-json")
                yield RadioButton("CSV", id="fmt-csv")
                yield RadioButton("Markdown Table", id="fmt-md")
                yield RadioButton("Plain Text Lines", id="fmt-txt")

            yield Label("Destination Path:")
            yield Input(value="./vheist-results.json", id="input-export-path")

            with Horizontal(id="export-actions"):
                yield Button("Cancel", id="btn-cancel-export", variant="error")
                yield Button("Export", id="btn-do-export", variant="success")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        path_input = self.query_one("#input-export-path", Input)
        base = Path(path_input.value).stem or "vheist-results"
        fmt_id = event.pressed.id
        ext_map = {"fmt-json": ".json", "fmt-csv": ".csv", "fmt-md": ".md", "fmt-txt": ".txt"}
        path_input.value = f"./{base}{ext_map.get(fmt_id, '.json')}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-export":
            self.dismiss(None)
        elif event.button.id == "btn-do-export":
            path_val = self.query_one("#input-export-path", Input).value.strip()
            if not path_val:
                self.app.notify("Specify an export path", severity="error")
                return
            radio_id = self.query_one("#format-choice", RadioSet).pressed_button.id
            fmt_map = {"fmt-json": "json", "fmt-csv": "csv", "fmt-md": "md", "fmt-txt": "txt"}
            fmt = fmt_map.get(radio_id, "json")
            self.dismiss((path_val, fmt))

    def action_cancel(self) -> None:
        self.dismiss(None)
