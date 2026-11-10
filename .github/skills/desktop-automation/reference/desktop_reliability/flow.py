"""Flow status aggregation for the desktop-reliability pattern.

This module implements the strict, no-false-positives aggregation rule for a
flow of interactions (R13.1, R13.2; design "Data Models" / Property 14):

    status = PASSED if every step's final_status == SUCCESS else FAILED

Partial verification is treated *identically* to complete failure: any single
unverified or failed interaction makes the whole flow ``FAILED``. This is the
desktop expression of the existing false-positive-prevention invariant — the
agent must never report a desktop flow as passed while any interaction is
unverified.

This module is *logic only* — no I/O, no screen/clock access.

Empty-flow behavior
-------------------
An empty flow (no steps) is reported as ``FAILED``, **not** ``PASSED``. A flow
with zero verified interactions has confirmed no real work, so treating it as a
passed flow of verified work would be a false positive — exactly what R13
forbids. Note that Python's ``all([])`` evaluates to ``True``, so the empty
case is handled *explicitly* rather than relying on ``all``.
"""

from __future__ import annotations

from typing import Iterable, List, Union

from .models import FinalStatus, FlowResult, FlowStatus, InteractionRecord

__all__ = [
    "aggregate_flow_status",
    "build_flow_result",
]


def _as_records(steps: Union[FlowResult, Iterable[InteractionRecord]]) -> List[InteractionRecord]:
    """Normalize the accepted inputs to a concrete list of records.

    Accepts either a :class:`FlowResult` (its ``steps`` are used) or any
    iterable of :class:`InteractionRecord`.
    """

    if isinstance(steps, FlowResult):
        return list(steps.steps)
    return list(steps)


def aggregate_flow_status(
    steps: Union[FlowResult, Iterable[InteractionRecord]],
) -> FlowStatus:
    """Aggregate per-step results into a single flow status (R13.1, R13.2).

    Returns :attr:`FlowStatus.PASSED` if and only if there is at least one step
    and *every* step has ``final_status == FinalStatus.SUCCESS``. In all other
    cases — any non-SUCCESS (unverified/failed) step, or an empty flow — returns
    :attr:`FlowStatus.FAILED`. Partial verification is treated identically to
    complete failure.

    :param steps: a :class:`FlowResult` or an iterable of
        :class:`InteractionRecord`.
    """

    records = _as_records(steps)

    # Explicit empty-flow handling: zero verified steps is FAILED, never PASSED
    # (a flow of no verified work must not be reported as a passed flow). Do not
    # rely on ``all([]) is True`` here.
    if not records:
        return FlowStatus.FAILED

    if all(record.final_status == FinalStatus.SUCCESS for record in records):
        return FlowStatus.PASSED
    return FlowStatus.FAILED


def build_flow_result(
    steps: Union[FlowResult, Iterable[InteractionRecord]],
) -> FlowResult:
    """Build a :class:`FlowResult` with its aggregated status (R13.2).

    Convenience wrapper around :func:`aggregate_flow_status`: materializes the
    steps and sets ``status`` to the aggregated value so the result can never
    drift from its constituent steps.

    :param steps: a :class:`FlowResult` or an iterable of
        :class:`InteractionRecord`.
    """

    records = _as_records(steps)
    return FlowResult(steps=records, status=aggregate_flow_status(records))
