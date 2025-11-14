import sqlite3
import pandas as pd
try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None
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
from tkinter import colorchooser
import concurrent.futures
import json
from typing import Any, Optional
from work_log_calendar_view import open_work_log_calendar
try:
    from work_log_manager import WorkLogManager
except ImportError as exc:
    WorkLogManager = None  # type: ignore[assignment]
    print(f"WorkLogManager 모듈 로드 실패: {exc}")
from cnt_data_plotter import CNTDataPlotter
from error_log_manager import ErrorLogManager
from db_file import read_db_file, is_cnt_related_data
from db_file import convert_datetime_vectorized
from matplotlib import colors as mcolors
from matplotlib.lines import Line2D

print(f"Matplotlib 백엔드: {matplotlib.get_backend()}")  # 디버깅용

# 전역 dict로 사용자 정의 파라미터 관리
custom_params = {}
plot_artists = []
artist_legend_map = {}
artist_legend_text_map = {}
plot_scale_mode = 'linear'
artist_colors = {}
artist_labels = {}
color_popup = None


# 폴더/파일 선택 기능 추가
def select_folder():
    """DB 파일이 있는 폴더를 선택하는 함수"""
    folder_path = filedialog.askdirectory(
        title="DB 파일이 있는 폴더를 선택하세요",
        initialdir=os.path.dirname(os.path.abspath(__file__))  # 현재 스크립트 위치를 기본값으로
    )
    return folder_path


def select_db_files():
    """DB 파일을 직접 선택하는 함수"""
    file_paths = filedialog.askopenfilenames(
        title="불러올 DB 파일을 선택하세요",
        initialdir=os.path.dirname(os.path.abspath(__file__)),
        filetypes=[("SQLite DB 파일", "*.db"), ("모든 파일", "*.*")]
    )
    return list(file_paths)

# 1. 기본 폴더 및 파일 목록 설정
db_folder = os.path.dirname(os.path.abspath(__file__))
db_files = sorted(glob.glob(os.path.join(db_folder, "*.db")))
manual_file_selection = False

if not db_files:    
    temp_root = tk.Tk()
    temp_root.withdraw()
    messagebox.showerror("오류", f"선택한 폴더에 DB 파일이 없습니다.\n폴더: {db_folder}")
    temp_root.destroy()
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

# 폴더/파일 선택 영역 UI 구성
folder_frame = ttk.Frame(frame)
folder_frame.pack(fill=tk.X, pady=(0, 10))
folder_frame.columnconfigure(0, weight=1)

folder_label = ttk.Label(folder_frame, text=f"현재 폴더: {db_folder}", font=('Arial', 9), foreground='gray')
folder_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

file_selection_var = tk.StringVar(value=f"폴더 내 DB 사용: {len(db_files)}개 파일")
file_status_label = ttk.Label(folder_frame, textvariable=file_selection_var, font=('Arial', 9), foreground='gray')
file_status_label.grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(2, 0))

button_column = ttk.Frame(folder_frame)
button_column.grid(row=0, column=1, rowspan=2, sticky=tk.E)


