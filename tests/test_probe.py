import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

import pytest

from vheist.config import Config
from vheist.models import Job, Result
from vheist.probe import jobs, parse_curl_output, probe, run_all


class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        host = self.headers.get("Host", "").split(":")[0]
        if host == "special.test":
            body = b"<html><head><title>Top Secret Portal</title></head><body>Welcome</body></html>"
            self.send_response(200)
            self.send_header("Server", "VheistServer/1.0")
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif host == "redir.test":
            self.send_response(301)
            self.send_header("Location", "https://special.test/")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            body = b"Not found"
            self.send_response(404)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def mock_server():
    srv = HTTPServer(("127.0.0.1", 0), DummyHandler)
    port = srv.server_port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield port
    srv.shutdown()


def test_parse_curl_output():
    raw = (
        b"HTTP/1.1 200 OK\r\n"
        b"Server: nginx/1.24\r\n"
        b"Content-Type: text/html\r\n"
        b"\r\n"
        b"<html><head><title>Hello &amp; Welcome</title></head><body>content</body></html>\n"
        b"---VHEIST_METRICS---\n"
        b"200 85 0.042 \n"
    )
    code, size, seconds, redirect, headers, title, body = parse_curl_output(raw)
    assert code == 200
    assert size == 85
    assert seconds == 0.042
    assert headers.get("Server") == "nginx/1.24"
    assert title == "Hello & Welcome"
    assert "content" in body


async def test_probe_extracts_title_and_server(mock_server):
    res = await probe("special.test", "127.0.0.1", "http", mock_server, timeout=2.0)
    assert res.ok
    assert res.code == 200
    assert res.server == "VheistServer/1.0"
    assert res.title == "Top Secret Portal"
    assert "special.test" in res.curl_cmd


async def test_probe_tracks_redirect(mock_server):
    res = await probe("redir.test", "127.0.0.1", "http", mock_server, timeout=2.0)
    assert res.ok
    assert res.code == 301
    assert res.redirect == "https://special.test/"


async def test_probe_connection_failure():
    # Attempt connecting to invalid closed port
    res = await probe("unknown.test", "127.0.0.1", "http", 1, timeout=1.0)
    assert not res.ok
    assert "rc=" in res.error


async def test_jobs_generation():
    cfg = Config(
        domains=["one.test", "two.test"],
        ips=["10.0.0.1", "10.0.0.2"],
        http=True,
        https=True,
        port_http=8080,
        port_https=8443,
    )
    generated = list(jobs(cfg))
    assert len(generated) == 8
    assert Job("one.test", "10.0.0.1", 8080, "http") in generated
    assert Job("two.test", "10.0.0.2", 8443, "https") in generated
