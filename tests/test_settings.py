"""
Tests for SettingsManager: DHCP/Static IP, VLAN 802.1Q, MAC spoofing, NTP sync, and cybersecurity validation.
"""

from pathlib import Path
from cirak.backend.settings_manager import SettingsManager


def test_settings_validation_and_persistence(tmp_path: Path):
    cfg_file = tmp_path / "settings.json"
    mgr = SettingsManager(settings_path=cfg_file, simulate=True)

    # Default NTP server must be time.deu.edu.tr
    assert mgr.settings.ntp_server == "time.deu.edu.tr"

    # Validations
    assert mgr.validate_ipv4("194.27.65.131") is True
    assert mgr.validate_ipv4("999.1.1.1") is False
    assert mgr.validate_ipv4("194.27.65.131; rm -rf /") is False

    assert mgr.validate_vlan(100) is True
    assert mgr.validate_vlan(0) is False
    assert mgr.validate_vlan(4095) is False

    # Unicast vs Multicast MAC validation
    assert mgr.validate_mac("b8:27:eb:12:34:56") is True
    assert mgr.validate_mac("01:00:0c:cc:cc:cc") is False  # Multicast bit set!
    assert mgr.validate_mac("00:00:00:00:00:00") is False

    assert mgr.validate_hostname("time.deu.edu.tr") is True
    assert mgr.validate_hostname("time.deu.edu.tr && whoami") is False

    # Apply static IP + VLAN in simulation mode
    mgr.settings.ip_mode = "static"
    mgr.settings.static_ip = "194.27.65.131"
    mgr.settings.subnet_prefix = 24
    mgr.settings.gateway = "194.27.65.1"
    mgr.settings.vlan_enabled = True
    mgr.settings.vlan_id = 65
    ok, msg = mgr.apply_network_config("eth0")
    assert ok is True
    assert cfg_file.exists()

    # Sync NTP in simulation mode
    ok_ntp, msg_ntp = mgr.sync_ntp_time("time.deu.edu.tr")
    assert ok_ntp is True
    assert "time.deu.edu.tr" in msg_ntp
