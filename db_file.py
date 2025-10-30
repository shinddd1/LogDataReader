"""
데이터베이스 파일 처리 모듈
DB 파일 읽기, PLC 복원, CNT 데이터 필터링, 구간 분석 기능을 제공합니다.
"""

import sqlite3
import pandas as pd
import numpy as np
import re
import datetime
import os
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk, messagebox


def read_db_file(db_path, params_to_read, time_cols, convert_datetime_vectorized):
    """
    DB 파일 읽기 함수 - PLC 복원 기능 포함 (초고속 세그먼트 기반)
    
    Args:
        db_path: 데이터베이스 파일 경로
        params_to_read: 읽을 파라미터 리스트
        time_cols: 시간 컬럼 리스트
        convert_datetime_vectorized: 벡터화된 datetime 변환 함수
        
    Returns:
        DataFrame: 처리된 데이터프레임
    """
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


def create_onselect_function(root, custom_params, ax1=None, ax2=None):
    """
    구간 선택 분석 함수를 생성하는 팩토리 함수
    
    Args:
        root: tkinter root 객체
        custom_params: 사용자 정의 파라미터 딕셔너리
        ax1: 첫 번째 축 (선택사항)
        ax2: 두 번째 축 (선택사항)
        
    Returns:
        onselect 함수
    """
    
    def onselect(xmin, xmax):
        print(f"onselect 함수 호출됨: xmin={xmin}, xmax={xmax}")
        try:
            # 전역 변수들에 접근
            global df_all, yvar, ax, fig
            print(f"전역 변수 상태 - df_all: {df_all is not None if 'df_all' in globals() else 'undefined'}")
            print(f"전역 변수 상태 - yvar: {yvar if 'yvar' in globals() else 'undefined'}")
            print(f"전역 변수 상태 - ax: {ax is not None if 'ax' in globals() else 'undefined'}")
            print(f"전역 변수 상태 - fig: {fig is not None if 'fig' in globals() else 'undefined'}")
        except Exception as e:
            print(f"전역 변수 접근 오류: {e}")
            return
        
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
                    if ax1 is not None:
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
    
    return onselect


def create_onselect_function_with_context(root, custom_params, df_all, yvar, ax, fig):
    """
    컨텍스트를 캡처하는 구간 선택 분석 함수를 생성하는 팩토리 함수
    
    Args:
        root: tkinter root 객체
        custom_params: 사용자 정의 파라미터 딕셔너리
        df_all: 데이터프레임
        yvar: y축 변수명
        ax: matplotlib axes
        fig: matplotlib figure
        
    Returns:
        onselect 함수
    """
    
    def onselect_with_context(xmin, xmax):
        print(f"onselect_with_context 호출됨: xmin={xmin}, xmax={xmax}")
        print(f"캡처된 컨텍스트 - df_all: {len(df_all) if df_all is not None else 'None'} rows")
        print(f"캡처된 컨텍스트 - yvar: {yvar}")
        
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
                    
                    # 구간 정보 기록
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
                    
                    # NaN 값 제거
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
                
                # 샷수 계산
                shot_nominal = total_E_nominal / (5e-4)
                shot_low = total_E_low / (5e-4)
                shot_high = total_E_high / (5e-4)
                
                # 구간별 상세 정보 생성
                segment_details = ""
                total_duration = 0
                total_points = 0
                for i, info in enumerate(segment_info):
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
            
            # 메시지박스 표시
            messagebox.showinfo("선택 구간 정보", msg)
            
            # 그래프 업데이트
            if fig and hasattr(fig, 'canvas'):
                fig.canvas.draw()
                
        except Exception as e:
            print(f"onselect_with_context 오류: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("오류", f"구간 분석 중 오류가 발생했습니다:\n{str(e)}")
    
    return onselect_with_context