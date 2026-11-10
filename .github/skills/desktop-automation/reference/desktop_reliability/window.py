"""Window Manager for the desktop-reliability pattern (R11).

This module implements the **Window Manager** supporting component described in
the design ("Components" → "Supporting components"):

    Window Manager — ``ensure_window_focus(window)`` confirms/raises focus
    (R11.1/R11.2) and exposes ``window_origin(window)`` for window-relative
    coordinates (R11.3).

It provides the two behaviors the Verified-Interaction Routine relies on:

- :func:`ensure_window_focus` — *before every interaction*, confirm the target
  window holds input focus and, when it does not, bring it to focus (R11.1 /
  R11.2). This is the focus precondition that prevents input from landing in the
  wrong application.
- :func:`window_origin` — expose a window's current top-left origin so the
  locator can resolve window-relative coordinates (``window_origin + win_offset``)
  per R11.3.

Design choices that keep this logic-only and fully testable
-----------------------------------------------------------
The reference implementation is a *development-time* validation aid, so the only
source of non-determinism — talking to a real desktop's window system — is
**injected**. :func:`ensure_window_focus` takes a ``focus_manager`` that exposes
``has_focus(window)`` and ``set_focus(window)``. The :class:`FocusManager`
``Protocol`` below documents that contract, and
:class:`desktop_reliability.fakes.FakeFocusManager` satisfies it, so the focus
logic can be exercised with no real window system. In a generated desktop
project the same contract is fulfilled by a thin wrapper over the framework
(``pywinauto`` ``set_focus()`` / ``win32gui``).

``window_origin`` is pure: it reads :class:`~desktop_reliability.models.WindowRef`
``origin`` and returns it, or ``None`` when the origin is unknown, so callers can
fall back to another localization strategy rather than computing a coordinate
from missing data.
"""

from __future__ import annotations

from typing import Optional, Tuple

try:  # pragma: no cover - typing.Protocol is always available on 3.8+
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover - legacy fallback
    from typing_extensions import Protocol, runtime_checkable  # type: ignore

from .models import WindowRef

__all__ = [
    "FocusManager",
    "ensure_window_focus",
    "window_origin",
]


@runtime_checkable
class FocusManager(Protocol):
    """The window-focus dependency required by :func:`ensure_window_focus`.

    Any object that can report and acquire input focus satisfies this contract.
    :class:`desktop_reliability.fakes.FakeFocusManager` implements it for tests;
    a generated desktop project wraps the real framework
    (``pywinauto`` / ``win32gui``) behind the same two methods.
    """

    def has_focus(self, window: object) -> bool:
        """Return whether ``window`` currently holds input focus."""
        ...

    def set_focus(self, window: object) -> None:
        """Give ``window`` input focus."""
        ...


def ensure_window_focus(window: object, *, focus_manager: FocusManager) -> bool:
    """Confirm the target window holds focus, acquiring it if missing (R11.1/R11.2).

    The Verified-Interaction Routine calls this immediately before every action so
    input always lands in the intended application. The focus *confirmation*
    (``has_focus``) always happens first; focus is *acquired* (``set_focus``) only
    when the window does not already hold it. Ordering the calls this way lets a
    test assert that a focus confirmation preceded the action (R11.1) and that
    focus was acquired only when needed (R11.2).

    :param window: the target window to focus (e.g. a
        :class:`~desktop_reliability.models.WindowRef`). Treated as an opaque
        token and passed straight through to the focus manager.
    :param focus_manager: the injected :class:`FocusManager`; supplies
        ``has_focus`` / ``set_focus``.
    :returns: ``True`` when focus had to be acquired (the window was not already
        focused), ``False`` when the window already held focus.
    """

    if focus_manager.has_focus(window):
        return False
    focus_manager.set_focus(window)
    return True


def window_origin(window: Optional[WindowRef]) -> Optional[Tuple[int, int]]:
    """Return the window's current top-left origin, or ``None`` when unknown (R11.3).

    The origin feeds window-relative coordinate resolution
    (``point = window_origin + win_offset``). Returning ``None`` instead of a
    guessed coordinate when the origin is unknown lets the locator fall through to
    another ranked strategy rather than clicking at a fabricated position.

    :param window: the :class:`~desktop_reliability.models.WindowRef` whose origin
        is requested; ``None`` (no window) yields ``None``.
    :returns: the ``(x, y)`` top-left origin when known, otherwise ``None``.
    """

    if window is None:
        return None
    return getattr(window, "origin", None)
