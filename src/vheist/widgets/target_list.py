"""Panel widget for managing target lists (Domains or IPs/CIDRs)."""

from collections.abc import Callable
from typing import Sequence

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, OptionList


class TargetListPanel(Vertical):
    """An interactive target list (OptionList) with add input and count badge."""

    DEFAULT_CSS = """
    TargetListPanel .panel-actions {
        height: 1;
        align: right middle;
        padding-right: 1;
        margin-top: 1;
    }
    TargetListPanel .panel-actions Button {
        height: 1;
        min-width: 8;
        padding: 0 1;
        border: none;
    }
    """

    def __init__(
        self,
        base_title: str,
        items: list[str],
        normalize: Callable[[str], str | list[str] | None],
        placeholder: str,
        on_change: Callable[[], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.base_title = base_title
        self.items = items
        self.normalize = normalize
        self.placeholder = placeholder
        self.on_change = on_change

    def compose(self) -> ComposeResult:
        yield OptionList(*self.items, id=f"{self.id}-options" if self.id else None)
        yield Input(placeholder=self.placeholder, id=f"{self.id}-input" if self.id else None)
        with Horizontal(classes="panel-actions"):
            yield Button("Clear", id=f"{self.id}-btn-clear" if self.id else "btn-clear", variant="error")

    def on_mount(self) -> None:
        self._refresh_title()

    @property
    def options(self) -> OptionList:
        return self.query_one(OptionList)

    @property
    def input_widget(self) -> Input:
        return self.query_one(Input)

    def _refresh_title(self) -> None:
        self.border_title = f"{self.base_title} ({len(self.items)})"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        val = event.value.strip()
        if not val:
            return

        normalized = self.normalize(val)
        if normalized is None or normalized == []:
            self.app.notify(f"Invalid format: {val!r}", severity="error")
            return

        candidates = [normalized] if isinstance(normalized, str) else normalized
        added = 0
        for cand in candidates:
            if cand not in self.items:
                self.items.append(cand)
                self.options.add_option(cand)
                added += 1

        event.input.value = ""
        self._refresh_title()
        if added > 0:
            if self.on_change:
                self.on_change()
        else:
            self.app.notify("Already in list", severity="warning")

    def delete_highlighted(self) -> None:
        idx = self.options.highlighted
        if idx is None or idx < 0 or idx >= len(self.items):
            return
        del self.items[idx]
        self.options.remove_option_at_index(idx)
        self._refresh_title()
        if self.on_change:
            self.on_change()

    def clear_all(self) -> None:
        self.items.clear()
        self.options.clear_options()
        self._refresh_title()
        if self.on_change:
            self.on_change()

    def add_bulk(self, candidates: Sequence[str]) -> int:
        added = 0
        for item in candidates:
            res = self.normalize(item)
            if res is None or res == []:
                continue
            to_add = [res] if isinstance(res, str) else res
            for clean_item in to_add:
                if clean_item not in self.items:
                    self.items.append(clean_item)
                    self.options.add_option(clean_item)
                    added += 1

        self._refresh_title()
        if added > 0 and self.on_change:
            self.on_change()
        return added

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if "btn-clear" in (event.button.id or ""):
            self.clear_all()
            self.app.notify(f"Cleared {self.base_title.lower()}", severity="information")
