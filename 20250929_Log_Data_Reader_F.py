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
import concurrent.futures
import json
from work_log_manager import WorkLogManager
from cnt_data_plotter import CNTDataPlotter
from error_log_manager import ErrorLogManager
from db_file import read_db_file, is_cnt_related_data
from db_file import convert_datetime_vectorized

print(f"Matplotlib 백엔드: {matplotlib.get_backend()}")  # 디버깅용

# 전역 dict로 사용자 정의 파라미터 관리
custom_params = {}


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

# 폴더 선택 프레임 추가
folder_frame = ttk.Frame(frame)
folder_frame.pack(fill=tk.X, pady=(0, 10))

# 현재 폴더 표시 레이블
folder_label = ttk.Label(folder_frame, text=f"현재 폴더: {db_folder}", font=('Arial', 9), foreground='gray')
folder_label.pack(side=tk.LEFT, padx=(0, 10))

def reload_folder():
    """폴더를 다시 선택하고 DB 파일 목록 및 파라미터 리스트를 새로고침"""
    global db_folder, db_files, df_sample, num_cols, time_cols, all_available_cols, numeric_cols, non_numeric_cols
    
    # 새 폴더 선택
    new_folder = select_folder()
    if not new_folder:  # 사용자가 취소한 경우
        return
    
    # 폴더에 DB 파일이 있는지 확인
    temp_files = sorted(glob.glob(os.path.join(new_folder, "*.db")))
    if not temp_files:
        messagebox.showerror("오류", f"선택한 폴더에 DB 파일이 없습니다.\n폴더: {new_folder}")
        return
    
    # 전역 변수 업데이트
    db_folder = new_folder
    db_files = temp_files
    
    print(f"\n폴더 변경: {db_folder}")
    print(f"찾은 DB 파일 수: {len(db_files)}")
    
    # 첫 번째 DB에서 컬럼 목록 다시 추출
    conn = sqlite3.connect(db_files[0])
    try:
        df_sample = pd.read_sql_query("SELECT * FROM data LIMIT 1", conn)
    except Exception as e:
        conn.close()
        messagebox.showerror("오류", f"DB 읽기 실패: {e}")
        return
    conn.close()
    
    # 시간 컬럼 및 수치형 컬럼 재탐색
    time_cols = [c for c in df_sample.columns if c.lower() in ['time', 'timestamp', 'datetime']]
    exclude_cols = time_cols
    
    all_available_cols = [c for c in df_sample.columns if c not in exclude_cols]
    numeric_cols = [c for c in df_sample.select_dtypes(include=[np.number]).columns if c not in exclude_cols]
    non_numeric_cols = [c for c in all_available_cols if c not in numeric_cols]
    
    # num_cols 재생성
    num_cols = numeric_cols.copy()
    
    # 비수치형 컬럼 중 플롯 가능한 것들 추가
    for col in non_numeric_cols:
        try:
            sample_values = df_sample[col].dropna()
            if len(sample_values) > 0:
                pd.to_numeric(sample_values.iloc[0])
                num_cols.append(col)
        except (ValueError, TypeError, IndexError):
            pass
    
    # fault 컬럼 강제 추가
    if 'fault' in df_sample.columns and 'fault' not in num_cols:
        num_cols.append('fault')
    
    # 폴더 레이블 업데이트
    folder_label.config(text=f"현재 폴더: {db_folder}")
    
    # 파라미터 리스트 업데이트
    var_list.delete(0, tk.END)
    
    # frequent_params 필터링
    frequent_params_filtered = []
    for param in frequent_params:
        if param in num_cols or param in custom_params:
            frequent_params_filtered.append(param)
    
    # other_params 재계산
    other_params = [c for c in num_cols if c not in frequent_params_filtered]
    
    # 리스트박스에 다시 추가
    if frequent_params_filtered:
        var_list.insert(tk.END, "------ 자주 쓰는 파라미터 ------")
        for col in frequent_params_filtered:
            var_list.insert(tk.END, col)
    if other_params:
        var_list.insert(tk.END, "------ 나머지 파라미터 ------")
        for col in other_params:
            var_list.insert(tk.END, col)
    
    messagebox.showinfo("완료", f"폴더가 변경되었습니다.\n\n폴더: {db_folder}\nDB 파일: {len(db_files)}개\n파라미터: {len(num_cols)}개")
    print(f"파라미터 리스트 새로고침 완료: {len(num_cols)}개")

# 폴더 선택 버튼
btn_select_folder = ttk.Button(folder_frame, text="📁 폴더 선택", command=reload_folder)
btn_select_folder.pack(side=tk.RIGHT)

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

# ... (나머지 코드는 파일이 너무 길어서 생략) ...
# 전체 파일 내용을 업로드해야 합니다.