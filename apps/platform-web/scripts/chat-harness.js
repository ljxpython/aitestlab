/* eslint-disable @typescript-eslint/no-unused-expressions */
// prettier-ignore
async (page) => {
  const responses = [];
  const consoleErrors = [];
  const pageErrors = [];

  page.on("response", (response) => {
    const path = response.url().split(/[?#]/, 1)[0].replace(/^https?:\/\/[^/]+/, "");
    if (path.startsWith("/api/langgraph/")) {
      responses.push({ path, status: response.status() });
    }
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text().slice(0, 300));
    }
  });
  page.on("pageerror", (error) => pageErrors.push(String(error).slice(0, 300)));

  const fail = (phase, message) => {
    throw new Error(
      JSON.stringify({
        phase,
        message,
        url: page.url(),
        responses,
        consoleErrors,
        pageErrors,
      }),
    );
  };

  const waitForAgentReply = async (marker, previousCount, phase) => {
    const deadline = Date.now() + 120000;
    while (Date.now() < deadline) {
      const fatal = responses.find(
        (item) => item.status === 409 || item.status >= 500,
      );
      if (fatal) {
        fail(phase, `关键 API 返回 ${fatal.status}：${fatal.path}`);
      }

      const replies = page.locator(".pw-chat-agent-message");
      const count = await replies.count();
      if (count > previousCount) {
        const text = await replies.last().innerText();
        if (text.includes(marker)) {
          return text;
        }
        const sendReady = await page
          .getByRole("button", { name: "发送消息", exact: true })
          .first()
          .isEnabled()
          .catch(() => false);
        if (sendReady && text.trim()) {
          fail(phase, `最新 Agent 回复未包含当前轮标识 ${marker}`);
        }
      }
      await page.waitForTimeout(250);
    }
    fail(phase, `未收到包含 ${marker} 的最新 Agent 回复`);
  };

  try {
    if (page.url().includes('/auth/login')) {
      fail('preflight', '当前浏览器没有登录态，页面链路未执行')
    }
    if (!/[?&]startNew=1(?:&|$)/.test(page.url())) {
      fail("preflight", "入口必须带 startNew=1，禁止复用历史 Thread");
    }

    const composer = page.locator('textarea[placeholder*="输入消息"]').first();
    await composer.waitFor({ state: "visible", timeout: 15000 }).catch(() => {
      fail(
        "preflight",
        "聊天输入框不可用，项目上下文、目标 Agent 或页面 readiness 未通过",
      );
    });
    const sendButton = page
      .getByRole("button", { name: "发送消息", exact: true })
      .first();

    const suffix = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const firstMarker = `HARNESS_FIRST_${suffix}`;
    const secondMarker = `HARNESS_SECOND_${suffix}`;

    await composer.fill(`请只原样输出：${firstMarker}`);
    await sendButton.click();
    const firstReply = await waitForAgentReply(firstMarker, 0, "first-run");

    await sendButton.waitFor({ state: "visible", timeout: 15000 });
    await page
      .waitForFunction(
        () =>
          [...document.querySelectorAll("button")].some(
            (button) =>
              button.textContent?.includes("发送消息") &&
              !(button instanceof HTMLButtonElement && button.disabled),
          ),
        undefined,
        { timeout: 15000 },
      )
      .catch(() => fail("second-run", "第一轮结束后发送按钮仍不可用"));
    await composer.fill(`请只原样输出：${secondMarker}`);
    await sendButton.click();
    const secondReply = await waitForAgentReply(secondMarker, 1, "second-run");

    const threadId = page.url().match(/[?&]threadId=([^&]+)/)?.[1] || "";
    if (!threadId) {
      fail("thread-persistence", "发送完成后 URL 没有持久化 threadId");
    }

    const beforeReloadReplies = await page
      .locator(".pw-chat-agent-message")
      .count();
    await page.reload({ waitUntil: "domcontentloaded" });
    await page
      .locator(".pw-chat-agent-message")
      .nth(beforeReloadReplies - 1)
      .waitFor({ state: "visible", timeout: 30000 });
    const restoredText = await page
      .locator(".pw-chat-agent-message")
      .last()
      .innerText();
    if (!restoredText.includes(secondMarker)) {
      fail("reopen", `刷新后最新 Agent 回复未恢复第二轮标识 ${secondMarker}`);
    }

    const fatalResponses = responses.filter(
      (item) => item.status === 409 || item.status >= 500,
    );
    if (fatalResponses.length > 0) {
      fail(
        "api-evidence",
        `捕获到 409/5xx 响应：${JSON.stringify(fatalResponses)}`,
      );
    }

    const criticalPaths = responses.filter((item) =>
      /\/runs\/stream$|\/threads\/[^/]+\/(state|history)$/.test(item.path),
    );
    const failedCritical = criticalPaths.filter((item) => item.status >= 400);
    if (failedCritical.length > 0) {
      fail(
        "api-evidence",
        `关键 API 返回错误：${JSON.stringify(failedCritical)}`,
      );
    }
    if (
      !criticalPaths.some(
        (item) => item.path.endsWith("/runs/stream") && item.status < 400,
      )
    ) {
      fail("api-evidence", "没有捕获到成功的 runs/stream 响应");
    }
    if (
      !criticalPaths.some(
        (item) => item.path.endsWith("/state") && item.status < 400,
      )
    ) {
      fail("api-evidence", "没有捕获到成功的 Thread state 响应");
    }
    if (
      !criticalPaths.some(
        (item) => item.path.endsWith("/history") && item.status < 400,
      )
    ) {
      fail("api-evidence", "没有捕获到成功的 Thread history 响应");
    }
    if (consoleErrors.length || pageErrors.length) {
      fail("browser-errors", "浏览器存在 console/page error");
    }

    return JSON.stringify({
      status: "passed",
      threadId,
      firstReply: firstReply.slice(0, 240),
      secondReply: secondReply.slice(0, 240),
      restoredReply: restoredText.slice(0, 240),
      criticalPaths,
    });
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("{")) {
      throw error;
    }
    fail("unexpected", error instanceof Error ? error.message : String(error));
  }
}
