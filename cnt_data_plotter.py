"""
CNT 모니터링 시스템 데이터 플롯 모듈
CNT_Monitoring_System/Data 경로의 데이터를 시간순으로 플롯
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.widgets import SpanSelector
from matplotlib.patches import Rectangle
try:
    from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
except ImportError:
    from matplotlib.backends._backend_tk import NavigationToolbar2Tk
import os
import glob
import datetime
import numpy as np
import math

# 한글 폰트 설정 (경고 방지)
import matplotlib
matplotlib.rcParams['font.family'] = ['Malgun Gothic', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False


class CNTDataPlotter:
    """CNT 모니터링 시스템 데이터 플롯 클래스"""
    
    def __init__(self, parent_frame):
        """
        초기화
        Args:
            parent_frame: 부모 tkinter 프레임
        """
        self.parent_frame = parent_frame
        self.data_path = r"C:\Users\user\Desktop\vscode\CNT_Monitoring_System\Data"
        self.current_data = None
        self.fig = None
        self.ax = None
        self.canvas = None
        self.span_selector = None
        self.current_column = None
        self.stats_text_obj = None
        self.drag_start_x = None
        self.is_dragging = False
        self.drag_rect = None
        self.drag_text = None
        self.shift_pressed = False
        
        self.setup_ui()
        self.load_all_files()
    
    def on_select(self, xmin, xmax):
        """드래그 선택 시 호출되는 콜백 함수"""
        print(f"드래그 선택됨: xmin={xmin}, xmax={xmax}")
        print(f"current_data 상태: {self.current_data is not None}")
        print(f"current_column 상태: {self.current_column}")
        
        if self.current_data is None or self.current_column is None:
            print("데이터나 컬럼이 없어서 리턴")
            return
        
        try:
            # 시간 컬럼 찾기
            time_columns = [col for col in self.current_data.columns 
                          if 'time' in col.lower() or 'date' in col.lower() or '시간' in col]
            
            if time_columns:
                time_col = time_columns[0]
                try:
                    x_data = pd.to_datetime(self.current_data[time_col])
                    # matplotlib 날짜를 pandas datetime으로 변환
                    if isinstance(xmin, (int, float)) and isinstance(xmax, (int, float)):
                        # matplotlib date number를 datetime으로 변환
                        xmin_dt = mdates.num2date(xmin).replace(tzinfo=None)
                        xmax_dt = mdates.num2date(xmax).replace(tzinfo=None) 
                        # timezone naive로 만들기
                        if x_data.dt.tz is not None:
                            x_data = x_data.dt.tz_localize(None)
                        mask = (x_data >= xmin_dt) & (x_data <= xmax_dt)
                        print(f"시간 기반 필터링: {xmin_dt} ~ {xmax_dt}, 매칭 데이터: {mask.sum()}개")
                    else:
                        # 인덱스 기반 필터링으로 폴백
                        mask = (self.current_data.index >= int(xmin)) & (self.current_data.index <= int(xmax))
                        print(f"인덱스 기반 필터링 (폴백): {int(xmin)} ~ {int(xmax)}, 매칭 데이터: {mask.sum()}개")
                except Exception as e:
                    print(f"시간 변환 실패: {e}")
                    # 시간 변환 실패시 인덱스 기반 필터링
                    mask = (self.current_data.index >= int(xmin)) & (self.current_data.index <= int(xmax))
                    print(f"인덱스 기반 필터링 (예외): {int(xmin)} ~ {int(xmax)}, 매칭 데이터: {mask.sum()}개")
            else:
                # 인덱스 기반 필터링
                mask = (self.current_data.index >= int(xmin)) & (self.current_data.index <= int(xmax))
                print(f"인덱스 기반 필터링: {int(xmin)} ~ {int(xmax)}, 매칭 데이터: {mask.sum()}개")
            
            # 선택된 범위의 데이터
            selected_data = self.current_data[mask][self.current_column]
            
            if len(selected_data) == 0:
                return
            
            # 통계 정보 계산
            stats = selected_data.describe()
            median_val = selected_data.median()
            
            # 통계 정보 텍스트 생성
            stats_text = (f"선택 구간 통계 (총 {len(selected_data)}개 포인트)\n"
                         f"평균: {stats['mean']:.3f}\n"
                         f"중간값: {median_val:.3f}\n"
                         f"표준편차: {stats['std']:.3f}\n"
                         f"최댓값: {stats['max']:.3f}\n"
                         f"최솟값: {stats['min']:.3f}")
            
            # 기존 통계 텍스트 제거
            if self.stats_text_obj:
                self.stats_text_obj.remove()
            
            # 새 통계 텍스트 추가
            self.stats_text_obj = self.ax.text(0.02, 0.98, stats_text, 
                                              transform=self.ax.transAxes,
                                              verticalalignment='top', 
                                              bbox=dict(boxstyle='round', 
                                                       facecolor='lightblue', 
                                                       alpha=0.8))
            
            self.canvas.draw()
            
        except Exception as e:
            print(f"드래그 선택 처리 오류: {e}")
    
    def on_span_select(self, xmin, xmax):
        """SpanSelector 드래그 선택 콜백 (로그 데이터 리더 방식)"""
        if self.current_data is None or self.current_column is None:
            return
        
        print(f"SpanSelector 드래그 선택: {xmin} ~ {xmax}")
        
        # 통계 팝업 표시
        self.show_statistics_popup(xmin, xmax)
    
    def show_statistics_popup(self, xmin, xmax):
        """통계 정보 팝업 창 표시"""
        if self.current_data is None or self.current_column is None:
            return
        
        try:
            # 데이터 필터링 (기존 on_select 로직 사용)
            time_columns = [col for col in self.current_data.columns 
                          if 'time' in col.lower() or 'date' in col.lower() or '시간' in col]
            
            if time_columns:
                time_col = time_columns[0]
                try:
                    x_data = pd.to_datetime(self.current_data[time_col])
                    if isinstance(xmin, (int, float)) and isinstance(xmax, (int, float)):
                        xmin_dt = mdates.num2date(xmin).replace(tzinfo=None)
                        xmax_dt = mdates.num2date(xmax).replace(tzinfo=None) 
                        if x_data.dt.tz is not None:
                            x_data = x_data.dt.tz_localize(None)
                        mask = (x_data >= xmin_dt) & (x_data <= xmax_dt)
                    else:
                        mask = (self.current_data.index >= int(xmin)) & (self.current_data.index <= int(xmax))
                except Exception as e:
                    mask = (self.current_data.index >= int(xmin)) & (self.current_data.index <= int(xmax))
            else:
                mask = (self.current_data.index >= int(xmin)) & (self.current_data.index <= int(xmax))
            
            # 선택된 범위의 데이터
            selected_data = self.current_data[mask][self.current_column]

            # 빈값/비숫자 값은 NaN으로 처리하고 제거
            try:
                selected_data = pd.to_numeric(selected_data, errors='coerce').dropna()
            except Exception:
                selected_data = selected_data.dropna()

            if len(selected_data) == 0:
                messagebox.showwarning("경고", "선택된 범위에 유효한 숫자 데이터가 없습니다.")
                return

            # 통계 정보 계산 (정제된 데이터 기준)
            stats = selected_data.describe()
            median_val = selected_data.median()
            
            # 시간 범위 텍스트
            time_range_text = self.format_time_range(xmin, xmax)
            
            # 팝업 창 생성
            self.create_statistics_popup(selected_data, stats, median_val, time_range_text)
            
        except Exception as e:
            print(f"통계 팝업 생성 오류: {e}")
            messagebox.showerror("오류", f"통계 정보를 계산할 수 없습니다:\n{e}")
    
    def format_time_range(self, xmin, xmax):
        """시간 범위를 사람이 읽기 쉬운 형식으로 변환"""
        try:
            # 시간 컬럼 확인
            time_columns = [col for col in self.current_data.columns 
                          if 'time' in col.lower() or 'date' in col.lower() or '시간' in col]
            
            if time_columns:
                # matplotlib date number를 datetime으로 변환
                start_dt = mdates.num2date(xmin).strftime('%Y-%m-%d %H:%M:%S')
                end_dt = mdates.num2date(xmax).strftime('%Y-%m-%d %H:%M:%S')
                return f"{start_dt} ~ {end_dt}"
            else:
                # 인덱스 기반
                return f"인덱스 {int(xmin)} ~ {int(xmax)}"
        except:
            return f"{xmin:.2f} ~ {xmax:.2f}"
    
    def create_statistics_popup(self, data, stats, median_val, time_range):
        """통계 정보 팝업 창 생성 (가우시안 그래프 포함)"""
        # 전달된 데이터 정제: 빈값/비숫자 -> NaN 처리 후 제거
        try:
            data = pd.to_numeric(data, errors='coerce').dropna()
        except Exception:
            try:
                data = data.dropna()
            except Exception:
                messagebox.showwarning("경고", "선택된 데이터가 비어있거나 처리할 수 없습니다.")
                return

        if len(data) == 0:
            messagebox.showwarning("경고", "선택된 범위에 유효한 숫자 데이터가 없습니다.")
            return

        # 통계 재계산 (정제된 데이터 기준)
        stats = data.describe()
        median_val = data.median()
        # 팝업 창 생성
        popup = tk.Toplevel(self.parent_frame)
        popup.title("선택 구간 통계 분석")
        popup.geometry("800x600")
        popup.resizable(True, True)
        
        # 메인 프레임
        main_frame = ttk.Frame(popup)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 상단 정보 프레임
        info_frame = ttk.LabelFrame(main_frame, text="선택 구간 정보", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 시간 범위와 데이터 개수
        ttk.Label(info_frame, text=f"시간 범위: {time_range}", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"데이터 포인트: {len(data):,}개", font=('Arial', 11)).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"컬럼: {self.current_column}", font=('Arial', 11)).pack(anchor=tk.W)
        
        # 통계 정보 프레임
        stats_frame = ttk.LabelFrame(main_frame, text="기본 통계", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 두 개 컬럼으로 통계 정보 배치
        left_stats = ttk.Frame(stats_frame)
        left_stats.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        right_stats = ttk.Frame(stats_frame)
        right_stats.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 왼쪽 통계
        ttk.Label(left_stats, text=f"평균: {self.format_number_km(stats['mean'])}", font=('Arial', 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(left_stats, text=f"중간값: {self.format_number_km(median_val)}", font=('Arial', 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(left_stats, text=f"표준편차: {self.format_number_km(stats['std'])}", font=('Arial', 10)).pack(anchor=tk.W, pady=2)
        # 오른쪽 통계
        ttk.Label(right_stats, text=f"최댓값: {self.format_number_km(stats['max'])}", font=('Arial', 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(right_stats, text=f"최솟값: {self.format_number_km(stats['min'])}", font=('Arial', 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(right_stats, text=f"범위: {self.format_number_km(stats['max'] - stats['min'])}", font=('Arial', 10)).pack(anchor=tk.W, pady=2)

        # --- Gaussian 신뢰구간 정보 추가 ---
        ci_frame = ttk.LabelFrame(main_frame, text="📊 신뢰 구간 (Gaussian, 1D)", padding=8)
        ci_frame.pack(fill=tk.X, pady=(0, 10))

        # 신뢰구간 기준값 (이론적 포함확률)
        sigma_levels = [1, 2, 3, 4, 5]
        theoretical = {1:68.27, 2:95.45, 3:99.73, 4:99.9937, 5:99.99994}

        # 실측 포함비율 계산
        mean_val = stats['mean']
        std_val = stats['std']
        min_val = stats['min']
        max_val = stats['max']

        # 각 sigma 레벨에 대해 범위를 계산하고 데이터 내 포함 비율 산출
        actual_percent = {}
        try:
            for s in sigma_levels:
                low = mean_val - s * std_val
                high = mean_val + s * std_val
                count_in = ((data >= low) & (data <= high)).sum()
                pct = 100.0 * count_in / len(data)
                actual_percent[s] = pct
        except Exception:
            # 계산 실패시 0으로 초기화
            actual_percent = {s: 0.0 for s in sigma_levels}

        # 표 헤더
        hdr = ttk.Frame(ci_frame)
        hdr.pack(fill=tk.X)
        ttk.Label(hdr, text="범위 (평균 ± kσ)", width=30, font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Label(hdr, text="포함 확률(%)", width=18, font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Label(hdr, text="해석", width=30, font=('Arial', 10, 'bold')).pack(side=tk.LEFT)

        # 각 행 추가
        interpretation = {
            1: '데이터의 3분의 2',
            2: '데이터의 대부분',
            3: '거의 전부',
            4: '극히 예외만 바깥',
            5: '물리학(입자 실험)에서 “발견” 판정 기준'
        }

        for s in sigma_levels:
            row = ttk.Frame(ci_frame)
            row.pack(fill=tk.X)
            ttk.Label(row, text=f"± {s}σ", width=8, font=('Arial', 10)).pack(side=tk.LEFT)
            ttk.Label(row, text=f"약 {theoretical[s]} %", width=22, font=('Arial', 10)).pack(side=tk.LEFT)
            ttk.Label(row, text=interpretation[s], width=38, font=('Arial', 10)).pack(side=tk.LEFT)
            # 실제 포함률 표시 (오른쪽 정렬)
            ttk.Label(row, text=f"실측: {actual_percent.get(s, 0.0):.2f} %", font=('Arial', 10)).pack(side=tk.RIGHT)

        # 값이 어떤 sigma 구간에 속하는지 판정하는 작은 헬퍼
        def which_sigma_bin(val):
            if std_val is None or np.isnan(std_val) or std_val == 0:
                return 'σ 계산 불가'
            dist = abs(val - mean_val)
            for s in sigma_levels:
                if dist <= s * std_val:
                    return f'±{s}σ 이내'
            return f'>{sigma_levels[-1]}σ'

        # mean/median/min/max가 어느 구간에 속하는지 표시
        marker_frame = ttk.Frame(ci_frame)
        marker_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(marker_frame, text=f"평균: {self.format_number_km(mean_val)} ({which_sigma_bin(mean_val)})", font=('Arial', 10)).pack(anchor=tk.W)
        ttk.Label(marker_frame, text=f"중간값: {self.format_number_km(median_val)} ({which_sigma_bin(median_val)})", font=('Arial', 10)).pack(anchor=tk.W)
        ttk.Label(marker_frame, text=f"최솟값: {self.format_number_km(min_val)} ({which_sigma_bin(min_val)})", font=('Arial', 10)).pack(anchor=tk.W)
        ttk.Label(marker_frame, text=f"최댓값: {self.format_number_km(max_val)} ({which_sigma_bin(max_val)})", font=('Arial', 10)).pack(anchor=tk.W)

        # --- 분포 등급(B): 전체 분포를 하나의 σ 레벨로 분류하여 요약 ---
        try:
            # 기준: 이론적 기대치의 90% 이상 실측되는 가장 작은 σ를 선택
            chosen_k = None
            for s in sigma_levels:
                if actual_percent.get(s, 0.0) >= (theoretical[s] * 0.9):
                    chosen_k = s
                    break

            # 없으면 실제/이론 비율이 가장 큰 σ를 선택
            if chosen_k is None:
                best_ratio = -1.0
                best_s = sigma_levels[-1]
                for s in sigma_levels:
                    th = theoretical[s]
                    if th <= 0:
                        continue
                    ratio = actual_percent.get(s, 0.0) / th
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_s = s
                chosen_k = best_s

            chosen_pct = actual_percent.get(chosen_k, 0.0)
            chosen_theo = theoretical.get(chosen_k, 0.0)
            summary_text = f"분포 등급: ±{chosen_k}σ — 실측 {chosen_pct:.2f}% (이론 {chosen_theo}%)"
        except Exception:
            summary_text = "분포 등급: 계산 실패"

        summary_lbl = ttk.Label(ci_frame, text=summary_text, font=('Arial', 10, 'bold'))
        summary_lbl.pack(fill=tk.X, pady=(6, 0))

        # 그래프 프레임
        graph_frame = ttk.LabelFrame(main_frame, text="데이터 분포 (히스토그램 + 가우시안 피팅)", padding=5)
        graph_frame.pack(fill=tk.BOTH, expand=True)
        
        # matplotlib 그래프 생성
        fig, ax = plt.subplots(figsize=(10, 4))

        # --- 히스토그램과 가우시안 플롯 (인라인으로 구현) ---
        # 히스토그램 그리기 (개수로 표시)
        n_bins = min(30, max(10, len(data) // 10))  # 적절한 bin 수 계산
        n, bins, patches = ax.hist(data, bins=n_bins, density=False, alpha=0.7,
                                 color='skyblue', edgecolor='black', linewidth=0.5)

        # 가우시안 곡선 피팅 (안정성 향상)
        try:
            mu = stats['mean']
            sigma = stats['std']

            # x 범위 생성
            x_min = data.min()
            x_max = data.max()
            if x_min == x_max:
                x_range = np.array([x_min])
            else:
                x_range = np.linspace(x_min, x_max, 200)

            # 히스토그램의 bin 너비 계산 (안전 검사)
            try:
                bin_width = float(bins[1] - bins[0]) if len(bins) > 1 else (x_max - x_min) if x_max != x_min else 1.0
            except Exception:
                bin_width = 1.0

            N = len(data)  # 전체 데이터 개수

            # sigma가 0이거나 NaN이면 가우시안 곡선을 그리지 않음 (대신 평균선만 표시)
            if sigma is None or np.isnan(sigma) or sigma == 0:
                ax.axvline(mu, color='red', linestyle='--', alpha=0.8, label=f'평균: {mu:.3f}')
                ax.axvline(median_val, color='green', linestyle='--', alpha=0.8, label=f'중간값: {median_val:.3f}')
            else:
                # scipy가 있으면 사용, 없으면 직접 계산
                try:
                    from scipy.stats import norm
                    pdf_vals = norm.pdf(x_range, mu, sigma)
                except Exception:
                    pdf_vals = (1.0 / (sigma * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_range - mu) / sigma) ** 2)

                # N * bin_width * pdf(x; μ,σ) 공식 사용하여 스케일 맞춤
                gaussian_curve = N * bin_width * pdf_vals
                ax.plot(x_range, gaussian_curve, 'r-', linewidth=2, label=f'가우시안 피팅\n(μ={mu:.3f}, σ={sigma:.3f})')
                ax.axvline(mu, color='red', linestyle='--', alpha=0.8, label=f'평균: {mu:.3f}')
                ax.axvline(median_val, color='green', linestyle='--', alpha=0.8, label=f'중간값: {median_val:.3f}')

        except Exception as e:
            print(f"가우시안 플롯 오류: {e}")

        ax.set_xlabel(f'{self.current_column}')
        ax.set_ylabel('개수 (count)')
        ax.set_title('데이터 분포 및 가우시안 피팅')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # 캔버스에 그래프 추가
        canvas = FigureCanvasTkAgg(fig, graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 툴바 추가
        toolbar = NavigationToolbar2Tk(canvas, graph_frame)
        toolbar.update()

        # 버튼 프레임
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # 닫기 버튼
        close_btn = ttk.Button(button_frame, text="닫기", command=popup.destroy)
        close_btn.pack(side=tk.RIGHT)

        # 데이터 내보내기 버튼
        export_btn = ttk.Button(button_frame, text="데이터 내보내기",
                                command=lambda: self.export_selected_data(data, time_range))
        export_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # 창을 화면 중앙에 배치
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (popup.winfo_width() // 2)
        y = (popup.winfo_screenheight() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")

        # 포커스 설정
        popup.focus_set()

    def format_number_km(self, value):
        """숫자를 K/M 단위로 변환"""
        try:
            abs_val = abs(value)
            if abs_val >= 1e6:
                return f"{value/1e6:.3f}M"
            elif abs_val >= 1e3:
                return f"{value/1e3:.3f}K"
            else:
                return f"{value:.3f}"
        except:
            return str(value)

    def export_selected_data(self, data, time_range):
        """선택된 데이터를 CSV로 내보내기"""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title=f"선택 구간 데이터 저장 ({time_range})"
            )
            
            if filename:
                data.to_csv(filename, index=True, header=True)
                messagebox.showinfo("저장 완료", f"데이터가 저장되었습니다:\n{filename}")
        except Exception as e:
            messagebox.showerror("저장 오류", f"데이터 저장 중 오류가 발생했습니다:\n{e}")
    

    
    def setup_ui(self):
        """UI 설정"""
        # 메인 프레임
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 상단 제어 패널
        control_frame = ttk.LabelFrame(main_frame, text="CNT 데이터 제어판", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 데이터 로드 영역
        load_frame = ttk.Frame(control_frame)
        load_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(load_frame, text="데이터 상태:", width=12).pack(side=tk.LEFT)
        
        load_all_btn = ttk.Button(load_frame, text="모든 파일 로드", command=self.load_all_files, width=15)
        load_all_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        load_selected_btn = ttk.Button(load_frame, text="선택 파일 로드", command=self.load_selected_files, width=15)
        load_selected_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 데이터 정보 영역
        info_frame = ttk.Frame(control_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.info_label = ttk.Label(info_frame, text="파일을 선택하세요...", font=('Arial', 9))
        self.info_label.pack(side=tk.LEFT)
        
        # 플롯 옵션 영역
        plot_frame = ttk.Frame(control_frame)
        plot_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(plot_frame, text="Y축 컬럼:", width=12).pack(side=tk.LEFT)
        
        self.column_var = tk.StringVar()
        self.column_combo = ttk.Combobox(plot_frame, textvariable=self.column_var, width=30, state="readonly")
        self.column_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        plot_btn = ttk.Button(plot_frame, text="플롯 생성", command=self.create_plot, width=12)
        plot_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        clear_btn = ttk.Button(plot_frame, text="플롯 지우기", command=self.clear_plot, width=12)
        clear_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # 테스트 데이터 생성 버튼 추가
        test_btn = ttk.Button(plot_frame, text="테스트 데이터", command=self.create_test_data, width=12)
        test_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # 플롯 영역
        plot_frame = ttk.LabelFrame(main_frame, text="데이터 플롯", padding=5)
        plot_frame.pack(fill=tk.BOTH, expand=True)
        
        # matplotlib 피규어 초기화
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.ax.set_title("CNT 모니터링 데이터")
        self.ax.set_xlabel("시간")
        self.ax.set_ylabel("값")
        self.ax.grid(True, alpha=0.3)
        
        # 캔버스 생성
        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 툴바 추가
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        
    
    def refresh_file_list(self):
        """파일 목록 새로고침 후 다시 로드"""
        self.load_all_files()
    
    def load_selected_files(self):
        """사용자가 선택한 파일들만 로드"""
        try:
            # 파일 선택 다이얼로그
            from tkinter import filedialog
            
            # 초기 디렉토리를 데이터 경로로 설정
            initial_dir = self.data_path if os.path.exists(self.data_path) else os.getcwd()
            
            # 복수 파일 선택 가능한 다이얼로그
            file_paths = filedialog.askopenfilenames(
                title="로드할 파일들을 선택하세요",
                initialdir=initial_dir,
                filetypes=[
                    ("Excel/CSV files", "*.xlsx *.xls *.csv"),
                    ("Excel files", "*.xlsx *.xls"),
                    ("CSV files", "*.csv"),
                    ("All files", "*.*")
                ]
            )
            
            if not file_paths:
                # 사용자가 취소한 경우
                return
            
            # 선택된 파일들을 처리 (load_all_files와 유사한 로직)
            self._load_files_from_paths(file_paths, "선택된")
            
        except Exception as e:
            self.info_label.config(text=f"파일 선택 오류: {e}")
    
    def _load_files_from_paths(self, file_paths, load_type=""):
        """주어진 파일 경로들로부터 데이터를 로드하는 공통 메서드"""
        try:
            if not file_paths:
                self.info_label.config(text="로드할 파일이 없습니다")
                return
            
            # 시간순 정렬 (파일 수정 시간 기준)
            try:
                file_paths = sorted(file_paths, key=lambda x: os.path.getmtime(x))
            except:
                # 파일 시간 정보를 가져올 수 없는 경우 이름순 정렬
                file_paths = sorted(file_paths)
            
            self.info_label.config(text=f"🔄 로딩 중... 총 {len(file_paths)}개 {load_type} 파일 처리")
            
            # 모든 파일 로드 및 통합
            all_data = []
            loaded_files = []
            
            for file_path in file_paths:
                try:
                    file_name = os.path.basename(file_path)
                    
                    # 파일 형식에 따라 읽기
                    if file_path.endswith('.csv'):
                        df = pd.read_csv(file_path)
                    else:
                        df = pd.read_excel(file_path)
                    
                    # 파일명을 데이터에 추가 (선택사항)
                    df['source_file'] = file_name
                    
                    all_data.append(df)
                    loaded_files.append(file_name)
                    
                except Exception as e:
                    print(f"파일 로드 실패 {file_name}: {e}")
                    continue
            
            if not all_data:
                self.info_label.config(text="로드 가능한 파일이 없습니다")
                return
            
            # 모든 데이터 통합 (FutureWarning 방지)
            self.current_data = pd.concat(all_data, ignore_index=True, sort=False)

            # 빈 문자열(비어있는 값)을 NaN으로 처리
            try:
                self.current_data.replace(r'^\s*$', np.nan, regex=True, inplace=True)
            except Exception:
                pass

            # 가능한 경우, 숫자형으로 변환하여 숫자형 컬럼으로 취급되게 함 (비정상 값은 NaN으로 변환)
            for col in self.current_data.columns:
                if col == 'source_file':
                    continue
                # 시간 컬럼은 건너뜀
                if any(k in col.lower() for k in ('time', 'date', '시간')):
                    continue
                try:
                    conv = pd.to_numeric(self.current_data[col], errors='coerce')
                    # 숫자로 변환 가능한 값이 있으면 컬럼을 치환
                    if conv.notna().sum() > 0:
                        self.current_data[col] = conv
                except Exception:
                    continue

            # 시간 컬럼이 있으면 정렬
            time_columns = [col for col in self.current_data.columns 
                          if 'time' in col.lower() or 'date' in col.lower() or '시간' in col]
            
            if time_columns:
                time_col = time_columns[0]
                try:
                    self.current_data[time_col] = pd.to_datetime(self.current_data[time_col])
                    self.current_data = self.current_data.sort_values(time_col).reset_index(drop=True)
                except:
                    pass  # 시간 정렬 실패시 무시
            
            # 컬럼 정보 업데이트
            numeric_columns = self.current_data.select_dtypes(include=[np.number]).columns.tolist()
            # source_file 컬럼 제외
            numeric_columns = [col for col in numeric_columns if col != 'source_file']
            
            self.column_combo['values'] = numeric_columns
            
            # 정보 표시
            total_rows = len(self.current_data)
            time_range = ""
            if time_columns:
                try:
                    min_time = self.current_data[time_columns[0]].min()
                    max_time = self.current_data[time_columns[0]].max()
                    time_range = f" | 시간범위: {min_time} ~ {max_time}"
                except:
                    pass
            
            info_text = f"✅ {load_type} 통합 완료: {len(loaded_files)}개 파일, {total_rows:,}개 행, {len(numeric_columns)}개 수치 컬럼{time_range}"
            self.info_label.config(text=info_text)
            
            # 첫 번째 수치 컬럼을 기본 선택
            if numeric_columns:
                self.column_combo.current(0)
                
        except Exception as e:
            self.info_label.config(text=f"파일 로드 오류: {e}")
            self.current_data = None

    def load_all_files(self):
        """모든 CNT 데이터 파일을 통합하여 로드"""
        try:
            if not os.path.exists(self.data_path):
                self.info_label.config(text=f"경로가 존재하지 않습니다: {self.data_path}")
                return
            
            # Excel 파일 찾기 (확장자별로)
            excel_patterns = ['*.xlsx', '*.xls', '*.csv']
            file_paths = []
            
            for pattern in excel_patterns:
                file_paths.extend(glob.glob(os.path.join(self.data_path, pattern)))
            
            if not file_paths:
                self.info_label.config(text="Excel/CSV 파일이 없습니다")
                return
            
            # 공통 로직 사용
            self._load_files_from_paths(file_paths, "전체")
                
        except Exception as e:
            self.info_label.config(text=f"파일 로드 오류: {e}")
            self.current_data = None
    

    
    def create_plot(self):
        """플롯 생성"""
        if self.current_data is None:
            messagebox.showwarning("데이터 없음", "먼저 파일을 선택하세요.")
            return
        
        selected_column = self.column_var.get()
        if not selected_column:
            messagebox.showwarning("컬럼 선택", "Y축 컬럼을 선택하세요.")
            return
        
        try:
            # 기존 플롯 지우기
            self.ax.clear()
            
            # 시간 컬럼 찾기
            time_columns = [col for col in self.current_data.columns 
                          if 'time' in col.lower() or 'date' in col.lower() or '시간' in col]
            
            if time_columns:
                time_col = time_columns[0]
                # 시간 컬럼을 datetime으로 변환
                try:
                    x_data = pd.to_datetime(self.current_data[time_col])
                    self.ax.plot(x_data, self.current_data[selected_column], 'b-', linewidth=1.2, markersize=2)
                    self.ax.set_xlabel("시간")
                    
                    # 시간 축 포맷팅
                    self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
                    self.ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
                    plt.setp(self.ax.xaxis.get_majorticklabels(), rotation=45)
                    
                except:
                    # 시간 변환 실패시 인덱스 사용
                    self.ax.plot(self.current_data.index, self.current_data[selected_column], 'b-', linewidth=1.2)
                    self.ax.set_xlabel("인덱스")
            else:
                # 시간 컬럼이 없으면 인덱스 사용
                self.ax.plot(self.current_data.index, self.current_data[selected_column], 'b-', linewidth=1.2)
                self.ax.set_xlabel("인덱스")
            
            self.ax.set_ylabel(selected_column)
            # 통합된 파일 수 표시
            unique_files = self.current_data['source_file'].nunique() if 'source_file' in self.current_data.columns else 1
            self.ax.set_title(f"CNT 통합 데이터: {selected_column} ({unique_files}개 파일, {len(self.current_data):,}개 데이터 포인트)\n[툴바: 확대/축소/팬 | 드래그: 데이터 선택]")
            self.ax.grid(True, alpha=0.3)
            
            # 현재 컬럼 저장 (드래그 선택 시 사용)
            self.current_column = selected_column
            
            # 기존 통계 텍스트 제거
            if self.stats_text_obj:
                self.stats_text_obj.remove()
                self.stats_text_obj = None
            
            # SpanSelector를 사용한 드래그 선택 기능 (로그 데이터 리더 방식)
            if self.span_selector:
                self.span_selector.disconnect_events()
            
            self.span_selector = SpanSelector(self.ax, self.on_span_select, 'horizontal', 
                                            useblit=True, 
                                            props=dict(alpha=0.3, facecolor='red'))
            
            print("SpanSelector 드래그 선택 기능 연결 완료")
            
            self.fig.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            messagebox.showerror("플롯 오류", f"플롯 생성 중 오류가 발생했습니다:\n{e}")
    
    def clear_plot(self):
        """플롯 지우기"""
        # SpanSelector 제거
        if self.span_selector:
            self.span_selector.disconnect_events()
            self.span_selector = None
        
        # 통계 텍스트 제거
        if self.stats_text_obj:
            self.stats_text_obj.remove()
            self.stats_text_obj = None
        

        
        # 현재 컬럼 초기화
        self.current_column = None
        
        self.ax.clear()
        self.ax.set_title("CNT 모니터링 데이터")
        self.ax.set_xlabel("시간")
        self.ax.set_ylabel("값")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()
    
    def create_test_data(self):
        """테스트용 더미 데이터 생성"""
        try:
            # 현재 시간부터 100개의 데이터 포인트 생성
            import numpy as np
            from datetime import datetime, timedelta
            
            start_time = datetime.now()
            times = [start_time + timedelta(minutes=i) for i in range(100)]
            
            # 가상의 CNT 데이터 (노이즈가 있는 사인파)
            np.random.seed(42)  # 재현 가능한 결과를 위해
            base_signal = np.sin(np.linspace(0, 4*np.pi, 100)) * 10 + 50
            noise = np.random.normal(0, 2, 100)
            cnt_values = base_signal + noise
            
            # DataFrame 생성
            self.current_data = pd.DataFrame({
                'timestamp': times,
                'CNT_Value': cnt_values,
                'source_file': ['test_data.xlsx'] * 100
            })
            
            # 컬럼 콤보박스 업데이트
            numeric_columns = ['CNT_Value']
            self.column_combo['values'] = numeric_columns
            if numeric_columns:
                self.column_combo.current(0)
            
            self.info_label.config(text=f"테스트 데이터 생성 완료: {len(self.current_data)}개 포인트")
            
        except Exception as e:
            self.info_label.config(text=f"테스트 데이터 생성 오류: {e}")
    
    def get_data_summary(self):
        """현재 데이터의 요약 정보 반환"""
        if self.current_data is None:
            return "데이터가 없습니다."
        
        # 통합된 파일 수 계산
        unique_files = self.current_data['source_file'].nunique() if 'source_file' in self.current_data.columns else 1
        
        summary = f"통합 데이터: {unique_files}개 파일\n"
        summary += f"행 수: {len(self.current_data):,}\n"
        summary += f"열 수: {len(self.current_data.columns)}\n"
        summary += f"수치 컬럼: {len(self.current_data.select_dtypes(include=[np.number]).columns)}"
        
        return summary


# 편의 함수
def create_cnt_data_plotter(parent_frame):
    """CNTDataPlotter 인스턴스 생성 편의 함수"""
    return CNTDataPlotter(parent_frame)
