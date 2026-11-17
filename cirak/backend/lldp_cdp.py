"""
Layer 2: LLDP (IEEE 802.1AB) and CDP (Cisco Discovery Protocol) packet parser.
Discovers switch model, port ID, VLAN tag, and management address.
"""

import socket
import struct
import time
from typing import Optional, Dict, Any
from cirak.backend.base import BaseTest
from cirak.backend.network_detector import NetworkDetector
from cirak.core.models import TestResult, TestStatus, LLDPInfo


class LLDPCdpTest(BaseTest):
    """Listens for LLDP and CDP broadcast frames or queries system lldpd daemon."""

    def __init__(self, interface: Optional[str] = None, timeout_sec: float = 2.5, simulate: bool = False):
        iface = interface or NetworkDetector.get_active_interface()
        super().__init__(name="2. Switch & Port (LLDP)", interface=iface, simulate=simulate)
        self.timeout_sec = timeout_sec

    def run(self) -> TestResult:
        """Run L2 discovery."""
        start_time = time.time()

        if self.simulate:
            info = self._get_simulated_info()
            summary = f"Switch: {info.system_name} | Port: {info.port_id} | VLAN: {info.vlan_id or 'Untagged'}"
            return self._create_result(
                status=TestStatus.PASSED,
                start_time=start_time,
                summary=summary,
                details=info.__dict__
            )

        # 1. Query lldpd daemon directly (fastest, 0 packet loss)
        daemon_data = NetworkDetector.get_lldp_from_daemon(self.interface)
        if daemon_data and daemon_data.get("system_name"):
            summary = (
                f"Switch: {daemon_data['system_name']} | Port: {daemon_data['port_id']} "
                f"| VLAN: {daemon_data.get('vlan_id') or 'Untagged'}"
            )
            return self._create_result(
                status=TestStatus.PASSED,
                start_time=start_time,
                summary=summary,
                details=daemon_data
            )

        # 2. Try raw socket sniffing
        info = self.capture_neighbor_info()
        if info and info.system_name:
            summary = f"Switch: {info.system_name} | Port: {info.port_id} | VLAN: {info.vlan_id or 'Untagged'}"
            return self._create_result(
                status=TestStatus.PASSED,
                start_time=start_time,
                summary=summary,
                details=info.__dict__
            )

        # 3. No LLDP packet received
        return self._create_result(
            status=TestStatus.WARNING,
            start_time=start_time,
            summary="LLDP/CDP Yanıtı Yok (Yönetimsiz Switch veya Bekleniyor)",
            details={"error": "No LLDP frames detected on interface"}
        )

    def _get_simulated_info(self) -> LLDPInfo:
        return LLDPInfo(
            chassis_id="00:1e:bd:8c:12:00",
            system_name="Catalyst-9300",
            port_id="Gi1/0/24",
            port_description="Kenar Switch Port 24",
            vlan_id=102,
            management_ip="10.20.0.254",
            ttl=120,
            protocol="LLDP",
        )

    def capture_neighbor_info(self) -> Optional[LLDPInfo]:
        """Sniff for LLDP or CDP frames on raw socket."""
        try:
            ETH_P_ALL = 3
            ETH_P_LLDP = 0x88cc
            sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(ETH_P_ALL))
            sock.bind((self.interface, 0))
            sock.settimeout(self.timeout_sec)

            deadline = time.time() + self.timeout_sec
            while time.time() < deadline:
                if self.is_cancelled:
                    break
                try:
                    packet, _ = sock.recvfrom(2048)
                except socket.timeout:
                    break

                if len(packet) >= 14:
                    eth_proto = struct.unpack("!H", packet[12:14])[0]
                    if eth_proto == ETH_P_LLDP:
                        info = self.parse_lldp_frame(packet[14:])
                        if info:
                            sock.close()
                            return info
                    elif packet[0:6] == b"\x01\x00\x0c\xcc\xcc\xcc":
                        info = self.parse_cdp_frame(packet[14:])
                        if info:
                            sock.close()
                            return info

            sock.close()
        except Exception:
            pass

        return None

    def parse_lldp_frame(self, payload: bytes) -> Optional[LLDPInfo]:
        """Parse IEEE 802.1AB LLDP TLVs."""
        info = LLDPInfo(protocol="LLDP")
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
                    info.chassis_id = self._format_chassis_id(val)
                elif tlv_type == 2:
                    info.port_id = self._format_port_id(val)
                elif tlv_type == 3 and len(val) >= 2:
                    info.ttl = struct.unpack("!H", val[:2])[0]
                elif tlv_type == 4:
                    info.port_description = val.decode("utf-8", errors="ignore").strip()
                elif tlv_type == 5:
                    info.system_name = val.decode("utf-8", errors="ignore").strip()
                elif tlv_type == 8:
                    info.management_ip = self._format_mgmt_address(val)
                elif tlv_type == 127:
                    vlan = self._parse_org_vlan(val)
                    if vlan is not None:
                        info.vlan_id = vlan

            return info if info.system_name or info.port_id else None
        except Exception:
            return None

    def parse_cdp_frame(self, payload: bytes) -> Optional[LLDPInfo]:
        """Parse Cisco CDP payload."""
        info = LLDPInfo(protocol="CDP")
        try:
            if len(payload) > 8:
                payload = payload[8:]
            if len(payload) < 4:
                return None
            info.ttl = payload[1]
            offset = 4

            while offset + 4 <= len(payload):
                field_type, field_len = struct.unpack("!HH", payload[offset:offset + 4])
                offset += 4
                val_len = field_len - 4
                if val_len < 0 or offset + val_len > len(payload):
                    break
                val = payload[offset:offset + val_len]
                offset += val_len

                if field_type == 0x0001:
                    info.system_name = val.decode("utf-8", errors="ignore").strip()
                elif field_type == 0x0003:
                    info.port_id = val.decode("utf-8", errors="ignore").strip()
                elif field_type == 0x000a and len(val) >= 2:
                    info.vlan_id = struct.unpack("!H", val[:2])[0]

            return info if info.system_name else None
        except Exception:
            return None

    def _format_chassis_id(self, val: bytes) -> str:
        if not val:
            return ""
        if val[0] == 4 and len(val[1:]) == 6:
            return ":".join(f"{b:02x}" for b in val[1:])
        return val[1:].decode("utf-8", errors="ignore").strip()

    def _format_port_id(self, val: bytes) -> str:
        if not val:
            return ""
        return val[1:].decode("utf-8", errors="ignore").strip()

    def _format_mgmt_address(self, val: bytes) -> str:
        if len(val) >= 5 and val[0] == 5 and val[1] == 1:
            return socket.inet_ntoa(val[2:6])
        return ""

    def _parse_org_vlan(self, val: bytes) -> Optional[int]:
        if len(val) >= 6 and val[:3] == b"\x00\x80\xc2" and val[3] == 1:
            return struct.unpack("!H", val[4:6])[0]
        return None
