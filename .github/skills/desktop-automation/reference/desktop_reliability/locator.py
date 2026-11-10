"""Element_Locator primitives and coordinate math for the desktop-reliability pattern.

This module implements **Component 2** of the design (the ``Element_Locator``):
the per-strategy localization *primitives*, the coordinate math they rely on
(anchor + offset, window origin + offset, absolute scaled by the active
scaling factor), the OCR text normalization, and the execution-vs-exploration
scaling recompute (``normalize_for_scaling``).

Scope of this module (task 2.1):

- :data:`STRATEGY_ORDER` — the fixed ranked traversal order (R5.1). The ranked
  *traversal loop* (``locate_with_fallback``) is implemented by a later task
  (2.2); only the constant lives here so 2.2 can build on it.
- :func:`run_strategy` — dispatches to a single strategy primitive and returns
  a :class:`StrategyResult` (point + confidence + ``matched`` flag).
- The six strategy primitives: :func:`image_match`, :func:`ocr_text_match`,
  :func:`anchor_relative`, :func:`roi_constrained`, :func:`window_relative`,
  :func:`absolute`.
- :func:`normalize` — OCR text normalization (R6.4): ``text.strip().lower()``.
- :func:`normalize_for_scaling` — execution-vs-exploration coordinate recompute
  (R10.2/R10.3): identity when the environments are equal; otherwise scale by
  the active scaling ratio.

All external dependencies are **injected** (an image matcher, an OCR provider,
and the :class:`~desktop_reliability.models.SessionEnvironment`) so every
primitive is exercisable with the deterministic fakes in ``fakes.py`` and needs
no real desktop, clock, or external service.

Confidence threshold gating (R6.1–R6.3) is reported by each primitive via
:meth:`StrategyResult.qualifies`, which accepts a match when its confidence is
**greater than or equal to** the threshold (exactly-at-threshold is accepted,
R6.3). Selecting the highest-ranked qualifying match across strategies is the
job of the traversal loop (task 2.2); the primitive only reports its own
confidence and whether it qualifies.

This module is *logic only* — it performs no I/O of its own; capture and timing
are the caller's responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol, Tuple, Union, runtime_checkable

from .models import (
    FULL_SCREEN,
    LocalizationResult,
    LocalizationStrategy,
    Region,
    ReliabilityConfig,
    SessionEnvironment,
    TargetElement,
    WindowRef,
    _FullScreenSentinel,
)

__all__ = [
    "STRATEGY_ORDER",
    "StrategyResult",
    "ImageMatcher",
    "OcrProvider",
    "Clock",
    "Capture",
    "normalize",
    "normalize_for_scaling",
    "scale_point",
    "can_constrain",
    "window_origin",
    "text_match",
    "image_match",
    "ocr_text_match",
    "anchor_relative",
    "roi_constrained",
    "window_relative",
    "absolute",
    "run_strategy",
    "backoff_delay_ms",
    "backoff_sleep",
    "locate_with_fallback",
]


# A region argument is either a bounded Region or the FULL_SCREEN sentinel.
RegionArg = Union[Region, _FullScreenSentinel]
Point = Tuple[int, int]


# ---------------------------------------------------------------------------
# Ranked strategy order (R5.1) — most → least stable.
# ---------------------------------------------------------------------------

#: The fixed, ranked traversal order used by ``locate_with_fallback`` (task 2.2).
#: Declared here because the locator primitives and the traversal share it; it
#: mirrors the declaration order of :class:`LocalizationStrategy` (R5.1).
STRATEGY_ORDER: Tuple[LocalizationStrategy, ...] = (
    LocalizationStrategy.IMAGE_MATCH,
    LocalizationStrategy.OCR_TEXT,
    LocalizationStrategy.ANCHOR_RELATIVE,
    LocalizationStrategy.ROI_CONSTRAINED,
    LocalizationStrategy.WINDOW_RELATIVE,
    LocalizationStrategy.ABSOLUTE,
)


# ---------------------------------------------------------------------------
# Injected dependency protocols (duck-typed; the fakes satisfy these).
# ---------------------------------------------------------------------------


@runtime_checkable
class ImageMatcher(Protocol):
    """An image-match provider returning a confidence score and optional point.

    Satisfied by :class:`desktop_reliability.fakes.FakeImageMatcher`; in
    generated code this wraps ``pyautogui.locateOnScreen`` / OpenCV. The result
    must expose ``confidence: float`` and ``point: Optional[(x, y)]``.
    """

    def match(self, reference: object, region: RegionArg = FULL_SCREEN) -> object: ...


@runtime_checkable
class OcrProvider(Protocol):
    """An OCR text provider returning the recognized text for a region.

    Satisfied by :class:`desktop_reliability.fakes.FakeOcrProvider`; in
    generated code this wraps ``pytesseract`` over the capture region.
    """

    def read(self, region: RegionArg = FULL_SCREEN) -> str: ...


@runtime_checkable
class Clock(Protocol):
    """A monotonic clock with non-blocking sleep (used for backoff).

    Satisfied by :class:`desktop_reliability.fakes.FakeClock`; in generated code
    this wraps ``time.monotonic`` / ``time.sleep``. ``now`` returns seconds as a
    float; ``sleep`` advances time by ``seconds``. The locator only needs
    ``sleep`` to realize the exponential backoff between attempts, but the full
    clock protocol is accepted so the same fake serves locator and verifier.
    """

    def now(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


#: A fresh-capture function: given the search region it returns a fresh screen
#: state for the current attempt. Models the design's ``capture_state(region)``.
#: :meth:`desktop_reliability.fakes.FakeScreen.capture` satisfies this directly,
#: so a test can pass ``screen.capture`` as the ``capture`` argument.
Capture = Callable[[RegionArg], object]


# ---------------------------------------------------------------------------
# StrategyResult — the candidate produced by a single strategy primitive.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategyResult:
    """The candidate match produced by one localization strategy.

    A strategy reports three things:

    - ``matched``: whether the strategy produced a candidate at all (e.g. the
      image matcher ran, the anchor was located, the OCR text was equal). A
      strategy that is *not applicable* to the target (missing reference,
      missing anchor, missing absolute coords, …) reports ``matched=False``.
    - ``point``: the resolved screen point ``(x, y)`` when matched.
    - ``confidence``: the Confidence_Score in ``[0.0, 1.0]``. Deterministic
      strategies (anchor / window / absolute / equal-text OCR) report ``1.0``;
      image-based strategies report the matcher's score.

    Threshold gating (R6.1–R6.3) is expressed by :meth:`qualifies`, which is
    **inclusive** at the threshold (R6.3). The traversal loop (task 2.2) is what
    selects the highest-ranked *qualifying* candidate; an individual primitive
    only reports its own state.
    """

    matched: bool
    point: Optional[Point] = None
    confidence: float = 0.0

    @classmethod
    def no_match(cls) -> "StrategyResult":
        """A non-match: the strategy produced no candidate (R6.2/R7.3/etc.)."""

        return cls(matched=False, point=None, confidence=0.0)

    @classmethod
    def hit(cls, point: Optional[Point], confidence: float) -> "StrategyResult":
        """A candidate match at ``point`` with the given ``confidence``."""

        return cls(matched=True, point=point, confidence=float(confidence))

    def qualifies(self, threshold: float) -> bool:
        """Whether this candidate is accepted at ``threshold`` (R6.1–R6.3).

        Accepts when the strategy matched and its confidence is **greater than
        or equal to** the threshold; rejects (returns ``False``) when the
        confidence is strictly below the threshold. Exactly-at-threshold is
        accepted (R6.3, inclusive).
        """

        return self.matched and self.confidence is not None and self.confidence >= threshold


# ---------------------------------------------------------------------------
# Text normalization (R6.4) and text matching (R6.4/R6.5).
# ---------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Normalize text for OCR comparison (R6.4).

    ``normalize(text) = lowercase(strip_leading_trailing_whitespace(text))``.
    Leading/trailing whitespace is trimmed and the result is lowercased so
    case and surrounding whitespace never cause a false mismatch. Raises if
    ``text`` is not a string (callers treat that as a normalization failure,
    R6.5).
    """

    return text.strip().lower()


