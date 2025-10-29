"""The Nanoleaf Lines integration."""
from __future__ import annotations

import asyncio
import logging
import socket
import struct
from datetime import timedelta

import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CREATE_GROUPS,
    CONF_TOKEN,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SHAPE_TYPE_LINE_SEGMENT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]


def get_platforms(entry):
    """Get platforms based on config."""
    platforms = [Platform.LIGHT]
    # Groups are registered via light platform
    return platforms


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nanoleaf Lines from a config entry."""
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]

    # Create API client
    api = NanoleafAPI(host, token)

    # Test connection and fetch initial data
    try:
        await hass.async_add_executor_job(api.get_layout)
        
        # Enable External Control for smooth streaming
        await hass.async_add_executor_job(api.enable_external_control)
        
    except Exception as err:
        _LOGGER.error("Failed to connect to Nanoleaf device: %s", err)
        raise ConfigEntryNotReady from err

    # Create update coordinator
    coordinator = NanoleafDataUpdateCoordinator(hass, api)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "create_groups": entry.data.get(CONF_CREATE_GROUPS, True),
    }

    # Register services
    async def handle_set_multiple_segments(call):
        """Handle the set_multiple_segments service call."""
        segment_colors_input = call.data.get("segment_colors", {})
        transition = call.data.get("transition", 0)
        
        # Convert segment indices to panel IDs and colors
        segments = coordinator.data.get("segments", [])
        panel_colors = {}
        
        for idx_str, rgb in segment_colors_input.items():
            idx = int(idx_str) if isinstance(idx_str, str) else idx_str
            if idx < len(segments):
                panel_id = segments[idx]["panelId"]
                panel_colors[panel_id] = tuple(rgb)
        
        # Send batch update
        transition_time = int(transition * 10)
        await hass.async_add_executor_job(
            api.set_multiple_panels,
            panel_colors,
            transition_time
        )
    
    hass.services.async_register(
        DOMAIN,
        "set_multiple_segments",
        handle_set_multiple_segments,
    )

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class NanoleafAPI:
    """API client for Nanoleaf device."""

    def __init__(self, host: str, token: str) -> None:
        """Initialize the API client."""
        self.host = host
        self.token = token
        self.base_url = f"http://{host}:{DEFAULT_PORT}/api/v1/{token}"
        
        # UDP streaming for smooth Ambilight
        self._udp_socket = None
        self._udp_port = None
        self._external_control_enabled = False
        self._pending_updates = {}  # Panel ID -> (R, G, B)
        self._update_lock = asyncio.Lock()
        self._update_pending = False

    def get_layout(self) -> dict:
        """Get the panel layout from the device."""
        url = f"{self.base_url}/panelLayout/layout"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()

    def get_state(self) -> dict:
        """Get the current state from the device."""
        url = f"{self.base_url}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()

    def set_state(self, on: bool | None = None, brightness: int | None = None) -> None:
        """Set the state of the device."""
        url = f"{self.base_url}/state"
        payload = {}
        
        if on is not None:
            payload["on"] = {"value": on}
        
        if brightness is not None:
            payload["brightness"] = {"value": brightness}
        
        if payload:
            response = requests.put(url, json=payload, timeout=5)
            response.raise_for_status()

    def set_panel_color(self, panel_id: int, r: int, g: int, b: int, transition_time: int = 0) -> None:
        """Set color for a specific panel using custom effect."""
        # This is kept for backwards compatibility but not recommended
        # Use set_multiple_panels for better performance
        url = f"{self.base_url}/effects"
        
        effect_data = {
            "write": {
                "command": "display",
                "animType": "custom",
                "animData": f"1 {panel_id} 1 {r} {g} {b} 0 {transition_time}",
                "loop": False,
                "palette": []
            }
        }
        
        response = requests.put(url, json=effect_data, timeout=5)
        response.raise_for_status()
    
    def enable_external_control(self) -> bool:
        """Enable UDP External Control mode (like Screen Mirroring)."""
        try:
            url = f"{self.base_url}/effects"
            payload = {"write": {"command": "display", "animType": "extControl", "extControlVersion": "v2"}}
            
            response = requests.put(url, json=payload, timeout=3)
            response.raise_for_status()
            
            # Get UDP port from device
            info_response = requests.get(self.base_url, timeout=3)
            info = info_response.json()
            
            # Create UDP socket
            self._udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._udp_socket.setblocking(False)
            self._udp_port = 60222  # Default Nanoleaf UDP port
            self._external_control_enabled = True
            
            _LOGGER.info("External Control (UDP) enabled for smooth streaming")
            return True
            
        except Exception as err:
            _LOGGER.warning("Failed to enable External Control, using HTTP fallback: %s", err)
            self._external_control_enabled = False
            return False
    
    def set_multiple_panels_udp(self, panel_colors: dict[int, tuple[int, int, int]], smooth: bool = True) -> None:
        """Set colors via UDP for zero-latency streaming (Ambilight optimized)."""
        if not self._external_control_enabled or not self._udp_socket:
            return self.set_multiple_panels(panel_colors, 0)
        
        try:
            # Build UDP packet: numPanels [panelId R G B W transTime] ...
            # Format: 2 bytes panel count, then 8 bytes per panel
            num_panels = len(panel_colors)
            
            packet = struct.pack('>H', num_panels)  # 2 bytes: panel count
            
            # Transition time for smooth fading between frames
            # 2 = 0.2s creates smooth interpolation at 10-15 FPS (Ambilight typical)
            # This makes the Nanoleafs internally fade between colors!
            trans_time = 2 if smooth else 0
            
            for panel_id, (r, g, b) in panel_colors.items():
                # 2 bytes panel ID, 1 byte R, 1 byte G, 1 byte B, 1 byte W, 2 bytes transition
                packet += struct.pack('>HBBBBH', panel_id, r, g, b, 0, trans_time)
            
            # Send UDP packet (fire and forget - no waiting!)
            self._udp_socket.sendto(packet, (self.host, self._udp_port))
            
        except Exception as err:
            _LOGGER.debug("UDP send failed, using HTTP fallback: %s", err)
            self.set_multiple_panels(panel_colors, 0)
    
    def set_multiple_panels(self, panel_colors: dict[int, tuple[int, int, int]], transition_time: int = 0) -> None:
        """Set colors for multiple panels in one API call (optimized for speed)."""
        url = f"{self.base_url}/effects"
        
        # Build animData: numPanels panelId1 frames R G B W time ...
        anim_parts = []
        for panel_id, (r, g, b) in panel_colors.items():
            anim_parts.append(f"{panel_id} 1 {r} {g} {b} 0 {transition_time}")
        
        num_panels = len(panel_colors)
        anim_data = f"{num_panels} " + " ".join(anim_parts)
        
        effect_data = {
            "write": {
                "command": "display",
                "animType": "custom",
                "animData": anim_data,
                "loop": False,
                "palette": []
            }
        }
        
        # Non-blocking: shorter timeout, don't wait for full response
        try:
            response = requests.put(url, json=effect_data, timeout=0.5)
        except requests.exceptions.Timeout:
            # Ignore timeout - command was likely sent
            pass
        except Exception:
            # Ignore other errors for fire-and-forget
            pass

    def get_all_segments(self) -> list[dict]:
        """Get all line segments from the layout."""
        layout = self.get_layout()
        panels = layout.get("positionData", [])
        
        # Filter only line segments (shapeType 18)
        segments = [
            panel for panel in panels
            if panel.get("shapeType") == SHAPE_TYPE_LINE_SEGMENT
        ]
        
        # Compute angles for sorting/grouping
        if segments:
            from math import atan2, degrees
            cx = sum(p["x"] for p in segments) / len(segments)
            cy = sum(p["y"] for p in segments) / len(segments)
            for p in segments:
                raw_angle = (degrees(atan2(p["y"] - cy, p["x"] - cx)) + 360) % 360
                p["angle_deg"] = round(raw_angle, 2)
        
        return segments
    
    @staticmethod
    def create_new_token(host: str) -> str:
        """Create a new auth token. Requires button press on device."""
        url = f"http://{host}:{DEFAULT_PORT}/api/v1/new"
        response = requests.post(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("auth_token")


class NanoleafDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Nanoleaf data."""

    def __init__(self, hass: HomeAssistant, api: NanoleafAPI) -> None:
        """Initialize the coordinator."""
        self.api = api
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from API."""
        try:
            # Get current state
            state = await self.hass.async_add_executor_job(self.api.get_state)
            
            # Get all segments (only once at startup, cached)
            if not hasattr(self, "_segments"):
                self._segments = await self.hass.async_add_executor_job(
                    self.api.get_all_segments
                )
            
            return {
                "state": state,
                "segments": self._segments,
            }
            
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

