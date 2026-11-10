"""Deterministic test fakes for the desktop-reliability reference implementation.

These fakes let the locator, verifier, and verified-interaction logic be
exercised with **no real desktop, no real clock, and no external services**.
They are *development-time-only* test aids (see ``models`` and the design
"Testing Strategy" → "Isolation"): screen capture, image matching, OCR, the
clock, and window focus are all faked so property/example tests are fast and
deterministic in oracle.

The four fakes mirror the four real dependencies the helpers talk to:

============================  =======================================  =========================
Fake                          Stands in for                            Consumed by (later tasks)
============================  =======================================  =========================
``FakeClock``                 the monotonic clock + ``sleep``          verifier poll / backoff
``FakeScreen``                ``screen_capture`` / ``capture_state``   locator, interaction
``FakeFocusManager``          window-focus manager                     window, interaction
``FakeImageMatcher``          image match (confidence)                 locator (IMAGE_MATCH)
``FakeOcrProvider``           OCR text recognition                     locator (OCR_TEXT)
============================  =======================================  =========================

Design choices that make the fakes flexible for downstream tasks:

- **Scripted sequences**: every fake accepts an ordered script so successive
  calls can return different values (e.g. a different frame for pre vs. post,
  or a rising confidence across retry attempts).
- **Queryable call logs**: every fake records the calls made against it
  (count, order, and arguments) so tests can assert ordering invariants such
  as "focus was confirmed before the action" or "a fresh frame was captured on
  every attempt".
- **No real time**: ``FakeClock`` advances a virtual clock; it never sleeps.

Nothing in this module performs I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable, List, Optional, Sequence, Tuple, Union

from .models import FULL_SCREEN, ImageRef, Region, _FullScreenSentinel

__all__ = [
    # Frame + result/record value types
    "Frame",
    "ImageMatchResult",
    "CaptureCall",
    "FocusOp",
    "ImageMatchCall",
    "OcrCall",
    # Fakes
    "FakeClock",
    "FakeScreen",
    "FakeFocusManager",
    "FakeImageMatcher",
    "FakeOcrProvider",
]


# A region argument is either a bounded Region or the FULL_SCREEN sentinel.
RegionArg = Union[Region, _FullScreenSentinel]

# Sentinel distinguishing "no value yet" from a legitimately-scripted ``None``.
_UNSET: object = object()


# ---------------------------------------------------------------------------
# Frame: an optional 2D screen representation that supports sub-region cropping
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Frame:
    """A minimal, hashable 2D screen representation.

    ``pixels`` is a tuple of rows, each row a tuple of hashable "pixel" values
    (any hashable token works — ints, chars, colors). Being frozen and built
    from tuples, a ``Frame`` is hashable and value-comparable, which is exactly
    what region-diff comparison (``pre == post``) and predicate evaluation
    need.

    A ``Frame`` is optional: ``FakeScreen`` happily returns plain scripted
    values (strings/dicts/ints) too. Use ``Frame`` only when a test wants real
    sub-region cropping via :meth:`crop`.
    """

    pixels: Tuple[Tuple[Hashable, ...], ...]

    @classmethod
    def of(cls, rows: Sequence[Sequence[Hashable]]) -> "Frame":
        """Build a ``Frame`` from any sequence-of-sequences."""

        return cls(tuple(tuple(row) for row in rows))

    @property
    def width(self) -> int:
        return len(self.pixels[0]) if self.pixels else 0

    @property
    def height(self) -> int:
        return len(self.pixels)

    def crop(self, region: RegionArg) -> "Frame":
        """Return the sub-frame bounded by ``region``.

        ``FULL_SCREEN`` (or anything that is not a bounded :class:`Region`)
        returns the frame unchanged. Out-of-bounds coordinates are clamped by
        normal Python slicing semantics, so cropping never raises.
        """

        if not isinstance(region, Region):
            return self
        rows = self.pixels[region.y : region.y + region.height]
        cropped = tuple(row[region.x : region.x + region.width] for row in rows)
        return Frame(cropped)


# ---------------------------------------------------------------------------
# Value / record types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImageMatchResult:
    """The scripted outcome of an image-match attempt.

    ``confidence`` is the scripted Confidence_Score in ``[0.0, 1.0]``; ``point``
    is the (optional) located screen point the matcher would report.
    """

    confidence: float
    point: Optional[Tuple[int, int]] = None


@dataclass(frozen=True)
class CaptureCall:
    """A single recorded :meth:`FakeScreen.capture` call."""

    index: int
    region: object
    frame: object


@dataclass(frozen=True)
class FocusOp:
    """A single recorded focus operation (``has_focus`` or ``set_focus``)."""

    op: str
    window: object
    result: Optional[bool] = None


@dataclass(frozen=True)
class ImageMatchCall:
    """A single recorded :meth:`FakeImageMatcher.match` call."""

    index: int
    reference: object
    region: object
    result: ImageMatchResult


@dataclass(frozen=True)
class OcrCall:
    """A single recorded :meth:`FakeOcrProvider.read` call."""

    index: int
    region: object
    text: str


# ---------------------------------------------------------------------------
# FakeClock — controllable virtual time, no real sleeping
# ---------------------------------------------------------------------------


class FakeClock:
    """A controllable monotonic clock that never really sleeps.

    The clock exposes the small surface the helpers need:

    - :meth:`now` — current virtual time in **seconds** (monotonic float).
    - :meth:`sleep` — advance virtual time by ``seconds`` (no real delay) and
      record the sleep so tests can assert backoff behavior.
    - :meth:`advance` — advance virtual time without recording a "sleep"
      (useful to model external time passing, e.g. a slow post-capture).

    It can drive both polling loops and backoff:

    - **Verify timeout** (default 10s): a polling loop reads :meth:`now`,
      compares against a deadline, and calls :meth:`sleep` between polls; the
      virtual clock crosses the deadline deterministically.
    - **Backoff schedule** ``delay(attempt) = 500ms * 2^(attempt-1)`` →
      ``0.5s, 1.0s, 2.0s`` is realized purely by :meth:`sleep` advancing the
      virtual clock.

    All sleeps are recorded in :attr:`sleeps` (in order) and summed in
    :attr:`total_slept`, so a test can assert the exact backoff sequence.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._time: float = float(start)
        #: Ordered list of every ``sleep`` duration (seconds) requested.
        self.sleeps: List[float] = []

    # -- reads ---------------------------------------------------------------

    def now(self) -> float:
        """Return the current virtual time in seconds."""

        return self._time

    @property
    def sleep_calls(self) -> int:
        """Number of :meth:`sleep` calls made so far."""

        return len(self.sleeps)

    @property
    def total_slept(self) -> float:
        """Total virtual time (seconds) consumed by :meth:`sleep` calls."""

        return sum(self.sleeps)

    # -- advancement ---------------------------------------------------------

    def sleep(self, seconds: float) -> None:
        """Advance virtual time by ``seconds`` and record the sleep.

        Negative durations are rejected so a buggy backoff calculation cannot
        silently move the clock backwards.
        """

        if seconds < 0:
            raise ValueError(f"sleep() requires a non-negative duration, got {seconds!r}")
        self.sleeps.append(float(seconds))
        self._time += float(seconds)

    def sleep_ms(self, milliseconds: float) -> None:
        """Convenience wrapper to sleep using a millisecond duration."""

        self.sleep(milliseconds / 1000.0)

    def advance(self, seconds: float) -> None:
        """Advance virtual time by ``seconds`` **without** recording a sleep.

        Use this to simulate time elapsing outside the helper's own backoff
        (for example, a post-capture that takes longer than the 2000 ms
        target, exercising R1.3).
        """

        if seconds < 0:
            raise ValueError(f"advance() requires a non-negative duration, got {seconds!r}")
        self._time += float(seconds)

    def reset(self, start: float = 0.0) -> None:
        """Reset the clock and clear the recorded sleeps."""

        self._time = float(start)
        self.sleeps.clear()


