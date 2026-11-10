---
name: web-automation-playwright
description: "Use when automating web applications with Playwright MCP, including browser context, locators, and live exploration."
argument-hint: "Provide the URL, target web flow, and browser or authentication constraints"
---

# Web Automation with Playwright

## Purpose

This skill provides specialized knowledge for web automation using **playwright-mcp** (MCP server for exploration) and **Playwright** (test framework for generated code).

**Key Distinction:**
- **playwright-mcp**: MCP server providing live exploration tools (`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, etc.)
- **Playwright**: Browser automation framework used in generated code (@playwright/test, com.microsoft.playwright, etc.)

This skill covers browser context management, web element identification strategies, Playwright-specific exploration patterns, and web automation best practices.

## When to Use

Activate this skill when:
- User mentions web, browser, URL, website, or web application
- Project contains Playwright dependencies
- Test involves browser-based interactions
- User explicitly requests Playwright automation

## Prerequisites

Before using this skill:
- Project analysis completed (via `project-analysis` skill)
- **playwright-mcp server available and functional** (provides exploration tools)
- Target URL or web application identified

**Execution Default:** Use a visible browser session (`headed`) by default for both live exploration and generated automation projects. Only use `headless` when the user explicitly requests it.

---

## Browser State & Context Management

### Multi-Tab Handling

**Rules:**
- Track all opened tabs with indices
- Always return to the original tab after popup/new tab interactions
- Use `browser_tabs` tool to list, create, close, or select tabs
- Document tab context switches in exploration notes

**Example Scenarios:**
- Popup windows that open in new tabs
- Multi-step flows that span tabs
- External authentication flows (OAuth, SSO)

**Best Practices:**
- Store original tab index before opening new tabs
- Explicitly switch back after completing operations in new tab
- Close temporary tabs to prevent resource leaks

### Frames & iFrames

**Detection:**
- Identify iframe presence through accessibility tree analysis
- Look for `iframe` role in `browser_snapshot` output

**Rules:**
- Switch context explicitly before interacting with iframe elements
- Always switch back to main frame after iframe operations
- Document iframe switches in exploration notes

**Common iframe Scenarios:**
- Embedded payment forms
- Chat widgets
- Third-party content (ads, social media widgets)

### Browser Storage

**What to Capture:**
- localStorage/sessionStorage state when relevant to test flow
- Cookies required for authentication
- IndexedDB data for offline-capable apps

**Rules:**
- Document storage requirements in test code
- Clear storage between test runs unless explicitly testing persistence
- Use `browser_run_code` to inspect/manipulate storage

**Example:**
```javascript
// Capture localStorage
const storage = await page.evaluate(() => JSON.stringify(localStorage));
```

### Dialog Handling

**Types:**
- Alerts (`window.alert()`)
- Confirms (`window.confirm()`)
- Prompts (`window.prompt()`)

**Rules:**
- Handle explicitly using `browser_handle_dialog`
- Document expected dialog text and chosen action (accept/dismiss)
- Never assume dialog behavior
- Test both accept and dismiss paths when business logic requires

---

## Live Web Exploration Workflow

### Initialization

**Request from user:**
- Target URL (required)
- Test objective (what should be validated?)
- Expected business outcome (what does success look like?)
- Authentication requirements (if any)

**Setup:**
1. Open browser tab in headed mode (for exploration)
2. Navigate to start URL using `browser_navigate`
3. Capture initial page structure using `browser_snapshot`
4. Begin documenting interaction flow

**Note:** Exploration uses **playwright-mcp server** for live discovery (browser_* tools). This is separate from later code generation which uses Playwright framework. After completing exploration, close the browser instance.

**Generated Code Rule:** When generating or updating Playwright projects, configure the default execution to stay `headed`. Only set `headless: true` or equivalent CLI/config overrides when the user explicitly asks for headless execution.

### Exploration Loop (Per Step)

#### A. Page Analysis

**Capture page structure:**
- Use `browser_snapshot` to get accessibility tree
- Identify all interactive elements (buttons, links, inputs, etc.)
- Note dynamic elements (loading indicators, modals, dropdowns)
- Record current page state (URL, title, key visible elements)

**Look for:**
- Loading indicators or skeleton screens
- Lazy-loaded content
- Infinite scroll behaviors
- Single-page app routing

#### B. Element Identification & Locator Strategy

**Extract from accessibility tree:**
- Element `element_ref` (unique identifier in snapshot)
- Element role (button, textbox, link, etc.)
- Accessible name (aria-label, visible text, etc.)
- Element attributes (id, data-testid, name, class)

**Rank locators by stability:**
1. **data-testid** - Most stable, purpose-built for testing
2. **aria-label / role** - Stable, accessibility-driven
3. **id** - Generally stable if not auto-generated
4. **name** - Stable for form elements
5. **visible text** - Least stable, changes with content

**Document chosen locator and rationale:**
```
Element: Login button
Locator: data-testid="login-btn"
Rationale: Explicit test ID, most stable option
Fallback: aria-label="Log in"
```

**Red Flags (avoid these locators):**
- Auto-generated IDs (e.g., `id="input-1234"`)
- Complex XPath based on structure
- CSS selectors based on styling classes
- nth-child or positional selectors

#### C. Action Execution

**Choose appropriate MCP tool:**

| Action | MCP Tool | Parameters |
|--------|----------|------------|
| Click button/link | `browser_click` | element_ref, description |
| Type text | `browser_type` | element_ref, text, description |
| Navigate to URL | `browser_navigate` | url |
| Complex logic | `browser_run_code` | javascript code |
| Select dropdown | `browser_click` (open) + `browser_click` (option) | - |
| File upload | `browser_file_upload` | element_ref, file_path |
| Hover | `browser_hover` | element_ref |

**Always provide:**
- Human-readable description of the action
- Exact element reference from snapshot
- Expected outcome

**Document the action:**
```
Step 3: Click "Login" button
Tool: browser_click
Element: element_ref from snapshot (data-testid="login-btn")
Expected: Navigate to dashboard page
```

#### D. Verification & Problem Identification

**Post-action verification:**
1. Capture new page structure using `browser_snapshot`
2. Verify expected state change:
   - URL changed?
   - New elements visible?
   - Error messages?
   - Success indicators?
3. Wait explicitly when required (use `browser_wait_for`)

**Identify potential automation issues:**

| Issue Type | Example | Solution |
|------------|---------|----------|
| Timing | Button enabled after API call | Explicit wait for element state |
| Dynamic content | Lazy-loaded images | Wait for specific element visibility |
| Animations | Slide-in modals | Wait for animation completion |
| Race conditions | Multiple API calls | Wait for network idle |
| Flakiness | Intermittent failures | Retry mechanism, better waits |

**Document challenges and solutions:**
```
Challenge: Submit button disabled until form validation completes
Solution: Wait for button to become enabled before clicking
Code: await page.waitForSelector('button[type=submit]:not([disabled])')
```

### Exploration Completion

After all exploration steps:

1. **Review complete interaction flow:**
   - [ ] All steps documented with clear descriptions
   - [ ] All element locators captured with stability rankings
   - [ ] All potential issues identified
   - [ ] Solutions recommended for each issue

2. **Close exploration browser session:**
   - Use `browser_close` or close tab
   - Clean up any resources

3. **Prepare exploration report:**
   - Complete flow overview
   - Element locator table
   - Identified issues and solutions
   - Recommended test implementation approach

4. **Proceed to code generation:**
   - Hand off documented exploration data to `code-generation` skill
   - Ensure all decisions are documented and traceable

---

## Web-Specific Challenges & Solutions

## Execution Defaults for Generated Projects

- Prefer Playwright configuration with `headless: false` or the equivalent visible-browser setting by default
- Treat CLI flags like `--headed` as optional reinforcement, not the only mechanism enforcing visibility
- If an existing project already forces `headless`, change it to visible execution unless the user explicitly requested headless behavior
- When documenting how to run the suite, present the visible/browser-open flow as the default command

### Single Page Applications (SPAs)

**Challenges:**
- Client-side routing (URL changes without page reload)
- Dynamic content loading
- State management complexity

**Solutions:**
- Use `browser_wait_for` to ensure content loads
- Wait for network idle after navigation
- Verify URL fragments/query params for route changes
- Check for framework-specific loading indicators (React, Vue, Angular)

### Infinite Scroll

**Challenge:** Content loads as user scrolls

**Solution:**
```javascript
// Scroll to bottom to trigger load
await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
// Wait for new content
await page.waitForSelector('selector-for-new-items');
```

### Shadow DOM

**Challenge:** Elements inside shadow roots not accessible via normal selectors

**Solution:**
- Use `browser_run_code` to pierce shadow DOM:
```javascript
const element = document.querySelector('host-element')
  .shadowRoot.querySelector('target-element');
```

### AJAX/XHR Requests

**Challenge:** Content updates asynchronously

**Solutions:**
- Wait for network idle: `await page.waitForLoadState('networkidle')`
- Wait for specific API response (use network interception)
- Wait for DOM changes that result from API response

### Authentication Flows

**Common Patterns:**
1. **Form-based:** Username/password fields
2. **OAuth/SSO:** Redirect to external provider
3. **MFA:** Additional verification step
4. **Session-based:** Cookie/token management

**Approach:**
- Document authentication requirements during exploration
- Capture all steps (including external redirects)
- Store credentials in environment variables (never hardcode)
- Consider authentication state preservation between tests

---

## Web Locator Best Practices

### Locator Stability Hierarchy

**Priority order:**
1. **data-testid** or similar test-specific attributes
2. **aria-label, aria-labelledby** (accessibility attributes)
3. **role** combined with accessible name
4. **id** (if stable and meaningful)
5. **name** (for form elements)
6. **Stable CSS classes** (not styling-related)
7. **visible text** (as last resort)

### Locator Construction Examples

**Good:**
```javascript
// Test ID
await page.locator('[data-testid="login-button"]').click();

// ARIA
await page.locator('button[aria-label="Submit form"]').click();

// Role + name
await page.locator('role=button[name="Login"]').click();

// Stable ID
await page.locator('#user-email-input').fill('test@example.com');
```

**Avoid:**
```javascript
// Auto-generated ID
await page.locator('#input-12345').click(); // ❌

// Complex XPath
await page.locator('//div[@class="container"]/div[2]/button[1]').click(); // ❌

// Position-based
await page.locator('button').nth(3).click(); // ❌

// Styling classes
await page.locator('.btn-primary.btn-lg.mt-3').click(); // ❌
```

### Combining Strategies

When no single strong locator exists:
```javascript
// Combine role, accessible name, and containment
await page.locator('form[aria-label="Login"]')
  .locator('button[type="submit"]').click();
```

---

## Web Project Initialization

If no project exists, create a new Playwright project:

### Project Structure

```
project-root/
├── src/
│   └── test/
│       ├── java/
│       │   ├── pages/           # Page objects
│       │   ├── steps/           # Cucumber step definitions
│       │   └── runners/         # Test runners
│       └── resources/
│           └── features/        # Cucumber feature files
├── pom.xml                      # Maven (Java)
├── package.json                 # npm (JS/TS)
├── requirements.txt             # pip (Python)
├── playwright.config.js         # Playwright configuration
└── .env                         # Environment variables
```

### Technology Stack Selection

**Ask user first**, then fallback to defaults:

**Java + Playwright + Cucumber (default):**
```xml
<dependencies>
    <dependency>
        <groupId>com.microsoft.playwright</groupId>
        <artifactId>playwright</artifactId>
    </dependency>
    <dependency>
        <groupId>io.cucumber</groupId>
        <artifactId>cucumber-java</artifactId>
    </dependency>
</dependencies>
```

**JavaScript/TypeScript + Playwright:**
```json
{
  "dependencies": {
    "@playwright/test": "^1.40.0"
  }
}
```

**Python + Playwright:**
```
playwright==1.40.0
pytest-playwright==0.4.3
```

### Browser Configuration

**Default (for exploration):**
- **Headed mode** during development/exploration
- **Chromium** browser (most common)

**Configurable:**
- Browser type (chromium, firefox, webkit)
- Viewport size
- Locale and timezone
- Permissions
- Device emulation (mobile testing)

---

## Integration Points

### With Other Skills

- **`live-exploration-workflow`**: This skill implements the web-specific version of the common exploration pattern
- **`project-analysis`**: Detects Playwright projects, identifies existing web tests
- **`code-generation`**: Receives exploration data (from playwright-mcp), generates Playwright test code
- **`execution-validation`**: Executes generated Playwright tests, validates results

### With Automation Agent

- Agent loads this skill when web technology detected
- Agent ensures **playwright-mcp tools available** before exploration (Phase 0 verification)
- Agent passes exploration findings (from playwright-mcp) to `code-generation` skill
- Agent coordinates between exploration (playwright-mcp tools) and code generation (Playwright framework)

### With MCP Tools (playwright-mcp server)

**Primary playwright-mcp tools:**
- `browser_navigate` - Navigate to URLs
- `browser_snapshot` - Capture accessibility tree
- `browser_click` - Click elements
- `browser_type` - Type text
- `browser_run_code` - Execute JavaScript
- `browser_wait_for` - Wait for conditions
- `browser_tabs` - Manage tabs
- `browser_take_screenshot` - Capture visual evidence
- `browser_close` - Close browser

**When to use each tool:**
- Use specific tools (`browser_click`, `browser_type`) for simple, clear actions
- Use `browser_run_code` for complex logic, custom validations, or framework-specific interactions

**Note:** All `browser_*` tools come from the **playwright-mcp server**. Playwright is the test framework used in generated code, not the MCP server.

---

## Quality Standards (Web-Specific)

1. **Selector Stability**: Prioritize data-testid and ARIA attributes
2. **Wait Strategy**: Always wait explicitly, never use fixed delays
3. **Browser State**: Clean up between tests (cookies, storage, sessions)
4. **Screenshots**: Capture on both failure and success
5. **Network**: Consider waiting for network idle for API-dependent UIs
6. **Cross-browser**: Document if test is browser-specific
7. **Viewport**: Document viewport requirements (mobile, tablet, desktop)

---

## Common Pitfalls

1. **Not verifying playwright-mcp availability**: Attempting exploration without playwright-mcp server running
2. **Not waiting for dynamic content**: Always wait for elements to be ready
3. **Using unstable locators**: Avoid auto-generated IDs and positional selectors
4. **Ignoring network state**: SPAs need network-aware waits
5. **Hardcoded delays**: Use smart waits instead of `sleep(5000)`
6. **Not handling dialogs**: Dialogs pause execution until handled
7. **Leaving browser open**: Always clean up resources using `browser_close`
8. **Not testing different viewport sizes**: Mobile vs desktop differences

---

## Examples

### Example 1: Login Flow Exploration

**Documented exploration:**
```
Step 1: Navigate to login page
- URL: https://example.com/login
- Initial state: Login form visible

Step 2: Identify username field
- Element: textbox, aria-label="Username"
- Locator: data-testid="username-input"
- Stability: High (test ID)

Step 3: Type username
- Action: browser_type
- Text: "testuser@example.com"

Step 4: Identify password field
- Element: textbox, type="password"
- Locator: data-testid="password-input"
- Stability: High (test ID)

Step 5: Type password
- Action: browser_type
- Text: "***" (from environment variable)

Step 6: Identify submit button
- Element: button, type="submit"
- Locator: data-testid="login-submit"
- Stability: High (test ID)

Step 7: Click submit
- Action: browser_click
- Expected: Navigate to dashboard

Step 8: Verify success
- Wait for: URL change to /dashboard
- Verify: Welcome message visible
- Element: heading, role="heading", level=1
- Text: "Welcome, Test User"
```

### Example 2: Handling Dynamic Content

**Challenge:** Product list loads asynchronously

**Exploration notes:**
```
Issue: Product list not immediately visible after page load
Observation: Loading spinner visible, then products appear
Solution: Wait for spinner to disappear, then verify products

Implementation:
1. Wait for spinner to be hidden:
   await page.waitForSelector('.loading-spinner', { state: 'hidden' })
2. Wait for first product to appear:
   await page.waitForSelector('[data-testid="product-card"]')
3. Verify expected number of products loaded
```

---

## Important: playwright-mcp vs Playwright

**Clarification to avoid confusion:**

- **playwright-mcp**: The MCP server that provides live exploration tools
  - Tools: `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, etc.
  - Purpose: Live exploration and interaction with web apps during discovery phase
  - When used: During agent's exploration workflow (Phase 2B)

- **Playwright**: The browser automation framework
  - Libraries: `@playwright/test`, `com.microsoft.playwright`, `playwright` (Python)
  - Purpose: Running generated test code (Page, Browser, Locator classes)
  - When used: In generated test code that runs after exploration

**These are related but distinct: playwright-mcp is the MCP server for exploration, Playwright is the framework for generated tests.**

---

**End of Web Automation Playwright Skill**

Use this skill whenever web automation is required. Always follow the locator stability hierarchy and wait strategies to ensure reliable, maintainable tests.
