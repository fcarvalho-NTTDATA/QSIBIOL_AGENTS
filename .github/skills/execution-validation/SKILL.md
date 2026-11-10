---
name: execution-validation
description: "Use when executing generated automation, classifying failures, applying focused repairs, and validating deliverables."
argument-hint: "Provide the generated tests, execution command, and target environment"
---

# Execution & Validation

## Purpose

This skill defines the execution loop, error classification framework, automatic fixing protocol, and deliverable validation standards. It ensures generated code works 100% before delivery.

## When to Use

Activate this skill when:
- Generated code needs execution validation
- Existing tests need to be run and analyzed
- Failures need classification and fixing
- Delivery validation required

---

## Core Principle: No Unvalidated Deliveries

**ABSOLUTE REQUIREMENT:**
- Generated code MUST be executed immediately after creation
- Code MUST be validated to work 100% before delivery
- Any errors detected MUST be analyzed and fixed automatically
- Iterative execution and correction until full success
- Final deliverable is a tested, functional automation script

---

## Execution Loop

### 1. Initial Execution

**Execute generated code:**
- Run all generated tests
- Capture execution output (stdout, stderr)
- Record test results (passed, failed, skipped)
- Collect artifacts (screenshots, logs, reports)
- Measure execution time

**Collect evidence:**
- Console output
- Framework-specific reports
- Screenshots (success and failure)
- Logs (application, test framework, MCP tools)
- Network traces (if applicable)

### 2. Result Analysis

**Analyze execution results:**

**If ALL tests passed:**
- Verify 100% pass rate
- Confirm expected outcomes achieved
- Validate screenshots captured
- Check final report generated
- → Proceed to Delivery Validation

**If ANY test failed:**
- Capture full failure context
- → Proceed to Error Classification

### 3. Error Classification

**Classify EVERY failure as one of three types:**

#### A. `code_issue` (Agent fixes automatically)

**Definition:** Problem in test code, not in application

**Examples:**
- Incorrect selector/locator
- Wrong wait strategy
- Timing issue in test code
- Missing waits
- Incorrect assertion
- Syntax error
- Import missing
- Wrong data type
- Framework configuration error

**Action:** Fix automatically, re-execute

#### B. `system_bug` (Document and notify user)

**Definition:** Problem in application under test

**Examples:**
- API returning 5xx error
- Application crash
- Documented endpoint not working
- Data inconsistency in application
- Expected element not present (application changed)
- Authentication failure (valid credentials rejected)
- Business logic error

**Action:** Document thoroughly, notify user, attempt workaround if possible

#### C. `user_input_needed` (Pause and ask)

**Definition:** Ambiguity or missing information

**Examples:**
- Missing credentials
- Wrong environment (test ran against prod instead of dev)
- Unclear expected behavior
- Multiple valid approaches (user must choose)
- Configuration missing

**Action:** Stop execution, ask user for clarification, adjust based on response

### 4. Automatic Fixing (for `code_issue`)

**Fix automatically (max 5 iterations):**

**Common fixes:**

1. **Selector/Locator issues:**
   - Try fallback locator from exploration data
   - Adjust selector syntax
   - Use more specific selector
   - Wait for element before interacting

2. **Timing issues:**
   - Increase wait timeout
   - Change wait strategy (visibility, presence, clickable)
   - Add explicit wait before action
   - Wait for network idle

3. **Framework issues:**
   - Fix import statements
   - Adjust configuration
   - Update dependencies
   - Correct syntax errors

4. **Data issues:**
   - Convert data types
   - Fix JSON format
   - Escape special characters
   - Use correct encoding

5. **Assertion issues:**
   - Adjust expected values to match actual (if actual is correct)
   - Fix assertion syntax
   - Use more flexible matchers

**Fixing process:**
1. Identify root cause from error message
2. Apply most likely fix
3. Re-execute immediately
4. Repeat until success or max iterations reached

### 5. Re-execution

**After each fix:**
- Execute tests again immediately
- Compare results with previous run
- Track progress (more tests passing?)
- Collect new artifacts

**Stop conditions:**
- 100% tests passing → Success, proceed to delivery
- Max iterations (5) reached → Escalate to user
- User-acknowledged limitation → Document and deliver with notice

### 6. Escalation (if stuck)

**If unable to fix after max iterations:**

**STOP execution immediately**

**Present detailed failure report:**
```markdown
# Automation Blocked - Unable to Achieve 100% Success

## Summary
- Total Tests: X
- Passed: Y
- Failed: Z
- Execution Time: Xm Ys

## Failure Details

### Test: [Test Name]
- **Error**: [Exact error message]
- **Classification**: [code_issue / system_bug / user_input_needed]
- **Root Cause**: [Analysis of what's wrong]

## Fix Attempts (5 iterations)
1. Attempt 1: [What was tried] → [Result]
2. Attempt 2: [What was tried] → [Result]
3. Attempt 3: [What was tried] → [Result]
4. Attempt 4: [What was tried] → [Result]
5. Attempt 5: [What was tried] → [Result]

## Blocker Analysis
[Detailed analysis of why fixes didn't work]

## Evidence
- Screenshot: [path]
- Full log: [path]
- Test output: [path]

## Recommendation
[What should happen next - user guidance needed]
```