# ---------------------------------------------------------------------------
# FakeScreen — scripted screen-capture source
# ---------------------------------------------------------------------------


class FakeScreen:
    """A deterministic screen-capture source returning scripted frames.

    Each call to :meth:`capture` returns the next scripted frame, modeling
    state changes between pre/post captures and across retry attempts. A
    "frame" is any value sufficient for region-diff comparison and predicate
    evaluation — a :class:`Frame`, a string, a dict, an int, etc. When a frame
    is a :class:`Frame` and a bounded :class:`Region` is requested, the frame
    is cropped to that sub-region; for any other frame type the region is
    recorded but the scripted value is returned unchanged.

    Scripting options (most → least specific):

    - ``frames=[...]``: an ordered sequence consumed one-per-:meth:`capture`.
    - ``default``: returned once the scripted sequence is exhausted; if no
      default is configured, exhausting the script raises ``IndexError`` so a
      test never silently captures an unintended frame.

    Frames can also be appended after construction with :meth:`script` /
    :meth:`script_many`, which is handy for building a sequence incrementally.

    Every capture is recorded in :attr:`calls` (a list of :class:`CaptureCall`)
    so tests can assert the count, order, and requested regions — for example
    that ``locate_with_fallback`` captured a *fresh* frame on every attempt
    (R9.1).
    """

    def __init__(
        self,
        frames: Optional[Sequence[object]] = None,
        *,
        default: object = _UNSET,
    ) -> None:
        self._frames: List[object] = list(frames) if frames is not None else []
        self._cursor: int = 0
        self._default: object = default
        #: Ordered record of every capture (region requested + frame returned).
        self.calls: List[CaptureCall] = []

    # -- scripting -----------------------------------------------------------

    def script(self, frame: object) -> "FakeScreen":
        """Append a single frame to the scripted sequence (returns self)."""

        self._frames.append(frame)
        return self

    def script_many(self, frames: Sequence[object]) -> "FakeScreen":
        """Append several frames to the scripted sequence (returns self)."""

        self._frames.extend(frames)
        return self

    def set_default(self, frame: object) -> "FakeScreen":
        """Set the frame returned after the scripted sequence is exhausted."""

        self._default = frame
        return self

    # -- capture -------------------------------------------------------------

    def capture(self, region: RegionArg = FULL_SCREEN) -> object:
        """Return the next scripted frame, cropped to ``region`` when possible.

        Raises ``IndexError`` when the script is exhausted and no ``default``
        was configured — surfacing an under-scripted test rather than hiding
        it.
        """

        if self._cursor < len(self._frames):
            frame = self._frames[self._cursor]
            self._cursor += 1
        elif self._default is not _UNSET:
            frame = self._default
        else:
            raise IndexError(
                "FakeScreen capture script exhausted: "
                f"{len(self._frames)} frame(s) scripted, "
                f"call #{len(self.calls) + 1} has no frame and no default."
            )

        result = frame.crop(region) if isinstance(frame, Frame) else frame
        self.calls.append(CaptureCall(index=len(self.calls), region=region, frame=result))
        return result

    # -- queries -------------------------------------------------------------

    @property
    def capture_count(self) -> int:
        """Total number of :meth:`capture` calls made."""

        return len(self.calls)

    @property
    def requested_regions(self) -> List[object]:
        """The regions requested, in capture order."""

        return [call.region for call in self.calls]

    @property
    def captured_frames(self) -> List[object]:
        """The frames returned, in capture order."""

        return [call.frame for call in self.calls]

    def reset(self) -> None:
        """Rewind the script cursor and clear the recorded calls."""

        self._cursor = 0
        self.calls.clear()


