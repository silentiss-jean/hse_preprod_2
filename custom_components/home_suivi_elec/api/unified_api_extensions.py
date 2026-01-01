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
from datetime import datetime, date

from ..cache_manager import get_cache_manager
from ..const import DOMAIN
from ..export import ExportService
from ..sensor_grouping import build_auto_groups, merge_with_existing
from ..storage_manager import StorageManager
from ..utils.json_response import json_response

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

    # -------------------------
    # Coût : status / génération
    # -------------------------

    async def get_cost_sensors_status(self):
        """
        GET /api/home_suivi_elec/config/cost_sensors_status
        Retourne le statut des sensors coût existants.
        """
        try:
            mgr = await self._get_storage_manager()
            user_cfg = await mgr.get_user_config()
            runtime_enabled = bool(user_cfg.get("enable_cost_sensors_runtime", False))

            from homeassistant.helpers import entity_registry as er

            entity_reg = er.async_get(self.hass)

            cost_sensors = []
            for entity_id, entry in entity_reg.entities.items():
                if entry.platform == DOMAIN and (
                    "cout" in entity_id.lower() or "cost" in entity_id.lower()
                ):
                    state = self.hass.states.get(entity_id)
                    cost_sensors.append(
                        {
                            "entity_id": entity_id,
                            "unique_id": entry.unique_id,
                            "state": state.state if state else "unknown",
                            "unit": (
                                state.attributes.get("unit_of_measurement") if state else None
                            ),
                        }
                    )

            return self._success(
                {"runtime_enabled": runtime_enabled, "count": len(cost_sensors), "sensors": cost_sensors}
            )

        except Exception as e:
            _LOGGER.exception("[API-CONFIG] Erreur get_cost_sensors_status: %s", e)
            return self._error(500, str(e))

    def _entity_unique_id(self, ent: Any) -> Optional[str]:
        return (
            getattr(ent, "unique_id", None)
            or getattr(ent, "_attr_unique_id", None)
            or getattr(ent, "attr_unique_id", None)
        )

    def _entity_source_energy(self, ent: Any) -> Optional[str]:
        # cost_tracking.HSECostSensor stocke la source dans _source_energy_entity + attrs compat [file:11]
        return (
            getattr(ent, "_source_energy_entity", None)
            or getattr(ent, "source_energy_entity", None)
            or getattr(ent, "source_entity", None)
            or getattr(ent, "sourceenergyentity", None)
            or getattr(ent, "sourceentity", None)
        )

    async def _generate_cost_sensors(self, data):
        _LOGGER.warning("HSE-TRACE: _generate_cost_sensors CALLED avec data=%s", data)
        """Crée les capteurs coût HSE et les ajoute via event-driven (sans reload)."""
        from homeassistant.helpers import entity_registry as er

        try:
            data = data or {}

            mgr = await self._get_storage_manager()
            user_cfg = await mgr.get_user_config()
            runtime_enabled = bool(user_cfg.get("enable_cost_sensors_runtime", False))

            if not runtime_enabled:
                return self._error(
                    400,
                    "Génération refusée: 'enable_cost_sensors_runtime' est désactivé.",
                )

            # Allowlist optionnelle depuis le store cost_ha (Coût: oui)
            cost_ha_map = await mgr.get_cost_ha_config()
            allowed_sources: Set[str] = {
                str(entity_id)
                for entity_id, cfg in (cost_ha_map or {}).items()
                if isinstance(cfg, dict) and bool(cfg.get("enabled", False))
            }
            use_allowlist = len(allowed_sources) > 0

            prix_ht = float(data.get("prix_ht", data.get("prixht", 0.0)) or 0.0)
            prix_ttc = float(data.get("prix_ttc", data.get("prixttc", 0.0)) or 0.0)

            _LOGGER.info(
                "[API-CONFIG] generate_cost_sensors HT=%.4f TTC=%.4f allowlist=%d (use=%s)",
                prix_ht,
                prix_ttc,
                len(allowed_sources),
                use_allowlist,
            )

            # create_cost_sensors : allowlist seulement si non vide
            cost_sensors = await create_cost_sensors(
                self.hass,
                prix_ht if prix_ht > 0 else None,
                prix_ttc if prix_ttc > 0 else None,
                allowed_source_entity_ids=allowed_sources if use_allowlist else None,
            )
            cost_sensors = [e for e in (cost_sensors or []) if e is not None]

            # Filet de sécurité: si allowlist active, on vérifie encore la source
            if use_allowlist:
                filtered = []
                for e in cost_sensors:
                    src = self._entity_source_energy(e)
                    if src and src in allowed_sources:
                        filtered.append(e)
                cost_sensors = filtered

            if not cost_sensors:
                return self._success(
                    {
                        "success": True,
                        "action": "generate_cost_sensors",
                        "runtime_enabled": True,
                        "added_now": 0,
                        "duplicates_skipped": 0,
                        "dropped_no_uid": 0,
                        "allowed_sources_count": len(allowed_sources),
                        "message": (
                            "Aucun capteur coût à créer ("
                            "allowlist vide => tous filtrés"
                            if use_allowlist
                            else "aucun sensor energy HSE trouvé"
                        ),
                        "prix_ht": prix_ht,
                        "prix_ttc": prix_ttc,
                    }
                )

            domain = self.hass.data.setdefault(DOMAIN, {})

            # Dédup robuste: mémoire runtime + entity_registry
            already: Set[str] = set(domain.get("_added_cost_uids", set()))
            entity_reg = er.async_get(self.hass)
            for entity_id, entry in entity_reg.entities.items():
                if entry.platform != DOMAIN:
                    continue
                if ("cout" in entity_id.lower()) or ("cost" in entity_id.lower()):
                    if entry.unique_id:
                        already.add(entry.unique_id)

            to_add = []
            dup = 0
            dropped_no_uid = 0

            for e in cost_sensors:
                uid = self._entity_unique_id(e)
                if not uid:
                    dropped_no_uid += 1
                    continue
                if uid in already:
                    dup += 1
                    continue
                to_add.append(e)
                already.add(uid)

            domain["_added_cost_uids"] = already

            if not to_add:
                return self._success(
                    {
                        "success": True,
                        "action": "generate_cost_sensors",
                        "runtime_enabled": True,
                        "added_now": 0,
                        "duplicates_skipped": dup,
                        "dropped_no_uid": dropped_no_uid,
                        "allowed_sources_count": len(allowed_sources),
                        "message": "Tous les capteurs coût générés étaient déjà présents (ou sans unique_id).",
                        "prix_ht": prix_ht,
                        "prix_ttc": prix_ttc,
                    }
                )

            # Mise à jour du store cost_ha pour chaque source réellement ajoutée
            cost_ha_map = cost_ha_map or {}
            for e in to_add:
                src = self._entity_source_energy(e)
                if not src:
                    continue
                entry = cost_ha_map.get(src)
                if not isinstance(entry, dict):
                    entry = {}
                entry["enabled"] = True
                entry["cost_entity_id"] = e.entity_id
                cost_ha_map[src] = entry

            await mgr.save_cost_ha_config(cost_ha_map)

            # sensor.py écoute hse_cost_sensors_ready et lit cost_sensors_pending
            domain["cost_sensors_pending"] = to_add
            domain["cost_sensors"] = to_add  # fallback

            payload = {
                "type": "cost",
                "count": len(to_add),
                "timestamp": self._get_timestamp(),
            }

            self.hass.bus.async_fire("hse_cost_sensors_ready", payload)
            self.hass.bus.async_fire("hsecostsensorsready", payload)

            return self._success(
                {
                    "success": True,
                    "action": "generate_cost_sensors",
                    "runtime_enabled": True,
                    "added_now": len(to_add),
                    "duplicates_skipped": dup,
                    "dropped_no_uid": dropped_no_uid,
                    "allowed_sources_count": len(allowed_sources),
                    "message": f"{len(to_add)} capteurs coût envoyés à l’ajout (event cost).",
                    "prix_ht": prix_ht,
                    "prix_ttc": prix_ttc,
                }
            )

        except Exception as e:
            _LOGGER.exception("[API-CONFIG] Erreur generate_cost_sensors: %s", e)
            return self._error(500, f"Erreur génération sensors coût: {e}")

    async def _export_cost_sensors_yaml(self):
        """
        GET /api/home_suivi_elec/config/export_cost_yaml
        Génère le YAML d'export des capteurs coût.
        """
        try:
            _LOGGER.info("[EXPORT] Génération YAML capteurs coût...")
            yaml_content = await self.export_service.generate_cost_sensors_yaml()

            if not yaml_content:
                return self._error(500, "Aucun contenu YAML généré")

            return web.Response(
                text=yaml_content,
                content_type="text/yaml; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="cost_sensors.yaml"'},
            )

        except Exception as e:
            _LOGGER.exception("[EXPORT] Erreur génération YAML: %s", e)
            return self._error(500, f"Erreur export YAML: {e}")

    # -------------------------
    # Groupes (auto + save)
    # -------------------------

    async def _auto_group_sensors(self, data):
        """
        Calcule automatiquement les groupes de capteurs (energy/power)
        et les fusionne avec la config existante (store sensor_groups).
        """
        try:
            mgr = await self._get_storage_manager()

            all_states = self.hass.states.async_all("sensor")
            sensors = []
            for state in all_states:
                attrs = state.attributes or {}
                device_class = attrs.get("device_class")
                if device_class not in ("energy", "power"):
                    continue

                sensors.append(
                    {
                        "entity_id": state.entity_id,
                        "device_class": device_class,
                        "integration": attrs.get("integration", "unknown"),
                        "area": attrs.get("area_id") or None,
                        "friendly_name": attrs.get("friendly_name", state.entity_id),
                    }
                )

            manual_keywords = (data or {}).get("keyword_mapping") or None
            if manual_keywords is not None and not isinstance(manual_keywords, dict):
                return self._error(400, "'keyword_mapping' doit être un objet")

            auto_groups = build_auto_groups(sensors, manual_keyword_mapping=manual_keywords)
            existing = await mgr.get_sensor_groups()
            merged = merge_with_existing(auto_groups, existing)

            ok = await mgr.save_sensor_groups(merged)
            if not ok:
                return self._error(500, "Impossible de sauvegarder sensor_groups")

            return self._success(
                {"message": "Groupes recalculés et sauvegardés", "groups": merged, "groups_count": len(merged)}
            )

        except Exception as e:
            _LOGGER.exception("[CONFIG] Erreur auto_group: %s", e)
            return self._error(500, f"Erreur auto_group: {e}")

    async def _save_sensor_groups(self, data):
        """Sauvegarde des groupes envoyés depuis le frontend (édition manuelle)."""
        try:
            mgr = await self._get_storage_manager()
            groups = (data or {}).get("groups")

            if not isinstance(groups, dict):
                return self._error(400, "'groups' doit être un objet {nom: config}")

            ok = await mgr.save_sensor_groups(groups)
            if not ok:
                return self._error(500, "Erreur sauvegarde sensor_groups")

            return self._success({"message": "Groupes sauvegardés avec succès", "groups_count": len(groups)})

        except Exception as e:
            _LOGGER.exception("[CONFIG] Erreur save_groups: %s", e)
            return self._error(500, f"Erreur save_groups: {e}")

    # -------------------------
    # Summary / CalculationEngine
    # -------------------------

    async def _calculate_summary_metrics(self, data):
        """
        POST /api/home_suivi_elec/config/calculate_summary
        Calcule les métriques agrégées pour Summary (interne/externe/delta).
        """
        try:
            _LOGGER.info("[CALCULATE-SUMMARY] Début calcul métriques")

            entity_ids = (data or {}).get("entity_ids", [])
            periods = (data or {}).get("periods", ["daily", "monthly"])
            pricing_config = (data or {}).get("pricing_config", {})
            external_id = (data or {}).get("external_id")

            if not isinstance(entity_ids, list) or len(entity_ids) == 0:
                return self._error(400, "'entity_ids' requis (liste non vide)")
            if not isinstance(periods, list) or len(periods) == 0:
                return self._error(400, "'periods' requis (liste non vide)")
            if not isinstance(pricing_config, dict):
                return self._error(400, "'pricing_config' requis (objet)")

            valid_periods = ["hourly", "daily", "weekly", "monthly", "yearly"]
            invalid_periods = [p for p in periods if p not in valid_periods]
            if invalid_periods:
                return self._error(
                    400,
                    f"Périodes invalides: {invalid_periods}. Valeurs autorisées: {valid_periods}",
                )

            from ..calculation_engine import CalculationEngine, PricingProfile

            engine = CalculationEngine(self.hass)
            profile = PricingProfile(pricing_config)

            results = {
                "internal": {},
                "external": {},
                "delta": {},
                "timestamp": self._get_timestamp(),
            }

            for period in periods:
                internal = await engine.get_group_metrics(
                    group_key="internal",
                    period=period,
                    pricing_profile=profile,
                    entity_ids=entity_ids,
                )
                results["internal"][period] = internal

                if external_id:
                    external = await engine.get_group_metrics(
                        group_key="external",
                        period=period,
                        pricing_profile=profile,
                        entity_ids=[external_id],
                    )
                    results["external"][period] = external

                    results["delta"][period] = {
                        "energy_kwh": round(external["energy_kwh"] - internal["energy_kwh"], 3),
                        "cost_ht": round(external["cost_ht"] - internal["cost_ht"], 2),
                        "cost_ttc": round(external["cost_ttc"] - internal["cost_ttc"], 2),
                        "total_ht": round(external["total_ht"] - internal["total_ht"], 2),
                        "total_ttc": round(external["total_ttc"] - internal["total_ttc"], 2),
                    }

            _LOGGER.info("[CALCULATE-SUMMARY] Terminé (%s périodes)", len(periods))
            return self._success(results)

        except Exception as e:
            _LOGGER.exception("[CALCULATE-SUMMARY] Erreur: %s", e)
            return self._error(500, f"Erreur calcul métriques: {e}")

    # -------------------------
    # Utils fichiers JSON (legacy)
    # -------------------------

    async def _load_json_file(self, file_path: str) -> Dict[str, Any]:
        def _load():
            if not os.path.exists(file_path):
                return {}
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                _LOGGER.error("Erreur lecture %s: %s", file_path, e)
                return {}

        return await asyncio.get_event_loop().run_in_executor(None, _load)

    async def _save_json_file(self, file_path: str, data: Any) -> None:
        def _save():
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        await asyncio.get_event_loop().run_in_executor(None, _save)

    def _get_selection_file_path(self) -> str:
        return os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "data", "capteurs_selection.json")
        )


