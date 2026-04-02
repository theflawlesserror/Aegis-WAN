"""
Aegis ML Sidecar — Prometheus Node Exporter
============================================
Scrapes the /logs endpoint for every tracked device and exposes
Prometheus metrics on :9101/metrics.

Device discovery (in priority order):
  1. AEGIS_DEVICES env var — comma-separated system_ip list (static, no API call needed)
  2. Auto-discovery   — queries VMANAGE_URL/dataservice/device on startup and
                        re-queries every AEGIS_REDISCOVERY_INTERVAL seconds so
                        newly registered vessels are picked up automatically.

Metrics exposed (all labelled by system_ip and link):
  aegis_link_actual_vqoe        - Raw vQoE score reported by vManage
  aegis_link_predicted_vqoe     - ML-predicted vQoE score
  aegis_link_rx_kbps            - Receive throughput (kbps)
  aegis_link_tx_kbps            - Transmit throughput (kbps)
  aegis_active_link             - 1 if this link is currently active, 0 otherwise
  aegis_scrape_success          - 1 if the last scrape for this device succeeded
  aegis_scrape_duration_seconds - How long the last scrape took

Usage:
  pip install prometheus-client httpx

  # Option A — auto-discover from vManage (recommended)
  VMANAGE_URL=http://localhost:8000 python aegis_exporter.py

  # Option B — static list (no vManage access needed)
  AEGIS_DEVICES=10.0.0.1,10.0.0.2 python aegis_exporter.py

Environment variables:
  AEGIS_SIDECAR_URL          Base URL of the sidecar          (default: http://localhost:8080)
  VMANAGE_URL                Base URL of vManage mock          (default: http://localhost:8000)
  AEGIS_DEVICES              Optional static comma-separated system_ip override
  AEGIS_LOG_LIMIT            Log entries to fetch per device   (default: 1)
  AEGIS_POLL_INTERVAL        Seconds between scrape cycles     (default: 5)
  AEGIS_REDISCOVERY_INTERVAL Seconds between device re-discovery runs (default: 60)
  AEGIS_DISCOVERY_RETRIES    Max attempts to reach vManage on startup (default: 10)
  AEGIS_DISCOVERY_RETRY_WAIT Seconds to wait between retries   (default: 3)
  EXPORTER_PORT              Metrics port                       (default: 9101)
"""

import os
import time
import logging
import signal
import sys
from typing import Dict, List, Set

import httpx
from prometheus_client import Counter, Gauge, start_http_server

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SIDECAR_URL             = os.getenv("AEGIS_SIDECAR_URL", "http://localhost:8080").rstrip("/")
VMANAGE_URL             = os.getenv("VMANAGE_URL", "http://localhost:8000").rstrip("/")
DEVICES_RAW             = os.getenv("AEGIS_DEVICES", "")       # optional static override
LOG_LIMIT               = int(os.getenv("AEGIS_LOG_LIMIT", "10"))  # fetch recent window to catch switches between scrapes
POLL_INTERVAL           = float(os.getenv("AEGIS_POLL_INTERVAL", "5"))
REDISCOVERY_INTERVAL    = float(os.getenv("AEGIS_REDISCOVERY_INTERVAL", "60"))
DISCOVERY_RETRIES       = int(os.getenv("AEGIS_DISCOVERY_RETRIES", "10"))
DISCOVERY_RETRY_WAIT    = float(os.getenv("AEGIS_DISCOVERY_RETRY_WAIT", "3"))
EXPORTER_PORT           = int(os.getenv("EXPORTER_PORT", "9101"))
REQUEST_TIMEOUT         = 10  # seconds; prevents hanging on a slow sidecar/vManage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("aegis_exporter")

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------
LABELS        = ["system_ip", "link"]
DEVICE_LABELS = ["system_ip"]

