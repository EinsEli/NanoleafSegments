#!/usr/bin/env python3
"""
Automatische Nanoleaf Lines-Authentifizierung & Layout-Debugger

Funktionen:
- Prüft auf gespeicherten Token (nanoleaf_token.json)
- Wenn keiner vorhanden oder ungültig → neuen Token anfordern
- Ruft Layout ab und zeigt Panels (IDs, Positionen etc.)
- Speichert neuen Token persistent

Voraussetzung:
- Nanoleaf Controller im selben Netzwerk
- Taste am Controller 5–7 Sekunden gedrückt halten, wenn das Skript neuen Token anfordert
"""

import requests
import json
import os
from math import atan2, degrees
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === EINSTELLUNGEN ===
NANOLEAF_IP = os.getenv("NANOLEAF_IP", "x.x.x.x")
TOKEN_FILE = "nanoleaf_token.json"  # Datei, in der das Token gespeichert wird
PORT = int(os.getenv("NANOLEAF_PORT", "16021"))
TIMEOUT = 5


def get_saved_token():
    """Liest gespeicherten Token aus Datei"""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
                return data.get("token")
        except Exception:
            pass
    return None


def save_token(token):
    """Speichert Token in Datei"""
    with open(TOKEN_FILE, "w") as f:
        json.dump({"token": token}, f)
    print(f"✅ Neuer Token gespeichert in '{TOKEN_FILE}'")


def request_new_token():
    """Fordert neuen Token vom Nanoleaf an (Taste am Controller gedrückt halten!)"""
    url = f"http://{NANOLEAF_IP}:{PORT}/api/v1/new"
    print(f"\n⚠️  Bitte jetzt die Power-Taste am Nanoleaf-Controller 5–7 Sekunden gedrückt halten!")
    print("→ Das Skript versucht, in ca. 5 Sekunden einen neuen Token zu holen...\n")
    import time
    time.sleep(5)
    try:
        r = requests.post(url, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        token = data.get("auth_token")
        if not token:
            raise ValueError("Antwort enthält keinen auth_token.")
        save_token(token)
        return token
    except Exception as e:
        print(f"❌ Fehler beim Erzeugen des Tokens: {e}")
        return None


def fetch_layout(ip, token):
    """Liest Layout vom Nanoleaf"""
    url = f"http://{ip}:{PORT}/api/v1/{token}/panelLayout/layout"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def compute_angles(panels):
    """Berechnet Winkel jedes Panels relativ zum Schwerpunkt"""
    cx = sum(p["x"] for p in panels) / len(panels)
    cy = sum(p["y"] for p in panels) / len(panels)
    for p in panels:
        raw_angle = (degrees(atan2(p["y"] - cy, p["x"] - cx)) + 360) % 360
        p["angle_deg"] = round(raw_angle, 2)
    panels.sort(key=lambda p: p["angle_deg"])
    return panels, (cx, cy)


def main():
    print("🔍 Nanoleaf Layout Debug & Auto-Auth\n")

    token = get_saved_token()
    if token:
        print(f"🔑 Gefundener gespeicherter Token: {token}")
    else:
        print("❌ Kein gespeicherter Token gefunden.")
        token = request_new_token()
        if not token:
            return

    # Teste Layout-Abruf
    try:
        layout = fetch_layout(NANOLEAF_IP, token)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("⚠️ Token ungültig! Versuche neuen zu erzeugen...")
            token = request_new_token()
            if not token:
                return
            layout = fetch_layout(NANOLEAF_IP, token)
        else:
            print(f"❌ HTTP-Fehler: {e}")
            return
    except Exception as e:
        print(f"❌ Verbindung fehlgeschlagen: {e}")
        return

    print("\n✅ Verbindung erfolgreich! Layoutdaten erhalten.\n")
 
    panels = layout.get("positionData", [])
    panels, (cx, cy) = compute_angles(panels)

    # Panel-Typen zählen und kategorisieren
    shape_types = {}
    for p in panels:
        st = p.get("shapeType", 0)
        shape_types[st] = shape_types.get(st, 0) + 1
    
    # Shape Type Namen
    shape_names = {
        16: "Connectoren (Verbindungsstücke)",
        18: "Lines (Leucht-Segmente)",
        19: "Controller (Power Supply)",
        20: "Controller"
    }

    print(f"📦 Gesamtanzahl Panels/Komponenten: {len(panels)}")
    print(f"📍 Schwerpunkt: ({cx:.1f}, {cy:.1f})\n")
    print("📊 Panel-Typen:")
    for st, count in sorted(shape_types.items()):
        name = shape_names.get(st, f"Unbekannter Typ {st}")
        print(f"   • ShapeType {st}: {count:>2}x  ({name})")
    
    lines_count = shape_types.get(18, 0)
    connector_count = shape_types.get(16, 0)
    print(f"\n💡 Sie haben {lines_count} Lines-Segmente und {connector_count} Connectoren")
    print(f"   → Das entspricht ungefähr {lines_count // 3} vollständigen Lines (je ~3 Segmente)\n")

    print("="*70)
    for p in panels:
        st = p.get("shapeType", 0)
        type_name = shape_names.get(st, "?")[:25]
        print(f"  ID {p['panelId']:>5}  |  Typ {st} ({type_name:25})  |  X={p['x']:>4}  Y={p['y']:>4}  ∠={p['angle_deg']:>6}°")

    # Optional speichern
    with open("nanoleaf_layout.json", "w") as f:
        json.dump(layout, f, indent=2)
    print("\n💾 Layout gespeichert in 'nanoleaf_layout.json'\n")


if __name__ == "__main__":
    main()
