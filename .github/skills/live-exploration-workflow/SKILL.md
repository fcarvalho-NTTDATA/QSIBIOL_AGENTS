---
name: live-exploration-workflow
description: "Use when exploring a live system to discover test flows, locators, and automation constraints before generating tests."
argument-hint: "Provide the target system, intended user flow, and access constraints"
---

# Live Exploration Workflow (Technology-Agnostic Pattern)

## Purpose

This skill defines the common exploration pattern shared across all automation technologies (web, mobile, API). It provides the high-level workflow that technology-specific skills customize for their context.

## When to Use

Activate this skill when:
- Creating new automated tests (no existing test found)
- Need to explore target system to understand automation approach
- Documenting interaction flows for code generation
- Used in combination with technology-specific skills

**Note:** This skill provides the PATTERN. Technology-specific skills (web, mobile, API) provide the IMPLEMENTATION.

---

## Three Critical Objectives of Live Exploration

All exploration sessions, regardless of technology, have THREE objectives:

1. **Capture Execution Steps**
   - Document the complete flow from start to finish
   - Record each action in order
   - Note business context for each step
   - Describe expected outcomes

2. **Extract Stable Locators/Identifiers**
   - Identify all interactive elements/endpoints
   - Extract multiple identification strategies
   - Rank strategies by stability
   - Choose the most stable option
   - Document fallback options

3. **Identify Potential Automation Challenges**
   - Spot timing/synchronization issues
   - Note dynamic behaviors
   - Recognize potential flakiness sources
   - Recommend solutions proactively

**Success Criteria:** All three objectives must be met before code generation can begin.

---

## Universal Exploration Pattern

All technologies follow this four-phase pattern:

### Phase 1: Initialization

**Collect from user:**
- Target system identifier (URL for web, app for mobile, base URL for API)
- Test objective (what should be validated?)
- Expected business outcome (what does success look like?)
- Authentication requirements (if any)
- Environment context (dev, staging, prod)

**Set up technology-specific connection:**
- Web: Open browser in visible (`headed`) mode by default, navigate to URL
- Mobile: Launch app on visible device/emulator by default
- API: Configure HTTP client, authenticate

**Default Visibility Rule:** Exploration should be visible by default for UI technologies. Use headless/hidden execution only when the user explicitly requests it.

**Capture initial state:**
- Web: `browser_snapshot` (accessibility tree)
- Mobile: `mobile_list_elements_on_screen` (page source)
- API: Document available endpoints

**Begin documentation:**
- Start recording interaction flow
- Note initial observations

### Phase 2: Exploration Loop

**Repeat for each step in the flow:**

#### A. Analyze Current State

**Capture system structure:**
- Web: Page structure (DOM/accessibility tree)
- Mobile: Screen structure (view hierarchy)
- API: Available endpoints and their schemas

**Identify interactive elements:**
- Buttons, links, inputs (web/mobile)
- API endpoints and methods

**Record current state:**
- Current location (URL, screen, endpoint)
- Visible/available elements
- Dynamic behaviors observed

#### B. Identify Target & Extract Locators

**Select target element/endpoint:**
- Choose next interaction target
- Extract identifiers/locators from live analysis

**Document identification strategies:**
- Web: data-testid, aria-label, id, name, text
- Mobile: resource-id (Android), accessibility id (iOS), text
- API: endpoint path, method, parameters

**Rank by stability:**
- Apply technology-specific stability hierarchy
- Document chosen strategy and rationale
- Note fallback options

**Technology-specific guidance:**
- Web: See `web-automation-playwright` skill
- Mobile: See `mobile-automation-appium` skill
- API: See `api-automation` skill

#### C. Execute Action

**Perform interaction using technology-appropriate tool:**
- Web: `browser_click`, `browser_type`, `browser_navigate`
- Mobile: `mobile_click_on_screen_at_coordinates`, `mobile_type_keys`, `mobile_swipe_on_screen`
- API: HTTP request (GET, POST, PUT, DELETE, etc.)

**Always provide:**
- Human-readable description
- Exact element reference or endpoint details
- Expected outcome

