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

    @classmethod
    def get_lldp_from_daemon(cls, iface: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Query system lldpd daemon via lldpctl for real switch neighbor details.
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
                target_if = if_node.get(target_iface) or (list(if_node.values())[0] if if_node else None)

                if target_if:
                    chassis = target_if.get("chassis", {})
                    port = target_if.get("port", {})
                    vlan = target_if.get("vlan", {})

                    chassis_name = chassis.get("name", "")
                    chassis_id = ""
                    if isinstance(chassis.get("id"), dict):
                        chassis_id = chassis["id"].get("value", "")
                    elif isinstance(chassis.get("id"), str):
                        chassis_id = chassis["id"]

                    port_id = ""
                    if isinstance(port.get("id"), dict):
                        port_id = port["id"].get("value", "")
                    elif isinstance(port.get("id"), str):
                        port_id = port["id"]

                    vlan_id = vlan.get("vlan-id") if isinstance(vlan, dict) else None
                    mgmt_ip = chassis.get("mgmt-ip", "")

                    if chassis_name or port_id:
                        return {
                            "system_name": chassis_name or "Switch",
                            "port_id": port_id or "Gi1/0/1",
                            "vlan_id": vlan_id,
                            "management_ip": mgmt_ip,
                            "chassis_id": chassis_id,
                            "protocol": "LLDP",
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
