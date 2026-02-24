"""
Windows Remote Network Monitor - Configuration
Edit these values before running the agent.
"""
import secrets
import socket

# ============================================================
# AUTH
# ============================================================
# Shared secret token — set the SAME value on your Mac client.
# Generate a new one with: python -c "import secrets; print(secrets.token_urlsafe(32))"
AUTH_TOKEN = "CHANGE_ME_" + secrets.token_urlsafe(16)

# ============================================================
# CAPTURE MODE
# ============================================================
# "proxy"  — Mode A: DNS proxy on port 53 (requires router DHCP change)
# "arp"    — Mode B: ARP spoofing (no router access needed)
CAPTURE_MODE = "proxy"

# ============================================================
# NETWORK
# ============================================================
# The local network interface name on Windows.
# Run 'ipconfig' to find yours (e.g. "Ethernet", "Wi-Fi").
INTERFACE = "Wi-Fi"

# Gateway IP — your Xfinity router's IP.
GATEWAY_IP = "10.0.0.1"

# Subnet to scan for devices (CIDR notation).
NETWORK_CIDR = "10.0.0.0/24"

# ============================================================
# DNS
# ============================================================
# Upstream DNS server to forward queries to.
UPSTREAM_DNS = "8.8.8.8"
UPSTREAM_DNS_ALT = "8.8.4.4"

# DNS proxy listen port (Mode A only).
DNS_PROXY_PORT = 53

# ============================================================
# API SERVER
# ============================================================
# Port for the FastAPI HTTP server.
API_PORT = 8745

# Bind address — 0.0.0.0 to accept connections from Tailscale.
API_HOST = "0.0.0.0"

# ============================================================
# DATABASE
# ============================================================
# SQLite database file path (relative to agent directory).
DB_PATH = "dns_monitor.db"

# ============================================================
# ARP SPOOF SETTINGS
# ============================================================
# Interval in seconds between ARP spoof packets.
ARP_SPOOF_INTERVAL = 2.0

# Target specific IPs only (empty list = spoof ALL devices on the network).
# Example: ["192.168.1.42", "192.168.1.43"]
ARP_TARGETS = []

# ============================================================
# LOGGING
# ============================================================
LOG_LEVEL = "INFO"

# Ignore DNS queries to these domains (reduce noise).
IGNORE_DOMAINS = [
    "localhost",
    "*.local",
    "*.arpa",
    "*.internal",
]
