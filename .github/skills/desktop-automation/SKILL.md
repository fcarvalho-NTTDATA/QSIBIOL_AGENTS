---
name: desktop-automation
description: "Use when automating Windows desktop or native GUI applications with Desktop Automation MCP tools."
argument-hint: "Describe the desktop application, target flow, and available environment"
---

# Desktop Automation with Desktop MCP

## Purpose

This skill provides specialized knowledge for desktop automation using **desktop-automation-mcp** (MCP server for exploration) and **desktop automation frameworks** (for generated code).

**Key Distinction:**
- **desktop-automation-mcp**: MCP server providing live exploration tools (`screen_capture`, `mouse_click`, `mouse_move`, `keyboard_type`, `keyboard_press`, `get_screen_size`)
- **Desktop Automation Frameworks**: Frameworks used in generated code (PyAutoGUI, AutoIt, Sikuli, pywinauto, etc.)

This skill covers screen interaction patterns, element identification through visual recognition, keyboard/mouse control strategies, window management, and desktop automation best practices for Windows applications.

## When to Use

Activate this skill when:
- User mentions desktop, Windows application, native app, or GUI automation
- Project involves desktop application testing
- Test requires keyboard/mouse interactions with desktop applications
- User explicitly requests desktop automation

## Prerequisites

Before using this skill:
- Project analysis completed (via `project-analysis` skill)
- **desktop-automation-mcp server available and functional** (provides exploration tools)
- Target application identified (executable path, name, or installer)
- Windows environment available

**Execution Default:** Use visible screen capture and real-time interaction by default for both live exploration and generated automation projects. Actions should be visually observable.

---

## Desktop Context & Environment Management

### Application State Management

**Application Lifecycle:**

1. **Launch Application**
   - Start application via executable path
   - Wait for application to be ready (window appears)
   - Verify application launched successfully
   - Capture initial state

2. **Window Focus Management**
   - Ensure target window has focus before interactions
   - Switch focus when dealing with multiple windows
   - Handle window minimization/maximization
   - Restore window state if needed

3. **Application Termination**
   - Close application gracefully (File → Exit, Alt+F4)
   - Force close if graceful close fails
   - Clean up resources
   - Verify application closed

**Rules:**
- Always verify window focus before interactions
- Document window state changes
- Handle unexpected popups/dialogs
- Track active windows throughout test flow

### Screen Resolution & Scaling

**Considerations:**
- Different screen resolutions affect element positions
- Windows scaling (100%, 125%, 150%, etc.) impacts coordinates
- Multi-monitor setups require screen identification

**Best Practices:**
- Capture screen size at test start using `get_screen_size`
- Document test resolution requirements
- Use relative positioning when possible
- Test on target resolution if coordinates are critical
- Consider scaling factors in coordinate calculations

**Example:**
```python
# Capture screen size
screen_width, screen_height = get_screen_size()

# Calculate relative position (center of screen)
center_x = screen_width // 2
center_y = screen_height // 2
```

### Multi-Window Handling

**Common Scenarios:**
- Main application window + dialog boxes
- Child windows (settings, preferences)
- Modal dialogs (save, confirm, error)
- System dialogs (file picker, print dialog)

**Rules:**
- Identify which window is active
- Switch focus explicitly when needed
- Wait for new windows to appear
- Handle popup dialogs immediately
- Return focus to main window after dialog operations

**Detection Strategies:**
- Screen capture before/after action
- Look for visual indicators (window titles, icons)
- Verify expected window content appears

---

## Element Identification & Localization Strategies

Desktop automation relies on **visual recognition** and **coordinate-based interaction** rather than DOM/accessibility tree.

### Primary Identification Methods

#### 1. Visual Recognition (OCR + Image Matching)

**OCR (Optical Character Recognition):**
- Identify UI elements by visible text
- Read button labels, menu items, field names
- Extract text from application for validation

**Advantages:**
- Works with any application
- No special hooks or accessibility APIs needed
- Intuitive (matches what user sees)

**Limitations:**
- Font rendering variations affect accuracy
- Text clarity depends on screen resolution
- Language-specific considerations

**Best Practices:**
- Capture clear screenshots during exploration
- Use high-contrast text areas when possible
- Verify OCR accuracy during exploration
- Consider font size and scaling

**Image Matching:**
- Identify UI elements by visual appearance
- Match buttons, icons, logos
- Template matching for repeated elements

**Advantages:**
- Works for non-text elements (icons, images)
- Reliable for consistent UI rendering
- Language-independent

**Limitations:**
- Sensitive to theme changes (dark mode, high contrast)
- Resolution-dependent
- Requires reference images

**Best Practices:**
- Capture reference images during exploration
- Store multiple variants for different themes
- Use fuzzy matching for slight variations
- Update reference images when UI changes

#### 2. Coordinate-Based Positioning

**Absolute Coordinates:**
- Fixed screen positions (x, y)
- Specific pixel locations

**Advantages:**
- Direct, fast interaction
- No image processing needed

**Limitations:**
- Brittle (breaks with UI changes, resolution changes)
- Not portable across environments
- Window position affects coordinates

**Best Practices:**
- Avoid absolute coordinates when possible
- Use only when element position is guaranteed stable
- Document resolution/scaling requirements
- Consider window position offset

**Relative Coordinates:**
- Position relative to reference points
- Offset from window edges or known elements

**Advantages:**
- More resilient to window repositioning
- Adaptable to different screen sizes

**Best Practices:**
- Identify stable reference points (window corners, specific UI elements)
- Calculate offsets during exploration
- Test with window in different positions

#### 3. Region-Based Interaction

**Strategy:**
- Define regions of interest (ROI)
- Search for elements within specific screen areas
- Reduce search space for better performance

**Example Regions:**
- Menu bar (top of window)
- Toolbar (below menu bar)
- Main content area (center)
- Status bar (bottom)
- Dialog boxes (modal overlays)

**Best Practices:**
- Capture and define regions during exploration
- Use regions to narrow element search
- Document region boundaries
- Verify region contains expected elements

---

## Interaction Patterns

### Mouse Operations

#### Click Operations

**Available:**
- `mouse_click(x, y, button='left', clicks=1)`
  - Left click, right click, double click
  - Middle click (mouse wheel)
  - Click at specific coordinates

