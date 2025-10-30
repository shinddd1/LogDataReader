"""
DB 플롯 관리 모듈
- 데이터 플롯 생성 및 관리
- matplotlib 인터페이스 제어
- 저장 및 UI 기능
- 작업 로그 쪽지 버튼 관리
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import SpanSelector, RadioButtons, Button
from matplotlib.lines import Line2D
import matplotlib.patches as patches
import numpy as np
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import timedelta
from collections import defaultdict
import datetime
import os


def create_plot_manager(db_files, time_cols, convert_datetime_vectorized, 
                       var_list, custom_params, root, onselect=None):
    """플롯 관리자 생성 팩토리 함수"""
    
    def plot_selected(event=None):
        """메인 플롯 함수"""
        global yvar, ax1, ax, df_all, ax2, all_axes
        
        # 1. 파라미터 선택 및 데이터 로딩
        all_dfs, yvar, params_to_read = load_selected_data(
            db_files, var_list, custom_params, time_cols, convert_datetime_vectorized
        )
        
        if not all_dfs:
            return
        
        # 2. 데이터 통합 및 필터링
        df_all = process_and_filter_data(all_dfs, yvar, custom_params)
        
        if df_all is None or len(df_all) == 0:
            return
        
        # 3. 플롯 생성
        fig, ax, ax1, ax2, all_axes = create_main_plot(df_all, yvar, custom_params)
        
        # 4. PLC 에러 표시
        add_plc_error_display(df_all, ax)
        
        # 5. UI 컨트롤 추가
        add_plot_controls(fig, ax, all_axes, yvar, df_all, root, custom_params, onselect)
        
        plt.show()
    
    return plot_selected


def load_selected_data(db_files, var_list, custom_params, time_cols, convert_datetime_vectorized):
    """선택된 파라미터 데이터 로딩"""
    from db_file import read_db_file, is_cnt_related_data
    
    all_dfs = []
    sel = var_list.curselection()
    if not sel:
        return [], None, []
    
    yvar = var_list.get(sel[0])
    
    # 헤더 항목 체크
    if yvar.startswith("------"):
        return [], None, []

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
            
        df = read_db_file(db_path, params_to_read, time_cols, convert_datetime_vectorized)
        if df is not None:
            all_dfs.append(df)
            print(f"성공: {os.path.basename(db_path)} - {len(df)} 행")
        else:
            print(f"실패: {os.path.basename(db_path)}")
    
    if not all_dfs:
        messagebox.showwarning("경고", "적합한 데이터가 없습니다.")
    
    return all_dfs, yvar, params_to_read


def process_and_filter_data(all_dfs, yvar, custom_params):
    """데이터 통합 및 조건 필터링"""
    df_all = pd.concat(all_dfs, ignore_index=True)
    df_all['datetime'] = pd.to_datetime(df_all['datetime'])
    df_all = df_all.sort_values('datetime').reset_index(drop=True)

    print(f"통합 데이터: {len(df_all)} 행")
    print(f"컬럼들: {list(df_all.columns)}")

    # 조건 적용 (custom_params에 정의된 경우)
    if yvar in custom_params:
        df_all = apply_custom_conditions(df_all, yvar, custom_params)
    
    return df_all


def apply_custom_conditions(df_all, yvar, custom_params):
    """사용자 정의 파라미터 조건 적용"""
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
                return None
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
            return None
    else:
        print("적용된 조건이 없습니다.")
    
    return df_all


def create_main_plot(df_all, yvar, custom_params):
    """메인 플롯 생성"""
    # x축 데이터 설정 (조건 필터링 후)
    x = df_all['datetime']
    print(f"X축 데이터 확인: {len(x)} 포인트, 범위: {x.min()} ~ {x.max()}")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax2 = None
    all_axes = [ax]

    if yvar == "Laser & EUV Power":
        ax1, ax2, all_axes = create_laser_euv_plot(df_all, x, ax)
    elif yvar in custom_params:
        ax1, ax2, all_axes = create_custom_parameter_plot(df_all, x, ax, yvar, custom_params)
    else:
        ax1, ax2, all_axes = create_single_parameter_plot(df_all, x, ax, yvar)

    # x축 설정 및 포맷팅
    ax.set_xlabel("Time")
    ax.grid(True)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()
    fig.tight_layout()
    
    # 네비게이션 모드 체크 및 설정
    if hasattr(fig.canvas, 'toolbar') and fig.canvas.toolbar is not None:
        print(f"Toolbar 모드: {fig.canvas.toolbar.mode}")
        # 기본 pan/zoom 모드를 비활성화
        fig.canvas.toolbar.pan()  # pan 모드 토글
        fig.canvas.toolbar.pan()  # 다시 토글해서 끄기
        print(f"Toolbar 모드 변경 후: {fig.canvas.toolbar.mode}")

    return fig, ax, ax1, ax2, all_axes


def create_laser_euv_plot(df_all, x, ax):
    """Laser & EUV Power 플롯 생성"""
    print("Laser & EUV Power Scatter 플롯 처리 시작")
    
    # 두 파라미터가 모두 존재하는지 확인
    required_params = ["laser_power_value", "euvChamber_euvPower_value"]
    available_params = [p for p in required_params if p in df_all.columns]
    
    print(f"필요한 파라미터: {required_params}")
    print(f"사용 가능한 파라미터: {available_params}")
    
    if len(available_params) == 0:
        messagebox.showwarning("경고", "Laser Power와 EUV Power 데이터가 모두 없습니다.")
        return ax, None, [ax]
    
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
    ax2 = None
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
        try:
            facecolors = scatter_obj.get_facecolors()
            markerfacecolor = facecolors[0] if len(facecolors) > 0 else 'gray'
        except:
            markerfacecolor = 'gray'
        
        legend_handles.append(Line2D([0], [0], marker='o', color='w', 
                                       markerfacecolor=markerfacecolor,
                                       markersize=8, label=label))
    
    ax1.legend(handles=legend_handles, loc='upper left', bbox_to_anchor=(0, 1))
    
    plt.title(f"Laser & EUV Power vs Time (Scatter, 조건 필터링 적용, {len(df_all)} 포인트)")
    
    return ax1, ax2, all_axes


def create_custom_parameter_plot(df_all, x, ax, yvar, custom_params):
    """사용자 정의 파라미터 플롯 생성"""
    param_info = custom_params[yvar]
    param_list = param_info['params']
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple', 'tab:brown', 'tab:pink', 'tab:gray']
    
    valid_params = [p for p in param_list if p in df_all.columns]
    print(f"유효한 파라미터들: {valid_params}")
    
    if len(valid_params) == 0:
        messagebox.showwarning("경고", "플롯할 수 있는 유효한 파라미터가 없습니다.")
        return ax, None, [ax]
    
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
    ax2 = axes_list[1] if len(axes_list) > 1 else None
    
    plt.title(f"{yvar} vs Time (조건 필터링 적용, {len(df_all)} 포인트)")
    
    return ax1, ax2, all_axes


def create_single_parameter_plot(df_all, x, ax, yvar):
    """단일 파라미터 플롯 생성"""
    ax.plot(x, df_all[yvar])
    ax.set_ylabel(yvar)
    plt.title(f"{yvar} vs Time (PLC Error 기반 복원)")
    
    return ax, None, [ax]


def add_plc_error_display(df_all, ax):
    """PLC 에러 상태 표시"""
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
                    try:
                        ax.axvspan(error_start, time_val, alpha=0.2, color='orange', label='PLC Error')
                    except:
                        pass
                    in_error = False
            
            if in_error and error_start is not None:
                try:
                    ax.axvspan(error_start, df_all['datetime'].iloc[-1], alpha=0.2, color='orange', label='PLC Error')
                except:
                    pass
        
        print(f"PLC Error 구간 표시: {error_mask.sum()} 포인트")


def add_plot_controls(fig, ax, all_axes, yvar, df_all, root, custom_params, onselect=None):
    """플롯 컨트롤 UI 추가"""
    # 백엔드 확인
    import matplotlib
    print(f"Matplotlib 백엔드: {matplotlib.get_backend()}")
    
    # 드래그 선택 기능 - 항상 새로운 컨텍스트 포함 함수를 사용
    print(f"add_plot_controls 호출됨: onselect={onselect is not None}")
    from db_file import create_onselect_function_with_context
    onselect_with_context = create_onselect_function_with_context(root, custom_params, df_all, yvar, ax, fig)
    print("context 포함 onselect 함수를 생성했습니다")
    
    print(f"SpanSelector 생성 중... ax={ax}, type={type(ax)}")
    
    # useblit=False로 설정해서 호환성 향상
    try:
        span = SpanSelector(ax, onselect_with_context, 'horizontal', useblit=False, 
                          props=dict(alpha=0.5, facecolor='red'),
                          interactive=True)
        print(f"SpanSelector 생성 완료: {span}")
        print(f"SpanSelector active: {span.active}")
        
        # SpanSelector를 그래프에 저장해서 가비지 컬렉션 방지
        if not hasattr(fig, '_span_selectors'):
            fig._span_selectors = []
        fig._span_selectors.append(span)
        
        # 추가 이벤트 연결 확인
        print(f"Figure canvas: {fig.canvas}")
        print(f"Axes navigation: {ax.get_navigate()}")
        
        # SpanSelector가 작동하지 않을 경우를 대비한 백업: 직접 마우스 이벤트 연결
        def backup_mouse_handler():
            print("백업 마우스 핸들러를 설정합니다...")
            
            class DragSelector:
                def __init__(self, ax, onselect_func):
                    self.ax = ax
                    self.onselect_func = onselect_func
                    self.press = None
                    self.release = None
                    
                def connect(self):
                    self.cidpress = self.ax.figure.canvas.mpl_connect('button_press_event', self.on_press)
                    self.cidrelease = self.ax.figure.canvas.mpl_connect('button_release_event', self.on_release)
                    
                def on_press(self, event):
                    if event.inaxes != self.ax:
                        return
                    if event.button != 1:  # 왼쪽 마우스 버튼만
                        return
                    self.press = event.xdata
                    print(f"드래그 시작: {self.press}")
                    
                def on_release(self, event):
                    if event.inaxes != self.ax:
                        return
                    if event.button != 1:
                        return
                    if self.press is None:
                        return
                        
                    self.release = event.xdata
                    print(f"드래그 종료: {self.release}")
                    
                    if self.press != self.release:
                        xmin, xmax = min(self.press, self.release), max(self.press, self.release)
                        print(f"선택 범위: {xmin} - {xmax}")
                        self.onselect_func(xmin, xmax)
                    
                    self.press = None
                    
            # 백업 핸들러 활성화
            backup_selector = DragSelector(ax, onselect_with_context)
            backup_selector.connect()
            
            # 백업도 저장
            if not hasattr(fig, '_backup_selectors'):
                fig._backup_selectors = []
            fig._backup_selectors.append(backup_selector)
            
        # 백업 핸들러 설정
        backup_mouse_handler()
        
    except Exception as e:
        print(f"SpanSelector 생성 실패: {e}")
        import traceback
        traceback.print_exc()

    # 스케일 버튼들
    try:
        radio_ax = fig.add_axes((0.05, 0.9, 0.15, 0.08))
        radio = RadioButtons(radio_ax, ('linear', 'log'), active=0)

        def set_scale(label):
            for axis in all_axes:
                try:
                    axis.set_yscale(label)
                except Exception as e:
                    print(f"축 스케일 변경 오류: {e}")
            fig.canvas.draw()

        radio.on_clicked(set_scale)
    except Exception as e:
        print(f"라디오 버튼 생성 오류: {e}")

    # 저장 버튼
    add_save_functionality(fig, yvar, df_all)
    
    # 작업 로그 쪽지 버튼
    create_work_log_buttons(fig, df_all)


def add_save_functionality(fig, yvar, df_all):
    """저장 기능 추가"""
    def save_current_data():
        try:
            # 현재 표시된 축의 x축 범위 가져오기
            if yvar == "Laser & EUV Power":
                # 전역 변수 확인
                import sys
                current_module = sys.modules[__name__]
                if hasattr(current_module, 'ax1') and current_module.ax1 is not None:
                    xlim = current_module.ax1.get_xlim()
                    print(f"Laser & EUV Power: ax1 xlim = {xlim}")
                else:
                    # fallback: 첫 번째 axes 사용
                    xlim = fig.axes[0].get_xlim()
                    print(f"Laser & EUV Power (fallback): ax xlim = {xlim}")
            else:
                xlim = fig.axes[0].get_xlim()
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
    try:
        save_ax = fig.add_axes((0.85, 0.02, 0.13, 0.04))
        save_btn = Button(save_ax, 'Save Data')
        save_btn.label.set_fontsize(9)
        save_btn.on_clicked(lambda x: save_current_data())
    except Exception as e:
        print(f"저장 버튼 생성 오류: {e}")


def create_work_log_buttons(fig, df_all):
    """작업 로그 쪽지 버튼 생성"""
    def create_date_note_buttons_in_plot():
        """현재 플롯된 데이터의 날짜 범위에 해당하는 로그 날짜만 쪽지 버튼으로 생성"""
        try:
            print("🔍 matplotlib 플롯 창 쪽지 버튼 생성 시작...")
            
            # 현재 플롯된 데이터의 날짜 범위 확인 (±30일 여유 범위 추가)
            if df_all.empty:
                print("❌ 플롯된 데이터가 없습니다.")
                return
                
            plot_start_date = df_all['datetime'].min().date() - timedelta(days=30)
            plot_end_date = df_all['datetime'].max().date() + timedelta(days=30)
            print(f"📊 플롯 데이터 날짜 범위 (±30일): {plot_start_date} ~ {plot_end_date}")
            
            # WorkLogManager 인스턴스를 통해 로그 로드
            # 전역 변수에서 work_log_manager 접근 시도
            try:
                import sys
                main_module = sys.modules.get('__main__')
                if main_module and hasattr(main_module, 'work_log_manager'):
                    work_log_manager = main_module.work_log_manager
                    logs = work_log_manager.load_work_logs()
                    print(f"📋 로드된 로그 개수: {len(logs) if logs else 0}")
                else:
                    print("❌ work_log_manager를 찾을 수 없습니다.")
                    return
            except Exception as e:
                print(f"❌ work_log_manager 로드 오류: {e}")
                return
            
            if not logs:
                print("❌ 로그가 없어서 쪽지 버튼을 생성하지 않습니다.")
                return

            # 날짜별로 로그 그룹화 (플롯 범위 내 날짜만)
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
                        # show_work_log_messages_for_date 함수 호출
                        try:
                            main_module = sys.modules.get('__main__')
                            if main_module and hasattr(main_module, 'show_work_log_messages_for_date'):
                                main_module.show_work_log_messages_for_date(date_key, logs_for_date)
                        except Exception as e:
                            print(f"로그 표시 함수 호출 오류: {e}")
            
            # 클릭 이벤트 연결
            fig.canvas.mpl_connect('button_press_event', on_note_click)
            
            print(f"🎉 matplotlib 쪽지 버튼 생성 완료! 플롯 창 상단에 표시됩니다.")
        
        except Exception as e:
            print(f"matplotlib 쪽지 버튼 생성 오류: {e}")
    
    create_date_note_buttons_in_plot()


# 모듈에서 export할 항목들
__all__ = ['create_plot_manager']