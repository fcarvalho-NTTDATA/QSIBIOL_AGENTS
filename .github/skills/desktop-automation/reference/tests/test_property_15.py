"""Property-based test for Property 15: multi-monitor click-offset calibration.

# Feature: desktop-automation-reliability, Property 15: Click-offset calibration measures, classifies, and applies a constant capture-vs-click divergence, with a zero-offset identity on single monitors

**Validates: Requirements 16.3, 16.4, 16.5, 16.6, 16.9, 16.10, 16.12, 16.13**

Property 15 (Requirement 16 — multi-monitor coordinate consistency):

    For any commanded interaction point and the observed point read from the
    Post_Action_State, the divergence is ``observed - commanded``; a divergence
    reproduced across at least two measurements whose horizontal and vertical
    components each agree within the tolerance (default 2 px) is classified
    stable and is applied as a constant correction to every subsequently
    resolved point; fewer than two measurements, or measurements that disagree
    by more than the tolerance, are unstable and never applied; and a
    single-monitor Virtual_Desktop always yields the zero-offset identity so
    resolved points are unchanged.

The functions under test live in ``desktop_reliability.calibration`` (the
multi-monitor Calibration helper / offset-correcting interaction-point
resolver): :func:`measure_divergence`, :func:`offset_is_stable`,
:func:`resolve_click_offset`, :func:`resolve_interaction_point`, and the
:class:`Calibrator` that ties them together.

Independent oracle
------------------
The test never calls the implementation to compute its expectations. It
re-derives every expected value directly from the spec formulas:

* divergence ``= observed - commanded`` (R16.3/R16.9),
* stability ``= len >= 2 and per-component spread <= tolerance`` (R16.4/R16.5),
* a stable offset's applied point ``= point + representative_vector``
  (R16.6/R16.10), where the representative is the most recent measurement,
* an unstable/unknown offset leaves the point unchanged (R16.13),
* a single-monitor desktop is the zero identity (R16.12).

Everything is pure coordinate math — no real desktop, screen, clock, or OS.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    Calibrator,
    ClickOffset,
    Monitor,
    measure_divergence,
    offset_is_stable,
    representative_offset,
    resolve_click_offset,
    resolve_interaction_point,
    vectors_agree,
)

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# Coordinate components spanning the Virtual_Desktop, including the negative and
# large-positive ranges non-primary monitors occupy.
_COORD = st.integers(min_value=-4000, max_value=8000)
_POINTS = st.tuples(_COORD, _COORD)
_TOLERANCE = st.integers(min_value=0, max_value=5)


# ---------------------------------------------------------------------------
# Independent oracle (re-derives the spec; never calls the SUT)
# ---------------------------------------------------------------------------


def _oracle_divergence(observed, commanded):
    return (observed[0] - commanded[0], observed[1] - commanded[1])


def _oracle_stable(measurements, tolerance):
    if len(measurements) < 2:
        return False
    tol = max(0, tolerance)
    xs = [m[0] for m in measurements]
    ys = [m[1] for m in measurements]
    return (max(xs) - min(xs)) <= tol and (max(ys) - min(ys)) <= tol


# ---------------------------------------------------------------------------
# Property 15 - divergence is observed - commanded (R16.3 / R16.9)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(observed=_POINTS, commanded=_POINTS)
def test_property_15_divergence_is_observed_minus_commanded(observed, commanded):
    # Feature: desktop-automation-reliability, Property 15: Click-offset calibration measures, classifies, and applies a constant capture-vs-click divergence, with a zero-offset identity on single monitors
    divergence = measure_divergence(observed, commanded)
    assert divergence == _oracle_divergence(observed, commanded)

    # The divergence is exactly the correction that maps commanded -> observed:
    # adding it back to the commanded point reproduces the observed point.
    assert (commanded[0] + divergence[0], commanded[1] + divergence[1]) == observed


# ---------------------------------------------------------------------------
# Property 15 - stability classification (R16.4 / R16.5)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(measurements=st.lists(_POINTS, max_size=6), tolerance=_TOLERANCE)
def test_property_15_stability_matches_oracle(measurements, tolerance):
    # Feature: desktop-automation-reliability, Property 15: Click-offset calibration measures, classifies, and applies a constant capture-vs-click divergence, with a zero-offset identity on single monitors
    assert offset_is_stable(measurements, tolerance) == _oracle_stable(measurements, tolerance)


@settings(max_examples=MAX_EXAMPLES)
@given(base=_POINTS, n=st.integers(min_value=2, max_value=6), tolerance=_TOLERANCE)
def test_property_15_repeated_within_tolerance_is_stable(base, n, tolerance):
    # Feature: desktop-automation-reliability, Property 15: Click-offset calibration measures, classifies, and applies a constant capture-vs-click divergence, with a zero-offset identity on single monitors
    # >= 2 measurements whose per-component spread is within tolerance are stable
    # (R16.4). Deviate from base by 0..tol (a band of width tol) so the spread of
    # each component never exceeds the tolerance.
    tol = max(0, tolerance)
    measurements = [base]
    for k in range(1, n):
        d = tol if k % 2 else 0
        measurements.append((base[0] + d, base[1] + d))
    # Sanity: the oracle agrees these are within tolerance.
    assert _oracle_stable(measurements, tolerance) is True
    assert offset_is_stable(measurements, tolerance) is True

    offset = resolve_click_offset(measurements, tolerance=tolerance)
    assert offset.stable is True
    # The representative is the most recent measurement (R16.6).
    assert offset.vector == representative_offset(measurements)
    assert offset.vector == measurements[-1]


@settings(max_examples=MAX_EXAMPLES)
@given(measurement=_POINTS)
def test_property_15_single_measurement_is_unstable(measurement):
    # Feature: desktop-automation-reliability, Property 15: Click-offset calibration measures, classifies, and applies a constant capture-vs-click divergence, with a zero-offset identity on single monitors
    # Fewer than two measurements -> unstable (R16.5), and the resolved offset
    # carries a zero vector that is never applied.
    assert offset_is_stable([measurement]) is False
    offset = resolve_click_offset([measurement])
    assert offset.stable is False
    assert offset.vector == (0, 0)


@settings(max_examples=MAX_EXAMPLES)
@given(a=_POINTS, tolerance=_TOLERANCE, extra=st.integers(min_value=1, max_value=50))
def test_property_15_disagreeing_measurements_are_unstable(a, tolerance, extra):
    # Feature: desktop-automation-reliability, Property 15: Click-offset calibration measures, classifies, and applies a constant capture-vs-click divergence, with a zero-offset identity on single monitors
    # Two measurements that differ by strictly more than the tolerance on a
    # component are unstable (R16.5).
    tol = max(0, tolerance)
    b = (a[0] + tol + extra, a[1])
    assert vectors_agree(a, b, tolerance) is False
    assert offset_is_stable([a, b], tolerance) is False
    assert resolve_click_offset([a, b], tolerance=tolerance).stable is False


# ---------------------------------------------------------------------------
# Property 15 - stable offset applies as a constant correction (R16.6 / R16.10)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(point=_POINTS, vector=_POINTS)
def test_property_15_stable_offset_applies_constant_correction(point, vector):
    # Feature: desktop-automation-reliability, Property 15: Click-offset calibration measures, classifies, and applies a constant capture-vs-click divergence, with a zero-offset identity on single monitors
    stable = ClickOffset(vector=vector, stable=True)
    expected = (point[0] + vector[0], point[1] + vector[1])
    assert resolve_interaction_point(point, stable) == expected
    assert stable.apply(point) == expected


@settings(max_examples=MAX_EXAMPLES)
@given(point=_POINTS, vector=_POINTS)
def test_property_15_unstable_or_unknown_offset_not_applied(point, vector):
    # Feature: desktop-automation-reliability, Property 15: Click-offset calibration measures, classifies, and applies a constant capture-vs-click divergence, with a zero-offset identity on single monitors
    # R16.13: an unstable or unknown offset must NOT move the resolved point.
    unstable = ClickOffset(vector=vector, stable=False)
    assert resolve_interaction_point(point, unstable) == point
    assert resolve_interaction_point(point, None) == point


# ---------------------------------------------------------------------------
# Property 15 - single-monitor desktop is the zero-offset identity (R16.12)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(point=_POINTS, measurements=st.lists(_POINTS, max_size=5))
def test_property_15_single_monitor_is_zero_identity(point, measurements):
    # Feature: desktop-automation-reliability, Property 15: Click-offset calibration measures, classifies, and applies a constant capture-vs-click divergence, with a zero-offset identity on single monitors
    # On a single-monitor Virtual_Desktop the offset is the zero identity
    # regardless of any measurements, so resolved points are unchanged (R16.12).
    offset = resolve_click_offset(measurements, single_monitor=True)
    assert offset.vector == (0, 0)
    assert offset.stable is True
    assert resolve_interaction_point(point, offset) == point

    # The Calibrator short-circuits identically when single_monitor is set.
    calib = Calibrator(single_monitor=True)
    for m in measurements:
        calib.record((m[0], m[1]), (0, 0))
    assert calib.is_stable is True
    assert calib.offset().vector == (0, 0)
    assert calib.correct(point) == point


# ---------------------------------------------------------------------------
# Property 15 - Calibrator accumulates and resolves correctly end to end
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(commanded=_POINTS, vector=_POINTS, point=_POINTS, n=st.integers(min_value=2, max_value=5))
def test_property_15_calibrator_reproduced_offset_corrects_points(commanded, vector, point, n):
    # Feature: desktop-automation-reliability, Property 15: Click-offset calibration measures, classifies, and applies a constant capture-vs-click divergence, with a zero-offset identity on single monitors
    # A perfectly reproduced divergence (observed = commanded + vector, n times)
    # is stable, equals the vector, and corrects any point by exactly that
    # vector (R16.3/R16.4/R16.6/R16.10).
    calib = Calibrator()
    observed = (commanded[0] + vector[0], commanded[1] + vector[1])
    for _ in range(n):
        recorded = calib.record(observed, commanded)
        assert recorded == vector  # each measurement equals the constant vector

    assert calib.is_stable is True
    offset = calib.offset()
    assert offset.stable is True
    assert offset.vector == vector
    assert calib.correct(point) == (point[0] + vector[0], point[1] + vector[1])