def text_match(recognized: Optional[str], expected: Optional[str]) -> bool:
    """Return whether ``recognized`` matches ``expected`` after normalization.

    Succeeds **iff** the two strings are equal after :func:`normalize`
    (lowercase + trim) is applied to both (R6.4). If either value cannot be
    normalized (e.g. it is ``None`` or not a string), normalization is treated
    as failed and the match is rejected (R6.5).
    """

    try:
        return normalize(recognized) == normalize(expected)  # type: ignore[arg-type]
    except (AttributeError, TypeError):
        # R6.5: text normalization failed -> reject the match.
        return False


# ---------------------------------------------------------------------------
# Scaling / coordinate recompute (R10.2/R10.3).
# ---------------------------------------------------------------------------


def scale_point(point: Point, scaling_factor: int) -> Point:
    """Scale a point by an absolute scaling factor expressed as a percent.

    ``scale_point((x, y), 150) == (round(x * 1.5), round(y * 1.5))``. A factor
    of ``100`` is the identity. This is the raw "adjust coordinates by the
    active Scaling_Factor" operation (R10.2).
    """

    ratio = scaling_factor / 100.0
    return (round(point[0] * ratio), round(point[1] * ratio))


def normalize_for_scaling(
    point: Point,
    session: Optional[SessionEnvironment],
) -> Point:
    """Recompute a recorded point for the execution-time environment (R10.2/R10.3).

    A point recorded during *exploration* must be re-expressed in the
    *execution-time* coordinate space before it is used. The transform is:

    - **Identity** when the execution-time environment equals the
      exploration-time environment — i.e. both the resolution and the scaling
      factor match (R10.3 "equal environments"), or when no ``session`` is
      supplied. The point is returned unchanged.
    - **Scale by the active ratio** otherwise: the point is multiplied by
      ``execution_scaling / exploration_scaling`` and rounded to the nearest
      pixel (R10.2/R10.3 "recompute using the execution-time values"). When
      exploration was at 100%, this reduces to scaling by the active factor,
      matching the design's ``scale(absolute, session.scaling)``.

    The magnitude of the transform is driven by the scaling ratio; a pure
    resolution change with equal scaling yields a ratio of ``1.0`` (the point is
    re-expressed against the execution values but its pixel coordinates are
    unchanged), which is the well-defined behavior in the absence of a separate
    resolution remap.
    """

    if session is None:
        return point

    environments_equal = (
        session.scaling_factor == session.exploration_scaling
        and session.resolution == session.exploration_resolution
    )
    if environments_equal:
        # R10.3: identity transform when the environments are equal.
        return point

    # R10.2/R10.3: recompute using execution-time scaling.
    ratio = session.scaling_factor / session.exploration_scaling
    return (round(point[0] * ratio), round(point[1] * ratio))


