"""
SQLite DB 파일을 Squall로 열기 위한 헬퍼 모듈
Squall: https://github.com/driscollis/squall
"""

import os
import subprocess
import sys
from pathlib import Path

def check_squall_installed():
    """Squall이 설치되어 있는지 확인"""
    try:
        # 방법 1: pip show로 확인
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "squall-sql"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True
        
        # 방법 2: 모듈 import 시도
        try:
            import squall
            return True
        except ImportError:
            pass
        
        # 방법 3: squall 명령어 확인 (Windows에서는 where, Unix에서는 which)
        import platform
        if platform.system() == "Windows":
            check_cmd = ["where", "squall"]
        else:
            check_cmd = ["which", "squall"]
        
        try:
            result = subprocess.run(
                check_cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
            
    except Exception:
        return False


def install_squall():
    """Squall 설치 시도"""
    try:
        print("Squall 설치 중...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "squall-sql"],
            check=True,
            timeout=120
        )
        print("✓ Squall 설치 완료")
        return True
    except subprocess.TimeoutExpired:
        print("✗ 설치 시간 초과")
        return False
    except subprocess.CalledProcessError as e:
        print(f"✗ 설치 실패: {e}")
        return False
    except Exception as e:
        print(f"✗ 설치 중 오류: {e}")
        return False


def open_db_with_squall(db_path):
    """
    Squall을 사용하여 DB 파일 열기
    
    Args:
        db_path: 열 DB 파일 경로 (문자열 또는 Path 객체)
        
    Returns:
        bool: 성공 여부
    """
    import platform
    
    # 경로 확인
    db_path = Path(db_path).resolve()  # 절대 경로로 변환
    if not db_path.exists():
        print(f"✗ 파일이 존재하지 않습니다: {db_path}")
        return False
    
    if not db_path.is_file():
        print(f"✗ 파일이 아닙니다: {db_path}")
        return False
    
    # 확장자 확인 (.db 또는 확장자 없음)
    if db_path.suffix and db_path.suffix.lower() not in ['.db', '.sqlite', '.sqlite3']:
        print(f"⚠ 경고: DB 파일 확장자가 아닙니다: {db_path.suffix}")
    
    # Squall 설치 확인
    if not check_squall_installed():
        print("Squall이 설치되어 있지 않습니다.")
        print("설치 방법:")
        print("  pip install squall-sql")
        print("\n자동으로 설치하시겠습니까?")
        
        # GUI에서 확인 (가능한 경우)
        try:
            import tkinter.messagebox as mb
            if mb.askyesno("Squall 설치", "Squall을 설치하시겠습니까?"):
                if not install_squall():
                    return False
            else:
                return False
        except:
            # GUI 없이 콘솔에서만 작동
            response = input("설치하시겠습니까? (y/n): ")
            if response.lower() == 'y':
                if not install_squall():
                    return False
            else:
                return False
    
    # Squall 실행
    try:
        print(f"🔍 Squall로 DB 파일 열기: {db_path.name}")
        db_path_str = str(db_path)
        
        # Windows에서 shell=True 사용 (PATH 환경변수 인식)
        is_windows = platform.system() == "Windows"
        shell = is_windows
        
        # 방법 1: python -m squall.squall로 실행 시도 (가장 안정적)
        try:
            # squall.squall 모듈이 실행 가능한지 확인
            import importlib.util
            spec = importlib.util.find_spec("squall.squall")
            if spec is None or spec.origin is None:
                raise ModuleNotFoundError("squall.squall module not found")
            
            cmd = [sys.executable, "-m", "squall.squall", "-f", db_path_str]
            print(f"  실행 중: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                check=True,
                timeout=3600  # 1시간 타임아웃
            )
            return True
        except subprocess.TimeoutExpired:
            print("  타임아웃 발생 (사용자가 Squall을 종료했을 수 있습니다)")
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, ModuleNotFoundError) as e:
            print(f"  방법 1 실패: {e}")
            # 다음 방법 시도
        
        # 방법 2: squall 명령어 직접 실행 시도
        try:
            cmd = ["squall", "-f", db_path_str]
            print(f"  실행 중: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                check=True,
                shell=shell,
                timeout=3600
            )
            return True
        except subprocess.TimeoutExpired:
            print("  타임아웃 발생")
            return True
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"  방법 2 실패: {e}")
            # 다음 방법 시도
        
        # 방법 3: runpy를 사용하여 모듈 실행
        try:
            import runpy
            original_argv = sys.argv
            sys.argv = ["squall", "-f", db_path_str]
            try:
                runpy.run_module("squall.squall", run_name="__main__")
                return True
            finally:
                sys.argv = original_argv
        except Exception as e:
            print(f"  방법 3 실패: {e}")
            # 다음 방법 시도
        
        # 방법 4: 직접 import해서 실행 시도
        try:
            # squall 패키지의 squall.py 모듈 직접 import
            try:
                from squall import squall as squall_module  # type: ignore
            except ImportError:
                # 대체 방법: 직접 파일 경로로 import
                import squall  # type: ignore
                import importlib.util
                if squall.__file__:
                    squall_path = str(squall.__file__).replace('__init__.py', 'squall.py')
                    spec = importlib.util.spec_from_file_location("squall_module", squall_path)
                    if spec and spec.loader:
                        squall_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(squall_module)
                    else:
                        raise ImportError("Cannot load squall module")
                else:
                    raise ImportError("Cannot find squall package")
            
            # squall.py의 main 함수 호출
            if hasattr(squall_module, 'main'):
                original_argv = sys.argv.copy()
                sys.argv = ["squall", "-f", db_path_str]
                try:
                    squall_module.main()
                    return True
                finally:
                    sys.argv = original_argv
        except Exception as e:
            print(f"  방법 4 실패: {e}")
            import traceback
            traceback.print_exc()
        
        # 모든 방법 실패
        print("✗ Squall 실행 실패 - 모든 방법 실패")
        print("\n수동 실행 방법:")
        print(f"  python -m squall.squall -f \"{db_path_str}\"")
        print(f"  또는")
        print(f"  squall -f \"{db_path_str}\"")
        return False
    
    except KeyboardInterrupt:
        print("\n✓ Squall 종료됨 (사용자 중단)")
        return True
    except Exception as e:
        print(f"✗ Squall 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def open_db_list_with_squall(db_files, selected_index=None):
    """
    여러 DB 파일 중 하나를 선택하여 Squall로 열기
    
    Args:
        db_files: DB 파일 경로 리스트
        selected_index: 선택된 파일 인덱스 (None이면 첫 번째 파일)
        
    Returns:
        bool: 성공 여부
    """
    if not db_files:
        print("✗ 열 DB 파일이 없습니다")
        return False
    
    if selected_index is None:
        selected_index = 0
    elif selected_index >= len(db_files):
        selected_index = 0
    
    db_path = db_files[selected_index]
    return open_db_with_squall(db_path)


def open_db_with_squall_interactive():
    """
    경로 입력 창을 통해 DB 파일 경로를 입력받아 Squall로 열기
    
    Returns:
        bool: 성공 여부
    """
    try:
        import tkinter as tk
        from tkinter import simpledialog, filedialog, messagebox
        
        root = tk.Tk()
        root.withdraw()  # 메인 창 숨기기
        
        # 사용자에게 선택권 제공
        choice = messagebox.askyesnocancel(
            "DB 파일 열기",
            "Squall로 DB 파일을 열겠습니다.\n\n"
            "예: 파일 선택 대화상자\n"
            "아니오: 경로 직접 입력\n"
            "취소: 취소"
        )
        
        if choice is None:  # 취소
            root.destroy()
            return False
        
        if choice:  # 파일 선택 대화상자
            db_path = filedialog.askopenfilename(
                title="열 DB 파일 선택",
                filetypes=[
                    ("SQLite Database", "*.db"),
                    ("All Files", "*.*")
                ],
                initialdir=os.getcwd()
            )
        else:  # 경로 직접 입력
            db_path = simpledialog.askstring(
                "DB 파일 경로 입력",
                "DB 파일 경로를 입력하세요:\n\n"
                "예: squall -f C:\\Users\\user\\Desktop\\2024-11-27.db\n"
                "또는: C:\\Users\\user\\Desktop\\2024-11-27.db\n"
                "또는: 2024-11-27.db (현재 폴더 기준)",
                initialvalue=""
            )
        
        root.destroy()
        
        if not db_path:
            print("경로가 입력되지 않았습니다.")
            return False
        
        # 따옴표 제거 (복사 붙여넣기 시 포함될 수 있음)
        db_path = db_path.strip('"').strip("'").strip()
        
        # "squall -f " 형태로 입력된 경우 경로 추출
        if db_path.startswith("squall") and "-f" in db_path:
            parts = db_path.split("-f", 1)
            if len(parts) > 1:
                db_path = parts[1].strip()
                # 따옴표 다시 제거 (경로 부분에만)
                db_path = db_path.strip('"').strip("'")
        
        # 상대 경로인 경우 현재 작업 디렉토리 기준으로 변환
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
        
        return open_db_with_squall(db_path)
        
    except ImportError:
        # tkinter가 없는 경우 콘솔에서만 입력받기
        db_path = input("DB 파일 경로를 입력하세요 (squall -f path/to/file.db 형태 가능): ").strip()
        
        if not db_path:
            print("경로가 입력되지 않았습니다.")
            return False
        
        # 따옴표 제거
        db_path = db_path.strip('"').strip("'")
        
        # "squall -f " 형태로 입력된 경우 경로 추출
        if db_path.startswith("squall") and "-f" in db_path:
            parts = db_path.split("-f", 1)
            if len(parts) > 1:
                db_path = parts[1].strip()
                # 따옴표 다시 제거
                db_path = db_path.strip('"').strip("'")
        
        # 상대 경로 처리
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
        
        return open_db_with_squall(db_path)
    except Exception as e:
        print(f"파일 선택 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


# 직접 실행 시 테스트
if __name__ == "__main__":
    import sys
    
    print("=" * 50)
    print("Squall DB Viewer Helper")
    print("=" * 50)
    print("\n사용 가능한 기능:")
    print("  - open_db_with_squall_interactive()  # 대화상자를 통해 DB 파일 선택")
    print("  - open_db_with_squall(db_path)       # 직접 경로 지정")
    print("\n사용 예시:")
    print("  from db_viewer_helper import open_db_with_squall_interactive")
    print("  open_db_with_squall_interactive()")
    print("\nSquall 설치 상태 확인 중...")
    
    try:
        is_installed = check_squall_installed()
        
        if is_installed:
            print("✓ Squall이 설치되어 있습니다.")
            
            # 명령줄 인자로 경로가 제공된 경우
            if len(sys.argv) > 1:
                db_path = " ".join(sys.argv[1:])
                # "squall -f" 형태 제거
                if "squall" in db_path and "-f" in db_path:
                    parts = db_path.split("-f", 1)
                    if len(parts) > 1:
                        db_path = parts[1].strip().strip('"').strip("'")
                
                print(f"\n제공된 경로: {db_path}")
                success = open_db_with_squall(db_path)
                sys.exit(0 if success else 1)
            else:
                print("\n대화상자를 통해 DB 파일을 선택합니다...")
                success = open_db_with_squall_interactive()
                sys.exit(0 if success else 1)
        else:
            print("✗ Squall이 설치되어 있지 않습니다.")
            print("\n설치 방법:")
            print("  pip install squall-sql")
            
            # 대화형 환경에서만 설치 물어보기
            try:
                if sys.stdin.isatty():
                    print("\n자동으로 설치하시겠습니까? (y/n): ", end="", flush=True)
                    response = input().strip().lower()
                    if response == 'y':
                        if install_squall():
                            print("\n설치 완료! DB 파일을 선택합니다...")
                            success = open_db_with_squall_interactive()
                            sys.exit(0 if success else 1)
                        else:
                            print("\n설치에 실패했습니다.")
                            sys.exit(1)
                    else:
                        print("\n설치를 건너뜁니다.")
                        sys.exit(0)
                else:
                    # 비대화형 환경 (디버그 콘솔 등)
                    print("\n※ 디버그 콘솔에서는 다음 명령으로 직접 함수를 호출하세요:")
                    print("  from db_viewer_helper import open_db_with_squall_interactive")
                    print("  open_db_with_squall_interactive()")
                    print("\n또는 수동으로 Squall 설치:")
                    print("  pip install squall-sql")
                    sys.exit(0)
            except (KeyboardInterrupt, EOFError):
                print("\n\n프로그램을 종료합니다.")
                sys.exit(0)
                
    except KeyboardInterrupt:
        print("\n\n프로그램을 종료합니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

