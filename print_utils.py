"""
터미널 출력 타임스탬프 유틸리티
프로젝트 전역에서 사용하는 타임스탬프가 포함된 print 함수
"""

import datetime
import sys


def tprint(*args, **kwargs):
    """
    타임스탬프가 포함된 print 함수
    
    Usage:
        tprint("일반 메시지")
        tprint("포맷팅:", value)
        tprint("파일 처리 완료", file=sys.stderr)  # 파일 지정 가능
    """
    # 현재 시간 포맷팅
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    
    # 메시지 조합
    message_parts = [timestamp] + [str(arg) for arg in args]
    message = " ".join(message_parts)
    
    # 원본 print와 동일하게 동작 (sep, end, file 등 모든 옵션 지원)
    if 'sep' not in kwargs:
        kwargs['sep'] = ' '
    if 'end' not in kwargs:
        kwargs['end'] = '\n'
    
    print(message, **kwargs)


# 기존 print를 tprint로 교체하고 싶다면 주석 해제
# print = tprint

