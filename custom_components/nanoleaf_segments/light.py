"""Support for Nanoleaf Lines individual segment lights."""
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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Store for tracking individual segment states
SEGMENT_STATES = {}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nanoleaf Lines segments from a config entry."""
    domain_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = domain_data["coordinator"]
    create_groups = domain_data.get("create_groups", True)
    device_name = entry.data.get("name", "Nanoleaf Lines")
    
    # Get all segments from coordinator data
    segments = coordinator.data.get("segments", [])
    
    # Create segment entities
    entities = [
        NanoleafSegmentLight(coordinator, entry, segment, idx, device_name)
        for idx, segment in enumerate(segments)
    ]
    
    _LOGGER.info("Setting up %d Nanoleaf Lines segment lights", len(entities))
    
    # Create group entities if enabled
    if create_groups:
        from .group import NanoleafSegmentGroup
        from .const import CONF_MANUAL_GROUPS, DEFAULT_GROUP_SIZE
        
        # Check for manual groups in options
        manual_groups = entry.options.get(CONF_MANUAL_GROUPS)
        
        if manual_groups:
            # Use manual groups (indices)
            groups = []
            for group_indices in manual_groups:
                group_segments = [segments[i] for i in group_indices if i < len(segments)]
                if group_segments:
                    groups.append(group_segments)
        else:
            # Use automatic grouping
            from .group import create_groups_by_position
            groups = create_groups_by_position(segments, DEFAULT_GROUP_SIZE)
        
        group_entities = [
            NanoleafSegmentGroup(coordinator, entry, group_segments, idx, device_name)
            for idx, group_segments in enumerate(groups)
        ]
        
        _LOGGER.info("Setting up %d Nanoleaf Lines segment groups", len(group_entities))
        entities.extend(group_entities)
    
    async_add_entities(entities)


class NanoleafSegmentLight(CoordinatorEntity, LightEntity):
    """Representation of a single Nanoleaf Lines segment."""

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_should_poll = True

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        segment: dict,
        index: int,
        device_name: str,
    ) -> None:
        """Initialize the segment light."""
        super().__init__(coordinator)
        
        self._segment = segment
        self._panel_id = segment["panelId"]
        self._index = index
        self._entry = entry
        self._device_name = device_name
        
        # Entity attributes
        self._attr_unique_id = f"{entry.entry_id}_segment_{self._panel_id}"
        self._attr_name = f"Segment {index + 1}"
        
        # Safe name for entity_id
        safe_name = device_name.lower().replace(" ", "_")
        self._attr_entity_id = f"light.{safe_name}_segment_{index + 1}"
        
        # Initialize state in global store if not exists
        state_key = f"{entry.entry_id}_{self._panel_id}"
        if state_key not in SEGMENT_STATES:
            SEGMENT_STATES[state_key] = {
                "is_on": True,
                "brightness": 255,
                "rgb_color": (255, 255, 255),
            }
    
    @property
    def _state_key(self) -> str:
        """Get the state key for this segment."""
        return f"{self._entry.entry_id}_{self._panel_id}"
    
    @property
    def _segment_state(self) -> dict:
        """Get the state for this segment."""
        return SEGMENT_STATES.get(self._state_key, {
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
        state = self._segment_state
        # Check both segment and global state
        if self.coordinator.data:
            state_data = self.coordinator.data.get("state", {})
            global_on = state_data.get("on", {}).get("value", True)
            return state.get("is_on", True) and global_on
        return state.get("is_on", True)

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._segment_state.get("brightness", 255)

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the RGB color value."""
        return self._segment_state.get("rgb_color", (255, 255, 255))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "panel_id": self._panel_id,
            "position_x": self._segment.get("x"),
            "position_y": self._segment.get("y"),
            "orientation": self._segment.get("o"),
            "shape_type": self._segment.get("shapeType"),
            "segment_index": self._index,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light segment."""
        state = self._segment_state
        state["is_on"] = True
        
        if ATTR_BRIGHTNESS in kwargs:
            state["brightness"] = kwargs[ATTR_BRIGHTNESS]
        
        if ATTR_RGB_COLOR in kwargs:
            state["rgb_color"] = tuple(kwargs[ATTR_RGB_COLOR])
        
        transition = kwargs.get(ATTR_TRANSITION, 0)
        
        # Apply the color change
        await self._async_set_panel_color(transition)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light segment."""
        state = self._segment_state
        state["is_on"] = False
        
        transition = kwargs.get(ATTR_TRANSITION, 0)
        
        # Set panel to black (off)
        await self._async_set_panel_color(transition)
        self.async_write_ha_state()

    async def _async_set_panel_color(self, transition: float = 0) -> None:
        """Set the color of this specific panel using custom effect."""
        try:
            state = self._segment_state
            
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
            
            # Convert transition time to tenths of a second
            transition_time = int(transition * 10)
            
            # Build animData for ALL segments to preserve their states
            # Format: numPanels panelId1 frames R G B W time ...
            all_segments = self.coordinator.data.get("segments", [])
            anim_parts = []
            
            for seg in all_segments:
                seg_panel_id = seg["panelId"]
                seg_state_key = f"{self._entry.entry_id}_{seg_panel_id}"
                
                if seg_panel_id == self._panel_id:
                    # This is the panel we're updating
                    anim_parts.append(f"{seg_panel_id} 1 {r} {g} {b} 0 {transition_time}")
                else:
                    # Preserve other panels' states
                    seg_state = SEGMENT_STATES.get(seg_state_key, {
                        "is_on": True,
                        "brightness": 255,
                        "rgb_color": (255, 255, 255)
                    })
                    
                    if seg_state.get("is_on", True):
                        seg_r, seg_g, seg_b = seg_state.get("rgb_color", (255, 255, 255))
                        seg_brightness = seg_state.get("brightness", 255)
                        seg_factor = seg_brightness / 255
                        seg_r = int(seg_r * seg_factor)
                        seg_g = int(seg_g * seg_factor)
                        seg_b = int(seg_b * seg_factor)
                    else:
                        seg_r, seg_g, seg_b = 0, 0, 0
                    
                    anim_parts.append(f"{seg_panel_id} 1 {seg_r} {seg_g} {seg_b} 0 {transition_time}")
            
            num_panels = len(all_segments)
            anim_data = f"{num_panels} " + " ".join(anim_parts)
            
            # Send the complete effect
            url = f"{self.coordinator.api.base_url}/effects"
            effect_data = {
                "write": {
                    "command": "display",
                    "animType": "custom",
                    "animData": anim_data,
                    "loop": False,
                    "palette": []
                }
            }
            
            def _send_effect():
                return requests.put(url, json=effect_data, timeout=5)
            
            await self.hass.async_add_executor_job(_send_effect)
            
            _LOGGER.debug(
                "Set panel %s to RGB(%d, %d, %d) with transition %d",
                self._panel_id, r, g, b, transition_time
            )
            
        except Exception as err:
            _LOGGER.error("Failed to set panel %s color: %s", self._panel_id, err)