**Document the action:**
- Step number and description
- Tool/method used
- Target element/endpoint
- Input data (if any)
- Expected result

#### D. Verify & Identify Challenges

**Capture post-action state:**
- Web: New `browser_snapshot`
- Mobile: New `mobile_list_elements_on_screen`
- API: Response status, headers, body

**Verify expected change:**
- Did the system respond as expected?
- Are new elements/data visible?
- Did navigation/transition occur?

**Wait when required:**
- Animations, transitions, loading indicators
- Network requests completing
- Dynamic content appearing

**Identify automation challenges:**

| Challenge Type | Examples | Documentation Needed |
|----------------|----------|----------------------|
| Timing | Loading indicators, API latency | Wait strategy, timeout values |
| Dynamic behavior | Lazy loading, infinite scroll | Detection method, triggering conditions |
| State management | Session state, authentication | Setup requirements, state preservation |
| Flakiness potential | Race conditions, async operations | Retry strategy, verification approach |
| Alternative paths | Error conditions, edge cases | Validation strategies for each path |

**Document solutions proactively:**
- For each identified challenge, recommend a solution
- Specify wait conditions, retry logic, or verification alternatives
- Note technology-specific best practices

### Phase 3: Review & Validation

**After completing all exploration steps:**

1. **Review complete interaction flow:**
   - [ ] All steps documented with clear descriptions
   - [ ] Each step has associated action and expected outcome
   - [ ] Business context captured for each interaction

2. **Validate locator/identifier capture:**
   - [ ] All interactive elements have stable identifiers
   - [ ] Locator strategies ranked by stability
   - [ ] Fallback options documented

3. **Confirm challenge identification:**
   - [ ] Timing/synchronization issues noted
   - [ ] Dynamic behaviors documented
   - [ ] Solutions recommended for each challenge
   - [ ] Edge cases and error paths considered

4. **Ensure completeness:**
   - [ ] Flow covers complete test scenario
   - [ ] All user interactions captured
   - [ ] All validation points identified
   - [ ] Prerequisites and setup documented

### Phase 4: Cleanup & Handoff

**Clean up technology-specific resources:**
- Web: Close browser instance
- Mobile: Terminate app using `mobile_terminate_app`
- API: Close connections, revoke temporary tokens

**Prepare exploration report:**
- Complete flow overview (step-by-step summary)
- Element/endpoint inventory (all identifiers captured)
- Challenge/solution matrix (identified issues and recommendations)
- Technology-specific notes (platform differences, configurations)

**Handoff to code generation:**
- Provide documented exploration data to `code-generation` skill
- Ensure all three objectives (steps, locators, challenges) are met
- Mark exploration as complete

---

## Exploration Quality Checklist

Before proceeding to code generation, verify:

- [ ] **Objective 1: Execution Steps Captured**
  - [ ] Complete flow documented from start to finish
  - [ ] Each step has clear description
  - [ ] Expected outcomes specified
  - [ ] Business context provided

- [ ] **Objective 2: Stable Locators Extracted**
  - [ ] All interactive elements identified
  - [ ] Multiple strategies explored per element
  - [ ] Most stable strategy chosen
  - [ ] Stability ranking applied
  - [ ] Fallback options documented

- [ ] **Objective 3: Automation Challenges Identified**
  - [ ] Timing issues spotted and documented
  - [ ] Dynamic behaviors noted
  - [ ] Flakiness sources recognized
  - [ ] Solutions recommended for each challenge
  - [ ] Edge cases considered

- [ ] **General Completeness**
  - [ ] All user interactions captured
  - [ ] All validation points identified
  - [ ] Technology-specific considerations noted
  - [ ] Resources cleaned up properly

**If ANY item is incomplete:** Return to exploration and complete it. Do not proceed to code generation until all objectives are met.

---

## Documentation Best Practices

### During Exploration

**Continuously document:**
- Each interaction step with business context
- Element locators discovered (with stability ranking)
- Observed behaviors (animations, delays, dynamic content)
- Validation points and expected outcomes
- Identified automation challenges
- Recommended solutions

