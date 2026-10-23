"""Run asynchronous curl probes for each (domain, ip, port, scheme) target."""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
import html
import re
from typing import TYPE_CHECKING

from .models import Job, Result, ScanStats

if TYPE_CHECKING:
    from .config import Config

WRITE_OUT_DELIMITER = "---VHEIST_METRICS---"
WRITE_OUT_FORMAT = f"\n{WRITE_OUT_DELIMITER}\n%{{http_code}} %{{size_download}} %{{time_total}} %{{redirect_url}}\n"

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_HEADER_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")


def parse_curl_output(raw_bytes: bytes) -> tuple[int | None, int, float, str, dict[str, str], str, str]:
    """Parse raw curl output containing HTTP response, body, and metrics delimiter.

    Returns: (code, size, seconds, redirect, headers, title, body_snippet)
    """
    text = raw_bytes.decode("latin1", errors="replace")

    headers: dict[str, str] = {}
    title = ""
    body_snippet = ""
    code: int | None = None
    size: int = 0
    seconds: float = 0.0
    redirect = ""

    if WRITE_OUT_DELIMITER in text:
        content, metrics = text.split(WRITE_OUT_DELIMITER, 1)
        m_parts = metrics.strip().split(maxsplit=3)
        if len(m_parts) >= 3:
            try:
                code = int(m_parts[0])
                size = int(m_parts[1])
                seconds = float(m_parts[2])
                redirect = m_parts[3].strip() if len(m_parts) > 3 else ""
            except (ValueError, IndexError):
                pass
    else:
        content = text

    # Split headers and body
    parts = re.split(r"\r?\n\r?\n", content, maxsplit=1)
    header_block = parts[0] if parts else ""
    body_part = parts[1] if len(parts) > 1 else ""

    # Parse HTTP response headers
    for line in header_block.splitlines():
        if m := _HEADER_RE.match(line):
            key = m.group(1).title()
            headers[key] = m.group(2).strip()

    # Extract title from body (or header block if unusual)
    if title_match := _TITLE_RE.search(content[:16384]):
        raw_title = title_match.group(1)
        clean_title = html.unescape(re.sub(r"\s+", " ", raw_title)).strip()
        title = clean_title[:120]

    body_snippet = body_part[:1000].strip()

    return code, size, seconds, redirect, headers, title, body_snippet


async def probe(
    domain: str,
    ip: str,
    scheme: str,
    port: int,
    timeout: float = 5.0,
    user_agent: str = "vheist/0.1.0",
) -> Result:
    """Probe a domain against an IP with curl, preserving Host header and TLS SNI."""
    url = f"{scheme}://{domain}:{port}/"
    cmd = [
        "curl",
        "-sS",
        "-k",
        "-i",
        "--max-time",
        str(timeout),
        "--resolve",
        f"{domain}:{port}:{ip}",
        "-A",
        user_agent,
        "--max-filesize",
        "5242880",  # 5MB safety limit
        "-w",
        WRITE_OUT_FORMAT,
        url,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return Result(domain, ip, port, scheme, error="curl executable not found")

    try:
        out, err = await proc.communicate()
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        raise

    if proc.returncode != 0 and not out:
        err_lines = err.decode(errors="replace").strip().splitlines()
        msg = err_lines[-1].removeprefix("curl: ") if err_lines else ""
        return Result(domain, ip, port, scheme, error=f"rc={proc.returncode} {msg}".strip())

    code, size, seconds, redirect, headers, title, body_snippet = parse_curl_output(out)
    server = headers.get("Server", "")

    return Result(
        domain=domain,
        ip=ip,
        port=port,
        scheme=scheme,
        code=code,
        size=size,
        seconds=seconds,
        redirect=redirect,
        title=title,
        server=server,
        headers=headers,
        body_snippet=body_snippet,
        error="" if (code and code > 0) else f"rc={proc.returncode}",
    )


def jobs(cfg: "Config") -> Iterator[Job]:
    """Generate all Job combinations from the active configuration."""
    for domain in cfg.domains:
        for ip in cfg.ips:
            for scheme, port in cfg.active_schemes_and_ports():
                yield Job(domain=domain, ip=ip, port=port, scheme=scheme)


class ProbeRunner:
    """Manages execution of probe jobs with concurrency, pause, and cancellation."""

    def __init__(self, cfg: "Config") -> None:
        self.cfg = cfg
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._stopped = False

    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def stop(self) -> None:
        self._stopped = True
        self._pause_event.set()

    async def run(
        self,
        on_result: Callable[[Result], Awaitable[None] | None],
        stats: ScanStats | None = None,
    ) -> None:
        """Run all jobs up to cfg.concurrency in parallel."""
        all_jobs = list(jobs(self.cfg))
        if stats:
            stats.start(len(all_jobs))

        sem = asyncio.Semaphore(self.cfg.concurrency)

        async def worker(job: Job) -> None:
            if self._stopped:
                return

            await self._pause_event.wait()
            if self._stopped:
                return

            async with sem:
                res = await probe(
                    domain=job.domain,
                    ip=job.ip,
                    scheme=job.scheme,
                    port=job.port,
                    timeout=self.cfg.timeout,
                    user_agent=self.cfg.user_agent,
                )

            if stats:
                stats.record(res)

            maybe = on_result(res)
            if maybe is not None:
                await maybe

        try:
            async with asyncio.TaskGroup() as tg:
                for job in all_jobs:
                    if self._stopped:
                        break
                    tg.create_task(worker(job))
        finally:
            if stats:
                stats.finish()


async def run_all(
    cfg: "Config",
    on_result: Callable[[Result], Awaitable[None] | None],
    stats: ScanStats | None = None,
) -> None:
    """Convenience helper to run all probes to completion."""
    runner = ProbeRunner(cfg)
    await runner.run(on_result, stats)
