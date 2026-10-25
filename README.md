# vheist

**High-speed virtual host discovery and probing TUI.** Probe subdomains, hostnames, and wordlists against target IP addresses using `curl --resolve`, extracting HTTP response headers, server banners, and page titles in real time.

![vheist demo](docs/demo.gif)

---

## Overview

Modern web infrastructures, load balancers, and reverse proxies (such as Nginx, Traefik, HAProxy, Envoy, and Cloudflare) frequently host multiple virtual hosts on shared IP addresses. Discovering hidden, staging, or internal virtual hosts often requires querying an IP address while requesting a specific domain in the HTTP `Host:` header and TLS SNI extension.

`vheist` automates and streamlines this reconnaissance process through an interactive, keyboard-driven Terminal User Interface (TUI) powered by Textual.

For each target combination of `(domain, IP, port, scheme)`, `vheist` executes:

```bash
curl -k -sS -i --resolve <domain>:<port>:<ip> <scheme>://<domain>:<port>/
```

This guarantees:
1. The TCP/TLS connection is established directly to the specified target IP (bypassing public DNS).
2. The TLS SNI (Server Name Indication) extension carries the domain name during the handshake.
3. The HTTP `Host:` header matches the virtual host being probed.
4. SSL/TLS certificate warnings are safely bypassed (`-k`).
5. HTTP response headers, redirects, server banners, and `<title>` tags are captured and analyzed.

---

## Features

### 🔍 Response Intelligence & Page Titles
- **Automatic `<title>` Extraction**: Quickly identify hidden internal portals, login screens, and admin dashboards (e.g., `<title>Internal Admin Portal</title>` vs. generic 404/default landing pages).
- **Server Banner Capture**: Extracts the `Server:` response header (e.g., `nginx/1.24`, `openresty`, `Apache`, `Microsoft-IIS/10.0`, `Cloudflare`).
- **Redirect Tracking**: Follows and displays HTTP `Location:` targets on 301/302 redirects.
- **Detailed Metrics**: Monitors response byte size, status codes, and latency in seconds.

### 🖥️ Rich Interactive Textual TUI
- **Live Metrics Bar**:
  - Embedded `ProgressBar` displaying real-time scan progress.
  - Active scan status (`IDLE`, `RUNNING`, `PAUSED`, `FINISHED`).
  - Real-time throughput counter (`req/s`) and elapsed timer.
  - Color-coded HTTP status breakdown badges (`2xx`, `3xx`, `4xx`, `5xx`, `Err`).
- **Target Management**:
  - Separate panels for **Domains** and **Endpoint IPs / CIDRs** with dynamic item counters.
  - Compact `Clear` buttons and `Delete` key support for individual item removal.
- **Interactive DataTable**:
  - Color-coded status pills: `2xx` (green), `3xx` (cyan), `4xx` (yellow), `5xx` (red), errors (dim red).
  - Zebra striping and row cursor navigation.
- **Live Search & Filtering**:
  - Instant text filter bar matching domains, IPs, status codes, page titles, servers, or errors.
  - One-key toggle for hiding failed probes (`f`).

### 🎯 CIDR & Target Expansion
- **CIDR Subnet Expansion**: Input network ranges like `192.168.1.0/29` or `192.168.2.0/30` directly—`vheist` automatically expands them into individual host IP addresses.
- **Wordlist & Bulk Import (`i`)**: Open the Bulk Import modal to paste multi-line domain or IP lists, or load large wordlist files from disk.

### 🔬 Result Inspector (`Enter`)
- Press `Enter` on any result row to view full request and response details:
  - Target URL and resolved IP/port.
  - Full HTTP response headers.
  - Body snippet preview.
  - **Copyable curl reproduction command**: One-click copy or copyable command to instantly replay the exact probe in your terminal.

### 💾 Persistent Autosave
- **Starts Empty**: On fresh installations, `vheist` starts with clean target lists (`domains = []`, `ips = []`) without cluttering dummy data.
- **State Memory**: Automatically saves and reloads targets, custom ports (e.g., 8080, 8443), timeouts, concurrency, and toggles to `~/.config/vheist/config.json` on every change.

### 📤 Multi-Format Export (`e`)
- Export scan results directly to:
  - **JSON**: Full structured data with metrics, headers, and curl commands.
  - **CSV**: Spreadsheet-compatible format with all metrics.
  - **Markdown**: Pre-formatted Markdown table ready for reports or bug bounty submissions.
  - **Plain Text**: Standard one-line output format.

