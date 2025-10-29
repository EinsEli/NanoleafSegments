#!/usr/bin/env python3
"""
Debug-Skript zum Testen der Nanoleaf Lines Segment-Steuerung
"""

import json
import os
import sys
import time
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

NANOLEAF_IP = os.getenv("NANOLEAF_IP")
NANOLEAF_PORT = int(os.getenv("NANOLEAF_PORT", "16021"))
TOKEN_FILE = "nanoleaf_token.json"


def load_token():
    """Lade Token aus Datei."""
    with open(TOKEN_FILE, "r") as f:
        data = json.load(f)
        return data["token"]


def get_segments():
    """Hole alle Segmente."""
    token = load_token()
    url = f"http://{NANOLEAF_IP}:{NANOLEAF_PORT}/api/v1/{token}/panelLayout/layout"
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    layout = response.json()
    
    # Filter nur Line Segments (shapeType 18)
    segments = [p for p in layout.get("positionData", []) if p.get("shapeType") == 18]
    return segments


def test_single_panel_only(panel_id, r, g, b, transition=0):
    """Teste einzelnes Panel (schaltet andere aus!)."""
    token = load_token()
    url = f"http://{NANOLEAF_IP}:{NANOLEAF_PORT}/api/v1/{token}/effects"
    
    print(f"\n{'='*60}")
    print(f"Testing SINGLE panel {panel_id} with RGB({r}, {g}, {b})")
    print(f"WARNING: This will turn OFF all other panels!")
    print(f"{'='*60}")
    
    # Format: numPanels panelId frames R G B W time
    payload = {
        "write": {
            "command": "display",
            "animType": "custom",
            "animData": f"1 {panel_id} 1 {r} {g} {b} 0 {transition}",
            "loop": False,
            "palette": []
        }
    }
    
    try:
        print(f"   Payload: {json.dumps(payload, indent=2)}")
        resp = requests.put(url, json=payload, timeout=5)
        print(f"   Status: {resp.status_code}")
        if resp.status_code != 204:
            print(f"   Response: {resp.text}")
        else:
            print("   ✓ Success (but other panels are now OFF)")
    except Exception as e:
        print(f"   ✗ Error: {e}")


def test_single_panel_preserve_others(panel_id, r, g, b, transition=0):
    """Teste einzelnes Panel und behalte andere bei."""
    token = load_token()
    url = f"http://{NANOLEAF_IP}:{NANOLEAF_PORT}/api/v1/{token}/effects"
    segments = get_segments()
    
    print(f"\n{'='*60}")
    print(f"Testing panel {panel_id} with RGB({r}, {g}, {b})")
    print(f"Preserving state of {len(segments)-1} other panels")
    print(f"{'='*60}")
    
    # Build animData for ALL segments
    anim_parts = []
    for seg in segments:
        seg_id = seg["panelId"]
        if seg_id == panel_id:
            # This is the one we're changing
            anim_parts.append(f"{seg_id} 1 {r} {g} {b} 0 {transition}")
        else:
            # Keep others white
            anim_parts.append(f"{seg_id} 1 255 255 255 0 {transition}")
    
    num_panels = len(segments)
    anim_data = f"{num_panels} " + " ".join(anim_parts)
    
    payload = {
        "write": {
            "command": "display",
            "animType": "custom",
            "animData": anim_data,
            "loop": False,
            "palette": []
        }
    }
    
    try:
        print(f"   NumPanels: {num_panels}")
        print(f"   AnimData length: {len(anim_data)} chars")
        resp = requests.put(url, json=payload, timeout=5)
        print(f"   Status: {resp.status_code}")
        if resp.status_code != 204:
            print(f"   Response: {resp.text}")
        else:
            print("   ✓ Success - other panels preserved!")
    except Exception as e:
        print(f"   ✗ Error: {e}")


