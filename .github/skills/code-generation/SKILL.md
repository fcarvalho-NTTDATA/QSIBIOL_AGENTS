---
name: code-generation
description: "Use when generating or modifying maintainable test automation from validated exploration data and project conventions."
argument-hint: "Provide validated exploration results, the target stack, and the requested test coverage"
---

# Code Generation

## Purpose

This skill provides rules and patterns for generating high-quality automation code from validated exploration data. It ensures code follows best practices, integrates with existing projects, and meets all quality gates.

## When to Use

Activate this skill when:
- Live exploration completed and need to generate code
- Extending existing tests with new scenarios
- Modifying automation code to fix issues or add coverage

## Prerequisites

Before code generation:
- [ ] Live exploration completed (via `live-exploration-workflow`)
- [ ] All three exploration objectives met (steps, locators, challenges)
- [ ] Technology-specific exploration data captured
- [ ] Project analysis completed (to understand existing patterns)

---

## MANDATORY Prerequisites for Code Creation

**EVERY code generation request MUST:**

1. **Live Exploration Completed**
   - Real system exploration using technology-appropriate MCP tools
   - NOT assumptions or theoretical flows

2. **System Structure Captured**
   - Web: `browser_snapshot` captured page structure
   - Mobile: `mobile_list_elements_on_screen` captured app structure
   - API: Real request/response pairs captured

3. **Real Identifiers Extracted**
   - Locators/selectors from live analysis
   - NOT guessed or template-based

4. **Interactions Validated**
   - Every action validated through actual execution
   - Expected outcomes confirmed

5. **Documentation Complete**
   - ALL discoveries documented during exploration:
     - Execution steps in order
     - Element locators with stability ranking
     - Identified automation challenges and solutions
     - Technology-specific behaviors

6. **Exploration Data as Single Source of Truth**
   - Use ONLY validated exploration data for code generation
   - NO assumptions or filling gaps with guesses

**FORBIDDEN Actions:**
- Creating code without live exploration
- Using assumed or template locators
- Generating theoretical test scenarios
- Skipping live interaction for speed
- Creating automation code without completing exploration phase
- Defaulting generated UI automation to headless or hidden execution without an explicit user request

---

## Quality Gates

All generated test code MUST meet these standards:

### 1. Code Coverage
- **Document**: What percentage of user story/flow is automated
- **Track**: Which scenarios are covered vs. not covered
- **Report**: Coverage gaps explicitly

### 2. Locator/Selector Stability
- **Prioritize**: Most stable identification strategy
- **Web**: data-testid > aria-label > id > name > text
- **Mobile**: resource-id/accessibility id > content-desc/name > text > xpath
- **API**: OpenAPI schema > field names > status codes > payloads
- **Document**: Why each locator was chosen

### 3. Execution Time
- **Target**: Single test completes in reasonable time
- **Threshold**: Document if test takes >2-3 minutes (web/API) or >3-5 minutes (mobile)
- **Optimize**: Reduce unnecessary waits, parallelize when possible

### 4. Resilience
- **Include**: Explicit waits for dynamic content
- **Implement**: Retries for known flaky operations
- **Handle**: Expected exceptions gracefully
- **Avoid**: Hard-coded delays (use smart waits instead)

### 4.1 Execution Mode Defaults
- **Web**: Generated Playwright projects must run in a visible browser (`headed`) by default
- **Mobile**: Generated Appium/mobile projects must use visible device/emulator/simulator sessions by default
- **Override**: Use `headless`, hidden, or background execution only when the user explicitly requests it
- **Conventions**: If the existing project forces hidden/headless execution and the user did not ask for that, change the default to visible execution

### 5. Maintainability
- **Naming**: Clear, descriptive names for tests, methods, variables
- **Comments**: Explain complex logic, business context
- **Reusability**: Extract common patterns into utilities
- **Structure**: Follow project conventions and patterns

### 6. Evidence
- **Capture**: Screenshots on both failure AND success
- **Log**: Important checkpoints and state changes
- **Report**: Comprehensive execution summary
- **Artifacts**: Store ALL evidence (screenshots, logs, reports) in the `evidences/` folder at the project root
   - Path convention: `<project-root>/evidences/`
  - Create the folder automatically if it does not exist
   - Do NOT use alternative folders like `evidence/`, `artifacts/`, or nested output roots outside project root
  - This applies to all technology types: web, mobile, and API

### 7. Parallel Safety
- **Isolate**: Tests must not share state
- **Independent**: Each test sets up own preconditions
- **Clean up**: Remove test data created during execution
- **Document**: Any tests that cannot run in parallel (with reason)

---

## Technology Stack Selection

### Selection Process

1. **Check for existing project:**
   - Use patterns from `project-analysis` skill
   - Match existing language and framework
   - Reuse existing test structure

2. **Ask user for preference:**
   - If no existing project, ask user to choose
   - Present options for identified technology (web/mobile/API)

3. **Fallback to defaults (only if no response):**
   - **Web**: Java + Playwright + Cucumber
   - **Mobile**: Java + Appium + Cucumber
   - **API**: Java + RestAssured + Cucumber

