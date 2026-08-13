"""Constants for the Synkronize integration."""

from __future__ import annotations

from logging import Logger, getLogger
from typing import Final

from homeassistant.const import Platform

LOGGER: Logger = getLogger(__package__)

DOMAIN: Final = "synkronize"
MANUFACTURER: Final = "Synkronize"
MODEL: Final = "Album Art Sync"

PLATFORMS: Final[list[Platform]] = [Platform.LIGHT]


CONF_MEDIA_PLAYER: Final = "media_player"
CONF_LIGHT_ENTITIES: Final = "light_entities"


CONF_SWATCH: Final = "swatch"
CONF_DISTRIBUTION: Final = "distribution"
CONF_ON_IDLE: Final = "on_idle"
CONF_IDLE_GRACE: Final = "idle_grace_seconds"
CONF_TRANSITION: Final = "transition"
CONF_BOOST: Final = "boost"
CONF_MIN_SATURATION: Final = "min_saturation"


SWATCH_VIBRANT: Final = "vibrant"
SWATCH_LIGHT_VIBRANT: Final = "light_vibrant"
SWATCH_DARK_VIBRANT: Final = "dark_vibrant"
SWATCH_MUTED: Final = "muted"
SWATCH_DOMINANT: Final = "dominant"

SWATCH_KEYS: Final[list[str]] = [
    SWATCH_VIBRANT,
    SWATCH_LIGHT_VIBRANT,
    SWATCH_DARK_VIBRANT,
    SWATCH_MUTED,
    SWATCH_DOMINANT,
]

EFFECT_NAMES: Final[dict[str, str]] = {
    SWATCH_VIBRANT: "Vibrant",
    SWATCH_LIGHT_VIBRANT: "Light Vibrant",
    SWATCH_DARK_VIBRANT: "Dark Vibrant",
    SWATCH_MUTED: "Muted",
    SWATCH_DOMINANT: "Dominant",
}

SWATCH_BY_EFFECT: Final[dict[str, str]] = {
    name: key for key, name in EFFECT_NAMES.items()
}


DISTRIBUTION_UNIFORM: Final = "uniform"
DISTRIBUTION_SPREAD: Final = "spread"
DISTRIBUTION_MODES: Final[list[str]] = [DISTRIBUTION_UNIFORM, DISTRIBUTION_SPREAD]


ON_IDLE_RESTORE: Final = "restore"
ON_IDLE_HOLD: Final = "hold"
ON_IDLE_OFF: Final = "off"
ON_IDLE_MODES: Final[list[str]] = [ON_IDLE_RESTORE, ON_IDLE_HOLD, ON_IDLE_OFF]


DEFAULT_SWATCH: Final = SWATCH_VIBRANT
DEFAULT_DISTRIBUTION: Final = DISTRIBUTION_SPREAD
DEFAULT_ON_IDLE: Final = ON_IDLE_RESTORE
DEFAULT_BRIGHTNESS: Final = 255

DEFAULT_IDLE_GRACE: Final = 10
MIN_IDLE_GRACE: Final = 0
MAX_IDLE_GRACE: Final = 600

DEFAULT_TRANSITION: Final = 2.0
MIN_TRANSITION: Final = 0.0
MAX_TRANSITION: Final = 30.0

DEFAULT_BOOST: Final = 0.4

DEFAULT_MIN_SATURATION: Final = 0.35


PALETTE_SIZE: Final = 10

EXTRACTION_QUALITY: Final = 5


ALBUM_ART_TIMEOUT: Final = 15
MAX_ALBUM_ART_BYTES: Final = 8 * 1024 * 1024

SWATCH_CACHE_SIZE: Final = 32


ACTIVE_MEDIA_STATES: Final[frozenset[str]] = frozenset({"playing", "buffering"})

UPDATE_DEBOUNCE: Final = 1.5


SERVICE_RESYNC: Final = "resync"
SERVICE_APPLY_IMAGE: Final = "apply_image"

ATTR_IMAGE_URL: Final = "image_url"


ATTR_SOURCE_MEDIA_PLAYER: Final = "source_media_player"
ATTR_MEDIA_TITLE: Final = "media_title"
ATTR_MEDIA_ARTIST: Final = "media_artist"
ATTR_ALBUM_ART_URL: Final = "album_art_url"
ATTR_EXTRACTED_PALETTE: Final = "extracted_palette"
ATTR_SWATCHES: Final = "swatches"
ATTR_COLOR_HEX: Final = "color_hex"
ATTR_DOMINANT_HUE: Final = "dominant_hue"
ATTR_DOMINANT_SATURATION: Final = "dominant_saturation"
ATTR_DOMINANT_LIGHTNESS: Final = "dominant_lightness"
ATTR_LIGHT_ENTITIES: Final = "light_entities"
ATTR_LIGHT_COUNT: Final = "light_count"
ATTR_APPLIED_COLORS: Final = "applied_colors"
ATTR_SYNC_STATE: Final = "sync_state"
ATTR_LAST_SYNC: Final = "last_sync"
ATTR_LAST_ERROR: Final = "last_error"
ATTR_FAILED_LIGHTS: Final = "failed_lights"

SYNC_STATE_DISABLED: Final = "disabled"
SYNC_STATE_WAITING: Final = "waiting"
SYNC_STATE_SYNCED: Final = "synced"
SYNC_STATE_MANUAL: Final = "manual"
