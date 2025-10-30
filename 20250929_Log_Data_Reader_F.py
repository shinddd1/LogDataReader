import sqlite3
import pandas as pd
import matplotlib
# 백엔드 설정 추가
matplotlib.use('TkAgg')  # 이 줄을 추가
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import ttk
import datetime  # 이 줄만 유지
import re
import os
import glob
import matplotlib.dates as mdates
from matplotlib.widgets import SpanSelector
from tkinter import messagebox
from tkinter import filedialog
import concurrent.futures
import json
from work_log_manager import WorkLogManager
from cnt_data_plotter import CNTDataPlotter
from error_log_manager import ErrorLogManager

print(f"Matplotlib 백엔드: {matplotlib.get_backend()}")  # 디버깅용

# 전역 dict로 사용자 정의 파라미터 관리
custom_params = {}

# make_to_datetime_safe 함수 수정 (벡터화 개선)
def make_to_datetime_safe(base_date):
    def to_datetime_safe(value):
        # NaN이나 None 값 먼저 체크
        if pd.isna(value):
            return pd.NaT
            
        # isinstance 체크 부분 수정 - datetime.datetime으로 변경
        if isinstance(value, pd.Timestamp) or isinstance(value, datetime.datetime):
            time_part = value.time()
            return base_date.replace(hour=time_part.hour,
                                     minute=time_part.minute,
                                     second=time_part.second,
                                     microsecond=time_part.microsecond)
        try:
            # 문자열이나 숫자 타입을 먼저 확인
            if isinstance(value, str):
                # 빈 문자열 체크
                if not value.strip():
                    return pd.NaT
                value = float(value)
            elif not isinstance(value, (int, float)):
                return pd.NaT
                
            return base_date + datetime.timedelta(seconds=int(float(value)))
        except (ValueError, TypeError, OverflowError):
            return pd.NaT
    return to_datetime_safe

# 벡터화된 datetime 변환 함수 추가
def convert_datetime_vectorized(series, base_date):
    """pandas Series를 벡터화 방식으로 datetime 변환"""
    try:
        # 1. NaN 값 처리
        valid_mask = pd.notna(series)
        result = pd.Series(pd.NaT, index=series.index, dtype='datetime64[ns]')
        
        if not valid_mask.any():
            return result
            
        valid_series = series[valid_mask]
        
        # 2. 이미 datetime 타입인 경우
        datetime_mask = valid_series.apply(lambda x: isinstance(x, (pd.Timestamp, datetime.datetime)))
        if datetime_mask.any():
            datetime_values = valid_series[datetime_mask]
            for idx, value in datetime_values.items():
                time_part = value.time()
                result.loc[idx] = base_date.replace(hour=time_part.hour,
                                                  minute=time_part.minute,
                                                  second=time_part.second,
                                                  microsecond=time_part.microsecond)
        
        # 3. 숫자 타입 처리 (vectorized)
        numeric_mask = ~datetime_mask
        if numeric_mask.any():
            numeric_values = valid_series[numeric_mask]
            try:
                # 문자열을 숫자로 변환 시도
                numeric_converted = pd.to_numeric(numeric_values, errors='coerce')
                valid_numeric = pd.notna(numeric_converted)
                
                if valid_numeric.any():
                    # 벡터화된 timedelta 계산
                    seconds = numeric_converted[valid_numeric].astype(int)
                    base_timestamps = pd.Timestamp(base_date)
                    result.loc[numeric_converted[valid_numeric].index] = base_timestamps + pd.to_timedelta(seconds, unit='s')
                    
            except Exception:
                pass
        
        return result
        
    except Exception as e:
        print(f"벡터화 변환 실패, fallback 사용: {e}")
        # fallback to apply method
        to_datetime_safe = make_to_datetime_safe(base_date)
        return series.apply(to_datetime_safe)

# 폴더 선택 기능 추가
def select_folder():
    """DB 파일이 있는 폴더를 선택하는 함수"""
    folder_path = filedialog.askdirectory(
        title="DB 파일이 있는 폴더를 선택하세요",
        initialdir=os.path.dirname(os.path.abspath(__file__))  # 현재 스크립트 위치를 기본값으로
    )
    return folder_path

# 1. 폴더 선택 또는 기본 폴더 사용
print("DB 파일 폴폴더를 선택하시겠습니까?")
print("1. 현재 폴더 사용 (기본)")
print("2. 다른 폴더 선택 (NAS 등)")

# 간단한 선택 창 생성
temp_root = tk.Tk()
temp_root.withdraw()  # 메인 창 숨기기

choice = messagebox.askyesno(
    "폴더 선택", 
    "DB 파일이 있는 폴더를 선택하시겠습니까?\n\n"
    "예: 폴더 선택 대화상자 열기\n"
    "아니오: 현재 폴더 사용"
)

if choice:
    db_folder = select_folder()
    if not db_folder:  # 사용자가 취소한 경우
        print("폴더 선택이 취소되었습니다. 현재 폴더를 사용합니다.")
        db_folder = os.path.dirname(os.path.abspath(__file__))
    else:
        print(f"선택된 폴더: {db_folder}")
else:
    db_folder = os.path.dirname(os.path.abspath(__file__))
    print(f"현재 폴더 사용: {db_folder}")

temp_root.destroy()

# DB 파일 탐색
db_files = sorted(glob.glob(os.path.join(db_folder, "*.db")))

if not db_files:    
    messagebox.showerror("오류", f"선택한 폴더에 DB 파일이 없습니다.\n폴더: {db_folder}")
    raise ValueError("DB 파일이 없습니다.")

print(f"찾은 DB 파일 수: {len(db_files)}")
for i, db_file in enumerate(db_files[:5]):  # 처음 5개만 표시
    print(f"  {i+1}. {os.path.basename(db_file)}")
if len(db_files) > 5:
    print(f"  ... 외 {len(db_files)-5}개")

# 2. 첫 번째 DB에서 컬럼 목록 추출
conn = sqlite3.connect(db_files[0])
try:
    df_sample = pd.read_sql_query("SELECT * FROM data LIMIT 1", conn)
except Exception as e:
    conn.close()
    raise ValueError(f"DB 읽기 실패: {e}")
conn.close()

# 3. 시간 컬럼 및 수치형 컬럼 자동 탐색 부분을 수정
time_cols = [c for c in df_sample.columns if c.lower() in ['time', 'timestamp', 'datetime']]
exclude_cols = time_cols  # fault 컬럼 제외를 제거

print(f"전체 컬럼 수: {len(df_sample.columns)}")
print(f"시간 컬럼: {time_cols}")
print(f"제외할 컬럼: {exclude_cols}")

# 수치형 컬럼뿐만 아니라 모든 컬럼을 포함하되, 시간만 제외
# 기존: 수치형 컬럼만 선택
# num_cols = [c for c in df_sample.select_dtypes(include=[np.number]).columns if c not in exclude_cols]

# 수정: 모든 컬럼을 포함하되 시간만 제외 (fault는 포함)
all_available_cols = [c for c in df_sample.columns if c not in exclude_cols]

# 수치형 컬럼 구분
numeric_cols = [c for c in df_sample.select_dtypes(include=[np.number]).columns if c not in exclude_cols]
non_numeric_cols = [c for c in all_available_cols if c not in numeric_cols]

print(f"수치형 컬럼 수: {len(numeric_cols)}")
print(f"비수치형 컬럼 수: {len(non_numeric_cols)}")
print(f"총 사용 가능한 컬럼 수: {len(all_available_cols)}")

# 수치형 컬럼을 기본으로 하되, 필요시 비수치형도 포함할 수 있도록
num_cols = numeric_cols.copy()

# 비수치형 컬럼 중에서도 플롯 가능한 것들을 추가 (예: 문자열이지만 숫자로 변환 가능한 것들)
for col in non_numeric_cols:
    try:
        # 샘플 데이터로 숫자 변환 가능성 체크
        sample_values = df_sample[col].dropna()
        if len(sample_values) > 0:
            # 첫 번째 값이 숫자로 변환 가능한지 체크
            pd.to_numeric(sample_values.iloc[0])
            num_cols.append(col)
            print(f"비수치형이지만 변환 가능한 컬럼 추가: {col}")
    except (ValueError, TypeError, IndexError):
        # 숫자로 변환 불가능한 컬럼은 제외
        pass

# fault 컬럼이 있다면 무조건 추가 (숫자 변환이 안되더라도)
if 'fault' in df_sample.columns and 'fault' not in num_cols:
    num_cols.append('fault')
    print("fault 컬럼 강제 추가")

print(f"최종 사용 가능한 파라미터 수: {len(num_cols)}")

# 디버깅: 누락된 컬럼들을 확인
if len(num_cols) < 349:
    print(f"\n=== 누락 분석 ===")
    print(f"예상: 349개, 실제: {len(num_cols)}개, 차이: {349 - len(num_cols)}개")
    
    # 모든 컬럼 타입 확인
    print(f"\n=== 전체 컬럼 타입 분석 ===")
    dtype_counts = df_sample.dtypes.value_counts()
    print(dtype_counts)
    
    # 제외된 컬럼들 확인
    excluded_cols = [c for c in df_sample.columns if c not in num_cols and c not in exclude_cols]
    if excluded_cols:
        print(f"\n=== 제외된 컬럼들 ({len(excluded_cols)}개) ===")
        for col in excluded_cols[:20]:  # 처음 20개만 표시
            print(f"  - {col}: {df_sample[col].dtype}")
        if len(excluded_cols) > 20:
            print(f"  ... 외 {len(excluded_cols) - 20}개")

# 4. tkinter 인터페이스 - 탭 구조로 변경
root = tk.Tk()
root.title("LEUS 로그 데이터 분석 시스템")
root.geometry("1200x800")  # 창 크기 확대

# 탭 컨트롤 생성
notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# 탭 1: 기존 로그 분석 탭
log_tab = ttk.Frame(notebook)
notebook.add(log_tab, text="로그 데이터 분석")

frame = ttk.Frame(log_tab)
frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

label = ttk.Label(frame, text="Y축 변수 선택:")
label.pack(pady=5)

# 스크롤바가 있는 리스트박스 프레임 생성
listbox_frame = ttk.Frame(frame)
listbox_frame.pack(fill=tk.BOTH, expand=True, pady=5)

# 리스트박스와 스크롤바 생성
var_list = tk.Listbox(listbox_frame, height=25, exportselection=False, font=('Arial', 10))
scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=var_list.yview)
var_list.configure(yscrollcommand=scrollbar.set)

