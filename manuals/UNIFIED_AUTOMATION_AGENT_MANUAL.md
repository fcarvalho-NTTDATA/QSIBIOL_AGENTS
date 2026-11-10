# Unified Automation Agent Manual (automation-agent-unified)

This document is the **user manual** for the **Unified Automation Manager Agent** (`automation-agent-unified`) — a single agent that consolidates the previous **Web/API Automation Agent** and **Mobile Automation Agent** into one orchestrated solution.

It covers automation across **Web (`playwright` MCP)**, **Mobile (`mobile-mcp` / Appium)**, **Desktop (`desktop-automation` MCP)**, and **API (REST/GraphQL/OpenAPI)** technologies, all under the same execution-first principles and quality gates.

---

## Table of Contents

- [1. Overview](#1-overview)
- [2. What This Agent Does (and Does Not Do)](#2-what-this-agent-does-and-does-not-do)
- [3. Key Features](#3-key-features)
- [4. Non-Negotiable Principles](#4-non-negotiable-principles)
- [5. Supported Technologies & Skill Orchestration](#5-supported-technologies--skill-orchestration)
- [6. Prerequisites](#6-prerequisites)
  - [6.1 MCP Servers (mandatory)](#61-mcp-servers-mandatory)
  - [6.2 Local Tooling](#62-local-tooling)
  - [6.3 Environment & Targets](#63-environment--targets)
- [7. How to Use (Prompt Recipes)](#7-how-to-use-prompt-recipes)
- [8. Unified Workflow (End-to-End)](#8-unified-workflow-end-to-end)
  - [8.1 Phase 0 — MCP Tools Verification](#81-phase-0--mcp-tools-verification)
  - [8.2 Phase 1 — Project Analysis](#82-phase-1--project-analysis)
  - [8.3 Phase 2A — Execute Existing Tests](#83-phase-2a--execute-existing-tests)
  - [8.4 Phase 2B — Live Exploration](#84-phase-2b--live-exploration)
  - [8.5 Phase 3 — Code Generation](#85-phase-3--code-generation)
  - [8.6 Phase 4 — Execution & Validation Loop](#86-phase-4--execution--validation-loop)
  - [8.7 Phase 5 — Delivery & Reporting](#87-phase-5--delivery--reporting)
- [9. Execution Modes](#9-execution-modes)
- [10. Technology Selection & Defaults](#10-technology-selection--defaults)
- [11. Quality Gates](#11-quality-gates)
- [12. Error Handling & Iteration Limits](#12-error-handling--iteration-limits)
- [13. False Positives Prevention](#13-false-positives-prevention)
- [14. Evidence, Artifacts & Reporting](#14-evidence-artifacts--reporting)
- [15. Cross-Technology Scenarios](#15-cross-technology-scenarios)
- [16. Desktop Reliability](#16-desktop-reliability)
- [17. Session Management & Cleanup](#17-session-management--cleanup)
- [18. Troubleshooting](#18-troubleshooting)
- [19. Best Practices](#19-best-practices)
- [20. Quick Reference](#20-quick-reference)

---

## 1. Overview

The **Unified Automation Manager Agent** is a single, technology-aware agent that handles **Web**, **Mobile**, **Desktop**, and **API** test automation through a common execution-first workflow.

It replaces the previous split between:

- **Web/API Automation Agent** (Playwright + API)
- **Mobile Automation Agent** (Appium + mobile-mcp)

Both agents have been consolidated into `automation-agent-unified`, which:

- Detects the target technology automatically (or from explicit user request)
- Loads the appropriate technology **skills** (Playwright, Mobile, Desktop, API)
- Performs **live exploration** with the matching MCP server
- Reuses existing automation projects when available
- Generates production-ready code in **any programming language**
- Iteratively executes and fixes the generated code until 100% functional
- Produces evidence (screenshots, page source, logs, reports) under `evidences/`

**Core Principle**: Live-execution-first. No assumptions, no theoretical code, no untested deliveries.

---

## 2. What This Agent Does (and Does Not Do)

### Does
- Analyzes existing automation projects (web, mobile, desktop, API) and reuses them.
- Performs **mandatory live exploration** for new or unknown flows.
- Generates Web automation via **Playwright** (using the **`playwright`** MCP server for exploration).
- Generates Mobile automation via **Appium** (using **mobile-mcp** for exploration), Android and iOS.
- Generates Desktop automation (e.g. PyAutoGUI, pywinauto) using the **`desktop-automation`** MCP server for exploration.
- Generates API automation via HTTP clients (RestAssured, axios, requests, supertest, etc.).
- Executes generated tests, fixes failures iteratively, and delivers execution-verified results.
- Produces evidence and a final report under `<project-root>/evidences/`.

### Does not
- Generate code from assumptions or templates without live exploration.
- Deliver code as “successful” if it hasn’t been executed and validated.
- Operate without MCP tools — MCP is mandatory.
- Hide failures or report false positives.
- Replace an existing stack with a different one without strong reason and user awareness.

---

## 3. Key Features

- **Unified entry point** for Web, Mobile, Desktop, and API automation
- **Automatic technology detection** based on user intent and project context
- **Live exploration** via the appropriate MCP server:
  - Web → `playwright` (browser_navigate, browser_snapshot, browser_click, browser_type, …)
  - Mobile → `mobile-mcp` (mobile_launch_app, mobile_list_elements_on_screen, mobile_click_on_screen_at_coordinates, …)
  - Desktop → `desktop-automation` (desktop_*)
  - API → HTTP clients (with optional OpenAPI/Postman input)
- **Intelligent element/endpoint discovery** with stability rankings:
  - Web: `data-testid` > `aria-*` > `id` > `name` > text
  - Android: `resource-id` > `content-desc` > `text`
  - iOS: `accessibility id` > `name` > `label`
- **Multi-language code generation** (Java, JavaScript/TypeScript, Python, C#, …)
- **Headed-by-default execution** for Web and Mobile (visible browser/device/emulator)
- **Iterative validation**: execute → classify → fix → re-execute (up to 5 iterations)
- **Mandatory final report** with screenshots/evidence
- **Project awareness**: detects framework and reuses structure instead of duplicating
- **Cross-technology coordination** (e.g., Web UI + API backend in one flow)

---

## 4. Non-Negotiable Principles

These rules are enforced by the agent and cannot be bypassed:

1. **MCP tools are mandatory** — no work begins without them available.
2. **Live-execution-first** — every decision validated on the real system.
3. **No code without live exploration** for new or unknown flows.
4. **No theoretical locators or endpoints** — only validated from live analysis.
5. **No untested deliveries** — generated code must be executed and pass.
6. **No false positives** — never report success when tests are failing.
7. **No partial success by default** — 100% pass rate required, unless the user explicitly acknowledges a documented `system_bug`.
8. **Headed by default** for Web and Mobile; headless/hidden only on explicit user request.
9. **Evidence required** under `<project-root>/evidences/`.
10. **Project awareness** — reuse existing automation; never duplicate.

If any conflict arises:

- Live exploration beats speed
- MCP tools beat convenience
- Real execution beats assumptions
- Validated code beats quick delivery
- 100% success beats partial success

---

## 5. Supported Technologies & Skill Orchestration

The agent loads skills dynamically based on detected technology.

### Detection Rules

| Trigger | Technology |
|---|---|
| Web, browser, URL, website mentions; Playwright deps | **Web** |
| Mobile, app, Android, iOS, device, emulator mentions; Appium deps | **Mobile** |
| Desktop, Windows application, native app, GUI automation mentions; PyAutoGUI / pywinauto / SikuliX / AutoIt deps | **Desktop** |
| API, endpoint, REST, GraphQL, OpenAPI, Postman mentions | **API** |

Mixed scenarios are supported (multiple skills can be loaded in the same session).

### Skill Loading Order

1. **Always first**: `project-analysis`
2. **Technology-specific** (one or more):
   - `web-automation-playwright`
   - `mobile-automation` (Appium)
   - `desktop-automation`
   - `api-automation`
3. **For new tests**: `live-exploration-workflow`
4. **For code generation**: `code-generation`
5. **For execution validation**: `execution-validation`

### Skill Precedence

- Technology-specific skills override generic patterns for their domain.
- Shared skills (`live-exploration-workflow`, `code-generation`, `execution-validation`) provide the common pattern.
- On conflict: **Safety → Technology-specific → Shared**.

---

## 6. Prerequisites

### 6.1 MCP Servers (mandatory)

Depending on the requested technology:

- **Web**: `playwright` server configured and reachable
- **Mobile**: `mobile-mcp` server configured and reachable
- **Desktop**: `desktop-automation` server configured and reachable
- **API**: Optional MCP (e.g., Postman MCP); HTTP clients may be used directly

If the required MCP server is **not configured**, the agent **stops in Phase 0** and requests configuration. It will not proceed with theoretical work.

The **Automation** (and **All**) package adds `qa_mcp_server`, `playwright` and `mobile-mcp` to `.vscode/mcp.json` (merged into the existing file). The `desktop-automation` server is not configured by the installer; add it yourself when you need desktop automation.

### 6.2 Local Tooling

Depending on stack and technology:

- **Web (Playwright)**:
  - Node + npm (TS/JS) or Java + Maven, Python, C#, etc., per selected stack
  - Playwright browsers installed for the chosen language binding
- **Mobile (Appium)**:
  - Appium Server (Node-based) installed
  - Drivers installed: `UiAutomator2` (Android), `XCUITest` (iOS, macOS only)
  - Android emulator/USB device or iOS simulator/device
- **API**:
  - HTTP client library appropriate to the selected stack

Common preflight commands:

- `java -version`, `mvn -version`
- `node -v`, `npm -v`
- `appium -v`, `appium driver list --installed`

If preflight fails, the agent classifies it as `user_input_needed` and stops until resolved (unless installation is explicitly authorized).

### 6.3 Environment & Targets

Common variables (project-specific examples; the agent does not require them):

- **Mobile target selection**: `MOBILE_EXECUTION_TARGET` = `emulator | usb | browserstack | saucelabs`
- **BrowserStack**: `BROWSERSTACK_USERNAME`, `BROWSERSTACK_ACCESS_KEY`, `BROWSERSTACK_APP_ID`
- **Sauce Labs**: `SAUCE_USERNAME`, `SAUCE_ACCESS_KEY`, `SAUCE_APP_ID`

Secrets must come from environment variables (or CI secrets) — never committed.

---

## 7. How to Use (Prompt Recipes)

The agent accepts the same natural-language patterns regardless of technology.

### Web

> “Create automation for the login flow at https://example.com in Java with Playwright.”

> “Automate the checkout scenario described in `test_cases/US002/test_cases.md` using TypeScript.”

### Mobile

> “Automate the onboarding flow of the Android app. Explore live with mobile-mcp, extract stable locators, then generate and execute tests until passing.”

> “Run the existing mobile suite on BrowserStack (`MOBILE_EXECUTION_TARGET=browserstack`) using environment variables for credentials.”

### API

> “Create API automation for the CRUD operations on `/api/users` in Python.”

> “Generate API tests from this OpenAPI spec and validate the contract end-to-end.”

### Extend Existing Project

> “Add automation for the user profile update flow to the existing project in `/automation/web-tests`.”

### Cross-Technology

> “Automate the checkout flow on the web app and validate the resulting order via the backend API in TypeScript.”

### Debug / Replay

> “Re-run the failing mobile tests, capture screenshots and page source on failure, and fix any code issues.”

---

## 8. Unified Workflow (End-to-End)

### 8.1 Phase 0 — MCP Tools Verification

Before anything else:

1. Check if the required MCP tools are available:
   - Web → `playwright/browser_*`
   - Mobile → `mobile-mcp/mobile_*`
   - Desktop → `desktop-automation/*`
2. If available → proceed to Phase 1.
3. If configured but not started → start the MCP server, verify tools, proceed.
4. If not configured at all → **STOP** and request configuration. Do not proceed.

**Absolute rule**: never attempt automation work without MCP tools.

### 8.2 Phase 1 — Project Analysis

Uses the `project-analysis` skill to:

- Inspect workspace structure
- Detect language, build system, and test frameworks
- Locate test files, page/screen objects, and utilities
- Compare the requested flow with existing coverage
- Decide between **execute existing** vs. **explore new**

### 8.3 Phase 2A — Execute Existing Tests

If an existing test covers the request:

1. Execute the test.
2. Analyze failures.
3. Fix `code_issue` failures automatically.
4. Report `system_bug` failures explicitly.
5. Re-execute until 100% success (or escalate per Section 12).

### 8.4 Phase 2B — Live Exploration

For new flows, the agent runs the `live-exploration-workflow` skill together with the appropriate technology skill:

- **Web** (`web-automation-playwright`):
  - Open browser in **headed mode by default**
  - Navigate, capture `browser_snapshot`, interact, verify state
  - Handle tabs, frames, storage, dialogs
- **Mobile** (`mobile-automation`):
  - Launch app on emulator/device (headed by default)
  - Capture page source and screenshots before/after each action
  - Handle Android vs. iOS specifics, permissions, context switches (NATIVE/WEBVIEW)
- **API** (`api-automation`):
  - Discover endpoints from OpenAPI/Postman or live calls
  - Validate schemas and authentication
  - Capture full request/response evidence

Exploration loop, per step:

1. **Analyze** — capture current structure
2. **Identify** — select target, extract stable locators/endpoints
3. **Execute** — perform action via MCP
4. **Verify** — confirm state change and note automation challenges

### 8.5 Phase 3 — Code Generation

Uses the `code-generation` skill. Mandatory prerequisites:

- Live exploration completed
- All elements/endpoints captured from real systems
- Locator strategies documented with stability rankings
- Automation challenges identified with solutions

Code generation:

1. Select technology stack (existing project default, user choice, or fallback default)
2. Generate code using **only validated exploration data**
3. Apply quality gates (coverage, stability, resilience, maintainability)
4. Include screenshot/evidence capture
5. Wire automated final report generation

### 8.6 Phase 4 — Execution & Validation Loop

Uses the `execution-validation` skill.

1. **Execute** generated code immediately.
2. **Analyze** results (pass/fail, output, artifacts).
3. **Classify** failures: `code_issue`, `system_bug`, `user_input_needed`.
4. **Fix** automatically for `code_issue` (max 5 iterations).
5. **Re-execute** and repeat until 100% success.

**Mobile execution gates** (recommended cadence):

- **Gate A — Build Gate** (e.g., `mvn -q -DskipTests package`)
- **Gate B — Appium Session Gate** (minimal smoke: create driver, capture screenshot + page source, quit)
- **Gate C — Full Flow Gate** (execute the full requested flow with assertions)

Delivery is not “complete” until Gate C passes (or a blocker is documented and explicitly accepted by the user).

### 8.7 Phase 5 — Delivery & Reporting

Final report includes:

- **Status**: ✅ FULLY FUNCTIONAL | ⚠️ PARTIAL — USER ACKNOWLEDGED | ❌ BLOCKED
- **Execution summary**: total, passed, failed, execution time
- **Evidence links**: reports, screenshots, page source (mobile), logs
- **What was automated**: step-by-step with status
- **Known limitations**: classification + user acknowledgment
- **Next steps**: how to run tests and view reports

All evidence is stored under `<project-root>/evidences/`. Do not write evidence to `evidence/`, `artifacts/`, or any other root unless the user explicitly overrides.

---

## 9. Execution Modes

The agent operates in one explicit mode:

- `exploration` — live discovery and mapping (technology-specific)
- `execution` — running existing automated tests
- `replay` — re-running flows without discovery
- `debug` — focused investigation of failures

For API specifically, sub-modes apply:

- `api-exploration`, `api-execution`, `api-debug`

Mode influences required steps but **never bypasses invariants**.

---

## 10. Technology Selection & Defaults

If the user does not specify a stack, and no existing project provides one:

- **Web**: Java + Playwright + Cucumber
- **Mobile**: Java + Appium + Cucumber
- **Desktop**: Python + PyAutoGUI + Pytest
- **API**: Java + RestAssured + Cucumber

These are **fallback defaults only**. The agent will:

1. Match the existing project stack if found.
2. Ask the user for preference if no project exists.
3. Use the default only if the user does not respond.

Any language/framework explicitly requested by the user is honored (JS/TS, Python, C#, Ruby, Go, Kotlin, …).

---

## 11. Quality Gates

Every delivery must meet:

- ✅ **Code coverage** documented (% of flow automated)
- ✅ **Stable locators/endpoints** (per stability ranking)
- ✅ **Resilient waits** (no fixed sleeps when avoidable)
- ✅ **Reasonable execution time** (single test ideally <2–3 min; document otherwise)
- ✅ **Maintainability** (clear naming, reusable components)
- ✅ **Evidence** captured on success **and** failure
- ✅ **Parallel safety** (isolated state) unless documented otherwise
- ✅ **Final report** generated automatically

Technology skills may extend these gates with additional requirements.

---

## 12. Error Handling & Iteration Limits

All failures are classified as:

| Category | Description | Action |
|---|---|---|
| `code_issue` | Defect in the generated automation | Fix automatically and re-execute |
| `system_bug` | Defect in the application under test | Document and notify user |
| `user_input_needed` | Missing information (creds, capabilities, intent) | Pause and ask the user |

### Iteration Limit

- **Maximum 5 correction iterations** per automation.
- If still failing after 5:
  - Agent **stops execution**.
  - Reports the exact blocker with evidence.
  - Requests explicit user guidance.
  - Does **not** mark the deliverable as successful.

---

## 13. False Positives Prevention

The unified agent enforces strict anti-false-positive behavior:

- Never report success without execution proof.
- Never deliver broken automation as functional.
- Always present a clear evidence line: `Tests executed: X, Passed: Y, Failed: Z`.
- Never hide errors in comments or documentation.
- If unable to fix after max iterations, be explicit about the blocker.

If the user explicitly accepts partial delivery with documented `system_bug` items, the agent may complete with status **⚠️ PARTIAL — USER ACKNOWLEDGED**.

---

## 14. Evidence, Artifacts & Reporting

All technologies must generate evidence under `<project-root>/evidences/`.

Typical contents:

- **Web**: screenshots, traces, HTML report (Playwright Report, Allure, etc.)
- **Mobile**: screenshots (PNG), page source (XML), HTML/Allure/ExtentReports
- **API**: request/response captures (JSON), schema validation reports, HTML report

Recommended layout for mobile:

```
<project-root>/evidences/
  test-runs/
    <run-id>/
      screenshot.png
      page_source.xml
      report.html
```

Final report is **always automated** by the generated project — not a manual step.

---

## 15. Cross-Technology Scenarios

When a scenario spans multiple technologies:

1. Identify all technologies involved (e.g., Web UI + API backend).
2. Load **all** required technology skills.
3. Explore each technology separately using its MCP/tooling.
4. Generate integrated test code coordinating across technologies.
5. Execute and validate the complete flow end-to-end.

The same execution-first and false-positive rules apply across all involved layers.

---

## 16. Desktop Reliability

Desktop automation must use post-action verification, resilient ranked localization, and evidence-based failure classification. The authoritative rules and reference implementation are defined in [desktop-automation/SKILL.md](../.github/skills/desktop-automation/SKILL.md).

---

## 17. Session Management & Cleanup

### Timeouts

- **Single exploration step**: max 30 s before requiring user input
- **Complete exploration session**: max 15 min before requiring confirmation
- **Single test execution**: max 5 min before marking as timeout failure
- **Iterative correction attempts**: max 5

### Cleanup Before Ending

- Close browser instances (Web)
- Terminate apps and end Appium sessions (Mobile)
- Close desktop applications started for the run (Desktop)
- Close API connections / clear tokens
- Capture final structure (if system still open)
- Save generated/updated code
- Provide execution instructions
- Summarize findings and recommendations

---

## 18. Troubleshooting

### MCP-Related

- **Tools missing**: Verify the MCP server is configured and started; otherwise STOP and configure.
- **MCP becomes unavailable mid-session**: Stop, notify user, attempt restart, or terminate.

### Web

- **Element not found** → use `browser_snapshot` and prefer `data-testid`/aria/id over text.
- **Timing issues** → replace sleeps with explicit Playwright waits.
- **Tabs/iframes** → track tab indices, switch frame context explicitly, revert after operation.

### Mobile

- **`session_not_created`** → verify Appium URL/port, drivers installed, device/emulator reachable, capabilities (udid/platformVersion/app).
- **Flaky locators** → re-capture page source; prefer `resource-id`/`accessibility id` over XPath.
- **Permission dialogs** → use auto-grant where possible; handle dialogs deterministically.
- **Device disconnects** → retry session, confirm USB debugging, ensure AVD is running.

### API

- **Auth failures** → confirm token/credential source; never hardcode secrets.
- **Schema mismatches** → record actual vs. expected; classify as `system_bug` if applicable.
- **Flaky responses** → add controlled retries with explicit conditions, not sleeps.

### Generic

- **`code_issue`** → let the agent retry within iteration limit.
- **`system_bug`** → fix the application first or accept documented limitation.
- **`user_input_needed`** → provide requested information.

---

## 19. Best Practices

### Before Starting

- Provide clear flow description, URLs/credentials, and target language/framework.
- Ensure the target system (web app, mobile app build, API base URL) is reachable.
- Make sure the correct MCP server is configured.

### During Development

- Review exploration findings (elements, endpoints, challenges).
- Watch execution output and artifacts.
- Intervene only for clarifications or `user_input_needed`.

### After Delivery

- ⚠️ **Human validation is mandatory.** Never blindly trust AI-generated automation.
- Review generated code, assertions, and error handling.
- Integrate into CI/CD; configure reporting and monitoring.
- Keep automation aligned with application changes.

### Patterns That Work Well

- Start with a **smoke test** before a full suite (especially mobile — Gate B before Gate C).
- Prefer the most stable locator strategy per platform.
- Keep secrets in env vars / CI secrets — never commit them.
- For known application defects, label them so the agent classifies failures as `system_bug`.

---

## 20. Quick Reference

| Task | Command Example |
|---|---|
| Web UI automation | `Create automation for [FLOW] at [URL] in [LANGUAGE]` |
| Mobile UI automation | `Automate [FLOW] on the [Android/iOS] app in [LANGUAGE]` |
| API automation | `Create API automation for [ENDPOINT/SPEC] in [LANGUAGE]` |
| Extend existing project | `Add automation for [FLOW] to existing project in [PATH]` |
| From test case | `Automate test case in [FILE]` |
| Bug reproduction | `Automate bug reproduction from [BUG-ID]` |
| Cross-technology | `Automate [WEB/MOBILE FLOW] and validate via [API] in [LANGUAGE]` |
| Specific mobile target | `Run mobile suite using BrowserStack with env vars for credentials` |

| Concern | Rule |
|---|---|
| MCP tools | Mandatory — STOP if unavailable |
| Live exploration | Mandatory for new flows |
| Headed/headless | Headed by default for Web/Mobile |
| Evidence location | `<project-root>/evidences/` |
| Iteration limit | Max 5 correction attempts |
| Default Web stack | Java + Playwright + Cucumber |
| Default Mobile stack | Java + Appium + Cucumber |
| Default Desktop stack | Python + PyAutoGUI + Pytest |
| Default API stack | Java + RestAssured + Cucumber |

---

**End of Unified Automation Agent Manual.**

For detailed technology-specific behavior, refer to the corresponding skill directories under `.github/skills/` (`web-automation-playwright`, `mobile-automation`, `desktop-automation`, `api-automation`, `project-analysis`, `live-exploration-workflow`, `code-generation`, `execution-validation`).
