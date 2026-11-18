"""
Layer 2: CDP (Cisco Discovery Protocol v1/v2), LLDP (IEEE 802.1AB), 802.1X NAC (EAPOL), and PVST+/STP Analyzer.
Features a continuous background L2 promiscuous sniffer so 60-second Cisco CDP beacons
and NAC-delayed port announcements are captured immediately without missing frames.
"""

import shutil
import socket
import struct
import subprocess
import threading
import time
from typing import Optional, Dict, Any
from cirak.backend.base import BaseTest
from cirak.backend.network_detector import NetworkDetector
from cirak.core.models import TestResult, TestStatus, LLDPInfo


class LLDPCdpTest(BaseTest):
    """Listens for CDP, LLDP, 802.1X EAPOL, and PVST+/STP BPDU frames with continuous background caching."""

    # Class-level continuous cache per interface so 60s CDP frames are never missed
    _bg_lock = threading.Lock()
    _bg_started = False
    _cached_cdp_lldp: Dict[str, LLDPInfo] = {}
    _cached_stp_nac: Dict[str, LLDPInfo] = {}
    _nac_active_ifaces: Dict[str, float] = {}
    _last_carrier_state: Dict[str, bool] = {}

    def __init__(self, interface: Optional[str] = None, timeout_sec: float = 3.0, simulate: bool = False):
        iface = interface or NetworkDetector.get_active_interface()
        super().__init__(name="2. Switch & Port (CDP/LLDP)", interface=iface, simulate=simulate)
        self.timeout_sec = timeout_sec
        if not simulate:
            self.ensure_background_listener(iface)

    @classmethod
    def ensure_background_listener(cls, iface: str = "eth0"):
        """Start lightweight background L2 sniffer thread once to catch 60s CDP beacons continuously."""
        with cls._bg_lock:
            if cls._bg_started:
                return
            cls._bg_started = True
            t = threading.Thread(target=cls._background_sniffer_loop, args=(iface,), daemon=True)
            t.start()

    @classmethod
    def get_cached_discovery(cls, iface: str = "eth0", max_age_sec: float = 180.0) -> Optional[Dict[str, Any]]:
        """Return latest full CDP/LLDP or NAC/STP telemetry from background sniffer or lldpd."""
        # 1. Check lldpd daemon first
        daemon_data = NetworkDetector.get_lldp_from_daemon(iface)
        if daemon_data and daemon_data.get("system_name"):
            if iface in cls._nac_active_ifaces and (time.time() - cls._nac_active_ifaces[iface] < 120):
                daemon_data["protocol"] = f"{daemon_data.get('protocol', 'CDP')} + 802.1X NAC"
                daemon_data["nac_active"] = True
            return daemon_data

        # 2. Check our continuous raw socket CDP/LLDP cache
        with cls._bg_lock:
            info = cls._cached_cdp_lldp.get(iface)
            if info and (time.time() - info.received_at < max_age_sec):
                d = dict(info.__dict__)
                if iface in cls._nac_active_ifaces and (time.time() - cls._nac_active_ifaces[iface] < 120):
                    if "NAC" not in d.get("protocol", ""):
                        d["protocol"] = f"{d.get('protocol', 'CDP')} + 802.1X NAC"
                    d["nac_active"] = True
                return d

            # 3. Check NAC / PVST+ cache if full CDP hasn't arrived yet
            stp_info = cls._cached_stp_nac.get(iface)
            if stp_info and (time.time() - stp_info.received_at < min(max_age_sec, 90.0)):
                d = dict(stp_info.__dict__)
                if "NAC" in d.get("protocol", "") or iface in cls._nac_active_ifaces:
                    d["nac_active"] = True
                return d

        return None

    @classmethod
    def _background_sniffer_loop(cls, default_iface: str):
        """Continuously listen for L2 multicast frames (CDP, LLDP, 802.1X EAPOL, PVST+ BPDU)."""
        parser_helper = cls(interface=default_iface, simulate=True)
        while True:
            iface = NetworkDetector.get_active_interface() or default_iface
            carrier = NetworkDetector.get_carrier(iface)

            # Reset cache when cable is unplugged or moved to another switch port!
            prev_carrier = cls._last_carrier_state.get(iface, False)
            cls._last_carrier_state[iface] = carrier
            if not carrier:
                with cls._bg_lock:
                    cls._cached_cdp_lldp.pop(iface, None)
                    cls._cached_stp_nac.pop(iface, None)
                    cls._nac_active_ifaces.pop(iface, None)
                time.sleep(1.0)
                continue

            if carrier and not prev_carrier:
                # Cable just plugged in! Trigger lldpd update to solicit neighbor response
                cls._trigger_l2_solicitation(iface)

            sock = None
            try:
                ETH_P_ALL = 3
                sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(ETH_P_ALL))
                sock.bind((iface, 0))
                sock.settimeout(2.0)

                # Enable PACKET_MR_PROMISC so Broadcom NIC passes all L2 multicast frames
                try:
                    if_idx = socket.if_nametoindex(iface)
                    mreq = struct.pack("IHH8s", if_idx, 1, 0, b"\x00" * 8)
                    sock.setsockopt(263, 1, mreq)
                except Exception:
                    pass

                session_end = time.time() + 30.0
                while time.time() < session_end and NetworkDetector.get_carrier(iface):
                    try:
                        packet, addr = sock.recvfrom(2048)
                    except socket.timeout:
                        continue
                    # Ignore outgoing frames transmitted by local lldpd daemon (PACKET_OUTGOING == 4)
                    if isinstance(addr, tuple) and len(addr) >= 3 and addr[2] == 4:
                        continue
                    parser_helper._process_raw_packet(iface, packet)
            except Exception:
                time.sleep(2.0)
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

    @staticmethod
    def _trigger_l2_solicitation(iface: str):
        """No-op passive mode: avoid triggering local lldpd self-broadcasts on the wire."""
        return

    def _process_raw_packet(self, iface: str, packet: bytes) -> Optional[LLDPInfo]:
        """Inspect a raw L2 Ethernet frame for LLDP, CDP, 802.1X EAPOL, or PVST+/STP (ignoring local 'cirak' frames)."""
        if len(packet) < 14:
            return None

        dst_mac = packet[0:6]
        src_mac = ":".join(f"{b:02x}" for b in packet[6:12])

        # CRITICAL: Ignore frames originating from our own Raspberry Pi NIC
        if NetworkDetector.is_local_device(mac_or_chassis=src_mac):
            return None

        eth_proto = struct.unpack("!H", packet[12:14])[0]
        payload_offset = 14
        dot1q_vlan: Optional[int] = None

        # Unwrap IEEE 802.1Q VLAN tag (0x8100)
        if eth_proto == 0x8100 and len(packet) >= 18:
            tci = struct.unpack("!H", packet[14:16])[0]
            dot1q_vlan = tci & 0x0FFF
            eth_proto = struct.unpack("!H", packet[16:18])[0]
            payload_offset = 18

        payload = packet[payload_offset:]

        # 1. IEEE 802.1AB LLDP (EtherType 0x88CC or dst 01:80:c2:00:00:0e)
        if eth_proto == 0x88CC or dst_mac == b"\x01\x80\xc2\x00\x00\x0e":
            info = self.parse_lldp_frame(payload, src_mac=src_mac, dot1q_vlan=dot1q_vlan)
            if info and not NetworkDetector.is_local_device(
                system_name=info.system_name,
                mac_or_chassis=info.chassis_id or src_mac,
                mgmt_ip=info.management_ip,
                system_descr=info.system_description,
            ):
                with self._bg_lock:
                    self._cached_cdp_lldp[iface] = info
                return info
            return None

        # 2. Cisco Discovery Protocol (CDP - Multicast 01:00:0c:cc:cc:cc)
        elif dst_mac == b"\x01\x00\x0c\xcc\xcc\xcc":
            info = self.parse_cdp_frame(payload, src_mac=src_mac, dot1q_vlan=dot1q_vlan)
            if info and not NetworkDetector.is_local_device(
                system_name=info.system_name,
                mac_or_chassis=info.chassis_id or src_mac,
                mgmt_ip=info.management_ip,
                system_descr=info.system_description,
            ):
                with self._bg_lock:
                    self._cached_cdp_lldp[iface] = info
                return info
            return None

        # 3. IEEE 802.1X Port-Based NAC / EAPOL (EtherType 0x888E or dst 01:80:c2:00:00:03)
        elif eth_proto == 0x888E or dst_mac == b"\x01\x80\xc2\x00\x00\x03":
            with self._bg_lock:
                self._nac_active_ifaces[iface] = time.time()
            nac_info = self.parse_eapol_nac_frame(payload, src_mac=src_mac, dot1q_vlan=dot1q_vlan)
            if nac_info:
                with self._bg_lock:
                    existing = self._cached_stp_nac.get(iface)
                    if existing and existing.vlan_id and not nac_info.vlan_id:
                        nac_info.vlan_id = existing.vlan_id
                    self._cached_stp_nac[iface] = nac_info
            return None

        # 4. Spanning Tree BPDU (IEEE STP 01:80:c2:00:00:00 or Cisco PVST+ 01:00:0c:cc:cc:cd)
        elif dst_mac in (b"\x01\x80\xc2\x00\x00\x00", b"\x01\x00\x0c\xcc\xcc\xcd"):
            stp_info = self.parse_stp_bpdu(payload, src_mac=src_mac, dot1q_vlan=dot1q_vlan, is_pvst=(dst_mac == b"\x01\x00\x0c\xcc\xcc\xcd"))
            if stp_info:
                with self._bg_lock:
                    if iface in self._nac_active_ifaces:
                        stp_info.protocol = "802.1X NAC + PVST+"
                        stp_info.system_description = "802.1X NAC Korumalı Port (CDP Periyodu Bekleniyor)"
                    self._cached_stp_nac[iface] = stp_info
            return None

        return None

    def run(self) -> TestResult:
        """Run L2 switch discovery (CDP, LLDP, 802.1X NAC, PVST+ BPDU, and MAC OUI inspection)."""
        start_time = time.time()

        if self.simulate:
            info = self._get_simulated_info()
            summary = f"[{info.protocol}] {info.system_name} | Port: {info.port_id} | VLAN: {info.vlan_id or 'Untagged'}"
            return self._create_result(
                status=TestStatus.PASSED,
                start_time=start_time,
                summary=summary,
                details=info.__dict__
            )

        # 1. Check if lldpd daemon or background CDP/LLDP cache already has full switch details
        cached = self.get_cached_discovery(self.interface)
        if cached and cached.get("protocol", "").startswith(("CDP", "LLDP")):
            proto = cached.get("protocol", "CDP/LLDP")
            summary = (
                f"[{proto}] {cached['system_name']} | Port: {cached['port_id']} "
                f"| VLAN: {cached.get('vlan_id') or 'Untagged'}"
            )
            status = TestStatus.WARNING if cached.get("is_unauthorized_switch") else TestStatus.PASSED
            return self._create_result(
                status=status,
                start_time=start_time,
                summary=summary,
                details=cached
            )

        # 2. Trigger active solicitation and sniff raw socket for full CDP/LLDP
        self._trigger_l2_solicitation(self.interface)
        info = self.capture_neighbor_info()
        if info and (info.system_name or info.port_id or info.chassis_id):
            if self.interface in self._nac_active_ifaces and "NAC" not in info.protocol:
                info.protocol = f"{info.protocol} + 802.1X NAC"
            summary = (
                f"[{info.protocol}] {info.system_name or info.vendor} | Port: {info.port_id or 'Bekleniyor'} "
                f"| VLAN: {info.vlan_id or 'Untagged'}"
            )
            status = TestStatus.WARNING if info.is_unauthorized_switch else TestStatus.PASSED
            return self._create_result(
                status=status,
                start_time=start_time,
                summary=summary,
                details=info.__dict__
            )

        # 3. Fallback L2 MAC / Gateway OUI inspection for unmanaged/unauthorized switches
        gw_info = NetworkDetector.get_default_gateway()
        gw_mac = NetworkDetector.get_gateway_mac(gw_info["gateway"]) if gw_info else None
        if gw_mac:
            vendor, is_unauth = NetworkDetector.identify_mac_vendor(gw_mac)
            if is_unauth:
                return self._create_result(
                    status=TestStatus.WARNING,
                    start_time=start_time,
                    summary=f"UYARI: Tüketici Cihazı ({vendor}) | CDP/LLDP Yok",
                    details={
                        "system_name": f"Yetkisiz/Yönetimsiz Cihaz ({vendor})",
                        "chassis_id": gw_mac,
                        "vendor": vendor,
                        "protocol": "L2-MAC",
                        "is_unauthorized_switch": True,
                    }
                )

        # 4. No CDP/LLDP packet received within window
        return self._create_result(
            status=TestStatus.WARNING,
            start_time=start_time,
            summary="CDP/LLDP Yanıtı Yok (60s Periyot Bekleniyor veya Yönetimsiz Switch)",
            details={
                "error": "No CDP/LLDP frames detected in listen window",
                "gateway_mac": gw_mac or "",
                "vendor": NetworkDetector.identify_mac_vendor(gw_mac)[0] if gw_mac else "Bilinmiyor",
            }
        )

    def _get_simulated_info(self) -> LLDPInfo:
        return LLDPInfo(
            chassis_id="94:33:d8:2a:01:ef",
            system_name="Catalyst-9300",
            system_description="Cisco IOS-XE Catalyst 9300 Series Switch",
            port_id="Gi1/0/24",
            port_description="Kenar Switch Port 24",
            vlan_id=102,
            vlan_name="Kampus-Veri",
            management_ip="10.20.0.254",
            ttl=180,
            protocol="CDP",
            vendor="Cisco Systems",
            capabilities="Switch, IGMP",
            is_unauthorized_switch=False,
        )

    def capture_neighbor_info(self) -> Optional[LLDPInfo]:
        """Sniff for CDP, LLDP, 802.1X EAPOL, or PVST+/STP BPDU frames on raw socket."""
        sock = None
        try:
            ETH_P_ALL = 3
            sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(ETH_P_ALL))
            sock.bind((self.interface, 0))
            sock.settimeout(0.8)

            try:
                if_idx = socket.if_nametoindex(self.interface)
                mreq = struct.pack("IHH8s", if_idx, 1, 0, b"\x00" * 8)
                sock.setsockopt(263, 1, mreq)
            except Exception:
                pass

            deadline = time.time() + self.timeout_sec
            while time.time() < deadline:
                if self.is_cancelled:
                    break
                # Check if lldpd or background thread caught a full CDP/LLDP frame in the meantime
                with self._bg_lock:
                    cached = self._cached_cdp_lldp.get(self.interface)
                    if cached and (time.time() - cached.received_at < 60):
                        return cached

                try:
                    packet, addr = sock.recvfrom(2048)
                except socket.timeout:
                    continue

                if isinstance(addr, tuple) and len(addr) >= 3 and addr[2] == 4:
                    continue

                full_info = self._process_raw_packet(self.interface, packet)
                if full_info:
                    return full_info

            # After full timeout, check daemon or fallback to NAC/PVST+ info if present
            daemon_data = NetworkDetector.get_lldp_from_daemon(self.interface)
            if daemon_data and daemon_data.get("system_name"):
                return LLDPInfo(**{k: v for k, v in daemon_data.items() if k in LLDPInfo.__dataclass_fields__})

            with self._bg_lock:
                return self._cached_cdp_lldp.get(self.interface) or self._cached_stp_nac.get(self.interface)
        except Exception:
            return None
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def parse_lldp_frame(
        self,
        payload: bytes,
        src_mac: str = "",
        dot1q_vlan: Optional[int] = None
    ) -> Optional[LLDPInfo]:
        """Parse IEEE 802.1AB LLDP TLVs."""
        info = LLDPInfo(protocol="LLDP", chassis_id=src_mac, vlan_id=dot1q_vlan)
        offset = 0
        total_len = len(payload)

        try:
            while offset + 2 <= total_len:
                tlv_header = struct.unpack("!H", payload[offset:offset + 2])[0]
                tlv_type = (tlv_header >> 9) & 0x7F
                tlv_len = tlv_header & 0x01FF
                offset += 2

                if offset + tlv_len > total_len:
                    break

                val = payload[offset:offset + tlv_len]
                offset += tlv_len

                if tlv_type == 0:
                    break
                elif tlv_type == 1:
                    cid = self._format_chassis_id(val)
                    if cid:
                        info.chassis_id = cid
                elif tlv_type == 2:
                    info.port_id = self._format_port_id(val)
                elif tlv_type == 3 and len(val) >= 2:
                    info.ttl = struct.unpack("!H", val[:2])[0]
                elif tlv_type == 4:
                    info.port_description = val.decode("utf-8", errors="ignore").strip()
                elif tlv_type == 5:
                    info.system_name = val.decode("utf-8", errors="ignore").strip()
                elif tlv_type == 6:
                    descr = val.decode("utf-8", errors="ignore").strip()
                    info.system_description = descr.splitlines()[0] if descr else ""
                elif tlv_type == 8:
                    mgmt = self._format_mgmt_address(val)
                    if mgmt:
                        info.management_ip = mgmt
                elif tlv_type == 127:
                    vlan = self._parse_org_vlan(val)
                    if vlan is not None:
                        info.vlan_id = vlan

            vendor, is_unauth = NetworkDetector.identify_mac_vendor(info.chassis_id or src_mac)
            info.vendor = vendor
            info.is_unauthorized_switch = is_unauth
            return info if (info.system_name or info.port_id) else None
        except Exception:
            return None

    def parse_cdp_frame(
        self,
        payload: bytes,
        src_mac: str = "",
        dot1q_vlan: Optional[int] = None
    ) -> Optional[LLDPInfo]:
        """
        Parse Cisco Discovery Protocol (CDPv1/v2) frame.
        Extracts Device ID, Port ID, Platform/Model, Native VLAN, Management IP, and Capabilities.
        """
        info = LLDPInfo(protocol="CDP", chassis_id=src_mac, vlan_id=dot1q_vlan)
        try:
            # Strip 8-byte 802.2 LLC + SNAP header (aa:aa:03:00:00:0c:20:00) if present
            if len(payload) >= 8 and payload[:3] == b"\xaa\xaa\x03":
                if payload[6:8] != b"\x20\x00":
                    return None
                payload = payload[8:]
            elif len(payload) > 8 and payload[1] in (60, 120, 180):
                payload = payload[8:]

            if len(payload) < 4:
                return None

            info.ttl = payload[1]
            offset = 4

            while offset + 4 <= len(payload):
                field_type, field_len = struct.unpack("!HH", payload[offset:offset + 4])
                if field_len < 4:
                    break
                val_len = field_len - 4
                offset += 4
                if offset + val_len > len(payload):
                    break
                val = payload[offset:offset + val_len]
                offset += val_len

                if field_type == 0x0001:  # Device ID (Switch Hostname)
                    info.system_name = val.decode("utf-8", errors="ignore").strip("\x00").strip()
                elif field_type in (0x0002, 0x0016):  # Addresses / Management IP
                    mgmt_ip = self._parse_cdp_addresses(val)
                    if mgmt_ip and not info.management_ip:
                        info.management_ip = mgmt_ip
                elif field_type == 0x0003:  # Port ID (e.g. GigabitEthernet1/0/24)
                    info.port_id = val.decode("utf-8", errors="ignore").strip("\x00").strip()
                elif field_type == 0x0004 and len(val) >= 4:  # Capabilities
                    cap_bits = struct.unpack("!I", val[:4])[0]
                    caps = []
                    if cap_bits & 0x01:
                        caps.append("Router")
                    if cap_bits & 0x08:
                        caps.append("Switch")
                    if cap_bits & 0x10:
                        caps.append("Host")
                    if cap_bits & 0x20:
                        caps.append("IGMP")
                    info.capabilities = ", ".join(caps)
                elif field_type == 0x0005 and not info.system_description:  # Software Version
                    ver_lines = [ln.strip() for ln in val.decode("utf-8", errors="ignore").splitlines() if ln.strip()]
                    if ver_lines:
                        info.system_description = ver_lines[0][:60]
                elif field_type == 0x0006:  # Platform / Hardware Model (e.g. cisco WS-C2960X-24TS-L)
                    platform = val.decode("utf-8", errors="ignore").strip("\x00").strip()
                    if platform:
                        info.system_description = platform
                elif field_type == 0x000A and len(val) >= 2:  # Native VLAN
                    info.vlan_id = struct.unpack("!H", val[:2])[0]
                elif field_type == 0x000B and len(val) >= 1:  # Duplex
                    dup = "Full Duplex" if val[0] == 1 else "Half Duplex"
                    if not info.port_description:
                        info.port_description = dup

            vendor, is_unauth = NetworkDetector.identify_mac_vendor(info.chassis_id or src_mac)
            info.vendor = vendor if vendor != "Kurumsal Ağ Cihazı" else "Cisco Systems"
            info.is_unauthorized_switch = is_unauth
            return info if (info.system_name or info.port_id) else None
        except Exception:
            return None

    def parse_eapol_nac_frame(
        self,
        payload: bytes,
        src_mac: str = "",
        dot1q_vlan: Optional[int] = None
    ) -> Optional[LLDPInfo]:
        """Parse IEEE 802.1X EAPOL frame emitted by NAC-enforced switch ports."""
        if not src_mac:
            return None
        vendor, is_unauth = NetworkDetector.identify_mac_vendor(src_mac)
        return LLDPInfo(
            chassis_id=src_mac,
            system_name=f"{vendor} Switch (NAC Aktif)",
            system_description="802.1X Port Erişim Kontrolü (CDP Paketi Bekleniyor...)",
            port_id="802.1X Denetiminde",
            vlan_id=dot1q_vlan,
            protocol="802.1X NAC",
            vendor=vendor,
            is_unauthorized_switch=is_unauth,
        )

    def parse_stp_bpdu(
        self,
        payload: bytes,
        src_mac: str = "",
        dot1q_vlan: Optional[int] = None,
        is_pvst: bool = False
    ) -> Optional[LLDPInfo]:
        """
        Extract switch MAC, vendor, Root/Bridge ID, and Cisco PVST+ Native VLAN ID from BPDU.
        In Cisco PVST+ frames (01:00:0c:cc:cc:cd), the trailing 6-byte TLV (00:00:00:02:VLAN_HI:VLAN_LO)
        carries the exact port VLAN ID even on 802.1X NAC restricted ports!
        """
        if not src_mac:
            return None

        vlan_id = dot1q_vlan
        port_str = "STP Aktif (CDP Bekleniyor)"

        # Extract Port ID and PVST+ PVID TLV if present
        try:
            # Standard 802.2 LLC (3 bytes) + BPDU header (35 bytes): Port ID is at LLC+29..31
            if is_pvst and len(payload) >= 48:
                # Cisco PVST+ SNAP (8 bytes) + 35-byte BPDU + PVID TLV (0x0000, len 0x0002, 2-byte VLAN = 49 bytes)
                port_num = struct.unpack("!H", payload[8 + 29: 8 + 31])[0] & 0x00FF
                if port_num > 0:
                    port_str = f"Port #{port_num} (PVST+)"
                idx = payload.rfind(b"\x00\x00\x00\x02")
                if idx != -1 and idx + 6 <= len(payload):
                    vlan_id = struct.unpack("!H", payload[idx + 4: idx + 6])[0]
            elif len(payload) >= 38 and payload[:3] == b"\x42\x42\x03":
                port_num = struct.unpack("!H", payload[3 + 29: 3 + 31])[0] & 0x00FF
                if port_num > 0:
                    port_str = f"Port #{port_num} (STP)"
        except Exception:
            pass

        vendor, is_unauth = NetworkDetector.identify_mac_vendor(src_mac)
        if is_pvst and vendor == "Kurumsal Ağ Cihazı":
            vendor = "Cisco Systems"

        return LLDPInfo(
            chassis_id=src_mac,
            system_name=f"{vendor} Switch",
            system_description="PVST+/STP Aktif (60sn CDP Periyodu Bekleniyor)",
            port_id=port_str,
            vlan_id=vlan_id,
            protocol="PVST+" if is_pvst else "STP-BPDU",
            vendor=vendor,
            is_unauthorized_switch=is_unauth,
        )

    @staticmethod
    def _parse_cdp_addresses(val: bytes) -> str:
        """Extract IPv4 address from CDP Address TLV (0x0002 / 0x0016)."""
        try:
            if len(val) < 9:
                return ""
            num_addrs = struct.unpack("!I", val[:4])[0]
            offset = 4
            for _ in range(min(num_addrs, 8)):
                if offset + 2 > len(val):
                    break
                pt_type = val[offset]
                pt_len = val[offset + 1]
                offset += 2
                if offset + pt_len + 2 > len(val):
                    break
                proto = val[offset:offset + pt_len]
                offset += pt_len
                addr_len = struct.unpack("!H", val[offset:offset + 2])[0]
                offset += 2
                if offset + addr_len > len(val):
                    break
                addr_bytes = val[offset:offset + addr_len]
                offset += addr_len
                if pt_type == 1 and proto == b"\xcc" and addr_len == 4:
                    return socket.inet_ntoa(addr_bytes)
        except Exception:
            pass
        return ""

    def _format_chassis_id(self, val: bytes) -> str:
        if not val:
            return ""
        if val[0] == 4 and len(val[1:]) == 6:
            return ":".join(f"{b:02x}" for b in val[1:])
        return val[1:].decode("utf-8", errors="ignore").strip()

    def _format_port_id(self, val: bytes) -> str:
        if not val:
            return ""
        if val[0] == 3 and len(val[1:]) == 6:
            return ":".join(f"{b:02x}" for b in val[1:])
        return val[1:].decode("utf-8", errors="ignore").strip()

    def _format_mgmt_address(self, val: bytes) -> str:
        if len(val) >= 6 and val[0] == 5 and val[1] == 1:
            return socket.inet_ntoa(val[2:6])
        return ""

    def _parse_org_vlan(self, val: bytes) -> Optional[int]:
        if len(val) >= 6 and val[:3] == b"\x00\x80\xc2" and val[3] == 1:
            return struct.unpack("!H", val[4:6])[0]
        return None