class ValidationActionView(HomeAssistantView):
    """
    POST /api/home_suivi_elec/validation/action
    Actions de correction pour synchronisation
    """

    url = "/api/home_suivi_elec/validation/action"
    name = "api:home_suivi_elec:validation_action"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    async def post(self, request):
        try:
            data = await request.json()
            action = (data or {}).get("action")

            selection_file = Path(__file__).parent.parent / "data" / "capteurs_selection.json"
            power_file = Path(__file__).parent.parent / "data" / "capteurs_power.json"

            def _apply_action():
                with open(selection_file, "r", encoding="utf-8") as f:
                    selection_data = json.load(f)

                with open(power_file, "r", encoding="utf-8") as f:
                    power_data = json.load(f)

                power_ids = {
                    s.get("entity_id")
                    for s in (power_data or [])
                    if isinstance(s, dict) and s.get("entity_id")
                }

                result = {"success": True, "action": action, "changes": [], "errors": []}

                if action == "disable_orphans":
                    for _category, items in selection_data.items():
                        if not isinstance(items, list):
                            continue
                        for item in items:
                            if item.get("enabled") and item.get("entity_id") not in power_ids:
                                item["enabled"] = False
                                result["changes"].append(
                                    {"entity_id": item.get("entity_id"), "action": "disabled", "reason": "orphan"}
                                )
                    result["message"] = f"{len(result['changes'])} capteur(s) orphelin(s) désactivé(s)"

                elif action == "enable_available":
                    for _category, items in selection_data.items():
                        if not isinstance(items, list):
                            continue
                        for item in items:
                            if (not item.get("enabled")) and item.get("entity_id") in power_ids:
                                item["enabled"] = True
                                result["changes"].append(
                                    {"entity_id": item.get("entity_id"), "action": "enabled", "reason": "available"}
                                )
                    result["message"] = f"{len(result['changes'])} capteur(s) activé(s)"

                elif action == "full_sync":
                    for _category, items in selection_data.items():
                        if not isinstance(items, list):
                            continue
                        for item in items:
                            entity_id = item.get("entity_id")
                            should_be_enabled = entity_id in power_ids
                            if item.get("enabled", False) != should_be_enabled:
                                item["enabled"] = should_be_enabled
                                result["changes"].append(
                                    {
                                        "entity_id": entity_id,
                                        "action": "enabled" if should_be_enabled else "disabled",
                                        "reason": "sync",
                                    }
                                )
                    result["message"] = f"{len(result['changes'])} capteur(s) synchronisé(s)"

                elif action == "disable_specific":
                    entity_ids = (data or {}).get("entity_ids", [])
                    for _category, items in selection_data.items():
                        if not isinstance(items, list):
                            continue
                        for item in items:
                            if item.get("entity_id") in entity_ids and item.get("enabled"):
                                item["enabled"] = False
                                result["changes"].append(
                                    {"entity_id": item.get("entity_id"), "action": "disabled", "reason": "user_request"}
                                )
                    result["message"] = f"{len(result['changes'])} capteur(s) désactivé(s)"

                else:
                    result["success"] = False
                    result["error"] = f"Action inconnue: {action}"
                    return result

                with open(selection_file, "w", encoding="utf-8") as f:
                    json.dump(selection_data, f, indent=2, ensure_ascii=False)

                return result

            result = await asyncio.get_event_loop().run_in_executor(None, _apply_action)
            _LOGGER.info("[VALIDATION-ACTION] '%s': %s", action, result.get("message"))
            return web.Response(
        text=json.dumps({"error": False, "data": result}, default=_json_default),
        content_type="application/json"
    )

        except Exception as e:
            _LOGGER.exception("[VALIDATION-ACTION] POST error: %s", e)
            return web.Response(
        text=json.dumps({"error": True, "message": str(e)}, default=_json_default),
        content_type="application/json",
        status=500
    )


