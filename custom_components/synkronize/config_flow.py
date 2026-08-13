"""Config and options flows for Synkronize."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
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
    DEFAULT_DISTRIBUTION,
    DEFAULT_IDLE_GRACE,
    DEFAULT_MIN_SATURATION,
    DEFAULT_ON_IDLE,
    DEFAULT_SWATCH,
    DEFAULT_TRANSITION,
    DISTRIBUTION_MODES,
    DOMAIN,
    MAX_IDLE_GRACE,
    MAX_TRANSITION,
    MIN_IDLE_GRACE,
    MIN_TRANSITION,
    ON_IDLE_MODES,
    SWATCH_KEYS,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _friendly_name(hass: HomeAssistant, entity_id: str) -> str:
    """Return an entity's friendly name, falling back to its entity id."""
    state = hass.states.get(entity_id)
    if state is None:
        return entity_id
    return state.attributes.get("friendly_name") or entity_id


def _entry_title(hass: HomeAssistant, media_player: str) -> str:
    """Build the entry title, such as ``Walkman Sync``."""
    return f"{_friendly_name(hass, media_player)} Sync"


def _select(key: str, options: list[str]) -> SelectSelector:
    """Build a translated dropdown selector."""
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            mode=SelectSelectorMode.DROPDOWN,
            translation_key=key,
        )
    )


def _slider(
    minimum: float, maximum: float, step: float, unit: str | None = None
) -> NumberSelector:
    """Build a slider selector.

    ``unit_of_measurement`` is omitted rather than set to ``None`` for unitless
    sliders: NumberSelectorConfig validates the key as a plain ``str``, so
    passing ``None`` raises and takes the whole options form down with it.
    """
    config = NumberSelectorConfig(
        min=minimum,
        max=maximum,
        step=step,
        mode=NumberSelectorMode.SLIDER,
    )
    if unit is not None:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


class SynkronizeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of a Synkronize entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which media player to follow and which lights to drive."""
        errors: dict[str, str] = {}

        if user_input is not None:
            media_player: str = user_input[CONF_MEDIA_PLAYER]
            lights: list[str] = user_input[CONF_LIGHT_ENTITIES]

            if not lights:
                errors[CONF_LIGHT_ENTITIES] = "no_lights"
            else:
                await self.async_set_unique_id(
                    f"{media_player}::{'_'.join(sorted(lights))}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=_entry_title(self.hass, media_player),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MEDIA_PLAYER): EntitySelector(
                        EntitySelectorConfig(domain="media_player")
                    ),
                    vol.Required(CONF_LIGHT_ENTITIES): EntitySelector(
                        EntitySelectorConfig(domain="light", multiple=True)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SynkronizeOptionsFlow:  # noqa: ARG004
        """Return the options flow for this entry."""
        return SynkronizeOptionsFlow()


class SynkronizeOptionsFlow(OptionsFlowWithReload):
    """Tune how colors are chosen and what happens when playback stops.

    Subclassing ``OptionsFlowWithReload`` means the entry reloads itself on save,
    so no manual update listener is needed to pick the new values up.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SWATCH,
                        default=options.get(CONF_SWATCH, DEFAULT_SWATCH),
                    ): _select(CONF_SWATCH, SWATCH_KEYS),
                    vol.Required(
                        CONF_DISTRIBUTION,
                        default=options.get(CONF_DISTRIBUTION, DEFAULT_DISTRIBUTION),
                    ): _select(CONF_DISTRIBUTION, DISTRIBUTION_MODES),
                    vol.Required(
                        CONF_ON_IDLE,
                        default=options.get(CONF_ON_IDLE, DEFAULT_ON_IDLE),
                    ): _select(CONF_ON_IDLE, ON_IDLE_MODES),
                    vol.Required(
                        CONF_IDLE_GRACE,
                        default=options.get(CONF_IDLE_GRACE, DEFAULT_IDLE_GRACE),
                    ): _slider(MIN_IDLE_GRACE, MAX_IDLE_GRACE, 1, "seconds"),
                    vol.Required(
                        CONF_TRANSITION,
                        default=options.get(CONF_TRANSITION, DEFAULT_TRANSITION),
                    ): _slider(MIN_TRANSITION, MAX_TRANSITION, 0.1, "seconds"),
                    vol.Required(
                        CONF_BOOST,
                        default=options.get(CONF_BOOST, DEFAULT_BOOST),
                    ): _slider(0, 1, 0.05),
                    vol.Required(
                        CONF_MIN_SATURATION,
                        default=options.get(
                            CONF_MIN_SATURATION, DEFAULT_MIN_SATURATION
                        ),
                    ): _slider(0, 1, 0.05),
                }
            ),
        )