### ⚡ Automation & Headless Mode
- Execute headless scans directly in CI/CD pipelines, bash scripts, or scheduled cron jobs using `vheist --run`.

---

## Installation

### Using `uv` (Recommended)

Run directly without manual installation:
```bash
uv run vheist
```

Install as a global user tool:
```bash
uv tool install .
```

### From Source

Clone the repository and sync dependencies:
```bash
git clone <repository-url>/vheist.git
cd vheist
uv sync
```

---

## Usage

### Interactive TUI

Launch the full graphical terminal application:
```bash
uv run vheist
```

### Headless / CLI Mode

Probe targets using the current saved configuration and stream results to `stdout`:
```bash
uv run vheist --run
```

Output formatted JSON directly to stdout:
```bash
uv run vheist --run --format json
```

Export scan results directly to file:
```bash
# Export to CSV
uv run vheist --run --export results.csv --format csv

# Export to Markdown table
uv run vheist --run --export report.md --format md

# Export to JSON
uv run vheist --run --export targets.json --format json
```

Specify a custom configuration file:
```bash
uv run vheist --config /path/to/custom-config.json
```

---

## Keyboard Shortcuts

| Key | Action | Description |
|:---:|:---|:---|
| `r` | **Run** | Start or restart probing all target combinations |
| `s` | **Stop** | Stop the active probe worker |
| `p` | **Pause / Resume** | Temporarily pause active probe workers and resume |
| `c` | **Clear** | Clear results table and reset scan statistics |
| `f` | **Toggle Failures** | Hide or show failed/timed-out probes |
| `i` | **Import** | Open Bulk Import modal (paste wordlists or load file) |
| `e` | **Export** | Open Export modal (JSON, CSV, Markdown, Text) |
| `Enter` | **Inspect** | View detailed inspector dialog for selected row |
| `Delete`| **Delete Target** | Remove highlighted target from focused list |
| `Tab` | **Navigate** | Move focus between lists, input fields, and settings |
| `?` | **Help** | Open interactive help dialog |
| `q` | **Quit** | Exit `vheist` |

---

## Configuration

Settings and targets are stored in standard JSON format:

```json
{
  "domains": [
    "origin.example.com",
    "staging.example.com"
  ],
  "ips": [
    "192.168.1.8",
    "192.168.1.80"
  ],
  "http": true,
  "https": true,
  "port_http": 80,
  "port_https": 443,
  "timeout": 5.0,
  "concurrency": 8,
  "hide_failures": false,
  "user_agent": "vheist/0.1.0"
}
```

### Storage Location
- Default: `~/.config/vheist/config.json`
- Respects `$XDG_CONFIG_HOME/vheist/config.json` if set.
- Override with the `$VHEIST_CONFIG` environment variable or `--config <path>` flag.

---

## Project Structure

```
vheist/
├── pyproject.toml         # Build definition (uv_build backend, textual, pytest)
├── uv.lock                # Dependency lockfile
├── .python-version        # Target Python version (3.13)
├── .gitignore             # Git ignore rules
├── README.md              # Documentation
├── src/
│   └── vheist/
│       ├── __init__.py    # Version metadata
│       ├── __main__.py    # CLI entrypoint & headless runner
│       ├── app.py         # Main Textual App & UI layout
│       ├── config.py      # Autosaving config, validation & CIDR normalizer
│       ├── models.py      # Job, Result, and ScanStats data structures
│       ├── probe.py       # Asynchronous curl engine & title parser
│       ├── export.py      # Exporters (JSON, CSV, Markdown, Text)
│       └── widgets/
│           ├── __init__.py
│           ├── modals.py      # Help, Inspector, Import, and Export modals
│           ├── stats_bar.py   # Live progress bar & status breakdown
│           └── target_list.py # Compact target list panels
└── tests/
    ├── __init__.py
    ├── test_app.py        # Textual async pilot tests
    ├── test_cli.py        # Headless mode tests
    ├── test_config.py     # Configuration roundtrip & normalizer tests
    ├── test_export.py     # Exporter formatting tests
    └── test_probe.py      # Curl probe & HTTP mock server tests
```

---

## Development & Testing

Run the full pytest suite with async support:

```bash
uv run pytest
```

Run test suite with verbose output:

```bash
uv run pytest -v
```

---

## License

MIT © Mike Kane