# 리스트박스와 스크롤바 배치
var_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

def add_custom_param():
    """
    사용자 정의 파라미터를 추가하는 함수입니다.
    검색 기능, 파라미터 선택, 값 조건 설정을 포함합니다.
    """
    win = tk.Toplevel(root)
    win.title("사용자 정의 파라미터 추가")
    win.geometry("1200x800")  # 창 크기 확대

    # --- 이름 입력 필드 추가 ---
    frame_name = ttk.Frame(win)
    frame_name.pack(padx=10, pady=5, fill=tk.X)
    ttk.Label(frame_name, text="새 파라미터 이름:").pack(side=tk.LEFT)
    entry_name = ttk.Entry(frame_name, font=('Arial', 11))
    entry_name.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
    
    # --- 검색 기능 추가 ---
    search_frame = ttk.Frame(win)
    search_frame.pack(fill=tk.X, padx=10, pady=5)
    
    ttk.Label(search_frame, text="파라미터 검색:").pack(side=tk.LEFT)
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, font=('Arial', 10))
    search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
    
    # 검색 초기화 버튼
    clear_btn = ttk.Button(search_frame, text="초기화", width=8)
    clear_btn.pack(side=tk.RIGHT)
    
    # --- 전체 파라미터 목록 (실제 DB 컬럼만) ---
    all_params = df_sample.columns.tolist()
    all_params = [p for p in all_params if p not in time_cols]  # 시간 컬럼만 제외 (fault는 포함)
    all_params.sort()  # 알파벳 순 정렬
    
    # --- 메인 컨텐츠 프레임 ---
    main_content_frame = ttk.Frame(win)
    main_content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    # --- 왼쪽: 파라미터 리스트 ---
    left_frame = ttk.LabelFrame(main_content_frame, text="파라미터 목록 (Ctrl/Shift 키 지원)", padding=5)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
    
    listbox_frame = ttk.Frame(left_frame)
    listbox_frame.pack(fill=tk.BOTH, expand=True)
    
    # EXTENDED 모드로 변경 (Ctrl/Shift 키 지원)
    lb = tk.Listbox(listbox_frame, selectmode=tk.EXTENDED, height=15, font=('Arial', 9))
    lb_scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=lb.yview)
    lb.configure(yscrollcommand=lb_scrollbar.set)
    
    lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    lb_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # 선택 버튼 프레임
    select_btn_frame = ttk.Frame(left_frame)
    select_btn_frame.pack(fill=tk.X, pady=(5, 0))
    
    select_btn = ttk.Button(select_btn_frame, text=">>> 선택 >>>", width=15)
    select_btn.pack()
    
    # 정보 레이블
    info_label = ttk.Label(left_frame, text=f"전체: {len(all_params)}개", font=('Arial', 9))
    info_label.pack(anchor=tk.W, pady=(5, 0))
    
    # --- 중앙: 컨트롤 버튼들 ---
    middle_frame = ttk.Frame(main_content_frame)
    middle_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 5))
    middle_frame.configure(width=120)
    
    # 가운데 정렬을 위한 여백
    ttk.Label(middle_frame, text="").pack(expand=True)
    
    select_all_btn = ttk.Button(middle_frame, text="전체 선택", width=12)
    select_all_btn.pack(pady=2)
    
    clear_selected_btn = ttk.Button(middle_frame, text="전체 해제", width=12)
    clear_selected_btn.pack(pady=2)
    
    remove_selected_btn = ttk.Button(middle_frame, text="선택 제거", width=12)
    remove_selected_btn.pack(pady=2)
    
    # 아래쪽 여백
    ttk.Label(middle_frame, text="").pack(expand=True)
    
    # --- 오른쪽: 선택된 파라미터 및 조건 설정 ---
    right_frame = ttk.LabelFrame(main_content_frame, text="선택된 파라미터 및 조건 설정", padding=5)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    right_frame.configure(width=500)  # 고정 너비 설정
    
    # 선택된 파라미터 리스트박스
    selected_listbox_frame = ttk.Frame(right_frame)
    selected_listbox_frame.pack(fill=tk.BOTH, expand=True)
    
    selected_lb = tk.Listbox(selected_listbox_frame, height=10, font=('Arial', 9), width=40)
    selected_scrollbar = ttk.Scrollbar(selected_listbox_frame, orient="vertical", command=selected_lb.yview)
    selected_lb.configure(yscrollcommand=selected_scrollbar.set)
    
    selected_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    selected_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # 선택 정보 레이블
    selected_info_label = ttk.Label(right_frame, text="선택된 파라미터: 0개", font=('Arial', 9))
    selected_info_label.pack(anchor=tk.W, pady=(5, 0))
    
    # 조건 설정 UI를 담을 프레임
    conditions_frame = ttk.Frame(right_frame)
    conditions_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
    
    # AND/OR 선택 콤보박스
    logic_frame = ttk.Frame(right_frame)
    logic_frame.pack(fill=tk.X, pady=5)
    
    ttk.Label(logic_frame, text="조건 결합 방식:").pack(side=tk.LEFT)
    logic_options = ["AND", "OR"]
    logic_var = tk.StringVar(value=logic_options[0])
    logic_combo = ttk.Combobox(logic_frame, textvariable=logic_var, values=logic_options, width=5)
    logic_combo.pack(side=tk.LEFT)
    
    # 선택된 파라미터들을 저장할 set (중복 방지)
    selected_params_set = set()
    
    # 조건 정보 저장 (파라미터: {조건, threshold} 형태)
    condition_info = {}
    
    def update_param_list():
        """검색어에 따라 파라미터 리스트 업데이트"""
        # 현재 선택된 항목들을 저장
        current_selections = []
        for idx in lb.curselection():
            current_selections.append(lb.get(idx))
        
        lb.delete(0, tk.END)
        search_text = search_var.get().lower()
        
        filtered_params = []
        for param in all_params:
            if search_text in param.lower():
                filtered_params.append(param)
        
        for param in filtered_params:
            lb.insert(tk.END, param)
        
        # 검색 후 이전 선택들 복원
        for selection in current_selections:
            if selection in filtered_params:
                try:
                    idx = filtered_params.index(selection)
                    lb.selection_set(idx)
                except:
                    pass
        
        # 정보 레이블 업데이트
        if search_text:
            info_text = f"검색 결과: {len(filtered_params)}개 / 전체: {len(all_params)}개"
        else:
            info_text = f"전체: {len(all_params)}개"
        info_label.config(text=info_text)
    
    def update_selected_display():
        """선택된 파라미터들을 오른쪽 리스트박스에 표시하고 조건 UI 생성"""
        selected_lb.delete(0, tk.END)
        
        # 조건 UI 초기화
        for widget in conditions_frame.winfo_children():
            widget.destroy()
        
        # 선택된 파라미터들을 리스트박스에 추가
        for param in sorted(selected_params_set):
            selected_lb.insert(tk.END, param)
        
        selected_info_label.config(text=f"선택된 파라미터: {len(selected_params_set)}개")
        
        # 조건 UI 생성
        create_condition_ui()
    
    def create_condition_ui():
        """선택된 파라미터에 따라 조건 설정 UI 동적 생성"""
        nonlocal condition_info
        condition_info = {}  # 초기화
        
        for i, param in enumerate(sorted(selected_params_set)):
            param_frame = ttk.LabelFrame(conditions_frame, text=param, padding=5)
            param_frame.pack(fill=tk.X, pady=2)
            
            condition_label = ttk.Label(param_frame, text="조건:", width=8)
            condition_label.grid(row=0, column=0, padx=5, pady=2, sticky='w')
            
            condition_options = ["이상", "이하", "초과", "미만", "같음", "다름"]
            condition_var = tk.StringVar(value=condition_options[0])
            condition_combo = ttk.Combobox(param_frame, textvariable=condition_var, values=condition_options, width=6)
            condition_combo.grid(row=0, column=1, padx=5, pady=2, sticky='w')
            
            threshold_label = ttk.Label(param_frame, text="Threshold:", width=8)
            threshold_label.grid(row=0, column=2, padx=5, pady=2, sticky='w')
            
            threshold_var = tk.StringVar()
            threshold_entry = ttk.Entry(param_frame, textvariable=threshold_var, width=10)
            threshold_entry.grid(row=0, column=3, padx=5, pady=2, sticky='w')
            
            # 조건 정보 저장
            condition_info[param] = {
                'condition_var': condition_var,
                'threshold_var': threshold_var
            }
    
    def add_selected_param():
        """선택된 파라미터들을 선택 리스트에 추가 (다중 선택 지원)"""
        selections = lb.curselection()
        added_count = 0
        
        for idx in selections:
            param = lb.get(idx)
            if param not in selected_params_set:
                selected_params_set.add(param)
                added_count += 1
        
        if added_count > 0:
            update_selected_display()
        
        # 선택 상태 유지 (사용자가 추가 선택을 계속할 수 있도록)
    
    def select_all_params():
        """현재 표시된 모든 파라미터를 선택"""
        for i in range(lb.size()):
            param = lb.get(i)
            selected_params_set.add(param)
        update_selected_display()
    
    def clear_all_selected():
        """모든 선택 해제"""
        selected_params_set.clear()
        update_selected_display()
    
    def remove_selected_param():
        """선택된 파라미터를 선택 리스트에서 제거"""
        selection = selected_lb.curselection()
        if selection:
            param = selected_lb.get(selection[0])
            if param in selected_params_set:
                selected_params_set.remove(param)
                update_selected_display()
    
    # 키보드 단축키 추가
    def on_key_press(event):
        if event.keysym == 'a' and (event.state & 0x4):  # Ctrl+A
            lb.select_set(0, tk.END)
            return "break"  # 기본 동작 방지
        elif event.keysym == 'Return':  # Enter 키
            add_selected_param()
            return "break"
        elif event.keysym == 'space':  # Space 키
            add_selected_param()
            return "break"
    
    lb.bind('<KeyPress>', on_key_press)
    
    # 초기 리스트 표시
    update_param_list()
    
    # 검색어 변경시 리스트 업데이트 (실시간) - 선택 유지
    def on_search_change(*args):
        update_param_list()
    
    search_var.trace('w', on_search_change)
    
    # 검색 초기화 기능
    def clear_search():
        search_var.set("")
        search_entry.focus()
    
    clear_btn.config(command=clear_search)
    
    # 버튼 기능 연결
    select_btn.config(command=add_selected_param)
    select_all_btn.config(command=select_all_params)
    clear_selected_btn.config(command=clear_all_selected)
    remove_selected_btn.config(command=remove_selected_param)
    
    # 더블클릭으로 빠른 선택
    def on_double_click(event):
        add_selected_param()
    
    lb.bind('<Double-1>', on_double_click)
    
    # 오른쪽 리스트박스에서 Delete 키로 제거
    def on_delete_key(event):
        remove_selected_param()
    
    selected_lb.bind('<Delete>', on_delete_key)
    selected_lb.bind('<BackSpace>', on_delete_key)
    
    # --- 버튼 프레임 ---
    btn_frame = ttk.Frame(win)
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    
    def on_ok():
        name = entry_name.get().strip()
        selected_params = list(selected_params_set)
        
        if not name:
            messagebox.showwarning("경고", "파라미터 이름을 입력하세요.", parent=win)
            entry_name.focus()
            return
            
        if not selected_params:
            messagebox.showwarning("경고", "추가할 파라미터를 선택하세요.", parent=win)
            return
        
        # 이름 중복 시 덮어쓰기 확인
        if name in custom_params or name in num_cols:
            if not messagebox.askyesno("이름 중복", 
                f"이미 '{name}' 이름이 존재합니다.\n덮어쓰시겠습니까?", parent=win):
                return
        
        # 조건 정보 저장 - 디버깅 추가
        param_conditions = {}
        all_conditions_valid = True
        
        print(f"\n=== 파라미터 '{name}' 조건 처리 ===")
        
        for param in selected_params:
            if param in condition_info:
                condition_var = condition_info[param]['condition_var']
                threshold_var = condition_info[param]['threshold_var']
                
                condition = condition_var.get()
                threshold = threshold_var.get().strip()
                
                print(f"  {param}: 조건='{condition}', Threshold='{threshold}'")
                
                # 조건이 있는데 threshold가 없는 경우만 오류
                if condition and condition != "이상" and not threshold:  # 기본값이 아닌 조건인데 threshold가 없는 경우
                    messagebox.showwarning("경고", f"'{param}'에 대한 조건을 설정하려면 Threshold 값을 입력해야 합니다.", parent=win)
                    all_conditions_valid = False
                    break
                
                # threshold가 있으면 조건 저장
                if threshold:
                    param_conditions[param] = {
                        'condition': condition,
                        'threshold': threshold
                    }
                    print(f"    -> 조건 저장됨")
                else:
                    print(f"    -> threshold 없음, 조건 무시")
            else:
                print(f"  {param}: condition_info에 없음")
        
        if not all_conditions_valid:
            return
        
        print(f"최종 저장될 조건들: {param_conditions}")
        print(f"결합 로직: {logic_var.get()}")
        
        # custom_params에 조건 정보와 함께 저장
        custom_params[name] = {
            'params': selected_params,
            'param_conditions': param_conditions,
            'logic': logic_var.get()
        }
        
        print(f"custom_params에 저장 완료: {custom_params[name]}")
        
        # --- 자주 쓰는 파라미터 섹션에 추가 ---
        # 기존 리스트에서 해당 이름 제거 (중복 방지)
        all_items = list(var_list.get(0, tk.END))
        if name in all_items:
            idx = all_items.index(name)
            var_list.delete(idx)
        
        # 자주 쓰는 파라미터 섹션 찾기
        frequent_header_idx = None
        other_header_idx = None
        for i, item in enumerate(var_list.get(0, tk.END)):
            if item == "------ 자주 쓰는 파라미터 ------":
                frequent_header_idx = i
            elif item == "------ 나머지 파라미터 ------":
                other_header_idx = i
                break
        
        # 자주 쓰는 파라미터 섹션에 추가
        if frequent_header_idx is not None:
            if other_header_idx is not None:
                # 나머지 파라미터 섹션이 있는 경우, 그 앞에 삽입
                var_list.insert(other_header_idx, name)
            else:
                # 나머지 파라미터 섹션이 없는 경우, 맨 끝에 추가
                var_list.insert(tk.END, name)
        else:
            # 자주 쓰는 파라미터 섹션이 없는 경우, 맨 끝에 추가
            var_list.insert(tk.END, name)
        
        # frequent_params 리스트에도 추가 (다음 실행 시 자동으로 자주 쓰는 파라미터에 포함)
        global frequent_params
        if name not in frequent_params:
            frequent_params.append(name)
        
        messagebox.showinfo("추가 완료", 
            f"'{name}' 파라미터가 추가되었습니다.\n포함된 파라미터: {len(selected_params)}개", parent=win)
        win.destroy()

    def on_cancel():
        win.destroy()

    btn_cancel = ttk.Button(btn_frame, text="취소", command=on_cancel)
    btn_cancel.pack(side=tk.RIGHT, padx=(5, 0))
    
    btn_ok = ttk.Button(btn_frame, text="추가", command=on_ok)
    btn_ok.pack(side=tk.RIGHT)
    
    # 도움말 텍스트 업데이트
    help_text = ("• Ctrl+클릭: 개별 선택/해제  • Shift+클릭: 범위 선택  • Ctrl+A: 모든 항목 선택\n"
                "• >>> 선택 >>> 버튼 또는 더블클릭/Enter/Space키로 선택  • 검색은 실시간 적용")
    help_label = ttk.Label(btn_frame, text=help_text, font=('Arial', 8), foreground='gray')
    help_label.pack(side=tk.LEFT, anchor=tk.W)
    
    # 엔터키로 검색, 이름 입력 후 엔터키로 포커스 이동
    search_entry.bind('<Return>', lambda e: lb.focus())
    entry_name.bind('<Return>', lambda e: search_entry.focus())
    
    # 초기 포커스
    entry_name.focus()

