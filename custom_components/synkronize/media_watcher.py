"""Watch a media player and say when its artwork changed.

A playing ``media_player`` fires a state event every second or so as
``media_position`` advances. Almost none of those matter to us: the only thing
that changes the color is the artwork. So this watcher filters on
``entity_picture`` and debounces what is left, which keeps skipping through a
few tracks from firing a color change per skip.

Non-playing states start a grace timer rather than reacting immediately, so a
brief pause holds the current color and only a real stop hands the lights back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.core import callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .const import ACTIVE_MEDIA_STATES, LOGGER, UPDATE_DEBOUNCE

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.core import (
        CALLBACK_TYPE,
        Event,
        EventStateChangedData,
        HomeAssistant,
    )


class MediaWatcher:
    """Reports artwork changes and idle periods for one media player."""

    def __init__(
        self,
        hass: HomeAssistant,
        media_player: str,
        on_artwork: Callable[[str], Awaitable[None]],
        on_idle: Callable[[], Awaitable[None]],
    ) -> None:
        """Initialize the watcher. Nothing is observed until ``async_start``."""
        self._hass = hass
        self._media_player = media_player
        self._on_artwork = on_artwork
        self._on_idle = on_idle

        self._idle_grace: float = 0
        self._artwork: str | None = None
        self._pending_artwork: str | None = None
        self._unsub_state: CALLBACK_TYPE | None = None
        self._unsub_idle: CALLBACK_TYPE | None = None
        self._debouncer = Debouncer(
            hass,
            LOGGER,
            cooldown=UPDATE_DEBOUNCE,
            immediate=False,
            function=self._async_fire_artwork,
        )

    @property
    def artwork(self) -> str | None:
        """Return the artwork path the media player is currently showing."""
        return self._artwork

    async def async_start(self, idle_grace: float) -> None:
        """Begin watching, and evaluate the player's current state right away."""
        self._idle_grace = idle_grace
        if self._unsub_state is None:
            self._unsub_state = async_track_state_change_event(
                self._hass,
                [self._media_player],
                self._handle_state_change,
            )
            LOGGER.debug("Watching %s", self._media_player)

        await self._async_evaluate()

    @callback
    def stop(self) -> None:
        """Stop watching and cancel anything pending.

        Reusable: ``async_start`` can be called again afterwards. Note this
        cancels the debouncer rather than shutting it down - ``async_shutdown``
        drops the debouncer's reference to its callback, which would leave a
        restarted watcher silently unable to report anything.
        """
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        self._cancel_idle_timer()
        self._debouncer.async_cancel()
        self._pending_artwork = None
        LOGGER.debug("Stopped watching %s", self._media_player)

    @callback
    def shutdown(self) -> None:
        """Stop watching for good, releasing the debouncer's callback."""
        self.stop()
        self._debouncer.async_shutdown()

    @callback
    def current_picture(self) -> str | None:
        """Read the player's artwork path straight from its current state.

        Unlike :attr:`artwork` this is not cleared when playback goes idle, so a
        manual resync still has something to work with.
        """
        state = self._hass.states.get(self._media_player)
        return state.attributes.get(ATTR_ENTITY_PICTURE) if state else None

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Handle a state event from the watched media player.

        A playing media player emits an event roughly every second as its
        position advances. Filtering those out here, synchronously, avoids
        spawning a task per tick.
        """
        new_state = event.data["new_state"]
        if new_state is None:
            return

        old_state = event.data["old_state"]
        if (
            old_state is not None
            and old_state.state == new_state.state
            and old_state.attributes.get(ATTR_ENTITY_PICTURE)
            == new_state.attributes.get(ATTR_ENTITY_PICTURE)
        ):
            return

        self._hass.async_create_task(self._async_evaluate())

    async def _async_evaluate(self) -> None:
        """Compare the player's current state against what we last acted on."""
        state = self._hass.states.get(self._media_player)
        if state is None:
            LOGGER.warning("Media player %s does not exist", self._media_player)
            return

        picture = state.attributes.get(ATTR_ENTITY_PICTURE)

        if state.state not in ACTIVE_MEDIA_STATES:
            self._schedule_idle()
            return

        self._cancel_idle_timer()

        if not picture:
            return

        if picture == self._artwork:
            return

        self._artwork = picture
        self._pending_artwork = picture
        await self._debouncer.async_call()

    async def _async_fire_artwork(self) -> None:
        """Hand the debounced artwork change to the owner."""
        picture, self._pending_artwork = self._pending_artwork, None
        if picture is not None:
            await self._on_artwork(picture)

    @callback
    def _schedule_idle(self) -> None:
        """Start the grace timer that ends in the idle behaviour firing."""
        if self._unsub_idle is not None:
            return

        self._artwork = None

        if self._idle_grace <= 0:
            self._hass.async_create_task(self._on_idle())
            return

        self._unsub_idle = async_call_later(
            self._hass, self._idle_grace, self._handle_idle_timeout
        )

    @callback
    def _handle_idle_timeout(self, _now: object) -> None:
        """Fire the idle behaviour once the grace period has elapsed."""
        self._unsub_idle = None
        self._hass.async_create_task(self._on_idle())

    @callback
    def _cancel_idle_timer(self) -> None:
        """Cancel a pending idle timer, if any."""
        if self._unsub_idle is not None:
            self._unsub_idle()
            self._unsub_idle = None
