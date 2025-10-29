#!/usr/bin/env python3
"""
Test UDP External Control für flüssiges Streaming (Ambilight)
"""

import json
import os
import socket
import struct
import time
import requests
from dotenv import load_dotenv

load_dotenv()

NANOLEAF_IP = os.getenv("NANOLEAF_IP")
NANOLEAF_PORT = int(os.getenv("NANOLEAF_PORT", "16021"))
UDP_PORT = 60222
TOKEN_FILE = "nanoleaf_token.json"


def load_token():
    """Lade Token."""
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)["token"]


def enable_external_control(host, token):
    """Aktiviere External Control Mode."""
    url = f"http://{host}:{NANOLEAF_PORT}/api/v1/{token}/effects"
    payload = {
        "write": {
            "command": "display",
            "animType": "extControl",
            "extControlVersion": "v2"
        }
    }
    
    response = requests.put(url, json=payload, timeout=5)
    response.raise_for_status()
    print("✓ External Control Mode aktiviert")


def get_segments():
    """Hole Segmente."""
    token = load_token()
    url = f"http://{NANOLEAF_IP}:{NANOLEAF_PORT}/api/v1/{token}/panelLayout/layout"
    response = requests.get(url, timeout=5)
    layout = response.json()
    segments = [p for p in layout.get("positionData", []) if p.get("shapeType") == 18]
    return segments


def send_udp_colors(sock, host, panel_colors, transition=2):
    """Sende Farben via UDP mit Transition für smooth fading."""
    num_panels = len(panel_colors)
    packet = struct.pack('>H', num_panels)
    
    for panel_id, (r, g, b) in panel_colors.items():
        # transition: 0 = instant, 2 = 0.2s smooth fade
        packet += struct.pack('>HBBBBH', panel_id, r, g, b, 0, transition)
    
    sock.sendto(packet, (host, UDP_PORT))


def test_smooth_streaming():
    """Test flüssiges Streaming wie Screen Mirroring."""
    token = load_token()
    segments = get_segments()
    
    print(f"\n{'='*60}")
    print(f"Testing UDP Streaming (wie Screen Mirroring)")
    print(f"Segments: {len(segments)}")
    print(f"{'='*60}\n")
    
    # Enable External Control
    enable_external_control(NANOLEAF_IP, token)
    
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Test: Farb-Wechsel über alle Segmente
    colors = [
        (255, 0, 0),    # Red
        (255, 127, 0),  # Orange
        (255, 255, 0),  # Yellow
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
        (148, 0, 211),  # Purple
    ]
    
    num_frames = 120
    start_time = time.time()
    
    print("Streaming 120 frames with SMOOTH interpolation...\n")
    print("The Nanoleafs will internally fade between colors!\n")
    
    for frame in range(num_frames):
        # Rotate colors across segments
        panel_colors = {}
        for i, seg in enumerate(segments):
            color_idx = (i + frame) % len(colors)
            panel_colors[seg["panelId"]] = colors[color_idx]
        
        # Send via UDP with 0.2s transition for smooth fading
        # This tells the Nanoleafs to interpolate between frames!
        send_udp_colors(sock, NANOLEAF_IP, panel_colors, transition=2)
        
        # Target: 15 FPS (works better with 0.2s transitions)
        time.sleep(1/15)
        
        if (frame + 1) % 30 == 0:
            elapsed = time.time() - start_time
            fps = (frame + 1) / elapsed
            print(f"Frame {frame+1:3d}: {fps:5.1f} FPS")
    
    total_time = time.time() - start_time
    avg_fps = num_frames / total_time
    
    print(f"\n{'='*60}")
    print(f"Streaming Complete!")
    print(f"  Total frames: {num_frames}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Average sent FPS: {avg_fps:.1f}")
    print(f"\n💡 With 0.2s transitions, the Nanoleafs interpolate internally!")
    print(f"   Visual smoothness: ~30-60 FPS (perceived)")
    print(f"\nResult: {'✓ SMOOTH' if avg_fps >= 10 else '✗ NEEDS OPTIMIZATION'}")
    print(f"{'='*60}\n")
    
    sock.close()


def test_group_updates():
    """Test schnelle Gruppen-Updates."""
    token = load_token()
    segments = get_segments()
    
    # Enable External Control
    enable_external_control(NANOLEAF_IP, token)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Divide into 9 groups (wie Ambilight)
    group_size = len(segments) // 9
    
    print(f"\n{'='*60}")
    print(f"Testing Ambilight Simulation (9 groups)")
    print(f"{'='*60}\n")
    
    # Simulate DIYHue sending colors to all 9 groups rapidly
    for cycle in range(20):
        for group_idx in range(9):
            start_idx = group_idx * group_size
            end_idx = start_idx + group_size
            
            # Random color for this group
            import random
            r, g, b = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
            
            panel_colors = {}
            for seg in segments[start_idx:end_idx]:
                panel_colors[seg["panelId"]] = (r, g, b)
            
            send_udp_colors(sock, NANOLEAF_IP, panel_colors)
            time.sleep(0.01)  # 10ms between groups
        
        print(f"Cycle {cycle + 1}/20 complete")
    
    print("\n✓ Ambilight simulation complete - check for smoothness!")
    sock.close()


if __name__ == "__main__":
    print(f"Nanoleaf IP: {NANOLEAF_IP}")
    
    try:
        print("\n1. Testing smooth streaming...")
        test_smooth_streaming()
        
        input("\nPress Enter to test Ambilight simulation...")
        test_group_updates()
        
    except KeyboardInterrupt:
        print("\n\nTest aborted")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

