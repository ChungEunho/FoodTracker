"""
_paths.py — 번들(.app) 및 스크립트 실행 모두에서 올바른 경로를 반환합니다.
"""
import sys
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def env_path() -> Path:
    """
    .env 파일 위치.
    - 스크립트 실행: 프로젝트 루트의 .env
    - .app 실행: .app 옆에 있는 .env (없으면 ~/Library/… 로 폴백)
    """
    if _is_frozen():
        # sys.executable = .app/Contents/MacOS/<name>  →  4단계 위가 .app 상위 폴더
        beside_app = Path(sys.executable).parents[3] / ".env"
        if beside_app.exists():
            return beside_app
        return data_dir() / ".env"
    return Path(__file__).parent / ".env"


def data_dir() -> Path:
    """
    DB / 사용자 데이터 저장 위치.
    - 스크립트 실행: 프로젝트 루트
    - .app 실행: ~/Library/Application Support/FoodTracker/
    """
    if _is_frozen():
        d = Path.home() / "Library" / "Application Support" / "FoodTracker"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return Path(__file__).parent
