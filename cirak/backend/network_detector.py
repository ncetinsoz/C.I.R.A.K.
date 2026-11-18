"""
Real Network Hardware Detection & System Telemetry Engine for Ç.I.R.A.K.
Reads actual Linux kernel sysfs, procfs, routing tables, and daemon state.
Target Environment: Raspberry Pi 4 (Raspberry Pi OS Lite / Linux).
"""

import glob
import json
from pathlib import Path
import os
import re
import socket
import subprocess
import time
from typing import Dict, Any, List, Optional, Tuple


class NetworkDetector:
    """Provides direct, zero-overhead access to real network hardware status."""

    @staticmethod
    def list_interfaces() -> List[str]:
        """List all network interfaces excluding loopback."""
        ifaces = []
        for p in glob.glob("/sys/class/net/*"):
            name = os.path.basename(p)
            if name != "lo":
                ifaces.append(name)
        return ifaces

    @classmethod
    def get_active_interface(cls) -> str:
        """
        Determine the primary active interface.
        Priority:
          1. eth0 if cable plugged in (carrier=1)
          2. Any non-lo interface with carrier=1
          3. Interface with default route in /proc/net/route
          4. eth0 if present, else first available interface, else lo
        """
        ifaces = cls.list_interfaces()

        # 1. Check eth0 (official Raspberry Pi wired port)
        if "eth0" in ifaces and cls.get_carrier("eth0"):
            return "eth0"

        # 2. Check any other wired interface with link
        for iface in ifaces:
            if cls.get_carrier(iface):
                return iface

        # 3. Check default gateway interface
        gw_info = cls.get_default_gateway()
        if gw_info and gw_info.get("interface") in ifaces:
            return gw_info["interface"]

        # 4. Check if wlan0 has an assigned IP
        if "wlan0" in ifaces and cls.get_ip_address_cidr("wlan0"):
            return "wlan0"

        if "eth0" in ifaces:
            return "eth0"

        return ifaces[0] if ifaces else "lo"

    @classmethod
    def get_carrier(cls, iface: Optional[str] = None) -> bool:
        """Check if physical cable is connected (carrier == 1)."""
        target = iface or cls.get_active_interface()
        carrier_path = Path(f"/sys/class/net/{target}/carrier")
        if carrier_path.exists():
            try:
                return carrier_path.read_text().strip() == "1"
            except Exception:
                return False
        return False

    @classmethod
    def get_speed_duplex(cls, iface: Optional[str] = None) -> Tuple[int, str]:
        """Query negotiated link speed (Mbps) and duplex mode."""
        target = iface or cls.get_active_interface()
        speed = 0
        duplex = "Unknown"

        speed_path = Path(f"/sys/class/net/{target}/speed")
        if speed_path.exists():
            try:
                val = int(speed_path.read_text().strip())
                if val > 0:
                    speed = val
            except Exception:
                speed = 0

        duplex_path = Path(f"/sys/class/net/{target}/duplex")
        if duplex_path.exists():
            try:
                duplex = duplex_path.read_text().strip().capitalize() + " Duplex"
            except Exception:
                duplex = "Unknown"

        return speed, duplex

    @classmethod
    def get_ip_address_cidr(cls, iface: Optional[str] = None) -> Optional[str]:
        """
        Extract the real assigned IPv4 address and CIDR prefix (e.g. 192.168.1.105/24).
        """
        target = iface or cls.get_active_interface()
        try:
            import netifaces
            addrs = netifaces.ifaddresses(target)
            inet_list = addrs.get(netifaces.AF_INET)
            if inet_list:
                for entry in inet_list:
                    ip = entry.get("addr")
                    netmask = entry.get("netmask")
                    if ip and not ip.startswith("127."):
                        if netmask:
                            cidr = sum(bin(int(x)).count("1") for x in netmask.split("."))
                            return f"{ip}/{cidr}"
                        return ip
        except Exception:
            pass

        # Fallback via 'ip -br addr show'
        try:
            res = subprocess.run(
                ["ip", "-br", "-4", "addr", "show", target],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1
            )
            if res.returncode == 0:
                parts = res.stdout.strip().split()
                if len(parts) >= 3 and "/" in parts[2]:
                    return parts[2]
        except Exception:
            pass

        return None

    @staticmethod
    def get_default_gateway() -> Optional[Dict[str, str]]:
        """Parse Linux /proc/net/route to find the default route."""
        route_file = Path("/proc/net/route")
        if not route_file.exists():
            return None

        try:
            for line in route_file.read_text().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 8:
                    iface = parts[0]
                    dest = parts[1]
                    gateway_hex = parts[2]
                    flags = int(parts[3], 16)

                    # Destination 00000000 and RTF_GATEWAY flag (0x2)
                    if dest == "00000000" and (flags & 0x2):
                        gw_int = int(gateway_hex, 16)
                        gw_ip = ".".join(str((gw_int >> (8 * i)) & 0xFF) for i in range(4))
                        return {"gateway": gw_ip, "interface": iface}
        except Exception:
            pass

        return None

    @staticmethod
    def get_gateway_mac(gateway_ip: str) -> Optional[str]:
        """Read target IP's hardware MAC address from kernel ARP cache /proc/net/arp."""
        arp_file = Path("/proc/net/arp")
        if not arp_file.exists():
            return None

        try:
            # First pass: check existing cache
            for line in arp_file.read_text().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == gateway_ip:
                    mac = parts[3].lower()
                    if mac != "00:00:00:00:00:00":
                        return mac

            # Second pass: trigger quick 1-ping ARP probe to refresh cache
            subprocess.run(
                ["ping", "-c", "1", "-W", "1", gateway_ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1.2
            )
            for line in arp_file.read_text().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == gateway_ip:
                    mac = parts[3].lower()
                    if mac != "00:00:00:00:00:00":
                        return mac
        except Exception:
            pass

        return None

    @staticmethod
    def get_dns_servers() -> List[str]:
        """Extract configured nameservers from /etc/resolv.conf."""
        servers = []
        resolv = Path("/etc/resolv.conf")
        if resolv.exists():
            try:
                for line in resolv.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("nameserver"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] != "127.0.0.1":
                            servers.append(parts[1])
            except Exception:
                pass
        return servers

    _oui_cache: Dict[str, str] = {}

    @classmethod
    def identify_mac_vendor(cls, mac: str) -> Tuple[str, bool]:
        """
        Identify hardware manufacturer from MAC OUI prefix.
        Uses built-in enterprise/consumer tables AND system IEEE OUI databases
        (/usr/share/arp-scan/ieee-oui.txt, /usr/share/ieee-data/oui.txt).
        Returns (vendor_name, is_unauthorized_consumer_device).
        """
        if not mac or len(mac) < 8:
            return "Bilinmeyen Üretici", False

        oui = mac.lower().replace(":", "").replace("-", "").replace(".", "")[:6]
        if len(oui) < 6:
            return "Bilinmeyen Üretici", False

        # 1. Consumer / Unauthorized Desktop Switch & Router Vendors
        consumer_ouis = {
            "c4ad34": "TP-Link (Tüketici/Masaüstü)",
            "50c7bf": "TP-Link (Tüketici/Masaüstü)",
            "18a6f7": "TP-Link (Tüketici/Masaüstü)",
            "e8de27": "TP-Link (Tüketici/Masaüstü)",
            "f4f26d": "TP-Link (Tüketici/Masaüstü)",
            "c83a35": "Tenda Technology (Yetkisiz Cihaz)",
            "b0df3a": "Tenda Technology (Yetkisiz Cihaz)",
            "001b11": "D-Link (Masaüstü Switch/Modem)",
            "1cbdb9": "D-Link (Masaüstü Switch/Modem)",
            "50ff20": "Keenetic / Zyxel (Modem/Router)",
            "588bf3": "Zyxel Communications",
            "286c07": "Xiaomi (Tüketici Router)",
            "04d9f5": "ASUS (Tüketici Router)",
            "9c5322": "Mercusys (Masaüstü Switch)",
        }
        if oui in consumer_ouis:
            return consumer_ouis[oui], True

        # 2. Fast Built-in Enterprise Network Vendors
        enterprise_ouis = {
            "00000c": "Cisco Systems",
            "001ebd": "Cisco Systems",
            "9433d8": "Cisco Systems",
            "000c85": "Cisco Systems",
            "001b54": "Cisco Systems",
            "002497": "Cisco Systems",
            "2c542d": "Cisco Systems",
            "500604": "Cisco Systems",
            "68bc0c": "Cisco Systems",
            "70df2f": "Cisco Systems",
            "b0aa77": "Cisco Systems",
            "f872ea": "Cisco Systems",
            "d8b190": "Cisco Systems",
            "0017df": "Cisco Systems",
            "001906": "Cisco Systems",
            "001d71": "Cisco Systems",
            "002155": "Cisco Systems",
            "002290": "Cisco Systems",
            "002699": "Cisco Systems",
            "0026cb": "Cisco Systems",
            "04dad2": "Cisco Systems",
            "10f311": "Cisco Systems",
            "189c5d": "Cisco Systems",
            "203a07": "Cisco Systems",
            "34dbfe": "Cisco Systems",
            "3cecef": "Cisco Systems",
            "44ad08": "Cisco Systems",
            "5475d0": "Cisco Systems",
            "58ac78": "Cisco Systems",
            "64f69d": "Cisco Systems",
            "70105c": "Cisco Systems",
            "74a02f": "Cisco Systems",
            "84b802": "Cisco Systems",
            "88f031": "Cisco Systems",
            "a0f849": "Cisco Systems",
            "acf2c5": "Cisco Systems",
            "c0626b": "Cisco Systems",
            "c80084": "Cisco Systems",
            "dcd2fc": "Cisco Systems",
            "e4c722": "Cisco Systems",
            "f07f06": "Cisco Systems",
            "f4cfe2": "Cisco Systems",
            "001a1e": "Aruba / HPE",
            "204c03": "Aruba / HPE",
            "3821c7": "Aruba / HPE",
            "002561": "ProCurve / HPE",
            "2c233a": "HPE Networking",
            "000585": "Juniper Networks",
            "28c0da": "Juniper Networks",
            "54e032": "Juniper Networks",
            "000496": "Extreme Networks",
            "00e02b": "Extreme Networks",
            "001882": "Huawei Enterprise",
            "487b6b": "Huawei Enterprise",
            "000c42": "MikroTik",
            "d4ca6d": "MikroTik",
            "005056": "VMware Infrastructure",
            "000c29": "VMware Infrastructure",
        }
        if oui in enterprise_ouis:
            return enterprise_ouis[oui], False

        if oui in cls._oui_cache:
            v = cls._oui_cache[oui]
            is_unauth = any(k in v.lower() for k in ("tp-link", "tenda", "d-link", "mercusys", "xiaomi"))
            return v, is_unauth

        # 3. Search Linux System IEEE OUI Databases (/usr/share/arp-scan/ieee-oui.txt, etc.)
        oui_upper = oui.upper()
        oui_dashed = f"{oui_upper[0:2]}-{oui_upper[2:4]}-{oui_upper[4:6]}"
        oui_files = [
            Path("/usr/share/arp-scan/ieee-oui.txt"),
            Path("/usr/share/ieee-data/oui.txt"),
            Path("/var/lib/ieee-data/oui.txt"),
            Path("/usr/share/nmap/nmap-mac-prefixes"),
        ]
        for fpath in oui_files:
            if fpath.exists():
                try:
                    for line in fpath.read_text(errors="ignore").splitlines():
                        if line.startswith(oui_upper) or line.startswith(oui_dashed):
                            parts = line.split(None, 1)
                            if len(parts) == 2:
                                vendor_raw = parts[1].replace("(hex)", "").replace("(base 16)", "").strip()
                                if "cisco" in vendor_raw.lower():
                                    vendor_raw = "Cisco Systems"
                                cls._oui_cache[oui] = vendor_raw[:32]
                                is_unauth = any(k in vendor_raw.lower() for k in ("tp-link", "tenda", "d-link", "mercusys", "xiaomi"))
                                return cls._oui_cache[oui], is_unauth
                except Exception:
                    continue

        return "Kurumsal Ağ Cihazı", False

    @classmethod
    def get_lldp_from_daemon(cls, iface: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Query system lldpd daemon via lldpctl for real switch neighbor details (supports both CDP and LLDP).
        """
        target_iface = iface or cls.get_active_interface()
        try:
            res = subprocess.run(
                ["lldpctl", "-f", "json", target_iface],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                lldp_node = data.get("lldp", {})
                if_node = lldp_node.get("interface", {})
                if isinstance(if_node, list) and if_node:
                    if_node = if_node[0]

                target_if = None
                if isinstance(if_node, dict):
                    target_if = if_node.get(target_iface) or (list(if_node.values())[0] if if_node else None)

                if isinstance(target_if, list) and target_if:
                    target_if = target_if[0]

                if isinstance(target_if, dict):
                    via_proto = target_if.get("via", "CDP/LLDP")
                    chassis = target_if.get("chassis", {})
                    port = target_if.get("port", {})
                    vlan = target_if.get("vlan", {})

                    # Handle case where chassis is nested under system name key
                    if isinstance(chassis, dict) and "name" not in chassis and len(chassis) == 1:
                        first_key = list(chassis.keys())[0]
                        if isinstance(chassis[first_key], dict):
                            inner = chassis[first_key]
                            inner.setdefault("name", first_key)
                            chassis = inner

                    chassis_name = chassis.get("name", "") if isinstance(chassis, dict) else ""
                    chassis_id = ""
                    if isinstance(chassis, dict):
                        if isinstance(chassis.get("id"), dict):
                            chassis_id = chassis["id"].get("value", "")
                        elif isinstance(chassis.get("id"), str):
                            chassis_id = chassis["id"]

                    port_id = ""
                    if isinstance(port, dict):
                        if isinstance(port.get("id"), dict):
                            port_id = port["id"].get("value", "")
                        elif isinstance(port.get("id"), str):
                            port_id = port["id"]

                    if isinstance(vlan, list) and vlan:
                        vlan = vlan[0]
                    vlan_id = vlan.get("vlan-id") if isinstance(vlan, dict) else None
                    mgmt_ip = chassis.get("mgmt-ip", "") if isinstance(chassis, dict) else ""
                    if isinstance(mgmt_ip, list) and mgmt_ip:
                        mgmt_ip = mgmt_ip[0]

                    chassis_descr = chassis.get("descr", "") if isinstance(chassis, dict) else ""
                    port_descr = port.get("descr", "") if isinstance(port, dict) else ""
                    vlan_name = vlan.get("name", "") if isinstance(vlan, dict) else ""

                    vendor, is_unauth = cls.identify_mac_vendor(chassis_id)

                    if chassis_name or port_id:
                        return {
                            "system_name": chassis_name or "Anahtarlama Cihazı",
                            "system_description": chassis_descr,
                            "port_id": port_id or "Bilinmiyor",
                            "port_description": port_descr,
                            "vlan_id": vlan_id,
                            "vlan_name": vlan_name,
                            "management_ip": str(mgmt_ip) if mgmt_ip else "",
                            "chassis_id": chassis_id,
                            "protocol": str(via_proto).upper(),
                            "vendor": vendor,
                            "is_unauthorized_switch": is_unauth,
                        }
        except Exception:
            pass
        return None

    @classmethod
    def get_packet_stats(cls, iface: Optional[str] = None) -> Tuple[int, int, int, int]:
        """Read real rx_bytes, tx_bytes, rx_packets, tx_packets from /proc/net/dev."""
        target_iface = iface or cls.get_active_interface()
        proc_dev = Path("/proc/net/dev")
        if proc_dev.exists():
            try:
                for line in proc_dev.read_text().splitlines():
                    if f"{target_iface}:" in line:
                        parts = line.split(":", 1)[1].split()
                        return int(parts[0]), int(parts[8]), int(parts[1]), int(parts[9])
            except Exception:
                pass
        return 0, 0, 0, 0
