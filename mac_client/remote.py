#!/usr/bin/env python3
"""
Windows Remote Network Monitor — Mac CLI Client
Connect to the Windows agent via Tailscale and run commands.

Usage:
    python remote.py status
    python remote.py exec "ipconfig /all"
    python remote.py scan
    python remote.py devices
    python remote.py alerts [--hours N]
    python remote.py alerts device <ip> [--hours N]
    python remote.py dns list [--limit N]
    python remote.py dns search <term> [--from DATE] [--to DATE]
    python remote.py dns device <ip> [--from DATE] [--to DATE]
    python remote.py dns domains [--ip IP] [--days N]
    python remote.py dns report <ip> [--days N]
    python remote.py dns timeline <ip> [--days N]
    python remote.py dns live
"""
import argparse
import json
import sys
import time
from datetime import datetime

import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich import box

# ============================================================
# CONFIGURATION — Edit these values
# ============================================================
# Your Windows PC's Tailscale IP (find it with 'tailscale status')
AGENT_URL = "http://100.x.x.x:8745"

# Same auth token as in windows_agent/config.py
AUTH_TOKEN = "CHANGE_ME"

# ============================================================
console = Console()


def _headers():
    return {"X-Auth-Token": AUTH_TOKEN}


def _get(path: str, params: dict = None) -> dict:
    """Make a GET request to the agent."""
    try:
        r = requests.get(f"{AGENT_URL}{path}", headers=_headers(), params=params, timeout=30)
        if r.status_code == 401:
            console.print("[red]Authentication failed. Check your AUTH_TOKEN.[/red]")
            sys.exit(1)
        if r.status_code == 403:
            console.print("[red]Invalid auth token.[/red]")
            sys.exit(1)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        console.print(f"[red]Cannot connect to agent at {AGENT_URL}[/red]")
        console.print("Check that the agent is running and Tailscale is connected.")
        sys.exit(1)
    except requests.RequestException as e:
        console.print(f"[red]Request failed: {e}[/red]")
        sys.exit(1)


def _post(path: str, data: dict = None) -> dict:
    """Make a POST request to the agent."""
    try:
        r = requests.post(f"{AGENT_URL}{path}", headers=_headers(), json=data, timeout=120)
        if r.status_code in (401, 403):
            console.print("[red]Authentication failed. Check your AUTH_TOKEN.[/red]")
            sys.exit(1)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        console.print(f"[red]Cannot connect to agent at {AGENT_URL}[/red]")
        sys.exit(1)
    except requests.RequestException as e:
        console.print(f"[red]Request failed: {e}[/red]")
        sys.exit(1)


# ── Commands ────────────────────────────────────────────────

def cmd_status():
    """Show agent status."""
    data = _get("/status")
    panel_text = (
        f"[bold green]Status:[/bold green] {data['status']}\n"
        f"[bold]Mode:[/bold] {data['capture_mode'].upper()}\n"
        f"[bold]Local IP:[/bold] {data['local_ip']}\n"
        f"[bold]Gateway:[/bold] {data['gateway_ip']}\n"
        f"[bold]Network:[/bold] {data['network']}\n"
        f"[bold]Interface:[/bold] {data['interface']}\n"
        f"\n[bold cyan]DNS Stats:[/bold cyan]\n"
        f"  Total queries: {data['dns_stats']['total_queries']}\n"
        f"  Queries today: {data['dns_stats']['queries_today']}\n"
        f"  Unique devices: {data['dns_stats']['unique_devices']}\n"
        f"\n[bold cyan]Components:[/bold cyan]\n"
    )
    for comp, running in data["components"].items():
        status_icon = "[green]ON[/green]" if running else "[dim]OFF[/dim]"
        panel_text += f"  {comp}: {status_icon}\n"

    console.print(Panel(panel_text, title="Windows Remote Monitor", border_style="blue"))


def cmd_exec(args):
    """Execute a command on the Windows PC."""
    data = _post("/exec", {
        "command": args.command,
        "shell": args.shell,
        "timeout": args.timeout,
    })

    if data["success"]:
        console.print(f"[green]Command succeeded (exit code {data['return_code']})[/green]")
    else:
        console.print(f"[red]Command failed (exit code {data['return_code']})[/red]")

    if data["stdout"]:
        console.print(Panel(data["stdout"].rstrip(), title="stdout", border_style="green"))
    if data["stderr"]:
        console.print(Panel(data["stderr"].rstrip(), title="stderr", border_style="red"))


def cmd_scan():
    """Scan the network for devices."""
    console.print("[cyan]Scanning network...[/cyan]")
    data = _get("/scan")

    table = Table(title=f"Network Devices ({data['count']} found)", box=box.ROUNDED)
    table.add_column("IP", style="bold")
    table.add_column("MAC")
    table.add_column("Hostname")
    table.add_column("Vendor")

    for d in data["devices"]:
        table.add_row(d["ip"], d["mac"], d.get("hostname", ""), d.get("vendor", ""))

    console.print(table)


