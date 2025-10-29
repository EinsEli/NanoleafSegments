#!/usr/bin/env python3
"""
Test verschiedene Transition-Zeiten für optimales Fading
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
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)["token"]


def enable_external_control(host, token):
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


def get_segments():
    token = load_token()
    url = f"http://{NANOLEAF_IP}:{NANOLEAF_PORT}/api/v1/{token}/panelLayout/layout"
    response = requests.get(url, timeout=5)
    layout = response.json()
    return [p for p in layout.get("positionData", []) if p.get("shapeType") == 18]


def send_color(sock, host, segments, color, transition):
    """Sende eine Farbe an alle Segmente."""
    num_panels = len(segments)
    packet = struct.pack('>H', num_panels)
    
    r, g, b = color
    for seg in segments:
        packet += struct.pack('>HBBBBH', seg["panelId"], r, g, b, 0, transition)
    
    sock.sendto(packet, (host, UDP_PORT))


def test_transition_times():
    """Teste verschiedene Transition-Zeiten."""
    token = load_token()
    segments = get_segments()
    
    print(f"\n{'='*60}")
    print(f"Testing Transition Times for Smooth Fading")
    print(f"Segments: {len(segments)}")
    print(f"{'='*60}\n")
    
    enable_external_control(NANOLEAF_IP, token)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Test different transition times
    test_cases = [
        (0, "Instant (no fade)", 0.5),
        (1, "0.1s transition", 0.5),
        (2, "0.2s transition (recommended)", 0.5),
        (3, "0.3s transition", 0.5),
        (5, "0.5s transition", 0.8),
    ]
    
    colors = [
        (255, 0, 0),    # Red
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
        (255, 255, 0),  # Yellow
    ]
    
    for trans_time, desc, wait_time in test_cases:
        print(f"\nTesting: {desc}")
        print(f"Watch for smoothness...\n")
        
        for i, color in enumerate(colors):
            send_color(sock, NANOLEAF_IP, segments, color, trans_time)
            time.sleep(wait_time)
            print(f"  Frame {i+1}/4", end='\r')
        
        print(f"\n✓ {desc} complete")
        
        input("\nPress Enter to test next transition time...")
    
    sock.close()
    print(f"\n{'='*60}")
    print("Test complete!")
    print("\nRecommendation:")
    print("  - For Ambilight: transition=2 (0.2s)")
    print("  - For fast effects: transition=1 (0.1s)")
    print("  - For smooth movies: transition=3 (0.3s)")
    print(f"{'='*60}\n")


def test_ambilight_simulation():
    """Simuliere Ambilight mit optimaler Transition."""
    token = load_token()
    segments = get_segments()
    
    print(f"\n{'='*60}")
    print(f"Ambilight Simulation (optimized)")
    print(f"{'='*60}\n")
    
    enable_external_control(NANOLEAF_IP, token)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Divide into groups
    group_size = len(segments) // 9
    
    import random
    
    print("Running smooth Ambilight simulation...")
    print("All 9 groups changing colors independently\n")
    
    for cycle in range(30):
        for group_idx in range(9):
            start_idx = group_idx * group_size
            end_idx = start_idx + group_size
            
            # Random color
            r = random.randint(50, 255)
            g = random.randint(50, 255)
            b = random.randint(50, 255)
            
            # Send only this group
            num_panels = end_idx - start_idx
            packet = struct.pack('>H', num_panels)
            
            for seg in segments[start_idx:end_idx]:
                # transition=2 for smooth fading!
                packet += struct.pack('>HBBBBH', seg["panelId"], r, g, b, 0, 2)
            
            sock.sendto(packet, (NANOLEAF_IP, UDP_PORT))
            
            # Slight delay between groups
            time.sleep(0.02)
        
        print(f"Cycle {cycle+1}/30 complete", end='\r')
        time.sleep(0.1)
    
    print("\n\n✓ Ambilight simulation complete!")
    print("The fading should be buttery smooth! 🧈")
    
    sock.close()


if __name__ == "__main__":
    print(f"Nanoleaf IP: {NANOLEAF_IP}")
    
    try:
        choice = input("\n1: Test transition times\n2: Ambilight simulation\nChoice (1/2): ")
        
        if choice == "1":
            test_transition_times()
        else:
            test_ambilight_simulation()
        
    except KeyboardInterrupt:
        print("\n\nTest aborted")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

