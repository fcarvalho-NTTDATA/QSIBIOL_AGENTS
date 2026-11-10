"""Action_Verifier: post-action verification and verdict classification.

This module implements **Component 3** of the design (the ``Action_Verifier``):
``verify_and_classify`` confirms that an interaction produced its
:class:`~desktop_reliability.models.ExpectedOutcome` by polling the post-action
state, and classifies any non-confirming result into a :class:`Verdict`.

Behavior (design "Component 3" pseudocode, R2.2-R2.5 / R3.1 / R3.2 / R4.2):

- Poll up to ``config.verify_timeout_seconds`` (default 10s) for the expected
  predicate to hold on a **present** post-state. The first thing checked is the
  post-state handed in by the caller; while time remains and a ``recapture``
  callable is injected, a fresh post-state is re-captured between polls,
  modeling ``capture_state(expected.region)`` (R2.5).
- Return :attr:`Verdict.CONFIRMED` as soon as the predicate holds (R2.2/R2.3).
- On timeout, classify the change: :attr:`Verdict.NO_OP_CLICK` when the
  post-state is region-identical to the pre-state (R3.1), otherwise
  :attr:`Verdict.WRONG_TARGET_CLICK` (the region changed but does not match the
  expected outcome, R3.2).

Two invariants this module guarantees:

1. **Exactly one verdict** is always returned for any inputs.
2. **A missing/None post-state can never be ``CONFIRMED``** (R4.2): success
   requires verification evidence, so :func:`matches_expected` short-circuits to
   ``False`` when no post-state is present.

Everything is **logic only** and fully injectable: the monotonic clock and the
post-state re-capture function are passed in, so the polling/timeout behavior is
driven by the deterministic fakes in ``fakes.py`` (``FakeClock`` /
``FakeScreen``) with no real sleeps and no real desktop. ``FakeScreen.capture``
satisfies the ``recapture`` contract directly.
"""

from __future__ import annotations

from typing import Callable, Optional, Protocol

from .fakes import Frame
from .models import (
    ExpectedOutcome,
    Region,
    ReliabilityConfig,
    Verdict,
    _FullScreenSentinel,
)

__all__ = [
    "Clock",
    "Recapture",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "matches_expected",
    "region_identical",
    "verify_and_classify",
]


# A region argument is either a bounded Region or the FULL_SCREEN sentinel.
RegionArg = "Region | _FullScreenSentinel"

#: A post-state re-capture function: given the verification region it returns a
#: fresh post-state. Models the design's ``capture_state(expected.region)``.
#: :meth:`desktop_reliability.fakes.FakeScreen.capture` satisfies this directly,
#: so a test can pass ``screen.capture`` as the ``recapture`` argument.
Recapture = Callable[[RegionArg], object]

#: Virtual time between polls of the post-state. The verify loop must advance
#: the (virtual) clock each iteration so it terminates deterministically at the
#: deadline; this is the step it advances by between re-captures. Mirrors the
#: backoff base (500 ms) and can be overridden per call.
DEFAULT_POLL_INTERVAL_SECONDS: float = 0.5


# ---------------------------------------------------------------------------
# Injected clock protocol (duck-typed; FakeClock satisfies it).
# ---------------------------------------------------------------------------


