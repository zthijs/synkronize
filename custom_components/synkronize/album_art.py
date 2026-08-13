"""Fetch the artwork a media player is currently showing.

A ``media_player`` publishes its artwork as the ``entity_picture`` attribute.
That is usually a *relative*, pre-signed path served by Home Assistant's own
media proxy::

    /api/media_player_proxy/media_player.spotify?token=<signed>&cache=<hash>

Because the token is already signed, fetching it back over HTTP needs no auth
header - it just needs to be turned into an absolute URL first. Some players
(Sonos, some DLNA renderers) publish an absolute CDN URL instead, which we pass
through untouched.

The ``cache=`` component of the proxy URL changes whenever the artwork changes,
which makes the URL itself a correct cache key upstream.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import ALBUM_ART_TIMEOUT, LOGGER, MAX_ALBUM_ART_BYTES

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class AlbumArtError(Exception):
    """Raised when artwork could not be resolved or downloaded."""


def resolve_artwork_url(hass: HomeAssistant, picture: str) -> str:
    """Turn a media player's ``entity_picture`` into an absolute URL."""
    if picture.startswith(("http://", "https://")):
        return picture

    try:
        base_url = get_url(
            hass,
            prefer_external=False,
            allow_internal=True,
            allow_ip=True,
            require_ssl=False,
            require_standard_port=False,
        )
    except NoURLAvailableError as err:
        msg = (
            "No internal Home Assistant URL is available to resolve the artwork path "
            f"'{picture}'. Set one under Settings > System > Network."
        )
        raise AlbumArtError(msg) from err

    return f"{base_url}{picture}"


async def async_fetch_artwork(hass: HomeAssistant, url: str) -> bytes:
    """Download artwork bytes, guarding against oversized and non-image responses."""
    session = async_get_clientsession(hass)
    timeout = aiohttp.ClientTimeout(total=ALBUM_ART_TIMEOUT)

    try:
        async with session.get(url, timeout=timeout) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            data = await response.content.read(MAX_ALBUM_ART_BYTES + 1)
    except (aiohttp.ClientError, TimeoutError) as err:
        msg = f"Could not download artwork from {url}: {err}"
        raise AlbumArtError(msg) from err

    if content_type and not content_type.startswith("image/"):
        msg = f"Artwork at {url} is not an image (Content-Type: {content_type})"
        raise AlbumArtError(msg)

    if not data:
        msg = f"Artwork at {url} was empty"
        raise AlbumArtError(msg)

    if len(data) > MAX_ALBUM_ART_BYTES:
        msg = f"Artwork at {url} is larger than the {MAX_ALBUM_ART_BYTES} byte limit"
        raise AlbumArtError(msg)

    LOGGER.debug("Downloaded %d bytes of artwork from %s", len(data), url)
    return data
