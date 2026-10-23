"""Data models for jobs, probe results, and scan statistics."""

from dataclasses import asdict, dataclass, field
import time


@dataclass(frozen=True)
class Job:
    """A target probing unit consisting of domain, IP, port, and scheme."""
    domain: str
    ip: str
    port: int
    scheme: str

    @property
    def target_key(self) -> str:
        return f"{self.scheme}://{self.domain}:{self.port}@{self.ip}"


@dataclass
class Result:
    """Outcome of probing a virtual host against a specific IP."""
    domain: str
    ip: str
    port: int
    scheme: str
    code: int | None = None
    size: int = 0
    seconds: float = 0.0
    redirect: str = ""
    title: str = ""
    server: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body_snippet: str = ""
    error: str = ""
    is_baseline: bool = False

    @property
    def ok(self) -> bool:
        """True if probe answered with an HTTP response (regardless of status code)."""
        return not self.error and self.code not in (None, 0)

    @property
    def status(self) -> str:
        """String representation of status code or error."""
        return self.error or str(self.code)

    @property
    def url(self) -> str:
        """Full URL targeted by the probe."""
        default_port = (self.scheme == "http" and self.port == 80) or (
            self.scheme == "https" and self.port == 443
        )
        port_part = "" if default_port else f":{self.port}"
        return f"{self.scheme}://{self.domain}{port_part}/"

    @property
    def curl_cmd(self) -> str:
        """Reproducible curl command."""
        return f"curl -k -sS -v --resolve {self.domain}:{self.port}:{self.ip} {self.url}"

    def line(self) -> str:
        """Single line representation for stdout or logs."""
        proto = f"{self.scheme}/{self.port}"
        if self.error:
            return f"{self.domain:<36} {self.ip:<16} {proto:<10} ERR: {self.error}"
        title_part = f" [{self.title[:30]}]" if self.title else ""
        redir_part = f" -> {self.redirect}" if self.redirect else ""
        server_part = f" ({self.server})" if self.server else ""
        return (
            f"{self.domain:<36} {self.ip:<16} {proto:<10} "
            f"{self.code} {self.size:>7}B {self.seconds:>5.2f}s"
            f"{server_part}{title_part}{redir_part}"
        )

    def to_dict(self) -> dict:
        """Dictionary representation for JSON serialization."""
        data = asdict(self)
        data["ok"] = self.ok
        data["url"] = self.url
        data["curl_cmd"] = self.curl_cmd
        return data


@dataclass
class ScanStats:
    """Running metrics and statistics for the current scan."""
    total: int = 0
    completed: int = 0
    succeeded: int = 0
    failed: int = 0
    codes: dict[int, int] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0

    def start(self, total: int) -> None:
        self.total = total
        self.completed = 0
        self.succeeded = 0
        self.failed = 0
        self.codes.clear()
        self.start_time = time.monotonic()
        self.end_time = 0.0

    def record(self, res: Result) -> None:
        self.completed += 1
        if res.ok:
            self.succeeded += 1
            if res.code:
                self.codes[res.code] = self.codes.get(res.code, 0) + 1
        else:
            self.failed += 1

    def finish(self) -> None:
        self.end_time = time.monotonic()

    @property
    def elapsed(self) -> float:
        if self.start_time == 0.0:
            return 0.0
        now = self.end_time or time.monotonic()
        return max(0.0, now - self.start_time)

    @property
    def rate(self) -> float:
        secs = self.elapsed
        return (self.completed / secs) if secs > 0 else 0.0

    @property
    def percent(self) -> float:
        return (self.completed / self.total * 100.0) if self.total > 0 else 0.0
