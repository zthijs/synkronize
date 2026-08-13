"""Extract a vibrant color from album artwork.

ColorThief gives us the *most common* colors in an image, ordered by dominance.
For album art that is rarely what we want on a lamp: the most common color of a
cover is very often a near-black background or a washed-out grey, which renders
as "lamp is basically off".

So this module scores ColorThief's palette rather than trusting its order. The
scoring follows the same idea as Android's Palette API - a candidate is judged
on how close its saturation and lightness sit to a target, with its population
as a tiebreaker. ColorThief exposes no population counts, so a palette entry's
rank stands in for population: entry 0 is the most common color in the image.

Everything except :func:`async_extract_palette` is a pure function, so the
scoring can be unit-tested without a Home Assistant instance.
"""

from __future__ import annotations

import colorsys
import io
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final

from colorthief import ColorThief

from .const import (
    EXTRACTION_QUALITY,
    LOGGER,
    PALETTE_SIZE,
    SWATCH_DARK_VIBRANT,
    SWATCH_DOMINANT,
    SWATCH_LIGHT_VIBRANT,
    SWATCH_MUTED,
    SWATCH_VIBRANT,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

type RGBColor = tuple[int, int, int]

_WEIGHT_SATURATION: Final = 3.0
_WEIGHT_LIGHTNESS: Final = 6.0
_WEIGHT_POPULATION: Final = 1.0
_WEIGHT_TOTAL: Final = _WEIGHT_SATURATION + _WEIGHT_LIGHTNESS + _WEIGHT_POPULATION

_RELAXATION_STEPS: Final = 3
_SATURATION_RELAXATION: Final = 0.5
_LIGHTNESS_RELAXATION: Final = 0.15

_MIN_LAMP_LIGHTNESS: Final = 0.20
_MAX_LAMP_LIGHTNESS: Final = 0.90


@dataclass(frozen=True, slots=True)
class SwatchTarget:
    """The region of HSL space a swatch should ideally land in.

    ``target_*`` values are what the scorer aims for; the ``min_saturation`` and
    lightness bounds decide which palette entries are eligible at all.
    """

    target_saturation: float
    target_lightness: float
    min_saturation: float
    min_lightness: float
    max_lightness: float


@dataclass(frozen=True, slots=True)
class Swatch:
    """A scored color picked out of an image's palette."""

    rgb: RGBColor
    hue: float
    saturation: float
    lightness: float
    score: float

    @property
    def hex_color(self) -> str:
        """Return the color as ``#rrggbb``."""
        return color_hex(self.rgb)


TARGETS: Final[dict[str, SwatchTarget]] = {
    SWATCH_VIBRANT: SwatchTarget(
        target_saturation=1.0,
        target_lightness=0.50,
        min_saturation=0.35,
        min_lightness=0.30,
        max_lightness=0.70,
    ),
    SWATCH_LIGHT_VIBRANT: SwatchTarget(
        target_saturation=1.0,
        target_lightness=0.74,
        min_saturation=0.35,
        min_lightness=0.55,
        max_lightness=1.00,
    ),
    SWATCH_DARK_VIBRANT: SwatchTarget(
        target_saturation=1.0,
        target_lightness=0.26,
        min_saturation=0.35,
        min_lightness=0.00,
        max_lightness=0.45,
    ),
    SWATCH_MUTED: SwatchTarget(
        target_saturation=0.30,
        target_lightness=0.50,
        min_saturation=0.00,
        min_lightness=0.30,
        max_lightness=0.70,
    ),
}


def color_hex(rgb: RGBColor) -> str:
    """Return an RGB tuple formatted as ``#rrggbb``."""
    red, green, blue = rgb
    return f"#{red:02x}{green:02x}{blue:02x}"


def to_hsl(rgb: RGBColor) -> tuple[float, float, float]:
    """Convert an RGB tuple to ``(hue 0-360, saturation 0-1, lightness 0-1)``."""
    hue, lightness, saturation = colorsys.rgb_to_hls(
        rgb[0] / 255, rgb[1] / 255, rgb[2] / 255
    )
    return (hue * 360, saturation, lightness)


def from_hsl(hue: float, saturation: float, lightness: float) -> RGBColor:
    """Convert ``(hue 0-360, saturation 0-1, lightness 0-1)`` back to RGB."""
    red, green, blue = colorsys.hls_to_rgb(hue / 360, lightness, saturation)
    return (round(red * 255), round(green * 255), round(blue * 255))


def _score(
    saturation: float, lightness: float, rank: int, total: int, target: SwatchTarget
) -> float:
    """Score one palette entry against a target, in the range 0-1.

    ``rank`` is the entry's index in the dominance-ordered palette and stands in
    for the population count ColorThief does not expose.
    """
    saturation_score = 1.0 - abs(saturation - target.target_saturation)
    lightness_score = 1.0 - abs(lightness - target.target_lightness)
    population_score = 1.0 - (rank / max(total - 1, 1))

    return (
        _WEIGHT_SATURATION * saturation_score
        + _WEIGHT_LIGHTNESS * lightness_score
        + _WEIGHT_POPULATION * population_score
    ) / _WEIGHT_TOTAL


def _relax(target: SwatchTarget, step: int) -> SwatchTarget:
    """Widen a target's eligibility window by ``step`` relaxation rounds.

    The final step opens the window completely, so any non-empty palette is
    guaranteed to produce a swatch.
    """
    if step <= 0:
        return target
    if step >= _RELAXATION_STEPS:
        return replace(target, min_saturation=0.0, min_lightness=0.0, max_lightness=1.0)

    return replace(
        target,
        min_saturation=target.min_saturation * (_SATURATION_RELAXATION**step),
        min_lightness=max(0.0, target.min_lightness - _LIGHTNESS_RELAXATION * step),
        max_lightness=min(1.0, target.max_lightness + _LIGHTNESS_RELAXATION * step),
    )


def _best_in_window(
    palette: list[RGBColor], window: SwatchTarget, target: SwatchTarget
) -> Swatch | None:
    """Return the highest-scoring palette entry that fits inside ``window``.

    ``window`` decides who is eligible, ``target`` decides what "good" means.
    They differ once relaxation kicks in.
    """
    total = len(palette)
    best: Swatch | None = None

    for rank, rgb in enumerate(palette):
        hue, saturation, lightness = to_hsl(rgb)
        if saturation < window.min_saturation:
            continue
        if not window.min_lightness <= lightness <= window.max_lightness:
            continue

        candidate = Swatch(
            rgb=rgb,
            hue=hue,
            saturation=saturation,
            lightness=lightness,
            score=_score(saturation, lightness, rank, total, target),
        )
        if best is None or candidate.score > best.score:
            best = candidate

    return best


def select_swatch(palette: list[RGBColor], target: SwatchTarget) -> Swatch | None:
    """Pick the best-scoring palette entry for ``target``.

    Eligibility is relaxed in rounds until at least one candidate qualifies, but
    scoring always happens against the *original* target - relaxing decides who
    may compete, not what "good" means.
    """
    if not palette:
        return None

    for step in range(_RELAXATION_STEPS + 1):
        best = _best_in_window(palette, _relax(target, step), target)
        if best is not None:
            return best

    return None


def build_swatches(palette: list[RGBColor], min_saturation: float) -> dict[str, Swatch]:
    """Build every named swatch for a palette.

    ``min_saturation`` raises or lowers the eligibility floor for the vibrant
    family only - the muted target deliberately wants low-saturation colors.
    Always includes a ``dominant`` swatch (ColorThief's own first choice) so
    users have an escape hatch back to unscored behaviour.
    """
    if not palette:
        return {}

    swatches: dict[str, Swatch] = {}
    for key, target in TARGETS.items():
        window = (
            target
            if key == SWATCH_MUTED
            else replace(target, min_saturation=min_saturation)
        )
        swatch = select_swatch(palette, window)
        if swatch is not None:
            swatches[key] = swatch

    hue, saturation, lightness = to_hsl(palette[0])
    swatches[SWATCH_DOMINANT] = Swatch(
        rgb=palette[0],
        hue=hue,
        saturation=saturation,
        lightness=lightness,
        score=1.0,
    )
    return swatches


def rank_by_vibrancy(palette: list[RGBColor]) -> list[RGBColor]:
    """Order a whole palette most- to least-vibrant.

    Used to spread colors across several lights: light 1 gets the most vibrant
    color, light 2 the next, and so on. No eligibility filtering here - the
    score alone pushes dull colors to the back.
    """
    target = TARGETS[SWATCH_VIBRANT]
    total = len(palette)

    scored: list[tuple[float, RGBColor]] = []
    for rank, rgb in enumerate(palette):
        _, saturation, lightness = to_hsl(rgb)
        scored.append((_score(saturation, lightness, rank, total, target), rgb))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [rgb for _, rgb in scored]


def boost_saturation(rgb: RGBColor, boost: float) -> RGBColor:
    """Push a color's saturation toward fully saturated by ``boost`` (0-1).

    This is the difference between a color that merely *came from* the artwork
    and one that reads as vibrant once a lamp renders it.
    """
    if boost <= 0:
        return rgb

    hue, saturation, lightness = to_hsl(rgb)
    return from_hsl(hue, saturation + (1.0 - saturation) * min(boost, 1.0), lightness)


def clamp_for_lamp(rgb: RGBColor) -> RGBColor:
    """Pull a color's lightness into the band a lamp can actually render.

    Near-black looks like the light failed to turn on, and near-white throws
    away the color entirely.
    """
    hue, saturation, lightness = to_hsl(rgb)
    clamped = min(max(lightness, _MIN_LAMP_LIGHTNESS), _MAX_LAMP_LIGHTNESS)
    if clamped == lightness:
        return rgb
    return from_hsl(hue, saturation, clamped)


def prepare_for_lamp(rgb: RGBColor, boost: float) -> RGBColor:
    """Apply the saturation boost and the lamp lightness clamp, in that order."""
    return clamp_for_lamp(boost_saturation(rgb, boost))


def _sync_extract_palette(
    data: bytes, color_count: int, quality: int
) -> list[RGBColor]:
    """Run ColorThief over raw image bytes. Blocking - call in an executor."""
    thief = ColorThief(io.BytesIO(data))
    try:
        palette = thief.get_palette(color_count=color_count, quality=quality)
    except Exception:  # noqa: BLE001
        palette = []

    if palette:
        return [(int(red), int(green), int(blue)) for red, green, blue in palette]

    red, green, blue = thief.get_color(quality=quality)
    return [(int(red), int(green), int(blue))]


async def async_extract_palette(
    hass: HomeAssistant,
    data: bytes,
    color_count: int = PALETTE_SIZE,
    quality: int = EXTRACTION_QUALITY,
) -> list[RGBColor]:
    """Extract a dominance-ordered color palette from raw image bytes."""
    try:
        palette = await hass.async_add_executor_job(
            _sync_extract_palette, data, color_count, quality
        )
    except Exception:  # noqa: BLE001
        LOGGER.exception("Failed to extract a color palette from the artwork")
        return []

    LOGGER.debug(
        "Extracted %d colors from %d bytes of artwork", len(palette), len(data)
    )
    return palette
