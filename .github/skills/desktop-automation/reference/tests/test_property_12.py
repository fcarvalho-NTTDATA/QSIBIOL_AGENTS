"""Property-based test for Property 12: re-attempt with fresh state.

# Feature: desktop-automation-reliability, Property 12: Failed interactions are re-attempted with fresh state, recording results before each retry

**Validates: Requirements 12.1, 12.2, 12.5**

Property 12 (design "Correctness Properties"):

    For any failed interaction, the routine records the localization strategy,
    confidence, and verification result before initiating a re-attempt, captures
    a fresh Pre_Action_State and re-runs verification on each re-attempt, and
    performs no more than the configured maximum of 3 interaction attempts.

The test exercises :func:`verified_interaction` (Component 1, ``interaction.py``)
end to end with **all side-effecting dependencies injected** so the per-attempt
lifecycle is observable and **no real file I/O occurs**:

* a *recording focus manager* marks an attempt boundary on every
  ``has_focus`` confirmation (the first call of each attempt), so the test can
  number the attempts deterministically;
* a *stateful capture* returns an **attempt-encoded** Pre_Action_State
  (``("state", attempt)``) so a fresh capture taken on a later attempt differs
  from an earlier one — a re-used (stale) pre-capture would be detectable; on
  the designated *success attempt* the post-capture returns a distinct
  confirming state so verification confirms only then;
* a *recording performer* logs the action (with its attempt number and the
  resolved point), and
* a *recording, no-I/O evidence writer* logs each ``pre`` / ``post`` store
  keyed by the attempt number embedded in the evidence file name (R1.4).

Because every focus confirmation, pre-store, action, and post-store lands in one
ordered event log, the test asserts the exact per-attempt interleaving against
an **independent oracle** that re-derives the expected sequence purely from the
scenario (the attempt the interaction confirms on, or never). The oracle never
inspects the implementation's own retry bookkeeping, so the test cannot
tautologically agree with it.

The interaction is driven through an **ABSOLUTE-only** target, so localization
always succeeds on the first locate attempt (strategy ``ABSOLUTE``, confidence
``1.0``) and an action is performed on every attempt — isolating the *retry*
behavior under test. Localization is therefore never the reason a re-attempt
happens here; verification failure is, which is exactly what "re-runs
verification on each re-attempt" requires.

Everything is logic-only with mocked screen/clock/focus and an injected no-op
evidence writer (no real desktop, sleeps, or file I/O).
"""

from __future__ import annotations

import re
from pathlib import Path

from hypothesis import example, given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    FULL_SCREEN,
    Action,
    ExpectedOutcome,
    FailureCategory,
    FakeClock,
    FakeFocusManager,
    FakeImageMatcher,
    FakeOcrProvider,
    FinalStatus,
    InteractionStep,
    LocalizationStrategy,
    Region,
    ReliabilityConfig,
    TargetElement,
    Verdict,
    WindowRef,
    verified_interaction,
)

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# The configured maximum number of interaction attempts (R12.1). Read from the
# config so the test tracks the canonical constant rather than a magic number.
MAX_INTERACTION_ATTEMPTS = ReliabilityConfig().max_interaction_attempts  # 3

# A short verify timeout keeps the (virtual) verify-poll loop bounded on the
# failing path without affecting the retry invariants under test.
_VERIFY_TIMEOUT_SECONDS = 1

# The distinct, confirming Post_Action_State. The expected-outcome predicate
# holds iff the observed state equals this token, so verification CONFIRMS only
# on the designated success attempt.
_SUCCESS_STATE = "CONFIRMED_STATE"

# A bounded verification region (distinct from FULL_SCREEN) so pre/post/verify
# captures are distinguishable from the locator's full-screen captures.
_VERIFICATION_REGION = Region(x=2, y=3, width=4, height=5)

# The step identifier appears verbatim in evidence file names (safe alphabet),
# letting the writer parse the attempt number out of the path.
_STEP_ID = "retry-step"

_ATTEMPT_RE = re.compile(r"_attempt(\d+)_")


def _attempt_from_name(name: str) -> int:
    """Parse the 1-based attempt number out of an evidence file name (R1.4)."""

    match = _ATTEMPT_RE.search(name)
    assert match is not None, f"unexpected evidence file name: {name!r}"
    return int(match.group(1))


# ---------------------------------------------------------------------------
# Harness: run one verified_interaction with fully injected, recording deps.
# ---------------------------------------------------------------------------


