"""
데이터베이스 파일 처리 모듈 (Polars 기반)
DB 파일 읽기, PLC 복원, CNT 데이터 필터링, 구간 분석 기능을 제공합니다.
Polars를 기본으로 사용하며, matplotlib 호환을 위해 필요한 부분만 pandas로 변환
"""

import sqlite3
try:
    from print_utils import tprint
except ImportError:
    # print_utils가 없으면 일반 print 사용
    def tprint(*args, **kwargs):
        import datetime
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        message_parts = [timestamp] + [str(arg) for arg in args]
        message = " ".join(message_parts)
        if 'sep' not in kwargs:
            kwargs['sep'] = ' '
        if 'end' not in kwargs:
            kwargs['end'] = '\n'
        print(message, **kwargs)
import polars as pl  # Polars는 항상 사용 가능하다고 가정
POLARS_AVAILABLE = True

# matplotlib 호환을 위한 pandas (최소한만 사용)
import pandas as pd
import numpy as np
import re
import datetime
import os
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk, messagebox
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import hashlib
import pickle


def extract_date_from_filename(filename):
    """
    파일명에서 YYYY-MM-DD 형식의 날짜 추출
    
    Args:
        filename: 파일명 (경로 포함 가능)
        
    Returns:
        datetime.datetime: 추출된 날짜, 실패 시 None
    """
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", os.path.basename(filename))
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return datetime.datetime(year, month, day)
        except ValueError:
            return None
    return None


# ============================================================================
# 1. 벡터화된 DateTime 변환 알고리즘 (Polars 기반)
# ============================================================================

def convert_datetime_vectorized_polars(lf_or_df, time_col, base_date):
    """
    Polars DataFrame/LazyFrame을 사용한 벡터화 datetime 변환
    
    Args:
        lf_or_df: Polars DataFrame 또는 LazyFrame
        time_col: 시간 컬럼명
        base_date: 기본 날짜 (datetime 객체)
        
    Returns:
        Polars LazyFrame: datetime 컬럼이 추가된 LazyFrame
    """
    try:
        # base_date를 Polars datetime literal로 생성
        base_datetime = datetime.datetime(
            base_date.year, base_date.month, base_date.day,
            0, 0, 0
        )
        base_date_pl = pl.lit(base_datetime).cast(pl.Datetime)
        
        # 스키마에서 타입 확인 (LazyFrame인 경우 collect_schema() 사용)
        if hasattr(lf_or_df, 'collect_schema'):
            # LazyFrame: collect_schema()로 경량 스키마 확인
            schema = lf_or_df.collect_schema()
            col_dtype = schema.get(time_col)
        elif hasattr(lf_or_df, 'schema'):
            # DataFrame: 직접 schema 속성 사용
            schema = lf_or_df.schema
            col_dtype = schema.get(time_col) if hasattr(schema, 'get') else None
        else:
            col_dtype = None
        
        if col_dtype == pl.Datetime:
            # datetime 타입: 날짜는 base_date, 시간만 추출하여 더하기
            # 시간을 초로 변환 (벡터화)
            time_seconds = (
                pl.col(time_col).dt.hour() * 3600
                + pl.col(time_col).dt.minute() * 60
                + pl.col(time_col).dt.second()
                + pl.col(time_col).dt.microsecond() / 1_000_000  # 마이크로초를 초로 변환
            )
            datetime_expr = base_date_pl + pl.duration(seconds=time_seconds)
        else:
            # 숫자 타입: 초 단위로 해석하여 base_date에 더하기
            datetime_expr = (
                base_date_pl 
                + pl.duration(seconds=pl.col(time_col).cast(pl.Int64))
            )
        
        return lf_or_df.with_columns([
            datetime_expr.alias("datetime")
        ])
        
    except Exception as e:
        print(f"Polars datetime 변환 실패, pandas fallback 사용: {e}")
        # fallback: pandas로 변환 후 처리
        if hasattr(lf_or_df, 'collect'):
            df_pd = lf_or_df.collect().to_pandas()
        elif hasattr(lf_or_df, 'to_pandas'):
            df_pd = lf_or_df.to_pandas()
        else:
            df_pd = lf_or_df
            
        df_pd['datetime'] = convert_datetime_vectorized(df_pd[time_col], base_date)
        return pl.from_pandas(df_pd).lazy()


# ============================================================================
# 2. PLC Error 기반 NaN 복원 알고리즘 (Polars 기반)
# ============================================================================