def cmd_devices():
    """List known devices from the database."""
    data = _get("/devices")

    table = Table(title=f"Known Devices ({data['count']})", box=box.ROUNDED)
    table.add_column("IP", style="bold")
    table.add_column("MAC")
    table.add_column("Hostname")
    table.add_column("Vendor")
    table.add_column("First Seen")
    table.add_column("Last Seen")

    for d in data["devices"]:
        table.add_row(
            d["ip"], d["mac"], d.get("hostname", ""), d.get("vendor", ""),
            d.get("first_seen", ""), d.get("last_seen", ""),
        )

    console.print(table)


def _print_dns_table(queries, title="DNS Queries"):
    """Print DNS queries as a rich table."""
    table = Table(title=title, box=box.ROUNDED)
    table.add_column("Time", style="dim")
    table.add_column("Source IP", style="bold")
    table.add_column("Domain", style="cyan")
    table.add_column("Type")

    for q in queries:
        ts = q.get("timestamp", "")
        # Shorten timestamp for display
        if "T" in ts:
            ts = ts.replace("T", " ")[:19]
        table.add_row(ts, q["source_ip"], q["domain"], q.get("query_type", ""))

    console.print(table)


def cmd_dns_list(args):
    """Show recent DNS queries."""
    data = _get("/dns/list", {"limit": args.limit})
    _print_dns_table(data["queries"], f"Recent DNS Queries ({data['count']})")


def cmd_dns_search(args):
    """Search DNS queries by domain keyword."""
    params = {"term": args.term, "limit": args.limit}
    if args.from_date:
        params["from"] = args.from_date
    if args.to_date:
        params["to"] = args.to_date

    data = _get("/dns/search", params)
    _print_dns_table(data["queries"], f"DNS Search: '{args.term}' ({data['count']} results)")


def cmd_dns_device(args):
    """Show DNS queries from a specific device."""
    params = {"limit": args.limit}
    if args.from_date:
        params["from"] = args.from_date
    if args.to_date:
        params["to"] = args.to_date

    data = _get(f"/dns/device/{args.ip}", params)
    _print_dns_table(data["queries"], f"DNS Queries from {args.ip} ({data['count']})")


def cmd_dns_report(args):
    """Generate a browsing report for a device."""
    data = _get(f"/dns/report/{args.ip}", {"days": args.days})

    console.print(Panel(
        f"[bold]Device:[/bold] {data['ip']}\n"
        f"[bold]Period:[/bold] Last {data['days']} days\n"
        f"[bold]Total queries:[/bold] {data['total_queries']}",
        title="Device Report",
        border_style="blue",
    ))

    # Top domains
    if data["top_domains"]:
        table = Table(title="Top Domains", box=box.ROUNDED)
        table.add_column("#", style="dim")
        table.add_column("Domain", style="cyan")
        table.add_column("Queries", style="bold")

        for i, d in enumerate(data["top_domains"], 1):
            table.add_row(str(i), d["domain"], str(d["cnt"]))

        console.print(table)

    # Daily breakdown
    if data["daily_breakdown"]:
        table = Table(title="Daily Breakdown", box=box.ROUNDED)
        table.add_column("Date", style="bold")
        table.add_column("Queries")

        for d in data["daily_breakdown"]:
            table.add_row(d["day"], str(d["cnt"]))

        console.print(table)


def cmd_dns_domains(args):
    """Show unique domains with visit counts and categories."""
    params = {"days": args.days, "limit": args.limit}
    if args.ip:
        params["ip"] = args.ip

    data = _get("/dns/domains", params)

    title = f"Unique Domains ({data['count']})"
    if args.ip:
        title += f" from {args.ip}"

    table = Table(title=title, box=box.ROUNDED)
    table.add_column("Domain", style="cyan")
    table.add_column("Visits", style="bold")
    table.add_column("Category")
    table.add_column("Severity")
    table.add_column("First Seen", style="dim")
    table.add_column("Last Seen", style="dim")

    severity_colors = {"high": "red", "medium": "yellow", "low": "dim"}

    for d in data["domains"]:
        cat_label = d.get("category_label") or ""
        severity = d.get("severity") or ""
        sev_color = severity_colors.get(severity, "white")

        if severity:
            severity_display = f"[{sev_color}]{severity.upper()}[/{sev_color}]"
            cat_display = f"[{sev_color}]{cat_label}[/{sev_color}]"
        else:
            severity_display = ""
            cat_display = ""

        first_seen = d.get("first_seen", "").replace("T", " ")[:19]
        last_seen = d.get("last_seen", "").replace("T", " ")[:19]

        table.add_row(d["domain"], str(d["cnt"]), cat_display, severity_display, first_seen, last_seen)

    console.print(table)


