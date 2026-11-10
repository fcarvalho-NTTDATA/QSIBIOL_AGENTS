"""Example unit tests for ``ReliabilityConfig`` defaults and model invariants.

These are *example/unit* tests (not property-based): they pin the exact design
constants and a few core model invariants so the reference implementation can
never silently drift from the governing documents.

Covered design constants (see ``models.ReliabilityConfig`` and the design
"Data Models" / constants section):

- ``confidence_threshold == 0.80``           (R6.1)
- ``verify_timeout_seconds == 10``           (R2.5)
- ``post_capture_target_ms == 2000``         (R1.2)
- ``max_locate_attempts == 3``               (R9.2)
- ``max_interaction_attempts == 3``          (R12.1)
- ``backoff_base_ms == 500``                 (R9.3)

Plus the exponential backoff schedule ``delay(attempt) = backoff_base_ms *
2^(attempt-1)`` → ``500ms, 1000ms, 2000ms`` for attempts 1, 2, 3 (R9.3).

Requirements: 1.2, 2.5, 6.1, 9.2, 9.3, 12.1
"""

from __future__ import annotations

from desktop_reliability import (
    FULL_SCREEN,
    Action,
    FailureCategory,
    FinalStatus,
    FlowStatus,
    LocalizationResult,
    LocalizationStrategy,
    ReliabilityConfig,
    Verdict,
)


# ---------------------------------------------------------------------------
# ReliabilityConfig default constants (R1.2, R2.5, R6.1, R9.2, R9.3, R12.1)
# ---------------------------------------------------------------------------


def test_confidence_threshold_default_is_0_80():
    """Confidence threshold defaults to 0.80 (R6.1)."""
    assert ReliabilityConfig().confidence_threshold == 0.80


def test_verify_timeout_seconds_default_is_10():
    """Verification polling budget defaults to 10 seconds (R2.5)."""
    assert ReliabilityConfig().verify_timeout_seconds == 10


def test_post_capture_target_ms_default_is_2000():
    """Post-action capture target defaults to 2000 ms (R1.2)."""
    assert ReliabilityConfig().post_capture_target_ms == 2000


def test_max_locate_attempts_default_is_3():
    """Localization is capped at 3 attempts (R9.2)."""
    assert ReliabilityConfig().max_locate_attempts == 3


def test_max_interaction_attempts_default_is_3():
    """Interactions are re-attempted up to 3 times (R12.1)."""
    assert ReliabilityConfig().max_interaction_attempts == 3


def test_backoff_base_ms_default_is_500():
    """Exponential backoff base defaults to 500 ms (R9.3)."""
    assert ReliabilityConfig().backoff_base_ms == 500


def test_all_defaults_together():
    """All design constants pinned in one place (0.80 / 10 / 2000 / 3 / 3 / 500)."""
    config = ReliabilityConfig()
    assert (
        config.confidence_threshold,
        config.verify_timeout_seconds,
        config.post_capture_target_ms,
        config.max_locate_attempts,
        config.max_interaction_attempts,
        config.backoff_base_ms,
    ) == (0.80, 10, 2000, 3, 3, 500)


def test_config_is_immutable():
    """``ReliabilityConfig`` is a frozen dataclass, so constants cannot be mutated."""
    config = ReliabilityConfig()
    try:
        config.confidence_threshold = 0.5  # type: ignore[misc]
    except Exception as exc:  # FrozenInstanceError is a subclass of Exception
        assert exc.__class__.__name__ == "FrozenInstanceError"
    else:  # pragma: no cover - guards against an accidentally-mutable config
        raise AssertionError("ReliabilityConfig should be frozen/immutable")


# ---------------------------------------------------------------------------
# Backoff schedule: delay(attempt) = backoff_base_ms * 2^(attempt-1)  (R9.3)
# ---------------------------------------------------------------------------
#
# No standalone backoff helper exists yet (the ``locate_with_fallback``
# traversal that applies it is a later task). These tests therefore validate
# the *design backoff formula* directly against ``backoff_base_ms`` so the
# constant and the schedule it produces stay locked to the design.


def _backoff_delay_ms(attempt: int, base_ms: int) -> int:
    """Design backoff formula: ``delay(attempt) = base_ms * 2^(attempt-1)``."""
    return base_ms * 2 ** (attempt - 1)


def test_backoff_schedule_matches_design_formula():
    """Attempts 1, 2, 3 yield 500ms, 1000ms, 2000ms from the default base (R9.3)."""
    base_ms = ReliabilityConfig().backoff_base_ms
    schedule = [_backoff_delay_ms(attempt, base_ms) for attempt in (1, 2, 3)]
    assert schedule == [500, 1000, 2000]


def test_backoff_first_attempt_equals_base():
    """The first attempt's delay equals the base (2^0 == 1) (R9.3)."""
    base_ms = ReliabilityConfig().backoff_base_ms
    assert _backoff_delay_ms(1, base_ms) == base_ms == 500


def test_backoff_doubles_each_attempt():
    """Each subsequent attempt doubles the previous delay (R9.3)."""
    base_ms = ReliabilityConfig().backoff_base_ms
    assert _backoff_delay_ms(2, base_ms) == 2 * _backoff_delay_ms(1, base_ms)
    assert _backoff_delay_ms(3, base_ms) == 2 * _backoff_delay_ms(2, base_ms)


# ---------------------------------------------------------------------------
# Core model invariants
# ---------------------------------------------------------------------------


def test_not_located_result_has_no_match_details():
    """``LocalizationResult.not_located()`` is a clean miss (R9.4)."""
    result = LocalizationResult.not_located()
    assert result.located is False
    assert result.point is None
    assert result.strategy is None
    assert result.confidence is None


def test_located_at_records_point_strategy_and_confidence():
    """``LocalizationResult.located_at(...)`` records the producing strategy (R5.4)."""
    result = LocalizationResult.located_at(
        point=(12, 34),
        strategy=LocalizationStrategy.IMAGE_MATCH,
        confidence=0.91,
    )
    assert result.located is True
    assert result.point == (12, 34)
    assert result.strategy is LocalizationStrategy.IMAGE_MATCH
    assert result.confidence == 0.91


def test_localization_strategy_members_and_order():
    """The six ranked strategies are present in most→least stable order (R5.1)."""
    assert [s.value for s in LocalizationStrategy] == [
        "image_match",
        "ocr_text",
        "anchor_relative",
        "roi_constrained",
        "window_relative",
        "absolute",
    ]


def test_verdict_members():
    """Verification yields exactly the three design verdicts (R2/R3)."""
    assert {v.value for v in Verdict} == {
        "confirmed",
        "no_op_click",
        "wrong_target_click",
    }


def test_failure_category_members():
    """Failure classification uses exactly the three design categories (R12.3)."""
    assert {c.value for c in FailureCategory} == {
        "code_issue",
        "system_bug",
        "user_input_needed",
    }


def test_action_and_flow_status_and_final_status_members():
    """Spot-check the remaining enums used across the pattern."""
    assert {a.value for a in Action} == {
        "click",
        "double_click",
        "right_click",
        "type",
        "press",
    }
    assert {s.value for s in FlowStatus} == {"passed", "failed"}
    assert {s.value for s in FinalStatus} == {"success", "failed"}


def test_full_screen_sentinel_repr_and_singleton():
    """``FULL_SCREEN`` reprs as ``FULL_SCREEN`` and is a singleton sentinel."""
    assert repr(FULL_SCREEN) == "FULL_SCREEN"
    assert FULL_SCREEN is FULL_SCREEN.__class__()