**Format:**
```
Step [N]: [Action Description]
Context: [Business reason for this step]
Target: [Element/endpoint identifier]
Locator Strategy: [Chosen approach]
Stability: [High/Medium/Low]
Fallback: [Alternative locator if primary fails]
Action: [Tool/method used]
Expected: [Expected outcome]
Challenge: [If any potential issue identified]
Solution: [Recommended approach to handle challenge]
```

### Post-Exploration Summary

**Provide to code generation skill:**

1. **Flow Overview:**
   - High-level summary of complete flow
   - Number of steps
   - Major phases (e.g., login, navigation, action, verification)

2. **Element/Endpoint Inventory:**
   - Table of all identifiers with strategies
   - Platform/technology differences (if applicable)

3. **Challenge/Solution Matrix:**
   - Identified issues
   - Recommended solutions
   - Implementation guidance

4. **Implementation Notes:**
   - Technology-specific considerations
   - Configuration requirements
   - Test data needs

### Desktop verification (mandatory for desktop targets)

Capture enough post-action evidence to distinguish success, no-op, and wrong-target interactions. Follow the verification and resilient ranked localization rules in [desktop-automation/SKILL.md](../desktop-automation/SKILL.md).

**Wait when required:** Use the technology-specific readiness signal before capturing verification evidence.

---

## Interaction with Technology Skills

### Technology skills provide:
- Specific tools to use
- Platform-specific locator strategies
- Technology-specific challenges and solutions
- Context management rules (tabs, contexts, connections)

### This skill provides:
- The common exploration workflow
- The three objectives framework
- General documentation patterns
- Quality checklist

**Usage:** Technology skills implement this pattern with their specific tools and strategies.

---

## Common Pitfalls (All Technologies)

1. **Incomplete exploration**: Stopping before all three objectives are met
2. **Skipping challenge identification**: Only capturing steps and locators, missing issues
3. **Weak locators**: Choosing convenient but unstable identifiers
4. **Missing documentation**: Not recording rationale for decisions
5. **No verification**: Not confirming actions succeeded
6. **Assuming outcomes**: Not capturing actual post-action state
7. **Rushing to code**: Generating code before exploration is complete

---

## Example: Exploration Documentation Template

```markdown
# Exploration Report: [Test Scenario Name]

## Overview
- **Technology**: [Web/Mobile/API]
- **Target**: [URL/App/Endpoint]
- **Objective**: [What we're testing]
- **Expected Outcome**: [Success criteria]

## Exploration Summary
- **Total Steps**: [N]
- **Elements Identified**: [N]
- **Challenges Found**: [N]
- **Duration**: [Time]

## Detailed Flow

### Step 1: [Action Description]
- **Context**: Why this step is needed
- **Target**: Element/endpoint identifier
- **Locator**: [Chosen strategy] (Stability: High)
- **Action**: [Tool used]
- **Expected**: [Outcome]
- **Actual**: [What happened]
- **Challenge**: [If any]
- **Solution**: [Recommended approach]

[Repeat for each step]

## Element/Endpoint Inventory

| Step | Type | Identifier | Stability | Fallback |
|------|------|------------|-----------|----------|
| 1 | Button | data-testid="login-btn" | High | aria-label="Login" |
| 2 | Input | id="username" | High | name="username" |
[...]

## Challenges & Solutions

| Challenge | Impact | Recommended Solution | Implementation Notes |
|-----------|--------|----------------------|----------------------|
| Login delay | Tests may timeout | Wait for dashboard element | Use explicit wait, timeout 10s |
| Dynamic list | Elements not immediately visible | Scroll until found | Implement scroll-to-element utility |
[...]

## Implementation Recommendations
- [Technology-specific notes]
- [Configuration requirements]
- [Test data needs]
- [Environment considerations]

## Completion Status
- [x] Objective 1: Execution steps captured
- [x] Objective 2: Stable locators extracted
- [x] Objective 3: Automation challenges identified
- [x] Resources cleaned up
- [x] Ready for code generation

---
Explored by: [Agent]
Date: [Date]
```

---

**End of Live Exploration Workflow Skill**

This pattern applies to all automation technologies. Technology-specific skills provide the implementation details for their context.
