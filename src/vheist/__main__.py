"""Command-line entrypoint for vheist."""

import argparse
import asyncio
from pathlib import Path
import sys

from .config import Config
from .export import export_results
from .models import Result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="vheist",
        description="High-speed virtual host discovery and probing TUI.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="path to config file (default: ~/.config/vheist/config.json)",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="headless mode: probe targets using configuration and print results to stdout",
    )
    parser.add_argument(
        "--export",
        type=Path,
        help="in --run mode: export results to specified file path",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "csv", "md"],
        default="text",
        help="output format for headless run or export (default: text)",
    )
    return parser.parse_args(argv)


def run_headless(cfg: Config, export_path: Path | None = None, fmt: str = "text") -> int:
    """Run probe scan in headless CLI mode."""
    from .probe import jobs, run_all

    all_jobs = list(jobs(cfg))
    if not all_jobs:
        print(
            "Error: No targets configured. Add domains and IPs in the TUI or config file.",
            file=sys.stderr,
        )
        return 1

    print(f"[*] vheist starting headless probe of {len(all_jobs)} combinations...", file=sys.stderr)
    results: list[Result] = []

    def on_result(res: Result) -> None:
        results.append(res)
        if fmt == "text":
            print(res.line(), flush=True)

    asyncio.run(run_all(cfg, on_result))

    if fmt == "json" and not export_path:
        from .export import to_json
        print(to_json(results))
    elif fmt == "csv" and not export_path:
        from .export import to_csv
        print(to_csv(results))
    elif fmt == "md" and not export_path:
        from .export import to_markdown
        print(to_markdown(results))

    if export_path:
        out = export_results(results, export_path, fmt)
        print(f"[*] Exported {len(results)} results to {out}", file=sys.stderr)

    return 0


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    cfg = Config.load(args.config)

    if args.run:
        sys.exit(run_headless(cfg, args.export, args.format))
    else:
        from .app import VhostHeist

        app = VhostHeist(cfg)
        app.run()


if __name__ == "__main__":
    main()
