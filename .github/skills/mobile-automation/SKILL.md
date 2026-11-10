---
name: mobile-automation
description: "Use when automating Android or iOS applications, devices, emulators, and Appium-based mobile test flows."
argument-hint: "Describe the mobile app, platform, device or emulator, and target flow"
---

# Mobile Automation with Appium

## Purpose

This skill provides specialized knowledge for mobile automation using **mobile-mcp** (MCP server for exploration) and **Appium** (test framework for generated code).

**Key Distinction:**
- **mobile-mcp**: MCP server providing live exploration tools (`mobile_launch_app`, `mobile_list_elements_on_screen`, `mobile_click_on_screen_at_coordinates`, etc.)
- **Appium**: Mobile test automation framework used in generated code (Java + Appium, Python + Appium, etc.)

This skill covers device/emulator management, mobile app context handling, platform-specific element identification strategies, and mobile automation best practices for Android and iOS.

## When to Use

Activate this skill when:
- User mentions mobile, app, Android, iOS, device, or emulator
- Project contains Appium or Mobile test dependencies
- Test involves mobile application interactions
- User explicitly requests mobile automation

## Prerequisites

Before using this skill:
- Project analysis completed (via `project-analysis` skill)
- **mobile-mcp server available and functional** (provides exploration tools)
- Target platform identified (Android or iOS)
- App package/bundle ID or APK/IPA path available
- Device or emulator available and connected

**Execution Default:** Use a visible real device, emulator, or simulator session by default for both live exploration and generated automation projects. Only use hidden or headless-style execution when the user explicitly requests it.

---

## Mobile Context & Environment Management

### Platform Handling (Android vs iOS)

**Detection:**
- User explicitly mentions platform
- Project configuration specifies platform
- App file extension (.apk for Android, .ipa for iOS)

**Platform-Specific Considerations:**

| Aspect | Android | iOS |
|--------|---------|-----|
| Automation Engine | UiAutomator2 | XCUITest |
| Locator Preferences | resource-id > content-desc > text | accessibility id > name > label |
| Package Format | APK | IPA |
| Identifier | Package name (com.example.app) | Bundle ID (com.example.app) |
| Permissions | Runtime permissions (dialogs) | Pre-install permissions + runtime |
| Contexts | NATIVE_APP, WEBVIEW | NATIVE_APP, WEBVIEW |

**Document platform differences:**
- Note when behavior differs between platforms
- Provide platform-specific implementations when needed
- Consider cross-platform abstraction for shared logic

### App Context Switching

**Context Types:**

1. **NATIVE_APP (Default)**
   - Native UI elements
   - Platform-specific controls
   - Default context for native apps

2. **WEBVIEW**
   - Embedded web content (hybrid apps)
   - HTML elements inside WebView component
   - Requires explicit context switch

3. **Multiple Apps**
   - Scenarios requiring multiple apps (e.g., SMS verification, deep linking)
   - Switch between apps during test

**Rules:**
- Always verify current context before interactions
- Switch context explicitly when interacting with WebView content
- Return to original context after context-specific operations
- Document context switches in exploration notes

**Example Scenarios:**
- Hybrid app with web login form (switch to WEBVIEW)
- Deep linking that opens another app
- SMS verification requiring SMS app

### Device/Emulator Management

**Required Capabilities:**
```json
{
  "platformName": "Android",
  "platformVersion": "12.0",
  "deviceName": "Pixel_5_Emulator",
  "app": "/path/to/app.apk",
  "appPackage": "com.example.app",
  "appActivity": ".MainActivity",
  "automationName": "UiAutomator2",
  "noReset": false
}
```

**Rules:**
- Document all required capabilities
- Support both real devices and emulators/simulators
- Prefer sessions the user can observe during execution; do not default to hidden/background device execution
- Verify device connection before starting exploration (use `mobile_list_available_devices`)
- Capture device logs for debugging
- Handle device-specific behaviors (screen sizes, OS versions)

**Device Farm Integration:**
- Support local execution
- Support cloud providers (BrowserStack, Sauce Labs, AWS Device Farm)
- Allow remote execution configuration

### App State Management