**Patterns:**
- **Single Click**: Button press, select item, activate element
- **Double Click**: Open file, launch application, edit field
- **Right Click**: Context menu, additional options

**Best Practices:**
- Move mouse to position first (using `mouse_move`)
- Small delay between move and click (let UI settle)
- Verify element at position before clicking
- Handle cases where click may open new windows/dialogs

**Example:**
```python
# Move to position
mouse_move(x=350, y=200)
time.sleep(0.3)  # Short delay

# Click
mouse_click(x=350, y=200, button='left', clicks=1)
```

#### Drag and Drop

**Pattern:**
1. Move mouse to source position
2. Press mouse button (click and hold)
3. Move mouse to target position
4. Release mouse button

**Use Cases:**
- Drag files to folders
- Rearrange UI elements
- Resize windows
- Scroll by dragging scrollbar

**Best Practices:**
- Smooth mouse movement between source and target
- Appropriate speed (not too fast)
- Verify drag operation completed
- Handle drop zones

#### Mouse Movement

**Available:**
- `mouse_move(x, y)`

**Use Cases:**
- Position mouse before click
- Trigger hover effects
- Reveal hidden UI elements (tooltips, menus)
- Smooth animations

**Best Practices:**
- Move incrementally for natural interaction
- Pause briefly after movement
- Avoid teleporting mouse instantly

### Keyboard Operations

#### Text Input

**Available:**
- `keyboard_type(text, interval=0.0)`

**Use Cases:**
- Enter text into fields
- Type search queries
- Fill forms
- Input commands

**Best Practices:**
- Click/focus field before typing
- Use appropriate typing speed (interval)
- Verify text entered correctly (screen capture + OCR)
- Handle special characters correctly
- Consider keyboard layout (language)

**Example:**
```python
# Click on text field
mouse_click(x=400, y=300)
time.sleep(0.2)

# Type text
keyboard_type("user@example.com", interval=0.05)
```

#### Special Keys & Shortcuts

**Available:**
- `keyboard_press(key, modifiers=[])`

**Common Keys:**
- `enter`, `tab`, `escape`, `backspace`, `delete`
- `space`, `home`, `end`, `pageup`, `pagedown`
- `up`, `down`, `left`, `right` (arrow keys)
- `f1` through `f12` (function keys)

**Modifiers:**
- `ctrl`, `alt`, `shift`, `win` (Windows key)

**Common Shortcuts:**
- `Ctrl+C` → Copy
- `Ctrl+V` → Paste
- `Ctrl+A` → Select All
- `Alt+F4` → Close Window
- `Ctrl+S` → Save
- `Ctrl+Z` → Undo
- `Win+D` → Show Desktop

**Best Practices:**
- Use keyboard shortcuts for efficiency
- Wait for action to complete after shortcut
- Verify shortcut had expected effect
- Document required shortcuts in exploration notes

**Example:**
```python
# Save file (Ctrl+S)
keyboard_press('s', modifiers=['ctrl'])
time.sleep(0.5)  # Wait for save dialog
```

#### Keyboard Navigation

**Patterns:**
- **Tab Navigation**: Move between fields using Tab
- **Arrow Keys**: Navigate menus, lists, selections
- **Enter**: Confirm selections, submit forms
- **Escape**: Cancel dialogs, close menus

**Best Practices:**
- Use keyboard navigation for accessibility
- More reliable than coordinate-based clicking in some cases
- Faster for complex navigation
- Document keyboard flow during exploration

---

## Screen Capture & Validation

### Capturing Screen State

**Available:**
- `screen_capture(x=None, y=None, width=None, height=None)`

**Use Cases:**
- **Full Screen**: Capture entire desktop
- **Window Capture**: Capture specific window area
- **Region Capture**: Capture specific UI region
- **Before/After Validation**: Compare states

**Best Practices:**
- Capture screen at key points during exploration
- Store captures with descriptive names
- Use captures for element identification
- Document what each capture represents
- Capture expected outcomes for validation

**Example:**
```python
# Capture before action
before = screen_capture()

# Perform action
mouse_click(x=500, y=300)
time.sleep(1)

# Capture after action
after = screen_capture()

# Compare or validate change
```

### Visual Validation Strategies

#### Text Verification (OCR)

**Pattern:**
1. Capture screen region containing expected text
2. Apply OCR to extract text
3. Verify expected text present
4. Document any discrepancies

**Use Cases:**
- Verify button labels
- Check message text
- Validate field values
- Confirm status messages

**Challenges:**
- OCR accuracy varies
- Font rendering affects recognition
- Background contrast impacts readability

**Best Practices:**
- Capture high-contrast text areas
- Use appropriate OCR confidence thresholds
- Handle minor variations (extra spaces, capitalization)
- Verify during exploration that OCR works for target text

#### Image Comparison

**Pattern:**
1. Capture reference image during exploration
2. Capture current screen during execution
3. Compare images (pixel-by-pixel or fuzzy)
4. Identify differences

**Use Cases:**
- Verify UI appearance
- Detect unexpected changes
- Confirm graphical elements
- Validate visual consistency

**Challenges:**
- Exact pixel matching too strict
- Minor rendering differences cause false failures
- Timestamp/dynamic content causes mismatches

**Best Practices:**
- Use fuzzy matching (allow small differences)
- Mask dynamic regions (timestamps, animations)
- Focus on stable UI regions
- Document acceptable difference thresholds

#### State Verification

**Pattern:**
- Capture screen before expected state
- Perform action
- Capture screen after action
- Verify expected state change occurred

**Examples:**
- Button enabled → disabled
- Text changed
- Window appeared/disappeared
- Color change (hover, selection)

---

## Desktop-Specific Challenges & Solutions

### Challenge 1: Dynamic Window Positioning

**Problem:**
- Windows may open at different positions
- Affects absolute coordinate-based interactions

**Solutions:**
- **Find Window**: Use window title or image matching to locate window
- **Relative Positioning**: Calculate element positions relative to window corner
- **Maximize Window**: Ensure consistent window size/position
- **Center Window**: Position window at screen center for predictability

**Exploration Strategy:**
- Document window position during exploration
- Test with window in different positions
- Use relative coordinates when possible

