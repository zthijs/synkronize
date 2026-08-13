"""The Synkronize light - a facade over the lights being synced to album art.

One entity per config entry. Turning it on starts watching the configured media
player and takes the lights over; turning it off hands them back according to
the idle behaviour. The effect dropdown picks which extracted swatch to use, so
the whole feature works from a stock Tile or Mushroom card with no custom card.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import voluptuous as vol
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ENTITY_ID_FORMAT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import STATE_ON
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

from .album_art import AlbumArtError, async_fetch_artwork, resolve_artwork_url
from .color_extractor import (
    RGBColor,
    async_extract_palette,
    build_swatches,
    color_hex,
    prepare_for_lamp,
    rank_by_vibrancy,
)
from .const import (
    ATTR_ALBUM_ART_URL,
    ATTR_APPLIED_COLORS,
    ATTR_COLOR_HEX,
    ATTR_DOMINANT_HUE,
    ATTR_DOMINANT_LIGHTNESS,
    ATTR_DOMINANT_SATURATION,
    ATTR_EXTRACTED_PALETTE,
    ATTR_FAILED_LIGHTS,
    ATTR_IMAGE_URL,
    ATTR_LAST_ERROR,
    ATTR_LAST_SYNC,
    ATTR_LIGHT_COUNT,
    ATTR_LIGHT_ENTITIES,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_TITLE,
    ATTR_SOURCE_MEDIA_PLAYER,
    ATTR_SWATCHES,
    ATTR_SYNC_STATE,
    CONF_BOOST,
    CONF_DISTRIBUTION,
    CONF_IDLE_GRACE,
    CONF_LIGHT_ENTITIES,
    CONF_MEDIA_PLAYER,
    CONF_MIN_SATURATION,
    CONF_ON_IDLE,
    CONF_SWATCH,
    CONF_TRANSITION,
    DEFAULT_BOOST,
    DEFAULT_BRIGHTNESS,
    DEFAULT_DISTRIBUTION,
    DEFAULT_IDLE_GRACE,
    DEFAULT_MIN_SATURATION,
    DEFAULT_ON_IDLE,
    DEFAULT_SWATCH,
    DEFAULT_TRANSITION,
    DISTRIBUTION_UNIFORM,
    DOMAIN,
    EFFECT_NAMES,
    LOGGER,
    MANUFACTURER,
    MODEL,
    ON_IDLE_OFF,
    ON_IDLE_RESTORE,
    SERVICE_APPLY_IMAGE,
    SERVICE_RESYNC,
    SWATCH_BY_EFFECT,
    SWATCH_CACHE_SIZE,
    SWATCH_DOMINANT,
    SYNC_STATE_DISABLED,
    SYNC_STATE_MANUAL,
    SYNC_STATE_SYNCED,
    SYNC_STATE_WAITING,
)
from .light_controller import LightController
from .media_watcher import MediaWatcher
from .snapshot import LightSnapshot

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .color_extractor import Swatch

_FALLBACK_RGB: RGBColor = (255, 255, 255)


@dataclass
class SynkronizeExtraData(ExtraStoredData):
    """The pre-sync light snapshot, persisted alongside the entity's state.

    Home Assistant restores the entity's own state for free, but the snapshot of
    *other* entities is ours to carry. Without it a restart or an options save
    (which reloads the entry) would lose the user's original light state while
    sync is running, and the restore-on-idle behaviour would put back the colors
    Synkronize applied instead.
    """

    snapshot: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        """Return the data in a JSON-serializable form."""
        return {"snapshot": self.snapshot}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Synkronize light and its entity services."""
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(SERVICE_RESYNC, None, "async_resync")
    platform.async_register_entity_service(
        SERVICE_APPLY_IMAGE,
        {vol.Required(ATTR_IMAGE_URL): cv.string},
        "async_apply_image",
    )

    async_add_entities([SynkronizeLight(hass, entry)])


