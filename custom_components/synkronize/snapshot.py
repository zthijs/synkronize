"""Remember what the lights looked like before Synkronize took them over.

Restoring uses :func:`homeassistant.helpers.state.async_reproduce_state` - the
same public helper Home Assistant's own scene component uses - so brightness,
RGB, color temperature, and effects all round-trip correctly whatever color mode
each light happens to be in. Doing it via ``scene.create`` would work too, but
would litter the user's instance with ``scene.*`` entities.

A snapshot also survives restarts and config-entry reloads: it can serialize
itself so the light entity can stash it alongside its restored state. Without
that, a reload while syncing would re-capture the colors *Synkronize itself*
applied, and "put my lights back" would quietly become a no-op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    ATTR_XY_COLOR,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State
from homeassistant.helpers.state import async_reproduce_state

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_RESTORED_ATTRIBUTES = (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_WHITE,
    ATTR_XY_COLOR,
)


class LightSnapshot:
    """Holds a captured light state and knows how to put it back."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize an empty snapshot."""
        self._hass = hass
        self._states: list[State] = []

    @property
    def has_capture(self) -> bool:
        """Return whether there is a captured state to restore."""
        return bool(self._states)

    def capture(self, entity_ids: list[str]) -> None:
        """Capture the current state of ``entity_ids``.

        A snapshot already held is kept - re-capturing while sync is running
        would record the colors Synkronize itself applied, which is exactly what
        the user does not want restored.
        """
        if self._states:
            return

        states: list[State] = []
        for entity_id in entity_ids:
            state = self._hass.states.get(entity_id)
            if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                LOGGER.debug("Not snapshotting %s - it has no usable state", entity_id)
                continue
            states.append(state)

        self._states = states
        LOGGER.debug("Snapshotted %d of %d lights", len(states), len(entity_ids))

    def clear(self) -> None:
        """Drop the captured state without restoring it."""
        self._states = []

    def as_list(self) -> list[dict[str, Any]]:
        """Serialize the snapshot so it can survive a restart or reload."""
        return [
            {
                "entity_id": state.entity_id,
                "state": state.state,
                "attributes": {
                    key: state.attributes[key]
                    for key in _RESTORED_ATTRIBUTES
                    if key in state.attributes
                },
            }
            for state in self._states
        ]

    def load(self, data: list[dict[str, Any]]) -> None:
        """Rehydrate a snapshot previously produced by :meth:`as_list`."""
        self._states = [
            State(item["entity_id"], item["state"], item.get("attributes") or {})
            for item in data
        ]
        if self._states:
            LOGGER.debug("Reloaded a snapshot of %d lights", len(self._states))

    async def async_restore(self, transition: float) -> None:
        """Restore the captured state and drop it."""
        if not self._states:
            return

        states, self._states = self._states, []
        LOGGER.debug("Restoring %d lights to their pre-sync state", len(states))
        await async_reproduce_state(
            self._hass,
            states,
            reproduce_options={ATTR_TRANSITION: transition},
        )
