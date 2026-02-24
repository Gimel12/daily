"""
Windows Remote Network Monitor — Main Agent
Starts the FastAPI HTTP server and the selected DNS capture mode.
"""
import asyncio
import logging
import signal
import socket
import sys
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from config import (
    CAPTURE_MODE, API_HOST, API_PORT, LOG_LEVEL,
    GATEWAY_IP, NETWORK_CIDR, INTERFACE,
)
from auth import verify_token
from db import (
    init_db, get_recent_queries, search_queries, get_queries_by_device,
    get_device_report, get_query_stats, get_all_devices,
    get_unique_domains, get_all_queries_for_alerts, get_activity_timeline,
)
from network_scanner import scan_network, get_known_devices
from command_executor import execute_command
from domain_categories import (
    categorize_domain, categorize_batch, get_alerts_from_queries, CATEGORIES,
)

# ── Logging setup ───────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agent.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("agent")

# ── Global references to capture components ─────────────────
dns_proxy_server = None
arp_spoofer = None
dns_sniffer = None


def _get_local_ip() -> str:
    """Get this machine's local network IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_capture():
    """Start the selected DNS capture mode."""
    global dns_proxy_server, arp_spoofer, dns_sniffer

    if CAPTURE_MODE == "proxy":
        logger.info("=== Starting Mode A: DNS Proxy ===")
        from dns_proxy import DNSProxyServer
        dns_proxy_server = DNSProxyServer()
        dns_proxy_server.start()

    elif CAPTURE_MODE == "arp":
        logger.info("=== Starting Mode B: ARP Spoof + DNS Sniffer ===")
        from arp_spoofer import ARPSpoofer
        from dns_sniffer import DNSSniffer

        my_ip = _get_local_ip()
        logger.info(f"Local IP: {my_ip}")

        arp_spoofer = ARPSpoofer()
        success = arp_spoofer.start()
        if not success:
            logger.error("ARP spoofer failed to start. DNS capture may not work.")

        dns_sniffer = DNSSniffer(my_ip=my_ip)
        dns_sniffer.start()

    else:
        logger.error(f"Unknown CAPTURE_MODE: {CAPTURE_MODE}. Use 'proxy' or 'arp'.")
        sys.exit(1)


def stop_capture():
    """Stop all capture components gracefully."""
    global dns_proxy_server, arp_spoofer, dns_sniffer

    if dns_proxy_server:
        dns_proxy_server.stop()
    if dns_sniffer:
        dns_sniffer.stop()
    if arp_spoofer:
        arp_spoofer.stop()


# ── FastAPI app ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    init_db()
    start_capture()
    logger.info(f"Agent ready on {API_HOST}:{API_PORT}")
    yield
    logger.info("Shutting down...")
    stop_capture()


app = FastAPI(
    title="Windows Remote Monitor",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request / Response models ───────────────────────────────
class ExecRequest(BaseModel):
    command: str
    shell: str = "powershell"
    timeout: int = 60


# ── API Endpoints ───────────────────────────────────────────

@app.get("/status", dependencies=[Depends(verify_token)])
async def status():
    """Health check and basic stats."""
    stats = get_query_stats()
    return {
        "status": "running",
        "capture_mode": CAPTURE_MODE,
        "local_ip": _get_local_ip(),
        "gateway_ip": GATEWAY_IP,
        "network": NETWORK_CIDR,
        "interface": INTERFACE,
        "dns_stats": stats,
        "components": {
            "dns_proxy": dns_proxy_server.is_running if dns_proxy_server else False,
            "arp_spoofer": arp_spoofer.is_running if arp_spoofer else False,
            "dns_sniffer": dns_sniffer.is_running if dns_sniffer else False,
        }
    }


@app.get("/dns/list", dependencies=[Depends(verify_token)])
async def dns_list(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get recent DNS queries."""
    queries = get_recent_queries(limit=limit, offset=offset)
    return {"count": len(queries), "queries": queries}


