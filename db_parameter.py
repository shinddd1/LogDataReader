"""
데이터베이스 파라미터 관리 모듈
사용자 정의 파라미터 추가 및 파라미터 리스트 관리 기능을 제공합니다.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import os

# 자주 사용하는 파라미터들을 저장하는 전역 리스트
frequent_params = []

def load_frequent_params():
    """frequent_params.txt 파일에서 자주 사용하는 파라미터를 로드합니다."""
    global frequent_params
    try:
        if os.path.exists('frequent_params.txt'):
            with open('frequent_params.txt', 'r', encoding='utf-8') as f:
                content = f.read().strip()
                # 쉼표로 구분된 파라미터들을 파싱
                if content:
                    # 줄바꿈과 쉼표로 분리하고 따옴표 제거
                    params = []
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and line != ',':
                            # 따옴표와 쉼표를 완전히 제거 (양쪽 끝에서)
                            param = line.strip().rstrip(',').strip('"').strip("'").strip()
                            if param:
                                params.append(param)
                    frequent_params.extend(params)
                    print(f"frequent_params 로드 완료: {len(params)}개 파라미터")
    except Exception as e:
        print(f"frequent_params.txt 로드 실패: {e}")

# 모듈 임포트 시 자동으로 frequent_params 로드
load_frequent_params()

def save_frequent_params():
    """frequent_params 리스트를 frequent_params.txt 파일에 저장합니다."""
    global frequent_params
    try:
        with open('frequent_params.txt', 'w', encoding='utf-8') as f:
            for i, param in enumerate(frequent_params):
                f.write(f'"{param}"')
                if i < len(frequent_params) - 1:
                    f.write(',\n')
                else:
                    f.write('\n')
        print(f"frequent_params 저장 완료: {len(frequent_params)}개 파라미터")
    except Exception as e:
        print(f"frequent_params.txt 저장 실패: {e}")


def create_add_custom_param_function(root, custom_params, frequent_params_param, num_cols, var_list, df_sample, time_cols):
    """
    사용자 정의 파라미터 추가 함수를 생성하는 팩토리 함수
    
    Args:
        root: tkinter root 객체
        custom_params: 사용자 정의 파라미터 딕셔너리
        frequent_params_param: 자주 사용하는 파라미터 리스트 (호환성을 위해 유지하지만 전역 frequent_params 사용)
        num_cols: 숫자 컬럼 리스트
        var_list: 변수 리스트박스 객체
        df_sample: 샘플 데이터프레임
        time_cols: 시간 컬럼 리스트
        
    Returns:
        add_custom_param 함수
    """
    global frequent_params
    
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
            if name not in frequent_params:
                frequent_params.append(name)
                save_frequent_params()  # 파일에 저장
            
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
    
    return add_custom_param


def setup_parameter_lists(var_list, num_cols, frequent_params_param, root):
    """
    파라미터 리스트 설정 함수
    
    Args:
        var_list: 변수 리스트박스 객체  
        num_cols: 숫자 컬럼 리스트
        frequent_params_param: 자주 사용하는 파라미터 리스트 (호환성을 위해 유지하지만 전역 frequent_params 사용)
        root: tkinter root 객체
        
    Returns:
        dict: 설정 함수들을 담은 딕셔너리
    """
    global frequent_params
    
    def populate_var_list():
        """변수 리스트 초기화"""
        var_list.delete(0, tk.END)
        
        # 자주 쓰는 파라미터 섹션
        if frequent_params:
            var_list.insert(tk.END, "------ 자주 쓰는 파라미터 ------")
            for param in frequent_params:
                if param in num_cols:
                    var_list.insert(tk.END, param)
        
        # 나머지 파라미터 섹션
        var_list.insert(tk.END, "------ 나머지 파라미터 ------")
        for col in num_cols:
            if col not in frequent_params:
                var_list.insert(tk.END, col)
    
    def add_to_frequent(param_name):
        """파라미터를 자주 사용하는 목록에 추가"""
        if param_name not in frequent_params:
            frequent_params.append(param_name)
            save_frequent_params()  # 파일에 저장
            populate_var_list()
    
    return {
        'populate_var_list': populate_var_list,
        'add_to_frequent': add_to_frequent
    }


def initialize_custom_params_and_ui(custom_params, frequent_params_param, num_cols, var_list, frame, add_custom_param):
    """
    사용자 정의 파라미터 초기화 및 UI 설정 함수
    
    Args:
        custom_params: 사용자 정의 파라미터 딕셔너리
        frequent_params_param: 자주 사용하는 파라미터 리스트 (호환성을 위해 유지하지만 전역 frequent_params 사용)
        num_cols: 숫자 컬럼 리스트
        var_list: 변수 리스트박스 객체
        frame: UI 프레임 객체
        add_custom_param: 파라미터 추가 함수
    """
    global frequent_params
    from tkinter import ttk
    
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

    # 파라미터 추가 버튼 생성
    btn_add_param = ttk.Button(frame, text="파라미터 추가", command=add_custom_param)
    btn_add_param.pack(pady=10)
    
    return btn_add_param