"""Property-based test for Property 4: ranked-order localization.

# Feature: desktop-automation-reliability, Property 4: Localization tries strategies in ranked order and selects the highest-ranked qualifying match

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 6.2, 7.3**

Property 4 (design "Correctness Properties"):

    For any combination of which localization strategies would match,
    ``locate_with_fallback`` evaluates strategies strictly in the order
    [image match, OCR text, anchor-relative, ROI-constrained, window-relative,
    absolute], returns the match produced by the highest-ranked strategy whose
    confidence is at or above the threshold, and records that producing
    strategy on the result.

This test exercises ``locate_with_fallback`` (Component 2, ``locator.py``)
against an **independent oracle**. The scenario generator decides *up front*,
for each of the six ranked strategies, whether that strategy would qualify, and
then realizes a :class:`TargetElement` plus deterministic fakes so each
strategy's qualification is exactly what was decided. The oracle is therefore
the trivially-correct statement of the property -- "the winner is the first
qualifying strategy in the fixed rank order" -- computed purely from the
generated ``would_qualify`` vector, never by calling the function under test or
its helpers.

Two complementary facets of the same property are checked:

* :func:`test_property_04_selects_highest_ranked_qualifying_match` -- the
  *selection* clause: the result is located iff some strategy qualifies, the
  recorded strategy is the highest-ranked qualifying one (R5.2/R5.3/R5.4), and
  the returned point/confidence are the ones that producing strategy yields.
* :func:`test_property_04_evaluates_strategies_in_strict_ranked_order` -- the
  *strict ordering* clause: strategies are evaluated in exactly
  [IMAGE_MATCH, OCR_TEXT, ANCHOR_RELATIVE, ROI_CONSTRAINED, WINDOW_RELATIVE,
  ABSOLUTE] order and traversal stops at the winner (R5.1/R5.2), verified by
  spying on the order in which ``run_strategy`` is invoked.

To isolate ranked-order selection from retry/backoff (Property 9, task 2.8) the
locator is configured with ``max_locate_attempts=1`` -- a single traversal of
the strategy ladder. Everything is logic-only with mocked frame/matchers and no
real desktop.
"""

from __future__ import annotations

from typing import List, NamedTuple, Optional, Tuple
from unittest import mock

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
    Region,
    ReliabilityConfig,
    STRATEGY_ORDER,
    TargetElement,
    WindowRef,
    locate_with_fallback,
)
from desktop_reliability import locator as locator_mod

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# Fixed confidence threshold (the design default, R6.1). Threshold-edge gating
# is Property 5's concern; here we only need clean qualify / not-qualify bands.
THRESHOLD = 0.80

# Fixed OCR strings: case/whitespace differences still normalize-equal for the
# qualifying case (R6.4), while the non-qualifying string never normalizes equal.
_OCR_EXPECTED = "Submit"
_OCR_MATCHING = "  submit  "  # normalizes to "submit" == normalize("Submit")
_OCR_NON_MATCHING = "Cancel"  # normalizes to "cancel" != "submit"


class Scenario(NamedTuple):
    """A fully-realized ranked-localization scenario plus its oracle inputs."""

    # Executable inputs to the function under test.
    target: TargetElement
    config: ReliabilityConfig
    image_matcher: FakeImageMatcher
    ocr_provider: FakeOcrProvider
    screen: FakeScreen

    # The decision vector aligned to STRATEGY_ORDER: would_qualify[i] is whether
    # STRATEGY_ORDER[i] is set up to qualify in isolation.
    would_qualify: Tuple[bool, ...]

    # Per-strategy expected (point, confidence) the producing strategy yields,
    # used by the independent oracle to predict the winning match.
    im_point: Tuple[int, int]
    im_conf: float
    roi: Region
    roi_point: Tuple[int, int]
    roi_conf: float
    anchor_img_point: Tuple[int, int]
    offset: Tuple[int, int]
    origin: Tuple[int, int]
    win_offset: Tuple[int, int]
    abs_point: Tuple[int, int]


# ---------------------------------------------------------------------------
# Independent oracle (pure statement of Property 4; never calls the SUT)
# ---------------------------------------------------------------------------


def _winner_index(would_qualify: Tuple[bool, ...]) -> Optional[int]:
    """The rank index of the highest-ranked qualifying strategy, or None."""

    return next((i for i, q in enumerate(would_qualify) if q), None)


