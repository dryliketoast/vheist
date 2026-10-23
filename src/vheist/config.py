"""Persistent configuration, saved to disk on every change."""

from dataclasses import asdict, dataclass, field, fields
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile

ENV_VAR = "VHEIST_CONFIG"

_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)([a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?)(\.[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?)*$"
)


def default_path() -> Path:
    if env := os.environ.get(ENV_VAR):
        return Path(env).expanduser()
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "vheist" / "config.json"


def normalize_domain(text: str) -> str | None:
    """Return a clean hostname, or None if `text` isn't one."""
    value = text.strip().lower().rstrip(".")
    return value if _HOSTNAME.match(value) else None


def normalize_ip_or_cidr(text: str, max_cidr_hosts: int = 256) -> list[str]:
    """Parse a single IP or CIDR range (e.g. 192.168.1.0/29).

    Expands CIDR notation up to `max_cidr_hosts` to prevent accidental resource exhaustion.
    """
    clean = text.strip()
    if not clean:
        return []

    # Check for single IP address first
    try:
        addr = ipaddress.ip_address(clean)
        return [str(addr)]
    except ValueError:
        pass

    # Check for CIDR network
    try:
        net = ipaddress.ip_network(clean, strict=False)
        # Avoid exploding huge ranges (e.g. /16 or /8)
        if net.num_addresses > max_cidr_hosts:
            return []
        # Return usable host addresses (for /31 or /32, returns addresses themselves)
        hosts = list(net.hosts()) if net.num_addresses > 2 else list(net)
        return [str(h) for h in hosts]
    except ValueError:
        return []


def normalize_port(value: str | int) -> int | None:
    """Validate TCP port number in range 1-65535."""
    try:
        p = int(value)
        return p if 1 <= p <= 65535 else None
    except (ValueError, TypeError):
        return None


@dataclass
class Config:
    # Starts completely empty by default; remembers last state on save
    domains: list[str] = field(default_factory=list)
    ips: list[str] = field(default_factory=list)
    http: bool = True
    https: bool = True
    port_http: int = 80
    port_https: int = 443
    timeout: float = 5.0
    concurrency: int = 8
    hide_failures: bool = False
    hide_baseline: bool = False
    user_agent: str = "vheist/0.1.0"
    path: Path = field(default_factory=default_path, repr=False, compare=False)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load from `path`; missing or unreadable file yields clean defaults (empty targets)."""
        path = path or default_path()
        cfg = cls(path=path)
        try:
            raw = json.loads(path.read_text())
        except (OSError, ValueError):
            return cfg
        if not isinstance(raw, dict):
            return cfg

        for f in fields(cls):
            if f.name == "path" or f.name not in raw:
                continue
            val = raw[f.name]
            default_val = getattr(cfg, f.name)
            if isinstance(val, type(default_val)):
                setattr(cfg, f.name, val)
            elif f.name == "timeout" and isinstance(val, (int, float)):
                cfg.timeout = float(val)

        cfg.timeout = max(0.5, float(cfg.timeout))
        cfg.concurrency = max(1, int(cfg.concurrency))
        cfg.port_http = normalize_port(cfg.port_http) or 80
        cfg.port_https = normalize_port(cfg.port_https) or 443
        return cfg

    def save(self) -> None:
        """Atomically write the configuration to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        del data["path"]
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".config-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def active_schemes_and_ports(self) -> list[tuple[str, int]]:
        """Return enabled (scheme, port) pairs."""
        pairs = []
        if self.http:
            pairs.append(("http", self.port_http))
        if self.https:
            pairs.append(("https", self.port_https))
        return pairs
