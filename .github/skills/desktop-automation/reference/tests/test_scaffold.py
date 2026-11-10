"""Generated-code scaffold check (R14.2 / R14.3) — the Layer 3 structural check.

This is a *smoke / structural* check (not a property test) that a generated
desktop-automation project conforms to the reusable reliability scaffold the
governing documents require. It runs against this **reference implementation**
as the canonical exemplar (``code-generation/SKILL.md`` points generated
projects here), so "does a generated project mirror the required scaffold?" is
verified by checking that the canonical scaffold itself holds.

It verifies the three things R14.2/R14.3 demand of a generated desktop project:

1. **The reusable helpers are exposed/importable** — the project ships
   ``verified_interaction`` (the verified-interaction routine), the
   ``locate_with_fallback`` locator, and a wait-for-expected-outcome verifier.
   The design's "Plane B" names the verifier helper
   ``wait_for_expected_outcome``; in this reference (and the design's
   Action_Verifier) it is implemented as ``verify_and_classify`` (see
   ``design.md`` "Component 3: Action_Verifier (``wait_for_expected_outcome`` +
   ``classify``)" and the package ``__init__`` exports). This test asserts the
   verifier helper is exposed under that canonical name.

2. **The verified-interaction lifecycle routes pre → interact → post → verify**
   — a single ``verified_interaction`` call is driven end to end over the
   deterministic fakes and is shown to (a) capture *before* the action, (b)
   perform the action at the point the locator resolved, (c) capture *after* the
   action, and (d) gate success on a CONFIRMED verifier verdict. A
   non-confirming verdict is shown to never produce a success — there is no path
   that returns success without verification (R4 / no false positives).

3. **Interactions route through the helpers, not raw framework primitives** — a
   source scan of the ``desktop_reliability`` package asserts the package never
   calls ``pyautogui.click`` / ``pyautogui.typewrite`` (nor imports
   ``pyautogui``) directly; interactions go through the injected performer
   abstraction (``InteractionPerformer``) instead.

Requirements: 14.2, 14.3
"""

from __future__ import annotations

import re
from pathlib import Path

import desktop_reliability
from desktop_reliability import (
    FULL_SCREEN,
    Action,
    ExpectedOutcome,
    FakeClock,
    FakeFocusManager,
    FakeImageMatcher,
    FakeOcrProvider,
    FakeScreen,
    FinalStatus,
    Frame,
    ImageMatchResult,
    ImageRef,
    InteractionPerformer,
    InteractionResult,
    InteractionStep,
    LocalizationStrategy,
    ReliabilityConfig,
    TargetElement,
    Verdict,
    WindowRef,
    classify_failure,
    locate_with_fallback,
    verified_interaction,
    verify_and_classify,
)


# ---------------------------------------------------------------------------
# 1. The reusable helpers are exposed/importable under their canonical names.
# ---------------------------------------------------------------------------
#
# The design's "Plane B" requires a generated project to ship three reusable
# helpers: ``verified_interaction``, ``locate_with_fallback``, and a
# wait-for-expected-outcome verifier. The verifier is implemented as
# ``verify_and_classify`` (the design's Action_Verifier); this is the canonical
# name the reference exports and the name generated projects mirror.


def test_reusable_helpers_are_exposed():
    """The verified-interaction routine + locate/verify helpers are importable."""
    # Verified-Interaction Routine (pre → interact → post → verify).
    assert callable(verified_interaction)
    # Ranked localization helper.
    assert callable(locate_with_fallback)
    # Wait-for-expected-outcome verifier (design's wait_for_expected_outcome ==
    # this implementation's verify_and_classify / Action_Verifier).
    assert callable(verify_and_classify)
    # Failure classification helper that the routine escalates to.
    assert callable(classify_failure)


def test_helpers_are_part_of_the_public_api():
    """The helpers are exported from the package's public ``__all__`` surface."""
    public = set(desktop_reliability.__all__)
    for name in (
        "verified_interaction",
        "locate_with_fallback",
        "verify_and_classify",
        "classify_failure",
        "InteractionPerformer",
    ):
        assert name in public, f"{name!r} must be part of the public scaffold API"