# ---------------------------------------------------------------------------
# FakeFocusManager — tracks window focus state
# ---------------------------------------------------------------------------


class FakeFocusManager:
    """A fake window-focus manager that tracks focus state per window.

    Models the Window Manager dependency (R11.1/R11.2): the verified-interaction
    routine must confirm focus *before* every action and acquire it when the
    target window does not already hold it.

    - :meth:`has_focus` — report whether ``window`` currently holds focus
      (recorded as a ``"has_focus"`` op).
    - :meth:`set_focus` — make ``window`` the focused window (recorded as a
      ``"set_focus"`` op). Focusing one window implicitly unfocuses others, so
      at most one window is focused at a time.
    - :meth:`ensure_focus` — convenience that checks focus and acquires it only
      when missing, returning ``True`` when a focus change was required.

    The ordered :attr:`operations` log lets tests assert that a focus
    confirmation preceded the action, and :attr:`focus_changes` counts how many
    times focus was actually acquired.

    Windows are compared by value when hashable; unhashable window references
    fall back to identity comparison, so any ``WindowRef``-like object works.
    """

    def __init__(self, focused: object = _UNSET) -> None:
        # The currently-focused window key, or _UNSET when nothing holds focus.
        self._focused: object = self._key(focused) if focused is not _UNSET else _UNSET
        #: Ordered log of focus operations (confirmations and acquisitions).
        self.operations: List[FocusOp] = []
        #: Number of times focus was actually acquired via set_focus.
        self.focus_changes: int = 0

    @staticmethod
    def _key(window: object) -> object:
        """Return a comparison key: the window itself if hashable, else its id."""

        try:
            hash(window)
        except TypeError:
            return id(window)
        return window

    def has_focus(self, window: object) -> bool:
        """Return whether ``window`` currently holds input focus (recorded)."""

        result = self._focused is not _UNSET and self._focused == self._key(window)
        self.operations.append(FocusOp(op="has_focus", window=window, result=result))
        return result

    def set_focus(self, window: object) -> None:
        """Give ``window`` input focus, unfocusing any other window (recorded)."""

        self._focused = self._key(window)
        self.focus_changes += 1
        self.operations.append(FocusOp(op="set_focus", window=window, result=True))

    def ensure_focus(self, window: object) -> bool:
        """Confirm focus and acquire it only if missing.

        Returns ``True`` when focus had to be acquired (the window was not
        already focused), ``False`` when it already held focus. Mirrors the
        ``ensure_window_focus`` contract used by the interaction routine.
        """

        if self.has_focus(window):
            return False
        self.set_focus(window)
        return True

    # -- queries -------------------------------------------------------------

    @property
    def focused(self) -> object:
        """The currently-focused window, or ``None`` when nothing holds focus."""

        return None if self._focused is _UNSET else self._focused

    @property
    def op_sequence(self) -> List[str]:
        """The ordered op names (e.g. ``["has_focus", "set_focus"]``)."""

        return [op.op for op in self.operations]

    def reset(self, focused: object = _UNSET) -> None:
        """Reset focus state and clear the operations log."""

        self._focused = self._key(focused) if focused is not _UNSET else _UNSET
        self.operations.clear()
        self.focus_changes = 0


