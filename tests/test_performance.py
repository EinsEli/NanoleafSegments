#!/usr/bin/env python3
"""
Performance-Test für Nanoleaf Lines Batch-Updates (Ambilight Simulation)
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


def batch_update_all(segments, colors):
    """Batch-Update aller Segmente (wie Screen Mirroring)."""
    token = load_token()
    url = f"http://{NANOLEAF_IP}:{NANOLEAF_PORT}/api/v1/{token}/effects"
    
    # Build animData
    anim_parts = []
    for i, seg in enumerate(segments):
        panel_id = seg["panelId"]
        r, g, b = colors[i % len(colors)]
        anim_parts.append(f"{panel_id} 1 {r} {g} {b} 0 0")  # no transition for speed
    
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
    
    start = time.time()
    resp = requests.put(url, json=payload, timeout=5)
    elapsed = time.time() - start
    
    return resp.status_code == 204, elapsed


def test_ambilight_simulation():
    """Simuliere Ambilight mit schnellen Farbwechseln."""
    segments = get_segments()
    print(f"Testing with {len(segments)} segments")
    print(f"\nSimulating Ambilight (like Screen Mirroring)")
    print("="*60)
    
    # Verschiedene Farbsets
    color_sets = [
        # Set 1: Regenbogen
        [
            (255, 0, 0), (255, 127, 0), (255, 255, 0), (0, 255, 0),
            (0, 0, 255), (75, 0, 130), (148, 0, 211)
        ],
        # Set 2: Blau-Grün
        [
            (0, 255, 255), (0, 200, 255), (0, 150, 255), (0, 100, 255),
            (0, 255, 200), (0, 255, 150), (0, 255, 100)
        ],
        # Set 3: Warm
        [
            (255, 100, 0), (255, 150, 0), (255, 200, 50), (255, 255, 100),
            (255, 200, 100), (255, 150, 50), (255, 100, 50)
        ],
    ]
    
    num_frames = 30
    times = []
    
    print(f"\nSending {num_frames} frames (all {len(segments)} segments per frame)...")
    print("This simulates smooth Ambilight updates\n")
    
    for i in range(num_frames):
        colors = color_sets[i % len(color_sets)]
        success, elapsed = batch_update_all(segments, colors)
        times.append(elapsed)
        
        fps = 1 / elapsed if elapsed > 0 else 0
        print(f"Frame {i+1:2d}: {elapsed*1000:6.2f}ms  ({fps:4.1f} FPS)  {'✓' if success else '✗'}")
        
        # Small delay to not overwhelm the device
        # time.sleep(0.05)
    
    # Statistics
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    avg_fps = 1 / avg_time if avg_time > 0 else 0
    
    print("\n" + "="*60)
    print("Performance Statistics:")
    print(f"  Average: {avg_time*1000:6.2f}ms ({avg_fps:4.1f} FPS)")
    print(f"  Min:     {min_time*1000:6.2f}ms ({1/min_time:4.1f} FPS)")
    print(f"  Max:     {max_time*1000:6.2f}ms ({1/max_time:4.1f} FPS)")
    print("\n" + "="*60)
    print(f"Total segments updated: {len(segments) * num_frames}")
    print(f"Total updates: {num_frames}")
    print(f"\nPerformance rating:")
    if avg_fps >= 20:
        print("  ✓ EXCELLENT - Smooth Ambilight possible!")
    elif avg_fps >= 10:
        print("  ✓ GOOD - Suitable for Ambilight")
    elif avg_fps >= 5:
        print("  ~ OK - Ambilight with reduced frame rate")
    else:
        print("  ✗ SLOW - Not suitable for real-time Ambilight")


def test_group_updates():
    """Teste Updates von Segment-Gruppen."""
    segments = get_segments()
    group_size = 3
    num_groups = (len(segments) + group_size - 1) // group_size
    
    print(f"\nTesting Group Updates")
    print("="*60)
    print(f"  Total segments: {len(segments)}")
    print(f"  Group size: {group_size}")
    print(f"  Number of groups: {num_groups}")
    print()
    
    # Teste Update von einzelnen Gruppen
    times = []
    for group_idx in range(min(num_groups, 5)):  # Test first 5 groups
        start_idx = group_idx * group_size
        end_idx = min(start_idx + group_size, len(segments))
        group_segments = segments[start_idx:end_idx]
        
        # Set group to red
        colors = [(255, 0, 0)] * len(group_segments)
        
        # Update only this group, preserve others
        all_colors = [(255, 255, 255)] * len(segments)  # white for others
        for i, seg_idx in enumerate(range(start_idx, end_idx)):
            all_colors[seg_idx] = colors[i]
        
        success, elapsed = batch_update_all(segments, all_colors)
        times.append(elapsed)
        
        print(f"Group {group_idx+1} ({len(group_segments)} segments): {elapsed*1000:6.2f}ms  {'✓' if success else '✗'}")
        # time.sleep(0.1)
    
    avg_time = sum(times) / len(times) if times else 0
    print(f"\nAverage group update: {avg_time*1000:6.2f}ms")


def main():
    print(f"Nanoleaf IP: {NANOLEAF_IP}:{NANOLEAF_PORT}")
    print("="*60)
    
    try:
        # Test 1: Ambilight simulation
        test_ambilight_simulation()
        
        input("\nPress Enter to test group updates...")
        
        # Test 2: Group updates
        test_group_updates()
        
    except KeyboardInterrupt:
        print("\n\nTest aborted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

