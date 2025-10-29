"""Support for Nanoleaf Lines segment groups."""
from __future__ import annotations

import logging
from typing import Any

import requests

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEFAULT_GROUP_SIZE

_LOGGER = logging.getLogger(__name__)

# Store for tracking group states
GROUP_STATES = {}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nanoleaf Lines segment groups from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_name = entry.data.get("name", "Nanoleaf Lines")
    
    # Get all segments from coordinator data
    segments = coordinator.data.get("segments", [])
    
    # Create groups based on position/angle
    groups = create_groups_by_position(segments, DEFAULT_GROUP_SIZE)
    
    # Create group entities
    entities = [
        NanoleafSegmentGroup(coordinator, entry, group_segments, idx, device_name)
        for idx, group_segments in enumerate(groups)
    ]
    
    _LOGGER.info("Setting up %d Nanoleaf Lines segment groups", len(entities))
    async_add_entities(entities)


def create_groups_by_position(segments: list[dict], group_size: int) -> list[list[dict]]:
    """Create groups of segments based on their position."""
    # Sort by angle (computed in debug script)
    sorted_segments = sorted(segments, key=lambda s: s.get("angle_deg", 0))
    
    # Split into groups
    groups = []
    for i in range(0, len(sorted_segments), group_size):
        group = sorted_segments[i:i + group_size]
        groups.append(group)
    
    return groups


class NanoleafSegmentGroup(CoordinatorEntity, LightEntity):
    """Representation of a group of Nanoleaf Lines segments."""

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        segments: list[dict],
        index: int,
        device_name: str,
    ) -> None:
        """Initialize the segment group."""
        super().__init__(coordinator)
        
        self._segments = segments
        self._panel_ids = [seg["panelId"] for seg in segments]
        self._index = index
        self._entry = entry
        self._device_name = device_name
        
        # Entity attributes
        self._attr_unique_id = f"{entry.entry_id}_group_{index}"
        self._attr_name = f"Group {index + 1}"
        
        # Safe name for entity_id
        safe_name = device_name.lower().replace(" ", "_")
        self._attr_entity_id = f"light.{safe_name}_group_{index + 1}"
        
        # Initialize state in global store
        state_key = f"{entry.entry_id}_group_{index}"
        if state_key not in GROUP_STATES:
            GROUP_STATES[state_key] = {
                "is_on": True,
                "brightness": 255,
                "rgb_color": (255, 255, 255),
            }
    
    @property
    def _state_key(self) -> str:
        """Get the state key for this group."""
        return f"{self._entry.entry_id}_group_{self._index}"
    
    @property
    def _group_state(self) -> dict:
        """Get the state for this group."""
        return GROUP_STATES.get(self._state_key, {
            "is_on": True,
            "brightness": 255,
            "rgb_color": (255, 255, 255),
        })

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Nanoleaf device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._device_name,
            manufacturer="Nanoleaf",
            model="Lines",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        state = self._group_state
        if self.coordinator.data:
            state_data = self.coordinator.data.get("state", {})
            global_on = state_data.get("on", {}).get("value", True)
            return state.get("is_on", True) and global_on
        return state.get("is_on", True)

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._group_state.get("brightness", 255)

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the RGB color value."""
        return self._group_state.get("rgb_color", (255, 255, 255))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "panel_ids": self._panel_ids,
            "group_id": self._index,
            "segment_count": len(self._segments),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light group."""
        state = self._group_state
        state["is_on"] = True
        
        if ATTR_BRIGHTNESS in kwargs:
            state["brightness"] = kwargs[ATTR_BRIGHTNESS]
        
        if ATTR_RGB_COLOR in kwargs:
            state["rgb_color"] = tuple(kwargs[ATTR_RGB_COLOR])
        
        transition = kwargs.get(ATTR_TRANSITION, 0)
        
        # Apply the color change to all segments in group
        await self._async_set_group_color(transition)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light group."""
        state = self._group_state
        state["is_on"] = False
        
        transition = kwargs.get(ATTR_TRANSITION, 0)
        
        # Set group panels to black (off)
        await self._async_set_group_color(transition)
        self.async_write_ha_state()

    async def _async_set_group_color(self, transition: float = 0) -> None:
        """Set the color of panels in this group only (Ambilight optimized with UDP)."""
        try:
            state = self._group_state
            
            # Determine color based on on/off state
            if state.get("is_on", False):
                r, g, b = state.get("rgb_color", (255, 255, 255))
                brightness = state.get("brightness", 255)
                # Apply brightness to RGB
                factor = brightness / 255
                r = int(r * factor)
                g = int(g * factor)
                b = int(b * factor)
            else:
                r, g, b = 0, 0, 0
            
            # Build panel_colors dict ONLY for this group's panels
            panel_colors = {}
            for panel_id in self._panel_ids:
                panel_colors[panel_id] = (r, g, b)
            
            # Use UDP streaming with smooth interpolation
            # The Nanoleafs will internally fade between colors!
            def _send_batch():
                return self.coordinator.api.set_multiple_panels_udp(panel_colors, smooth=True)
            
            # Direct call without waiting - maximum speed!
            try:
                self.coordinator.api.set_multiple_panels_udp(panel_colors, smooth=True)
            except Exception:
                # Fallback to async if direct fails
                self.hass.loop.call_soon_threadsafe(
                    lambda: self.hass.async_add_executor_job(_send_batch)
                )
            
            _LOGGER.debug(
                "Sent group %d (%d panels) to RGB(%d, %d, %d)",
                self._index, len(self._panel_ids), r, g, b
            )
            
        except Exception as err:
            _LOGGER.error("Failed to set group %d color: %s", self._index, err)