### Challenge 2: UI Rendering Delays

**Problem:**
- Application UI may not render immediately
- Elements appear after brief delay
- Interactions fail if attempted too early

**Solutions:**
- **Explicit Waits**: Wait for specific UI element to appear
- **Screen Capture Polling**: Repeatedly capture until expected content visible
- **Timeout Mechanism**: Set maximum wait time
- **Visual Confirmation**: Verify element present before interaction

**Best Practices:**
- Never use fixed delays (time.sleep) alone
- Implement smart waits (poll for visual change)
- Document typical rendering times during exploration
- Set appropriate timeout values

**Example:**
```python
def wait_for_element_visible(reference_image, timeout=10, interval=0.5):
    """Wait until element matching reference image appears."""
    elapsed = 0
    while elapsed < timeout:
        screen = screen_capture()
        if image_contains(screen, reference_image):
            return True
        time.sleep(interval)
        elapsed += interval
    return False
```

### Challenge 3: Application State Inconsistency

**Problem:**
- Application state may vary between runs
- Previous test data affects current test
- Settings/preferences persist

**Solutions:**
- **Reset Application State**: Clear data, reset settings before test
- **Use Fresh Environment**: Launch clean application instance
- **Parameterize Tests**: Handle different starting states
- **Cleanup After Test**: Restore original state

**Best Practices:**
- Document required preconditions during exploration
- Implement setup/teardown procedures
- Reset to known state at test start
- Clean up test data after execution

### Challenge 4: System Dialogs & Popups

**Problem:**
- Unexpected system dialogs (UAC, firewall, updates)
- Application popups (tips, updates, notifications)
- Block test execution

**Solutions:**
- **Detect and Handle**: Screen capture + OCR to detect dialogs
- **Auto-Dismiss**: Close expected popups automatically
- **Skip First Run**: Disable first-run experiences
- **Disable Notifications**: Configure application to suppress popups

**Best Practices:**
- Document all dialogs encountered during exploration
- Implement generic dialog handler
- Test with clean application install
- Provide configuration to disable popups

### Challenge 5: Keyboard Layouts & Languages

**Problem:**
- Different keyboard layouts affect key mapping
- Language-specific characters
- Special symbols vary by layout

**Solutions:**
- **Use English Keyboard Layout**: Standardize on US English for automation
- **Copy-Paste for Special Characters**: Use clipboard instead of typing
- **Document Required Layout**: Specify keyboard layout in test requirements
- **Detect Current Layout**: Verify layout before test execution

**Best Practices:**
- Test on target keyboard layout
- Document any layout dependencies
- Use shortcuts that work across layouts
- Handle localization during exploration

### Challenge 6: Screen Resolution & DPI Scaling

**Problem:**
- Different screen resolutions change element positions
- Windows scaling (125%, 150%) affects coordinates
- Multi-monitor setups complicate positioning

**Solutions:**
- **Normalize Resolution**: Run tests at specific resolution
- **Scale Coordinates**: Adjust for DPI scaling factor
- **Use Primary Monitor**: Ensure application on primary screen
- **Relative Positioning**: Avoid absolute coordinates

**Best Practices:**
- Document target resolution during exploration
- Detect and adjust for scaling factor
- Test on target environment
- Use resolution-independent identification when possible

**Example:**
```python
# Get screen size and calculate scaled position
screen_width, screen_height = get_screen_size()

# Position at 25% from left, 50% from top (relative)
x = int(screen_width * 0.25)
y = int(screen_height * 0.50)

mouse_click(x, y)
```

---

## Exploration Best Practices

### During Exploration

1. **Capture Every Step**
   - Take screenshot before and after each action
   - Document exact coordinates used
   - Record keyboard shortcuts and text input
   - Note timing requirements (waits, delays)

2. **Extract Multiple Identification Strategies**
   - Visual: Capture reference images for buttons, icons
   - Text: Note readable text via OCR
   - Position: Record coordinates (with resolution context)
   - Region: Define UI regions for targeted search

3. **Rank by Stability**
   - **Most Stable**: Image matching of unique icons, OCR of unique text
   - **Medium Stability**: Region-based search + OCR
   - **Least Stable**: Absolute coordinates

4. **Document Challenges**
   - Timing issues (slow loading, animations)
   - Dynamic positioning (window placement)
   - State dependencies (requires specific starting state)
   - System dialogs/popups
   - Resolution/scaling requirements

5. **Validate Visual Recognition**
   - Test OCR accuracy for all text elements
   - Verify image matching works for all icons/buttons
   - Confirm coordinates are accurate
   - Document any recognition failures

### Desktop-Specific Exploration Checklist

- [ ] Application launch method documented (path, shortcut, command)
- [ ] Window state captured (size, position, maximized/normal)
- [ ] Screen resolution and scaling noted
- [ ] All interactive elements identified (buttons, fields, menus)
- [ ] Reference images captured for key elements
- [ ] OCR tested for all text elements
- [ ] Keyboard shortcuts documented
- [ ] Mouse interaction coordinates recorded
- [ ] Timing requirements identified
- [ ] Dialogs and popups noted
- [ ] Application state preconditions documented
- [ ] Expected outcomes visually captured
- [ ] Automation challenges identified with solutions

---

## Framework Selection for Generated Code

### Recommended Frameworks by Language

#### Python
1. **PyAutoGUI**
   - General-purpose desktop automation
   - Cross-platform (Windows, Mac, Linux)
   - Simple API for mouse/keyboard
   - Image recognition built-in

2. **pywinauto**
   - Windows-specific
   - UI Automation / Win32 API access
   - More reliable element identification
   - Better window management

3. **Sikuli / SikuliX**
   - Visual automation (image-based)
   - Pattern matching
   - OpenCV integration
   - Cross-platform

#### AutoIt
- Windows automation scripting language
- Native Windows API access
- Lightweight and fast
- Good for simple automation tasks

### Selection Criteria

| Factor | PyAutoGUI | pywinauto | SikuliX | AutoIt |
|--------|-----------|-----------|---------|--------|
| **Ease of Use** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Reliability** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Platform Support** | Cross-platform | Windows only | Cross-platform | Windows only |
| **Element Identification** | Image/Coordinates | UI Automation API | Image matching | UI elements |
| **Community Support** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |

**Default Recommendation:** 
- **pywinauto** for Windows applications (best reliability and element access)
- **PyAutoGUI** for cross-platform or simple automation needs
- **SikuliX** for heavy visual pattern matching requirements

---

## Code Generation Guidelines

### Structure

Generated desktop automation code should include:

1. **Setup Section**
   - Import required libraries
   - Configure screen resolution/scaling detection
   - Set up logging
   - Define helper functions

2. **Application Launch**
   - Start application
   - Wait for application to be ready
   - Maximize/position window
   - Handle first-run dialogs

3. **Test Steps**
   - Each exploration step becomes a test method
   - Include visual validation after key actions
   - Handle expected dialogs/popups
   - Implement waits and retries

4. **Teardown**
   - Close application gracefully
   - Clean up test data
   - Capture final state

### Code Quality Standards

- **Locator Comments**: Explain why each locator strategy chosen
- **Wait Strategies**: Use smart waits, not fixed delays
- **Error Handling**: Catch and handle expected failures
- **Screenshots**: Capture evidence at key points
- **Logging**: Detailed execution logs
- **Parameterization**: External configuration for coordinates, paths, text

### Example Code Template (Python + PyAutoGUI)

```python
import pyautogui
import time
from PIL import Image
import pytesseract

# Configuration
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
APPLICATION_PATH = "C:\\Program Files\\MyApp\\app.exe"
SCREENSHOTS_DIR = "screenshots"

def launch_application():
    """Launch target application and wait for ready."""
    # Launch application
    os.startfile(APPLICATION_PATH)
    
    # Wait for application window to appear
    time.sleep(3)
    
    # Maximize window for consistent positioning
    pyautogui.hotkey('win', 'up')
    time.sleep(1)

def wait_for_element(reference_image, timeout=10):
    """Wait for element to appear on screen."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            location = pyautogui.locateOnScreen(reference_image, confidence=0.8)
            if location:
                return location
        except:
            pass
        time.sleep(0.5)
    raise Exception(f"Element not found: {reference_image}")

def click_button(reference_image):
    """Find and click button by image."""
    location = wait_for_element(reference_image)
    center = pyautogui.center(location)
    pyautogui.click(center.x, center.y)
    time.sleep(0.5)

def test_workflow():
    """Main test workflow from exploration."""
    try:
        # Step 1: Launch application
        launch_application()
        
        # Step 2: Click "New" button
        click_button("new_button.png")
        
        # Step 3: Enter text in field
        pyautogui.click(400, 300)  # Click text field
        pyautogui.typewrite("Test data", interval=0.05)
        
        # Step 4: Click "Save" button
        click_button("save_button.png")
        
        # Step 5: Verify success message
        screenshot = pyautogui.screenshot()
        text = pytesseract.image_to_string(screenshot)
        assert "Success" in text, "Success message not found"
        
        print("✅ Test passed")
        
    except Exception as e:
        # Capture failure screenshot
        pyautogui.screenshot(f"{SCREENSHOTS_DIR}/failure.png")
        print(f"❌ Test failed: {e}")
        raise
    
    finally:
        # Close application
        pyautogui.hotkey('alt', 'f4')
        time.sleep(1)

if __name__ == "__main__":
    test_workflow()
```

---

## Desktop Reliability (Specification — Source of Truth)

> **This section is the primary source of truth for desktop automation reliability.** The Unified Automation Agent prompt (`automation-agent-unified.agent.md`), the agent manual (`UNIFIED_AUTOMATION_AGENT_MANUAL.md`), and the `live-exploration-workflow`, `execution-validation`, and `code-generation` skills all reference these rules and MUST NOT contradict them. If any other document disagrees on a rule or a constant, **this document wins**.

Desktop automation has two recurring failure modes this specification eliminates:

1. **Unverified interactions** — the agent clicked, assumed success, and moved on. Verification after every interaction is now **mandatory**, and **No-op** clicks (nothing changed) and **Wrong-target** clicks (the wrong thing changed) must be detected explicitly.
2. **Unstable element localization** — elements move or change appearance across themes, DPI/scaling, resolution, and window position. Brittle absolute-coordinate clicking is replaced by **confidence-based, ranked localization with fallback**, plus re-capture/retry with backoff and scaling awareness.

### Two enforcement planes, one rule set (R14)

The rules are authored **once** and enforced **identically in both planes**:

- **Plane A — Live exploration:** the agent driving the screen through **desktop-automation-mcp** tools (`screen_capture`, `mouse_click`, `mouse_move`, `keyboard_type`, `keyboard_press`, `get_screen_size`). Each step of the rule set maps to MCP tool calls plus the agent's structured reasoning.
- **Plane B — Generated automation code:** the script the agent produces (PyAutoGUI / pywinauto / SikuliX / AutoIt), which **must ship** a reusable `verified_interaction` routine plus `locate_with_fallback` and `wait_for_expected_outcome` helpers, and route **all** interactions through them rather than calling raw framework `click`/`type` directly.

**R14 enforcement applies to BOTH planes.** The same four conceptual components (Verified-Interaction Routine, Element_Locator, Action_Verifier, Failure-Handler) appear in each plane; only the mechanism differs (MCP tool calls vs. framework API calls). The agent MUST apply these rules during live exploration **and** bake them into generated code.

**Canonical reference implementation:** the executable, source-of-truth pattern for all of the routines below lives at
[`.github/skills/desktop-automation/reference/`](./reference/) (package `desktop_reliability/`). Generated desktop projects are expected to mirror these behavioral helpers: `verified_interaction` (`interaction.py`), `locate_with_fallback` (`locator.py`), `verify_and_classify` (`verifier.py`), `classify_failure`/`escalate` (`failure.py`), and flow aggregation (`flow.py`). The reference is a **development-time pattern**, not a runtime dependency — using the agent does not require Python.

### Reliability constants (authoritative)

These constants are authoritative. Every governing document MUST use these exact values; no document may contradict another.

