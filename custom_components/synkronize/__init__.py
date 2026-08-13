"""Synkronize - set your lights to the vibrant color of the artwork that is playing.

For more details about this integration, please refer to
https://github.com/zthijs/synkronize
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import PLATFORMS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Synkronize from a config entry.

    There is nothing to poll and no session to establish - the light entity owns
    the media player watcher - so setup is just forwarding the platform.
    """
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
