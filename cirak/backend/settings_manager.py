"""
System & Network Configuration Manager for Ç.I.R.A.K. (LinkRunner AT 2000 Grade).
Handles:
  1. IP Mode: DHCP vs Static IPv4 (IP, CIDR Prefix, Gateway, DNS)
  2. Layer 2: IEEE 802.1Q VLAN Tagging & Hardware MAC Address Override
  3. Time & NTP Synchronization (Default: time.deu.edu.tr via RFC 4330 SNTPv4 + timedatectl)
  4. UI Theme Persistence (Dark Industrial default vs Soft Light)
Security: Strict input validation (ipaddress, regex) and shell=False subprocess execution.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import time
from typing import Optional, Tuple, Dict, Any
from cirak import config
from cirak.backend.network_detector import NetworkDetector


_MAC_REGEX = re.compile(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$")
_HOSTNAME_REGEX = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9.\-]{0,251}[a-zA-Z0-9])?$")
_IFACE_REGEX = re.compile(r"^[a-zA-Z0-9._\-]{1,15}$")


@dataclass
class CirakSettings:
    """Persistent configuration state for the handheld analyzer."""
    ip_mode: str = "dhcp"                 # "dhcp" or "static"
    static_ip: str = "194.27.65.131"
    subnet_prefix: int = 24
    gateway: str = "194.27.65.1"
    dns_server: str = "193.140.151.224"
    vlan_enabled: bool = False
    vlan_id: int = 100                    # 1 .. 4094
    custom_mac_enabled: bool = False
    custom_mac: str = ""
    ntp_server: str = config.DEFAULT_NTP_SERVER
    ntp_enabled: bool = True
    theme: str = config.THEME_DARK
    profile_name: str = config.DEFAULT_PROFILE


class SettingsManager:
    """Manages persistent device settings and applies validated Linux kernel network parameters."""

    def __init__(self, settings_path: Optional[Path] = None, simulate: bool = False):
        self.settings_path = settings_path or config.SETTINGS_FILE
        self.simulate = simulate
        self.settings = self.load()

    def load(self) -> CirakSettings:
        """Load settings from JSON file or initialize defaults with current hardware state."""
        defaults = CirakSettings()
        # Populate defaults from live interface if available
        real_cidr = NetworkDetector.get_ip_address_cidr("eth0")
        if real_cidr and "/" in real_cidr:
            ip_part, pfx_part = real_cidr.split("/", 1)
            defaults.static_ip = ip_part
            if pfx_part.isdigit():
                defaults.subnet_prefix = int(pfx_part)
        gw = NetworkDetector.get_default_gateway()
        if gw and gw.get("gateway"):
            defaults.gateway = gw["gateway"]
        dns_list = NetworkDetector.get_dns_servers()
        if dns_list:
            defaults.dns_server = dns_list[0]
        hw_mac = self.get_interface_mac("eth0")
        if hw_mac:
            defaults.custom_mac = hw_mac

        if self.settings_path.exists():
            try:
                raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
                for k, v in raw.items():
                    if hasattr(defaults, k):
                        setattr(defaults, k, v)
            except Exception:
                pass
        return defaults

    def save(self, settings: Optional[CirakSettings] = None) -> bool:
        """Save configuration securely with 0600 permissions."""
        if settings is not None:
            self.settings = settings
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(
                json.dumps(asdict(self.settings), indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            os.chmod(self.settings_path, 0o600)
            return True
        except Exception:
            return False

    # =========================================================================
    # Validation Helpers (Cybersecurity Hardened)
    # =========================================================================
    @staticmethod
    def validate_ipv4(ip_str: str) -> bool:
        try:
            addr = ipaddress.IPv4Address(ip_str.strip())
            return not (addr.is_multicast or addr.is_unspecified or addr.is_loopback)
        except Exception:
            return False

    @staticmethod
    def validate_prefix(prefix: int) -> bool:
        return isinstance(prefix, int) and (8 <= prefix <= 30)

    @staticmethod
    def validate_vlan(vlan_id: int) -> bool:
        return isinstance(vlan_id, int) and (1 <= vlan_id <= 4094)

    @staticmethod
    def validate_mac(mac_str: str) -> bool:
        mac = mac_str.strip().lower()
        if not _MAC_REGEX.match(mac):
            return False
        first_octet = int(mac.split(":")[0], 16)
        # Must be unicast (LSB of first octet == 0) and not all-zeros
        if (first_octet & 0x01) != 0 or mac == "00:00:00:00:00:00":
            return False
        return True

    @staticmethod
    def validate_hostname(host_str: str) -> bool:
        h = host_str.strip()
        if not h or len(h) > 253:
            return False
        return bool(_HOSTNAME_REGEX.match(h))

    # =========================================================================
    # Hardware Inspection & Execution
    # =========================================================================
    @staticmethod
    def get_interface_mac(iface: str = "eth0") -> str:
        if not _IFACE_REGEX.match(iface):
            return "00:00:00:00:00:00"
        p = Path(f"/sys/class/net/{iface}/address")
        if p.exists():
            try:
                return p.read_text().strip().lower()
            except Exception:
                pass
        return "00:00:00:00:00:00"

    @staticmethod
    def get_permanent_mac(iface: str = "eth0") -> str:
        """Read factory burned-in MAC address from sysfs or ethtool -P."""
        if not _IFACE_REGEX.match(iface):
            return ""
        try:
            res = subprocess.run(
                ["ethtool", "-P", iface],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.5
            )
            if res.returncode == 0 and ":" in res.stdout:
                perm = res.stdout.split(":", 1)[1].strip().lower()
                if _MAC_REGEX.match(perm) and perm != "00:00:00:00:00:00":
                    return perm
        except Exception:
            pass
        return SettingsManager.get_interface_mac(iface)

    def apply_network_config(self, iface: str = "eth0") -> Tuple[bool, str]:
        """Validate and apply IP (DHCP/Static), VLAN 802.1Q, and MAC configuration to Linux stack."""
        if not _IFACE_REGEX.match(iface):
            return False, "Geçersiz ağ arayüzü adı."

        s = self.settings

        # 1. Validate inputs before touching kernel interfaces
        if s.ip_mode == "static":
            if not self.validate_ipv4(s.static_ip):
                return False, f"Geçersiz Statik IP adresi: {s.static_ip}"
            if not self.validate_prefix(s.subnet_prefix):
                return False, f"Geçersiz CIDR alt ağ maskesi: /{s.subnet_prefix} (8-30 olmalı)"
            if s.gateway and not self.validate_ipv4(s.gateway):
                return False, f"Geçersiz Ağ Geçidi IP adresi: {s.gateway}"
            if s.dns_server and not self.validate_ipv4(s.dns_server):
                return False, f"Geçersiz DNS IP adresi: {s.dns_server}"

        if s.vlan_enabled and not self.validate_vlan(s.vlan_id):
            return False, f"Geçersiz 802.1Q VLAN ID: {s.vlan_id} (1-4094 arası olmalı)"

        if s.custom_mac_enabled and not self.validate_mac(s.custom_mac):
            return False, f"Geçersiz Unicast MAC adresi: {s.custom_mac}"

        s.profile_name = (
            f"VLAN{s.vlan_id}-{'Statik' if s.ip_mode == 'static' else 'DHCP'}"
            if s.vlan_enabled
            else ("Kampus-Statik-IP" if s.ip_mode == "static" else "Kampus-Dinamik-DHCP")
        )
        self.save()

        if self.simulate:
            return True, f"✓ Ayarlar doğrulandı ve kaydedildi ({s.profile_name})."

        messages = []

        # 2. Apply Custom MAC Address if enabled
        if s.custom_mac_enabled:
            current_mac = self.get_interface_mac(iface)
            if current_mac != s.custom_mac.lower():
                ok = self._run_privileged(["ip", "link", "set", "dev", iface, "down"])
                ok = ok and self._run_privileged(["ip", "link", "set", "dev", iface, "address", s.custom_mac.lower()])
                ok = ok and self._run_privileged(["ip", "link", "set", "dev", iface, "up"])
                if ok:
                    messages.append(f"MAC: {s.custom_mac.lower()}")
                else:
                    return False, "MAC adresi değiştirilemedi (CAP_NET_ADMIN yetkisini kontrol edin)."

        # 3. Configure 802.1Q VLAN Sub-interface if enabled
        target_iface = iface
        if s.vlan_enabled:
            vlan_iface = f"{iface}.{s.vlan_id}"
            if not Path(f"/sys/class/net/{vlan_iface}").exists():
                self._run_privileged([
                    "ip", "link", "add", "link", iface,
                    "name", vlan_iface, "type", "vlan", "id", str(s.vlan_id)
                ])
            self._run_privileged(["ip", "link", "set", "dev", vlan_iface, "up"])
            target_iface = vlan_iface
            messages.append(f"VLAN {s.vlan_id} ({vlan_iface})")
        else:
            # Remove any stale eth0.<vlan> subinterfaces created earlier
            for p in Path("/sys/class/net").glob(f"{iface}.*"):
                sub_name = p.name
                if _IFACE_REGEX.match(sub_name):
                    self._run_privileged(["ip", "link", "delete", sub_name])

        # 4. Apply IP Configuration (Static vs DHCP)
        if s.ip_mode == "static":
            cidr_addr = f"{s.static_ip.strip()}/{s.subnet_prefix}"
            self._run_privileged(["ip", "-4", "addr", "flush", "dev", target_iface])
            ok_ip = self._run_privileged(["ip", "addr", "add", cidr_addr, "dev", target_iface])
            if s.gateway:
                self._run_privileged(["ip", "route", "replace", "default", "via", s.gateway.strip(), "dev", target_iface])
            if ok_ip:
                messages.append(f"Statik IP: {cidr_addr}")
            else:
                return False, f"Statik IP ({cidr_addr}) {target_iface} arayüzüne atanamadı."
        else:
            # Trigger DHCP renewal via dhclient, dhcpcd, or nmcli
            if shutil.which("dhcpcd"):
                self._run_privileged(["dhcpcd", "-n", target_iface])
            elif shutil.which("dhclient"):
                self._run_privileged(["dhclient", "-r", target_iface])
                self._run_privileged(["dhclient", target_iface])
            elif shutil.which("nmcli"):
                self._run_privileged(["nmcli", "device", "reapply", target_iface])
            messages.append("Mod: Otomatik DHCP")

        return True, "✓ Uygulandı: " + " | ".join(messages)

    def sync_ntp_time(self, server: Optional[str] = None) -> Tuple[bool, str]:
        """
        Query NTP server (default: time.deu.edu.tr) using RFC 4330 SNTPv4 over UDP 123,
        enable systemd-timesyncd if available, and synchronize system clock.
        """
        target_server = (server or self.settings.ntp_server or config.DEFAULT_NTP_SERVER).strip()
        if not self.validate_hostname(target_server):
            return False, f"Geçersiz NTP sunucu adresi: {target_server}"

        self.settings.ntp_server = target_server
        self.save()

        if self.simulate:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return True, f"✓ NTP Eşitlendi ({target_server}) -> {now_str} (RTT: 1.8 ms)"

        # 1. Perform direct UDP 123 SNTPv4 query to verify reachability and fetch exact atomic time
        t0 = time.perf_counter()
        ntp_epoch_1970 = 2208988800
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3.0)
            # SNTPv4 client request packet (LI=0, VN=3, Mode=3 -> 0x1B followed by 47 zero bytes)
            packet = b"\x1b" + (47 * b"\x00")
            sock.sendto(packet, (target_server, 123))
            data, _ = sock.recvfrom(1024)
            rtt_ms = (time.perf_counter() - t0) * 1000.0

            if len(data) >= 48:
                tx_sec, tx_frac = struct.unpack("!II", data[40:48])
                unix_ts = tx_sec - ntp_epoch_1970 + (tx_frac / float(2**32))
                ntp_dt = datetime.fromtimestamp(unix_ts)
                formatted_time = ntp_dt.strftime("%Y-%m-%d %H:%M:%S")

                # Update system clock if user has permission
                self._run_privileged(["timedatectl", "set-ntp", "true"])
                self._run_privileged(["date", "-s", f"@{int(unix_ts)}"])

                return True, f"✓ {target_server} ile eşitlendi: {formatted_time} ({rtt_ms:.1f} ms)"
        except Exception as e:
            # Fallback to timedatectl status check if UDP 123 is filtered
            self._run_privileged(["timedatectl", "set-ntp", "true"])
            return False, f"NTP yanıtı alınamadı ({target_server}:123 - {type(e).__name__})"
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

        return False, f"NTP sunucusundan ({target_server}) geçerli yanıt alınamadı."

    @staticmethod
    def _run_privileged(cmd: list) -> bool:
        """Execute system networking command safely with shell=False (tries direct CAP_NET_ADMIN then sudo -n)."""
        for prefix in ([], ["sudo", "-n"]):
            try:
                res = subprocess.run(
                    prefix + cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3.0,
                    shell=False,
                )
                if res.returncode == 0:
                    return True
            except Exception:
                continue
        return False
