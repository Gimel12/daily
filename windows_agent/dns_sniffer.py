"""
DNS Sniffer — Captures DNS packets on the network and logs them.
Used by both Mode A (proxy) and Mode B (ARP spoof).
In Mode B, this sniffs DNS packets flowing through the machine after ARP spoofing.
In Mode A, the dns_proxy.py handles logging directly, but this can run as extra capture.
"""
import threading
import logging
from scapy.all import sniff, DNS, DNSQR, IP, conf

from config import IGNORE_DOMAINS, INTERFACE
from db import log_dns_query

logger = logging.getLogger("dns_sniffer")


def _should_ignore(domain: str) -> bool:
    """Check if a domain matches any ignore pattern."""
    domain = domain.rstrip(".")
    for pattern in IGNORE_DOMAINS:
        if pattern.startswith("*."):
            suffix = pattern[1:]
            if domain.endswith(suffix) or domain == pattern[2:]:
                return True
        elif domain == pattern:
            return True
    return False


def _get_query_type(qtype: int) -> str:
    """Convert DNS query type int to string."""
    types = {
        1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR",
        15: "MX", 16: "TXT", 28: "AAAA", 33: "SRV", 255: "ANY",
        65: "HTTPS",
    }
    return types.get(qtype, str(qtype))


class DNSSniffer:
    """Packet sniffer that captures DNS queries from the network."""

    def __init__(self, my_ip: str = None):
        self._running = False
        self._thread = None
        self._iface = INTERFACE
        self._my_ip = my_ip  # This machine's IP, to exclude our own queries

    def _process_packet(self, pkt):
        """Process a captured DNS packet."""
        try:
            if not pkt.haslayer(DNS) or not pkt.haslayer(DNSQR):
                return

            dns_layer = pkt[DNS]
            # Only process queries (qr=0), not responses
            if dns_layer.qr != 0:
                return

            ip_layer = pkt[IP] if pkt.haslayer(IP) else None
            if not ip_layer:
                return

            source_ip = ip_layer.src

            # Skip our own DNS queries
            if self._my_ip and source_ip == self._my_ip:
                return

            domain = dns_layer.qd.qname.decode("utf-8", errors="ignore").rstrip(".")
            query_type = _get_query_type(dns_layer.qd.qtype)

            if _should_ignore(domain):
                return

            # Get source MAC if available
            source_mac = ""
            if pkt.haslayer("Ether"):
                source_mac = pkt["Ether"].src

            logger.debug(f"DNS: {source_ip} ({source_mac}) -> {domain} ({query_type})")

            log_dns_query(
                source_ip=source_ip,
                domain=domain,
                query_type=query_type,
                source_mac=source_mac,
            )

        except Exception as e:
            logger.error(f"Error processing DNS packet: {e}")

    def _sniff_loop(self):
        """Run the packet sniffer."""
        logger.info(f"DNS sniffer started on interface: {self._iface}")
        try:
            sniff(
                iface=self._iface,
                filter="udp port 53",
                prn=self._process_packet,
                store=False,
                stop_filter=lambda _: not self._running,
            )
        except Exception as e:
            logger.error(f"Sniffer error: {e}")
            self._running = False

    def start(self):
        """Start the DNS sniffer in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._sniff_loop, daemon=True)
        self._thread.start()
        logger.info("DNS sniffer is running.")

    def stop(self):
        """Stop the DNS sniffer."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("DNS sniffer stopped.")

    @property
    def is_running(self) -> bool:
        return self._running
