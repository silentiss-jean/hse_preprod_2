# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Vues REST (HTTP) pour Home Suivi Élec — isolées du métier.

Conserve les comportements existants et la validation par device_id.
PHASE 2.7: Adapté pour Storage API avec fallback fichier JSON legacy.

✅ CORRIGÉ : Support natif des sensors HSE energy (sensor.hse_*_today_energy_{cycle})
"""

import os
import json
import logging
import asyncio
from typing import Any, Dict, List, Set, Optional, Tuple
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

# ✅ DEC-005: Définir les chemins directement pour éviter import circulaire
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
CAPTEURS_POWER_PATH = os.path.join(DATA_DIR, "capteurs_power.json")
CAPTEURS_SELECTION_PATH = os.path.join(DATA_DIR, "capteurs_selection.json")
USER_CONFIG_PATH = os.path.join(DATA_DIR, "user_config.json")

from .manage_selection import (
    _enrich_base,
    _enrich_device_info,
    _load_quality_map_sync,
)

from .const import (
    DOMAIN, DEFAULTS,
    CONF_PRIX_HT, CONF_PRIX_TTC,
    CONF_PRIX_HT_HP, CONF_PRIX_TTC_HP,
    CONF_PRIX_HT_HC, CONF_PRIX_TTC_HC,
    CONF_HC_START, CONF_HC_END,
    CONF_ABONNEMENT_MENSUEL_HT, CONF_ABONNEMENT_MENSUEL_TTC
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "home_suivi_elec"

from datetime import time

def _parse_datetime_flexible(value):
    """Parse datetime ISO ou date YYYY-MM-DD"""
    if not value:
        return None
    # Essaie datetime ISO complet
    dt = dt_util.parse_datetime(value)
    if dt:
        return dt
    # Fallback : parse date seule YYYY-MM-DD
    try:
        d = dt_util.parse_date(value)
        if d:
            from datetime import datetime
            return datetime.combine(d, time.min).replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    except Exception:
        pass
    return None

def _normalize(v: Optional[str]) -> str:
    return (v or "").strip().lower()

def _compute_signature(c: Dict[str, Any]) -> str:
    name = _normalize(c.get("friendly_name") or c.get("nom"))
    area = _normalize(c.get("area") or c.get("zone"))
    return f"{name}|{area}"

def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _build_hse_energy_sensor_id(source_entity_id: str, cycle: str) -> str:
    """
    Construit l'entity_id du sensor HSE associé à un capteur source.

    - Si la source est déjà un sensor "energy" (today_energy, consommation, etc.),
      on génère sensor.hse_<base_name>_<cycle>
    - Sinon, on génère sensor.hse_<base_name>_energy_<cycle>
    """
    base_name = (
        source_entity_id
        .replace("sensor.", "")
        .replace("_today_energy", "")
        .replace("_consommation_d_aujourd_hui", "")
    )

    is_energy = (
        "_energy" in source_entity_id
        or "_today_energy" in source_entity_id
        or "consommation" in source_entity_id
    )

    if is_energy:
        return f"sensor.hse_{base_name}_{cycle}"
    else:
        return f"sensor.hse_{base_name}_energy_{cycle}"

def _normalize_selection_entry(
    row: Dict[str, Any],
    cap: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Normalise une entrée de sélection (usage_* + méta source) en restant rétro-compatible."""
    row = dict(row)
    eid = row.get("entity_id") or ""
    cap = cap or {}

    source_type = (
        cap.get("source_type")
        or cap.get("type")
        or row.get("source_type")
        or row.get("type")
        or ""
    )

    # Si déjà présents, ne pas toucher (nouveau frontend)
    if "usage_power" in row or "usage_energy" in row:
        # On peut tout de même refléter le typage source si absent
        row.setdefault("source_type", source_type)
        row.setdefault("is_power", source_type == "power")
        row.setdefault(
            "is_energy",
            source_type in ("energy_direct", "energy_utility", "hse_energy", "energy"),
        )
        return row

    # Cas simple : si on sait déjà que c'est un power / energy
    if source_type == "power":
        row.setdefault("usage_power", eid)
        row.setdefault("usage_energy", None)
    elif source_type in ("energy_direct", "energy_utility", "hse_energy", "energy"):
        row.setdefault("usage_energy", eid)
        row.setdefault("usage_power", None)
    else:
        # Inconnu → on laisse vide, le frontend ou une passe ultérieure décidera
        row.setdefault("usage_power", None)
        row.setdefault("usage_energy", None)

    # Exposer aussi le typage source au frontend
    row.setdefault("source_type", source_type)
    row.setdefault("is_power", source_type == "power")
    row.setdefault(
        "is_energy",
        source_type in ("energy_direct", "energy_utility", "hse_energy", "energy"),
    )

    return row

