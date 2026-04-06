import { expect, test, type Page, type Route } from "@playwright/test";

type JsonValue = Record<string, unknown> | Array<unknown>;

async function mockApi(page: Page): Promise<void> {
  const activeRuns = {
    runs: [
      {
        run_id: "run_demo_001",
        status: "running",
        run_label: "Demo Run",
        universe: ["NVDA", "AVGO", "TSM"],
        created_at: "2026-04-06T08:00:00Z",
        started_at: "2026-04-06T08:00:05Z",
        completed_at: null,
      },
      {
        run_id: "run_demo_002",
        status: "completed",
        run_label: "Completed Run",
        universe: ["MSFT", "AMZN", "GOOGL"],
        created_at: "2026-04-05T04:00:00Z",
        started_at: "2026-04-05T04:00:05Z",
        completed_at: "2026-04-05T04:15:00Z",
      },
    ],
    count: 2,
  };

  let savedRuns = {
    runs: [
      {
        run_id: "run_saved_001",
        tickers: ["NVDA", "TSM"],
        model: "claude-sonnet-4-6",
        completed_at: "2026-04-05T04:15:00Z",
        success: true,
        publication_status: "PASS",
        word_count: 1234,
        json_path: "/tmp/run_saved_001.json",
        md_path: "/tmp/run_saved_001.md",
      },
    ],
    count: 1,
  };

  const fulfillJson = async (route: Route, payload: JsonValue) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    });
  };

  await page.route("**/api/v1/runs*", async (route) => {
    if (route.request().method() === "GET") {
      await fulfillJson(route, activeRuns);
      return;
    }
    if (route.request().method() === "POST") {
      await fulfillJson(route, {
        run_id: "run_started_123",
        status: "queued",
        events_url: "/api/v1/runs/run_started_123/events",
      });
      return;
    }
    await route.fallback();
  });

  await page.route("**/api/v1/saved-runs*", async (route) => {
    if (route.request().method() === "GET") {
      await fulfillJson(route, savedRuns);
      return;
    }
    await route.fallback();
  });

  await page.route("**/api/v1/saved-runs/*", async (route) => {
    if (route.request().method() === "DELETE") {
      const runId = route.request().url().split("/").pop() || "unknown";
      savedRuns = {
        runs: savedRuns.runs.filter(
          (run) => (run as Record<string, unknown>).run_id !== runId,
        ) as typeof savedRuns.runs,
        count: Math.max(savedRuns.count - 1, 0),
      };
      await fulfillJson(route, { deleted: true, run_id: runId });
      return;
    }

    if (route.request().method() === "GET") {
      await fulfillJson(route, {
        run_id: "run_saved_001",
        report_markdown: "# Report",
      });
      return;
    }

    await route.fallback();
  });

  await page.addInitScript(() => {
    class MockEventSource {
      onerror: ((event: Event) => void) | null = null;
      onopen: ((event: Event) => void) | null = null;
      readonly url: string;

      constructor(url: string) {
        this.url = url;
        window.setTimeout(() => {
          this.onopen?.(new Event("open"));
        }, 0);
      }

      addEventListener() {
        return undefined;
      }

      removeEventListener() {
        return undefined;
      }

      close() {
        return undefined;
      }
    }

    // @ts-expect-error test shim
    window.EventSource = MockEventSource;
  });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("dashboard renders active and saved run summaries", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Meridian Research Terminal")).toBeVisible();
  await expect(page.getByText("Recent Runs")).toBeVisible();
  await expect(page.getByRole("link", { name: /run_demo_001/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /run_saved_001/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /saved reports f4/i })).toBeVisible();
});

test("new run page supports preset and custom ticker editing", async ({ page }) => {
  await page.goto("/runs/new");

  await expect(page.getByText("Preset Universe")).toBeVisible();
  await page.getByRole("button", { name: "AI COMPUTE" }).click();
  await expect(page.getByText(/Universe\s+\(5 tickers\)/)).toBeVisible();

  const input = page.getByPlaceholder("ADD TICKER + ENTER");
  await input.fill("CSCO");
  await input.press("Enter");

  await expect(page.getByText(/Universe\s+\(6 tickers\)/)).toBeVisible();
  await expect(page.getByRole("button", { name: /CSCO ×/ })).toBeVisible();
});

test("saved runs page supports delete confirmation flow", async ({ page }) => {
  await page.goto("/saved");

  await expect(page.getByRole("heading", { name: /Saved Runs \(1\)/ })).toBeVisible();
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("button", { name: "Confirm delete" })).toBeVisible();
  await page.getByRole("button", { name: "Confirm delete" }).click();

  await expect(page.getByText("No saved runs found.")).toBeVisible();
});

test("command bar navigation routes to settings", async ({ page }) => {
  await page.goto("/");

  const commandInput = page.getByPlaceholder(/COMMAND — TYPE SCREEN NAME/);
  await commandInput.fill("SETTINGS");
  await expect(commandInput).toHaveValue("SETTINGS");
  await commandInput.press("Enter");

  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByText("API Connection")).toBeVisible();
});
