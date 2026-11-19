"""
RFC 5227 IPv4 Address Conflict Detection (ACD) & Active ARP Probe Analyzer.
Detects:
  1. Duplicate IP / IP Conflicts (two different MAC addresses claiming the same IPv4)
  2. Default Gateway ARP Spoofing / MAC inconsistency
  3. Live RFC 5227 ARP Probes (Sender IP 0.0.0.0) & Gratuitous ARP broadcasts on the local VLAN
"""

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import time
from typing import Dict, List, Optional, Set
from cirak.backend.network_detector import NetworkDetector


@dataclass
class ARPConflictReport:
    interface: str
    local_ip: str
    gateway_ip: str
    has_conflict: bool = False
    conflicts: List[str] = field(default_factory=list)
    verified_nodes: List[str] = field(default_factory=list)
    arp_probes_captured: int = 0
    gratuitous_arps_captured: int = 0
    active_arp_entries: int = 0
    duration_ms: float = 0.0
    summary: str = ""


class ARPConflictDetector:
    """Executes active L2 ARP probing and passive RFC 5227 conflict analysis."""

    def __init__(self, interface: Optional[str] = None, listen_sec: float = 2.2, simulate: bool = False):
        self.interface = interface or NetworkDetector.get_active_interface()
        self.listen_sec = listen_sec
        self.simulate = simulate

    def run_scan(self) -> ARPConflictReport:
        t0 = time.perf_counter()

        if self.simulate:
            time.sleep(0.1)
            return ARPConflictReport(
                interface=self.interface,
                local_ip="194.27.65.131",
                gateway_ip="194.27.65.1",
                has_conflict=False,
                conflicts=[],
                verified_nodes=[
                    "Cihaz IP (194.27.65.131): Çakışma Yok (Tekil MAC) ✓",
                    "Ağ Geçidi (194.27.65.1): 94:33:d8:2a:01:ef (Cisco Systems) ✓",
                ],
                arp_probes_captured=3,
                gratuitous_arps_captured=1,
                active_arp_entries=18,
                duration_ms=(time.perf_counter() - t0) * 1000.0,
                summary="IP Çakışması Yok | ARP Tablosu Tutarlı",
            )

        ip_cidr = NetworkDetector.get_ip_address_cidr(self.interface) or ""
        local_ip = ip_cidr.split("/")[0] if "/" in ip_cidr else ip_cidr
        local_mac = (NetworkDetector.get_mac_address(self.interface) or "").lower()
        gw_info = NetworkDetector.get_default_gateway()
        gw_ip = gw_info.get("gateway", "") if gw_info else ""

        ip_to_macs: Dict[str, Set[str]] = {}
        conflicts: List[str] = []
        verified: List[str] = []
        probes_seen = 0
        garp_seen = 0

        # 1. Read kernel /proc/net/arp table first
        arp_path = Path("/proc/net/arp")
        if arp_path.exists():
            try:
                for line in arp_path.read_text().splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 6:
                        ip_addr = parts[0].strip()
                        mac_addr = parts[3].strip().lower()
                        if mac_addr and mac_addr != "00:00:00:00:00:00":
                            ip_to_macs.setdefault(ip_addr, set()).add(mac_addr)
            except Exception:
                pass

        # 2. Active Raw Socket ARP Probe + L2 ARP Sniffing (RFC 5227)
        raw_ok, raw_probes, raw_garps = self._raw_arp_probe_and_listen(
            local_ip=local_ip,
            local_mac=local_mac,
            gw_ip=gw_ip,
            ip_to_macs=ip_to_macs,
        )
        probes_seen += raw_probes
        garp_seen += raw_garps

        # 3. Fallback / Supplement with arping -D (Duplicate Address Detection) if available
        if local_ip and shutil.which("arping"):
            try:
                res = subprocess.run(
                    ["arping", "-D", "-I", self.interface, "-c", "2", "-w", "1", local_ip],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.8,
                )
                # In arping -D mode, exit code 1 means a duplicate IP replied!
                if res.returncode == 1 and "Unicast reply" in res.stdout:
                    for ln in res.stdout.splitlines():
                        if "[" in ln and "]" in ln:
                            dup_mac = ln.split("[")[1].split("]")[0].strip().lower()
                            if dup_mac and dup_mac != local_mac:
                                ip_to_macs.setdefault(local_ip, set()).add(dup_mac)
                                if local_mac:
                                    ip_to_macs[local_ip].add(local_mac)
            except Exception:
                pass

        # 4. Analyze collected IP -> MAC mappings for conflicts
        if local_ip:
            local_claimants = ip_to_macs.get(local_ip, set()) - ({local_mac} if local_mac else set())
            if local_claimants:
                bad_mac = next(iter(local_claimants))
                vendor, _ = NetworkDetector.identify_mac_vendor(bad_mac)
                conflicts.append(f"KRİTİK: Cihaz IP'niz ({local_ip}) başka bir cihazda aktif! MAC: {bad_mac} ({vendor})")
            else:
                verified.append(f"Cihaz IP ({local_ip}): Çakışma Yok (Tekil) ✓")

        if gw_ip:
            gw_macs = ip_to_macs.get(gw_ip, set())
            if not gw_macs:
                gw_m = NetworkDetector.get_gateway_mac(gw_ip)
                if gw_m:
                    gw_macs.add(gw_m.lower())
            if len(gw_macs) > 1:
                mac_list = ", ".join(sorted(gw_macs))
                conflicts.append(f"KRİTİK: Ağ Geçidi ({gw_ip}) için çoklu MAC yanıtı (ARP Spoofing/Çakışma): {mac_list}")
            elif len(gw_macs) == 1:
                g_mac = next(iter(gw_macs))
                vendor, _ = NetworkDetector.identify_mac_vendor(g_mac)
                verified.append(f"Gateway ({gw_ip}): {g_mac} ({vendor}) ✓")

        for ip_k, mac_set in sorted(ip_to_macs.items()):
            if ip_k in (local_ip, gw_ip):
                continue
            if len(mac_set) > 1:
                m_str = " & ".join(sorted(mac_set))
                conflicts.append(f"IP Çakışması ({ip_k}): {m_str}")

        has_conflict = len(conflicts) > 0
        summary = (
            f"🚨 {len(conflicts)} IP ÇAKIŞMASI TESPİT EDİLDİ!"
            if has_conflict
            else f"✓ IP Çakışması Yok ({len(ip_to_macs)} ARP Kaydı, {probes_seen} Probe)"
        )

        return ARPConflictReport(
            interface=self.interface,
            local_ip=local_ip or "Yok",
            gateway_ip=gw_ip or "Yok",
            has_conflict=has_conflict,
            conflicts=conflicts,
            verified_nodes=verified,
            arp_probes_captured=probes_seen,
            gratuitous_arps_captured=garp_seen,
            active_arp_entries=len(ip_to_macs),
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            summary=summary,
        )

    def _raw_arp_probe_and_listen(
        self,
        local_ip: str,
        local_mac: str,
        gw_ip: str,
        ip_to_macs: Dict[str, Set[str]],
    ) -> tuple[bool, int, int]:
        """Send active RFC 5227 ARP Probe & Who-Has frames and inspect incoming ARP packets."""
        sock = None
        probes_cnt = 0
        garp_cnt = 0
        try:
            ETH_P_ARP = 0x0806
            sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ARP))
            sock.bind((self.interface, 0))
            sock.settimeout(0.4)

            if local_mac and len(local_mac.split(":")) == 6:
                src_mac_bytes = bytes(int(x, 16) for x in local_mac.split(":"))
                # 1. Send RFC 5227 ARP Probe for our own IP (Sender IP = 0.0.0.0, Target IP = local_ip)
                if local_ip:
                    probe_pkt = self.build_arp_request(src_mac_bytes, "0.0.0.0", local_ip)
                    sock.send(probe_pkt)
                    probes_cnt += 1
                # 2. Send ARP Who-Has for Default Gateway
                if gw_ip and local_ip:
                    gw_pkt = self.build_arp_request(src_mac_bytes, local_ip, gw_ip)
                    sock.send(gw_pkt)
                    probes_cnt += 1

            deadline = time.time() + self.listen_sec
            while time.time() < deadline:
                try:
                    pkt, addr = sock.recvfrom(2048)
                except socket.timeout:
                    continue
                # Ignore our own outgoing packets (PACKET_OUTGOING == 4)
                if isinstance(addr, tuple) and len(addr) >= 3 and addr[2] == 4:
                    continue
                if len(pkt) < 42:
                    continue

                eth_type = struct.unpack("!H", pkt[12:14])[0]
                arp_offset = 14
                if eth_type == 0x8100 and len(pkt) >= 46:
                    eth_type = struct.unpack("!H", pkt[16:18])[0]
                    arp_offset = 18
                if eth_type != 0x0806:
                    continue

                arp_hdr = pkt[arp_offset: arp_offset + 28]
                if len(arp_hdr) < 28:
                    continue
                htype, ptype, hlen, plen, oper = struct.unpack("!HHBBH", arp_hdr[:8])
                if htype != 1 or ptype != 0x0800 or hlen != 6 or plen != 4:
                    continue

                sha = ":".join(f"{b:02x}" for b in arp_hdr[8:14]).lower()
                spa = socket.inet_ntoa(arp_hdr[14:18])
                tpa = socket.inet_ntoa(arp_hdr[24:28])

                if sha == local_mac:
                    continue

                # RFC 5227 ARP Probe from another host (spa == 0.0.0.0)
                if spa == "0.0.0.0":
                    probes_cnt += 1
                    continue

                # Gratuitous ARP (spa == tpa)
                if spa == tpa:
                    garp_cnt += 1

                if sha != "00:00:00:00:00:00":
                    ip_to_macs.setdefault(spa, set()).add(sha)

            return True, probes_cnt, garp_cnt
        except Exception:
            return False, probes_cnt, garp_cnt
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    @staticmethod
    def build_arp_request(src_mac: bytes, sender_ip: str, target_ip: str) -> bytes:
        """Build a 42-byte Ethernet + IPv4 ARP Request (or RFC 5227 ARP Probe when sender_ip='0.0.0.0')."""
        dst_mac = b"\xff\xff\xff\xff\xff\xff"
        eth_hdr = dst_mac + src_mac + struct.pack("!H", 0x0806)
        arp_payload = struct.pack(
            "!HHBBH6s4s6s4s",
            1,          # Hardware type: Ethernet (1)
            0x0800,     # Protocol type: IPv4 (0x0800)
            6,          # Hardware size: 6
            4,          # Protocol size: 4
            1,          # Opcode: ARP Request (1)
            src_mac,
            socket.inet_aton(sender_ip),
            b"\x00" * 6,
            socket.inet_aton(target_ip),
        )
        return eth_hdr + arp_payload
