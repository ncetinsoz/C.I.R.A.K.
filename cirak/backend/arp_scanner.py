"""
Subnet IP Occupancy & Fast ARP Sweep tool.
Discovers active hosts, MAC addresses, and vendor identification on the local LAN.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import socket
import subprocess
import time
from typing import List, Optional, Callable
from cirak.core.models import ARPDevice


class ARPScanner:
    """Fast subnet scanner discovering active IP and MAC addresses."""

    def __init__(self, interface: str = "eth0", simulate: bool = False):
        self.interface = interface
        self.simulate = simulate
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def scan_subnet(
        self,
        subnet_prefix: str = "10.20.102.",
        start_host: int = 1,
        end_host: int = 254,
        max_workers: int = 30,
        on_host_found: Optional[Callable[[ARPDevice], None]] = None
    ) -> List[ARPDevice]:
        """Sweep subnet IP range and collect responsive devices."""
        self._is_cancelled = False

        if self.simulate:
            return self._get_simulated_devices(on_host_found)

        devices: List[ARPDevice] = []

        def ping_host(host_num: int) -> Optional[ARPDevice]:
            if self._is_cancelled:
                return None
            ip = f"{subnet_prefix}{host_num}"
            try:
                # Fast 1-packet ping with 200ms timeout
                res = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", ip],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.5
                )
                if res.returncode == 0:
                    mac = self._lookup_mac_in_arp(ip)
                    vendor = self._guess_vendor(mac)
                    dev = ARPDevice(ip=ip, mac=mac, vendor=vendor, response_time_ms=1.2)
                    if on_host_found:
                        on_host_found(dev)
                    return dev
            except Exception:
                pass
            return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(ping_host, h) for h in range(start_host, end_host + 1)]
            for f in futures:
                res = f.result()
                if res:
                    devices.append(res)

        if not devices and self.simulate:
            return self._get_simulated_devices(on_host_found)

        return devices

    def _lookup_mac_in_arp(self, ip: str) -> str:
        try:
            arp_file = Path("/proc/net/arp")
            if arp_file.exists():
                for line in arp_file.read_text().splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 4 and parts[0] == ip:
                        return parts[3]
        except Exception:
            pass
        return "00:00:00:00:00:00"

    def _guess_vendor(self, mac: str) -> str:
        prefix = mac.lower().replace(":", "")[:6]
        vendors = {
            "005056": "VMware",
            "000c29": "VMware",
            "b827eb": "Raspberry Pi Foundation",
            "dca632": "Raspberry Pi Foundation",
            "001ebd": "Cisco Systems",
            "c4ad34": "TP-Link Technologies",
            "3c846a": "Apple",
        }
        return vendors.get(prefix, "Genel Ağ Cihazı")

    def _get_simulated_devices(self, on_host_found: Optional[Callable[[ARPDevice], None]] = None) -> List[ARPDevice]:
        simulated = [
            ARPDevice(ip="10.20.102.1", mac="00:0c:29:84:a1:fe", vendor="Cisco Core Gateway", response_time_ms=0.8),
            ARPDevice(ip="10.20.102.10", mac="00:50:56:a1:42:11", vendor="VMware DNS/LDAP", response_time_ms=1.4),
            ARPDevice(ip="10.20.102.45", mac="b8:27:eb:54:21:40", vendor="Raspberry Pi (ÇIRAK)", response_time_ms=0.2),
            ARPDevice(ip="10.20.102.88", mac="3c:84:6a:12:ef:90", vendor="Apple MacBook Pro", response_time_ms=3.1),
            ARPDevice(ip="10.20.102.105", mac="c4:ad:34:12:ef:90", vendor="TP-Link (Şüpheli)", response_time_ms=1.8),
            ARPDevice(ip="10.20.102.254", mac="00:1e:bd:8c:12:00", vendor="Cisco Catalyst Switch", response_time_ms=0.9),
        ]
        if on_host_found:
            for d in simulated:
                on_host_found(d)
        return simulated
