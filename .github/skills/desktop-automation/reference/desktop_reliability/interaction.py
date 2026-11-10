"""Verified-Interaction Routine: the single-interaction orchestrator (Component 1).

This module implements **Component 1** of the design (the *Verified-Interaction
Routine*): :func:`verified_interaction` drives the full lifecycle of one
interaction and is the **only** place a desktop interaction is ever reported as a
success. It composes the other components into the design's lifecycle:

    define expected outcome -> confirm focus -> pre-capture -> locate ->
    interact -> post-capture -> verify -> classify -> (retry with backoff |
    escalate)

Lifecycle (design "Component 1" pseudocode, requirement tags inline):

1. **Expected outcome must exist (R2.1).** The routine refuses to act without an
   explicit :class:`~desktop_reliability.models.ExpectedOutcome`; success is
   defined relative to it.
2. **Bounded re-attempt loop (R12.1).** Up to
   ``config.max_interaction_attempts`` (default 3) attempts. Each attempt runs
   the whole locate -> interact -> verify cycle on fresh state (R12.2).
3. **Focus before every interaction (R11.1/R11.2).** ``ensure_window_focus`` is
   called at the start of each attempt so input always lands in the intended
   window before anything is captured or clicked.
4. **Pre-capture strictly before the action (R1.1/R1.4).** The Pre_Action_State
   of the verification region is captured and stored under ``evidences/`` before
   the element is located or the action is performed.
5. **Ranked localization with fallback (R5-R10).** ``locate_with_fallback``
   resolves the on-screen point. On *not located* the localization outcome is
   recorded first (R12.5), a backoff is applied (R9.3/R12), and the attempt is
   abandoned for the next one.
6. **Interact at the resolved point (R11.3).** ``perform_interaction`` is invoked
   with the located point (already resolved relative to the window origin and
   scaling by the locator).
7. **Post-capture after the action (R1.2/R1.3/R1.4).** The Post_Action_State is
   captured (targeting 2000 ms, but a late capture is accepted) and stored.
8. **Verify and classify (R2.2-R2.5 / R3).** ``verify_and_classify`` polls for
   the expected outcome and returns a :class:`~desktop_reliability.models.Verdict`.
   The verdict is recorded on the interaction.
9. **Success has exactly one source (R2.3/R4.1/R4.2).** The routine returns a
   success **iff** the verdict is ``CONFIRMED`` *and* a Post_Action_State was
   stored as evidence. There is no "assume success" branch.
10. **Record before retry (R12.5).** A non-confirming verdict is recorded before
    the backoff and re-attempt.
11. **Escalate on exhaustion (R12.3/R12.4/R13).** When the attempts are spent
    without a CONFIRMED outcome, :func:`escalate` classifies the failure into
    exactly one category, signals the flow to stop, and builds a report carrying
    the captured Pre/Post evidence, the localization strategy, the confidence,
    and the verification verdict.

Why everything is injected
--------------------------
Like ``locator.py`` and ``verifier.py``, every side-effecting dependency is
**injected** so the whole routine is exercisable with the deterministic fakes in
``fakes.py`` and needs no real desktop, clock, focus system, or filesystem:

============================  ==========================================
Injected dependency           Provided in tests by
============================  ==========================================
``capture``                   ``FakeScreen.capture``
``perform_interaction``       a recording test callable
``image_matcher``             ``FakeImageMatcher``
``ocr_provider``              ``FakeOcrProvider``
``focus_manager``             ``FakeFocusManager``
``clock``                     ``FakeClock``
``evidence_writer``           a recording writer (no real file I/O)
============================  ==========================================

This module is *logic only* — it performs no I/O of its own; capture, timing,
focus, and evidence writes are all the injected dependencies' responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple, Union

from .evidence import Writer, store_evidence
from .calibration import resolve_interaction_point
from .failure import FailureReport, FailureSignal, escalate
from .locator import (
    Capture,
    Clock,
    ImageMatcher,
    OcrProvider,
    backoff_sleep,
    locate_with_fallback,
)
from .models import (
    Action,
    ClickOffset,
    ExpectedOutcome,
    FinalStatus,
    InteractionRecord,
    InteractionStep,
    ReliabilityConfig,
    SessionEnvironment,
    Verdict,
)
from .verifier import verify_and_classify
from .window import FocusManager, ensure_window_focus

__all__ = [
    "InteractionPerformer",
    "InteractionResult",
    "verified_interaction",
]


Point = Tuple[int, int]

#: An interaction performer: perform ``action`` at the resolved screen ``point``.
#: Models the design's ``perform_interaction(step.action, location.point)``. The
#: point is already resolved relative to the window origin and adjusted for
#: scaling by ``locate_with_fallback`` (R11.3), so the performer just executes
#: the click/type at the given coordinate. In generated code this wraps
#: ``pyautogui.click`` / ``typewrite`` / ``pywinauto``; in tests it is a
#: recording callable so ordering ("pre-capture strictly before the action") and
#: the click coordinate can be asserted.
InteractionPerformer = Callable[[Action, Point], None]


@dataclass
class InteractionResult:
    """The outcome of a single :func:`verified_interaction` call.

    Carries the accumulated :class:`~desktop_reliability.models.InteractionRecord`
    (localization strategy, confidence, verification verdict, ordered Pre/Post
    evidence paths, attempt count, terminal status) and, on failure, the
    :class:`~desktop_reliability.failure.FailureReport` produced by escalation.

    ``succeeded`` is the single, evidence-backed success signal (R4): it is
    ``True`` **iff** the interaction ended on a ``CONFIRMED`` verdict with a
    stored Post_Action_State and no failure report was produced. Use the
    factories :meth:`success` / :meth:`failure` rather than constructing
    instances directly.
    """

    record: InteractionRecord
    failure_report: Optional[FailureReport] = None

    @classmethod
    def success(cls, record: InteractionRecord) -> "InteractionResult":
        """Build a successful result (no failure report)."""

        return cls(record=record, failure_report=None)

    @classmethod
    def failure(
        cls, record: InteractionRecord, report: FailureReport
    ) -> "InteractionResult":
        """Build a failed result carrying its escalation report."""

        return cls(record=record, failure_report=report)

    @property
    def succeeded(self) -> bool:
        """Whether the interaction was a verified, evidence-backed success (R4).

        ``True`` only when the record's terminal status is ``SUCCESS``, its
        verification verdict is ``CONFIRMED``, a Post_Action_State was stored as
        evidence, and no failure report exists. Every other outcome
        (``NO_OP_CLICK``, ``WRONG_TARGET_CLICK``, not-located, missing evidence)
        is a failure.
        """

        return (
            self.failure_report is None
            and self.record.final_status == FinalStatus.SUCCESS
            and self.record.verification == Verdict.CONFIRMED
            and bool(self.record.post_evidence)
        )


def verified_interaction(
    step: InteractionStep,
    expected_outcome: ExpectedOutcome,
    config: ReliabilityConfig,
    *,
    capture: Capture,
    perform_interaction: InteractionPerformer,
    image_matcher: ImageMatcher,
    ocr_provider: OcrProvider,
    focus_manager: FocusManager,
    clock: Clock,
    session: Optional[SessionEnvironment] = None,
    click_offset: Optional[ClickOffset] = None,
    evidence_writer: Optional[Writer] = None,
    project_root: Optional[Union[str, Path]] = None,
    evidences_root: Optional[Union[str, Path]] = None,
    poll_interval_seconds: Optional[float] = None,
    failure_signal: Optional[FailureSignal] = None,
) -> InteractionResult:
    """Drive one interaction through the verified lifecycle (Component 1).

    Implements the design's *Verified-Interaction Routine*. Returns an
    :class:`InteractionResult` whose ``succeeded`` is ``True`` **iff** the
    interaction produced a ``CONFIRMED`` verdict backed by stored
    Post_Action_State evidence (R2.3/R4.1/R4.2) — the *only* path to success. For
    every other case (no-op, wrong-target, element not located, or attempts
    exhausted) the interaction is treated as failed, the failure is classified
    and escalated (R12.3/R12.4/R13), and the result carries the escalation report.

    The lifecycle for each of up to ``config.max_interaction_attempts`` attempts
    (R12.1) is:

    1. ``ensure_window_focus`` before anything else (R11.1/R11.2).
    2. Pre-capture the verification region and store it as evidence *before*
       locating or acting (R1.1/R1.4).
    3. ``locate_with_fallback`` to resolve the point (R5-R10). On *not located*,
       record the (empty) localization outcome first (R12.5), back off (R9.3/R12),
       and move to the next attempt.
    4. ``perform_interaction`` at the resolved point (R11.3), recording the
       producing localization strategy and confidence on the record (R5.4).
    5. Post-capture the verification region and store it as evidence
       (R1.2/R1.3/R1.4); a late post-capture is still accepted.
    6. ``verify_and_classify`` (polling up to the verify timeout) and record the
       verdict (R2.2-R2.5/R3). On ``CONFIRMED`` return success immediately; any
       other verdict is recorded (R12.5), backed off, and retried.

    When all attempts are exhausted without a CONFIRMED outcome, :func:`escalate`
    classifies the failure into exactly one category, signals the flow to stop,
    and builds a report with the captured evidence, strategy, confidence, and
    verdict (R12.3/R12.4). The exponential backoff between attempts follows
    ``500ms * 2^(attempt-1)`` and is *not* applied after the final attempt
    (no pointless trailing delay before escalation), mirroring
    ``locate_with_fallback``.

    :param step: the interaction step (target, action, window, verification region).
    :param expected_outcome: the explicit, observable success check (R2.1);
        must not be ``None``.
    :param config: thresholds and budgets (attempts, timeout, backoff base).
    :param capture: the screen-capture function ``capture(region) -> state``;
        used for the pre/post captures and as the re-capture source the verifier
        polls. Callers should give the fake screen a ``default`` frame so the
        verify poll never exhausts the script.
    :param perform_interaction: performs the action at the resolved point.
    :param image_matcher: image-match provider for localization.
    :param ocr_provider: OCR provider for localization.
    :param focus_manager: window-focus manager for the focus precondition.
    :param clock: monotonic clock driving verify polling and backoff.
    :param session: optional execution/exploration environment for scaling math.
    :param click_offset: optional measured multi-monitor Click_Offset (R16). When
        a *stable* offset is supplied, every resolved interaction point is
        corrected by it before the action is commanded (R16.6/R16.10); ``None``
        or an unstable offset leaves the point unchanged (R16.13). On a
        single-monitor desktop use :meth:`ClickOffset.zero` (the identity).
    :param evidence_writer: optional write sink for evidence; inject a recording
        writer to avoid real file I/O in tests. When ``None`` a real write occurs.
    :param project_root: optional project root for ``<project-root>/evidences/``.
    :param evidences_root: optional explicit evidence directory (overrides
        ``project_root``).
    :param poll_interval_seconds: optional verify poll cadence override.
    :param failure_signal: optional explicit classification hint passed to
        escalation for causes the record cannot disambiguate.
    :raises ValueError: if ``expected_outcome`` is ``None`` (R2.1).
    """

    # R2.1: an explicit expected outcome must exist before acting. Success is
    # defined relative to it, so there is nothing to verify without one.
    if expected_outcome is None:
        raise ValueError(
            "verified_interaction requires an explicit expected_outcome (R2.1)"
        )

    record = InteractionRecord(step_id=step.id)

    def _store(capture_obj: object, phase: str, attempt: int) -> str:
        """Store one capture under ``evidences/`` and return its path (R1.4)."""

        return store_evidence(
            capture_obj,
            step.id,
            phase,
            attempt,
            project_root=project_root,
            evidences_root=evidences_root,
            writer=evidence_writer,
        )

    def _backoff(attempt: int) -> None:
        """Apply the exponential backoff between attempts only (R9.3/R12).

        No trailing sleep after the final attempt — a backoff right before
        escalation would delay the failure report for no benefit. This mirrors
        the "no trailing sleep" convention in ``locate_with_fallback``.
        """

        if attempt < config.max_interaction_attempts:
            backoff_sleep(attempt, config, clock=clock)

    for attempt in range(1, config.max_interaction_attempts + 1):  # R12.1
        record.attempts = attempt

        # R11.1/R11.2: confirm (and, if needed, acquire) focus before anything
        # is captured or clicked, so input lands in the intended window.
        ensure_window_focus(step.target_window, focus_manager=focus_manager)

        # R1.1/R1.4: capture and store the Pre_Action_State strictly BEFORE the
        # element is located or the action is performed.
        pre = capture(step.verification_region)
        record.pre_evidence.append(_store(pre, "pre", attempt))

        # R5-R10: resolve the target to a screen point via ranked fallback.
        location = locate_with_fallback(
            step.target,
            config,
            capture=capture,
            image_matcher=image_matcher,
            ocr_provider=ocr_provider,
            session=session,
            clock=clock,
        )

        if not location.located:
            # R12.5: record the localization outcome (no strategy/confidence
            # produced; nothing verified yet) BEFORE backing off and retrying.
            record.localization_strategy = location.strategy  # None
            record.confidence = location.confidence  # None
            record.verification = None
            _backoff(attempt)  # R9.3/R12
            continue

        # R5.4: record the producing strategy and its confidence.
        record.localization_strategy = location.strategy
        record.confidence = location.confidence

        # R16.6/R16.10/R16.13: correct the resolved point by the measured
        # Click_Offset before commanding the interaction. On a single-monitor
        # desktop (or an unknown/unstable offset) this is the identity, so the
        # point is unchanged; on a multi-monitor desktop with a stable offset it
        # compensates for the constant capture-vs-click plane divergence. The
        # offset-correcting resolver is the single choke point every commanded
        # interaction routes through (R16.17).
        commanded_point = resolve_interaction_point(location.point, click_offset)

        # R11.3: perform the interaction at the resolved (window-relative,
        # scaling-adjusted, offset-corrected) point.
        perform_interaction(step.action, commanded_point)

        # R1.2/R1.3/R1.4: capture and store the Post_Action_State after the
        # action (targeting 2000 ms; a late post-capture is still accepted —
        # latency never invalidates the evidence).
        post = capture(step.verification_region)
        record.post_evidence.append(_store(post, "post", attempt))

        # R2.2-R2.5/R3: verify the expected outcome (polling up to the timeout
        # via the injected capture) and classify any non-confirming result.
        verdict = verify_and_classify(
            pre,
            post,
            expected_outcome,
            config,
            clock=clock,
            recapture=capture,
            poll_interval_seconds=poll_interval_seconds,
        )
        record.verification = verdict

        # R2.3/R4.1/R4.2: the single source of success — a CONFIRMED verdict
        # backed by present Post_Action_State evidence. No "assume success".
        if verdict == Verdict.CONFIRMED and record.post_evidence:
            record.final_status = FinalStatus.SUCCESS
            return InteractionResult.success(record)

        # R3.3/R3.4/R12.5: No-op or Wrong-target -> failed. The verdict is
        # already recorded above; back off before the next attempt.
        _backoff(attempt)  # R12

    # R12.3/R12.4/R13: attempts exhausted without a CONFIRMED outcome. Classify
    # into exactly one category, signal the flow to stop, and report with the
    # captured Pre/Post evidence, strategy, confidence, and verdict.
    report = escalate(record, failure_signal)
    return InteractionResult.failure(record, report)
