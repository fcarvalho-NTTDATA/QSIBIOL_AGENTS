# QA Orchestrator — Complete Manual

This manual covers everything you need to use, extend, and maintain the QA Orchestrator: how the VS Code extension works, how each specialist agent behaves, the full MCP prompt template reference, and how to publish new versions.

---

## Table of Contents

- [1. What Is QA Orchestrator](#1-what-is-qa-orchestrator)
- [2. Download, Install, and Setup](#2-download-install-and-setup)
- [3. How the Orchestrator Routes Requests](#3-how-the-orchestrator-routes-requests)
- [4. Specialist Agents](#4-specialist-agents)
  - [4.1 User Story Agent](#41-user-story-agent)
  - [4.2 Test Case Agent](#42-test-case-agent)
  - [4.3 Unified Automation Agent](#43-unified-automation-agent)
  - [4.4 Accessibility Agents](#44-accessibility-agents)
  - [4.5 Test Data Agent](#45-test-data-agent)
  - [4.6 SAP Web Automation Agent](#46-sap-web-automation-agent)
  - [4.7 Test Plan Coverage Agent](#47-test-plan-coverage-agent)
- [5. MCP Prompt Templates](#5-mcp-prompt-templates)
- [6. MCP Servers](#6-mcp-servers)
- [7. Publishing a New VSIX Version](#7-publishing-a-new-vsix-version)
- [8. Troubleshooting](#8-troubleshooting)

---

## 1. What Is QA Orchestrator

QA Orchestrator is a VS Code extension that installs AI-powered QA agents and skills directly into your workspace. It integrates with **GitHub Copilot Chat** through a central `qa-orchestrator` agent that:

1. Receives natural-language QA requests from you
2. Identifies the right specialist (automation, accessibility, documentation, test data, data testing, unit test coverage, test plan coverage, SAP)
3. Routes the request and supervises execution
4. Returns results without requiring you to know which agent to call

The extension also configures the MCP (Model Context Protocol) servers each package needs in `.vscode/mcp.json`, giving agents direct access to a browser, a mobile device, databases, and local file-conversion tools (see [6. MCP Servers](#6-mcp-servers)).

---

## 2. Download, Install, and Setup

### Download

Get the latest `.vsix` from the release page:

**[GitLab Releases](https://umane.emeal.nttdata.com/git/QSAGIQSAGENTICINNOVA/qsagentic/-/releases)**

### Install the extension

1. Open VS Code → **Extensions** (`Ctrl+Shift+X`)
2. Click `···` → **Install from VSIX...**
3. Select the downloaded `.vsix` file

### Setup your workspace (once per project)

1. Open your project folder in VS Code
2. Press `Ctrl+Shift+P` → **QA Orchestrator: Setup Workspace**
3. Choose a package:

| Package | Agents installed | Skills installed | Manual |
|---|---|---|---|
| **All** *(recommended)* | All specialists + orchestrator | All available skills | All |
| **Automation** | Automation + orchestrator | 8 automation skills | Automation |
| **Test Data** | Test Data + orchestrator | 5 test data skills | — |
| **Data Testing** | Data Testing, Test Data + orchestrator | 17 skills: 10 data-testing, `generate-test-plan`, `json-to-markdown` and 5 test data skills | Data Testing |
| **Unit Test Coverage** | Unit Test Coverage + orchestrator | 5 unit-test coverage skills | Unit Test Coverage |
| **Test Plan Coverage** | Test Plan Coverage + orchestrator | 5 plan coverage skills | Test Plan Coverage |
| **Documentation** | User Story, Test Case (incl. test plans), Test Plan Coverage + orchestrator | 6 doc skills + 5 plan coverage skills | Documentation, Test Plan Coverage |
| **Accessibility** | 13 accessibility agents + orchestrator | 4 a11y skills | Accessibility |
| **SAP Web Automation** | SAP Web Agent + orchestrator | 3 SAP skills | — |

Every package also installs this manual (`QA_ORCHESTRATOR_MANUAL.md`). The same packages can be installed from the command line with `qa_mcp_servers.exe install <all|automation|testdata|datatesting|doc|accessibility|sap|unittestcoverage|testplancoverage>`; `qa_mcp_servers.exe --help` lists the exact contents of each package.

Setup copies into the workspace:

```
.github/agents/           ← agent definition files
.github/skills/           ← supporting skill modules
.github/copilot-instructions.md
manuals/                  ← reference documentation
mcp_servers/qa_mcp_servers.exe
.vscode/mcp.json          ← MCP server configuration
dbhub.toml.example        ← only for packages that use DBHub (All, Data Testing)
```

Installs are **additive**: you can run Setup Workspace again with another package and everything installed before is kept — nothing is deleted. Files that already exist in the workspace (agents, skills, manuals, `copilot-instructions.md`, `AGENTS.md`, `dbhub.toml.example`) are **never overwritten**, because they may be shared between packages or customised by you; only missing files are added. The `qa_mcp_servers.exe` binary itself is still updated. `.vscode/mcp.json` is merged, not replaced — see [6. MCP Servers](#6-mcp-servers).

### Start using

1. Open **GitHub Copilot Chat** (`Ctrl+Alt+I`)
2. Click the agent selector → choose **qa-orchestrator**
3. Describe your task in plain language

---

## 3. How the Orchestrator Routes Requests

The `qa-orchestrator` agent acts as a dispatcher. When it receives a request, it classifies it into one or more task codes and delegates each one to the matching specialist:

| Code | Request pattern | Routed to |
|---|---|---|
| T1 | "accessibility", "WCAG", "audit", "a11y" | Accessibility Agent (`accessibility-agent`) |
| T2 | "playwright", "web automation", "web test", "browser" | Automation Agent — Web (`automation-agent-unified`) |
| T3 | "mobile", "appium", "android", "iOS", "app test" | Automation Agent — Mobile (`automation-agent-unified`) |
| T4 | "API", "REST", "GraphQL", "endpoint", "swagger", "OpenAPI" | Automation Agent — API (`automation-agent-unified`) |
| T5 | "test case", "acceptance criteria", "test plan", "generate plan" | Test Case Agent (`test-case-agent`) |
| T6 | "INVEST", "evaluate user story", "story quality" | User Story Agent (`user-story-agent`) |
| T9 | "sap", "fiori", "sapui5", "s/4hana", "odata", "webgui" | SAP Web Automation Agent (`sap-web-agent`) |
| T10 | "test data", "synthetic data", "generate data", "populate database", "seed data", "bulk data", "ddl", "script" | Test Data Agent (`test-data-generation-agent`) |
| T11 | "data testing", "database validation", "ETL validation", "source to target", "reconciliation", "data quality", "schema validation" | Data Testing Agent (`data-testing-agent`) |
| T12 | "unit test", "coverage", "code coverage", "coverage gap", "jacoco", "junit", "raise coverage" | Unit Test Coverage Agent (`unit-test-coverage-agent`) |
| T13 | "test plan coverage", "test cases vs code", "plan vs plan", "manual test coverage", "regression suite gaps", "obsolete test cases", "semantic dictionary" | Test Plan Coverage Agent (`test-plan-coverage-agent`) |

Routing rules:

- SAP targets (SAP, Fiori, SAPUI5, S/4HANA, SAP GUI Web) always go to T9, never to T2.
- Test plans and test cases are one T5 delegation to `test-case-agent`, with `deliverables` set to `test_plan`, `test_cases`, or both.
- "Coverage" is routed by what is covered: code by unit tests → T12; one test plan source by another (test cases vs. code, suite vs. suite) → T13; acceptance criteria by test cases → part of T5.
- A request can contain several task codes (e.g. "evaluate this story, then generate the test plan and test cases" → T6, then T5). Common orders: T6 → T5, T5 → T10, T10 → automation task, T13 → T5 (generate cases for coverage gaps).

The routing rules live in `.github/agents/qa-orchestrator.agent.md` and can be customized per workspace.

---

## 4. Specialist Agents

### 4.1 User Story Agent

**Purpose**: Evaluate and iteratively improve user stories using INVEST criteria.

#### INVEST criteria

- **Independent** — story can be developed without depending on others
- **Negotiable** — details can be discussed and adjusted
- **Valuable** — provides clear value to users/stakeholders
- **Estimable** — team can estimate effort required
- **Small** — can be completed within one iteration
- **Testable** — clear criteria for testing completion

#### How to use

```
Evaluate the user story US-123
Evaluate the user story in file user_stories/US-101.md
Improve user story US-123
Improve user story US-123 with target score 9.0 and max 3 iterations
Add acceptance criteria for error handling to user story US-123
```

#### Workflow

1. Loads story and previous evaluation (if any)
2. Evaluates it with the `user-story-invest-evaluator` skill — never scores ad hoc
3. Scores each INVEST dimension (1–10)
4. Applies improvements targeting the lowest-scoring areas
5. Iterates up to 5 times (default) or stops earlier when the average score is > 8.0 or no further improvement is detected
6. Saves evaluation as JSON and generates Markdown via the `json-to-markdown` skill

#### Output structure

```
user_stories/evaluations/US-123/
  US-123-evaluation.json
  US-123-evaluation.md
  US-123-evaluation-iteration-1.json
  US-123-evaluation-iteration-2.json
```

#### Quality thresholds (customizable)

| Score | Meaning |
|---|---|
| < 5 | Critical — immediate action required |
| 5–7 | Needs improvement |
| 7–8 | Good quality |
| > 8 | Excellent (default stopping threshold) |

#### Rules

- Never evaluates ad hoc — always follows the `user-story-invest-evaluator` skill
- Never skips Markdown generation for final evaluation
- Always tracks iterations with numbered files
- Stopping criteria can be customized per request

---

### 4.2 Test Case Agent

**Purpose**: Generate complete test cases with 100% acceptance criteria coverage and full traceability from requirements to tests. The Test Case Agent also owns test plan generation (via the `generate-test-plan` and `json-to-markdown` skills) — there is no separate test plan agent.

#### How to use

```
Generate test cases for user story US-002
Extract acceptance criteria for user story US-123
Create a test plan for user stories US-101, US-102, US-103
Convert test_cases/US-123/test_cases.json to markdown
```

#### Workflow

PDF and Word user stories are first converted to Markdown with the `convert_pdf_md_tool` / `convert_word_md_tool` MCP tools.

**Step 1 — Extract acceptance criteria** (minimum 3 revision passes):
- Pass A: initial extraction (explicit + implicit criteria)
- Pass B: refine, split, deduplicate
- Pass C: validate completeness
- Pass D: final sanity check (testability, atomicity)

**Step 2 — Generate or reuse test plan** (`generate-test-plan` skill):
- When the plan is a prerequisite for test cases, reuses a valid plan in `/test_plan/` that covers the stories, or creates one automatically if missing
- An explicit test plan request always generates a new plan (up to 10 user stories per plan)

**Step 3 — Generate test cases**:
- For each AC: happy path, negative cases, boundary values, roles/permissions, persistence, error handling, integration
- Verifies 100% coverage before finishing

**Step 4 — Convert to Markdown**:
- Uses the `json-to-markdown` skill

#### Output structure

```
test_cases/US-002/
  acceptance_criteria.json
  acceptance_criteria.md
  test_cases.json
  test_cases.md

test_plan/
  test_plan_YYYYMMDD_HHMMSS.json   ← or the output name you request
  test_plan_YYYYMMDD_HHMMSS.md
```

#### Coverage requirement

The agent verifies and reports:

```json
{
  "total_acceptance_criteria": 15,
  "covered_acceptance_criteria": 15,
  "uncovered_acceptance_criteria": []
}
```

No uncovered AC is allowed before delivery.

#### Rules

- Never invents requirements — all values and ranges must come from source docs
- 100% coverage required
- Evidence traceability required for all test cases
- Requests missing data instead of guessing

---

### 4.3 Unified Automation Agent

**Purpose**: Automate Web, Mobile, Desktop, and API flows using live exploration — no assumptions, no untested code.

#### How to use

```
Create automation for the login flow at https://example.com in Java with Playwright
Automate the onboarding flow of the Android app
Create API automation for the CRUD operations on /api/users in Python
Add automation for the user profile update flow to the existing project in /automation/web-tests
Automate the checkout flow on the web and validate the order via the backend API in TypeScript
Re-run the failing mobile tests, capture screenshots, and fix any code issues
```

#### Technology detection

| Keywords | Technology |
|---|---|
| web, browser, URL, website, Playwright | Web (`playwright` MCP server) |
| mobile, app, Android, iOS, device, emulator, Appium | Mobile (`mobile-mcp`) |
| desktop, Windows application, native app, GUI automation | Desktop (`desktop-automation` MCP) |
| API, endpoint, REST, GraphQL, OpenAPI, Postman | API |

Mixed scenarios supported — multiple technology skills can be active simultaneously.

#### Execution phases

**Phase 0 — MCP verification**: Confirms required MCP servers are available. Stops if not configured.

**Phase 1 — Project analysis**: Detects language, build system, test framework, existing coverage. Decides between running existing tests or exploring new flow.

**Phase 2A — Execute existing tests** (when the requested tests already exist).

**Phase 2B — Live exploration** (for new flows):
- Web: opens browser in headed mode, captures snapshots, identifies stable locators
- Mobile: launches app on device/emulator, captures page source and screenshots
- API: discovers endpoints from OpenAPI/Postman or live calls

**Phase 3 — Code generation**: Generates code using only validated exploration data.

**Phase 4 — Execution & validation loop**: Executes, classifies failures, fixes, re-executes (max 5 iterations).

**Phase 5 — Delivery**: Final report with status, evidence links, execution summary.

#### Failure classification

| Category | Description | Action |
|---|---|---|
| `code_issue` | Bug in the generated automation | Fix automatically and re-execute |
| `system_bug` | Bug in the application under test | Document and notify user |
| `user_input_needed` | Missing information | Pause and ask user |

#### Technology defaults (if not specified)

| Technology | Default stack |
|---|---|
| Web | Java + Playwright + Cucumber |
| Mobile | Java + Appium + Cucumber |
| Desktop | Python + PyAutoGUI + Pytest |
| API | Java + RestAssured + Cucumber |

Any language/framework explicitly requested by the user is honored.

> The `desktop-automation` MCP server used for desktop exploration is not configured by Setup Workspace; add it to `.vscode/mcp.json` yourself when you need desktop automation.

#### Non-negotiable rules

1. MCP tools are mandatory — no work begins without them
2. Live exploration required for new or unknown flows
3. No theoretical locators or endpoints — only validated from live analysis
4. No untested deliveries
5. Headed by default for Web and Mobile
6. Evidence under `<project-root>/evidences/`

---

### 4.4 Accessibility Agents

**Purpose**: Run WCAG accessibility audits on live web pages using Playwright MCP and produce stable, traceable artifacts.

#### Agents available

| Agent | What it audits |
|---|---|
| **Accessibility Agent** (`accessibility-agent`) | Full audit orchestration — runs axe-core, the mandatory alt-text validation and the optional validators you select, then produces the dashboard |
| **Alt Text Validator** (`alt-text-validator`) | Image alternative text quality and correctness |
| **Animated Content Safety Validator** (`animated-content-safety-validator`) | Time limits, moving/auto-updating content, flashes (WCAG 2.2.x, 2.3.x) |
| **Consistency and Errors Validator** (`consistency-and-errors-validator`) | Repeated UI patterns, form errors, input assistance, redundant entry, authentication safeguards |
| **Document Structure Inspector** (`document-structure-inspector`) | Page title, heading hierarchy, lists, tables, landmarks, target spacing |
| **Image Text Contrast Validator** (`image-text-contrast-validator`) | Contrast of text rendered inside images |
| **Input Purpose and Autocomplete Validator** (`input-purpose-and-autocomplete-validator`) | Input purpose, autocomplete semantics, field instructions |
| **Language Validation Agent** (`language-validation-agent`) | Page and content language declarations |
| **Media Accessibility Validator** (`media-accessibility-validator`) | Transcripts, captions, audio description, autoplay audio |
| **Navigation Predictability Validator** (`navigation-predictability-validator`) | Bypass blocks, link purpose, multiple ways, predictable context changes |
| **Pointer Interaction Validator** (`pointer-interaction-validator`) | Hover/focus content, gestures, pointer cancellation, motion actuation, dragging |
| **Tab Navigation Validator** (`tab-navigation-validator`) | Keyboard navigation, focus visibility, traps |
| **Visual Resilience Validator** (`visual-resilience-validator`) | Use of color, contrast, resize, reflow, text spacing (WCAG 1.4.12), focus visibility |

#### How to use

```
Run accessibility audit for https://example.com
Audit accessibility for https://example.com and generate remediation suggestions
Validate the page language for https://example.com
Validate tab navigation for https://example.com
Audit visual resilience (including text spacing) for https://example.com
Audit media accessibility for https://example.com
```

**Use the Accessibility Agent** (orchestrator) for full audits with consolidated output.  
**Use a specialized validator** when the problem is already known and you need focused evidence.

#### Workflow

1. Renders the page in a real browser via Playwright MCP
2. Runs axe-core rule-based validation
3. Runs the alt-text validator (mandatory when images are present), then asks you once which of the relevant optional validators to run; unselected ones are recorded as `skipped-by-user`
4. Proposes minimal remediation patches
5. Revalidates when safe
6. Writes artifacts to `artifacts/a11y/<target-slug>/`
7. Generates the dashboard with the `generate_a11y_dashboard_tool` MCP tool once all selected validators finish

#### Output structure

```
artifacts/a11y/<target-slug>/
  axe-before.json / axe-after.json
  semantic-before.json / semantic-after.json
  report-before.json / report-after.json
  dom-desktop.html / dom-mobile.html
  accessibility-desktop.md / accessibility-mobile.md
  desktop.png / mobile.png
  changelog.md
  limitations.md
  suggested-patch.diff
  uncovered_criteria.md
  dashboard.html
  alt-text-review.json
  report-<validator>.md + <validator>-review.json   ← one pair per validator executed
                                                     (e.g. report-visual-resilience.md)
```

#### Shared accessibility skills

- **a11y-audit-foundation** — canonical output paths, target URL resolution, safe interaction rules
- **a11y-playwright-interactions** — live keyboard navigation, focus management and widget interactions
- **a11y-report-normalization** — canonical report filenames, Markdown integrity, stable JSON/Markdown outputs
- **a11y-structural-heuristics** — visible main-text extraction, heading/list/table heuristics

---

### 4.5 Test Data Agent

**Purpose**: Generate realistic, domain-aware synthetic test data that respects business constraints, schema definitions, and security payload patterns. For high-volumetry scenarios (1,000+ rows per table), the agent generates an **executable population script** instead of inline data rows.

#### Skills used

- `bulk-data-script-generator` — generates SQL/Python population scripts for 1,000+ row scenarios
- `domain-constraints` — business rule constraints per domain
- `schema-parser` — infers constraints from JSON Schema, SQL, OpenAPI
- `security-test-payloads` — injects known attack patterns for security testing
- `test-data-factories` — generates coherent datasets from specs

#### How to use — standard (< 1,000 rows)

```
Generate test data for a user registration form
Create a dataset with 100 users following this JSON schema: [schema]
Generate security test payloads for the login endpoint
Generate 50 orders with referential integrity to the users table
Generate test data based on the schema in schemas/products.sql
```

#### How to use — high-volumetry (>= 1,000 rows per table)

When the volume is >= 1,000 rows per table, the agent generates a **DDL-based population script** that you run directly on your database. No data rows are produced — only executable code.

```
Generate a population script for 1 million rows in the orders table. DDL: [paste DDL]
I need to populate a SQL Server test database with 10M rows. Here is the DDL: [paste DDL]
Generate a bulk data script for PostgreSQL using the DDL in schemas/create_tables.sql
Generate a Python bulk-insert script for 500,000 rows using schemas/users.sql
```

The agent will:
1. Parse the DDL to extract tables, columns, types, constraints, and foreign keys
2. Determine the correct table generation order (parents before children)
3. Generate a self-contained script with a configurable header (`row_count`, `batch_size`)
4. Include a cleanup block to delete generated test data
5. Save the output to `test_data/<domain>_bulk_<timestamp>/` with a `README.md`

SQL validation is **opt-in**: only when you ask for it (e.g. "validate the script", "run SQLFluff"), the agent validates the script with `validate_generated_sql_tool` (up to 3 fix attempts, otherwise `FAILED_VALIDATION`) and then saves it with `validate_and_save_generated_sql_tool`, which also writes `validation-report.json`.

#### High-volumetry output

```
test_data/orders_bulk_2026-07-27T10-00-00Z/
  populate_test_data.sql  ← run this against your database
  README.md               ← engine, row count, how to run, cleanup instructions
  validation-report.json  ← only when validation was requested
```

#### Supported database engines (population scripts)

| Engine | Script type |
|--------|------------|
| SQL Server / Azure SQL | T-SQL batch with `WHILE` loop + seeded `CHECKSUM`-based expressions |
| PostgreSQL | PL/pgSQL function with `generate_series` |
| MySQL / MariaDB | Stored procedure with `WHILE` loop |
| Any (Python output) | Faker + psycopg2 / pyodbc / pymysql bulk-insert |

---

### 4.6 SAP Web Automation Agent

**Purpose**: Automate SAP Web applications (SAP Fiori Launchpad, SAP GUI Web, S/4HANA) using SAPUI5-specific patterns with OData backend validation.

> **When to use this agent vs. the Unified Automation Agent:**
> - Target system is SAP Fiori, SAP GUI Web, S/4HANA, or any SAPUI5 application → **always use `sap-web-agent`**
> - Target system is a generic web application (no SAP/SAPUI5) → use `automation-agent-unified`
> - The Unified Automation Agent is **not aware** of SAPUI5 rendering lifecycle, Shadow DOM depth, dynamic ID patterns, SSO authentication flows, or native SAP controls.

#### How to use

```
Automate the purchase order creation flow in SAP Fiori at https://mycompany.com/fiori
Explore the SAP Fiori Launchpad at https://mycompany.com/fiori
Automate the vendor invoice posting flow in SAP Fiori with OData validation
Debug failing SAP tests in project automation/sap-purchase-order
```

#### Supported SAP application types

| Type | URL Pattern | Indicators |
|---|---|---|
| **Fiori Launchpad** | `/sap/bc/ui5_ui5/ui2/ushell/` | Tile grid, shell header with SAP logo |
| **SAP GUI Web** | `/sap/bc/gui/sap/its/webgui` | iFrames with classic SAP transaction layout |
| **S/4HANA Cloud** | `/ui/` or `*.hana.ondemand.com` | Modern Fiori design, Fiori Elements |
| **Standalone SAPUI5** | `/sap/bc/ui5_ui5/` | Single-page SAPUI5 app, Component.js in source |

#### SAP-specific MCP tools

These 6 tools extend the standard `playwright/*` browser tools with SAPUI5-specific capabilities:

| Tool | When to Use |
|---|---|
| `sap_wait_ready_tool` | After every SAP page navigation or tile click — before any interaction |
| `sap_extract_tiles_tool` | After navigating to the Fiori Launchpad — to discover available apps |
| `sap_get_control_tool` | During exploration — to introspect a SAPUI5 control's type, state and binding |
| `sap_handle_value_help_tool` | Whenever an SAP input field requires F4 value selection |
| `sap_capture_errors_tool` | After every Save, Create, Post or Approve action |
| `sap_intercept_odata_tool` | Call **before** the UI action that triggers the OData call |

#### SAPUI5 locator priority

Never use dynamic SAP IDs (`#__xmlview0--button`, `#__field123`) — they change with every SAP release.

| Priority | Selector type | Example |
|---|---|---|
| 1 — most stable | Stable ID suffix | `[id$="--saveButton"]` |
| 1 | Aria label | `[aria-label="Save"]` |
| 1 | Data attribute | `[data-sap-ui]` |
| 2 | SAP class + title | `.sapMBtn[title="Save"]` |
| 3 | Structural | `.sapMBarRight .sapMBtn:first-child` |
| 4 — avoid | Visible text | `text="Save"` |

#### Workflow phases

```
Phase 0 — Verify playwright/* + sap_* tools are available
Phase 1 — Navigate to SAP URL → sap_wait_ready_tool → identify app type
Phase 2 — Authentication (Form Login / SSO / already authenticated)
           → save storageState to sap-session.json
Phase 3 — Live exploration: sap_wait_ready_tool → browser_snapshot → interact
           → sap_capture_errors_tool after critical actions
           → sap_intercept_odata_tool for create/update/delete/search operations
Phase 4 — Code generation (TypeScript by default)
Phase 5 — Execution & validation (max 5 iterations)
Phase 6 — Delivery: report + evidence under <project>/evidences/
```

#### SAP authentication methods

| Method | Auto-detected | Notes |
|---|---|---|
| SAP Form Login | ✅ Yes | `sap-user` / `sap-password` fields |
| SSO / SAML 2.0 | ✅ Yes | Redirect to Azure AD, Okta, SAP IAS |
| Already authenticated | ✅ Yes | Tiles visible, no login form |
| SAP Logon Ticket | Manual | `MYSAPSSO2` cookie configuration |

**Session persistence:** After first login, `storageState` is saved to `sap-session.json`. Subsequent runs reuse this file.

**Credentials:** Always use environment variables — never hardcode:
```bash
SAP_URL="https://mycompany.com/fiori"
SAP_USERNAME="my_user"
SAP_PASSWORD="my_password"
```

#### Error handling

| Error type | Action |
|---|---|
| `code_issue` (wrong locator, timing) | Fix automatically, re-execute (max 5 iterations) |
| `system_bug` (OData 500, business rule violation) | Document SAP error, notify user |
| `user_input_needed` (system unreachable, credentials missing, MCP tools unavailable) | Pause and request user input |
| `sap_session_expired` (redirect to login) | Re-authenticate using `sap-auth-session` skill |
| `sapui5_not_initialized` | Increase timeout, verify it is a SAP application |

#### Installation

```bash
python qa_mcp_servers.py install sap
```

Installs: the orchestrator, `sap-web-agent.agent.md`, SAP skills (`sap-ui5-locator-strategy`, `sap-auth-session`, `sap-odata-validator`), this manual, and the `qa_mcp_server` and `playwright` MCP servers.

The SAP agent also uses the `project-analysis`, `live-exploration-workflow`, `code-generation` and `execution-validation` skills, which are not part of the `sap` package; install the **Automation** (or **All**) package as well to get them.

### 4.7 Test Plan Coverage Agent

**Agent:** `test-plan-coverage-agent` · **Task code:** T13 · **Manual:** `TEST_PLAN_COVERAGE_AGENT_MANUAL.md`

Measures how well one test plan source covers another — e.g. what the code does vs. what an existing test suite tests (spreadsheet, Word, PDF, Markdown, or tool export), or one suite vs. another — and classifies every case as `Total`, `Partial`, or `No coverage` with its supporting evidence. It builds the inputs it needs (semantic dictionary, code-first inventory, test case inventory) and runs a deterministic Python analyzer that produces an HTML or Markdown report by domain and journey.

```
Measure the coverage of the test cases in docs/regression.docx against the code in src/app, code covered by test cases, by journey.
```

#### Installation

```bash
python qa_mcp_servers.py install testplancoverage
```

Installs: the orchestrator, `test-plan-coverage-agent.agent.md`, the `plan-coverage-*` skills, this manual, the Test Plan Coverage manual, and the `qa_mcp_server` MCP server. Also included in the `doc` package. Requires Python 3 in the workspace to run the bundled scripts.

---

## 5. MCP Prompt Templates

Prompt templates let you invoke full agent workflows with a single structured command. In MCP-compatible clients (e.g., Claude Desktop), open the prompt picker and select a template. You can also invoke them programmatically:

```json
{
  "method": "prompts/get",
  "params": {
    "name": "accessibility_full_audit",
    "arguments": { "url": "https://example.com" }
  }
}
```

---

### Accessibility prompts

| Prompt | Required args | Description |
|---|---|---|
| `accessibility_full_audit` | `url` | Full end-to-end accessibility audit |
| `accessibility_alt_text` | `url` | Validate alt text for all images |
| `accessibility_document_structure` | `url` | Validate heading hierarchy and document structure |
| `accessibility_tab_navigation` | `url` | Validate keyboard / tab navigation |
| `accessibility_language` | `url` | Validate page language declaration |
| `accessibility_media` | `url` | Audit audio/video accessibility |
| `accessibility_text_spacing` | `url` | WCAG 1.4.12 text-spacing resilience check |
| `accessibility_image_contrast` | `url` | Contrast for text rendered inside images |
| `accessibility_consistency_errors` | `url` | Consistency of repeated UI patterns and form errors |
| `accessibility_dashboard` | *(none)* | Generate dashboard from existing audit artifacts. Optional: `artifacts_folder` |

**Examples:**
```
accessibility_full_audit  url="https://myapp.com"
accessibility_dashboard  artifacts_folder="artifacts/a11y"
```

---

### User Story prompts

| Prompt | Required args | Optional args | Description |
|---|---|---|---|
| `user_story_evaluate` | `user_story` | — | Evaluate a user story using INVEST criteria |
| `user_story_improve` | `user_story` | `minimum_score` (8.0), `max_attempts` (5) | Iteratively improve until quality threshold is met |
| `user_story_improve_specific` | `user_story`, `what_to_improve` | — | Apply a specific improvement |

**Examples:**
```
user_story_evaluate  user_story="user_stories/US-001.md"
user_story_improve  user_story="user_stories/US-001.md"  minimum_score=9.0  max_attempts=3
user_story_improve_specific  user_story="user_stories/US-001.md"  what_to_improve="edge cases for empty cart"
```

---

### Test case / plan prompts

| Prompt | Required args | Description |
|---|---|---|
| `test_case_generate` | `user_story` | Generate test cases with 100% AC coverage |
| `test_case_extract_ac` | `user_story` | Extract and validate acceptance criteria |
| `test_plan_generate` | `user_stories` | Generate a test plan (comma-separated paths) |

**Examples:**
```
test_case_generate  user_story="user_stories/US-002.md"
test_plan_generate  user_stories="user_stories/US-101.md, user_stories/US-102.md"
```

---

### Test data prompts

| Prompt | Required args | Optional args (default) | Description |
|---|---|---|---|
| `test_data_generate` | `domain`, `entities` | `volume` (10), `format` (JSON), `scenarios` (valid, invalid, edge) | Generate synthetic test data for a domain (volume >= 1,000 switches to bulk script mode) |
| `test_data_from_schema` | `schema_source` | `volume` (20), `format` (JSON), `business_rules` | Generate data from a DDL / OpenAPI / JSON Schema (file, folder, attachment or pasted content) |
| `test_data_bulk_script` | `ddl_source`, `row_count` | `db_engine` (SQL Server), `engine_version` (2016+), `output_format` (SQL), `generation_mode` (rerunnable), `validate` (false) | **High-volumetry**: generate a DB population script for 1,000+ rows |
| `test_data_single_table_no_validation` | `ddl_source`, `row_count` | `db_engine` (SQL Server), `engine_version` (2016+), `generation_mode` (rerunnable), `business_rules` | Population script for one table, without SQL validation |
| `test_data_single_table_with_validation` | `ddl_source`, `row_count` | `db_engine` (SQL Server), `engine_version` (2016+), `generation_mode` (rerunnable), `business_rules` | Population script for one table, validated and saved |
| `test_data_independent_tables_with_validation` | `ddl_source`, `row_count_per_table` | `engine_version` (2016+), `business_rules` | Validated SQL Server script for independent tables |
| `test_data_related_tables_with_foreign_keys` | `ddl_source`, `parent_row_count`, `child_row_count` | `db_engine` (SQL Server), `engine_version` (2016+), `generation_mode` (rerunnable), `business_rules` | Validated script for parent-child tables |
| `test_data_existing_parent_new_child` | `ddl_source`, `parent_table`, `child_table`, `child_row_count` | `db_engine` (SQL Server), `engine_version` (2016+), `business_rules` | Populate a child table using keys of an existing parent table |
| `test_data_reproducible_script` | `ddl_source`, `row_count_per_table` | `db_engine` (SQL Server), `engine_version` (2016+), `seed` (42), `reference_date` (2026-07-29), `deterministic_run_id` (SEED-42), `business_rules` | Deterministic, reproducible population script |
| `test_data_postgresql_with_validation` | `ddl_source`, `row_count_per_table` | `postgresql_version` (15), `generation_mode` (rerunnable), `business_rules` | Validated PostgreSQL population script |
| `test_data_mysql_with_validation` | `ddl_source`, `row_count_per_table` | `mysql_or_mariadb` (MySQL), `engine_version` (8.0), `generation_mode` (rerunnable), `business_rules` | Validated MySQL / MariaDB population script |
| `test_data_validate_existing_script` | `ddl_source`, `sql_script_source` | `db_engine` (SQL Server), `engine_version` (2016+), `max_attempts` (3) | Validate and minimally correct an existing population script |
| `test_data_sqlserver_insurance_reference_case` | `ddl_source` | `row_count_per_table` (2000), `engine_version` (2016+) | Reference insurance notification population scenario |
| `test_data_security_payloads` | `target_fields` | `attack_types` (SQL injection, XSS, command injection) | Generate security test payloads for authorized testing |

**Examples:**
```
test_data_generate  domain="e-commerce"  entities="users, orders, products"  volume=50
test_data_from_schema  schema_source="schemas/create_tables.sql"  volume=30
test_data_bulk_script  ddl_source="schemas/create_tables.sql"  row_count=1000000  db_engine="SQL Server"
test_data_bulk_script  ddl_source="schemas/users.sql"  row_count=500000  db_engine="PostgreSQL"  output_format="Python"
test_data_security_payloads  target_fields="username, search_query"  attack_types="SQL injection, XSS"
```

---

### Automation prompts

| Prompt | Required args | Optional args | Description |
|---|---|---|---|
| `automation_web` | `what_to_automate`, `url` | `language` (Java), `framework` (Playwright + Cucumber) | Web automation with Playwright |
| `automation_mobile` | `what_to_automate` | `platform` (Android), `language` (Java), `framework` (Appium + Cucumber) | Mobile automation with Appium |
| `automation_api` | `what_to_automate`, `api_url` | `language` (Java), `framework` (RestAssured + Cucumber), `api_spec` | REST/GraphQL API automation |
| `automation_extend_existing` | `project`, `what_to_automate` | — | Add new scenarios to an existing project |
| `automation_debug_replay` | `project` | `test_name` | Debug and fix failing tests |
| `automation_cross_technology` | `ui_flow`, `api_validation`, `url`, `api_url` | `language` (TypeScript) | End-to-end scenario spanning UI + API |

**Examples:**
```
automation_web  what_to_automate="login flow"  url="https://myapp.com"  language="TypeScript"
automation_mobile  what_to_automate="onboarding flow"  platform="Android"
automation_api  what_to_automate="CRUD on /api/users"  api_url="https://api.myapp.com"  api_spec="specs/openapi.yaml"
automation_debug_replay  project="automacao_teste/demoblaze-login"
automation_cross_technology  ui_flow="checkout flow"  api_validation="validate order via /api/orders"  url="https://shop.com"  api_url="https://api.shop.com"
```

---

### SAP prompts

| Prompt | Required args | Optional args (default) | Description |
|---|---|---|---|
| `sap_automate_flow` | `what_to_automate`, `sap_url` | `language` (TypeScript), `framework` (Playwright) | Automate a SAP Fiori / Web flow with SAPUI5-specific patterns |
| `sap_explore_launchpad` | `sap_url` | — | Explore and map the apps and tiles of the Fiori Launchpad |
| `sap_validate_odata` | `sap_url`, `ui_flow`, `odata_endpoint` | — | Automate a SAP UI flow and validate its OData calls in parallel |
| `sap_debug_replay` | `project` | `test_name` | Debug and fix failing SAP automation tests |

**Examples:**
```
sap_automate_flow  what_to_automate="purchase order creation"  sap_url="https://mycompany.com/fiori"
sap_explore_launchpad  sap_url="https://mycompany.com/fiori"
sap_validate_odata  sap_url="https://mycompany.com/fiori"  ui_flow="create purchase order"  odata_endpoint="/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV"
```

---

## 6. MCP Servers

Setup adds to `.vscode/mcp.json` only the MCP servers the chosen package needs:

| Server | Description |
|---|---|
| `qa_mcp_server` | Local executable — PDF/Word conversion, accessibility dashboard generation, SAP support, and SQL validation |
| `playwright` | Browser automation via `@playwright/mcp` — used by Automation, Accessibility and SAP agents |
| `mobile-mcp` | Mobile device automation via `@mobilenext/mobile-mcp` — used by the Automation agent (mobile flows) |
| `dbhub` | Read-only database discovery and SQL execution via `@bytebase/dbhub` — used by the Data Testing agent |

| Package | MCP servers added |
|---|---|
| **All** | `qa_mcp_server`, `playwright`, `mobile-mcp`, `dbhub` |
| **Automation** | `qa_mcp_server`, `playwright`, `mobile-mcp` |
| **Test Data** | `qa_mcp_server` |
| **Data Testing** | `qa_mcp_server`, `dbhub` |
| **Documentation** | `qa_mcp_server` |
| **Accessibility** | `qa_mcp_server`, `playwright` |
| **SAP** | `qa_mcp_server`, `playwright` |
| **Unit Test Coverage** | `qa_mcp_server` |
| **Test Plan Coverage** | `qa_mcp_server` |

The servers are **merged** into the existing file: missing servers are added, existing server entries are left untouched, and any other servers or keys are preserved. If `.vscode/mcp.json` can't be parsed, it is not modified and a warning is shown. **QA Orchestrator: Configure MCP Executable Path** only replaces the `qa_mcp_server` entry.

### MCP tools provided by `qa_mcp_server`

| Tool | Description |
|---|---|
| `convert_pdf_md_tool` | Converts a PDF file to Markdown with AI-powered image analysis |
| `convert_word_md_tool` | Converts a Word (.docx) file to Markdown |
| `generate_a11y_dashboard_tool` | Generates a consolidated HTML dashboard from accessibility audit artifacts |
| `sap_wait_ready_tool` / `sap_get_control_tool` / `sap_extract_tiles_tool` / `sap_handle_value_help_tool` / `sap_capture_errors_tool` / `sap_intercept_odata_tool` | SAPUI5 helpers used by the SAP Web Automation agent (see [4.6](#46-sap-web-automation-agent)) |
| `validate_generated_sql_tool` | Validates generated SQL without writing files. Parameters: `sql`, `dialect` (`tsql` default, `postgres`, `mysql`, `ansi`), `ddl`, `engine_version`, `compatibility_level`, `generation_mode` (`rerunnable` / `reproducible`), `transaction_mode` (`atomic` default / `incremental`) |
| `validate_and_save_generated_sql_tool` | Validates and saves generated SQL plus `validation-report.json` under `test_data/<artifact_name>/`. Also accepts `transaction_mode`, `block_on_schema_inconclusive` (default `false`: an inconclusive schema check is only a warning unless `true`) and `expected_sql_sha256` (save refused with `SQL_CHANGED_AFTER_VALIDATION` if the SQL changed after validation) |

> Test plan generation, INVEST evaluation and JSON-to-Markdown conversion are provided by the `generate-test-plan`, `user-story-invest-evaluator` and `json-to-markdown` skills, not by MCP tools.

### Markdown templates

The `json-to-markdown` skill ships with the templates used to convert JSON artifacts to formatted Markdown:

```
.github/skills/json-to-markdown/templates/
  evaluation_template.md   ← user story evaluation reports
  test_case_template.md    ← test case documents
  test_plan_template.md    ← test plan documents
```

---

## 7. Publishing a New VSIX Version

The GitLab CI/CD pipeline builds two kinds of VSIX. The full process is in `RELEASING.md` at the root of the repository.

### How it works

```
merge on main
        │
        ▼
GitLab CI/CD (.gitlab-ci.yml), shell runner tagged vsix-vm
        │
        ├─ Downloads qa_mcp_servers.exe from the package registry → vscode-extension/resources/mcp_servers/
        ├─ Copies .github/agents/, .github/skills/, manuals/, .github/copilot-instructions.md,
        │  AGENTS.md and dbhub.toml.example → vscode-extension/resources/
        │
        ├─ build-latest (automatic): packages the "latest" VSIX for testing
        └─ release-patch / release-minor (manual ▶): packages the next release,
           creates the GitLab Release vX.Y.Z and publishes it to the download portal
```

### Latest builds and releases

- Every merge on `main` that does **not** include `[skip ci]` builds a **latest** VSIX for testing.
- A **release** is either a patch (`1.3.1` → `1.3.2`, fixes and small changes) or a minor (`1.3.2` → `1.4.0`, new agents or features). To publish one:
  1. In your merge request, add a `## X.Y.Z` section with the release notes to `RELEASE_NOTES.md` (required — the job fails without it). The `build-latest` job log shows the next patch and minor numbers.
  2. After the merge, in **Build → Pipelines**, open the latest `main` pipeline and click **▶ release-patch** or **▶ release-minor**.
- For a new major (e.g. `2.0.0`), set `version` in `vscode-extension/package.json` in your merge request; the release uses it when it is higher than the next minor.

### How agents and skills reach the VSIX

The pipeline always copies from the **root of the repo** at build time:

- `.github/agents/` → bundled into VSIX
- `.github/skills/` → bundled into VSIX
- `.github/copilot-instructions.md` → bundled into VSIX
- `manuals/` → bundled into VSIX
- `AGENTS.md` and `dbhub.toml.example` → bundled into VSIX

This means you never need to copy files into `vscode-extension/resources/` manually. Edit agents or skills in the root and push — the next CI run picks them up automatically.

### Adding a new agent

1. Create the agent file in `.github/agents/your-agent.agent.md`
2. Add it to the relevant package in `src/config/constants.py` (`AGENT_GROUPS`) and mirror the change in `vscode-extension/extension.js` (`AGENT_GROUPS`, plus `AXET_SKILL_GROUPS` / `GROUP_MCP_SERVERS` for new skills or packages). The **All** package picks up every agent automatically.
3. Add the agent to the `agents:` list and routing table of `.github/agents/qa-orchestrator.agent.md` so the orchestrator can delegate to it
4. Push to `main` — the CI builds and publishes the new VSIX

### GitLab CI/CD variables (required)

Set these in **GitLab → Settings → CI/CD → Variables**:

| Variable | Value | Type |
|---|---|---|
| `RAILWAY_URL` | `https://qa-release-production.up.railway.app` | Variable |
| `RELEASE_SECRET` | *(shared secret with Railway release server)* | Masked |
| `GITLAB_PUSH_TOKEN` | *(token used to push the version bump commit to `main`)* | Masked |

### Infrastructure components

| Component | Description |
|---|---|
| **qa-runner** (Railway) | GitLab Runner — always running, picks up CI jobs (the job runs in the `node:20-slim` image) |
| **qa-release** (Railway) | FastAPI release server — stores VSIXs and exe on a persistent volume, serves the download page |

---

## 8. Troubleshooting

### Extension / Workspace

**The qa-orchestrator agent doesn't appear in Copilot Chat**
→ Check that `.github/agents/qa-orchestrator.agent.md` exists in your workspace. Run **QA Orchestrator: Setup Workspace** again.

**The MCP server doesn't connect**
→ Verify `mcp_servers/qa_mcp_servers.exe` exists and `.vscode/mcp.json` points to the correct path.  
→ Use **QA Orchestrator: Configure MCP Executable Path** to update the path without re-running setup.

**VS Code version error on install**
→ Update VS Code to 1.95 or later (`Help > Check for Updates`).

**Setup fails with permission error**
→ Ensure the workspace folder is writable. On Windows, try running VS Code as administrator once.

---

### Automation Agent

**MCP tools missing (playwright / mobile)**
→ Verify the MCP server is configured in `.vscode/mcp.json` and the required binary/npm package is installed.

**Web: element not found**
→ Use `browser_snapshot` and prefer `data-testid` / `aria-*` / `id` over text-based locators.

**Mobile: `session_not_created`**
→ Verify Appium URL/port, installed drivers (`appium driver list --installed`), device/emulator reachable, and capabilities (udid, platformVersion, app path).

**Iteration limit reached (max 5)**
→ The agent stops and reports the exact blocker. Check the failure classification — `system_bug` means the application itself has a defect.

---

### Accessibility Agent

**Dashboard not generated**
→ The dashboard is generated only after all validators finish and canonical artifacts are consolidated. Let the full audit complete before requesting the dashboard.

**Partial audit results**
→ Do not treat a partial run as a full pass. If a validator was blocked, re-run it separately.

---

### CI/CD Pipeline

**Job stuck — no runner available**
→ Check that the `qa-runner` Railway service is running. The runner auto-registers on first start using `RUNNER_TOKEN` and `GITLAB_URL` env vars.

**`[skip ci]` not working**
→ Ensure the exact string `[skip ci]` (lowercase, with brackets) is in the commit message.

**VSIX upload fails**
→ Verify `RAILWAY_URL` and `RELEASE_SECRET` CI/CD variables are set correctly in GitLab Settings.

**Agents not updated in new VSIX**
→ Confirm the changes are in `.github/agents/` (repo root), not in `vscode-extension/resources/`. The pipeline always copies from root — files in `vscode-extension/resources/.github/` are not tracked in git.

---

## Quick Reference

| Task | What to type in Copilot |
|---|---|
| Evaluate user story | `Evaluate the user story US-123` |
| Improve user story | `Improve user story US-123` |
| Generate test cases | `Generate test cases for user story US-002` |
| Generate test plan | `Create a test plan for user stories US-101, US-102` |
| Web automation | `Automate the login flow at https://example.com` |
| Mobile automation | `Automate the onboarding flow on the Android app` |
| API automation | `Create API tests for /api/users` |
| Full accessibility audit | `Run accessibility audit for https://example.com` |
| Tab navigation check | `Validate tab navigation for https://example.com` |
| Generate test data (small volume) | `Generate test data for a user registration form` |
| Bulk population script | `Generate a population script for 1 million rows using the DDL in schemas/orders.sql` |
| Test plan coverage | `Compare the test cases in docs/regression.docx with the code in src/app, code covered by test cases` |