| Constant | Value | Requirement |
|---|---|---|
| `confidence_threshold` | **0.80** (image matching; accept when `>=` threshold) | R6.1, R6.3 |
| `verify_timeout` | **10 seconds** (poll for expected outcome) | R2.5 |
| `post_capture_target` | **2000 ms** (target; accept late captures) | R1.2, R1.3 |
| `max_interaction_attempts` | **3** (per-interaction re-attempt budget) | R12.1 |
| `max_locate_attempts` | **3** (per-localization retry budget) | R9.2 |
| Agent-level correction iterations | **5** (code-fix loop for `code_issue`) | existing invariant |
| Backoff schedule | **`500ms * 2^(attempt-1)`** → 500 ms, 1000 ms, 2000 ms, … | R9.3 |
| Ranked strategy order | image matching → OCR text → anchor-relative → ROI-constrained → window-relative → absolute | R5.1 |
| Error categories | `code_issue`, `system_bug`, `user_input_needed` | R12.3 |
| Evidence location | `<project-root>/evidences/` (step-identifying, attempt-numbered names) | R1.4 |
| Click-offset tolerance | **2 px** per component (default; horizontal and vertical) | R16.4 |
| Stable-offset measurements | **2** agreeing measurements minimum | R16.4 |
| Single-monitor Click_Offset | **zero vector** (identity; resolved points unchanged) | R16.12 |

> **Two retry layers, never conflated:** the **3 per-interaction re-attempts** (`max_interaction_attempts`, R12.1) and the **3 per-localization retries** (`max_locate_attempts`, R9.2) are different layers, and both differ from the **5 agent-level code-fix iterations**. A single interaction may locate up to 3 times per attempt, and be re-attempted up to 3 times; `code_issue` failures are fixed and re-run within the 5-iteration agent loop.

---

### R1 — Mandatory pre-action and post-action state capture

- **R1.1** Before every mouse/keyboard interaction, capture a **Pre_Action_State** of the Verification_Region (the ROI when defined, otherwise full screen).
- **R1.2** After the interaction, capture a **Post_Action_State** of the Verification_Region with a target of **2000 ms**.
- **R1.3** If the post-capture takes longer than 2000 ms, **accept the late capture** and continue verification — latency never invalidates the evidence.
- **R1.4** Store each Pre/Post capture under `<project-root>/evidences/` with a name that identifies the step (and attempt).

Plane A: `screen_capture(...)` before and after. Plane B: a `screen_capture()`/`pyautogui.screenshot(region=...)` wrapper before and after, written through the evidence store.

### R2 — Mandatory post-action verification

- **R2.1** Define an explicit **Expected_Outcome** for each interaction **before** performing it (a new window appears, a field shows typed text, a button becomes disabled, etc.).
- **R2.2** When the interaction completes, compare the Post_Action_State against the Expected_Outcome **before** the next interaction begins.
- **R2.3** When the Expected_Outcome is confirmed, proceed to the next step.
- **R2.4** While the Expected_Outcome is **not** confirmed, hold execution at the current step (do not advance) until the failure-handling procedure resolves it or manual intervention is provided.
- **R2.5** Poll the Post_Action_State up to a configurable timeout (**default 10 s**) before concluding the outcome did not occur.

### R3 — No-op and Wrong-target detection

- **R3.1** If the Post_Action_State is **region-identical** to the Pre_Action_State after an interaction expected to change state → classify as **No_Op_Click**.
- **R3.2** If the Post_Action_State **differs** from the Pre_Action_State but does **not** match the Expected_Outcome → classify as **Wrong_Target_Click**.
- **R3.3 / R3.4** Both No_Op_Click and Wrong_Target_Click are treated as **failed** and trigger the failure-handling procedure (R12). They are never silently passed.

### R4 — Success requires verification evidence (no false positives)

- **R4.1** Treat an interaction as successful **only** when the Action_Verifier confirms the Expected_Outcome **with present post-action evidence**. A `CONFIRMED` verdict is the *single* source of success — there is no "assume success" branch.
- **R4.2** If verification evidence is unavailable (no/missing post-state), the interaction **cannot** be `CONFIRMED` and is treated as **failed**.

### R5 — Ranked localization strategies with fallback

- **R5.1** Rank strategies by decreasing stability, in this **fixed order**:
  **image matching (confidence) → OCR text → anchor-relative → ROI-constrained → window-relative → absolute coordinates**.
- **R5.2** Attempt strategies in ranked order until one returns a match at or above the `confidence_threshold`.
- **R5.3** When more than one strategy would match, select the match produced by the **highest-ranked** strategy (first qualifying match wins).
- **R5.4** **Record** the strategy that produced the selected match on the localization result.

### R6 — Confidence thresholds and fuzzy matching

- **R6.1** Apply a configurable image-match `confidence_threshold` (**default 0.80**).
- **R6.2** If a match's confidence is **strictly below** the threshold, reject it and attempt the next-ranked strategy.
- **R6.3** If a match's confidence **equals** the threshold, **accept** it (gating is inclusive: `confidence >= threshold`).
- **R6.4** For OCR text matching, **normalize** before comparing: `normalize(text) = lowercase(strip_leading_trailing_whitespace(text))`. Match iff the normalized strings are equal.
- **R6.5** If text normalization fails (e.g. non-string / un-normalizable input), reject the match and attempt the next-ranked strategy.

### R7 — Anchor-relative positioning

- **R7.1** When a target lacks a stable absolute position, compute its point as `anchor_point + offset`.
- **R7.2** **Confirm the anchor is present** in the current screen state before computing the anchor-relative point.
- **R7.3** If the anchor cannot be located, produce **no** anchor-relative point and fall through to the next-ranked strategy.

### R8 — Region-of-interest (ROI) search

- **R8.1** When a Region_Of_Interest is defined, **constrain the search to that ROI first**.
- **R8.2** If the search cannot be constrained to the ROI (undefined/invalid/empty ROI), fall back to a **full-screen** search.
- **R8.3** When the target is found within its ROI, **use that match without expanding** to full screen.
- **R8.4** If the target is not found within its ROI, **expand to full screen** before reporting the element as not located.

### R9 — Re-capture and retry with backoff