# ---------------------------------------------------------------------------
# Geometry helpers.
# ---------------------------------------------------------------------------


def can_constrain(frame: object, roi: object) -> bool:
    """Whether a search can be constrained to ``roi`` (R8.1/R8.2).

    A search can be constrained only to a **valid, non-empty** bounded
    :class:`Region` (positive width and height). An undefined, full-screen, or
    empty/invalid ROI cannot constrain the search, so the caller falls back to
    a full-screen search (R8.2). When ``frame`` is a croppable frame (exposes
    ``width``/``height``), the ROI must also fit within the frame bounds.
    """

    if not isinstance(roi, Region):
        return False
    if roi.width <= 0 or roi.height <= 0:
        return False
    # When the frame advertises its bounds, the ROI must fit inside them.
    frame_w = getattr(frame, "width", None)
    frame_h = getattr(frame, "height", None)
    if isinstance(frame_w, int) and isinstance(frame_h, int):
        if roi.x < 0 or roi.y < 0:
            return False
        if roi.x + roi.width > frame_w or roi.y + roi.height > frame_h:
            return False
    return True


def _roi_center(roi: Region) -> Point:
    """Return the center point of a bounded region."""

    return (roi.x + roi.width // 2, roi.y + roi.height // 2)


def window_origin(window: Optional[WindowRef]) -> Optional[Point]:
    """Return the current top-left origin of ``window`` (R11.3).

    Reads the origin recorded on the :class:`WindowRef`. Returns ``None`` when
    the window or its origin is unknown, in which case window-relative
    positioning is not applicable. (The Window Manager component in ``window.py``
    — a later task — provides the live origin in generated code; here the
    reference reads the structured ``WindowRef.origin``.)
    """

    if window is None:
        return None
    return window.origin


# ---------------------------------------------------------------------------
# Strategy primitives.
# ---------------------------------------------------------------------------


def image_match(
    reference: object,
    *,
    image_matcher: ImageMatcher,
    region: RegionArg = FULL_SCREEN,
) -> StrategyResult:
    """IMAGE_MATCH primitive: match a reference image and report confidence (R6.1–R6.3).

    Runs the injected image matcher against ``region`` and reports the located
    point with the matcher's Confidence_Score. The accept/reject decision is
    left to :meth:`StrategyResult.qualifies` (and the traversal loop). When no
    reference image is available the strategy is not applicable and reports a
    non-match.
    """

    if reference is None:
        return StrategyResult.no_match()
    result = image_matcher.match(reference, region)
    return StrategyResult.hit(point=getattr(result, "point", None),
                              confidence=getattr(result, "confidence", 0.0))


def ocr_text_match(
    expected_text: Optional[str],
    *,
    ocr_provider: OcrProvider,
    region: RegionArg = FULL_SCREEN,
) -> StrategyResult:
    """OCR_TEXT primitive: match recognized text against expected text (R6.4/R6.5).

    Reads text from ``region`` and compares it to ``expected_text`` after
    normalization (lowercase + trim). Succeeds iff the normalized strings are
    equal (R6.4); a normalization failure rejects the match (R6.5). On a match
    the located point is the center of the search region when it is a bounded
    :class:`Region` (otherwise unknown). Text equality is binary, so a match
    reports full confidence (``1.0``) and a non-match reports ``0.0``.
    """

    if expected_text is None:
        return StrategyResult.no_match()
    recognized = ocr_provider.read(region)
    if not text_match(recognized, expected_text):
        return StrategyResult.no_match()
    point = _roi_center(region) if isinstance(region, Region) else None
    return StrategyResult.hit(point=point, confidence=1.0)


def _locate_anchor(
    anchor: TargetElement,
    *,
    image_matcher: ImageMatcher,
    config: ReliabilityConfig,
    session: Optional[SessionEnvironment],
) -> Optional[Point]:
    """Locate a stable anchor element and return its point, or ``None`` (R7.2/R7.3).

    The anchor is located by image matching its reference (the typical "stable,
    reliably locatable" element); the match must meet the confidence threshold
    to count as present. If the anchor has no reference image but does carry an
    absolute coordinate, that coordinate (recomputed for scaling) is used as a
    fallback. Returns ``None`` when the anchor cannot be confirmed (R7.3).
    """

    if anchor.reference is not None:
        region = anchor.roi if isinstance(anchor.roi, Region) else FULL_SCREEN
        result = image_matcher.match(anchor.reference, region)
        confidence = getattr(result, "confidence", 0.0)
        point = getattr(result, "point", None)
        if point is not None and confidence >= config.confidence_threshold:
            return point
        return None
    if anchor.absolute is not None:
        return normalize_for_scaling(anchor.absolute, session)
    return None


def anchor_relative(
    target: TargetElement,
    *,
    image_matcher: ImageMatcher,
    config: ReliabilityConfig,
    session: Optional[SessionEnvironment] = None,
) -> StrategyResult:
    """ANCHOR_RELATIVE primitive: ``point = anchor.point + offset`` (R7.1–R7.3).

    Confirms the anchor is present in the current screen state before computing
    the target position (R7.2). When the anchor is located, the target point is
    the anchor point plus the configured offset (R7.1). When the anchor cannot
    be located — or the target has no anchor/offset — no anchor-relative point
    is produced (``matched=False``) so the caller falls through to the next
    strategy (R7.3).
    """

    if target.anchor is None or target.offset is None:
        return StrategyResult.no_match()
    anchor_point = _locate_anchor(
        target.anchor, image_matcher=image_matcher, config=config, session=session
    )
    if anchor_point is None:
        return StrategyResult.no_match()  # R7.3: fall through to next strategy.
    dx, dy = target.offset
    return StrategyResult.hit(point=(anchor_point[0] + dx, anchor_point[1] + dy), confidence=1.0)


def roi_constrained(
    target: TargetElement,
    frame: object,
    config: ReliabilityConfig,
    *,
    image_matcher: ImageMatcher,
) -> StrategyResult:
    """ROI_CONSTRAINED primitive: search the ROI first, expand only if needed (R8.1–R8.4).

    When the target defines a Region_Of_Interest that the search can be
    constrained to (R8.1), the ROI is searched first; a qualifying match there
    is returned without expanding to the full screen (R8.3). When the ROI is
    undefined/invalid (cannot constrain, R8.2) or the element is not found
    within it (R8.4), the search expands to the full screen and that result is
    returned (the caller decides whether it qualifies before reporting the
    element as not located).
    """

    if can_constrain(frame, target.roi):
        in_roi = image_match(target.reference, image_matcher=image_matcher, region=target.roi)
        if in_roi.qualifies(config.confidence_threshold):
            return in_roi  # R8.3: found within ROI, do not expand.
    # R8.2/R8.4: cannot constrain, or not found in ROI -> full-screen search.
    return image_match(target.reference, image_matcher=image_matcher, region=FULL_SCREEN)


def window_relative(
    target: TargetElement,
    *,
    session: Optional[SessionEnvironment] = None,
) -> StrategyResult:
    """WINDOW_RELATIVE primitive: ``point = window_origin + win_offset`` (R11.3, R10.2/R10.3).

    Computes the interaction point relative to the *current* window origin
    (R11.3). The recorded window offset is recomputed for the execution-time
    environment via :func:`normalize_for_scaling` — the identity transform when
    the environments are equal (matching the design's ``window_origin +
    win_offset``), or scaled by the active factor when scaling differs
    (R10.2/R10.3). Not applicable (``matched=False``) when the window origin or
    the offset is unknown.
    """

    origin = window_origin(target.window)
    if origin is None or target.win_offset is None:
        return StrategyResult.no_match()
    dx, dy = normalize_for_scaling(target.win_offset, session)
    return StrategyResult.hit(point=(origin[0] + dx, origin[1] + dy), confidence=1.0)


def absolute(
    target: TargetElement,
    *,
    session: Optional[SessionEnvironment] = None,
) -> StrategyResult:
    """ABSOLUTE primitive: last-resort recorded coordinates, scaled (R10.2/R10.3).

    Uses the recorded absolute coordinate, recomputed for the execution-time
    environment via :func:`normalize_for_scaling` (scaled by the active scaling
    factor; identity when the environments are equal). Not applicable
    (``matched=False``) when no absolute coordinate is recorded.
    """

    if target.absolute is None:
        return StrategyResult.no_match()
    return StrategyResult.hit(point=normalize_for_scaling(target.absolute, session), confidence=1.0)


# ---------------------------------------------------------------------------
# Strategy dispatch.
# ---------------------------------------------------------------------------


def run_strategy(
    strategy: LocalizationStrategy,
    target: TargetElement,
    frame: object,
    config: ReliabilityConfig,
    *,
    image_matcher: ImageMatcher,
    ocr_provider: OcrProvider,
    session: Optional[SessionEnvironment] = None,
) -> StrategyResult:
    """Dispatch a single localization strategy and return its candidate.

    Routes ``strategy`` to the matching primitive and returns the resulting
    :class:`StrategyResult` (point + confidence + ``matched`` flag). The
    dependencies (image matcher, OCR provider, session environment) are injected
    so the dispatch is fully testable with the deterministic fakes. Selecting
    the highest-ranked *qualifying* candidate across strategies is the job of
    the traversal loop (task 2.2); this function evaluates exactly one strategy.

    Region routing:

    - IMAGE_MATCH searches the full screen via the matcher.
    - OCR_TEXT reads the target's ROI when defined, else the full screen.
    - ROI_CONSTRAINED searches the ROI first (with full-screen fallback).
    - ANCHOR_RELATIVE / WINDOW_RELATIVE / ABSOLUTE are computed coordinate math.
    """

    if strategy == LocalizationStrategy.IMAGE_MATCH:
        return image_match(target.reference, image_matcher=image_matcher, region=FULL_SCREEN)

    if strategy == LocalizationStrategy.OCR_TEXT:
        region: RegionArg = target.roi if isinstance(target.roi, Region) else FULL_SCREEN
        return ocr_text_match(target.text, ocr_provider=ocr_provider, region=region)

    if strategy == LocalizationStrategy.ANCHOR_RELATIVE:
        return anchor_relative(
            target, image_matcher=image_matcher, config=config, session=session
        )

    if strategy == LocalizationStrategy.ROI_CONSTRAINED:
        return roi_constrained(target, frame, config, image_matcher=image_matcher)

    if strategy == LocalizationStrategy.WINDOW_RELATIVE:
        return window_relative(target, session=session)

    if strategy == LocalizationStrategy.ABSOLUTE:
        return absolute(target, session=session)

    # Defensive: an unknown strategy never produces a match.
    return StrategyResult.no_match()  # pragma: no cover


# ---------------------------------------------------------------------------
# Backoff schedule (R9.3).
# ---------------------------------------------------------------------------


def backoff_delay_ms(attempt: int, config: ReliabilityConfig) -> int:
    """Exponential backoff delay for ``attempt`` in milliseconds (R9.3).

    Implements the design schedule ``delay(attempt) = backoff_base_ms *
    2^(attempt-1)`` so the per-attempt delay is indexed by the (1-based) attempt
    number: attempts 1, 2, 3 yield ``500ms, 1000ms, 2000ms`` from the default
    base. ``attempt`` is 1-based; a value below 1 is treated as 1 so the
    schedule never produces a fractional/negative delay.
    """

    safe_attempt = max(1, attempt)
    return config.backoff_base_ms * 2 ** (safe_attempt - 1)


def backoff_sleep(
    attempt: int,
    config: ReliabilityConfig,
    *,
    clock: Optional[Clock] = None,
) -> int:
    """Sleep the backoff delay for ``attempt`` and return it in milliseconds (R9.3).

    Computes :func:`backoff_delay_ms` and, when a ``clock`` is injected, advances
    it by that many seconds (``delay_ms / 1000``) via ``clock.sleep`` so the
    backoff is realized deterministically against the fake clock with no real
    delay. When no ``clock`` is supplied the delay is computed and returned but
    no sleep occurs, which keeps the schedule inspectable in contexts that do
    not drive time. The returned millisecond delay lets callers/tests assert the
    exact backoff applied.
    """

    delay_ms = backoff_delay_ms(attempt, config)
    if clock is not None:
        clock.sleep(delay_ms / 1000.0)
    return delay_ms


# ---------------------------------------------------------------------------
# locate_with_fallback — ranked traversal with retry and backoff (R5/R9).
# ---------------------------------------------------------------------------


def locate_with_fallback(
    target: TargetElement,
    config: ReliabilityConfig,
    *,
    capture: Capture,
    image_matcher: ImageMatcher,
    ocr_provider: OcrProvider,
    session: Optional[SessionEnvironment] = None,
    clock: Optional[Clock] = None,
) -> LocalizationResult:
    """Resolve a target to a screen point via ranked fallback, retry, and backoff.

    Implements **Component 2** of the design (the ``Element_Locator`` traversal
    loop). For each attempt it captures a *fresh* screen state, walks
    :data:`STRATEGY_ORDER` in fixed rank order, and accepts the first strategy
    whose candidate qualifies at the configured confidence threshold; the
    highest-ranked qualifying match wins. The producing strategy and its
    confidence are recorded on the returned :class:`LocalizationResult`.

    Behavior (design "Component 2" pseudocode):

    - **Fresh capture per attempt (R9.1):** ``capture(FULL_SCREEN)`` is called
      at the start of every attempt so each attempt evaluates the strategies
      against a newly captured frame (transient rendering delays do not poison
      later attempts). The captured frame is what ROI-constrained search bounds
      itself against; the injected ``image_matcher`` / ``ocr_provider`` resolve
      the actual candidate per strategy, and ``session`` drives the
      execution-vs-exploration scaling recompute inside the coordinate
      strategies (R10.2/R10.3).
    - **Ranked traversal, highest-ranked wins (R5.1–R5.3):** strategies are
      evaluated strictly in [image match, OCR text, anchor-relative,
      ROI-constrained, window-relative, absolute] order; the loop returns on the
      first strategy whose :meth:`StrategyResult.qualifies` is true (confidence
      ``>=`` threshold, inclusive — R6.1–R6.3), so a higher-ranked qualifying
      match always takes precedence over a lower-ranked one.
    - **Records the producing strategy (R5.4):** the result carries the strategy
      that produced the selected match and its confidence.
    - **Bounded attempts with exponential backoff (R9.2/R9.3):** at most
      ``config.max_locate_attempts`` (default 3) attempts are made. When an
      attempt yields no qualifying match *and* another attempt remains, the
      backoff delay ``500ms * 2^(attempt-1)`` is applied **between** attempts via
      :func:`backoff_sleep` (no trailing sleep after the final attempt). A
      ``clock`` is injected so the backoff is realized against the fake clock.
    - **NotLocated when exhausted (R9.4):** once every attempt is exhausted with
      no qualifying match, a not-located result is returned.

    This function is *logic only*: capture and timing are injected, so it is
    fully exercisable with the deterministic fakes (``FakeScreen`` /
    ``FakeImageMatcher`` / ``FakeOcrProvider`` / ``FakeClock``) and needs no real
    desktop.
    """

    for attempt in range(1, config.max_locate_attempts + 1):  # R9.2: bounded attempts
        # R9.1: capture a fresh screen state at the start of every attempt.
        frame = capture(FULL_SCREEN)

        for strategy in STRATEGY_ORDER:  # R5.2: ranked traversal, most→least stable.
            candidate = run_strategy(
                strategy,
                target,
                frame,
                config,
                image_matcher=image_matcher,
                ocr_provider=ocr_provider,
                session=session,
            )
            # R5.3/R6.1–R6.3: first (highest-ranked) qualifying match wins.
            if candidate.qualifies(config.confidence_threshold):
                # R5.4: record the producing strategy and its confidence.
                return LocalizationResult.located_at(
                    point=candidate.point,
                    strategy=strategy,
                    confidence=candidate.confidence,
                )

        # No qualifying strategy this attempt. Apply exponential backoff between
        # attempts only (R9.3) — no trailing sleep once attempts are exhausted.
        if attempt < config.max_locate_attempts:
            backoff_sleep(attempt, config, clock=clock)

    # R9.4: all attempts exhausted without a qualifying match.
    return LocalizationResult.not_located()
