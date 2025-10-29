"""Constants for the Nanoleaf Segments integration."""
from typing import Final

DOMAIN: Final = "nanoleaf_segments"

# Configuration
CONF_HOST: Final = "host"
CONF_TOKEN: Final = "token"
CONF_NAME: Final = "name"
CONF_CREATE_GROUPS: Final = "create_groups"
CONF_GROUP_SIZE: Final = "group_size"
CONF_MANUAL_GROUPS: Final = "manual_groups"

# Defaults
DEFAULT_NAME: Final = "Nanoleaf Segments"
DEFAULT_PORT: Final = 16021
DEFAULT_SCAN_INTERVAL: Final = 10  # seconds
DEFAULT_GROUP_SIZE: Final = 3  # segments per group

# API endpoints
API_BASE: Final = "http://{host}:{port}/api/v1/{token}"
API_LAYOUT: Final = "/panelLayout/layout"
API_STATE: Final = "/state"
API_EFFECTS: Final = "/effects"
API_SET_VALUE: Final = "/state"

# Panel Shape Types
SHAPE_TYPE_CONNECTOR: Final = 16
SHAPE_TYPE_LINE_SEGMENT: Final = 18
SHAPE_TYPE_CONTROLLER: Final = 19
SHAPE_TYPE_CONTROLLER_ALT: Final = 20

# Attributes
ATTR_PANEL_ID: Final = "panel_id"
ATTR_PANEL_IDS: Final = "panel_ids"
ATTR_POSITION_X: Final = "position_x"
ATTR_POSITION_Y: Final = "position_y"
ATTR_ORIENTATION: Final = "orientation"
ATTR_SHAPE_TYPE: Final = "shape_type"
ATTR_GROUP_ID: Final = "group_id"
ATTR_SEGMENT_COUNT: Final = "segment_count"

