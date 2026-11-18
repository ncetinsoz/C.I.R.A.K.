"""
Wi-Fi Environment Scanner & Channel Congestion Diagnostic Engine.
Extracts live 2.4 GHz and 5 GHz AP parameters via Linux 'iw', 'nmcli', and 'iwlist'.
Target Hardware: Raspberry Pi 4 (Cypress/Broadcom BCM43455 on wlan0).
Strictly returns real hardware scan results when simulate=False.
"""

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import List, Optional, Dict
from cirak.backend.network_detector import NetworkDetector


@dataclass
class WiFiAccessPoint:
    ssid: str
    bssid: str
    signal_dbm: int
    signal_pct: int
    channel: int
    frequency_mhz: int
    band: str      # "2.4 GHz" or "5 GHz"
    security: str  # "WPA2-PSK", "WPA2-Enterprise", "WPA3", "Açık Ağ (Open)"
    is_connected: bool = False


@dataclass
class WiFiScanReport:
    access_points: List[WiFiAccessPoint]
    total_aps: int
    count_24ghz: int
    count_5ghz: int
    best_24ghz_channel: int
    channel_density: Dict[int, int]
    connected_ssid: Optional[str] = None
    connected_ip: Optional[str] = None
    scan_duration_ms: float = 0.0
    status_message: str = ""