def test_all_segments_one_color():
    """Setze alle Segmente auf eine Farbe."""
    token = load_token()
    segments = get_segments()
    url = f"http://{NANOLEAF_IP}:{NANOLEAF_PORT}/api/v1/{token}/effects"
    
    print(f"\n{'='*60}")
    print(f"Setting all {len(segments)} segments to RED")
    print(f"{'='*60}")
    
    # Build animData for all segments
    # Format: numPanels panelId1 frames R G B W time panelId2 frames R G B W time ...
    anim_data_parts = []
    for seg in segments:
        panel_id = seg["panelId"]
        anim_data_parts.append(f"{panel_id} 1 255 0 0 0 10")
    
    num_panels = len(segments)
    anim_data = f"{num_panels} " + " ".join(anim_data_parts)
    
    payload = {
        "write": {
            "command": "display",
            "animType": "custom",
            "animData": anim_data,
            "loop": False,
            "palette": []
        }
    }
    
    try:
        print(f"NumPanels: {num_panels}")
        resp = requests.put(url, json=payload, timeout=5)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 204:
            print("✓ All segments set to RED")
        else:
            print(f"Response: {resp.text}")
    except Exception as e:
        print(f"✗ Error: {e}")


def test_rainbow_effect():
    """Teste Regenbogen-Effekt über alle Segmente."""
    token = load_token()
    segments = get_segments()
    url = f"http://{NANOLEAF_IP}:{NANOLEAF_PORT}/api/v1/{token}/effects"
    
    print(f"\n{'='*60}")
    print(f"Rainbow effect across {len(segments)} segments")
    print(f"{'='*60}")
    
    colors = [
        (255, 0, 0),    # Red
        (255, 127, 0),  # Orange
        (255, 255, 0),  # Yellow
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
        (75, 0, 130),   # Indigo
        (148, 0, 211),  # Violet
    ]
    
    anim_data_parts = []
    for i, seg in enumerate(segments):
        panel_id = seg["panelId"]
        color = colors[i % len(colors)]
        r, g, b = color
        anim_data_parts.append(f"{panel_id} 1 {r} {g} {b} 0 10")
    
    num_panels = len(segments)
    anim_data = f"{num_panels} " + " ".join(anim_data_parts)
    
    payload = {
        "write": {
            "command": "display",
            "animType": "custom",
            "animData": anim_data,
            "loop": False,
            "palette": []
        }
    }
    
    try:
        print(f"NumPanels: {num_panels}")
        resp = requests.put(url, json=payload, timeout=5)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 204:
            print("✓ Rainbow effect applied")
        else:
            print(f"Response: {resp.text}")
    except Exception as e:
        print(f"✗ Error: {e}")


def main():
    print(f"Nanoleaf IP: {NANOLEAF_IP}:{NANOLEAF_PORT}")
    
    # Get segments
    segments = get_segments()
    print(f"\nFound {len(segments)} line segments")
    
    if not segments:
        print("No segments found!")
        return
    
    # Test first segment with different methods
    first_segment = segments[0]
    panel_id = first_segment["panelId"]
    
    print(f"\nTesting with first segment: Panel ID {panel_id}")
    
    # Test 1: Single panel only (turns others off)
    print("\n" + "="*60)
    print("TEST 1: Single panel only (will turn others OFF)")
    print("="*60)
    input("Press Enter to continue...")
    test_single_panel_only(panel_id, 255, 0, 0, transition=10)
    
    # Test 2: Single panel but preserve others
    print("\n" + "="*60)
    print("TEST 2: Single panel with others preserved")
    print("="*60)
    input("Press Enter to continue...")
    test_single_panel_preserve_others(panel_id, 255, 0, 0, transition=10)
    
    # Test 3: All segments RED
    print("\n" + "="*60)
    print("TEST 3: All segments RED")
    print("="*60)
    input("Press Enter to continue...")
    test_all_segments_one_color()
    
    # Test 4: Rainbow effect
    print("\n" + "="*60)
    print("TEST 4: Rainbow effect")
    print("="*60)
    input("Press Enter to continue...")
    test_rainbow_effect()
    
    print("\n" + "="*60)
    print("Testing complete!")
    print("="*60)


if __name__ == "__main__":
    main()

