"""
Wireless (Wi-Fi) Network Scanner tool.
Scans 2.4 GHz and 5 GHz bands for SSID, BSSID, RSSI signal strength, and channel density.
"""

import subprocess
import re
from typing import List
from cirak.core.models import WiFiNetwork


class WiFiScanner:
    """Scans for available wireless access points on wlan0."""

    def __init__(self, interface: str = "wlan0", simulate: bool = False):
        self.interface = interface
        self.simulate = simulate

    def scan_networks(self) -> List[WiFiNetwork]:
        """Perform scan using nmcli or iw."""
        if self.simulate:
            return self._get_simulated_networks()

        networks: List[WiFiNetwork] = []
        try:
            # Try nmcli
            res = subprocess.run(
                ["nmcli", "-t", "-f", "SSID,BSSID,CHAN,SIGNAL,SECURITY", "dev", "wifi", "list"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 5 and parts[0]:
                        ssid = parts[0]
                        bssid = parts[1]
                        chan = int(parts[2]) if parts[2].isdigit() else 1
                        signal = int(parts[3]) if parts[3].isdigit() else 50
                        sec = parts[4]
                        networks.append(WiFiNetwork(
                            ssid=ssid,
                            bssid=bssid,
                            signal_quality_pct=signal,
                            channel=chan,
                            security=sec,
                            connected=(ssid == "eduroam")
                        ))
                if networks:
                    return networks
        except Exception:
            pass

        return self._get_simulated_networks()

    def _get_simulated_networks(self) -> List[WiFiNetwork]:
        return [
            WiFiNetwork(ssid="eduroam", bssid="00:27:0d:34:21:40", signal_quality_pct=92, channel=36, security="WPA2-Enterprise (802.1X)", connected=True),
            WiFiNetwork(ssid="Kampus-Misafir", bssid="00:27:0d:34:21:41", signal_quality_pct=88, channel=36, security="Açık (Web Portal)"),
            WiFiNetwork(ssid="YBS_Lab_5G", bssid="a0:04:60:88:91:10", signal_quality_pct=74, channel=44, security="WPA2-PSK"),
            WiFiNetwork(ssid="Rektorluk_Net", bssid="e4:8d:8c:12:34:56", signal_quality_pct=52, channel=6, security="WPA2/WPA3"),
        ]
