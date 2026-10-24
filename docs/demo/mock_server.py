"""Two fake backends on 127.0.0.1:18080 and 127.0.0.2:18080 that route by Host header (used to render docs/demo.gif)."""
import http.server, threading, time, zlib

def page(title, body="", server="nginx/1.24.0"):
    html = f"<!doctype html><html><head><title>{title}</title></head><body><h1>{title}</h1>{body}</body></html>"
    return html.encode(), server

SITES = {
    "127.0.0.1": {  # public edge: a few real sites, internal ones fall through to the default
        "www.example.com":     (200, page("Example Corp - Home", "<p>Welcome</p>" * 40)),
        "api.example.com":     (200, page("API Gateway", "<pre>{}</pre>", "openresty")),
        "shop.example.com":    (200, page("Example Shop", "<p>Catalogue</p>" * 60, "Apache/2.4.58 (Ubuntu)")),
        "admin.example.com":   (302, ("", "nginx/1.24.0", "/login")),
        "mail.example.com":    (301, ("", "nginx/1.24.0", "https://mail.example.com/")),
        "old.example.com":     (404, page("404 Not Found", "", "nginx/1.24.0")),
    },
    "127.0.0.2": {  # internal ingress: the hidden stuff
        "www.example.com":     (200, page("Example Corp - Home", "<p>Welcome</p>" * 40)),
        "admin.example.com":   (200, page("Internal Admin Portal", "<form>login</form>" * 10, "Caddy")),
        "grafana.example.com": (200, page("Grafana", "<div>dashboards</div>" * 80, "Caddy")),
        "jenkins.example.com": (403, page("Authentication required", "", "Jetty(10.0.20)")),
        "git.example.com":     (200, page("Gitea: Git with a cup of tea", "<p>repos</p>" * 70, "Caddy")),
        "staging.example.com": (200, page("Staging - Example Corp", "<p>build 1482</p>" * 30, "nginx/1.24.0")),
        "vpn.example.com":     (503, page("Service Unavailable", "", "nginx/1.24.0")),
    },
}
DEFAULT = (404, page("Default Site", "<p>No such virtual host</p>", "nginx/1.24.0"))

def make(ip):
    table = SITES[ip]
    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *a): pass
        def do_GET(self):
            host = (self.headers.get("Host") or "").split(":")[0]
            status, payload = table.get(host, DEFAULT)
            body, server, *loc = payload
            body = body.encode() if isinstance(body, str) else body
            time.sleep(0.03 + (zlib.crc32(host.encode()) % 100) / 1000 + (0.08 if ip == '127.0.0.2' else 0))
            self.send_response(status)
            self.send_header("Server", server)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            if loc: self.send_header("Location", loc[0])
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers(); self.wfile.write(body)
    return http.server.ThreadingHTTPServer((ip, 18080), H)

for ip in SITES:
    threading.Thread(target=make(ip).serve_forever, daemon=True).start()
while True: time.sleep(3600)