def restore_plc_error_data_polars(lf, plc_error_col, cols_in_db):
    """
    Polars 기반 PLC error 정보를 사용한 NaN 데이터 복원
    
    Args:
        lf: Polars LazyFrame
        plc_error_col: PLC error 컬럼명
        cols_in_db: 복원할 파라미터 컬럼 리스트
        
    Returns:
        Polars LazyFrame: 복원된 LazyFrame (collect는 호출하지 않음)
    """
    # LazyFrame 스키마에서 컬럼 목록 가져오기 (성능 경고 방지)
    schema_names = lf.collect_schema().names()
    if plc_error_col is None or plc_error_col not in schema_names:
        return lf
    
    tprint(f"PLC error 초고속 복원 시작 (Polars): {plc_error_col}")
    
    # 1. PLC 상태 복원
    # 첫 유효값을 찾기 위해 먼저 collect (작은 작업)
    df_temp = lf.select(pl.col(plc_error_col)).head(1000).collect()
    initial_state = 0
    if len(df_temp) > 0 and df_temp[plc_error_col].is_not_null().any():
        first_valid = df_temp.filter(pl.col(plc_error_col).is_not_null())
        if len(first_valid) > 0:
            initial_state = int(first_valid[plc_error_col][0])
    
    # PLC error 컬럼 forward fill
    lf = lf.with_columns([
        pl.col(plc_error_col)
        .forward_fill()
        .fill_null(initial_state)
        .cast(pl.Int64)
        .alias(plc_error_col)
    ])
    
    # 2. 에러 마스크 생성
    error_mask = pl.col(plc_error_col) == 1
    valid_mask = pl.col(plc_error_col) == 0
    
    # 3. 모든 파라미터를 한 번에 복원 (벡터화 최적화)
    schema_names = lf.collect_schema().names()
    restore_columns = []
    
    for param in cols_in_db:
        if param in schema_names and param != plc_error_col:
            # 에러 구간은 null로 마스킹하고 forward fill
            filled_col = (
                pl.when(error_mask)
                .then(None)  # 에러 구간은 null
                .otherwise(pl.col(param))
                .forward_fill()
            )
            
            # 정상 구간에서만 복원된 값 사용
            restore_columns.append(
                pl.when(valid_mask & filled_col.is_not_null())
                .then(filled_col)
                .otherwise(pl.col(param))
                .alias(param)
            )
    
    # 모든 파라미터를 한 번에 처리 (단일 with_columns 호출로 최적화)
    if restore_columns:
        lf = lf.with_columns(restore_columns)
    
    tprint(f"  처리 완료 (Polars, {len(restore_columns)}개 파라미터)")
    
    return lf


# ============================================================================
# 1. 벡터화된 DateTime 변환 알고리즘 (Pandas 호환 - fallback용)
# ============================================================================

def make_to_datetime_safe(base_date):
    """
    안전한 datetime 변환 함수를 생성하는 팩토리 함수
    
    Args:
        base_date: 기본 날짜 (datetime 객체)
        
    Returns:
        to_datetime_safe 함수
    """
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


def convert_datetime_vectorized(series, base_date):
    """
    pandas Series를 벡터화 방식으로 datetime 변환
    
    Args:
        series: 변환할 pandas Series (시간 데이터)
        base_date: 기본 날짜 (datetime 객체)
        
    Returns:
        pandas Series: datetime 변환된 Series
    """
    try:
        # 1. NaN 값 처리
        valid_mask = pd.notna(series)
        result = pd.Series(pd.NaT, index=series.index, dtype='datetime64[ns]')
        
        if not valid_mask.any():
            return result
            
        valid_series = series[valid_mask]
        
        # 2. 이미 datetime 타입인 경우 (벡터화 처리)
        datetime_mask = valid_series.apply(lambda x: isinstance(x, (pd.Timestamp, datetime.datetime)))
        if datetime_mask.any():
            # datetime 타입 값들을 Series로 변환 (dt accessor 사용을 위해)
            datetime_series = pd.to_datetime(valid_series[datetime_mask])
            
            # numpy 기반으로 시간 부분을 timedelta로 변환
            time_seconds = (
                datetime_series.dt.hour * 3600
                + datetime_series.dt.minute * 60
                + datetime_series.dt.second
                + datetime_series.dt.microsecond / 1_000_000  # 마이크로초도 포함
            )
            
            # base_date에 시간 부분을 더해서 최종 datetime 생성
            result.loc[datetime_series.index] = pd.Timestamp(base_date) + pd.to_timedelta(time_seconds, unit='s')
        
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


