---
name: project-analysis
description: "Use first for an automation task to detect the project stack, frameworks, test assets, and viable execution paths."
argument-hint: "Provide the project path and the automation goal"
---

# Project Analysis

## Purpose

This skill provides systematic workspace analysis to detect existing automation projects, identify technology stacks, locate test files, and make informed decisions about execution vs. exploration.

## When to Use

**ALWAYS use this skill FIRST** in any automation task.

---

## Analysis Workflow

### 1. Workspace Structure Inspection

**Use `list_dir` to inspect:**
```
workspace-root/
├── src/          # Source code
├── test/         # Test code
├── package.json  # npm project
├── pom.xml       # Maven project
├── build.gradle  # Gradle project
├── requirements.txt  # Python project
├── pyproject.toml    # Python (modern)
└── .env          # Environment variables
```

**Check for common test directories:**
- `src/test/`, `test/`, `tests/`, `__tests__/`, `spec/`
- `.github/workflows/` (CI/CD configurations)

### 2. Technology Stack Detection

#### Language Detection

| Indicator | Language |
|-----------|----------|
| `pom.xml`, `.java` files | Java |
| `package.json`, `.js`/`.ts` files | JavaScript/TypeScript |
| `requirements.txt`, `.py` files | Python |
| `build.gradle`, `.kt` files | Kotlin |
| `Gemfile`, `.rb` files | Ruby |

#### Build System Detection

| File | Build System |
|------|--------------|
| `pom.xml` | Maven (Java) |
| `build.gradle` / `build.gradle.kts` | Gradle (Java/Kotlin) |
| `package.json` | npm/yarn (JavaScript/TypeScript) |
| `requirements.txt` / `pyproject.toml` | pip/poetry (Python) |

#### Framework Detection

**Search for dependencies in build files:**

**Web Automation:**
- `playwright`, `@playwright/test` → Playwright (JavaScript/TypeScript)
- `com.microsoft.playwright` → Playwright (Java)
- `playwright` (Python package) → Playwright (Python)
- `selenium-webdriver` → Selenium
- `org.seleniumhq.selenium` → Selenium (Java)

**Mobile Automation:**
- `io.appium:java-client` → Appium (Java)
- `webdriverio`, `@wdio/appium-service` → WebdriverIO (mobile)
- `Appium-Python-Client` → Appium (Python)

**API Automation:**
- `io.rest-assured:rest-assured` → RestAssured (Java)
- `axios`, `supertest` → API clients (JavaScript)
- `requests`, `httpx` → HTTP clients (Python)

**Test Frameworks:**
- `io.cucumber:cucumber-java` → Cucumber (Java)
- `@cucumber/cucumber` → Cucumber (JavaScript)
- `pytest`, `unittest` → Pytest/unittest (Python)
- `org.testng:testng` → TestNG (Java)
- `junit` → JUnit (Java)
- `jest`, `mocha`, `vitest` → JavaScript test frameworks

### 3. Locate Existing Test Assets

**Search for:**

**Test files:**
```bash
# Search patterns
**/*Test.java       # Java tests
**/*Spec.js         # JavaScript specs
**/*_test.py        # Python tests
**/*.feature        # Cucumber features
**/test_*.py        # Python test convention
```

**Page/Screen Objects:**
```bash
**/pages/**         # Web page objects
**/screens/**       # Mobile screen objects
**/page_objects/**  # Alternative naming
```

**Step Definitions:**
```bash
**/steps/**         # Cucumber step definitions
**/step_definitions/**
```

**Utilities & Helpers:**
```bash
**/utils/**
**/helpers/**
**/support/**
```

**Configuration Files:**
```bash
playwright.config.js    # Playwright config
wdio.conf.js           # WebdriverIO config
pytest.ini             # Pytest config
testng.xml             # TestNG config
cucumber.properties    # Cucumber config
```

**Use `grep_search` to find:**
- Test annotations (`@Test`, `describe(`, `def test_`)
- Cucumber keywords (`@Given`, `@When`, `@Then`)
- Automation tool imports (`from playwright`, `import io.appium`)

### 4. Analyze Test Coverage

**Compare user request with existing tests:**

1. **Extract test intent from user request:**
   - What feature/flow needs testing?
   - What actions are involved?
   - What validations are needed?

2. **Search existing tests:**
   - Use `semantic_search` for related functionality
   - Use `grep_search` for specific keywords
   - Check feature files for matching scenarios

3. **Determine coverage status:**
   - **Full coverage**: Exact test already exists
   - **Partial coverage**: Related test exists, needs extension
   - **No coverage**: New test needed

### 5. Decision: Execute vs. Explore

**If existing test found:**
→ **EXECUTE mode**
- Run the existing test
- Analyze results
- Fix if failing
- Extend if needed

**If no existing test found:**
→ **EXPLORATION mode**
- Proceed to live exploration workflow
- Use technology-appropriate skill
- Document and generate new test

**If partial coverage:**
→ **HYBRID mode**
- Execute existing test first
- Identify gap
- Explore additional functionality
- Extend existing test

---

## Analysis Output Format

**Provide structured analysis:**

