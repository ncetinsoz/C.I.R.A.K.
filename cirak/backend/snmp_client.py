"""
Zero-Dependency Pure-Python SNMPv2c Client & Switch Port/Sensor Analyzer.
Encodes and decodes ASN.1 / BER SNMPv2c GET and GETNEXT PDUs directly over UDP/161.
Extracts:
  - System Identity: sysName, sysDescr (IOS/Firmware), sysUpTime, sysLocation
  - Hardware Sensors: Switch Chassis Temperature (°C) & CPU Load (%) (Cisco & Standard MIBs)
  - Port Status Table (IF-MIB): ifDescr/ifName, ifAdminStatus (Up/Admin-Down),
    ifOperStatus (Up/Down/Err-Disabled), ifSpeed (Mbps), ifInErrors/ifOutErrors, ifAlias (Port Description)
"""

from dataclasses import dataclass, field
import socket
import time
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class SNMPPortInfo:
    index: int
    name: str
    admin_status: str       # "UP", "ADMIN-DOWN", "TESTING"
    oper_status: str        # "UP", "DOWN", "DORMANT"
    speed_mbps: int
    alias: str = ""
    in_errors: int = 0
    out_errors: int = 0

    @property
    def display_state(self) -> str:
        if self.admin_status == "ADMIN-DOWN":
            return "KAPALI (Admin-Down)"
        if self.oper_status == "UP":
            return "AÇIK (UP / Aktif)"
        return "BOŞTA (Link Down)"


@dataclass
class SNMPSwitchReport:
    target_ip: str
    community: str
    reachable: bool
    sys_name: str = ""
    sys_descr: str = ""
    uptime_str: str = ""
    location: str = ""
    temperature_c: Optional[int] = None
    cpu_load_pct: Optional[int] = None
    ports: List[SNMPPortInfo] = field(default_factory=list)
    total_ports: int = 0
    up_ports: int = 0
    down_ports: int = 0
    admin_down_ports: int = 0
    query_time_ms: float = 0.0
    error_message: str = ""


