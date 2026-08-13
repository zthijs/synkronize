"""Tests for the vibrancy scoring in ``color_extractor``.

Everything exercised here is a pure function, so no Home Assistant instance is
needed. The point of these tests is the behaviour that motivates the whole
module: on real album art, the *most common* color is usually not the color you
want on a lamp.
"""

from __future__ import annotations

import pytest

from custom_components.synkronize.color_extractor import (
    TARGETS,
    Swatch,
    boost_saturation,
    build_swatches,
    clamp_for_lamp,
    color_hex,
    from_hsl,
    prepare_for_lamp,
    rank_by_vibrancy,
    select_swatch,
    to_hsl,
)
from custom_components.synkronize.const import (
    SWATCH_DARK_VIBRANT,
    SWATCH_DOMINANT,
    SWATCH_LIGHT_VIBRANT,
    SWATCH_MUTED,
    SWATCH_VIBRANT,
)

COVER_PALETTE = [
    (18, 18, 20),
    (96, 94, 90),
    (210, 205, 198),
    (222, 45, 38),
    (60, 120, 190),
]

GREYSCALE_PALETTE = [
    (10, 10, 10),
    (128, 128, 128),
    (245, 245, 245),
]


def test_color_hex() -> None:
    """Colors format as lowercase six-digit hex."""
    assert color_hex((222, 45, 38)) == "#de2d26"
    assert color_hex((0, 0, 0)) == "#000000"


def test_hsl_round_trip() -> None:
    """RGB survives a trip through HSL and back."""
    for rgb in COVER_PALETTE:
        hue, saturation, lightness = to_hsl(rgb)
        assert from_hsl(hue, saturation, lightness) == rgb


def test_vibrant_beats_dominant() -> None:
    """The vibrant swatch skips the dominant near-black background."""
    swatches = build_swatches(COVER_PALETTE, min_saturation=0.35)

    assert swatches[SWATCH_DOMINANT].rgb == COVER_PALETTE[0]
    assert swatches[SWATCH_VIBRANT].rgb != COVER_PALETTE[0]
    assert swatches[SWATCH_VIBRANT].rgb in {(222, 45, 38), (60, 120, 190)}


def test_vibrant_is_saturated_and_mid_lightness() -> None:
    """The vibrant swatch lands inside its own target window."""
    swatch = build_swatches(COVER_PALETTE, min_saturation=0.35)[SWATCH_VIBRANT]
    target = TARGETS[SWATCH_VIBRANT]

    assert swatch.saturation >= target.min_saturation
    assert target.min_lightness <= swatch.lightness <= target.max_lightness


def test_light_and_dark_vibrant_differ_in_lightness() -> None:
    """Light and dark vibrant pull toward opposite ends of the lightness range."""
    swatches = build_swatches(
        [*COVER_PALETTE, (255, 170, 160), (70, 10, 8)],
        min_saturation=0.35,
    )

    assert (
        swatches[SWATCH_LIGHT_VIBRANT].lightness
        > swatches[SWATCH_DARK_VIBRANT].lightness
    )


def test_muted_prefers_low_saturation() -> None:
    """The muted swatch is less saturated than the vibrant one."""
    swatches = build_swatches(COVER_PALETTE, min_saturation=0.35)

    assert swatches[SWATCH_MUTED].saturation < swatches[SWATCH_VIBRANT].saturation


def test_greyscale_artwork_still_yields_a_swatch() -> None:
    """A cover with no saturated color relaxes rather than returning nothing."""
    swatches = build_swatches(GREYSCALE_PALETTE, min_saturation=0.35)

    assert SWATCH_VIBRANT in swatches
    assert swatches[SWATCH_VIBRANT].rgb in GREYSCALE_PALETTE


def test_empty_palette_yields_no_swatches() -> None:
    """An empty palette produces nothing rather than raising."""
    assert build_swatches([], min_saturation=0.35) == {}


def test_select_swatch_on_empty_palette() -> None:
    """Selecting from an empty palette returns None."""
    assert select_swatch([], TARGETS[SWATCH_VIBRANT]) is None


def test_min_saturation_option_is_respected() -> None:
    """Raising the floor pushes the choice toward more saturated colors."""
    relaxed = build_swatches(COVER_PALETTE, min_saturation=0.0)[SWATCH_VIBRANT]
    strict = build_swatches(COVER_PALETTE, min_saturation=0.6)[SWATCH_VIBRANT]

    assert strict.saturation >= 0.6
    assert strict.saturation >= relaxed.saturation


def test_rank_by_vibrancy_orders_the_whole_palette() -> None:
    """Ranking keeps every color and puts the dull background last."""
    ranked = rank_by_vibrancy(COVER_PALETTE)

    assert sorted(ranked) == sorted(COVER_PALETTE)
    assert ranked[-1] == (18, 18, 20)


def test_rank_by_vibrancy_on_empty_palette() -> None:
    """Ranking an empty palette returns an empty list."""
    assert rank_by_vibrancy([]) == []


def test_boost_raises_saturation() -> None:
    """Boosting moves a color toward fully saturated without changing its hue."""
    muddy = (140, 110, 100)
    boosted = boost_saturation(muddy, 0.5)

    original_hue, original_saturation, _ = to_hsl(muddy)
    boosted_hue, boosted_saturation, _ = to_hsl(boosted)

    assert boosted_saturation > original_saturation
    assert boosted_hue == pytest.approx(original_hue, abs=1.0)


def test_zero_boost_is_a_no_op() -> None:
    """A boost of zero leaves the color untouched."""
    assert boost_saturation((140, 110, 100), 0) == (140, 110, 100)


def test_clamp_pulls_near_black_into_range() -> None:
    """Near-black is lifted so the lamp does not read as switched off."""
    _, _, lightness = to_hsl(clamp_for_lamp((8, 4, 4)))

    assert lightness >= 0.19


def test_clamp_pulls_near_white_into_range() -> None:
    """Near-white is pulled down so some color survives."""
    _, _, lightness = to_hsl(clamp_for_lamp((252, 250, 250)))

    assert lightness <= 0.91


def test_clamp_leaves_mid_range_colors_alone() -> None:
    """A color already in range comes back byte-identical."""
    assert clamp_for_lamp((222, 45, 38)) == (222, 45, 38)


def test_prepare_for_lamp_applies_both_steps() -> None:
    """Preparation boosts saturation and clamps lightness in one call."""
    prepared = prepare_for_lamp((20, 14, 12), 0.8)
    _, saturation, lightness = to_hsl(prepared)

    assert saturation > to_hsl((20, 14, 12))[1]
    assert lightness >= 0.19


def test_swatch_hex_color() -> None:
    """A swatch renders itself as hex."""
    swatch = Swatch(
        rgb=(222, 45, 38), hue=2.0, saturation=0.7, lightness=0.51, score=0.9
    )

    assert swatch.hex_color == "#de2d26"
