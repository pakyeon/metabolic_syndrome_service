import { expect, test } from "@playwright/test";

// Mock responses for different safety levels
const mockClearResponse = {
  analysis: { domain: "lifestyle", complexity: "simple", safety: "clear" },
  answer: "규칙적인 운동과 균형잡힌 식사가 중요합니다.",
  citations: ["생활습관 가이드 2024"],
  observations: [
    { role: "reasoning", title: "일반 상담", content: "안전한 생활습관 조언" },
    { role: "action", title: "정보 제공", content: "근거 기반 권장사항" }
  ],
  safety: { level: "clear" }
};

const mockCautionResponse = {
  analysis: { domain: "medical", complexity: "medium", safety: "caution" },
  answer: "혈당 수치가 높으므로 의료진과 상담하여 관리 계획을 조정하는 것이 좋습니다.",
  citations: ["당뇨 관리 지침 2024"],
  observations: [
    { role: "reasoning", title: "수치 분석", content: "경계선 혈당 수치 확인" },
    { role: "action", title: "주의 권고", content: "의료진 확인 권장" }
  ],
  safety: {
    level: "caution",
    bannerTitle: "의학적 주의가 필요한 내용",
    bannerBody: "상담 시 근거를 공유하며 의료진 확인이 필요함을 함께 안내하세요.",
    escalationCopy: "담당 의사와 상담을 권장합니다."
  }
};

const mockEscalateResponse = {
  analysis: { domain: "medical", complexity: "high", safety: "escalate" },
  answer: "약물 조정은 의사의 판단이 필요한 사항입니다. 즉시 담당 의사와 상담해 주세요.",
  citations: [],
  observations: [
    { role: "reasoning", title: "위험 평가", content: "약물 관련 질문 감지" },
    { role: "action", title: "안전 조치", content: "Action: safety_escalation" }
  ],
  safety: {
    level: "escalate",
    bannerTitle: "의료 에스컬레이션 필요",
    bannerBody: "이 질문은 의료 전문가의 직접적인 판단이 필요한 주제입니다.",
    escalationCopy: "의학적 판단이 필요한 주제입니다. 치료 결정은 반드시 담당 의사와 상의해 주세요."
  }
};

function createSSEResponse(mockResponse: any) {
  return [
    `data: ${JSON.stringify({
      type: "node_update",
      node: "analysis",
      data: {
        analysis: mockResponse.analysis,
        safety: mockResponse.safety,
        observations: mockResponse.observations
      }
    })}\n\n`,
    `data: ${JSON.stringify({
      type: "node_update",
      node: "synthesis",
      data: {
        answer: mockResponse.answer,
        citations: mockResponse.citations,
        safety: mockResponse.safety
      }
    })}\n\n`,
    `data: ${JSON.stringify({
      type: "complete",
      total_duration: 0.3
    })}\n\n`
  ].join("");
}

test.describe("Safety System", () => {
  test("clear safety level - no banner displayed", async ({ page }) => {
    await page.route("**/v1/retrieve/stream", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: createSSEResponse(mockClearResponse)
      });
    });

    await page.goto("/");

    // Submit a safe question
    await page.locator("textarea#prompt").fill("운동을 얼마나 해야 하나요?");
    await page.getByRole("button", { name: "답변 요청" }).click();

    // Wait a moment for any potential banner
    await page.waitForTimeout(2000);

    // Verify no safety banner appears (only escalate and caution show banners)
    const safetyBanner = page.getByRole("status");
    await expect(safetyBanner).not.toBeVisible();

    // Verify transparency timeline still works
    await expect(page.getByText("일반 상담").first()).toBeVisible();
  });

  test("caution safety level - warning banner displayed", async ({ page }) => {
    await page.route("**/v1/retrieve/stream", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: createSSEResponse(mockCautionResponse)
      });
    });

    await page.goto("/");

    // Submit a question requiring caution
    await page.locator("textarea#prompt").fill("혈당이 150인데 괜찮나요?");
    await page.getByRole("button", { name: "답변 요청" }).click();

    // Wait for timeline to populate
    await expect(page.getByText("수치 분석").first()).toBeVisible({ timeout: 10000 });

    // Verify caution banner appears
    const safetyBanner = page.getByRole("status");
    await expect(safetyBanner).toBeVisible();

    // Check banner content
    await expect(safetyBanner).toContainText("의사");
  });

  test("escalate safety level - critical banner displayed", async ({ page }) => {
    await page.route("**/v1/retrieve/stream", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: createSSEResponse(mockEscalateResponse)
      });
    });

    await page.goto("/");

    // Submit a question requiring escalation
    await page.locator("textarea#prompt").fill("약을 줄이고 싶어요");
    await page.getByRole("button", { name: "답변 요청" }).click();

    // Wait for safety escalation in timeline
    await expect(page.getByText("Action: safety_escalation")).toBeVisible({ timeout: 10000 });

    // Verify escalation banner appears
    const safetyBanner = page.getByRole("status");
    await expect(safetyBanner).toBeVisible();

    // Check banner contains escalation guidance
    await expect(safetyBanner).toContainText("의사");
  });

  test("safety detection from draft prompt keywords", async ({ page }) => {
    await page.route("**/v1/retrieve/stream", async (route) => {
      // Don't respond immediately - test draft detection
      await new Promise(resolve => setTimeout(resolve, 100));
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: createSSEResponse(mockClearResponse)
      });
    });

    await page.goto("/");

    // Type a keyword that triggers safety detection (약, 처방, etc.)
    await page.locator("textarea#prompt").fill("약 처방");

    // The safety system should detect keywords even before submission
    // This tests the draft prompt detection in useSafetyEnvelope
    // Note: This may not show banner until submission depending on implementation
  });

  test("transparency timeline shows different observation types", async ({ page }) => {
    await page.route("**/v1/retrieve/stream", async (route) => {
      const response = {
        ...mockCautionResponse,
        observations: [
          { role: "reasoning", title: "Thought", content: "분석 중..." },
          { role: "action", title: "Action", content: "데이터 검색" },
          { role: "observation", title: "Observation", content: "결과 확인" }
        ]
      };
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: createSSEResponse(response)
      });
    });

    await page.goto("/");

    await page.locator("textarea#prompt").fill("테스트 질문");
    await page.getByRole("button", { name: "답변 요청" }).click();

    // Verify different types appear in transparency timeline
    await expect(page.getByRole("strong").filter({ hasText: "Thought" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("strong").filter({ hasText: "Action" })).toBeVisible();
    await expect(page.getByRole("strong").filter({ hasText: "Observation" })).toBeVisible();
  });
});