# frequent_params 처리 부분 수정
frequent_params = [
    "Laser & EUV Power",  # 사용자 정의 파라미터
    "euvChamber_gas_euvCone_mfc_flow_value",
    "euvChamber_gas_laserCone_mfc_flow_value", 
    "euvChamber_gas_bearingUnit_mfc_flow_value",
    "euvChamber_pressure_value",
    "laser_power_value",
    "euvChamber_euvPower_value"
]

# "Laser & EUV Power" 사용자 정의 파라미터를 미리 등록 (조건 추가)
custom_params["Laser & EUV Power"] = {
    'params': ["laser_power_value", "euvChamber_euvPower_value"],
    'param_conditions': {
        "laser_power_value": {
            'condition': '초과',
            'threshold': '0'
        },
        "euvChamber_euvPower_value": {
            'condition': '초과', 
            'threshold': '0'
        }
    },  # 두 파워값 모두 0 초과 조건 설정
    'logic': 'AND'  # 두 조건을 모두 만족해야 함
}

# frequent_params 필터링 수정: custom_params도 포함
frequent_params_filtered = []
for param in frequent_params:
    if param in num_cols or param in custom_params:  # custom_params도 포함하도록 수정
        frequent_params_filtered.append(param)

# other_params에서는 사용자 정의 파라미터 제외
other_params = [c for c in num_cols if c not in frequent_params_filtered]

# 리스트박스에 추가
if frequent_params_filtered:
    var_list.insert(tk.END, "------ 자주 쓰는 파라미터 ------")
    for col in frequent_params_filtered:
        var_list.insert(tk.END, col)
if other_params:
    var_list.insert(tk.END, "------ 나머지 파라미터 ------")
    for col in other_params:
        var_list.insert(tk.END, col)

btn_add_param = ttk.Button(frame, text="파라미터 추가", command=add_custom_param)
btn_add_param.pack(pady=10)

# DB 파일 읽기 함수 (빠른 버전으로 복원)
def read_db_file(db_path, params_to_read, time_cols):
    import sqlite3, re, datetime
    conn = sqlite3.connect(db_path)
    try:
        pragma_df = pd.read_sql_query("PRAGMA table_info(data)", conn)
        available_cols = pragma_df['name'].tolist()
    except Exception as e:
        print(f"{db_path} 읽기 실패: {e}")
        conn.close()
        return None

    time_col = next((c for c in time_cols if c in available_cols), None)
    if time_col is None:
        conn.close()
        return None

    # 실제로 DB에 존재하는 컬럼만 조회하도록 필터링
    cols_in_db = [col for col in params_to_read if col in available_cols]
    if not cols_in_db:
        conn.close()
        return None
        
    query_cols = ', '.join([time_col] + cols_in_db)
    query = f"SELECT {query_cols} FROM data"
    
    try:
        df = pd.read_sql_query(query, conn)
        
        # 비수치형 컬럼을 수치형으로 변환 시도
        for col in cols_in_db:
            if col in df.columns and df[col].dtype == 'object':
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except Exception as e:
                    print(f"{col} 컬럼 변환 실패: {e}")  # 변환 실패 로그 추가
                    pass  # 변환 실패시 그대로 유지
                    
    except Exception as e:
        print(f"{db_path} 쿼리 실패: {e}")
        conn.close()
        return None
    
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", os.path.basename(db_path))
    if match:
        base_date = datetime.datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    else:
        base_date = datetime.datetime.now() # Fallback
        
    # 벡터화 변환 사용 (더 빠르고 안전함)
    df['datetime'] = convert_datetime_vectorized(df[time_col], base_date)
    return df

