from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from apk_research.desktop.evidence_navigation_window import (
    UnifiedEvidenceMainWindow,
)
from apk_research.desktop.protocol_analysis_v025 import (
    format_protocol_analysis,
)
from apk_research.desktop.packet_inspector import (
    RAW_PCAP_ARTIFACT,
    format_packet_details,
    inspect_archive_flow,
    packet_action_label,
    packet_metadata_label,
    packet_search_text,
)

_ROLE_PACKET = int(Qt.ItemDataRole.UserRole)


class PacketInspectorMainWindow(UnifiedEvidenceMainWindow):
    """v0.18 Raw / Packet Inspector over the existing Research ZIP PCAP."""

    packetReady = Signal(dict)

    def _build_ui(self) -> None:
        super()._build_ui()
        self.packet_tab_index = self.tabs.insertTab(
            self.evidence_tab_index + 1,
            self._build_packet_tab(),
            "Packets",
        )

    def _build_evidence_tab(self) -> QWidget:
        page = super()._build_evidence_tab()
        layout = page.layout()
        packet_nav = QHBoxLayout()
        self.evidence_open_packets = QPushButton(
            "Пакеты выбранного flow"
        )
        self.evidence_open_packets.setEnabled(False)
        packet_nav.addWidget(self.evidence_open_packets)
        packet_nav.addStretch(1)
        layout.insertLayout(
            max(0, layout.count() - 2),
            packet_nav,
        )
        return page

    def _build_network_tab(self) -> QWidget:
        page = super()._build_network_tab()
        layout = page.layout()
        self.network_open_packets = QPushButton(
            "Пакеты выбранного flow"
        )
        self.network_open_packets.setEnabled(False)
        layout.insertWidget(
            max(0, layout.count() - 1),
            self.network_open_packets,
        )
        return page

    def _build_packet_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        controls = QHBoxLayout()
        self.packet_load_selected = QPushButton(
            "Открыть пакеты выбранного flow"
        )
        self.packet_open_timeline = QPushButton(
            "Открыть действие в Timeline"
        )
        self.packet_open_timeline.setEnabled(False)
        self.packet_search = QLineEdit()
        self.packet_search.setPlaceholderText(
            "packet / time / IP / port / action / DNS / TLS / QUIC / HTTP3 / HTTP / ACK / sequence"
        )
        controls.addWidget(self.packet_load_selected)
        controls.addWidget(self.packet_open_timeline)
        controls.addWidget(self.packet_search, 1)
        layout.addLayout(controls)

        self.packet_summary = QLabel(
            "Packet Inspector: выберите flow в Evidence или Network"
        )
        self.packet_summary.setWordWrap(True)
        layout.addWidget(self.packet_summary)

        self.protocol_analysis = QPlainTextEdit()
        self.protocol_analysis.setReadOnly(True)
        self.protocol_analysis.setMaximumHeight(220)
        self.protocol_analysis.setPlaceholderText(
            "v0.25: выберите поток для анализа транспорта и протоколов."
        )
        layout.addWidget(self.protocol_analysis)

        self.packet_table = QTableWidget()
        self.packet_table.setColumnCount(9)
        self.packet_table.setHorizontalHeaderLabels(
            [
                "#",
                "Target UTC",
                "Dir",
                "Protocol",
                "Source",
                "Destination",
                "Captured",
                "Action window",
                "Protocol evidence",
            ]
        )
        self.packet_table.setAlternatingRowColors(True)
        self.packet_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.packet_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.packet_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.packet_table.verticalHeader().setVisible(False)
        self.packet_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.packet_table, 1)

        self.packet_details = QPlainTextEdit()
        self.packet_details.setReadOnly(True)
        self.packet_details.setMaximumHeight(330)
        self.packet_details.setPlaceholderText(
            "Выберите пакет для raw locator и bounded hex-preview."
        )
        layout.addWidget(self.packet_details)

        note = QLabel(
            "Packet Inspector читает существующий traffic.pcap напрямую из Research ZIP. "
            "Он не создаёт новую forensic-истину и не трактует зашифрованные байты как plaintext. "
            "v0.25 анализирует только захваченные байты: разрывы sequence, повторы ACK и диапазонов "
            "остаются наблюдениями захвата, а не доказанной потерей/повторной передачей. "
            "Зашифрованные прикладные данные не выдаются за открытый текст."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        return page

    def _connect_signals(self) -> None:
        super()._connect_signals()
        self.packetReady.connect(self._on_packet_ready)
        self.evidence_tree.itemSelectionChanged.connect(
            self._update_evidence_packet_button
        )
        self.evidence_open_packets.clicked.connect(
            self._open_evidence_packets
        )
        self.network_tree.itemSelectionChanged.connect(
            self._update_network_packet_button
        )
        self.network_open_packets.clicked.connect(
            self._open_network_packets
        )
        self.packet_load_selected.clicked.connect(
            self._open_current_packet_flow
        )
        self.packet_open_timeline.clicked.connect(
            self._open_packet_timeline
        )
        self.packet_search.textChanged.connect(
            self._apply_packet_filter
        )
        self.packet_table.itemSelectionChanged.connect(
            self._on_packet_selection_changed
        )

    def _update_evidence_packet_button(self) -> None:
        node = self._selected_evidence_node()
        flow_id = self._node_flow_id(node)
        enabled = False
        if flow_id:
            if isinstance(node, dict) and str(node.get("kind") or "") == "raw":
                locator = node.get("locator")
                enabled = (
                    isinstance(locator, dict)
                    and str(locator.get("artifact") or "") == RAW_PCAP_ARTIFACT
                )
            else:
                enabled = True
        self.evidence_open_packets.setEnabled(enabled)

    def _update_network_packet_button(self) -> None:
        data = self._selected_network_data()
        flow = data[1] if data else None
        self.network_open_packets.setEnabled(
            isinstance(flow, dict)
            and bool(flow.get("flow_id"))
        )

    def _flow_from_evidence_selection(self) -> dict[str, Any] | None:
        node = self._selected_evidence_node()
        flow_id = self._node_flow_id(node)
        model = getattr(self, "_evidence_model", None)
        flow_index = (
            model.get("flow_index")
            if isinstance(model, dict)
            else None
        )
        if not flow_id or not isinstance(flow_index, dict):
            return None
        flow = flow_index.get(flow_id)
        return flow if isinstance(flow, dict) else None

    def _open_current_packet_flow(self) -> None:
        flow = self._flow_from_evidence_selection()
        archive = str(getattr(self, "_evidence_archive", "") or "")
        if flow is not None and archive:
            self._load_packet_flow(archive, flow)
            return
        data = self._selected_network_data()
        if not data:
            return
        _, network_flow = data
        network_archive = str(
            getattr(self, "_network_archive", "")
            or ""
        )
        if isinstance(network_flow, dict) and network_archive:
            self._load_packet_flow(network_archive, network_flow)

    def _open_evidence_packets(self) -> None:
        flow = self._flow_from_evidence_selection()
        archive = str(getattr(self, "_evidence_archive", "") or "")
        if flow is None or not archive:
            return
        self._load_packet_flow(archive, flow)

    def _open_network_packets(self) -> None:
        data = self._selected_network_data()
        if not data:
            return
        _, flow = data
        archive = str(getattr(self, "_network_archive", "") or "")
        if isinstance(flow, dict) and archive:
            self._load_packet_flow(archive, flow)

    def _open_evidence_item(
        self,
        item,
        column: int,
    ) -> None:
        node = item.data(0, int(Qt.ItemDataRole.UserRole))
        if isinstance(node, dict) and str(node.get("kind") or "") == "raw":
            locator = node.get("locator")
            if (
                isinstance(locator, dict)
                and str(locator.get("artifact") or "") == RAW_PCAP_ARTIFACT
            ):
                self.evidence_tree.setCurrentItem(item)
                self._open_evidence_packets()
                return
        super()._open_evidence_item(item, column)

    def _load_packet_flow(
        self,
        archive: str,
        flow: dict[str, Any],
    ) -> None:
        flow_id = str(flow.get("flow_id") or "")
        cache = getattr(self, "_packet_report", None)
        if (
            isinstance(cache, dict)
            and str(cache.get("archive") or "") == archive
            and str(cache.get("flow_id") or "") == flow_id
        ):
            self.tabs.setCurrentIndex(self.packet_tab_index)
            return

        self.packet_summary.setText(
            f"Чтение raw PCAP для {flow_id or 'flow'}…"
        )
        self.controller._thread(
            self._load_packet_flow_worker,
            Path(archive),
            dict(flow),
        )

    def _load_packet_flow_worker(
        self,
        archive: Path,
        flow: dict[str, Any],
    ) -> None:
        try:
            report = inspect_archive_flow(
                archive,
                flow,
            )
            self.packetReady.emit(report)
        except KeyError:
            self.controller.error.emit(
                f"В Research ZIP нет {RAW_PCAP_ARTIFACT}"
            )
        except Exception as exc:
            self.controller.error.emit(
                str(exc) or exc.__class__.__name__
            )

    def _on_packet_ready(self, report: dict) -> None:
        self._packet_report = report
        self.protocol_analysis.setPlainText(
            format_protocol_analysis(report.get("protocol_analysis"))
        )
        packets = [
            packet
            for packet in report.get("packets") or []
            if isinstance(packet, dict)
        ]
        self.packet_table.setRowCount(len(packets))

        for row, packet in enumerate(packets):
            values = [
                str(packet.get("packet_index") or ""),
                str(packet.get("target_utc") or ""),
                str(packet.get("direction") or "unknown"),
                str(packet.get("protocol") or "").upper(),
                self._packet_endpoint(
                    packet.get("src"),
                    packet.get("src_port"),
                ),
                self._packet_endpoint(
                    packet.get("dst"),
                    packet.get("dst_port"),
                ),
                str(packet.get("captured_length") or 0),
                packet_action_label(packet) or "—",
                packet_metadata_label(packet),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(_ROLE_PACKET, packet)
                self.packet_table.setItem(row, column, item)

        self.packet_table.resizeColumnsToContents()
        session = report.get("transport_session")
        session_text = ""
        if (
            isinstance(session, dict)
            and session.get("applicable") is True
        ):
            session_text = (
                f" • handshake {session.get('handshake_status') or '—'}"
                f" • termination {session.get('termination_status') or '—'}"
            )
        self.packet_summary.setText(
            f"{report.get('flow_id') or '—'}"
            f" • {str(report.get('protocol') or '').upper() or '—'}"
            f" • {int(report.get('selected_packet_count') or 0)} packet(s) in flow"
            f" / {int(report.get('total_packet_count') or 0)} total PCAP packet(s)"
            f" • linktype {report.get('linktype') if report.get('linktype') is not None else '—'}"
            f" • PCAP {int(report.get('artifact_size') or 0)} bytes"
            f" • CRC32 {report.get('artifact_crc32') or '—'}"
            f" • action windows {int(report.get('timeline_action_window_count') or 0)}"
            f" • matched packets {int(report.get('packet_action_match_count') or 0)}"
            f"{session_text}"
        )
        self.tabs.setCurrentIndex(self.packet_tab_index)
        self._apply_packet_filter()
        if packets:
            self.packet_table.selectRow(0)

    @staticmethod
    def _packet_endpoint(ip_value: Any, port_value: Any) -> str:
        ip_text = str(ip_value or "—")
        port_text = "—" if port_value is None else str(port_value)
        return f"{ip_text}:{port_text}"

    def _selected_packet(self) -> dict[str, Any] | None:
        row = self.packet_table.currentRow()
        if row < 0:
            return None
        item = self.packet_table.item(row, 0)
        if item is None:
            return None
        value = item.data(_ROLE_PACKET)
        return value if isinstance(value, dict) else None

    def _selected_packet_action_id(self) -> str:
        packet = self._selected_packet()
        if not isinstance(packet, dict):
            return ""
        for value in packet.get("temporal_action_ids") or []:
            action_id = str(value or "")
            if action_id:
                return action_id
        return ""

    def _update_packet_timeline_button(self) -> None:
        self.packet_open_timeline.setEnabled(
            bool(self._selected_packet_action_id())
        )

    def _on_packet_selection_changed(self) -> None:
        self._show_packet_details()
        self._update_packet_timeline_button()

    def _open_packet_timeline(self) -> None:
        action_id = self._selected_packet_action_id()
        report = getattr(self, "_packet_report", None)
        archive = (
            str(report.get("archive") or "")
            if isinstance(report, dict)
            else ""
        )
        if not action_id or not archive:
            return
        if (
            archive
            == str(getattr(self, "_timeline_archive", "") or "")
            and self._select_timeline_action(action_id)
        ):
            return
        self._pending_timeline_action_id = action_id
        self.controller._thread(
            self._load_refined_timeline,
            archive,
        )

    def _show_packet_details(self) -> None:
        packet = self._selected_packet()
        if packet is None:
            self.packet_details.clear()
            return
        artifact = (
            str(
                getattr(self, "_packet_report", {}).get("artifact")
                if isinstance(getattr(self, "_packet_report", None), dict)
                else ""
            )
            or RAW_PCAP_ARTIFACT
        )
        self.packet_details.setPlainText(
            format_packet_details(
                packet,
                artifact=artifact,
            )
        )

    def _apply_packet_filter(self) -> None:
        if not hasattr(self, "packet_table"):
            return
        query = self.packet_search.text().strip().lower()
        for row in range(self.packet_table.rowCount()):
            item = self.packet_table.item(row, 0)
            packet = item.data(_ROLE_PACKET) if item is not None else None
            visible = (
                not query
                or (
                    isinstance(packet, dict)
                    and query in packet_search_text(packet)
                )
                or any(
                    query in str(
                        self.packet_table.item(row, column).text()
                        if self.packet_table.item(row, column) is not None
                        else ""
                    ).lower()
                    for column in range(self.packet_table.columnCount())
                )
            )
            self.packet_table.setRowHidden(row, not visible)
