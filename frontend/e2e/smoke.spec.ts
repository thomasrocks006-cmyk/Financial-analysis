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

  const auditPacket = {
    run_id: "run_demo_001",
    quality_score: 8.6,
    gates_passed: [1, 2, 3, 4, 5, 6, 7],
    gates_failed: [8],
    blockers: ["Macro sensitivity requires CIO review"],
    agents_succeeded: ["sector", "valuation"],
    agents_failed: [],
    total_claims: 24,
    pass_claims: 18,
    caveat_claims: 5,
    fail_claims: 1,
    tier1_claims: 6,
    tier2_claims: 8,
    tier3_claims: 7,
    tier4_claims: 3,
    ic_approved: true,
    ic_vote_breakdown: {
      pm: "approve",
      risk: "approve",
      compliance: "conditional",
    },
    mandate_compliant: true,
    esg_exclusions: ["Thermal coal"],
    stage_latencies_ms: { stage_1: 1200, stage_2: 2200 },
    total_pipeline_duration_s: 182,
    rebalancing_summary: { turnover_pct: 8.4 },
  };

  const quantPacket = {
    run_id: "run_demo_001",
    quant: {
      run_id: "run_demo_001",
      var_analysis: { var_pct: 2.31, cvar_pct: 3.42 },
      drawdown_analysis: { max_drawdown_pct: 9.8 },
      portfolio_volatility: 0.184,
      var_method: "historical",
      confidence_level: 0.95,
      etf_overlap: { overlaps: { XLK: 42.1, SOXX: 35.4 } },
      etf_differentiation_score: 72.5,
      factor_exposures: [
        {
          ticker: "NVDA",
          market_beta: 1.22,
          size_loading: -0.12,
          value_loading: -0.34,
          momentum_loading: 0.58,
          quality_loading: 0.41,
        },
      ],
      portfolio_factor_exposure: { market_beta: 1.1, size_loading: -0.1, momentum_loading: 0.33 },
      fixed_income_context: {},
      ic_record: { is_approved: true, votes: { pm: "approve", risk: "approve" } },
      mandate_compliance: { compliant: true, breaches: [] },
      baseline_weights: { NVDA: 0.12, AVGO: 0.11, TSM: 0.09 },
      optimisation_results: { objective: "max_sharpe", improvement_bps: 42 },
      rebalance_proposal: { trades: [{ ticker: "NVDA", action: "trim", delta_pct: -1.2 }] },
      attribution: { allocation_effect: 0.8, selection_effect: 1.2 },
      esg_scores: [{ ticker: "NVDA", score: 71 }],
    },
  };

  const provenancePacket = {
    run_id: "run_demo_001",
    provenance: {
      run_id: "run_demo_001",
      created_at: "2026-04-06T08:16:00Z",
      total_stages: 15,
      stages_with_provenance: 2,
      completeness_pct: 13,
      stage_cards: [
        {
          stage_num: 0,
          stage_label: "Bootstrap",
          run_id: "run_demo_001",
          timestamp: "2026-04-06T08:00:05Z",
          agent_name: "orchestrator",
          model_used: "claude-sonnet-4-6",
          model_temperature: 0.3,
          inputs: [{ name: "Universe request", source_type: "request", stage_origin: null, freshness: null, confidence: 1 }],
          outputs: [{ name: "Validated universe", output_type: "json", description: "Initial stage payload", artifact_path: null }],
          gate_passed: true,
          gate_reason: "Universe request accepted",
          gate_blockers: [],
          assumptions: ["Assume AU market session open"],
          duration_ms: 1200,
          error: null,
        },
      ],
      report_sections: [
        {
          section_title: "Executive Summary",
          section_index: 1,
          source_stages: [0, 1],
          source_agents: ["orchestrator", "valuation"],
          data_sources: [],
          confidence_level: "high",
          methodology_tags: ["summary", "multi-factor"],
        },
      ],
    },
  };

  const stageDetail = {
    stage_num: 0,
    stage_label: "Bootstrap",
    status: "completed",
    duration_ms: 1200,
    gate_passed: true,
    gate_reason: "Universe request accepted",
    output: {
      universe: ["NVDA", "AVGO", "TSM"],
      accepted: true,
      market: "us",
    },
    has_output: true,
  };

  const fulfillJson = async (route: Route, payload: JsonValue) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    });
  };

  await page.route("**/api/v1/runs**", async (route) => {
    const method = route.request().method();
    const url = new URL(route.request().url());
    const path = url.pathname;
    const runIdMatch = path.match(/\/api\/v1\/runs\/([^/]+)$/);

    if (method === "GET" && path.endsWith("/api/v1/runs")) {
      await fulfillJson(route, activeRuns);
      return;
    }

    if (method === "POST" && path.endsWith("/api/v1/runs")) {
      await fulfillJson(route, {
        run_id: "run_started_123",
        status: "queued",
        events_url: "/api/v1/runs/run_started_123/events",
      });
      return;
    }

    if (method === "GET" && path.endsWith("/audit")) {
      await fulfillJson(route, { audit_packet: auditPacket });
      return;
    }

    if (method === "GET" && path.endsWith("/quant")) {
      await fulfillJson(route, quantPacket);
      return;
    }

    if (method === "GET" && path.endsWith("/provenance")) {
      await fulfillJson(route, provenancePacket);
      return;
    }

    if (method === "GET" && /\/stages\/\d+$/.test(path)) {
      await fulfillJson(route, stageDetail);
      return;
    }

    if (method === "GET" && path.endsWith("/report")) {
      await fulfillJson(route, {
        run_id: "run_demo_001",
        report_markdown: "# Demo Report",
        word_count: 1234,
        estimated_pages: 4,
      });
      return;
    }

    if (method === "GET" && runIdMatch) {
      const runId = runIdMatch[1];
      const run = activeRuns.runs.find((item) => item.run_id === runId) || activeRuns.runs[0];
      await fulfillJson(route, run);
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
      listeners = new Map<string, Array<(event: MessageEvent) => void>>();
      onerror: ((event: Event) => void) | null = null;
      onopen: ((event: Event) => void) | null = null;
      readonly url: string;

      constructor(url: string) {
        this.url = url;
        window.setTimeout(() => {
          this.onopen?.(new Event("open"));
        }, 0);

        const events = [
          {
            type: "pipeline_started",
            payload: {
              run_id: "run_demo_001",
              event_type: "pipeline_started",
              timestamp: "2026-04-06T08:00:05Z",
              stage: null,
              stage_label: null,
              agent_name: "orchestrator",
              duration_ms: null,
              data: {},
            },
          },
          {
            type: "stage_started",
            payload: {
              run_id: "run_demo_001",
              event_type: "stage_started",
              timestamp: "2026-04-06T08:00:06Z",
              stage: 0,
              stage_label: "Bootstrap",
              agent_name: "orchestrator",
              duration_ms: null,
              data: {},
            },
          },
          {
            type: "stage_completed",
            payload: {
              run_id: "run_demo_001",
              event_type: "stage_completed",
              timestamp: "2026-04-06T08:00:07Z",
              stage: 0,
              stage_label: "Bootstrap",
              agent_name: "orchestrator",
              duration_ms: 1200,
              data: {},
            },
          },
          {
            type: "stage_started",
            payload: {
              run_id: "run_demo_001",
              event_type: "stage_started",
              timestamp: "2026-04-06T08:00:08Z",
              stage: 1,
              stage_label: "Universe Validation",
              agent_name: "validator",
              duration_ms: null,
              data: {},
            },
          },
          {
            type: "stage_completed",
            payload: {
              run_id: "run_demo_001",
              event_type: "stage_completed",
              timestamp: "2026-04-06T08:00:10Z",
              stage: 1,
              stage_label: "Universe Validation",
              agent_name: "validator",
              duration_ms: 2400,
              data: {},
            },
          },
          {
            type: "pipeline_completed",
            payload: {
              run_id: "run_demo_001",
              event_type: "pipeline_completed",
              timestamp: "2026-04-06T08:03:07Z",
              stage: null,
              stage_label: null,
              agent_name: null,
              duration_ms: 182000,
              data: {},
            },
          },
        ];

        events.forEach((entry, index) => {
          window.setTimeout(() => {
            this.dispatch(entry.type, entry.payload);
          }, 30 * (index + 1));
        });
      }

      dispatch(type: string, payload: Record<string, unknown>) {
        const event = new MessageEvent(type, { data: JSON.stringify(payload) });
        const listeners = this.listeners.get(type) || [];
        listeners.forEach((listener: (event: MessageEvent) => void) => listener(event));
      }

      addEventListener(type: string, callback: (event: MessageEvent) => void) {
        const listeners = this.listeners.get(type) || [];
        listeners.push(callback);
        this.listeners.set(type, listeners);
        return undefined;
      }

      removeEventListener(type: string, callback: (event: MessageEvent) => void) {
        const listeners = this.listeners.get(type) || [];
        this.listeners.set(
          type,
          listeners.filter((listener: (event: MessageEvent) => void) => listener !== callback),
        );
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
  await expect(page.getByRole("link", { name: /run_saved_001/i }).first()).toBeVisible();
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

test("portfolio screen shows run staging and overlay data", async ({ page }) => {
  await page.goto("/portfolio");

  await expect(page.getByText("Portfolio Workbench")).toBeVisible();
  await expect(page.getByText("Run staging board")).toBeVisible();
  await expect(page.getByRole("button", { name: /run_demo_001/i })).toBeVisible();
  await expect(page.getByText("Selected run overlay")).toBeVisible();
  await expect(page.getByText(/Desk overlap:/)).toBeVisible();
});

test("audit screen loads gate and committee data", async ({ page }) => {
  await page.goto("/audit");

  await expect(page.getByText("Audit Console")).toBeVisible();
  await expect(page.getByText("Gate Console")).toBeVisible();
  await expect(page.getByText("Investment Committee", { exact: true })).toBeVisible();
  await expect(page.getByText("Macro sensitivity requires CIO review")).toBeVisible();
  await expect(page.getByText("APPROVED")).toBeVisible();
});

test("quant screen loads analytics for selected run", async ({ page }) => {
  await page.goto("/quant");

  await expect(page.getByText("Quant Lab")).toBeVisible();
  await expect(page.getByText("Market Risk Metrics")).toBeVisible();
  await expect(page.getByText("ETF Overlap & Differentiation")).toBeVisible();
  await expect(page.getByText("72.5 / 100")).toBeVisible();
});

test("run detail covers report audit provenance and stage detail tabs", async ({ page }) => {
  await page.goto("/runs/run_demo_001");

  await expect(page.getByText("Completed")).toBeVisible();

  await page.getByRole("button", { name: "Report", exact: true }).click();
  await expect(page.getByText("Research Report")).toBeVisible();
  await expect(page.getByText("Demo Report")).toBeVisible();

  await page.getByRole("button", { name: "Audit & Quality", exact: true }).click();
  await expect(page.getByText("Quality Score")).toBeVisible();
  await expect(page.locator("li", { hasText: "Macro sensitivity requires CIO review" })).toBeVisible();

  await page.getByRole("button", { name: "Provenance", exact: true }).click();
  await expect(page.getByText("Provenance Coverage")).toBeVisible();
  await expect(page.getByText(/Executive Summary/i)).toBeVisible();

  await page.getByRole("button", { name: "Stage Detail", exact: true }).click();
  await page.getByText("Bootstrap", { exact: true }).first().click();
  await expect(page.getByText(/Gate reason:/)).toBeVisible();
  await expect(page.getByText(/Universe request accepted/)).toBeVisible();
});
