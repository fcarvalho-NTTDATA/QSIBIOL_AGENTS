"""Property-based test for Property 13 (failure classification + escalation).

# Feature: desktop-automation-reliability, Property 13: Exhausted failures are classified into exactly one category and stop the flow with evidence

Property 13: Exhausted failures are classified into exactly one category and
stop the flow with evidence.

*For any* interaction that remains failed after the maximum re-attempts, the
Failure-Handler assigns exactly one of ``code_issue``, ``system_bug``, or
``user_input_needed``, stops the current flow, and reports the failure together
with the captured Pre_Action_State and Post_Action_State evidence.

**Validates: Requirements 12.3, 12.4**

Implementation under test: ``desktop_reliability.failure`` — the
``classify_failure`` / ``stop_current_flow`` / ``report_failure`` pipeline wired
together by ``escalate`` (the design's single ``classify_failure(record)`` entry
point). The test drives that pipeline over a wide space of exhausted
:class:`InteractionRecord` values (varying localization strategy, confidence,
verification verdict, evidence paths) and over the optional explicit
:class:`FailureSignal` override, asserting the three invariants of Property 13:

1. **Exactly one category** — the report carries a single member of the
   ``{code_issue, system_bug, user_input_needed}`` set (R12.3).
2. **Stops the flow** — the report's flow-control signal is ``STOP`` (R12.4).
3. **Reports with evidence** — the captured Pre/Post evidence paths are carried
   through into the report unchanged (R12.4).

No real desktop, clock, or filesystem is needed: the failure handler is pure
logic over the record.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    FailureCategory,
    FailureSignal,
    FinalStatus,
    FlowControl,
    InteractionRecord,
    LocalizationStrategy,
    Verdict,
    classify_failure,
    escalate,
    stop_current_flow,
)

# The three (and only three) categories an exhausted failure may be assigned.
_CATEGORIES = (
    FailureCategory.CODE_ISSUE,
    FailureCategory.SYSTEM_BUG,
    FailureCategory.USER_INPUT_NEEDED,
)

# A non-confirming verdict (or none): an *exhausted* failure never carries a
# CONFIRMED verdict (that would be a success, not a failure to escalate).
_FAILED_VERDICTS = (None, Verdict.NO_OP_CLICK, Verdict.WRONG_TARGET_CLICK)

# Localization strategy may be absent (target never resolved) or any ranked one.
_STRATEGY_CHOICES = (None,) + tuple(LocalizationStrategy)

# Optional explicit classification hint: none, or any defined signal.
_SIGNAL_CHOICES = (None,) + tuple(FailureSignal)


def _evidence_paths(phase: str) -> st.SearchStrategy[list[str]]:
    """Generate a (possibly empty) list of evidence paths under ``evidences/``.

    Models the captured Pre/Post state paths recorded on an interaction; the
    exact strings only need to round-trip through the report unchanged.
    """

    segment = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
        min_size=1,
        max_size=12,
    )
    one_path = st.builds(
        lambda name, attempt: f"evidences/{name}_{phase}_attempt{attempt}.png",
        segment,
        st.integers(min_value=1, max_value=3),
    )
    return st.lists(one_path, min_size=0, max_size=4)


@st.composite
def exhausted_records(draw: st.DrawFn) -> InteractionRecord:
    """Build an exhausted :class:`InteractionRecord` to be escalated.

    Constrained to the realistic input space of a failure that has run out of
    re-attempts: a step id, up to ``max_interaction_attempts`` (3) attempts, an
    optional localization strategy and confidence in ``[0, 1]``, a
    non-confirming verification verdict (or none), and captured Pre/Post
    evidence paths.
    """

    return InteractionRecord(
        step_id=draw(st.text(min_size=1, max_size=20)),
        attempts=draw(st.integers(min_value=1, max_value=3)),
        localization_strategy=draw(st.sampled_from(_STRATEGY_CHOICES)),
        confidence=draw(
            st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0))
        ),
        verification=draw(st.sampled_from(_FAILED_VERDICTS)),
        pre_evidence=draw(_evidence_paths("pre")),
        post_evidence=draw(_evidence_paths("post")),
    )


# Feature: desktop-automation-reliability, Property 13: Exhausted failures are classified into exactly one category and stop the flow with evidence
@settings(max_examples=200)
@given(record=exhausted_records(), signal=st.sampled_from(_SIGNAL_CHOICES))
def test_property_13_exhausted_failure_classified_stops_flow_with_evidence(
    record: InteractionRecord,
    signal: FailureSignal | None,
) -> None:
    """Validates: Requirements 12.3, 12.4.

    Every exhausted failure is assigned exactly one category, stops the flow,
    and is reported together with its captured Pre/Post evidence.
    """

    # Snapshot the captured evidence before escalation so we can prove the
    # report carries it through unchanged.
    expected_pre = tuple(record.pre_evidence)
    expected_post = tuple(record.post_evidence)

    report = escalate(record, signal)

    # 1. Classified into EXACTLY ONE of the three categories (R12.3). Summing
    #    equality across the three categories proves both membership and mutual
    #    exclusivity (exactly one match).
    assert isinstance(report.category, FailureCategory)
    assert sum(report.category == category for category in _CATEGORIES) == 1
    # The classification is persisted on the record and the interaction is
    # marked failed.
    assert record.failure_category == report.category
    assert record.final_status == FinalStatus.FAILED
    # An explicit signal selects the category deterministically (same signal on
    # a fresh record yields the same single category).
    if signal is not None:
        assert classify_failure(InteractionRecord(step_id="probe"), signal) == (
            report.category
        )

    # 2. The current flow is stopped (R12.4).
    assert report.flow_control == FlowControl.STOP
    assert stop_current_flow() == FlowControl.STOP

    # 3. The failure is reported together with the captured Pre/Post evidence
    #    (R12.4) plus the recorded diagnostics, all carried through unchanged.
    assert report.pre_evidence == expected_pre
    assert report.post_evidence == expected_post
    assert report.step_id == record.step_id
    assert report.localization_strategy == record.localization_strategy
    assert report.confidence == record.confidence
    assert report.verification == record.verification