**CRITICAL RULE**: Respect explicit language/tooling choices
- If user specifies a stack, use it exactly
- If repository has existing project, match it exactly
- Do NOT add, remove, or substitute stacks arbitrarily

### Supported Stacks by Technology

**Web Automation:**
- Java + Playwright + Cucumber
- Java + Playwright + TestNG
- JavaScript/TypeScript + Playwright
- Python + Playwright + Pytest

**Mobile Automation:**
- Java + Appium + Cucumber
- Java + Appium + TestNG
- JavaScript/TypeScript + WebdriverIO
- Python + Appium + Pytest

**API Automation:**
- Java + RestAssured + Cucumber
- JavaScript/TypeScript + axios/supertest + Jest
- Python + requests + Pytest

---

## Code Integration Principles

### 1. Prefer Incremental Changes

- **Add to existing**: Extend existing test files when possible
- **Avoid rewrites**: Don't replace working code unnecessarily
- **Minimal diffs**: Make smallest change that achieves goal

### 2. Reuse Existing Code & Patterns

**CRITICAL**: Before creating ANY new method, function, or component:
- **Search existing codebase** for similar functionality
- **Reuse existing methods/functions** whenever possible
- **Extend existing classes/modules** rather than duplicating
- **Never create duplicate methods** - if similar logic exists, refactor to reuse it

**Specific reuse guidelines:**
- **Page/Screen objects**: Add methods to existing page objects, don't create new ones for same page
- **Utilities/Helpers**: Use existing helper functions, consolidate similar helpers
- **Step definitions**: Reuse existing steps with parameters instead of creating similar steps
- **Configuration**: Use existing config patterns and extend when needed
- **Locators**: If element already defined in page object, reference it instead of redefining
- **Wait strategies**: Reuse existing wait/retry logic instead of duplicating
- **Validation logic**: Extract and reuse validation methods across tests