def _expected_match(
    scn: Scenario,
) -> Tuple[Optional[LocalizationStrategy], Optional[Tuple[int, int]], Optional[float]]:
    """Predict (strategy, point, confidence) of the selected match.

    Computed solely from the generated decision vector and the scenario's
    recorded geometry, reimplementing each strategy's point/confidence per the
    spec (anchor + offset, ROI centre, window origin + offset, etc.). This is
    deliberately independent of ``locate_with_fallback`` and ``run_strategy``.
    """

    idx = _winner_index(scn.would_qualify)
    if idx is None:
        return None, None, None

    strategy = STRATEGY_ORDER[idx]
    if strategy == LocalizationStrategy.IMAGE_MATCH:
        return strategy, scn.im_point, scn.im_conf
    if strategy == LocalizationStrategy.OCR_TEXT:
        roi = scn.roi
        return strategy, (roi.x + roi.width // 2, roi.y + roi.height // 2), 1.0
    if strategy == LocalizationStrategy.ANCHOR_RELATIVE:
        ax, ay = scn.anchor_img_point
        dx, dy = scn.offset
        return strategy, (ax + dx, ay + dy), 1.0
    if strategy == LocalizationStrategy.ROI_CONSTRAINED:
        return strategy, scn.roi_point, scn.roi_conf
    if strategy == LocalizationStrategy.WINDOW_RELATIVE:
        ox, oy = scn.origin
        wx, wy = scn.win_offset
        return strategy, (ox + wx, oy + wy), 1.0
    # ABSOLUTE (session is None -> identity transform).
    return strategy, scn.abs_point, 1.0


# ---------------------------------------------------------------------------
# Scenario generator: realize an arbitrary qualify/not-qualify vector
# ---------------------------------------------------------------------------


_POINTS = st.tuples(st.integers(min_value=-50, max_value=50),
                    st.integers(min_value=-50, max_value=50))
_QUAL_CONF = st.floats(min_value=THRESHOLD, max_value=1.0)
_NONQUAL_CONF = st.floats(min_value=0.0, max_value=THRESHOLD - 0.01)


@st.composite
def _ranked_scenario(draw) -> Scenario:
    would_qualify = tuple(draw(st.lists(st.booleans(), min_size=6, max_size=6)))

    # Geometry / points used to build the producing-strategy results.
    im_point = draw(_POINTS)
    roi = Region(
        x=draw(st.integers(min_value=0, max_value=50)),
        y=draw(st.integers(min_value=0, max_value=50)),
        width=draw(st.integers(min_value=1, max_value=50)),
        height=draw(st.integers(min_value=1, max_value=50)),
    )
    roi_point = draw(_POINTS)
    anchor_img_point = draw(_POINTS)
    offset = draw(_POINTS)
    origin = draw(_POINTS)
    win_offset = draw(_POINTS)
    abs_point = draw(_POINTS)

    im_conf = draw(_QUAL_CONF if would_qualify[0] else _NONQUAL_CONF)
    roi_conf = draw(_QUAL_CONF if would_qualify[3] else _NONQUAL_CONF)
    anchor_conf = draw(_QUAL_CONF if would_qualify[2] else _NONQUAL_CONF)

    # IMAGE_MATCH (idx 0) and ROI_CONSTRAINED (idx 3) both query target.reference
    # ("target"); a per-reference queue is consumed positionally. IMAGE_MATCH
    # consumes position 0; when reached, ROI consumes the next position(s):
    #   - would_qualify[3] True  -> ROI's in-ROI match (pos 1) qualifies.
    #   - would_qualify[3] False -> in-ROI (pos 1) + full-screen fallback (pos 2)
    #     both fail to qualify.
    target_results: List[ImageMatchResult] = [ImageMatchResult(confidence=im_conf, point=im_point)]
    if would_qualify[3]:
        target_results.append(ImageMatchResult(confidence=roi_conf, point=roi_point))
    else:
        target_results.append(ImageMatchResult(confidence=roi_conf, point=roi_point))
        target_results.append(ImageMatchResult(confidence=0.0, point=(0, 0)))

    # ANCHOR_RELATIVE (idx 2) locates its anchor via image match on "anchor"
    # (a distinct reference, independent queue). The anchor counts as present
    # only when the match has a point and confidence >= threshold (R7.2/R7.3).
    anchor_results = [ImageMatchResult(confidence=anchor_conf, point=anchor_img_point)]

    image_matcher = FakeImageMatcher(
        per_reference={"target": target_results, "anchor": anchor_results},
        default=ImageMatchResult(confidence=0.0, point=(0, 0)),
    )

    # OCR_TEXT (idx 1): the recognized text normalizes-equal to the expected
    # text iff this strategy should qualify (R6.4); confidence is binary (1.0).
    ocr_text = _OCR_MATCHING if would_qualify[1] else _OCR_NON_MATCHING
    ocr_provider = FakeOcrProvider(default=ocr_text)

    # WINDOW_RELATIVE (idx 4) and ABSOLUTE (idx 5) are deterministic coordinate
    # math that always qualify (confidence 1.0) when their inputs are present;
    # presence is toggled to realize their qualify decision.
    window = WindowRef(origin=origin) if would_qualify[4] else None
    target = TargetElement(
        reference=ImageRef(path="target"),
        text=_OCR_EXPECTED,
        anchor=TargetElement(reference=ImageRef(path="anchor")),
        offset=offset,
        roi=roi,
        window=window,
        win_offset=win_offset if would_qualify[4] else None,
        absolute=abs_point if would_qualify[5] else None,
    )

    # A frame with no advertised bounds so can_constrain only validates the ROI
    # (a valid, non-empty Region here), keeping ROI-constrained search active.
    screen = FakeScreen(default="frame")

    # Single traversal: isolate ranked-order selection from retry/backoff.
    config = ReliabilityConfig(confidence_threshold=THRESHOLD, max_locate_attempts=1)

    return Scenario(
        target=target,
        config=config,
        image_matcher=image_matcher,
        ocr_provider=ocr_provider,
        screen=screen,
        would_qualify=would_qualify,
        im_point=im_point,
        im_conf=im_conf,
        roi=roi,
        roi_point=roi_point,
        roi_conf=roi_conf,
        anchor_img_point=anchor_img_point,
        offset=offset,
        origin=origin,
        win_offset=win_offset,
        abs_point=abs_point,
    )


# ---------------------------------------------------------------------------
# Property 4 - selection: highest-ranked qualifying match, strategy recorded
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_ranked_scenario())
def test_property_04_selects_highest_ranked_qualifying_match(scn: Scenario):
    # Feature: desktop-automation-reliability, Property 4: Localization tries strategies in ranked order and selects the highest-ranked qualifying match
    result = locate_with_fallback(
        scn.target,
        scn.config,
        capture=scn.screen.capture,
        image_matcher=scn.image_matcher,
        ocr_provider=scn.ocr_provider,
        session=None,
        clock=FakeClock(),
    )

    expected_strategy, expected_point, expected_conf = _expected_match(scn)

    if expected_strategy is None:
        # No strategy qualified -> NotLocated, with nothing recorded (R9.4).
        assert result.located is False
        assert result.strategy is None
        assert result.point is None
        assert result.confidence is None
        return

    # Located by the highest-ranked qualifying strategy (R5.2/R5.3) and that
    # producing strategy is recorded on the result (R5.4).
    assert result.located is True
    assert result.strategy == expected_strategy

    # The returned match is the one that strategy produces (point + confidence),
    # not some other strategy's candidate.
    assert result.point == expected_point
    assert result.confidence == expected_conf

    # The accepted match is at or above the configured threshold (R6.2).
    assert result.confidence is not None
    assert result.confidence >= scn.config.confidence_threshold


