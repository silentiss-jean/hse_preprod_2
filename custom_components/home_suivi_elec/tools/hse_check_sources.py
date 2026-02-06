#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""hse_check_sources.py

But:
- Identifier les capteurs "potentiellement non fiables" dans ta sélection HSE.
- On se base UNIQUEMENT sur les métadonnées du catalogue capteurs_power_v1 (unit/device_class) + selection enabled.

Pourquoi "potentiellement":
- Les unités les plus fiables viennent des states HA (runtime), mais depuis core-ssh on n'y accède pas facilement.

Usage (dans HA core-ssh):
  python3 hse_check_sources.py

Sortie:
- OK: source reconnue (power W/kW ou energy Wh/kWh/MWh)
- WARN: unit/device_class manquants
- ERROR: unit incohérente (ex: unit="kWh" mais marqué power, ou inverse)

"""

from __future__ import annotations

import glob
import json
import os
from typing import Any, Dict, List, Optional, Tuple


POWER_UNITS = {"W", "kW"}
ENERGY_UNITS = {"Wh", "kWh", "MWh"}


def unwrap_store(obj: Any) -> Any:
    """Déplie les wrappers Storage HA: {version, minor_version, key, data}."""
    cur = obj
    for _ in range(10):
        if isinstance(cur, dict) and "data" in cur and "key" in cur and "version" in cur:
            cur = cur.get("data")
            continue
        break
    return cur


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_one(pattern: str) -> Optional[str]:
    matches = sorted(glob.glob(pattern))
    return matches[0] if matches else None


def iter_enabled_entities(selection: Any) -> List[str]:
    enabled: List[str] = []
    if isinstance(selection, dict):
        for _, lst in selection.items():
            if not isinstance(lst, list):
                continue
            for item in lst:
                if not isinstance(item, dict):
                    continue
                if not item.get("enabled", False):
                    continue
                eid = item.get("entity_id") or item.get("entityid") or item.get("entityId")
                if eid:
                    enabled.append(str(eid))
    elif isinstance(selection, list):
        for item in selection:
            if isinstance(item, dict) and item.get("enabled", False) and item.get("entity_id"):
                enabled.append(str(item["entity_id"]))
    return sorted(set(enabled))


def get_meta_unit(meta: Dict[str, Any]) -> Optional[str]:
    u = meta.get("unit") or meta.get("unit_of_measurement")
    if isinstance(u, str) and u.strip():
        return u.strip()
    return None


def get_meta_device_class(meta: Dict[str, Any]) -> Optional[str]:
    dc = meta.get("device_class")
    if dc is None:
        return None
    return str(dc)


def classify(meta: Dict[str, Any]) -> Tuple[str, str]:
    unit = get_meta_unit(meta)
    dc = get_meta_device_class(meta)

    if dc == "power" or unit in POWER_UNITS:
        if unit in ENERGY_UNITS:
            return "ERROR", f"device_class=power mais unit={unit} (energy)"
        return "OK", f"power (unit={unit or '?'})"

    if dc == "energy" or unit in ENERGY_UNITS:
        if unit in POWER_UNITS:
            return "ERROR", f"device_class=energy mais unit={unit} (power)"
        return "OK", f"energy (unit={unit or '?'})"

    if unit is None and dc is None:
        return "WARN", "unit/device_class absents"

    return "WARN", f"inclassable (device_class={dc}, unit={unit})"


def main():
    base = os.getcwd()

    sel_path = find_one(os.path.join(base, ".storage", "home_suivi_elec_capteurs_selection_v*"))
    cat_path = find_one(os.path.join(base, ".storage", "home_suivi_elec_capteurs_power_v*"))

    if not sel_path:
        raise SystemExit("Selection introuvable: .storage/home_suivi_elec_capteurs_selection_v*")
    if not cat_path:
        raise SystemExit("Catalogue introuvable: .storage/home_suivi_elec_capteurs_power_v*")

    selection_raw = load_json(sel_path)
    catalog_raw = load_json(cat_path)

    selection = unwrap_store(selection_raw)
    catalog = unwrap_store(catalog_raw)

    if not isinstance(catalog, list):
        raise SystemExit(f"Catalogue invalide (pas une liste): {type(catalog)}")

    index: Dict[str, Dict[str, Any]] = {}
    for it in catalog:
        if not isinstance(it, dict):
            continue
        eid = it.get("entity_id") or it.get("entityid") or it.get("entityId")
        if eid:
            index[str(eid)] = it

    enabled = iter_enabled_entities(selection)

    print(f"Selection: {len(enabled)} entités enabled")
    print(f"Catalogue: {len(index)} entités indexées")
    print("")

    missing = 0
    warn = 0
    err = 0

    for eid in enabled:
        meta = index.get(eid)
        if not meta:
            missing += 1
            print(f"MISSING  {eid}  (absent du catalogue capteurs_power)")
            continue

        level, msg = classify(meta)
        if level == "WARN":
            warn += 1
        elif level == "ERROR":
            err += 1

        name = meta.get("friendly_name") or meta.get("nom") or ""
        print(f"{level:<7} {eid}  {name}  → {msg}")

    print("\nRésumé:")
    print(f"- OK/WARN/ERROR/MISSING: {len(enabled) - warn - err - missing}/{warn}/{err}/{missing}")


if __name__ == "__main__":
    main()