- **R9.1** If the target is not located on an attempt, capture a **fresh** screen state and retry.
- **R9.2** Retry localization up to a configurable maximum of **3 attempts** (`max_locate_attempts`).
- **R9.3** Apply exponential backoff **between** attempts: `delay(attempt) = 500ms * 2^(attempt-1)` (500 ms, 1000 ms, 2000 ms, …). No trailing delay after the final attempt.
- **R9.4** If all attempts are exhausted without a qualifying match, report the element as **NotLocated**.

### R10 — Resolution and scaling awareness

- **R10.1** At session start, capture the **screen resolution** and the active **Scaling_Factor** (via `get_screen_size` + OS scaling query).
- **R10.2** When the Scaling_Factor is not 100%, adjust coordinate calculations and reference-image matching by the captured factor.
- **R10.3** If execution-time resolution/scaling differs from the exploration-time values, **recompute** relative positions using the execution-time values. When the environments are equal, the transform is the **identity**.

### R11 — Window focus and positioning

- **R11.1** Immediately before an interaction, **confirm the target window holds input focus**.
- **R11.2** If the target window does not hold focus, **bring it to focus** before performing the interaction.
- **R11.3** Where window position affects coordinates, compute interaction coordinates **relative to the current window origin** (`window_origin + win_offset`).

### R12 — Failure handling, retry, classification, escalation

- **R12.1** When an interaction is classified as failed, **re-locate and re-attempt** up to a maximum of **3 attempts** (`max_interaction_attempts`).
- **R12.2** When re-attempting, capture a **fresh Pre_Action_State** and **re-run verification** after the re-attempt.
- **R12.3** If the interaction remains failed after the maximum re-attempts, **classify** it into exactly one of `code_issue`, `system_bug`, or `user_input_needed`.
- **R12.4** On exhaustion, **stop the current flow** and **report** the failure together with the captured Pre/Post evidence, the localization strategy, the confidence, and the verification verdict.
- **R12.5** When an interaction is **first** classified as failed, **record** the localization strategy, the confidence obtained, and the verification result **immediately, before any re-attempt**.

**Classification rules (R12.3):**

- **`code_issue`** — defect in the automation logic (wrong reference image, bad ROI, brittle absolute coordinate, insufficient wait, threshold mis-set). Fixed and re-run within the **5-iteration** agent loop.
- **`system_bug`** — defect in the application under test (target genuinely absent, app crashed, unexpected app state). Documented and surfaced; not retried indefinitely.
- **`user_input_needed`** — ambiguity or missing information (expected outcome undeterminable, unknown target/credentials, indistinguishable equally-confident targets). Execution pauses for the user.

**Verdict → failure mapping:** `NO_OP_CLICK` → re-locate (the click likely missed) and re-attempt; usually `code_issue` unless the control is genuinely inert (`system_bug`). `WRONG_TARGET_CLICK` → re-locate with stricter ROI/anchor and re-attempt; usually `code_issue`, and may be `user_input_needed` when targets are indistinguishable.

### R13 — No false positives for desktop flows

- **R13.1** Report a step as passed **only** when verification evidence confirms its Expected_Outcome.
- **R13.2** If **any** interaction in a flow is unverified or failed, report the **flow** status as `FAILED`, treating partial verification identically to complete failure. Aggregation: `status = PASSED if all(step.final_status == SUCCESS) else FAILED`. An empty flow is `FAILED` (zero verified work is not a pass).

### R14 — Enforcement in both planes (live exploration AND generated code)

- **R14.1** Apply the verification, localization, and failure-handling rules **during live exploration** using `desktop-automation-mcp` tools.
- **R14.2** Implement the same rules in **generated code** using the selected desktop framework.
- **R14.3** Generated code MUST provide a **reusable `verified_interaction` routine** (pre-capture → interact → post-capture → verify) plus `locate_with_fallback` and `wait_for_expected_outcome` helpers, and route every interaction through them. The canonical pattern is the [reference implementation](./reference/).

---

### R16 — Multi-monitor coordinate consistency and click-offset calibration

> **This is the rule set for the "it found the element but clicked the wrong place" failure.** On a multi-monitor setup the plane an element is **read** in (`screen_capture`) and the plane an interaction is **commanded** in (`mouse_click`) can diverge by a **constant vector** — non-primary monitors have negative or large-positive origins on the unified **Virtual_Desktop**, and each monitor may have its own scaling. Localization can be perfectly correct while the click still lands in the wrong spot. R16 measures that divergence (the **Click_Offset**) and corrects every commanded point. On a single monitor the Click_Offset is the **zero vector**, so the same logic is a no-op and stays correct on single-monitor and single-resolution machines.

- **R16.1** At session start, capture the **per-monitor geometry** of every connected monitor on the Virtual_Desktop: each monitor's **origin** (may be negative or large-positive), **width**, **height**, **per-monitor Scaling_Factor**, and which monitor is **primary** — in addition to the R10.1 resolution/scaling capture.
- **R16.2** Do **not** assume `screen_capture`, `mouse_click`, and `get_screen_size` share a single coordinate plane.
- **R16.3** When a Calibration or verification interaction completes, measure the divergence between the read plane and the command plane as the vector **`(observed_point − commanded_point)`**, where `observed_point` is read from the Post_Action_State.
- **R16.4** When a divergence vector is **reproduced across at least two measurements** whose horizontal and vertical components each agree within a configurable tolerance (**default 2 px**), classify the Click_Offset as **stable**.
- **R16.5** If fewer than two measurements exist for the current monitor, or measurements differ by more than the tolerance, classify the Click_Offset as **unstable**.
- **R16.6** When the Click_Offset is **stable**, treat the measured divergence as the Click_Offset and **apply it to every subsequently resolved interaction point**.
- **R16.7** When the target window origin falls **outside the primary monitor's bounds**, treat the window as residing on a **non-primary monitor** of the Virtual_Desktop.
- **R16.8** When the target window is on a non-primary monitor, perform a **one-time Calibration** that commands an interaction with a reference element located at or above the `confidence_threshold` (R6) and reads the observed point from the Post_Action_State.
- **R16.9** When a Calibration interaction completes, compute the Click_Offset as **`(observed_point − commanded_point)`**.
- **R16.10** When Calibration completes, **apply the measured Click_Offset** to every interaction point resolved afterward, until a re-calibration occurs.
- **R16.11** When the target window **moves to a different monitor**, **re-calibrate** the Click_Offset before further interactions with that window.
- **R16.12** When the Virtual_Desktop has a **single connected monitor**, set the Click_Offset to the **zero vector** so Calibration and compensation leave resolved points unchanged.
- **R16.13** While the Click_Offset is **unknown or unstable**, **prefer anchor-relative (R7) and window-relative (R11) localization over absolute coordinates** — a point computed from an element within the same captured frame cancels a constant capture-vs-click offset.
- **R16.14** If the per-monitor Scaling_Factor **differs** between the monitor where the element is read and the monitor where the interaction is commanded, classify as **`user_input_needed`** (R12) and **do not** perform the interaction with an uncorrected coordinate.
- **R16.15** Apply Calibration and Click_Offset compensation **during live exploration** (Plane A), consistent with R14.
- **R16.16** Generated code MUST provide a **reusable Calibration helper** and an **offset-correcting interaction-point resolver**.
- **R16.17** Generated code MUST route **every** interaction's point through the offset-correcting resolver, consistent with R14.
- **R16.18** Generated code MUST NOT use **hardcoded absolute coordinates** for target elements on non-primary monitors.

