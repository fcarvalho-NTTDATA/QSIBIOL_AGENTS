"""Property-based test for Property 6: OCR text normalization invariance.

# Feature: desktop-automation-reliability, Property 6: OCR matching is invariant under case and surrounding whitespace

**Validates: Requirements 6.4**

Property 6 (design "Correctness Properties"):

    For any recognized text and expected text, OCR text matching succeeds if and
    only if the two strings are equal after lowercasing and trimming leading and
    trailing whitespace.

The property is exercised at two layers of Component 2 (the ``Element_Locator``):

* :func:`test_property_06_text_match_invariant` — the pure normalization
  comparator :func:`desktop_reliability.text_match`, which underpins the
  OCR_TEXT strategy. This is where case/whitespace invariance lives, so it is
  hit hardest, including the **whitespace-only** edge case (both sides trim to
  the empty string, so they match) and the **un-normalizable** edge cases
  (``None`` / non-string values, which can never match — R6.5).
* :func:`test_property_06_ocr_text_match_through_provider` — the same invariant
  observed through the :func:`desktop_reliability.ocr_text_match` strategy
  primitive, driving recognized text through the deterministic
  :class:`FakeOcrProvider` so the property is verified at the strategy entry
  point (matched iff normalized-equal; full confidence on a match).

Independent oracle
------------------
The oracle (:func:`_normalized_equal`) recomputes the property's definition
directly from Python's ``str.strip()`` / ``str.lower()`` and treats any value
that cannot be normalized as a non-match. It never calls the functions under
test (``normalize`` / ``text_match`` / ``ocr_text_match``), so the test cannot
tautologically agree with the implementation.

Everything is logic-only with no real desktop, OCR engine, or clock.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from desktop_reliability import (
    FULL_SCREEN,
    FakeOcrProvider,
    Region,
    ocr_text_match,
    text_match,
)

# Run well above the required minimum of 100 iterations.
MAX_EXAMPLES = 200

# Whitespace characters that ``str.strip()`` trims; used to build leading/
# trailing decorations and the whitespace-only edge case.
_WHITESPACE = " \t\n\r\f\v"

# A mixed alphabet covering both letter cases, digits, internal spaces, and a
# unicode pair (é/É) whose case folding is stable, so generated examples
# exercise case and whitespace variation richly.
_TEXT_ALPHABET = "abcABC123 _-éÉ"

# Values that cannot be normalized (no ``.strip()``), per R6.5.
_UN_NORMALIZABLE = st.one_of(
    st.none(),
    st.integers(),
    st.lists(st.integers(), max_size=3),
)

_ws_text = st.text(alphabet=_WHITESPACE, max_size=4)
_plain_text = st.text(alphabet=_TEXT_ALPHABET, max_size=8)


# ---------------------------------------------------------------------------
# Independent oracle (does not call the functions under test)
# ---------------------------------------------------------------------------


def _normalized_equal(recognized: object, expected: object) -> bool:
    """Oracle for Property 6: equal after trim + lowercase, else non-match.

    Recomputes the property definition directly. Any value that cannot be
    normalized (``None`` / non-string) is treated as a non-match (R6.5),
    mirroring the contract without invoking the implementation's helpers.
    """

    try:
        return recognized.strip().lower() == expected.strip().lower()  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def _recased(draw, base: str) -> str:
    """Return ``base`` with each character independently upper/lower-cased."""

    return "".join(ch.upper() if draw(st.booleans()) else ch.lower() for ch in base)


@st.composite
def _matching_pair(draw):
    """Two strings equal after normalization: same base, varied case + outer ws.

    Both sides share the same internal text (internal whitespace is preserved
    by ``strip``), differing only in letter case and leading/trailing
    whitespace, so they normalize to the same value.
    """

    base = draw(st.text(alphabet="abc123 éÉ", max_size=6))
    left = draw(_ws_text) + draw(_recased(base)) + draw(_ws_text)
    right = draw(_ws_text) + draw(_recased(base)) + draw(_ws_text)
    return left, right


@st.composite
def _string_pair(draw):
    """A (recognized, expected) pair biased to exercise both branches.

    Kinds: ``match`` (equal after normalization), ``random`` (usually unequal),
    ``ws`` (both whitespace-only, equal-after-trim edge case), and ``edge`` (one
    or both sides un-normalizable, e.g. ``None``).
    """

    kind = draw(st.sampled_from(["match", "random", "ws", "edge"]))
    if kind == "match":
        return draw(_matching_pair())
    if kind == "random":
        return draw(_plain_text), draw(_plain_text)
    if kind == "ws":
        return draw(_ws_text), draw(_ws_text)
    # edge: at least one side may be un-normalizable.
    left = draw(st.one_of(_UN_NORMALIZABLE, _plain_text))
    right = draw(st.one_of(_UN_NORMALIZABLE, _plain_text))
    return left, right


# ---------------------------------------------------------------------------
# Property 6 - pure normalization comparator
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_string_pair())
def test_property_06_text_match_invariant(pair):
    # Feature: desktop-automation-reliability, Property 6: OCR matching is invariant under case and surrounding whitespace
    recognized, expected = pair

    # The implementation succeeds iff the two values are normalized-equal.
    assert text_match(recognized, expected) == _normalized_equal(recognized, expected)

    # Matching is symmetric in its two arguments.
    assert text_match(recognized, expected) == text_match(expected, recognized)


# ---------------------------------------------------------------------------
# Property 6 - case-only invariance (always matches)
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_plain_text)
def test_property_06_case_and_surrounding_whitespace_invariant(core):
    # Feature: desktop-automation-reliability, Property 6: OCR matching is invariant under case and surrounding whitespace
    # Decorating a string with differing case and surrounding whitespace must
    # never change the match outcome: a value always matches itself wrapped in
    # arbitrary leading/trailing whitespace and recased.
    decorated_upper = "  " + core.upper() + "\t"
    decorated_lower = "\n" + core.lower() + "   "

    assert text_match(core, decorated_upper) is True
    assert text_match(decorated_lower, decorated_upper) is True
    # Sanity-check the oracle agrees on this constructed-to-match case.
    assert _normalized_equal(core, decorated_upper) is True


# ---------------------------------------------------------------------------
# Property 6 - whitespace-only and un-normalizable explicit edge cases
# ---------------------------------------------------------------------------


def test_property_06_whitespace_only_and_unnormalizable_edges():
    # Feature: desktop-automation-reliability, Property 6: OCR matching is invariant under case and surrounding whitespace
    # Whitespace-only strings normalize to the empty string, so any two of them
    # match (and match the empty string).
    assert text_match("   ", "\t\n") is True
    assert text_match("", "  \f ") is True

    # Un-normalizable values (None / non-string) can never match (R6.5).
    assert text_match(None, "ok") is False
    assert text_match("ok", None) is False
    assert text_match(None, None) is False
    assert text_match(123, "123") is False


# ---------------------------------------------------------------------------
# Property 6 - observed through the OCR_TEXT strategy primitive
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(_string_pair())
def test_property_06_ocr_text_match_through_provider(pair):
    # Feature: desktop-automation-reliability, Property 6: OCR matching is invariant under case and surrounding whitespace
    recognized, expected = pair

    # The OCR provider yields the recognized text for the searched region.
    provider = FakeOcrProvider(sequence=[recognized])
    result = ocr_text_match(expected, ocr_provider=provider, region=FULL_SCREEN)

    # The strategy matches iff recognized and expected are normalized-equal
    # (when expected is None the primitive short-circuits to a non-match, which
    # the oracle also reports since None cannot be normalized).
    assert result.matched == _normalized_equal(recognized, expected)

    # A match reports full confidence; a non-match reports none. The point is
    # unknown for a full-screen search in either case.
    if result.matched:
        assert result.confidence == 1.0
    else:
        assert result.confidence == 0.0
    assert result.point is None
