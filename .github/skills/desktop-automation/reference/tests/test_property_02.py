"""Property-based test for Property 2: success requires confirmed evidence.

# Feature: desktop-automation-reliability, Property 2: Success requires confirmed verification evidence (no false positives)

**Validates: Requirements 2.3, 2.4, 3.3, 3.4, 4.1, 4.2, 13.1**

Property 2 (design "Correctness Properties"):

    For any interaction outcome, the Verified-Interaction Routine reports
    SUCCESS if and only if the Action_Verifier produced a CONFIRMED verdict
    backed by present post-action evidence; for every other case
    (NO_OP_CLICK, WRONG_TARGET_CLICK, or missing evidence) it reports FAILED
    and initiates failure handling, and never advances to the next step.

The function under test is :func:`verified_interaction` (Component 1,
``interaction.py``) — the *only* place a desktop interaction is ever reported as
a success. The test drives it with the deterministic fakes (``FakeScreen`` /
``FakeClock`` / ``FakeImageMatcher`` / ``FakeOcrProvider`` / ``FakeFocusManager``)
and a recording evidence writer + recording interaction performer, so **no real
desktop, clock, focus system, or file I/O** is exercised.

Independent oracle
------------------
The test never consults the implementation's verdict logic
(``verify_and_classify`` / ``matches_expected`` / ``region_identical``). Instead
it controls the two independent inputs that fully determine the outcome and
recomputes the expected result directly:

* **Localizability** — whether the target can be resolved at all. A target with
  absolute coordinates always locates (confidence ``1.0`` >= the ``0.80``
  threshold); a target carrying no localization data never locates, so no
  Post_Action_State is ever captured (the "missing evidence" case, R4.2).
* **Predicate satisfaction on the present post-state** — the expected outcome's
  predicate is ``state == target_state``; the post-capture is scripted to a
  known value, so the oracle knows whether the predicate holds without calling
  the verifier.

Because the routine retries non-confirming attempts on fresh state (and the
scripted screen returns its ``default`` post-state once exhausted), the single
condition that yields SUCCESS is::

    should_succeed = located and (post_state == target_state)

Every other combination (not located, or located but the predicate never holds)
must report FAILED, must produce a :class:`FailureReport` that stops the flow,
and must never report success.

Two complementary facets are checked:

* :func:`test_property_02_success_iff_confirmed_with_evidence` — locatable
  targets where the verdict varies: SUCCESS exactly when the predicate holds on
  the present post-evidence, FAILED + failure handling otherwise.
* :func:`test_property_02_missing_evidence_is_failure` — un-locatable targets:
  no post-evidence is ever captured, so the interaction is always FAILED, never
  performs the action, and always initiates failure handling (R4.2).
"""

from __future__ import annotations

from hypothesis import given, settings
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
    FakeScreen,
    FinalStatus,
    FlowControl,
    InteractionStep,
    ReliabilityConfig,
    TargetElement,
    Verdict,
    WindowRef,
    verified_interaction,
)

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# Alphabet of "screen states". Kept wide enough that the input space does not
# exhaust before MAX_EXAMPLES (so the test genuinely runs >= 100 iterations),
# while the strategies still force frequent predicate hits/misses (CONFIRMED vs
# NO_OP / WRONG_TARGET) via an explicit ``match`` choice rather than relying on
# chance equality.
_STATES = st.integers(min_value=0, max_value=10_000)

# The interaction actions, sampled to add entropy without affecting the oracle.
_ACTIONS = st.sampled_from(list(Action))

# A sentinel returned by the locate-phase capture; never equals a _STATES value
# and never feeds the predicate, so it cannot perturb the oracle.
_LOCATE_FRAME = "locate-frame"

# A stable, filesystem-safe step identifier (evidence naming is Property 3's
# concern; here it only needs to be valid).
_STEP_ID = "step-02"

_VALID_CATEGORIES = (
    FailureCategory.CODE_ISSUE,
    FailureCategory.SYSTEM_BUG,
    FailureCategory.USER_INPUT_NEEDED,
)


# ---------------------------------------------------------------------------
# Test-side helpers (independent of the function under test)
# ---------------------------------------------------------------------------


def _make_predicate(target_state: object):
    """An explicit, observable check: the post-state equals ``target_state``."""

    def predicate(state: object, _target: object = target_state) -> bool:
        return state == _target

    return predicate


def _recording_writer():
    """A recording evidence writer that performs no real file I/O."""

    written: list = []

    def writer(capture: object, path) -> None:
        written.append((capture, str(path)))

    return writer, written


def _recording_performer():
    """A recording interaction performer that performs no real interaction."""

    calls: list = []

    def perform(action: object, point: object) -> None:
        calls.append((action, point))

    return perform, calls


def _run(step: InteractionStep, expected: ExpectedOutcome, *, post_state: object):
    """Drive ``verified_interaction`` with fully mocked dependencies.

    The screen is scripted ``[pre, locate, post]`` and defaults to ``post`` once
    exhausted, so any verify-poll re-capture and any retry attempt observe the
    same post-state (keeping the outcome deterministic). All side effects
    (capture, interaction, focus, clock, evidence write) go through fakes /
    recorders — no real I/O occurs.
    """

    # ``pre`` differs from ``post`` is irrelevant to this property; use distinct
    # tokens that are not in the _STATES alphabet so they never satisfy the
    # predicate by accident on the pre-capture.
    screen = FakeScreen(frames=["pre-frame", _LOCATE_FRAME, post_state], default=post_state)
    clock = FakeClock()
    image_matcher = FakeImageMatcher(default=0.0)
    ocr_provider = FakeOcrProvider(default="")
    focus_manager = FakeFocusManager()
    writer, written = _recording_writer()
    perform, perform_calls = _recording_performer()

    result = verified_interaction(
        step,
        expected,
        ReliabilityConfig(),
        capture=screen.capture,
        perform_interaction=perform,
        image_matcher=image_matcher,
        ocr_provider=ocr_provider,
        focus_manager=focus_manager,
        clock=clock,
        evidence_writer=writer,
        # An explicit evidence dir keeps path computation off the real repo;
        # the recording writer means it is never actually written to.
        evidences_root="/tmp/desktop-reliability-test-evidence",
    )
    return result, written, perform_calls