def apply_new_data_source(new_folder: str, new_files: list[str], mode: str) -> bool:
    """선택된 폴더/파일 정보로 전역 상태와 UI를 갱신합니다."""
    global db_folder, db_files, df_sample, num_cols, time_cols, all_available_cols, numeric_cols, non_numeric_cols, manual_file_selection

    if not new_files:
        messagebox.showerror("오류", "선택한 경로에 DB 파일이 없습니다.")
        return False

    db_folder = new_folder
    db_files = new_files
    manual_file_selection = mode == "files"

    print(f"\n데이터 소스 변경: {db_folder}")
    print(f"사용할 DB 파일 수: {len(db_files)}")

    conn = sqlite3.connect(db_files[0])
    try:
        df_sample_local = pd.read_sql_query("SELECT * FROM data LIMIT 1", conn)
    except Exception as exc:
        conn.close()
        messagebox.showerror("오류", f"DB 읽기 실패: {exc}")
        return False
    conn.close()

    # 전역 메타데이터 갱신
    df_sample = df_sample_local
    time_cols = [c for c in df_sample.columns if c.lower() in ['time', 'timestamp', 'datetime']]
    exclude_cols = time_cols

    all_available_cols = [c for c in df_sample.columns if c not in exclude_cols]
    numeric_cols = [c for c in df_sample.select_dtypes(include=[np.number]).columns if c not in exclude_cols]
    non_numeric_cols = [c for c in all_available_cols if c not in numeric_cols]

    num_cols = numeric_cols.copy()
    for col in non_numeric_cols:
        try:
            sample_values = df_sample[col].dropna()
            if len(sample_values) > 0:
                pd.to_numeric(sample_values.iloc[0])
                num_cols.append(col)
        except (ValueError, TypeError, IndexError):
            continue

    if 'fault' in df_sample.columns and 'fault' not in num_cols:
        num_cols.append('fault')

    folder_label.config(text=f"현재 폴더: {db_folder}")
    if manual_file_selection:
        file_selection_var.set(f"수동 선택: {len(db_files)}개 파일")
    else:
        file_selection_var.set(f"폴더 내 DB 사용: {len(db_files)}개 파일")

    var_list.delete(0, tk.END)

    frequent_params_filtered = []
    for param in frequent_params:
        if param in num_cols or param in custom_params:
            frequent_params_filtered.append(param)

    other_params = [c for c in num_cols if c not in frequent_params_filtered]

    if frequent_params_filtered:
        var_list.insert(tk.END, "------ 자주 쓰는 파라미터 ------")
        for col in frequent_params_filtered:
            var_list.insert(tk.END, col)
    if other_params:
        var_list.insert(tk.END, "------ 나머지 파라미터 ------")
        for col in other_params:
            var_list.insert(tk.END, col)

    if mode == "folder":
        message = f"폴더가 변경되었습니다.\n\n폴더: {db_folder}\nDB 파일: {len(db_files)}개\n파라미터: {len(num_cols)}개"
    else:
        sample_names = [os.path.basename(path) for path in db_files[:5]]
        sample_text = "\n".join(sample_names)
        if len(db_files) > 5:
            sample_text += f"\n... 외 {len(db_files) - 5}개"
        message = (
            "파일 선택이 완료되었습니다.\n\n"
            f"선택한 폴더: {db_folder}\n"
            f"선택한 파일: {len(db_files)}개\n"
            f"예시 목록:\n{sample_text}"
        )

    messagebox.showinfo("완료", message)
    print(f"파라미터 리스트 새로고침 완료: {len(num_cols)}개")
    return True


def reload_folder():
    """폴더를 다시 선택하고 DB 파일 목록 및 파라미터 리스트를 새로고침"""
    new_folder = select_folder()
    if not new_folder:
        return

    temp_files = sorted(glob.glob(os.path.join(new_folder, "*.db")))
    if not temp_files:
        messagebox.showerror("오류", f"선택한 폴더에 DB 파일이 없습니다.\n폴더: {new_folder}")
        return

    apply_new_data_source(new_folder, temp_files, mode="folder")


def select_files_for_analysis():
    """분석에 사용할 DB 파일을 직접 선택합니다."""
    selected_files = select_db_files()
    if not selected_files:
        return

    base_dirs = {os.path.dirname(path) for path in selected_files}
    if len(base_dirs) > 1:
        messagebox.showerror("오류", "서로 다른 폴더의 파일은 동시에 선택할 수 없습니다.")
        return

    target_folder = base_dirs.pop() if base_dirs else db_folder
    apply_new_data_source(target_folder, sorted(selected_files), mode="files")


btn_select_folder = ttk.Button(button_column, text="📁 폴더 선택", command=reload_folder)
btn_select_folder.pack(fill=tk.X)

btn_select_files = ttk.Button(button_column, text="📄 파일 선택", command=select_files_for_analysis)
btn_select_files.pack(fill=tk.X, pady=(4, 0))

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


# onselect 함수는 db_file.py의 create_onselect_function_with_context를 사용
# 중복 코드는 db_file.py로 통합되어 제거됨