class HomeElecMigrationHelpersView(HomeAssistantView):
    """Endpoints POST pour création auto + validation des helpers utility_meter."""

    url = "/api/home_suivi_elec/migration/{action}"
    name = "api:home_suivi_elec:migration_helpers"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.export_service = ExportService(hass)
        _LOGGER.info("API Migration helpers initialisée")

    async def post(self, request, action=None):
        try:
            if action is None:
                action = request.match_info.get("action", "unknown")

            data = await request.json()
            _LOGGER.info("Migration POST /%s payload=%s", action, data)

            if action == "create_helpers":
                sensors = (data or {}).get("sensors") or []
                cycles = (data or {}).get("cycles") or []
                result = await self.export_service.create_helpers_auto(sensors, cycles)
                return json_response(result)

            if action == "validate":
                helpers = (data or {}).get("helpers") or []
                details = await self.export_service.validate_helpers(helpers)
                valid = all(details.values()) if details else False
                return web.Response(
        text=json.dumps({"valid": valid, "details": details}, default=_json_default),
        content_type="application/json"
    )

            return json_response({"success": False, "error": f"Action inconnue: {action}"}, status=404)

        except Exception as e:
            _LOGGER.exception("Erreur API Migration POST /%s: %s", action, e)
            return web.Response(
        text=json.dumps({"success": False, "error": str(e)}, default=_json_default),
        content_type="application/json",
        status=500
    )