# ============================================================================
# 2. PLC Error 기반 NaN 복원 알고리즘 (Pandas 호환 - fallback용)
# ============================================================================

def restore_plc_error_data(df, plc_error_col, cols_in_db):
    """
    PLC error 정보를 기반으로 NaN 데이터를 복원하는 함수 (초고속 세그먼트 기반)
    
    Args:
        df: 처리할 DataFrame
        plc_error_col: PLC error 컬럼명
        cols_in_db: 복원할 파라미터 컬럼 리스트
        
    Returns:
        DataFrame: 복원된 DataFrame
    """
    if plc_error_col is None or plc_error_col not in df.columns:
        return df
    
    print(f"PLC error 초고속 복원 시작: {plc_error_col}")
    
    # 1. PLC 상태 복원 (fillna 한 번만 사용)
    plc_raw = df[plc_error_col].copy()
    first_valid = plc_raw.first_valid_index()
    initial_state = 0 if first_valid is None else int(plc_raw.loc[first_valid])
    
    # 매우 빠른 forward fill
    plc_restored = plc_raw.fillna(method='ffill').fillna(initial_state).astype(int)
    df[plc_error_col] = plc_restored
    
    # 2. 에러 구간 찾기 (벡터화)
    error_mask = plc_restored == 1
    valid_mask = plc_restored == 0  # 정상 구간 마스크
    
    # 3. 벡터화 기반 복원 (한 번에 처리)
    for param in cols_in_db:
        if param in df.columns and param != plc_error_col:
            original_nan_count = df[param].isna().sum()
            
            if original_nan_count > 0:
                # 에러 구간을 NaN으로 마스킹하여 forward fill이 전파되지 않도록 함
                param_data = df[param].copy()
                param_data[error_mask] = np.nan
                
                # forward fill 적용 (에러 구간은 NaN으로 유지되어 전파 방지)
                filled_data = param_data.fillna(method='ffill')
                
                # 정상 구간에서만 복원된 값을 사용
                # where: valid_mask가 False(에러)이면 원래 값, True(정상)이면 filled_data 사용
                df[param] = df[param].where(~valid_mask, filled_data)
                
                restored_nan_count = df[param].isna().sum()
                restored_count = original_nan_count - restored_nan_count
                
                if restored_count > 0:
                    print(f"  {param}: {restored_count} 포인트 복원")
    
    # 세그먼트 개수 계산 (로깅용)
    error_diff = error_mask.astype(int).diff().fillna(0)
    error_start_indices = df.index[error_diff == 1].tolist()
    segments_count = len(error_start_indices)
    
    print(f"  처리 완료: {segments_count + 1}개 정상 세그먼트 (추정)")
    print(f"  PLC error 구간: {error_mask.sum()} 포인트")
    
    return df


# ============================================================================
# DB 파일 읽기 함수
# ============================================================================

def is_restored_file(file_path):
    """
    파일명이 'restored'로 끝나는지 확인
    
    Args:
        file_path: 파일 경로
        
    Returns:
        bool: 파일명이 'restored'로 끝나면 True
    """
    filename = os.path.basename(file_path)
    # 확장자 제거 후 확인
    name_without_ext = os.path.splitext(filename)[0]
    return name_without_ext.lower().endswith('restored')


