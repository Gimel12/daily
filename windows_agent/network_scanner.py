"""
Network Scanner — Discovers devices on the local network using ARP.
"""
import logging
import socket
import subprocess
from typing import List, Dict

from scapy.all import ARP, Ether, srp

from config import NETWORK_CIDR, INTERFACE
from db import upsert_device, get_all_devices

logger = logging.getLogger("network_scanner")


def _resolve_hostname(ip: str) -> str:
    """Try to resolve a hostname from an IP address."""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror, OSError):
        return ""


def _get_vendor_from_mac(mac: str) -> str:
    """Basic vendor lookup from MAC OUI prefix. Returns empty if unknown."""
    # Common home device OUIs — extend as needed
    oui_map = {
        "00:50:56": "VMware",
        "00:0c:29": "VMware",
        "b8:27:eb": "Raspberry Pi",
        "dc:a6:32": "Raspberry Pi",
        "ac:de:48": "Apple",
        "f0:18:98": "Apple",
        "3c:22:fb": "Apple",
        "a4:83:e7": "Apple",
        "00:1a:79": "Samsung",
        "8c:f5:a3": "Samsung",
        "fc:f1:36": "Samsung",
        "30:b4:9e": "TP-Link",
        "50:c7:bf": "TP-Link",
        "74:da:38": "Intel",
        "00:15:5d": "Hyper-V",
    }
    prefix = mac[:8].lower()
    return oui_map.get(prefix, "")


def scan_network(cidr: str = None) -> List[Dict]:
    """
    Scan the network using ARP and return a list of discovered devices.
    Each device: {ip, mac, hostname, vendor}
    """
    target = cidr or NETWORK_CIDR
    logger.info(f"Scanning network: {target}")

    try:
        ans, _ = srp(
            Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=target),
            timeout=5,
            verbose=False,
            iface=INTERFACE,
        )
    except Exception as e:
        logger.error(f"ARP scan failed: {e}")
        # Fallback: use arp -a command
        return _scan_via_arp_command()

    devices = []
    for sent, received in ans:
        ip = received.psrc
        mac = received.hwsrc
        hostname = _resolve_hostname(ip)
        vendor = _get_vendor_from_mac(mac)

        device = {
            "ip": ip,
            "mac": mac,
            "hostname": hostname,
            "vendor": vendor,
        }
        devices.append(device)

        # Save to database
        upsert_device(ip=ip, mac=mac, hostname=hostname, vendor=vendor)

    logger.info(f"Scan complete: {len(devices)} devices found.")
    return devices


def _scan_via_arp_command() -> List[Dict]:
    """Fallback: parse 'arp -a' output on Windows."""
    logger.info("Using fallback ARP table scan...")
    devices = []
    try:
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] == "dynamic":
                ip = parts[0]
                mac = parts[1].replace("-", ":")
                hostname = _resolve_hostname(ip)
                vendor = _get_vendor_from_mac(mac)
                device = {
                    "ip": ip,
                    "mac": mac,
                    "hostname": hostname,
                    "vendor": vendor,
                }
                devices.append(device)
                upsert_device(ip=ip, mac=mac, hostname=hostname, vendor=vendor)
    except Exception as e:
        logger.error(f"ARP command fallback failed: {e}")

    logger.info(f"Fallback scan: {len(devices)} devices found.")
    return devices


def get_known_devices() -> List[Dict]:
    """Return all previously discovered devices from the database."""
    return get_all_devices()
