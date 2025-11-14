"""
작업 로그 관리 모듈 (PyQt5 버전)
작업 로그 입력, 저장, 로드, 내보내기, 달력 보기 기능을 제공
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

from work_log_calendar_view import open_work_log_calendar

CATEGORY_OPTIONS: List[str] = [
    "Li-Ag 충전",
    "IR Align",
    "EUV Align",
    "CNT 장착",
    "기타 장비 점검",
]

STATUS_OPTIONS: List[str] = ["진행중", "완료"]


class WorkLogManager:
    """작업 로그 관리 컨트롤러 클래스."""

    def __init__(self, parent_widget: Optional[Any] = None) -> None:
        """컨트롤러를 초기화한다."""
        if parent_widget is not None and not isinstance(parent_widget, QtWidgets.QWidget):
            self.parent_widget = None
        else:
            self.parent_widget = parent_widget
        self.log_file_path = Path(__file__).resolve().parent / "work_log.json"

        print(f"작업 로그 파일: {self.log_file_path}")
        if self.log_file_path.exists():
            logs = self.load_work_logs()
            print(f"기존 로그 {len(logs)}개 로드됨")
        else:
            print("새 작업 로그 파일이 생성됩니다.")

    def load_work_logs(self) -> List[Dict[str, Any]]:
        """JSON 파일에서 작업 로그를 읽어 리스트로 반환한다."""
        if not self.log_file_path.exists():
            return []
        try:
            with self.log_file_path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as exc:  # noqa: BLE001
            print(f"로그 파일 읽기 오류: {exc}")
        return []

    def save_work_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """작업 로그 리스트를 JSON 파일로 저장한다."""
        try:
            with self.log_file_path.open("w", encoding="utf-8") as file:
                json.dump(logs, file, ensure_ascii=False, indent=2)
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"로그 파일 저장 오류: {exc}")
            return False

    def sort_logs(self, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """작업 로그 리스트를 시작 시각 기준으로 정렬한다."""
        return sorted(logs, key=self._log_sort_key, reverse=True)

    @staticmethod
    def _log_sort_key(log: Dict[str, Any]) -> datetime.datetime:
        """정렬을 위한 기준 시각을 계산한다."""
        start_value = log.get("start_datetime")
        if start_value:
            parsed = WorkLogManager._parse_datetime(start_value)
            if parsed is not None:
                return parsed

        date_value = log.get("date")
        if date_value:
            try:
                return datetime.datetime.strptime(date_value, "%Y-%m-%d")
            except ValueError:
                pass

        timestamp_value = log.get("timestamp")
        if timestamp_value:
            try:
                return datetime.datetime.strptime(timestamp_value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        return datetime.datetime.min

    @staticmethod
    def _parse_datetime(value: str) -> Optional[datetime.datetime]:
        """문자열을 datetime 객체로 변환한다."""
        try:
            return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError:
            return None

    def show_work_log(self) -> None:
        """PyQt 대화상자를 띄워 작업 로그를 관리한다."""
        app = QtWidgets.QApplication.instance()
        created = False
        if app is None:
            app = QtWidgets.QApplication(sys.argv or [""])  # type: ignore[arg-type]
            created = True

        parent: Optional[QtWidgets.QWidget] = self.parent_widget if isinstance(self.parent_widget, QtWidgets.QWidget) else None
        dialog = WorkLogManagerDialog(manager=self, parent=parent)
        dialog.exec_()

        if created:
            app.quit()


class WorkLogManagerDialog(QtWidgets.QDialog):
    """작업 로그 입력 및 목록 관리를 위한 대화상자."""

    def __init__(self, manager: WorkLogManager, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """대화상자를 초기화한다."""
        super().__init__(parent)
        self.manager = manager
        self._display_logs: List[Dict[str, Any]] = []

        self.setWindowTitle("작업 로그 관리")
        self.resize(1100, 780)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._build_ui()
        self._connect_signals()
        self._set_default_times()
        self.refresh_table()

    def _build_ui(self) -> None:
        """UI 위젯을 생성하고 배치한다."""
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self._build_input_group()
        self._build_table_group()

    def _build_input_group(self) -> None:
        """입력 영역 UI를 구성한다."""
        group = QtWidgets.QGroupBox("새 작업 로그 입력", self)
        layout = QtWidgets.QGridLayout(group)

        today = QtCore.QDate.currentDate()
        now = QtCore.QDateTime.currentDateTime()

        date_label = QtWidgets.QLabel("날짜:", group)
        self.date_edit = QtWidgets.QDateEdit(today, group)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setCalendarPopup(True)

        category_label = QtWidgets.QLabel("작업 종류:", group)
        self.category_combo = QtWidgets.QComboBox(group)
        self.category_combo.addItems(CATEGORY_OPTIONS)

        status_label = QtWidgets.QLabel("상태:", group)
        self.status_combo = QtWidgets.QComboBox(group)
        self.status_combo.addItems(STATUS_OPTIONS)

        start_label = QtWidgets.QLabel("시작 시각:", group)
        self.start_edit = QtWidgets.QDateTimeEdit(now, group)
        self.start_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_edit.setCalendarPopup(True)

        self.end_label = QtWidgets.QLabel("예상 종료:", group)
        self.end_edit = QtWidgets.QDateTimeEdit(now.addSecs(3600), group)
        self.end_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_edit.setCalendarPopup(True)

        content_label = QtWidgets.QLabel("작업 내용:", group)
        self.content_edit = QtWidgets.QPlainTextEdit(group)
        self.content_edit.setPlaceholderText("작업 내용을 입력하세요.")
        self.content_edit.setMinimumHeight(100)

        self.add_button = QtWidgets.QPushButton("로그 추가", group)
        self.clear_button = QtWidgets.QPushButton("입력 초기화", group)

        layout.addWidget(date_label, 0, 0)
        layout.addWidget(self.date_edit, 0, 1)
        layout.addWidget(category_label, 0, 2)
        layout.addWidget(self.category_combo, 0, 3)
        layout.addWidget(status_label, 0, 4)
        layout.addWidget(self.status_combo, 0, 5)

        layout.addWidget(start_label, 1, 0)
        layout.addWidget(self.start_edit, 1, 1, 1, 2)
        layout.addWidget(self.end_label, 1, 3)
        layout.addWidget(self.end_edit, 1, 4, 1, 2)

        layout.addWidget(content_label, 2, 0, 1, 6)
        layout.addWidget(self.content_edit, 3, 0, 1, 6)

        layout.addWidget(self.clear_button, 4, 4)
        layout.addWidget(self.add_button, 4, 5)

        self.main_layout.addWidget(group)

    def _build_table_group(self) -> None:
        """로그 목록 영역 UI를 구성한다."""
        group = QtWidgets.QGroupBox("작업 로그 이력", self)
        layout = QtWidgets.QVBoxLayout(group)

        filter_layout = QtWidgets.QHBoxLayout()
        filter_label = QtWidgets.QLabel("카테고리 필터:", group)
        self.filter_combo = QtWidgets.QComboBox(group)
        self.filter_combo.addItem("전체")
        self.filter_combo.addItems(CATEGORY_OPTIONS)
        self.filter_combo.setCurrentIndex(0)
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()

        self.table = QtWidgets.QTableWidget(0, 6, group)
        self.table.setHorizontalHeaderLabels(
            ["날짜", "작업 종류", "상태", "작업 시간", "내용", "등록 시간"],
        )
        header = self.table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(True)
        vertical_header = self.table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)

        button_layout = QtWidgets.QHBoxLayout()
        self.refresh_button = QtWidgets.QPushButton("새로고침", group)
        self.edit_button = QtWidgets.QPushButton("선택 로그 수정", group)
        self.delete_button = QtWidgets.QPushButton("선택 로그 삭제", group)
        self.export_button = QtWidgets.QPushButton("로그 내보내기", group)
        self.calendar_button = QtWidgets.QPushButton("달력으로 보기", group)

        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.calendar_button)
        button_layout.addStretch()

        self.stats_label = QtWidgets.QLabel("표시할 로그가 없습니다.", group)
        self.stats_label.setStyleSheet("color: #555555;")

        layout.addLayout(filter_layout)
        layout.addWidget(self.table)
        layout.addWidget(self.stats_label)
        layout.addLayout(button_layout)

        self.main_layout.addWidget(group, stretch=1)

    def _connect_signals(self) -> None:
        """위젯 시그널을 슬롯에 연결한다."""
        self.status_combo.currentTextChanged.connect(self._on_status_changed)
        self.add_button.clicked.connect(self._on_add_clicked)
        self.clear_button.clicked.connect(self._on_clear_clicked)
        self.refresh_button.clicked.connect(self.refresh_table)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.edit_button.clicked.connect(self._on_edit_clicked)
        self.export_button.clicked.connect(self._on_export_clicked)
        self.calendar_button.clicked.connect(self._on_calendar_clicked)
        self.filter_combo.currentTextChanged.connect(self.refresh_table)
        self.table.doubleClicked.connect(self._on_detail_requested)

    def _set_default_times(self) -> None:
        """시작/종료 시각의 기본값을 설정한다."""
        now = QtCore.QDateTime.currentDateTime()
        self.start_edit.setDateTime(now)
        self.end_edit.setDateTime(now.addSecs(3600))

    def _on_status_changed(self, status_text: str) -> None:
        """상태에 따라 종료 라벨을 갱신한다."""
        if status_text == "완료":
            self.end_label.setText("완료 시각:")
        else:
            self.end_label.setText("예상 종료:")

    def _on_clear_clicked(self) -> None:
        """입력 필드를 초기화한다."""
        self.date_edit.setDate(QtCore.QDate.currentDate())
        self.category_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self._set_default_times()
        self.content_edit.clear()
        self.content_edit.setFocus()

    def refresh_table(self) -> None:
        """로그 테이블 데이터를 새로고침한다."""
        logs = self.manager.sort_logs(self.manager.load_work_logs())
        filter_value = self._current_filter()

        filtered: List[Dict[str, Any]] = []
        for log in logs:
            if filter_value != "전체" and log.get("category", "미분류") != filter_value:
                continue
            filtered.append(log)

        self._display_logs = filtered
        self.table.setRowCount(len(filtered))

        for row, log in enumerate(filtered):
            self._populate_row(row, log)

        self.table.resizeColumnsToContents()
        self._update_stats(filtered, len(logs))

    def _populate_row(self, row: int, log: Dict[str, Any]) -> None:
        """테이블의 한 행을 채운다."""
        items = [
            log.get("date", ""),
            log.get("category", "미분류"),
            log.get("status", "미지정"),
            self._format_time_range(log),
            self._content_preview(log.get("content", "")),
            log.get("timestamp", ""),
        ]

        for column, value in enumerate(items):
            item = QtWidgets.QTableWidgetItem(value)
            if column == 2:
                color = QtGui.QColor("#1e88e5")
                if value == "완료":
                    color = QtGui.QColor("#2e7d32")
                item.setForeground(QtGui.QBrush(color))
            if column == 4:
                item.setToolTip(log.get("content", ""))
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, column, item)

    def _collect_form_data(self) -> Optional[Dict[str, Any]]:
        """입력 폼 값을 읽어 검증한 뒤 로그 딕셔너리를 생성한다."""
        date_value = self.date_edit.date().toPyDate()
        category = self.category_combo.currentText().strip()
        status = self.status_combo.currentText().strip()
        start_dt = self.start_edit.dateTime().toPyDateTime()
        end_dt = self.end_edit.dateTime().toPyDateTime()
        content = self.content_edit.toPlainText().strip()

        if not category:
            QtWidgets.QMessageBox.warning(self, "입력 오류", "장비 카테고리를 선택하세요.")
            return None
        if not status:
            QtWidgets.QMessageBox.warning(self, "입력 오류", "작업 상태를 선택하세요.")
            return None
        if not content:
            QtWidgets.QMessageBox.warning(self, "입력 오류", "작업 내용을 입력하세요.")
            self.content_edit.setFocus()
            return None
        if start_dt >= end_dt:
            QtWidgets.QMessageBox.warning(
                self,
                "시간 오류",
                "종료 시간은 시작 시간보다 늦어야 합니다.",
            )
            return None

        new_log: Dict[str, Any] = {
            "date": date_value.strftime("%Y-%m-%d"),
            "category": category,
            "status": status,
            "start_datetime": start_dt.strftime("%Y-%m-%d %H:%M"),
            "end_datetime": end_dt.strftime("%Y-%m-%d %H:%M"),
            "start_time": start_dt.strftime("%H:%M"),
            "end_time": end_dt.strftime("%H:%M"),
            "content": content,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return new_log

    def _on_add_clicked(self) -> None:
        """새 로그를 추가한다."""
        form_data = self._collect_form_data()
        if form_data is None:
            return

        logs = self.manager.load_work_logs()
        logs.append(form_data)
        logs = self.manager.sort_logs(logs)

        if self.manager.save_work_logs(logs):
            QtWidgets.QMessageBox.information(self, "저장 완료", "작업 로그가 저장되었습니다.")
            self._on_clear_clicked()
            self.refresh_table()
        else:
            QtWidgets.QMessageBox.critical(self, "저장 실패", "로그 저장에 실패했습니다.")

    def _on_edit_clicked(self) -> None:
        """선택한 로그를 수정한다."""
        log = self._current_selection()
        if log is None:
            QtWidgets.QMessageBox.information(
                self,
                "선택 필요",
                "수정할 로그를 먼저 선택하세요.",
            )
            return

        dialog = LogEditorDialog(log, parent=self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        updated_log = dialog.result_log
        if updated_log is None:
            return

        logs = self.manager.load_work_logs()
        target_timestamp = updated_log["timestamp"]
        for index, item in enumerate(logs):
            if item.get("timestamp") == target_timestamp:
                logs[index] = updated_log
                break
        else:
            QtWidgets.QMessageBox.warning(self, "수정 실패", "해당 로그를 찾을 수 없습니다.")
            return

        logs = self.manager.sort_logs(logs)
        if self.manager.save_work_logs(logs):
            QtWidgets.QMessageBox.information(self, "수정 완료", "작업 로그가 수정되었습니다.")
            self.refresh_table()
        else:
            QtWidgets.QMessageBox.critical(self, "수정 실패", "로그 수정 중 오류가 발생했습니다.")

    def _on_delete_clicked(self) -> None:
        """선택한 로그를 삭제한다."""
        log = self._current_selection()
        if log is None:
            QtWidgets.QMessageBox.information(
                self,
                "선택 필요",
                "삭제할 로그를 먼저 선택하세요.",
            )
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "삭제 확인",
            "선택한 로그를 삭제하시겠습니까?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        logs = self.manager.load_work_logs()
        target_timestamp = log.get("timestamp")
        logs = [
            item
            for item in logs
            if item.get("timestamp") != target_timestamp
        ]

        if self.manager.save_work_logs(self.manager.sort_logs(logs)):
            QtWidgets.QMessageBox.information(self, "삭제 완료", "선택한 로그가 삭제되었습니다.")
            self.refresh_table()
        else:
            QtWidgets.QMessageBox.critical(self, "삭제 실패", "로그 삭제 중 오류가 발생했습니다.")

    def _on_export_clicked(self) -> None:
        """로그 데이터를 파일로 내보낸다."""
        logs = self.manager.load_work_logs()
        if not logs:
            QtWidgets.QMessageBox.warning(self, "내보내기", "내보낼 로그가 없습니다.")
            return

        file_path, file_type = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "작업 로그 내보내기",
            "work_log_export.xlsx",
            "Excel Files (*.xlsx);;CSV Files (*.csv);;JSON Files (*.json)",
        )
        if not file_path:
            return

        try:
            if file_path.lower().endswith(".json"):
                with Path(file_path).open("w", encoding="utf-8") as file:
                    json.dump(logs, file, ensure_ascii=False, indent=2)
            else:
                df = pd.DataFrame(logs)
                if file_path.lower().endswith(".csv"):
                    df.to_csv(file_path, index=False, encoding="utf-8-sig")
                else:
                    df.to_excel(file_path, index=False)
            QtWidgets.QMessageBox.information(
                self,
                "내보내기 완료",
                f"로그가 내보내졌습니다:\n{file_path}",
            )
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(
                self,
                "내보내기 실패",
                f"파일 내보내기에 실패했습니다:\n{exc}",
            )

    def _on_calendar_clicked(self) -> None:
        """달력 뷰를 연다."""
        logs = self.manager.load_work_logs()
        if not logs:
            QtWidgets.QMessageBox.information(self, "정보", "등록된 작업 로그가 없습니다.")
            return
        open_work_log_calendar(self, logs)

    def _on_detail_requested(self, index: QtCore.QModelIndex) -> None:
        """선택된 로그의 상세 정보를 표시한다."""
        log = self._current_selection()
        if log is None:
            return
        dialog = LogDetailDialog(log, parent=self)
        dialog.exec_()

    def _current_filter(self) -> str:
        """현재 선택된 필터 값을 반환한다."""
        return self.filter_combo.currentText().strip()

    def _current_selection(self) -> Optional[Dict[str, Any]]:
        """현재 테이블에서 선택된 로그를 반환한다."""
        selected = self.table.currentRow()
        if selected < 0 or selected >= len(self._display_logs):
            return None
        return self._display_logs[selected]

    def _format_time_range(self, log: Dict[str, Any]) -> str:
        """로그에 포함된 시간 범위를 문자열로 만든다."""
        start_value = log.get("start_datetime")
        end_value = log.get("end_datetime")
        if start_value and end_value:
            start_dt = WorkLogManager._parse_datetime(start_value)
            end_dt = WorkLogManager._parse_datetime(end_value)
            if start_dt and end_dt:
                if start_dt.date() == end_dt.date():
                    return f"{start_dt.strftime('%H:%M')} ~ {end_dt.strftime('%H:%M')}"
                return (
                    f"{start_dt.strftime('%m/%d %H:%M')} ~ "
                    f"{end_dt.strftime('%m/%d %H:%M')}"
                )

        start_time = log.get("start_time")
        end_time = log.get("end_time")
        if start_time and end_time:
            return f"{start_time} ~ {end_time}"

        return "시간 정보 없음"

    def _content_preview(self, content: str, limit: int = 80) -> str:
        """내용의 미리보기를 생성한다."""
        clean = content.replace("\n", " ").strip()
        if len(clean) <= limit:
            return clean
        return f"{clean[:limit]}..."

    def _update_stats(self, filtered: List[Dict[str, Any]], total_count: int) -> None:
        """상태 표시 라벨을 갱신한다."""
        unique_days = len({log.get("date") for log in filtered})
        message = (
            f"총 {total_count}건 중 {len(filtered)}건 표시 | "
            f"고유 날짜 {unique_days}일"
        )
        self.stats_label.setText(message)


class LogEditorDialog(QtWidgets.QDialog):
    """기존 로그 수정을 위한 대화상자."""

    def __init__(self, log: Dict[str, Any], parent: Optional[QtWidgets.QWidget] = None) -> None:
        """수정 대화상자를 초기화한다."""
        super().__init__(parent)
        self.original_log = log
        self.result_log: Optional[Dict[str, Any]] = None

        self.setWindowTitle("작업 로그 수정")
        self.resize(600, 400)

        self._build_ui()
        self._populate_fields()

    def _build_ui(self) -> None:
        """UI 위젯을 구성한다."""
        layout = QtWidgets.QVBoxLayout(self)

        form_layout = QtWidgets.QFormLayout()

        self.date_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate(), self)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setCalendarPopup(True)

        self.category_combo = QtWidgets.QComboBox(self)
        self.category_combo.addItems(CATEGORY_OPTIONS)

        self.status_combo = QtWidgets.QComboBox(self)
        self.status_combo.addItems(STATUS_OPTIONS)

        self.start_edit = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime(), self)
        self.start_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_edit.setCalendarPopup(True)

        self.end_edit = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime(), self)
        self.end_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_edit.setCalendarPopup(True)

        self.content_edit = QtWidgets.QPlainTextEdit(self)
        self.content_edit.setMinimumHeight(120)

        form_layout.addRow("날짜:", self.date_edit)
        form_layout.addRow("작업 종류:", self.category_combo)
        form_layout.addRow("상태:", self.status_combo)
        form_layout.addRow("시작 시각:", self.start_edit)
        form_layout.addRow("종료 시각:", self.end_edit)
        form_layout.addRow("작업 내용:", self.content_edit)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        button_box.accepted.connect(self._handle_accept)
        button_box.rejected.connect(self.reject)

        layout.addLayout(form_layout)
        layout.addWidget(button_box)

    def _populate_fields(self) -> None:
        """기존 로그 값을 입력 위젯에 채운다."""
        date_str = self.original_log.get("date", "")
        if date_str:
            try:
                date = QtCore.QDate.fromString(date_str, "yyyy-MM-dd")
                if date.isValid():
                    self.date_edit.setDate(date)
            except ValueError:
                pass

        start_str = self.original_log.get("start_datetime")
        if start_str:
            start = QtCore.QDateTime.fromString(start_str, "yyyy-MM-dd HH:mm")
            if start.isValid():
                self.start_edit.setDateTime(start)

        end_str = self.original_log.get("end_datetime")
        if end_str:
            end = QtCore.QDateTime.fromString(end_str, "yyyy-MM-dd HH:mm")
            if end.isValid():
                self.end_edit.setDateTime(end)

        category = self.original_log.get("category", CATEGORY_OPTIONS[0])
        status = self.original_log.get("status", STATUS_OPTIONS[0])
        self.category_combo.setCurrentText(category)
        self.status_combo.setCurrentText(status)
        self.content_edit.setPlainText(self.original_log.get("content", ""))

    def _handle_accept(self) -> None:
        """저장 버튼 클릭 시 입력값을 검증하고 결과를 저장한다."""
        start_dt = self.start_edit.dateTime().toPyDateTime()
        end_dt = self.end_edit.dateTime().toPyDateTime()
        if start_dt >= end_dt:
            QtWidgets.QMessageBox.warning(self, "시간 오류", "종료 시간은 시작보다 늦어야 합니다.")
            return

        content = self.content_edit.toPlainText().strip()
        if not content:
            QtWidgets.QMessageBox.warning(self, "입력 오류", "작업 내용을 입력하세요.")
            return

        new_log: Dict[str, Any] = {
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "category": self.category_combo.currentText().strip(),
            "status": self.status_combo.currentText().strip(),
            "start_datetime": start_dt.strftime("%Y-%m-%d %H:%M"),
            "end_datetime": end_dt.strftime("%Y-%m-%d %H:%M"),
            "start_time": start_dt.strftime("%H:%M"),
            "end_time": end_dt.strftime("%H:%M"),
            "content": content,
            "timestamp": self.original_log.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "modified": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        self.result_log = new_log
        self.accept()


class LogDetailDialog(QtWidgets.QDialog):
    """로그 상세 내용을 표시하는 대화상자."""

    def __init__(self, log: Dict[str, Any], parent: Optional[QtWidgets.QWidget] = None) -> None:
        """상세보기 대화상자를 초기화한다."""
        super().__init__(parent)
        self.log = log

        self.setWindowTitle(f"작업 로그 상세보기 - {log.get('date', '')}")
        self.resize(600, 500)

        self._build_ui()

    def _build_ui(self) -> None:
        """상세보기 UI를 구성한다."""
        layout = QtWidgets.QVBoxLayout(self)

        form_layout = QtWidgets.QFormLayout()

        form_layout.addRow("날짜:", QtWidgets.QLabel(self.log.get("date", "미지정"), self))
        form_layout.addRow("작업 종류:", QtWidgets.QLabel(self.log.get("category", "미분류"), self))

        status_label = QtWidgets.QLabel(self.log.get("status", "미지정"), self)
        if self.log.get("status") == "완료":
            status_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
        else:
            status_label.setStyleSheet("color: #1e88e5; font-weight: bold;")
        form_layout.addRow("상태:", status_label)

        form_layout.addRow("작업 시간:", QtWidgets.QLabel(self._time_range_text(), self))

        form_layout.addRow("등록 시간:", QtWidgets.QLabel(self.log.get("timestamp", ""), self))
        if "modified" in self.log:
            modified_label = QtWidgets.QLabel(self.log["modified"], self)
            modified_label.setStyleSheet("color: #ef6c00;")
            form_layout.addRow("수정 시간:", modified_label)

        layout.addLayout(form_layout)

        layout.addWidget(QtWidgets.QLabel("작업 내용:", self))
        content_edit = QtWidgets.QPlainTextEdit(self)
        content_edit.setPlainText(self.log.get("content", ""))
        content_edit.setReadOnly(True)
        layout.addWidget(content_edit)

        close_button = QtWidgets.QPushButton("닫기", self)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

    def _time_range_text(self) -> str:
        """로그의 시간 범위를 문자열로 변환한다."""
        start_value = self.log.get("start_datetime")
        end_value = self.log.get("end_datetime")
        if start_value and end_value:
            start_dt = WorkLogManager._parse_datetime(start_value)
            end_dt = WorkLogManager._parse_datetime(end_value)
            if start_dt and end_dt:
                if start_dt.date() == end_dt.date():
                    return f"{start_dt.strftime('%H:%M')} ~ {end_dt.strftime('%H:%M')}"
                return (
                    f"{start_dt.strftime('%m/%d %H:%M')} ~ "
                    f"{end_dt.strftime('%m/%d %H:%M')}"
                )

        start_time = self.log.get("start_time")
        end_time = self.log.get("end_time")
        if start_time and end_time:
            return f"{start_time} ~ {end_time}"

        return "시간 정보 없음"


def create_work_log_manager(parent_widget: Optional[Any] = None) -> WorkLogManager:
    """WorkLogManager 인스턴스를 생성한다."""
    return WorkLogManager(parent_widget)


def show_work_log_window(parent_widget: Optional[Any] = None) -> WorkLogManager:
    """작업 로그 창을 즉시 띄우고 WorkLogManager를 반환한다."""
    manager = WorkLogManager(parent_widget)
    manager.show_work_log()
    return manager


if __name__ == "__main__":
    work_log_manager = WorkLogManager()
    work_log_manager.show_work_log()
