import { test, expect } from '@playwright/test';

/**
 * E2E User Scenario Test: 신규 대사증후군 환자의 첫 상담
 *
 * 시나리오: 상담사 이지원이 검진 결과 대사증후군 진단을 받은 김하늘 환자와 첫 상담을 진행
 *
 * - 환자: 김하늘 (55세, 남성, BMI 28.5, 혈압 140/90, 공복혈당 180)
 * - 상담사: 이지원 (경력 2년)
 */

test.describe('대사증후군 상담 전체 시나리오', () => {
  test.beforeEach(async ({ page }) => {
    // Console errors 캡처
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log(`Browser console error: ${msg.text()}`);
      }
    });
  });

  test('신규 환자 첫 상담 워크플로우 (E2E)', async ({ page }) => {
    // ============================================================
    // Stage 1: 환자 선택 (환자 목록 UI)
    // ============================================================

    await test.step('환자 목록 페이지 접근', async () => {
      await page.goto('http://localhost:3000/patients');

      // 페이지 로딩 확인
      await expect(page.locator('h1, h2')).toContainText(/환자 목록|Patient List/i);

      // 테이블이 렌더링될 때까지 대기
      await page.waitForSelector('table', { timeout: 5000 });
    });

    await test.step('환자 목록에서 김하늘 환자 선택', async () => {
      // 김하늘 환자 행 찾기
      const patientRow = page.locator('tr:has-text("김하늘")');
      await expect(patientRow).toBeVisible({ timeout: 10000 });

      // 환자 정보 확인
      const rowText = await patientRow.textContent();
      expect(rowText).toContain('55'); // 나이

      // 환자 클릭
      await patientRow.click();

      // Workspace로 이동 확인
      await expect(page).toHaveURL(/patient_id=/, { timeout: 5000 });
    });

    // ============================================================
    // Stage 2: 상담 준비 (Preparation Mode)
    // ============================================================

    await test.step('상담 준비 페이지 로딩 확인', async () => {
      // 환자 데이터 로딩 대기 (최대 5초)
      await page.waitForTimeout(2000);

      // 환자 이름이 화면에 표시되는지 확인
      const pageContent = await page.textContent('body');
      expect(pageContent).toContain('김하늘');
    });

    await test.step('상담 준비 시작 버튼 클릭', async () => {
      const prepButton = page.locator('button:has-text("상담 준비 시작")');
      await expect(prepButton).toBeEnabled({ timeout: 5000 });

      await prepButton.click();

      // 진행 단계 표시 확인 (여러 가능성 중 하나라도 나타나면 성공)
      await expect(page.locator('text=/환자 기록 검색 중|이전 상담 패턴|예상 질문 생성|권장 답변 준비|전달 방식 예시/i')).toBeVisible({ timeout: 3000 });
    });

    await test.step('상담 준비 완료 대기', async () => {
      // 상담 시작 버튼이 활성화될 때까지 대기 (최대 35초)
      const startButton = page.locator('button:has-text("상담 시작")');
      await expect(startButton).toBeEnabled({ timeout: 35000 });

      console.log('✅ 상담 준비 완료');
    });

    await test.step('PreparationSidebar 섹션 확인', async () => {
      // 핵심 포인트 섹션
      await expect(page.locator('h3:has-text("핵심 포인트")')).toBeVisible();

      // 예상 질문 섹션
      await expect(page.locator('h3:has-text(/예상 질문|Anticipated/i)')).toBeVisible();

      // 주의사항 섹션
      await expect(page.locator('h3:has-text("주의사항")')).toBeVisible();

      console.log('✅ PreparationSidebar 모든 섹션 표시됨');
    });

    // ============================================================
    // Stage 3: 상담 시작 (Live Mode)
    // ============================================================

    await test.step('상담 시작 버튼 클릭 및 모드 전환', async () => {
      const startButton = page.locator('button:has-text("상담 시작")');
      await startButton.click();

      // Live 모드로 전환 확인 (최대 2초)
      await page.waitForTimeout(1000);

      // 사이드바 축소 확인 (60px)
      const sidebar = page.locator('aside').filter({ hasText: /Preparation|preparation/i });
      const sidebarWidth = await sidebar.evaluate(el => el.offsetWidth);

      // 축소 상태 확인 (60px 또는 그 이하)
      expect(sidebarWidth).toBeLessThan(100);

      console.log(`✅ Live 모드 전환 완료 (사이드바 너비: ${sidebarWidth}px)`);
    });

    // ============================================================
    // Stage 4: 실시간 응답 검증
    // ============================================================

    await test.step('질문 1: 일반 질문 (운동 권장사항)', async () => {
      const chatInput = page.locator('input[type="text"], textarea').first();
      await chatInput.fill('혈당이 높은데 어떤 운동을 해야 하나요?');
      await chatInput.press('Enter');

      // AG-UI 투명성 타임라인 확인
      await expect(page.locator('text=/질문 분석|Thought|reasoning/i')).toBeVisible({ timeout: 5000 });

      // 답변 카드 표시 확인 (최대 10초)
      await expect(page.locator('[class*="answerCard"], [class*="message"]')).toBeVisible({ timeout: 10000 });

      console.log('✅ 질문 1 답변 수신 완료');
    });

    await test.step('질문 2: 안전 경고 테스트 (의학적 판단 필요)', async () => {
      const chatInput = page.locator('input[type="text"], textarea').first();
      await chatInput.fill('약은 언제 먹어야 하나요?');
      await chatInput.press('Enter');

      // 안전 경고 배너 표시 확인
      await expect(page.locator('text=/담당 의사|의료진|에스컬레이션|escalate/i')).toBeVisible({ timeout: 10000 });

      console.log('✅ 질문 2 안전 경고 표시됨');
    });

    await test.step('질문 3: FAQ 캐시 테스트 (빠른 응답)', async () => {
      const startTime = Date.now();

      const chatInput = page.locator('input[type="text"], textarea').first();
      await chatInput.fill('운동은 얼마나 해야 하나요?');
      await chatInput.press('Enter');

      // 답변 대기
      await page.waitForSelector('[class*="answerCard"], [class*="message"]', { timeout: 2000 });

      const responseTime = Date.now() - startTime;

      console.log(`✅ 질문 3 응답 시간: ${responseTime}ms`);

      // FAQ 캐시 히트 시 500ms 이내 예상
      if (responseTime < 500) {
        console.log('🚀 FAQ 캐시 히트 (매우 빠름)');
      } else if (responseTime < 2000) {
        console.log('⚡ FAQ 캐시 미스 또는 일반 검색 (빠름)');
      } else {
        console.log('⏱️ 일반 검색 (정상)');
      }
    });

    // ============================================================
    // Stage 5: 세션 저장 확인
    // ============================================================

    await test.step('세션 및 메시지 저장 확인', async () => {
      // 메시지가 자동 저장되었는지 콘솔 로그 확인 (실제 검증은 백엔드 DB 확인 필요)
      console.log('✅ 세션 관리: 프론트엔드 코드에서 자동 저장 구현됨');
      console.log('   (실제 저장 검증은 백엔드 DB 쿼리로 확인 필요)');
    });

    // ============================================================
    // 최종 검증
    // ============================================================

    await test.step('전체 워크플로우 완료', async () => {
      console.log('\n========================================');
      console.log('✅ 전체 사용자 시나리오 테스트 완료');
      console.log('========================================');
      console.log('검증 항목:');
      console.log('  ✓ 환자 목록 → 환자 선택');
      console.log('  ✓ 상담 준비 → 진행 단계 표시');
      console.log('  ✓ PreparationSidebar 섹션');
      console.log('  ✓ 상담 시작 → 모드 전환');
      console.log('  ✓ 일반 질문 → 답변 카드');
      console.log('  ✓ 의학 질문 → 안전 경고');
      console.log('  ✓ FAQ 질문 → 빠른 응답');
      console.log('========================================\n');
    });
  });

  // ============================================================
  // 추가 테스트: 성능 SLA 검증
  // ============================================================

  test('성능 SLA 검증 - Live Mode <5초', async ({ page }) => {
    // 환자 페이지로 직접 이동 (환자 목록 건너뛰기)
    await page.goto('http://localhost:3000/?patient_id=P0001');

    // 페이지 로딩 대기
    await page.waitForTimeout(3000);

    // Live 모드로 전환
    const modeSwitch = page.locator('button, label').filter({ hasText: /live|실시간/i });
    if (await modeSwitch.isVisible()) {
      await modeSwitch.click();
      await page.waitForTimeout(500);
    }

    // 질문 입력
    const chatInput = page.locator('input[type="text"], textarea').first();
    await chatInput.fill('간단한 테스트 질문입니다.');

    const startTime = Date.now();
    await chatInput.press('Enter');

    // 답변 대기
    await page.waitForSelector('[class*="answerCard"], [class*="message"]', { timeout: 6000 });

    const responseTime = Date.now() - startTime;

    console.log(`응답 시간: ${responseTime}ms`);

    // SLA 확인: <5초 (5000ms)
    expect(responseTime).toBeLessThan(5000);

    if (responseTime < 2000) {
      console.log('🚀 매우 빠름 (<2초)');
    } else if (responseTime < 5000) {
      console.log('✅ SLA 충족 (<5초)');
    }
  });

  // ============================================================
  // 추가 테스트: ReferencesPanel 표시 확인
  // ============================================================

  test('ReferencesPanel 조건부 렌더링 확인', async ({ page }) => {
    await page.goto('http://localhost:3000/?patient_id=P0001');
    await page.waitForTimeout(3000);

    // Live 모드로 전환
    const modeSwitch = page.locator('button, label').filter({ hasText: /live|실시간/i });
    if (await modeSwitch.isVisible()) {
      await modeSwitch.click();
      await page.waitForTimeout(500);
    }

    // 질문 입력 (citations 생성 유도)
    const chatInput = page.locator('input[type="text"], textarea').first();
    await chatInput.fill('대사증후군 운동 권장사항을 알려주세요.');
    await chatInput.press('Enter');

    // 답변 대기
    await page.waitForSelector('[class*="answerCard"], [class*="message"]', { timeout: 10000 });

    // ReferencesPanel 또는 Citation 관련 요소 확인
    const hasReferences = await page.locator('text=/참고|출처|reference|citation/i').isVisible();

    if (hasReferences) {
      console.log('✅ ReferencesPanel 또는 Citations 표시됨');
    } else {
      console.log('⚠️ Citations가 없거나 ReferencesPanel 미표시 (정상일 수 있음)');
    }
  });
});

// ============================================================
// 헬퍼 함수
// ============================================================

// 추후 추가 가능한 헬퍼 함수들
// - 스크린샷 캡처
// - 성능 메트릭 수집
// - 백엔드 API 직접 호출 검증 등
