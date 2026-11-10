"""Property-based test for Property 9: bounded retry with fresh capture and backoff.

# Feature: desktop-automation-reliability, Property 9: Bounded retry with fresh capture and exponential backoff

**Validates: Requirements 9.1, 9.2, 9.3, 9.4**

Property 9 (design "Correctness Properties"):

    For any sequence of failed localization attempts, the Element_Locator
    captures a fresh screen state on each attempt, performs no more than the
    configured maximum of 3 attempts, applies an exponential backoff delay
    following ``500ms * 2^(attempt-1)`` between attempts, and reports the element
    as not located once all attempts are exhausted without a qualifying match.

The test exercises :func:`locate_with_fallback` (Component 2, ``locator.py``)
against an **independent oracle** that re-derives the four observable
guarantees directly from the generated scenario, never calling the
implementation's own ``backoff_delay_ms`` / ``backoff_sleep`` helpers:

* **Fresh capture per attempt (R9.1):** the deterministic :class:`FakeScreen`
  records every ``capture`` call, so the test asserts exactly one fresh
  full-screen capture happened per attempt actually made.
* **Bounded attempts (R9.2):** at most ``config.max_locate_attempts`` attempts
  occur — never more — and a never-matching run uses the full cap (the default
  of 3 is always included in the generated range).
* **Exponential backoff between attempts (R9.3):** the controllable
  :class:`FakeClock` records every sleep, so the test asserts the sleep
  sequence equals ``base * 2^(i-1)`` (seconds) for each *inter-attempt* gap,
  with no trailing sleep after the final attempt.
* **NotLocated when exhausted (R9.4):** a run whose every attempt fails returns
  a not-located result.

Localization is driven through the **OCR_TEXT** strategy on an OCR-only target:
each attempt consumes exactly one scripted OCR read, so "match on attempt k vs.
never match" is controlled precisely without any matcher double-counting. The
fake clock makes the backoff deterministic with no real sleeps.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    FakeClock,
    FakeOcrProvider,
    FakeImageMatcher,
    FakeScreen,
    Frame,
    FULL_SCREEN,
    LocalizationStrategy,
    ReliabilityConfig,
    TargetElement,
    locate_with_fallback,
)

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# Text the OCR_TEXT strategy is asked to find, plus a value that never matches.
_EXPECTED_TEXT = "Target"
_NON_MATCHING_TEXT = "zzz-no-match"

# Backoff bases that all yield exact binary float seconds (base * 2^k / 1000),
# and that include the design default of 500 ms (R9.3).
_BACKOFF_BASES = (250, 500, 1000)


# ---------------------------------------------------------------------------
# Scenario strategy
# ---------------------------------------------------------------------------


@st.composite
def _retry_scenario(draw):
    """Generate a bounded-retry localization scenario.

    Produces a ``ReliabilityConfig`` (varying the attempt cap and backoff base,
    always covering the design defaults of 3 attempts / 500 ms), plus a
    ``success_attempt`` that is either a 1-based attempt index at which the OCR
    read matches, or ``None`` meaning the element is never located (every
    attempt fails, forcing exhaustion).
    """

    max_attempts = draw(st.integers(min_value=1, max_value=5))
    backoff_base_ms = draw(st.sampled_from(_BACKOFF_BASES))

    config = ReliabilityConfig(
        max_locate_attempts=max_attempts,
        backoff_base_ms=backoff_base_ms,
    )

    # None => never matches (exhaustion, R9.4); otherwise match on this attempt.
    success_attempt = draw(
        st.one_of(st.none(), st.integers(min_value=1, max_value=max_attempts))
    )
    return config, success_attempt


# ---------------------------------------------------------------------------
# Property 9 - bounded retry with fresh capture and exponential backoff
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_retry_scenario())
def test_property_09_bounded_retry_with_fresh_capture_and_backoff(scenario):
    # Feature: desktop-automation-reliability, Property 9: Bounded retry with fresh capture and exponential backoff
    config, success_attempt = scenario
    max_attempts = config.max_locate_attempts

    # OCR-only target: only the OCR_TEXT strategy can ever produce a candidate,
    # and it consumes exactly one scripted read per attempt (no matcher
    # double-counting), so the attempt at which a match occurs is controlled.
    target = TargetElement(text=_EXPECTED_TEXT)

    # Script one OCR read per possible attempt: matching only on success_attempt.
    ocr_script = [
        _EXPECTED_TEXT if (success_attempt is not None and i == success_attempt)
        else _NON_MATCHING_TEXT
        for i in range(1, max_attempts + 1)
    ]
    ocr = FakeOcrProvider(sequence=ocr_script, default=_NON_MATCHING_TEXT)

    # The image matcher is never expected to qualify (no reference on target);
    # a low default keeps any incidental call a clean non-match.
    matcher = FakeImageMatcher(default=0.0)

    # A fresh frame per capture; content is irrelevant to OCR-driven matching.
    screen = FakeScreen(default=Frame.of([[0, 0], [0, 0]]))
    clock = FakeClock()

    result = locate_with_fallback(
        target,
        config,
        capture=screen.capture,
        image_matcher=matcher,
        ocr_provider=ocr,
        clock=clock,
    )

    # --- Independent oracle ------------------------------------------------
    located = success_attempt is not None
    # Attempts actually made: stop at the matching attempt, else use the cap.
    attempts_made = success_attempt if located else max_attempts
    # Backoff applies strictly between attempts -> one gap per failed attempt,
    # never a trailing sleep after the final attempt (R9.3). Re-derived here as
    # base * 2^(i-1) seconds, independent of the implementation's helpers.
    expected_sleeps = [
        config.backoff_base_ms * 2 ** (i - 1) / 1000.0
        for i in range(1, attempts_made)
    ]

    # R9.4: located iff a qualifying match occurred within the attempt budget.
    assert result.located is located

    # R9.2: never more than the configured maximum; exhaustion uses the full cap.
    assert attempts_made <= max_attempts
    assert screen.capture_count <= max_attempts
    if not located:
        assert attempts_made == max_attempts

    # R9.1: a fresh full-screen capture on each attempt actually made - exactly
    # one per attempt, no more and no fewer.
    assert screen.capture_count == attempts_made
    assert screen.requested_regions == [FULL_SCREEN] * attempts_made
    # The OCR strategy is consulted once per attempt as well (fresh evaluation).
    assert ocr.call_count == attempts_made

    # R9.3: exponential backoff 500ms * 2^(attempt-1) applied between attempts.
    assert clock.sleeps == expected_sleeps
    assert clock.sleep_calls == max(0, attempts_made - 1)

    # On success, the producing strategy and confidence are recorded (R5.4);
    # the OCR_TEXT match reports full confidence.
    if located:
        assert result.strategy is LocalizationStrategy.OCR_TEXT
        assert result.confidence == 1.0
    else:
        assert result.point is None
        assert result.strategy is None


# ---------------------------------------------------------------------------
# Property 9 - exhaustion under the design defaults (3 attempts, 500 ms)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(
    # Vary only the never-matching OCR text and the captured frame so the
    # default schedule is locked while the inputs still range widely.
    st.text(alphabet="abcdefghij ", min_size=0, max_size=8),
    st.integers(min_value=0, max_value=3),
)
def test_property_09_exhaustion_uses_default_three_attempts_and_500ms(noise_text, pixel):
    # Feature: desktop-automation-reliability, Property 9: Bounded retry with fresh capture and exponential backoff
    config = ReliabilityConfig()  # defaults: 3 attempts, 500 ms base (R9.2/R9.3)

    # An OCR-only target whose scripted reads never normalize-equal the expected
    # text -> every attempt fails -> exhaustion (R9.4).
    target = TargetElement(text=_EXPECTED_TEXT)
    never_match = f"{noise_text}#never"  # cannot equal _EXPECTED_TEXT after normalize
    ocr = FakeOcrProvider(default=never_match)
    matcher = FakeImageMatcher(default=0.0)
    screen = FakeScreen(default=Frame.of([[pixel]]))
    clock = FakeClock()

    result = locate_with_fallback(
        target,
        config,
        capture=screen.capture,
        image_matcher=matcher,
        ocr_provider=ocr,
        clock=clock,
    )

    # R9.4: not located once all attempts are exhausted.
    assert result.located is False
    # R9.1/R9.2: exactly the configured maximum of 3 fresh captures - no more.
    assert screen.capture_count == 3
    assert screen.requested_regions == [FULL_SCREEN, FULL_SCREEN, FULL_SCREEN]
    # R9.3: backoff between attempts is 500ms * 2^(attempt-1) -> 0.5s, 1.0s, and
    # no trailing sleep after the third (final) attempt.
    assert clock.sleeps == [0.5, 1.0]