def test_interaction_performer_abstraction_is_exposed():
    """Interactions are performed via an injected performer abstraction, not raw clicks."""
    # InteractionPerformer is the seam through which clicks/types are routed, so
    # generated code never has to call a framework primitive inline.
    assert InteractionPerformer is not None


# ---------------------------------------------------------------------------
# Shared fixtures for the lifecycle smoke tests.
# ---------------------------------------------------------------------------

#: A reference image so localization resolves via the IMAGE_MATCH strategy.
_BUTTON = ImageRef(path="login_button.png", name="login")

#: The resolved on-screen point the (fake) image matcher reports.
_RESOLVED_POINT = (10, 20)


def _confirmed_frame() -> Frame:
    """A screen frame whose verification region shows the expected 'loaded' state."""
    return Frame.of([["loaded"]])


def _step() -> InteractionStep:
    """A simple click step located by image match, verified over the full screen."""
    return InteractionStep(
        id="login_click",
        target=TargetElement(reference=_BUTTON),
        action=Action.CLICK,
        target_window=WindowRef(id=1, title="App", origin=(0, 0)),
        verification_region=FULL_SCREEN,
    )


def _expected(predicate) -> ExpectedOutcome:
    return ExpectedOutcome(
        description="app reaches the 'loaded' state",
        predicate=predicate,
        region=FULL_SCREEN,
    )


def _run_interaction(predicate, *, config=None):
    """Drive one ``verified_interaction`` over the fakes, recording the lifecycle.

    Returns ``(result, events, performed, focus_manager)`` where ``events`` is the
    ordered capture/perform lifecycle log and ``performed`` is the list of
    ``(action, point)`` the performer received.
    """
    config = config or ReliabilityConfig()
    screen = FakeScreen(default=_confirmed_frame())
    clock = FakeClock()
    focus = FakeFocusManager()
    matcher = FakeImageMatcher(default=ImageMatchResult(confidence=0.95, point=_RESOLVED_POINT))
    ocr = FakeOcrProvider()

    events: list = []
    performed: list = []

    def capture(region):
        events.append(("capture", region))
        return screen.capture(region)

    def perform(action, point):
        events.append(("perform", action, point))
        performed.append((action, point))

    written: list = []

    result = verified_interaction(
        _step(),
        _expected(predicate),
        config,
        capture=capture,
        perform_interaction=perform,
        image_matcher=matcher,
        ocr_provider=ocr,
        focus_manager=focus,
        clock=clock,
        evidence_writer=lambda cap, path: written.append(str(path)),
    )
    return result, events, performed, focus, matcher


# ---------------------------------------------------------------------------
# 2. The verified-interaction lifecycle: pre → interact → post → verify.
# ---------------------------------------------------------------------------


def test_lifecycle_routes_pre_interact_post_verify_on_success():
    """A CONFIRMED interaction captures pre, acts, captures post, and verifies."""
    result, events, performed, focus, matcher = _run_interaction(
        predicate=lambda post: isinstance(post, Frame) and any("loaded" in row for row in post.pixels)
    )

    # Success is granted, and only because a CONFIRMED verdict backed by stored
    # post-evidence was produced (R2.3 / R4.1 / R4.2).
    assert isinstance(result, InteractionResult)
    assert result.succeeded is True
    assert result.record.final_status is FinalStatus.SUCCESS
    assert result.record.verification is Verdict.CONFIRMED
    assert result.record.post_evidence, "a Post_Action_State must be stored as evidence"
    assert result.record.pre_evidence, "a Pre_Action_State must be stored as evidence"

    # The locator ran and the routine recorded the producing strategy (R5.4),
    # i.e. verified_interaction orchestrates locate_with_fallback.
    assert matcher.call_count > 0
    assert result.record.localization_strategy is LocalizationStrategy.IMAGE_MATCH

    # The action was performed at the point the locator resolved (R11.3) —
    # interaction routes through the located coordinate, not a raw guess.
    assert performed == [(Action.CLICK, _RESOLVED_POINT)]

    # Focus was confirmed before the interaction lifecycle (R11.1).
    assert focus.operations, "window focus must be confirmed before interacting"

    # Ordering: a pre-capture strictly before the action and a post-capture
    # after it (pre → interact → post).
    perform_index = next(i for i, e in enumerate(events) if e[0] == "perform")
    captures_before = [i for i, e in enumerate(events) if e[0] == "capture" and i < perform_index]
    captures_after = [i for i, e in enumerate(events) if e[0] == "capture" and i > perform_index]
    assert captures_before, "must capture a Pre_Action_State before the interaction"
    assert captures_after, "must capture a Post_Action_State after the interaction"


