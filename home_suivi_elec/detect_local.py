# -*- coding: utf-8 -*-
"""
Détection automatique des capteurs power/energy depuis Home Assistant.

VERSION 2.10 : Détection multi-intégration complète
  ✅ Détection native sans subprocess jq
  ✅ Classification enrichie (device_class > unit > state_class)
  ✅ Filtrage intelligent avec valeurs par défaut
  ✅ Architecture prête pour config_entry.options (TODO CONFIG)
  ✅ Tagging des helpers
  ✅ Détection multi-plateforme enrichie
  ✅ NOUVEAU : Groupement par (device_id, integration) pour capturer TOUTES les intégrations
  ✅ NOUVEAU : Conservation des sensors de toutes les intégrations (Tapo + TP-Link + etc.)

PRIORITÉS :
  1. Energy (kWh) physique > Power (W) physique
  2. Energy virtuel (PowerCalc) > Power virtuel (PowerCalc)
  3. Physique > Virtuel > Helper
  4. today_energy > device_energy (pour Tapo/Tuya)

TAGS ENRICHIS :
  - integration: platform utilisé pour ce sensor
  - platform_declared: entry.platform (source officielle)
  - platform_detected: premier platform via device identifiers
  - is_multi_platform: true si même device physique dans plusieurs intégrations
  - all_platforms: liste de toutes les plateformes détectées
  - physical_signature: empreinte unique du device physique (pour groupement UI)
  - reference_type: "physical" | "calculated" | "aggregated"
  - is_virtual, is_helper, helper_type
"""

import os
import json
import yaml
import logging
from typing import Any, Dict, List, Optional, Tuple, Set
from datetime import datetime


_LOGGER = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_QUALITY_MAP_FILE = os.path.join(DATA_DIR, "integration_quality.yaml")
_CAPTEURS_FILE = os.path.join(DATA_DIR, "capteurs_power.json")

# ============================================================================
# CONFIGURATION (TODO CONFIG: À brancher sur config_entry.options)
# ============================================================================

DEFAULT_EXCLUDED_PLATFORMS = {
    "co2signal",
    "integration",
    "history_stats",
}

DEFAULT_HELPER_PLATFORMS = {
    "group": {
        "type": "aggregated",
        "description": "Somme de plusieurs sensors",
        "priority_penalty": -80,
        "ui_category": "user_helpers",
    },
    "min_max": {
        "type": "aggregated",
        "description": "Min/Max/Mean de sensors",
        "priority_penalty": -80,
        "ui_category": "user_helpers",
    },
    "statistics": {
        "type": "aggregated",
        "description": "Statistiques (moyenne, écart-type)",
        "priority_penalty": -85,
        "ui_category": "user_helpers",
    },
    "utility_meter": {
        "type": "meter",
        "description": "Compteur avec reset périodique",
        "priority_penalty": -50,
        "ui_category": "user_helpers",
    },
}

def __get_excluded_platforms(config_entry=None) -> Set[str]:
    # TODO CONFIG: Décommenter quand config_flow.py est implémenté
    # if config_entry and config_entry.options:
    #     return set(config_entry.options.get("excluded_platforms", []))
    return DEFAULT_EXCLUDED_PLATFORMS

def __get_helper_platforms(config_entry=None) -> Dict[str, Dict]:
    # TODO CONFIG: Décommenter quand config_flow.py est implémenté
    # if config_entry and config_entry.options:
    #     helper_list = config_entry.options.get("helper_platforms", [])
    #     return {h: DEFAULT_HELPER_PLATFORMS[h] for h in helper_list if h in DEFAULT_HELPER_PLATFORMS}
    return DEFAULT_HELPER_PLATFORMS

def __should_detect_helpers(config_entry=None) -> bool:
    # TODO CONFIG: Décommenter quand config_flow.py est implémenté
    # if config_entry and config_entry.options:
    #     return config_entry.options.get("detect_helpers", True)
    return True

# ============================================================================
# CONSTANTES MÉTIER
# ============================================================================

VIRTUAL_INTEGRATIONS = {
    "powercalc": {"reliability": 75, "type": "calculated"}
}

PREFERRED_ENERGY_NAMES = [
    "today_energy", "daily_energy", "device_energy", "energy",
]

PREFERRED_POWER_NAMES = [
    "current_power", "device_power", "power",
]