def _run(success_attempt, action, point):
    """Drive one :func:`verified_interaction` with recording, no-I/O dependencies.

    ``success_attempt`` is the 1-based attempt on which verification should
    confirm, or ``None`` to never confirm (forcing exhaustion of the re-attempt
    budget). The target carries *only* an absolute coordinate, so localization
    resolves via the ABSOLUTE strategy on every attempt and an action is always
    performed.

    Returns ``(result, events, pre_frames, post_frames, state)`` where:

    * ``events`` is the shared, ordered log of ``("focus", attempt)`` /
      ``("pre", attempt)`` / ``("action", attempt, point)`` /
      ``("post", attempt)`` markers;
    * ``pre_frames`` / ``post_frames`` are ``(attempt, captured_state)`` pairs
      recorded by the evidence writer (no real file is ever written);
    * ``state`` exposes the shared counters, including ``full_screen_captures``
      (the number of fresh full-screen locate captures taken).
    """

    config = ReliabilityConfig(verify_timeout_seconds=_VERIFY_TIMEOUT_SECONDS)
    clock = FakeClock()
    window = WindowRef(id=1, title="App", origin=(0, 0))

    events: list = []
    pre_frames: list = []
    post_frames: list = []
    # ``attempt`` advances on each focus confirmation (the first call of every
    # attempt); ``acted`` flips when the action runs and resets each attempt.
    state = {"attempt": 0, "acted": False, "full_screen_captures": 0}

    # Real focus state/logic lives in the fake; the wrapper only observes order
    # and marks attempt boundaries. The window starts focused so ``has_focus``
    # returns True and no ``set_focus`` is needed — one focus op per attempt.
    inner_focus = FakeFocusManager(focused=window)

    class _RecordingFocusManager:
        """Marks an attempt boundary on each focus confirmation (R11.1)."""

        def has_focus(self, w: object) -> bool:
            state["attempt"] += 1
            state["acted"] = False
            events.append(("focus", state["attempt"]))
            return inner_focus.has_focus(w)

        def set_focus(self, w: object) -> None:  # pragma: no cover - never hit
            inner_focus.set_focus(w)
            events.append(("set_focus", state["attempt"]))

    focus_manager = _RecordingFocusManager()

    def capture(region):
        """Return an attempt-encoded state; the confirming state only on success."""

        if region is FULL_SCREEN:
            # The locator captures a fresh full-screen frame each attempt (R9.1).
            state["full_screen_captures"] += 1
        attempt = state["attempt"]
        if (
            state["acted"]
            and success_attempt is not None
            and attempt == success_attempt
        ):
            # Post-action state on the success attempt: the expected outcome.
            return _SUCCESS_STATE
        # Pre-action state, and the (unchanged) post state on failing attempts:
        # encoded by attempt number so a fresh capture differs across attempts,
        # and pre == post on a failing attempt -> NO_OP_CLICK.
        return ("state", attempt)

    def perform(performed_action, performed_point):
        state["acted"] = True
        events.append(("action", state["attempt"], performed_point))

    def writer(capture_obj, path):
        # Recording, no-I/O evidence writer: classify the store by the phase
        # suffix and parse the attempt number from the file name (R1.4).
        name = Path(path).name
        attempt = _attempt_from_name(name)
        if name.endswith("_pre.png"):
            events.append(("pre", attempt))
            pre_frames.append((attempt, capture_obj))
        elif name.endswith("_post.png"):
            events.append(("post", attempt))
            post_frames.append((attempt, capture_obj))

    step = InteractionStep(
        id=_STEP_ID,
        target=TargetElement(absolute=point),
        action=action,
        target_window=window,
        verification_region=_VERIFICATION_REGION,
    )
    expected = ExpectedOutcome(
        description="post-state equals the confirming state",
        predicate=lambda s: s == _SUCCESS_STATE,
        region=_VERIFICATION_REGION,
    )

    result = verified_interaction(
        step,
        expected,
        config,
        capture=capture,
        perform_interaction=perform,
        image_matcher=FakeImageMatcher(default=0.0),
        ocr_provider=FakeOcrProvider(default=""),
        focus_manager=focus_manager,
        clock=clock,
        evidence_writer=writer,
    )
    return result, events, pre_frames, post_frames, state


