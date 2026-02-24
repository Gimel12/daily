"""
Mode A — DNS Proxy Server
Runs a DNS server on port 53 that logs every query and forwards to upstream DNS.
Requires router DHCP to point devices to this machine's IP.
"""
import socket
import struct
import threading
import logging
from dnslib import DNSRecord, DNSHeader, QTYPE, RR
from dnslib.server import DNSServer, DNSHandler, BaseResolver

from config import UPSTREAM_DNS, UPSTREAM_DNS_ALT, DNS_PROXY_PORT, IGNORE_DOMAINS
from db import log_dns_query

logger = logging.getLogger("dns_proxy")


def _should_ignore(domain: str) -> bool:
    """Check if a domain matches any ignore pattern."""
    domain = domain.rstrip(".")
    for pattern in IGNORE_DOMAINS:
        if pattern.startswith("*."):
            suffix = pattern[1:]  # e.g. ".local"
            if domain.endswith(suffix) or domain == pattern[2:]:
                return True
        elif domain == pattern:
            return True
    return False


class LoggingResolver(BaseResolver):
    """DNS resolver that logs queries and forwards to upstream."""

    def __init__(self, upstream: str = UPSTREAM_DNS, upstream_alt: str = UPSTREAM_DNS_ALT):
        self.upstream = upstream
        self.upstream_alt = upstream_alt

    def resolve(self, request, handler):
        """Resolve a DNS request by forwarding and logging."""
        qname = str(request.q.qname)
        qtype = QTYPE[request.q.qtype]
        client_ip = handler.client_address[0]

        # Log the query (unless ignored)
        if not _should_ignore(qname):
            logger.info(f"DNS query from {client_ip}: {qname} ({qtype})")
            try:
                log_dns_query(
                    source_ip=client_ip,
                    domain=qname.rstrip("."),
                    query_type=qtype,
                )
            except Exception as e:
                logger.error(f"Failed to log DNS query: {e}")

        # Forward to upstream DNS
        try:
            response = self._forward(request.pack(), self.upstream)
        except Exception:
            try:
                response = self._forward(request.pack(), self.upstream_alt)
            except Exception as e:
                logger.error(f"Upstream DNS failed: {e}")
                reply = request.reply()
                reply.header.rcode = 2  # SERVFAIL
                return reply

        return DNSRecord.parse(response)

    def _forward(self, data: bytes, upstream: str, port: int = 53, timeout: float = 5.0) -> bytes:
        """Forward raw DNS packet to upstream server."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(data, (upstream, port))
            response, _ = sock.recvfrom(4096)
            return response
        finally:
            sock.close()


class DNSProxyServer:
    """Manages the DNS proxy server lifecycle."""

    def __init__(self):
        self.server = None
        self._running = False

    def start(self):
        """Start the DNS proxy server."""
        resolver = LoggingResolver()
        self.server = DNSServer(
            resolver,
            port=DNS_PROXY_PORT,
            address="0.0.0.0",
            tcp=False,
        )
        self._running = True
        logger.info(f"DNS Proxy starting on port {DNS_PROXY_PORT} (forwarding to {UPSTREAM_DNS})")
        self.server.start_thread()
        logger.info("DNS Proxy is running.")

    def stop(self):
        """Stop the DNS proxy server."""
        if self.server:
            self.server.stop()
            self._running = False
            logger.info("DNS Proxy stopped.")

    @property
    def is_running(self) -> bool:
        return self._running