# ---------------------------------------------------------------------------
# FakeImageMatcher — scripted image-match confidence scores
# ---------------------------------------------------------------------------


def _ref_key(reference: object) -> object:
    """Derive a stable scripting key from an image reference.

    An :class:`ImageRef` keys on its ``path`` (the stable identity of a
    reference capture); any other hashable reference keys on itself; an
    unhashable reference keys on its ``id``.
    """

    if isinstance(reference, ImageRef):
        return reference.path
    try:
        hash(reference)
    except TypeError:
        return id(reference)
    return reference


class FakeImageMatcher:
    """Returns scripted image-match confidence scores for reference/frame pairs.

    The matcher does no real pixel comparison; it returns scripted
    :class:`ImageMatchResult` values so the locator's threshold gating (R6) and
    ranked-order selection (R5) can be tested deterministically.

    Three scripting modes, resolved in priority order on each :meth:`match`:

    1. **Per-reference queue** (``per_reference={ref_key: [results...]}``):
       results keyed by reference identity (an :class:`ImageRef` keys on its
       ``path``), consumed one per matching call. Best when different targets
       must score differently.
    2. **Global sequence** (``sequence=[results...]``): consumed one per call
       regardless of reference. Best for modeling a rising confidence across
       retry attempts.
    3. **Default** (``default``): returned when nothing else is scripted.

    Results may be given as a bare ``float`` (confidence only) or an
    :class:`ImageMatchResult` (confidence + point); floats are coerced. Every
    call is recorded in :attr:`calls`.
    """

    def __init__(
        self,
        sequence: Optional[Sequence[Union[float, ImageMatchResult]]] = None,
        *,
        per_reference: Optional[dict] = None,
        default: Union[float, ImageMatchResult] = 0.0,
    ) -> None:
        self._sequence: List[ImageMatchResult] = (
            [self._coerce(r) for r in sequence] if sequence is not None else []
        )
        self._seq_cursor: int = 0
        self._per_reference: dict = {}
        if per_reference:
            for key, results in per_reference.items():
                self._per_reference[key] = [self._coerce(r) for r in results]
        self._per_reference_cursor: dict = {k: 0 for k in self._per_reference}
        self._default: ImageMatchResult = self._coerce(default)
        #: Ordered record of every match call.
        self.calls: List[ImageMatchCall] = []

    @staticmethod
    def _coerce(result: Union[float, ImageMatchResult]) -> ImageMatchResult:
        if isinstance(result, ImageMatchResult):
            return result
        return ImageMatchResult(confidence=float(result))

    def script_reference(
        self, reference: object, results: Sequence[Union[float, ImageMatchResult]]
    ) -> "FakeImageMatcher":
        """Queue per-reference results for ``reference`` (returns self)."""

        key = _ref_key(reference)
        self._per_reference.setdefault(key, [])
        self._per_reference[key].extend(self._coerce(r) for r in results)
        self._per_reference_cursor.setdefault(key, 0)
        return self

    def match(self, reference: object, region: RegionArg = FULL_SCREEN) -> ImageMatchResult:
        """Return the scripted match result for ``reference`` (recorded)."""

        key = _ref_key(reference)
        cursor = self._per_reference_cursor.get(key, 0)
        queue = self._per_reference.get(key)
        if queue is not None and cursor < len(queue):
            result = queue[cursor]
            self._per_reference_cursor[key] = cursor + 1
        elif self._seq_cursor < len(self._sequence):
            result = self._sequence[self._seq_cursor]
            self._seq_cursor += 1
        else:
            result = self._default

        self.calls.append(
            ImageMatchCall(
                index=len(self.calls), reference=reference, region=region, result=result
            )
        )
        return result

    @property
    def call_count(self) -> int:
        """Total number of :meth:`match` calls made."""

        return len(self.calls)

    def reset(self) -> None:
        """Rewind all cursors and clear the recorded calls."""

        self._seq_cursor = 0
        self._per_reference_cursor = {k: 0 for k in self._per_reference}
        self.calls.clear()


