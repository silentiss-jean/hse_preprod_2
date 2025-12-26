# -*- coding: utf-8 -*-
"""
Gestion métier + index capteurs pour Home Suivi Élec.
- Index entity_id -> infos enrichies (device, qualité, référence)
- Exposition utilitaire async_get_capteurs_index pour __init__.py
- Enregistrement des vues REST depuis manage_selection_views.py

PHASE 2.7: Adapté pour utiliser StorageManager au lieu de fichiers JSON.
"""

import os
import json
import logging
import asyncio
import yaml
from functools import partial
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, device_registry as dr, area_registry as ar

_LOGGER = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")

# Chemins legacy (lecture seule pour capteurs_power.json et integration_quality.yaml)
CAPTEURS_POWER_PATH = os.path.join(DATA_DIR, "capteurs_power.json")
QUALITY_MAP_PATH = os.path.join(DATA_DIR, "integration_quality.yaml")

# ⚠️ DEPRECATED - Utiliser StorageManager à la place
CAPTEURS_SELECTION_PATH = os.path.join(DATA_DIR, "capteurs_selection.json")
USER_CONFIG_PATH = os.path.join(DATA_DIR, "user_config.json")

__all__ = [
    "CAPTEURS_POWER_PATH", "CAPTEURS_SELECTION_PATH", "USER_CONFIG_PATH", "QUALITY_MAP_PATH",
    "async_get_capteurs_index", "async_setup_selection_api",
]

# Mémoire process: index rapide entity_id -> infos enrichies
_CAPTEURS_INDEX: Dict[str, Dict[str, Any]] = {}