@app.get("/dns/search", dependencies=[Depends(verify_token)])
async def dns_search(
    term: str = Query(..., min_length=1),
    limit: int = Query(200, ge=1, le=1000),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    """Search DNS queries by domain keyword."""
    queries = search_queries(term=term, limit=limit, from_date=from_date, to_date=to_date)
    return {"term": term, "count": len(queries), "queries": queries}


@app.get("/dns/device/{ip}", dependencies=[Depends(verify_token)])
async def dns_device(
    ip: str,
    limit: int = Query(200, ge=1, le=1000),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    """Get DNS queries from a specific device."""
    queries = get_queries_by_device(ip=ip, limit=limit, from_date=from_date, to_date=to_date)
    return {"ip": ip, "count": len(queries), "queries": queries}


@app.get("/dns/report/{ip}", dependencies=[Depends(verify_token)])
async def dns_report(
    ip: str,
    days: int = Query(30, ge=1, le=365),
):
    """Generate a browsing report for a device."""
    report = get_device_report(ip=ip, days=days)
    return report


@app.get("/scan", dependencies=[Depends(verify_token)])
async def network_scan():
    """Scan the network for connected devices."""
    devices = scan_network()
    return {"count": len(devices), "devices": devices}


@app.get("/devices", dependencies=[Depends(verify_token)])
async def list_devices():
    """List all previously discovered devices."""
    devices = get_known_devices()
    return {"count": len(devices), "devices": devices}


@app.post("/exec", dependencies=[Depends(verify_token)])
async def exec_command(req: ExecRequest):
    """Execute a command on the Windows PC."""
    result = execute_command(
        command=req.command,
        shell=req.shell,
        timeout=req.timeout,
    )
    return result


@app.get("/alerts", dependencies=[Depends(verify_token)])
async def get_alerts(
    hours: int = Query(24, ge=1, le=720),
):
    """Get flagged domains from the last N hours (adult, VPN, dating, etc.)."""
    queries = get_all_queries_for_alerts(hours=hours)
    alerts = get_alerts_from_queries(queries)
    return {"hours": hours, "count": len(alerts), "alerts": alerts}


@app.get("/alerts/device/{ip}", dependencies=[Depends(verify_token)])
async def get_device_alerts(
    ip: str,
    hours: int = Query(24, ge=1, le=720),
):
    """Get flagged domains for a specific device."""
    queries = get_all_queries_for_alerts(hours=hours)
    device_queries = [q for q in queries if q.get("source_ip") == ip]
    alerts = get_alerts_from_queries(device_queries)
    return {"ip": ip, "hours": hours, "count": len(alerts), "alerts": alerts}


@app.get("/dns/domains", dependencies=[Depends(verify_token)])
async def dns_domains(
    ip: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(200, ge=1, le=1000),
):
    """Get unique domains with visit counts and auto-categorization."""
    domains = get_unique_domains(ip=ip, days=days, limit=limit)
    # Add category info to each domain
    for d in domains:
        cat = categorize_domain(d["domain"])
        d["category"] = cat["category"] if cat else None
        d["category_label"] = cat["label"] if cat else None
        d["severity"] = cat["severity"] if cat else None
    return {"count": len(domains), "domains": domains}


@app.get("/dns/timeline/{ip}", dependencies=[Depends(verify_token)])
async def dns_timeline(
    ip: str,
    days: int = Query(7, ge=1, le=90),
):
    """Get hourly activity timeline for a device."""
    timeline = get_activity_timeline(ip=ip, days=days)
    return {"ip": ip, "days": days, "timeline": timeline}


@app.get("/categories", dependencies=[Depends(verify_token)])
async def list_categories():
    """List all domain categories and their known domains."""
    result = {}
    for cat_id, cat in CATEGORIES.items():
        result[cat_id] = {
            "label": cat["label"],
            "severity": cat["severity"],
            "domain_count": len(cat["domains"]),
            "keyword_count": len(cat["keywords"]),
        }
    return result


@app.post("/spoof/refresh", dependencies=[Depends(verify_token)])
async def refresh_spoof_targets():
    """Re-scan network and update ARP spoof targets (Mode B only)."""
    if not arp_spoofer:
        raise HTTPException(status_code=400, detail="ARP spoofer not active (Mode A?)")
    targets = arp_spoofer.refresh_targets()
    return {"targets": targets, "count": len(targets)}


# ── Main ────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════╗
║   Windows Remote Network Monitor v1.0        ║
║   Mode: {CAPTURE_MODE.upper():8s}                            ║
║   API:  http://{API_HOST}:{API_PORT}             ║
╚══════════════════════════════════════════════╝
    """)
    uvicorn.run(
        "agent:app",
        host=API_HOST,
        port=API_PORT,
        log_level=LOG_LEVEL.lower(),
    )