**App Lifecycle:**
- **Installation**: Install app before first run
- **Launch**: Launch app using `mobile_launch_app`
- **Reset**: Clear app data between tests (or reinstall)
- **Background/Foreground**: Handle app state transitions
- **Termination**: Properly terminate app using `mobile_terminate_app`

**Permissions:**
- Document app permissions required
- Handle permission dialogs during first launch
- Automate permission grants where possible

**Deep Linking & Push Notifications:**
- Test deep link handling
- Verify push notification interactions
- Handle background app launches

### Network & Location

**Network Simulation:**
- Airplane mode testing
- Slow network simulation
- Offline mode testing

**Location Services:**
- Set GPS coordinates for location-based features
- Test location permission dialogs
- Verify map-based interactions

**Rules:**
- Document network dependencies
- Test offline scenarios when relevant
- Handle location permission requests

---

## Live Mobile App Exploration Workflow

### Initialization

**Request from user:**
- Platform (Android or iOS) - required
- App path (APK/IPA) or package/bundle ID - required
- Device/emulator details (or use available device)
- Test objective (what should be validated?)
- Expected business outcome (what does success look like?)
- Authentication requirements (if any)

**Setup:**
1. List available devices using `mobile_list_available_devices`
2. Launch app on device/emulator using `mobile_launch_app`
3. Capture initial screen structure using `mobile_list_elements_on_screen`
4. Begin documenting interaction flow

**Note:** Exploration uses **mobile-mcp server** for live discovery (mobile_* tools). This is separate from later code generation which uses Appium framework. After completing exploration, terminate the app using `mobile_terminate_app`.

**Generated Code Rule:** When generating or updating mobile automation projects, default to visible device/emulator/simulator execution. Only configure hidden or headless-style execution when the user explicitly asks for it.

### Exploration Loop (Per Step)

#### A. Screen Analysis

**Capture screen structure:**
- Use `mobile_list_elements_on_screen` to get page source hierarchy
- Identify all interactive elements (buttons, text fields, lists, switches, etc.)
- Note dynamic elements (loading indicators, animations, toasts)
- Take screenshot using `mobile_take_screenshot` for visual reference
- Record current screen state

**Look for:**
- Loading indicators or splash screens
- Lazy-loaded content (scrollable lists)
- Animations or transitions
- Platform-specific UI elements (TabBar on iOS, NavigationDrawer on Android)

#### B. Element Identification & Locator Strategy

**Extract from page source:**
- Element attributes (resource-id, content-desc, text, class, bounds, accessibility id, name, label)
- Element type (button, textField, scrollView, etc.)
- Element hierarchy (parent/child relationships)
- Element state (enabled, visible, selected)

**Rank locators by stability:**

**Android:**
1. **resource-id** - Most stable, purpose-built identifier
2. **content-desc** - Accessibility description, stable
3. **text** - Visible text, less stable (changes with content/localization)
4. **xpath** - Last resort, brittle (avoid if possible)

**iOS:**
1. **accessibility id** - Most stable, purpose-built identifier
2. **name** - Element name, stable
3. **label** - Visible label, less stable
4. **xpath** - Last resort, brittle (avoid if possible)

**Document chosen locator and rationale:**
```
Element: Login button
Platform: Android
Locator: resource-id="com.example.app:id/login_button"
Rationale: Explicit resource ID, most stable option
Fallback: content-desc="Login"
```

**Red Flags (avoid these locators):**
- XPath based solely on hierarchy
- Positional selectors (nth element)
- Locators using bounds/coordinates only
- Class-based selectors without additional identifiers

#### C. Action Execution

**Choose appropriate mobile-mcp tool:**

| Action | mobile-mcp Tool | Parameters |
|--------|-----------------|------------|
| Tap element | `mobile_click_on_screen_at_coordinates` | x, y, description |
| Type text | `mobile_type_keys` | keys, description |
| Swipe | `mobile_swipe_on_screen` | start_x, start_y, end_x, end_y |
| Long press | `mobile_long_press_on_screen_at_coordinates` | x, y, duration, description |
| Double tap | `mobile_double_tap_on_screen` | x, y, description |
| Press button | `mobile_press_button` | button_name (Home, Back) |

**Always provide:**
- Human-readable description of the action
- Exact coordinates or element reference from screen analysis
- Expected outcome

