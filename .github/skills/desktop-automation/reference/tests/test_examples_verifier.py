"""Example tests for representative No-op and Wrong-target verdicts.

These are *example/unit* tests for the Action_Verifier (``verify_and_classify``)
that complement the exhaustive ``Property 1`` property test (task 3.2). Where the
property test asserts the classification invariant holds across *all* generated
inputs, these tests pin two concrete, human-readable scenarios so the No-op and
Wrong-target branches stay anchored to a recognizable real-world situation:

- **NO_OP_CLICK** (R3.1): a "Save" interaction was expected to surface a
  "saved" confirmation in the status bar, but the click hit a disabled control
  and nothing in the verification region changed — the post-state is
  region-identical to the pre-state, so the verdict is ``NO_OP_CLICK``.
- **WRONG_TARGET_CLICK** (R3.2): the click landed on the wrong control, so the
  status bar *did* change (a menu opened) but the expected "saved" confirmation
  never appeared — the post-state differs from the pre-state yet fails the
  expected predicate, so the verdict is ``WRONG_TARGET_CLICK``.

A CONFIRMED contrast case using the same fixtures anchors that the scenario
frames and predicate are well-formed (the expected outcome is reachable), and a
polling variant exercises the R2.5 poll-until-timeout path with the deterministic
``FakeClock``/``FakeScreen`` so there are no real sleeps and no real desktop.

Requirements: 3.1, 3.2
"""

from __future__ import annotations

from desktop_reliability import (
    FULL_SCREEN,
    ExpectedOutcome,
    FakeClock,
    FakeScreen,
    Frame,
    Region,
    ReliabilityConfig,
    Verdict,
    verify_and_classify,
)


# ---------------------------------------------------------------------------
# Scenario fixtures: a small application window whose bottom row is the status
# bar used as the Verification_Region. Each "pixel" is a hashable token.
# ---------------------------------------------------------------------------

#: The Verification_Region: the bottom status-bar row of the 4x4 window.
STATUS_REGION = Region(x=0, y=3, width=4, height=1)


def _screen(status_row):
    """Build a 4x4 window frame with ``status_row`` as the bottom status bar."""
    return Frame.of(
        [
            ["title", "title", "title", "close"],
            ["doc", "doc", "doc", "doc"],
            ["doc", "doc", "doc", "doc"],
            list(status_row),
        ]
    )


#: Pre-action state: editor is idle, status bar shows the Save control + "ready".
IDLE = _screen(["save", "btn", "ready", "idle"])

#: No-op post-state: byte-for-byte identical status bar (the click changed nothing).
NO_OP_POST = _screen(["save", "btn", "ready", "idle"])

#: Wrong-target post-state: the status bar changed (a menu opened) but no "saved".
WRONG_TARGET_POST = _screen(["save", "btn", "menu", "open"])

#: Confirmed post-state: the expected "saved" confirmation appears in the region.
CONFIRMED_POST = _screen(["save", "btn", "saved", "ok"])


def _shows_saved(post) -> bool:
    """Expected outcome predicate: the status region reports a 'saved' confirmation."""
    if not isinstance(post, Frame):
        return False
    cropped = post.crop(STATUS_REGION)
    return any("saved" in row for row in cropped.pixels)


def _save_outcome() -> ExpectedOutcome:
    """The Expected_Outcome shared by every scenario: a 'saved' status appears."""
    return ExpectedOutcome(
        description="status bar shows a 'saved' confirmation",
        predicate=_shows_saved,
        region=STATUS_REGION,
    )


def _save_outcome_full_screen() -> ExpectedOutcome:
    """A full-screen variant of the Expected_Outcome for the polling scenario.

    Using ``FULL_SCREEN`` as the verification region means re-captured frames are
    returned uncropped by ``FakeScreen.capture``, so the polling loop compares
    whole frames (no double-cropping when a re-capture source is injected).
    """
    return ExpectedOutcome(
        description="status bar shows a 'saved' confirmation",
        predicate=_shows_saved,
        region=FULL_SCREEN,
    )


# ---------------------------------------------------------------------------
# NO_OP_CLICK (R3.1): nothing changed within the verification region.
# ---------------------------------------------------------------------------


def test_no_op_click_when_region_unchanged():
    """An unchanged region after an expected-to-change click is a No-op (R3.1)."""
    verdict = verify_and_classify(
        pre=IDLE,
        post=NO_OP_POST,
        expected=_save_outcome(),
        config=ReliabilityConfig(),
        clock=FakeClock(),
    )
    assert verdict is Verdict.NO_OP_CLICK


def test_no_op_click_polls_until_timeout_then_classifies():
    """A No-op still polls up to the verify timeout before concluding (R2.5/R3.1).

    With a re-capture source that keeps returning the same unchanged status bar,
    the verifier polls (advancing the virtual clock) until the deadline, then
    classifies the unchanged region as a No-op. No real time elapses.
    """
    config = ReliabilityConfig(verify_timeout_seconds=2)
    clock = FakeClock()
    # Every re-capture returns the same unchanged post-state.
    screen = FakeScreen(default=NO_OP_POST)

    verdict = verify_and_classify(
        pre=IDLE,
        post=NO_OP_POST,
        expected=_save_outcome_full_screen(),
        config=config,
        clock=clock,
        recapture=screen.capture,
    )

    assert verdict is Verdict.NO_OP_CLICK
    # The loop advanced the virtual clock to (at least) the deadline by polling.
    assert clock.total_slept >= config.verify_timeout_seconds
    # At least one fresh post-state was re-captured while polling.
    assert screen.capture_count >= 1


# ---------------------------------------------------------------------------
# WRONG_TARGET_CLICK (R3.2): region changed, but not into the expected outcome.
# ---------------------------------------------------------------------------


def test_wrong_target_click_when_region_changes_unexpectedly():
    """A changed region that fails the expected predicate is a Wrong-target (R3.2)."""
    verdict = verify_and_classify(
        pre=IDLE,
        post=WRONG_TARGET_POST,
        expected=_save_outcome(),
        config=ReliabilityConfig(),
        clock=FakeClock(),
    )
    assert verdict is Verdict.WRONG_TARGET_CLICK


# ---------------------------------------------------------------------------
# CONFIRMED contrast: the same fixtures can reach success, proving the scenario
# is well-formed (the No-op/Wrong-target verdicts are not artifacts of an
# impossible expected outcome).
# ---------------------------------------------------------------------------


def test_confirmed_contrast_with_same_fixtures():
    """With the expected 'saved' confirmation present, the verdict is CONFIRMED."""
    verdict = verify_and_classify(
        pre=IDLE,
        post=CONFIRMED_POST,
        expected=_save_outcome(),
        config=ReliabilityConfig(),
        clock=FakeClock(),
    )
    assert verdict is Verdict.CONFIRMED