class SynkronizeLight(LightEntity, RestoreEntity):
    """A light whose color follows the artwork of a media player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the entity from its config entry."""
        self.hass = hass
        self._entry = entry
        self._media_player: str = entry.data[CONF_MEDIA_PLAYER]
        self._light_entities: list[str] = list(entry.data[CONF_LIGHT_ENTITIES])

        self._attr_unique_id = f"{entry.entry_id}_light"
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{DOMAIN} {entry.title}",
            hass=hass,
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

        self._is_on = False
        self._brightness = DEFAULT_BRIGHTNESS
        self._effect: str = EFFECT_NAMES.get(
            self._option(CONF_SWATCH, DEFAULT_SWATCH),
            EFFECT_NAMES[DEFAULT_SWATCH],
        )
        self._rgb: RGBColor = _FALLBACK_RGB
        self._manual_color: RGBColor | None = None

        self._palette: list[RGBColor] = []
        self._swatches: dict[str, Swatch] = {}
        self._palette_cache: OrderedDict[str, list[RGBColor]] = OrderedDict()

        self._applied_colors: dict[str, str] = {}
        self._failed_lights: dict[str, str] = {}
        self._last_error: str | None = None
        self._last_sync: str | None = None
        self._sync_state = SYNC_STATE_DISABLED

        self._lock = asyncio.Lock()

        self._controller = LightController(hass)
        self._snapshot = LightSnapshot(hass)
        self._watcher = MediaWatcher(
            hass,
            self._media_player,
            self._async_on_artwork,
            self._async_on_idle,
        )

    def _option(self, key: str, default: Any) -> Any:
        """Read an option, falling back to its default."""
        return self._entry.options.get(key, default)

    @property
    def _transition(self) -> float:
        """Return the fade duration used for every color change."""
        return float(self._option(CONF_TRANSITION, DEFAULT_TRANSITION))

    @property
    def _boost(self) -> float:
        """Return how far extracted colors are pushed toward full saturation."""
        return float(self._option(CONF_BOOST, DEFAULT_BOOST))

    async def async_added_to_hass(self) -> None:
        """Restore the previous on/off state and brightness, then resume syncing.

        The effect is deliberately *not* restored from the last state: the
        selected swatch lives in the entry options (picking an effect writes it
        back there), so the options are the single source of truth and a freshly
        saved option is never clobbered by a stale restored value.
        """
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._is_on = last_state.state == STATE_ON
            self._brightness = (
                last_state.attributes.get(ATTR_BRIGHTNESS) or DEFAULT_BRIGHTNESS
            )

        if (extra := await self.async_get_last_extra_data()) is not None:
            self._snapshot.load(extra.as_dict().get("snapshot") or [])

        if self._is_on:
            self._sync_state = SYNC_STATE_WAITING
            await self._async_start_watching()

    async def async_will_remove_from_hass(self) -> None:
        """Stop watching the media player."""
        self._watcher.shutdown()
        await super().async_will_remove_from_hass()

    @property
    def extra_restore_state_data(self) -> SynkronizeExtraData:
        """Persist the pre-sync snapshot across restarts and reloads."""
        return SynkronizeExtraData(self._snapshot.as_list())

    @property
    def is_on(self) -> bool:
        """Return whether syncing is enabled."""
        return self._is_on

    @property
    def brightness(self) -> int:
        """Return the brightness applied to the underlying lights."""
        return self._brightness

    @property
    def rgb_color(self) -> RGBColor:
        """Return the color currently being shown."""
        return self._rgb

    @property
    def effect(self) -> str:
        """Return the selected swatch, as its display name."""
        return self._effect

    @property
    def effect_list(self) -> list[str]:
        """Return the selectable swatches."""
        return list(EFFECT_NAMES.values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostics and template-friendly color data."""
        attributes: dict[str, Any] = {
            ATTR_SOURCE_MEDIA_PLAYER: self._media_player,
            ATTR_LIGHT_ENTITIES: self._light_entities,
            ATTR_LIGHT_COUNT: len(self._light_entities),
            ATTR_SYNC_STATE: self._sync_state,
            ATTR_COLOR_HEX: color_hex(self._rgb),
            ATTR_APPLIED_COLORS: self._applied_colors,
        }

        media_state = self.hass.states.get(self._media_player)
        if media_state is not None:
            attributes[ATTR_MEDIA_TITLE] = media_state.attributes.get("media_title")
            attributes[ATTR_MEDIA_ARTIST] = media_state.attributes.get("media_artist")

        if self._watcher.artwork:
            attributes[ATTR_ALBUM_ART_URL] = self._watcher.artwork

        if self._palette:
            attributes[ATTR_EXTRACTED_PALETTE] = [
                list(color) for color in self._palette
            ]

        if self._swatches:
            attributes[ATTR_SWATCHES] = {
                key: swatch.hex_color for key, swatch in self._swatches.items()
            }
            dominant = self._swatches[SWATCH_DOMINANT]
            attributes[ATTR_DOMINANT_HUE] = round(dominant.hue, 1)
            attributes[ATTR_DOMINANT_SATURATION] = round(dominant.saturation, 2)
            attributes[ATTR_DOMINANT_LIGHTNESS] = round(dominant.lightness, 2)

        if self._last_sync:
            attributes[ATTR_LAST_SYNC] = self._last_sync
        if self._last_error:
            attributes[ATTR_LAST_ERROR] = self._last_error
        if self._failed_lights:
            attributes[ATTR_FAILED_LIGHTS] = self._failed_lights

        return attributes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable syncing, and optionally change swatch, brightness, or color."""
        async with self._lock:
            was_off = not self._is_on
            self._is_on = True
            self._last_error = None
            self._failed_lights = {}

            if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
                self._brightness = brightness

            if (effect := kwargs.get(ATTR_EFFECT)) in SWATCH_BY_EFFECT:
                self._effect = effect
                self._manual_color = None
                self._persist_swatch(SWATCH_BY_EFFECT[effect])

            if was_off:
                await self._async_start_watching()

            rgb_color = kwargs.get(ATTR_RGB_COLOR)
            if rgb_color is not None:
                self._manual_color = (rgb_color[0], rgb_color[1], rgb_color[2])
                await self._async_apply_uniform(self._manual_color, SYNC_STATE_MANUAL)
            elif self._manual_color is not None:
                await self._async_apply_uniform(self._manual_color, SYNC_STATE_MANUAL)
            else:
                await self._async_sync_to_artwork(self._watcher.artwork)

            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Disable syncing and hand the lights back."""
        async with self._lock:
            self._is_on = False
            self._manual_color = None
            self._sync_state = SYNC_STATE_DISABLED

            self._watcher.stop()
            await self._async_release_lights()

            self.async_write_ha_state()

    async def async_resync(self) -> None:
        """Re-download the current artwork and re-apply it, ignoring the cache."""
        async with self._lock:
            if not self._is_on:
                LOGGER.debug("Ignoring resync - syncing is disabled")
                return

            self._manual_color = None
            await self._async_sync_to_artwork(
                self._watcher.current_picture(),
                force=True,
            )
            self.async_write_ha_state()

    async def async_apply_image(self, image_url: str) -> None:
        """Apply the colors of an arbitrary image, ignoring the media player."""
        async with self._lock:
            try:
                url = resolve_artwork_url(self.hass, image_url)
            except AlbumArtError as err:
                self._fail(str(err))
            else:
                palette = await self._async_palette_for(url)
                if palette:
                    self._snapshot.capture(self._light_entities)
                    await self._async_apply_palette(palette, SYNC_STATE_MANUAL)

            self.async_write_ha_state()

    async def _async_on_artwork(self, artwork: str) -> None:
        """Handle the media player showing new artwork."""
        async with self._lock:
            if not self._is_on:
                return

            self._manual_color = None
            await self._async_sync_to_artwork(artwork)
            self.async_write_ha_state()

    async def _async_on_idle(self) -> None:
        """Handle playback having stopped for longer than the grace period."""
        async with self._lock:
            if not self._is_on or self._sync_state == SYNC_STATE_WAITING:
                return

            LOGGER.debug(
                "Playback idle - running the '%s' behaviour",
                self._option(CONF_ON_IDLE, DEFAULT_ON_IDLE),
            )
            await self._async_release_lights()
            self._sync_state = SYNC_STATE_WAITING
            self.async_write_ha_state()

    async def _async_start_watching(self) -> None:
        """Snapshot the lights and start watching the media player."""
        self._snapshot.capture(self._light_entities)
        await self._watcher.async_start(
            float(self._option(CONF_IDLE_GRACE, DEFAULT_IDLE_GRACE))
        )

    async def _async_release_lights(self) -> None:
        """Hand the underlying lights back per the configured idle behaviour."""
        on_idle = self._option(CONF_ON_IDLE, DEFAULT_ON_IDLE)

        if on_idle == ON_IDLE_RESTORE:
            await self._snapshot.async_restore(self._transition)
        elif on_idle == ON_IDLE_OFF:
            await self._controller.async_turn_off(
                self._light_entities, self._transition
            )
            self._snapshot.clear()
        else:
            self._snapshot.clear()

        self._applied_colors = {}

    async def _async_sync_to_artwork(
        self,
        artwork: str | None,
        *,
        force: bool = False,
    ) -> None:
        """Extract colors from ``artwork`` and push them to the lights.

        ``force`` drops the cached palette first, so a cover that changed behind
        an unchanged URL is picked up.
        """
        if artwork is None:
            self._sync_state = SYNC_STATE_WAITING
            return

        try:
            url = resolve_artwork_url(self.hass, artwork)
        except AlbumArtError as err:
            self._fail(str(err))
            return

        if force:
            self._palette_cache.pop(url, None)

        palette = await self._async_palette_for(url)
        if not palette:
            return

        self._snapshot.capture(self._light_entities)
        await self._async_apply_palette(palette, SYNC_STATE_SYNCED)

    async def _async_palette_for(self, url: str) -> list[RGBColor]:
        """Return the palette for an image URL, downloading it only if needed."""
        if (cached := self._palette_cache.get(url)) is not None:
            self._palette_cache.move_to_end(url)
            LOGGER.debug("Reusing the cached palette for %s", url)
            return cached

        try:
            data = await async_fetch_artwork(self.hass, url)
        except AlbumArtError as err:
            self._fail(str(err))
            return []

        palette = await async_extract_palette(self.hass, data)
        if not palette:
            self._fail(f"No colors could be extracted from the artwork at {url}")
            return []

        self._palette_cache[url] = palette
        while len(self._palette_cache) > SWATCH_CACHE_SIZE:
            self._palette_cache.popitem(last=False)

        return palette

    async def _async_apply_palette(
        self, palette: list[RGBColor], sync_state: str
    ) -> None:
        """Turn a palette into per-light colors and apply them."""
        self._palette = palette
        self._swatches = build_swatches(
            palette,
            float(self._option(CONF_MIN_SATURATION, DEFAULT_MIN_SATURATION)),
        )

        swatch_key = SWATCH_BY_EFFECT.get(self._effect, DEFAULT_SWATCH)
        swatch = self._swatches.get(swatch_key) or self._swatches[SWATCH_DOMINANT]
        chosen = prepare_for_lamp(swatch.rgb, self._boost)

        await self._async_apply(
            self._colors_for(palette, swatch.rgb, chosen), chosen, sync_state
        )

    def _colors_for(
        self,
        palette: list[RGBColor],
        swatch_rgb: RGBColor,
        chosen: RGBColor,
    ) -> dict[str, RGBColor]:
        """Map each configured light to the color it should show."""
        if (
            self._option(CONF_DISTRIBUTION, DEFAULT_DISTRIBUTION)
            == DISTRIBUTION_UNIFORM
        ):
            return dict.fromkeys(self._light_entities, chosen)

        ordered = [
            swatch_rgb,
            *(color for color in rank_by_vibrancy(palette) if color != swatch_rgb),
        ]
        prepared = [prepare_for_lamp(color, self._boost) for color in ordered]

        return {
            entity_id: prepared[index % len(prepared)]
            for index, entity_id in enumerate(self._light_entities)
        }

    async def _async_apply_uniform(self, color: RGBColor, sync_state: str) -> None:
        """Apply a single color to every configured light."""
        await self._async_apply(
            dict.fromkeys(self._light_entities, color), color, sync_state
        )

    async def _async_apply(
        self,
        light_colors: dict[str, RGBColor],
        displayed: RGBColor,
        sync_state: str,
    ) -> None:
        """Push colors to the lights and record the outcome."""
        result = await self._controller.async_apply_colors(
            light_colors,
            self._transition,
            self._brightness,
        )

        self._applied_colors = result.applied_colors
        self._failed_lights = result.failed_lights

        if result.all_failed:
            self._last_error = "None of the configured lights could be updated"
            return

        self._rgb = displayed
        self._sync_state = sync_state
        self._last_sync = dt_util.utcnow().isoformat()
        self._last_error = (
            f"{result.failed_count} of {len(result.results)} lights failed"
            if self._failed_lights
            else None
        )

    def _persist_swatch(self, swatch_key: str) -> None:
        """Write an effect chosen from the dropdown back into the entry options.

        This keeps the options flow and the effect dropdown from disagreeing:
        there is exactly one stored answer to "which swatch". Safe to call from
        a service handler - no update listener is registered on the entry, so
        this does not trigger a reload.
        """
        if self._option(CONF_SWATCH, DEFAULT_SWATCH) == swatch_key:
            return

        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_SWATCH: swatch_key},
        )

    def _fail(self, message: str) -> None:
        """Record an error on the entity so it is visible without reading logs."""
        LOGGER.error(message)
        self._last_error = message