**Request user guidance:**
- Explain the blocker clearly
- Provide evidence
- Ask for direction (accept limitation? different approach?)

---

## Delivery Validation

**Before delivering automation:**

### 1. Execution Criteria

**Check:**
- [ ] All tests executed successfully (100% pass rate)
- [ ] OR user explicitly acknowledged documented limitations
- [ ] Final execution time reasonable
- [ ] No errors or warnings (or all justified)

### 2. Quality Criteria

**Verify:**
- [ ] Code follows quality gates (from `code-generation` skill)
- [ ] Stable locators used
- [ ] Explicit waits implemented
- [ ] Screenshots captured on failure AND success
- [ ] Automated final report generated
- [ ] Report includes visual evidence
- [ ] Code is maintainable (clear names, comments)

### 3. Evidence Criteria

**Confirm:**
- [ ] Screenshots exist and are accessible
- [ ] Logs captured and readable
- [ ] Final report generated automatically
- [ ] Report viewable without additional tools
- [ ] All artifacts stored in `evidences/` folder at project root

### 4. Documentation Criteria

**Ensure:**
- [ ] README or execution instructions provided
- [ ] How to run tests documented
- [ ] How to view reports documented
- [ ] Environment requirements documented
- [ ] Known limitations documented (if any)

---

## Delivery Report Template

**Provide this report when delivering automation:**

```markdown
## Automation Delivery Report

**Status**: [✅ FULLY FUNCTIONAL | ⚠️ PARTIAL - USER ACKNOWLEDGED | ❌ BLOCKED]

**Technology**: [Web/Mobile/API]

**Test Execution Summary**:
- Total Tests: X
- Passed: Y
- Failed: Z
- Execution Time: Xm Ys
- Platform/Environment: [Details]

**Evidence**:
- Execution Report: [path or link]
- Screenshots:
  - Success: [path]
  - Failure: [path if any]
- Logs: [path]

**What Was Automated**:
- [Step 1: Description] - ✅ Working
- [Step 2: Description] - ✅ Working
- [Step 3: Description] - ✅ Working
- [Step 4: Description] - ❌ Blocked by system bug #123 (if any)

**Known Limitations** (if any):
- **Issue**: [Description]
- **Classification**: [system_bug | user_input_needed]
- **Workaround**: [If available]
- **User Acknowledgment**: [Acknowledged on DATE by USER]

**Configuration**:
- Language: [Java/JavaScript/Python]
- Framework: [Playwright/Appium/RestAssured]
- Test Runner: [Cucumber/TestNG/Jest/Pytest]
- Build Tool: [Maven/npm/pip]

**How to Run Tests**:
```bash
[Command to execute tests]
```

**How to View Reports**:
[Instructions to access and view reports]

**Next Steps**:
- [Recommended improvements]
- [Additional scenarios to automate]
- [Technical debt to address]
```

---

## Environment & Test Data Management

### Environment Configuration

**Always ask user:**
- Which environment to target (dev, staging, prod)
- Store environment-specific configs in separate files (`.env`, `config.json`)
- Never hardcode URLs, credentials, or environment-specific data
- Support environment selection via command-line arguments or env variables

**Best practices:**
```bash
# .env file (not committed)
BASE_URL=https://dev.example.com
API_KEY=abc123
USERNAME=testuser
PASSWORD=testpass

# Select environment at runtime
npm test --env=dev
mvn test -Denv=staging
```

### Test Data Strategy

**Prefer idempotent operations:**
- Tests can run multiple times safely
- Avoid dependencies on specific data state

**For data creation:**
- Generate unique identifiers (timestamps, UUIDs)
- Record created entities for cleanup
- Example: `email = "test_" + timestamp + "@example.com"`

**Setup/Teardown:**
- Provide setup scripts when data persistence needed
- Clean up test data after execution
- Reset application state between tests when required

### Credentials & Secrets Management

**NEVER hardcode credentials in test code**

**Use environment variables:**
```java
String username = System.getenv("TEST_USERNAME");
String password = System.getenv("TEST_PASSWORD");
```

**Prompt user for storage strategy:**
- `.env` file (local development)
- Vault (HashiCorp Vault, AWS Secrets Manager)
- CI secrets (GitHub Actions secrets, Jenkins credentials)

**Mask in output:**
- Replace credentials with `[REDACTED]` in logs
- Never print full tokens or passwords
- Sanitize all reports and artifacts

---

## False Positives Prevention

**ABSOLUTE PROHIBITION:** Never report success or deliver code when tests are failing.

**The agent MUST:**
- Execute generated tests and verify actual results
- Compare expected vs actual outcomes explicitly
- If ANY test fails: classify error and attempt fix OR stop and report blocker
- Never assume success without execution evidence
- Never suppress or hide failures in reporting

