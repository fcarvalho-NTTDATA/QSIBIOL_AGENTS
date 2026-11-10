"""Canonical desktop-reliability reference implementation.

This package is the canonical, executable pattern referenced by
``.github/skills/desktop-automation/SKILL.md``. It encodes the
behavioral helpers that generated desktop-automation projects must include:

- ``verified_interaction`` — pre-capture, interact, post-capture, verify
- ``locate_with_fallback`` — ranked localization with retry/backoff
- ``verify_and_classify`` — verdict classification (CONFIRMED / NO_OP_CLICK /
  WRONG_TARGET_CLICK)
- ``classify_failure`` — failure classification, escalation, and reporting
- flow status aggregation

The ``interaction`` module (``verified_interaction`` orchestration), the locator
primitives (``locator``), the action verifier (``verifier``), the evidence store
(``evidence``), the window manager (``window``), the failure handler
(``failure``), the deterministic test ``fakes`` (screen, clock, focus, image/OCR
matchers), and ``flow`` aggregation are all available now. This package is a
development-time-only validation aid; it is not a runtime dependency of the
agent or its deliverables.
"""

from __future__ import annotations

from .evidence import (
    EVIDENCE_DIRNAME,
    VALID_PHASES,
    evidence_path,
    sanitize_step_id,
    store_evidence,
)
from .calibration import (
    DEFAULT_OFFSET_TOLERANCE_PX,
    MIN_STABLE_MEASUREMENTS,
    Calibrator,
    is_on_non_primary_monitor,
    measure_divergence,
    offset_is_stable,
    prefer_relative_localization,
    representative_offset,
    requires_recalibration,
    resolve_click_offset,
    resolve_interaction_point,
    scaling_conflict,
    vectors_agree,
    window_monitor,
)
from .failure import (
    FailureReport,
    FailureSignal,
    FlowControl,
    classify_failure,
    escalate,
    report_failure,
    stop_current_flow,
)
from .fakes import (
    CaptureCall,
    FakeClock,
    FakeFocusManager,
    FakeImageMatcher,
    FakeOcrProvider,
    FakeScreen,
    FocusOp,
    Frame,
    ImageMatchCall,
    ImageMatchResult,
    OcrCall,
)
from .flow import aggregate_flow_status, build_flow_result
from .interaction import (
    InteractionPerformer,
    InteractionResult,
    verified_interaction,
)
from .locator import (
    STRATEGY_ORDER,
    StrategyResult,
    absolute,
    anchor_relative,
    backoff_delay_ms,
    backoff_sleep,
    can_constrain,
    image_match,
    locate_with_fallback,
    normalize,
    normalize_for_scaling,
    ocr_text_match,
    roi_constrained,
    run_strategy,
    scale_point,
    text_match,
    window_relative,
)
from .models import (
    Action,
    ClickOffset,
    ExpectedOutcome,
    FailureCategory,
    FinalStatus,
    FlowResult,
    FlowStatus,
    FULL_SCREEN,
    ImageRef,
    InteractionRecord,
    InteractionStep,
    LocalizationResult,
    LocalizationStrategy,
    Monitor,
    Region,
    ReliabilityConfig,
    SessionEnvironment,
    TargetElement,
    Verdict,
    WindowRef,
)

from .verifier import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    matches_expected,
    region_identical,
    verify_and_classify,
)
from .window import ensure_window_focus, window_origin

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
    # Flow aggregation
    "aggregate_flow_status",
    "build_flow_result",
    # Element_Locator (primitives + coordinate math)
    "STRATEGY_ORDER",
    "StrategyResult",
    "run_strategy",
    "normalize",
    "text_match",
    "normalize_for_scaling",
    "scale_point",
    "can_constrain",
    "image_match",
    "ocr_text_match",
    "anchor_relative",
    "roi_constrained",
    "window_relative",
    "absolute",
    # Element_Locator (traversal + retry/backoff)
    "locate_with_fallback",
    "backoff_delay_ms",
    "backoff_sleep",
    # Action_Verifier
    "verify_and_classify",
    "matches_expected",
    "region_identical",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    # Verified-Interaction Routine
    "verified_interaction",
    "InteractionResult",
    "InteractionPerformer",
    # Evidence store
    "store_evidence",
    "evidence_path",
    "sanitize_step_id",
    "EVIDENCE_DIRNAME",
    "VALID_PHASES",
    # Window manager
    "ensure_window_focus",
    "window_origin",
    # Multi-monitor click-offset calibration (R16)
    "Calibrator",
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
    "DEFAULT_OFFSET_TOLERANCE_PX",
    "MIN_STABLE_MEASUREMENTS",
    # Failure handler
    "classify_failure",
    "report_failure",
    "escalate",
    "stop_current_flow",
    "FailureReport",
    "FailureSignal",
    "FlowControl",
    # Test fakes (development-time only)
    "Frame",
    "ImageMatchResult",
    "CaptureCall",
    "FocusOp",
    "ImageMatchCall",
    "OcrCall",
    "FakeClock",
    "FakeScreen",
    "FakeFocusManager",
    "FakeImageMatcher",
    "FakeOcrProvider",
]