PRIORITY_MAP = {
    ("energy", "physical"): 100,
    ("power", "physical"): 80,
    ("energy", "calculated"): 60,
    ("power", "calculated"): 40,
    ("energy", "aggregated"): 20,
    ("power", "aggregated"): 20,
    ("energy", "unknown"): 50,
    ("power", "unknown"): 30,
}

# ============================================================================
# DÉTECTION DES PLATEFORMES
# ============================================================================

def __get_energy_platforms_from_registry(entity_reg, hass) -> Set[str]:
    platforms = set()
    for entry in entity_reg.entities.values():
        if entry.domain != "sensor":
            continue
        state = hass.states.get(entry.entity_id)
        if not state:
            continue
        attrs = state.attributes
        unit = str(attrs.get("unit_of_measurement", "")).lower().strip()
        device_class = str(attrs.get("device_class", "")).lower().strip()
        if device_class in ("power", "energy"):
            platforms.add(entry.platform)
        elif any(u in unit for u in ["w", "wh", "kwh", "kw", "mwh", "watt"]):
            platforms.add(entry.platform)
    return platforms

# ============================================================================
# CLASSIFICATION
# ============================================================================

def __classify_sensor(state) -> str:
    """Classe le sensor brut en 'power' ou 'energy' de façon cohérente avec HSE."""
    if not state:
        return "unknown"

    attrs = state.attributes or {}
    device_class = str(attrs.get("device_class", "")).lower().strip()
    unit = str(attrs.get("unit_of_measurement", "")).lower().strip()
    state_class = str(attrs.get("state_class", "")).lower().strip()

    # Capteurs power instantanés
    if device_class == "power" and state_class == "measurement" and unit in ("w", "kw"):
        return "power"

    # Capteurs energy directs (compteurs)
    if device_class == "energy" and state_class == "total_increasing" and unit in ("kwh", "wh"):
        return "energy"

    # Fallbacks doux pour compat anciens capteurs
    if device_class == "power" and unit in ("w", "watt", "watts", "kw", "kilowatt"):
        return "power"

    if device_class == "energy" and unit in ("kwh", "wh", "mwh", "gwh"):
        return "energy"

    if state_class in ("total", "total_increasing") and unit in ("kwh", "wh"):
        return "energy"

    return "unknown"


def __classify_platform(platform: str, has_device_id: bool, excluded_platforms: Set[str], helper_platforms: Dict[str, Dict]) -> Dict[str, Any]:
    if platform in excluded_platforms:
        return {"action": "exclude", "reason": "user_excluded"}
    if platform in helper_platforms:
        config = helper_platforms[platform]
        return {"action": "include", "reference_type": config["type"], "is_helper": True, "helper_config": config}
    if has_device_id:
        return {"action": "include", "reference_type": "physical", "is_helper": False}
    if platform in VIRTUAL_INTEGRATIONS:
        return {"action": "include", "reference_type": "calculated", "is_helper": False}
    return {"action": "include", "reference_type": "unknown", "is_helper": False}

def __calculate_priority(sensor_type: str, reference_type: str, helper_config: Optional[Dict] = None) -> int:
    base_priority = PRIORITY_MAP.get((sensor_type, reference_type), 25)
    if helper_config:
        penalty = helper_config.get("priority_penalty", 0)
        base_priority += penalty
    return max(0, base_priority)

def __calculate_reliability_score(platform: str, reference_type: str, has_device_id: bool) -> int:
    if has_device_id:
        return 100
    if platform in VIRTUAL_INTEGRATIONS:
        return VIRTUAL_INTEGRATIONS[platform]["reliability"]
    if reference_type == "aggregated":
        return 30
    return 50

# ============================================================================
# DÉTECTION MULTI-PLATEFORME
# ============================================================================

def __detect_all_platforms_from_device(device_reg, device_id: str) -> List[str]:
    if not device_id:
        return []
    device = device_reg.async_get(device_id)
    if not device or not device.identifiers:
        return []
    platforms = []
    for identifier in device.identifiers:
        if isinstance(identifier, (tuple, list)) and len(identifier) >= 1:
            platform = str(identifier[0]).lower()
            if platform not in platforms:
                platforms.append(platform)
    return platforms

