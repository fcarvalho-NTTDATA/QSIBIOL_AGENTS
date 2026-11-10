"""Failure classification, flow-stop signalling, and reporting (R12.3-R12.5).

This module implements **Component 4 — Failure-Handler / Escalation** from the
design (`classify_failure`). When the Verified-Interaction Routine exhausts its
re-attempt budget, an exhausted :class:`~desktop_reliability.models.InteractionRecord`
is escalated here, where it is:

1. **Classified** into *exactly one* existing error category — ``code_issue``,
   ``system_bug``, or ``user_input_needed`` (R12.3).
2. **Stopped** — the current flow is signalled to halt (R12.4).
3. **Reported** — a :class:`FailureReport` is built carrying the captured
   Pre/Post evidence paths, the localization strategy, the confidence, and the
   verification verdict that were recorded on the interaction (R12.4, R12.5).

This is *logic-only* reference code: there is no real flow engine and no real
output sink, so two modelling choices are made and documented here:

- **"Stop the flow" is a returnable signal, not a side effect.** ``stop_current_flow``
  returns a :class:`FlowControl` value (``STOP``); it never calls ``sys.exit``,
  raises, prints, or mutates global state. Real planes (live exploration / the
  generated script) interpret a ``STOP`` signal as "halt and do not advance to
  the next step".
- **"Report the failure" is a returned dataclass, not I/O.** ``report_failure``
  *builds and returns* a :class:`FailureReport`; it does not print, log, or
  write files. Persisting the report (e.g. under ``<project-root>/evidences/``)
  is the caller's concern in a real plane.

Keeping both pure makes the classification and escalation behaviour fully
property-testable without a desktop, clock, or filesystem.

Mapping to the design pseudocode
---------------------------------
The design's single ``classify_failure(record)`` entry point performs classify →
``stop_current_flow()`` → ``report_failure(...)``. Here that pipeline is split so
each piece is independently usable and testable, and :func:`escalate` wires them
back together exactly as the pseudocode describes (and returns the full report):

    category = classify_failure(record)      # classify + record mutation (R12.3)
    report   = report_failure(record)        # build report; embeds STOP signal
    # or, equivalently, the full pipeline in one call:
    report   = escalate(record)              # classify -> stop -> report

Default classification heuristic (no explicit signal)
-----------------------------------------------------
The record does not carry every distinguishing signal (it cannot, for example,
tell "the element is genuinely absent" apart from "the reference image is
wrong"). So classification works from the inspectable signals that *are* on the
record, with an optional :class:`FailureSignal` override for the cases the
record cannot disambiguate:

- **No localization strategy and no verification verdict** ⇒ the target could
  not be resolved at all ⇒ ambiguity / missing information ⇒
  ``user_input_needed`` (design first branch: "unknown expected state, missing
  target").
- **Otherwise** (a strategy ran and/or a ``NO_OP_CLICK`` / ``WRONG_TARGET_CLICK``
  verdict was produced) ⇒ a locator/wait/assertion defect in the automation ⇒
  ``code_issue`` (design ``else`` branch, and the "usually ``code_issue``"
  verdict mapping).
- **``system_bug``** (element truly absent, app crashed, unexpected app state)
  cannot be inferred from the record alone, so it is selected only when the
  caller passes the corresponding :class:`FailureSignal`.

Passing a :class:`FailureSignal` always takes precedence over the heuristic,
giving the caller a deterministic way to express knowledge the record lacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Tuple

from .models import (
    FailureCategory,
    FinalStatus,
    InteractionRecord,
    LocalizationStrategy,
    Verdict,
)

__all__ = [
    "FlowControl",
    "FailureSignal",
    "FailureReport",
    "stop_current_flow",
    "classify_failure",
    "report_failure",
    "escalate",
]


# ---------------------------------------------------------------------------
# Flow-control signal
# ---------------------------------------------------------------------------


class FlowControl(str, Enum):
    """A returnable flow-control signal (R12.4).

    Modelled as a value rather than a real side effect so the escalation logic
    stays pure. Real planes interpret :attr:`STOP` as "halt the current flow and
    do not advance to the next step".
    """

    STOP = "stop"
    CONTINUE = "continue"


def stop_current_flow() -> FlowControl:
    """Signal that the current flow must stop (R12.4).

    Returns :attr:`FlowControl.STOP`. This is a pure, returnable signal: it does
    **not** exit the process, raise, print, or mutate any global state. The
    caller (or, in a real plane, the flow engine) is responsible for honouring
    the signal by halting execution.
    """

    return FlowControl.STOP


# ---------------------------------------------------------------------------
# Classification signals
# ---------------------------------------------------------------------------


class FailureSignal(str, Enum):
    """An optional, explicit classification hint for :func:`classify_failure`.

    The :class:`~desktop_reliability.models.InteractionRecord` cannot, on its
    own, distinguish every failure cause (notably it cannot prove an element is
    *genuinely* absent versus mis-located by a bad reference). When the caller
    has that knowledge, it passes the matching signal and classification becomes
    deterministic. Each member maps to exactly one
    :class:`~desktop_reliability.models.FailureCategory` (see
    :data:`_SIGNAL_CATEGORY`).
    """

    # -> user_input_needed (ambiguity / missing information)
    AMBIGUOUS_TARGET = "ambiguous_target"
    MISSING_INFORMATION = "missing_information"
    UNKNOWN_EXPECTED_STATE = "unknown_expected_state"

    # -> system_bug (defect in the application under test)
    ELEMENT_ABSENT = "element_absent"
    APPLICATION_CRASHED = "application_crashed"
    UNEXPECTED_APP_STATE = "unexpected_app_state"

    # -> code_issue (defect in the automation logic)
    LOCATOR_DEFECT = "locator_defect"
    WAIT_DEFECT = "wait_defect"
    ASSERTION_DEFECT = "assertion_defect"


#: Total mapping from every :class:`FailureSignal` to its category. Defined as a
#: complete mapping so signal-driven classification is exhaustive and total.
_SIGNAL_CATEGORY: Mapping[FailureSignal, FailureCategory] = {
    FailureSignal.AMBIGUOUS_TARGET: FailureCategory.USER_INPUT_NEEDED,
    FailureSignal.MISSING_INFORMATION: FailureCategory.USER_INPUT_NEEDED,
    FailureSignal.UNKNOWN_EXPECTED_STATE: FailureCategory.USER_INPUT_NEEDED,
    FailureSignal.ELEMENT_ABSENT: FailureCategory.SYSTEM_BUG,
    FailureSignal.APPLICATION_CRASHED: FailureCategory.SYSTEM_BUG,
    FailureSignal.UNEXPECTED_APP_STATE: FailureCategory.SYSTEM_BUG,
    FailureSignal.LOCATOR_DEFECT: FailureCategory.CODE_ISSUE,
    FailureSignal.WAIT_DEFECT: FailureCategory.CODE_ISSUE,
    FailureSignal.ASSERTION_DEFECT: FailureCategory.CODE_ISSUE,
}


# ---------------------------------------------------------------------------
# Failure report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FailureReport:
    """The escalation report emitted when an interaction is exhausted (R12.4).

    Carries the full diagnostics recorded on the interaction so a failure is
    traceable without re-deriving anything: the chosen category, the captured
    Pre/Post evidence paths, the localization strategy and confidence, and the
    verification verdict (R12.4, R12.5). ``flow_control`` records that the flow
    was signalled to stop (it is the value returned by :func:`stop_current_flow`).

    Immutable so a built report cannot drift from the record it was derived from.
    """

    step_id: str
    category: FailureCategory
    localization_strategy: Optional[LocalizationStrategy]
    confidence: Optional[float]
    verification: Optional[Verdict]
    pre_evidence: Tuple[str, ...] = field(default_factory=tuple)
    post_evidence: Tuple[str, ...] = field(default_factory=tuple)
    flow_control: FlowControl = FlowControl.STOP


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _decide_category(
    record: InteractionRecord,
    signal: Optional[FailureSignal],
) -> FailureCategory:
    """Decide exactly one category for an exhausted failure (R12.3).

    An explicit :class:`FailureSignal` always wins. With no signal, the decision
    is made deterministically from the inspectable record fields (see the module
    docstring for the full rationale).
    """

    if signal is not None:
        try:
            return _SIGNAL_CATEGORY[signal]
        except KeyError as exc:  # pragma: no cover - defensive; mapping is total
            raise ValueError(f"Unknown failure signal: {signal!r}") from exc

    # Default heuristic over inspectable record signals.
    if record.localization_strategy is None and record.verification is None:
        # The locator never produced a strategy and nothing was verified: the
        # target could not be resolved at all. Per the design's first branch
        # this is ambiguity / missing information (e.g. unknown/missing target).
        return FailureCategory.USER_INPUT_NEEDED

    # A localization strategy ran and/or a verdict (NO_OP_CLICK /
    # WRONG_TARGET_CLICK) was produced: this is a locator/wait/assertion defect
    # in the automation -> code_issue (the design's else branch).
    return FailureCategory.CODE_ISSUE


def classify_failure(
    record: InteractionRecord,
    signal: Optional[FailureSignal] = None,
) -> FailureCategory:
    """Classify an exhausted failure into exactly one category (R12.3).

    Assigns exactly one of :class:`~desktop_reliability.models.FailureCategory`
    (``CODE_ISSUE`` / ``SYSTEM_BUG`` / ``USER_INPUT_NEEDED``) based on the
    record's inspectable signals, with an optional :class:`FailureSignal`
    override for causes the record cannot disambiguate. As a side effect it
    records the chosen category on the interaction and marks it failed
    (``record.failure_category`` and ``record.final_status = FAILED``).

    A category is *always* returned (the function is total), so callers can rely
    on exactly one classification per exhausted interaction.

    :param record: the exhausted interaction record to classify.
    :param signal: optional explicit classification hint that overrides the
        default heuristic.
    :returns: the single :class:`~desktop_reliability.models.FailureCategory`.
    """

    category = _decide_category(record, signal)

    # Persist the classification on the record and mark the interaction failed.
    record.failure_category = category
    record.final_status = FinalStatus.FAILED

    return category


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def report_failure(
    record: InteractionRecord,
    category: Optional[FailureCategory] = None,
) -> FailureReport:
    """Build the escalation report from a classified record (R12.4, R12.5).

    Pure: it reads the diagnostics recorded on the interaction and returns an
    immutable :class:`FailureReport`. It performs no I/O — it does not print,
    log, or persist anything. The report embeds the flow-stop signal produced by
    :func:`stop_current_flow`, expressing that the flow was halted (R12.4).

    :param record: the interaction record (already classified by
        :func:`classify_failure`).
    :param category: the category to report; when omitted, the record's own
        ``failure_category`` is used.
    :raises ValueError: if no category is given and the record has not been
        classified yet.
    """

    resolved = category if category is not None else record.failure_category
    if resolved is None:
        raise ValueError(
            "Cannot report a failure before it is classified: pass a category "
            "or call classify_failure(record) first."
        )

    return FailureReport(
        step_id=record.step_id,
        category=resolved,
        localization_strategy=record.localization_strategy,
        confidence=record.confidence,
        verification=record.verification,
        pre_evidence=tuple(record.pre_evidence),
        post_evidence=tuple(record.post_evidence),
        flow_control=stop_current_flow(),
    )


def escalate(
    record: InteractionRecord,
    signal: Optional[FailureSignal] = None,
) -> FailureReport:
    """Run the full escalation pipeline and return the report (R12.3-R12.5).

    This is the design's single ``classify_failure(record)`` entry point with
    the three steps wired together: classify the failure (mutating the record),
    stop the current flow, and report with the captured evidence. Returns the
    :class:`FailureReport` (whose ``category`` is the chosen classification and
    whose ``flow_control`` is the ``STOP`` signal).

    :param record: the exhausted interaction record to escalate.
    :param signal: optional explicit classification hint (see
        :func:`classify_failure`).
    """

    category = classify_failure(record, signal)
    return report_failure(record, category)