**Document the action:**
```
Step 3: Tap "Login" button
Tool: mobile_click_on_screen_at_coordinates
Element: center coordinates from bounds (resource-id="login_button")
Coordinates: x=540, y=1200
Expected: Navigate to home screen
```

#### D. Verification & Problem Identification

**Post-action verification:**
1. Capture new screen structure using `mobile_list_elements_on_screen`
2. Verify expected state change:
   - New screen visible?
   - New elements appeared?
   - Error messages?
   - Success indicators (toast, snackbar)?
3. Wait explicitly when required (for animations, network calls, splash screens)

**Identify potential automation issues:**

| Issue Type | Example | Solution |
|------------|---------|----------|
| Timing | Splash screen delays app load | Wait for splash to disappear |
| Animations | Element slides into view | Wait for animation completion |
| Lazy loading | List items load on scroll | Scroll to load, wait for elements |
| Permission dialogs | Camera/location permissions | Handle platform-specific dialogs |
| Keyboard | Keyboard covers elements | Dismiss keyboard before interaction |
| Platform differences | Different UI on Android vs iOS | Document differences, provide platform-specific logic |

**Document challenges and solutions:**
```
Challenge: Submit button disabled until form validation completes
Solution: Wait for button to become enabled before tapping
Code: Wait for enabled state or check element attributes
Alternative: Validate form fields first, then tap
```

### Exploration Completion

After all exploration steps:

1. **Review complete interaction flow:**
   - [ ] All steps documented with clear descriptions
   - [ ] All element locators captured with stability rankings
   - [ ] All potential issues identified
   - [ ] Solutions recommended for each issue
   - [ ] Platform-specific behaviors noted

2. **Terminate app:**
   - Use `mobile_terminate_app` to clean up

3. **Prepare exploration report:**
   - Complete flow overview
   - Element locator table (with platform differences)
   - Identified issues and solutions
   - Recommended test implementation approach
   - Platform-specific considerations

4. **Proceed to code generation:**
   - Hand off documented exploration data to `code-generation` skill
   - Ensure all decisions are documented and traceable

---

## Mobile-Specific Challenges & Solutions

### Gestures & Touch Actions

**Swipe:**
- Document direction (left, right, up, down)
- Specify start/end coordinates
- Note speed (fast vs slow swipe)
- Common use: Page transitions, drawer open/close, dismiss notifications

**Scroll:**
- Use `scrollIntoView` utility when available
- For long lists: scroll to find element, then interact
- Consider lazy loading: elements may not exist until scrolled into view

**Long Press:**
- Specify duration (typically 1000ms+)
- Common use: Context menus, drag initiation

**Pinch/Zoom:**
- Document gesture coordinates
- Common use: Maps, image viewers

**Drag & Drop:**
- Capture source and target elements
- Document drag path

**Always verify gesture completion:**
- Check screen state changed as expected
- Use visual or element-based verification

### List & ScrollView Handling

**Challenges:**
- Long lists with many items
- Lazy loading (items load as you scroll)
- Performance (loading large datasets)

**Solutions:**
- **Scroll to element**: Implement scroll-until-found strategy
- **Use stable identifiers**: resource-id or content-desc for list items
- **Avoid index-based selection**: Brittle, breaks if list order changes
- **Verify item count**: Check expected number of items loaded

**Example approach:**
```
1. Get initial element count
2. Scroll down
3. Wait for new elements to load
4. Repeat until target element found or end reached
```

### Native vs Hybrid Apps

**Native Apps:**
- All UI is platform-native
- Use native locators only
- No context switching needed

**Hybrid Apps:**
- Mix of native and web content
- **Switch context to WEBVIEW** for web content
- Document which screens are native vs web
- Provide utility methods for context switching

**Detection:**
- Check available contexts
- Look for WebView element in page source
- User may explicitly indicate hybrid nature

**Best Practice:**
- Create abstraction layer that handles context switching transparently
- Document context requirements per screen

### Permissions & System Dialogs

**Types:**
- Runtime permissions (camera, location, notifications, contacts, etc.)
- System dialogs (update prompts, connectivity warnings)
- Platform-specific dialogs

**Handling:**