class CacheClearView(HomeAssistantView):
    """Vue pour vider le cache"""

    url = "/api/home_suivi_elec/cache/clear"
    name = "api:home_suivi_elec:cache_clear"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    async def post(self, request):
        try:
            cache = get_cache_manager()
            count = cache.invalidate_all()

            _LOGGER.info("[cache] Vidé : %s entrées", count)

            return json_response(
                {"success": True, "message": f"Cache vidé ({count} entrées supprimées)", "cleared_entries": count}
            )

        except Exception as e:
            _LOGGER.exception("[cache_clear] Erreur: %s", e)
            return web.Response(
        text=json.dumps({"success": False, "error": str(e)}, default=_json_default),
        content_type="application/json",
        status=500
    )


class CacheInvalidateEntityView(HomeAssistantView):
    """Vue pour invalider un capteur spécifique"""

    url = "/api/home_suivi_elec/cache/invalidate"
    name = "api:home_suivi_elec:cache_invalidate"
    requires_auth = False  # demandé : conserver requires_auth=False partout
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request):
        try:
            data = await request.json()
            entity_id = (data or {}).get("entity_id")

            if not entity_id:
                return web.Response(
        text=json.dumps({"success": False, "error": "entity_id manquant"}, default=_json_default),
        content_type="application/json",
        status=400
    )

            cache = get_cache_manager()
            cleared = cache.invalidate_entity(entity_id)

            return web.Response(
        text=json.dumps({"success": True, "entity_id": entity_id, "cleared_entries": cleared}, default=_json_default),
        content_type="application/json"
    )

        except Exception as e:
            _LOGGER.exception("[cache_invalidate] Erreur: %s", e)
            return web.Response(
        text=json.dumps({"success": False, "error": str(e)}, default=_json_default),
        content_type="application/json",
        status=500
    )


