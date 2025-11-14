"""
Error Log 관리 모듈
DB 파일들의 events 테이블을 확인하고 관리하는 기능을 제공
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
import pandas as pd
import threading
from datetime import datetime


class ErrorLogManager:
    """Error Log 관리 클래스"""
    
    def __init__(self, parent_root=None, data_folder="Data"):
        """
        초기화
        Args:
            parent_root: 부모 tkinter root 윈도우
            data_folder: DB 파일들이 있는 폴더 경로
        """
        self.parent_root = parent_root
        self.data_folder = data_folder
        self.events_data = []
        
    def show_error_log_window(self):
        """Error Log 확인 창 표시"""
        if not self.parent_root:
            print("부모 윈도우가 설정되지 않았습니다.")
            return
            
        event_win = tk.Toplevel(self.parent_root)
        event_win.title("Error Log 확인")
        event_win.geometry("1200x800")
        event_win.transient(self.parent_root)
        
        # 상단 프레임 - 정보 표시
        info_frame = ttk.Frame(event_win)
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        info_label = ttk.Label(info_frame, text="Error Log 로딩 중...", font=('Arial', 12, 'bold'))
        info_label.pack(anchor=tk.W)
        
        # 진행률 표시
        progress_frame = ttk.Frame(event_win)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        
        progress_var = tk.StringVar()
        progress_label = ttk.Label(progress_frame, textvariable=progress_var, font=('Arial', 10))
        progress_label.pack(anchor=tk.W)
        
        progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        progress_bar.pack(fill=tk.X, pady=(5, 10))
        
        # 메인 컨텐츠 프레임
        main_frame = ttk.Frame(event_win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 로그 목록 트리뷰
        log_columns = ('Datetime', '이벤트 타입', '메시지', '파일명')
        log_tree = ttk.Treeview(main_frame, columns=log_columns, show='headings', height=20)
        
        # 컬럼 설정
        log_tree.heading('Datetime', text='Datetime')
        log_tree.heading('이벤트 타입', text='이벤트 타입')
        log_tree.heading('메시지', text='메시지')
        log_tree.heading('파일명', text='파일명')
        
        log_tree.column('Datetime', width=200)
        log_tree.column('이벤트 타입', width=100)
        log_tree.column('메시지', width=600)
        log_tree.column('파일명', width=150)
        
        # 스크롤바
        v_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=log_tree.yview)
        h_scrollbar = ttk.Scrollbar(main_frame, orient="horizontal", command=log_tree.xview)
        log_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 그리드 배치
        log_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # 하단 버튼 프레임
        button_frame = ttk.Frame(event_win)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 통계 라벨
        stats_label = ttk.Label(button_frame, text="", font=('Arial', 9))
        stats_label.pack(side=tk.LEFT)
        
        # 함수 정의
        def refresh_logs():
            """로그 새로고침"""
            self._load_error_logs_async(log_tree, info_label, progress_var, progress_label, progress_bar, stats_label)
        
        def export_logs():
            """로그 내보내기"""
            self._export_error_logs(event_win)
        
        # 버튼들
        export_btn = ttk.Button(button_frame, text="로그 내보내기", command=export_logs)
        export_btn.pack(side=tk.RIGHT)
        
        refresh_btn = ttk.Button(button_frame, text="새로고침", command=refresh_logs)
        refresh_btn.pack(side=tk.RIGHT, padx=(0, 5))
        
        # 로그 상세보기 이벤트
        log_tree.bind('<Double-1>', lambda e: self._show_log_detail(e, log_tree, event_win))
        
        # 초기 로그 로딩
        refresh_logs()
        
        # 창 포커스
        event_win.focus_set()
    
    def _load_error_logs_async(self, log_tree, info_label, progress_var, progress_label, progress_bar, stats_label):
        """비동기로 Error Log 로딩"""
        def load_thread():
            try:
                # UI 초기화
                log_tree.after(0, lambda: self._clear_tree(log_tree))
                log_tree.after(0, lambda: info_label.config(text="데이터 파일 검색 중..."))
                log_tree.after(0, lambda: progress_var.set("데이터 파일을 검색하고 있습니다..."))
                
                # 데이터 폴더 확인
                if not os.path.exists(self.data_folder):
                    log_tree.after(0, lambda: info_label.config(text=f"데이터 폴더를 찾을 수 없습니다: {self.data_folder}"))
                    log_tree.after(0, lambda: progress_var.set(f"폴더가 존재하지 않습니다: {self.data_folder}"))
                    return
                
                # DB 파일 찾기
                db_files = []
                excel_files = []
                
                for file in os.listdir(self.data_folder):
                    if file.endswith('.db'):
                        db_files.append(os.path.join(self.data_folder, file))
                    elif file.endswith(('.xlsx', '.xls')):
                        excel_files.append(os.path.join(self.data_folder, file))
                
                # DB 파일이 없으면 현재 상황 안내
                if not db_files:
                    if excel_files:
                        message = f"SQLite DB 파일은 없지만 Excel 파일 {len(excel_files)}개를 발견했습니다.\n현재 시스템에서는 Excel 파일로 데이터를 저장하고 있습니다."
                        log_tree.after(0, lambda: info_label.config(text="DB 파일 없음 - Excel 파일 사용 중"))
                        log_tree.after(0, lambda: progress_var.set(message))
                        log_tree.after(0, lambda: self._show_available_files(log_tree, excel_files))
                        log_tree.after(0, lambda: stats_label.config(text=f"Excel 파일 {len(excel_files)}개 발견 (SQLite DB 파일 없음)"))
                    else:
                        log_tree.after(0, lambda: info_label.config(text="데이터 파일을 찾을 수 없습니다."))
                        log_tree.after(0, lambda: progress_var.set("DB 파일과 Excel 파일이 모두 없습니다."))
                        log_tree.after(0, lambda: stats_label.config(text="사용 가능한 데이터 파일이 없습니다."))
                    return
                
                log_tree.after(0, lambda: progress_bar.config(maximum=len(db_files)))
                
                all_events = []
                
                for i, db_file in enumerate(db_files):
                    filename = os.path.basename(db_file)
                    log_tree.after(0, lambda f=filename: progress_var.set(f"처리 중: {f}"))
                    log_tree.after(0, lambda i=i: progress_bar.config(value=i))
                    
                    try:
                        # DB 연결 및 events 테이블 조회
                        conn = sqlite3.connect(db_file)
                        cursor = conn.cursor()
                        
                        # events 테이블 존재 확인
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events';")
                        if cursor.fetchone():
                            # 컬럼 정보 먼저 가져오기
                            cursor.execute("PRAGMA table_info(events)")
                            columns = [column[1] for column in cursor.fetchall()]
                            
                            # 시간 관련 컬럼 찾기
                            time_columns = ['timestamp', 'time', 'datetime', 'date', 'created_at', 'updated_at']
                            order_column = None
                            for time_col in time_columns:
                                if time_col in columns:
                                    order_column = time_col
                                    break
                            
                            # 적절한 쿼리 실행
                            if order_column:
                                cursor.execute(f"SELECT * FROM events ORDER BY {order_column} DESC LIMIT 1000")
                            else:
                                cursor.execute("SELECT * FROM events LIMIT 1000")
                            
                            events = cursor.fetchall()
                            
                            for event in events:
                                event_dict = dict(zip(columns, event))
                                event_dict['source_file'] = filename
                                
                                # 파일명에서 날짜 추출 + Time을 시:분:초로 변환해서 Datetime 생성
                                if 'time' in event_dict:
                                    try:
                                        # 파일명에서 날짜 추출 (예: 2025-09-25.db -> 2025-09-25)
                                        file_date = filename.replace('.db', '')
                                        
                                        # Time 값을 초 단위로 가정하고 시:분:초로 변환
                                        time_seconds = int(float(event_dict['time']))
                                        hours = time_seconds // 3600
                                        minutes = (time_seconds % 3600) // 60
                                        seconds = time_seconds % 60
                                        
                                        # 완전한 datetime 문자열 생성
                                        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                                        full_datetime = f"{file_date} {time_str}"
                                        event_dict['Datetime'] = full_datetime
                                        
                                        # 원본 time 컬럼 제거
                                        del event_dict['time']
                                        
                                    except Exception as e:
                                        print(f"Time → Datetime 변환 오류: {e}")
                                        # 변환 실패시 원본 값 유지하고 컬럼명만 변경
                                        event_dict['Datetime'] = str(event_dict.pop('time', ''))
                                elif 'datetime' in event_dict:
                                    # datetime 컬럼이 있으면 그대로 사용
                                    event_dict['Datetime'] = str(event_dict['datetime'])
                                    del event_dict['datetime']
                                
                                all_events.append(event_dict)
                        
                        conn.close()
                        
                    except Exception as e:
                        print(f"DB 파일 {filename} 처리 중 오류: {e}")
                        continue
                
                # 시간순 정렬 (최신 순) - Datetime 또는 다른 시간 컬럼 사용
                def get_sort_key(event):
                    # Datetime이 있으면 우선 사용
                    if 'Datetime' in event:
                        return event['Datetime']
                    # 그 다음 다른 시간 컬럼들 시도
                    for time_col in ['timestamp', 'time', 'datetime', 'date']:
                        if time_col in event:
                            return str(event[time_col])
                    return ''
                
                all_events.sort(key=get_sort_key, reverse=True)
                self.events_data = all_events
                
                # UI 업데이트
                log_tree.after(0, lambda: self._populate_tree(log_tree, all_events))
                log_tree.after(0, lambda: info_label.config(text=f"Error Log 로딩 완료 - 총 {len(all_events)}개 이벤트"))
                log_tree.after(0, lambda: progress_var.set(f"완료: {len(all_events)}개 이벤트 로드됨"))
                log_tree.after(0, lambda: progress_bar.config(value=len(db_files)))
                log_tree.after(0, lambda: self._update_stats(stats_label, all_events))
                
            except Exception as e:
                log_tree.after(0, lambda: messagebox.showerror("오류", f"Error Log 로딩 중 오류가 발생했습니다:\n{e}"))
        
        # 스레드로 실행
        thread = threading.Thread(target=load_thread)
        thread.daemon = True
        thread.start()
    
    def _clear_tree(self, tree):
        """트리뷰 초기화"""
        for item in tree.get_children():
            tree.delete(item)
    
    def _populate_tree(self, tree, events):
        """트리뷰에 이벤트 데이터 채우기"""
        for event in events:
            # 메시지 길이 제한
            message = str(event.get('message', ''))[:200]
            if len(str(event.get('message', ''))) > 200:
                message += '...'
            
            tree.insert('', tk.END, values=(
                event.get('Datetime', event.get('timestamp', '')),  # Datetime 컬럼 우선
                event.get('event_type', event.get('type', '')),
                message,
                event.get('source_file', '')
            ))
    
    def _show_available_files(self, tree, excel_files):
        """사용 가능한 Excel 파일들을 트리뷰에 표시"""
        # 안내 메시지 추가
        tree.insert('', tk.END, values=(
            "📋 안내사항",
            "",
            "정보",
            "현재 시스템은 Excel 파일로 데이터를 저장합니다. Error Log 기능을 사용하려면 SQLite DB 파일이 필요합니다."
        ))
        
        tree.insert('', tk.END, values=(
            "💡 해결방법",
            "",
            "제안",
            "1) 시스템을 DB 저장 모드로 변경하거나, 2) Excel 파일용 Error Log 분석 기능을 별도 개발하는 것을 권장합니다."
        ))
        
        # 구분선
        tree.insert('', tk.END, values=(
            "─" * 50,
            "",
            "",
            ""
        ))
        
        for file_path in excel_files[:10]:  # 최대 10개만 표시
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            file_size_mb = round(file_size / (1024 * 1024), 2)
            
            # 파일 수정 시간
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            mod_time_str = mod_time.strftime('%Y-%m-%d %H:%M:%S')
            
            tree.insert('', tk.END, values=(
                filename,
                mod_time_str,
                "Excel 파일",
                f"{file_size_mb} MB"
            ))
        
        if len(excel_files) > 10:
            tree.insert('', tk.END, values=(
                f"... 및 {len(excel_files) - 10}개 파일 더",
                "",
                "기타",
                "표시된 것은 최근 10개 파일입니다."
            ))
    
    def _update_stats(self, stats_label, events):
        """통계 정보 업데이트"""
        if not events:
            stats_label.config(text="이벤트가 없습니다.")
            return
        
        # 이벤트 타입별 통계
        type_counts = {}
        for event in events:
            event_type = event.get('event_type', event.get('type', '알 수 없음'))
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
        
        # 최근 이벤트 시간
        latest_time = events[0].get('timestamp', '알 수 없음')
        
        # 통계 텍스트 구성
        stats_text = f"총 {len(events)}개 이벤트, 최근: {latest_time}"
        if type_counts:
            type_summary = ", ".join([f"{k}: {v}" for k, v in list(type_counts.items())[:3]])
            stats_text += f" | {type_summary}"
        
        stats_label.config(text=stats_text)
    
    def _show_log_detail(self, event, log_tree, parent_win):
        """로그 상세보기"""
        selection = log_tree.selection()
        if not selection:
            return
            
        item = log_tree.item(selection[0])
        values = item['values']
        
        # 해당 이벤트 찾기
        selected_event = None
        for event in self.events_data:
            if (event.get('source_file', '') == values[0] and
                event.get('timestamp', '') == values[1]):
                selected_event = event
                break
        
        if not selected_event:
            return
            
        # 상세보기 창
        detail_win = tk.Toplevel(parent_win)
        detail_win.title(f"Error Log 상세보기 - {selected_event.get('source_file', '')}")
        detail_win.geometry("800x600")
        detail_win.transient(parent_win)
        
        detail_frame = ttk.Frame(detail_win)
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 기본 정보
        info_frame = ttk.Frame(detail_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        info_items = [
            ("파일명:", selected_event.get('source_file', '')),
            ("시간:", selected_event.get('timestamp', '')),
            ("이벤트 타입:", selected_event.get('event_type', selected_event.get('type', ''))),
            ("레벨:", selected_event.get('level', ''))
        ]
        
        for i, (label, value) in enumerate(info_items):
            if value:  # 값이 있는 경우만 표시
                ttk.Label(info_frame, text=label, font=('Arial', 10, 'bold')).grid(
                    row=i, column=0, sticky='w', padx=(0, 10), pady=(2, 0))
                ttk.Label(info_frame, text=str(value), font=('Arial', 10)).grid(
                    row=i, column=1, sticky='w', pady=(2, 0))
        
        # 메시지 내용
        ttk.Label(detail_frame, text="메시지:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        
        message_frame = ttk.Frame(detail_frame)
        message_frame.pack(fill=tk.BOTH, expand=True)
        
        message_text = tk.Text(message_frame, wrap=tk.WORD, font=('Arial', 10))
        message_scrollbar = ttk.Scrollbar(message_frame, orient="vertical", command=message_text.yview)
        message_text.configure(yscrollcommand=message_scrollbar.set)
        
        message_text.insert(tk.End, selected_event.get('message', ''))
        message_text.config(state=tk.DISABLED)
        
        message_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        message_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 기타 속성들 (있는 경우)
        other_attrs = {k: v for k, v in selected_event.items() 
                      if k not in ['source_file', 'timestamp', 'event_type', 'type', 'level', 'message']}
        
        if other_attrs:
            ttk.Label(detail_frame, text="기타 속성:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            
            attr_frame = ttk.Frame(detail_frame)
            attr_frame.pack(fill=tk.X, pady=(0, 10))
            
            attr_text = tk.Text(attr_frame, height=5, wrap=tk.WORD, font=('Arial', 9))
            attr_scrollbar = ttk.Scrollbar(attr_frame, orient="vertical", command=attr_text.yview)
            attr_text.configure(yscrollcommand=attr_scrollbar.set)
            
            for key, value in other_attrs.items():
                attr_text.insert(tk.END, f"{key}: {value}\n")
            
            attr_text.config(state=tk.DISABLED)
            
            attr_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            attr_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 닫기 버튼
        ttk.Button(detail_frame, text="닫기", command=detail_win.destroy).pack(pady=(10, 0))
    
    def _export_error_logs(self, parent_win):
        """Error Log 내보내기"""
        if not self.events_data:
            messagebox.showwarning("경고", "내보낼 로그가 없습니다.", parent=parent_win)
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("JSON files", "*.json")],
            title="Error Log 내보내기",
            initialfile=f"error_log_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            parent=parent_win
        )
        
        if file_path:
            try:
                if file_path.endswith('.json'):
                    import json
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.events_data, f, ensure_ascii=False, indent=2)
                else:
                    df_export = pd.DataFrame(self.events_data)
                    if file_path.endswith('.xlsx'):
                        df_export.to_excel(file_path, index=False)
                    else:
                        df_export.to_csv(file_path, index=False, encoding='utf-8-sig')
                
                messagebox.showinfo("내보내기 완료", f"Error Log가 내보내졌습니다:\n{file_path}", parent=parent_win)
                
            except Exception as e:
                messagebox.showerror("내보내기 실패", f"파일 내보내기에 실패했습니다:\n{e}", parent=parent_win)
    
    def _clear_old_logs(self, parent_win, refresh_callback):
        """오래된 로그 정리"""
        if not messagebox.askyesno("로그 정리 확인", 
                                 "30일 이상 된 Error Log를 정리하시겠습니까?\n"
                                 "이 작업은 되돌릴 수 없습니다.", parent=parent_win):
            return
        
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=30)
            
            cleared_count = 0
            db_files = []
            if os.path.exists(self.data_folder):
                for file in os.listdir(self.data_folder):
                    if file.endswith('.db'):
                        db_files.append(os.path.join(self.data_folder, file))
            
            for db_file in db_files:
                try:
                    conn = sqlite3.connect(db_file)
                    cursor = conn.cursor()
                    
                    # events 테이블 존재 확인
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events';")
                    if cursor.fetchone():
                        # 30일 이전 로그 삭제
                        cursor.execute("DELETE FROM events WHERE timestamp < ?", 
                                     (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),))
                        cleared_count += cursor.rowcount
                        conn.commit()
                    
                    conn.close()
                    
                except Exception as e:
                    print(f"DB 파일 {db_file} 정리 중 오류: {e}")
                    continue
            
            messagebox.showinfo("정리 완료", f"총 {cleared_count}개의 오래된 Error Log가 정리되었습니다.", parent=parent_win)
            refresh_callback()
            
        except Exception as e:
            messagebox.showerror("정리 실패", f"로그 정리 중 오류가 발생했습니다:\n{e}", parent=parent_win)


# 편의 함수들
def create_error_log_manager(parent_root=None, data_folder="Data"):
    """ErrorLogManager 인스턴스 생성 편의 함수"""
    return ErrorLogManager(parent_root, data_folder)


def show_error_log_window(parent_root=None, data_folder="Data"):
    """Error Log 창을 바로 표시하는 편의 함수"""
    manager = ErrorLogManager(parent_root, data_folder)
    manager.show_error_log_window()
    return manager


# 메인 실행 (테스트용)
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # 메인 창 숨기기
    show_error_log_window(root)
    root.mainloop()
