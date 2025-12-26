# -*- coding: utf-8 -*-
"""
Diagnostic autonome : détection des intégrations et capteurs energy/power
--------------------------------------------------------------------------

Ce script lit directement la base SQLite de Home Assistant
(`/config/home-assistant_v2.db`) pour repérer les capteurs energy/power
et afficher les intégrations qui les fournissent.

✅ A exécuter directement depuis SSH :
    python3 /config/detect_local_debug_standalone.py
"""

import sqlite3
import json
import os
from collections import defaultdict

DB_PATH = "/config/home-assistant_v2.db"

def classify_sensor(attributes_json):
    """Détermine si le capteur est de type power / energy selon les attributs."""
    try:
        attrs = json.loads(attributes_json or "{}")
    except json.JSONDecodeError:
        attrs = {}

    unit = str(attrs.get("unit_of_measurement", "")).lower()
    device_class = str(attrs.get("device_class", "")).lower()

    if device_class == "energy" or unit in ("kwh", "wh", "mwh"):
        return "energy"
    if device_class == "power" or unit in ("w", "watt", "watts", "kw"):
        return "power"
    return "unknown"


def detect_integrations():
    if not os.path.exists(DB_PATH):
        print(f"❌ Base Home Assistant introuvable : {DB_PATH}")
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Récupère les dernières valeurs de toutes les entités
    cur.execute("""
        SELECT entity_id, attributes
        FROM states
        WHERE entity_id LIKE 'sensor.%'
        GROUP BY entity_id
    """)

    integrations = defaultdict(lambda: {"energy": [], "power": [], "unknown": []})

    for entity_id, attrs_json in cur.fetchall():
        sensor_type = classify_sensor(attrs_json)
        integration = entity_id.split(".")[1].split("_")[0] if "_" in entity_id else "unknown"
        integrations[integration][sensor_type].append(entity_id)

    con.close()

    print("===== 🔍 Intégrations détectées avec capteurs energy/power =====\n")
    for integ, sensors in sorted(integrations.items()):
        energy_count = len(sensors["energy"])
        power_count = len(sensors["power"])
        if energy_count == 0 and power_count == 0:
            continue
        print(f"🔹 {integ}")
        if energy_count:
            print(f"   ⚡ Energy sensors ({energy_count}):")
            for s in sensors["energy"]:
                print(f"     - {s}")
        if power_count:
            print(f"   🔌 Power sensors ({power_count}):")
            for s in sensors["power"]:
                print(f"     - {s}")
        print()

    print("✅ Fin du diagnostic.")


if __name__ == "__main__":
    detect_integrations()