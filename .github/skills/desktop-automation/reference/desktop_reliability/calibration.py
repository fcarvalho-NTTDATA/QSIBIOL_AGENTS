"""Multi-monitor coordinate consistency and click-offset calibration (R16).

This module implements **Requirement 16** — the piece that makes desktop
automation reliable on **multi-monitor** setups (and a no-op identity on single
monitors). It addresses the failure mode where the agent *reads* an element at
one coordinate (via ``screen_capture``) but the *commanded* click
(``mouse_click``) lands somewhere else, because the capture plane and the click
plane diverge by a constant vector on the Virtual_Desktop.

The fix is a measured, self-correcting **Click_Offset**:

1. At session start the per-monitor geometry of the Virtual_Desktop is captured
   (origins — which may be negative or large-positive — widths, heights,
   per-monitor scaling factors, and which monitor is primary). See
   :class:`~desktop_reliability.models.Monitor` and
   :class:`~desktop_reliability.models.SessionEnvironment` (R16.1).
2. When a Calibration or verification interaction completes, the divergence
   between where the element was *read* and where the interaction was
   *commanded* is measured as ``observed_point - commanded_point`` from the
   Post_Action_State (:func:`measure_divergence`, R16.3/R16.9).
3. A divergence reproduced across at least two measurements, whose horizontal
   and vertical components each agree within a configurable tolerance (default
   **2 px**), is classified **stable** (:func:`offset_is_stable`, R16.4);
   otherwise it is **unstable** (R16.5).
4. A stable offset is applied to every subsequently resolved interaction point
   (:meth:`~desktop_reliability.models.ClickOffset.apply` /
   :func:`resolve_interaction_point`, R16.6/R16.10). A single-monitor desktop
   yields the **zero** offset identity so resolved points are unchanged
   (R16.12).

Monitor reasoning:

- A window whose origin falls outside the primary monitor's bounds is treated
  as residing on a non-primary monitor (:func:`is_on_non_primary_monitor`,
  R16.7), which triggers a one-time Calibration (R16.8) and offset application
  (R16.10).
- A window that moves to a different monitor forces re-calibration
  (:func:`requires_recalibration`, R16.11).
- If the per-monitor scaling factor differs between the monitor the element is
  *read* on and the monitor the interaction is *commanded* on, the situation is
  classified ``user_input_needed`` and the interaction must NOT proceed with an
  uncorrected coordinate (:func:`scaling_conflict`, R16.14).

While the offset is unknown or unstable, the Element_Locator should prefer
anchor-relative (R7) and window-relative (R11) localization over absolute
coordinates, because a point computed from an element *within the same captured
frame* cancels a constant capture-versus-click offset (R16.13). The ranked
``STRATEGY_ORDER`` already places those strategies above ``ABSOLUTE``, so this
preference is structural; :func:`prefer_relative_localization` exposes the
predicate for callers/generated code that want to assert it explicitly.

Everything here is **logic only** — no real desktop, screen, clock, or OS calls.
The same model the deterministic tests exercise is what generated desktop
projects mirror as their reusable Calibration helper and offset-correcting
interaction-point resolver (R16.16/R16.17).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .models import ClickOffset, Monitor, SessionEnvironment

__all__ = [
    "DEFAULT_OFFSET_TOLERANCE_PX",
    "MIN_STABLE_MEASUREMENTS",
    "Point",
    "measure_divergence",
    "vectors_agree",
    "offset_is_stable",
    "representative_offset",
    "resolve_click_offset",
    "resolve_interaction_point",
    "window_monitor",
    "is_on_non_primary_monitor",
    "requires_recalibration",
    "scaling_conflict",
    "prefer_relative_localization",
    "Calibrator",
]


Point = Tuple[int, int]

#: Default per-component agreement tolerance for offset stability (R16.4).
DEFAULT_OFFSET_TOLERANCE_PX: int = 2

#: Minimum number of agreeing measurements required to classify an offset as
#: stable (R16.4 "reproduced across at least two measurements").
MIN_STABLE_MEASUREMENTS: int = 2


# ---------------------------------------------------------------------------
# Divergence measurement (R16.3 / R16.9)
# ---------------------------------------------------------------------------


def measure_divergence(observed: Point, commanded: Point) -> Point:
    """Measure the capture-vs-click divergence as ``observed - commanded`` (R16.3/R16.9).

    ``observed`` is the point where the resulting state change actually occurred,
    read from the Post_Action_State; ``commanded`` is the point the interaction
    was issued at. The returned vector is the correction that, added to a
    commanded point, reproduces the observed point — i.e. the Click_Offset
    contributed by this single measurement.
    """

    return (observed[0] - commanded[0], observed[1] - commanded[1])


def vectors_agree(a: Point, b: Point, tolerance: int = DEFAULT_OFFSET_TOLERANCE_PX) -> bool:
    """Whether two divergence vectors agree within ``tolerance`` per component (R16.4).

    Agreement is component-wise: the horizontal components must differ by no
    more than ``tolerance`` **and** the vertical components must differ by no
    more than ``tolerance``. A negative tolerance is treated as ``0`` (exact
    agreement), so a malformed tolerance can never widen the band.
    """

    tol = max(0, tolerance)
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


# ---------------------------------------------------------------------------
# Stability classification (R16.4 / R16.5)
# ---------------------------------------------------------------------------


def offset_is_stable(
    measurements: Sequence[Point],
    tolerance: int = DEFAULT_OFFSET_TOLERANCE_PX,
) -> bool:
    """Classify a sequence of divergence measurements as stable (R16.4/R16.5).

    Returns ``True`` (stable) only when the offset is **reproduced across at
    least two measurements** whose horizontal and vertical components each agree
    within ``tolerance`` (R16.4). Returns ``False`` (unstable) when fewer than
    two measurements exist, or when any measurement diverges from another by
    more than the tolerance (R16.5).

    Agreement is evaluated as the spread (max − min) of each component across
    all measurements: stable iff both component spreads are within ``tolerance``.
    This is equivalent to requiring every pair to agree, and is order- and
    representative-independent.
    """

    if len(measurements) < MIN_STABLE_MEASUREMENTS:
        return False  # R16.5: fewer than two measurements -> unstable.
    tol = max(0, tolerance)
    xs = [m[0] for m in measurements]
    ys = [m[1] for m in measurements]
    return (max(xs) - min(xs)) <= tol and (max(ys) - min(ys)) <= tol


def representative_offset(measurements: Sequence[Point]) -> Point:
    """The single offset vector that represents a set of agreeing measurements.

    Uses the **most recent** measurement as the representative Click_Offset
    (R16.6 "treat the measured divergence as the Click_Offset"). When the
    measurements are stable they all agree within tolerance, so the most recent
    one is a faithful representative and tracks the latest observation. Raises
    ``ValueError`` for an empty sequence (there is nothing to represent).
    """

    if not measurements:
        raise ValueError("representative_offset requires at least one measurement")
    return measurements[-1]


def resolve_click_offset(
    measurements: Sequence[Point],
    *,
    monitor: Optional[Monitor] = None,
    tolerance: int = DEFAULT_OFFSET_TOLERANCE_PX,
    single_monitor: bool = False,
) -> ClickOffset:
    """Resolve accumulated measurements into a :class:`ClickOffset` (R16.4–R16.6/R16.12).

    - **Single monitor (R16.12):** when ``single_monitor`` is true the
      Virtual_Desktop is one coordinate plane, so the offset is the **zero
      identity** (stable, zero vector) regardless of any measurements — applying
      it leaves resolved points unchanged.
    - **Stable (R16.4/R16.6):** when the measurements are stable, the offset
      carries the :func:`representative_offset` vector and ``stable=True`` so it
      will be applied to subsequently resolved points.
    - **Unstable (R16.5/R16.13):** otherwise the offset is ``stable=False`` with
      a zero vector; it must not be applied (the caller prefers relative
      localization instead).
    """

    if single_monitor:
        return ClickOffset.zero(monitor=monitor)  # R16.12
    if offset_is_stable(measurements, tolerance):
        return ClickOffset(
            vector=representative_offset(measurements),
            stable=True,
            monitor=monitor,
        )  # R16.4/R16.6
    return ClickOffset(vector=(0, 0), stable=False, monitor=monitor)  # R16.5


def resolve_interaction_point(
    point: Point,
    click_offset: Optional[ClickOffset],
) -> Point:
    """Correct a resolved interaction ``point`` by the Click_Offset (R16.6/R16.10/R16.13).

    This is the **offset-correcting interaction-point resolver** every commanded
    interaction routes its point through (R16.16/R16.17). When ``click_offset``
    is a *stable* offset its vector is added to the point (R16.6/R16.10); when it
    is ``None`` or unstable the point is returned unchanged (R16.13) — an
    unstable/unknown offset is never applied as a guess.
    """

    if click_offset is None:
        return point
    return click_offset.apply(point)


# ---------------------------------------------------------------------------
# Monitor reasoning (R16.7 / R16.11)
# ---------------------------------------------------------------------------


def window_monitor(
    session: SessionEnvironment,
    window_origin: Optional[Point],
) -> Optional[Monitor]:
    """Return the monitor a window origin resides on (R16.7/R16.11).

    Delegates to :meth:`SessionEnvironment.monitor_for_point`. Returns ``None``
    when the origin is unknown or falls on no captured monitor.
    """

    if window_origin is None:
        return None
    return session.monitor_for_point(window_origin)


def is_on_non_primary_monitor(
    session: SessionEnvironment,
    window_origin: Optional[Point],
) -> bool:
    """Whether a window origin lies outside the primary monitor's bounds (R16.7).

    Returns ``True`` when a primary monitor is known and the window origin does
    **not** fall within it — i.e. the window resides on a non-primary monitor of
    the Virtual_Desktop, which triggers one-time Calibration (R16.8). Returns
    ``False`` on a single-monitor desktop, when the origin is unknown, or when no
    primary monitor was captured (nothing to be non-primary relative to).
    """

    if window_origin is None or session.is_single_monitor:
        return False
    primary = session.primary_monitor
    if primary is None:
        return False
    return not primary.contains(window_origin)


def requires_recalibration(
    previous_monitor: Optional[Monitor],
    current_monitor: Optional[Monitor],
) -> bool:
    """Whether the window moved to a different monitor since calibration (R16.11).

    Returns ``True`` when both monitors are known and differ — the target window
    moved to a different monitor of the Virtual_Desktop, so the Click_Offset must
    be re-calibrated before further interactions. Returns ``False`` when the
    monitor is unchanged, or when either monitor is unknown (no basis to force a
    re-calibration).
    """

    if previous_monitor is None or current_monitor is None:
        return False
    return previous_monitor != current_monitor


# ---------------------------------------------------------------------------
# Scaling-conflict guard (R16.14)
# ---------------------------------------------------------------------------


def scaling_conflict(
    read_monitor: Optional[Monitor],
    command_monitor: Optional[Monitor],
) -> bool:
    """Whether read and command monitors have different per-monitor scaling (R16.14).

    Returns ``True`` when both monitors are known and their per-monitor scaling
    factors differ — a mixed-DPI situation a single constant Click_Offset cannot
    correct. The caller must classify this ``user_input_needed`` (consistent with
    R12) and must NOT perform the interaction with an uncorrected coordinate.
    Returns ``False`` when the scaling matches or a monitor is unknown.
    """

    if read_monitor is None or command_monitor is None:
        return False
    return read_monitor.scaling_factor != command_monitor.scaling_factor


def prefer_relative_localization(click_offset: Optional[ClickOffset]) -> bool:
    """Whether relative localization should be preferred over absolute (R16.13).

    Returns ``True`` while the Click_Offset is unknown (``None``) or unstable,
    because a point computed from an element within the same captured frame
    (anchor-relative R7, window-relative R11) cancels a constant
    capture-versus-click offset, whereas an absolute coordinate does not. Returns
    ``False`` once a stable offset is known (absolute coordinates can then be
    corrected safely).
    """

    return click_offset is None or not click_offset.stable


# ---------------------------------------------------------------------------
# Calibrator — accumulates measurements and produces a Click_Offset
# ---------------------------------------------------------------------------


@dataclass
class Calibrator:
    """Accumulates divergence measurements and resolves the Click_Offset (R16).

    This is the reusable **Calibration helper** generated desktop projects
    mirror (R16.16). It ties the module functions together for the
    verified-interaction routine and for generated code:

    - :meth:`record` adds a measurement from an ``(observed, commanded)`` pair
      (R16.3/R16.9), keyed to the monitor it was taken on.
    - :meth:`offset` resolves the accumulated measurements into a
      :class:`ClickOffset` — the zero identity on a single monitor (R16.12), a
      stable vector once reproduced within tolerance (R16.4/R16.6), or an
      unstable zero otherwise (R16.5).
    - :meth:`note_monitor` / :meth:`requires_recalibration` track the active
      monitor so a window moving to a different monitor forces re-calibration
      and clears stale measurements (R16.11).

    ``single_monitor`` short-circuits everything to the zero identity so the same
    helper is correct on single-monitor setups without any calibration round
    trip.
    """

    tolerance: int = DEFAULT_OFFSET_TOLERANCE_PX
    single_monitor: bool = False
    monitor: Optional[Monitor] = None
    measurements: List[Point] = field(default_factory=list)

    def record(self, observed: Point, commanded: Point) -> Point:
        """Record one divergence measurement and return it (R16.3/R16.9)."""

        divergence = measure_divergence(observed, commanded)
        self.measurements.append(divergence)
        return divergence

    def note_monitor(self, monitor: Optional[Monitor]) -> bool:
        """Update the active monitor, clearing measurements on a move (R16.11).

        Returns ``True`` when the monitor changed (a re-calibration is required
        and the stale measurements were cleared), ``False`` otherwise.
        """

        if requires_recalibration(self.monitor, monitor):
            self.measurements.clear()
            self.monitor = monitor
            return True
        if self.monitor is None:
            self.monitor = monitor
        return False

    def requires_recalibration(self, current_monitor: Optional[Monitor]) -> bool:
        """Whether ``current_monitor`` differs from the calibrated monitor (R16.11)."""

        return requires_recalibration(self.monitor, current_monitor)

    @property
    def is_stable(self) -> bool:
        """Whether the accumulated measurements are stable (R16.4/R16.5/R16.12)."""

        if self.single_monitor:
            return True
        return offset_is_stable(self.measurements, self.tolerance)

    def offset(self) -> ClickOffset:
        """Resolve the accumulated measurements into a :class:`ClickOffset` (R16)."""

        return resolve_click_offset(
            self.measurements,
            monitor=self.monitor,
            tolerance=self.tolerance,
            single_monitor=self.single_monitor,
        )

    def correct(self, point: Point) -> Point:
        """Correct ``point`` by the current offset, only when stable (R16.6/R16.13)."""

        return resolve_interaction_point(point, self.offset())