def __get_physical_device_signature(device_reg, device_id: str) -> Optional[str]:
    device = device_reg.async_get(device_id)
    if not device or not device.identifiers:
        return None
    unique_ids = []
    for identifier in device.identifiers:
        if isinstance(identifier, (tuple, list)) and len(identifier) >= 2:
            unique_id = str(identifier[1])
            if unique_id not in unique_ids:
                unique_ids.append(unique_id)
    if not unique_ids:
        return None
    return "|".join(sorted(unique_ids))

def __detect_integration_complete(entity_reg, device_reg, entity_id: str, entry) -> Dict[str, Any]:
    result = {
        "integration": "unknown",
        "platform_declared": None,
        "platform_detected": None,
        "is_multi_platform": False,
        "all_platforms": [],
        "all_platforms_raw": [],
        "physical_signature": None,
    }
    
    if entry.platform:
        result["platform_declared"] = str(entry.platform).lower()
        result["all_platforms_raw"].append(result["platform_declared"])
    
    if entry.device_id:
        detected_platforms = __detect_all_platforms_from_device(device_reg, entry.device_id)
        if detected_platforms:
            result["platform_detected"] = detected_platforms[0]
            result["all_platforms_raw"].extend(detected_platforms)
        result["physical_signature"] = __get_physical_device_signature(device_reg, entry.device_id)
    
    result["all_platforms_raw"] = list(set(result["all_platforms_raw"]))
    result["all_platforms"] = result["all_platforms_raw"]
    
    if len(result["all_platforms"]) > 1:
        result["is_multi_platform"] = True
        _LOGGER.info(
            f"🔀 {entity_id} → Multi-plateforme détecté ! "
            f"Platform déclaré: {result['platform_declared']}, "
            f"Plateformes disponibles: {result['all_platforms']}, "
            f"Signature physique: {result['physical_signature']}"
        )
    
    result["integration"] = result["platform_declared"] or result["platform_detected"] or "unknown"
    _LOGGER.debug(
        f"🔍 {entity_id} → integration: {result['integration']} "
        f"(declared={result['platform_declared']}, detected={result['platform_detected']})"
    )
    
    return result

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def __read_json_sync(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def __write_json_sync(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def __load_quality_map_sync() -> Dict[str, str]:
    if not os.path.exists(_QUALITY_MAP_FILE):
        return {}
    with open(_QUALITY_MAP_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        return {str(k): str(v) for k, v in data.items()}

def __is_premium(quality_scale: str) -> bool:
    return quality_scale in ("platinum", "gold")

def __device_signature(c: Dict[str, Any]) -> str:
    name = (c.get("friendly_name") or c.get("nom") or "").strip().lower()
    
    # Nettoyer TOUS les suffixes energy
    name = name.replace("device energy", "")
    name = name.replace("today energy", "")
    name = name.replace("consommation d'aujourd'hui", "")
    name = name.replace("d'aujourd'hui", "")
    
    # Nettoyer TOUS les suffixes power
    name = name.replace("device power", "")
    name = name.replace("current power", "")
    name = name.replace("consommation actuelle", "")
    name = name.replace("actuelle", "")
    
    # Nettoyer les mots génériques
    name = name.replace("consommation", "")
    name = name.replace("puissance", "")
    
    # Nettoyer les espaces multiples
    name = " ".join(name.split())
    
    zone = (c.get("zone") or "").strip().lower()
    sensor_type = (c.get("type") or "").strip().lower()
    return f"{name}|{zone}|{sensor_type}"

def __get_name_preference(entity_id: str, sensor_type: str) -> int:
    entity_lower = entity_id.lower()
    if sensor_type == "energy":
        for idx, name in enumerate(PREFERRED_ENERGY_NAMES):
            if name in entity_lower:
                return idx
    elif sensor_type == "power":
        for idx, name in enumerate(PREFERRED_POWER_NAMES):
            if name in entity_lower:
                return idx
    return 999

# ============================================================================
# DÉTECTION PRINCIPALE - VERSION 2.10
# ============================================================================

def __detect_from_hass(hass, config_entry=None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    VERSION 2.10 : Groupement par (device_id, integration) pour capturer
    TOUTES les intégrations d'un même device physique.
    """
    try:
        from homeassistant.helpers import (
            entity_registry as er,
            device_registry as dr,
            area_registry as ar,
        )
    except ImportError:
        _LOGGER.error("Impossible d'importer les registries HA")
        return ([], [])

    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    excluded_platforms = __get_excluded_platforms(config_entry)
    helper_platforms = __get_helper_platforms(config_entry)
    detect_helpers = __should_detect_helpers(config_entry)
    
    _LOGGER.info(
        f"🔧 Config: exclusions={list(excluded_platforms)}, "
        f"helpers={'activés' if detect_helpers else 'désactivés'}"
    )

    energy_platforms = __get_energy_platforms_from_registry(entity_reg, hass)
    _LOGGER.info(f"✅ Plateformes énergétiques détectées: {sorted(energy_platforms)}")

    # CHANGEMENT V2.10 : Dict avec clé (device_id, integration)
    devices: Dict[str, Dict[str, Any]] = {}

    for state in hass.states.async_all("sensor"):
        entity_id = state.entity_id
        
        if entity_id.startswith("sensor.hse_"):
            continue
        
        sensor_type = __classify_sensor(state)
        if sensor_type == "unknown":
            continue
        
        entry = entity_reg.async_get(entity_id)
        if not entry:
            continue
        
        integration_info = __detect_integration_complete(entity_reg, device_reg, entity_id, entry)
        integration = integration_info["integration"]
        
        if integration not in energy_platforms:
            continue

        device_id = entry.device_id
        has_device_id = bool(device_id)
        
        platform_info = __classify_platform(
            integration,
            has_device_id,
            excluded_platforms,
            helper_platforms if detect_helpers else {}
        )
        
        if platform_info["action"] == "exclude":
            _LOGGER.debug(
                f"🚫 {entity_id} exclu : plateforme={integration} "
                f"(raison: {platform_info['reason']})"
            )
            continue
        
        is_helper = platform_info.get("is_helper", False)
        if is_helper and not detect_helpers:
            _LOGGER.debug(f"🚫 {entity_id} exclu : helper désactivé par config")
            continue
        
        is_virtual = not has_device_id
        
        if is_virtual and not is_helper:
            safe_name = entity_id.replace("sensor.", "")[:50]
            device_id = f"virtual_{integration}_{safe_name}"

        # CHANGEMENT V2.10 : Clé unique = device_id + integration
        device_key = f"{device_id}@{integration}"

        if device_key not in devices:
            if is_virtual or is_helper:
                devices[device_key] = {
                    "device_id": device_id,
                    "integration": integration,
                    "name": state.attributes.get("friendly_name", entity_id),
                    "manufacturer": integration.capitalize(),
                    "model": "Helper" if is_helper else "Virtual Sensor",
                    "area": "",
                    "is_virtual": is_virtual,
                    "is_helper": is_helper,
                    "sensors": {"energy": [], "power": []}
                }
            else:
                device = device_reg.async_get(device_id)
                if not device:
                    continue
                area = None
                if device.area_id:
                    area = area_reg.async_get_area(device.area_id)
                devices[device_key] = {
                    "device_id": device_id,
                    "integration": integration,
                    "name": device.name or "Unknown",
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "area": area.name if area else "",
                    "is_virtual": False,
                    "is_helper": False,
                    "sensors": {"energy": [], "power": []}
                }

        reference_type = platform_info["reference_type"]
        helper_config = platform_info.get("helper_config")
        
        reliability = __calculate_reliability_score(integration, reference_type, has_device_id)
        priority = __calculate_priority(sensor_type, reference_type, helper_config)

        cand = {
            "entity_id": entity_id,
            "friendly_name": state.attributes.get("friendly_name", entity_id),
            "unit": state.attributes.get("unit_of_measurement"),
            "device_class": state.attributes.get("device_class"),
            "state_class": state.attributes.get("state_class"),
            "integration": integration,
            "is_virtual": is_virtual,
            "is_helper": is_helper,
            "helper_type": helper_config.get("type") if helper_config else None,
            "reference_type": reference_type,
            "reliability_score": reliability,
            "priority": priority,
            "platform_declared": integration_info["platform_declared"],
            "platform_detected": integration_info["platform_detected"],
            "is_multi_platform": integration_info["is_multi_platform"],
            "all_platforms": integration_info["all_platforms"],
            "physical_signature": integration_info["physical_signature"],
        }
        devices[device_key]["sensors"][sensor_type].append(cand)

    result_energy = []
    result_power = []

    for device_key, device_data in devices.items():
        energy_sensors = device_data["sensors"]["energy"]
        power_sensors = device_data["sensors"]["power"]

        if energy_sensors:
            energy_sensors.sort(
                key=lambda x: (
                    -x["priority"],
                    __get_name_preference(x["entity_id"], "energy")
                )
            )
            best_energy = energy_sensors[0]
            result_energy.append({
                "entity_id": best_energy["entity_id"],
                "friendly_name": best_energy["friendly_name"],
                "nom": device_data["name"],
                "zone": device_data["area"],
                "integration": best_energy["integration"],
                "device_id": device_data["device_id"],
                "type": "energy",
                "unit": best_energy["unit"],
                "device_class": best_energy["device_class"],
                "state_class": best_energy.get("state_class"),
                "is_virtual": best_energy["is_virtual"],
                "is_helper": best_energy["is_helper"],
                "helper_type": best_energy.get("helper_type"),
                "reference_type": best_energy["reference_type"],
                "reliability_score": best_energy["reliability_score"],
                "priority": best_energy["priority"],
                "platform_declared": best_energy["platform_declared"],
                "platform_detected": best_energy["platform_detected"],
                "is_multi_platform": best_energy["is_multi_platform"],
                "all_platforms": best_energy["all_platforms"],
                "physical_signature": best_energy["physical_signature"],
                "alternatives": [s["entity_id"] for s in energy_sensors[1:3]],
                "related_power": power_sensors[0]["entity_id"] if power_sensors else None,
                "usage": "analytics" if best_energy["is_helper"] else "tracking",
                "sync_status": "active",
                "last_seen": datetime.now().isoformat(),
                "first_detected": datetime.now().isoformat(),
                "unavailable_since": None,
                "removal_scheduled": None,
            })

        if power_sensors:
            power_sensors.sort(
                key=lambda x: (
                    -x["priority"],
                    __get_name_preference(x["entity_id"], "power")
                )
            )
            best_power = power_sensors[0]
            result_power.append({
                "entity_id": best_power["entity_id"],
                "friendly_name": best_power["friendly_name"],
                "nom": device_data["name"],
                "zone": device_data["area"],
                "integration": best_power["integration"],
                "device_id": device_data["device_id"],
                "type": "power",
                "unit": best_power["unit"],
                "device_class": best_power["device_class"],
                "state_class": best_power.get("state_class"),
                "is_virtual": best_power["is_virtual"],
                "is_helper": best_power["is_helper"],
                "helper_type": best_power.get("helper_type"),
                "reference_type": best_power["reference_type"],
                "reliability_score": best_power["reliability_score"],
                "priority": best_power["priority"],
                "platform_declared": best_power["platform_declared"],
                "platform_detected": best_power["platform_detected"],
                "is_multi_platform": best_power["is_multi_platform"],
                "all_platforms": best_power["all_platforms"],
                "physical_signature": best_power["physical_signature"],
                "alternatives": [s["entity_id"] for s in power_sensors[1:3]],
                "related_energy": energy_sensors[0]["entity_id"] if energy_sensors else None,
                "usage": "analytics" if best_power["is_helper"] else "monitoring",
                "sync_status": "active",
                "last_seen": datetime.now().isoformat(),
                "first_detected": datetime.now().isoformat(),
                "unavailable_since": None,
                "removal_scheduled": None,
            })

    return (result_energy, result_power)

# ============================================================================
# ANNOTATION & DÉDOUBLONNAGE
# ============================================================================

def __annotate_and_deduplicate(capteurs_raw: List[Dict[str, Any]], quality_map: Dict[str, str]) -> List[Dict[str, Any]]:
    for c in capteurs_raw:
        integ = c.get("integration")
        q = quality_map.get(integ, "custom")
        c["quality_scale"] = q
        c["is_premium"] = __is_premium(q)

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for c in capteurs_raw:
        sig = __device_signature(c)
        groups.setdefault(sig, []).append(c)

    for signature, group in groups.items():
        if len(group) > 1:
            ordered = sorted(
                group,
                key=lambda x: (
                    x.get("priority", 0),
                    x.get("is_premium", False),
                    not x.get("is_virtual", True),
                ),
                reverse=True
            )
            for idx, sensor in enumerate(ordered):
                sensor["is_duplicate"] = (idx > 0)
                sensor["is_main_duplicate"] = (idx == 0)
                sensor["duplicate_rank"] = idx + 1
                sensor["duplicate_group"] = signature
                sensor["suggested_enabled"] = (idx == 0)
                sensor["enabled"] = False  # ← AJOUT
                sensor["disabled"] = False
                sensor["alternatives"] = [
                    s["entity_id"] for s in ordered if s["entity_id"] != sensor["entity_id"]
                ][:3]

            main = ordered[0]
            duplicates_info = ", ".join([
                f"{s['entity_id']} ({s['integration']}, {s['priority']})"
                for s in ordered[1:]
            ])
            _LOGGER.info(
                f"🔍 Doublon détecté '{signature}': {len(ordered)} sensors. "
                f"Suggéré: {main['entity_id']} ({main['integration']}, priorité {main['priority']}). "
                f"Alternatives: {duplicates_info}"
            )
        else:
            sensor = group[0]
            sensor["is_duplicate"] = False
            sensor["is_main_duplicate"] = True
            sensor["duplicate_rank"] = 1
            sensor["duplicate_group"] = signature
            sensor["suggested_enabled"] = True
            sensor["enabled"] = False  # ← AJOUT
            sensor["disabled"] = False
            sensor["alternatives"] = []

    return capteurs_raw

# ============================================================================
# POINT D'ENTRÉE PRINCIPAL
# ============================================================================

async def run_detect_local(*args, **kwargs) -> List[Dict[str, Any]]:
    hass = kwargs.get("hass")
    config_entry = kwargs.get("config_entry")
    
    if hass is not None:
        quality_map = await hass.async_add_executor_job(__load_quality_map_sync)
        result_energy, result_power = __detect_from_hass(hass, config_entry)
        capteurs_final = __annotate_and_deduplicate(result_energy + result_power, quality_map)
        
        total = len(capteurs_final)
        physical = sum(1 for c in capteurs_final if not c.get("is_virtual") and not c.get("is_helper"))
        virtual = sum(1 for c in capteurs_final if c.get("is_virtual"))
        helpers = sum(1 for c in capteurs_final if c.get("is_helper"))
        multi_platform = sum(1 for c in capteurs_final if c.get("is_multi_platform"))
        energy_count = sum(1 for c in capteurs_final if c.get("type") == "energy")
        power_count = sum(1 for c in capteurs_final if c.get("type") == "power")
        duplicates = sum(1 for c in capteurs_final if c.get("is_duplicate"))
        suggested = sum(1 for c in capteurs_final if c.get("suggested_enabled"))
        
        # NOUVEAU V2.10 : Compteur par intégration
        integrations_count = {}
        for c in capteurs_final:
            integ = c.get("integration", "unknown")
            integrations_count[integ] = integrations_count.get(integ, 0) + 1
        
        _LOGGER.info(
            "[DETECT] total=%s, physique=%s, virtuel=%s, helpers=%s, multi_platform=%s, "
            "energy=%s, power=%s, doublons_detectes=%s, suggeres_actifs=%s",
            total, physical, virtual, helpers, multi_platform, energy_count, power_count, duplicates, suggested
        )
        _LOGGER.info(
            "[DETECT] Répartition par intégration: %s",
            ", ".join([f"{k}={v}" for k, v in sorted(integrations_count.items(), key=lambda x: -x[1])[:10]])
        )
        
        await hass.async_add_executor_job(__write_json_sync, _CAPTEURS_FILE, capteurs_final)
        return capteurs_final
    else:
        quality_map = __load_quality_map_sync()
        capteurs_raw = __read_json_sync(_CAPTEURS_FILE) if os.path.exists(_CAPTEURS_FILE) else []
        capteurs_final = __annotate_and_deduplicate(capteurs_raw, quality_map)
        
        total = len(capteurs_final)
        duplicates = sum(1 for c in capteurs_final if c.get("is_duplicate"))
        suggested = sum(1 for c in capteurs_final if c.get("suggested_enabled"))
        
        print(f"[DETECT] capteurs_total={total}, doublons={duplicates}, suggeres={suggested}")
        __write_json_sync(_CAPTEURS_FILE, capteurs_final)
        return capteurs_final

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_detect_local())
