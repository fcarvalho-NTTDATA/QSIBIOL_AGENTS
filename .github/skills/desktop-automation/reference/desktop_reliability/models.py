"""Core data models and configuration for the desktop-reliability pattern.

These models are the conceptual structures the behavioral helpers operate on
(see ``desktop-automation/SKILL.md`` and the design "Data Models" section). In
generated desktop projects they become dataclasses/dicts; here they are the
canonical, importable reference shapes.

This module contains *data models only* — no business logic. The locator,
verifier, interaction, failure, and flow behavior live in their own modules and
are added by later tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Tuple

__all__ = [
    # Enums
    "Action",
    "LocalizationStrategy",
    "Verdict",
    "FinalStatus",
    "FailureCategory",
    "FlowStatus",
    # Geometry / references
    "Region",
    "FULL_SCREEN",
    "WindowRef",
    "ImageRef",
    "Monitor",
    # Models
    "TargetElement",
    "ExpectedOutcome",
    "InteractionStep",
    "LocalizationResult",
    "InteractionRecord",
    "SessionEnvironment",
    "ClickOffset",
    "FlowResult",
    # Config
    "ReliabilityConfig",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Action(str, Enum):
    """The interaction performed against a target element."""

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    PRESS = "press"


class LocalizationStrategy(str, Enum):
    """Ranked localization strategies, most to least stable.

    The fixed traversal order is defined in ``locator.STRATEGY_ORDER`` and
    matches this declaration order (R5.1).
    """

    IMAGE_MATCH = "image_match"
    OCR_TEXT = "ocr_text"
    ANCHOR_RELATIVE = "anchor_relative"
    ROI_CONSTRAINED = "roi_constrained"
    WINDOW_RELATIVE = "window_relative"
    ABSOLUTE = "absolute"


class Verdict(str, Enum):
    """The outcome of post-action verification (R2/R3)."""

    CONFIRMED = "confirmed"
    NO_OP_CLICK = "no_op_click"
    WRONG_TARGET_CLICK = "wrong_target_click"


class FinalStatus(str, Enum):
    """Terminal status of a single interaction."""

    SUCCESS = "success"
    FAILED = "failed"


class FailureCategory(str, Enum):
    """The three existing error-classification categories (R12.3)."""

    CODE_ISSUE = "code_issue"
    SYSTEM_BUG = "system_bug"
    USER_INPUT_NEEDED = "user_input_needed"


class FlowStatus(str, Enum):
    """Aggregate status of a flow of interactions (R13.2)."""

    PASSED = "passed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Geometry and references
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Region:
    """A bounded rectangular screen area.

    Coordinates are in pixels with the origin at the top-left of the screen.
    """

    x: int
    y: int
    width: int
    height: int


class _FullScreenSentinel:
    """Sentinel type denoting the entire screen rather than a bounded region.

    A dedicated type (rather than ``None``) lets a verification/search target
    explicitly mean "the full screen", distinct from "unspecified".
    """

    _instance: Optional["_FullScreenSentinel"] = None

    def __new__(cls) -> "_FullScreenSentinel":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "FULL_SCREEN"

    def __reduce__(self):  # pragma: no cover - pickling support
        return (_full_screen, ())


def _full_screen() -> "_FullScreenSentinel":
    return FULL_SCREEN


#: Singleton sentinel meaning "the entire screen" for region-typed fields.
FULL_SCREEN: _FullScreenSentinel = _FullScreenSentinel()


@dataclass(frozen=True)
class WindowRef:
    """A reference to a target window.

    Any of the identifying attributes may be provided; ``origin`` is the
    window's top-left position when known (used for window-relative
    coordinates, R11.3).
    """

    id: Optional[int] = None
    title: Optional[str] = None
    origin: Optional[Tuple[int, int]] = None


@dataclass(frozen=True)
class ImageRef:
    """A reference capture used for image matching.

    ``path`` points to a stored reference image; ``name`` is an optional
    human-readable label.
    """

    path: str
    name: Optional[str] = None


@dataclass(frozen=True)
class Monitor:
    """The geometry of one connected monitor on the Virtual_Desktop (R16.1).

    A monitor occupies a rectangle on the unified multi-monitor coordinate
    plane. Its ``origin`` is the top-left corner **in virtual-desktop
    coordinates**, which may be negative or large-positive for non-primary
    monitors (e.g. a monitor placed to the left of the primary has a negative
    ``x``). ``scaling_factor`` is the *per-monitor* display scaling percentage
    (100, 125, 150, …); different monitors may scale differently. ``primary``
    marks the monitor the OS reports as primary — the one whose origin is the
    virtual-desktop origin ``(0, 0)`` on a standard layout.
    """

    origin: Tuple[int, int]
    width: int
    height: int
    scaling_factor: int = 100
    primary: bool = False

    def contains(self, point: Tuple[int, int]) -> bool:
        """Whether ``point`` falls within this monitor's bounds (half-open).

        A point on the left/top edge is inside; a point on the right/bottom
        edge is outside, so adjacent monitors partition the plane without
        overlap. Used to decide which monitor a window origin resides on
        (R16.7).
        """

        x, y = point
        ox, oy = self.origin
        return ox <= x < ox + self.width and oy <= y < oy + self.height


# ---------------------------------------------------------------------------
# Targeting models
# ---------------------------------------------------------------------------


@dataclass
class TargetElement:
    """Describes how to locate an on-screen element via ranked strategies.

    Each optional attribute feeds a specific localization strategy:

    - ``reference`` → IMAGE_MATCH
    - ``text`` → OCR_TEXT
    - ``anchor`` + ``offset`` → ANCHOR_RELATIVE
    - ``roi`` → ROI_CONSTRAINED (constrains the search area)
    - ``window`` + ``win_offset`` → WINDOW_RELATIVE
    - ``absolute`` → ABSOLUTE (last resort)
    """

    reference: Optional[ImageRef] = None
    text: Optional[str] = None
    anchor: Optional["TargetElement"] = None
    offset: Optional[Tuple[int, int]] = None
    roi: Optional[Region] = None
    window: Optional[WindowRef] = None
    win_offset: Optional[Tuple[int, int]] = None
    absolute: Optional[Tuple[int, int]] = None


@dataclass
class ExpectedOutcome:
    """An explicit, observable check that defines interaction success (R2.1).

    ``predicate`` receives the captured Post_Action_State and returns ``True``
    when the expected outcome holds. ``region`` is the verification region the
    predicate is evaluated against (a bounded ``Region`` or ``FULL_SCREEN``).
    """

    description: str
    predicate: Callable[[object], bool]
    region: "Region | _FullScreenSentinel" = FULL_SCREEN


@dataclass
class InteractionStep:
    """A single step in an interaction flow."""

    id: str
    target: TargetElement
    action: Action
    target_window: WindowRef
    verification_region: "Region | _FullScreenSentinel" = FULL_SCREEN


# ---------------------------------------------------------------------------
# Result / record models
# ---------------------------------------------------------------------------


@dataclass
class LocalizationResult:
    """The result of attempting to resolve a target to a screen point.

    Prefer the :meth:`located_at` / :meth:`not_located` factories over
    constructing instances directly.
    """

    located: bool
    point: Optional[Tuple[int, int]] = None
    strategy: Optional[LocalizationStrategy] = None
    confidence: Optional[float] = None

    @classmethod
    def located_at(
        cls,
        point: Tuple[int, int],
        strategy: LocalizationStrategy,
        confidence: float,
    ) -> "LocalizationResult":
        """Build a successful (located) result (R5.4 records the strategy)."""

        return cls(
            located=True,
            point=point,
            strategy=strategy,
            confidence=confidence,
        )

    @classmethod
    def not_located(cls) -> "LocalizationResult":
        """Build a failed (not-located) result (R9.4)."""

        return cls(located=False, point=None, strategy=None, confidence=None)


@dataclass
class InteractionRecord:
    """The accumulated record for a single interaction across its attempts."""

    step_id: str
    attempts: int = 0
    localization_strategy: Optional[LocalizationStrategy] = None
    confidence: Optional[float] = None
    verification: Optional[Verdict] = None
    pre_evidence: list[str] = field(default_factory=list)
    post_evidence: list[str] = field(default_factory=list)
    final_status: FinalStatus = FinalStatus.FAILED
    failure_category: Optional[FailureCategory] = None


@dataclass(frozen=True)
class SessionEnvironment:
    """Resolution and scaling captured at session start (R10.1, R16.1).

    ``scaling_factor`` and ``exploration_scaling`` are percentages
    (e.g. ``100``, ``125``, ``150``).

    ``monitors`` is the per-monitor geometry of the Virtual_Desktop captured at
    session start (R16.1): every connected monitor's origin (which may be
    negative or large-positive), width, height, per-monitor scaling factor, and
    primary flag. It defaults to empty for single-plane callers that do not
    supply monitor geometry; helpers treat an empty/single-monitor desktop as a
    zero-offset identity (R16.12).
    """

    resolution: Tuple[int, int]
    scaling_factor: int
    exploration_resolution: Tuple[int, int]
    exploration_scaling: int
    monitors: Tuple[Monitor, ...] = ()

    @property
    def is_single_monitor(self) -> bool:
        """Whether the Virtual_Desktop comprises at most one monitor (R16.12).

        A desktop with zero or one connected monitor is a single coordinate
        plane: Calibration and Click_Offset compensation must be the identity
        (zero offset) so resolved points are left unchanged.
        """

        return len(self.monitors) <= 1

    @property
    def primary_monitor(self) -> "Optional[Monitor]":
        """The monitor flagged primary, or the first monitor, or ``None``.

        Used to decide whether a window origin lies on the primary monitor or
        on a non-primary monitor of the Virtual_Desktop (R16.7).
        """

        for monitor in self.monitors:
            if monitor.primary:
                return monitor
        return self.monitors[0] if self.monitors else None

    def monitor_for_point(self, point: Tuple[int, int]) -> "Optional[Monitor]":
        """Return the monitor whose bounds contain ``point`` (R16.7/R16.11).

        Identifies which monitor of the Virtual_Desktop a window origin (or any
        point) resides on, so the system can detect when a target window is on a
        non-primary monitor (R16.7) or has moved to a different monitor
        (R16.11). Returns ``None`` when no monitor contains the point.
        """

        for monitor in self.monitors:
            if monitor.contains(point):
                return monitor
        return None


@dataclass(frozen=True)
class ClickOffset:
    """The measured capture-vs-click divergence for the current monitor (R16).

    On a multi-monitor Virtual_Desktop the plane an element is *read* in
    (``screen_capture``) and the plane an interaction is *commanded* in
    (``mouse_click``) can diverge by a constant vector. ``ClickOffset`` is that
    vector, measured as ``(observed_point - commanded_point)`` from the
    Post_Action_State during Calibration/verification (R16.3/R16.9).

    - ``vector`` — the ``(dx, dy)`` correction to add to a resolved point before
      commanding the interaction (R16.6/R16.10). The zero vector is the
      single-monitor / no-correction identity (R16.12).
    - ``stable`` — whether the offset has been confirmed stable: reproduced
      across at least two measurements agreeing within tolerance (R16.4). An
      unknown or unstable offset is ``stable=False`` (R16.5) and must not be
      applied as a correction (R16.13).
    - ``monitor`` — the monitor the offset was measured on, so a window moving
      to a different monitor forces re-calibration (R16.11).
    """

    vector: Tuple[int, int] = (0, 0)
    stable: bool = False
    monitor: Optional[Monitor] = None

    @classmethod
    def zero(cls, monitor: Optional["Monitor"] = None) -> "ClickOffset":
        """The zero-offset identity used on single-monitor desktops (R16.12).

        A zero vector that is treated as *stable* so that applying it leaves
        every resolved interaction point unchanged without ever blocking on
        calibration.
        """

        return cls(vector=(0, 0), stable=True, monitor=monitor)

    def apply(self, point: Tuple[int, int]) -> Tuple[int, int]:
        """Return ``point`` corrected by the offset, but only when stable (R16.6/R16.13).

        When the offset is stable the correction vector is added to the resolved
        point (R16.6/R16.10). While the offset is unknown or unstable the point
        is returned unchanged (R16.13) — the caller is responsible for
        preferring anchor/window-relative localization in that case.
        """

        if not self.stable:
            return point
        return (point[0] + self.vector[0], point[1] + self.vector[1])


@dataclass
class FlowResult:
    """The aggregate result of a flow of interactions."""

    steps: list[InteractionRecord] = field(default_factory=list)
    status: FlowStatus = FlowStatus.FAILED


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReliabilityConfig:
    """Tunable thresholds and budgets for the reliability routines.

    Defaults match the design constants so no governing document contradicts
    another.
    """

    confidence_threshold: float = 0.80  # R6.1
    verify_timeout_seconds: int = 10  # R2.5
    post_capture_target_ms: int = 2000  # R1.2
    max_locate_attempts: int = 3  # R9.2
    max_interaction_attempts: int = 3  # R12.1
    backoff_base_ms: int = 500  # R9.3
