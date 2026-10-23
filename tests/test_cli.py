from pathlib import Path
from unittest.mock import MagicMock, patch

from vheist.__main__ import parse_args, run_headless
from vheist.config import Config
from vheist.models import Result


def test_parse_args():
    args = parse_args(["--run", "--format", "json", "--export", "out.json"])
    assert args.run is True
    assert args.format == "json"
    assert args.export == Path("out.json")


def test_run_headless_empty_targets_returns_error(tmp_path: Path):
    cfg = Config(path=tmp_path / "c.json", domains=[], ips=[])
    rc = run_headless(cfg)
    assert rc == 1


def test_run_headless_with_targets(tmp_path: Path, capsys):
    cfg = Config(path=tmp_path / "c.json", domains=["example.test"], ips=["127.0.0.1"], https=False)
    fake_res = Result("example.test", "127.0.0.1", 80, "http", 200, 50, 0.01, title="OK")

    with patch("vheist.probe.probe", return_value=fake_res):
        rc = run_headless(cfg, fmt="text")
        assert rc == 0
        captured = capsys.readouterr()
        assert "example.test" in captured.out
        assert "200" in captured.out


def test_run_headless_export_file(tmp_path: Path):
    cfg = Config(path=tmp_path / "c.json", domains=["export.test"], ips=["127.0.0.1"], https=False)
    fake_res = Result("export.test", "127.0.0.1", 80, "http", 200, 100, 0.05, title="Exported")
    export_file = tmp_path / "out.csv"

    with patch("vheist.probe.probe", return_value=fake_res):
        rc = run_headless(cfg, export_path=export_file, fmt="csv")
        assert rc == 0
        assert export_file.exists()
        assert "export.test" in export_file.read_text()
