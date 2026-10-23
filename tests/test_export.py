import json
from pathlib import Path

from vheist.export import export_results, to_csv, to_json, to_markdown, to_text
from vheist.models import Result


def sample_results() -> list[Result]:
    return [
        Result(
            domain="admin.example.com",
            ip="10.0.0.1",
            port=443,
            scheme="https",
            code=200,
            size=1500,
            seconds=0.12,
            title="Admin Login",
            server="nginx/1.24",
        ),
        Result(
            domain="dev.example.com",
            ip="10.0.0.2",
            port=80,
            scheme="http",
            code=302,
            size=0,
            seconds=0.05,
            redirect="https://dev.example.com/",
        ),
        Result(
            domain="down.example.com",
            ip="10.0.0.3",
            port=80,
            scheme="http",
            error="rc=7 Connection refused",
        ),
    ]


def test_to_csv():
    csv_str = to_csv(sample_results())
    lines = csv_str.strip().splitlines()
    assert len(lines) == 4  # Header + 3 rows
    assert "admin.example.com" in lines[1]
    assert "10.0.0.1" in lines[1]
    assert "Admin Login" in lines[1]


def test_to_json():
    json_str = to_json(sample_results())
    data = json.loads(json_str)
    assert len(data) == 3
    assert data[0]["domain"] == "admin.example.com"
    assert data[0]["code"] == 200
    assert data[0]["ok"] is True
    assert data[2]["ok"] is False


def test_to_markdown():
    md = to_markdown(sample_results())
    assert "| `admin.example.com` | `10.0.0.1` |" in md
    assert "**200**" in md


def test_to_text():
    txt = to_text(sample_results())
    assert "admin.example.com" in txt
    assert "ERR: rc=7" in txt


def test_export_results_file(tmp_path: Path):
    out_file = tmp_path / "exports" / "scan.csv"
    res_path = export_results(sample_results(), out_file, fmt="csv")
    assert res_path.exists()
    assert "admin.example.com" in res_path.read_text()
