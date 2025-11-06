#!/bin/bash

# 대사증후군 상담사 어시스턴트 - 통합 실행 스크립트
# Backend와 Frontend를 동시에 실행합니다.

set -e  # 에러 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 프로세스 종료 함수
cleanup() {
    echo -e "\n${YELLOW}종료 중...${NC}"
    if [ ! -z "$BACKEND_PID" ]; then
        echo -e "${BLUE}백엔드 프로세스 종료 (PID: $BACKEND_PID)${NC}"
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        echo -e "${BLUE}프론트엔드 프로세스 종료 (PID: $FRONTEND_PID)${NC}"
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    exit 0
}

# SIGINT (Ctrl+C) 및 SIGTERM 핸들러 등록
trap cleanup SIGINT SIGTERM

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}대사증후군 상담사 어시스턴트 시작${NC}"
echo -e "${GREEN}========================================${NC}\n"

# 백엔드 디렉토리 확인
if [ ! -d "backend" ]; then
    echo -e "${RED}오류: backend 디렉토리를 찾을 수 없습니다.${NC}"
    exit 1
fi

# 프론트엔드 디렉토리 확인
if [ ! -d "frontend" ]; then
    echo -e "${RED}오류: frontend 디렉토리를 찾을 수 없습니다.${NC}"
    exit 1
fi

# 포트 확인
check_port() {
    local port=$1
    local name=$2
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${YELLOW}경고: 포트 $port ($name)가 이미 사용 중입니다.${NC}"
        echo -e "${YELLOW}기존 프로세스를 종료하거나 다른 포트를 사용하세요.${NC}"
        read -p "계속하시겠습니까? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

check_port 8000 "백엔드"
check_port 3000 "프론트엔드"

# 백엔드 시작
echo -e "${BLUE}[1/2] 백엔드 서버 시작 중...${NC}"
cd backend

# uv가 설치되어 있는지 확인
if ! command -v uv &> /dev/null; then
    echo -e "${RED}오류: uv가 설치되어 있지 않습니다.${NC}"
    echo -e "${YELLOW}설치 방법: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
    exit 1
fi

# 의존성 확인
if [ ! -d ".venv" ] && [ ! -f "uv.lock" ]; then
    echo -e "${YELLOW}백엔드 의존성 설치 중...${NC}"
    uv sync
fi

# 백엔드 실행 (백그라운드)
echo -e "${GREEN}백엔드 서버 시작: http://localhost:8000${NC}"
uv run uvicorn metabolic_backend.api.server:app --host 0.0.0.0 --port 8000 --reload > ../backend.log 2>&1 &
BACKEND_PID=$!

cd ..

# 백엔드 준비 대기
echo -e "${BLUE}백엔드 서버 준비 대기 중...${NC}"
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}백엔드 서버 준비 완료!${NC}"
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
    echo -n "."
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "\n${RED}오류: 백엔드 서버가 시작되지 않았습니다.${NC}"
    echo -e "${YELLOW}로그 확인: tail -f backend.log${NC}"
    cleanup
    exit 1
fi

echo

# 프론트엔드 시작
echo -e "${BLUE}[2/2] 프론트엔드 서버 시작 중...${NC}"
cd frontend

# npm이 설치되어 있는지 확인
if ! command -v npm &> /dev/null; then
    echo -e "${RED}오류: npm이 설치되어 있지 않습니다.${NC}"
    exit 1
fi

# node_modules 확인
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}프론트엔드 의존성 설치 중...${NC}"
    npm install
fi

# 프론트엔드 실행 (백그라운드)
echo -e "${GREEN}프론트엔드 서버 시작: http://localhost:3000${NC}"
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!

cd ..

# 프론트엔드 준비 대기
echo -e "${BLUE}프론트엔드 서버 준비 대기 중...${NC}"
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}프론트엔드 서버 준비 완료!${NC}"
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
    echo -n "."
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "\n${YELLOW}경고: 프론트엔드 서버가 아직 시작되지 않았습니다.${NC}"
    echo -e "${YELLOW}로그 확인: tail -f frontend.log${NC}"
fi

echo

# 최종 메시지
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 모든 서버가 실행되었습니다!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${BLUE}백엔드:${NC}   http://localhost:8000"
echo -e "${BLUE}프론트엔드:${NC} http://localhost:3000"
echo -e "${BLUE}API 문서:${NC}  http://localhost:8000/docs"
echo -e "${YELLOW}로그 확인:${NC}"
echo -e "  백엔드:   tail -f backend.log"
echo -e "  프론트엔드: tail -f frontend.log"
echo -e "\n${YELLOW}종료하려면 Ctrl+C를 누르세요.${NC}\n"

# 로그 파일을 실시간으로 표시 (선택사항)
if [ "$1" == "--logs" ]; then
    tail -f backend.log frontend.log &
    TAIL_PID=$!
    trap "kill $TAIL_PID 2>/dev/null || true; cleanup" SIGINT SIGTERM
fi

# 프로세스 종료 대기
wait