class SNMPClient:
    """Lightweight ASN.1 BER SNMPv2c client over UDP port 161."""

    # Standard MIB-II & Cisco Enterprise OIDs
    OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
    OID_SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
    OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"
    OID_SYS_LOCATION = "1.3.6.1.2.1.1.6.0"

    # Cisco Environmental Monitor Temperature & CPU Busy %
    OID_CISCO_TEMP_1 = "1.3.6.1.4.1.9.9.13.1.3.1.3.1"
    OID_CISCO_TEMP_1008 = "1.3.6.1.4.1.9.9.13.1.3.1.3.1008"
    OID_CISCO_CPU_5SEC = "1.3.6.1.4.1.9.9.109.1.1.1.1.6.1"
    OID_CISCO_CPU_OLD = "1.3.6.1.4.1.9.2.1.56.0"

    # IF-MIB Table prefixes
    OID_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
    OID_IF_SPEED = "1.3.6.1.2.1.2.2.1.5"
    OID_IF_ADMIN = "1.3.6.1.2.1.2.2.1.7"
    OID_IF_OPER = "1.3.6.1.2.1.2.2.1.8"
    OID_IF_IN_ERR = "1.3.6.1.2.1.2.2.1.14"
    OID_IF_OUT_ERR = "1.3.6.1.2.1.2.2.1.20"
    OID_IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"
    OID_IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"
    OID_IF_ALIAS = "1.3.6.1.2.1.31.1.1.1.18"

    def __init__(
        self,
        target_ip: str,
        community: str = "public",
        port: int = 161,
        timeout_sec: float = 1.2,
        simulate: bool = False,
    ):
        self.target_ip = target_ip.strip()
        self.community = community.strip() or "public"
        self.port = port
        self.timeout_sec = timeout_sec
        self.simulate = simulate
        self._req_id = 1001

    def query_switch(self, max_ports: int = 56) -> SNMPSwitchReport:
        """Query switch system scalars, temperature/CPU sensors, and interface port table."""
        t0 = time.perf_counter()

        if self.simulate:
            time.sleep(0.1)
            return self._get_simulated_report(t0)

        if not self.target_ip:
            return SNMPSwitchReport(
                target_ip="",
                community=self.community,
                reachable=False,
                error_message="Geçerli bir Switch Yönetim IP adresi girilmedi.",
            )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout_sec)

        try:
            # 1. Query System Scalars (sysName, sysDescr, sysUpTime, sysLocation)
            scalars = self._snmp_get_multi(
                sock,
                [
                    self.OID_SYS_NAME,
                    self.OID_SYS_DESCR,
                    self.OID_SYS_UPTIME,
                    self.OID_SYS_LOCATION,
                ],
            )
            if not scalars:
                return SNMPSwitchReport(
                    target_ip=self.target_ip,
                    community=self.community,
                    reachable=False,
                    query_time_ms=(time.perf_counter() - t0) * 1000.0,
                    error_message=(
                        f"{self.target_ip} adresinden SNMPv2c yanıtı alınamadı "
                        f"(Community: '{self.community}' hatalı veya UDP/161 kapalı)."
                    ),
                )

            sys_name = str(scalars.get(self.OID_SYS_NAME, "") or self.target_ip)
            sys_descr = str(scalars.get(self.OID_SYS_DESCR, "") or "SNMP Destekli Ağ Cihazı")
            raw_uptime = scalars.get(self.OID_SYS_UPTIME, 0)
            uptime_str = self._format_timeticks(raw_uptime if isinstance(raw_uptime, int) else 0)
            location = str(scalars.get(self.OID_SYS_LOCATION, "") or "")

            # 2. Query Optional Cisco Temperature & CPU OIDs
            sensors = self._snmp_get_multi(
                sock,
                [
                    self.OID_CISCO_TEMP_1,
                    self.OID_CISCO_TEMP_1008,
                    self.OID_CISCO_CPU_5SEC,
                    self.OID_CISCO_CPU_OLD,
                ],
            )
            temp_c: Optional[int] = None
            for t_oid in (self.OID_CISCO_TEMP_1008, self.OID_CISCO_TEMP_1):
                val = sensors.get(t_oid)
                if isinstance(val, int) and 10 <= val <= 115:
                    temp_c = val
                    break

            cpu_pct: Optional[int] = None
            for c_oid in (self.OID_CISCO_CPU_5SEC, self.OID_CISCO_CPU_OLD):
                val = sensors.get(c_oid)
                if isinstance(val, int) and 0 <= val <= 100:
                    cpu_pct = val
                    break

            # If exact scalar instance didn't match, try 1-step GETNEXT on Cisco temperature table
            if temp_c is None:
                t_walk = self._snmp_walk_column(sock, "1.3.6.1.4.1.9.9.13.1.3.1.3", max_rows=3)
                for v in t_walk.values():
                    if isinstance(v, int) and 10 <= v <= 115:
                        temp_c = v
                        break

            # 3. Walk IF-MIB Columns for Port Status Table
            names_map = self._snmp_walk_column(sock, self.OID_IF_NAME, max_rows=max_ports)
            if not names_map:
                names_map = self._snmp_walk_column(sock, self.OID_IF_DESCR, max_rows=max_ports)

            admin_map = self._snmp_walk_column(sock, self.OID_IF_ADMIN, max_rows=max_ports)
            oper_map = self._snmp_walk_column(sock, self.OID_IF_OPER, max_rows=max_ports)
            high_spd_map = self._snmp_walk_column(sock, self.OID_IF_HIGH_SPEED, max_rows=max_ports)
            spd_map = self._snmp_walk_column(sock, self.OID_IF_SPEED, max_rows=max_ports) if not high_spd_map else {}
            alias_map = self._snmp_walk_column(sock, self.OID_IF_ALIAS, max_rows=max_ports)
            in_err_map = self._snmp_walk_column(sock, self.OID_IF_IN_ERR, max_rows=max_ports)
            out_err_map = self._snmp_walk_column(sock, self.OID_IF_OUT_ERR, max_rows=max_ports)

            ports: List[SNMPPortInfo] = []
            up_cnt = 0
            down_cnt = 0
            adm_down_cnt = 0

            for if_idx in sorted(names_map.keys()):
                p_name = str(names_map[if_idx]).strip()
                if not p_name or p_name.lower().startswith(("null", "Nu0", "stack", "unrouted")):
                    continue

                adm_val = admin_map.get(if_idx, 1)
                oper_val = oper_map.get(if_idx, 2)

                adm_str = "UP" if adm_val == 1 else ("ADMIN-DOWN" if adm_val == 2 else "TESTING")
                oper_str = "UP" if oper_val == 1 else ("DOWN" if oper_val == 2 else "DORMANT")

                if adm_str == "ADMIN-DOWN":
                    adm_down_cnt += 1
                elif oper_str == "UP":
                    up_cnt += 1
                else:
                    down_cnt += 1

                spd_mbps = 0
                if if_idx in high_spd_map and isinstance(high_spd_map[if_idx], int):
                    spd_mbps = int(high_spd_map[if_idx])
                elif if_idx in spd_map and isinstance(spd_map[if_idx], int):
                    spd_mbps = int(spd_map[if_idx]) // 1_000_000

                ports.append(
                    SNMPPortInfo(
                        index=if_idx,
                        name=p_name,
                        admin_status=adm_str,
                        oper_status=oper_str,
                        speed_mbps=spd_mbps,
                        alias=str(alias_map.get(if_idx, "") or "")[:28],
                        in_errors=int(in_err_map.get(if_idx, 0) or 0),
                        out_errors=int(out_err_map.get(if_idx, 0) or 0),
                    )
                )

            return SNMPSwitchReport(
                target_ip=self.target_ip,
                community=self.community,
                reachable=True,
                sys_name=sys_name,
                sys_descr=sys_descr,
                uptime_str=uptime_str,
                location=location,
                temperature_c=temp_c,
                cpu_load_pct=cpu_pct,
                ports=ports,
                total_ports=len(ports),
                up_ports=up_cnt,
                down_ports=down_cnt,
                admin_down_ports=adm_down_cnt,
                query_time_ms=(time.perf_counter() - t0) * 1000.0,
            )
        except Exception as e:
            return SNMPSwitchReport(
                target_ip=self.target_ip,
                community=self.community,
                reachable=False,
                query_time_ms=(time.perf_counter() - t0) * 1000.0,
                error_message=f"SNMP sorgu hatası: {e}",
            )
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _snmp_get_multi(self, sock: socket.socket, oids: List[str]) -> Dict[str, Any]:
        """Send a single SNMPv2c GET request for multiple OIDs and return {oid: value}."""
        self._req_id += 1
        pkt = self.build_snmp_packet(self.community, oids, pdu_tag=0xA0, req_id=self._req_id)
        try:
            sock.sendto(pkt, (self.target_ip, self.port))
            resp, _ = sock.recvfrom(8192)
            varbinds = self.parse_snmp_response(resp)
            return {oid: val for oid, val in varbinds if val is not None}
        except Exception:
            return {}

    def _snmp_walk_column(self, sock: socket.socket, prefix_oid: str, max_rows: int = 56) -> Dict[int, Any]:
        """Walk an SNMP table column using GETNEXT requests and return {row_index: value}."""
        result: Dict[int, Any] = {}
        current_oid = prefix_oid
        prefix_dot = prefix_oid + "."

        for _ in range(max_rows):
            self._req_id += 1
            pkt = self.build_snmp_packet(self.community, [current_oid], pdu_tag=0xA1, req_id=self._req_id)
            try:
                sock.sendto(pkt, (self.target_ip, self.port))
                resp, _ = sock.recvfrom(8192)
                varbinds = self.parse_snmp_response(resp)
                if not varbinds:
                    break
                next_oid, val = varbinds[0]
                if not next_oid.startswith(prefix_dot) or val is None or next_oid == current_oid:
                    break
                suffix = next_oid[len(prefix_dot):]
                idx_str = suffix.split(".")[0]
                if idx_str.isdigit():
                    result[int(idx_str)] = val
                current_oid = next_oid
            except Exception:
                break

        return result

    # =========================================================================
    # Pure-Python ASN.1 BER Encoder / Decoder for SNMPv2c
    # =========================================================================
    @staticmethod
    def _encode_length(length: int) -> bytes:
        if length < 0x80:
            return bytes([length])
        elif length <= 0xFF:
            return bytes([0x81, length])
        else:
            return bytes([0x82, (length >> 8) & 0xFF, length & 0xFF])

    @classmethod
    def _encode_tlv(cls, tag: int, value: bytes) -> bytes:
        return bytes([tag]) + cls._encode_length(len(value)) + value

    @classmethod
    def _encode_integer(cls, val: int) -> bytes:
        if val == 0:
            return cls._encode_tlv(0x02, b"\x00")
        out = []
        v = val
        while v > 0:
            out.append(v & 0xFF)
            v >>= 8
        if out[-1] & 0x80:
            out.append(0x00)
        out.reverse()
        return cls._encode_tlv(0x02, bytes(out))

    @classmethod
    def _encode_oid(cls, oid_str: str) -> bytes:
        parts = [int(x) for x in oid_str.strip(".").split(".") if x.isdigit()]
        if len(parts) < 2:
            parts = [1, 3, 6, 1]
        encoded = bytearray([parts[0] * 40 + parts[1]])
        for sub in parts[2:]:
            if sub == 0:
                encoded.append(0)
            else:
                stack = []
                while sub > 0:
                    stack.append(sub & 0x7F)
                    sub >>= 7
                for i in range(len(stack) - 1, 0, -1):
                    encoded.append(stack[i] | 0x80)
                encoded.append(stack[0])
        return cls._encode_tlv(0x06, bytes(encoded))

    @classmethod
    def build_snmp_packet(
        cls,
        community: str,
        oids: List[str],
        pdu_tag: int = 0xA0,  # 0xA0 = GetRequest, 0xA1 = GetNextRequest
        req_id: int = 1,
    ) -> bytes:
        """Build an ASN.1 BER encoded SNMPv2c packet."""
        vbs = bytearray()
        for oid in oids:
            vb = cls._encode_oid(oid) + cls._encode_tlv(0x05, b"")  # NULL value
            vbs += cls._encode_tlv(0x30, vb)
        varbind_list = cls._encode_tlv(0x30, bytes(vbs))

        pdu_body = (
            cls._encode_integer(req_id)
            + cls._encode_integer(0)  # error-status = 0
            + cls._encode_integer(0)  # error-index = 0
            + varbind_list
        )
        pdu = cls._encode_tlv(pdu_tag, pdu_body)

        msg_body = (
            cls._encode_integer(1)  # SNMP version 1 == SNMPv2c
            + cls._encode_tlv(0x04, community.encode("utf-8"))
            + pdu
        )
        return cls._encode_tlv(0x30, msg_body)

    @staticmethod
    def _decode_length(data: bytes, offset: int) -> Tuple[int, int]:
        first = data[offset]
        offset += 1
        if not (first & 0x80):
            return first, offset
        num_bytes = first & 0x7F
        length = 0
        for _ in range(num_bytes):
            length = (length << 8) | data[offset]
            offset += 1
        return length, offset

    @staticmethod
    def _decode_oid(val: bytes) -> str:
        if not val:
            return ""
        first = val[0]
        parts = [first // 40, first % 40]
        sub = 0
        for b in val[1:]:
            sub = (sub << 7) | (b & 0x7F)
            if not (b & 0x80):
                parts.append(sub)
                sub = 0
        return ".".join(str(x) for x in parts)

    @classmethod
    def parse_snmp_response(cls, data: bytes) -> List[Tuple[str, Any]]:
        """Decode ASN.1 BER SNMPv2c GetResponse packet into a list of (oid_str, value)."""
        out: List[Tuple[str, Any]] = []
        try:
            if not data or data[0] != 0x30:
                return out
            _, idx = cls._decode_length(data, 1)

            # 1. Version (INTEGER)
            if data[idx] != 0x02:
                return out
            v_len, idx = cls._decode_length(data, idx + 1)
            idx += v_len

            # 2. Community (OCTET STRING)
            if data[idx] != 0x04:
                return out
            c_len, idx = cls._decode_length(data, idx + 1)
            idx += c_len

            # 3. GetResponse PDU (0xA2)
            if data[idx] != 0xA2:
                return out
            _, idx = cls._decode_length(data, idx + 1)

            # Skip request-id, error-status, error-index (3 INTEGERs)
            for _ in range(3):
                if data[idx] != 0x02:
                    return out
                i_len, idx = cls._decode_length(data, idx + 1)
                idx += i_len

            # VarBindList (SEQUENCE 0x30)
            if data[idx] != 0x30:
                return out
            vbl_len, idx = cls._decode_length(data, idx + 1)
            end_vbl = idx + vbl_len

            while idx < end_vbl:
                if data[idx] != 0x30:
                    break
                vb_len, idx = cls._decode_length(data, idx + 1)
                vb_end = idx + vb_len

                # OID (0x06)
                if data[idx] != 0x06:
                    break
                oid_len, idx = cls._decode_length(data, idx + 1)
                oid_str = cls._decode_oid(data[idx: idx + oid_len])
                idx += oid_len

                # Value TLV
                val_tag = data[idx]
                val_len, idx = cls._decode_length(data, idx + 1)
                raw_val = data[idx: idx + val_len]
                idx = vb_end

                # Decode value by ASN.1 tag
                if val_tag in (0x02, 0x41, 0x42, 0x43):  # INTEGER, Counter32, Gauge32, TimeTicks
                    int_val = 0
                    for b in raw_val:
                        int_val = (int_val << 8) | b
                    out.append((oid_str, int_val))
                elif val_tag == 0x46:  # Counter64
                    int_val = 0
                    for b in raw_val:
                        int_val = (int_val << 8) | b
                    out.append((oid_str, int_val))
                elif val_tag == 0x04:  # OCTET STRING
                    out.append((oid_str, raw_val.decode("utf-8", errors="ignore").strip()))
                elif val_tag == 0x06:  # OID
                    out.append((oid_str, cls._decode_oid(raw_val)))
                elif val_tag == 0x40 and len(raw_val) == 4:  # IpAddress
                    out.append((oid_str, ".".join(str(b) for b in raw_val)))
                elif val_tag in (0x80, 0x81, 0x82):  # noSuchObject / noSuchInstance / endOfMibView
                    out.append((oid_str, None))
                else:
                    out.append((oid_str, None))
        except Exception:
            pass
        return out

    @staticmethod
    def _format_timeticks(ticks: int) -> str:
        if ticks <= 0:
            return "--"
        total_sec = ticks // 100
        days, rem = divmod(total_sec, 86400)
        hours, rem = divmod(rem, 3600)
        mins, _ = divmod(rem, 60)
        if days > 0:
            return f"{days} gün, {hours} sa, {mins} dk"
        return f"{hours} saat, {mins} dk"

    def _get_simulated_report(self, t0: float) -> SNMPSwitchReport:
        sim_ports = [
            SNMPPortInfo(1, "Gi1/0/1", "UP", "UP", 1000, "Uplink-Core-Fiber", 0, 0),
            SNMPPortInfo(2, "Gi1/0/2", "UP", "UP", 1000, "AP-Kutuphane-Kat1", 0, 0),
            SNMPPortInfo(3, "Gi1/0/3", "UP", "DOWN", 0, "Oda-104-Data", 0, 0),
            SNMPPortInfo(4, "Gi1/0/4", "ADMIN-DOWN", "DOWN", 0, "Kapatildi-ErrDisable", 14, 0),
            SNMPPortInfo(5, "Gi1/0/5", "UP", "UP", 1000, "CIRAK-Test-Portu", 0, 0),
            SNMPPortInfo(6, "Gi1/0/6", "ADMIN-DOWN", "DOWN", 0, "Misafir-Pasif-Port", 0, 0),
            SNMPPortInfo(7, "Gi1/0/7", "UP", "DOWN", 0, "Lab-PC-07", 0, 0),
            SNMPPortInfo(8, "Gi1/0/8", "UP", "UP", 100, "IP-Telefon-108", 0, 0),
        ]
        return SNMPSwitchReport(
            target_ip=self.target_ip or "194.27.65.2",
            community=self.community,
            reachable=True,
            sys_name="DEU-SW-2960X-K1",
            sys_descr="Cisco IOS Software, C2960X Software (C2960X-UNIVERSALK9-M), Version 15.2(7)E4",
            uptime_str="42 gün, 11 sa, 18 dk",
            location="DEÜ Mühendislik Sistem Odası K1",
            temperature_c=41,
            cpu_load_pct=12,
            ports=sim_ports,
            total_ports=len(sim_ports),
            up_ports=4,
            down_ports=2,
            admin_down_ports=2,
            query_time_ms=(time.perf_counter() - t0) * 1000.0,
        )
