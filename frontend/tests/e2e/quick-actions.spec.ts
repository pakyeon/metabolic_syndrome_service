import { expect, test } from "@playwright/test";

// Mock responses for different quick actions
const mockExercisePlanResponse = {
  analysis: { domain: "lifestyle", complexity: "medium", safety: "clear" },
  answer: "주간 운동 계획: 월/수/금 근력운동 30분, 화/목 유산소 40분을 권장합니다.",
  citations: ["운동 가이드라인 2024"],
  observations: [
    { role: "reasoning", title: "운동 계획 수립", content: "야간 근무 패턴 고려" },
    { role: "action", title: "계획 생성", content: "주 5회 분산 운동" }
  ],
  safety: { level: "clear" }
};

const mockNutritionResponse = {
  analysis: { domain: "nutrition", complexity: "simple", safety: "clear" },
  answer: "저당 단백질 간식: 1) 그릭 요거트, 2) 삶은 계란, 3) 아몬드 한 줌",
  citations: ["영양 가이드 2024"],
  observations: [
    { role: "reasoning", title: "영양 분석", content: "야간 근무 후 간식" },
    { role: "action", title: "추천 생성", content: "단백질 위주 선택" }
  ],
  safety: { level: "clear" }
};

const mockMedicalEscalationResponse = {
  analysis: { domain: "medical", complexity: "simple", safety: "escalate" },
  answer: "가슴 두근거림이 반복되면 즉시 담당 의사와 상담이 필요합니다.",
  citations: [],
  observations: [
    { role: "reasoning", title: "증상 평가", content: "심혈관 증상 감지" },
    { role: "action", title: "안전 조치", content: "Action: safety_escalation" }
  ],
  safety: {
    level: "escalate",
    bannerTitle: "의료 에스컬레이션 필요",
    bannerBody: "이 증상은 의료 전문가의 즉각적인 평가가 필요합니다.",
    escalationCopy: "즉시 담당 의사와 상담해 주세요."
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

test.describe("Quick Actions", () => {
  test("exercise plan quick action", async ({ page }) => {
    await page.route("**/v1/retrieve/stream", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: createSSEResponse(mockExercisePlanResponse)
      });
    });

    await page.goto("/");

    // Click the exercise plan quick action
    await page.getByRole("button", { name: /주간 운동 플랜/i }).click();

    // Verify mode switched to live
    await expect(page.getByText("실시간 모드 SLA: 답변 시작 10초 이내")).toBeVisible();

    // Verify prompt was hydrated
    await expect(page.locator("textarea#prompt")).toHaveValue(/운동 계획/);
  });

  test("nutrition recommendation quick action", async ({ page }) => {
    await page.route("**/v1/retrieve/stream", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: createSSEResponse(mockNutritionResponse)
      });
    });

    await page.goto("/");

    // Click the nutrition quick action
    await page.getByRole("button", { name: /야식 대체/i }).click();

    // Verify mode switched to live
    await expect(page.getByText("실시간 모드 SLA: 답변 시작 10초 이내")).toBeVisible();

    // Verify prompt was hydrated
    await expect(page.locator("textarea#prompt")).toHaveValue(/간식/);
  });

  test("medical escalation quick action shows safety banner", async ({ page }) => {
    await page.route("**/v1/retrieve/stream", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: createSSEResponse(mockMedicalEscalationResponse)
      });
    });

    await page.goto("/");

    // Click the medical escalation quick action
    await page.getByRole("button", { name: /의료 에스컬레이션/i }).click();

    // Submit the hydrated prompt to trigger the response
    await page.getByRole("button", { name: "답변 요청" }).click();

    // Wait for safety escalation in timeline
    await expect(page.getByText("Action: safety_escalation")).toBeVisible({ timeout: 10000 });

    // Verify safety banner appears
    const safetyBanner = page.getByRole("status");
    await expect(safetyBanner).toBeVisible();
    await expect(safetyBanner).toContainText("의사");
  });

  test("all four quick actions are present", async ({ page }) => {
    await page.goto("/");

    // Verify all 4 quick action buttons exist
    await expect(page.getByRole("button", { name: /상담 준비 요약/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /주간 운동 플랜/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /의료 에스컬레이션/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /야식 대체/i })).toBeVisible();
  });
});