# ---------------------------------------------------------------------------
# FakeOcrProvider — scripted recognized text
# ---------------------------------------------------------------------------


class FakeOcrProvider:
    """Returns scripted recognized text for a captured region.

    Stands in for real OCR so the locator's OCR_TEXT strategy and its
    case/whitespace normalization (R6.4/R6.5) can be tested deterministically.
    Scripting mirrors :class:`FakeImageMatcher`:

    1. **Per-region queue** (``per_region={region: [text...]}``): text keyed by
       the requested region, consumed one per matching call.
    2. **Global sequence** (``sequence=[text...]``): consumed one per call.
    3. **Default** (``default``): returned when nothing else is scripted
       (defaults to the empty string, modeling "no text recognized").

    Regions used as keys must be hashable; the frozen :class:`Region` and the
    ``FULL_SCREEN`` sentinel both are. Every call is recorded in :attr:`calls`.
    """

    def __init__(
        self,
        sequence: Optional[Sequence[str]] = None,
        *,
        per_region: Optional[dict] = None,
        default: str = "",
    ) -> None:
        self._sequence: List[str] = list(sequence) if sequence is not None else []
        self._seq_cursor: int = 0
        self._per_region: dict = {}
        if per_region:
            for key, texts in per_region.items():
                self._per_region[key] = list(texts)
        self._per_region_cursor: dict = {k: 0 for k in self._per_region}
        self._default: str = default
        #: Ordered record of every read call.
        self.calls: List[OcrCall] = []

    def script_region(self, region: RegionArg, texts: Sequence[str]) -> "FakeOcrProvider":
        """Queue per-region recognized text for ``region`` (returns self)."""

        self._per_region.setdefault(region, [])
        self._per_region[region].extend(texts)
        self._per_region_cursor.setdefault(region, 0)
        return self

    def read(self, region: RegionArg = FULL_SCREEN) -> str:
        """Return the scripted recognized text for ``region`` (recorded)."""

        cursor = self._per_region_cursor.get(region, 0)
        queue = self._per_region.get(region)
        if queue is not None and cursor < len(queue):
            text = queue[cursor]
            self._per_region_cursor[region] = cursor + 1
        elif self._seq_cursor < len(self._sequence):
            text = self._sequence[self._seq_cursor]
            self._seq_cursor += 1
        else:
            text = self._default

        self.calls.append(OcrCall(index=len(self.calls), region=region, text=text))
        return text

    @property
    def call_count(self) -> int:
        """Total number of :meth:`read` calls made."""

        return len(self.calls)

    def reset(self) -> None:
        """Rewind all cursors and clear the recorded calls."""

        self._seq_cursor = 0
        self._per_region_cursor = {k: 0 for k in self._per_region}
        self.calls.clear()