def _locatable_step(target_state: object, action: Action = Action.CLICK) -> tuple:
    """Build a step whose target always locates (absolute coords, conf 1.0)."""

    window = WindowRef(id=1, title="app", origin=(0, 0))
    target = TargetElement(absolute=(10, 20))
    step = InteractionStep(
        id=_STEP_ID,
        target=target,
        action=action,
        target_window=window,
        verification_region=FULL_SCREEN,
    )
    expected = ExpectedOutcome(
        description="post-state equals the target state",
        predicate=_make_predicate(target_state),
        region=FULL_SCREEN,
    )
    return step, expected


def _unlocatable_step(action: Action = Action.CLICK) -> tuple:
    """Build a step whose target can never be located (no localization data)."""

    window = WindowRef(id=1, title="app", origin=(0, 0))
    target = TargetElement()  # no reference / text / anchor / window-offset / absolute
    step = InteractionStep(
        id=_STEP_ID,
        target=target,
        action=action,
        target_window=window,
        verification_region=FULL_SCREEN,
    )
    expected = ExpectedOutcome(
        description="never reached (target never locates)",
        predicate=_make_predicate(object()),  # arbitrary; never evaluated to True
        region=FULL_SCREEN,
    )
    return step, expected


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def _locatable_scenario(draw):
    """A locatable target, a scripted post-state, and the predicate's target.

    ``match`` biases toward the predicate holding (CONFIRMED / SUCCESS coverage);
    when it does not hold a genuinely different ``target_state`` is drawn so the
    interaction is a FAILED (No-op / Wrong-target) outcome.
    """

    post_state = draw(_STATES)
    action = draw(_ACTIONS)
    match = draw(st.booleans())
    if match:
        target_state = post_state
    else:
        # Force a different target so the predicate provably fails.
        target_state = draw(_STATES.filter(lambda s: s != post_state))
    return post_state, target_state, action


# ---------------------------------------------------------------------------
# Property 2 - SUCCESS iff CONFIRMED with present post-evidence
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_locatable_scenario())
def test_property_02_success_iff_confirmed_with_evidence(scenario):
    # Feature: desktop-automation-reliability, Property 2: Success requires confirmed verification evidence (no false positives)
    post_state, target_state, action = scenario
    step, expected = _locatable_step(target_state, action)

    result, written, perform_calls = _run(step, expected, post_state=post_state)

    # Independent oracle: the target always locates, so SUCCESS happens exactly
    # when the expected predicate holds on the present post-state.
    should_succeed = post_state == target_state

    # The biconditional at the heart of Property 2 (no false positives).
    assert result.succeeded is should_succeed

    if should_succeed:
        # SUCCESS is backed by a CONFIRMED verdict and present post-evidence
        # (R2.3 / R4.1), and no failure handling was initiated.
        assert result.failure_report is None
        assert result.record.final_status is FinalStatus.SUCCESS
        assert result.record.verification is Verdict.CONFIRMED
        assert result.record.post_evidence  # present post-action evidence (R4)
        # A post-capture was actually written as evidence.
        assert any(phase_path.endswith("_post.png") for _, phase_path in written)
    else:
        # Every non-confirmed outcome (No-op / Wrong-target) is FAILED, initiates
        # failure handling, stops the flow, and never reports success
        # (R3.3 / R3.4 / R4.2 / R13.1).
        assert result.record.final_status is FinalStatus.FAILED
        assert result.record.verification is not Verdict.CONFIRMED
        assert result.failure_report is not None
        assert result.failure_report.flow_control is FlowControl.STOP
        assert result.failure_report.category in _VALID_CATEGORIES


# ---------------------------------------------------------------------------
# Property 2 - missing evidence is always a failure (R4.2)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(post_state=_STATES, action=_ACTIONS)
def test_property_02_missing_evidence_is_failure(post_state, action):
    # Feature: desktop-automation-reliability, Property 2: Success requires confirmed verification evidence (no false positives)
    step, expected = _unlocatable_step(action)

    result, written, perform_calls = _run(step, expected, post_state=post_state)

    # No localization ever succeeds => no Post_Action_State is ever captured, so
    # there can be no verification evidence and therefore no success (R4.2).
    assert result.succeeded is False
    assert result.record.post_evidence == []
    assert result.record.verification is None  # nothing was ever verified

    # No interaction is performed when the target cannot be located.
    assert perform_calls == []

    # Failure handling is initiated and the flow is stopped (R12 / R13.1).
    assert result.record.final_status is FinalStatus.FAILED
    assert result.failure_report is not None
    assert result.failure_report.flow_control is FlowControl.STOP
    assert result.failure_report.category in _VALID_CATEGORIES

    # No post-evidence artifact was ever written (only pre-captures, if any).
    assert all(not phase_path.endswith("_post.png") for _, phase_path in written)
