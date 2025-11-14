"""
구간 선택 및 적분 분석 모듈
드래그 선택 구간에 대한 적분 계산 및 샷수 분석 기능을 제공합니다.
"""

import pandas as pd
import numpy as np
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk, messagebox


def compute_total_energy(t, P, EUV, E_pulse):
    """
    총 에너지 및 샷수 계산 (새로운 논리)
    
    Args:
        t: np.ndarray, time array [s]
        P: np.ndarray, laser power array [W]
        EUV: np.ndarray, EUV signal array
        E_pulse: float, energy per pulse [J]
        
    Returns:
        E_total: float, 총 에너지 [J]
        N_shots: float, 총 샷수
    """
    # NaN을 0으로 처리 (NaN도 0으로 인식)
    P_clean = np.where(np.isnan(P), 0, P)
    EUV_clean = np.where(np.isnan(EUV), 0, EUV)
    
    # 조건 마스크 m_i 정의: m_i = {1, if P_i > 0 AND EUV_i > 0; 0, otherwise}
    # np.where는 조건이 True면 1, False면 0을 반환하므로 모든 경우가 명시적으로 처리됨
    # - P > 0 AND EUV > 0 → m = 1
    # - P <= 0 OR EUV <= 0 → m = 0 (P=0, EUV=0, P<0, EUV<0, NaN 모두 포함)
    epsilon = 1e-10
    m = np.where((P_clean > epsilon) & (EUV_clean > epsilon), 1, 0)
    
    # v_i = m_i * m_{i+1} (연속성 체크)
    v = m[:-1] * m[1:]
    
    # 시간 간격이 큰 경우 v를 0으로 강제 설정 (세그먼트 분리)
    # 이유: P와 EUV가 모두 > 0이어서 m=1이지만, 실제로는 데이터 수집 중단 구간이 있을 수 있음
    # - 시간 간격 >= 임계값(2초)인 경우 → v = 0으로 설정
    # - 이렇게 하면 시간 간격이 2초 이상인 지점에서 세그먼트가 분리됨
    dt_array = np.diff(t) if len(t) > 1 else np.array([0])
    if len(dt_array) > 0:
        # 임계값: 2초 (2초 이상이면 세그먼트 분리)
        time_gap_threshold = 2.0
        # 큰 시간 간격이 있는 위치 찾기 (2초 이상)
        large_gap_mask = dt_array >= time_gap_threshold
        
        # 큰 시간 간격이 있는 위치에서 v=0으로 강제 설정 (세그먼트 분리)
        v[large_gap_mask] = 0
    
    # Δt_i = t_{i+1} - t_i
    dt = np.diff(t)
    
    # (P_i + P_{i+1}) / 2 (P_clean 사용)
    P_avg = 0.5 * (P_clean[:-1] + P_clean[1:])
    
    # E_total = Σ v_i * (P_i + P_{i+1})/2 * Δt_i
    E_total = np.sum(v * P_avg * dt)
    
    # N_shots = E_total / E_pulse
    N_shots = E_total / E_pulse
    
    return E_total, N_shots