**Canonical implementation:** `calibration.py` in the [reference implementation](./reference/) — `measure_divergence`, `offset_is_stable`, `resolve_click_offset`, `resolve_interaction_point`, and the `Calibrator` helper, plus `Monitor` / `ClickOffset` / `SessionEnvironment.monitors` in `models.py`. The Verified-Interaction Routine routes its resolved point through `resolve_interaction_point(point, click_offset)` before commanding the interaction.

**Plane A (live exploration):** capture monitor geometry with `get_screen_size` + the OS monitor query; on a non-primary monitor, click a high-confidence reference element, read where the change actually occurred from the post-capture, and compute `(observed − commanded)`; once two measurements agree within 2 px, add that vector to every subsequent click point. **Plane B (generated code):** emit the `Calibrator` + `resolve_interaction_point` helpers and route every `pyautogui.click` / `pywinauto` interaction through them; never hardcode absolute coordinates for non-primary-monitor targets.

---

### Reusable pseudocode patterns

These are the language-neutral patterns the agent follows in Plane A and emits as helpers in Plane B. The canonical, executable versions live in the [reference implementation](./reference/). The default generated stack is **Python + PyAutoGUI/pywinauto + Pytest**.

#### `verified_interaction` — the single-interaction orchestrator (Component 1)

Drives the lifecycle **define expected outcome → confirm focus → pre-capture → locate → interact → post-capture → verify → classify → (retry with backoff | escalate)**. A `CONFIRMED` verdict backed by stored post-evidence is the **only** path to success.

```text
function verified_interaction(step, expected_outcome, config):
    assert expected_outcome is defined                              # R2.1

    record = new InteractionRecord(step_id = step.id)

    for attempt in 1..config.max_interaction_attempts (default 3):   # R12.1
        ensure_window_focus(step.target_window)                     # R11.1/11.2

        pre = capture_state(step.verification_region)               # R1.1
        store_evidence(pre, step.id, "pre", attempt)                # R1.4

        location = locate_with_fallback(step.target, config)        # R5–R10
        if location.not_located:
            record.append(localization_failure(location))           # R12.5 (record first)
            backoff_sleep(attempt, config)                          # R9.3 / R12
            continue

        record.localization_strategy = location.strategy           # R5.4
        record.confidence = location.confidence

        point = resolve_interaction_point(location.point, click_offset)  # R16.6/16.10/16.13
        perform_interaction(step.action, point)                    # R11.3 (window-relative, offset-corrected)

        post = capture_state(step.verification_region)             # R1.2 (target 2000 ms; accept if late, R1.3)
        store_evidence(post, step.id, "post", attempt)             # R1.4

        verdict = verify_and_classify(pre, post, expected_outcome, config)   # R2.2–2.5 + R3
        record.verification = verdict

        if verdict == CONFIRMED:                                   # R2.3 / R4.1
            return Success(record)                                 # only path to success

        record.append(verdict)                                     # R12.5 (record before retry)
        backoff_sleep(attempt, config)                             # R12

    classification = classify_failure(record)                      # R12.3 (one of 3 categories)
    return Failure(record, classification)                         # R12.4 / R13
```

#### `locate_with_fallback` — ranked localization with retry and backoff (Component 2)

```text
# R5.1 fixed ranked order (most → least stable)
STRATEGY_ORDER = [ IMAGE_MATCH, OCR_TEXT, ANCHOR_RELATIVE,
                   ROI_CONSTRAINED, WINDOW_RELATIVE, ABSOLUTE ]

function locate_with_fallback(target, config):
    for attempt in 1..config.max_locate_attempts (default 3):       # R9.2
        frame = capture_state(target.search_region or full_screen)  # R9.1 fresh capture
        frame = normalize_for_scaling(frame, session.scaling)       # R10.2

        for strategy in STRATEGY_ORDER:                             # R5.2 ranked traversal
            candidate = run_strategy(strategy, target, frame, config)
            if candidate.matched and candidate.confidence >= config.threshold:  # R6.1–6.3 (inclusive)
                return Located(point = candidate.point,             # R5.3 first/highest-ranked wins
                               strategy = strategy,                 # R5.4 record producing strategy
                               confidence = candidate.confidence)
        backoff_sleep(attempt, config)                              # R9.3 exp backoff from 500ms

    return NotLocated(target)                                       # R9.4

function run_strategy(strategy, target, frame, config):
    switch strategy:
        IMAGE_MATCH:    return image_match(target.reference, frame, config.threshold)   # R6.1–6.3
        OCR_TEXT:       text = ocr(frame, target.region)
                        return text_match(normalize(text), normalize(target.text))      # R6.4/6.5
        ANCHOR_RELATIVE:
                        anchor = locate(target.anchor, frame)
                        if anchor.not_found: return NoMatch         # R7.3 fall through
                        return Match(point = anchor.point + target.offset)              # R7.1/7.2
        ROI_CONSTRAINED:
                        if target.roi defined and can_constrain(frame, target.roi):     # R8.1
                            m = search(frame within target.roi)
                            if m.found: return m                    # R8.3 use without expanding
                        return search(full_screen_frame)            # R8.2/8.4 escalate
        WINDOW_RELATIVE: return Match(point = window_origin(target.window) + target.win_offset)  # R11.3
        ABSOLUTE:        return Match(point = scale(target.absolute, session.scaling))   # R10.2

function normalize(text): return lowercase(strip_leading_trailing_whitespace(text))     # R6.4
```

