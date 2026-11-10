"""Documentation consistency check (R15) — the Layer 3 structural/lint check.

This is a *structural lint* (not a property test) that the six governing
documents for desktop-automation reliability stay mutually consistent, so the
agent prompt, skills, and manual cannot drift apart. It encodes the three things
Requirement 15 demands:

1. **R15.1 — Source of truth is complete.**
   ``desktop-automation/SKILL.md`` documents the full **R1–R14** rule set and
   **points to the reference implementation** (``./reference/``), so the Skill is
   the single authoritative specification.

2. **R15.2 / R15.3 / R15.4 — Everyone references the rules.**
   The five other governing documents
    (``automation-agent-unified.agent.md``, ``UNIFIED_AUTOMATION_AGENT_MANUAL.md``,
   ``execution-validation/SKILL.md``, ``code-generation/SKILL.md``, and
   ``live-exploration-workflow/SKILL.md``) each reference the desktop
   verification / localization rules **and** cite the source-of-truth Skill, so
   none of them forks the rules.

3. **Constants never contradict.**
   No document states a *different* value for any canonical reliability constant
   (confidence ``0.80`` / verify timeout ``10 s`` / post-capture ``2000 ms`` /
   max interaction attempts ``3`` / max locate attempts ``3`` / agent correction
   iterations ``5`` / backoff ``500ms * 2^(attempt-1)``). The check is tolerant:
   a document is *not* failed for omitting a constant — only for stating a
   contradicting value.

Design notes
------------
- Document paths are resolved **relative to the repository root**, discovered by
  walking up from this test file until the source-of-truth Skill is found. No
  absolute machine path is hard-coded.
- A missing document yields a clear ``pytest.skip`` for that check rather than a
  confusing error.
- The constants check is scoped to each document's **Desktop Reliability
  region** so legacy/unrelated numbers elsewhere in a file (e.g. an old
  ``confidence=0.8`` code sample, a generic ``5s to 10s`` retry example, or
  ``time.sleep(0.3)``) never produce false contradictions. Within those regions
  the value-extracting regexes are anchored on each constant's label/unit, so
  only genuine constant statements are validated.

Requirements: 15.1, 15.2, 15.3, 15.4
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Repository-root resolution + document registry (no absolute paths).
# ---------------------------------------------------------------------------

#: Relative path (from the repo root) of the source-of-truth Skill. Used both as
#: the repo-root sentinel and as the primary document under test.
_SKILL_RELPATH = ".github/skills/desktop-automation/SKILL.md"

#: The six governing documents, keyed by a short identifier, as paths relative
#: to the repository root.
DOCS: dict[str, str] = {
    "skill": _SKILL_RELPATH,
    "agent": ".github/agents/automation-agent-unified.agent.md",
    "manual": "manuals/UNIFIED_AUTOMATION_AGENT_MANUAL.md",
    "execution_validation": ".github/skills/execution-validation/SKILL.md",
    "code_generation": ".github/skills/code-generation/SKILL.md",
    "live_exploration": ".github/skills/live-exploration-workflow/SKILL.md",
}

#: The five documents that must *reference* the source-of-truth Skill (R15.2-4).
_REFERRING_DOCS = ("agent", "manual", "execution_validation", "code_generation", "live_exploration")

#: Human-friendly labels for assertion messages.
_DOC_LABELS = {
    "skill": "desktop-automation/SKILL.md",
    "agent": "automation-agent-unified.agent.md",
    "manual": "UNIFIED_AUTOMATION_AGENT_MANUAL.md",
    "execution_validation": "execution-validation/SKILL.md",
    "code_generation": "code-generation/SKILL.md",
    "live_exploration": "live-exploration-workflow/SKILL.md",
}


def _repo_root() -> Path:
    """Walk up from this test file until the source-of-truth Skill is found."""
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / _SKILL_RELPATH).exists():
            return candidate
    raise RuntimeError(
        "Could not locate the repository root: "
        f"no ancestor of {here} contains {_SKILL_RELPATH!r}."
    )


def _read_doc(key: str) -> str:
    """Read a governing document by key, skipping the check if it is missing."""
    path = _repo_root() / DOCS[key]
    if not path.exists():
        pytest.skip(f"governing document not found: {DOCS[key]} (label: {_DOC_LABELS[key]})")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Desktop Reliability region extraction.
# ---------------------------------------------------------------------------
#
# Each document carries its desktop rules in a clearly delimited region. The
# constants check operates only on that region so unrelated numbers elsewhere in
# the file cannot produce false contradictions. ``start`` is a substring marking
# the region's beginning; ``end`` (when given) marks where it stops.

_REGION_MARKERS: dict[str, tuple[str, str | None]] = {
    "skill": ("## Desktop Reliability (Specification", None),
    "agent": ("### 4.10 Desktop Reliability", "\n## 5."),
    "manual": ("## 16. Desktop Reliability", "## 17."),
    "execution_validation": ("Desktop Verification Gating", "**Forbidden Actions:**"),
    "code_generation": ("## Desktop Reliability Helpers", "\n## Code Integration"),
    "live_exploration": ("Desktop verification (mandatory", "**Wait when required:**"),
}


def _desktop_region(key: str, text: str) -> str:
    """Return the desktop-reliability slice of ``text`` for document ``key``.

    Falls back to the whole document when the start marker is absent (the
    label-anchored regexes still keep the constants check honest), so the check
    degrades safely rather than silently scanning nothing.
    """
    start_marker, end_marker = _REGION_MARKERS[key]
    start = text.find(start_marker)
    if start == -1:
        return text
    if end_marker is None:
        return text[start:]
    end = text.find(end_marker, start + len(start_marker))
    return text[start:] if end == -1 else text[start:end]


# ---------------------------------------------------------------------------
# Check 1 (R15.1): the Skill documents R1–R14 and points to the reference impl.
# ---------------------------------------------------------------------------


def test_skill_documents_full_r1_to_r14_rule_set():
    """``desktop-automation/SKILL.md`` carries a heading for every rule R1..R14."""
    text = _read_doc("skill")
    missing = [
        f"R{n}"
        for n in range(1, 15)
        # e.g. "### R1 — Mandatory ...". \b after R{n} keeps R1 from matching R14.
        if re.search(rf"^###\s+R{n}\b", text, re.MULTILINE) is None
    ]
    assert not missing, (
        "the source-of-truth Skill must document the full R1-R14 rule set as "
        f"section headings; missing rule headings: {missing}"
    )


def test_skill_points_to_reference_implementation():
    """The Skill cites the canonical reference implementation under ``reference/``."""
    text = _read_doc("skill")
    # The Skill links to the package via a relative markdown link (./reference/)
    # and/or the full repo path .../desktop-automation/reference/.
    points_to_reference = (
        "./reference/" in text
        or "desktop-automation/reference" in text
        or "](reference/)" in text
    )
    assert points_to_reference, (
        "the Skill must point to the canonical reference implementation "
        "(expected a path reference to ./reference/ or desktop-automation/reference/)"
    )
    # And it should name it as the reference implementation, not just link a dir.
    assert re.search(r"reference\s+implementation", text, re.IGNORECASE), (
        "the Skill must describe the linked artifact as the reference implementation"
    )


# ---------------------------------------------------------------------------
# Check 2 (R15.2 / R15.3 / R15.4): every other document references the rules
# and cites the source-of-truth Skill.
# ---------------------------------------------------------------------------

#: Any one of these (case-insensitive) shows a document references the desktop
#: verification / localization rule set rather than ignoring it.
_DESKTOP_RULE_KEYWORDS = (
    "verify-and-classify",
    "verified_interaction",
    "verified-interaction",
    "verification evidence",
    "post-action verification",
    "no-op",
    "no_op_click",
    "wrong-target",
    "wrong_target_click",
    "ranked localization",
    "resilient ranked localization",
    "locate_with_fallback",
    "wait_for_expected_outcome",
    "desktop verification",
)

#: The source-of-truth Skill citation every referring document must contain.
_SKILL_CITATION = "desktop-automation/SKILL.md"


@pytest.mark.parametrize("key", _REFERRING_DOCS)
def test_document_references_desktop_rules_and_cites_skill(key: str):
    """Each governing doc references the desktop rules AND cites the Skill (R15.2-4)."""
    text = _read_doc(key)
    lowered = text.lower()

    matched_keywords = [kw for kw in _DESKTOP_RULE_KEYWORDS if kw in lowered]
    assert matched_keywords, (
        f"{_DOC_LABELS[key]} must reference the desktop verification/localization "
        f"rules (none of the expected keywords were found): {list(_DESKTOP_RULE_KEYWORDS)}"
    )

    assert _SKILL_CITATION in text, (
        f"{_DOC_LABELS[key]} must cite the source-of-truth Skill "
        f"({_SKILL_CITATION}) so the rules cannot drift"
    )


# ---------------------------------------------------------------------------
# Check 3: no document contradicts another on the canonical constants.
# ---------------------------------------------------------------------------
#
# Each scanner returns every value a document *states* for one constant, read
# from its Desktop Reliability region with a label/unit-anchored regex. The
# check then asserts each stated value is canonical -- omission is fine, only a
# contradicting value fails. Because every document is held to the same
# canonical value, agreement across documents follows.


def _confidence_values(text: str) -> list[float]:
    """Confidence-threshold decimals stated near the word 'confidence'.

    A confidence threshold is by definition a value in ``(0, 1]``, so results
    are filtered to that range. That keeps the scanner from mistaking nearby
    requirement identifiers (``R6.1``, ``R12.4`` -> decimals ``6.1`` / ``12.4``)
    for a threshold, while any genuinely contradicting value (``0.7``, ``0.9``,
    ``0.85`` …) is still in range and therefore still caught.
    """
    raw: list[float] = []
    for m in re.finditer(r"confidence[^\n]{0,40}?(\d+\.\d+)", text, re.IGNORECASE):
        raw.append(float(m.group(1)))
    for m in re.finditer(r"(\d+\.\d+)[^\n]{0,40}?confidence", text, re.IGNORECASE):
        raw.append(float(m.group(1)))
    return [v for v in raw if 0.0 < v <= 1.0]


def _verify_timeout_seconds(text: str) -> list[int]:
    """Timeout values expressed in seconds (e.g. '10 s', '10s', '10-second')."""
    # The seconds unit is matched with a trailing word boundary and an
    # explicit (econds|econd|ec|empty) tail so words like '3 steps' never match.
    return [int(m.group(1)) for m in re.finditer(r"(\d+)\s*-?\s*s(?:econds|econd|ec|)\b", text)]


def _post_capture_ms(text: str) -> list[int]:
    """Post-capture target latency in ms, anchored on post-capture/target labels."""
    values: list[int] = []
    for pattern in (
        r"post[-_ ]?capture[^\n]{0,40}?(\d+)\s*ms",
        r"post_capture_target[^\n]{0,30}?(\d+)\s*ms",
        r"target[^\n]{0,30}?(\d+)\s*ms",
    ):
        values.extend(int(m.group(1)) for m in re.finditer(pattern, text, re.IGNORECASE))
    return values


def _backoff_base_ms(text: str) -> list[int]:
    """Exponential-backoff base in ms (the value multiplied by 2^(attempt-1))."""
    values: list[int] = []
    # The base is the ms value immediately before a '* 2' / 'x 2' / '× 2' factor.
    for m in re.finditer(r"(\d+)\s*(?:ms|milliseconds)\s*[*x\u00d7]\s*2", text, re.IGNORECASE):
        values.append(int(m.group(1)))
    for m in re.finditer(r"backoff[^\n]{0,40}?(\d+)\s*(?:ms|milliseconds)", text, re.IGNORECASE):
        values.append(int(m.group(1)))
    return values


def _attempt_counts(text: str) -> list[int]:
    """Per-interaction / per-localization attempt budgets (canonically 3).

    Deliberately does NOT read a value out of the ``max_*_attempts`` config
    identifiers: in the documents those identifiers are followed by a
    requirement reference (e.g. ``max_interaction_attempts``, R12.1), so reading
    "the next number" there would capture ``12``/``9`` rather than the budget.
    The budget is instead read from the prose/table phrasings below.
    """
    values: list[int] = []
    # "3 attempts", "3 interaction attempts", "3 re-attempts", ... (number first).
    for m in re.finditer(r"(\d+)[\s\w-]{0,22}?attempts\b", text, re.IGNORECASE):
        values.append(int(m.group(1)))
    # Manual-style table/prose cells: "interaction attempts | `3`" (number last).
    for m in re.finditer(
        r"(?:interaction|localization|locate)\s+attempts\W{0,8}(\d+)", text, re.IGNORECASE
    ):
        values.append(int(m.group(1)))
    return values


def _iteration_counts(text: str) -> list[int]:
    """Agent-level correction-iteration budget (canonically 5).

    The number-first regex keeps the digit adjacent to ``iteration(s)`` (only an
    optional hyphen/space or a budget qualifier like "correction" may sit
    between), so markdown anchor links such as
    ``(#12-error-handling--iteration-limits)`` -- where "12" is far from
    "iteration" and separated by other words -- are never misread as ``12``.
    """
    values: list[int] = []
    # "5-iteration", "5 correction iterations", "5 code-fix iterations", ...
    for m in re.finditer(
        r"(\d+)\s*-?\s*(?:(?:agent-level|code-fix|correction)\s+)*iterations?\b",
        text,
        re.IGNORECASE,
    ):
        values.append(int(m.group(1)))
    # Table cell where the number trails the label: "correction iterations | `5`".
    for m in re.finditer(r"correction iterations\W{0,8}(\d+)", text, re.IGNORECASE):
        values.append(int(m.group(1)))
    return values


#: name -> (scanner, canonical-values, render-for-messages)
_CONSTANTS = {
    "confidence_threshold (0.80)": (_confidence_values, {0.80}),
    "verify_timeout (10 s)": (_verify_timeout_seconds, {10}),
    "post_capture_target (2000 ms)": (_post_capture_ms, {2000}),
    "backoff_base (500 ms)": (_backoff_base_ms, {500}),
    "max_attempts (3)": (_attempt_counts, {3}),
    "agent_correction_iterations (5)": (_iteration_counts, {5}),
}


@pytest.mark.parametrize("key", list(DOCS))
def test_document_does_not_contradict_canonical_constants(key: str):
    """No document states a non-canonical value for any reliability constant."""
    region = _desktop_region(key, _read_doc(key))

    contradictions: list[str] = []
    for name, (scanner, canonical) in _CONSTANTS.items():
        for value in scanner(region):
            if value not in canonical:
                contradictions.append(
                    f"{name}: found {value!r} (canonical {sorted(canonical)})"
                )

    assert not contradictions, (
        f"{_DOC_LABELS[key]} contradicts the canonical reliability constants: "
        + "; ".join(contradictions)
    )


def test_skill_actually_states_every_constant():
    """Guard against vacuous passing: the source of truth states each constant.

    If a scanner silently stopped matching (e.g. the Skill was reworded), the
    contradiction check above could pass without ever inspecting a value. This
    asserts the source-of-truth Skill region yields each canonical value at
    least once, so the scanners are exercised against real content.
    """
    region = _desktop_region("skill", _read_doc("skill"))
    for name, (scanner, canonical) in _CONSTANTS.items():
        found = set(scanner(region))
        assert found, f"scanner for {name} found no value in the Skill's desktop region"
        assert found <= canonical, (
            f"the Skill's own desktop region is internally inconsistent for {name}: "
            f"found {sorted(found)}, canonical {sorted(canonical)}"
        )
