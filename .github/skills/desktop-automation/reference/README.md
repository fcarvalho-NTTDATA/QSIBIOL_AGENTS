# Desktop Reliability — Canonical Reference Implementation

This directory is the **canonical desktop-reliability pattern** referenced by
[`desktop-automation/SKILL.md`](../SKILL.md). It is the concrete, executable
example that the governing automation documents encode and point to. Generated
desktop-automation projects are expected to mirror the behavioral helpers
implemented here.

## What this is (and is not)

- **It is** the source-of-truth example for the four behavioral components:
  - `verified_interaction` — pre-capture → interact → post-capture → verify
  - `locate_with_fallback` — ranked localization with retry and exponential backoff
  - `verify_and_classify` — verdict classification (CONFIRMED / NO_OP_CLICK / WRONG_TARGET_CLICK)
  - `classify_failure` — failure classification, escalation, and reporting
  - `calibration` — multi-monitor Click_Offset measurement + offset-correcting resolver (R16)
  - flow status aggregation
- **It is not** a runtime dependency. Python plus Hypothesis/Pytest is a
  **development-time-only** validation aid used to verify the logic-layer
  behavior the documents describe. The end user of the agent never runs this
  folder, and the actual deliverable (the governing markdown documents) does
  not require Python.

## Layout

```
reference/
  desktop_reliability/    # the reusable helper package
    __init__.py
    models.py             # data models + ReliabilityConfig defaults (later task)
    fakes.py              # mocked screen/clock/focus/matchers (later task)
    locator.py            # locate_with_fallback + coordinate math (later task)
    verifier.py           # verify_and_classify (later task)
    calibration.py        # multi-monitor Click_Offset calibration + resolver (R16)
    evidence.py           # evidence store under <project-root>/evidences/ (later task)
    window.py             # focus + window-relative coordinates (later task)
    interaction.py        # verified_interaction orchestration (later task)
    failure.py            # classify_failure + escalation (later task)
    flow.py               # flow status aggregation (later task)
  tests/                  # property-based (Hypothesis) + example tests (later tasks)
  requirements.txt        # hypothesis, pytest (dev-time only)
  pytest.ini
  README.md               # this file
```

> Note: most modules listed above are created by later implementation tasks.
> This skeleton currently contains the `desktop_reliability` package and the
> `tests` directory only.

## Run instructions

From this `reference/` directory:

1. (Recommended) create and activate a virtual environment, then install the
   development-time validation dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

2. Run the test suite with pytest:

   ```bash
   python -m pytest
   ```

`pytest.ini` is configured to discover tests in the `tests/` directory, so
running `python -m pytest` from this directory picks them up automatically.

The property-based tests use [Hypothesis](https://hypothesis.readthedocs.io/)
and run a minimum of 100 iterations each, mocking the screen, clock, and focus
so no real desktop is required.