def read_db_file(db_path, params_to_read, time_cols, convert_datetime_vectorized):
    """
    DB 파일 읽기 함수 - PLC 복원 기능 포함 (Polars 기반)
    
    Args:
        db_path: 데이터베이스 파일 경로
        params_to_read: 읽을 파라미터 리스트
        time_cols: 시간 컬럼 리스트
        convert_datetime_vectorized: 벡터화된 datetime 변환 함수 (호환성 유지용, 사용 안 함)
        
    Returns:
        pd.DataFrame: 처리된 데이터프레임 (matplotlib 호환을 위해 pandas로 반환)
    """
    if not POLARS_AVAILABLE:
        raise ImportError("Polars가 필요합니다. 설치: pip install polars")
    
    # 파일명이 'restored'로 끝나면 PLC 복원 건너뛰기
    skip_plc_restoration = is_restored_file(db_path)
    
    # SQLite 연결 최적화 및 스키마 확인 (Polars로 직접)
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        # SQLite 성능 최적화 PRAGMA 설정
        conn.execute("PRAGMA journal_mode=OFF")  # WAL 비활성화 (읽기 전용 시)
        conn.execute("PRAGMA synchronous=OFF")   # 동기화 비활성화 (속도 향상)
        conn.execute("PRAGMA cache_size=-100000")  # 캐시 크기 증가 (100MB)
        
        # Polars로 직접 스키마 확인 (pandas 거치지 않음)
        try:
            schema_df = pl.read_database(
                query="PRAGMA table_info(data)",
                connection=conn
            )
            available_cols = schema_df['name'].to_list()
        except Exception:
            # Polars로 실패 시 최소한만 pandas 사용 (fallback)
            pragma_df = pd.read_sql_query("PRAGMA table_info(data)", conn)
            available_cols = pragma_df['name'].tolist()
    except Exception as e:
        print(f"{db_path} 스키마 확인 실패: {e}")
        if conn:
            conn.close()
        return None

    # datetime 컬럼이 이미 있으면 그대로 사용 (병합 파일 처리)
    datetime_already_exists = 'datetime' in available_cols
    
    if datetime_already_exists:
        time_col = 'datetime'
    else:
        # time 컬럼 찾기 (기존 파일)
        time_col = next((c for c in time_cols if c in available_cols), None)
    if time_col is None:
        return None
    
    cols_in_db = [col for col in params_to_read if col in available_cols]
    if not cols_in_db:
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
    
    # Polars로 직접 SQLite 읽기 (LazyFrame으로 - 효율적)
    lf = None
    
    # 방법 1: sqlite3 연결 객체 사용 (최적화된 연결 재사용)
    try:
        if conn is None:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=OFF")
            conn.execute("PRAGMA synchronous=OFF")
            conn.execute("PRAGMA cache_size=-100000")
        
        # Polars로 직접 읽기 (LazyFrame 반환 시도)
        df_temp = pl.read_database(
            query=query,
            connection=conn
        )
        # LazyFrame으로 변환하여 연산 체이닝
        lf = df_temp.lazy()
        conn.close()
        conn = None
    except Exception as e:
        # 방법 2: connection_uri 사용
        try:
            if conn:
                conn.close()
                conn = None
            df_temp = pl.read_database_uri(
                uri=f"sqlite:///{db_path}",
                query=query,
                engine="connectorx"
            )
            lf = df_temp.lazy()
        except Exception as e2:
            # 방법 3: pandas로 읽어서 Polars로 변환 (최종 fallback)
            try:
                if conn is None:
                    conn = sqlite3.connect(db_path)
                df_pd_temp = pd.read_sql_query(query, conn)
                if conn:
                    conn.close()
                    conn = None
                df_temp = pl.from_pandas(df_pd_temp)
                lf = df_temp.lazy()
            except Exception as e3:
                print(f"{db_path} 읽기 실패: {e3}")
                if conn:
                    conn.close()
                return None
    
    # 컬럼 타입 변환을 LazyFrame 단계로 이동 (한 번에 처리)
    # LazyFrame에서 스키마 확인 (경량 작업)
    schema = lf.collect_schema()
    type_conversions = []
    
    for col in cols_in_db:
        if col in schema:
            col_dtype = schema[col]
            # Object나 Utf8 타입이면 Float64로 변환
            if col_dtype == pl.Object or col_dtype == pl.Utf8:
                type_conversions.append(
                    pl.col(col).cast(pl.Float64, strict=False).alias(col)
                )
    
    # 타입 변환을 한 번에 적용 (LazyFrame 유지)
    if type_conversions:
        lf = lf.with_columns(type_conversions)
    
    # datetime 컬럼이 이미 있으면 변환 과정 생략 (LazyFrame 체이닝 유지)
    if datetime_already_exists:
        # datetime 컬럼을 Polars datetime 타입으로 변환 (LazyFrame 단계)
        try:
            lf = lf.with_columns(
                pl.col('datetime').str.to_datetime().alias('datetime')
            )
        except Exception:
            # 이미 datetime 타입이거나 변환이 필요한 경우
            try:
                lf = lf.with_columns(
                    pl.col('datetime').cast(pl.Datetime).alias('datetime')
                )
            except Exception:
                pass  # 변환이 필요 없으면 그대로 유지
        
        # PLC error 기반 NaN 복원 (LazyFrame 체이닝 유지)
        # collect_schema()는 스키마만 확인하므로 경량 작업
        schema_names = lf.collect_schema().names()
        if plc_error_col and plc_error_col in schema_names and not skip_plc_restoration:
            lf = restore_plc_error_data_polars(lf, plc_error_col, cols_in_db)
        elif skip_plc_restoration:
            tprint(f"  파일명이 'restored'로 끝나므로 PLC 복원을 건너뜁니다: {os.path.basename(db_path)}")
        
    else:
        # 기존 로직: time 컬럼에서 datetime 생성 (원본 파일 처리)
        # 날짜 추출
        base_date = extract_date_from_filename(db_path)
        if base_date is None:
            tprint(f"경고: {os.path.basename(db_path)} 파일명에서 날짜를 찾을 수 없어 오늘 날짜를 사용합니다.")
            base_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # datetime 변환 (LazyFrame 체이닝 유지)
        lf = convert_datetime_vectorized_polars(lf, time_col, base_date)
        
        # PLC error 기반 NaN 복원 (LazyFrame 체이닝 유지)
        schema_names = lf.collect_schema().names()
        if plc_error_col and plc_error_col in schema_names and not skip_plc_restoration:
            lf = restore_plc_error_data_polars(lf, plc_error_col, cols_in_db)
        elif skip_plc_restoration:
            tprint(f"  파일명이 'restored'로 끝나므로 PLC 복원을 건너뜁니다: {os.path.basename(db_path)}")
    
    # LazyFrame 실행 - 마지막에 한 번만 collect() 호출
    df_pl_result = lf.collect()
    
    # matplotlib 호환을 위해 pandas로 변환 (마지막 단계)
    return df_pl_result.to_pandas()