# ---------------------------------------------------------------------------
# Property 12 - re-attempt with fresh state, recording results before retry
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES, deadline=None)
@given(
    success_attempt=st.one_of(st.none(), st.integers(min_value=1, max_value=4)),
    action=st.sampled_from(list(Action)),
    point=st.tuples(
        st.integers(min_value=-2000, max_value=2000),
        st.integers(min_value=-2000, max_value=2000),
    ),
)
# Anchor the key retry scenarios so they are always exercised:
@example(success_attempt=None, action=Action.CLICK, point=(10, 20))  # full exhaustion
@example(success_attempt=2, action=Action.CLICK, point=(5, 5))       # fail then confirm
@example(success_attempt=4, action=Action.CLICK, point=(7, 7))       # beyond cap -> exhaust
def test_property_12_reattempt_with_fresh_state(success_attempt, action, point):
    # Feature: desktop-automation-reliability, Property 12: Failed interactions are re-attempted with fresh state, recording results before each retry
    result, events, pre_frames, post_frames, state = _run(
        success_attempt, action, point
    )

    # --- Independent oracle: number of attempts and the terminal verdict. ---
    confirms = success_attempt is not None and success_attempt <= MAX_INTERACTION_ATTEMPTS
    n = success_attempt if confirms else MAX_INTERACTION_ATTEMPTS

    # R12.1: no more than the configured maximum of 3 interaction attempts.
    assert n <= MAX_INTERACTION_ATTEMPTS
    assert result.record.attempts == n

    # Exact per-attempt interleaving: focus -> pre -> action -> post, repeated
    # once per attempt. This single equality establishes that each attempt runs
    # the full locate/interact/verify cycle in order.
    expected_events: list = []
    for i in range(1, n + 1):
        expected_events.append(("focus", i))
        expected_events.append(("pre", i))
        expected_events.append(("action", i, point))
        expected_events.append(("post", i))
    assert events == expected_events

    # R12.2: a fresh Pre_Action_State is captured each attempt. The captured
    # pre-states are attempt-encoded, so a re-used (stale) capture would repeat
    # attempt 1's frame; distinct frames prove a new capture happened each time.
    assert pre_frames == [(i, ("state", i)) for i in range(1, n + 1)]
    captured_pre = [frame for _, frame in pre_frames]
    assert len(set(captured_pre)) == n  # all distinct -> all fresh
    # A fresh full-screen locate capture also occurred once per attempt (R9.1).
    assert state["full_screen_captures"] == n

    # R12.2: verification is re-run on each re-attempt - one post-capture (the
    # state verification inspects) recorded per attempt, in attempt order.
    assert [attempt for attempt, _ in post_frames] == list(range(1, n + 1))

    # The localization strategy and confidence are recorded (ABSOLUTE wins).
    assert result.record.localization_strategy is LocalizationStrategy.ABSOLUTE
    assert result.record.confidence == 1.0

    # R12.5: for every re-attempt boundary, the prior attempt's verdict-producing
    # steps (action + post-capture/verify) complete before the re-attempt's fresh
    # pre-capture begins -> results are recorded before each retry is initiated.
    focus_positions = [idx for idx, ev in enumerate(events) if ev[0] == "focus"]
    post_positions = [idx for idx, ev in enumerate(events) if ev[0] == "post"]
    pre_positions = [idx for idx, ev in enumerate(events) if ev[0] == "pre"]
    for i in range(1, n):  # each retry: attempt i -> attempt i+1
        assert post_positions[i - 1] < focus_positions[i]
        assert post_positions[i - 1] < pre_positions[i]

    # --- Terminal outcome ---------------------------------------------------
    if confirms:
        # Confirmed on attempt n: a verified, evidence-backed success.
        assert result.succeeded
        assert result.record.final_status is FinalStatus.SUCCESS
        assert result.record.verification is Verdict.CONFIRMED
        assert result.failure_report is None
    else:
        # Never confirmed: failed after exactly the maximum attempts, escalated
        # with the recorded strategy/confidence/verdict carried into the report.
        assert not result.succeeded
        assert result.record.attempts == MAX_INTERACTION_ATTEMPTS
        assert result.record.final_status is FinalStatus.FAILED
        assert result.record.verification is Verdict.NO_OP_CLICK
        assert result.failure_report is not None
        assert result.failure_report.localization_strategy is LocalizationStrategy.ABSOLUTE
        assert result.failure_report.confidence == 1.0
        assert result.failure_report.verification is Verdict.NO_OP_CLICK
        assert result.failure_report.category is FailureCategory.CODE_ISSUE


# ---------------------------------------------------------------------------
# Property 12 - deterministic exhaustion: exactly three attempts on failure
# ---------------------------------------------------------------------------


def test_property_12_exhausts_three_attempts_recording_before_each_retry():
    # Feature: desktop-automation-reliability, Property 12: Failed interactions are re-attempted with fresh state, recording results before each retry
    """A never-confirming interaction re-attempts exactly 3 times with fresh state.

    Spells out the full retry sequence: three attempts, each capturing a fresh
    Pre_Action_State and re-running verification, with the prior attempt's
    results recorded before each re-attempt (R12.1/R12.2/R12.5).
    """

    point = (12, 34)
    result, events, pre_frames, post_frames, state = _run(None, Action.CLICK, point)

    # R12.1: exactly the configured maximum of 3 attempts, never confirmed.
    assert result.record.attempts == MAX_INTERACTION_ATTEMPTS == 3
    assert not result.succeeded
    assert result.record.verification is Verdict.NO_OP_CLICK
    assert result.failure_report is not None

    # Full ordered lifecycle: focus -> pre -> action -> post, three times over.
    assert events == [
        ("focus", 1), ("pre", 1), ("action", 1, point), ("post", 1),
        ("focus", 2), ("pre", 2), ("action", 2, point), ("post", 2),
        ("focus", 3), ("pre", 3), ("action", 3, point), ("post", 3),
    ]

    # R12.2: a fresh, distinct Pre_Action_State captured on every attempt.
    assert pre_frames == [(1, ("state", 1)), (2, ("state", 2)), (3, ("state", 3))]
    assert [attempt for attempt, _ in post_frames] == [1, 2, 3]
    assert state["full_screen_captures"] == 3
