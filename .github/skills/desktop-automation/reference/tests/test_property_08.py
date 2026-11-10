"""Property-based test for Property 8: ROI search.

# Feature: desktop-automation-reliability, Property 8: ROI search constrains first and expands only when needed

**Validates: Requirements 8.1, 8.3, 8.4**

Property 8 (design "Correctness Properties"):

    For any target with a defined Region_Of_Interest, the search is constrained
    to that ROI first; if the target is found within the ROI that match is used
    without expanding to full screen; if it is not found within the ROI the
    search expands to full screen before the element is reported as not located.

The test exercises ``roi_constrained`` (Component 2, the ROI_CONSTRAINED
strategy primitive in ``locator.py``) against an **independent oracle**. The
oracle decides for itself whether a ROI can constrain the search — it re-derives
ROI validity directly from the generated ROI/frame dimensions and never calls
the implementation's own ``can_constrain`` helper, so the test cannot
tautologically agree with the code under test.

Behavior is observed two ways, both independent of the implementation's
internals:

* The **call log** of the injected :class:`FakeImageMatcher` records, in order,
  the region each search was issued against. This is what proves "constrains
  first" (the first search is the ROI), "without expanding" (no full-screen
  search when found in the ROI), and "expands to full screen" (a second,
  full-screen search when not found in the ROI / when the ROI is unusable).
* The returned :class:`StrategyResult` (point / confidence / ``qualifies``)
  proves which search produced the selected outcome, and that an element which
  is found nowhere is only reported as not-located *after* the full-screen
  expansion (R8.4).

Two complementary facets are checked:

* :func:`test_property_08_roi_constrains_first_and_expands_only_when_needed` —
  the full property across valid in-bounds ROIs and unusable (undefined / empty
  / negative / out-of-bounds) ROIs.
* :func:`test_property_08_invalid_or_empty_roi_forces_full_screen` — the
  explicit invalid/empty-ROI edge case, asserting it forces a single
  full-screen search with no ROI search at all (R8.2 fallback).

Everything is logic-only with a mocked image matcher and no real desktop.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    FULL_SCREEN,
    FakeImageMatcher,
    Frame,
    ImageMatchResult,
    ImageRef,
    Region,
    ReliabilityConfig,
    TargetElement,
    roi_constrained,
)

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200


# ---------------------------------------------------------------------------
# Test-side helpers (independent of the function under test)
# ---------------------------------------------------------------------------


def _oracle_can_constrain(roi: object, frame_w: int, frame_h: int) -> bool:
    """Independent oracle: can a search be constrained to ``roi`` (R8.1/R8.2)?

    Re-derives the documented "valid, non-empty, in-bounds bounded region" rule
    directly from the generated values, without invoking the implementation's
    ``can_constrain`` helper. A search can be constrained only to a bounded
    :class:`Region` with positive width and height that fits within the frame
    bounds; anything else (undefined, full-screen, empty, negative-origin, or
    out-of-bounds) cannot constrain the search and forces a full-screen fallback.
    """

    if not isinstance(roi, Region):
        return False
    if roi.width <= 0 or roi.height <= 0:
        return False
    if roi.x < 0 or roi.y < 0:
        return False
    if roi.x + roi.width > frame_w or roi.y + roi.height > frame_h:
        return False
    return True


def _frame_of(width: int, height: int) -> Frame:
    """Build a ``Frame`` of the given dimensions (advertises width/height)."""

    return Frame.of([[0] * width for _ in range(height)])


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Confidence alphabet that straddles the default 0.80 threshold (including the
# exactly-at-threshold value) so both "found in ROI" and "not found in ROI"
# outcomes occur frequently across examples.
_CONF = st.one_of(
    st.sampled_from([0.0, 0.5, 0.79, 0.80, 0.81, 1.0]),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)

_POINTS = st.tuples(st.integers(min_value=-50, max_value=50),
                    st.integers(min_value=-50, max_value=50))


@st.composite
def _frame_dims(draw):
    """Generate frame dimensions used both for the frame and ROI bounds."""

    return draw(st.integers(min_value=1, max_value=8)), draw(st.integers(min_value=1, max_value=8))


@st.composite
def _valid_roi(draw, width: int, height: int) -> Region:
    """Generate a valid, non-empty ROI fully inside a ``width`` x ``height`` frame."""

    x = draw(st.integers(min_value=0, max_value=width - 1))
    rw = draw(st.integers(min_value=1, max_value=width - x))
    y = draw(st.integers(min_value=0, max_value=height - 1))
    rh = draw(st.integers(min_value=1, max_value=height - y))
    return Region(x=x, y=y, width=rw, height=rh)


@st.composite
def _invalid_roi(draw, width: int, height: int):
    """Generate a ROI that cannot constrain the search (R8.2 fallback case).

    Covers every "unusable ROI" shape: undefined, empty (zero width/height),
    negative origin, and out-of-bounds (extends past the frame).
    """

    kind = draw(
        st.sampled_from(["none", "empty_w", "empty_h", "neg_x", "neg_y", "oob_w", "oob_h"])
    )
    if kind == "none":
        return None
    if kind == "empty_w":
        return Region(x=0, y=0, width=0, height=draw(st.integers(min_value=1, max_value=height)))
    if kind == "empty_h":
        return Region(x=0, y=0, width=draw(st.integers(min_value=1, max_value=width)), height=0)
    if kind == "neg_x":
        return Region(x=draw(st.integers(min_value=-5, max_value=-1)), y=0, width=1, height=1)
    if kind == "neg_y":
        return Region(x=0, y=draw(st.integers(min_value=-5, max_value=-1)), width=1, height=1)
    if kind == "oob_w":
        return Region(x=0, y=0, width=width + draw(st.integers(min_value=1, max_value=5)), height=1)
    # kind == "oob_h"
    return Region(x=0, y=0, width=1, height=height + draw(st.integers(min_value=1, max_value=5)))


@st.composite
def _scenario(draw):
    """A frame, a ROI (valid or unusable), and scripted ROI/full-screen matches."""

    width, height = draw(_frame_dims())
    if draw(st.booleans()):
        roi = draw(_valid_roi(width, height))
    else:
        roi = draw(_invalid_roi(width, height))
    return (
        width,
        height,
        roi,
        draw(_CONF),        # confidence the matcher reports for the ROI search
        draw(_CONF),        # confidence the matcher reports for the full-screen search
        draw(_POINTS),      # point the matcher reports for the ROI search
        draw(_POINTS),      # point the matcher reports for the full-screen search
    )


@st.composite
def _invalid_scenario(draw):
    """A frame, an *unusable* ROI, and a scripted full-screen match only."""

    width, height = draw(_frame_dims())
    return width, height, draw(_invalid_roi(width, height)), draw(_CONF), draw(_POINTS)


# ---------------------------------------------------------------------------
# Property 8 - constrain first, expand only when needed
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_scenario())
def test_property_08_roi_constrains_first_and_expands_only_when_needed(scenario):
    # Feature: desktop-automation-reliability, Property 8: ROI search constrains first and expands only when needed
    width, height, roi, roi_conf, full_conf, roi_point, full_point = scenario

    config = ReliabilityConfig()
    threshold = config.confidence_threshold
    frame = _frame_of(width, height)
    target = TargetElement(reference=ImageRef(path="ref.png"), roi=roi)

    # Independent oracle decides whether the ROI can constrain the search.
    constrainable = _oracle_can_constrain(roi, width, height)

    # Script the matcher in call order: a constrainable ROI is searched first,
    # then (only if needed) the full screen; an unusable ROI goes straight to a
    # single full-screen search.
    roi_result = ImageMatchResult(confidence=roi_conf, point=roi_point)
    full_result = ImageMatchResult(confidence=full_conf, point=full_point)
    matcher = FakeImageMatcher(
        sequence=[roi_result, full_result] if constrainable else [full_result]
    )

    result = roi_constrained(target, frame, config, image_matcher=matcher)

    regions = [call.region for call in matcher.calls]

    if constrainable and roi_conf >= threshold:
        # R8.1/R8.3: constrained to the ROI and found there -> the ROI match is
        # used WITHOUT expanding the search to the full screen.
        assert len(regions) == 1
        assert regions[0] == roi
        assert result.matched
        assert result.point == roi_point
        assert result.confidence == roi_conf
        assert result.qualifies(threshold)
    elif constrainable:
        # R8.4: constrained to the ROI first, not found there -> the search
        # expands to the full screen before the outcome is reported.
        assert len(regions) == 2
        assert regions[0] == roi
        assert regions[1] is FULL_SCREEN
        assert result.matched
        assert result.point == full_point
        assert result.confidence == full_conf
        # The element is only reported located/not-located based on the
        # full-screen result, i.e. AFTER the expansion happened (R8.4).
        assert result.qualifies(threshold) == (full_conf >= threshold)
    else:
        # R8.2: the ROI cannot constrain the search -> a single full-screen
        # search is performed; no ROI search is issued.
        assert len(regions) == 1
        assert regions[0] is FULL_SCREEN
        assert result.matched
        assert result.point == full_point
        assert result.confidence == full_conf


# ---------------------------------------------------------------------------
# Property 8 - invalid / empty ROI forces a full-screen fallback (R8.2)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_invalid_scenario())
def test_property_08_invalid_or_empty_roi_forces_full_screen(scenario):
    # Feature: desktop-automation-reliability, Property 8: ROI search constrains first and expands only when needed
    width, height, roi, full_conf, full_point = scenario

    config = ReliabilityConfig()
    frame = _frame_of(width, height)
    target = TargetElement(reference=ImageRef(path="ref.png"), roi=roi)

    # Sanity: the independent oracle confirms this ROI cannot constrain a search.
    assert not _oracle_can_constrain(roi, width, height)

    matcher = FakeImageMatcher(
        sequence=[ImageMatchResult(confidence=full_conf, point=full_point)]
    )

    result = roi_constrained(target, frame, config, image_matcher=matcher)

    regions = [call.region for call in matcher.calls]

    # The unusable ROI is never searched; the search falls straight back to a
    # single full-screen search.
    assert len(regions) == 1
    assert regions[0] is FULL_SCREEN
    assert result.matched
    assert result.point == full_point
    assert result.confidence == full_conf