def cmd_dns_timeline(args):
    """Show hourly activity timeline for a device."""
    data = _get(f"/dns/timeline/{args.ip}", {"days": args.days})

    table = Table(title=f"Activity Timeline for {args.ip} (last {args.days} days)", box=box.ROUNDED)
    table.add_column("Hour", style="bold")
    table.add_column("Queries")
    table.add_column("Activity", style="cyan")

    max_cnt = max((t["cnt"] for t in data["timeline"]), default=1)

    for t in data["timeline"]:
        bar_len = int((t["cnt"] / max_cnt) * 30) if max_cnt > 0 else 0
        bar = "#" * bar_len
        table.add_row(t["hour"], str(t["cnt"]), bar)

    console.print(table)


def cmd_alerts(args):
    """Show flagged domains (adult, VPN, dating, gambling, etc.)."""
    data = _get("/alerts", {"hours": args.hours})

    if data["count"] == 0:
        console.print(f"[green]No alerts in the last {args.hours} hours.[/green]")
        return

    table = Table(title=f"ALERTS — Last {args.hours} hours ({data['count']} flags)", box=box.HEAVY)
    table.add_column("Severity", style="bold")
    table.add_column("Category")
    table.add_column("Domain", style="cyan")
    table.add_column("Device IP", style="bold")
    table.add_column("Time", style="dim")

    for a in data["alerts"]:
        sev = a["severity"]
        if sev == "high":
            sev_display = "[red bold]HIGH[/red bold]"
        elif sev == "medium":
            sev_display = "[yellow]MEDIUM[/yellow]"
        else:
            sev_display = sev

        ts = a.get("timestamp", "").replace("T", " ")[:19]
        table.add_row(sev_display, a["label"], a["domain"], a["source_ip"], ts)

    console.print(table)


def cmd_alerts_device(args):
    """Show flagged domains for a specific device."""
    data = _get(f"/alerts/device/{args.ip}", {"hours": args.hours})

    if data["count"] == 0:
        console.print(f"[green]No alerts for {args.ip} in the last {args.hours} hours.[/green]")
        return

    table = Table(title=f"ALERTS for {args.ip} — Last {args.hours} hours", box=box.HEAVY)
    table.add_column("Severity", style="bold")
    table.add_column("Category")
    table.add_column("Domain", style="cyan")
    table.add_column("Time", style="dim")

    for a in data["alerts"]:
        sev = a["severity"]
        if sev == "high":
            sev_display = "[red bold]HIGH[/red bold]"
        elif sev == "medium":
            sev_display = "[yellow]MEDIUM[/yellow]"
        else:
            sev_display = sev

        ts = a.get("timestamp", "").replace("T", " ")[:19]
        table.add_row(sev_display, a["label"], a["domain"], ts)

    console.print(table)


def cmd_dns_live(args):
    """Live tail of DNS queries (polls every 2 seconds)."""
    console.print("[cyan]Live DNS monitoring (Ctrl+C to stop)...[/cyan]\n")
    seen_ids = set()
    last_id = 0

    # Inline severity check for live coloring
    HIGH_KEYWORDS = ["porn", "xxx", "nsfw", "hentai", "onlyfans", "fap", "nude", "sexo",
                     "casino", "gambling", "betting", "slots", "self-harm", "suicide"]
    HIGH_DOMAINS = ["pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com", "redtube.com",
                    "onlyfans.com", "chaturbate.com", "stripchat.com", "draftkings.com",
                    "fanduel.com", "stake.com", "bet365.com"]
    MED_KEYWORDS = ["vpn", "unblock", "proxy-", "hookup", "dating"]
    MED_DOMAINS = ["tinder.com", "bumble.com", "grindr.com", "omegle.com", "nordvpn.com",
                   "expressvpn.com", "surfshark.com", "protonvpn.com", "torproject.org"]

    def _live_severity(domain):
        d = domain.lower()
        for kw in HIGH_KEYWORDS:
            if kw in d:
                return "high"
        for dd in HIGH_DOMAINS:
            if d == dd or d.endswith("." + dd):
                return "high"
        for kw in MED_KEYWORDS:
            if kw in d:
                return "medium"
        for dd in MED_DOMAINS:
            if d == dd or d.endswith("." + dd):
                return "medium"
        return None

    try:
        while True:
            data = _get("/dns/list", {"limit": 20})
            new_queries = []

            for q in reversed(data["queries"]):
                qid = q.get("id", 0)
                if qid > last_id:
                    new_queries.append(q)
                    last_id = qid

            for q in new_queries:
                ts = q.get("timestamp", "").replace("T", " ")[:19]
                domain = q["domain"]
                src = q["source_ip"]
                qtype = q.get("query_type", "A")

                flag = _live_severity(domain)
                if flag == "high":
                    domain_display = f"[red bold]{domain} *** FLAGGED ***[/red bold]"
                elif flag == "medium":
                    domain_display = f"[yellow]{domain} * flagged *[/yellow]"
                else:
                    domain_display = f"[cyan]{domain}[/cyan]"

                console.print(f"[dim]{ts}[/dim]  [bold]{src}[/bold]  {domain_display}  [dim]{qtype}[/dim]")

            time.sleep(2)

    except KeyboardInterrupt:
        console.print("\n[yellow]Live monitoring stopped.[/yellow]")


