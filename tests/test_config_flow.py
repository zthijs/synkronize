"""Tests for the selector helpers behind the config and options forms.

Selectors validate their config at construction time, so a malformed one raises
while the form is being built - which the frontend surfaces as the unhelpful
"Config flow could not be loaded: 400: Bad Request". Constructing them here is
enough to catch that without a running Home Assistant.
"""

from __future__ import annotations

import pytest
import voluptuous as vol

from custom_components.synkronize.config_flow import _select, _slider
from custom_components.synkronize.const import (
    DISTRIBUTION_MODES,
    MAX_IDLE_GRACE,
    MAX_TRANSITION,
    MIN_IDLE_GRACE,
    MIN_TRANSITION,
    ON_IDLE_MODES,
    SWATCH_KEYS,
)


def test_unitless_slider_builds() -> None:
    """A slider with no unit must not set unit_of_measurement to None.

    NumberSelectorConfig validates that key as a plain str, so passing None
    raises and takes the whole options form down.
    """
    selector = _slider(0, 1, 0.05)

    assert "unit_of_measurement" not in selector.config


def test_slider_with_unit_keeps_it() -> None:
    """A slider given a unit still carries it through."""
    selector = _slider(MIN_TRANSITION, MAX_TRANSITION, 0.1, "seconds")

    assert selector.config["unit_of_measurement"] == "seconds"


def test_slider_bounds_are_preserved() -> None:
    """Min, max, and step survive into the selector config."""
    selector = _slider(MIN_IDLE_GRACE, MAX_IDLE_GRACE, 1, "seconds")

    assert selector.config["min"] == MIN_IDLE_GRACE
    assert selector.config["max"] == MAX_IDLE_GRACE
    assert selector.config["step"] == 1


@pytest.mark.parametrize(
    "options",
    [SWATCH_KEYS, DISTRIBUTION_MODES, ON_IDLE_MODES],
)
def test_select_builds_for_every_dropdown(options: list[str]) -> None:
    """Every dropdown in the options form constructs cleanly."""
    selector = _select("swatch", options)

    assert selector.config["options"] == options


def test_every_options_slider_builds() -> None:
    """Build each slider the options form uses, exactly as it does."""
    sliders = [
        _slider(MIN_IDLE_GRACE, MAX_IDLE_GRACE, 1, "seconds"),
        _slider(MIN_TRANSITION, MAX_TRANSITION, 0.1, "seconds"),
        _slider(0, 1, 0.05),
        _slider(0, 1, 0.05),
    ]

    assert len(sliders) == 4


def test_selectors_validate_a_plausible_value() -> None:
    """A selector rejects an out-of-range value rather than passing it through."""
    selector = _slider(0, 1, 0.05)

    assert selector(0.4) == 0.4

    with pytest.raises(vol.Invalid):
        selector(5)
