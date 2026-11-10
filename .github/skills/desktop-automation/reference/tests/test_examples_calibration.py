"""Example tests for multi-monitor Click_Offset correction (Requirement 16).

These are *example/unit* tests that complement the exhaustive Property 15/16
tests by pinning two concrete, human-readable multi-monitor scenarios end to end
through :func:`verified_interaction`:

- **Single monitor (R16.12):** with no click offset supplied (the identity), the
  commanded interaction point equals the resolved point — the resolver never
  moves a coordinate on a single-plane desktop.
- **Non-primary monitor with a stable offset (R16.6/R16.10/R16.17):** a window on
  a second monitor whose capture plane diverges from its click plane by a
  constant vector. After calibration produces a *stable* Click_Offset, the
  verified-interaction routine routes the resolved point through the
  offset-correcting resolver, so the commanded click lands at
  ``resolved + offset`` — the spot the element actually occupies in the click
  plane.

The scenario uses the deterministic fakes (no real desktop/clock/focus/IO). The
target locates via absolute coordinates (confidence 1.0) so the resolved point
is known exactly and the only variable under test is the offset correction.

Requirements: 16.6, 16.10, 16.12, 16.17
"""

from __future__ import annotations

from desktop_reliability import (
    FULL_SCREEN,
    Action,
    Calibrator,
    ClickOffset,
    ExpectedOutcome,
    FakeClock,
    FakeFocusManager,
    FakeImageMatcher,
    FakeOcrProvider,
    FakeScreen,
    InteractionStep,
    Monitor,
    ReliabilityConfig,
    TargetElement,
    Verdict,
    WindowRef,
    verified_interaction,
)

# The element is recorded at this absolute point (the capture/read plane).
RESOLVED_POINT = (1300, 420)

# A "screen state" token that satisfies the expected outcome after the click.
CONFIRMED_STATE = "saved"


def _run(*, click_offset):
    """Drive verified_interaction with a locatable target and a recording performer.

    Returns ``(result, perform_calls)`` where ``perform_calls`` records the exact
    point the interaction was commanded at, so the test can assert the
    offset-corrected coordinate.
    """

    window = WindowRef(id=7, title="app", origin=(1280, 0))
    target = TargetElement(absolute=RESOLVED_POINT)
    step = InteractionStep(
        id="calib-step",
        target=target,
        action=Action.CLICK,
        target_window=window,
        verification_region=FULL_SCREEN,
    )
    expected = ExpectedOutcome(
        description="the post-state equals the confirmed state",
        predicate=lambda state: state == CONFIRMED_STATE,
        region=FULL_SCREEN,
    )

    screen = FakeScreen(frames=["pre", "locate", CONFIRMED_STATE], default=CONFIRMED_STATE)
    perform_calls = []

    result = verified_interaction(
        step,
        expected,
        ReliabilityConfig(),
        capture=screen.capture,
        perform_interaction=lambda action, point: perform_calls.append((action, point)),
        image_matcher=FakeImageMatcher(default=0.0),
        ocr_provider=FakeOcrProvider(default=""),
        focus_manager=FakeFocusManager(),
        clock=FakeClock(),
        click_offset=click_offset,
        evidence_writer=lambda capture, path: None,
        evidences_root="/tmp/desktop-reliability-calibration-test",
    )
    return result, perform_calls


def test_single_monitor_identity_leaves_point_unchanged():
    """On a single-plane desktop the commanded point equals the resolved point (R16.12)."""
    result, perform_calls = _run(click_offset=None)

    assert result.succeeded is True
    assert result.record.verification is Verdict.CONFIRMED
    # No offset -> the resolver is the identity: commanded == resolved.
    assert perform_calls == [(Action.CLICK, RESOLVED_POINT)]


def test_zero_offset_identity_leaves_point_unchanged():
    """An explicit zero (single-monitor) offset is also the identity (R16.12)."""
    result, perform_calls = _run(click_offset=ClickOffset.zero())

    assert result.succeeded is True
    assert perform_calls == [(Action.CLICK, RESOLVED_POINT)]


def test_stable_offset_corrects_commanded_point_on_non_primary_monitor():
    """A stable Click_Offset shifts the commanded click to the real target (R16.6/R16.10/R16.17)."""
    # Calibration on the second monitor measured a constant divergence: the
    # element reads 11px right and 7px down from where the click actually lands.
    second_monitor = Monitor(origin=(1280, 0), width=1920, height=1080, primary=False)
    calibrator = Calibrator(monitor=second_monitor)
    # Two agreeing measurements => stable (commanded vs observed differ by (11,7)).
    calibrator.record(observed=(1311, 427), commanded=(1300, 420))
    calibrator.record(observed=(1312, 428), commanded=(1301, 421))
    offset = calibrator.offset()
    assert offset.stable is True

    result, perform_calls = _run(click_offset=offset)

    assert result.succeeded is True
    # The commanded point is the resolved point corrected by the stable offset.
    expected_point = (RESOLVED_POINT[0] + offset.vector[0], RESOLVED_POINT[1] + offset.vector[1])
    assert perform_calls == [(Action.CLICK, expected_point)]
    assert perform_calls[0][1] != RESOLVED_POINT  # the correction actually moved the click


def test_unstable_offset_is_not_applied():
    """An unstable offset must not move the commanded point (R16.13)."""
    unstable = ClickOffset(vector=(40, 25), stable=False)
    result, perform_calls = _run(click_offset=unstable)

    assert result.succeeded is True
    # Unstable -> resolver leaves the point unchanged.
    assert perform_calls == [(Action.CLICK, RESOLVED_POINT)]