class Clock(Protocol):
    """A monotonic clock with non-blocking sleep.

    Satisfied by :class:`desktop_reliability.fakes.FakeClock`; in generated code
    this wraps ``time.monotonic`` / ``time.sleep``. ``now`` returns seconds as a
    float; ``sleep`` advances time by ``seconds``.
    """

    def now(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


# ---------------------------------------------------------------------------
# Expected-outcome matching (R2.2 / R4.2).
# ---------------------------------------------------------------------------


def matches_expected(post: object, expected: ExpectedOutcome) -> bool:
    """Return whether the post-state satisfies the expected outcome (R2.2/R4.2).

    A **missing** post-state (``None``) can never satisfy the outcome (R4.2):
    success requires verification evidence, so this returns ``False`` before the
    predicate is ever consulted - guaranteeing a missing post-state can never
    yield :attr:`Verdict.CONFIRMED`. Otherwise the expected outcome's
    ``predicate`` is evaluated against the present post-state.

    **Predicate exceptions are guarded** (returns ``False``): a predicate that
    raises means the expected outcome could not be observed, which - by the
    reliability principle "no confirmation without positive evidence" (R4) -
    must be treated as *not matched* rather than crashing verification. This
    keeps a flaky/erroring check from ever producing a false ``CONFIRMED`` and
    lets the polling loop continue to its timeout and classify normally.
    """

    if post is None:
        return False  # R4.2: no evidence -> cannot be a success.
    try:
        return bool(expected.predicate(post))
    except Exception:
        # A predicate that errors is "outcome not observed" (never a success).
        return False


# ---------------------------------------------------------------------------
# Region-diff comparison (R3.1).
# ---------------------------------------------------------------------------


def region_identical(pre: object, post: object, region: RegionArg) -> bool:
    """Return whether ``pre`` and ``post`` are identical within ``region`` (R3.1).

    The comparison is the basis for No-op detection: when the post-state is
    indistinguishable from the pre-state within the verification region, nothing
    observable changed.

    Comparison rules:

    - **Frame states**: when both ``pre`` and ``post`` are :class:`Frame`
      objects, each is cropped to ``region`` and the cropped sub-frames are
      compared for value equality. The ``FULL_SCREEN`` sentinel (or any
      non-:class:`Region` value) crops to the whole frame, so a full-screen
      verification region compares the entire frames (``Frame.crop`` returns the
      frame unchanged for a non-bounded region).
    - **Other states**: when the states are not both frames (strings, dicts,
      ints, ``None``, mixed types, ...), they are compared directly for value
      equality. Mismatched types are therefore "not identical", and two missing
      states (``None``/``None``) count as identical (no change).
    """

    if isinstance(pre, Frame) and isinstance(post, Frame):
        return pre.crop(region) == post.crop(region)
    return pre == post


# ---------------------------------------------------------------------------
# Verify-and-classify (R2.2-R2.5 / R3.1 / R3.2).
# ---------------------------------------------------------------------------


def verify_and_classify(
    pre: object,
    post: object,
    expected: ExpectedOutcome,
    config: ReliabilityConfig,
    *,
    clock: Clock,
    recapture: Optional[Recapture] = None,
    poll_interval_seconds: Optional[float] = None,
) -> Verdict:
    """Confirm the expected outcome by polling, else classify the change.

    Polls the post-state for up to ``config.verify_timeout_seconds`` (default
    10s, R2.5) for the expected predicate to hold on a present post-state
    (R2.2). Returns:

    - :attr:`Verdict.CONFIRMED` as soon as the predicate holds (R2.3 / R4.1).
    - On timeout, :attr:`Verdict.NO_OP_CLICK` when the post-state is
      region-identical to the pre-state (R3.1), otherwise
      :attr:`Verdict.WRONG_TARGET_CLICK` (changed, but not the expected change,
      R3.2).

    Polling model (deterministic and always terminating):

    - The caller-supplied ``post`` is checked first. While the deadline has not
      passed **and** a ``recapture`` callable is injected, the clock is advanced
      by ``poll_interval_seconds`` and a fresh post-state is re-captured via
      ``recapture(expected.region)`` before the next check (R2.5 "poll ... before
      concluding"). This models the design's ``post = capture_state(expected.region)``.
    - When **no** ``recapture`` is injected the post-state cannot change, so the
      handed-in ``post`` is checked exactly once and the result is classified
      immediately (graceful single-poll behavior - re-checking an unchanged
      state would be pointless).
    - The (virtual) clock is advanced via ``clock.sleep`` each iteration so the
      loop crosses the deadline in a bounded number of steps; with the fake
      clock there are no real sleeps.

    The poll interval defaults to :data:`DEFAULT_POLL_INTERVAL_SECONDS` (0.5s,
    mirroring the backoff base) and may be overridden via
    ``poll_interval_seconds``; a non-positive override is clamped up to the
    default so the (virtual) clock always advances and the loop terminates.

    Guarantees: exactly one :class:`Verdict` is always returned, and a
    missing/``None`` post-state can never be :attr:`Verdict.CONFIRMED` (R4.2,
    enforced by :func:`matches_expected`).
    """

    region = expected.region
    # A strictly-positive interval guarantees the (virtual) clock advances each
    # poll so the loop crosses the deadline in a bounded number of steps; a
    # non-positive request is clamped up to the default to prevent a stall.
    interval = (
        DEFAULT_POLL_INTERVAL_SECONDS
        if poll_interval_seconds is None or poll_interval_seconds <= 0
        else float(poll_interval_seconds)
    )
    deadline = clock.now() + config.verify_timeout_seconds

    # R2.5: poll up to the timeout for the expected outcome. The handed-in post
    # is checked first; fresh post-states are re-captured between polls.
    while True:
        if matches_expected(post, expected):
            return Verdict.CONFIRMED  # R2.3 / R4.1
        # Stop polling when there is nothing new to observe (no recapture
        # source) or the timeout has been reached.
        if recapture is None or clock.now() >= deadline:
            break
        clock.sleep(interval)
        post = recapture(region)  # re-capture while polling (capture_state)

    # Timeout reached (or no re-capture source): classify the change. R3.1 vs
    # R3.2 - identical within the region is a No-op; any other difference is a
    # Wrong-target. A missing post-state never reached CONFIRMED above.
    if region_identical(pre, post, region):
        return Verdict.NO_OP_CLICK  # R3.1
    return Verdict.WRONG_TARGET_CLICK  # R3.2
