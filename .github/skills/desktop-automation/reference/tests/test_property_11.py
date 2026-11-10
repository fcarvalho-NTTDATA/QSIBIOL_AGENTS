"""Property-based test for Property 11: focus is confirmed before every interaction.

# Feature: desktop-automation-reliability, Property 11: Focus is confirmed before every interaction

**Validates: Requirements 11.1, 11.2**

Property 11 (design "Correctness Properties"):

    For any interaction, a window-focus confirmation occurs before the action is
    performed; when the target window does not already hold focus, focus is
    acquired before the action runs.

The test exercises :func:`verified_interaction` (Component 1, ``interaction.py``),
which calls ``ensure_window_focus`` at the start of every attempt — before the
pre-capture, localization, and the interaction itself. To make the *relative
order* of (focus confirmation / acquisition) vs. (the action) observable, both
the focus manager and the interaction performer write into a single shared,
ordered event log:

* :class:`_RecordingFocusManager` is a thin observation layer that **delegates**
  all focus state and logic to a real
  :class:`~desktop_reliability.fakes.FakeFocusManager` (so focus behavior is the
  fake's, not the test's) while appending each ``has_focus`` / ``set_focus`` call
  to the shared log.
* the recording performer appends an ``"action"`` event when the interaction is
  actually performed at the resolved point.

Because every focus op and every action lands in one ordered list, the test can
assert the exact interleaving against an **independent oracle** that re-derives
the expected event sequence purely from the scenario (initial focus state and
the number of attempts that perform an action). The oracle never inspects the
implementation's own focus logic, so the test cannot tautologically agree with
it.

Two initial states are covered (Property 11's two clauses):

* **already-focused** — a focus *confirmation* (``has_focus``) precedes the
  action and focus is **never** acquired (R11.1).
* **not-focused** — a focus *confirmation* precedes the action and focus is
  *acquired* (``set_focus``) after the confirmation and before the action
  (R11.2); on any subsequent attempt the window already holds focus, so no
  further acquisition occurs.

The interaction is driven through an ABSOLUTE-only target so localization always
succeeds on the first locate attempt and the action is always performed, letting
the focus/action ordering be asserted on every attempt. Everything is logic-only
with mocked screen/clock/focus and an injected no-op evidence writer (no real
desktop, sleeps, or file I/O).
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    Action,
    ExpectedOutcome,
    FakeClock,
    FakeFocusManager,
    FakeImageMatcher,
    FakeOcrProvider,
    FakeScreen,
    Frame,
    InteractionStep,
    ReliabilityConfig,
    TargetElement,
    WindowRef,
    verified_interaction,
)

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# A short verify timeout keeps the (virtual) verify-poll loop bounded on the
# failing path without affecting the focus-ordering invariant under test.
_VERIFY_TIMEOUT_SECONDS = 1


# ---------------------------------------------------------------------------
# Recording focus manager: observes ordering, delegates logic to the fake
# ---------------------------------------------------------------------------


class _RecordingFocusManager:
    """A focus manager that records op order while delegating to a FakeFocusManager.

    Satisfies the ``FocusManager`` contract (``has_focus`` / ``set_focus``).
    Every call is appended to the shared ``events`` log *and* forwarded to the
    wrapped :class:`FakeFocusManager`, so the real focus state/logic stays with
    the fake while the shared log captures the order of focus ops relative to
    the recorded action. This keeps the observation layer independent of the
    code under test.
    """

    def __init__(self, inner: FakeFocusManager, events: list) -> None:
        self._inner = inner
        self._events = events

    def has_focus(self, window: object) -> bool:
        result = self._inner.has_focus(window)
        self._events.append(("has_focus", window, result))
        return result

    def set_focus(self, window: object) -> None:
        self._inner.set_focus(window)
        self._events.append(("set_focus", window))


# ---------------------------------------------------------------------------
# Independent oracle
# ---------------------------------------------------------------------------


def _expected_events(
    initial_focused: bool,
    n_actions: int,
    window: object,
    action: Action,
    point: tuple,
) -> list:
    """Re-derive the expected focus/action event sequence (R11.1/R11.2).

    For each attempt that performs an action the routine must, in order:
    confirm focus (``has_focus``); when the window does not already hold focus,
    acquire it (``set_focus``); then perform the action. Acquiring focus makes
    the window focused for every later attempt, so ``set_focus`` happens at most
    once (only when the window started unfocused).
    """

    seq: list = []
    focused = initial_focused
    for _ in range(n_actions):
        seq.append(("has_focus", window, focused))  # R11.1: confirmation first
        if not focused:
            seq.append(("set_focus", window))  # R11.2: acquire only when missing
            focused = True
        seq.append(("action", action, point))  # the interaction itself
    return seq


# ---------------------------------------------------------------------------
# Scenario strategy
# ---------------------------------------------------------------------------


@st.composite
def _focus_scenario(draw):
    """Generate a focus-before-interaction scenario.

    Produces both initial focus states (already-focused vs. not-focused), a
    ``confirmed`` flag that controls how many attempts perform an action (one on
    confirmation, the full re-attempt budget on a never-confirming outcome), and
    an ABSOLUTE-only target whose coordinate is the point the action lands on.
    """

    initial_focused = draw(st.booleans())
    confirmed = draw(st.booleans())
    action = draw(st.sampled_from(list(Action)))
    point = draw(
        st.tuples(
            st.integers(min_value=0, max_value=2000),
            st.integers(min_value=0, max_value=2000),
        )
    )
    window_id = draw(st.integers(min_value=1, max_value=1000))
    return initial_focused, confirmed, action, point, window_id


# ---------------------------------------------------------------------------
# Property 11 - focus is confirmed before every interaction
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_focus_scenario())
def test_property_11_focus_confirmed_before_every_interaction(scenario):
    # Feature: desktop-automation-reliability, Property 11: Focus is confirmed before every interaction
    initial_focused, confirmed, action, point, window_id = scenario

    window = WindowRef(id=window_id, title=f"win-{window_id}")
    # ABSOLUTE-only target: image/OCR/anchor/window strategies are inapplicable,
    # so the ranked locator always falls through to ABSOLUTE and resolves to
    # ``point`` on the first locate attempt - the action is therefore performed
    # on every interaction attempt, letting the focus/action ordering be checked.
    target = TargetElement(absolute=point)
    step = InteractionStep(id="step-focus", target=target, action=action, target_window=window)

    # The predicate is constant per scenario: True confirms on the first attempt
    # (one action); False never confirms, exhausting the re-attempt budget (an
    # action per attempt). Either way focus must precede each action.
    expected = ExpectedOutcome(
        description="constant outcome", predicate=lambda _state: confirmed
    )
    config = ReliabilityConfig(verify_timeout_seconds=_VERIFY_TIMEOUT_SECONDS)

    # Shared, ordered event log written by both the focus manager and performer.
    events: list = []

    inner_focus = (
        FakeFocusManager(focused=window) if initial_focused else FakeFocusManager()
    )
    focus_manager = _RecordingFocusManager(inner_focus, events)

    def performer(performed_action, performed_point):
        events.append(("action", performed_action, performed_point))

    frame = Frame.of([[1]])
    screen = FakeScreen(default=frame)
    clock = FakeClock()

    result = verified_interaction(
        step,
        expected,
        config,
        capture=screen.capture,
        perform_interaction=performer,
        image_matcher=FakeImageMatcher(default=0.0),
        ocr_provider=FakeOcrProvider(default=""),
        focus_manager=focus_manager,
        clock=clock,
        evidence_writer=lambda _capture, _path: None,  # no real file I/O
    )

    # Number of attempts that perform an action: confirmation succeeds on the
    # first attempt; otherwise every attempt up to the budget runs an action.
    n_actions = 1 if confirmed else config.max_interaction_attempts
    assert result.succeeded is confirmed

    # --- Independent oracle: exact focus/action interleaving ---------------
    expected_events = _expected_events(initial_focused, n_actions, window, action, point)
    assert events == expected_events

    # --- Cross-checks of the two clauses, derived directly from the log ----
    action_indices = [i for i, ev in enumerate(events) if ev[0] == "action"]
    assert len(action_indices) == n_actions

    for idx in action_indices:
        # R11.1: a focus confirmation precedes this action.
        confirmations_before = [
            j for j, ev in enumerate(events[:idx]) if ev[0] == "has_focus"
        ]
        assert confirmations_before, "no focus confirmation before the action"
        last_confirmation = confirmations_before[-1]
        # R11.2: when that confirmation reported the window unfocused, focus is
        # acquired after the confirmation and before the action.
        if events[last_confirmation][2] is False:
            acquisitions = [
                k
                for k in range(last_confirmation + 1, idx)
                if events[k][0] == "set_focus"
            ]
            assert acquisitions, "focus not acquired before the action when unfocused"

    # R11.2 boundary: focus is acquired exactly once when the window started
    # unfocused, and never when it already held focus.
    assert inner_focus.focus_changes == (0 if initial_focused else 1)


# ---------------------------------------------------------------------------
# Property 11 - acquisition ordering when the window starts unfocused
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(
    action=st.sampled_from(list(Action)),
    point=st.tuples(
        st.integers(min_value=0, max_value=2000),
        st.integers(min_value=0, max_value=2000),
    ),
)
def test_property_11_focus_acquired_before_action_when_not_focused(action, point):
    # Feature: desktop-automation-reliability, Property 11: Focus is confirmed before every interaction
    window = WindowRef(id=7, title="unfocused-window")
    target = TargetElement(absolute=point)
    step = InteractionStep(id="step-acquire", target=target, action=action, target_window=window)

    # Confirm on the first attempt so exactly one action is performed; this
    # isolates the not-already-focused acquisition ordering (R11.2).
    expected = ExpectedOutcome(description="confirmed", predicate=lambda _state: True)
    config = ReliabilityConfig(verify_timeout_seconds=_VERIFY_TIMEOUT_SECONDS)

    events: list = []
    inner_focus = FakeFocusManager()  # nothing holds focus initially
    focus_manager = _RecordingFocusManager(inner_focus, events)

    def performer(performed_action, performed_point):
        events.append(("action", performed_action, performed_point))

    screen = FakeScreen(default=Frame.of([[1]]))

    result = verified_interaction(
        step,
        expected,
        config,
        capture=screen.capture,
        perform_interaction=performer,
        image_matcher=FakeImageMatcher(default=0.0),
        ocr_provider=FakeOcrProvider(default=""),
        focus_manager=focus_manager,
        clock=FakeClock(),
        evidence_writer=lambda _capture, _path: None,
    )

    assert result.succeeded is True

    # Exactly one of each op, in the order: confirm (False) -> acquire -> action.
    assert events == [
        ("has_focus", window, False),
        ("set_focus", window),
        ("action", action, point),
    ]
    assert inner_focus.focus_changes == 1
    # After acquisition the fake reports the target window as focused.
    assert inner_focus.has_focus(window) is True
