import json
from pathlib import Path

from vheist.config import (
    Config,
    normalize_domain,
    normalize_ip_or_cidr,
    normalize_port,
)


def test_fresh_config_starts_empty(tmp_path: Path):
    cfg = Config.load(tmp_path / "nonexistent.json")
    assert cfg.domains == []
    assert cfg.ips == []
    assert cfg.http is True
    assert cfg.https is True
    assert cfg.port_http == 80
    assert cfg.port_https == 443
    assert cfg.timeout == 5.0
    assert cfg.concurrency == 8


def test_roundtrip_save_and_load(tmp_path: Path):
    p = tmp_path / "sub" / "config.json"
    cfg = Config(
        path=p,
        domains=["alpha.test", "beta.test"],
        ips=["10.0.0.1", "10.0.0.2"],
        http=False,
        https=True,
        port_https=8443,
        timeout=3.5,
        concurrency=16,
    )
    cfg.save()
    loaded = Config.load(p)
    assert loaded == cfg
    assert loaded.domains == ["alpha.test", "beta.test"]
    assert loaded.ips == ["10.0.0.1", "10.0.0.2"]
    assert loaded.active_schemes_and_ports() == [("https", 8443)]


def test_corrupt_file_handled_gracefully(tmp_path: Path):
    p = tmp_path / "broken.json"
    p.write_text("{invalid-json-content")
    cfg = Config.load(p)
    assert cfg.domains == []
    assert cfg.ips == []

    p.write_text(json.dumps({"domains": "not-a-list", "concurrency": -5, "timeout": "bad"}))
    cfg2 = Config.load(p)
    assert isinstance(cfg2.domains, list)
    assert cfg2.concurrency == 1
    assert cfg2.timeout == 5.0  # falls back to default


def test_normalize_domain():
    assert normalize_domain(" SUB.EXAMPLE.COM. ") == "sub.example.com"
    assert normalize_domain("test-host_1.internal") == "test-host_1.internal"
    assert normalize_domain("not a domain!") is None
    assert normalize_domain("") is None


def test_normalize_ip_or_cidr():
    assert normalize_ip_or_cidr("  127.0.0.1  ") == ["127.0.0.1"]
    assert normalize_ip_or_cidr("::1") == ["::1"]

    # CIDR /30 gives 2 usable host addresses
    expanded = normalize_ip_or_cidr("192.168.1.0/30")
    assert expanded == ["192.168.1.1", "192.168.1.2"]

    # Huge networks are capped/rejected to protect system resources
    assert normalize_ip_or_cidr("10.0.0.0/8") == []
    assert normalize_ip_or_cidr("invalid-ip") == []


def test_normalize_port():
    assert normalize_port(80) == 80
    assert normalize_port("443") == 443
    assert normalize_port(65535) == 65535
    assert normalize_port(0) is None
    assert normalize_port(70000) is None
    assert normalize_port("not-a-port") is None
