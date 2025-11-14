# LEUS Log Data Reader

LEUS 장비에서 생성되는 DB 파일을 모아서 분석·시각화하고, 작업 로그를 관리하기 위한 Python 기반 툴입니다.  
`20251104_Log_Data_Reader_F.py` Tkinter GUI와 PyQt5 하위 모듈을 조합해 데이터를 불러오고, 파라미터를 선택해 그래프를 확인하며, 선택 구간 적분 및 로그 관리까지 한 번에 처리할 수 있습니다.

## 주요 기능

- **DB 데이터 로딩/머지**  
  - SQLite DB 파일을 Polars 기반 파이프라인으로 고속 처리  
  - PLC Error 복원, CNT 관련 데이터 필터링, 캐시 재사용 지원  
  - 폴더 전체 또는 개별 파일을 선택해 일괄 로딩

- **데이터 시각화**  
  - Matplotlib를 사용한 파라미터 플롯  
  - 더블클릭 색상 변경, 축 스케일 팝업(Linear/Log), 폰트 확대  
  - `SpanSelector`를 통한 구간 드래그 → 적분/샷수/세그먼트 분석

- **작업 로그 관리 (PyQt5)**  
  - `work_log_manager.py`: 작업 입력, 수정, 삭제, 내보내기  
  - `work_log_calendar_view.py`: 일별/월별 달력에서 로그 현황 확인  
  - JSON 기반 저장, CSV/XLSX/JSON 내보내기

- **유틸리티 모듈**  
  - `Onselect_integral.py`: 선택 구간 적분 및 통계 계산  
  - `db_file.py`: Polars 기반 DB 읽기/복원/캐싱 파이프라인

## 디렉터리 구조(요약)

```
LogDataReader/
├─ 20251104_Log_Data_Reader_F.py   # 메인 GUI (Tkinter)
├─ work_log_manager.py             # PyQt5 작업 로그 관리자
├─ work_log_calendar_view.py       # PyQt5 달력 뷰
├─ db_file.py                      # DB 처리 파이프라인
├─ Onselect_integral.py            # 적분/세그먼트 분석 유틸
├─ cnt_data_plotter.py, ...        # 기타 서브 모듈
└─ README.md / requirements.txt
```

## 실행 환경

- Python 3.10 이상 권장  
- Windows 10/11 (pyproj는 Win 전용 UI 활용)  
- Tkinter와 PyQt5를 동시에 사용하므로 GUI 지원 환경 필요

## 설치 방법

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows PowerShell 기준
pip install --upgrade pip
pip install -r requirements.txt
```

## 실행 방법

```bash
python 20251104_Log_Data_Reader_F.py
```

1. **DB 경로 선택**: 폴더 또는 개별 파일 선택  
2. **파라미터 선택**: 리스트에서 플롯할 항목 선택 → 그래프 확인  
3. **구간 분석**: 그래프에서 드래그하여 적분/통계 결과 확인  
4. **작업 로그 관리**: `로그 입력` 버튼 → PyQt5 대화상자에서 관리  
5. **달력 보기**: 작업 로그 창에서 `달력으로 보기`

## 데이터/로그 파일

- 작업 로그는 기본적으로 `work_log.json`에 저장됩니다.  
- 필요 시 `로그 내보내기` 기능으로 CSV/XLSX/JSON 추출 가능합니다.

## 개발 참고

- Polars 사용 시 PyArrow가 필요할 수 있습니다.  
- Excel 내보내기를 위해 `openpyxl` 설치가 권장됩니다.  
- `connectorx`는 선택적으로 사용되며(Polars DB 연결), 설치되어 있으면 성능 향상에 도움이 됩니다.

## 라이선스

본 저장소는 별도 라이선스를 명시하지 않았습니다. 사내 프로젝트 가이드라인에 따라 사용해 주세요.