def test_success_requires_a_confirmed_verdict_no_false_positive():
    """A non-confirming verdict never yields success, even though the click happened."""
    # The expected outcome never holds, and the screen never changes, so the
    # verifier classifies a No-op — there is no path to success without a
    # CONFIRMED verdict (R4 / R13).
    result, _events, performed, _focus, _matcher = _run_interaction(
        predicate=lambda post: False
    )

    assert result.succeeded is False
    assert result.record.final_status is FinalStatus.FAILED
    assert result.record.verification is Verdict.NO_OP_CLICK
    # The interaction *was* attempted (the lifecycle ran), but unverified work
    # is treated as failure and escalated with a report.
    assert performed, "the interaction should still have been attempted"
    assert result.failure_report is not None
    assert result.failure_report.category is not None


def test_verify_and_classify_is_the_outcome_gate():
    """The wait-for-expected-outcome verifier returns the lifecycle's verdict directly."""
    confirmed = Frame.of([["loaded"]])
    verdict = verify_and_classify(
        pre=confirmed,
        post=confirmed,
        expected=_expected(
            lambda post: isinstance(post, Frame) and any("loaded" in row for row in post.pixels)
        ),
        config=ReliabilityConfig(),
        clock=FakeClock(),
    )
    assert verdict is Verdict.CONFIRMED


# ---------------------------------------------------------------------------
# 3. Interactions route through the helpers, not raw framework primitives.
# ---------------------------------------------------------------------------

#: The raw framework primitives a generated project must NOT call inline; all
#: clicks/types route through the injected ``InteractionPerformer`` instead.
_RAW_CALL_PATTERNS = (
    re.compile(r"pyautogui\s*\.\s*click\s*\("),
    re.compile(r"pyautogui\s*\.\s*typewrite\s*\("),
)
_RAW_IMPORT_PATTERN = re.compile(r"^\s*(?:import\s+pyautogui|from\s+pyautogui\s+import)", re.MULTILINE)


def _package_source_files() -> list:
    """Every ``.py`` file in the reusable ``desktop_reliability`` package."""
    package_dir = Path(desktop_reliability.__file__).parent
    files = sorted(package_dir.glob("*.py"))
    assert files, "expected to find the desktop_reliability package source files"
    return files


def test_package_does_not_call_raw_pyautogui_primitives():
    """No package file calls pyautogui.click()/typewrite() directly (R14.2)."""
    offenders: dict = {}
    for path in _package_source_files():
        source = path.read_text(encoding="utf-8")
        hits = [p.pattern for p in _RAW_CALL_PATTERNS if p.search(source)]
        if hits:
            offenders[path.name] = hits
    assert not offenders, (
        "interactions must route through the injected performer abstraction, "
        f"not raw framework primitives; found direct calls: {offenders}"
    )


def test_package_does_not_import_pyautogui():
    """The reusable package takes its click/type performer by injection, not import."""
    offenders = [
        path.name
        for path in _package_source_files()
        if _RAW_IMPORT_PATTERN.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "the desktop_reliability package must not import pyautogui directly; "
        f"these files import it: {offenders}"
    )


def test_single_source_of_success_is_gated_on_confirmed():
    """The routine grants success in exactly one place, guarded by a CONFIRMED verdict."""
    from desktop_reliability import interaction as interaction_mod

    source = Path(interaction_mod.__file__).read_text(encoding="utf-8")
    # Exactly one place returns a success result...
    assert source.count("InteractionResult.success(") == 1
    # ...and a CONFIRMED-verdict guard exists, so success cannot be returned
    # without verification (R4 / no "assume success" branch).
    assert "verdict == Verdict.CONFIRMED" in source
