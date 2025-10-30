"""
작업 로그 관리 모듈
작업 로그 입력, 저장, 로드, 내보내기 기능을 제공
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import json
import os
import pandas as pd


class WorkLogManager:
    """작업 로그 관리 클래스"""
    
    def __init__(self, parent_root=None):
        """
        초기화
        Args:
            parent_root: 부모 tkinter root 윈도우
        """
        self.parent_root = parent_root
        self.log_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "work_log.json"
        )
        
        # 초기화 시 로그 파일 상태 출력
        print(f"작업 로그 파일: {self.log_file_path}")
        if os.path.exists(self.log_file_path):
            logs = self.load_work_logs()
            print(f"기존 로그 {len(logs)}개 로드됨")
        else:
            print("새 작업 로그 파일이 생성됩니다.")
    
    def load_work_logs(self):
        """기존 작업 로그를 JSON 파일에서 로드"""
        if os.path.exists(self.log_file_path):
            try:
                with open(self.log_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"로그 파일 읽기 오류: {e}")
                return []
        return []
    
    def save_work_logs(self, logs):
        """작업 로그를 JSON 파일에 저장"""
        try:
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"로그 파일 저장 오류: {e}")
            return False
    
    def show_work_log(self):
        """작업 로그 입력/관리 창 표시"""
        if not self.parent_root:
            print("부모 윈도우가 설정되지 않았습니다.")
            return
            
        log_win = tk.Toplevel(self.parent_root)
        log_win.title("작업 로그 관리")
        log_win.geometry("1200x800")
        log_win.transient(self.parent_root)
        
        # 메인 프레임
        main_frame = ttk.Frame(log_win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 상단: 새 로그 입력 섹션
        input_frame = ttk.LabelFrame(main_frame, text="새 작업 로그 입력", padding=10)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 날짜 입력 UI 생성
        date_vars = self._create_date_input(input_frame)
        
        # 카테고리 및 상태 선택 UI 생성
        category_vars = self._create_category_input(input_frame)
        
        # 시간 입력 UI 생성
        time_vars = self._create_time_input(input_frame)
        
        # 상태 변경 시 라벨 업데이트 함수
        def on_status_change(*args):
            status = category_vars['status'].get()
            if status == "완료":
                time_vars['end_label'].config(text="완료 시각:")
            else:
                time_vars['end_label'].config(text="예상 종료:")
        
        category_vars['status'].trace('w', on_status_change)
        
        # 작업 내용 입력 UI 생성
        content_text = self._create_content_input(input_frame)
        
        # 하단: 기존 로그 목록 표시
        log_tree = self._create_log_list(main_frame)
        
        # 로그 새로고침 함수
        def refresh_log_list():
            self._refresh_log_list(log_tree, stats_label)
        
        # 로그 추가 함수
        def add_log():
            self._add_log(date_vars, category_vars, time_vars, content_text, log_win, refresh_log_list)
        
        # 로그 삭제 함수  
        def delete_selected_log():
            self._delete_selected_log(log_tree, log_win, refresh_log_list)
        
        # 로그 수정 함수
        def edit_selected_log():
            self._edit_selected_log(log_tree, log_win, refresh_log_list)
        
        # 로그 내보내기 함수
        def export_logs():
            self._export_logs(log_win)
        
        # 입력 버튼 생성
        self._create_input_buttons(input_frame, add_log, content_text)
        
        # 하단 버튼 생성 및 stats_label 받기
        stats_label = self._create_bottom_buttons(self._current_log_list_frame, refresh_log_list, delete_selected_log, edit_selected_log, export_logs)
        
        # 로그 상세보기 이벤트 바인딩
        log_tree.bind('<Double-1>', lambda e: self._show_log_detail(e, log_tree, log_win))
        
        # 초기 로그 목록 로드
        refresh_log_list()
        
        # 엔터키로 로그 추가
        content_text.bind('<Control-Return>', lambda e: add_log())
        
        # 창 포커스
        log_win.focus_set()
        content_text.focus()
    
    def _create_date_input(self, parent_frame):
        """날짜 입력 UI 생성"""
        date_frame = ttk.Frame(parent_frame)
        date_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(date_frame, text="날짜:", width=10).pack(side=tk.LEFT)
        
        # 오늘 날짜를 기본값으로
        today = datetime.datetime.now()
        
        year_var = tk.StringVar(value=str(today.year))
        month_var = tk.StringVar(value=f"{today.month:02d}")
        day_var = tk.StringVar(value=f"{today.day:02d}")
        
        year_spinbox = tk.Spinbox(date_frame, from_=2020, to=2030, width=6, textvariable=year_var)
        year_spinbox.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(date_frame, text="년").pack(side=tk.LEFT, padx=(0, 10))
        
        month_spinbox = tk.Spinbox(date_frame, from_=1, to=12, width=4, textvariable=month_var, format="%02.0f")
        month_spinbox.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(date_frame, text="월").pack(side=tk.LEFT, padx=(0, 10))
        
        day_spinbox = tk.Spinbox(date_frame, from_=1, to=31, width=4, textvariable=day_var, format="%02.0f")
        day_spinbox.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(date_frame, text="일").pack(side=tk.LEFT, padx=(0, 10))
        
        # 현재 시간을 기본값으로 하는 버튼
        def set_today():
            now = datetime.datetime.now()
            year_var.set(str(now.year))
            month_var.set(f"{now.month:02d}")
            day_var.set(f"{now.day:02d}")
        
        today_btn = ttk.Button(date_frame, text="오늘", command=set_today, width=8)
        today_btn.pack(side=tk.LEFT, padx=(20, 0))
        
        return {'year': year_var, 'month': month_var, 'day': day_var}
    
    def _create_time_input(self, parent_frame):
        """시작/종료 시간 입력 UI 생성 (날짜 포함)"""
        time_frame = ttk.LabelFrame(parent_frame, text="작업 시간", padding=5)
        time_frame.pack(fill=tk.X, pady=(5, 5))
        
        # 시작 시간
        start_frame = ttk.Frame(time_frame)
        start_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(start_frame, text="시작:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        start_datetime_frame = ttk.Frame(start_frame)
        start_datetime_frame.pack(fill=tk.X, pady=(2, 0))
        
        # 시작 날짜
        ttk.Label(start_datetime_frame, text="날짜:", width=8).grid(row=0, column=0, sticky='w', padx=(0, 5))
        
        now = datetime.datetime.now()
        start_year_var = tk.StringVar(value=str(now.year))
        start_month_var = tk.StringVar(value=f"{now.month:02d}")
        start_day_var = tk.StringVar(value=f"{now.day:02d}")
        
        start_year_spin = tk.Spinbox(start_datetime_frame, from_=2020, to=2030, width=6, textvariable=start_year_var)
        start_year_spin.grid(row=0, column=1, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="년").grid(row=0, column=2, padx=(0, 8))
        
        start_month_spin = tk.Spinbox(start_datetime_frame, from_=1, to=12, width=4, textvariable=start_month_var, format="%02.0f")
        start_month_spin.grid(row=0, column=3, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="월").grid(row=0, column=4, padx=(0, 8))
        
        start_day_spin = tk.Spinbox(start_datetime_frame, from_=1, to=31, width=4, textvariable=start_day_var, format="%02.0f")
        start_day_spin.grid(row=0, column=5, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="일").grid(row=0, column=6, padx=(0, 15))
        
        # 시작 시간
        ttk.Label(start_datetime_frame, text="시각:", width=8).grid(row=0, column=7, sticky='w', padx=(0, 5))
        
        start_hour_var = tk.StringVar(value=f"{now.hour:02d}")
        start_min_var = tk.StringVar(value=f"{now.minute:02d}")
        
        start_hour_spin = tk.Spinbox(start_datetime_frame, from_=0, to=23, width=4, textvariable=start_hour_var, format="%02.0f")
        start_hour_spin.grid(row=0, column=8, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="시").grid(row=0, column=9, padx=(0, 8))
        
        start_min_spin = tk.Spinbox(start_datetime_frame, from_=0, to=59, width=4, textvariable=start_min_var, format="%02.0f")
        start_min_spin.grid(row=0, column=10, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="분").grid(row=0, column=11, padx=(0, 10))
        
        def set_current_datetime():
            current = datetime.datetime.now()
            start_year_var.set(str(current.year))
            start_month_var.set(f"{current.month:02d}")
            start_day_var.set(f"{current.day:02d}")
            start_hour_var.set(f"{current.hour:02d}")
            start_min_var.set(f"{current.minute:02d}")
        
        current_btn = ttk.Button(start_datetime_frame, text="현재", command=set_current_datetime, width=6)
        current_btn.grid(row=0, column=12, padx=(10, 0))
        
        # 종료/예상종료 시간
        end_frame = ttk.Frame(time_frame)
        end_frame.pack(fill=tk.X, pady=(10, 0))
        
        end_label = ttk.Label(end_frame, text="예상 종료:", font=('Arial', 10, 'bold'))
        end_label.pack(anchor=tk.W)
        
        end_datetime_frame = ttk.Frame(end_frame)
        end_datetime_frame.pack(fill=tk.X, pady=(2, 0))
        
        # 종료 날짜
        ttk.Label(end_datetime_frame, text="날짜:", width=8).grid(row=0, column=0, sticky='w', padx=(0, 5))
        
        # 기본적으로 시작 날짜와 동일하게 설정 (하루 후로 설정할 수도 있음)
        end_year_var = tk.StringVar(value=str(now.year))
        end_month_var = tk.StringVar(value=f"{now.month:02d}")
        end_day_var = tk.StringVar(value=f"{now.day:02d}")
        
        end_year_spin = tk.Spinbox(end_datetime_frame, from_=2020, to=2030, width=6, textvariable=end_year_var)
        end_year_spin.grid(row=0, column=1, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="년").grid(row=0, column=2, padx=(0, 8))
        
        end_month_spin = tk.Spinbox(end_datetime_frame, from_=1, to=12, width=4, textvariable=end_month_var, format="%02.0f")
        end_month_spin.grid(row=0, column=3, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="월").grid(row=0, column=4, padx=(0, 8))
        
        end_day_spin = tk.Spinbox(end_datetime_frame, from_=1, to=31, width=4, textvariable=end_day_var, format="%02.0f")
        end_day_spin.grid(row=0, column=5, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="일").grid(row=0, column=6, padx=(0, 15))
        
        # 종료 시간
        ttk.Label(end_datetime_frame, text="시각:", width=8).grid(row=0, column=7, sticky='w', padx=(0, 5))
        
        end_hour_var = tk.StringVar(value=f"{(now.hour + 1) % 24:02d}")
        end_min_var = tk.StringVar(value=f"{now.minute:02d}")
        
        end_hour_spin = tk.Spinbox(end_datetime_frame, from_=0, to=23, width=4, textvariable=end_hour_var, format="%02.0f")
        end_hour_spin.grid(row=0, column=8, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="시").grid(row=0, column=9, padx=(0, 8))
        
        end_min_spin = tk.Spinbox(end_datetime_frame, from_=0, to=59, width=4, textvariable=end_min_var, format="%02.0f")
        end_min_spin.grid(row=0, column=10, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="분").grid(row=0, column=11, padx=(0, 10))
        
        # 편의 버튼들
        convenience_frame = ttk.Frame(end_datetime_frame)
        convenience_frame.grid(row=0, column=12, padx=(10, 0))
        
        def set_same_day():
            """시작 날짜와 같은 날로 설정"""
            end_year_var.set(start_year_var.get())
            end_month_var.set(start_month_var.get())
            end_day_var.set(start_day_var.get())
        
        def set_next_day():
            """다음 날로 설정"""
            try:
                start_date = datetime.datetime(
                    int(start_year_var.get()),
                    int(start_month_var.get()),
                    int(start_day_var.get())
                )
                next_date = start_date + datetime.timedelta(days=1)
                end_year_var.set(str(next_date.year))
                end_month_var.set(f"{next_date.month:02d}")
                end_day_var.set(f"{next_date.day:02d}")
            except ValueError:
                pass  # 잘못된 날짜인 경우 무시
        
        same_day_btn = ttk.Button(convenience_frame, text="당일", command=set_same_day, width=6)
        same_day_btn.pack(side=tk.TOP, pady=(0, 2))
        
        next_day_btn = ttk.Button(convenience_frame, text="다음날", command=set_next_day, width=6)
        next_day_btn.pack(side=tk.TOP)
        
        return {
            'start_year': start_year_var, 'start_month': start_month_var, 'start_day': start_day_var,
            'start_hour': start_hour_var, 'start_min': start_min_var,
            'end_year': end_year_var, 'end_month': end_month_var, 'end_day': end_day_var,
            'end_hour': end_hour_var, 'end_min': end_min_var,
            'end_label': end_label
        }

    def _create_time_input_for_edit(self, parent_frame, log_data):
        """수정용 시간 입력 UI 생성 (날짜 포함)"""
        time_frame = ttk.LabelFrame(parent_frame, text="작업 시간", padding=5)
        time_frame.pack(fill=tk.X, pady=(5, 5))
        
        # 기존 데이터에서 날짜/시간 파싱
        start_datetime_str = log_data.get('start_datetime', '')
        end_datetime_str = log_data.get('end_datetime', '')
        
        # 기존 데이터 호환성 처리
        if not start_datetime_str and 'start_time' in log_data:
            # 기존 형식: 날짜는 로그 날짜, 시간만 별도
            start_datetime_str = f"{log_data['date']} {log_data['start_time']}"
        if not end_datetime_str and 'end_time' in log_data:
            end_datetime_str = f"{log_data['date']} {log_data['end_time']}"
        
        # 기본값 설정
        try:
            start_dt = datetime.datetime.strptime(start_datetime_str, "%Y-%m-%d %H:%M")
        except:
            start_dt = datetime.datetime.now()
        
        try:
            end_dt = datetime.datetime.strptime(end_datetime_str, "%Y-%m-%d %H:%M")
        except:
            end_dt = start_dt + datetime.timedelta(hours=1)
        
        # 시작 시간
        start_frame = ttk.Frame(time_frame)
        start_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(start_frame, text="시작:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        start_datetime_frame = ttk.Frame(start_frame)
        start_datetime_frame.pack(fill=tk.X, pady=(2, 0))
        
        # 시작 날짜
        ttk.Label(start_datetime_frame, text="날짜:", width=8).grid(row=0, column=0, sticky='w', padx=(0, 5))
        
        now = datetime.datetime.now()
        start_year_var = tk.StringVar(value=str(now.year))
        start_month_var = tk.StringVar(value=f"{now.month:02d}")
        start_day_var = tk.StringVar(value=f"{now.day:02d}")
        
        start_year_spin = tk.Spinbox(start_datetime_frame, from_=2020, to=2030, width=6, textvariable=start_year_var)
        start_year_spin.grid(row=0, column=1, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="년").grid(row=0, column=2, padx=(0, 8))
        
        start_month_spin = tk.Spinbox(start_datetime_frame, from_=1, to=12, width=4, textvariable=start_month_var, format="%02.0f")
        start_month_spin.grid(row=0, column=3, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="월").grid(row=0, column=4, padx=(0, 8))
        
        start_day_spin = tk.Spinbox(start_datetime_frame, from_=1, to=31, width=4, textvariable=start_day_var, format="%02.0f")
        start_day_spin.grid(row=0, column=5, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="일").grid(row=0, column=6, padx=(0, 15))
        
        # 시작 시간
        ttk.Label(start_datetime_frame, text="시각:", width=8).grid(row=0, column=7, sticky='w', padx=(0, 5))
        
        start_hour_var = tk.StringVar(value=f"{start_dt.hour:02d}")
        start_min_var = tk.StringVar(value=f"{start_dt.minute:02d}")
        
        start_hour_spin = tk.Spinbox(start_datetime_frame, from_=0, to=23, width=4, textvariable=start_hour_var, format="%02.0f")
        start_hour_spin.grid(row=0, column=8, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="시").grid(row=0, column=9, padx=(0, 8))
        
        start_min_spin = tk.Spinbox(start_datetime_frame, from_=0, to=59, width=4, textvariable=start_min_var, format="%02.0f")
        start_min_spin.grid(row=0, column=10, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="분").grid(row=0, column=11)
        
        # 종료 시간
        end_frame = ttk.Frame(time_frame)
        end_frame.pack(fill=tk.X, pady=(10, 0))
        
        status = log_data.get('status', '진행중')
        end_label_text = "완료:" if status == "완료" else "예상 종료:"
        end_label = ttk.Label(end_frame, text=end_label_text, font=('Arial', 10, 'bold'))
        end_label.pack(anchor=tk.W)
        
        end_datetime_frame = ttk.Frame(end_frame)
        end_datetime_frame.pack(fill=tk.X, pady=(2, 0))
        
        # 종료 날짜
        ttk.Label(end_datetime_frame, text="날짜:", width=8).grid(row=0, column=0, sticky='w', padx=(0, 5))
        
        end_year_var = tk.StringVar(value=str(end_dt.year))
        end_month_var = tk.StringVar(value=f"{end_dt.month:02d}")
        end_day_var = tk.StringVar(value=f"{end_dt.day:02d}")
        
        end_year_spin = tk.Spinbox(end_datetime_frame, from_=2020, to=2030, width=6, textvariable=end_year_var)
        end_year_spin.grid(row=0, column=1, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="년").grid(row=0, column=2, padx=(0, 8))
        
        end_month_spin = tk.Spinbox(end_datetime_frame, from_=1, to=12, width=4, textvariable=end_month_var, format="%02.0f")
        end_month_spin.grid(row=0, column=3, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="월").grid(row=0, column=4, padx=(0, 8))
        
        end_day_spin = tk.Spinbox(end_datetime_frame, from_=1, to=31, width=4, textvariable=end_day_var, format="%02.0f")
        end_day_spin.grid(row=0, column=5, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="일").grid(row=0, column=6, padx=(0, 15))
        
        # 종료 시간
        ttk.Label(end_datetime_frame, text="시각:", width=8).grid(row=0, column=7, sticky='w', padx=(0, 5))
        
        end_hour_var = tk.StringVar(value=f"{end_dt.hour:02d}")
        end_min_var = tk.StringVar(value=f"{end_dt.minute:02d}")
        
        end_hour_spin = tk.Spinbox(end_datetime_frame, from_=0, to=23, width=4, textvariable=end_hour_var, format="%02.0f")
        end_hour_spin.grid(row=0, column=8, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="시").grid(row=0, column=9, padx=(0, 8))
        
        end_min_spin = tk.Spinbox(end_datetime_frame, from_=0, to=59, width=4, textvariable=end_min_var, format="%02.0f")
        end_min_spin.grid(row=0, column=10, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="분").grid(row=0, column=11)
        
        # 편의 버튼들
        convenience_frame = ttk.Frame(end_datetime_frame)
        convenience_frame.grid(row=0, column=12, padx=(10, 0))
        
        def set_same_day():
            """시작 날짜와 같은 날로 설정"""
            end_year_var.set(start_year_var.get())
            end_month_var.set(start_month_var.get())
            end_day_var.set(start_day_var.get())
        
        def set_next_day():
            """다음 날로 설정"""
            try:
                start_date = datetime.datetime(
                    int(start_year_var.get()),
                    int(start_month_var.get()),
                    int(start_day_var.get())
                )
                next_date = start_date + datetime.timedelta(days=1)
                end_year_var.set(str(next_date.year))
                end_month_var.set(f"{next_date.month:02d}")
                end_day_var.set(f"{next_date.day:02d}")
            except ValueError:
                pass  # 잘못된 날짜인 경우 무시
        
        same_day_btn = ttk.Button(convenience_frame, text="당일", command=set_same_day, width=6)
        same_day_btn.pack(side=tk.TOP, pady=(0, 2))
        
        next_day_btn = ttk.Button(convenience_frame, text="다음날", command=set_next_day, width=6)
        next_day_btn.pack(side=tk.TOP)
        
        return {
            'start_year': start_year_var, 'start_month': start_month_var, 'start_day': start_day_var,
            'start_hour': start_hour_var, 'start_min': start_min_var,
            'end_year': end_year_var, 'end_month': end_month_var, 'end_day': end_day_var,
            'end_hour': end_hour_var, 'end_min': end_min_var,
            'end_label': end_label
        }

    def _create_category_input(self, parent_frame):
        """카테고리 및 상태 선택 UI 생성"""
        category_frame = ttk.Frame(parent_frame)
        category_frame.pack(fill=tk.X, pady=(5, 5))

        # 작업 종류 카테고리
        ttk.Label(category_frame, text="작업 종류:", width=10).pack(side=tk.LEFT)
        
        category_var = tk.StringVar()
        categories = ["Li-Ag 충전", "IR Align", "EUV Align", "기타 장비 점검"]
        category_combo = ttk.Combobox(category_frame, textvariable=category_var, values=categories, width=15)
        category_combo.pack(side=tk.LEFT, padx=(0, 20))
        category_combo.current(0)  # 기본값 설정
        
        # 작업 상태
        ttk.Label(category_frame, text="상태:", width=8).pack(side=tk.LEFT)
        
        status_var = tk.StringVar()
        statuses = ["진행중", "완료"]
        status_combo = ttk.Combobox(category_frame, textvariable=status_var, values=statuses, width=10)
        status_combo.pack(side=tk.LEFT)
        status_combo.current(0)  # 기본값: 진행중
        
        return {'category': category_var, 'status': status_var}
    
    def _create_content_input(self, parent_frame):
        """작업 내용 입력 UI 생성"""
        content_frame = ttk.Frame(parent_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        
        ttk.Label(content_frame, text="작업 내용:").pack(anchor=tk.W)
        
        content_text_frame = ttk.Frame(content_frame)
        content_text_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        content_text = tk.Text(content_text_frame, height=4, wrap=tk.WORD, font=('Arial', 10))
        content_scrollbar = ttk.Scrollbar(content_text_frame, orient="vertical", command=content_text.yview)
        content_text.configure(yscrollcommand=content_scrollbar.set)
        
        content_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        return content_text
    
    def _create_content_input_for_edit(self, parent_frame, log_data):
        """수정용 작업 내용 입력 UI 생성"""
        content_frame = ttk.Frame(parent_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        
        ttk.Label(content_frame, text="작업 내용:").pack(anchor=tk.W)
        
        content_text_frame = ttk.Frame(content_frame)
        content_text_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        content_text = tk.Text(content_text_frame, height=6, wrap=tk.WORD, font=('Arial', 10))
        content_scrollbar = ttk.Scrollbar(content_text_frame, orient="vertical", command=content_text.yview)
        content_text.configure(yscrollcommand=content_scrollbar.set)
        
        # 기존 내용 입력
        content_text.insert(tk.END, log_data.get('content', ''))
        
        content_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        return content_text
    
    def _create_input_buttons(self, parent_frame, add_log_func, content_text):
        """입력 버튼 생성"""
        input_btn_frame = ttk.Frame(parent_frame)
        input_btn_frame.pack(fill=tk.X)
        
        add_btn = ttk.Button(input_btn_frame, text="로그 추가", command=add_log_func)
        add_btn.pack(side=tk.RIGHT)
        
        clear_btn = ttk.Button(input_btn_frame, text="입력 초기화", 
                              command=lambda: content_text.delete("1.0", tk.END))
        clear_btn.pack(side=tk.RIGHT, padx=(0, 5))
    
    def _create_log_list(self, parent_frame):
        """로그 목록 UI 생성"""
        log_list_frame = ttk.LabelFrame(parent_frame, text="작업 로그 이력", padding=10)
        log_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 로그 목록 Treeview
        log_columns = ('날짜', '작업 종류', '상태', '작업시간', '작업내용', '등록시간')
        log_tree = ttk.Treeview(log_list_frame, columns=log_columns, show='headings', height=15)
        
        # 컬럼 설정
        log_tree.heading('날짜', text='날짜')
        log_tree.heading('작업 종류', text='작업 종류')
        log_tree.heading('상태', text='상태')
        log_tree.heading('작업시간', text='작업시간')
        log_tree.heading('작업내용', text='작업 내용')
        log_tree.heading('등록시간', text='등록 시간')
        
        log_tree.column('날짜', width=100)
        log_tree.column('작업 종류', width=100)
        log_tree.column('상태', width=70)
        log_tree.column('작업시간', width=120)
        log_tree.column('작업내용', width=300)
        log_tree.column('등록시간', width=150)
        
        # 스크롤바
        log_v_scrollbar = ttk.Scrollbar(log_list_frame, orient="vertical", command=log_tree.yview)
        log_h_scrollbar = ttk.Scrollbar(log_list_frame, orient="horizontal", command=log_tree.xview)
        log_tree.configure(yscrollcommand=log_v_scrollbar.set, xscrollcommand=log_h_scrollbar.set)
        
        # 그리드 배치
        log_tree.grid(row=0, column=0, sticky='nsew')
        log_v_scrollbar.grid(row=0, column=1, sticky='ns')
        log_h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        log_list_frame.grid_rowconfigure(0, weight=1)
        log_list_frame.grid_columnconfigure(0, weight=1)
        
        # log_list_frame을 나중에 사용하기 위해 저장
        self._current_log_list_frame = log_list_frame
        
        return log_tree
    
    def _create_bottom_buttons(self, log_list_frame, refresh_func, delete_func, edit_func, export_func):
        """하단 버튼들 생성"""
        bottom_frame = ttk.Frame(log_list_frame)
        bottom_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        
        stats_label = ttk.Label(bottom_frame, text="", font=('Arial', 9))
        stats_label.pack(side=tk.LEFT)
        
        # 버튼들
        export_btn = ttk.Button(bottom_frame, text="로그 내보내기", command=export_func)
        export_btn.pack(side=tk.RIGHT)
        
        edit_btn = ttk.Button(bottom_frame, text="선택 로그 수정", command=edit_func)
        edit_btn.pack(side=tk.RIGHT, padx=(0, 5))
        
        delete_btn = ttk.Button(bottom_frame, text="선택 로그 삭제", command=delete_func)
        delete_btn.pack(side=tk.RIGHT, padx=(0, 5))
        
        refresh_btn = ttk.Button(bottom_frame, text="새로고침", command=refresh_func)
        refresh_btn.pack(side=tk.RIGHT, padx=(0, 5))
        
        return stats_label
    
    def _add_log(self, date_vars, category_vars, time_vars, content_text, parent_win, refresh_func):
        """로그 추가"""
        try:
            # 입력 검증
            date_str = f"{date_vars['year'].get()}-{date_vars['month'].get()}-{date_vars['day'].get()}"
            category = category_vars['category'].get().strip()
            status = category_vars['status'].get().strip()
            content = content_text.get("1.0", tk.END).strip()
            
            # 시작/종료 날짜+시간 정보
            start_date = f"{time_vars['start_year'].get()}-{time_vars['start_month'].get()}-{time_vars['start_day'].get()}"
            start_time = f"{time_vars['start_hour'].get()}:{time_vars['start_min'].get()}"
            start_datetime = f"{start_date} {start_time}"
            
            end_date = f"{time_vars['end_year'].get()}-{time_vars['end_month'].get()}-{time_vars['end_day'].get()}"
            end_time = f"{time_vars['end_hour'].get()}:{time_vars['end_min'].get()}"
            end_datetime = f"{end_date} {end_time}"
            
            if not category:
                messagebox.showwarning("입력 오류", "장비 카테고리를 선택하세요.", parent=parent_win)
                return
            
            if not status:
                messagebox.showwarning("입력 오류", "작업 상태를 선택하세요.", parent=parent_win)
                return
            
            if not content:
                messagebox.showwarning("입력 오류", "작업 내용을 입력하세요.", parent=parent_win)
                content_text.focus()
                return
            
            # 날짜 유효성 검증
            try:
                datetime.datetime.strptime(date_str, "%Y-%m-%d")
                datetime.datetime.strptime(start_datetime, "%Y-%m-%d %H:%M")
                datetime.datetime.strptime(end_datetime, "%Y-%m-%d %H:%M")
            except ValueError:
                messagebox.showerror("날짜/시간 오류", "올바른 날짜와 시간을 입력하세요.", parent=parent_win)
                return
            
            # 시작 시간이 종료 시간보다 늦은지 확인
            start_dt = datetime.datetime.strptime(start_datetime, "%Y-%m-%d %H:%M")
            end_dt = datetime.datetime.strptime(end_datetime, "%Y-%m-%d %H:%M")
            
            if start_dt >= end_dt:
                messagebox.showwarning("시간 오류", "종료 시간은 시작 시간보다 늦어야 합니다.", parent=parent_win)
                return
            
            # 새 로그 항목 생성 (기존 호환성을 위해 기존 필드도 유지)
            new_log = {
                "date": date_str,
                "category": category,
                "status": status,
                "start_datetime": start_datetime,  # 새 필드
                "end_datetime": end_datetime,      # 새 필드
                "start_time": start_time,          # 기존 호환성
                "end_time": end_time,              # 기존 호환성
                "content": content,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 기존 로그 로드 후 추가
            logs = self.load_work_logs()
            logs.append(new_log)
            
            # 날짜순으로 정렬 (최신이 위로)
            logs.sort(key=lambda x: x["date"], reverse=True)
            
            # 저장
            if self.save_work_logs(logs):
                messagebox.showinfo("저장 완료", "작업 로그가 저장되었습니다.", parent=parent_win)
                
                # 입력 필드 초기화
                content_text.delete("1.0", tk.END)
                
                # 로그 목록 새로고침
                refresh_func()
            else:
                messagebox.showerror("저장 실패", "로그 저장에 실패했습니다.", parent=parent_win)
                
        except Exception as e:
            messagebox.showerror("오류", f"로그 추가 중 오류가 발생했습니다:\n{e}", parent=parent_win)
    
    def _refresh_log_list(self, log_tree, stats_label):
        """로그 목록을 새로고침"""
        # 기존 항목 삭제
        for item in log_tree.get_children():
            log_tree.delete(item)
        
        # 로그 로드 및 표시
        logs = self.load_work_logs()
        for log in logs:
            # 작업 내용이 너무 길면 줄여서 표시
            content_preview = log['content'][:80] + ('...' if len(log['content']) > 80 else '')
            
            # 시간 정보 처리 (새 형식 우선, 기존 형식 호환)
            if 'start_datetime' in log and 'end_datetime' in log:
                status = log.get('status', '미지정')
                try:
                    start_dt = datetime.datetime.strptime(log['start_datetime'], "%Y-%m-%d %H:%M")
                    end_dt = datetime.datetime.strptime(log['end_datetime'], "%Y-%m-%d %H:%M")
                    
                    # 같은 날이면 시간만, 다른 날이면 날짜+시간
                    if start_dt.date() == end_dt.date():
                        time_info = f"{start_dt.strftime('%H:%M')} ~ {end_dt.strftime('%H:%M')}"
                    else:
                        time_info = f"{start_dt.strftime('%m/%d %H:%M')} ~ {end_dt.strftime('%m/%d %H:%M')}"
                    
                    if status == "진행중":
                        time_info += " (예상)"
                        
                except ValueError:
                    time_info = "시간 형식 오류"
                    
            elif 'start_time' in log and 'end_time' in log:
                # 기존 형식 호환
                status = log.get('status', '미지정')
                if status == "완료":
                    time_info = f"{log['start_time']} ~ {log['end_time']}"
                else:
                    time_info = f"{log['start_time']} ~ {log['end_time']} (예상)"
            else:
                time_info = "시간 미기록"
            
            log_tree.insert('', tk.END, values=(
                log['date'],
                log.get('category', '미분류'),
                log.get('status', '미지정'),
                time_info,
                content_preview,
                log['timestamp']
            ))
        
        # 통계 정보 업데이트
        total_logs = len(logs)
        if total_logs > 0:
            latest_date = logs[0]['date']  # 이미 날짜순 정렬됨
            
            # 상태별 통계
            in_progress = sum(1 for log in logs if log.get('status') == '진행중')
            completed = sum(1 for log in logs if log.get('status') == '완료')
            
            stats_text = f"총 {total_logs}개 로그 (진행중: {in_progress}, 완료: {completed}), 최근: {latest_date}"
        else:
            stats_text = "등록된 로그가 없습니다."
        
        stats_label.config(text=stats_text)
    
    def _delete_selected_log(self, log_tree, parent_win, refresh_func):
        """선택된 로그 삭제"""
        selection = log_tree.selection()
        if not selection:
            messagebox.showwarning("선택 오류", "삭제할 로그를 선택하세요.", parent=parent_win)
            return
        
        if not messagebox.askyesno("삭제 확인", "선택된 로그를 삭제하시겠습니까?", parent=parent_win):
            return
        
        try:
            # 선택된 로그 정보 가져오기
            item = log_tree.item(selection[0])
            values = item['values']
            
            logs = self.load_work_logs()
            # 해당 로그를 찾아서 삭제
            for i, log in enumerate(logs):
                if (log['date'] == values[0] and 
                    log.get('category', '미분류') == values[1] and
                    log['timestamp'] == values[5]):
                    logs.pop(i)
                    break
            
            if self.save_work_logs(logs):
                messagebox.showinfo("삭제 완료", "로그가 삭제되었습니다.", parent=parent_win)
                refresh_func()
            else:
                messagebox.showerror("삭제 실패", "로그 삭제에 실패했습니다.", parent=parent_win)
                
        except Exception as e:
            messagebox.showerror("오류", f"로그 삭제 중 오류가 발생했습니다:\n{e}", parent=parent_win)
    
    def _edit_selected_log(self, log_tree, parent_win, refresh_func):
        """선택된 로그 수정"""
        selection = log_tree.selection()
        if not selection:
            messagebox.showwarning("선택 오류", "수정할 로그를 선택하세요.", parent=parent_win)
            return
        
        try:
            # 선택된 로그 정보 가져오기
            item = log_tree.item(selection[0])
            values = item['values']
            
            logs = self.load_work_logs()
            selected_log = None
            selected_index = None
            
            for i, log in enumerate(logs):
                if (log['date'] == values[0] and 
                    log.get('category', '미분류') == values[1] and
                    log['timestamp'] == values[5]):
                    selected_log = log
                    selected_index = i
                    break
            
            if not selected_log:
                messagebox.showerror("오류", "해당 로그를 찾을 수 없습니다.", parent=parent_win)
                return
            
            # 수정 창 생성
            self._show_edit_window(selected_log, selected_index, parent_win, refresh_func)
            
        except Exception as e:
            messagebox.showerror("오류", f"로그 수정 중 오류가 발생했습니다:\n{e}", parent=parent_win)
    
    def _show_edit_window(self, log_data, log_index, parent_win, refresh_func):
        """로그 수정 창 표시"""
        edit_win = tk.Toplevel(parent_win)
        edit_win.title(f"작업 로그 수정 - {log_data['date']}")
        edit_win.geometry("800x700")
        edit_win.transient(parent_win)
        edit_win.grab_set()  # 모달 창으로 설정
        
        # 메인 프레임
        main_frame = ttk.Frame(edit_win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 제목
        title_label = ttk.Label(main_frame, text="작업 로그 수정", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # 입력 프레임
        input_frame = ttk.LabelFrame(main_frame, text="로그 정보 수정", padding=10)
        input_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 날짜 입력 UI 생성
        date_vars = self._create_date_input_for_edit(input_frame, log_data)
        
        # 카테고리 및 상태 선택 UI 생성
        category_vars = self._create_category_input_for_edit(input_frame, log_data)
        
        # 시간 입력 UI 생성
        time_vars = self._create_time_input_for_edit(input_frame, log_data)
        
        # 상태 변경 시 라벨 업데이트 함수
        def on_status_change(*args):
            status = category_vars['status'].get()
            if status == "완료":
                time_vars['end_label'].config(text="완료 시각:")
            else:
                time_vars['end_label'].config(text="예상 종료:")
        
        category_vars['status'].trace('w', on_status_change)
        
        # 작업 내용 입력 UI 생성
        content_text = self._create_content_input_for_edit(input_frame, log_data)
        
        # 버튼 프레임
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # 수정 완료 함수
        def save_changes():
            self._save_log_changes(log_index, date_vars, category_vars, time_vars, content_text, edit_win, refresh_func)
        
        # 버튼들
        cancel_btn = ttk.Button(button_frame, text="취소", command=edit_win.destroy)
        cancel_btn.pack(side=tk.RIGHT)
        
        save_btn = ttk.Button(button_frame, text="수정 완료", command=save_changes)
        save_btn.pack(side=tk.RIGHT, padx=(0, 5))
        
        # 창 포커스
        edit_win.focus_set()
        content_text.focus()
    
    def _create_date_input_for_edit(self, parent_frame, log_data):
        """수정용 날짜 입력 UI 생성"""
        date_frame = ttk.Frame(parent_frame)
        date_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(date_frame, text="날짜:", width=10).pack(side=tk.LEFT)
        
        # 기존 날짜 파싱
        date_parts = log_data['date'].split('-')
        
        year_var = tk.StringVar(value=date_parts[0])
        month_var = tk.StringVar(value=date_parts[1])
        day_var = tk.StringVar(value=date_parts[2])
        
        year_spinbox = tk.Spinbox(date_frame, from_=2020, to=2030, width=6, textvariable=year_var)
        year_spinbox.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(date_frame, text="년").pack(side=tk.LEFT, padx=(0, 10))
        
        month_spinbox = tk.Spinbox(date_frame, from_=1, to=12, width=4, textvariable=month_var, format="%02.0f")
        month_spinbox.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(date_frame, text="월").pack(side=tk.LEFT, padx=(0, 10))
        
        day_spinbox = tk.Spinbox(date_frame, from_=1, to=31, width=4, textvariable=day_var, format="%02.0f")
        day_spinbox.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(date_frame, text="일").pack(side=tk.LEFT, padx=(0, 10))
        
        return {'year': year_var, 'month': month_var, 'day': day_var}
    
    def _create_category_input_for_edit(self, parent_frame, log_data):
        """수정용 카테고리 및 상태 선택 UI 생성"""
        category_frame = ttk.Frame(parent_frame)
        category_frame.pack(fill=tk.X, pady=(5, 5))
        # 작업 종류
        ttk.Label(category_frame, text="작업 종류:", width=10).pack(side=tk.LEFT)
        
        category_var = tk.StringVar(value=log_data.get('category', ''))
        categories = ["Li-Ag 충전", "IR Align", "EUV Align", "기타 장비 점검"]
        category_combo = ttk.Combobox(category_frame, textvariable=category_var, values=categories, width=15)
        category_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        # 작업 상태
        ttk.Label(category_frame, text="상태:", width=8).pack(side=tk.LEFT)
        
        status_var = tk.StringVar(value=log_data.get('status', '진행중'))
        statuses = ["진행중", "완료"]
        status_combo = ttk.Combobox(category_frame, textvariable=status_var, values=statuses, width=10)
        status_combo.pack(side=tk.LEFT)
        
        return {'category': category_var, 'status': status_var}
    
    def _create_time_input_for_edit(self, parent_frame, log_data):
        """수정용 시간 입력 UI 생성 (날짜 포함)"""
        time_frame = ttk.LabelFrame(parent_frame, text="작업 시간", padding=5)
        time_frame.pack(fill=tk.X, pady=(5, 5))
        
        # 기존 데이터에서 날짜/시간 파싱
        start_datetime_str = log_data.get('start_datetime', '')
        end_datetime_str = log_data.get('end_datetime', '')
        
        # 기존 데이터 호환성 처리
        if not start_datetime_str and 'start_time' in log_data:
            # 기존 형식: 날짜는 로그 날짜, 시간만 별도
            start_datetime_str = f"{log_data['date']} {log_data['start_time']}"
        if not end_datetime_str and 'end_time' in log_data:
            end_datetime_str = f"{log_data['date']} {log_data['end_time']}"
        
        # 기본값 설정
        try:
            start_dt = datetime.datetime.strptime(start_datetime_str, "%Y-%m-%d %H:%M")
        except:
            start_dt = datetime.datetime.now()
        
        try:
            end_dt = datetime.datetime.strptime(end_datetime_str, "%Y-%m-%d %H:%M")
        except:
            end_dt = start_dt + datetime.timedelta(hours=1)
        
        # 시작 시간
        start_frame = ttk.Frame(time_frame)
        start_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(start_frame, text="시작:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        start_datetime_frame = ttk.Frame(start_frame)
        start_datetime_frame.pack(fill=tk.X, pady=(2, 0))
        
        # 시작 날짜
        ttk.Label(start_datetime_frame, text="날짜:", width=8).grid(row=0, column=0, sticky='w', padx=(0, 5))
        
        start_year_var = tk.StringVar(value=str(start_dt.year))
        start_month_var = tk.StringVar(value=f"{start_dt.month:02d}")
        start_day_var = tk.StringVar(value=f"{start_dt.day:02d}")
        
        start_year_spin = tk.Spinbox(start_datetime_frame, from_=2020, to=2030, width=6, textvariable=start_year_var)
        start_year_spin.grid(row=0, column=1, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="년").grid(row=0, column=2, padx=(0, 8))
        
        start_month_spin = tk.Spinbox(start_datetime_frame, from_=1, to=12, width=4, textvariable=start_month_var, format="%02.0f")
        start_month_spin.grid(row=0, column=3, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="월").grid(row=0, column=4, padx=(0, 8))
        
        start_day_spin = tk.Spinbox(start_datetime_frame, from_=1, to=31, width=4, textvariable=start_day_var, format="%02.0f")
        start_day_spin.grid(row=0, column=5, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="일").grid(row=0, column=6, padx=(0, 15))
        
        # 시작 시간
        ttk.Label(start_datetime_frame, text="시각:", width=8).grid(row=0, column=7, sticky='w', padx=(0, 5))
        
        start_hour_var = tk.StringVar(value=f"{start_dt.hour:02d}")
        start_min_var = tk.StringVar(value=f"{start_dt.minute:02d}")
        
        start_hour_spin = tk.Spinbox(start_datetime_frame, from_=0, to=23, width=4, textvariable=start_hour_var, format="%02.0f")
        start_hour_spin.grid(row=0, column=8, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="시").grid(row=0, column=9, padx=(0, 8))
        
        start_min_spin = tk.Spinbox(start_datetime_frame, from_=0, to=59, width=4, textvariable=start_min_var, format="%02.0f")
        start_min_spin.grid(row=0, column=10, padx=(0, 2))
        ttk.Label(start_datetime_frame, text="분").grid(row=0, column=11)
        
        # 종료 시간
        end_frame = ttk.Frame(time_frame)
        end_frame.pack(fill=tk.X, pady=(10, 0))
        
        status = log_data.get('status', '진행중')
        end_label_text = "완료:" if status == "완료" else "예상 종료:"
        end_label = ttk.Label(end_frame, text=end_label_text, font=('Arial', 10, 'bold'))
        end_label.pack(anchor=tk.W)
        
        end_datetime_frame = ttk.Frame(end_frame)
        end_datetime_frame.pack(fill=tk.X, pady=(2, 0))
        
        # 종료 날짜
        ttk.Label(end_datetime_frame, text="날짜:", width=8).grid(row=0, column=0, sticky='w', padx=(0, 5))
        
        end_year_var = tk.StringVar(value=str(end_dt.year))
        end_month_var = tk.StringVar(value=f"{end_dt.month:02d}")
        end_day_var = tk.StringVar(value=f"{end_dt.day:02d}")
        
        end_year_spin = tk.Spinbox(end_datetime_frame, from_=2020, to=2030, width=6, textvariable=end_year_var)
        end_year_spin.grid(row=0, column=1, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="년").grid(row=0, column=2, padx=(0, 8))
        
        end_month_spin = tk.Spinbox(end_datetime_frame, from_=1, to=12, width=4, textvariable=end_month_var, format="%02.0f")
        end_month_spin.grid(row=0, column=3, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="월").grid(row=0, column=4, padx=(0, 8))
        
        end_day_spin = tk.Spinbox(end_datetime_frame, from_=1, to=31, width=4, textvariable=end_day_var, format="%02.0f")
        end_day_spin.grid(row=0, column=5, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="일").grid(row=0, column=6, padx=(0, 15))
        
        # 종료 시간
        ttk.Label(end_datetime_frame, text="시각:", width=8).grid(row=0, column=7, sticky='w', padx=(0, 5))
        
        end_hour_var = tk.StringVar(value=f"{end_dt.hour:02d}")
        end_min_var = tk.StringVar(value=f"{end_dt.minute:02d}")
        
        end_hour_spin = tk.Spinbox(end_datetime_frame, from_=0, to=23, width=4, textvariable=end_hour_var, format="%02.0f")
        end_hour_spin.grid(row=0, column=8, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="시").grid(row=0, column=9, padx=(0, 8))
        
        end_min_spin = tk.Spinbox(end_datetime_frame, from_=0, to=59, width=4, textvariable=end_min_var, format="%02.0f")
        end_min_spin.grid(row=0, column=10, padx=(0, 2))
        ttk.Label(end_datetime_frame, text="분").grid(row=0, column=11)
        
        # 편의 버튼들
        convenience_frame = ttk.Frame(end_datetime_frame)
        convenience_frame.grid(row=0, column=12, padx=(10, 0))
        
        def set_same_day():
            """시작 날짜와 같은 날로 설정"""
            end_year_var.set(start_year_var.get())
            end_month_var.set(start_month_var.get())
            end_day_var.set(start_day_var.get())
        
        def set_next_day():
            """다음 날로 설정"""
            try:
                start_date = datetime.datetime(
                    int(start_year_var.get()),
                    int(start_month_var.get()),
                    int(start_day_var.get())
                )
                next_date = start_date + datetime.timedelta(days=1)
                end_year_var.set(str(next_date.year))
                end_month_var.set(f"{next_date.month:02d}")
                end_day_var.set(f"{next_date.day:02d}")
            except ValueError:
                pass  # 잘못된 날짜인 경우 무시
        
        same_day_btn = ttk.Button(convenience_frame, text="당일", command=set_same_day, width=6)
        same_day_btn.pack(side=tk.TOP, pady=(0, 2))
        
        next_day_btn = ttk.Button(convenience_frame, text="다음날", command=set_next_day, width=6)
        next_day_btn.pack(side=tk.TOP)
        
        return {
            'start_year': start_year_var, 'start_month': start_month_var, 'start_day': start_day_var,
            'start_hour': start_hour_var, 'start_min': start_min_var,
            'end_year': end_year_var, 'end_month': end_month_var, 'end_day': end_day_var,
            'end_hour': end_hour_var, 'end_min': end_min_var,
            'end_label': end_label
        }
    
    def _save_log_changes(self, log_index, date_vars, category_vars, time_vars, content_text, edit_win, refresh_func):
        """로그 변경사항 저장"""
        try:
            # 입력 검증
            date_str = f"{date_vars['year'].get()}-{date_vars['month'].get()}-{date_vars['day'].get()}"
            category = category_vars['category'].get().strip()
            status = category_vars['status'].get().strip()
            content = content_text.get("1.0", tk.END).strip()
            
            # 시작/종료 날짜+시간 정보
            start_date = f"{time_vars['start_year'].get()}-{time_vars['start_month'].get()}-{time_vars['start_day'].get()}"
            start_time = f"{time_vars['start_hour'].get()}:{time_vars['start_min'].get()}"
            start_datetime = f"{start_date} {start_time}"
            
            end_date = f"{time_vars['end_year'].get()}-{time_vars['end_month'].get()}-{time_vars['end_day'].get()}"
            end_time = f"{time_vars['end_hour'].get()}:{time_vars['end_min'].get()}"
            end_datetime = f"{end_date} {end_time}"
            
            if not category:
                messagebox.showwarning("입력 오류", "작업 종류 카테고리를 선택하세요.", parent=edit_win)
                return
            
            if not status:
                messagebox.showwarning("입력 오류", "작업 상태를 선택하세요.", parent=edit_win)
                return
            
            if not content:
                messagebox.showwarning("입력 오류", "작업 내용을 입력하세요.", parent=edit_win)
                content_text.focus()
                return
            
            # 날짜 유효성 검증
            try:
                datetime.datetime.strptime(date_str, "%Y-%m-%d")
                start_dt = datetime.datetime.strptime(start_datetime, "%Y-%m-%d %H:%M")
                end_dt = datetime.datetime.strptime(end_datetime, "%Y-%m-%d %H:%M")
            except ValueError:
                messagebox.showerror("날짜/시간 오류", "올바른 날짜와 시간을 입력하세요.", parent=edit_win)
                return
            
            # 시작 시간이 종료 시간보다 늦은지 확인
            if start_dt >= end_dt:
                messagebox.showwarning("시간 오류", "종료 시간은 시작 시간보다 늦어야 합니다.", parent=edit_win)
                return
            
            # 기존 로그 로드
            logs = self.load_work_logs()
            
            if log_index >= len(logs):
                messagebox.showerror("오류", "해당 로그를 찾을 수 없습니다.", parent=edit_win)
                return
            
            # 로그 업데이트 (원래 timestamp는 유지)
            original_timestamp = logs[log_index]['timestamp']
            logs[log_index] = {
                "date": date_str,
                "category": category,
                "status": status,
                "start_datetime": start_datetime,  # 새 필드
                "end_datetime": end_datetime,      # 새 필드
                "start_time": start_time,          # 기존 호환성
                "end_time": end_time,              # 기존 호환성
                "content": content,
                "timestamp": original_timestamp,
                "modified": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 수정 시간 추가
            }
            
            # 날짜순으로 정렬 (최신이 위로)
            logs.sort(key=lambda x: x["date"], reverse=True)
            
            # 저장
            if self.save_work_logs(logs):
                messagebox.showinfo("수정 완료", "작업 로그가 수정되었습니다.", parent=edit_win)
                edit_win.destroy()
                refresh_func()
            else:
                messagebox.showerror("수정 실패", "로그 수정에 실패했습니다.", parent=edit_win)
                
        except Exception as e:
            messagebox.showerror("오류", f"로그 수정 중 오류가 발생했습니다:\n{e}", parent=edit_win)
    
    def _show_log_detail(self, event, log_tree, parent_win):
        """로그 상세보기"""
        selection = log_tree.selection()
        if not selection:
            return
            
        item = log_tree.item(selection[0])
        values = item['values']
        
        # 해당 로그의 전체 내용 찾기
        logs = self.load_work_logs()
        selected_log = None
        for log in logs:
            if (log['date'] == values[0] and 
                log.get('category', '미분류') == values[1] and
                log['timestamp'] == values[5]):  # 새로운 컬럼 구조에 맞게 인덱스 변경
                selected_log = log
                break
        
        if not selected_log:
            return
            
        # 상세보기 창
        detail_win = tk.Toplevel(parent_win)
        detail_win.title(f"작업 로그 상세보기 - {selected_log['date']}")
        detail_win.geometry("700x600")
        detail_win.transient(parent_win)
        
        detail_frame = ttk.Frame(detail_win)
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 기본 정보
        info_frame = ttk.Frame(detail_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text="날짜:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=(0, 10))
        ttk.Label(info_frame, text=selected_log['date'], font=('Arial', 10)).grid(row=0, column=1, sticky='w')
        
        ttk.Label(info_frame, text="작업 종류:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
        ttk.Label(info_frame, text=selected_log.get('category', '미분류'), font=('Arial', 10)).grid(row=1, column=1, sticky='w', pady=(5, 0))
        
        ttk.Label(info_frame, text="상태:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
        status_text = selected_log.get('status', '미지정')
        status_color = 'green' if status_text == '완료' else 'blue'
        status_label = ttk.Label(info_frame, text=status_text, font=('Arial', 10, 'bold'), foreground=status_color)
        status_label.grid(row=2, column=1, sticky='w', pady=(5, 0))
        
        # 작업 시간 정보
        if 'start_time' in selected_log and 'end_time' in selected_log:
            status = selected_log.get('status', '미지정')
            time_label = "완료 시간:" if status == "완료" else "예상 시간:"
            ttk.Label(info_frame, text="시작 시간:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
            ttk.Label(info_frame, text=selected_log['start_time'], font=('Arial', 10)).grid(row=3, column=1, sticky='w', pady=(5, 0))
            
            ttk.Label(info_frame, text=time_label, font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
            ttk.Label(info_frame, text=selected_log['end_time'], font=('Arial', 10)).grid(row=4, column=1, sticky='w', pady=(5, 0))
        
        ttk.Label(info_frame, text="등록시간:", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
        ttk.Label(info_frame, text=selected_log['timestamp'], font=('Arial', 10)).grid(row=5, column=1, sticky='w', pady=(5, 0))
        
        # 수정 시간 정보 (있는 경우)
        if 'modified' in selected_log:
            ttk.Label(info_frame, text="수정시간:", font=('Arial', 10, 'bold')).grid(row=6, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
            ttk.Label(info_frame, text=selected_log['modified'], font=('Arial', 10), foreground='orange').grid(row=6, column=1, sticky='w', pady=(5, 0))
        
        # 작업 내용
        ttk.Label(detail_frame, text="작업 내용:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        
        content_detail_frame = ttk.Frame(detail_frame)
        content_detail_frame.pack(fill=tk.BOTH, expand=True)
        
        content_detail_text = tk.Text(content_detail_frame, wrap=tk.WORD, font=('Arial', 10))
        content_detail_scrollbar = ttk.Scrollbar(content_detail_frame, orient="vertical", command=content_detail_text.yview)
        content_detail_text.configure(yscrollcommand=content_detail_scrollbar.set)
        
        content_detail_text.insert(tk.END, selected_log['content'])
        content_detail_text.config(state=tk.DISABLED)
        
        content_detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content_detail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 닫기 버튼
        close_btn = ttk.Button(detail_frame, text="닫기", command=detail_win.destroy)
        close_btn.pack(pady=(10, 0))
    
    def _export_logs(self, parent_win):
        """로그를 파일로 내보내기"""
        logs = self.load_work_logs()
        if not logs:
            messagebox.showwarning("경고", "내보낼 로그가 없습니다.", parent=parent_win)
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("JSON files", "*.json")],
            title="작업 로그 내보내기",
            initialfile="work_log_export",
            parent=parent_win
        )
        
        if file_path:
            try:
                if file_path.endswith('.json'):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(logs, f, ensure_ascii=False, indent=2)
                else:
                    df_export = pd.DataFrame(logs)
                    if file_path.endswith('.xlsx'):
                        df_export.to_excel(file_path, index=False)
                    else:
                        df_export.to_csv(file_path, index=False, encoding='utf-8-sig')
                
                messagebox.showinfo("내보내기 완료", f"로그가 내보내졌습니다:\n{file_path}", parent=parent_win)
                
            except Exception as e:
                messagebox.showerror("내보내기 실패", f"파일 내보내기에 실패했습니다:\n{e}", parent=parent_win)


# 편의 함수들
def create_work_log_manager(parent_root=None):
    """WorkLogManager 인스턴스 생성 편의 함수"""
    return WorkLogManager(parent_root)


def show_work_log_window(parent_root=None):
    """작업 로그 창을 바로 표시하는 편의 함수"""
    manager = WorkLogManager(parent_root)
    manager.show_work_log()
    return manager


# 메인 실행 (테스트용)
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # 메인 창 숨기기
    show_work_log_window(root)
    root.mainloop()