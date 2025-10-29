"""Config flow for Nanoleaf Lines integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_CREATE_GROUPS,
    CONF_MANUAL_GROUPS,
    CONF_NAME,
    CONF_TOKEN,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class NanoleafLinesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nanoleaf Lines."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NanoleafLinesOptionsFlow:
        """Get the options flow for this handler."""
        return NanoleafLinesOptionsFlow(config_entry)

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._token: str | None = None
        self._name: str | None = None
        self._create_groups: bool = True
        self._manual_groups: list[list[int]] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - ask for host and pairing method."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._name = user_input.get(CONF_NAME, "Nanoleaf Lines")
            self._create_groups = user_input.get(CONF_CREATE_GROUPS, True)
            
            # Check if user wants to pair or has a token
            if user_input.get("pairing_mode", False):
                return await self.async_step_pair()
            else:
                return await self.async_step_token()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_NAME, default="Nanoleaf Lines"): str,
                    vol.Required("pairing_mode", default=True): bool,
                    vol.Required(CONF_CREATE_GROUPS, default=True): bool,
                }
            ),
            errors=errors,
            description_placeholders={
                "pairing_mode_desc": "Aktivieren Sie diese Option, um ein neues Gerät zu koppeln (Sie müssen die Power-Taste drücken). Deaktivieren Sie sie, wenn Sie bereits ein Token haben."
            }
        )
    
    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle pairing - create new token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Wait a moment, then try to pair
                await asyncio.sleep(1)
                
                token = await self.hass.async_add_executor_job(
                    create_new_token,
                    self._host,
                )
                
                # Validate the new token
                await self.hass.async_add_executor_job(
                    validate_connection,
                    self._host,
                    token,
                )
                
                # Create a unique ID based on the host
                await self.async_set_unique_id(self._host)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._name,
                    data={
                        CONF_HOST: self._host,
                        CONF_TOKEN: token,
                        CONF_NAME: self._name,
                        CONF_CREATE_GROUPS: self._create_groups,
                    },
                )
                
            except PairingTimeout:
                errors["base"] = "pairing_timeout"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during pairing")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="pair",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "instructions": f"Halten Sie jetzt die Power-Taste an Ihrem Nanoleaf Controller ({self._host}) für 5-7 Sekunden gedrückt, bis die LED zu blinken beginnt. Klicken Sie dann auf 'Absenden'."
            }
        )
    
    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual token entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate the connection
                await self.hass.async_add_executor_job(
                    validate_connection,
                    self._host,
                    user_input[CONF_TOKEN],
                )
                
                # Create a unique ID based on the host
                await self.async_set_unique_id(self._host)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._name,
                    data={
                        CONF_HOST: self._host,
                        CONF_TOKEN: user_input[CONF_TOKEN],
                        CONF_NAME: self._name,
                        CONF_CREATE_GROUPS: self._create_groups,
                    },
                )
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )


def validate_connection(host: str, token: str) -> bool:
    """Validate the connection to the Nanoleaf device."""
    url = f"http://{host}:{DEFAULT_PORT}/api/v1/{token}"
    
    try:
        response = requests.get(f"{url}/panelLayout/layout", timeout=5)
        
        if response.status_code == 401:
            raise InvalidAuth
        
        response.raise_for_status()
        data = response.json()
        
        # Validate that we got layout data
        if "positionData" not in data:
            raise CannotConnect
            
        return True
        
    except requests.exceptions.Timeout:
        raise CannotConnect
    except requests.exceptions.ConnectionError:
        raise CannotConnect
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 401:
            raise InvalidAuth
        raise CannotConnect


def create_new_token(host: str) -> str:
    """Create a new auth token. Requires button press on device."""
    url = f"http://{host}:{DEFAULT_PORT}/api/v1/new"
    
    try:
        response = requests.post(url, timeout=30)
        
        if response.status_code == 403:
            raise PairingTimeout
        
        response.raise_for_status()
        data = response.json()
        token = data.get("auth_token")
        
        if not token:
            raise CannotConnect
        
        return token
        
    except requests.exceptions.Timeout:
        raise PairingTimeout
    except requests.exceptions.ConnectionError:
        raise CannotConnect


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class PairingTimeout(HomeAssistantError):
    """Error to indicate pairing timeout (button not pressed)."""


class NanoleafLinesOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Nanoleaf Lines."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._segments = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_groups()

    async def async_step_groups(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure manual groups."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Parse group configuration
            group_config = user_input.get("group_config", "")
            
            try:
                manual_groups = self._parse_group_config(group_config)
                
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_MANUAL_GROUPS: manual_groups,
                    },
                )
            except ValueError:
                errors["base"] = "invalid_group_config"

        # Get segments for display
        if self._segments is None:
            try:
                host = self.config_entry.data[CONF_HOST]
                token = self.config_entry.data[CONF_TOKEN]
                
                # Fetch layout
                url = f"http://{host}:{DEFAULT_PORT}/api/v1/{token}/panelLayout/layout"
                response = await self.hass.async_add_executor_job(
                    requests.get, url, None, 5
                )
                layout = response.json()
                
                # Filter segments
                self._segments = [
                    p for p in layout.get("positionData", [])
                    if p.get("shapeType") == 18
                ]
            except Exception:
                self._segments = []

        # Current groups
        current_groups = self.config_entry.options.get(CONF_MANUAL_GROUPS, [])
        group_str = "; ".join([",".join(map(str, g)) for g in current_groups]) if current_groups else ""

        return self.async_show_form(
            step_id="groups",
            data_schema=vol.Schema(
                {
                    vol.Optional("group_config", default=group_str): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "num_segments": str(len(self._segments)) if self._segments else "0",
                "example": "0,1,2; 3,4,5; 6,7,8",
            },
        )

    def _parse_group_config(self, config_str: str) -> list[list[int]]:
        """Parse group configuration string."""
        if not config_str.strip():
            return []
        
        groups = []
        for group_str in config_str.strip().split(";"):
            group_str = group_str.strip()
            if not group_str:
                continue
            
            try:
                indices = [int(x.strip()) for x in group_str.split(",")]
                groups.append(indices)
            except ValueError:
                raise ValueError("Invalid group configuration")
        
        return groups

