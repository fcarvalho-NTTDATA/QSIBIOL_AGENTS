"""Property-based test for Property 3: ordered, step-identified evidence.

# Feature: desktop-automation-reliability, Property 3: Every interaction captures ordered, step-identified evidence

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

Property 3 (design "Correctness Properties"):

    For any interaction, the routine records a Pre_Action_State strictly before
    performing the action and a Post_Action_State after it, accepts the
    post-state even when its capture latency exceeds the 2000 ms target, and
    stores both captures at paths rooted under ``<project-root>/evidences/``
    whose names include the interaction's step identifier.

The test exercises :func:`verified_interaction` (Component 1,
``interaction.py``) end to end with **all side-effecting dependencies injected**
so capture/store ordering is observable and **no real file I/O occurs**:

* a *recording interaction performer* (``perform``) appends an ``"action"``
  marker to a shared event log when the click/type is executed, and
* a *recording evidence writer* (``writer``) appends a ``"pre_store"`` /
  ``"post_store"`` marker (keyed off the ``_pre.png`` / ``_post.png`` suffix the
  evidence store puts in the file name) instead of touching the filesystem.

Because the store of each capture is what *records* the evidence, the relative
order of the ``pre_store`` / ``action`` / ``post_store`` markers in that single
shared log is exactly the "pre strictly before the action, post after it"
ordering the property asserts (R1.1/R1.2).

A controllable :class:`FakeClock` simulates a slow post-capture: the first
capture taken *after* the action advances the virtual clock by a drawn latency,
which the late-capture facets push above the 2000 ms target
(``ReliabilityConfig.post_capture_target_ms``) to prove the post-state is still
accepted and verification still proceeds (R1.3).

The oracle is **independent**: the expected event order, the expected evidence
directory (``<project-root>/evidences``), and the expected file names
(``<step>_attempt1_<phase>.png``) are all recomputed directly from the generated
inputs and the property's specification — never by calling the evidence store's
own :func:`evidence_path` / :func:`sanitize_step_id`. Step identifiers are
constrained to the filesystem-safe alphabet so they appear verbatim in the path.

Everything is logic-only with mocked screen/clock/focus and no real desktop,
sleeps, or disk writes.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from hypothesis import example, given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    FULL_SCREEN,
    Action,
    ExpectedOutcome,
    FakeClock,
    FakeFocusManager,
    FakeImageMatcher,
    FakeOcrProvider,
    FakeScreen,
    InteractionStep,
    ReliabilityConfig,
    TargetElement,
    Verdict,
    WindowRef,
    verified_interaction,
)

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# The post-capture latency target (ms) the implementation is allowed to exceed
# without invalidating the evidence (R1.2/R1.3). Read from the config so the
# test tracks the canonical constant rather than a magic number.
POST_CAPTURE_TARGET_MS = ReliabilityConfig().post_capture_target_ms  # 2000

# Distinct, hashable "frame" tokens. Localization here uses the ABSOLUTE
# strategy (see ``_run``), which never inspects the frame, so the frame content
# only needs to drive the expected-outcome predicate for verification.
PRE_FRAME = "PRE"
POST_FRAME = "POST"


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


def _step_ids() -> st.SearchStrategy:
    """Step identifiers over the filesystem-safe alphabet ``[A-Za-z0-9._-]``.

    The first character is alphanumeric so the identifier is non-empty and is
    the *identity* under the evidence store's sanitization, which means the raw
    step id appears verbatim in the evidence file name (R1.4) — letting the
    oracle assert ``step_id in path.name`` and the exact file name.
    """

    return st.from_regex(r"[A-Za-z0-9][A-Za-z0-9._-]{0,19}", fullmatch=True)


def _points() -> st.SearchStrategy:
    """A recorded absolute coordinate the ABSOLUTE strategy resolves to."""

    return st.tuples(
        st.integers(min_value=-2000, max_value=2000),
        st.integers(min_value=-2000, max_value=2000),
    )


# ---------------------------------------------------------------------------
# Harness: run one verified_interaction with fully injected, recording deps.
# ---------------------------------------------------------------------------


def _run(step_id, action, absolute_point, post_latency_seconds, project_root):
    """Drive one :func:`verified_interaction` with recording, no-I/O dependencies.

    Returns ``(result, events, clock)`` where ``events`` is the shared,
    time-ordered log of ``("pre_store", path)`` / ``("action", point)`` /
    ``("post_store", path)`` markers.

    The target carries *only* an absolute coordinate, so localization resolves
    via the ABSOLUTE strategy on attempt 1 (every higher-ranked strategy is
    inapplicable and reports no match), and the expected-outcome predicate holds
    on the post-state, so verification confirms immediately on the first check
    — giving a deterministic single-attempt success with exactly one pre-store,
    one action, and one post-store to assert ordering against.
    """

    config = ReliabilityConfig()
    clock = FakeClock()
    events: list = []
    state = {"action_done": False, "post_captured": False}

    # The locate capture (between pre and post) returns the default; only the
    # pre capture returns PRE_FRAME, and every post/recapture returns POST_FRAME.
    screen = FakeScreen(frames=[PRE_FRAME], default=POST_FRAME)

    def capture(region):
        frame = screen.capture(region)
        # The first capture taken *after* the action is the post-capture; model
        # its latency by advancing the virtual clock (R1.2/R1.3). Using
        # ``advance`` (not ``sleep``) keeps it out of the backoff bookkeeping.
        if state["action_done"] and not state["post_captured"]:
            state["post_captured"] = True
            clock.advance(post_latency_seconds)
        return frame

    def perform(action_arg, point):
        state["action_done"] = True
        events.append(("action", point))

    def writer(capture_obj, path):
        # Recording, no-I/O evidence writer: classify the store by the phase
        # suffix the evidence store puts in the file name (R1.4). No file is
        # ever written.
        name = Path(path).name
        if name.endswith("_pre.png"):
            events.append(("pre_store", str(path)))
        elif name.endswith("_post.png"):
            events.append(("post_store", str(path)))

    target = TargetElement(absolute=absolute_point)
    step = InteractionStep(
        id=step_id,
        target=target,
        action=action,
        target_window=WindowRef(id=1, title="App", origin=(0, 0)),
        verification_region=FULL_SCREEN,
    )
    expected = ExpectedOutcome(
        description="post-state equals the expected post frame",
        predicate=lambda s: s == POST_FRAME,
        region=FULL_SCREEN,
    )

    result = verified_interaction(
        step,
        expected,
        config,
        capture=capture,
        perform_interaction=perform,
        image_matcher=FakeImageMatcher(),
        ocr_provider=FakeOcrProvider(),
        focus_manager=FakeFocusManager(),
        clock=clock,
        project_root=project_root,
        evidence_writer=writer,
    )
    return result, events, clock


# ---------------------------------------------------------------------------
# Property 3 - ordered, step-identified evidence (with late-capture coverage)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES, deadline=None)
@given(
    step_id=_step_ids(),
    action=st.sampled_from(list(Action)),
    absolute_point=_points(),
    post_latency_ms=st.integers(min_value=0, max_value=6000),
)
# Force the late-capture edge case: a post-capture whose latency exceeds the
# 2000 ms target must still be accepted (R1.3).
@example(
    step_id="login_button",
    action=Action.CLICK,
    absolute_point=(10, 20),
    post_latency_ms=POST_CAPTURE_TARGET_MS + 500,
)
def test_property_03_ordered_step_identified_evidence(
    step_id, action, absolute_point, post_latency_ms
):
    # Feature: desktop-automation-reliability, Property 3: Every interaction captures ordered, step-identified evidence
    project_root = "fake_project_root"
    result, events, clock = _run(
        step_id, action, absolute_point, post_latency_ms / 1000.0, project_root
    )

    # The interaction is a verified, evidence-backed success on attempt 1.
    assert result.succeeded
    assert result.record.verification is Verdict.CONFIRMED
    assert result.record.attempts == 1
    assert len(result.record.pre_evidence) == 1
    assert len(result.record.post_evidence) == 1

    # --- Ordering (R1.1/R1.2): pre recorded strictly before the action, post
    # after it. The shared event log is the independent observation. ---
    kinds = [kind for kind, _ in events]
    assert kinds.count("pre_store") == 1
    assert kinds.count("action") == 1
    assert kinds.count("post_store") == 1

    pre_idx = kinds.index("pre_store")
    action_idx = kinds.index("action")
    post_idx = kinds.index("post_store")
    assert pre_idx < action_idx, "Pre_Action_State must be recorded before the action"
    assert action_idx < post_idx, "Post_Action_State must be recorded after the action"
    # Independent oracle for the full ordering of the recorded sequence.
    assert kinds == ["pre_store", "action", "post_store"]

    # The recorded markers correspond to the evidence paths on the record.
    pre_path = events[pre_idx][1]
    post_path = events[post_idx][1]
    action_point = events[action_idx][1]
    assert pre_path == result.record.pre_evidence[0]
    assert post_path == result.record.post_evidence[0]
    # The action was performed at the resolved (absolute) point.
    assert action_point == absolute_point

    # --- Late-capture acceptance (R1.3): the post-state is accepted even when
    # its capture latency exceeds the 2000 ms target. ---
    if post_latency_ms > POST_CAPTURE_TARGET_MS:
        # The post-capture latency exceeded the target...
        assert clock.now() * 1000 > POST_CAPTURE_TARGET_MS
    # ...and regardless of latency the post-state was still stored and confirmed.
    assert result.record.post_evidence

    # --- Step-identified paths under <project-root>/evidences/ (R1.4). ---
    # Independent oracle: recompute the expected evidence directory and file
    # names directly from the inputs (never via the store's own helpers).
    evidences_root = Path(project_root) / "evidences"
    for phase, paths in (
        ("pre", result.record.pre_evidence),
        ("post", result.record.post_evidence),
    ):
        for raw in paths:
            path = Path(raw)
            # Rooted under <project-root>/evidences/.
            assert path.parent == evidences_root
            assert "evidences" in path.parts
            # File name includes the step identifier (verbatim for the safe
            # alphabet) and matches the canonical naming scheme.
            assert step_id in path.name
            assert path.name == f"{step_id}_attempt1_{phase}.png"


# ---------------------------------------------------------------------------
# Focused late-capture edge case (deterministic, also asserts no real file I/O)
# ---------------------------------------------------------------------------


def test_property_03_late_post_capture_is_accepted():
    # Feature: desktop-automation-reliability, Property 3: Every interaction captures ordered, step-identified evidence
    """A post-capture slower than the 2000 ms target is still accepted (R1.3).

    The post-capture advances the virtual clock by 3500 ms (well past the
    2000 ms target), yet the post-state is still stored and verification still
    confirms — and, because the evidence writer is injected, no real file I/O
    occurs (the ``evidences/`` directory is never created on disk).
    """

    late_seconds = (POST_CAPTURE_TARGET_MS + 1500) / 1000.0  # 3.5s > 2.0s target
    project_root = f"fake_project_root_{uuid4().hex}"

    result, events, clock = _run(
        "save_button", Action.CLICK, (5, 5), late_seconds, project_root
    )

    # The late post-state was accepted: evidence recorded and outcome confirmed.
    assert result.succeeded
    assert result.record.verification is Verdict.CONFIRMED
    assert len(result.record.post_evidence) == 1

    # The post-capture latency genuinely exceeded the 2000 ms target.
    assert clock.now() * 1000 > POST_CAPTURE_TARGET_MS

    # Ordering held even with the slow post-capture.
    assert [kind for kind, _ in events] == ["pre_store", "action", "post_store"]

    # No real file I/O: the injected writer captured the stores and the real
    # evidence directory was never created.
    assert not (Path(project_root) / "evidences").exists()