def create_onselect_function_with_context(root, custom_params, df_all, yvar, ax, fig, ax1=None, ax2=None):
    """
    컨텍스트를 캡처하는 구간 선택 분석 함수를 생성하는 팩토리 함수
    
    Args:
        root: tkinter root 객체
        custom_params: 사용자 정의 파라미터 딕셔너리
        df_all: 데이터프레임
        yvar: y축 변수명
        ax: matplotlib axes (기본 축)
        fig: matplotlib figure
        ax1: 첫 번째 축 (선택사항, Laser & EUV Power용)
        ax2: 두 번째 축 (선택사항, Laser & EUV Power용)
        
    Returns:
        onselect 함수
    """
    # ax1이 지정되지 않으면 ax를 사용
    if ax1 is None:
        ax1 = ax
    
    def onselect_with_context(xmin, xmax):
        try:
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
                # laser_power_value와 euvChamber_euvPower_value 컬럼이 있는지 확인
                required_cols = ['laser_power_value', 'euvChamber_euvPower_value']
                missing_cols = [col for col in required_cols if col not in df_sel.columns]
                
                if 'laser_power_value' not in df_sel.columns or df_sel['laser_power_value'].isna().all():
                    messagebox.showinfo("선택 구간 정보", msg + "\n\n레이저 파워 데이터가 없어 샷수 계산을 할 수 없습니다.")
                    return
                
                if 'euvChamber_euvPower_value' not in df_sel.columns거나 df_sel['euvChamber_euvPower_value'].isna().all():
                    messagebox.showinfo("선택 구간 정보", msg + "\n\nEUV 파워 데이터가 없어 샷수 계산을 할 수 없습니다.")
                    return
                
                # 데이터 정렬 및 NaN 제거
                df_processed = df_sel.sort_values('datetime').reset_index(drop=True)
                
                # 유효한 데이터만 필터링 (둘 다 NaN이 아닌 경우)
                valid_mask = df_processed['laser_power_value'].notna() & df_processed['euvChamber_euvPower_value'].notna()
                df_valid = df_processed[valid_mask].copy()
                
                if len(df_valid) < 2:
                    messagebox.showinfo("선택 구간 정보", msg + "\n\n유효한 레이저 파워 및 EUV 파워 데이터가 부족합니다.")
                    return
                
                # 시간 배열 (초 단위)
                t = (df_valid['datetime'] - df_valid['datetime'].iloc[0]).dt.total_seconds().values
                P = df_valid['laser_power_value'].values
                EUV = df_valid['euvChamber_euvPower_value'].values
                
                # NaN이 있는 경우 제거 (추가 안전장치)
                valid_indices = ~(np.isnan(t) | np.isnan(P) | np.isnan(EUV))
                if valid_indices.sum() < 2:
                    messagebox.showinfo("선택 구간 정보", msg + "\n\n유효한 데이터 포인트가 부족합니다.")
                    return
                
                t = t[valid_indices]
                P = P[valid_indices]
                EUV = EUV[valid_indices]
                
                # NaN을 0으로 처리
                P_clean = np.where(np.isnan(P), 0, P)
                EUV_clean = np.where(np.isnan(EUV), 0, EUV)
                
                # 새로운 논리로 총 에너지 및 샷수 계산
                E_pulse = 5e-4  # 0.0005 J = 500 μJ
                E_total, N_shots = compute_total_energy(t, P_clean, EUV_clean, E_pulse)
                
                # 적분되는 세그먼트 찾기
                # 
                # 1단계: Power 데이터 기반으로 m_i 정의
                # m_i = {1, if P_i > 0 AND EUV_i > 0; 0, otherwise}
                # - P > 0 AND EUV > 0 → m = 1 (적분 가능)
                # - P <= 0 OR EUV <= 0 → m = 0 (적분 불가)
                epsilon = 1e-10
                m = np.where((P_clean > epsilon) & (EUV_clean > epsilon), 1, 0)
                
                # 2단계: m 기반으로 v_i 계산 (원래 정의)
                # v_i = m_i * m_{i+1} (연속성 체크)
                # - v_i = 1: 포인트 i와 i+1이 모두 적분 가능 (m[i] = 1 AND m[i+1] = 1)
                # - v_i = 0: 포인트 i 또는 i+1 중 하나라도 적분 불가 (m[i] = 0 OR m[i+1] = 0)
                dt_array = np.diff(t) if len(t) > 1 else np.array([0])
                v = m[:-1] * m[1:]
                
                # 3단계: 시간 간격이 큰 경우 v를 0으로 강제 설정 (세그먼트 분리)
                # 이유: P와 EUV가 모두 > 0이어서 m=1이지만, 실제로는 데이터 수집 중단 구간이 있을 수 있음
                # - 시간 간격 >= 임계값(2초)인 경우 → v = 0으로 설정
                # - 이렇게 하면 시간 간격이 2초 이상인 지점에서 세그먼트가 분리됨
                # 
                # 즉, v = 0의 최종 정의:
                #   (1) Power 데이터 기반: m[i] = 0 OR m[i+1] = 0 → v[i] = 0
                #   (2) 시간 간격 기반: dt[i] >= 2초 → v[i] = 0 (강제 설정)
                if len(dt_array) > 0:
                    # 임계값: 2초 (2초 이상이면 세그먼트 분리)
                    time_gap_threshold = 2.0
                    # 큰 시간 간격이 있는 위치 찾기 (2초 이상)
                    large_gap_mask = dt_array >= time_gap_threshold
                    
                    # 큰 시간 간격이 있는 위치에서 v=0으로 강제 설정 (세그먼트 분리)
                    v[large_gap_mask] = 0
                    
                
                # v_i = 1인 연속된 구간을 세그먼트로 찾기 (v 기준으로 세그먼트 정의)
                # v_i = 0이 되면 세그먼트가 끝남
                segments = []
                segment_start_idx = None
                
                for i in range(len(v)):
                    if v[i] == 1:
                        # v_i = 1인 경우 - 연속된 적분 구간 내부
                        if segment_start_idx is None:
                            segment_start_idx = i  # 세그먼트 시작
                    else:
                        # v_i = 0인 경우 - 세그먼트 종료
                        if segment_start_idx is not None:
                            # v[segment_start_idx:i] = 1인 구간이 세그먼트
                            # v[i] = 0이므로 세그먼트는 segment_start_idx부터 i-1까지
                            segment_end_idx = i - 1  # 마지막 v 인덱스 (i-1)
                            segments.append((segment_start_idx, segment_end_idx))
                            segment_start_idx = None
                
                # 마지막 세그먼트 처리
                if segment_start_idx is not None:
                    segment_end_idx = len(v) - 1  # v의 마지막 인덱스
                    segments.append((segment_start_idx, segment_end_idx))
                
                # 세그먼트 정보 수집 (v = 1인 구간 기준)
                segment_info_list = []
                total_integral_time = 0
                total_integral_points = 0
                
                # dt_array 재계산 (v 기준 세그먼트에 맞게)
                dt_array_full = np.diff(t) if len(t) > 1 else np.array([0])
                
                for seg_idx, (start_idx, end_idx) in enumerate(segments):
                    # v 기준 세그먼트: v[start_idx:end_idx+1] = 1인 구간
                    # v[i] = m[i] * m[i+1]이므로, v[i] = 1이면 포인트 i와 i+1이 연속된 적분 구간
                    # 따라서 v[start_idx:end_idx+1] = 1이면 포인트 start_idx부터 포인트 end_idx+1까지가 세그먼트
                    point_start_idx = start_idx
                    point_end_idx = end_idx + 1  # v 인덱스 end_idx까지이면 포인트 end_idx+1까지
                    
                    # 포인트 인덱스 범위 확인
                    if point_end_idx > len(df_valid):
                        point_end_idx = len(df_valid)
                    
                    # 세그먼트의 시작과 끝 시간 (포인트 기준)
                    seg_start_datetime = df_valid['datetime'].iloc[point_start_idx]
                    seg_end_datetime = df_valid['datetime'].iloc[point_end_idx - 1]  # 마지막 포인트
                    
                    # v 기준으로 실제 적분되는 시간 계산 (v = 1인 구간의 dt 합)
                    # v[start_idx:end_idx+1] = 1인 구간의 dt 합
                    # dt_array_full[start_idx:end_idx+1]의 합
                    if end_idx + 1 <= len(dt_array_full):
                        seg_integral_time = np.sum(dt_array_full[start_idx:end_idx+1])
                    else:
                        seg_integral_time = np.sum(dt_array_full[start_idx:])
                    
                    # v 기준으로 실제 적분되는 포인트 수 계산
                    # v[start_idx:end_idx+1] = 1인 구간의 포인트 수
                    # v 구간이 (end_idx - start_idx + 1)개이면, 포인트는 (end_idx - start_idx + 2)개
                    seg_integral_points = (end_idx - start_idx + 1) + 1
                    
                    # 세그먼트 시간과 포인트 수는 적분 시간과 포인트 수와 동일하게 설정
                    seg_time = seg_integral_time
                    seg_points = seg_integral_points
                    
                    # 세그먼트 평균 파워 - 세그먼트 내 모든 포인트의 평균
                    seg_point_indices = np.arange(point_start_idx, point_end_idx)
                    seg_P = P_clean[seg_point_indices]
                    seg_avg_power = np.mean(seg_P) if len(seg_P) > 0 else 0.0
                    
                    segment_info_list.append({
                        'index': seg_idx + 1,
                        'start': seg_start_datetime,
                        'end': seg_end_datetime,
                        'duration': seg_time,  # 적분 시간과 동일
                        'points': seg_points,  # 적분 포인트 수와 동일
                        'integral_time': seg_integral_time,
                        'integral_points': seg_integral_points,
                        'avg_power': seg_avg_power
                    })
                    
                    total_integral_time += seg_integral_time
                    total_integral_points += seg_integral_points
                
                # 구간 정보
                segment_start = df_valid['datetime'].iloc[0]
                segment_end = df_valid['datetime'].iloc[-1]
                segment_duration = (segment_end - segment_start).total_seconds()
                total_points = len(t)
                
                # 날짜 범위 계산
                start_date = segment_start.strftime('%Y-%m-%d')
                end_date = segment_end.strftime('%Y-%m-%d')
                if start_date == end_date:
                    date_range_text = f"날짜: {start_date}"
                else:
                    date_range_text = f"날짜 범위: {start_date} ~ {end_date}"
                
                # 메시지 구성
                msg += (
                    f"\n\n[적분 구간 정보]"
                    f"\n{date_range_text}"
                    f"\n적분되는 총 시간: {total_integral_time:.2f}초"
                    f"\n적분되는 총 포인트 수: {total_integral_points}개"
                    f"\n적분 세그먼트 수: {len(segments)}개"
                )
                
                # 각 세그먼트 상세 정보
                if len(segment_info_list) > 0:
                    msg += "\n\n[세그먼트별 상세 정보]"
                    for seg_info in segment_info_list:
                        seg_start_str = seg_info['start'].strftime('%Y-%m-%d %H:%M:%S')
                        seg_end_str = seg_info['end'].strftime('%Y-%m-%d %H:%M:%S')
                        msg += (
                            f"\n세그먼트 {seg_info['index']}: {seg_start_str} ~ {seg_end_str}"
                            f"\n  적분 시간: {seg_info['integral_time']:.2f}초"
                            f"\n  적분 포인트 수: {seg_info['integral_points']}개"
                            f"\n  평균 파워: {seg_info['avg_power']:.3f} W"
                        )
                else:
                    msg += "\n\n적분 가능한 세그먼트가 없습니다."
                
                msg += (
                    f"\n\n[전체 선택 구간 정보]"
                    f"\n총 시간: {segment_duration:.1f}초"
                    f"\n총 포인트 수: {total_points}개"
                    f"\n\n[샷수 계산 결과]"
                    f"\n적분 에너지: {E_total:.3e} J"
                    f"\n계산된 샷 수: {N_shots:.2f}"
                    f"\n(에너지 펄스당: {E_pulse*1e6:.1f} μJ)"
                )
                
            else:
                # 단일 파라미터 분석
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
                    param_list = custom_params[yvar]['params'] if isinstance(custom_params[yvar], dict) else custom_params[yvar]
                    for param in param_list:
                        if param in df_sel.columns:
                            param_data = df_sel[param].dropna()
                            if len(param_data) > 1:
                                param_integral = param_data.mean() * delta_sec
                                param_avg = param_data.mean()
                                param_max = param_data.max()
                                param_min = param_data.min()
                                
                                msg += f"\n\n{param}:\n"
                                msg += f"  적분값: {param_integral:.3f} (단위·초)\n"
                                msg += f"  평균값: {param_avg:.3f}\n"
                                msg += f"  최대값: {param_max:.3f}\n"
                                msg += f"  최소값: {param_min:.3f}\n"
                                msg += f"  샷수 (데이터 포인트): {len(param_data)}개\n"
            
            # 스크롤 가능한 정보 창 표시 (복사 가능)
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
                
                # 텍스트 위젯 생성 (복사 가능하도록 state=tk.NORMAL)
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
                text_widget.configure(state=tk.NORMAL)  # 복사 가능하도록 NORMAL 상태 유지
                
                # 전체 선택 기능 (Ctrl+A)
                def select_all(event):
                    text_widget.tag_add(tk.SEL, "1.0", tk.END)
                    text_widget.mark_set(tk.INSERT, "1.0")
                    text_widget.see(tk.INSERT)
                    return "break"
                
                text_widget.bind("<Control-a>", select_all)
                text_widget.bind("<Control-A>", select_all)
                
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
            
            # 그래프 업데이트
            if fig and hasattr(fig, 'canvas'):
                fig.canvas.draw()
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("오류", f"구간 분석 중 오류가 발생했습니다:\n{str(e)}")
    
    return onselect_with_context