```markdown
# Project Analysis Results

## Technology Stack
- **Language**: [Java/JavaScript/Python/etc.]
- **Build System**: [Maven/npm/pip/etc.]
- **Automation Frameworks**:
  - Web: [Playwright/Selenium/none]
  - Mobile: [Appium/none]
  - API: [RestAssured/axios/requests/none]
- **Test Framework**: [Cucumber/TestNG/Jest/Pytest/etc.]

## Project Structure
- **Test Directory**: [path]
- **Page/Screen Objects**: [path or "Not found"]
- **Step Definitions**: [path or "Not found"]
- **Utilities**: [path or "Not found"]
- **Configuration**: [files found]

## Existing Test Coverage
- **Related Tests Found**: [count]
  - [test file 1]: [description]
  - [test file 2]: [description]
- **Coverage Status**: [Full/Partial/None]

## Recommendation
- **Mode**: [Execute/Explore/Hybrid]
- **Rationale**: [Why this mode was chosen]
- **Next Steps**: [What to do next]
- **Required Skills**: [List of skills to invoke]
```

---

## Technology-Specific Analysis

### Web Projects

**Look for:**
- Browser automation dependencies
- Page object pattern
- Playwright/Selenium configuration
- Test files with browser interactions

**Indicators:**
- `browser.newPage()`, `page.goto()` (Playwright)
- `driver.get()`, `WebDriver` (Selenium)
- URL navigation in tests

### Mobile Projects

**Look for:**
- Appium dependencies
- Mobile-specific capabilities files
- APK/IPA files in project
- Screen object pattern

**Indicators:**
- `DesiredCapabilities`, `AndroidDriver`, `IOSDriver`
- `platformName`, `deviceName` in configs
- Mobile gesture code (swipe, tap)

### API Projects

**Look for:**
- HTTP client dependencies
- OpenAPI/Swagger files
- Postman collections
- API endpoint definitions

**Indicators:**
- `RestAssured`, `axios`, `requests` imports
- HTTP method calls (GET, POST, PUT, DELETE)
- JSON schema validation

---

## Integration with Technology Skills

**After analysis:**

1. **Identify technology type** (web, mobile, API, or combination)
2. **Invoke appropriate technology skills:**
   - Web → `web-automation-playwright`
   - Mobile → `mobile-automation-appium`
   - API → `api-automation`
3. **Provide analysis results** to downstream skills
4. **Inform technology stack selection** for code generation

---

## Common Patterns by Framework

### Cucumber Projects

**Structure:**
```
src/test/
├── resources/features/    # .feature files
└── java/
    ├── steps/             # Step definitions
    ├── pages/             # Page objects
    └── runners/           # Test runners
```

**Detection:**
- Feature files (`.feature`)
- Cucumber dependencies
- `@Given`, `@When`, `@Then` annotations

### Playwright Projects

**Structure:**
```
tests/                     # Test files
├── pages/                 # Page object models
├── fixtures/              # Test fixtures
└── playwright.config.js   # Configuration
```

**Detection:**
- `playwright.config.js`
- `@playwright/test` imports
- `test()`, `expect()` usage

### Appium Projects

**Structure:**
```
src/test/
├── java/
│   ├── screens/           # Screen objects
│   ├── tests/             # Test classes
│   └── utils/             # Helpers (capabilities, driver factory)
└── resources/
    ├── apps/              # APK/IPA files
    └── capabilities/      # Capability configs
```

**Detection:**
- Appium dependencies
- `AndroidDriver`, `IOSDriver`
- Mobile capabilities configuration

---

## Example Analysis

**User Request:** "Create automation for login flow"

**Analysis Process:**
1. Inspect workspace → Found Maven Java project
2. Check dependencies → Playwright + Cucumber found
3. Locate tests → `src/test/resources/features/` contains feature files
4. Search for "login" → Found `login.feature` with login scenarios
5. Check coverage → Existing test covers basic login, not MFA login

**Analysis Output:**
```markdown
# Project Analysis Results

## Technology Stack
- **Language**: Java
- **Build System**: Maven
- **Automation Frameworks**:
  - Web: Playwright
  - Mobile: none
  - API: none
- **Test Framework**: Cucumber (BDD)

## Project Structure
- **Test Directory**: src/test/
- **Page Objects**: src/test/java/pages/
- **Step Definitions**: src/test/java/steps/
- **Feature Files**: src/test/resources/features/
- **Configuration**: playwright.config.js, cucumber.properties

## Existing Test Coverage
- **Related Tests Found**: 1
  - login.feature: Basic username/password login test
- **Coverage Status**: Partial (MFA login not covered)

## Recommendation
- **Mode**: Hybrid (Execute existing + Explore MFA flow)
- **Rationale**: Basic login exists and should be verified. MFA flow needs new exploration.
- **Next Steps**:
  1. Execute existing login.feature test
  2. If passing, proceed to explore MFA flow
  3. Extend login.feature with MFA scenario
- **Required Skills**: 
  - `web-automation-playwright` (web technology)
  - `live-exploration-workflow` (for MFA exploration)
  - `code-generation` (to extend test)
  - `execution-validation` (to run and validate)
```

---

## Quality Standards

- **Thoroughness**: Check all common locations and patterns
- **Accuracy**: Verify technology detection with multiple indicators
- **Clarity**: Provide clear, actionable recommendations
- **Traceability**: Document what was found and where

---

## Common Pitfalls

1. **Stopping too early**: Not checking all possible test locations
2. **Missing mixed projects**: Projects with multiple technologies (web + API)
3. **Ignoring configuration**: Not checking config files for framework details
4. **Shallow search**: Not looking for related tests via semantic search
5. **Assuming absence**: Not found ≠ doesn't exist; may be non-standard structure

---

**End of Project Analysis Skill**

Always run this analysis FIRST before any automation work. It informs all downstream decisions.
