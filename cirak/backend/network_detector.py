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
    def get_mac_address(interface: str = "eth0") -> Optional[str]:
        """Read interface hardware MAC address from /sys/class/net/<iface>/address."""
        try:
            addr_file = Path(f"/sys/class/net/{interface}/address")
            if addr_file.exists():
                mac = addr_file.read_text().strip().lower()
                if mac and mac != "00:00:00:00:00:00":
                    return mac
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

        # 1. Consumer / SOHO / Unauthorized Desktop Switch & Router Vendors (Expanded TP-Link & SOHO OUIs)
        consumer_ouis = {
            "c4ad34": "TP-Link Technologies",
            "50c7bf": "TP-Link Technologies",
            "18a6f7": "TP-Link Technologies",
            "e8de27": "TP-Link Technologies",
            "f4f26d": "TP-Link Technologies",
            "001d0f": "TP-Link Technologies",
            "0023cd": "TP-Link Technologies",
            "002719": "TP-Link Technologies",
            "10feed": "TP-Link Technologies",
            "14cc20": "TP-Link Technologies",
            "14cf92": "TP-Link Technologies",
            "1c3bf3": "TP-Link Technologies",
            "20dc56": "TP-Link Technologies",
            "246968": "TP-Link Technologies",
            "30b5c2": "TP-Link Technologies",
            "34e894": "TP-Link Technologies",
            "40ed00": "TP-Link Technologies",
            "50d4f7": "TP-Link Technologies",
            "54af97": "TP-Link Technologies",
            "5c899a": "TP-Link Technologies",
            "6032b1": "TP-Link Technologies",
            "60e327": "TP-Link Technologies",
            "6466b3": "TP-Link Technologies",
            "647002": "TP-Link Technologies",
            "6c5ab0": "TP-Link Technologies",
            "74da38": "TP-Link Technologies",
            "788cb5": "TP-Link Technologies",
            "8416f9": "TP-Link Technologies",
            "90f652": "TP-Link Technologies",
            "98da24": "TP-Link Technologies",
            "98dac4": "TP-Link Technologies",
            "a0f3c1": "TP-Link Technologies",
            "ac84c6": "TP-Link Technologies",
            "b04e26": "TP-Link Technologies",
            "b09575": "TP-Link Technologies",
            "b0be76": "TP-Link Technologies",
            "c025e9": "TP-Link Technologies",
            "c04a00": "TP-Link Technologies",
            "d46e0e": "TP-Link Technologies",
            "d807b6": "TP-Link Technologies",
            "d84732": "TP-Link Technologies",
            "e4c32a": "TP-Link Technologies",
            "ec086b": "TP-Link Technologies",
            "ec172f": "TP-Link Technologies",
            "f81a67": "TP-Link Technologies",
            "f8d111": "TP-Link Technologies",
            "c83a35": "Tenda Technology",
            "b0df3a": "Tenda Technology",
            "001b11": "D-Link Corporation",
            "1cbdb9": "D-Link Corporation",
            "50ff20": "Keenetic / Zyxel",
            "588bf3": "Zyxel Communications",
            "286c07": "Xiaomi Router",
            "04d9f5": "ASUS Network",
            "9c5322": "Mercusys (TP-Link)",
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

        consumer_keywords = (
            "tp-link", "tplink", "tp link", "tenda", "d-link", "dlink",
            "mercusys", "xiaomi", "keenetic", "zyxel", "netgear", "totolink", "cudy", "asus"
        )

        if oui in cls._oui_cache:
            v = cls._oui_cache[oui]
            is_unauth = any(k in v.lower() for k in consumer_keywords)
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
                                v_low = vendor_raw.lower()
                                if "cisco" in v_low:
                                    vendor_raw = "Cisco Systems"
                                elif "tp-link" in v_low or "tplink" in v_low:
                                    vendor_raw = "TP-Link Technologies"
                                cls._oui_cache[oui] = vendor_raw[:32]
                                is_unauth = any(k in v_low for k in consumer_keywords)
                                return cls._oui_cache[oui], is_unauth
                except Exception:
                    continue

        return "Kurumsal Ağ Cihazı", False

    @classmethod
    def extract_model_and_ios(cls, descr: str, sw_ver: str = "", vendor: str = "") -> Tuple[str, str]:
        """
        Separate hardware Model/Platform from OS/IOS Software Version string.
        Handles lldpd's '<Platform> runs on <Software Version>' format as well as raw CDP/LLDP strings.
        """
        descr_clean = (descr or "").strip()
        sw_clean = (sw_ver or "").strip()

        raw_model = descr_clean
        raw_sw = sw_clean

        # lldpd formats CDP platform + version as: "cisco WS-C2960X-24TS-L runs on Cisco IOS Software..."
        if " runs on " in descr_clean:
            parts = descr_clean.split(" runs on ", 1)
            raw_model = parts[0].strip()
            if not raw_sw:
                raw_sw = parts[1].strip()
        elif not raw_sw and ("version " in descr_clean.lower() or "ios" in descr_clean.lower()):
            raw_sw = descr_clean

        # 1. Normalize Model Name
        if raw_model.lower().startswith("cisco "):
            raw_model = "Cisco " + raw_model[6:].strip()
        elif "catalyst" in raw_model.lower() and not raw_model.lower().startswith("cisco"):
            raw_model = "Cisco " + raw_model

        # If raw_model is actually a long IOS banner, extract the platform code in parentheses or before 'Software'
        if "ios software" in raw_model.lower() or len(raw_model) > 42:
            m_plat = re.search(r",\s*([A-Za-z0-9\-_]+)\s+Software\s*\(([^)]+)\)", raw_model)
            if m_plat:
                raw_model = f"Cisco {m_plat.group(1)} ({m_plat.group(2).split('-')[0]})"
            else:
                raw_model = raw_model.split(",")[0].strip()[:38]

        if not raw_model:
            raw_model = vendor or "Kurumsal Switch"

        # 2. Extract Concise Software / IOS Version for Network Admins
        ios_out = ""
        if raw_sw:
            os_family = "IOS"
            sw_low = raw_sw.lower()
            if "ios-xe" in sw_low or "ios xe" in sw_low:
                os_family = "Cisco IOS-XE"
            elif "nx-os" in sw_low or "nxos" in sw_low:
                os_family = "Cisco NX-OS"
            elif "ios" in sw_low:
                os_family = "Cisco IOS"
            elif "arubaos" in sw_low:
                os_family = "ArubaOS"
            elif "junos" in sw_low:
                os_family = "JunOS"
            elif "routeros" in sw_low:
                os_family = "RouterOS"
            elif "procurve" in sw_low:
                os_family = "HPE ProCurve"
            else:
                os_family = ""

            ver_match = re.search(r"Version\s+([0-9A-Za-z.\(\)\-:]+)", raw_sw, re.IGNORECASE)
            if ver_match:
                ver_num = ver_match.group(1).rstrip(",;")
                # Extract image feature set if available e.g. (C2960X-UNIVERSALK9-M)
                feat_match = re.search(r"\(([A-Za-z0-9_\-]+)\)", raw_sw)
                feat_tag = ""
                if feat_match:
                    f_raw = feat_match.group(1)
                    if "UNIVERSALK9" in f_raw:
                        feat_tag = " (UNIVERSALK9)"
                    elif "LANBASE" in f_raw:
                        feat_tag = " (LANBASE)"
                    elif "IPBASE" in f_raw:
                        feat_tag = " (IPBASE)"
                prefix = f"{os_family} " if os_family else "Sürüm "
                ios_out = f"{prefix}{ver_num}{feat_tag}".strip()
            else:
                first_line = raw_sw.splitlines()[0].strip()
                if first_line != raw_model:
                    ios_out = first_line[:44]

        return raw_model[:40], (ios_out or "Belirtilmedi")

    @classmethod
    def get_local_mac_addresses(cls) -> set:
        """Return lowercase MAC addresses of all local network interfaces (eth0, wlan0, etc.)."""
        macs = set()
        net_dir = Path("/sys/class/net")
        if net_dir.exists():
            for p in net_dir.iterdir():
                addr_file = p / "address"
                if addr_file.exists():
                    try:
                        m = addr_file.read_text().strip().lower()
                        if m and m != "00:00:00:00:00:00":
                            macs.add(m)
                    except Exception:
                        pass
        return macs

    @classmethod
    def is_local_device(
        cls,
        system_name: str = "",
        mac_or_chassis: str = "",
        mgmt_ip: str = "",
        system_descr: str = "",
    ) -> bool:
        """
        Return True if an L2 LLDP/CDP frame or neighbor entry belongs to this local Ç.I.R.A.K.
        Raspberry Pi itself (e.g., outgoing lldpd advertisements for 'cirak').
        """
        if system_name:
            name_low = system_name.strip().lower()
            local_host = socket.gethostname().strip().lower()
            if (
                name_low in ("cirak", "çırak", "c.i.r.a.k.", "localhost", "raspberrypi", local_host)
                or name_low.startswith("cirak.")
                or (local_host and name_low.startswith(local_host + "."))
            ):
                return True

        if mac_or_chassis:
            mac_low = mac_or_chassis.strip().lower()
            if mac_low in cls.get_local_mac_addresses():
                return True

        if mgmt_ip:
            local_cidr = cls.get_ip_address_cidr()
            if local_cidr:
                local_ip = local_cidr.split("/")[0].strip()
                if mgmt_ip.strip() == local_ip:
                    return True

        if system_descr and "debian gnu/linux" in system_descr.lower() and "linux" in system_descr.lower():
            if not system_name or system_name.strip().lower() in ("cirak", socket.gethostname().strip().lower()):
                return True

        return False

    @classmethod
    def get_lldp_from_daemon(cls, iface: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Query system lldpd daemon via lldpctl for real switch neighbor details (supports both CDP and LLDP).
        Automatically ignores any local self-advertisements ('cirak' / local MAC / local IP)
        and separates Hardware Model from IOS / Software Version.
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

                if_entries = if_node if isinstance(if_node, list) else ([if_node] if isinstance(if_node, dict) else [])
                candidates = []
                for entry in if_entries:
                    if not isinstance(entry, dict):
                        continue
                    val = entry.get(target_iface) or (list(entry.values())[0] if entry else None)
                    if isinstance(val, list):
                        candidates.extend(val)
                    elif isinstance(val, dict):
                        candidates.append(val)

                for target_if in candidates:
                    if not isinstance(target_if, dict):
                        continue
                    via_proto = target_if.get("via", "CDP/LLDP")
                    chassis = target_if.get("chassis", {})
                    port = target_if.get("port", {})
                    vlan = target_if.get("vlan", {})

                    if isinstance(chassis, dict) and "name" not in chassis and len(chassis) == 1:
                        first_key = list(chassis.keys())[0]
                        if isinstance(chassis[first_key], dict):
                            inner = dict(chassis[first_key])
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

                    if cls.is_local_device(
                        system_name=chassis_name,
                        mac_or_chassis=chassis_id,
                        mgmt_ip=str(mgmt_ip) if mgmt_ip else "",
                        system_descr=chassis_descr,
                    ):
                        continue

                    vendor, is_unauth = cls.identify_mac_vendor(chassis_id)
                    clean_model, clean_ios = cls.extract_model_and_ios(chassis_descr, vendor=vendor)

                    if chassis_name or port_id:
                        return {
                            "system_name": chassis_name or "Anahtarlama Cihazı",
                            "system_description": clean_model,
                            "software_version": clean_ios,
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
    def probe_gateway_device(cls, iface: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Active L2/L3 Discovery for Home/SOHO Routers (e.g., TP-Link, Keenetic, Zyxel, ASUS)
        and Unmanaged Switches that do not transmit Cisco CDP or IEEE LLDP frames.
        """
        target_iface = iface or cls.get_active_interface()
        if not cls.get_carrier(target_iface):
            return None

        gw_info = cls.get_default_gateway()
        gw_ip = gw_info["gateway"] if gw_info else ""
        gw_mac = cls.get_gateway_mac(gw_ip) if gw_ip else None

        # Fallback: check any active neighbor MAC on target_iface in /proc/net/arp
        if not gw_mac:
            arp_file = Path("/proc/net/arp")
            if arp_file.exists():
                try:
                    for line in arp_file.read_text().splitlines()[1:]:
                        parts = line.split()
                        if len(parts) >= 6 and parts[5] == target_iface and parts[3] != "00:00:00:00:00:00":
                            gw_ip = gw_ip or parts[0]
                            gw_mac = parts[3].lower()
                            break
                except Exception:
                    pass

        if not gw_mac:
            return None

        vendor, is_consumer = cls.identify_mac_vendor(gw_mac)
        speed, duplex = cls.get_speed_duplex(target_iface)
        link_str = f"{speed}M {duplex}" if speed > 0 else "Aktif Link"

        # Probe HTTP title / Server / Realm and Reverse DNS on Gateway IP for model & firmware details
        http_title = ""
        http_server = ""
        dns_host = ""

        if gw_ip:
            try:
                dns_host = socket.gethostbyaddr(gw_ip)[0]
            except Exception:
                pass

            for port in (80, 8080):
                sock = None
                try:
                    sock = socket.create_connection((gw_ip, port), timeout=0.6)
                    req = f"GET / HTTP/1.0\r\nHost: {gw_ip}\r\nUser-Agent: CIRAK-Diagnostic\r\n\r\n".encode("ascii")
                    sock.sendall(req)
                    raw_resp = sock.recv(4096).decode("utf-8", errors="ignore")
                    m_srv = re.search(r"^Server:\s*(.+)$", raw_resp, re.IGNORECASE | re.MULTILINE)
                    if m_srv:
                        http_server = m_srv.group(1).strip()[:36]
                    m_auth = re.search(r'realm="([^"]+)"', raw_resp, re.IGNORECASE)
                    if m_auth:
                        http_title = m_auth.group(1).strip()[:36]
                    m_title = re.search(r"<title>([^<]+)</title>", raw_resp, re.IGNORECASE)
                    if m_title and not http_title:
                        t_candidate = m_title.group(1).strip()
                        if t_candidate and not any(x in t_candidate.lower() for x in ("redirect", "301", "302", "index", "login")):
                            http_title = t_candidate[:36]
                    if http_title or http_server:
                        break
                except Exception:
                    pass
                finally:
                    if sock:
                        try:
                            sock.close()
                        except Exception:
                            pass

        dev_type = "Kablosuz Router / Switch" if is_consumer else "Ağ Geçidi / Switch"
        if http_title:
            sys_name = f"{http_title} ({gw_ip})" if gw_ip else http_title
            model_name = f"{vendor} • {http_title}"
        elif dns_host and dns_host != gw_ip:
            sys_name = f"{dns_host} ({ vendor })"
            model_name = f"{vendor} ({dev_type})"
        else:
            sys_name = f"{vendor} Yönlendirici/Switch"
            model_name = f"{vendor} ({dev_type})"

        sw_info = (
            f"Web: {http_server} (CDP/LLDP Yok)"
            if http_server
            else "CDP/LLDP Yok (Yönetimsiz / SOHO Cihaz)"
        )

        return {
            "system_name": sys_name[:38],
            "system_description": model_name[:40],
            "software_version": sw_info[:42],
            "port_id": f"LAN Portu ({link_str})",
            "port_description": "Doğrudan L2 Bağlantı",
            "vlan_id": 1,
            "vlan_name": "Untagged (Standart LAN)",
            "management_ip": gw_ip or "Yok",
            "chassis_id": gw_mac,
            "protocol": "L2-ARP / GW",
            "vendor": vendor,
            "is_unauthorized_switch": is_consumer,
        }

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