actual_vqoe = Gauge(
    "aegis_link_actual_vqoe",
    "Raw vQoE score reported by vManage for this link",
    LABELS,
)
predicted_vqoe = Gauge(
    "aegis_link_predicted_vqoe",
    "ML-predicted vQoE score for this link",
    LABELS,
)
rx_kbps = Gauge(
    "aegis_link_rx_kbps",
    "Receive throughput in kbps for this link",
    LABELS,
)
tx_kbps = Gauge(
    "aegis_link_tx_kbps",
    "Transmit throughput in kbps for this link",
    LABELS,
)
active_link = Gauge(
    "aegis_active_link",
    "1 if this link is currently the active route, 0 otherwise",
    LABELS,
)
scrape_success = Gauge(
    "aegis_scrape_success",
    "1 if the last sidecar scrape for this device succeeded, 0 otherwise",
    DEVICE_LABELS,
)
scrape_duration = Gauge(
    "aegis_scrape_duration_seconds",
    "Duration of the last sidecar scrape for this device in seconds",
    DEVICE_LABELS,
)
route_switches = Counter(
    "aegis_route_switches_total",
    "Total number of successful hysteresis-triggered route switches, by destination link",
    LABELS,  # system_ip + link (the link switched TO)
)

# Per-device watermark: highest log 'step' already counted so we never
# double-count a switch when the same rolling window is re-fetched.
_seen_up_to: Dict[str, int] = {}


# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------
KNOWN_LINKS = {"5G", "Satellite"}  # extend if more link types are added