class EnableSensorView(HomeAssistantView):
    """
    POST /api/home_suivi_elec/enable_sensor
    Active un capteur désactivé depuis le frontend.
    """
    
    url = "/api/home_suivi_elec/enable_sensor"
    name = "api:home_suivi_elec:enable_sensor"
    requires_auth = False
    cors_allowed = True
    
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
    
    async def post(self, request):
        """Active un capteur désactivé."""
        try:
            data = await request.json()
            entity_id = (data or {}).get("entity_id")
            
            if not entity_id:
                return web.Response(
        text=json.dumps({"success": False, "error": "entity_id required"}, default=_json_default),
        content_type="application/json",
        status=400
    )
            
            result = await enable_sensor_entity(self.hass, entity_id)
            
            if result["success"]:
                return web.Response(
        text=json.dumps({"error": False, "data": result}, default=_json_default),
        content_type="application/json"
    )
            else:
                return json_response(result, status=400)
                
        except Exception as e:
            _LOGGER.exception("[enable_sensor] Erreur: %s", e)
            return web.Response(
        text=json.dumps({"success": False, "error": str(e)}, default=_json_default),
        content_type="application/json",
        status=500
    )

class HistoryAnalysisView(HomeAssistantView):
    """
    GET+POST /api/home_suivi_elec/history/{action}
    Endpoints pour analyse de coûts historiques
    """
    
    url = "/api/home_suivi_elec/history/{action}"
    name = "api:home_suivi_elec:history"
    requires_auth = False
    cors_allowed = True
    
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        _LOGGER.info("🕒 API History Analysis initialisée")
    
    # === GET ===
    
    async def get(self, request, action=None):
        """GET /api/home_suivi_elec/history/{action}"""
        try:
            if action is None:
                action = request.match_info.get("action", "unknown")
            
            _LOGGER.info(f"[HISTORY-API] GET /{action}")
            
            if action == "available_sensors":
                return await self._get_available_sensors()
            
            if action == "test":
                return self._success({"message": "History API opérationnelle"})
            
            return self._error(404, f"Action GET inconnue: {action}")
            
        except Exception as e:
            _LOGGER.exception(f"[HISTORY-API] Erreur GET: {e}")
            return self._error(500, str(e))
    
    # === POST ===
    
    async def post(self, request, action=None):
        """POST /api/home_suivi_elec/history/{action}"""
        try:
            if action is None:
                action = request.match_info.get("action", "unknown")
            
            try:
                data = await request.json()
            except Exception as e:
                return self._error(400, f"JSON invalide: {e}")
            
            _LOGGER.info(f"[HISTORY-API] POST /{action}")
            
            if action == "costs":
                return await self._fetch_history_costs(data)
            
            if action == "analysis":
                return await self._analyze_comparison(data)
            
            return self._error(404, f"Action POST inconnue: {action}")
            
        except Exception as e:
            _LOGGER.exception(f"[HISTORY-API] Erreur POST: {e}")
            return self._error(500, str(e))
    
    # === MÉTHODES INTERNES ===
    
    async def _get_available_sensors(self):
        """Retourne les capteurs HSE energy disponibles pour l'analyse"""
        try:
            all_states = self.hass.states.async_all("sensor")
            cycles = ("_hourly", "_daily", "_weekly", "_monthly", "_yearly")
            
            sensors = []
            for state in all_states:
                entity_id = state.entity_id
                if entity_id.startswith("sensor.hse_") and entity_id.endswith(cycles):
                    attrs = state.attributes or {}
                    sensors.append({
                        "entity_id": entity_id,
                        "friendly_name": attrs.get("friendly_name", entity_id),
                        "cycle": attrs.get("cycle", "unknown"),
                        "source_entity": attrs.get("source_entity"),
                        "unit": attrs.get("unit_of_measurement", "kWh")
                    })
            
            _LOGGER.info(f"[HISTORY] {len(sensors)} capteurs disponibles")
            
            return self._success({
                "sensors": sensors,
                "count": len(sensors)
            })
            
        except Exception as e:
            _LOGGER.exception(f"[HISTORY] Erreur available_sensors: {e}")
            return self._error(500, str(e))
    
    async def _fetch_history_costs(self, data):
        """
        POST /api/home_suivi_elec/history/costs
        Récupère les coûts historiques pour deux périodes
        """
        try:
            baseline_start = data.get("baseline_start")
            baseline_end = data.get("baseline_end")
            event_start = data.get("event_start")
            event_end = data.get("event_end")
            focus_entity_id = data.get("focus_entity_id")
            group_by = data.get("group_by", "hour")
            
            _LOGGER.info(f"[HISTORY-COSTS] baseline: {baseline_start} → {baseline_end}")
            _LOGGER.info(f"[HISTORY-COSTS] event: {event_start} → {event_end}")
            
            # TODO: Implémenter récupération via recorder
            result = {
                "baseline": {
                    "start": baseline_start,
                    "end": baseline_end,
                    "total_kwh": 0.0,
                    "total_cost_ht": 0.0,
                    "total_cost_ttc": 0.0,
                    "sensors": []
                },
                "event": {
                    "start": event_start,
                    "end": event_end,
                    "total_kwh": 0.0,
                    "total_cost_ht": 0.0,
                    "total_cost_ttc": 0.0,
                    "sensors": []
                },
                "comparison": {
                    "delta_kwh": 0.0,
                    "delta_cost_ht": 0.0,
                    "delta_cost_ttc": 0.0,
                    "delta_percent": 0.0
                },
                "focus_entity": focus_entity_id,
                "group_by": group_by
            }
            
            return self._success(result)
            
        except Exception as e:
            _LOGGER.exception(f"[HISTORY-COSTS] Erreur: {e}")
            return self._error(500, str(e))
    
    async def _analyze_comparison(self, data):
        """
        POST /api/home_suivi_elec/history/analysis
        Analyse comparative détaillée entre deux périodes
        """
        try:
            baseline_start = data.get("baseline_start")
            baseline_end = data.get("baseline_end")
            event_start = data.get("event_start")
            event_end = data.get("event_end")
            focus_entity_id = data.get("focus_entity_id")
            group_by = data.get("group_by", "hour")
            top_limit = data.get("top_limit", 10)
            top_sort_by = data.get("top_sort_by", "cost_ttc")
            
            _LOGGER.info(f"[HISTORY-ANALYSIS] Analyse comparative demandée")
            _LOGGER.info(f"[HISTORY-ANALYSIS] top {top_limit} by {top_sort_by}")
            
            # TODO: Implémenter logique réelle
            result = {
                "baseline_period": {
                    "start": baseline_start,
                    "end": baseline_end,
                    "total_kwh": 0.0,
                    "total_cost_ht": 0.0,
                    "total_cost_ttc": 0.0,
                    "sensor_count": 0
                },
                "event_period": {
                    "start": event_start,
                    "end": event_end,
                    "total_kwh": 0.0,
                    "total_cost_ht": 0.0,
                    "total_cost_ttc": 0.0,
                    "sensor_count": 0
                },
                "comparison": {
                    "delta_kwh": 0.0,
                    "delta_cost_ht": 0.0,
                    "delta_cost_ttc": 0.0,
                    "delta_percent_kwh": 0.0,
                    "delta_percent_cost": 0.0,
                    "trend": "stable"
                },
                "by_sensor": [],
                "timeline": [],
                "focus_entity": focus_entity_id,
                "parameters": {
                    "group_by": group_by,
                    "top_limit": top_limit,
                    "top_sort_by": top_sort_by
                }
            }
            
            return self._success(result)
            
        except Exception as e:
            _LOGGER.exception(f"[HISTORY-ANALYSIS] Erreur: {e}")
            return self._error(500, str(e))
    
    # === HELPERS ===
    
    def _success(self, data: Any) -> web.Response:
        return web.Response(
            text=json.dumps({"error": False, "data": data}, default=_json_default),
            content_type="application/json"
        )

    def _error(self, status: int, message: str) -> web.Response:
        return web.Response(
            text=json.dumps({"error": True, "message": message}, default=_json_default),
            content_type="application/json",
            status=status
        )
