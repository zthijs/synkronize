"""Tests for snapshot serialization.

The serialize/rehydrate pair is what lets a snapshot survive a restart or an
options save. If it breaks, "put my lights back" silently restores the colors
Synkronize itself applied - so it is worth pinning down.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from homeassistant.core import State

from custom_components.synkronize.snapshot import LightSnapshot

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _snapshot_of(*states: State) -> LightSnapshot:
    """Build a snapshot holding ``states`` without needing a running hass."""
    snapshot = LightSnapshot(cast("HomeAssistant", None))
    snapshot.load(
        [
            {
                "entity_id": state.entity_id,
                "state": state.state,
                "attributes": dict(state.attributes),
            }
            for state in states
        ]
    )
    return snapshot


def test_round_trip_preserves_restorable_attributes() -> None:
    """Serializing and rehydrating keeps what the light restore needs."""
    original = State(
        "light.bed_light",
        "on",
        {"brightness": 77, "rgb_color": (0, 255, 0), "color_mode": "rgb"},
    )

    restored = _snapshot_of(original).as_list()

    assert restored == [
        {
            "entity_id": "light.bed_light",
            "state": "on",
            "attributes": {
                "brightness": 77,
                "color_mode": "rgb",
                "rgb_color": (0, 255, 0),
            },
        }
    ]


def test_unrestorable_attributes_are_dropped() -> None:
    """Attributes the light restore ignores are not carried around."""
    state = State(
        "light.bed_light",
        "on",
        {
            "brightness": 100,
            "friendly_name": "Bed Light",
            "supported_features": 44,
            "supported_color_modes": ["rgb"],
        },
    )

    attributes = _snapshot_of(state).as_list()[0]["attributes"]

    assert attributes == {"brightness": 100}


def test_off_state_round_trips() -> None:
    """A light that was off comes back as off."""
    entry = _snapshot_of(State("light.bed_light", "off", {})).as_list()[0]

    assert entry["state"] == "off"
    assert entry["attributes"] == {}


def test_load_replaces_any_previous_capture() -> None:
    """Rehydrating overwrites whatever the snapshot held."""
    snapshot = _snapshot_of(State("light.one", "on", {"brightness": 1}))
    snapshot.load([{"entity_id": "light.two", "state": "off", "attributes": {}}])

    assert [entry["entity_id"] for entry in snapshot.as_list()] == ["light.two"]


def test_empty_snapshot_serializes_to_an_empty_list() -> None:
    """A snapshot with nothing captured stores nothing."""
    snapshot = LightSnapshot(cast("HomeAssistant", None))

    assert snapshot.as_list() == []
    assert not snapshot.has_capture


def test_load_sets_has_capture() -> None:
    """A rehydrated snapshot counts as a capture, so it is not overwritten."""
    snapshot = _snapshot_of(State("light.bed_light", "on", {"brightness": 5}))

    assert snapshot.has_capture

    snapshot.clear()

    assert not snapshot.has_capture