**Android (UiAutomator2):**
- Can interact with system dialogs
- Use resource-id from android package
- Example: `com.android.packageinstaller:id/permission_allow_button`

**iOS (XCUITest):**
- XCUITest alert handling
- Can interact with system permission alerts
- Example: "Allow" button in permission alert

**Document:**
- Which permissions are needed
- When they are requested
- How to handle in automation

### Keyboard & Input Handling

**Challenges:**
- Keyboard covers part of screen
- Different keyboard types (numeric, email, phone)
- Autocomplete/suggestions

**Solutions:**
- **Hide keyboard** after text input (platform-specific):
  - Android: Press Back button
  - iOS: Tap outside text field or "Done" button
- **Handle autocomplete**: Either accept or dismiss suggestions
- **Verify input**: Check text field value after typing

**Keyboard Types:**
- Document expected keyboard type (helps validate field configuration)
- Verify correct keyboard appears (e.g., numeric for phone number)

### App Lifecycle Management

**States:**
- **Foreground**: App active and visible
- **Background**: App suspended but in memory
- **Terminated**: App fully closed

**Test scenarios:**
- App backgrounding (Home button press)
- App resume after background
- App interruptions (incoming call, notification)
- Lock screen behavior

**Implementation:**
- Use `mobile_press_button` with "Home" to background app
- Launch app again to test resume
- Verify app state persists (or resets) as expected

### Device Orientation

**Orientations:**
- **Portrait**: Default for most apps
- **Landscape**: Rotation support

**Testing:**
- Set orientation using `mobile_set_orientation`
- Verify layout changes correctly
- Check element positions adjust
- Ensure functionality works in both orientations

**Document:**
- Which orientations are supported
- If layout significantly differs
- Orientation requirements per screen

### Performance & Resource Management

**Best practices:**
- Close app sessions properly (use `mobile_terminate_app`)
- Reset app state between tests when needed (reinstall or clear data)
- Monitor test execution time (mobile tests typically slower than web)
- Optimize waits and synchronization

**Resource cleanup:**
- Terminate apps after tests
- Clear app data between test runs (if required)
- Close emulators if not reused

---

## Mobile Locator Best Practices

### Locator Stability Hierarchy

**Android (Priority order):**
1. **resource-id** (e.g., `com.example.app:id/login_button`)
2. **content-desc** (accessibility description)
3. **text** (visible text, less stable due to localization)
4. **xpath** (last resort, very brittle)

**iOS (Priority order):**
1. **accessibility id** (purpose-built identifier)
2. **name** (element name)
3. **label** (visible label)
4. **xpath** (last resort, very brittle)

### Locator Construction Examples

**Good (Android):**
```java
// Resource ID
driver.findElement(By.id("com.example.app:id/login_button")).click();

// Content description
driver.findElement(By.accessibilityId("Login button")).click();

// Fallback to text
driver.findElement(By.xpath("//*[@text='Login']")).click();
```

**Good (iOS):**
```java
// Accessibility ID
driver.findElement(By.accessibilityId("login_button")).click();

// Name
driver.findElement(By.name("Login")).click();

// Label
driver.findElement(By.xpath("//*[@label='Login']")).click();
```

**Avoid:**
```java
// XPath based on hierarchy
driver.findElement(By.xpath("//android.widget.LinearLayout[1]/android.widget.Button[2]")).click(); // ❌

// Coordinates only (without element verification)
driver.tap(540, 1200); // ❌ No element validation

// Index-based selection in list
driver.findElements(By.className("android.widget.TextView")).get(3).click(); // ❌
```

### Combining Strategies

When no single strong locator exists:
```java
// Combine class and text
driver.findElement(By.xpath("//android.widget.Button[@text='Submit']")).click();

// Find within parent
WebElement parent = driver.findElement(By.id("com.example.app:id/form_container"));
parent.findElement(By.accessibilityId("submit_button")).click();
```

---

## Mobile Project Initialization

If no project exists, create a new mobile automation project:

### Project Structure

