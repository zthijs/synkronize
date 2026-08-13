"""Apply colors to the user's real lights, with per-light error tracking.

Everything that talks to the underlying ``light`` entities goes through here, so
availability checks, RGB capability checks, and failure reporting behave
identically whether a color came from a track change, a service call, or the
light entity's own turn_on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ColorMode,
)
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

from .color_extractor import color_hex
from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .color_extractor import RGBColor


class LightError(Enum):
    """Why a light could not be given a color."""

    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"
    NO_RGB_SUPPORT = "no_rgb_support"
    SERVICE_CALL_FAILED = "service_call_failed"


@dataclass
class LightResult:
    """Outcome of applying a color to one light."""

    entity_id: str
    success: bool
    color: RGBColor | None = None
    error: LightError | None = None
    error_message: str | None = None


@dataclass
class ApplyColorsResult:
    """Outcome of applying colors to a group of lights."""

    results: list[LightResult] = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        """Return whether every light accepted its color."""
        return bool(self.results) and all(result.success for result in self.results)

    @property
    def all_failed(self) -> bool:
        """Return whether no light accepted its color."""
        return bool(self.results) and not any(result.success for result in self.results)

    @property
    def succeeded_count(self) -> int:
        """Return how many lights accepted their color."""
        return sum(1 for result in self.results if result.success)

    @property
    def failed_count(self) -> int:
        """Return how many lights did not accept their color."""
        return sum(1 for result in self.results if not result.success)

    @property
    def applied_colors(self) -> dict[str, str]:
        """Return the colors that actually landed, as ``entity_id -> #rrggbb``."""
        return {
            result.entity_id: color_hex(result.color)
            for result in self.results
            if result.success and result.color is not None
        }

    @property
    def failed_lights(self) -> dict[str, str]:
        """Return the lights that failed, as ``entity_id -> reason``."""
        return {
            result.entity_id: result.error_message or str(result.error)
            for result in self.results
            if not result.success
        }


class LightController:
    """Applies colors to light entities and reports what happened."""

    RGB_COLOR_MODES: ClassVar[set[ColorMode]] = {
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
        ColorMode.HS,
        ColorMode.XY,
    }

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the controller."""
        self.hass = hass

    def check_light_availability(
        self, entity_id: str
    ) -> tuple[bool, LightError | None, str | None]:
        """Check that a light exists, is online, and can show an RGB color."""
        state = self.hass.states.get(entity_id)

        if state is None:
            return (
                False,
                LightError.NOT_FOUND,
                f"Light entity '{entity_id}' does not exist",
            )

        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return (
                False,
                LightError.UNAVAILABLE,
                f"Light '{entity_id}' is {state.state}",
            )

        supported_modes = state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) or []
        if supported_modes and not set(supported_modes) & self.RGB_COLOR_MODES:
            return (
                False,
                LightError.NO_RGB_SUPPORT,
                f"Light '{entity_id}' cannot show RGB colors ({supported_modes})",
            )

        return (True, None, None)

    async def async_apply_color(
        self,
        entity_id: str,
        color: RGBColor,
        transition: float,
        brightness: int | None = None,
    ) -> LightResult:
        """Apply one color to one light. Availability is assumed to be checked."""
        service_data: dict[str, object] = {
            ATTR_ENTITY_ID: entity_id,
            ATTR_RGB_COLOR: list(color),
            ATTR_TRANSITION: transition,
        }
        if brightness is not None:
            service_data[ATTR_BRIGHTNESS] = brightness

        try:
            await self.hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                service_data,
                blocking=True,
            )
        except Exception as err:  # noqa: BLE001
            message = f"Failed to apply a color to {entity_id}: {err}"
            LOGGER.error(message)
            return LightResult(
                entity_id=entity_id,
                success=False,
                color=color,
                error=LightError.SERVICE_CALL_FAILED,
                error_message=message,
            )

        LOGGER.debug(
            "Applied RGB%s to %s (transition=%ss)", color, entity_id, transition
        )
        return LightResult(entity_id=entity_id, success=True, color=color)

    async def async_apply_colors(
        self,
        light_colors: dict[str, RGBColor],
        transition: float,
        brightness: int | None = None,
    ) -> ApplyColorsResult:
        """Apply a color per light, skipping any light that cannot take one."""
        result = ApplyColorsResult()

        for entity_id, color in light_colors.items():
            is_available, error, message = self.check_light_availability(entity_id)
            if not is_available:
                LOGGER.warning("Skipping light: %s", message)
                result.results.append(
                    LightResult(
                        entity_id=entity_id,
                        success=False,
                        error=error,
                        error_message=message,
                    )
                )
                continue

            result.results.append(
                await self.async_apply_color(entity_id, color, transition, brightness)
            )

        if result.all_failed:
            LOGGER.error(
                "None of the %d configured lights could be updated", len(result.results)
            )
        elif not result.all_succeeded:
            LOGGER.warning(
                "Updated %d of %d lights",
                result.succeeded_count,
                len(result.results),
            )

        return result

    async def async_turn_off(self, entity_ids: list[str], transition: float) -> None:
        """Turn off every underlying light."""
        for entity_id in entity_ids:
            try:
                await self.hass.services.async_call(
                    LIGHT_DOMAIN,
                    "turn_off",
                    {ATTR_ENTITY_ID: entity_id, ATTR_TRANSITION: transition},
                    blocking=True,
                )
            except Exception as err:  # noqa: BLE001
                LOGGER.error("Failed to turn off %s: %s", entity_id, err)