def _load_json(path: str) -> Any:
    """Charge un fichier JSON (usage legacy uniquement)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_quality_map_sync() -> Dict[str, str]:
    """Charge la carte de qualité des intégrations depuis YAML."""
    if not os.path.exists(QUALITY_MAP_PATH):
        return {}
    with open(QUALITY_MAP_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        return {str(k): str(v) for k, v in data.items()}


def _normalize(v: Optional[str]) -> str:
    """Normalise une chaîne (lowercase, trim)."""
    return (v or "").strip().lower()


def _is_premium(scale: str) -> bool:
    """Détermine si une échelle de qualité est premium."""
    return scale in ("platinum", "gold")


def _detect_source_type(c: Dict[str, Any]) -> str:
    """Classe le capteur en 'power', 'energy_direct', 'energy_utility', 'hse_energy' ou 'unknown'."""
    eid = c.get("entity_id") or ""
    # 1) DÉFINIR unit AVANT TOUT USAGE
    unit = str(c.get("unit_of_measurement") or c.get("unit") or "").lower()
    device_class = c.get("device_class")
    state_class = c.get("state_class")
    integration = (c.get("integration") or "").lower()

    # Sensors HSE générés par l'intégration
    if eid.startswith("sensor.hse_"):
        if "_energy_" in eid or eid.endswith(("_h", "_d", "_w", "_m", "_y")):
            return "hse_energy"

    # Utility meters HA
    if integration == "utility_meter" or "utility_meter" in eid:
        return "energy_utility"

    # Capteurs power instantanés
    if device_class == "power" and state_class == "measurement" and unit in ("w", "kw"):
        return "power"

    # Capteurs energy directs (compteurs)
    if device_class == "energy" and state_class == "total_increasing" and unit in ("kwh", "wh"):
        return "energy_direct"

    return "unknown"


def _enrich_base(
    c: Dict[str, Any],
    quality_map: Dict[str, str],
    reference_id: Optional[str],
    ) -> Dict[str, Any]:
    """Enrichit un capteur avec qualité, référence, typage source, origine et rôles Summary."""
    c = dict(c)

    integ = c.get("integration")
    if "quality_scale" not in c:
        q = quality_map.get(integ, "custom")
        c["quality_scale"] = q
        c["is_premium"] = _is_premium(q)

    # Capteur de référence (technique)
    c["is_reference"] = (c.get("entity_id") == reference_id)

    # Typage source
    source_type = _detect_source_type(c)
    c["source_type"] = source_type
    c["is_power"] = source_type == "power"
    c["is_energy_direct"] = source_type == "energy_direct"
    c["is_energy_utility"] = source_type == "energy_utility"
    c["is_hse_energy"] = source_type == "hse_energy"
    c["is_energy"] = source_type in ("energy_direct", "energy_utility", "hse_energy")
    c["is_unknown_source"] = source_type == "unknown"

    # Origine de la donnée (par défaut: capteur natif)
    c.setdefault("source_origin", "native")

    # --------- Flags pour Summary / sélection ---------

    # 1) Capteur sélectionné dans la config (bool métier global)
    c.setdefault("selected", False)

    # 2) Inclure ce capteur dans les agrégats Summary (conso, coûts, etc.)
    if "include_in_summary" not in c:
        c["include_in_summary"] = bool(c.get("selected", False))

    # 3) Rôle Summary optionnel
    c.setdefault("summary_role", None)

    # 4) Doit-il être totalement ignoré par les écrans Summary ?
    c.setdefault("ignore_in_summary", False)

    # --------- Flags pour capteurs de coût HA (minimal) ---------
    # On ne propose le coût HA que pour les vrais capteurs d'énergie.
    if c.get("is_energy"):
        # Préférence utilisateur: ce capteur doit-il avoir un sensor coût HA ?
        # - bool persistant, piloté par l'UI (toggle "Coût: oui/non")
        c.setdefault("cost_ha_enabled", False)

        # Entity_id du sensor de coût HA déjà créé (ou None si absent)
        c.setdefault("cost_ha_entity_id", None)

        # Dernier état brut + unité du sensor coût HA (pour un petit badge)
        c.setdefault("cost_ha_state", None)
        c.setdefault("cost_ha_unit", None)
    else:
        # Pour les non-énergie, on force à None pour que l'UI cache le toggle
        c["cost_ha_enabled"] = None
        c["cost_ha_entity_id"] = None
        c["cost_ha_state"] = None
        c["cost_ha_unit"] = None

    return c


def _enrich_device_info(hass: HomeAssistant, caps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrichit les capteurs avec infos device/area depuis registries HA."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    for c in caps:
        eid = c.get("entity_id")
        if not eid:
            continue
        entry = ent_reg.async_get(eid)
        if not entry:
            continue

        c["device_id"] = entry.device_id
        c["area_id"] = entry.area_id

        dev = dev_reg.async_get(entry.device_id) if entry.device_id else None
        if dev:
            if not c.get("area_id"):
                c["area_id"] = dev.area_id
            c["device_identifiers"] = list(dev.identifiers) if dev.identifiers else []
            c["device_connections"] = list(dev.connections) if dev.connections else []
            c["device_name"] = dev.name_by_user or dev.name or ""
            c["manufacturer"] = dev.manufacturer or ""
            c["model"] = dev.model or ""

            if c.get("area_id"):
                area = area_reg.async_get_area(c["area_id"])
                if area:
                    c["area_name"] = area.name
    return caps


async def async_get_capteurs_index(hass: HomeAssistant) -> Dict[str, Dict[str, Any]]:
    """
    Construit/retourne un index enrichi des capteurs de puissance.
    
    PHASE 2.7: Utilise StorageManager pour récupérer le capteur de référence.
    """
    global _CAPTEURS_INDEX

    if _CAPTEURS_INDEX:
        return _CAPTEURS_INDEX

    loop = asyncio.get_running_loop()
    detected = []
    if os.path.exists(CAPTEURS_POWER_PATH):
        detected = await loop.run_in_executor(None, lambda: _load_json(CAPTEURS_POWER_PATH))

    # ✅ PHASE 2.7: Récupérer capteur référence depuis StorageManager (snake_case)
    reference_id = None
    try:
        storage_manager = hass.data.get("home_suivi_elec", {}).get("storage_manager")
        if storage_manager:
            user_config = await storage_manager.get_user_config()
            reference_id = user_config.get("external_capteur")  # ✅ snake_case
        else:
            _LOGGER.warning("[INDEX] StorageManager non disponible, référence=None")
    except Exception as e:
        _LOGGER.exception("[INDEX] Erreur récupération référence: %s", e)
        reference_id = None

    quality_map = await loop.run_in_executor(None, _load_quality_map_sync)

    detected = _enrich_device_info(hass, detected or [])

    idx: Dict[str, Dict[str, Any]] = {}
    for c in detected or []:
        eid = c.get("entity_id")
        if not eid:
            continue
        idx[eid] = _enrich_base(c, quality_map, reference_id)

    _CAPTEURS_INDEX = idx
    hass.data.setdefault("home_suivi_elec", {})
    hass.data["home_suivi_elec"]["capteurs_index"] = idx
    return idx


async def async_setup_selection_api(hass: HomeAssistant, sync_manager=None):
    """Enregistre les vues REST depuis le module dédié."""
    from .manage_selection_views import (
        GetSensorsView, SaveSelectionView, GetSelectionView,
        GetConsumptionsView, GetInstantPowerView,
        GetUserConfigView, SaveUserConfigView,
        GetUserOptionsView, SaveUserOptionsView,
        GetSummaryView,
    )

    hass.http.register_view(GetSensorsView(hass))
    hass.http.register_view(SaveSelectionView(hass))
    hass.http.register_view(GetSelectionView(hass))
    hass.http.register_view(GetConsumptionsView(hass))
    hass.http.register_view(GetInstantPowerView(hass))
    hass.http.register_view(GetUserConfigView(hass))
    hass.http.register_view(SaveUserConfigView(hass))
    hass.http.register_view(SaveUserOptionsView(hass))
    hass.http.register_view(GetUserOptionsView(hass))
    hass.http.register_view(GetSummaryView(hass))
    
    # ✅ PHASE 2.6: APIs de synchronisation
    if sync_manager:
        from .manage_selection_views import GetSyncStatusView, ForceSyncView
        hass.http.register_view(GetSyncStatusView(hass, sync_manager))
        hass.http.register_view(ForceSyncView(hass, sync_manager))
        _LOGGER.info("[REST] API capteurs + sync enregistrée")
    else:
        _LOGGER.info("[REST] API capteurs enregistrée (sync non disponible)")