```
project-root/
├── src/
│   └── test/
│       ├── java/
│       │   ├── screens/         # Screen objects (mobile equivalent of page objects)
│       │   ├── steps/           # Cucumber step definitions
│       │   ├── runners/         # Test runners
│       │   └── utils/           # Helper utilities
│       └── resources/
│           ├── features/        # Cucumber feature files
│           ├── apps/            # APK/IPA files
│           └── capabilities/    # Device capability configs
├── pom.xml                      # Maven (Java)
├── package.json                 # npm (JS/TS)
├── requirements.txt             # pip (Python)
└── .env                         # Environment variables (app paths, device IDs)
```

### Technology Stack Selection

**Ask user first**, then fallback to defaults:

**Java + Appium + Cucumber (default):**
```xml
<dependencies>
    <dependency>
        <groupId>io.appium</groupId>
        <artifactId>java-client</artifactId>
    </dependency>
    <dependency>
        <groupId>io.cucumber</groupId>
        <artifactId>cucumber-java</artifactId>
    </dependency>
</dependencies>
```

**Java + Appium + TestNG:**
```xml
<dependency>
    <groupId>org.testng</groupId>
    <artifactId>testng</artifactId>
</dependency>
```

**JavaScript/TypeScript + WebdriverIO:**
```json
{
  "dependencies": {
    "@wdio/appium-service": "^8.0.0",
    "webdriverio": "^8.0.0"
  }
}
```

**Python + Appium + Pytest:**
```
Appium-Python-Client==3.1.0
pytest==7.4.0
```

### Capabilities Configuration

**Android Example:**
```json
{
  "platformName": "Android",
  "platformVersion": "12.0",
  "deviceName": "Pixel 5",
  "app": "/path/to/app.apk",
  "appPackage": "com.example.app",
  "appActivity": ".MainActivity",
  "automationName": "UiAutomator2",
  "autoGrantPermissions": true,
  "noReset": false
}
```

**iOS Example:**
```json
{
  "platformName": "iOS",
  "platformVersion": "16.0",
  "deviceName": "iPhone 14",
  "app": "/path/to/app.ipa",
  "bundleId": "com.example.app",
  "automationName": "XCUITest",
  "autoAcceptAlerts": false,
  "noReset": false
}
```

---

## Integration Points

### With Other Skills

- **`live-exploration-workflow`**: This skill implements the mobile-specific version of the common exploration pattern
- **`project-analysis`**: Detects Appium/mobile projects, identifies existing mobile tests
- **`code-generation`**: Receives exploration data (from mobile-mcp), generates Appium test code
- **`execution-validation`**: Executes generated mobile tests, validates results

### With Automation Agent

- Agent loads this skill when mobile technology detected
- Agent ensures **mobile-mcp tools available** before exploration (Phase 0 verification)
- Agent passes exploration findings (from mobile-mcp) to `code-generation` skill
- Agent coordinates between exploration (mobile-mcp tools) and code generation (Appium framework)

### With MCP Tools (mobile-mcp server)

**Primary mobile-mcp tools:**
- `mobile_list_available_devices` - List connected devices/emulators
- `mobile_launch_app` - Launch app on device
- `mobile_list_elements_on_screen` - Capture page source hierarchy
- `mobile_click_on_screen_at_coordinates` - Tap elements
- `mobile_type_keys` - Type text
- `mobile_swipe_on_screen` - Swipe gesture
- `mobile_long_press_on_screen_at_coordinates` - Long press
- `mobile_double_tap_on_screen` - Double tap
- `mobile_press_button` - Press device buttons (Home, Back)
- `mobile_take_screenshot` - Capture visual evidence
- `mobile_terminate_app` - Terminate app
- `mobile_get_orientation` / `mobile_set_orientation` - Handle device rotation

**Note:** All `mobile_*` tools come from the **mobile-mcp server**, not from an "Appium MCP". Appium is the test framework used in generated code, not the MCP server.

---

## Quality Standards (Mobile-Specific)

1. **Locator Stability**: Prioritize resource-id (Android) and accessibility id (iOS)
2. **Wait Strategy**: Always wait explicitly for elements, animations, and network calls
3. **App State**: Clean up between tests (terminate app, clear data, or reinstall)
4. **Screenshots**: Capture on both failure and success
5. **Platform Differences**: Document and handle Android vs iOS differences
6. **Permissions**: Handle permission dialogs appropriately
7. **Gestures**: Verify gestures complete successfully
8. **Cross-platform**: Provide unified abstraction for common functionality when possible