def read_db_file_with_plc_restoration(db_path, params_to_read, time_cols):
    import sqlite3, re, datetime
    conn = sqlite3.connect(db_path)
    try:
        pragma_df = pd.read_sql_query("PRAGMA table_info(data)", conn)
        available_cols = pragma_df['name'].tolist()
    except Exception as e:
        print(f"{db_path} 읽기 실패: {e}")
        conn.close()
        return None

    time_col = next((c for c in time_cols if c in available_cols), None)
    if time_col is None:
        conn.close()
        return None

    # PLC error 컬럼도 함께 읽기
    cols_in_db = [col for col in params_to_read if col in available_cols]
    if not cols_in_db:
        conn.close()
        return None
    
    # PLC error 컬럼 찾기
    plc_error_candidates = ['plc_connection_error', 'serverFault', 'fault']
    plc_error_col = None
    for candidate in plc_error_candidates:
        if candidate in available_cols:
            plc_error_col = candidate
            break
    
    # 쿼리할 컬럼 준비
    query_cols = [time_col] + cols_in_db
    if plc_error_col and plc_error_col not in query_cols:
        query_cols.append(plc_error_col)
    
    query = f"SELECT {', '.join(query_cols)} FROM data"
    
    try:
        df = pd.read_sql_query(query, conn)
        
        # 비수치형 컬럼을 수치형으로 변환 시도
        for col in cols_in_db:
            if col in df.columns and df[col].dtype == 'object':
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except:
                    pass
                    
    except Exception as e:
        print(f"{db_path} 쿼리 실패: {e}")
        conn.close()
        return None
    
    conn.close()
    
    # 날짜 추출 및 시간 변환 (벡터화 개선)
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", os.path.basename(db_path))
    if match:
        base_date = datetime.datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    else:
        base_date = datetime.datetime.now()
        
    # 벡터화 변환 사용 (더 빠르고 안전함)
    df['datetime'] = convert_datetime_vectorized(df[time_col], base_date)
    
    # === 고속 PLC error 기반 NaN 복원 ===
    if plc_error_col and plc_error_col in df.columns:
        print(f"PLC error 고속 복원 시작: {os.path.basename(db_path)}")
        
        # 1. PLC error 상태 벡터화 복원
        plc_raw = df[plc_error_col].copy()
        
        # 초기 상태 설정
        first_valid_idx = plc_raw.first_valid_index()
        initial_state = 0 if first_valid_idx is None else int(plc_raw.loc[first_valid_idx])
        
        # 벡터화된 에지 탐지 및 상태 복원
        plc_restored = plc_raw.copy()
        
        # 유효한 값들만 추출
        valid_mask = plc_raw.notna()
        valid_values = plc_raw[valid_mask]
        valid_indices = valid_values.index
        
        if len(valid_values) > 0:
            # 에지 탐지 (벡터화)
            prev_values = valid_values.shift(1).fillna(initial_state)
            edge_mask = valid_values != prev_values
            edges = valid_values[edge_mask]
            
            if len(edges) > 0:
                print(f"  탐지된 에지: {len(edges)}개")
                for idx, value in edges.items():
                    prev_val = int(prev_values.loc[idx])
                    curr_val = int(value)
                    if prev_val == 0 and curr_val == 1:
                        print(f"    라이징 에지 (0→1): {df['datetime'].loc[idx]}")
                    elif prev_val == 1 and curr_val == 0:
                        print(f"    폴링 에지 (1→0): {df['datetime'].loc[idx]}")
            
            # forward fill로 상태 전파 (매우 빠름!)
            plc_restored = plc_raw.fillna(method='ffill').fillna(initial_state).astype(int)
        else:
            plc_restored = pd.Series(initial_state, index=plc_raw.index)
        
        df[plc_error_col] = plc_restored
        
        # 2. 각 파라미터의 고속 NaN 복원
        error_mask = plc_restored == 1  # 에러 마스크 (벡터)
        normal_mask = ~error_mask       # 정상 마스크 (벡터)
        
        for param in cols_in_db:
            if param in df.columns and param != plc_error_col:
                original_nan_count = df[param].isna().sum()
                
                if original_nan_count > 0:
                    # 벡터화된 복원
                    param_values = df[param].copy()
                    
                    # 정상 구간에서만 forward fill 적용 (매우 빠름!)
                    # 에러 구간은 NaN으로 마스킹
                    param_values[error_mask] = np.nan
                    
                    # 정상 구간에서만 forward fill
                    for i in range(len(df)):
                        if normal_mask.iloc[i] and pd.isna(param_values.iloc[i]):
                            if i > 0 and pd.notna(param_values.iloc[i-1]):
                                param_values.iloc[i] = param_values.iloc[i-1]
                    
                    # 또는 더 빠른 방법: groupby 사용
                    # 에러 구간별로 그룹을 나누어 각 그룹 내에서만 ffill
                    
                    df[param] = param_values
                    
                    restored_nan_count = df[param].isna().sum()
                    restored_count = original_nan_count - restored_nan_count
                    
                    if restored_count > 0:
                        print(f"  {param}: {original_nan_count} -> {restored_nan_count} NaN "
                              f"({restored_count} 포인트 복원)")
        
        error_points = (plc_restored == 1).sum()
        print(f"  PLC error=1 구간: {error_points} 포인트 ({error_points/len(df)*100:.1f}%)")
    
    return df

# 더욱 고속화된 버전 (세그먼트 기반)
def read_db_file_with_plc_restoration_fast(db_path, params_to_read, time_cols):
    import sqlite3, re, datetime
    conn = sqlite3.connect(db_path)
    try:
        pragma_df = pd.read_sql_query("PRAGMA table_info(data)", conn)
        available_cols = pragma_df['name'].tolist()
    except Exception as e:
        print(f"{db_path} 읽기 실패: {e}")
        conn.close()
        return None

    time_col = next((c for c in time_cols if c in available_cols), None)
    if time_col is None:
        conn.close()
        return None

    cols_in_db = [col for col in params_to_read if col in available_cols]
    if not cols_in_db:
        conn.close()
        return None
    
    # PLC error 컬럼 찾기
    plc_error_candidates = ['plc_connection_error', 'serverFault', 'fault']
    plc_error_col = None
    for candidate in plc_error_candidates:
        if candidate in available_cols:
            plc_error_col = candidate
            break
    
    query_cols = [time_col] + cols_in_db
    if plc_error_col and plc_error_col not in query_cols:
        query_cols.append(plc_error_col)
    
    query = f"SELECT {', '.join(query_cols)} FROM data"
    
    try:
        df = pd.read_sql_query(query, conn)
        for col in cols_in_db:
            if col in df.columns and df[col].dtype == 'object':
                df[col] = pd.to_numeric(df[col], errors='coerce')
    except Exception as e:
        print(f"{db_path} 쿼리 실패: {e}")
        conn.close()
        return None
    
    conn.close()
    
    # 시간 변환 (벡터화 개선)
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", os.path.basename(db_path))
    if match:
        base_date = datetime.datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    else:
        base_date = datetime.datetime.now()
        
    # 벡터화 변환 사용 (더 빠르고 안전함)
    df['datetime'] = convert_datetime_vectorized(df[time_col], base_date)
    
    # === 초고속 세그먼트 기반 복원 ===
    if plc_error_col and plc_error_col in df.columns:
        print(f"PLC error 초고속 복원 시작: {os.path.basename(db_path)}")
        
        # 1. PLC 상태 복원 (fillna 한 번만 사용)
        plc_raw = df[plc_error_col].copy()
        first_valid = plc_raw.first_valid_index()
        initial_state = 0 if first_valid is None else int(plc_raw.loc[first_valid])
        
        # 매우 빠른 forward fill
        plc_restored = plc_raw.fillna(method='ffill').fillna(initial_state).astype(int)
        df[plc_error_col] = plc_restored
        
        # 2. 에러 구간 찾기 (벡터화)
        error_mask = plc_restored == 1
        
        # 3. 세그먼트 기반 복원 (매우 빠름!)
        # 에러 구간 변화점 찾기
        error_diff = error_mask.astype(int).diff().fillna(0)
        error_start_indices = df.index[error_diff == 1].tolist()  # 에러 시작점
        error_end_indices = df.index[error_diff == -1].tolist()   # 에러 종료점
        
        # 정상 구간 세그먼트 정의
        segments = []
        prev_end = 0
        
        for start_idx in error_start_indices:
            if start_idx > prev_end:
                segments.append((prev_end, start_idx - 1))
            # 해당 에러의 종료점 찾기
            end_idx = next((end for end in error_end_indices if end > start_idx), len(df) - 1)
            prev_end = end_idx + 1
        
        # 마지막 세그먼트
        if prev_end < len(df):
            segments.append((prev_end, len(df) - 1))
        
        # 4. 각 정상 세그먼트에서만 빠른 forward fill
        for param in cols_in_db:
            if param in df.columns and param != plc_error_col:
                original_nan_count = df[param].isna().sum()
                
                if original_nan_count > 0:
                    # 세그먼트별 forward fill (매우 빠름!)
                    for start_idx, end_idx in segments:
                        if start_idx <= end_idx:
                            segment_data = df[param].iloc[start_idx:end_idx+1]
                            filled_segment = segment_data.fillna(method='ffill')
                            df.loc[df.index[start_idx:end_idx+1], param] = filled_segment
                    
                    restored_nan_count = df[param].isna().sum()
                    restored_count = original_nan_count - restored_nan_count
                    
                    if restored_count > 0:
                        print(f"  {param}: {restored_count} 포인트 복원")
        
        print(f"  처리 완료: {len(segments)}개 정상 세그먼트")
        print(f"  PLC error 구간: {error_mask.sum()} 포인트")
    
    return df

# 기존 함수를 고속 버전으로 교체
read_db_file_with_plc_restoration = read_db_file_with_plc_restoration_fast

