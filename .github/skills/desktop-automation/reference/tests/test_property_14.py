"""Property-based test for flow status aggregation (Property 14).

# Feature: desktop-automation-reliability, Property 14: Flow status passes only when every step is verified

Validates: Requirements 13.2

Property 14 (design "Correctness Properties"):

    For any flow composed of interaction results, the reported flow status is
    ``PASSED`` if and only if every step has status ``SUCCESS``; if any
    interaction is unverified or failed, the flow status is ``FAILED`` (partial
    verification is treated identically to complete failure).

This exercises ``aggregate_flow_status`` / ``build_flow_result`` in
``desktop_reliability.flow`` over many randomly-generated flows.

Oracle
------
The aggregation is *logic only*: it depends solely on each step's
``final_status``. The reference implementation (and the design module
docstring) make the no-false-positives rule explicit:

    status == PASSED  iff  there is at least one step AND every step is SUCCESS
    status == FAILED  otherwise (any non-SUCCESS step, or an empty flow)

An empty flow has confirmed no verified work, so reporting it as ``PASSED``
would be a false positive — exactly what R13 forbids. The oracle below encodes
this directly so "every step SUCCESS" is evaluated against real, present steps.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    FinalStatus,
    FlowResult,
    FlowStatus,
    InteractionRecord,
    Verdict,
    aggregate_flow_status,
    build_flow_result,
)


# ---------------------------------------------------------------------------
# Smart generators: build realistic InteractionRecords across the input space.
# Aggregation depends only on ``final_status``, so the generator deliberately
# samples both terminal states uniformly and pairs FAILED steps with a
# realistic "unverified or non-confirming" verification result.
# ---------------------------------------------------------------------------

# A bounded pool of step ids so flows can contain repeated/realistic ids.
_step_ids = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
    min_size=1,
    max_size=12,
)


@st.composite
def interaction_records(draw: st.DrawFn) -> InteractionRecord:
    """Generate an :class:`InteractionRecord` with a realistic terminal state.

    ``final_status`` is sampled uniformly from {SUCCESS, FAILED}. A SUCCESS
    step carries a CONFIRMED verdict; a FAILED step carries either an
    unverified result (``None``) or a non-confirming verdict (No-op /
    Wrong-target) — modeling "unverified or failed" from Property 14.
    """

    final_status = draw(st.sampled_from(list(FinalStatus)))
    step_id = draw(_step_ids)
    attempts = draw(st.integers(min_value=1, max_value=3))

    if final_status == FinalStatus.SUCCESS:
        verification = Verdict.CONFIRMED
    else:
        verification = draw(
            st.sampled_from([None, Verdict.NO_OP_CLICK, Verdict.WRONG_TARGET_CLICK])
        )

    return InteractionRecord(
        step_id=step_id,
        attempts=attempts,
        verification=verification,
        final_status=final_status,
    )


def _expected_status(records: list[InteractionRecord]) -> FlowStatus:
    """Independent oracle for Property 14 (no false positives on empty flows)."""

    if records and all(r.final_status == FinalStatus.SUCCESS for r in records):
        return FlowStatus.PASSED
    return FlowStatus.FAILED


# ---------------------------------------------------------------------------
# Property 14
# ---------------------------------------------------------------------------


# Feature: desktop-automation-reliability, Property 14: Flow status passes only when every step is verified
@settings(max_examples=200)
@given(records=st.lists(interaction_records(), min_size=0, max_size=20))
def test_flow_status_passes_only_when_every_step_is_verified(records):
    """PASSED iff every (present) step is SUCCESS; any non-SUCCESS step => FAILED."""

    status = aggregate_flow_status(records)

    # Core biconditional: status is PASSED exactly when the flow is non-empty
    # and every step succeeded.
    every_step_success = bool(records) and all(
        r.final_status == FinalStatus.SUCCESS for r in records
    )
    assert (status == FlowStatus.PASSED) == every_step_success
    assert status == _expected_status(records)

    # Status is always exactly one of the two terminal values.
    assert status in (FlowStatus.PASSED, FlowStatus.FAILED)

    # Partial verification is treated identically to complete failure: if any
    # single step is unverified/failed, the whole flow is FAILED.
    if any(r.final_status != FinalStatus.SUCCESS for r in records):
        assert status == FlowStatus.FAILED


# Feature: desktop-automation-reliability, Property 14: Flow status passes only when every step is verified
@settings(max_examples=200)
@given(records=st.lists(interaction_records(), min_size=0, max_size=20))
def test_build_flow_result_status_matches_aggregation(records):
    """``build_flow_result`` can never drift from ``aggregate_flow_status`` (R13.2)."""

    result = build_flow_result(records)
    assert isinstance(result, FlowResult)
    assert result.status == aggregate_flow_status(records)
    assert list(result.steps) == list(records)
    # Accepting a FlowResult as input reproduces the same aggregated status.
    assert aggregate_flow_status(result) == result.status


# Feature: desktop-automation-reliability, Property 14: Flow status passes only when every step is verified
@settings(max_examples=200)
@given(
    successes=st.lists(
        interaction_records().filter(
            lambda r: r.final_status == FinalStatus.SUCCESS
        ),
        min_size=1,
        max_size=15,
    ),
    failure=interaction_records().filter(
        lambda r: r.final_status == FinalStatus.FAILED
    ),
    insert_at=st.integers(min_value=0, max_value=15),
)
def test_single_unverified_step_forces_failed_regardless_of_position(
    successes, failure, insert_at
):
    """An all-SUCCESS flow is PASSED, but inserting one FAILED step anywhere => FAILED."""

    # An all-success, non-empty flow passes.
    assert aggregate_flow_status(successes) == FlowStatus.PASSED

    # Injecting a single failed/unverified step at any position flips it.
    position = insert_at % (len(successes) + 1)
    contaminated = successes[:position] + [failure] + successes[position:]
    assert aggregate_flow_status(contaminated) == FlowStatus.FAILED