# plot_selected 함수의 사용자 정의 파라미터 부분 수정
def plot_selected(event=None):
    global yvar, ax1, ax, df_all, ax2, all_axes, plot_artists, artist_legend_map, plot_scale_mode, artist_colors, artist_labels, color_popup
    
    all_dfs = []
    plot_artists.clear()
    artist_legend_map.clear()
    artist_legend_text_map.clear()
    artist_colors.clear()
    artist_labels.clear()
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

    # 병렬로 여러 파일 읽기 (고속)
    from db_file import read_multiple_db_files_parallel, read_db_file_with_cache
    
    # 여러 파일이면 병렬 읽기 (ThreadPoolExecutor + Polars 병렬 처리), 단일 파일이면 캐싱 사용
    if len(db_files) > 1:
        print(f"⚡ 병렬 읽기 모드: {len(db_files)}개 파일")
        dfs_list = read_multiple_db_files_parallel(
            db_files, 
            params_to_read, 
            time_cols, 
            convert_datetime_vectorized,
            max_workers=None  # 자동 결정
        )
        # None이 아닌 결과만 필터링
        all_dfs = [df for df in dfs_list if df is not None]
    else:
        # 단일 파일은 캐싱 사용
        for db_path in db_files:
            # CNT 관련 데이터 제외 (개선된 로직)
            if is_cnt_related_data(db_path, params_to_read):
                print(f"CNT 관련 데이터 제외: {os.path.basename(db_path)}")
                continue
                
            df = read_db_file_with_cache(
                db_path, 
                params_to_read, 
                time_cols, 
                convert_datetime_vectorized,
                use_cache=True
            )
            if df is not None:
                all_dfs.append(df)
                print(f"성공: {os.path.basename(db_path)} - {len(df)} 행")
            else:
                print(f"실패: {os.path.basename(db_path)}")
    
    if not all_dfs:
        messagebox.showwarning("경고", "적합한 데이터가 없습니다.")
        return

    # Polars로 빠른 병합 (성능 향상)
    if POLARS_AVAILABLE and pl is not None and len(all_dfs) > 1:
        try:
            # pandas DataFrame을 Polars로 변환
            dfs_pl = [pl.from_pandas(df) for df in all_dfs]
            # Polars concat (더 빠름)
            df_all_pl = pl.concat(dfs_pl)
            # datetime 정렬
            df_all_pl = df_all_pl.sort('datetime')
            # pandas로 변환 (matplotlib 호환)
            df_all = df_all_pl.to_pandas()
        except Exception as e:
            print(f"Polars 병합 실패, pandas로 fallback: {e}")
            # fallback: pandas concat
            df_all = pd.concat(all_dfs, ignore_index=True)
            df_all['datetime'] = pd.to_datetime(df_all['datetime'])
            df_all = df_all.sort_values('datetime').reset_index(drop=True)
    else:
        # pandas 기반 병합
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
                    
                    # 조건에 따라 마스크 생성 (0 초과 조건은 부동소수 정밀도 이슈를 고려해 epsilon 추가)
                    epsilon = np.finfo(float).eps
                    if condition == "이상":
                        mask = df_all[param] >= threshold_value
                    elif condition == "이하":
                        mask = df_all[param] <= threshold_value
                    elif condition == "초과":
                        mask = df_all[param] > threshold_value + epsilon
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
        all_colors: list[str] = []

        if "laser_power_value" in available_params:
            print(f"Laser Power Scatter 플롯: X축 길이={len(x)}, Y축 길이={len(df_all['laser_power_value'])}")
            scatter1 = ax1.scatter(
                x,
                df_all['laser_power_value'],
                label='Laser Power',
                color='red',
                s=8,
                alpha=0.7,
                picker=True,
            )
            ax1.set_ylabel('Laser Power (W)', color='red')
            ax1.tick_params(axis='y', labelcolor='red')
            all_scatters = [scatter1]
            all_labels = ['Laser Power']
            hex_color = mcolors.to_hex('red')
            all_colors.append(hex_color)
            artist_colors[scatter1] = hex_color
            artist_labels[scatter1] = 'Laser Power'
        else:
            # Laser Power가 없는 경우 더미 scatter
            scatter1 = ax1.scatter([], [], label='Laser Power (No Data)', 
                                 color='red', alpha=0.3, s=8)
            ax1.set_ylabel('Laser Power (No Data)', color='red')
            all_scatters = [scatter1]
            all_labels = ['Laser Power (No Data)']
            hex_color = mcolors.to_hex('red')
            all_colors.append(hex_color)
            artist_colors[scatter1] = hex_color
            artist_labels[scatter1] = 'Laser Power (No Data)'
        
        # 두 번째 축 (EUV Power) - 보라색 Scatter
        if "euvChamber_euvPower_value" in available_params:
            ax2 = ax1.twinx()
            print(f"EUV Power Scatter 플롯: X축 길이={len(x)}, Y축 길이={len(df_all['euvChamber_euvPower_value'])}")
            scatter2 = ax2.scatter(
                x,
                df_all['euvChamber_euvPower_value'],
                label='EUV Power',
                color='purple',
                s=8,
                alpha=0.7,
                picker=True,
            )
            ax2.set_ylabel('EUV Power (W)', color='purple')
            ax2.tick_params(axis='y', labelcolor='purple')
            all_scatters.append(scatter2)
            all_labels.append('EUV Power')
            hex_color = mcolors.to_hex('purple')
            all_colors.append(hex_color)
            artist_colors[scatter2] = hex_color
            artist_labels[scatter2] = 'EUV Power'
            all_axes = [ax1, ax2]
        else:
            all_axes = [ax1]
        
        # 범례 추가 (scatter 객체 사용)
        legend_handles = []
        scatter_handle_pairs = []
        for scatter_obj, label, face_color in zip(all_scatters, all_labels, all_colors):
            legend_item = Line2D(
                [0],
                [0],
                marker='o',
                color=face_color,
                markerfacecolor=face_color,
                markeredgecolor=face_color,
                markersize=8,
                label=label,
            )
            legend_handles.append(legend_item)
            scatter_handle_pairs.append((scatter_obj, legend_item))
        
        legend = ax1.legend(handles=legend_handles, loc='upper left', bbox_to_anchor=(0, 1))
        legend_texts = legend.get_texts()
        for (scatter_obj, legend_handle), text in zip(scatter_handle_pairs, legend_texts):
            artist_legend_map[scatter_obj] = legend_handle
            artist_legend_text_map[scatter_obj] = text
            text.set_fontsize(text.get_fontsize() * 2)
            text.set_color(artist_colors.get(scatter_obj, '#000000'))
        
        plt.title(f"Laser & EUV Power vs Time (Scatter, 조건 필터링 적용, {len(df_all)} 포인트)")
        plot_artists.extend(all_scatters)
        
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
            line1 = ax1.plot(
                x,
                df_all[param],
                label=param,
                color=colors[0],
                linewidth=1.5,
                picker=5,
            )
            ax1.set_ylabel(param, color=colors[0])
            ax1.tick_params(axis='y', labelcolor=colors[0])
            
            axes_list = [ax1]
            all_lines = line1
            all_labels = [param]
            for created_line in line1:
                color_hex = mcolors.to_hex(created_line.get_color())
                artist_colors[created_line] = color_hex
                artist_labels[created_line] = param
            
            for i, param in enumerate(valid_params[1:], 1):
                if i == 1:
                    new_ax = ax1.twinx()
                else:
                    new_ax = ax1.twinx()
                    new_ax.spines['right'].set_position(('outward', 60 * (i-1)))
                
                print(f"추가 파라미터 플롯: {param}, X축 길이: {len(x)}, Y축 길이: {len(df_all[param])}")
                line = new_ax.plot(
                    x,
                    df_all[param],
                    label=param,
                    color=colors[i % len(colors)],
                    linewidth=1.5,
                    picker=5,
                )
                new_ax.set_ylabel(param, color=colors[i % len(colors)])
                new_ax.tick_params(axis='y', labelcolor=colors[i % len(colors)])
                
                axes_list.append(new_ax)
                all_lines.extend(line)
                all_labels.append(param)
                for created_line in line:
                    color_hex = mcolors.to_hex(created_line.get_color())
                    artist_colors[created_line] = color_hex
                    artist_labels[created_line] = param
            
            legend = ax1.legend(all_lines, all_labels, loc='upper left', bbox_to_anchor=(0, 1))
            legend_texts = legend.get_texts()
            for line_artist, text in zip(all_lines, legend_texts):
                artist_legend_map[line_artist] = line_artist
                artist_legend_text_map[line_artist] = text
                text.set_fontsize(text.get_fontsize() * 2)
                text.set_color(artist_colors.get(line_artist, '#000000'))
            
            if len(valid_params) > 2:
                plt.subplots_adjust(right=0.7 - 0.05 * max(0, len(valid_params) - 3))
            
            all_axes = axes_list
            
            if len(axes_list) > 1:
                ax2 = axes_list[1]
        
        plt.title(f"{yvar} vs Time (조건 필터링 적용, {len(df_all)} 포인트)")
        plot_artists.extend(all_lines)
        
    else:
        # 단일 파라미터는 기존 로직 유지
        single_lines = ax.plot(x, df_all[yvar], picker=5)
        for created_line in single_lines:
            color_hex = mcolors.to_hex(created_line.get_color())
            artist_colors[created_line] = color_hex
            artist_labels[created_line] = yvar
        plot_artists.extend(single_lines)
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
                    if error_start is not None:
                        ax.axvspan(error_start, time_val, alpha=0.2, color='orange', label='PLC Error')
                    in_error = False
            
            if in_error:
                if error_start is not None:
                    ax.axvspan(error_start, df_all['datetime'].iloc[-1], alpha=0.2, color='orange', label='PLC Error')
        
        print(f"PLC Error 구간 표시: {error_mask.sum()} 포인트")

    # x축 설정 및 포맷팅
    ax.set_xlabel("Time")
    ax.grid(True)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()
    fig.tight_layout()

    # 드래그 선택 기능 - Onselect_integral.py 모듈 사용
    from Onselect_integral import create_onselect_function_with_context
    # ax1, ax2 설정 (Laser & EUV Power의 경우 ax1이 ax이고 ax2는 twinx)
    onselect_func = create_onselect_function_with_context(root, custom_params, df_all, yvar, ax, fig, 
                                                          ax1=ax if yvar == "Laser & EUV Power" else None, 
                                                          ax2=ax2 if 'ax2' in locals() or 'ax2' in globals() else None)
    span = SpanSelector(ax, onselect_func, 'horizontal', useblit=True, props=dict(alpha=0.3, facecolor='red'))
    # SpanSelector 객체가 가비지 컬렉션으로 사라지지 않도록 figure에 참조를 보관
    setattr(fig, "_span_selector", span)

    from matplotlib.widgets import Button

    scale_var = tk.StringVar(master=root, value=plot_scale_mode)
    scale_popup = None

    def _double_size(value: float | int | str | None) -> float:
        if value is None:
            base = plt.rcParams.get('font.size', 10)
        elif isinstance(value, str):
            try:
                base = float(value)
            except ValueError:
                base = plt.rcParams.get('font.size', 10)
        else:
            base = float(value)
        return float(base) * 2

    def _double_axis_fonts():
        double_axis = [ax]
        if all_axes:
            double_axis = list(dict.fromkeys([ax] + all_axes))

        x_label = ax.xaxis.label
        x_label.set_fontsize(_double_size(x_label.get_fontsize()))
        for tick in ax.get_xticklabels():
            tick.set_fontsize(_double_size(tick.get_fontsize()))

        for axis in double_axis:
            y_label = axis.yaxis.label
            if y_label is not None:
                y_label.set_fontsize(_double_size(y_label.get_fontsize()))
            for tick in axis.get_yticklabels():
                tick.set_fontsize(_double_size(tick.get_fontsize()))

    def apply_scale():
        global plot_scale_mode
        mode = scale_var.get()
        for axis in all_axes:
            try:
                axis.set_yscale(mode)
            except Exception as exc:
                print(f"축 스케일 변경 오류: {exc}")
        plot_scale_mode = mode
        fig.canvas.draw_idle()

    def show_scale_popup():
        nonlocal scale_popup

        if scale_popup is not None and scale_popup.winfo_exists():
            scale_popup.focus_set()
            return

        scale_popup = tk.Toplevel(root)
        scale_popup.title("Y축 스케일 설정")
        scale_popup.geometry("260x140")
        scale_popup.resizable(False, False)

        ttk.Label(scale_popup, text="Y축 스케일을 선택하세요:", font=('Arial', 11)).pack(pady=(10, 5))

        ttk.Radiobutton(
            scale_popup,
            text="선형 (Linear)",
            variable=scale_var,
            value='linear',
            command=apply_scale,
        ).pack(anchor=tk.W, padx=15, pady=3)

        ttk.Radiobutton(
            scale_popup,
            text="로그 (Log)",
            variable=scale_var,
            value='log',
            command=apply_scale,
        ).pack(anchor=tk.W, padx=15, pady=3)

        def close_popup():
            nonlocal scale_popup
            if scale_popup is not None:
                scale_popup.destroy()
                scale_popup = None

        scale_popup.protocol("WM_DELETE_WINDOW", close_popup)

    def _extract_artist_color(artist) -> str:
        stored = artist_colors.get(artist)
        if stored:
            return stored
        try:
            if hasattr(artist, 'get_facecolor'):
                face_color = artist.get_facecolor()
                return mcolors.to_hex(face_color)
            if hasattr(artist, 'get_color'):
                return mcolors.to_hex(artist.get_color())
        except Exception as exc:  # pragma: no cover - 안전장치
            print(f"색상 추출 중 예외: {exc}")
        return '#1f77b4'

    def _update_artist_color(artist, new_color: str):
        if hasattr(artist, 'set_color'):
            try:
                artist.set_color(new_color)
            except Exception:
                pass
        if hasattr(artist, 'set_facecolor'):
            try:
                artist.set_facecolor(new_color)
            except Exception:
                pass
        if hasattr(artist, 'set_edgecolor'):
            try:
                artist.set_edgecolor(new_color)
            except Exception:
                pass

        legend_artist = artist_legend_map.get(artist)
        if legend_artist is not None:
            legend_artist.set_markerfacecolor(new_color)
            if hasattr(legend_artist, 'set_color'):
                try:
                    legend_artist.set_color(new_color)
                except Exception:
                    pass
            if hasattr(legend_artist, 'set_markeredgecolor'):
                try:
                    legend_artist.set_markeredgecolor(new_color)
                except Exception:
                    pass

        legend_text = artist_legend_text_map.get(artist)
        if legend_text is not None:
            legend_text.set_color(new_color)

        axis = getattr(artist, 'axes', None)
        if axis is not None:
            try:
                axis.yaxis.label.set색(new_color)
            except Exception:
                pass
            try:
                axis.tick_params(axis='y', colors=new_color)
            except Exception:
                pass

        artist_colors[artist] = new_color
        fig.canvas.draw_idle()

    color_popup_content: ttk.Frame | None = None

    def rebuild_color_popup():
        nonlocal color_popup_content
        global color_popup

        if color_popup is None or not color_popup.winfo_exists():
            return

        if color_popup_content is None or not color_popup_content.winfo_exists():
            color_popup_content = ttk.Frame(color_popup, padding=12)
            color_popup_content.pack(fill=tk.BOTH, expand=True)
        else:
            for child in color_popup_content.winfo_children():
                child.destroy()

        if not plot_artists:
            ttk.Label(color_popup_content, text="변경 가능한 플롯이 없습니다.").pack(pady=10)
            return

        for artist in plot_artists:
            label_text = artist_labels.get(artist, artist.get_label())
            row = ttk.Frame(color_popup_content)
            row.pack(fill=tk.X, pady=4)

            ttk.Label(row, text=label_text).pack(side=tk.LEFT, padx=(0, 6))
            swatch = tk.Label(row, width=6, relief="groove", background=_extract_artist_color(artist))
            swatch.pack(side=tk.LEFT, padx=(0, 10))

            def choose_color(a=artist, swatch_label=swatch):
                initial = _extract_artist_color(a)
                color_selection = colorchooser.askcolor(color=initial, title="색상 선택")
                if not color_selection or color_selection[1] is None:
                    return
                new_color = color_selection[1]
                _update_artist_color(a, new_color)
                swatch_label.configure(background=new_color)

            ttk.Button(row, text="색상 변경", command=choose_color).pack(side=tk.RIGHT)

    def open_color_popup():
        nonlocal color_popup_content
        global color_popup

        if color_popup is None or not color_popup.winfo_exists():
            color_popup = tk.Toplevel(root)
            color_popup.title("플롯 색상 설정")
            height_estimate = max(200, 90 + 40 * max(1, len(plot_artists)))
            color_popup.geometry(f"340x{height_estimate}")
            color_popup.resizable(False, True)

            def handle_close():
                nonlocal color_popup_content
                global color_popup
                if color_popup is not None:
                    color_popup.destroy()
                color_popup = None
                color_popup_content = None

            color_popup.protocol("WM_DELETE_WINDOW", handle_close)
            color_popup_content = None
        else:
            color_popup.deiconify()
            color_popup.focus_set()

        rebuild_color_popup()

    def on_key_press(event):
        if getattr(event, 'key', '') == 's':
            show_scale_popup()

    def on_figure_close(_):
        nonlocal scale_popup, color_popup_content
        global color_popup
        if scale_popup is not None and scale_popup.winfo_exists():
            scale_popup.destroy()
        scale_popup = None
        if color_popup is not None and color_popup.winfo_exists():
            color_popup.destroy()
        color_popup = None
        color_popup_content = None

    fig.canvas.mpl_connect('close_event', on_figure_close)
    fig.canvas.mpl_connect('key_press_event', on_key_press)

    _double_axis_fonts()
    apply_scale()
    open_color_popup()
    show_scale_popup()

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
            
            print(f"현재 화면 সময় 범위: {dt_min} ~ {dt_max}")
            
            # 현재 화면에 표시된 시간 범위의 데이터만 필터링
            # matplotlib 한계로 인해 경계 값이 살짝 잘리는 경우가 있어 여유 구간을 둔다.
            epsilon = pd.Timedelta(seconds=1)
            dt_min_adj = dt_min - epsilon
            dt_max_adj = dt_max + epsilon
            mask_visible = (df_all['datetime'] >= dt_min_adj) & (df_all['datetime'] <= dt_max_adj)

            if not mask_visible.any():
                # 여유 범위 내에 데이터가 없다면 가장 가까운 상한선을 사용해 재시도한다.
                nearest_max = df_all.loc[df_all['datetime'] >= dt_min, 'datetime'].max()
                if pd.notna(nearest_max):
                    mask_visible = (df_all['datetime'] >= dt_min_adj) & (df_all['datetime'] <= nearest_max)

            df_visible = df_all[mask_visible].copy()
            
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
        
        # 트리뷰와 스크्रोल바 배치
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
        manager = _create_work_log_manager()
        if manager is None:
            messagebox.showerror(
                "오류",
                "work_log_manager 모듈을 불러오지 못했습니다. PyQt5 설치 여부를 확인해주세요.",
            )
            return
        logs = manager.load_work_logs()
        
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

_work_log_manager_instance: Optional[Any] = None


def _create_work_log_manager() -> Optional[Any]:
    """WorkLogManager 인스턴스를 새로 생성한다."""
    global _work_log_manager_instance
    if WorkLogManager is None:
        return None
    _work_log_manager_instance = WorkLogManager(root)
    return _work_log_manager_instance


def show_work_log():
    """작업 로그 입력/관리 창 표시"""
    manager = _create_work_log_manager()
    if manager is None:
        messagebox.showerror(
            "오류",
            "work_log_manager 모듈을 불러오지 못했습니다. PyQt5 설치 여부를 확인해주세요.",
        )
        return
    manager.show_work_log()

# 로그 입력 버튼 추가 (기존 버튼들 다음에)
btn_work_log = ttk.Button(frame, text="로그 입력", command=show_work_log)
btn_work_log.pack(pady=5)

# 작업 로그 관리자 초기화 완료 (work_log_manager에서 초기화 정보 출력됨)

print("tkinter 메인루프 시작")
root.mainloop()
print("프로그램 종료")
