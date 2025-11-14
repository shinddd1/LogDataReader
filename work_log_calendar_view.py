"""
작업 로그 달력 뷰 모듈 (PyQt5 버전)
작업 로그를 달력 형태로 확인하기 위한 창을 제공
"""

from __future__ import annotations

import calendar
import datetime
from typing import Any, Dict, List, Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

WEEKDAY_NAMES: Tuple[str, ...] = ("월", "화", "수", "목", "금", "토", "일")


def open_work_log_calendar(parent_widget: Optional[QtWidgets.QWidget], logs: List[Dict[str, Any]]) -> None:
    """작업 로그 달력 창을 연다."""
    if not logs:
        target_parent = parent_widget if isinstance(parent_widget, QtWidgets.QWidget) else None
        QtWidgets.QMessageBox.information(target_parent, "정보", "표시할 작업 로그가 없습니다.")
        return

    target_parent = parent_widget if isinstance(parent_widget, QtWidgets.QWidget) else None
    dialog = WorkLogCalendarDialog(logs=logs, parent=target_parent)
    dialog.exec_()


class WorkLogCalendarDialog(QtWidgets.QDialog):
    """작업 로그를 달력 형식으로 보여주는 대화상자."""

    def __init__(self, logs: List[Dict[str, Any]], parent: Optional[QtWidgets.QWidget] = None) -> None:
        """대화상자를 초기화한다."""
        super().__init__(parent)
        self.logs = logs
        self.logs_by_date: Dict[datetime.date, List[Dict[str, Any]]] = {}
        self.month_counts: Dict[Tuple[int, int], int] = {}
        self._day_buttons: Dict[datetime.date, QtWidgets.QToolButton] = {}
        self._month_buttons: Dict[Tuple[int, int], QtWidgets.QToolButton] = {}

        self._prepare_logs()

        self.current_date = self._initial_date()
        self.selected_date = self.current_date
        self.view_mode = "일별"

        self.setWindowTitle("작업 로그 달력")
        self.resize(900, 700)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._build_ui()
        self._draw_calendar()
        self._update_detail_for_date(self.current_date)

    def _prepare_logs(self) -> None:
        """로그 데이터를 날짜별로 정리한다."""
        for log in self.logs:
            date_str = log.get("date")
            if not date_str:
                continue
            try:
                date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            self.logs_by_date.setdefault(date_obj, []).append(log)
            self.month_counts[(date_obj.year, date_obj.month)] = (
                self.month_counts.get((date_obj.year, date_obj.month), 0) + 1
            )

    def _initial_date(self) -> datetime.date:
        """달력 표시를 시작할 기본 날짜를 반환한다."""
        if self.logs_by_date:
            return max(self.logs_by_date.keys())
        return datetime.date.today()

    def _build_ui(self) -> None:
        """UI 위젯을 생성하고 배치한다."""
        self.main_layout = QtWidgets.QVBoxLayout(self)

        header_layout = QtWidgets.QHBoxLayout()
        self.prev_button = QtWidgets.QPushButton("◀", self)
        self.prev_button.setFixedWidth(40)
        self.next_button = QtWidgets.QPushButton("▶", self)
        self.next_button.setFixedWidth(40)

        self.month_label = QtWidgets.QLabel("", self)
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.today_button = QtWidgets.QPushButton("오늘", self)
        self.today_button.setFixedWidth(70)

        header_layout.addWidget(self.prev_button)
        header_layout.addWidget(self.month_label, stretch=1)
        header_layout.addWidget(self.next_button)
        header_layout.addWidget(self.today_button)

        view_layout = QtWidgets.QHBoxLayout()
        view_layout.addWidget(QtWidgets.QLabel("표시 단위:", self))
        self.view_mode_combo = QtWidgets.QComboBox(self)
        self.view_mode_combo.addItems(["일별", "월별"])
        view_layout.addWidget(self.view_mode_combo)
        view_layout.addStretch()

        legend_layout = QtWidgets.QHBoxLayout()
        legend_layout.addWidget(QtWidgets.QLabel("표시 안내:", self))
        legend_layout.addLayout(self._create_legend_item("로그 없음", "#f0f0f0"))
        legend_layout.addLayout(self._create_legend_item("로그 있음", "#d8f0ff"))
        legend_layout.addStretch()

        self.weekday_header_widget = QtWidgets.QWidget(self)
        weekday_layout = QtWidgets.QHBoxLayout(self.weekday_header_widget)
        weekday_layout.setContentsMargins(0, 0, 0, 0)
        for name in WEEKDAY_NAMES:
            label = QtWidgets.QLabel(name, self.weekday_header_widget)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-weight: bold;")
            weekday_layout.addWidget(label)

        self.calendar_frame = QtWidgets.QFrame(self)
        self.calendar_layout = QtWidgets.QGridLayout(self.calendar_frame)
        self.calendar_layout.setContentsMargins(0, 0, 0, 0)
        self.calendar_layout.setSpacing(4)

        detail_group = QtWidgets.QGroupBox("선택한 기간의 로그", self)
        detail_layout = QtWidgets.QVBoxLayout(detail_group)

        self.selected_period_label = QtWidgets.QLabel("", detail_group)
        self.selected_period_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        detail_layout.addWidget(self.selected_period_label)

        self.log_table = QtWidgets.QTableWidget(0, 5, detail_group)
        self.log_table.setHorizontalHeaderLabels(
            ["날짜", "카테고리", "상태", "시간", "내용 요약"],
        )
        header = self.log_table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        self.log_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.log_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        vertical_header = self.log_table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        detail_layout.addWidget(self.log_table)

        self.summary_label = QtWidgets.QLabel("선택한 기간에 등록된 로그가 없습니다.", detail_group)
        detail_layout.addWidget(self.summary_label)

        self.main_layout.addLayout(header_layout)
        self.main_layout.addLayout(view_layout)
        self.main_layout.addLayout(legend_layout)
        self.main_layout.addWidget(self.weekday_header_widget)
        self.main_layout.addWidget(self.calendar_frame, stretch=1)
        self.main_layout.addWidget(detail_group, stretch=1)

        self.prev_button.clicked.connect(self._go_previous_period)
        self.next_button.clicked.connect(self._go_next_period)
        self.today_button.clicked.connect(self._go_today)
        self.view_mode_combo.currentTextChanged.connect(self._on_view_mode_changed)

    def _create_legend_item(self, text: str, color: str) -> QtWidgets.QHBoxLayout:
        """범례 항목을 생성한다."""
        layout = QtWidgets.QHBoxLayout()
        color_label = QtWidgets.QLabel(self)
        color_label.setFixedSize(16, 16)
        color_label.setStyleSheet(f"background-color: {color}; border: 1px solid #aaaaaa;")
        layout.addWidget(color_label)
        layout.addWidget(QtWidgets.QLabel(text, self))
        return layout

    def _clear_calendar(self) -> None:
        """달력 레이아웃의 모든 위젯을 제거한다."""
        self._day_buttons.clear()
        self._month_buttons.clear()
        while self.calendar_layout.count():
            item = self.calendar_layout.takeAt(0)
            if item is None:
                continue
            item_widget = item.widget()
            if item_widget is not None:
                item_widget.setParent(None)

    def _draw_calendar(self) -> None:
        """현재 모드에 따라 달력을 그린다."""
        self._clear_calendar()
        self.view_mode = self.view_mode_combo.currentText()

        if self.view_mode == "월별":
            self.weekday_header_widget.hide()
            self._draw_month_selector()
        else:
            self.weekday_header_widget.show()
            self._draw_day_calendar()

    def _draw_day_calendar(self) -> None:
        """일별 달력 뷰를 생성한다."""
        year = self.current_date.year
        month = self.current_date.month
        self.month_label.setText(f"{year}년 {month:02d}월")

        cal = calendar.Calendar(firstweekday=0)
        for row, week in enumerate(cal.monthdatescalendar(year, month)):
            for col, day in enumerate(week):
                button = QtWidgets.QToolButton(self.calendar_frame)
                button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
                button.setCheckable(True)
                button.setAutoRaise(False)

                logs = self.logs_by_date.get(day, [])
                base_text = str(day.day)
                if logs:
                    base_text += f"\n{len(logs)}건"
                button.setText(base_text)

                if day.month == month:
                    button.setEnabled(True)
                    bg_color = "#d8f0ff" if logs else "#f0f0f0"
                else:
                    button.setEnabled(False)
                    bg_color = "#eeeeee"

                button.setStyleSheet(
                    "QToolButton {"
                    f"background-color: {bg_color};"
                    "border: 1px solid #cccccc;"
                    "padding: 6px;"
                    "}"
                    "QToolButton:checked {"
                    "border: 2px solid #1976d2;"
                    "}"
                )

                button.clicked.connect(lambda checked, d=day: self._on_day_selected(d))
                self.calendar_layout.addWidget(button, row, col)
                self._day_buttons[day] = button

        self._update_day_selection()

    def _draw_month_selector(self) -> None:
        """월별 선택 격자를 생성한다."""
        year = self.current_date.year
        self.month_label.setText(f"{year}년")

        months_per_row = 3
        for index, month in enumerate(range(1, 13)):
            row = index // months_per_row
            col = index % months_per_row
            button = QtWidgets.QToolButton(self.calendar_frame)
            button.setCheckable(True)
            button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

            count = self.month_counts.get((year, month), 0)
            text = f"{month:02d}월"
            if count:
                text += f"\n{count}건"
            button.setText(text)

            bg_color = "#d8f0ff" if count else "#f0f0f0"
            button.setStyleSheet(
                "QToolButton {"
                f"background-color: {bg_color};"
                "border: 1px solid #cccccc;"
                "padding: 12px;"
                "}"
                "QToolButton:checked {"
                "border: 2px solid #1976d2;"
                "}"
            )

            button.clicked.connect(lambda checked, y=year, m=month: self._on_month_selected(y, m))
            self.calendar_layout.addWidget(button, row, col)
            self._month_buttons[(year, month)] = button

        self._update_month_selection()

    def _on_view_mode_changed(self, mode: str) -> None:
        """표시 단위 변경 시 달력을 새로 그린다."""
        self.view_mode = mode
        if mode == "월별":
            self.selected_date = self.selected_date.replace(day=1)
        self._draw_calendar()
        self._update_detail_for_date(self.selected_date)

    def _on_day_selected(self, day: datetime.date) -> None:
        """일자를 선택했을 때 상세 정보를 갱신한다."""
        self.selected_date = day
        self.current_date = day
        self._update_day_selection()
        self._update_detail_for_date(day)

    def _on_month_selected(self, year: int, month: int) -> None:
        """월을 선택했을 때 상세 정보를 갱신한다."""
        selected = datetime.date(year, month, 1)
        self.selected_date = selected
        self.current_date = selected
        self._update_month_selection()
        self._update_detail_for_date(selected)

    def _update_day_selection(self) -> None:
        """선택된 날짜 버튼의 상태를 갱신한다."""
        for day, button in self._day_buttons.items():
            button.setChecked(day == self.selected_date)

    def _update_month_selection(self) -> None:
        """선택된 월 버튼의 상태를 갱신한다."""
        for (year, month), button in self._month_buttons.items():
            button.setChecked(
                year == self.selected_date.year and month == self.selected_date.month,
            )

    def _go_previous_period(self) -> None:
        """이전 기간으로 이동한다."""
        if self.view_mode == "월별":
            self.current_date = self.current_date.replace(year=self.current_date.year - 1)
        else:
            first_day = self.current_date.replace(day=1)
            prev_month_last = first_day - datetime.timedelta(days=1)
            self.current_date = prev_month_last
        self._draw_calendar()
        self._update_detail_for_date(self.selected_date)

    def _go_next_period(self) -> None:
        """다음 기간으로 이동한다."""
        if self.view_mode == "월별":
            self.current_date = self.current_date.replace(year=self.current_date.year + 1)
        else:
            days_in_month = calendar.monthrange(self.current_date.year, self.current_date.month)[1]
            next_month_first = self.current_date.replace(day=1) + datetime.timedelta(days=days_in_month)
            self.current_date = next_month_first
        self._draw_calendar()
        self._update_detail_for_date(self.selected_date)

    def _go_today(self) -> None:
        """오늘 날짜를 기준으로 달력을 갱신한다."""
        today = datetime.date.today()
        self.current_date = today
        self.selected_date = today
        self.view_mode_combo.setCurrentText("일별")
        self._draw_calendar()
        self._update_detail_for_date(today)

    def _update_detail_for_date(self, date_value: datetime.date) -> None:
        """선택된 기간의 로그 테이블을 갱신한다."""
        label, entries = self._collect_logs_for_period(date_value)
        self.selected_period_label.setText(label)

        self.log_table.setRowCount(0)
        if not entries:
            self.summary_label.setText("선택한 기간에 등록된 로그가 없습니다.")
            return

        for row, (log_date, log) in enumerate(entries):
            self.log_table.insertRow(row)
            row_values = [
                log_date.strftime("%Y-%m-%d"),
                log.get("category", "미분류"),
                log.get("status", "미지정"),
                self._format_time_info(log),
                self._content_summary(log.get("content", "")),
            ]
            for col, value in enumerate(row_values):
                item = QtWidgets.QTableWidgetItem(value)
                if col == 2:
                    color = QtGui.QColor("#1e88e5")
                    if value == "완료":
                        color = QtGui.QColor("#2e7d32")
                    item.setForeground(QtGui.QBrush(color))
                self.log_table.setItem(row, col, item)

        total_count = len(entries)
        unique_days = len({log_date for log_date, _ in entries})
        self.summary_label.setText(f"총 {total_count}개 로그 (대상 {unique_days}일)")
        self.log_table.resizeColumnsToContents()

    def _collect_logs_for_period(self, date_value: datetime.date) -> Tuple[str, List[Tuple[datetime.date, Dict[str, Any]]]]:
        """표시 단위에 따라 기간별 로그를 수집한다."""
        if self.view_mode == "월별":
            start = date_value.replace(day=1)
            last_day = calendar.monthrange(date_value.year, date_value.month)[1]
            days = [start + datetime.timedelta(days=i) for i in range(last_day)]
            label = f"{start.strftime('%Y-%m-%d')} ~ {(start + datetime.timedelta(days=last_day - 1)).strftime('%Y-%m-%d')} (월간)"
        else:
            days = [date_value]
            label = date_value.strftime("%Y-%m-%d (%a)")

        collected: List[Tuple[datetime.date, Dict[str, Any]]] = []
        for day in days:
            for log in self.logs_by_date.get(day, []):
                collected.append((day, log))

        collected.sort(key=lambda item: (item[0], self._log_sort_key(item[1])))
        return label, collected

    @staticmethod
    def _log_sort_key(log: Dict[str, Any]) -> Tuple[str, str]:
        """정렬을 위한 키를 반환한다."""
        return (
            log.get("start_datetime") or log.get("date", ""),
            log.get("start_time") or "",
        )

    @staticmethod
    def _format_time_info(log: Dict[str, Any]) -> str:
        """로그의 시간 정보를 문자열로 변환한다."""
        start_dt = log.get("start_datetime")
        end_dt = log.get("end_datetime")
        if start_dt and end_dt:
            return f"{start_dt} ~ {end_dt}"

        start_time = log.get("start_time")
        end_time = log.get("end_time")
        if start_time and end_time:
            return f"{start_time} ~ {end_time}"

        return "시간 미기록"

    @staticmethod
    def _content_summary(content: str, limit: int = 60) -> str:
        """로그 내용의 요약 문자열을 생성한다."""
        clean = content.strip().replace("\n", " ")
        if len(clean) <= limit:
            return clean or "내용 없음"
        return f"{clean[:limit - 3]}..."


if __name__ == "__main__":
    sample_logs = [
        {
            "date": "2025-03-12",
            "category": "CNT 장착",
            "status": "완료",
            "start_datetime": "2025-03-12 09:30",
            "end_datetime": "2025-03-12 10:45",
            "start_time": "09:30",
            "end_time": "10:45",
            "content": "샘플 로그 내용",
        }
    ]
    app = QtWidgets.QApplication([])
    dialog = WorkLogCalendarDialog(sample_logs)
    dialog.exec_()