**Delivery Gate:**
1. Execute complete test suite
2. Verify 100% pass rate OR have explicit user acknowledgment of known limitations
3. If stuck after max correction iterations: STOP, document blocker, request user guidance
4. Present clear evidence: "Tests executed: X, Passed: Y, Failed: Z"

### Desktop Verification Gating

For desktop automation, verify each interaction outcome and classify no-op or wrong-target failures using the evidence rules in [desktop-automation/SKILL.md](../desktop-automation/SKILL.md).

**Forbidden Actions:**
- Delivering code without execution proof
- Marking failed tests as "might work"
- Hiding errors in comments or documentation
- Assuming fixes worked without re-execution
- Reporting "test created successfully" without execution
- Saying "all tests passing" without execution proof
- Delivering code with assumption "it should work"

**Required Actions:**
- Always execute before delivery
- Show actual execution results
- Be honest about failures
- Provide evidence of success

---

## Iterative Correction Protocol (Detailed)

### Iteration Loop

**Max iterations: 5**

**Each iteration:**

1. **Execute tests**
2. **Capture results**
3. **Analyze failures**
4. **Classify errors** (code_issue, system_bug, user_input_needed)
5. **For code_issue:**
   - Identify root cause
   - Apply fix
   - Re-execute
6. **For system_bug:**
   - Document thoroughly
   - Notify user
   - Attempt workaround if possible
   - If workaround succeeds, continue; else, escalate
7. **For user_input_needed:**
   - Stop and ask user
   - Adjust based on response
   - Re-execute
8. **Track progress:**
   - Are more tests passing?
   - Is the same error recurring?
   - Is a different error appearing?

**Exit conditions:**
- **Success**: 100% pass rate achieved
- **Partial**: User acknowledges limitation, documented
- **Blocked**: Max iterations reached, escalate to user

### Example Iteration Log

```
Iteration 1:
- Tests run: 5
- Passed: 3
- Failed: 2
  - Test: Login flow
    - Error: Timeout waiting for dashboard
    - Classification: code_issue (insufficient wait)
    - Fix: Increase wait timeout from 5s to 10s
  - Test: Search flow
    - Error: Element not found
    - Classification: code_issue (selector incorrect)
    - Fix: Use fallback selector from exploration data

Iteration 2:
- Tests run: 5
- Passed: 4
- Failed: 1
  - Test: Search flow
    - Error: Element still not found
    - Classification: code_issue (need to wait for dynamic content)
    - Fix: Add explicit wait for element visibility

Iteration 3:
- Tests run: 5
- Passed: 5
- Failed: 0
- Result: 100% success, ready for delivery
```

---

## Integration Points

### With Other Skills

- **`code-generation`**: Receives generated code for execution
- **`project-analysis`**: Uses project info to run correct commands
- **`web-automation-playwright`**: Technology-specific execution guidance
- **`mobile-automation-appium`**: Technology-specific execution guidance
- **`api-automation`**: Technology-specific execution guidance

### With Automation Agent

- Agent invokes this skill after code generation
- Agent enforces iterative correction protocol
- Agent uses delivery report format
- Agent makes final decision to deliver or escalate

---

## Technology-Specific Execution

**Web (Playwright):**
```bash
# Java
mvn test

# JavaScript/TypeScript
npx playwright test

# Python
pytest
```

**Mobile (Appium):**
```bash
# Java
mvn test -Dplatform=android

# JavaScript/TypeScript
npx wdio run wdio.conf.js

# Python
pytest tests/mobile/
```

**API (RestAssured):**
```bash
# Java
mvn test -Dtest=ApiTest

# JavaScript
npm test

# Python
pytest tests/api/
```

---

## Common Execution Issues & Fixes

| Issue | Classification | Fix |
|-------|----------------|-----|
| Timeout waiting for element | code_issue | Increase timeout, improve wait strategy |
| Element not found | code_issue | Use fallback locator, add wait |
| Stale element reference | code_issue | Re-find element before interaction |
| API 401 Unauthorized | code_issue | Refresh token, fix auth header |
| API 500 Internal Server Error | system_bug | Document, notify user, check if transient |
| Screenshot not captured | code_issue | Fix screenshot path, check permissions |
| Report not generated | code_issue | Check report config, verify output path |
| Missing credentials | user_input_needed | Ask user for credentials |
| Wrong environment | user_input_needed | Clarify which environment to use |

---

## Quality Checklist

Before delivery:
- [ ] All tests executed
- [ ] 100% pass rate achieved (or limitation acknowledged)
- [ ] Evidence captured (screenshots, logs)
- [ ] Final report generated automatically
- [ ] Report includes visual evidence
- [ ] Report accessible without additional tools
- [ ] Execution instructions documented
- [ ] Known limitations documented (if any)
- [ ] No false positives (all passes are real passes)
- [ ] No hidden failures

---

**End of Execution & Validation Skill**

Use this skill to execute, validate, fix, and deliver automation with confidence. Never deliver unvalidated code.