class WiFiScanner:
    """Scans and analyzes real local Wi-Fi spectrum on wlan0."""

    def __init__(self, interface: str = "wlan0", simulate: bool = False):
        self.interface = interface
        self.simulate = simulate

    def scan(self) -> WiFiScanReport:
        """Scan airwaves and return real hardware Wi-Fi inventory."""
        t_start = time.perf_counter()

        if self.simulate:
            time.sleep(0.15)
            return self._get_simulated_report(t_start)

        # 1. Ensure wireless interface is unblocked and UP before scanning
        self._ensure_wlan_up()

        # 2. Multi-backend real hardware scan (iw -> nmcli -> iwlist)
        connected_bssid, connected_ssid = self._get_current_association()

        aps = self._scan_with_iw(connected_bssid)
        if not aps:
            aps = self._scan_with_nmcli()
        if not aps:
            aps = self._scan_with_iwlist(connected_bssid)

        # Sort APs by signal strength (strongest first)
        aps.sort(key=lambda a: a.signal_dbm, reverse=True)

        # Analyze 2.4 GHz & 5 GHz channel density
        density_24: Dict[int, int] = {}
        count_24 = 0
        count_5 = 0

        for ap in aps:
            if connected_ssid and ap.ssid == connected_ssid and not any(x.is_connected for x in aps):
                ap.is_connected = True
            if ap.band == "2.4 GHz":
                count_24 += 1
                density_24[ap.channel] = density_24.get(ap.channel, 0) + 1
            else:
                count_5 += 1

        # Best non-overlapping channel in 2.4GHz (among 1, 6, 11)
        best_chan = min([1, 6, 11], key=lambda c: density_24.get(c, 0))

        for ap in aps:
            if ap.is_connected and not connected_ssid:
                connected_ssid = ap.ssid
                break

        wlan_ip = NetworkDetector.get_ip_address_cidr(self.interface)
        if wlan_ip and "/" in wlan_ip:
            wlan_ip = wlan_ip.split("/")[0]

        status_msg = f"{len(aps)} ağ bulundu" if aps else "Çevrede Wi-Fi ağı bulunamadı veya wlan0 meşgul"

        return WiFiScanReport(
            access_points=aps,
            total_aps=len(aps),
            count_24ghz=count_24,
            count_5ghz=count_5,
            best_24ghz_channel=best_chan,
            channel_density=density_24,
            connected_ssid=connected_ssid,
            connected_ip=wlan_ip,
            scan_duration_ms=(time.perf_counter() - t_start) * 1000.0,
            status_message=status_msg,
        )

    def _ensure_wlan_up(self):
        """Ensure wlan0 is not soft-blocked by rfkill and link is UP."""
        try:
            flags_path = Path(f"/sys/class/net/{self.interface}/flags")
            if flags_path.exists():
                flags = int(flags_path.read_text().strip(), 16)
                if not (flags & 0x1):  # IFF_UP bit not set
                    for prefix in ([], ["sudo", "-n"]):
                        if shutil.which("rfkill"):
                            subprocess.run(
                                prefix + ["rfkill", "unblock", "wifi"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                timeout=1.5,
                            )
                        res = subprocess.run(
                            prefix + ["ip", "link", "set", self.interface, "up"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=1.5,
                        )
                        if res.returncode == 0:
                            time.sleep(0.4)
                            break
        except Exception:
            pass

    def _get_current_association(self) -> tuple[str, Optional[str]]:
        """Check currently associated BSSID and SSID on wlan0."""
        bssid = ""
        ssid = None
        if shutil.which("iw"):
            try:
                res = subprocess.run(
                    ["iw", "dev", self.interface, "link"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.5,
                )
                if res.returncode == 0 and "Connected to " in res.stdout:
                    for line in res.stdout.splitlines():
                        line = line.strip()
                        if line.startswith("Connected to "):
                            bssid = line.split()[2].lower()
                        elif line.startswith("SSID:"):
                            ssid = line.split(":", 1)[1].strip()
            except Exception:
                pass
        return bssid, ssid

    def _scan_with_iw(self, connected_bssid: str = "") -> List[WiFiAccessPoint]:
        """Scan using Linux nl80211 'iw' utility (tries direct, sudo -n, and cached dump)."""
        if not shutil.which("iw"):
            return []

        commands = [
            ["iw", "dev", self.interface, "scan"],
            ["sudo", "-n", "iw", "dev", self.interface, "scan"],
            ["iw", "dev", self.interface, "scan", "dump"],
        ]

        raw_output = ""
        for cmd in commands:
            try:
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=7,
                )
                if res.returncode == 0 and "BSS " in res.stdout:
                    raw_output = res.stdout
                    break
            except Exception:
                continue

        if not raw_output:
            return []

        aps: List[WiFiAccessPoint] = []
        seen_bssids = set()

        current_bssid = ""
        current_ssid = ""
        current_signal = -85
        current_freq = 2412
        current_chan = 0
        has_privacy = False
        has_rsn = False
        has_wpa = False
        has_8021x = False
        has_sae = False

        def _flush_ap():
            if not current_bssid or current_bssid in seen_bssids:
                return
            seen_bssids.add(current_bssid)
            chan = current_chan if current_chan > 0 else self._freq_to_channel(current_freq)
            band = "5 GHz" if current_freq > 3000 else "2.4 GHz"
            pct = min(max(int(2 * (current_signal + 100)), 0), 100)

            if has_8021x:
                sec = "WPA2-Enterprise (802.1X)"
            elif has_sae:
                sec = "WPA3-SAE"
            elif has_rsn:
                sec = "WPA2-PSK"
            elif has_wpa:
                sec = "WPA-PSK"
            elif has_privacy:
                sec = "WEP / Şifreli"
            else:
                sec = "Açık Ağ (Open)"

            aps.append(WiFiAccessPoint(
                ssid=self._decode_iw_ssid(current_ssid) if current_ssid else "<Gizli Ağ>",
                bssid=current_bssid,
                signal_dbm=current_signal,
                signal_pct=pct,
                channel=chan,
                frequency_mhz=current_freq,
                band=band,
                security=sec,
                is_connected=(current_bssid == connected_bssid and bool(connected_bssid)),
            ))

        for raw_line in raw_output.splitlines():
            line = raw_line.strip()
            if raw_line.startswith("BSS ") and "(" in raw_line:
                _flush_ap()
                current_bssid = line.split()[1].split("(")[0].strip().lower()
                current_ssid = ""
                current_signal = -85
                current_freq = 2412
                current_chan = 0
                has_privacy = False
                has_rsn = False
                has_wpa = False
                has_8021x = False
                has_sae = False
            elif line.startswith("freq:"):
                try:
                    current_freq = int(float(line.split()[1]))
                except Exception:
                    current_freq = 2412
            elif line.startswith("signal:"):
                try:
                    current_signal = int(float(line.split()[1]))
                except Exception:
                    current_signal = -75
            elif line.startswith("SSID:"):
                current_ssid = line.split(":", 1)[1].strip()
            elif line.startswith("DS Parameter set: channel"):
                try:
                    current_chan = int(line.split()[-1])
                except Exception:
                    pass
            elif line.startswith("* primary channel:"):
                try:
                    current_chan = int(line.split()[-1])
                except Exception:
                    pass
            elif line.startswith("capability:") and "Privacy" in line:
                has_privacy = True
            elif line.startswith("RSN:"):
                has_rsn = True
            elif line.startswith("WPA:"):
                has_wpa = True
            elif "Authentication suites:" in line:
                if "802.1X" in line or "IEEE 802.1X" in line:
                    has_8021x = True
                if "SAE" in line:
                    has_sae = True

        _flush_ap()
        return aps

    def _scan_with_nmcli(self) -> List[WiFiAccessPoint]:
        """Scan using NetworkManager nmcli CLI with proper escaped-colon splitting."""
        if not shutil.which("nmcli"):
            return []

        cmd = [
            "nmcli", "-t", "-f",
            "IN-USE,BSSID,SSID,CHAN,FREQ,SIGNAL,SECURITY",
            "device", "wifi", "list", "--rescan", "auto"
        ]
        aps: List[WiFiAccessPoint] = []
        seen_bssids = set()
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=7,
            )
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.splitlines():
                    if not line.strip():
                        continue
                    # Split only on unescaped colons (nmcli escapes colons inside BSSID/SSID as \:)
                    parts = re.split(r"(?<!\\):", line.strip())
                    if len(parts) >= 7:
                        in_use = parts[0].strip() == "*"
                        bssid = parts[1].replace("\\:", ":").strip().lower()
                        if not bssid or bssid in seen_bssids:
                            continue
                        seen_bssids.add(bssid)

                        ssid = parts[2].replace("\\:", ":").strip() or "<Gizli Ağ>"
                        chan_str = parts[3].strip()
                        chan = int(chan_str) if chan_str.isdigit() else 1

                        freq_digits = re.findall(r"\d+", parts[4])
                        freq = int(freq_digits[0]) if freq_digits else 2412

                        sig_str = parts[5].strip()
                        signal_pct = int(sig_str) if sig_str.isdigit() else 50
                        sec = parts[6].replace("\\:", ":").strip() or "Açık Ağ (Open)"

                        dbm = int((signal_pct / 2.0) - 100)
                        band = "5 GHz" if freq > 3000 else "2.4 GHz"

                        aps.append(WiFiAccessPoint(
                            ssid=ssid,
                            bssid=bssid,
                            signal_dbm=dbm,
                            signal_pct=signal_pct,
                            channel=chan,
                            frequency_mhz=freq,
                            band=band,
                            security=sec,
                            is_connected=in_use,
                        ))
        except Exception:
            pass

        return aps

    def _scan_with_iwlist(self, connected_bssid: str = "") -> List[WiFiAccessPoint]:
        """Fallback scanner using wireless-tools 'iwlist'."""
        if not shutil.which("iwlist"):
            return []

        raw_out = ""
        for prefix in (["sudo", "-n"], []):
            try:
                res = subprocess.run(
                    prefix + ["iwlist", self.interface, "scan"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=7,
                )
                if res.returncode == 0 and "Cell " in res.stdout:
                    raw_out = res.stdout
                    break
            except Exception:
                continue

        if not raw_out:
            return []

        aps: List[WiFiAccessPoint] = []
        current_bssid = ""
        current_ssid = ""
        current_chan = 1
        current_freq = 2412
        current_sig = -80
        current_sec = "Açık Ağ (Open)"

        def _flush():
            if not current_bssid:
                return
            band = "5 GHz" if current_freq > 3000 else "2.4 GHz"
            pct = min(max(int(2 * (current_sig + 100)), 0), 100)
            aps.append(WiFiAccessPoint(
                ssid=current_ssid or "<Gizli Ağ>",
                bssid=current_bssid,
                signal_dbm=current_sig,
                signal_pct=pct,
                channel=current_chan,
                frequency_mhz=current_freq,
                band=band,
                security=current_sec,
                is_connected=(current_bssid == connected_bssid and bool(connected_bssid)),
            ))

        for line in raw_out.splitlines():
            line = line.strip()
            if line.startswith("Cell ") and "Address:" in line:
                _flush()
                current_bssid = line.split("Address:")[-1].strip().lower()
                current_ssid = ""
                current_chan = 1
                current_freq = 2412
                current_sig = -80
                current_sec = "Açık Ağ (Open)"
            elif line.startswith("ESSID:"):
                current_ssid = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("Channel:"):
                try:
                    current_chan = int(line.split(":")[1].strip())
                except Exception:
                    pass
            elif line.startswith("Frequency:"):
                try:
                    ghz = float(line.split(":")[1].split()[0])
                    current_freq = int(ghz * 1000)
                except Exception:
                    pass
            elif "Signal level=" in line:
                m = re.search(r"Signal level=(-?\d+)", line)
                if m:
                    current_sig = int(m.group(1))
            elif "Encryption key:on" in line:
                current_sec = "WPA/WPA2"
            elif "WPA2" in line:
                current_sec = "WPA2-PSK"

        _flush()
        return aps

    @staticmethod
    def _decode_iw_ssid(raw_ssid: str) -> str:
        """Decode hex escape sequences (e.g. \\xc3\\x9c) produced by iw scan for UTF-8 SSIDs."""
        if "\\x" not in raw_ssid:
            return raw_ssid
        try:
            b = raw_ssid.encode("latin1").decode("unicode_escape").encode("latin1")
            return b.decode("utf-8", errors="replace")
        except Exception:
            return raw_ssid

    @staticmethod
    def _freq_to_channel(freq: int) -> int:
        if freq == 2484:
            return 14
        if 2412 <= freq <= 2472:
            return (freq - 2412) // 5 + 1
        if 5170 <= freq <= 5825:
            return (freq - 5170) // 5 + 34
        return 1

    def _get_simulated_report(self, t_start: float) -> WiFiScanReport:
        aps = [
            WiFiAccessPoint("DEU-Ogrenci", "d8:b1:90:3a:42:10", -45, 90, 36, 5180, "5 GHz", "WPA2-Enterprise", is_connected=True),
            WiFiAccessPoint("eduroam", "d8:b1:90:3a:42:11", -48, 88, 36, 5180, "5 GHz", "802.1X EAP"),
            WiFiAccessPoint("DEU-Personel", "d8:b1:90:3a:42:12", -52, 84, 44, 5220, "5 GHz", "WPA2-Enterprise"),
            WiFiAccessPoint("DEU-Misafir", "d8:b1:90:3a:42:13", -58, 76, 6, 2437, "2.4 GHz", "Web Portal (Open)"),
            WiFiAccessPoint("Lab-Robotik-AP", "c4:ad:34:11:89:fe", -64, 68, 1, 2412, "2.4 GHz", "WPA2-PSK"),
            WiFiAccessPoint("Muhendislik-IoT", "b8:27:eb:76:12:90", -72, 54, 11, 2462, "2.4 GHz", "WPA2-PSK"),
            WiFiAccessPoint("Kutuphane-Hizmet", "00:1e:bd:55:aa:bb", -81, 38, 149, 5745, "5 GHz", "WPA3-SAE"),
        ]
        return WiFiScanReport(
            access_points=aps,
            total_aps=len(aps),
            count_24ghz=3,
            count_5ghz=4,
            best_24ghz_channel=1,
            channel_density={1: 1, 6: 1, 11: 1},
            connected_ssid="DEU-Ogrenci",
            connected_ip="194.27.65.131",
            scan_duration_ms=(time.perf_counter() - t_start) * 1000.0,
            status_message="Simülasyon Modu",
        )
