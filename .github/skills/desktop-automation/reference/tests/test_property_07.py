"""Property-based test for Property 7: anchor-relative positioning.

# Feature: desktop-automation-reliability, Property 7: Anchor-relative positioning equals anchor plus offset, and only when the anchor is present

**Validates: Requirements 7.1, 7.2, 7.3**

Property 7 (design "Correctness Properties"):

    For any anchor position and offset, when the anchor is located the computed
    target point equals the anchor point plus the offset; when the anchor cannot
    be located no anchor-relative point is produced and the next-ranked strategy
    is attempted.

The test exercises the ANCHOR_RELATIVE strategy of the Element_Locator
(``anchor_relative`` and, in traversal context, ``locate_with_fallback`` in
``locator.py``). It checks three facets of the same property:

* :func:`test_property_07_point_equals_anchor_plus_offset` — when the anchor is
  present (located either by image match at/above threshold, or via its absolute
  coordinate), the resolved point equals ``anchor_point + offset`` exactly
  (R7.1/R7.2).
* :func:`test_property_07_absent_anchor_produces_no_point` — when the anchor
  cannot be located (confidence below threshold, no located point, or no anchor
  information at all), no anchor-relative point is produced: ``matched`` is
  ``False`` and ``point`` is ``None`` (R7.2/R7.3).
* :func:`test_property_07_absent_anchor_falls_through_to_next_strategy` — driven
  through ``locate_with_fallback``: when the anchor is present the ANCHOR_RELATIVE
  strategy produces ``anchor + offset``; when the anchor is absent the locator
  falls through to the next-ranked qualifying strategy (ABSOLUTE) instead of
  producing an anchor-relative point (R7.3).

The oracle is **independent**: the expected point is recomputed directly as
``(anchor_x + dx, anchor_y + dy)`` from the generated inputs rather than by
calling the locator's own ``_locate_anchor`` helper, so the test cannot
tautologically agree with the implementation. ``session`` is held at ``None``
throughout so the anchor-plus-offset arithmetic is isolated from scaling
recompute (which is Property 10's concern).

Everything is logic-only with mocked image matcher / OCR / screen / clock and no
real desktop.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    FakeClock,
    FakeImageMatcher,
    FakeOcrProvider,
    FakeScreen,
    ImageMatchResult,
    ImageRef,
    LocalizationStrategy,
    ReliabilityConfig,
    TargetElement,
    anchor_relative,
    locate_with_fallback,
)

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# Coordinate ranges: anchors live on-screen (non-negative); offsets may be
# negative (the target can sit above/left of its anchor).
_COORD = st.integers(min_value=0, max_value=3000)
_OFFSET = st.integers(min_value=-1500, max_value=1500)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def _present_anchor_scenario(draw):
    """A locatable anchor + offset, for the anchor-plus-offset facet (R7.1/R7.2).

    The anchor is present either via an image-match reference whose confidence
    is at or above the configured threshold, or via its absolute coordinate
    (used by ``_locate_anchor`` when no reference image is available).
    """

    ax = draw(_COORD)
    ay = draw(_COORD)
    dx = draw(_OFFSET)
    dy = draw(_OFFSET)
    threshold = draw(st.floats(min_value=0.1, max_value=1.0))
    kind = draw(st.sampled_from(["image", "absolute"]))
    # Confidence at/above threshold so the image-located anchor is confirmed.
    confidence = draw(st.floats(min_value=threshold, max_value=1.0))
    return ax, ay, dx, dy, threshold, kind, confidence


@st.composite
def _absent_anchor_scenario(draw):
    """An anchor that cannot be located, for the no-point facet (R7.2/R7.3).

    Three ways the anchor fails to be confirmed:

    - ``low_confidence``: an image match below the threshold,
    - ``none_point``: a match that reports no located point,
    - ``no_anchor_info``: an anchor carrying neither reference image nor
      absolute coordinate.
    """

    ax = draw(_COORD)
    ay = draw(_COORD)
    dx = draw(_OFFSET)
    dy = draw(_OFFSET)
    threshold = draw(st.floats(min_value=0.2, max_value=1.0))
    kind = draw(st.sampled_from(["low_confidence", "none_point", "no_anchor_info"]))
    # Strictly-below-threshold confidence for the low_confidence case.
    low_confidence = draw(st.floats(min_value=0.0, max_value=threshold, exclude_max=True))
    return ax, ay, dx, dy, threshold, kind, low_confidence


@st.composite
def _traversal_scenario(draw):
    """A target whose anchor is present or absent, for the fall-through facet.

    The target carries no image/OCR/window/ROI inputs, so the only higher- or
    equal-ranked strategy that can qualify besides ANCHOR_RELATIVE is the
    last-resort ABSOLUTE coordinate. This isolates the R7.3 behavior: when the
    anchor is present ANCHOR_RELATIVE wins; when it is absent the locator falls
    through to ABSOLUTE rather than producing an anchor-relative point.
    """

    present = draw(st.booleans())
    ax = draw(_COORD)
    ay = draw(_COORD)
    dx = draw(_OFFSET)
    dy = draw(_OFFSET)
    abs_x = draw(_COORD)
    abs_y = draw(_COORD)
    # Default threshold is 0.80; present anchors score at/above it, absent ones
    # strictly below it.
    if present:
        confidence = draw(st.floats(min_value=0.80, max_value=1.0))
    else:
        confidence = draw(st.floats(min_value=0.0, max_value=0.80, exclude_max=True))
    return present, ax, ay, dx, dy, abs_x, abs_y, confidence


# ---------------------------------------------------------------------------
# Facet 1 - anchor present => point == anchor + offset (R7.1/R7.2)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_present_anchor_scenario())
def test_property_07_point_equals_anchor_plus_offset(scenario):
    # Feature: desktop-automation-reliability, Property 7: Anchor-relative positioning equals anchor plus offset, and only when the anchor is present
    ax, ay, dx, dy, threshold, kind, confidence = scenario

    config = ReliabilityConfig(confidence_threshold=threshold)

    if kind == "image":
        ref = ImageRef(path=f"anchor_{ax}_{ay}.png")
        anchor = TargetElement(reference=ref)
        matcher = FakeImageMatcher().script_reference(
            ref, [ImageMatchResult(confidence=confidence, point=(ax, ay))]
        )
    else:  # "absolute" - no reference image, located via absolute coordinate
        anchor = TargetElement(absolute=(ax, ay))
        matcher = FakeImageMatcher()  # not consulted for an absolute-only anchor

    target = TargetElement(anchor=anchor, offset=(dx, dy))

    result = anchor_relative(target, image_matcher=matcher, config=config, session=None)

    # Independent oracle: the point is exactly anchor + offset.
    assert result.matched is True
    assert result.point == (ax + dx, ay + dy)
    # Anchor-relative positioning is deterministic once the anchor is confirmed.
    assert result.confidence == 1.0


# ---------------------------------------------------------------------------
# Facet 2 - anchor absent => no anchor-relative point (R7.2/R7.3)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_absent_anchor_scenario())
def test_property_07_absent_anchor_produces_no_point(scenario):
    # Feature: desktop-automation-reliability, Property 7: Anchor-relative positioning equals anchor plus offset, and only when the anchor is present
    ax, ay, dx, dy, threshold, kind, low_confidence = scenario

    config = ReliabilityConfig(confidence_threshold=threshold)

    if kind == "low_confidence":
        ref = ImageRef(path=f"anchor_{ax}_{ay}.png")
        anchor = TargetElement(reference=ref)
        matcher = FakeImageMatcher().script_reference(
            ref, [ImageMatchResult(confidence=low_confidence, point=(ax, ay))]
        )
    elif kind == "none_point":
        ref = ImageRef(path=f"anchor_{ax}_{ay}.png")
        anchor = TargetElement(reference=ref)
        # Even a high confidence cannot confirm an anchor with no located point.
        matcher = FakeImageMatcher().script_reference(
            ref, [ImageMatchResult(confidence=1.0, point=None)]
        )
    else:  # "no_anchor_info" - neither reference image nor absolute coordinate
        anchor = TargetElement()
        matcher = FakeImageMatcher()

    target = TargetElement(anchor=anchor, offset=(dx, dy))

    result = anchor_relative(target, image_matcher=matcher, config=config, session=None)

    # Independent oracle: an unconfirmed anchor yields no anchor-relative point,
    # so the caller falls through to the next-ranked strategy (R7.3).
    assert result.matched is False
    assert result.point is None


# ---------------------------------------------------------------------------
# Facet 3 - traversal: present => ANCHOR_RELATIVE, absent => next strategy (R7.3)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_traversal_scenario())
def test_property_07_absent_anchor_falls_through_to_next_strategy(scenario):
    # Feature: desktop-automation-reliability, Property 7: Anchor-relative positioning equals anchor plus offset, and only when the anchor is present
    present, ax, ay, dx, dy, abs_x, abs_y, confidence = scenario

    config = ReliabilityConfig()  # default 0.80 threshold

    ref = ImageRef(path=f"anchor_{ax}_{ay}.png")
    anchor = TargetElement(reference=ref)
    # The target itself has no image/OCR/window/ROI inputs; only its anchor and
    # a last-resort absolute coordinate are available. So the only equal- or
    # lower-ranked strategy that can qualify is ABSOLUTE.
    target = TargetElement(anchor=anchor, offset=(dx, dy), absolute=(abs_x, abs_y))

    matcher = FakeImageMatcher().script_reference(
        ref, [ImageMatchResult(confidence=confidence, point=(ax, ay))]
    )
    # ABSOLUTE qualifies regardless of attempt, so capture/clock are exercised
    # but no backoff is needed; a default frame is enough (it is never matched).
    screen = FakeScreen(default=0)
    ocr = FakeOcrProvider()
    clock = FakeClock()

    result = locate_with_fallback(
        target,
        config,
        capture=screen.capture,
        image_matcher=matcher,
        ocr_provider=ocr,
        session=None,
        clock=clock,
    )

    assert result.located is True
    if present:
        # The confirmed anchor produces anchor + offset via ANCHOR_RELATIVE.
        assert result.strategy is LocalizationStrategy.ANCHOR_RELATIVE
        assert result.point == (ax + dx, ay + dy)
    else:
        # No anchor-relative point: the locator advanced to the next-ranked
        # qualifying strategy (ABSOLUTE) instead (R7.3).
        assert result.strategy is LocalizationStrategy.ABSOLUTE
        assert result.point == (abs_x, abs_y)