---

## Common Pitfalls

1. **Not verifying mobile-mcp availability**: Attempting exploration without mobile-mcp server running
2. **Not checking device list first**: Launch app without verifying device availability via `mobile_list_available_devices`
3. **Not waiting for animations**: Mobile apps have many animations; wait for completion
4. **Using coordinate-only taps**: Always verify element exists at coordinates first
5. **Ignoring platform differences**: Android and iOS behave differently
6. **Not handling keyboard**: Keyboard can cover elements; dismiss when needed
7. **Brittle XPath locators**: Avoid hierarchy-based XPath; use stable IDs (resource-id, accessibility id)
8. **Not terminating app**: Always clean up resources using `mobile_terminate_app`
9. **Assuming instant transitions**: Screens take time to load; wait explicitly
10. **Hardcoded waits**: Use smart waits based on element state, not fixed delays

---

## Examples

### Example 1: Login Flow Exploration (Android)

**Documented exploration:**
```
Platform: Android

Step 1: Launch app
- Package: com.example.app
- Activity: .MainActivity
- Initial state: Splash screen visible

Step 2: Wait for splash to disappear
- Challenge: 2-second splash animation
- Solution: Wait for login screen elements to appear

Step 3: Identify username field
- Element: EditText
- Locator: resource-id="com.example.app:id/username_input"
- Content-desc: "Username"
- Stability: High (resource ID)

Step 4: Tap username field and type
- Action: mobile_click_on_screen_at_coordinates (focus field)
- Then: mobile_type_keys
- Text: "testuser@example.com"

Step 5: Identify password field
- Element: EditText, input-type="textPassword"
- Locator: resource-id="com.example.app:id/password_input"
- Content-desc: "Password"
- Stability: High (resource ID)

Step 6: Tap password field and type
- Action: mobile_click_on_screen_at_coordinates (focus field)
- Then: mobile_type_keys
- Text: "***" (from environment variable)

Step 7: Dismiss keyboard
- Action: mobile_press_button("Back")
- Reason: Keyboard covers submit button

Step 8: Identify submit button
- Element: Button
- Locator: resource-id="com.example.app:id/login_button"
- Text: "Login"
- Stability: High (resource ID)

Step 9: Tap submit
- Action: mobile_click_on_screen_at_coordinates
- Expected: Navigate to home screen

Step 10: Verify success
- Wait for: Home screen elements visible
- Verify: Welcome message visible
- Element: TextView, text="Welcome, Test User"
```

### Example 2: Handling ScrollView

**Challenge:** Item not visible, need to scroll

**Exploration notes:**
```
Issue: Product list requires scrolling to find item
Observation: List has 50 items, only 10 visible initially
Solution: Scroll until target item found

Implementation:
1. Get initial screen elements
2. Check if target item visible
3. If not, swipe up to scroll down
4. Wait for new elements to load
5. Repeat until found or max scroll reached
6. Tap target item when visible

Code concept:
- Loop with max iterations (prevent infinite scroll)
- Use swipe gesture: from bottom to top
- Wait after each swipe for content to load
- Verify target element after each scroll
```

---

## Important: mobile-mcp vs Appium

**Clarification to avoid confusion:**

- **mobile-mcp**: The MCP server that provides live exploration tools
  - Tools: `mobile_launch_app`, `mobile_list_elements_on_screen`, `mobile_click_on_screen_at_coordinates`, etc.
  - Purpose: Live exploration and interaction with mobile apps during discovery phase
  - When used: During agent's exploration workflow (Phase 2B)

- **Appium**: The mobile test automation framework
  - Libraries: `io.appium:java-client`, `Appium-Python-Client`, `@wdio/appium-service`
  - Purpose: Running generated test code (AndroidDriver, IOSDriver)
  - When used: In generated test code that runs after exploration

**DO NOT confuse "Appium MCP" (doesn't exist) with "mobile-mcp" (the actual MCP server).**

---

**End of Mobile Automation Appium Skill**

Use this skill whenever mobile automation is required. Always follow platform-specific locator preferences and handle mobile-specific challenges appropriately.
