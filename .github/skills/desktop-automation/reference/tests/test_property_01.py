"""Property-based test for Property 1: verdict classification.

# Feature: desktop-automation-reliability, Property 1: Verdict classification is exhaustive and correct

**Validates: Requirements 2.2, 2.3, 2.4, 2.5, 3.1, 3.2**

Property 1 (design "Correctness Properties"):

    For any pre-state and post-state over a verification region together with an
    expected outcome, ``verify_and_classify`` returns exactly one verdict such
    that: it returns CONFIRMED if and only if the expected-outcome predicate
    holds on a present post-state within the polling timeout; otherwise it
    returns NO_OP_CLICK when the post-state is region-identical to the pre-state,
    and WRONG_TARGET_CLICK when the post-state differs from the pre-state but
    fails the expected predicate.

The test exercises ``verify_and_classify`` (Component 3, ``verifier.py``) against
an **independent oracle**. The oracle never calls the function-under-test's own
helpers (``region_identical`` / ``matches_expected``); it recomputes region
identity directly from :class:`Frame.crop` (test-side infrastructure) and the
predicate directly, so the test cannot tautologically agree with the
implementation.

Two complementary facets of the same property are checked:

* :func:`test_property_01_verdict_classification_single_post` — the core
  classification logic with a single, present post-state (no re-capture): the
  CONFIRMED iff predicate, and the NO_OP vs WRONG_TARGET split by region diff.
* :func:`test_property_01_verdict_classification_polling_within_timeout` — the
  "within the polling timeout" clause, driving the deterministic
  :class:`FakeClock` and a scripted :class:`FakeScreen` so the verifier polls a
  sequence of evolving post-states and confirms as soon as one matches before
  the deadline.

Everything is logic-only with mocked screen/clock and no real desktop or sleeps.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

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

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# Small pixel alphabet so frame equality (No-op) and inequality (Wrong-target)
# both occur frequently across generated examples.
_TOKENS = st.integers(min_value=0, max_value=2)


# ---------------------------------------------------------------------------
# Test-side helpers (independent of the function under test)
# ---------------------------------------------------------------------------


def _crop(frame: object, region: object) -> object:
    """Crop ``frame`` to ``region`` using only test infrastructure.

    Mirrors the design's region-diff comparison without invoking the verifier's
    own ``region_identical`` helper, keeping the oracle independent.
    """

    return frame.crop(region) if isinstance(frame, Frame) else frame


def _region_identical(pre: object, post: object, region: object) -> bool:
    """Oracle region-identity: identical within ``region`` (R3.1)."""

    return _crop(pre, region) == _crop(post, region)


def _make_predicate(target: object):
    """Build an explicit, observable predicate: state equals a target frame."""

    def predicate(state: object, _target: object = target) -> bool:
        return state == _target

    return predicate


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def _frames(draw, width: int, height: int) -> Frame:
    """Generate a ``Frame`` of the given dimensions from the pixel alphabet."""

    rows = draw(
        st.lists(
            st.lists(_TOKENS, min_size=width, max_size=width),
            min_size=height,
            max_size=height,
        )
    )
    return Frame.of(rows)


@st.composite
def _regions(draw, width: int, height: int):
    """Generate a verification region: FULL_SCREEN or an in-bounds Region."""

    if draw(st.booleans()):
        return FULL_SCREEN
    x = draw(st.integers(min_value=0, max_value=width - 1))
    w = draw(st.integers(min_value=1, max_value=width - x))
    y = draw(st.integers(min_value=0, max_value=height - 1))
    h = draw(st.integers(min_value=1, max_value=height - y))
    return Region(x=x, y=y, width=w, height=h)


@st.composite
def _single_post_scenario(draw):
    """A present pre/post pair, a region, and an expected-outcome target frame.

    ``same`` biases toward region-identical states (No-op coverage); ``match``
    biases toward the predicate holding on the post (CONFIRMED coverage). The
    post is always a present (non-None) frame, per Property 1's "present
    post-state".
    """

    width = draw(st.integers(min_value=1, max_value=4))
    height = draw(st.integers(min_value=1, max_value=4))

    pre = draw(_frames(width, height))
    same = draw(st.booleans())
    post = pre if same else draw(_frames(width, height))
    region = draw(_regions(width, height))

    match = draw(st.booleans())
    target = post if match else draw(_frames(width, height))
    return pre, post, region, target


@st.composite
def _polling_scenario(draw):
    """A pre-state plus a sequence of post-states observed across polls.

    The verifier checks ``post0`` first, then re-captures ``recaptured`` one per
    poll. ``target`` is sometimes pinned to one of the observed states (so the
    predicate becomes satisfied at a specific poll) and sometimes free.
    """

    width = draw(st.integers(min_value=1, max_value=3))
    height = draw(st.integers(min_value=1, max_value=3))

    pre = draw(_frames(width, height))
    post0 = draw(_frames(width, height))
    n_recaptures = draw(st.integers(min_value=1, max_value=5))
    recaptured = [draw(_frames(width, height)) for _ in range(n_recaptures)]
    region = draw(_regions(width, height))

    observed = [post0] + recaptured
    # index in [0, len(observed)] - len(observed) means "do not pin to observed".
    pin = draw(st.integers(min_value=0, max_value=len(observed)))
    if pin < len(observed):
        target = observed[pin]
    else:
        target = draw(_frames(width, height))
    return pre, post0, recaptured, region, target


# ---------------------------------------------------------------------------
# Property 1 - core classification with a single present post-state
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_single_post_scenario())
def test_property_01_verdict_classification_single_post(scenario):
    # Feature: desktop-automation-reliability, Property 1: Verdict classification is exhaustive and correct
    pre, post, region, target = scenario

    expected = ExpectedOutcome(
        description="post equals target frame",
        predicate=_make_predicate(target),
        region=region,
    )
    clock = FakeClock()

    # No re-capture source: the present post is checked exactly once, then the
    # change is classified (R3.1 / R3.2).
    result = verify_and_classify(
        pre, post, expected, ReliabilityConfig(), clock=clock
    )

    # Independent oracle from Property 1's specification.
    if post == target:  # predicate holds on the present post-state
        expected_verdict = Verdict.CONFIRMED
    elif _region_identical(pre, post, region):
        expected_verdict = Verdict.NO_OP_CLICK
    else:
        expected_verdict = Verdict.WRONG_TARGET_CLICK

    # Exactly one verdict, and it is the correct one.
    assert result in (
        Verdict.CONFIRMED,
        Verdict.NO_OP_CLICK,
        Verdict.WRONG_TARGET_CLICK,
    )
    assert result is expected_verdict

    # CONFIRMED holds iff the predicate holds on the present post (R2.3 / R4.1).
    assert (result is Verdict.CONFIRMED) == (post == target)


# ---------------------------------------------------------------------------
# Property 1 - "within the polling timeout" (fake clock drives the poll loop)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_polling_scenario())
def test_property_01_verdict_classification_polling_within_timeout(scenario):
    # Feature: desktop-automation-reliability, Property 1: Verdict classification is exhaustive and correct
    pre, post0, recaptured, region, target = scenario

    observed = [post0] + recaptured
    n = len(recaptured)

    expected = ExpectedOutcome(
        description="some polled post equals target frame",
        predicate=_make_predicate(target),
        region=region,
    )
    clock = FakeClock()
    screen = FakeScreen(frames=list(recaptured), default=recaptured[-1])

    # The recapture models ``capture_state`` and returns full frames; the
    # verifier crops to the region internally (in region_identical), exactly as
    # it treats the caller-supplied ``post`` in the single-post path. Requesting
    # FULL_SCREEN from the fake avoids a double-crop while still exercising the
    # fake screen as the scripted re-capture source.
    def recapture(_region, _screen=screen):
        return _screen.capture(FULL_SCREEN)

    # With poll_interval == 1.0s and verify_timeout == n, the loop checks post0
    # then re-captures each of the n scripted frames before crossing the
    # deadline - so every observed state gets a CONFIRMED check within the
    # timeout, and exactly n re-captures occur.
    config = ReliabilityConfig(verify_timeout_seconds=n)
    result = verify_and_classify(
        pre,
        post0,
        expected,
        config,
        clock=clock,
        recapture=recapture,
        poll_interval_seconds=1.0,
    )

    # Independent oracle: CONFIRMED iff the predicate holds on some observed
    # (present) post-state within the timeout; otherwise classify the final
    # observed post-state by region diff.
    if any(state == target for state in observed):
        expected_verdict = Verdict.CONFIRMED
    elif _region_identical(pre, recaptured[-1], region):
        expected_verdict = Verdict.NO_OP_CLICK
    else:
        expected_verdict = Verdict.WRONG_TARGET_CLICK

    assert result in (
        Verdict.CONFIRMED,
        Verdict.NO_OP_CLICK,
        Verdict.WRONG_TARGET_CLICK,
    )
    assert result is expected_verdict

    # The poll loop must have consumed exactly one fresh capture per poll up to
    # the deadline (no more, no fewer) when no early CONFIRMED short-circuited.
    if expected_verdict is not Verdict.CONFIRMED:
        assert screen.capture_count == n