def read_multiple_db_files_parallel(db_files, params_to_read, time_cols, convert_datetime_vectorized, 
                                     max_workers=None, skip_cnt_check=False):
    """
    여러 DB 파일을 병렬로 읽기 (ThreadPoolExecutor + Polars 병렬 처리)
    
    ThreadPoolExecutor로 여러 파일을 동시에 읽고, 각 파일 내부의 데이터 처리(PLC 복원, 변환 등)는 Polars가 병렬로 처리합니다.
    
    Args:
        db_files: 읽을 DB 파일 경로 리스트
        params_to_read: 읽을 파라미터 리스트
        time_cols: 시간 컬럼 리스트
        convert_datetime_vectorized: 벡터화된 datetime 변환 함수
        max_workers: 최대 병렬 작업 수 (None이면 자동 결정)
        skip_cnt_check: CNT 체크 건너뛰기 여부
        
    Returns:
        list: 읽은 DataFrame 리스트 (실패한 파일은 None)
    """
    
    if not db_files:
        return []
    
    # 최적의 워커 수 결정
    # I/O 바운드 작업(파일 읽기)이므로 논리 프로세서 수 활용
    if max_workers is None:
        import multiprocessing
        logical_processors = multiprocessing.cpu_count()  # 논리 프로세서 수
        physical_cores = logical_processors // 2  # 대략적인 물리 코어 수 (하이퍼스레딩 고려)
        
        # I/O 바운드 작업(파일 읽기)은 I/O 대기 시간이 많으므로
        # 논리 프로세서 수의 1.5배가 적절
        # 논리 프로세서 수에 따라 최대값 동적 조정:
        # - 8개 이하 (저사양): 최대 논리 프로세서 수의 2배 (예: 8개 → 최대 16개)
        # - 16개 이상 (고사양): 최대 32개로 제한
        recommended_workers = logical_processors + logical_processors // 2  # 논리 프로세서 수의 1.5배
        
        # 최대값 동적 조정
        if logical_processors <= 8:
            # 저사양 CPU (i5-1135G7 등): 논리 프로세서의 2배까지
            max_recommended = logical_processors * 2  # 8개 → 최대 16개
        else:
            # 고사양 CPU (i7-13700 등): 최대 32개로 제한
            max_recommended = 32
        
        recommended_workers = min(recommended_workers, max_recommended)
        recommended_workers = max(4, recommended_workers)  # 최소 4개
        max_workers = min(len(db_files), recommended_workers)
        
        # 설정 정보 출력
        tprint(f"  CPU 정보: {logical_processors} 논리 프로세서, {physical_cores} 물리 코어 (추정)")
        tprint(f"  권장 워커 수: {recommended_workers}개 (I/O 바운드 작업 최적화)")
    
    results = {}
    
    def read_single_file(db_path):
        """단일 파일 읽기 (병렬 실행용)"""
        try:
            # CNT 체크
            if not skip_cnt_check and is_cnt_related_data(db_path, params_to_read):
                return db_path, None, "CNT 관련 데이터 제외"
            
            # Polars가 내부적으로 병렬 처리하여 파일 읽기 및 PLC 복원 수행
            df = read_db_file(db_path, params_to_read, time_cols, convert_datetime_vectorized)
            if df is not None:
                return db_path, df, "성공"
            else:
                return db_path, None, "읽기 실패"
        except Exception as e:
            return db_path, None, f"오류: {str(e)}"
    
    # 병렬로 파일 읽기
    tprint(f"  설정: 최대 {max_workers}개 스레드로 {len(db_files)}개 파일 처리 (각 파일 내부는 Polars가 병렬 처리)")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 모든 파일 읽기 작업 제출
        future_to_file = {
            executor.submit(read_single_file, db_path): db_path 
            for db_path in db_files
        }
        
        # 진행 상황 추적
        completed = 0
        total = len(db_files)
        
        # 완료된 작업부터 결과 수집
        for future in as_completed(future_to_file):
            db_path, df, status = future.result()
            results[db_path] = (df, status)
            completed += 1
            
            # 진행 상황 출력
            filename = os.path.basename(db_path)
            
            # 남은 작업 수 계산 (제출된 작업 - 완료된 작업)
            remaining_tasks = total - completed
            
            if df is not None:
                tprint(f"  [완료] [{completed}/{total}] {filename}: {len(df):,} 행 (대기: {remaining_tasks}개)")
            else:
                tprint(f"  [오류] [{completed}/{total}] {filename}: {status} (대기: {remaining_tasks}개)")
    
    # 원본 파일 순서대로 결과 반환
    return [results.get(db_path, (None, "처리 안됨"))[0] for db_path in db_files]


