"""Stats and progress bar widget for vheist."""

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Label, ProgressBar

from ..models import ScanStats


class StatsBar(Widget):
    """Real-time scan progress, throughput, and status breakdown."""

    DEFAULT_CSS = """
    StatsBar {
        height: 3;
        dock: top;
        background: $surface;
        padding: 0 1;
        border-bottom: solid $primary;
    }
    #stats-row {
        height: 3;
        align: left middle;
    }
    #progress {
        width: 25;
        margin-right: 2;
    }
    .stat-label {
        margin-right: 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="stats-row"):
            yield ProgressBar(id="progress", total=100, show_percentage=True, show_eta=False)
            yield Label("Idle", id="lbl-status", classes="stat-label")
            yield Label("0/0", id="lbl-jobs", classes="stat-label")
            yield Label("0.0 req/s", id="lbl-rate", classes="stat-label")
            yield Label("0.0s", id="lbl-time", classes="stat-label")
            yield Label("", id="lbl-badges", classes="stat-label")

    def update_stats(self, stats: ScanStats, is_running: bool, is_paused: bool) -> None:
        pbar = self.query_one("#progress", ProgressBar)
        lbl_status = self.query_one("#lbl-status", Label)
        lbl_jobs = self.query_one("#lbl-jobs", Label)
        lbl_rate = self.query_one("#lbl-rate", Label)
        lbl_time = self.query_one("#lbl-time", Label)
        lbl_badges = self.query_one("#lbl-badges", Label)

        if stats.total > 0:
            pbar.total = stats.total
            pbar.progress = stats.completed
        else:
            pbar.total = 100
            pbar.progress = 0

        if is_running:
            state_text = Text("PAUSED", style="bold yellow") if is_paused else Text("RUNNING", style="bold green")
        elif stats.completed > 0 and stats.completed >= stats.total:
            state_text = Text("FINISHED", style="bold cyan")
        else:
            state_text = Text("IDLE", style="dim")

        lbl_status.update(state_text)
        lbl_jobs.update(f"Jobs: {stats.completed}/{stats.total}")
        lbl_rate.update(f"{stats.rate:.1f} req/s")
        lbl_time.update(f"{stats.elapsed:.1f}s")

        # Status pills breakdown
        badges = Text()
        c2xx = sum(count for code, count in stats.codes.items() if 200 <= code < 300)
        c3xx = sum(count for code, count in stats.codes.items() if 300 <= code < 400)
        c4xx = sum(count for code, count in stats.codes.items() if 400 <= code < 500)
        c5xx = sum(count for code, count in stats.codes.items() if 500 <= code < 600)
        errs = stats.failed

        if c2xx:
            badges.append(f" 2xx:{c2xx} ", style="bold black on green")
            badges.append(" ")
        if c3xx:
            badges.append(f" 3xx:{c3xx} ", style="bold black on cyan")
            badges.append(" ")
        if c4xx:
            badges.append(f" 4xx:{c4xx} ", style="bold black on yellow")
            badges.append(" ")
        if c5xx:
            badges.append(f" 5xx:{c5xx} ", style="bold white on red")
            badges.append(" ")
        if errs:
            badges.append(f" Err:{errs} ", style="dim red")

        lbl_badges.update(badges)

    def reset(self) -> None:
        pbar = self.query_one("#progress", ProgressBar)
        pbar.total = 100
        pbar.progress = 0
        self.query_one("#lbl-status", Label).update(Text("IDLE", style="dim"))
        self.query_one("#lbl-jobs", Label).update("0/0")
        self.query_one("#lbl-rate", Label).update("0.0 req/s")
        self.query_one("#lbl-time", Label).update("0.0s")
        self.query_one("#lbl-badges", Label).update("")
