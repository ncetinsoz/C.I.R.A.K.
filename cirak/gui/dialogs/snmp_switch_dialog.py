"""
Touch-Optimized SNMPv2c Switch Port & Sensor Deep-Dive Modal Dialog.
Queries the connected or specified Switch via SNMPv2c and displays:
  - System Name, IOS/Firmware Version, Uptime, Location
  - Chassis Temperature (°C) & CPU Load (%)
  - Port Summary Counts: Total, Active (UP), Idle (Link Down), Administratively Disabled (Admin-Down / Err-Disabled)
  - Filterable Live Port Table (Port Name, Status, Speed, Description/Alias, Error Counters)
"""

from typing import Optional
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from cirak import config
from cirak.backend.network_detector import NetworkDetector
from cirak.backend.settings_manager import SettingsManager
from cirak.backend.snmp_client import SNMPClient, SNMPSwitchReport
from cirak.core.worker import BaseWorker
from cirak.gui.theme import ThemeManager
from cirak.gui.views.settings_view import TouchableLineEdit, TouchKeypadDialog


class SwitchSNMPDialog(QDialog):
    """Deep-dive SNMP Switch Port & Hardware Sensor Inspector Modal (760x445)."""

    def __init__(
        self,
        initial_ip: str = "",
        initial_community: str = "",
        parent: QWidget = None,
        auto_query: bool = True,
    ):
        super().__init__(parent)
        self.setWindowTitle("SNMP Switch Port, Durum ve Sıcaklık Analizörü")
        self.setFixedSize(760, 445)
        self.setModal(True)

        self.settings_mgr = SettingsManager(simulate=False)
        self._worker: Optional[BaseWorker] = None
        self._last_report: Optional[SNMPSwitchReport] = None
        self._port_filter = "ALL"  # "ALL", "UP", "DOWN", "ADMIN-DOWN"

        gw = NetworkDetector.get_default_gateway()
        default_ip = initial_ip.strip() if initial_ip and initial_ip not in ("--", "Bildirilmedi", "Yok") else ""
        if not default_ip and gw and gw.get("gateway"):
            default_ip = gw["gateway"]

        self.target_ip = default_ip or "194.27.65.1"
        self.community = initial_community.strip() or self.settings_mgr.settings.snmp_community or "public"

        self._init_ui()
        # Automatically trigger query if target IP is ready
        if auto_query and self.target_ip:
            self._run_snmp_query()

    def _init_ui(self):
        colors = ThemeManager.get_colors()
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        input_bg = "#020617" if is_dark else "#f8fafc"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg_main']};
                border: 2px solid {colors['accent_indigo']};
                border-radius: 12px;
            }}
            QFrame#SNMPBar {{
                background-color: {colors['card_bg']};
                border: 1.5px solid {colors['card_border']};
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {colors['text_primary']};
            }}
            QLineEdit {{
                background-color: {input_bg};
                color: {colors['text_primary']};
                border: 1.5px solid {colors['accent_indigo']};
                border-radius: 5px;
                padding: 2px 6px;
                font-family: "DejaVu Sans Mono", monospace;
                font-size: 11px;
                font-weight: bold;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # 1. Top Control Bar: Target IP + SNMP Community String + Query Button
        ctrl_frame = QFrame()
        ctrl_frame.setObjectName("SNMPBar")
        ctrl_l = QHBoxLayout(ctrl_frame)
        ctrl_l.setContentsMargins(10, 6, 10, 6)
        ctrl_l.setSpacing(6)

        lbl_ip = QLabel("Switch IP:")
        lbl_ip.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 10px; font-weight: 800;")
        self.edit_ip = TouchableLineEdit(self.target_ip)
        self.edit_ip.setFixedSize(130, 26)
        self.edit_ip.tapped.connect(lambda: self._open_kbd("SNMP Hedef Switch IP", self.edit_ip, "ip"))

        lbl_comm = QLabel("SNMP Community:")
        lbl_comm.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 10px; font-weight: 800;")
        self.edit_comm = TouchableLineEdit(self.community)
        self.edit_comm.setFixedSize(120, 26)
        self.edit_comm.tapped.connect(
            lambda: self._open_kbd("SNMP Community String", self.edit_comm, "snmp")
        )
        btn_kbd_comm = QPushButton("ABC")
        btn_kbd_comm.setFixedSize(44, 26)
        btn_kbd_comm.setStyleSheet("font-size: 10px; font-weight: bold; padding: 1px 4px;")
        btn_kbd_comm.clicked.connect(
            lambda: self._open_kbd("SNMP Community String", self.edit_comm, "snmp")
        )

        self.btn_query = QPushButton("🔍 SNMP Sorgula")
        self.btn_query.setFixedHeight(26)
        self.btn_query.setCursor(Qt.PointingHandCursor)
        self.btn_query.setStyleSheet(
            f"background-color: {colors['accent_indigo']}; color: #ffffff; border-radius: 5px; padding: 2px 10px; font-size: 11px; font-weight: 900;"
        )
        self.btn_query.clicked.connect(self._run_snmp_query)

        self.btn_close = QPushButton("✕ Kapat")
        self.btn_close.setFixedHeight(26)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)

        ctrl_l.addWidget(lbl_ip)
        ctrl_l.addWidget(self.edit_ip)
        ctrl_l.addSpacing(4)
        ctrl_l.addWidget(lbl_comm)
        ctrl_l.addWidget(self.edit_comm)
        ctrl_l.addWidget(btn_kbd_comm)
        ctrl_l.addStretch()
        ctrl_l.addWidget(self.btn_query)
        ctrl_l.addWidget(self.btn_close)
        layout.addWidget(ctrl_frame)

        # 2. Switch Hardware, Thermal & Uptime Summary Strip
        sum_frame = QFrame()
        sum_frame.setObjectName("SNMPBar")
        sum_l = QVBoxLayout(sum_frame)
        sum_l.setContentsMargins(10, 6, 10, 6)
        sum_l.setSpacing(3)

        top_info = QHBoxLayout()
        self.lbl_sys_name = QLabel("Cihaz: Sorgulanıyor...")
        self.lbl_sys_name.setStyleSheet(f"color: {colors['accent_cyan']}; font-family: monospace; font-size: 11px; font-weight: 900;")

        self.lbl_temp_cpu = QLabel("Sıcaklık: -- °C | CPU: --%")
        self.lbl_temp_cpu.setStyleSheet(f"color: {colors['status_success']}; font-family: monospace; font-size: 11px; font-weight: 900;")

        self.lbl_uptime = QLabel("Uptime: --")
        self.lbl_uptime.setStyleSheet(f"color: {colors['accent_amber']}; font-family: monospace; font-size: 10px; font-weight: bold;")

        top_info.addWidget(self.lbl_sys_name)
        top_info.addStretch()
        top_info.addWidget(self.lbl_temp_cpu)
        top_info.addSpacing(12)
        top_info.addWidget(self.lbl_uptime)

        self.lbl_sys_descr = QLabel("Yazılım / IOS: --")
        self.lbl_sys_descr.setStyleSheet(f"color: {colors['text_secondary']}; font-family: monospace; font-size: 10px;")

        sum_l.addLayout(top_info)
        sum_l.addWidget(self.lbl_sys_descr)
        layout.addWidget(sum_frame)

        # 3. Port Filter & Statistics Bar
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)

        self.btn_f_all = QPushButton("Tüm Portlar (0)")
        self.btn_f_up = QPushButton("🟢 Açık / UP (0)")
        self.btn_f_down = QPushButton("⚪ Boşta / DOWN (0)")
        self.btn_f_admin = QPushButton("🔴 Kapalı / Admin-Down (0)")

        for b, mode in (
            (self.btn_f_all, "ALL"),
            (self.btn_f_up, "UP"),
            (self.btn_f_down, "DOWN"),
            (self.btn_f_admin, "ADMIN-DOWN"),
        ):
            b.setFixedHeight(26)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, m=mode: self._set_port_filter(m))
            filter_row.addWidget(b)

        filter_row.addStretch()
        layout.addLayout(filter_row)

        # 4. Port Status Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Port (IF-MIB)",
            "Durum (Admin / Oper)",
            "Hız",
            "Açıklama (ifAlias)",
            "Hata (In/Out)",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {colors['card_bg']};
                border: 1.5px solid {colors['card_border']};
                border-radius: 8px;
                color: {colors['text_primary']};
                font-family: "DejaVu Sans Mono", monospace;
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {colors['bar_bg']};
                color: {colors['text_secondary']};
                font-weight: 800;
                font-size: 10px;
                border: none;
                border-bottom: 1px solid {colors['card_border']};
                padding: 5px;
            }}
        """)

        hdr_view = self.table.horizontalHeader()
        hdr_view.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr_view.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr_view.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        layout.addWidget(self.table, 1)

    def _open_kbd(self, title: str, line_edit: TouchableLineEdit, mode: str):
        dlg = TouchKeypadDialog(title=title, initial_value=line_edit.text(), mode=mode, parent=self)
        if dlg.exec() == QDialog.Accepted:
            line_edit.setText(dlg.result_text)

    def _set_port_filter(self, mode: str):
        self._port_filter = mode
        self._populate_table()

    def _run_snmp_query(self):
        ip = self.edit_ip.text().strip()
        comm = self.edit_comm.text().strip() or "public"
        self.settings_mgr.settings.snmp_community = comm
        self.settings_mgr.save()

        self.btn_query.setEnabled(False)
        self.btn_query.setText("Sorgulanıyor...")
        self.lbl_sys_name.setText(f"Cihaz: {ip} sorgulanıyor (UDP/161)...")

        def _task():
            client = SNMPClient(target_ip=ip, community=comm, timeout_sec=1.2, simulate=False)
            return client.query_switch()

        self._worker = BaseWorker(_task)
        self._worker.signals.result.connect(self._on_query_finished, Qt.QueuedConnection)
        self._worker.signals.error.connect(self._on_query_error, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._worker)

    def _on_query_finished(self, report: SNMPSwitchReport):
        colors = ThemeManager.get_colors()
        self.btn_query.setEnabled(True)
        self.btn_query.setText("🔍 SNMP Sorgula")
        self._last_report = report

        if not report.reachable:
            self.lbl_sys_name.setText(f"✗ SNMP Yanıtı Yok ({report.target_ip})")
            self.lbl_sys_name.setStyleSheet(f"color: {colors['status_error']}; font-family: monospace; font-size: 11px; font-weight: 900;")
            self.lbl_sys_descr.setText(report.error_message)
            self.table.setRowCount(0)
            return

        self.lbl_sys_name.setText(f"✓ Cihaz: {report.sys_name} ({report.target_ip})")
        self.lbl_sys_name.setStyleSheet(f"color: {colors['accent_cyan']}; font-family: monospace; font-size: 11px; font-weight: 900;")

        t_str = f"{report.temperature_c} °C" if report.temperature_c is not None else "Sensör Yok"
        c_str = f"%{report.cpu_load_pct}" if report.cpu_load_pct is not None else "--"
        self.lbl_temp_cpu.setText(f"🌡 Sıcaklık: {t_str} | CPU: {c_str}")
        self.lbl_uptime.setText(f"⏱ Uptime: {report.uptime_str}")

        _, ios_clean = NetworkDetector.extract_model_and_ios(report.sys_descr, sw_ver=report.sys_descr)
        self.lbl_sys_descr.setText(f"Yazılım / Sistem: {(ios_clean or report.sys_descr)[:85]}")

        self.btn_f_all.setText(f"Tüm Portlar ({report.total_ports})")
        self.btn_f_up.setText(f"🟢 Açık / UP ({report.up_ports})")
        self.btn_f_down.setText(f"⚪ Boşta / DOWN ({report.down_ports})")
        self.btn_f_admin.setText(f"🔴 Kapalı / Admin-Down ({report.admin_down_ports})")

        self._populate_table()

    def _on_query_error(self, err_tuple):
        self.btn_query.setEnabled(True)
        self.btn_query.setText("🔍 SNMP Sorgula")
        self.lbl_sys_name.setText("✗ SNMP Sorgu Hatası")

    def _populate_table(self):
        if not self._last_report or not self._last_report.reachable:
            return

        colors = ThemeManager.get_colors()
        filtered = []
        for p in self._last_report.ports:
            if self._port_filter == "ALL":
                filtered.append(p)
            elif self._port_filter == "UP" and p.oper_status == "UP" and p.admin_status == "UP":
                filtered.append(p)
            elif self._port_filter == "DOWN" and p.oper_status != "UP" and p.admin_status == "UP":
                filtered.append(p)
            elif self._port_filter == "ADMIN-DOWN" and p.admin_status == "ADMIN-DOWN":
                filtered.append(p)

        self.table.setRowCount(len(filtered))
        for row, p in enumerate(filtered):
            self.table.setRowHeight(row, 28)

            it_name = QTableWidgetItem(p.name)
            it_name.setFont(QFont("DejaVu Sans Mono", 10, QFont.Bold))

            if p.admin_status == "ADMIN-DOWN":
                st_color = colors["status_error"]
            elif p.oper_status == "UP":
                st_color = colors["status_success"]
            else:
                st_color = colors["text_secondary"]

            it_state = QTableWidgetItem(p.display_state)
            it_state.setForeground(QColor(st_color))
            it_state.setFont(QFont("DejaVu Sans Mono", 10, QFont.Bold))

            spd_txt = f"{p.speed_mbps} Mbps" if p.speed_mbps > 0 else "--"
            it_spd = QTableWidgetItem(spd_txt)
            it_spd.setTextAlignment(Qt.AlignCenter)

            it_alias = QTableWidgetItem(p.alias or "--")

            err_total = p.in_errors + p.out_errors
            it_err = QTableWidgetItem(f"{p.in_errors} / {p.out_errors}")
            it_err.setTextAlignment(Qt.AlignCenter)
            if err_total > 0:
                it_err.setForeground(QColor(colors["status_warning"]))

            self.table.setItem(row, 0, it_name)
            self.table.setItem(row, 1, it_state)
            self.table.setItem(row, 2, it_spd)
            self.table.setItem(row, 3, it_alias)
            self.table.setItem(row, 4, it_err)
