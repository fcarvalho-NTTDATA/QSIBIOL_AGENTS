"""Property-based test for Property 5: confidence threshold gating.

# Feature: desktop-automation-reliability, Property 5: Confidence threshold gates matches inclusively

**Validates: Requirements 6.1, 6.2, 6.3**

Property 5 (design "Correctness Properties"):

    For any image-match confidence value and configured threshold, the
    Element_Locator accepts the match when the confidence is greater than or
    equal to the threshold and rejects it (falling through to the next-ranked
    strategy) when the confidence is strictly below the threshold.

The gate is **inclusive** at the threshold: a confidence exactly equal to the
threshold is accepted (R6.3). Below the threshold the image match is rejected
and the locator continues to the next-ranked strategy (R6.2).

The test exercises the gate against an **independent oracle**. The oracle is the
plain arithmetic relation ``confidence >= threshold`` recomputed test-side; it
never calls :meth:`StrategyResult.qualifies` or any other code path of the
function-under-test, so the test cannot tautologically agree with the
implementation.

Three complementary facets of the same property are checked:

* :func:`test_property_05_threshold_gate_is_inclusive` — the core gate
  (:meth:`StrategyResult.qualifies`) over every confidence/threshold pair,
  including the exactly-at-threshold boundary, and the rule that a non-match
  never qualifies.
* :func:`test_property_05_below_threshold_falls_through_to_next_strategy` — the
  end-to-end consequence in ``locate_with_fallback``: an IMAGE_MATCH at or above
  threshold is accepted (highest-ranked wins), while one strictly below is
  rejected and the locator falls through to the next-ranked qualifying strategy.
* :func:`test_property_05_exactly_at_threshold_is_accepted` — an explicit,
  non-generated assertion of the boundary case (confidence == threshold is
  accepted), guaranteeing the edge is always covered.

Everything is logic-only with mocked screen/matchers and no real desktop.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    FULL_SCREEN,
    FakeClock,
    FakeImageMatcher,
    FakeOcrProvider,
    FakeScreen,
    Frame,
    ImageMatchResult,
    ImageRef,
    LocalizationStrategy,
    ReliabilityConfig,
    StrategyResult,
    TargetElement,
    image_match,
    locate_with_fallback,
)

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# A confidence/threshold value in the valid [0.0, 1.0] range (no NaN/inf).
_UNIT = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def _threshold_and_confidence(draw):
    """A (threshold, confidence) pair biased to exercise the boundary.

    A free ``threshold`` in ``[0, 1]`` is drawn, then the ``confidence`` is
    placed in a deliberately chosen relation to it so the strictly-below,
    exactly-equal, and strictly-above regions are all sampled densely (a purely
    uniform pair would almost never land exactly on the threshold):

    - ``equal``: ``confidence == threshold`` (the inclusive boundary, R6.3).
    - ``below``: ``confidence`` strictly below ``threshold`` when possible.
    - ``above``: ``confidence`` strictly above ``threshold`` when possible.
    - ``free``: any value in ``[0, 1]``.

    The oracle (``confidence >= threshold``) is uniform across all of these, so
    the bias only improves coverage; it never changes the expected result.
    """

    threshold = draw(_UNIT)
    relation = draw(st.sampled_from(("equal", "below", "above", "free")))

    if relation == "equal":
        confidence = threshold
    elif relation == "below":
        if threshold <= 0.0:
            confidence = threshold  # nothing is below 0.0; fall back to the boundary
        else:
            confidence = draw(
                st.floats(
                    min_value=0.0,
                    max_value=threshold,
                    exclude_max=True,
                    allow_nan=False,
                    allow_infinity=False,
                )
            )
    elif relation == "above":
        if threshold >= 1.0:
            confidence = threshold  # nothing is above 1.0; fall back to the boundary
        else:
            confidence = draw(
                st.floats(
                    min_value=threshold,
                    max_value=1.0,
                    exclude_min=True,
                    allow_nan=False,
                    allow_infinity=False,
                )
            )
    else:  # free
        confidence = draw(_UNIT)

    return threshold, confidence


# ---------------------------------------------------------------------------
# Facet 1 - the gate itself is inclusive at the threshold
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(pair=_threshold_and_confidence(), matched=st.booleans(), point=st.tuples(
    st.integers(min_value=0, max_value=4000), st.integers(min_value=0, max_value=4000)
))
def test_property_05_threshold_gate_is_inclusive(pair, matched, point):
    # Feature: desktop-automation-reliability, Property 5: Confidence threshold gates matches inclusively
    threshold, confidence = pair

    result = (
        StrategyResult.hit(point=point, confidence=confidence)
        if matched
        else StrategyResult.no_match()
    )

    # Independent oracle: a candidate qualifies iff it matched AND its
    # confidence is at or above the threshold (>= is inclusive, R6.1/R6.3).
    expected = matched and confidence >= threshold

    assert result.qualifies(threshold) is expected

    # A non-match never qualifies regardless of confidence (R6.2 fall-through).
    if not matched:
        assert result.qualifies(threshold) is False

    # For a real match, acceptance is governed purely by the inclusive relation.
    if matched:
        assert result.qualifies(threshold) is (confidence >= threshold)


# ---------------------------------------------------------------------------
# Facet 2 - below-threshold image match falls through to the next strategy
# ---------------------------------------------------------------------------


@st.composite
def _fallthrough_scenario(draw):
    """A target whose IMAGE_MATCH confidence gates against a configured threshold.

    The target carries a reference image (IMAGE_MATCH, rank 1) and an absolute
    coordinate (ABSOLUTE, the lowest rank). The injected image matcher returns a
    single scripted confidence for every image lookup, and the absolute
    coordinate always qualifies (deterministic confidence ``1.0``). So the
    locator selects IMAGE_MATCH exactly when the scripted confidence clears the
    threshold and otherwise falls through to ABSOLUTE — making the gate's
    accept/reject decision directly observable via the producing strategy.

    The image point and the absolute point are kept distinct so the selected
    point is an unambiguous witness of which strategy won.
    """

    threshold, confidence = draw(_threshold_and_confidence())

    image_point = draw(
        st.tuples(st.integers(min_value=0, max_value=1000), st.integers(min_value=0, max_value=1000))
    )
    # Keep the absolute point distinct from the image point.
    absolute_point = (image_point[0] + draw(st.integers(min_value=1, max_value=500)),
                      image_point[1] + draw(st.integers(min_value=1, max_value=500)))

    return threshold, confidence, image_point, absolute_point


@settings(max_examples=MAX_EXAMPLES)
@given(scenario=_fallthrough_scenario())
def test_property_05_below_threshold_falls_through_to_next_strategy(scenario):
    # Feature: desktop-automation-reliability, Property 5: Confidence threshold gates matches inclusively
    threshold, confidence, image_point, absolute_point = scenario

    config = ReliabilityConfig(confidence_threshold=threshold)

    # Every image lookup (IMAGE_MATCH at rank 1, and the ROI-constrained full
    # screen fallback) returns the same scripted confidence/point, so the gate
    # decision is consistent across the traversal.
    matcher = FakeImageMatcher(default=ImageMatchResult(confidence=confidence, point=image_point))
    ocr = FakeOcrProvider()  # never matches (no target.text)
    screen = FakeScreen(default=Frame.of([[0]]))
    clock = FakeClock()

    target = TargetElement(
        reference=ImageRef(path="ref.png"),
        absolute=absolute_point,
    )

    result = locate_with_fallback(
        target,
        config,
        capture=screen.capture,
        image_matcher=matcher,
        ocr_provider=ocr,
        clock=clock,
    )

    # Independent oracle: the image match is accepted iff confidence >= threshold
    # (inclusive). When accepted, the highest-ranked strategy (IMAGE_MATCH) wins;
    # otherwise the gate rejects it and the locator falls through to the only
    # other qualifying strategy, ABSOLUTE.
    image_accepted = confidence >= threshold

    assert result.located is True
    if image_accepted:
        assert result.strategy is LocalizationStrategy.IMAGE_MATCH
        assert result.point == image_point
        assert result.confidence == confidence
    else:
        assert result.strategy is LocalizationStrategy.ABSOLUTE
        assert result.point == absolute_point


# ---------------------------------------------------------------------------
# Facet 3 - the exactly-at-threshold boundary is always accepted (R6.3)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(threshold=_UNIT)
def test_property_05_exactly_at_threshold_is_accepted(threshold):
    # Feature: desktop-automation-reliability, Property 5: Confidence threshold gates matches inclusively
    # A confidence exactly equal to the threshold is accepted (inclusive gate).
    at_threshold = StrategyResult.hit(point=(10, 20), confidence=threshold)
    assert at_threshold.qualifies(threshold) is True

    # And it is accepted through the actual image-match primitive too.
    matcher = FakeImageMatcher(default=ImageMatchResult(confidence=threshold, point=(10, 20)))
    primitive = image_match(ImageRef(path="ref.png"), image_matcher=matcher, region=FULL_SCREEN)
    assert primitive.qualifies(threshold) is True
