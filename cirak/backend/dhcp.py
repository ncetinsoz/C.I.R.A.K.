"""
Layer 3: DHCP Negotiation & Rogue DHCP Hunter.
Measures DHCP response time, extracts IP lease configuration,
and detects unauthorized / rogue DHCP servers (rogue modems/routers) on the LAN.
"""

import glob
from pathlib import Path
import random
import socket
import struct
import time
from typing import List, Optional
from cirak.backend.base import BaseTest
from cirak.backend.network_detector import NetworkDetector
from cirak.core.models import TestResult, TestStatus, DHCPInfo
from cirak import config


class DHCPTest(BaseTest):
    """Executes DHCP Discover / Offer transaction and detects rogue servers."""

    def __init__(
        self,
        interface: Optional[str] = None,
        timeout_sec: float = 2.5,
        approved_servers: Optional[List[str]] = None,
        simulate: bool = False,
    ):
        iface = interface or NetworkDetector.get_active_interface()
        super().__init__(name="3. DHCP Sunucusu", interface=iface, simulate=simulate)
        self.timeout_sec = timeout_sec
        self.approved_servers = approved_servers or config.APPROVED_DHCP_SERVERS

    def run(self) -> TestResult:
        """Execute DHCP query and return real network lease details."""
        start_time = time.time()

        if self.simulate:
            primary = self._get_simulated_authorized_offer()
            return self._create_result(
                status=TestStatus.PASSED,
                start_time=start_time,
                summary=f"IP: {primary.offered_ip} | Sunucu: {primary.server_id} ({primary.response_time_ms:.1f} ms)",
                details=primary.__dict__
            )

        # 1. Try active broadcast DHCPDISCOVER
        offers = self.discover_dhcp_servers()
        if offers:
            primary = offers[0]
            has_rogue = any(o.is_rogue for o in offers)
            status = TestStatus.WARNING if has_rogue else TestStatus.PASSED
            summary = f"IP: {primary.offered_ip} | Sunucu: {primary.server_id} ({primary.response_time_ms:.1f} ms)"
            if has_rogue:
                summary += " [UYARI: Yetkisiz DHCP!]"
            return self._create_result(
                status=status,
                start_time=start_time,
                summary=summary,
                details={
                    "offered_ip": primary.offered_ip,
                    "server_id": primary.server_id,
                    "router": primary.router,
                    "dns_servers": primary.dns_servers,
                    "response_time_ms": primary.response_time_ms,
                    "is_rogue": primary.is_rogue,
                    "offers_count": len(offers),
                }
            )

        # 2. If active probe got no response, check real assigned IP on the interface
        real_ip = NetworkDetector.get_ip_address_cidr(self.interface)
        if real_ip:
            gw_info = NetworkDetector.get_default_gateway()
            gw_ip = gw_info["gateway"] if gw_info else "Mevcut Ağ"
            return self._create_result(
                status=TestStatus.PASSED,
                start_time=start_time,
                summary=f"IP: {real_ip} | Ağ Geçidi: {gw_ip}",
                details={"offered_ip": real_ip, "server_id": gw_ip, "interface": self.interface}
            )

        # 3. No IP and no DHCP response
        return self._create_result(
            status=TestStatus.FAILED,
            start_time=start_time,
            summary="DHCP Yanıtı Yok (IP Alınamadı)",
            details={"error": "No DHCPOFFER and no assigned IPv4 on interface"}
        )

    def _get_simulated_authorized_offer(self) -> DHCPInfo:
        return DHCPInfo(
            offered_ip="10.20.102.88",
            subnet_mask="255.255.255.0",
            router="10.20.102.1",
            dns_servers=["10.20.0.10", "10.20.0.11"],
            domain_name="kampus.edu.tr",
            lease_time_sec=86400,
            server_id="10.20.0.1",
            server_mac="00:50:56:bf:21:40",
            response_time_ms=124.0,
            is_rogue=False,
        )

    def _get_simulated_rogue_offer(self) -> DHCPInfo:
        return DHCPInfo(
            offered_ip="192.168.1.105",
            subnet_mask="255.255.255.0",
            router="192.168.1.1",
            dns_servers=["192.168.1.1"],
            domain_name="home",
            lease_time_sec=3600,
            server_id="192.168.1.1",
            server_mac="c4:ad:34:12:ef:90",
            response_time_ms=18.0,
            is_rogue=True,
        )

    def discover_dhcp_servers(self) -> List[DHCPInfo]:
        """Broadcast DHCPDISCOVER and collect DHCPOFFER packets."""
        offers: List[DHCPInfo] = []
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Essential for Linux RPi when dhcpcd/NetworkManager is running on UDP 68
            sock.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_REUSEPORT", 15), 1)

            try:
                # SO_BINDTODEVICE (requires CAP_NET_RAW)
                sock.setsockopt(socket.SOL_SOCKET, 25, self.interface.encode())
            except Exception:
                pass

            sock.bind(("", 68))
            sock.settimeout(self.timeout_sec)

            xid = random.randint(1, 0xFFFFFFFF)
            packet = self._build_dhcp_discover(xid)
            t_send = time.time()
            sock.sendto(packet, ("255.255.255.255", 67))

            deadline = time.time() + self.timeout_sec
            while time.time() < deadline:
                if self.is_cancelled:
                    break
                try:
                    data, _ = sock.recvfrom(2048)
                    rtt = (time.time() - t_send) * 1000.0
                    parsed = self._parse_dhcp_offer(data, rtt)
                    if parsed:
                        if self.approved_servers and parsed.server_id not in self.approved_servers:
                            parsed.is_rogue = True
                        offers.append(parsed)
                except socket.timeout:
                    break
        except Exception:
            pass
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

        return offers

    def _build_dhcp_discover(self, xid: int) -> bytes:
        op = 1
        htype = 1
        hlen = 6
        hops = 0
        secs = 0
        flags = 0x8000
        ciaddr = b"\x00" * 4
        yiaddr = b"\x00" * 4
        siaddr = b"\x00" * 4
        giaddr = b"\x00" * 4
        chaddr = bytes([random.randint(0x00, 0xFF) for _ in range(6)]) + (b"\x00" * 10)
        sname = b"\x00" * 64
        file_ = b"\x00" * 128
        cookie = b"\x63\x82\x53\x63"

        options = (
            b"\x35\x01\x01"
            b"\x37\x04\x01\x03\x06\x0f"
            b"\xff"
        )

        header = struct.pack("!BBBBIHH4s4s4s4s16s64s128s4s",
            op, htype, hlen, hops, xid, secs, flags,
            ciaddr, yiaddr, siaddr, giaddr, chaddr, sname, file_, cookie
        )
        return header + options

    def _parse_dhcp_offer(self, data: bytes, rtt_ms: float) -> Optional[DHCPInfo]:
        if len(data) < 240:
            return None

        magic_cookie = data[236:240]
        if magic_cookie != b"\x63\x82\x53\x63":
            return None

        yiaddr = socket.inet_ntoa(data[16:20])
        chaddr_bytes = data[28:34]
        chaddr_mac = ":".join(f"{b:02x}" for b in chaddr_bytes)

        info = DHCPInfo(
            offered_ip=yiaddr,
            server_mac=chaddr_mac,
            response_time_ms=round(rtt_ms, 1),
        )

        offset = 240
        while offset < len(data):
            opt_type = data[offset]
            if opt_type == 255:
                break
            if opt_type == 0:
                offset += 1
                continue

            if offset + 1 >= len(data):
                break
            opt_len = data[offset + 1]
            opt_data = data[offset + 2: offset + 2 + opt_len]
            offset += 2 + opt_len

            if opt_type == 1 and opt_len == 4:
                info.subnet_mask = socket.inet_ntoa(opt_data)
            elif opt_type == 3 and opt_len >= 4:
                info.router = socket.inet_ntoa(opt_data[:4])
            elif opt_type == 6 and opt_len >= 4:
                info.dns_servers = [
                    socket.inet_ntoa(opt_data[i:i+4])
                    for i in range(0, opt_len, 4)
                ]
            elif opt_type == 15:
                info.domain_name = opt_data.decode("utf-8", errors="ignore")
            elif opt_type == 51 and opt_len == 4:
                info.lease_time_sec = struct.unpack("!I", opt_data)[0]
            elif opt_type == 54 and opt_len == 4:
                info.server_id = socket.inet_ntoa(opt_data)

        return info if info.server_id else None
