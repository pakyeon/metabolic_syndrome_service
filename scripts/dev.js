#!/usr/bin/env node

/**
 * 통합 개발 서버 실행 스크립트
 * 백엔드와 프론트엔드를 동시에 실행합니다.
 */

const { spawn } = require('child_process');
const path = require('path');

const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

function log(color, message) {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

// 프로세스 종료 함수
let processes = [];

function cleanup() {
  log('yellow', '\n종료 중...');
  processes.forEach(proc => {
    try {
      proc.kill('SIGTERM');
    } catch (e) {
      // 프로세스가 이미 종료된 경우 무시
    }
  });
  process.exit(0);
}

process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);

// 백엔드 시작
log('blue', '[1/2] 백엔드 서버 시작 중...');
const backendPath = path.join(__dirname, '..', 'backend');
const backendProcess = spawn('uv', 
  ['run', 'uvicorn', 'metabolic_backend.api.server:app', '--host', '0.0.0.0', '--port', '8000', '--reload'],
  {
    cwd: backendPath,
    stdio: 'inherit',
    shell: true
  }
);

backendProcess.on('error', (err) => {
  log('red', `백엔드 실행 오류: ${err.message}`);
  log('yellow', 'uv가 설치되어 있는지 확인하세요: curl -LsSf https://astral.sh/uv/install.sh | sh');
  process.exit(1);
});

processes.push(backendProcess);

// 프론트엔드 시작
setTimeout(() => {
  log('blue', '[2/2] 프론트엔드 서버 시작 중...');
  const frontendPath = path.join(__dirname, '..', 'frontend');
  const frontendProcess = spawn('npm', ['run', 'dev'], {
    cwd: frontendPath,
    stdio: 'inherit',
    shell: true
  });

  frontendProcess.on('error', (err) => {
    log('red', `프론트엔드 실행 오류: ${err.message}`);
    log('yellow', 'npm이 설치되어 있는지 확인하세요.');
    cleanup();
  });

  processes.push(frontendProcess);

  log('green', '\n✅ 모든 서버가 실행되었습니다!');
  log('cyan', '백엔드:   http://localhost:8000');
  log('cyan', '프론트엔드: http://localhost:3000');
  log('cyan', 'API 문서:  http://localhost:8000/docs');
  log('yellow', '\n종료하려면 Ctrl+C를 누르세요.\n');
}, 2000);

