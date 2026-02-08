"""Extensions API Unifiée - Méthodes POST/GET pour configuration"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Optional, Set

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from ..cache_manager import get_cache_manager
from ..const import DOMAIN
from ..export import ExportService
from ..sensor_grouping import build_auto_groups, merge_with_existing
from ..storage_manager import StorageManager
from ..utils.json_response import json_response

try:
    from ..group_totals import refresh_group_totals, refresh_group_totals_scope  # type: ignore
except Exception:
    refresh_group_totals = None  # type: ignore
    refresh_group_totals_scope = None  # type: ignore

try:
    # Nom "propre" (présent dans ton projet)
    from ..cost_tracking import create_cost_sensors  # type: ignore
except Exception:
    try:
        # Variante historique possible
        from ..cost_tracking import createcostsensors as create_cost_sensors  # type: ignore
    except Exception:
        # Fallback legacy
        from ..costtracking import createcostsensors as create_cost_sensors  # type: ignore


_LOGGER = logging.getLogger(__name__)

# Fonction helper globale pour serializer JSON
def _json_default(obj):
    """Serializer JSON custom pour datetime/date"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

class HomeElecUnifiedConfigAPIView(HomeAssistantView):
    """API Configuration - Méthodes POST/GET pour gestion config"""

    url = "/api/home_suivi_elec/config/{action}"
    name = "api:home_suivi_elec:config"
    requires_auth = False
    cors_allowed = True

    _GET_ALIASES = {
        "costsensorsstatus": "cost_sensors_status",
        "cost_sensors_status": "cost_sensors_status",
        "exportcostyaml": "export_cost_yaml",
        "export_cost_yaml": "export_cost_yaml",
    }

    _POST_ALIASES = {
        "saveselection": "save_selection",
        "updateoptions": "update_options",
        "togglesensor": "toggle_sensor",
        "resetconfig": "reset_config",
        "autogroup": "auto_group",
        "savegroups": "save_groups",
        "savegroupsets": "save_group_sets",
        "refreshgrouptotals": "refresh_group_totals",
        "refresh_group_totals": "refresh_group_totals",
        "generatecostsensors": "generate_cost_sensors",
        "generate_cost_sensors": "generate_cost_sensors",
        "calculatesummary": "calculate_summary",
        "calculate_summary": "calculate_summary",
        "set_cost_ha": "set_cost_ha",
        "setcostha": "set_cost_ha",
    }

    # ✅ AJOUT : Méthode pour activer un capteur
    async def _enable_sensor(self, data):
        """Active un capteur désactivé dans l'entity_registry."""
        try:
            entity_id = (data or {}).get("entity_id")
            
            if not entity_id:
                return self._error(400, "entity_id required")
            
            from homeassistant.helpers import entity_registry as er
            
            entity_reg = er.async_get(self.hass)
            entry = entity_reg.async_get(entity_id)
            
            if not entry:
                return self._error(404, f"Entity {entity_id} not found in registry")
            
            if not entry.disabled:
                return self._error(400, f"Entity {entity_id} is already enabled")
            
            # Activer l'entité
            entity_reg.async_update_entity(entity_id, disabled_by=None)
            
            _LOGGER.info(f"✅ Entity {entity_id} enabled by user via HSE")
            
            return self._success({
                "message": f"Entity {entity_id} enabled successfully. A restart or reload may be required.",
                "entity_id": entity_id,
                "was_disabled_by": str(entry.disabled_by),
            })
            
        except Exception as e:
            _LOGGER.exception("Erreur _enable_sensor: %s", e)
            return self._error(500, f"Erreur activation capteur: {e}")

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.export_service = ExportService(hass)
        _LOGGER.info("API Configuration initialisée")

    # -------------------------
    # Helpers réponse / storage
    # -------------------------

    def _success(self, data: Any, status: int = 200) -> web.Response:
        return web.Response(
            text=json.dumps({"error": False, "data": data}, default=_json_default),
            content_type="application/json",
            status=status
        )

    def _error(self, status: int, message: str) -> web.Response:
        return web.Response(
            text=json.dumps({"success": False, "error": message}, default=_json_default),
            content_type="application/json",
            status=status
        )


    async def _get_storage_manager(self) -> StorageManager:
        data = self.hass.data.get(DOMAIN, {})
        mgr = data.get("storage_manager")
        if isinstance(mgr, StorageManager):
            return mgr
        return StorageManager(self.hass)

    def _get_timestamp(self) -> str:
        return datetime.now().isoformat()

    # -------------
    # Router GET/POST
    # -------------

    async def post(self, request, action=None):
        """POST /api/home_suivi_elec/config/{action} - Actions de configuration"""
        try:
            if action is None:
                action = request.match_info.get("action", "unknown")
            action = self._POST_ALIASES.get(action, action)

            _LOGGER.info("API Config POST: /%s", action)

            try:
                data = await request.json()
            except Exception as e:
                return self._error(400, f"JSON invalide: {e}")

            if action == "save_selection":
                return await self._save_sensor_selection(data)

            if action == "update_options":
                return await self._update_integration_options(data)

            if action == "toggle_sensor":
                return await self._toggle_sensor_state(data)

            if action == "reset_config":
                return await self._reset_configuration(data)

            if action == "auto_group":
                return await self._auto_group_sensors(data)

            if action == "save_groups":
                return await self._save_sensor_groups(data)

            if action == "generate_cost_sensors":
                return await self._generate_cost_sensors(data)

            if action == "calculate_summary":
                return await self._calculate_summary_metrics(data)

            if action == "enable_sensor":
                return await self._enable_sensor(data)

            if action == "save_group_sets":
                return await self._save_group_sets(data)

            if action == "refresh_group_totals":
                return await self._refresh_group_totals(data)

            return self._error(404, f"Action POST inconnue: {action}")

        except Exception as e:
            _LOGGER.exception("Erreur API Config POST: %s", e)
            return self._error(500, str(e))

    async def get(self, request, action=None):
        """GET /api/home_suivi_elec/config/{action} - Lecture / status"""
        try:
            if action is None:
                action = request.match_info.get("action", "unknown")

            action = self._GET_ALIASES.get(action, action)
            _LOGGER.info("API Config GET: /%s", action)

            if action == "cost_sensors_status":
                return await self.get_cost_sensors_status()

            if action == "export_cost_yaml":
                return await self._export_cost_sensors_yaml()

            return self._error(404, f"Action GET inconnue: {action}")

        except Exception as e:
            _LOGGER.exception("Erreur API Config GET: %s", e)
            return self._error(500, str(e))

    # -------------------------
    # Actions config (selection)
    # -------------------------

    async def _save_sensor_selection(self, data):
        """Sauvegarde la sélection de capteurs (fichier legacy)."""
        try:
            selection = (data or {}).get("selection", {})
            if not isinstance(selection, dict):
                return self._error(400, "'selection' doit être un objet")

            valid_categories = ["salle_de_bain", "cuisine", "chauffage", "general"]
            for category, sensors in selection.items():
                if category not in valid_categories:
                    _LOGGER.warning("Catégorie inconnue: %s", category)

                if not isinstance(sensors, list):
                    return self._error(400, f"Catégorie '{category}' doit être une liste")

                for sensor in sensors:
                    if not isinstance(sensor, dict) or "entity_id" not in sensor:
                        return self._error(400, "Chaque capteur doit avoir un 'entity_id'")

            selection_file = self._get_selection_file_path()
            await self._save_json_file(selection_file, selection)

            return self._success(
                {
                    "message": "Sélection sauvegardée avec succès",
                    "categories_saved": len(selection),
                    "total_sensors": sum(len(sensors) for sensors in selection.values()),
                }
            )

        except Exception as e:
            _LOGGER.exception("Erreur save_sensor_selection: %s", e)
            return self._error(500, f"Erreur sauvegarde: {e}")

    async def _update_integration_options(self, data):
        """Met à jour les options de l'intégration (runtime hass.data uniquement)."""
        try:
            options = (data or {}).get("options", {})
            if not isinstance(options, dict):
                return self._error(400, "'options' doit être un objet")

            valid_options = [
                "auto_generate",
                "tariff_type",
                "contract_type",
                "hp_hc_enabled",
                "subscription_cost",
                "external_sensor",
            ]

            filtered_options = {}
            for key, value in options.items():
                if key in valid_options:
                    filtered_options[key] = value
                else:
                    _LOGGER.warning("Option inconnue ignorée: %s", key)

            if DOMAIN in self.hass.data:
                current_options = self.hass.data[DOMAIN].get("options", {})
                current_options.update(filtered_options)
                self.hass.data[DOMAIN]["options"] = current_options

            return self._success(
                {"message": "Options mises à jour avec succès", "updated_options": filtered_options}
            )

        except Exception as e:
            _LOGGER.exception("Erreur update_integration_options: %s", e)
            return self._error(500, f"Erreur mise à jour options: {e}")

    async def _toggle_sensor_state(self, data):
        """Active/désactive un capteur spécifique dans capteurs_selection.json."""
        try:
            entity_id = (data or {}).get("entity_id")
            enabled = (data or {}).get("enabled", None)

            if not entity_id:
                return self._error(400, "'entity_id' requis")
            if enabled is None:
                return self._error(400, "'enabled' requis (true/false)")

            enabled = bool(enabled)

            selection_file = self._get_selection_file_path()
            selection = await self._load_json_file(selection_file)

            sensor_found = False
            for _category, sensors in (selection or {}).items():
                if not isinstance(sensors, list):
                    continue
                for sensor in sensors:
                    if sensor.get("entity_id") == entity_id:
                        sensor["enabled"] = enabled
                        sensor_found = True
                        break
                if sensor_found:
                    break

            if not sensor_found:
                return self._error(404, f"Capteur {entity_id} introuvable")

            await self._save_json_file(selection_file, selection)

            return self._success(
                {
                    "message": f"Capteur {'activé' if enabled else 'désactivé'} avec succès",
                    "entity_id": entity_id,
                    "enabled": enabled,
                }
            )

        except Exception as e:
            _LOGGER.exception("Erreur toggle_sensor_state: %s", e)
            return self._error(500, f"Erreur toggle capteur: {e}")

    async def _reset_configuration(self, data):
        """Réinitialise la configuration (selon type)."""
        try:
            reset_type = (data or {}).get("type", "selection")

            if reset_type == "selection":
                selection_file = self._get_selection_file_path()
                empty_selection = {
                    "salle_de_bain": [],
                    "cuisine": [],
                    "chauffage": [],
                    "general": [],
                }
                await self._save_json_file(selection_file, empty_selection)
                message = "Sélection réinitialisée"

            elif reset_type == "options":
                if DOMAIN in self.hass.data:
                    self.hass.data[DOMAIN]["options"] = {
                        "auto_generate": True,
                        "tariff_type": "base",
                        "contract_type": "particulier",
                    }
                message = "Options réinitialisées"

            else:
                return self._error(400, f"Type de reset inconnu: {reset_type}")

            return self._success({"message": message, "reset_type": reset_type})

        except Exception as e:
            _LOGGER.exception("Erreur reset_configuration: %s", e)
            return self._error(500, f"Erreur reset: {e}")

    # ... (file continues unchanged below)

    async def _save_group_sets(self, data):
        """Sauvegarde du document canon group_sets (rooms/types/...)."""
        try:
            mgr = await self._get_storage_manager()
            group_sets = (data or {}).get("group_sets")

            if not isinstance(group_sets, dict):
                return self._error(400, "'group_sets' doit être un objet")

            ok = await mgr.save_group_sets(group_sets)
            if not ok:
                return self._error(500, "Erreur sauvegarde group_sets")

            sets = group_sets.get("sets")
            count_sets = len(sets) if isinstance(sets, dict) else 0

            # NOTE: storage-only. Recompute totals is triggered explicitly from frontend.

            return self._success({
                "message": "Group sets sauvegardés avec succès",
                "count_sets": count_sets,
            })

        except Exception as e:
            _LOGGER.exception("[CONFIG] Erreur save_group_sets: %s", e)
            return self._error(500, f"Erreur save_group_sets: {e}")

    async def _refresh_group_totals(self, data):
        """Recalcule les totaux groupés (rooms/types) sur demande explicite."""
        try:
            scope = (data or {}).get("scope")
            scope = str(scope or "").strip().lower()

            if refresh_group_totals is None:
                return self._error(500, "refresh_group_totals indisponible")

            if scope in ("rooms", "types") and refresh_group_totals_scope is not None:
                await refresh_group_totals_scope(self.hass, scope)
            else:
                # fallback: full recompute
                await refresh_group_totals(self.hass)

            return self._success({
                "message": "Recalcul lancé",
                "scope": scope or "all",
                "timestamp": self._get_timestamp(),
            })

        except Exception as e:
            _LOGGER.exception("[CONFIG] refresh_group_totals failed: %s", e)
            return self._error(500, f"Erreur refresh_group_totals: {e}")
