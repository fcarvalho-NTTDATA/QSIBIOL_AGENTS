"""Evidence Store for the desktop-reliability pattern (R1.4).

This module implements the **Evidence Store** dependency described in the design
("Components" → "Evidence Store"):

    store_evidence(capture, step_id, phase, attempt) writes under
    <project-root>/evidences/ with a step-identifying name (R1.4), consistent
    with the existing evidence convention.

Every Pre_Action_State and Post_Action_State captured by the Verified-Interaction
Routine is persisted here so that a step is only ever counted as successful when
there is verification evidence (R4), and so that failures are traceable by step
and attempt (design "Evidence on error").

Design choices that keep this logic-only and fully testable
-----------------------------------------------------------
The reference implementation is a *development-time* validation aid, so the two
sources of non-determinism — **where** evidence lives and the **actual write** —
are both injectable:

- **Path computation is pure.** :func:`evidence_path` computes the destination
  ``Path`` with no I/O. Property tests (task 4.4) can assert that the path is
  rooted under ``evidences/`` and includes the step identifier without touching
  a filesystem.
- **The write is injectable.** :func:`store_evidence` accepts an optional
  ``writer(capture, path)`` callable so tests can capture *what* would be written
  *where* without performing real file I/O, an optional ``project_root`` so a
  test never writes into the real repository, and an optional ``evidences_root``
  that names the evidence directory directly (overriding
  ``<project-root>/evidences/``). Real I/O happens only via the built-in default
  writer, and only then is the evidence directory created
  (``parents=True, exist_ok=True``).

Naming scheme (collision-resistant, step-identifying)
-----------------------------------------------------
A capture is stored at::

    <project-root>/evidences/<step>_attempt<attempt>_<phase>.png

where ``<step>`` is the step identifier (sanitized for filesystem safety — see
:func:`sanitize_step_id`), ``<attempt>`` is the 1-based attempt number, and
``<phase>`` is ``"pre"`` or ``"post"``. The triple ``(step, attempt, phase)``
uniquely identifies one capture within a flow, so two captures never collide:

- different steps  → different ``<step>`` segment,
- the same step retried → different ``attempt<n>`` segment (R12 re-attempts),
- pre vs. post of one attempt → different ``<phase>`` segment (R1.1/R1.2).

The step identifier always appears in the file name (R1.4). Sanitization is the
*identity* for the typical identifier alphabet ``[A-Za-z0-9._-]``; only
filesystem-unsafe characters (path separators, reserved characters, control
characters) are replaced with ``_``. Generators in property tests should
constrain step identifiers to that safe alphabet so the raw identifier appears
verbatim in the path.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional, Union

__all__ = [
    "EVIDENCE_DIRNAME",
    "VALID_PHASES",
    "Writer",
    "sanitize_step_id",
    "evidence_path",
    "store_evidence",
]


#: The directory (relative to the project root) all evidence is written under.
EVIDENCE_DIRNAME = "evidences"

#: The only two valid capture phases (R1.1 pre-action, R1.2 post-action).
VALID_PHASES = ("pre", "post")

#: A write sink: persists ``capture`` to ``path``. Injected by tests to avoid I/O.
Writer = Callable[[object, Path], None]

# Characters that are safe to keep verbatim in an evidence file name. Everything
# else (path separators, Windows-reserved characters, whitespace, control
# characters, …) is replaced with ``_`` so the name is portable and cannot
# escape the ``evidences/`` directory.
_SAFE_STEP_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_step_id(step_id: str) -> str:
    """Return a filesystem-safe rendering of ``step_id`` for use in a file name.

    Replaces every character outside the safe identifier alphabet
    ``[A-Za-z0-9._-]`` with ``_`` so the result can never contain a path
    separator or a reserved character and therefore cannot escape the
    ``evidences/`` directory. For a typical identifier (``"step1"``,
    ``"login-button"``, ``"submit_form.2"``) the function is the identity, so
    the step identifier appears verbatim in the evidence path (R1.4).

    :raises TypeError: if ``step_id`` is not a string.
    :raises ValueError: if ``step_id`` is empty or sanitizes to an empty string
        (a capture must always be attributable to an identifiable step).
    """

    if not isinstance(step_id, str):
        raise TypeError(f"step_id must be a string, got {type(step_id).__name__}")
    if not step_id:
        raise ValueError("step_id must be a non-empty string")
    safe = _SAFE_STEP_CHARS.sub("_", step_id)
    if not safe.strip("_"):
        raise ValueError(f"step_id {step_id!r} has no filesystem-safe characters")
    return safe


def _validate_phase(phase: str) -> str:
    """Validate that ``phase`` is one of ``"pre"`` / ``"post"`` (R1.1/R1.2)."""

    if phase not in VALID_PHASES:
        raise ValueError(
            f"phase must be one of {VALID_PHASES!r}, got {phase!r}"
        )
    return phase


def _validate_attempt(attempt: int) -> int:
    """Validate that ``attempt`` is a positive (1-based) integer (R12.1)."""

    # ``bool`` is an ``int`` subclass; reject it explicitly so ``True`` is not
    # silently accepted as attempt ``1``.
    if isinstance(attempt, bool) or not isinstance(attempt, int):
        raise TypeError(f"attempt must be an int, got {type(attempt).__name__}")
    if attempt < 1:
        raise ValueError(f"attempt must be >= 1, got {attempt}")
    return attempt


def _resolve_evidences_root(
    project_root: Optional[Union[str, Path]],
    evidences_root: Optional[Union[str, Path]],
) -> Path:
    """Resolve the directory evidence is written into (the ``evidences/`` root).

    Two injection points cover both how the design phrases the convention and
    how tests want to control I/O:

    - ``evidences_root`` — when given, it **is** the evidence directory and is
      used verbatim (no ``evidences/`` segment is appended). This is the most
      direct override for a test pointing at a throwaway temp directory.
    - ``project_root`` — otherwise the directory is ``<project-root>/evidences/``
      (the design's ``<project-root>/evidences/`` convention, R1.4), with the
      project root defaulting to the current working directory in production.

    ``evidences_root`` takes precedence when both are supplied. The default
    (neither supplied) is ``<cwd>/evidences/``.
    """

    if evidences_root is not None:
        return Path(evidences_root)
    root = Path.cwd() if project_root is None else Path(project_root)
    return root / EVIDENCE_DIRNAME


def evidence_path(
    project_root: Optional[Union[str, Path]],
    step_id: str,
    phase: str,
    attempt: int,
    *,
    evidences_root: Optional[Union[str, Path]] = None,
) -> Path:
    """Compute the destination path for a capture — pure, performs no I/O (R1.4).

    Returns ``<project-root>/evidences/<step>_attempt<attempt>_<phase>.png`` (see
    the module docstring for the full naming scheme). The returned path is always
    rooted under the resolved ``evidences/`` directory and its file name always
    includes the (sanitized) step identifier, the attempt number, and the phase,
    so the triple uniquely identifies one capture.

    This function does **not** create any directory or write any file; it only
    computes the path, so it is safe to call from property tests that assert
    path structure without filesystem access.

    :param project_root: the project root; ``None`` resolves to the current
        working directory. Ignored when ``evidences_root`` is supplied.
    :param step_id: the interaction step identifier (R1.4); sanitized via
        :func:`sanitize_step_id`.
    :param phase: ``"pre"`` or ``"post"`` (validated).
    :param attempt: the 1-based attempt number (validated, ``>= 1``).
    :param evidences_root: optional explicit evidence directory; when given it is
        used verbatim instead of ``<project-root>/evidences/``.
    """

    safe_step = sanitize_step_id(step_id)
    _validate_phase(phase)
    _validate_attempt(attempt)

    directory = _resolve_evidences_root(project_root, evidences_root)
    file_name = f"{safe_step}_attempt{attempt}_{phase}.png"
    return directory / file_name


def _default_writer(capture: object, path: Path) -> None:
    """Persist ``capture`` to ``path``, creating ``evidences/`` as needed (R1.4).

    The directory is created lazily here (``parents=True, exist_ok=True``) so the
    pure :func:`evidence_path` and any test that injects its own ``writer`` never
    touch the filesystem. The write itself is best-effort and ordered to match
    how real captures arrive in a generated desktop project:

    1. a screenshot-like object exposing ``save(path)`` (PyAutoGUI / Pillow image)
       is asked to save itself;
    2. raw ``bytes`` / ``bytearray`` are written directly;
    3. anything else falls back to writing its text representation, so the
       reference store still produces a traceable artifact.
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    save = getattr(capture, "save", None)
    if callable(save):
        save(str(path))
    elif isinstance(capture, (bytes, bytearray)):
        path.write_bytes(bytes(capture))
    else:
        path.write_text(str(capture), encoding="utf-8")


def store_evidence(
    capture: object,
    step_id: str,
    phase: str,
    attempt: int,
    *,
    project_root: Optional[Union[str, Path]] = None,
    evidences_root: Optional[Union[str, Path]] = None,
    writer: Optional[Writer] = None,
) -> str:
    """Store one Pre/Post capture under ``<project-root>/evidences/`` (R1.4).

    Computes the destination via :func:`evidence_path` and persists ``capture``
    there, returning the path as a ``str`` (which slots directly into
    :class:`~desktop_reliability.models.InteractionRecord.pre_evidence` /
    ``post_evidence``, both ``list[str]``).

    The location and the write are both injectable to keep the reference
    implementation testable:

    - ``writer`` — an optional ``(capture, path) -> None`` callable. When
      supplied, **no real file I/O occurs** here; the writer decides what (if
      anything) to do. Tests inject a recording writer to assert *what* would be
      written *where*. When omitted, a built-in default writer performs the real
      write and creates the evidence directory on demand.
    - ``project_root`` — an optional root so tests never write into the real
      repository; defaults to the current working directory. Evidence then lives
      under ``<project-root>/evidences/``.
    - ``evidences_root`` — an optional explicit evidence directory used verbatim
      (takes precedence over ``project_root``); the most direct override for a
      test pointing at a throwaway temp directory.

    :param capture: the captured screen state (a screenshot object, ``bytes``, or
        any value the chosen ``writer`` understands).
    :param step_id: the interaction step identifier (R1.4).
    :param phase: ``"pre"`` or ``"post"`` (validated).
    :param attempt: the 1-based attempt number (validated, ``>= 1``).
    :param project_root: project root; ``None`` resolves to the current working
        directory.
    :param evidences_root: optional explicit evidence directory; overrides
        ``project_root`` when supplied.
    :param writer: optional write sink; when ``None`` a real-I/O default is used.
    :returns: the evidence path as a string.
    """

    path = evidence_path(
        project_root, step_id, phase, attempt, evidences_root=evidences_root
    )
    sink = writer if writer is not None else _default_writer
    sink(capture, path)
    return str(path)