def _normalize_selection_payload(
    raw: Dict[str, Any],
    by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Applique _normalize_selection_entry à tout le payload de sélection."""
    result: Dict[str, Any] = {}
    for integ, lst in (raw or {}).items():
        out_lst: List[Dict[str, Any]] = []
        for row in lst or []:
            eid = row.get("entity_id") or ""
            cap = by_id.get(eid)
            out_lst.append(_normalize_selection_entry(row, cap))
        result[integ] = out_lst
    return result

async def _get_cost_ha_map(hass: HomeAssistant) -> dict:
    """Retourne {entity_id: {enabled, cost_entity_id}} depuis le store cost_ha."""
    data = hass.data.get(DOMAIN, {})
    mgr = data.get("storage_manager") or StorageManager(hass)

    if not hasattr(mgr, "get_cost_ha_config"):
        _LOGGER.warning("[COST-HA] StorageManager sans get_cost_ha_config")
        return {}

    store = await mgr.get_cost_ha_config()
    _LOGGER.info("[COST-HA] map=%s", store)
    return store or {}

def _flatten_selection(normalized: dict) -> dict:
    """Retourne un dict {entity_id: entry} à partir du payload normalisé."""
    out = {}
    for _, lst in (normalized or {}).items():
        if not isinstance(lst, list):
            continue
        for entry in lst:
            eid = (entry or {}).get("entity_id")
            if eid:
                out[eid] = entry
    return out

def _compute_need_restart(old_norm: dict, new_norm: dict) -> bool:
    """
    Restart uniquement si changement 'hard' (sources / type),
    pas si c'est juste enabled/include_in_summary.
    """
    old_map = _flatten_selection(old_norm)
    new_map = _flatten_selection(new_norm)

    # Ajout/suppression d'entités
    if set(old_map.keys()) != set(new_map.keys()):
        return True

    soft_keys = {"enabled", "include_in_summary"}
    hard_keys = {"usage_power", "usage_energy"}

    for eid, new_entry in new_map.items():
        old_entry = old_map.get(eid) or {}

        # Si une clé "hard" change => restart
        for k in hard_keys:
            if (old_entry.get(k) != new_entry.get(k)):
                return True
                
    return False

class GetSensorsView(HomeAssistantView):
    url = "/api/home_suivi_elec/get_sensors"
    name = "api:home_suivi_elec:get_sensors"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        """✅ PHASE 2.7: Utilise StorageManager pour récupérer sélection et user_config."""
        try:
            loop = asyncio.get_running_loop()

            # Charger capteurs détectés (toujours en fichier JSON)
            data = []
            if os.path.exists(CAPTEURS_POWER_PATH):
                data = await loop.run_in_executor(
                    None, lambda: _load_json(CAPTEURS_POWER_PATH)
                )

            # ✅ Charger sélection + user_config via StorageManager (ou fallback JSON)
            storage_manager = self.hass.data.get("home_suivi_elec", {}).get(
                "storage_manager"
            )
            if storage_manager:
                selection_data = await storage_manager.get_capteurs_selection()
                user_config = await storage_manager.get_user_config()
                cost_ha_map = await storage_manager.get_cost_ha_config()
            else:
                selection_data = {}
                if os.path.exists(CAPTEURS_SELECTION_PATH):
                    selection_data = await loop.run_in_executor(
                        None, lambda: _load_json(CAPTEURS_SELECTION_PATH)
                    )
                user_config = {}
                if os.path.exists(USER_CONFIG_PATH):
                    user_config = await loop.run_in_executor(
                        None, lambda: _load_json(USER_CONFIG_PATH)
                    )
                cost_ha_map = {}

            # ✅ Ne considérer le capteur de référence que si use_external est actif
            use_external = bool(user_config.get("use_external"))
            mode = user_config.get("mode", "sensor")
            reference_id = None
            if use_external and mode != "manual":
                reference_id = user_config.get("external_capteur")

            # ✅ Charger la quality_map (comme dans manage_selection.py)
            quality_map = await loop.run_in_executor(None, _load_quality_map_sync)

            # Enrichir device info
            data = _enrich_device_info(self.hass, data or [])

            # Index des capteurs activés
            enabled_ids: Set[str] = set()
            for integ, lst in (selection_data or {}).items():
                for row in lst or []:
                    if row.get("enabled") and row.get("entity_id"):
                        enabled_ids.add(row["entity_id"])

            selections: Dict[str, List[Dict[str, Any]]] = {}
            alternatives: Dict[str, List[Dict[str, Any]]] = {}
            reference_sensor: Dict[str, Any] = {}

            def _attach_ha_state(cap: Dict[str, Any]) -> None:
                """Ajoute ha_state/ha_unit (safe) sans casser la rétro-compatibilité."""
                eid = cap.get("entity_id")
                if not eid:
                    cap["ha_state"] = "unknown"
                    cap["ha_unit"] = None
                    return
                st = self.hass.states.get(eid)
                cap["ha_state"] = st.state if st else "unknown"
                cap["ha_unit"] = (
                    st.attributes.get("unit_of_measurement") if st else None
                )

            for c in data or []:
                integ = c.get("integration", "unknown")
                eid = c.get("entity_id")

                # Retrouver la ligne de sélection associée
                sel_row = None
                for row in (selection_data.get(integ) or []):
                    if row.get("entity_id") == eid:
                        sel_row = row
                        break

                if sel_row:
                    # refléter l'état sélection + summary dans le capteur brut
                    c["selected"] = bool(sel_row.get("enabled"))
                    if "include_in_summary" in sel_row:
                        c["include_in_summary"] = bool(
                            sel_row.get("include_in_summary")
                        )

                # 🔹 fusionner la config coût depuis cost_ha_map (store dédié)
                if isinstance(cost_ha_map, dict):
                    cost_entry = cost_ha_map.get(eid)
                    if isinstance(cost_entry, dict):
                        c["cost_ha_enabled"] = bool(cost_entry.get("enabled", False))
                        c["cost_ha_entity_id"] = cost_entry.get("cost_entity_id")

                cap = _enrich_base(c, quality_map, reference_id)
                _attach_ha_state(cap)

                if eid in enabled_ids:
                    selections.setdefault(integ, []).append(cap)
                else:
                    alternatives.setdefault(integ, []).append(cap)

                if cap.get("is_reference"):
                    reference_sensor = cap

            # Fallback: exposer un reference_sensor exploitable même si external_capteur
            # n'est pas présent dans capteurs_power.json.
            if use_external and reference_id and not reference_sensor:
                st = self.hass.states.get(reference_id)
                reference_sensor = {
                    "entity_id": reference_id,
                    "friendly_name": (
                        st.attributes.get("friendly_name") if st else reference_id
                    ),
                    "integration": (
                        reference_id.split(".", 1)[0]
                        if "." in reference_id
                        else "unknown"
                    ),
                    "is_reference": True,
                    "source_origin": "external_reference",
                }
                _attach_ha_state(reference_sensor)

            return self.json(
                {
                    "selected": selections,
                    "alternatives": alternatives,
                    "reference_sensor": reference_sensor or {},
                }
            )

        except Exception as e:
            _LOGGER.exception("Erreur get_sensors: %s", e)
            return self.json(
                {"selected": {}, "alternatives": {}, "reference_sensor": {}}
            )

class SaveSelectionView(HomeAssistantView):
    url = "/api/home_suivi_elec/save_selection"
    name = "api:home_suivi_elec:save_selection"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request):
        """✅ PHASE 2.7: Sauvegarde via StorageManager."""
        try:
            body = await request.json()
            loop = asyncio.get_running_loop()

            detected = []
            if os.path.exists(CAPTEURS_POWER_PATH):
                detected = await loop.run_in_executor(None, lambda: _load_json(CAPTEURS_POWER_PATH))

            detected = _enrich_device_info(self.hass, detected or [])
            by_id: Dict[str, Dict[str, Any]] = {c.get("entity_id"): c for c in detected if c.get("entity_id")}

            seen_signatures: Set[str] = set()
            conflicts: List[Dict[str, Any]] = []

            # 1) Conflits de signature (inchangé)
            for integ, lst in (body or {}).items():
                for row in lst or []:
                    if not row.get("enabled"):
                        continue
                    eid = row.get("entity_id") or ""
                    cap = by_id.get(eid)
                    if not cap:
                        continue
                    sig = _compute_signature(cap)
                    if sig in seen_signatures:
                        conflicts.append({
                            "entity_id": eid,
                            "integration": integ,
                            "friendly_name": cap.get("friendly_name"),
                            "area": cap.get("area") or cap.get("zone"),
                            "signature": sig,
                            "type": "signature",
                        })
                    else:
                        seen_signatures.add(sig)

            # 2) Conflits par device_id, avec exception 1 power + 1 energy
            device_to_entities: Dict[str, List[Tuple[str, str]]] = {}
            for integ, lst in (body or {}).items():
                for row in lst or []:
                    if not row.get("enabled"):
                        continue
                    eid = row.get("entity_id") or ""
                    cap = by_id.get(eid)
                    if not cap:
                        continue
                    did = cap.get("device_id")
                    if not did:
                        continue
                    device_to_entities.setdefault(did, []).append((eid, integ))

            device_conflicts: List[Dict[str, Any]] = []
            for did, items in device_to_entities.items():
                if len(items) <= 1:
                    continue

                # Récupérer les types (source_type) pour ce device
                types: List[str] = []
                for eid, _ in items:
                    cap = by_id.get(eid) or {}
                    st = (cap.get("source_type") or cap.get("type") or "").lower()
                    types.append(st)

                # Normaliser les types "energy-like"
                norm_types = []
                for t in types:
                    if t.replace("_", "") in ("energydirect", "energyutility", "hseenergy"):
                        norm_types.append("energy")
                    else:
                        norm_types.append(t)

                # Cas autorisé : exactement 2 entités, 1 power + 1 energy -> pas de conflit
                if len(items) == 2 and set(norm_types) == {"power", "energy"}:
                    continue

                # Sinon, vrai conflit de device
                device_conflicts.append({
                    "device_id": did,
                    "entities": [{"entity_id": e, "integration": i} for e, i in items],
                })

            if conflicts or device_conflicts:
                return self.json({
                    "success": False,
                    "error": "Conflits détectés (doublon ou même appareil).",
                    "conflicts": conflicts,
                    "device_conflicts": device_conflicts,
                })

            # 🔹 Nouvelle étape : normaliser usage_power / usage_energy
            normalized_body: Dict[str, List[Dict[str, Any]]] = {}
            for integ, lst in (body or {}).items():
                out_lst: List[Dict[str, Any]] = []
                for row in lst or []:
                    eid = row.get("entity_id") or ""
                    cap = by_id.get(eid)
                    out_lst.append(_normalize_selection_entry(row, cap))
                normalized_body[integ] = out_lst

            # Charger l'ancienne sélection + normaliser comme GetSelectionView
            old_data = {}
            storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")
            if storage_manager:
                old_data = await storage_manager.get_capteurs_selection()
            elif os.path.exists(CAPTEURS_SELECTION_PATH):
                old_data = await loop.run_in_executor(None, lambda: _load_json(CAPTEURS_SELECTION_PATH))

            old_normalized = _normalize_selection_payload(old_data or {}, by_id)

            # Normaliser aussi la nouvelle sélection (même format que GetSelectionView)
            new_normalized = _normalize_selection_payload(normalized_body or {}, by_id)

            need_restart = _compute_need_restart(old_normalized, new_normalized)

            # ✅ PHASE 2.7: Sauvegarder via StorageManager
            storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")
            if storage_manager:
                await storage_manager.save_capteurs_selection(normalized_body)
                _LOGGER.info("[SAVE_SELECTION] Sauvegardé via Storage API")
            else:
                os.makedirs(os.path.dirname(CAPTEURS_SELECTION_PATH), exist_ok=True)
                _save_json(CAPTEURS_SELECTION_PATH, normalized_body)
                _LOGGER.warning("[SAVE_SELECTION] Sauvegardé via fichier JSON (fallback)")

            selected_ids: Set[str] = set()
            for integ, lst in (normalized_body or {}).items():
                for row in lst or []:
                    if row.get("enabled") and row.get("entity_id"):
                        selected_ids.add(row["entity_id"])

            message = (
                "Sélection enregistrée (appliquée immédiatement)."
                if not need_restart
                else "Sélection enregistrée. Recharge/redémarrage nécessaire pour appliquer le changement de source."
            )

            return self.json({
                "success": True,
                "selected": sorted(selected_ids),
                "need_restart": need_restart,
                "message": message,
            })

        except Exception as e:
            _LOGGER.exception("Erreur save_selection: %s", e)
            return self.json({"success": False, "need_restart": False, "error": str(e)})

class GetSelectionView(HomeAssistantView):
    url = "/api/home_suivi_elec/get_selection"
    name = "api:home_suivi_elec:get_selection"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        """✅ PHASE 2.7: Utilise StorageManager au lieu du fichier JSON."""
        try:
            storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")
            loop = asyncio.get_running_loop()

            # 🔹 récupérer aussi le mapping coût HA
            cost_map = await _get_cost_ha_map(self.hass)

            # Charger les capteurs détectés pour avoir by_id (comme dans SaveSelectionView)
            detected = []
            if os.path.exists(CAPTEURS_POWER_PATH):
                detected = await loop.run_in_executor(None, lambda: _load_json(CAPTEURS_POWER_PATH))

            detected = _enrich_device_info(self.hass, detected or [])
            by_id: Dict[str, Dict[str, Any]] = {c.get("entity_id"): c for c in detected if c.get("entity_id")}

            if not storage_manager:
                _LOGGER.error("[GET_SELECTION] StorageManager non disponible")
                # Fallback sur fichier JSON legacy
                if os.path.exists(CAPTEURS_SELECTION_PATH):
                    data = await loop.run_in_executor(None, lambda: _load_json(CAPTEURS_SELECTION_PATH))
                    normalized = _normalize_selection_payload(data or {}, by_id)

                    # 🔹 enrichir avec cost_ha dans le mode fallback aussi
                    for category, sensors in normalized.items():
                        if not isinstance(sensors, list):
                            continue
                        for entry in sensors:
                            entity_id = entry.get("entity_id")
                            if not entity_id:
                                continue
                            cfg = cost_map.get(entity_id) or {}
                            entry["cost_ha_enabled"] = bool(cfg.get("enabled", False))
                            entry["cost_ha_entity_id"] = cfg.get("cost_entity_id")

                    return self.json(normalized)
                return self.json({})

            data = await storage_manager.get_capteurs_selection()
            normalized = _normalize_selection_payload(data or {}, by_id)

            # 🔹 enrichir toutes les entrées avec cost_ha
            for category, sensors in normalized.items():
                if not isinstance(sensors, list):
                    continue
                for entry in sensors:
                    entity_id = entry.get("entity_id")
                    if not entity_id:
                        continue
                    cfg = cost_map.get(entity_id) or {}
                    entry["cost_ha_enabled"] = bool(cfg.get("enabled", False))
                    entry["cost_ha_entity_id"] = cfg.get("cost_entity_id")

            return self.json(normalized)

        except Exception as e:
            _LOGGER.exception("Erreur get_selection: %s", e)
            return self.json({})

class GetConsumptionsView(HomeAssistantView):
    """✅ CORRIGÉ : Utilise les sensors HSE energy natifs."""
    url = "/api/home_suivi_elec/get_consumptions"
    name = "api:home_suivi_elec:get_consumptions"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        """✅ PHASE 2.7: Charge sélection via StorageManager."""
        try:
            # ✅ Charger sélection via StorageManager
            storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")
            if storage_manager:
                selections = await storage_manager.get_capteurs_selection()
                user_config = await storage_manager.get_user_config()
            else:
                loop = asyncio.get_running_loop()
                selections = await loop.run_in_executor(
                    None, lambda: _load_json(CAPTEURS_SELECTION_PATH)
                ) if os.path.exists(CAPTEURS_SELECTION_PATH) else {}
                user_config = await loop.run_in_executor(
                    None, lambda: _load_json(USER_CONFIG_PATH)
                ) if os.path.exists(USER_CONFIG_PATH) else {}

            external_id = user_config.get("external_capteur")
            use_external = bool(user_config.get("use_external"))

            cycles = ["hourly", "daily", "weekly", "monthly", "yearly"]
            result: Dict[str, Dict[str, Optional[float]]] = {}

            # Sensors HSE
            for integration, capteurs in (selections or {}).items():
                for c in (capteurs or []):
                    if not (c.get("enabled") and c.get("entity_id")):
                        continue
                    capteur_id = c["entity_id"]
                    result.setdefault(capteur_id, {})

                    for cycle in cycles:
                        hse_sensor_id = _build_hse_energy_sensor_id(capteur_id, cycle)
                        st = self.hass.states.get(hse_sensor_id)
                        value: Optional[float] = None
                        if st and st.state not in (None, "unknown", "unavailable"):
                            try:
                                value = float(st.state)
                            except Exception:
                                value = None
                        result[capteur_id][cycle] = value

            # Capteur externe (référence)
            if use_external and external_id:
                result.setdefault(external_id, {})
                for cycle in cycles:
                    hse_sensor_id = _build_hse_energy_sensor_id(external_id, cycle)
                    st = self.hass.states.get(hse_sensor_id)
                    value: Optional[float] = None
                    if st and st.state not in (None, "unknown", "unavailable"):
                        try:
                            value = float(st.state)
                        except Exception:
                            value = None
                    result[external_id][cycle] = value

            return self.json(result)

        except Exception as e:
            _LOGGER.exception("Erreur get_consumptions: %s", e)
            return self.json({})

class GetInstantPowerView(HomeAssistantView):
    url = "/api/home_suivi_elec/get_instant_puissance"
    name = "api:home_suivi_elec:get_instant_puissance"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        """✅ PHASE 2.7: Charge sélection via StorageManager.

        ⚠️ Endpoint puissance instantanée (W): ne doit pas remonter des capteurs énergie
        (kWh/Wh), sinon le frontend peut les additionner par erreur comme des watts.
        """
        try:
            # ✅ Charger sélection via StorageManager
            storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")
            if storage_manager:
                selection = await storage_manager.get_capteurs_selection()
                user_config = await storage_manager.get_user_config()
            else:
                loop = asyncio.get_running_loop()
                selection = await loop.run_in_executor(
                    None, lambda: _load_json(CAPTEURS_SELECTION_PATH)
                ) if os.path.exists(CAPTEURS_SELECTION_PATH) else {}
                user_config = await loop.run_in_executor(
                    None, lambda: _load_json(USER_CONFIG_PATH)
                ) if os.path.exists(USER_CONFIG_PATH) else {}

            # ✅ Garder uniquement les sources power
            entity_ids: List[str] = []
            ignored: List[str] = []

            for capteurs in (selection or {}).values():
                for c in (capteurs or []):
                    if not (c.get("enabled") and c.get("entity_id")):
                        continue

                    # Format normalisé: usage_power prioritaire
                    if c.get("usage_power"):
                        entity_ids.append(c["usage_power"])
                        continue

                    source_type = str(c.get("source_type") or "").lower()
                    is_power = bool(c.get("is_power")) or source_type == "power"
                    is_energy = bool(c.get("is_energy")) or bool(c.get("usage_energy"))

                    if is_power:
                        entity_ids.append(c["entity_id"])
                    elif is_energy:
                        ignored.append(c["entity_id"])
                    else:
                        # Type inconnu => prudence (éviter mélange d'unités)
                        ignored.append(c["entity_id"])

            # dédoublonnage stable
            seen: Set[str] = set()
            deduped: List[str] = []
            for eid in entity_ids:
                if eid in seen:
                    continue
                seen.add(eid)
                deduped.append(eid)
            entity_ids = deduped

            if ignored:
                _LOGGER.warning(
                    "[INSTANT_POWER] %s capteur(s) non-power ignoré(s) pour la puissance instantanée: %s",
                    len(ignored),
                    ", ".join(ignored[:10]) + ("..." if len(ignored) > 10 else ""),
                )

            use_external = bool(user_config.get("use_external"))
            ext_id = user_config.get("external_capteur")
            if use_external and ext_id and ext_id not in entity_ids:
                entity_ids.append(ext_id)

            power_states: Dict[str, Optional[float]] = {}
            for entity_id in entity_ids:
                state = self.hass.states.get(entity_id)
                try:
                    if state is None or state.state in (None, "unknown", "unavailable"):
                        power_states[entity_id] = None
                        continue

                    raw = float(state.state)
                    unit = (state.attributes.get("unit_of_measurement") or "").strip()

                    # Normaliser kW -> W si besoin
                    if unit == "kW":
                        power_states[entity_id] = raw * 1000.0
                    elif unit in ("W", ""):
                        power_states[entity_id] = raw
                    else:
                        # unité non puissance => on renvoie None pour éviter toute addition invalide
                        power_states[entity_id] = None
                except Exception:
                    power_states[entity_id] = None

            return self.json(power_states)

        except Exception as e:
            _LOGGER.exception("Erreur get_instant_puissance: %s", e)
            return self.json({})

class SensorMappingView(HomeAssistantView):
    """✅ NOUVEAU : Endpoint pour récupérer le mapping des consommations par période."""
    url = "/api/home_suivi_elec/sensor_mapping"
    name = "api:home_suivi_elec:sensor_mapping"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        """Retourne le mapping { entity_id: { hourly: kWh, daily: kWh, ... } }."""
        try:
            storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")
            if storage_manager:
                selection = await storage_manager.get_capteurs_selection()
                user_config = await storage_manager.get_user_config()
            else:
                loop = asyncio.get_running_loop()
                selection = await loop.run_in_executor(
                    None, lambda: _load_json(CAPTEURS_SELECTION_PATH)
                ) if os.path.exists(CAPTEURS_SELECTION_PATH) else {}
                user_config = await loop.run_in_executor(
                    None, lambda: _load_json(USER_CONFIG_PATH)
                ) if os.path.exists(USER_CONFIG_PATH) else {}

            cycles = ["hourly", "daily", "weekly", "monthly", "yearly"]
            mapping: Dict[str, Dict[str, Optional[float]]] = {}

            # Récupérer tous les entity_ids sélectionnés
            entity_ids: List[str] = []
            for capteurs in (selection or {}).values():
                for c in (capteurs or []):
                    if c.get("enabled") and c.get("entity_id"):
                        entity_ids.append(c["entity_id"])

            # Ajouter le capteur externe si actif
            use_external = bool(user_config.get("use_external"))
            ext_id = user_config.get("external_capteur")
            if use_external and ext_id and ext_id not in entity_ids:
                entity_ids.append(ext_id)

            # Pour chaque capteur, récupérer les valeurs des sensors HSE energy
            for entity_id in entity_ids:
                mapping[entity_id] = {}
                for cycle in cycles:
                    hse_sensor_id = _build_hse_energy_sensor_id(entity_id, cycle)
                    state = self.hass.states.get(hse_sensor_id)
                    value: Optional[float] = None
                    if state and state.state not in (None, "unknown", "unavailable"):
                        try:
                            value = float(state.state)
                        except Exception:
                            value = None
                    mapping[entity_id][cycle] = value

            _LOGGER.info(f"[SENSOR_MAPPING] ✅ Mapping extrait: {len(mapping)} capteurs")
            return self.json({
                "data": {
                    "mapping": mapping,
                    "total_sources": len(mapping)
                },
                "total_hse_sensors": len(entity_ids) * len(cycles)
            })

        except Exception as e:
            _LOGGER.exception("Erreur sensor_mapping: %s", e)
            return self.json({
                "data": {"mapping": {}, "total_sources": 0},
                "total_hse_sensors": 0
            })


class GetUserConfigView(HomeAssistantView):
    url = "/api/home_suivi_elec/get_user_config"
    name = "api:home_suivi_elec:get_user_config"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        """✅ PHASE 2.7: Utilise StorageManager."""
        try:
            storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")
            if not storage_manager:
                _LOGGER.error("[GET_USER_CONFIG] StorageManager non disponible")
                # Fallback fichier JSON
                if os.path.exists(USER_CONFIG_PATH):
                    loop = asyncio.get_running_loop()
                    data = await loop.run_in_executor(None, lambda: _load_json(USER_CONFIG_PATH))
                    return self.json(data)
                return self.json({})

            data = await storage_manager.get_user_config()
            return self.json(data or {})

        except Exception as e:
            _LOGGER.exception("Erreur get_user_config: %s", e)
            return self.json({})

class SaveUserConfigView(HomeAssistantView):
    url = "/api/home_suivi_elec/save_user_config"
    name = "api:home_suivi_elec:save_user_config"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request):
        """✅ PHASE 2.7: Utilise StorageManager."""
        try:
            body = await request.json()

            storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")
            if storage_manager:
                await storage_manager.save_user_config(body)
                _LOGGER.info("[SAVE_USER_CONFIG] Sauvegardé via Storage API")
            else:
                # Fallback fichier JSON
                _save_json(USER_CONFIG_PATH, body)
                _LOGGER.warning("[SAVE_USER_CONFIG] Sauvegardé via fichier JSON (fallback)")

            return self.json({"success": True})

        except Exception as e:
            _LOGGER.exception("Erreur save_user_config: %s", e)
            return self.json({"success": False})

class GetUserOptionsView(HomeAssistantView):
    url = "/api/home_suivi_elec/get_user_options"
    name = "api:home_suivi_elec:get_user_options"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Optional[Store] = None

    async def _load_ignored(self) -> List[str]:
        """✅ PHASE 2.7: Charge ignored depuis StorageManager."""
        try:
            storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")
            if not storage_manager:
                _LOGGER.error("GetUserOptionsView: StorageManager non disponible")
                return []
            return await storage_manager.get_ignored_entities()
        except Exception as e:
            _LOGGER.exception("GetUserOptionsView: ignored_entities load failed: %s", e)
            return []

    async def get(self, request):
        try:
            entries = self.hass.config_entries.async_entries("home_suivi_elec")
            if not entries:
                return self.json({})

            entry: ConfigEntry = entries[0]
            data = dict(entry.data or {})
            opts = dict(entry.options or {})

            # ✅ Normalisation type_contrat avec priorité options > data
            type_contrat = (opts.get("type_contrat") or data.get("type_contrat") or "prix_unique")
            type_contrat = str(type_contrat).strip().lower()
            if type_contrat in ("hp-hc", "heurescreuses", "heures_creuses"):
                type_contrat = "heures_creuses"
            if type_contrat in ("fixe", "prixunique", "prix_unique"):
                type_contrat = "prix_unique"

            # Fusionner data + opts APRÈS avoir extrait type_contrat
            eff = {**data, **opts}

            defaults_fixe = DEFAULTS.get("prix_unique", {})
            defaults_hc = DEFAULTS.get("heures_creuses", {})

            resp = {
                "type_contrat": type_contrat,
                "abonnement_ht": eff.get("abonnement_ht", eff.get(CONF_ABONNEMENT_MENSUEL_HT, defaults_fixe.get(CONF_ABONNEMENT_MENSUEL_HT, 0))),
                "abonnement_ttc": eff.get("abonnement_ttc", eff.get(CONF_ABONNEMENT_MENSUEL_TTC, defaults_fixe.get(CONF_ABONNEMENT_MENSUEL_TTC, 0))),
                "prix_ht": eff.get(CONF_PRIX_HT, eff.get("prix_ht", defaults_fixe.get(CONF_PRIX_HT, 0))),
                "prix_ttc": eff.get(CONF_PRIX_TTC, eff.get("prix_ttc", defaults_fixe.get(CONF_PRIX_TTC, 0))),
                "prix_ht_hp": eff.get(CONF_PRIX_HT_HP, eff.get("prix_ht_hp", defaults_hc.get(CONF_PRIX_HT_HP, 0))),
                "prix_ttc_hp": eff.get(CONF_PRIX_TTC_HP, eff.get("prix_ttc_hp", defaults_hc.get(CONF_PRIX_TTC_HP, 0))),
                "prix_ht_hc": eff.get(CONF_PRIX_HT_HC, eff.get("prix_ht_hc", defaults_hc.get(CONF_PRIX_HT_HC, 0))),
                "prix_ttc_hc": eff.get(CONF_PRIX_TTC_HC, eff.get("prix_ttc_hc", defaults_hc.get(CONF_PRIX_TTC_HC, 0))),
                "hc_start": eff.get(CONF_HC_START, eff.get("hc_start", defaults_hc.get(CONF_HC_START, "22:00"))),
                "hc_end": eff.get(CONF_HC_END, eff.get("hc_end", defaults_hc.get(CONF_HC_END, "06:00"))),
                "use_external": bool(eff.get("use_external", False)),
                "external_capteur": eff.get("external_capteur", ""),
                "consommation_externe": eff.get("consommation_externe", 0),
                "mode": eff.get("mode", "sensor"),
                "enable_cost_sensors_runtime": bool(eff.get("enable_cost_sensors_runtime", False)),
            }

            resp["ignored_entities"] = await self._load_ignored()
            return self.json(resp)

        except Exception as e:
            _LOGGER.exception("Erreur get_user_options: %s", e)
            return self.json({})

class SaveUserOptionsView(HomeAssistantView):
    url = "/api/home_suivi_elec/save_user_options"
    name = "api:home_suivi_elec:save_user_options"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request):
        try:
            entries = self.hass.config_entries.async_entries(DOMAIN)
            if not entries:
                return self.json({"success": False})

            entry: ConfigEntry = entries[0]
            body = await request.json()

            if not isinstance(body, dict):
                return self.json(
                    {"success": False, "error": "Payload must be a JSON object"},
                    status_code=400,
                )

            current_opts: Dict[str, Any] = dict(entry.options or {})

            # Refus strict du camelCase (API snake_case only)
            forbidden = [
                k
                for k in body.keys()
                if any(x in k for x in ("Contrat", "External", "Capteur", "Externe", "Runtime"))
            ]
            if forbidden:
                return self.json(
                    {
                        "success": False,
                        "error": "camelCase keys are not accepted",
                        "keys": forbidden,
                    },
                    status_code=400,
                )

            # Normalisation type_contrat
            if "type_contrat" in body:
                v = str(body.get("type_contrat") or "").strip().lower()
                if v in ("hp-hc", "heurescreuses", "heures_creuses"):
                    body["type_contrat"] = "heures_creuses"
                elif v in ("fixe", "prixunique", "prix_unique"):
                    body["type_contrat"] = "prix_unique"

            # Normalisation booleans
            if "use_external" in body:
                body["use_external"] = bool(body.get("use_external"))
            if "enable_cost_sensors_runtime" in body:
                body["enable_cost_sensors_runtime"] = bool(body.get("enable_cost_sensors_runtime"))

            # Écriture options
            current_opts.update(body)
            self.hass.config_entries.async_update_entry(entry, options=current_opts)

            # Reco 1: mettre à jour la config runtime "effective" si elle existe déjà
            # (car chez toi elle est normalement recalculée au setup/reload). [file:57]
            try:
                domain_data = self.hass.data.get(DOMAIN)
                if isinstance(domain_data, dict):
                    effective = dict(entry.data or {})
                    effective.update(current_opts)
                    domain_data["effective_options"] = effective
            except Exception:  # volontairement silencieux pour éviter toute régression
                pass

            # Reco 2: reload async (non bloquant) pour réaligner tout ce qui dépend du setup/reload. [file:57]
            self.hass.async_create_task(self.hass.config_entries.async_reload(entry.entry_id))

            return self.json({"success": True})

        except Exception as e:
            _LOGGER.exception("Erreur save_user_options: %s", e)
            return self.json({"success": False})

class GetSummaryView(HomeAssistantView):
    url = "/api/home_suivi_elec/get_summary"
    name = "api:home_suivi_elec:get_summary"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        """✅ PHASE 2.7: Charge sélection via StorageManager."""
        try:
            loop = asyncio.get_running_loop()

            power = await loop.run_in_executor(
                None, lambda: _load_json(CAPTEURS_POWER_PATH)
            ) if os.path.exists(CAPTEURS_POWER_PATH) else []

            # ✅ Charger sélection via StorageManager
            storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")
            if storage_manager:
                selection = await storage_manager.get_capteurs_selection()
            else:
                selection = await loop.run_in_executor(
                    None, lambda: _load_json(CAPTEURS_SELECTION_PATH)
                ) if os.path.exists(CAPTEURS_SELECTION_PATH) else {}

            total = len(power or [])

            enabled_ids: Set[str] = set()
            for integ, lst in (selection or {}).items():
                for row in lst or []:
                    if row.get("enabled") and row.get("entity_id"):
                        enabled_ids.add(row["entity_id"])

            actifs = len(enabled_ids)

            by_sig: Dict[str, int] = {}
            for cap in power or []:
                sig = _compute_signature(cap)
                by_sig[sig] = by_sig.get(sig, 0) + 1

            duplicates = sum(1 for v in by_sig.values() if v > 1)

            return self.json({
                "total_capteurs": total,
                "actifs": actifs,
                "doublons_detectes": duplicates
            })

        except Exception as e:
            _LOGGER.exception("Erreur get_summary: %s", e)
            return self.json({})

class GetSyncStatusView(HomeAssistantView):
    """GET /api/home_suivi_elec/sync/status - Statut de la synchronisation."""
    url = "/api/home_suivi_elec/sync/status"
    name = "api:home_suivi_elec:sync:status"
    requires_auth = False

    def __init__(self, hass: HomeAssistant, sync_manager) -> None:
        self.hass = hass
        self.sync_manager = sync_manager

    async def get(self, request):
        try:
            status = self.sync_manager.get_status()
            return self.json(status)
        except Exception as e:
            _LOGGER.exception("Erreur get_sync_status: %s", e)
            return self.json({"error": str(e)}, status_code=500)

class ForceSyncView(HomeAssistantView):
    """POST /api/home_suivi_elec/sync/force - Force une synchronisation."""
    url = "/api/home_suivi_elec/sync/force"
    name = "api:home_suivi_elec:sync:force"
    requires_auth = False

    def __init__(self, hass: HomeAssistant, sync_manager) -> None:
        self.hass = hass
        self.sync_manager = sync_manager

    async def post(self, request):
        try:
            await self.sync_manager.force_sync()
            return self.json({"success": True})
        except Exception as e:
            _LOGGER.exception("Erreur force_sync: %s", e)
            return self.json({"success": False, "error": str(e)}, status_code=500)

class AutoSelectBestSensorsView(HomeAssistantView):
    """API pour sélectionner automatiquement les meilleurs capteurs."""
    url = "/api/home_suivi_elec/auto_select_best_sensors"
    name = "api:home_suivi_elec:auto_select_best_sensors"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request):
        """Sélection automatique intelligente (capteurs physiques uniquement)."""
        try:
            from .sensor_quality_scorer import (
                auto_select_best_sensors,
                enrich_sensors_with_quality,
                is_physical_sensor
            )

            loop = asyncio.get_running_loop()
            detected = []
            if os.path.exists(CAPTEURS_POWER_PATH):
                detected = await loop.run_in_executor(None, lambda: _load_json(CAPTEURS_POWER_PATH))

            _LOGGER.info(f"[AUTO_SELECT] Total capteurs chargés : {len(detected)}")

            detected = _enrich_device_info(self.hass, detected or [])
            physical_only = [s for s in detected if is_physical_sensor(s)]
            helpers_count = len(detected) - len(physical_only)

            _LOGGER.info(
                f"[AUTO_SELECT] Physiques : {len(physical_only)} | "
                f"Helpers exclus : {helpers_count}"
            )

            physical_only = enrich_sensors_with_quality(physical_only)
            selected = auto_select_best_sensors(physical_only)

            selection_by_integration = {}
            for sensor in selected:
                integration = sensor.get("integration", "unknown")
                if integration not in selection_by_integration:
                    selection_by_integration[integration] = []
                selection_by_integration[integration].append({
                    "entity_id": sensor["entity_id"],
                    "enabled": True,
                    "auto_selected": True,
                    "quality_score": sensor["quality_score"]
                })

            # ✅ PHASE 2.7: Sauvegarder via StorageManager
            storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")
            if storage_manager:
                await storage_manager.save_capteurs_selection(selection_by_integration)
            else:
                _save_json(CAPTEURS_SELECTION_PATH, selection_by_integration)

            _LOGGER.info(
                f"[AUTO_SELECT] ✅ {len(selected)} capteurs physiques sélectionnés "
                f"({helpers_count} helpers exclus)"
            )

            return self.json({
                "success": True,
                "selected_count": len(selected),
                "physical_sensors": len(physical_only),
                "helpers_excluded": helpers_count,
                "selection": selection_by_integration,
                "message": (
                    f"{len(selected)} meilleurs capteurs physiques sélectionnés. "
                    f"{helpers_count} helpers exclus."
                )
            })

        except Exception as e:
            _LOGGER.exception("Erreur auto_select_best_sensors: %s", e)
            return self.json({"success": False, "error": str(e)}, status_code=500)

class GetSensorQualityScoresView(HomeAssistantView):
    """API pour obtenir les scores de qualité de tous les capteurs."""
    url = "/api/home_suivi_elec/get_sensor_quality_scores"
    name = "api:home_suivi_elec:get_sensor_quality_scores"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        """Retourne les capteurs avec leurs scores (physiques et helpers séparés)."""
        try:
            from .sensor_quality_scorer import enrich_sensors_with_quality

            loop = asyncio.get_running_loop()
            detected = []
            if os.path.exists(CAPTEURS_POWER_PATH):
                detected = await loop.run_in_executor(None, lambda: _load_json(CAPTEURS_POWER_PATH))

            detected = _enrich_device_info(self.hass, detected or [])
            detected = enrich_sensors_with_quality(detected)

            physical = [s for s in detected if not s.get("is_helper")]
            helpers = [s for s in detected if s.get("is_helper")]

            by_device = {}
            for sensor in physical:
                device_id = sensor.get("device_id", "no_device")
                if device_id not in by_device:
                    by_device[device_id] = []
                by_device[device_id].append(sensor)

            _LOGGER.debug(
                f"[QUALITY_SCORES] Total : {len(detected)} | "
                f"Physiques : {len(physical)} | Helpers : {len(helpers)}"
            )

            return self.json({
                "success": True,
                "total": len(detected),
                "physical_count": len(physical),
                "helpers_count": len(helpers),
                "sensors": detected,
                "physical": physical,
                "helpers": helpers,
                "by_device": by_device
            })

        except Exception as e:
            _LOGGER.exception("Erreur get_sensor_quality_scores: %s", e)
            return self.json({"success": False, "error": str(e)}, status_code=500)

class HSESensorsPublicView(HomeAssistantView):
    """GET /api/home_suivi_elec/lovelace_sensors - Liste tous les sensors HSE exposés."""
    url = "/api/home_suivi_elec/lovelace_sensors"
    name = "api:home_suivi_elec:lovelace_sensors"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        try:
            sensors = []
            for state in self.hass.states.async_all():
                if state.entity_id.startswith("sensor.hse_"):
                    sensors.append({
                        "entity_id": state.entity_id,
                        "state": state.state,
                        "attributes": dict(state.attributes)
                    })
            return self.json(sensors)
        except Exception as e:
            _LOGGER.error(f"Erreur HSESensorsPublicView: {e}")
            return self.json([])

class GetHistoryCostsView(HomeAssistantView):
    url = "/api/home_suivi_elec/history_costs"
    name = "api:home_suivi_elec:history_costs"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request):
        try:
            from .history_analytics import (
                fetch_statistics_hourly_sum,
                compute_hourly_deltas_kwh,
                compute_costs_per_hour,
                aggregate_period,
                normalize_comparison,
                compute_top_entities,
            )
            from .calculation_engine import PricingProfile

            body = await request.json()
            if not isinstance(body, dict):
                return self.json({"success": False, "error": "Payload must be a JSON object"}, status_code=400)

            selection_scope = body.get("selection_scope", "summary_selected")
            focus_entity_id = body.get("focus_entity_id")
            group_by = body.get("group_by", "hour")
            week_anchor_day = body.get("week_anchor_day", "monday")
            comparison_periods = body.get("comparison_periods") or {}
            top_limit = int(body.get("top_limit", 10) or 10)
            top_sort_by = body.get("top_sort_by", "cost_ttc") or "cost_ttc"

            baseline_cfg = (comparison_periods.get("baseline") or {})
            event_cfg = (comparison_periods.get("event") or {})

            try:
                baseline_start = _parse_datetime_flexible(baseline_cfg.get("start"))
                baseline_end = _parse_datetime_flexible(baseline_cfg.get("end"))
                event_start = _parse_datetime_flexible(event_cfg.get("start"))
                event_end = _parse_datetime_flexible(event_cfg.get("end"))
            except Exception as e:
                _LOGGER.error(f"Parse datetime error: {e}")
                return self.json({"success": False, "error": "Invalid datetime in comparison_periods"}, status_code=400)

            if not all([baseline_start, baseline_end, event_start, event_end]):
                return self.json({"success": False, "error": "Missing start/end in comparison_periods"}, status_code=400)


            baseline_duration_s = (baseline_end - baseline_start).total_seconds()
            event_duration_s = (event_end - event_start).total_seconds()

            normalized_supported = (baseline_duration_s >= 3600 and event_duration_s >= 3600)

            # 1) Déterminer la liste entity_ids
            entity_ids: List[str] = []

            if selection_scope == "summary_selected":
                storage_manager = self.hass.data.get(DOMAIN, {}).get("storage_manager")
                if storage_manager:
                    selection = await storage_manager.get_capteurs_selection()
                else:
                    loop = asyncio.get_running_loop()
                    selection = await loop.run_in_executor(
                        None, lambda: _load_json(CAPTEURS_SELECTION_PATH)
                    ) if os.path.exists(CAPTEURS_SELECTION_PATH) else {}

                for _, lst in (selection or {}).items():
                    for row in (lst or []):
                        if not row.get("enabled"):
                            continue
                        # si include_in_summary existe, on le respecte
                        if "include_in_summary" in row and not row.get("include_in_summary"):
                            continue

                        # priorité à usage_energy si présent (format normalisé)
                        if row.get("usage_energy"):
                            entity_ids.append(row["usage_energy"])
                        elif row.get("entity_id"):
                            entity_ids.append(row["entity_id"])

            elif isinstance(selection_scope, list):
                entity_ids = [str(x) for x in selection_scope if x]
            else:
                return self.json({"success": False, "error": "Invalid selection_scope"}, status_code=400)

            # dédoublonnage + limite
            entity_ids = sorted(set(entity_ids))
            if not entity_ids:
                return self.json({"success": False, "error": "No entities selected"}, status_code=400)
            if len(entity_ids) > 50:
                return self.json({"success": False, "error": "Too many entities (max 50)"}, status_code=400)

            # 2) Construire pricing_profile depuis entry options/data (comme GetUserOptionsView)
            entries = self.hass.config_entries.async_entries(DOMAIN)
            if not entries:
                return self.json({"success": False, "error": "No config entry found"}, status_code=500)
            entry: ConfigEntry = entries[0]
            data = dict(entry.data or {})
            opts = dict(entry.options or {})
            eff = {**data, **opts}

            type_contrat = str(eff.get("type_contrat") or "prix_unique").strip().lower()
            if type_contrat in ("hp-hc", "heurescreuses", "heures_creuses"):
                type_contrat = "heures_creuses"
            if type_contrat in ("fixe", "prixunique", "prix_unique"):
                type_contrat = "prix_unique"

            prix_ht = float(eff.get(CONF_PRIX_HT, eff.get("prix_ht", 0)) or 0)
            prix_ttc = float(eff.get(CONF_PRIX_TTC, eff.get("prix_ttc", 0)) or 0)
            abonnement_ht = float(eff.get(CONF_ABONNEMENT_MENSUEL_HT, eff.get("abonnement_ht", 0)) or 0)
            abonnement_ttc = float(eff.get(CONF_ABONNEMENT_MENSUEL_TTC, eff.get("abonnement_ttc", 0)) or 0)

            prix_ht_hp = float(eff.get(CONF_PRIX_HT_HP, eff.get("prix_ht_hp", prix_ht)) or prix_ht)
            prix_ttc_hp = float(eff.get(CONF_PRIX_TTC_HP, eff.get("prix_ttc_hp", prix_ttc)) or prix_ttc)
            prix_ht_hc = float(eff.get(CONF_PRIX_HT_HC, eff.get("prix_ht_hc", prix_ht)) or prix_ht)
            prix_ttc_hc = float(eff.get(CONF_PRIX_TTC_HC, eff.get("prix_ttc_hc", prix_ttc)) or prix_ttc)

            hc_start = str(eff.get(CONF_HC_START, eff.get("hc_start", "22:00")) or "22:00")
            hc_end = str(eff.get(CONF_HC_END, eff.get("hc_end", "06:00")) or "06:00")

            # PricingProfile utilise hp.debut/hp.fin => HP = (HC_END -> HC_START)
            pricing_config = {
                "type_contrat": type_contrat,
                "prix_ht": prix_ht,
                "prix_ttc": prix_ttc,
                "abonnement_ht": abonnement_ht,
                "abonnement_ttc": abonnement_ttc,
                "hp": {
                    "prix_ht": prix_ht_hp,
                    "prix_ttc": prix_ttc_hp,
                    "debut": hc_end,
                    "fin": hc_start,
                },
                "hc": {
                    "prix_ht": prix_ht_hc,
                    "prix_ttc": prix_ttc_hc,
                },
            }
            pricing_profile = PricingProfile(pricing_config)

            # 3) Charger stats sur la fenêtre globale
            all_start = min(baseline_start, event_start)
            all_end = max(baseline_end, event_end)

            stats_by_entity = await fetch_statistics_hourly_sum(self.hass, entity_ids, all_start, all_end)
            if not stats_by_entity:
                return self.json({"success": False, "error": "No statistics returned"}, status_code=500)

            entity_comparisons = []

            for entity_id in entity_ids:
                rows = stats_by_entity.get(entity_id) or []
                deltas = compute_hourly_deltas_kwh(rows)
                hourly_costs = compute_costs_per_hour(deltas, pricing_profile)

                baseline_agg = aggregate_period(hourly_costs, baseline_start, baseline_end)
                event_agg = aggregate_period(hourly_costs, event_start, event_end)

                comp = normalize_comparison(baseline_agg, event_agg, baseline_duration_s, event_duration_s)

                st = self.hass.states.get(entity_id)
                display_name = st.attributes.get("friendly_name") if st else entity_id

                entity_comparisons.append(
                    {
                        "entity_id": entity_id,
                        "display_name": display_name,
                        **comp,
                    }
                )

            total_baseline = {
                "energy_kwh": round(sum(x["baseline_energy_kwh"] for x in entity_comparisons), 3),
                "cost_ht": round(sum(x["baseline_cost_ht"] for x in entity_comparisons), 4),
                "cost_ttc": round(sum(x["baseline_cost_ttc"] for x in entity_comparisons), 4),
            }
            total_event = {
                "energy_kwh": round(sum(x["event_energy_kwh"] for x in entity_comparisons), 3),
                "cost_ht": round(sum(x["event_cost_ht"] for x in entity_comparisons), 4),
                "cost_ttc": round(sum(x["event_cost_ttc"] for x in entity_comparisons), 4),
            }
            total_comp = normalize_comparison(total_baseline, total_event, baseline_duration_s, event_duration_s)

            top_entities = compute_top_entities(entity_comparisons, top_sort_by, top_limit)

            focus_data = None
            if focus_entity_id:
                for x in entity_comparisons:
                    if x["entity_id"] == focus_entity_id:
                        focus_data = x
                        break

            max_delta_entity = max(entity_comparisons, key=lambda x: abs(float(x.get("delta_cost_ttc") or 0.0)), default=None)

            return self.json(
                {
                    "success": True,
                    "data": {
                        "meta": {
                            "group_by": group_by,
                            "week_anchor_day": week_anchor_day,
                            "entity_count": len(entity_ids),
                            "baseline_duration_s": baseline_duration_s,
                            "event_duration_s": event_duration_s,
                            "normalized_supported": normalized_supported,
                        },
                        "comparison": {
                            "total": total_comp,
                            "focus_entity": focus_data,
                            "extremes": {
                                "max_delta_entity": (
                                    {
                                        "entity_id": max_delta_entity["entity_id"],
                                        "display_name": max_delta_entity["display_name"],
                                        "delta_cost_ttc": max_delta_entity["delta_cost_ttc"],
                                        "delta_cost_ttc_per_hour": max_delta_entity["delta_cost_ttc_per_hour"],
                                        "delta_cost_ttc_per_day": max_delta_entity["delta_cost_ttc_per_day"],
                                    }
                                    if max_delta_entity
                                    else None
                                )
                            },
                        },
                        "top_entities": {
                            "by_cost_ttc": top_entities,
                        },
                    },
                }
            )

        except Exception as e:
            _LOGGER.exception("Erreur history_costs: %s", e)
            return self.json({"success": False, "error": str(e)}, status_code=500)