# onselect 함수를 원래대로 복원
def onselect(xmin, xmax):
    dt_min = mdates.num2date(xmin).replace(tzinfo=None)
    dt_max = mdates.num2date(xmax).replace(tzinfo=None)
    df_sel = df_all[(df_all['datetime'] >= dt_min) & (df_all['datetime'] <= dt_max)]
    
    if len(df_sel) < 2:
        plt.pause(0.01)
        messagebox.showinfo("선택 구간 정보", "선택 구간 내 데이터가 부족합니다.")
        return

    first_time = df_sel['datetime'].iloc[0]
    last_time = df_sel['datetime'].iloc[-1]
    delta_sec = abs((last_time - first_time).total_seconds())
    
    msg = (
        f"선택 구간 내 첫 포인트: {first_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"선택 구간 내 마지막 포인트: {last_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"선택 구간 내 시간 차이: {delta_sec:.2f}초"
    )
    
    if yvar == "Laser & EUV Power":
        # laser_power_value 컬럼이 있는지 확인
        if 'laser_power_value' not in df_sel.columns or df_sel['laser_power_value'].isna().all():
            messagebox.showinfo("선택 구간 정보", msg + "\n\n레이저 파워 데이터가 없어 샷수 계산을 할 수 없습니다.")
            return
            
        # 연속적인 레이저 파워 구간만 찾기
        df_laser = df_sel[df_sel['laser_power_value'].notnull()].copy()
        if len(df_laser) < 2:
            messagebox.showinfo("선택 구간 정보", msg + "\n\n유효한 레이저 파워 데이터가 부족합니다.")
            return
        
        # 시간 간격이 너무 큰 구간 제외 (5초 이상 간격이 있으면 연속성이 깨진 것으로 판단)
        df_laser = df_laser.sort_values('datetime').reset_index(drop=True)
        time_diffs = df_laser['datetime'].diff().dt.total_seconds()
        
        # 연속적인 구간들 찾기
        continuous_segments = []
        current_segment = []
        
        for i, row in df_laser.iterrows():
            if i == 0 or time_diffs.iloc[i] <= 5.0:  # 5초 이하 간격이면 연속으로 판단
                current_segment.append(i)
            else:
                if len(current_segment) >= 10:  # 최소 10개 포인트 이상인 구간만 유효
                    continuous_segments.append(current_segment)
                current_segment = [i]
        
        # 마지막 구간 처리
        if len(current_segment) >= 10:
            continuous_segments.append(current_segment)
        
        if not continuous_segments:
            messagebox.showinfo("선택 구간 정보", 
                msg + "\n\n연속적인 레이저 파워 구간이 없습니다.\n" +
                "(최소 10개 포인트, 5초 이하 간격 필요)")
            return
        
        # 모든 연속 구간의 적분값을 합계
        total_E_nominal = 0
        total_E_low = 0
        total_E_high = 0
        segment_info = []
        all_markers = []
        
        for segment_idx, segment in enumerate(continuous_segments):
            df_segment = df_laser.iloc[segment].copy()
            
            # 구간 정보 기록 - 년월일 정보 포함
            segment_start = df_segment['datetime'].iloc[0]
            segment_end = df_segment['datetime'].iloc[-1]
            segment_duration = (segment_end - segment_start).total_seconds()
            segment_info.append({
                'start': segment_start,
                'end': segment_end,
                'duration': segment_duration,
                'points': len(df_segment)
            })
            
            t = (df_segment['datetime'] - df_segment['datetime'].iloc[0]).dt.total_seconds().values
            p = df_segment['laser_power_value'].values
            
            # NaN 값 제거 (이중 체크)
            valid_mask = ~np.isnan(p)
            if valid_mask.sum() < 2:
                continue  # 이 구간은 건너뛰기
            
            t = t[valid_mask]
            p = p[valid_mask]
            
            # 이 구간의 적분 계산
            E_segment = np.trapz(p, t)
            dt_intervals = np.diff(t)
            E_seg_low = 0
            E_seg_high = 0
            
            for i in range(len(dt_intervals)):
                dt_i = dt_intervals[i]
                x_val = p[i]
                y_val = p[i+1]
                E_low_part = (0.8 * x_val + 0.2 * y_val) * dt_i
                E_high_part = (0.2 * x_val + 0.8 * y_val) * dt_i
                E_seg_low += E_low_part
                E_seg_high += E_high_part
            
            # 전체 합계에 추가
            total_E_nominal += E_segment
            total_E_low += E_seg_low
            total_E_high += E_seg_high
            
            # 구간별 마커 추가
            try:
                marker_start = ax1.scatter(segment_start, df_segment['laser_power_value'].iloc[0], 
                                        color='green', s=80, marker='o', zorder=5)
                marker_end = ax1.scatter(segment_end, df_segment['laser_power_value'].iloc[-1], 
                                      color='red', s=80, marker='s', zorder=5)
                all_markers.extend([marker_start, marker_end])
                
                # 연속 구간 영역 하이라이트
                ax1.axvspan(segment_start, segment_end, alpha=0.1, color='green', zorder=1)
                
                if ax2 and 'euvChamber_euvPower_value' in df_segment.columns:
                    marker_euv_start = ax2.scatter(segment_start, df_segment['euvChamber_euvPower_value'].iloc[0], 
                                                 color='green', s=80, marker='o', zorder=5)
                    marker_euv_end = ax2.scatter(segment_end, df_segment['euvChamber_euvPower_value'].iloc[-1], 
                                               color='red', s=80, marker='s', zorder=5)
                    all_markers.extend([marker_euv_start, marker_euv_end])
            except Exception as e:
                print(f"구간 {segment_idx+1} 마커 추가 중 오류: {e}")
        
        # 샷수 계산
        shot_nominal = total_E_nominal / (5e-4)
        shot_low = total_E_low / (5e-4)
        shot_high = total_E_high / (5e-4)
        
        # 구간별 상세 정보 생성 - 년월일 정보 포함
        segment_details = ""
        total_duration = 0
        total_points = 0
        for i, info in enumerate(segment_info):
            # 시작과 끝 시간에 날짜와 시간을 모두 포함하여 표시
            start_datetime = info['start'].strftime('%Y-%m-%d %H:%M:%S')
            end_datetime = info['end'].strftime('%Y-%m-%d %H:%M:%S')
            segment_details += f"\n구간 {i+1}: {start_datetime} ~ {end_datetime} ({info['duration']:.1f}초, {info['points']}개 포인트)"
            
            total_duration += info['duration']
            total_points += info['points']
        
        # 전체 구간의 날짜 범위 계산
        all_dates = []
        for info in segment_info:
            start_date = info['start'].strftime('%Y-%m-%d')
            end_date = info['end'].strftime('%Y-%m-%d')
            if start_date not in all_dates:
                all_dates.append(start_date)
            if end_date not in all_dates:
                all_dates.append(end_date)
        
        all_dates.sort()
        if len(all_dates) == 1:
            date_range_text = f"날짜: {all_dates[0]}"
        else:
            date_range_text = f"날짜 범위: {all_dates[0]} ~ {all_dates[-1]} ({len(all_dates)}일간)"
        
        msg += (
            f"\n\n[연속 구간 분석 - 모든 구간 합계]"
            f"\n{date_range_text}"
            f"\n연속 구간 수: {len(continuous_segments)}개"
            f"\n총 연속 시간: {total_duration:.1f}초"
            f"\n총 포인트 수: {total_points}개"
            f"{segment_details}"
            f"\n\n[샷수 계산 결과 (전체 합계)]"
            f"\n적분 에너지: {total_E_nominal:.3e} J"
            f"\n계산된 샷 수: {shot_nominal:.2f}"
        )
        
        # 기존 마커 제거
        for artist in getattr(onselect, "markers", []):
            try:
                artist.remove()
            except:
                pass
        
        # 새 마커들 저장
        onselect.markers = all_markers
    
    else:
        # 단일 파라미터 분석 (20250825 기존 로직 유지)
        if yvar in df_sel.columns:
            param_data = df_sel[yvar].dropna()
            if len(param_data) > 1:
                time_diff = df_sel['datetime'].diff().dt.total_seconds().dropna()
                avg_interval = time_diff.mean()
                
                param_integral = param_data.mean() * delta_sec
                param_avg = param_data.mean()
                param_max = param_data.max()
                param_min = param_data.min()
                
                msg += f"\n\n{yvar}:\n"
                msg += f"  적분값: {param_integral:.3f} (단위·초)\n"
                msg += f"  평균값: {param_avg:.3f}\n"
                msg += f"  최대값: {param_max:.3f}\n"
                msg += f"  최소값: {param_min:.3f}\n"
                msg += f"  샷수 (데이터 포인트): {len(param_data)}개\n"
                msg += f"  평균 시간 간격: {avg_interval:.3f}초\n"
                msg += f"  연속 시간 간격: {delta_sec:.2f}초\n"
        
        elif yvar in custom_params:
            for param in custom_params[yvar]:
                if param in df_sel.columns:
                    param_data = df_sel[param].dropna()
                    if len(param_data) > 1:
                        param_integral = param_data.mean() * delta_sec
                        param_avg = param_data.mean()
                        
                        msg += f"\n{param}:\n"
                        msg += f"  적분값: {param_integral:.3f} (단위·초)\n"
                        msg += f"  평균값: {param_avg:.3f}\n"
                        msg += f"  샷수: {len(param_data)}개\n"
    
    # PLC error 정보 추가 (간단하게)
    plc_error_cols = ['plc_connection_error', 'serverFault', 'fault']
    plc_error_col = None
    for col in plc_error_cols:
        if col in df_sel.columns:
            plc_error_col = col
            break

    # 스크롤 가능한 정보 창 표시 (20250822 버전)
    def show_scrollable_info(title, message):
        info_window = tk.Toplevel()
        info_window.title(title)
        info_window.geometry("800x600")  # 창 크기 확대
        info_window.transient(root)
        info_window.grab_set()
        
        # 메인 프레임
        main_frame = ttk.Frame(info_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 텍스트 위젯과 스크롤바가 있는 프레임
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # 텍스트 위젯 생성
        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=('Consolas', 10))
        
        # 세로 스크롤바
        v_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=v_scrollbar.set)
        
        # 가로 스크롤바
        h_scrollbar = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=text_widget.xview)
        text_widget.configure(xscrollcommand=h_scrollbar.set)
        
        # 레이아웃 설정
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 텍스트 삽입
        text_widget.insert(tk.END, message)
        text_widget.configure(state=tk.DISABLED)  # 읽기 전용으로 설정
        
        # 확인 버튼
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ok_button = ttk.Button(btn_frame, text="확인", command=info_window.destroy)
        ok_button.pack(side=tk.RIGHT)
        
        # 창을 화면 중앙에 배치
        info_window.update_idletasks()
        x = (info_window.winfo_screenwidth() // 2) - (info_window.winfo_width() // 2)
        y = (info_window.winfo_screenheight() // 2) - (info_window.winfo_height() // 2)
        info_window.geometry(f"+{x}+{y}")
        
        # 포커스 설정
        info_window.focus_set()
    
    show_scrollable_info("선택 구간 정보", msg)
    
    # 시간 축 포맷 재설정 (드래그 후 뒤틀림 방지)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.canvas.draw()

def is_cnt_related_data(db_path, params_to_read):
    """
    데이터베이스 파일이 CNT 관련 데이터를 포함하는지 확인
    Args:
        db_path: 데이터베이스 파일 경로
        params_to_read: 읽으려는 파라미터 목록
    Returns:
        bool: CNT 관련 데이터면 True, 아니면 False
    """
    # 파일명 기반 체크 (기존 로직)
    db_filename = os.path.basename(db_path).lower()
    if 'cnt' in db_filename or 'monitoring' in db_filename:
        return True
    
    # CNT 관련 파라미터명 패턴들
    cnt_patterns = [
        r'cnt\d*',  # cnt, cnt1, cnt2 등
        r'cn[a-z]\d*',  # cnA, cnB, cnC 등
        r'count\d*',  # count, count1, count2 등
        r'monitor\d*',  # monitor, monitor1 등
        r'sensor\d*cnt',  # sensor1cnt 등
    ]
    
    # 파라미터명에서 CNT 관련 패턴 체크
    for param in params_to_read:
        param_lower = param.lower()
        for pattern in cnt_patterns:
            if re.search(pattern, param_lower):
                print(f"CNT 관련 파라미터 발견: {param}")
                return True
    
    # 데이터베이스 테이블 구조 체크 (간단한 샘플링)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 목록 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table_name in tables:
            table = table_name[0]
            # 컬럼 목록 확인
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            
            for col_info in columns:
                col_name = col_info[1].lower()
                for pattern in cnt_patterns:
                    if re.search(pattern, col_name):
                        print(f"CNT 관련 컬럼 발견: {col_name} in table {table}")
                        conn.close()
                        return True
        
        conn.close()
        
    except Exception as e:
        print(f"데이터베이스 구조 체크 실패 {db_path}: {e}")
    
    return False

# plot_selected 함수의 사용자 정의 파라미터 부분 수정
def plot_selected(event=None):
    global yvar, ax1, ax, df_all, ax2, all_axes
    
    all_dfs = []
    sel = var_list.curselection()
    if not sel:
        return
    yvar = var_list.get(sel[0])
    
    # 헤더 항목 체크
    if yvar.startswith("------"):
        return

    print(f"선택된 파라미터: {yvar}")

    if yvar in custom_params:
        param_info = custom_params[yvar]
        print(f"사용자 정의 파라미터 정보: {param_info}")
        params_to_read = param_info['params']
    elif yvar == "Laser & EUV Power":
        params_to_read = ["laser_power_value", "euvChamber_euvPower_value"]
    else:
        params_to_read = [yvar]

    print(f"읽을 파라미터들: {params_to_read}")

    # PLC error 기반 복원된 데이터 로드
    # 파라미터 분석에서는 CNT 모니터링 데이터 제외
    for db_path in db_files:
        # CNT 관련 데이터 제외 (개선된 로직)
        if is_cnt_related_data(db_path, params_to_read):
            print(f"CNT 관련 데이터 제외: {os.path.basename(db_path)}")
            continue
            
        df = read_db_file_with_plc_restoration(db_path, params_to_read, time_cols)
        if df is not None:
            all_dfs.append(df)
            print(f"성공: {os.path.basename(db_path)} - {len(df)} 행")
        else:
            print(f"실패: {os.path.basename(db_path)}")
    
    if not all_dfs:
        messagebox.showwarning("경고", "적합한 데이터가 없습니다.")
        return

    df_all = pd.concat(all_dfs, ignore_index=True)
    df_all['datetime'] = pd.to_datetime(df_all['datetime'])
    df_all = df_all.sort_values('datetime').reset_index(drop=True)

    print(f"통합 데이터: {len(df_all)} 행")
    print(f"컬럼들: {list(df_all.columns)}")

    # 조건 적용 (custom_params에 정의된 경우)
    if yvar in custom_params:
        param_info = custom_params[yvar]
        param_conditions = param_info.get('param_conditions', {})
        logic = param_info.get('logic', 'AND')
        
        print(f"적용할 조건들: {param_conditions}")
        print(f"결합 로직: {logic}")
        
        # 필터링 마스크 초기화
        combined_mask = None
        
        for param, condition_data in param_conditions.items():
            condition = condition_data.get('condition', '')
            threshold = condition_data.get('threshold', '')
            
            print(f"처리 중인 조건: {param} - {condition} {threshold}")
            
            if condition and threshold and param in df_all.columns:
                try:
                    threshold_value = float(threshold)
                    
                    # 조건에 따라 마스크 생성
                    if condition == "이상":
                        mask = df_all[param] >= threshold_value
                    elif condition == "이하":
                        mask = df_all[param] <= threshold_value
                    elif condition == "초과":
                        mask = df_all[param] > threshold_value
                    elif condition == "미만":
                        mask = df_all[param] < threshold_value
                    elif condition == "같음":
                        mask = df_all[param] == threshold_value
                    elif condition == "다름":
                        mask = df_all[param] != threshold_value
                    else:
                        mask = pd.Series([True] * len(df_all), index=df_all.index)
                    
                    print(f"조건 적용 결과: {param} - {condition} {threshold} -> {mask.sum()}개 데이터 포인트 만족")
                    
                    # AND/OR 로직에 따라 마스크 결합
                    if combined_mask is None:
                        combined_mask = mask
                        print(f"첫 번째 조건 설정: {combined_mask.sum()}개 포인트")
                    elif logic == "AND":
                        combined_mask = combined_mask & mask
                        print(f"AND 결합 후: {combined_mask.sum()}개 포인트")
                    elif logic == "OR":
                        combined_mask = combined_mask | mask
                        print(f"OR 결합 후: {combined_mask.sum()}개 포인트")
                    
                except ValueError:
                    messagebox.showerror("오류", f"Threshold 값은 숫자로 입력해야 합니다: {threshold}")
                    return
            elif param not in df_all.columns:
                print(f"경고: 파라미터 '{param}'이 데이터에 없습니다.")
            elif not condition or not threshold:
                print(f"조건이나 threshold가 비어있음: {param} - '{condition}' '{threshold}'")
        
        # 최종 마스크 적용
        if combined_mask is not None:
            original_count = len(df_all)
            df_all = df_all[combined_mask].copy()
            print(f"조건 필터링 결과: {original_count} -> {len(df_all)} 포인트")
            
            if len(df_all) == 0:
                messagebox.showwarning("경고", "조건을 만족하는 데이터가 없습니다.")
                return
        else:
            print("적용된 조건이 없습니다.")
    
    # x축 데이터 설정 (조건 필터링 후)
    x = df_all['datetime']
    print(f"X축 데이터 확인: {len(x)} 포인트, 범위: {x.min()} ~ {x.max()}")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax2 = None
    all_axes = [ax]

    if yvar == "Laser & EUV Power":
        # "Laser & EUV Power" Scatter 플롯 처리 (수정됨)
        print("Laser & EUV Power Scatter 플롯 처리 시작")
        
        # 두 파라미터가 모두 존재하는지 확인
        required_params = ["laser_power_value", "euvChamber_euvPower_value"]
        available_params = [p for p in required_params if p in df_all.columns]
        
        print(f"필요한 파라미터: {required_params}")
        print(f"사용 가능한 파라미터: {available_params}")
        
        if len(available_params) == 0:
            messagebox.showwarning("경고", "Laser Power와 EUV Power 데이터가 모두 없습니다.")
            return
        
        # 첫 번째 축 (Laser Power) - 빨간색 Scatter
        ax1 = ax
        if "laser_power_value" in available_params:
            print(f"Laser Power Scatter 플롯: X축 길이={len(x)}, Y축 길이={len(df_all['laser_power_value'])}")
            scatter1 = ax1.scatter(x, df_all['laser_power_value'], 
                                 label='Laser Power', color='red', s=8, alpha=0.7)
            ax1.set_ylabel('Laser Power (W)', color='red')
            ax1.tick_params(axis='y', labelcolor='red')
            all_scatters = [scatter1]
            all_labels = ['Laser Power']
        else:
            # Laser Power가 없는 경우 더미 scatter
            scatter1 = ax1.scatter([], [], label='Laser Power (No Data)', 
                                 color='red', alpha=0.3, s=8)
            ax1.set_ylabel('Laser Power (No Data)', color='red')
            all_scatters = [scatter1]
            all_labels = ['Laser Power (No Data)']
        
        # 두 번째 축 (EUV Power) - 보라색 Scatter
        if "euvChamber_euvPower_value" in available_params:
            ax2 = ax1.twinx()
            print(f"EUV Power Scatter 플롯: X축 길이={len(x)}, Y축 길이={len(df_all['euvChamber_euvPower_value'])}")
            scatter2 = ax2.scatter(x, df_all['euvChamber_euvPower_value'], 
                                 label='EUV Power', color='purple', s=8, alpha=0.7)
            ax2.set_ylabel('EUV Power (W)', color='purple')
            ax2.tick_params(axis='y', labelcolor='purple')
            all_scatters.append(scatter2)
            all_labels.append('EUV Power')
            all_axes = [ax1, ax2]
        else:
            all_axes = [ax1]
        
        # 범례 추가 (scatter 객체 사용)
        legend_handles = []
        for i, (scatter_obj, label) in enumerate(zip(all_scatters, all_labels)):
            # scatter 객체에서 PathCollection을 가져와서 범례용 핸들 생성
            legend_handles.append(plt.Line2D([0], [0], marker='o', color='w', 
                                           markerfacecolor=scatter_obj.get_facecolors()[0] if len(scatter_obj.get_facecolors()) > 0 else 'gray',
                                           markersize=8, label=label))
        
        ax1.legend(handles=legend_handles, loc='upper left', bbox_to_anchor=(0, 1))
        
        plt.title(f"Laser & EUV Power vs Time (Scatter, 조건 필터링 적용, {len(df_all)} 포인트)")
        
    elif yvar in custom_params:
        # 사용자 정의 파라미터 처리 (기존 로직)
        param_info = custom_params[yvar]
        param_list = param_info['params']
        colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple', 'tab:brown', 'tab:pink', 'tab:gray']
        
        valid_params = [p for p in param_list if p in df_all.columns]
        print(f"유효한 파라미터들: {valid_params}")
        
        if len(valid_params) == 0:
            messagebox.showwarning("경고", "플롯할 수 있는 유효한 파라미터가 없습니다.")
            return
        
        if len(valid_params) > 0:
            ax1 = ax
            param = valid_params[0]
            
            print(f"첫 번째 파라미터 플롯: {param}, X축 길이: {len(x)}, Y축 길이: {len(df_all[param])}")
            line1 = ax1.plot(x, df_all[param], label=param, color=colors[0], linewidth=1.5)
            ax1.set_ylabel(param, color=colors[0])
            ax1.tick_params(axis='y', labelcolor=colors[0])
            
            axes_list = [ax1]
            all_lines = line1
            all_labels = [param]
            
            for i, param in enumerate(valid_params[1:], 1):
                if i == 1:
                    new_ax = ax1.twinx()
                else:
                    new_ax = ax1.twinx()
                    new_ax.spines['right'].set_position(('outward', 60 * (i-1)))
                
                print(f"추가 파라미터 플롯: {param}, X축 길이: {len(x)}, Y축 길이: {len(df_all[param])}")
                line = new_ax.plot(x, df_all[param], label=param, color=colors[i % len(colors)], linewidth=1.5)
                new_ax.set_ylabel(param, color=colors[i % len(colors)])
                new_ax.tick_params(axis='y', labelcolor=colors[i % len(colors)])
                
                axes_list.append(new_ax)
                all_lines.extend(line)
                all_labels.append(param)
            
            ax1.legend(all_lines, all_labels, loc='upper left', bbox_to_anchor=(0, 1))
            
            if len(valid_params) > 2:
                plt.subplots_adjust(right=0.7 - 0.05 * max(0, len(valid_params) - 3))
            
            all_axes = axes_list
            
            if len(axes_list) > 1:
                ax2 = axes_list[1]
        
        plt.title(f"{yvar} vs Time (조건 필터링 적용, {len(df_all)} 포인트)")
        
    else:
        # 단일 파라미터는 기존 로직 유지
        ax.plot(x, df_all[yvar])
        ax.set_ylabel(yvar)
        plt.title(f"{yvar} vs Time (PLC Error 기반 복원)")

    # PLC error 상태 표시
    plc_error_cols = ['plc_connection_error', 'serverFault', 'fault']
    plc_error_col = None
    for col in plc_error_cols:
        if col in df_all.columns:
            plc_error_col = col
            break
    
    if plc_error_col:
        error_mask = df_all[plc_error_col] == 1
        if error_mask.any():
            in_error = False
            error_start = None
            
            for time_val, is_error in zip(df_all['datetime'], error_mask):
                if is_error and not in_error:
                    error_start = time_val
                    in_error = True
                elif not is_error and in_error:
                    ax.axvspan(error_start, time_val, alpha=0.2, color='orange', label='PLC Error')
                    in_error = False
            
            if in_error:
                ax.axvspan(error_start, df_all['datetime'].iloc[-1], alpha=0.2, color='orange', label='PLC Error')
        
        print(f"PLC Error 구간 표시: {error_mask.sum()} 포인트")

    # x축 설정 및 포맷팅
    ax.set_xlabel("Time")
    ax.grid(True)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()
    fig.tight_layout()

    # 드래그 선택 기능
    span = SpanSelector(ax, onselect, 'horizontal', useblit=True, props=dict(alpha=0.3, facecolor='red'))

    # 기존의 스케일 버튼들
    from matplotlib.widgets import RadioButtons, Button
    radio_ax = fig.add_axes([0.05, 0.9, 0.15, 0.08])
    radio = RadioButtons(radio_ax, ('linear', 'log'), active=0)

    def set_scale(label):
        for axis in all_axes:
            try:
                axis.set_yscale(label)
            except Exception as e:
                print(f"축 스케일 변경 오류: {e}")
        fig.canvas.draw()

    radio.on_clicked(set_scale)

    # 저장 기능 수정
    def save_current_data():
        try:
            # 현재 표시된 축의 x축 범위 가져오기
            current_ax = None
            if yvar == "Laser & EUV Power":
                if 'ax1' in globals() and ax1 is not None:
                    current_ax = ax1
                    xlim = ax1.get_xlim()
                    print(f"Laser & EUV Power: ax1 xlim = {xlim}")
                else:
                    current_ax = ax
                    xlim = ax.get_xlim()
                    print(f"Laser & EUV Power (fallback): ax xlim = {xlim}")
            else:
                current_ax = ax
                xlim = ax.get_xlim()
                print(f"일반 플롯: ax xlim = {xlim}")
            
            # matplotlib의 날짜 숫자를 datetime으로 변환
            dt_min = mdates.num2date(xlim[0]).replace(tzinfo=None)
            dt_max = mdates.num2date(xlim[1]).replace(tzinfo=None)
            
            print(f"현재 화면 시간 범위: {dt_min} ~ {dt_max}")
            
            # 현재 화면에 표시된 시간 범위의 데이터만 필터링
            df_visible = df_all[(df_all['datetime'] >= dt_min) & (df_all['datetime'] <= dt_max)].copy()
            
            print(f"필터링된 데이터 포인트: {len(df_visible)}개 (전체: {len(df_all)}개)")
            
            if df_visible.empty:
                messagebox.showwarning("경고", "현재 화면에 표시된 데이터가 없습니다.")
                return
            
            # datetime을 문자열로 변환 (Excel/CSV 저장용)
            df_visible['datetime'] = df_visible['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # 파일명 생성 (안전한 문자로 변환)
            safe_filename = str(yvar).replace(' ', '_').replace('&', 'and').replace('/', '_')
            
            # 시간 범위를 파일명에 추가
            time_range_str = f"{dt_min.strftime('%Y%m%d_%H%M')}-{dt_max.strftime('%Y%m%d_%H%M')}"
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx")],
                title="현재 화면 데이터 저장",
                initialfile=f"{safe_filename}_{time_range_str}"
            )
            
            if not file_path:
                return
            
            # 파일 저장
            if file_path.lower().endswith('.xlsx'):
                df_visible.to_excel(file_path, index=False)
            else:
                df_visible.to_csv(file_path, index=False, encoding='utf-8-sig')
            
            # 저장 완료 메시지 (상세 정보 포함)
            messagebox.showinfo("저장 완료", 
                f"파일이 저장되었습니다:\n{file_path}\n\n"
                f"저장된 데이터: {len(df_visible)}개 포인트 (전체 {len(df_all)}개 중)\n"
                f"화면 시간 범위: {dt_min.strftime('%Y-%m-%d %H:%M:%S')} ~ {dt_max.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"파라미터: {yvar}")
                
        except Exception as e:
            print(f"저장 오류 상세: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("저장 오류", f"파일 저장 중 오류가 발생했습니다:\n{str(e)}")

    # 저장 버튼 생성
    save_ax = fig.add_axes([0.85, 0.02, 0.13, 0.04])
    save_btn = Button(save_ax, 'Save Data')
    save_btn.label.set_fontsize(9)
    save_btn.on_clicked(lambda x: save_current_data())
    
    # 날짜별 쪽지 버튼을 matplotlib 플롯 창에 생성 (플롯 데이터 날짜 범위에 맞춤)
    def create_date_note_buttons_in_plot():
        """현재 플롯된 데이터의 날짜 범위에 해당하는 로그 날짜만 쪽지 버튼으로 생성"""
        try:
            print("🔍 matplotlib 플롯 창 쪽지 버튼 생성 시작...")
            
            # 현재 플롯된 데이터의 날짜 범위 확인 (±30일 여유 범위 추가)
            if 'df_all' not in globals() or df_all.empty:
                print("❌ 플롯된 데이터가 없습니다.")
                return
                
            from datetime import timedelta
            plot_start_date = df_all['datetime'].min().date() - timedelta(days=30)
            plot_end_date = df_all['datetime'].max().date() + timedelta(days=30)
            print(f"📊 플롯 데이터 날짜 범위 (±30일): {plot_start_date} ~ {plot_end_date}")
            
            # WorkLogManager 인스턴스를 통해 로그 로드
            logs = work_log_manager.load_work_logs()
            print(f"📋 로드된 로그 개수: {len(logs) if logs else 0}")
            
            if not logs:
                print("❌ 로그가 없어서 쪽지 버튼을 생성하지 않습니다.")
                return

            # 날짜별로 로그 그룹화 (플롯 범위 내 날짜만)
            from collections import defaultdict
            import datetime
            logs_by_date = defaultdict(list)
            
            for i, log in enumerate(logs):
                print(f"🔍 로그 {i+1}: {log}")
                
                log_date_str = None
                if 'date' in log:
                    log_date_str = str(log['date'])
                    print(f"  📅 date 키에서 추출: {log_date_str}")
                elif 'timestamp' in log:
                    log_date_str = str(log['timestamp'])[:10]
                    print(f"  📅 timestamp 키에서 추출: {log_date_str}")
                else:
                    print(f"  ❌ 날짜 키를 찾을 수 없음: {list(log.keys())}")
                
                if log_date_str:
                    try:
                        log_date = datetime.datetime.strptime(log_date_str, '%Y-%m-%d').date()
                        print(f"  📅 변환된 날짜: {log_date}")
                        print(f"  📊 플롯 범위: {plot_start_date} ~ {plot_end_date}")
                        print(f"  ✅ 범위 체크: {plot_start_date} <= {log_date} <= {plot_end_date} = {plot_start_date <= log_date <= plot_end_date}")
                        
                        # 플롯 데이터 날짜 범위 내에 있는 로그만 포함
                        if plot_start_date <= log_date <= plot_end_date:
                            logs_by_date[log_date_str].append(log)
                            print(f"📅 플롯 범위 내 로그 발견: {log_date_str}")
                        else:
                            print(f"  ❌ 범위 외 로그: {log_date}")
                    except ValueError as e:
                        print(f"  ❌ 날짜 변환 오류: {e} - {log_date_str}")
                        continue
            
            sorted_dates = sorted(logs_by_date.keys())
            print(f"📅 플롯 범위 내 로그 날짜들: {sorted_dates}")
            
            if not sorted_dates:
                print("❌ 플롯 범위 내에 로그가 없습니다.")
                return
            
            print(f"📝 matplotlib 쪽지 버튼 생성 시작... (총 {min(len(sorted_dates), 8)}개)")
            
            # matplotlib 플롯 상단에 쪽지 버튼들 배치 (Linear/Log 버튼 위쪽)
            button_width = 0.08
            button_height = 0.035
            start_x = 0.1
            y_pos = 0.96  # 더 위쪽으로 이동
            
            for i, date in enumerate(sorted_dates):
                if i >= 8:
                    break
                    
                x_pos = start_x + i * (button_width + 0.01)
                
                try:
                    # 쪽지 버튼 영역 생성
                    note_ax = fig.add_axes((x_pos, y_pos, button_width, button_height))
                    note_ax.set_facecolor('#ffffcc')  # 쪽지 노란색 배경
                    note_ax.set_xlim(0, 1)
                    note_ax.set_ylim(0, 1)
                    note_ax.axis('off')  # 축 숨기기
                    
                    # 쪽지 텍스트 추가
                    note_ax.text(0.5, 0.7, '📝', ha='center', va='center', fontsize=12)
                    note_ax.text(0.5, 0.3, f'{date[5:]}', ha='center', va='center', fontsize=8, weight='bold')
                    
                    # 테두리 추가
                    import matplotlib.patches as patches
                    rect = patches.Rectangle((0, 0), 1, 1, linewidth=1, edgecolor='#cccccc', facecolor='none')
                    note_ax.add_patch(rect)
                    
                    # 클릭 가능한 영역으로 만들기
                    note_ax.set_picker(True)
                    
                    # 각 버튼에 고유 ID 저장
                    note_ax._note_date = date
                    note_ax._note_logs = logs_by_date[date]
                    
                    print(f"✅ matplotlib 쪽지 버튼 생성 완료: {date}")
                    
                except Exception as btn_error:
                    print(f"❌ 버튼 생성 오류 ({date}): {btn_error}")
                    
            # 전역 클릭 이벤트 핸들러 추가
            def on_note_click(event):
                """쪽지 버튼 클릭 이벤트 처리"""
                if event.inaxes is not None:
                    # 클릭된 axes가 쪽지 버튼인지 확인
                    if hasattr(event.inaxes, '_note_date'):
                        date_key = event.inaxes._note_date
                        logs_for_date = event.inaxes._note_logs
                        print(f"📝 {date_key} 쪽지 클릭됨!")
                        show_work_log_messages_for_date(date_key, logs_for_date)
            
            # 클릭 이벤트 연결
            fig.canvas.mpl_connect('button_press_event', on_note_click)
            
            print(f"🎉 matplotlib 쪽지 버튼 생성 완료! 플롯 창 상단에 표시됩니다.")
        
        except Exception as e:
            print(f"matplotlib 쪽지 버튼 생성 오류: {e}")
    
    create_date_note_buttons_in_plot()
    
    plt.show()

def show_work_log_messages_for_date(date, logs_for_date):
    """특정 날짜의 작업 로그 메시지를 보여주는 함수"""
    try:
        if not logs_for_date:
            messagebox.showinfo("로그 정보", f"{date}에 등록된 작업 로그가 없습니다.")
            return
        
        # 새 창 생성
        log_view_win = tk.Toplevel()
        log_view_win.title(f"작업 로그 - {date}")
        log_view_win.geometry("800x500")
        log_view_win.resizable(True, True)
        
        # 메인 프레임
        main_frame = ttk.Frame(log_view_win, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 제목
        title_label = ttk.Label(main_frame, text=f"📝 {date} 작업 로그", 
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 15))
        
        # 트리뷰 프레임
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 트리뷰 위젯 생성
        columns = ('시간', '카테고리', '메시지')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        # 컬럼 헤더 설정
        tree.heading('시간', text='시간')
        tree.heading('카테고리', text='카테고리')
        tree.heading('메시지', text='작업 내용')
        
        # 컬럼 너비 설정
        tree.column('시간', width=80, minwidth=80)
        tree.column('카테고리', width=120, minwidth=100)
        tree.column('메시지', width=400, minwidth=200)
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # 트리뷰와 스크롤바 배치
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 카테고리별 색상 정의
        category_colors = {
            'Li-Ag 충전': '#ffcccc',    # 연한 빨강
            'IR Align': '#ccccff',      # 연한 파랑
            'EUV Align': '#ccffcc',     # 연한 초록
            '기타 장비 점검': '#ffccff'  # 연한 보라
        }
        
        # 태그 설정
        for category, color in category_colors.items():
            tree.tag_configure(category, background=color)
        
        # 로그 데이터 추가 (시간순 정렬) - timestamp 키 사용
        sorted_logs = sorted(logs_for_date, key=lambda x: x.get('timestamp', x.get('date', '')))
        
        for log in sorted_logs:
            # timestamp에서 시간 부분 추출, 없으면 빈 문자열
            timestamp = log.get('timestamp', '')
            if len(timestamp) >= 16:
                time_part = timestamp[11:16]  # HH:MM 형식
            else:
                time_part = ''
                
            category = log.get('category', '알 수 없음')
            message = log.get('content', '')  # WorkLogManager에서는 'content' 키 사용
            
            # 태그는 카테고리명으로 설정
            tag = category if category in category_colors else ''
            
            tree.insert('', tk.END, 
                       values=(time_part, category, message),
                       tags=(tag,))
        
        # 통계 정보
        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(fill=tk.X, pady=(10, 0))
        
        total_logs = len(logs_for_date)
        category_counts = {}
        for log in logs_for_date:
            cat = log['category']
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        stats_text = f"총 {total_logs}개 로그 | "
        for cat, count in category_counts.items():
            stats_text += f"{cat}: {count}개  "
        
        stats_label = ttk.Label(stats_frame, text=stats_text, 
                               font=('Arial', 9), foreground='gray')
        stats_label.pack()
        
        # 닫기 버튼
        close_btn = ttk.Button(main_frame, text="닫기", 
                              command=log_view_win.destroy)
        close_btn.pack(pady=(10, 0))
        
        # 창 중앙 배치
        log_view_win.transient()
        log_view_win.grab_set()
        
    except Exception as e:
        messagebox.showerror("오류", f"로그 표시 중 오류가 발생했습니다:\n{e}")
        print(f"로그 표시 오류: {e}")

def show_work_log_messages():
    """작업 로그 메시지를 보여주는 함수"""
    try:
        # WorkLogManager를 통해 로그 데이터 가져오기
        logs = work_log_manager.load_work_logs()
        
        if not logs:
            messagebox.showinfo("로그 정보", "등록된 작업 로그가 없습니다.")
            return
        
        # 새 창 생성
        log_view_win = tk.Toplevel()
        log_view_win.title("작업 로그 메시지 보기")
        log_view_win.geometry("800x600")
        
        # 메인 프레임
        main_frame = ttk.Frame(log_view_win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 상단 정보
        info_label = ttk.Label(main_frame, text=f"총 {len(logs)}개의 작업 로그", font=('Arial', 12, 'bold'))
        info_label.pack(pady=(0, 10))
        
        # 로그 목록 프레임
        list_frame = ttk.LabelFrame(main_frame, text="작업 로그 목록", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview 생성
        columns = ('날짜', '카테고리', '내용 미리보기')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        # 컬럼 설정
        tree.heading('날짜', text='날짜')
        tree.heading('카테고리', text='카테고리')
        tree.heading('내용 미리보기', text='작업 내용')
        
        tree.column('날짜', width=120)
        tree.column('카테고리', width=150)
        tree.column('내용 미리보기', width=400)
        
        # 스크롤바
        v_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 그리드 배치
        tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # 데이터 삽입 (최신순으로 정렬)
        logs_sorted = sorted(logs, key=lambda x: x['date'], reverse=True)
        for log in logs_sorted:
            # 내용 미리보기 (첫 50자)
            content_preview = log['content'][:50] + ('...' if len(log['content']) > 50 else '')
            
            tree.insert('', tk.END, values=(
                log['date'],
                log['category'],
                content_preview
            ))
        
        # 상세보기 기능
        def show_detail(event):
            selection = tree.selection()
            if not selection:
                return
                
            item = tree.item(selection[0])
            values = item['values']
            
            # 해당 로그 찾기
            selected_log = None
            for log in logs_sorted:
                if (log['date'] == values[0] and 
                    log['category'] == values[1]):
                    selected_log = log
                    break
            
            if not selected_log:
                return
            
            # 상세보기 창
            detail_win = tk.Toplevel(log_view_win)
            detail_win.title(f"작업 로그 상세 - {selected_log['date']}")
            detail_win.geometry("600x400")
            
            detail_frame = ttk.Frame(detail_win)
            detail_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 기본 정보
            info_frame = ttk.Frame(detail_frame)
            info_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(info_frame, text="날짜:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=(0, 10))
            ttk.Label(info_frame, text=selected_log['date']).grid(row=0, column=1, sticky='w')
            
            ttk.Label(info_frame, text="카테고리:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
            ttk.Label(info_frame, text=selected_log['category']).grid(row=1, column=1, sticky='w', pady=(5, 0))
            
            if 'timestamp' in selected_log:
                ttk.Label(info_frame, text="등록시간:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
                ttk.Label(info_frame, text=selected_log['timestamp']).grid(row=2, column=1, sticky='w', pady=(5, 0))
            
            # 작업 내용
            ttk.Label(detail_frame, text="작업 내용:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            
            content_frame = ttk.Frame(detail_frame)
            content_frame.pack(fill=tk.BOTH, expand=True)
            
            content_text = tk.Text(content_frame, wrap=tk.WORD, font=('Arial', 10))
            content_scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=content_text.yview)
            content_text.configure(yscrollcommand=content_scrollbar.set)
            
            content_text.insert(tk.END, selected_log['content'])
            content_text.config(state=tk.DISABLED)
            
            content_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 닫기 버튼
            close_btn = ttk.Button(detail_frame, text="닫기", command=detail_win.destroy)
            close_btn.pack(pady=(10, 0))
        
        tree.bind('<Double-1>', show_detail)
        
        # 하단 버튼
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        close_btn = ttk.Button(button_frame, text="닫기", command=log_view_win.destroy)
        close_btn.pack(side=tk.RIGHT)
        
        # 창 포커스
        log_view_win.focus_set()
        
    except Exception as e:
        messagebox.showerror("오류", f"로그 메시지를 불러오는 중 오류가 발생했습니다:\n{e}")

# Error Log 관리 기능 (모듈 사용)
def show_event_log():
    """Error Log 확인 창 표시 (error_log_manager 모듈 사용)"""
    try:
        # 현재 폴더를 data_folder로 설정
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # ErrorLogManager 인스턴스 생성
        error_manager = ErrorLogManager(parent_root=root, data_folder=current_dir)
        
        # Error Log 창 표시
        error_manager.show_error_log_window()
        
    except Exception as e:
        print(f"Error Log 창 표시 오류: {e}")
        messagebox.showerror("오류", f"Error Log 창을 표시할 수 없습니다: {str(e)}")

# 데이터 로딩 시작 - 이 부분을 제거하거나 주석 처리
# import threading
# thread = threading.Thread(target=load_data_thread)
# thread.daemon = True
# thread.start()

# Error log 확인 버튼 추가
btn_event_log = ttk.Button(frame, text="Error Log 확인", command=show_event_log)
btn_event_log.pack(pady=5)

# 플롯 버튼 추가
btn_plot = ttk.Button(frame, text="선택한 파라미터 플롯하기", command=plot_selected)
btn_plot.pack(pady=10)

# 탭 2: CNT 데이터 플롯 탭 추가
cnt_tab = ttk.Frame(notebook)
notebook.add(cnt_tab, text="CNT 데이터 플롯")

# CNT 데이터 플롯터 초기화
cnt_plotter = CNTDataPlotter(cnt_tab)

# 작업 로그 관리자 초기화
work_log_manager = WorkLogManager(root)

# 작업 로그 창 표시 함수 (WorkLogManager를 사용)
def show_work_log():
    """작업 로그 입력/관리 창 표시"""
    work_log_manager.show_work_log()

# 로그 입력 버튼 추가 (기존 버튼들 다음에)
btn_work_log = ttk.Button(frame, text="로그 입력", command=show_work_log)
btn_work_log.pack(pady=5)

# 작업 로그 관리자 초기화 완료 (work_log_manager에서 초기화 정보 출력됨)

print("tkinter 메인루프 시작")
root.mainloop()
print("프로그램 종료")