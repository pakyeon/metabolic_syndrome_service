# 대사증후군 상담사 어시스턴트 - 통합 실행 스크립트 사용 가이드

## 빠른 시작

### 방법 1: 스크립트 사용 (권장)

#### Linux/Mac/WSL
```bash
./start.sh
```

로그를 함께 보려면:
```bash
./start.sh --logs
```

#### Windows
```cmd
start.bat
```

#### npm 사용 (모든 플랫폼)
```bash
# 루트 디렉토리에서
npm install  # concurrently 설치
npm run dev
```

### 방법 2: 개별 실행

#### 백엔드만 실행
```bash
cd backend
uv run uvicorn metabolic_backend.api.server:app --host 0.0.0.0 --port 8000 --reload
```

#### 프론트엔드만 실행
```bash
cd frontend
npm run dev
```

---

## 스크립트 기능

### `start.sh` (Linux/Mac/WSL)

주요 기능:
- ✅ 백엔드와 프론트엔드를 순차적으로 시작
- ✅ 각 서버의 준비 상태 확인
- ✅ 포트 충돌 감지 및 경고
- ✅ Ctrl+C로 깔끔하게 종료
- ✅ 로그 파일 자동 생성 (`backend.log`, `frontend.log`)
- ✅ `--logs` 플래그로 실시간 로그 표시

사용 예시:
```bash
# 기본 실행
./start.sh

# 로그 함께 보기
./start.sh --logs
```

### `start.bat` (Windows)

주요 기능:
- ✅ 백엔드와 프론트엔드를 별도 창에서 실행
- ✅ 각 서버가 독립적인 창에서 실행되어 로그 확인 용이

### `npm run dev` (모든 플랫폼)

주요 기능:
- ✅ `concurrently`를 사용하여 백엔드/프론트엔드 동시 실행
- ✅ 색상 구분된 출력 (백엔드: 파란색, 프론트엔드: 녹색)
- ✅ Ctrl+C로 모든 프로세스 동시 종료

---

## 로그 확인

### 실시간 로그 보기
```bash
# 백엔드 로그
tail -f backend.log

# 프론트엔드 로그
tail -f frontend.log

# 둘 다 보기
tail -f backend.log frontend.log
```

### 로그 파일 위치
- 백엔드: `backend.log` (프로젝트 루트)
- 프론트엔드: `frontend.log` (프로젝트 루트)

---

## 문제 해결

### 포트가 이미 사용 중인 경우

#### Linux/Mac/WSL
```bash
# 포트 사용 중인 프로세스 확인
lsof -i :8000  # 백엔드
lsof -i :3000  # 프론트엔드

# 프로세스 종료
kill -9 <PID>
```

#### Windows
```cmd
# 포트 사용 중인 프로세스 확인
netstat -ano | findstr :8000
netstat -ano | findstr :3000

# 프로세스 종료
taskkill /PID <PID> /F
```

### 백엔드가 시작되지 않는 경우

1. **uv가 설치되어 있는지 확인**
   ```bash
   uv --version
   ```

2. **의존성 설치 확인**
   ```bash
   cd backend
   uv sync
   ```

3. **환경 변수 확인**
   - `.env` 파일이 있는지 확인
   - 필요한 API 키가 설정되어 있는지 확인

### 프론트엔드가 시작되지 않는 경우

1. **npm이 설치되어 있는지 확인**
   ```bash
   npm --version
   ```

2. **의존성 설치 확인**
   ```bash
   cd frontend
   npm install
   ```

3. **포트 충돌 확인**
   - 다른 Next.js 앱이 실행 중인지 확인

---

## 실행 순서

스크립트는 다음 순서로 실행됩니다:

1. **환경 확인**
   - 백엔드/프론트엔드 디렉토리 존재 확인
   - 포트 8000, 3000 사용 가능 여부 확인

2. **백엔드 시작**
   - 의존성 확인 및 설치 (필요시)
   - 백엔드 서버 시작
   - `/healthz` 엔드포인트 확인까지 대기

3. **프론트엔드 시작**
   - 의존성 확인 및 설치 (필요시)
   - 프론트엔드 서버 시작
   - 서버 준비 상태 확인

4. **실행 완료**
   - 모든 서버 URL 표시
   - 로그 파일 위치 안내

---

## 추가 명령어

### 모든 의존성 설치
```bash
npm run install:all
```

### 백엔드만 설치
```bash
npm run install:backend
```

### 프론트엔드만 설치
```bash
npm run install:frontend
```

### 테스트 실행
```bash
npm run test:backend    # 백엔드 테스트
npm run test:frontend  # 프론트엔드 E2E 테스트
```

---

**참고**: 스크립트 실행 시 생성되는 로그 파일은 `.gitignore`에 추가하는 것을 권장합니다.

