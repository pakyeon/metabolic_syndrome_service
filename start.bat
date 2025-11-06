# 대사증후군 상담사 어시스턴트 - 통합 실행 스크립트 (Windows)

@echo off
setlocal enabledelayedexpansion

echo ========================================
echo 대사증후군 상담사 어시스턴트 시작
echo ========================================
echo.

REM 백엔드 디렉토리 확인
if not exist "backend" (
    echo 오류: backend 디렉토리를 찾을 수 없습니다.
    exit /b 1
)

REM 프론트엔드 디렉토리 확인
if not exist "frontend" (
    echo 오류: frontend 디렉토리를 찾을 수 없습니다.
    exit /b 1
)

REM 백엔드 시작
echo [1/2] 백엔드 서버 시작 중...
cd backend
start "백엔드 서버" cmd /k "uv run uvicorn metabolic_backend.api.server:app --host 0.0.0.0 --port 8000 --reload"
cd ..

REM 백엔드 준비 대기
echo 백엔드 서버 준비 대기 중...
timeout /t 5 /nobreak >nul

REM 프론트엔드 시작
echo [2/2] 프론트엔드 서버 시작 중...
cd frontend
start "프론트엔드 서버" cmd /k "npm run dev"
cd ..

echo.
echo ========================================
echo ✅ 서버가 시작되었습니다!
echo ========================================
echo 백엔드:   http://localhost:8000
echo 프론트엔드: http://localhost:3000
echo API 문서:  http://localhost:8000/docs
echo.
echo 종료하려면 각 창을 닫으세요.
echo.

pause

