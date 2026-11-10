"""Property-based test for Property 16: multi-monitor placement reasoning.

# Feature: desktop-automation-reliability, Property 16: Monitor placement reasoning detects non-primary monitors, forces re-calibration on monitor change, guards mixed-DPI, and prefers relative localization while the offset is unknown

**Validates: Requirements 16.7, 16.11, 16.13, 16.14**

Property 16 (Requirement 16 — multi-monitor coordinate consistency):

    For any per-monitor Virtual_Desktop geometry and target window origin: a
    window origin outside the primary monitor's bounds is treated as residing on
    a non-primary monitor (R16.7); a window that moves to a different monitor
    forces re-calibration (R16.11); a difference in per-monitor scaling between
    the read monitor and the command monitor is a mixed-DPI conflict that must
    not proceed with an uncorrected coordinate (R16.14); and while the
    Click_Offset is unknown or unstable, relative localization is preferred over
    absolute coordinates (R16.13).

The functions under test live in ``desktop_reliability.calibration`` and
``desktop_reliability.models`` (``Monitor`` / ``SessionEnvironment``):
:func:`is_on_non_primary_monitor`, :func:`requires_recalibration`,
:func:`scaling_conflict`, and :func:`prefer_relative_localization`.

Independent oracle
------------------
The expectations are re-derived from the spec, not from the implementation:

* non-primary  ``= origin is known, multi-monitor, and primary does not contain origin`` (R16.7),
* re-calibration ``= both monitors known and different`` (R16.11),
* scaling conflict ``= both monitors known and scaling factors differ`` (R16.14),
* prefer relative ``= offset is None or not stable`` (R16.13).

Everything is pure geometry/logic — no real desktop, screen, or OS.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    ClickOffset,
    Monitor,
    SessionEnvironment,
    is_on_non_primary_monitor,
    prefer_relative_localization,
    requires_recalibration,
    scaling_conflict,
    window_monitor,
)

MAX_EXAMPLES = 200

_SCALING = st.sampled_from([100, 125, 150, 175, 200])
_DIM = st.integers(min_value=600, max_value=3840)


@st.composite
def _two_monitor_session(draw):
    """A primary monitor at the origin and a second monitor placed beside it.

    The secondary monitor is placed either to the left (negative origin) or to
    the right (large-positive origin) of the primary so the test exercises the
    negative and large-positive origin ranges non-primary monitors occupy.
    """

    pw = draw(_DIM)
    ph = draw(_DIM)
    primary = Monitor(origin=(0, 0), width=pw, height=ph,
                       scaling_factor=draw(_SCALING), primary=True)

    sw = draw(_DIM)
    sh = draw(_DIM)
    place_left = draw(st.booleans())
    sx = -sw if place_left else pw  # adjacent, non-overlapping
    secondary = Monitor(origin=(sx, 0), width=sw, height=sh,
                        scaling_factor=draw(_SCALING), primary=False)

    session = SessionEnvironment(
        resolution=(pw, ph),
        scaling_factor=primary.scaling_factor,
        exploration_resolution=(pw, ph),
        exploration_scaling=primary.scaling_factor,
        monitors=(primary, secondary),
    )
    return session, primary, secondary


# ---------------------------------------------------------------------------
# Property 16 - non-primary monitor detection (R16.7)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(data=_two_monitor_session())
def test_property_16_non_primary_detection(data):
    # Feature: desktop-automation-reliability, Property 16: Monitor placement reasoning detects non-primary monitors, forces re-calibration on monitor change, guards mixed-DPI, and prefers relative localization while the offset is unknown
    session, primary, secondary = data

    # A point inside the primary monitor is NOT on a non-primary monitor.
    primary_point = (primary.origin[0] + primary.width // 2,
                     primary.origin[1] + primary.height // 2)
    assert is_on_non_primary_monitor(session, primary_point) is False
    assert window_monitor(session, primary_point) == primary

    # A point inside the secondary monitor IS on a non-primary monitor (R16.7).
    secondary_point = (secondary.origin[0] + secondary.width // 2,
                       secondary.origin[1] + secondary.height // 2)
    assert is_on_non_primary_monitor(session, secondary_point) is True
    assert window_monitor(session, secondary_point) == secondary

    # Unknown origin is never classified as non-primary.
    assert is_on_non_primary_monitor(session, None) is False


@settings(max_examples=MAX_EXAMPLES)
@given(point=st.tuples(st.integers(-100, 100), st.integers(-100, 100)))
def test_property_16_single_monitor_never_non_primary(point):
    # Feature: desktop-automation-reliability, Property 16: Monitor placement reasoning detects non-primary monitors, forces re-calibration on monitor change, guards mixed-DPI, and prefers relative localization while the offset is unknown
    # A single-monitor desktop is one plane: nothing is ever "non-primary"
    # (R16.7 only applies relative to a primary on a multi-monitor desktop).
    primary = Monitor(origin=(0, 0), width=1920, height=1080, primary=True)
    session = SessionEnvironment(
        resolution=(1920, 1080), scaling_factor=100,
        exploration_resolution=(1920, 1080), exploration_scaling=100,
        monitors=(primary,),
    )
    assert session.is_single_monitor is True
    assert is_on_non_primary_monitor(session, point) is False


# ---------------------------------------------------------------------------
# Property 16 - re-calibration on monitor change (R16.11)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(data=_two_monitor_session())
def test_property_16_recalibration_on_monitor_change(data):
    # Feature: desktop-automation-reliability, Property 16: Monitor placement reasoning detects non-primary monitors, forces re-calibration on monitor change, guards mixed-DPI, and prefers relative localization while the offset is unknown
    _session, primary, secondary = data

    # Same monitor -> no re-calibration; different monitor -> re-calibration.
    assert requires_recalibration(primary, primary) is False
    assert requires_recalibration(primary, secondary) is True
    assert requires_recalibration(secondary, primary) is True

    # Unknown on either side never forces a (potentially spurious) re-calibration.
    assert requires_recalibration(None, primary) is False
    assert requires_recalibration(primary, None) is False


# ---------------------------------------------------------------------------
# Property 16 - mixed-DPI conflict guard (R16.14)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(read_scaling=_SCALING, command_scaling=_SCALING)
def test_property_16_scaling_conflict(read_scaling, command_scaling):
    # Feature: desktop-automation-reliability, Property 16: Monitor placement reasoning detects non-primary monitors, forces re-calibration on monitor change, guards mixed-DPI, and prefers relative localization while the offset is unknown
    read_monitor = Monitor(origin=(0, 0), width=1920, height=1080, scaling_factor=read_scaling)
    command_monitor = Monitor(origin=(1920, 0), width=1920, height=1080, scaling_factor=command_scaling)

    expected_conflict = read_scaling != command_scaling
    assert scaling_conflict(read_monitor, command_monitor) is expected_conflict

    # Unknown monitor on either side is not a conflict (no basis to block).
    assert scaling_conflict(None, command_monitor) is False
    assert scaling_conflict(read_monitor, None) is False


# ---------------------------------------------------------------------------
# Property 16 - prefer relative localization while offset unknown/unstable (R16.13)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(vector=st.tuples(st.integers(-50, 50), st.integers(-50, 50)), stable=st.booleans())
def test_property_16_prefer_relative_while_offset_unknown(vector, stable):
    # Feature: desktop-automation-reliability, Property 16: Monitor placement reasoning detects non-primary monitors, forces re-calibration on monitor change, guards mixed-DPI, and prefers relative localization while the offset is unknown
    offset = ClickOffset(vector=vector, stable=stable)
    # Prefer relative iff the offset is not yet stable (R16.13).
    assert prefer_relative_localization(offset) is (not stable)

    # An entirely unknown offset (None) always prefers relative localization.
    assert prefer_relative_localization(None) is True

    # The zero identity is stable, so absolute coordinates can be used safely.
    assert prefer_relative_localization(ClickOffset.zero()) is False
