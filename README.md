# Nanoleaf Segments

A custom integration for [Home Assistant](https://www.home-assistant.io/) to control individual Segments of Nanoleaf lights.  
This can be used in combination with a Philips TV and [diyHue](https://diyhue.org/) to create a custom ambient lighting setup.

## Installation

### HACS Installation

1. **Add Repository:**
   - Add this repository as a custom repository in HACS:
     ```
     https://github.com/EinsEli/nanoleaf-segments
     ```
2. **Install Integration:**
   - Search for "Nanoleaf Segments" in HACS and install it.

### Manual Installation

1. **Download or Clone:**
   - Download or clone this repository into your Home Assistant `custom_components` directory:
     ```
     custom_components/nanoleaf_segments/
     ```

2. **Restart Home Assistant:**
   - Restart Home Assistant to load the new integration.


## Configuration

   - Go to **Settings** > **Devices & Services** > **Add Integration**.
   - Search for "Nanoleaf (Segments)" and follow the prompts.
   - To pair a Nanoleaf device you can...
     - ...enter an existing authentication token.
     - ...press and hold the power button on the Nanoleaf controller for 5-7 seconds until the lights start flashing. This will automatically obtain a new authentication token.

## Grouping Segments

This integration supports grouping segments into light groups. This allows you to efficiently control a group of segments at once.
- You can enable or disable automatic group creation during setup.
- You can also manually define groups of segments at a later time in the integration options.
> [!NOTE] Manually defining Groups
> If the automatically generated groups are not suitable for your needs, you can manually define groups of segments.  
> The format for the manual group definition is a list of group indices separated by semicolons.  
> For example: `0,1,2; 3,4,5; 6,7` will create 3 groups:
> - Group `1`: Segments `0`, `1`, `2`	
> - Group `2`: Segments `3`, `4`, `5`
> - Group `3`: Segments `6`, `7`