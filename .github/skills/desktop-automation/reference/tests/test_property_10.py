"""Property-based test for Property 10: window-origin + scaling resolution.

# Feature: desktop-automation-reliability, Property 10: Coordinates are resolved relative to window origin and adjusted for scaling

**Validates: Requirements 10.2, 10.3, 11.3**

Property 10 (design "Correctness Properties"):

    For any window origin, scaling factor, and recorded position, the resolved
    interaction point equals the position computed relative to the current
    window origin and adjusted by the active scaling factor; when the
    execution-time resolution or scaling differs from the exploration-time
    values, the position is recomputed using the execution-time values, and the
    transform is the identity when execution-time and exploration-time
    environments are equal.

This exercises the Element_Locator coordinate math (Component 2, ``locator.py``):

* :func:`window_relative` — the WINDOW_RELATIVE strategy primitive that resolves
  a point as ``window_origin + adjusted(win_offset)`` (R11.3).
* :func:`normalize_for_scaling` — the execution-vs-exploration recompute used by
  the coordinate strategies (R10.2/R10.3): identity when the environments are
  equal, otherwise scale the recorded position by the execution-time ratio.
* :func:`absolute` / :func:`scale_point` — the last-resort scaled coordinate and
  the raw "adjust by the active scaling factor" operation, included so the 100%
  vs non-100% scaling clause is covered directly.

Every assertion is checked against an **independent oracle** that recomputes the
expected point directly from the window origin, the recorded offset, and the
scaling ratio. The oracle never calls the functions under test
(``window_relative`` / ``normalize_for_scaling`` / ``absolute``); it re-derives
the spec formula in the test, so the test cannot tautologically agree with the
implementation.

Everything is logic-only coordinate math with no real desktop, screen, or clock.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    LocalizationStrategy,
    SessionEnvironment,
    TargetElement,
    WindowRef,
    absolute,
    normalize_for_scaling,
    run_strategy,
    scale_point,
    window_origin,
    window_relative,
)
from desktop_reliability import ReliabilityConfig
from desktop_reliability.fakes import FakeImageMatcher, FakeOcrProvider

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# Scaling factors as OS-reported percentages. The pool deliberately includes
# 100 (identity scaling) and several non-100 values so both the "100% scaling"
# and "non-100% scaling" cases in Property 10 are exercised across the run.
_SCALING_FACTORS = st.sampled_from([100, 125, 150, 175, 200, 250])

# A small pool of common display resolutions; equal vs. different resolutions
# both occur frequently across generated examples.
_RESOLUTIONS = st.sampled_from(
    [(1280, 720), (1366, 768), (1920, 1080), (2560, 1440), (3840, 2160)]
)

# Coordinate components for origins and offsets (offsets may be negative).
_ORIGIN_COORD = st.integers(min_value=0, max_value=4000)
_OFFSET_COORD = st.integers(min_value=-2000, max_value=2000)
_POINTS = st.tuples(_OFFSET_COORD, _OFFSET_COORD)
_ORIGINS = st.tuples(_ORIGIN_COORD, _ORIGIN_COORD)


# ---------------------------------------------------------------------------
# Independent oracle (re-derives the spec formula; never calls the SUT)
# ---------------------------------------------------------------------------


def _environments_equal(session: SessionEnvironment) -> bool:
    """Oracle: are the execution-time and exploration-time environments equal?

    Equal means both the scaling factor and the resolution match between
    execution and exploration (R10.3 "equal environments").
    """

    return (
        session.scaling_factor == session.exploration_scaling
        and session.resolution == session.exploration_resolution
    )


def _oracle_adjust(point, session: SessionEnvironment):
    """Oracle recompute of a recorded ``point`` for the execution environment.

    Identity when the environments are equal (R10.3); otherwise scale by the
    execution-time ratio ``scaling_factor / exploration_scaling`` and round to
    the nearest pixel (R10.2/R10.3 "recompute using the execution-time values").
    """

    if _environments_equal(session):
        return point
    ratio = session.scaling_factor / session.exploration_scaling
    return (round(point[0] * ratio), round(point[1] * ratio))


def _oracle_window_point(origin, offset, session):
    """Oracle: resolved window-relative point = origin + adjusted(offset)."""

    adjusted = _oracle_adjust(offset, session)
    return (origin[0] + adjusted[0], origin[1] + adjusted[1])


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def _sessions(draw, *, force_equal=None):
    """Generate a :class:`SessionEnvironment`.

    ``force_equal=True`` pins execution to exploration (equal environments);
    ``force_equal=False`` guarantees a mismatch in scaling and/or resolution;
    ``None`` lets either occur. The scaling pool includes 100% and non-100%.
    """

    explore_scaling = draw(_SCALING_FACTORS)
    explore_res = draw(_RESOLUTIONS)

    if force_equal is True:
        exec_scaling = explore_scaling
        exec_res = explore_res
    elif force_equal is False:
        # Guarantee at least one of (scaling, resolution) differs.
        differ_scaling = draw(st.booleans())
        if differ_scaling:
            exec_scaling = draw(_SCALING_FACTORS.filter(lambda s: s != explore_scaling))
            exec_res = explore_res if draw(st.booleans()) else draw(_RESOLUTIONS)
        else:
            exec_scaling = explore_scaling
            exec_res = draw(_RESOLUTIONS.filter(lambda r: r != explore_res))
    else:
        exec_scaling = draw(_SCALING_FACTORS)
        exec_res = draw(_RESOLUTIONS)

    return SessionEnvironment(
        resolution=exec_res,
        scaling_factor=exec_scaling,
        exploration_resolution=explore_res,
        exploration_scaling=explore_scaling,
    )


# ---------------------------------------------------------------------------
# Property 10 - window-relative resolution = origin + scaling-adjusted offset
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(origin=_ORIGINS, offset=_POINTS, session=_sessions())
def test_property_10_window_relative_resolved_point(origin, offset, session):
    # Feature: desktop-automation-reliability, Property 10: Coordinates are resolved relative to window origin and adjusted for scaling
    target = TargetElement(window=WindowRef(origin=origin), win_offset=offset)

    result = window_relative(target, session=session)

    # The strategy is applicable, so it produces a point at full confidence.
    assert result.matched is True
    assert result.confidence == 1.0

    # Independent oracle: point relative to the current window origin, adjusted
    # for the active scaling factor (R11.3 + R10.2/R10.3).
    assert result.point == _oracle_window_point(origin, offset, session)

    # And the resolved point is anchored at the window origin: removing the
    # adjusted offset returns the origin exactly.
    adjusted = _oracle_adjust(offset, session)
    assert result.point == (origin[0] + adjusted[0], origin[1] + adjusted[1])


@settings(max_examples=MAX_EXAMPLES)
@given(origin=_ORIGINS, offset=_POINTS, session=_sessions())
def test_property_10_window_relative_via_dispatch_matches(origin, offset, session):
    # Feature: desktop-automation-reliability, Property 10: Coordinates are resolved relative to window origin and adjusted for scaling
    # Routing the WINDOW_RELATIVE strategy through run_strategy resolves the same
    # window-origin-relative, scaling-adjusted point as the primitive (R11.3).
    target = TargetElement(window=WindowRef(origin=origin), win_offset=offset)

    dispatched = run_strategy(
        LocalizationStrategy.WINDOW_RELATIVE,
        target,
        frame=None,
        config=ReliabilityConfig(),
        image_matcher=FakeImageMatcher(),
        ocr_provider=FakeOcrProvider(),
        session=session,
    )

    assert dispatched.matched is True
    assert dispatched.point == _oracle_window_point(origin, offset, session)


# ---------------------------------------------------------------------------
# Property 10 - identity transform when the environments are equal
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(origin=_ORIGINS, offset=_POINTS, point=_POINTS, session=_sessions(force_equal=True))
def test_property_10_identity_when_environments_equal(origin, offset, point, session):
    # Feature: desktop-automation-reliability, Property 10: Coordinates are resolved relative to window origin and adjusted for scaling
    # Equal execution/exploration environments => the scaling transform is the
    # identity (R10.3): the recorded position is returned unchanged.
    assert _environments_equal(session)
    assert normalize_for_scaling(point, session) == point

    # Window-relative resolution therefore equals a plain origin + offset, with
    # no scaling adjustment applied.
    target = TargetElement(window=WindowRef(origin=origin), win_offset=offset)
    result = window_relative(target, session=session)
    assert result.point == (origin[0] + offset[0], origin[1] + offset[1])

    # The last-resort absolute strategy is likewise unscaled under equal envs.
    abs_target = TargetElement(absolute=point)
    assert absolute(abs_target, session=session).point == point


# ---------------------------------------------------------------------------
# Property 10 - recompute using execution-time values on a mismatch
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(origin=_ORIGINS, offset=_POINTS, point=_POINTS, session=_sessions(force_equal=False))
def test_property_10_recompute_on_mismatch_uses_execution_values(origin, offset, point, session):
    # Feature: desktop-automation-reliability, Property 10: Coordinates are resolved relative to window origin and adjusted for scaling
    # When execution-time resolution or scaling differs from exploration-time,
    # the position is recomputed using the execution-time values (R10.2/R10.3).
    assert not _environments_equal(session)

    expected_ratio = session.scaling_factor / session.exploration_scaling
    expected_point = (round(point[0] * expected_ratio), round(point[1] * expected_ratio))
    assert normalize_for_scaling(point, session) == expected_point

    # The window-relative resolution recomputes the offset with the same
    # execution-time ratio before adding the current window origin.
    target = TargetElement(window=WindowRef(origin=origin), win_offset=offset)
    assert window_relative(target, session=session).point == _oracle_window_point(
        origin, offset, session
    )


@settings(max_examples=MAX_EXAMPLES)
@given(
    point=_POINTS,
    explore_scaling=_SCALING_FACTORS,
    exec_a=_SCALING_FACTORS,
    exec_b=_SCALING_FACTORS,
    resolution=_RESOLUTIONS,
)
def test_property_10_recompute_tracks_execution_scaling(
    point, explore_scaling, exec_a, exec_b, resolution
):
    # Feature: desktop-automation-reliability, Property 10: Coordinates are resolved relative to window origin and adjusted for scaling
    # The recompute is driven by the *execution-time* scaling: two sessions that
    # share the exploration baseline but differ only in execution scaling must
    # produce points consistent with their own execution ratios (R10.3).
    session_a = SessionEnvironment(
        resolution=resolution,
        scaling_factor=exec_a,
        exploration_resolution=resolution,
        exploration_scaling=explore_scaling,
    )
    session_b = SessionEnvironment(
        resolution=resolution,
        scaling_factor=exec_b,
        exploration_resolution=resolution,
        exploration_scaling=explore_scaling,
    )

    assert normalize_for_scaling(point, session_a) == _oracle_adjust(point, session_a)
    assert normalize_for_scaling(point, session_b) == _oracle_adjust(point, session_b)


# ---------------------------------------------------------------------------
# Property 10 - 100% and non-100% scaling both adjust by the active factor
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(point=_POINTS, scaling=_SCALING_FACTORS, resolution=_RESOLUTIONS)
def test_property_10_active_scaling_factor_from_100_baseline(point, scaling, resolution):
    # Feature: desktop-automation-reliability, Property 10: Coordinates are resolved relative to window origin and adjusted for scaling
    # With exploration recorded at 100%, recomputing for the execution-time
    # scaling is exactly "adjust by the active scaling factor" (R10.2). This
    # covers the 100% case (identity) and every non-100% case in one assertion.
    session = SessionEnvironment(
        resolution=resolution,
        scaling_factor=scaling,
        exploration_resolution=resolution,
        exploration_scaling=100,
    )

    # Independent oracle: scale each component by the active factor / 100.
    ratio = scaling / 100.0
    expected = (round(point[0] * ratio), round(point[1] * ratio))

    # normalize_for_scaling against a 100% baseline equals the raw scale_point.
    assert normalize_for_scaling(point, session) == expected
    assert scale_point(point, scaling) == expected

    if scaling == 100:
        # 100% scaling is always the identity.
        assert normalize_for_scaling(point, session) == point
    else:
        # At non-100% scaling the point is the identity only when rounding
        # maps it back onto itself (true for the origin, and for small
        # components that round back, e.g. (0,1) at 125%). Compare against
        # the independently-computed expected value rather than assuming
        # only the origin is fixed.
        assert (normalize_for_scaling(point, session) == point) == (expected == point)


# ---------------------------------------------------------------------------
# Property 10 - the resolved point is anchored at the current window origin
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(origin=_ORIGINS, offset=_POINTS, session=_sessions())
def test_property_10_anchored_at_current_window_origin(origin, offset, session):
    # Feature: desktop-automation-reliability, Property 10: Coordinates are resolved relative to window origin and adjusted for scaling
    # The resolution is relative to the *current* window origin: shifting the
    # window origin shifts the resolved point by the same delta (R11.3), while
    # the scaling-adjusted offset between point and origin is unchanged.
    window = WindowRef(origin=origin)
    assert window_origin(window) == origin

    target = TargetElement(window=window, win_offset=offset)
    base = window_relative(target, session=session).point

    moved_origin = (origin[0] + 37, origin[1] - 19)
    moved_target = TargetElement(window=WindowRef(origin=moved_origin), win_offset=offset)
    moved = window_relative(moved_target, session=session).point

    assert moved == (base[0] + 37, base[1] - 19)