# 메모리 캐싱을 위한 전역 캐시 (파일별, 파라미터별)
_cache = {}
_cache_max_size = 50  # 최대 캐시 항목 수


def _get_cache_key(db_path, params_to_read):
    """캐시 키 생성"""
    params_str = ','.join(sorted(params_to_read))
    return f"{db_path}::{params_str}"


def read_db_file_with_cache(db_path, params_to_read, time_cols, convert_datetime_vectorized, 
                             use_cache=True):
    """
    캐싱을 사용한 DB 파일 읽기 (같은 요청 재사용 시 즉시 반환)
    
    Args:
        db_path: DB 파일 경로
        params_to_read: 읽을 파라미터 리스트
        time_cols: 시간 컬럼 리스트
        convert_datetime_vectorized: 벡터화된 datetime 변환 함수
        use_cache: 캐시 사용 여부
        
    Returns:
        pd.DataFrame: 처리된 데이터프레임
    """
    if not use_cache:
        return read_db_file(db_path, params_to_read, time_cols, convert_datetime_vectorized)
    
    cache_key = _get_cache_key(db_path, params_to_read)
    
    # 캐시 확인
    if cache_key in _cache:
        cached_df, cached_time = _cache[cache_key]
        # 파일 수정 시간 확인 (파일이 변경되었으면 캐시 무효화)
        try:
            file_mtime = os.path.getmtime(db_path)
            if cached_time >= file_mtime:
                tprint(f"  💾 캐시에서 읽기: {os.path.basename(db_path)}")
                return cached_df.copy()
        except OSError:
            pass
    
    # 캐시 미스: 실제 읽기
    df = read_db_file(db_path, params_to_read, time_cols, convert_datetime_vectorized)
                
    if df is not None:
        # 캐시에 저장 (최대 크기 제한)
        if len(_cache) >= _cache_max_size:
            # 가장 오래된 항목 제거 (FIFO)
            oldest_key = next(iter(_cache))
            del _cache[oldest_key]
        
        file_mtime = os.path.getmtime(db_path) if os.path.exists(db_path) else 0
        _cache[cache_key] = (df.copy(), file_mtime)
    
    return df


def clear_cache():
    """캐시 초기화"""
    global _cache
    _cache.clear()
    print("캐시가 초기화되었습니다.")


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


# create_onselect_function_with_context는 Onselect_integral.py 모듈로 분리됨
# LDR 하위 모듈로 import하여 사용
from Onselect_integral import create_onselect_function_with_context