# ── Argument parser ─────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="remote",
        description="Windows Remote Network Monitor — Mac CLI Client",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # status
    sub.add_parser("status", help="Show agent status")

    # exec
    p_exec = sub.add_parser("exec", help="Execute a command on Windows PC")
    p_exec.add_argument("cmd_string", metavar="command", help="Command to execute")
    p_exec.add_argument("--shell", choices=["powershell", "cmd"], default="powershell")
    p_exec.add_argument("--timeout", type=int, default=60)

    # scan
    sub.add_parser("scan", help="Scan network for devices")

    # devices
    sub.add_parser("devices", help="List known devices")

    # dns
    p_dns = sub.add_parser("dns", help="DNS query commands")
    dns_sub = p_dns.add_subparsers(dest="dns_command", help="DNS subcommands")

    # dns list
    p_dns_list = dns_sub.add_parser("list", help="Show recent DNS queries")
    p_dns_list.add_argument("--limit", type=int, default=100)

    # dns search
    p_dns_search = dns_sub.add_parser("search", help="Search DNS queries by keyword")
    p_dns_search.add_argument("term", help="Search term (e.g. 'youtube', 'tiktok')")
    p_dns_search.add_argument("--limit", type=int, default=200)
    p_dns_search.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    p_dns_search.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD)")

    # dns device
    p_dns_dev = dns_sub.add_parser("device", help="Show queries from a device")
    p_dns_dev.add_argument("ip", help="Device IP address")
    p_dns_dev.add_argument("--limit", type=int, default=200)
    p_dns_dev.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    p_dns_dev.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD)")

    # dns report
    p_dns_report = dns_sub.add_parser("report", help="Generate device browsing report")
    p_dns_report.add_argument("ip", help="Device IP address")
    p_dns_report.add_argument("--days", type=int, default=30)

    # dns domains
    p_dns_domains = dns_sub.add_parser("domains", help="Show unique domains with categories")
    p_dns_domains.add_argument("--ip", help="Filter by device IP")
    p_dns_domains.add_argument("--days", type=int, default=7)
    p_dns_domains.add_argument("--limit", type=int, default=200)

    # dns timeline
    p_dns_tl = dns_sub.add_parser("timeline", help="Show hourly activity for a device")
    p_dns_tl.add_argument("ip", help="Device IP address")
    p_dns_tl.add_argument("--days", type=int, default=7)

    # dns live
    dns_sub.add_parser("live", help="Live tail of DNS queries")

    # alerts
    p_alerts = sub.add_parser("alerts", help="Show flagged domains (adult, VPN, etc.)")
    p_alerts_sub = p_alerts.add_subparsers(dest="alerts_command")

    # alerts (default — all devices)
    p_alerts.add_argument("--hours", type=int, default=24)

    # alerts device <ip>
    p_alerts_dev = p_alerts_sub.add_parser("device", help="Show alerts for a specific device")
    p_alerts_dev.add_argument("ip", help="Device IP address")
    p_alerts_dev.add_argument("--hours", type=int, default=24)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "status":
        cmd_status()
    elif args.command == "exec":
        # Remap the attribute name
        args.command_str = args.cmd_string
        class ExecArgs:
            command = args.cmd_string
            shell = args.shell
            timeout = args.timeout
        cmd_exec(ExecArgs())
    elif args.command == "scan":
        cmd_scan()
    elif args.command == "devices":
        cmd_devices()
    elif args.command == "alerts":
        if hasattr(args, "alerts_command") and args.alerts_command == "device":
            cmd_alerts_device(args)
        else:
            cmd_alerts(args)
    elif args.command == "dns":
        if not args.dns_command:
            console.print("[yellow]Usage: remote.py dns {list|search|device|domains|report|timeline|live}[/yellow]")
            return
        if args.dns_command == "list":
            cmd_dns_list(args)
        elif args.dns_command == "search":
            cmd_dns_search(args)
        elif args.dns_command == "device":
            cmd_dns_device(args)
        elif args.dns_command == "domains":
            cmd_dns_domains(args)
        elif args.dns_command == "report":
            cmd_dns_report(args)
        elif args.dns_command == "timeline":
            cmd_dns_timeline(args)
        elif args.dns_command == "live":
            cmd_dns_live(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