def discover_devices(client: httpx.Client) -> Set[str]:
    """
    Query vManage for all registered device system_ips.
    Mirrors the same endpoint app.py uses: GET /dataservice/device
    Returns an empty set (with a warning) if the call fails — the caller
    decides whether to retry or fall back.
    """
    try:
        resp = client.get(
            f"{VMANAGE_URL}/dataservice/device",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        devices = resp.json().get("data", [])
        ips: Set[str] = set()
        for d in devices:
            s_ip = d.get("system_ip")
            if s_ip:
                ips.add(s_ip)
        log.info("Auto-discovered %d device(s): %s", len(ips), sorted(ips))
        return ips
    except Exception as exc:
        log.warning("Device discovery failed: %s", exc)
        return set()


def discover_with_retry(client: httpx.Client) -> Set[str]:
    """
    Retry discover_devices up to DISCOVERY_RETRIES times.
    This lets the exporter start alongside the stack without crashing
    if vManage hasn't finished booting yet.
    """
    for attempt in range(1, DISCOVERY_RETRIES + 1):
        ips = discover_devices(client)
        if ips:
            return ips
        log.info(
            "Discovery attempt %d/%d yielded no devices — retrying in %.0fs …",
            attempt, DISCOVERY_RETRIES, DISCOVERY_RETRY_WAIT,
        )
        time.sleep(DISCOVERY_RETRY_WAIT)
    log.error(
        "Could not discover any devices after %d attempts. "
        "Set AEGIS_DEVICES=<ip1,ip2,...> to use a static list instead.",
        DISCOVERY_RETRIES,
    )
    return set()


# ---------------------------------------------------------------------------
# Scrape logic
# ---------------------------------------------------------------------------
def scrape_device(client: httpx.Client, system_ip: str) -> None:
    """Fetch the latest log entry for *system_ip* and update all gauges."""
    t0 = time.monotonic()
    try:
        resp = client.get(
            f"{SIDECAR_URL}/logs",
            params={"system_ip": system_ip, "limit": LOG_LIMIT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        elapsed = time.monotonic() - t0
        log.warning("Scrape failed for %s after %.2fs: %s", system_ip, elapsed, exc)
        scrape_success.labels(system_ip=system_ip).set(0)
        scrape_duration.labels(system_ip=system_ip).set(elapsed)
        return

    elapsed = time.monotonic() - t0
    scrape_success.labels(system_ip=system_ip).set(1)
    scrape_duration.labels(system_ip=system_ip).set(elapsed)

    current_active = data.get("active_link")
    logs = data.get("logs", [])

    if not logs:
        log.debug("No log entries returned for %s", system_ip)
        return

    latest = logs[-1]  # most recent tick
    links_data = latest.get("links", {})

    for link in KNOWN_LINKS:
        link_info = links_data.get(link, {})

        actual_vqoe.labels(system_ip=system_ip, link=link).set(
            link_info.get("actual_vqoe", 0.0)
        )
        predicted_vqoe.labels(system_ip=system_ip, link=link).set(
            link_info.get("predicted_vqoe", 0.0)
        )
        rx_kbps.labels(system_ip=system_ip, link=link).set(
            link_info.get("rx_kbps", 0.0)
        )
        tx_kbps.labels(system_ip=system_ip, link=link).set(
            link_info.get("tx_kbps", 0.0)
        )
        active_link.labels(system_ip=system_ip, link=link).set(
            1.0 if current_active == link else 0.0
        )


    # --- Count new route switches -------------------------------------------
    # Walk every log entry in the returned window and increment the counter
    # only for steps we haven't seen before (watermark approach), so a switch
    # is counted exactly once even if the same window is returned on the next
    # scrape cycle. "Triggered switch to X" is the only string that represents
    # a switch that was actually committed (errors use "ERROR:" prefix).
    watermark = _seen_up_to.get(system_ip, 0)
    new_watermark = watermark
    for entry in logs:
        step_num = entry.get("step", 0)
        if step_num <= watermark:
            continue
        routing_update = entry.get("routing_update") or ""
        if routing_update.startswith("Triggered switch to "):
            dest_link = routing_update.removeprefix("Triggered switch to ").strip()
            route_switches.labels(system_ip=system_ip, link=dest_link).inc()
            log.info("%s: counted switch to '%s' (step=%d)", system_ip, dest_link, step_num)
        if step_num > new_watermark:
            new_watermark = step_num
    _seen_up_to[system_ip] = new_watermark

    log.debug(
        "Scraped %s in %.3fs | active=%s | links=%s",
        system_ip, elapsed, current_active, list(links_data.keys()),
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run_loop(client: httpx.Client, static_devices: List[str]) -> None:
    """
    Main polling loop — runs until SIGINT/SIGTERM.

    If static_devices is non-empty it is used as-is and no re-discovery
    is performed. Otherwise devices are refreshed from vManage every
    REDISCOVERY_INTERVAL seconds so the exporter adapts to fleet changes.
    """
    use_static = bool(static_devices)
    devices: Set[str] = set(static_devices)

    if not use_static:
        devices = discover_with_retry(client)
        if not devices:
            log.error("No devices to scrape. Exiting.")
            sys.exit(1)

    last_discovery = time.monotonic()
    log.info(
        "Scrape loop started | devices=%s | poll=%.1fs | sidecar=%s",
        sorted(devices), POLL_INTERVAL, SIDECAR_URL,
    )

    while True:
        cycle_start = time.monotonic()

        # Periodic re-discovery (auto mode only)
        if not use_static and (cycle_start - last_discovery) >= REDISCOVERY_INTERVAL:
            fresh = discover_devices(client)
            if fresh:
                if fresh != devices:
                    added   = fresh - devices
                    removed = devices - fresh
                    if added:
                        log.info("New devices detected: %s", sorted(added))
                    if removed:
                        log.info("Devices no longer registered: %s", sorted(removed))
                    devices = fresh
            last_discovery = cycle_start

        for ip in sorted(devices):
            scrape_device(client, ip)

        elapsed = time.monotonic() - cycle_start
        time.sleep(max(0.0, POLL_INTERVAL - elapsed))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    # Graceful shutdown on SIGTERM (e.g. from Docker / systemd)
    def _handle_signal(signum, frame):
        log.info("Received signal %s — shutting down.", signal.Signals(signum).name)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Parse static device list if provided
    static_devices: List[str] = []
    if DEVICES_RAW.strip():
        static_devices = [ip.strip() for ip in DEVICES_RAW.split(",") if ip.strip()]
        log.info("Using static device list: %s", static_devices)
    else:
        log.info(
            "AEGIS_DEVICES not set — will auto-discover from vManage at %s",
            VMANAGE_URL,
        )

    log.info("Starting Prometheus metrics server on port %d", EXPORTER_PORT)
    start_http_server(EXPORTER_PORT)

    with httpx.Client() as client:
        run_loop(client, static_devices)


if __name__ == "__main__":
    main()