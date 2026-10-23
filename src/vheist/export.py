"""Export scan results to CSV, JSON, Markdown, or text files."""

import csv
import json
from pathlib import Path
from typing import Sequence

from .models import Result


def to_csv(results: Sequence[Result]) -> str:
    """Format results as a CSV string."""
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Domain", "IP", "Port", "Scheme", "Status", "Code", "Size", "TimeSeconds",
        "Title", "Server", "Redirect", "URL", "Error", "CurlCommand"
    ])
    for r in results:
        writer.writerow([
            r.domain, r.ip, r.port, r.scheme, r.status, r.code or "", r.size,
            f"{r.seconds:.3f}", r.title, r.server, r.redirect, r.url, r.error, r.curl_cmd
        ])
    return output.getvalue()


def to_json(results: Sequence[Result], indent: int = 2) -> str:
    """Format results as a JSON string."""
    return json.dumps([r.to_dict() for r in results], indent=indent)


def to_markdown(results: Sequence[Result]) -> str:
    """Format results as a Markdown table."""
    lines = [
        "| Domain | IP | Proto | Status | Title | Server | Size | Time | Redirect |",
        "|--------|----|-------|--------|-------|--------|------|------|----------|"
    ]
    for r in results:
        proto = f"{r.scheme}/{r.port}"
        title = r.title.replace("|", "/")
        server = r.server.replace("|", "/")
        lines.append(
            f"| `{r.domain}` | `{r.ip}` | {proto} | **{r.status}** | {title} | {server} | {r.size}B | {r.seconds:.2f}s | {r.redirect} |"
        )
    return "\n".join(lines) + "\n"


def to_text(results: Sequence[Result]) -> str:
    """Format results as plain text lines."""
    return "\n".join(r.line() for r in results) + "\n"


def export_results(results: Sequence[Result], path: Path | str, fmt: str = "json") -> Path:
    """Write results to a file in the chosen format (json, csv, md, txt)."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    fmt_lower = fmt.lower().strip(".")

    if fmt_lower == "csv":
        content = to_csv(results)
    elif fmt_lower in ("md", "markdown"):
        content = to_markdown(results)
    elif fmt_lower in ("txt", "text"):
        content = to_text(results)
    else:  # default json
        content = to_json(results)

    p.write_text(content, encoding="utf-8")
    return p