# ---------------------------------------------------------------------------
# Property 4 - strict ranked-order traversal that stops at the winner
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_ranked_scenario())
def test_property_04_evaluates_strategies_in_strict_ranked_order(scn: Scenario):
    # Feature: desktop-automation-reliability, Property 4: Localization tries strategies in ranked order and selects the highest-ranked qualifying match
    evaluated: List[LocalizationStrategy] = []
    real_run_strategy = locator_mod.run_strategy

    def spy(strategy, *args, **kwargs):
        evaluated.append(strategy)
        return real_run_strategy(strategy, *args, **kwargs)

    with mock.patch.object(locator_mod, "run_strategy", spy):
        locate_with_fallback(
            scn.target,
            scn.config,
            capture=scn.screen.capture,
            image_matcher=scn.image_matcher,
            ocr_provider=scn.ocr_provider,
            session=None,
            clock=FakeClock(),
        )

    idx = _winner_index(scn.would_qualify)
    if idx is None:
        # No strategy qualifies: every strategy is evaluated, in exact order.
        assert evaluated == list(STRATEGY_ORDER)
    else:
        # Strategies are evaluated strictly in rank order up to and including
        # the winner; traversal stops there (no lower-ranked strategy is tried).
        assert evaluated == list(STRATEGY_ORDER[: idx + 1])

    # Whatever the outcome, evaluation never deviates from the fixed rank order
    # (R5.1): the evaluated sequence is always a prefix of STRATEGY_ORDER.
    assert evaluated == list(STRATEGY_ORDER[: len(evaluated)])