**Code quality through reuse:**
- Write DRY (Don't Repeat Yourself) code
- Extract common patterns into reusable functions
- Consolidate duplicate logic found during exploration
- Prefer composition over duplication
- Keep codebase maintainable by minimizing redundancy

### 3. Respect Project Conventions

- **Naming**: Match existing naming conventions
- **Structure**: Place files in expected locations
- **Formatting**: Match existing code style
- **Imports**: Follow existing import organization

### 4. Balance Abstraction & Simplicity

- **Page objects**: Create only for pages actually used; add to existing page objects when possible
- **Utilities**: Create new utility ONLY when pattern repeats 3+ times AND doesn't exist yet
- **Avoid over-engineering**: Keep it simple and practical
- **Avoid under-engineering**: Don't duplicate code when abstraction would help
- **Right-size solutions**: Simple for one-time use, abstracted for repeated patterns

### 5. All Locators from Real Analysis

- **Every selector**: Must come from exploration data
- **No assumptions**: Never guess element identifiers
- **Traceability**: Can trace every locator to exploration snapshot

---

## Code Creation Workflow (5 Phases)

### Phase 1: Validate Prerequisites (REQUIRED)

**Check:**
- [ ] Live exploration completed
- [ ] Technology-appropriate MCP tools used
- [ ] System structure captured
- [ ] Real identifiers extracted
- [ ] Interactions validated
- [ ] Documentation complete

**If ANY prerequisite missing:** STOP and complete exploration first.

### Phase 2: Element Discovery & Documentation Review (REQUIRED)

**Review exploration data:**
- Execution steps in order
- Element locators with stability ranking
- Identified automation challenges
- Recommended solutions

**Validate completeness:**
- All interactions have locators
- All locators have stability ranking
- All challenges have solutions

### Phase 3: Technology Stack Selection (REQUIRED)

**Determine stack:**
1. Check existing project (use same stack)
2. Ask user if no project exists
3. Fallback to default if no response

**Verify:**
- Language selected
- Framework selected
- Test runner selected
- Build system identified

### Phase 4: Generate Code (ONLY AFTER 1-3)

**Step 4.1: Analyze Existing Codebase for Reuse**
- Search for existing methods/functions that perform similar actions
- Identify existing page/screen objects that can be extended
- Find existing utilities/helpers that can be reused
- Review existing step definitions for reusable patterns
- Map exploration steps to existing code where possible

**Step 4.2: Plan Code Structure with Maximum Reuse**
- For each new action: Can existing method be reused or extended?
- For each new locator: Does it already exist in page object?
- For each validation: Can existing validation method be reused?
- Document what will be NEW vs what will be REUSED

**Step 4.3: Generate Code Using Exploration Data + Existing Code**
- Execution steps → Reuse existing methods OR create new test steps
- Element locators → Reuse existing locators OR add new ones to existing page objects
- Challenges + solutions → Reuse existing wait strategies OR implement new ones
- Technology stack → Follow existing code patterns and conventions
- Execution mode defaults → Make visible/headed execution the default unless the user explicitly requested headless/hidden execution

**Follow quality gates:**
- [ ] Stable locators used
- [ ] Explicit waits implemented (reused or new)
- [ ] Screenshot capture added
- [ ] Clear naming applied
- [ ] Comments for complex logic
- [ ] Visible/headed execution is the default for UI automation unless the user explicitly requested otherwise
- [ ] **Maximum code reuse achieved** (no duplicated methods/functions)
- [ ] **Existing patterns extended** (not recreated)
- [ ] **DRY principle followed** (consolidate any discovered duplication)

**Implement identified solutions:**
- Timing issues → Reuse existing wait utilities OR create explicit waits
- Dynamic content → Reuse existing detection logic OR implement smart detection
- Error scenarios → Use existing error handlers OR add try-catch with meaningful errors
- Alternative paths → Reuse existing conditional utilities OR add conditional logic

**Add automated reporting:**
- Screenshot capture on success and failure
- Execution summary generation
- Report must be generated automatically at test completion
- Supported formats: HTML, JSON, or framework-specific
- Screenshots embedded or linked in report

### Phase 5: Validate Generated Code (MANDATORY)

**After generation:**
- Review code for completeness
- Check all locators match exploration data
- Verify quality gates met
- Ensure reporting is implemented

**Before delivery:**
- Code must be executed (see `execution-validation` skill)
- NOT included in this skill's scope

---

## Screenshots & Final Reporting Requirements

**All generated tests MUST:**

1. **Capture screenshots on failure:**
   - Implement in test framework's failure hook
   - Include timestamp in filename
   - Store in `evidences/` folder at project root (create if not exists)

2. **Capture screenshots at test completion:**
   - Final state screenshot
   - Success confirmation visual
   - Store in `evidences/` folder at project root (create if not exists)

3. **Generate comprehensive final report:**
   - Execution summary (tests run, passed, failed)
   - Screenshots embedded or linked
   - Execution time per test
   - Failure details with stack traces

4. **Report accessibility:**
   - Must be viewable without additional tools (HTML preferred)
   - Screenshots must be visible in report
   - Report generated automatically at test end

5. **Framework-specific reporting:**
   - ExtentReports (Java)
   - Allure (multi-language)
   - Playwright HTML Reporter (Playwright)
   - Pytest-html (Python)
   - Jest/Mocha reporters (JavaScript)

---

## Desktop Reliability Helpers

Desktop projects must implement post-action verification and resilient ranked localization according to [desktop-automation/SKILL.md](../desktop-automation/SKILL.md), reusing its reference implementation patterns where applicable.

## Code Integration

## Integration Points

### With Other Skills

- **`live-exploration-workflow`**: Provides exploration data for code generation
- **`project-analysis`**: Provides existing project patterns to follow
- **`web-automation-playwright`**: Provides web-specific code patterns
- **`mobile-automation-appium`**: Provides mobile-specific code patterns
- **`api-automation`**: Provides API-specific code patterns
- **`execution-validation`**: Receives generated code for execution

### With Automation Agent

- Agent ensures prerequisites met before invoking this skill
- Agent delegates to technology-specific skills for implementation details
- Agent passes generated code to `execution-validation` skill

---

## Common Pitfalls

1. **Skipping prerequisites**: Generating code without exploration
2. **Using unstable locators**: Choosing convenient but brittle selectors
3. **Hardcoded waits**: Using `sleep(5000)` instead of smart waits
4. **Ignoring project patterns**: Not matching existing code style
5. **Over-abstraction**: Creating unnecessary layers
6. **Missing error handling**: Not implementing try-catch for expected errors
7. **No screenshot capture**: Forgetting to add evidence collection
8. **No automated reporting**: Missing final report generation
9. **Duplicating code**: Creating new methods when similar ones exist
10. **Not searching existing code**: Failing to identify reusable components
11. **Recreating utilities**: Writing new helpers when existing ones could be used
12. **Ignoring existing page objects**: Creating new page objects for already-defined pages

---

## Quality Checklist

Before considering code generation complete:

- [ ] All prerequisites validated
- [ ] Exploration data reviewed and complete
- [ ] Technology stack selected
- [ ] **Existing codebase analyzed for reusable components**
- [ ] **Maximum code reuse strategy planned**
- [ ] Code generated using exploration data as single source
- [ ] Quality gates met:
  - [ ] Code coverage documented
  - [ ] Stable locators used
  - [ ] Execution time reasonable
  - [ ] Resilience implemented (waits, retries)
  - [ ] Maintainable (clear names, comments)
  - [ ] Evidence capture added (screenshots, logs)
  - [ ] Parallel-safe (isolated tests)
  - [ ] **No duplicate methods/functions created**
  - [ ] **Existing code reused wherever possible**
  - [ ] **DRY principle followed**
- [ ] Screenshots on failure implemented
- [ ] Screenshots on completion implemented
- [ ] Automated final report generation implemented
- [ ] Report includes visual evidence
- [ ] Existing patterns reused where applicable
- [ ] Project conventions respected
- [ ] No unused abstractions created
- [ ] All locators traceable to exploration

**If ANY item incomplete:** Return to appropriate phase and complete it.

---

**End of Code Generation Skill**

Use this skill after exploration is complete to generate high-quality, maintainable automation code. Always validate prerequisites and follow quality gates.