#### `verify_and_classify` — outcome verification + verdict classification (Component 3)

```text
function verify_and_classify(pre, post, expected, config):
    deadline = now + config.verify_timeout (default 10s)            # R2.5
    while now < deadline:
        if matches_expected(post, expected):                       # R2.2
            return CONFIRMED                                       # R2.3 / R4.1
        post = capture_state(expected.region)                      # re-capture while polling
    if region_identical(pre, post, expected.region):               # R3.1
        return NO_OP_CLICK
    else:                                                          # R3.2 changed but not expected
        return WRONG_TARGET_CLICK

function matches_expected(post, expected):
    if post is missing: return false                               # R4.2 no evidence ⇒ not success
    return expected.predicate(post)                                # observable check
```

#### `classify_failure` — classification, stop, and escalation (Component 4)

```text
function classify_failure(record):
    if record indicates ambiguity / missing info:                  # R12.3
        category = user_input_needed
    elif record indicates application defect (element absent, crash, wrong state):
        category = system_bug
    else:                                                          # locator/wait/assertion defect
        category = code_issue

    stop_current_flow()                                            # R12.4
    report_failure(record.pre_evidence, record.post_evidence, category,
                   record.localization_strategy, record.confidence, record.verification)  # R12.4/12.5
    return category
```

#### `calibrate` / `resolve_interaction_point` — multi-monitor click-offset (R16)

```text
# R16.3/16.9: divergence between where the element was read and where the click landed
function measure_divergence(observed, commanded):
    return (observed.x - commanded.x, observed.y - commanded.y)

# R16.4/16.5: stable iff >= 2 measurements agree within tolerance (default 2px) per component
function offset_is_stable(measurements, tolerance = 2):
    if count(measurements) < 2: return false                       # R16.5
    return spread_x(measurements) <= tolerance and spread_y(measurements) <= tolerance  # R16.4

# R16.6/16.10/16.12: resolve the Click_Offset to apply to resolved points
function resolve_click_offset(measurements, monitor, single_monitor):
    if single_monitor: return ClickOffset(vector=(0,0), stable=true)    # R16.12 zero identity
    if offset_is_stable(measurements):
        return ClickOffset(vector=most_recent(measurements), stable=true)  # R16.4/16.6
    return ClickOffset(vector=(0,0), stable=false)                 # R16.5 (not applied)

# R16.6/16.10/16.13: correct a resolved point, but ONLY when the offset is stable
function resolve_interaction_point(point, click_offset):
    if click_offset is none or not click_offset.stable: return point   # R16.13 (prefer relative)
    return (point.x + click_offset.vector.x, point.y + click_offset.vector.y)

# R16.7/16.8/16.11: monitor reasoning drives when to (re)calibrate
function is_on_non_primary_monitor(session, window_origin):        # R16.7
    if single_monitor(session) or window_origin is none: return false
    return not session.primary_monitor.contains(window_origin)

function requires_recalibration(previous_monitor, current_monitor):  # R16.11
    return both known and previous_monitor != current_monitor

# R16.14: mixed-DPI between read and command monitor => user_input_needed, do not click uncorrected
function scaling_conflict(read_monitor, command_monitor):
    return both known and read_monitor.scaling != command_monitor.scaling
```

#### Flow status aggregation (R13)

```text
function flow_status(steps):
    if steps is empty: return FAILED                               # zero verified work is not a pass
    return PASSED if all(step.final_status == SUCCESS for step in steps) else FAILED   # R13.2
```

#### Plane A vs. Plane B mechanism mapping

| Concept | Plane A (desktop-automation-mcp) | Plane B (generated code) |
|---|---|---|
| Capture state | `screen_capture(x, y, width, height)` | `pyautogui.screenshot(region=...)` / framework equivalent |
| Image match + confidence | agent compares captures, reasons about similarity | `pyautogui.locateOnScreen(img, confidence=...)` / OpenCV |
| OCR text match | agent reads text from capture | `pytesseract` over the capture region |
| Click / type | `mouse_click`, `mouse_move`, `keyboard_type`, `keyboard_press` | `pyautogui.click/typewrite/press`, `pywinauto` |
| Screen size / scaling | `get_screen_size` + OS scaling query | `pyautogui.size()` + OS DPI query |
| Window focus | observe + focus via interaction | `pywinauto` `set_focus()` / `win32gui` |

---

## Integration with Universal Patterns

This skill integrates with:
- **live-exploration-workflow**: Desktop implements the universal exploration pattern; its Verify step applies the desktop verify-and-classify rules (R1–R4, R9, R12) defined above
- **code-generation**: Desktop follows universal code generation quality gates and MUST emit the reusable `verified_interaction` / `locate_with_fallback` / `wait_for_expected_outcome` helpers (R14.3)
- **execution-validation**: Desktop uses universal execution and fixing loop; a desktop step passes only with verification evidence and any unverified/No-op/Wrong-target outcome makes the flow `FAILED` (R4, R13)
- **project-analysis**: Extended to detect desktop automation frameworks

**Desktop-Specific Additions:**
- Visual recognition strategies (OCR, image matching)
- Coordinate-based interaction patterns
- Screen capture and validation approaches
- Desktop application lifecycle management
- Windows-specific considerations

---

## Summary

Desktop automation with Desktop MCP focuses on **visual interaction** rather than programmatic element access. Success requires:

1. **Robust Visual Recognition**: Reliable OCR and image matching
2. **Smart Positioning**: Relative coordinates and region-based search
3. **Timing Management**: Appropriate waits for UI rendering
4. **State Control**: Consistent application state and environment
5. **Comprehensive Exploration**: Thorough capture of all visual elements and interactions

Follow the universal exploration pattern, adapt identification strategies to visual methods, and generate maintainable code that handles the unique challenges of desktop automation.
