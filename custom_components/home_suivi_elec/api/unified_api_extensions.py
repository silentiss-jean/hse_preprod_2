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
    from ..group_totals import refresh_group_totals  # type: ignore
except Exception:
    refresh_group_totals = None  # type: ignore

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

            # ══════════════════════════════════════════════════════════════════
            # Configuration des prix et allowlist
            # ══════════════════════════════════════════════════════════════════

            # Lire la config pricing depuis config_entries (pour détecter type_contrat)
            from ..cost_tracking import get_pricing_config
            pricing_config = get_pricing_config(self.hass)
            type_contrat = pricing_config.get("type_contrat", "fixe")

            # Prix depuis payload API (priorité) ou depuis config_entries (fallback)
            prix_ht = float(data.get("prix_ht", data.get("prixht", 0.0)) or 0.0)
            prix_ttc = float(data.get("prix_ttc", data.get("prixttc", 0.0)) or 0.0)

            if prix_ht <= 0:
                prix_ht = float(pricing_config.get("prix_ht", 0.0))
            if prix_ttc <= 0:
                prix_ttc = float(pricing_config.get("prix_ttc", 0.0))

            # Allowlist optionnelle depuis le store cost_ha (Coût: oui)
            cost_ha_map = await mgr.get_cost_ha_config()
            allowed_sources: Set[str] = {
                str(entity_id)
                for entity_id, cfg in (cost_ha_map or {}).items()
                if isinstance(cfg, dict) and bool(cfg.get("enabled", False))
            }
            use_allowlist = len(allowed_sources) > 0

            _LOGGER.info(
                "[API-CONFIG] generate_cost_sensors type=%s HT=%.4f TTC=%.4f allowlist=%d (use=%s)",
                type_contrat,
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

            # ══════════════════════════════════════════════════════════════════
            # 💾 PERSISTANCE : Mise à jour du store cost_ha AVANT dédup
            # (pour garantir que le store existe même si tous sont dédupliqués)
            # ══════════════════════════════════════════════════════════════════

            _LOGGER.info(
                "[API-CONFIG] 💾 Préparation persistance pour %d capteurs coût générés",
                len(cost_sensors)
            )

            cost_ha_map = cost_ha_map or {}

            for e in cost_sensors:
                src = self._entity_source_energy(e)
                if not src:
                    continue
                
                # Lire les attributs du capteur coût créé
                attrs = {}
                if hasattr(e, "extra_state_attributes") and callable(e.extra_state_attributes):
                    attrs = e.extra_state_attributes or {}
                elif hasattr(e, "_attr_extra_state_attributes"):
                    attrs = e._attr_extra_state_attributes or {}
                
                # Construire l'entity_id du capteur coût
                cost_entity_id = getattr(e, "entity_id", None)
                if not cost_entity_id:
                    cost_entity_id = f"sensor.{getattr(e, '_attr_suggested_object_id', 'unknown')}"
                
                # Persister la config complète (pour réconciliation + détection changement contrat)
                entry = {
                    "enabled": True,
                    "cost_entity_id": cost_entity_id,
                    "type_contrat": type_contrat,
                    "prix_ht": prix_ht,
                    "prix_ttc": prix_ttc,
                    # Infos depuis attributs du capteur
                    "cycle": attrs.get("cycle", "daily"),
                    "variant": attrs.get("variant", "ht"),
                    "tarif_type": attrs.get("tarif_type"),
                    "price_per_kwh": attrs.get("price_per_kwh", 0.0),
                    "last_updated": self._get_timestamp(),
                }
                
                # Garder l'ancienne config si elle existe (pour tracer l'historique)
                old_entry = cost_ha_map.get(src)
                if isinstance(old_entry, dict):
                    entry["previous_type_contrat"] = old_entry.get("type_contrat")
                    entry["created_at"] = old_entry.get("created_at", entry["last_updated"])
                else:
                    entry["created_at"] = entry["last_updated"]
                
                cost_ha_map[src] = entry

            # Sauvegarder AVANT la dédup pour garantir la création du fichier
            if cost_ha_map:
                try:
                    await mgr.save_cost_ha_config(cost_ha_map)
                    _LOGGER.info(
                        "[API-CONFIG] ✅ Store cost_ha mis à jour : %d sources persistées (type=%s)",
                        len(cost_ha_map),
                        type_contrat,
                    )
                except Exception as e:
                    _LOGGER.exception("[API-CONFIG] ❌ Erreur sauvegarde store cost_ha: %s", e)

            # ══════════════════════════════════════════════════════════════════
            # Déduplication (après persistance)
            # ══════════════════════════════════════════════════════════════════

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
                    "message": f"{len(to_add)} capteurs coût envoyés à l'ajout (event cost).",
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
                        "is_energy": device_class == "energy",
                        "is_power": device_class == "power",
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

            # Refresh totals (rooms/types) après mise à jour de group_sets
            if refresh_group_totals is not None:
                try:
                    await refresh_group_totals(self.hass)
                except Exception as e:
                    _LOGGER.exception("[CONFIG] refresh_group_totals failed: %s", e)

            return self._success({
                "message": "Group sets sauvegardés avec succès",
                "count_sets": count_sets,
            })

        except Exception as e:
            _LOGGER.exception("[CONFIG] Erreur save_group_sets: %s", e)
            return self._error(500, f"Erreur save_group_sets: {e}")

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
    
    def _is_derived_from(self, entity_id: str, reference_id: str) -> bool:
        """True si entity_id == reference_id OU si en remontant source_entity on tombe sur reference_id."""
        if not entity_id or not reference_id:
            return False

        visited = set()
        current = entity_id

        while current and current not in visited:
            if current == reference_id:
                return True

            visited.add(current)
            st = self.hass.states.get(current)
            if not st:
                return False

            attrs = st.attributes or {}
            parent = attrs.get("source_entity") or attrs.get("source_energy_entity")
            if not parent or parent == current:
                return False

            current = parent

        return False

    # === GET ===
    
    async def get(self, request, action=None):
        """GET /api/home_suivi_elec/history/{action}"""
        try:
            if action is None:
                action = request.match_info.get("action", "unknown")
            
            _LOGGER.info(f"[HISTORY-API] GET /{action}")
            
            if action == "available_sensors":
                return await self._get_available_sensors()

            if action == "current_costs":
                return await self._get_current_costs()
            
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

            if action == "cost_analysis":
                return await self._analyze_cost_comparison(data)
            
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
    
    async def _get_current_costs(self):
        """
        GET /api/home_suivi_elec/history/current_costs
        Retourne l'état actuel des capteurs coût (temps réel).

        ✅ CORRECTIONS :
        - Déduplication : 1 seul capteur par source (priorité TTC > HT)
        - Détection automatique TTC/HT dans l'entity_id
        - Filtrage capteurs unavailable, inactifs (0€, 0kWh)
        - Logs détaillés pour diagnostic

        ✅ NOUVELLE FEATURE :
        - Inclure le capteur de référence (compteur) séparément + calcul de l'écart (gap)
        """
        try:
            from homeassistant.helpers import entity_registry as er

            # 🆕 Récupérer le capteur de référence depuis config_entries
            external_capteur = None
            try:
                config_entries = self.hass.config_entries.async_entries(DOMAIN)
                if config_entries:
                    hse_entry = config_entries[0]
                    # Fallback "external_sensor" pour éviter une régression si l'option n'est pas encore renommée
                    external_capteur = (
                        hse_entry.options.get("external_capteur")
                        or hse_entry.options.get("external_sensor")
                    )
                    _LOGGER.info(f"[CURRENT-COSTS] Capteur de référence: {external_capteur}")
            except Exception as e:
                _LOGGER.warning(f"[CURRENT-COSTS] Impossible de lire external_capteur: {e}")

            # ✅ CORRECTION: pré-initialiser reference_sensor à partir de external_capteur
            # (même si aucun capteur coût "référence" n'est trouvé/retourné)
            reference_sensor = None
            if external_capteur:
                ref_state = self.hass.states.get(external_capteur)
                ref_attrs = (ref_state.attributes or {}) if ref_state else {}

                ref_energy = 0.0
                if ref_state and ref_state.state not in ("unknown", "unavailable"):
                    try:
                        ref_energy = float(ref_state.state)
                    except (ValueError, TypeError):
                        ref_energy = 0.0

                reference_sensor = {
                    "entity_id": external_capteur,
                    "friendly_name": ref_attrs.get("friendly_name", external_capteur),
                    "cost_ttc": 0.0,
                    "cost_ht": 0.0,
                    "energy_kwh": round(ref_energy, 3),
                    "unit": ref_attrs.get("unit_of_measurement"),
                    "source_entity": external_capteur,
                    "cycle": "daily",
                    "is_reference": True,
                    "reference_only": True,  # marker: placeholder (pas un capteur coût HSE)
                    "state": ref_state.state if ref_state else None,
                }

            entity_reg = er.async_get(self.hass)

            cost_sensors_map = {}  # Dict[source_entity_id, sensor_data] (SANS référence)
            excluded_count = 0
            excluded_reasons = {
                "unavailable": 0,
                "unknown": 0,
                "zero_values": 0,
                "source_unavailable": 0,
                "duplicate_ht": 0,
            }

            for entity_id, entry in entity_reg.entities.items():
                if (
                    entry.platform == "home_suivi_elec"
                    and "_cout_daily" in entity_id
                    and entity_id.startswith("sensor.hse_")
                ):
                    state = self.hass.states.get(entity_id)
                    if not state:
                        excluded_count += 1
                        excluded_reasons["unavailable"] += 1
                        continue

                    # ✅ FILTRAGE 1 : Exclure si state unavailable/unknown
                    if state.state in ("unavailable", "unknown", "none", None):
                        excluded_count += 1
                        excluded_reasons["unavailable"] += 1
                        _LOGGER.debug(f"[CURRENT-COSTS] Exclus {entity_id}: state={state.state}")
                        continue

                    attrs = state.attributes or {}
                    source_entity_id = attrs.get("source_entity")

                    if not source_entity_id:
                        _LOGGER.debug(f"[CURRENT-COSTS] Exclus {entity_id}: pas de source_entity")
                        continue

                    # ✅ FILTRAGE 2 : Vérifier l'état de la source d'énergie
                    source_state = self.hass.states.get(source_entity_id)
                    if source_state and source_state.state in ("unavailable", "unknown"):
                        excluded_count += 1
                        excluded_reasons["source_unavailable"] += 1
                        _LOGGER.debug(
                            f"[CURRENT-COSTS] Exclus {entity_id}: source {source_entity_id} unavailable"
                        )
                        continue

                    # Récupérer l'énergie depuis la source
                    energy_kwh = 0.0
                    if source_state and source_state.state not in ("unknown", "unavailable"):
                        try:
                            energy_kwh = float(source_state.state)
                        except (ValueError, TypeError):
                            pass

                    # 🆕 Détecter si c'est le capteur de référence
                    is_reference = bool(external_capteur and self._is_derived_from(source_entity_id, external_capteur))


                    # ✅ DÉTECTION DU TYPE DE CAPTEUR (TTC ou HT)
                    is_ttc = "_ttc" in entity_id.lower()
                    is_ht = "_ht" in entity_id.lower() and "_ttc" not in entity_id.lower()

                    # Lire la valeur du capteur
                    try:
                        sensor_value = float(state.state) if state.state not in ("unknown", "unavailable") else 0.0
                    except (ValueError, TypeError):
                        sensor_value = 0.0

                    # ✅ CALCUL INTELLIGENT TTC/HT selon le type de capteur
                    if is_ttc:
                        cost_ttc = sensor_value
                        cost_ht = cost_ttc / 1.1 if cost_ttc > 0 else 0.0
                        _LOGGER.debug(
                            f"[CURRENT-COSTS] {entity_id} (TTC): {cost_ttc:.2f}€ TTC → {cost_ht:.2f}€ HT"
                        )
                    elif is_ht:
                        cost_ht = sensor_value
                        cost_ttc = cost_ht * 1.1 if cost_ht > 0 else 0.0
                        _LOGGER.debug(
                            f"[CURRENT-COSTS] {entity_id} (HT): {cost_ht:.2f}€ HT → {cost_ttc:.2f}€ TTC"
                        )
                    else:
                        cost_ttc = sensor_value
                        cost_ht = cost_ttc / 1.1 if cost_ttc > 0 else 0.0
                        _LOGGER.warning(f"[CURRENT-COSTS] {entity_id} sans suffixe TTC/HT, suppose TTC")

                    # ✅ FILTRAGE 3 : Exclure si coût=0 ET énergie=0
                    if cost_ttc == 0.0 and energy_kwh == 0.0:
                        excluded_count += 1
                        excluded_reasons["zero_values"] += 1
                        _LOGGER.debug(f"[CURRENT-COSTS] Exclus {entity_id}: coût=0 énergie=0")
                        continue

                    sensor_data = {
                        "entity_id": entity_id,
                        "friendly_name": attrs.get("friendly_name", entity_id),
                        "cost_ttc": round(cost_ttc, 2),
                        "cost_ht": round(cost_ht, 2),
                        "energy_kwh": round(energy_kwh, 3),
                        "unit": attrs.get("unit_of_measurement", "EUR"),
                        "source_entity": source_entity_id,
                        "cycle": "daily",
                        "is_reference": is_reference,
                        "reference_only": False,  # 🆕 (explicite)
                    }

                    # 🆕 Séparer référence vs internes
                    if is_reference:
                        # ✅ CORRECTION: si on a déjà un placeholder reference_only, on le remplace
                        if reference_sensor is not None and reference_sensor.get("reference_only"):
                            reference_sensor = sensor_data
                            _LOGGER.info(
                                f"[CURRENT-COSTS] Référence (placeholder→capteur coût): {entity_id} = {cost_ttc:.2f}€"
                            )
                            continue

                        if reference_sensor is None:
                            reference_sensor = sensor_data
                            _LOGGER.info(
                                f"[CURRENT-COSTS] Référence détectée: {entity_id} = {cost_ttc:.2f}€"
                            )
                        else:
                            # Dédup sur la référence aussi (priorité TTC > HT)
                            existing_is_ttc = "_ttc" in reference_sensor["entity_id"].lower()
                            if is_ttc and not existing_is_ttc:
                                _LOGGER.info(
                                    f"[CURRENT-COSTS] Référence: remplacement {reference_sensor['entity_id']} (HT) "
                                    f"par {entity_id} (TTC)"
                                )
                                reference_sensor = sensor_data
                            elif is_ht and existing_is_ttc:
                                excluded_count += 1
                                excluded_reasons["duplicate_ht"] += 1
                                _LOGGER.debug(
                                    f"[CURRENT-COSTS] Référence: exclusion {entity_id} (HT) "
                                    f"doublon de {reference_sensor['entity_id']} (TTC)"
                                )
                            else:
                                _LOGGER.warning(
                                    f"[CURRENT-COSTS] Référence: doublon ambigu "
                                    f"{reference_sensor['entity_id']} vs {entity_id}"
                                )
                        continue  # ⚠️ Ne pas mettre la référence dans cost_sensors_map

                    # ✅ DÉDUPLICATION : Gérer les doublons TTC/HT pour la même source (internes)
                    if source_entity_id in cost_sensors_map:
                        existing = cost_sensors_map[source_entity_id]
                        existing_is_ttc = "_ttc" in existing["entity_id"].lower()

                        if is_ttc and not existing_is_ttc:
                            _LOGGER.info(
                                f"[CURRENT-COSTS] Remplacement {existing['entity_id']} (HT) "
                                f"par {entity_id} (TTC) pour source {source_entity_id}"
                            )
                        elif is_ht and existing_is_ttc:
                            excluded_count += 1
                            excluded_reasons["duplicate_ht"] += 1
                            _LOGGER.debug(
                                f"[CURRENT-COSTS] Exclus {entity_id} (HT): "
                                f"doublon de {existing['entity_id']} (TTC)"
                            )
                            continue
                        else:
                            _LOGGER.warning(
                                f"[CURRENT-COSTS] Doublon ambigu pour {source_entity_id}: "
                                f"{existing['entity_id']} vs {entity_id}"
                            )
                            continue

                    cost_sensors_map[source_entity_id] = sensor_data

            # Convertir en liste (sans le capteur de référence)
            cost_sensors = list(cost_sensors_map.values())
            cost_sensors.sort(key=lambda x: x["cost_ttc"], reverse=True)

            top_10 = cost_sensors[:10]
            other_sensors = cost_sensors[10:]

            # Totaux (SANS référence)
            total_cost_ttc = sum(s["cost_ttc"] for s in cost_sensors)
            total_cost_ht = sum(s["cost_ht"] for s in cost_sensors)
            total_energy = sum(s["energy_kwh"] for s in cost_sensors)

            # 🆕 Calculer l'écart vs référence
            gap_info = None
            if reference_sensor:
                gap_energy = reference_sensor["energy_kwh"] - total_energy
                gap_cost_ttc = reference_sensor["cost_ttc"] - total_cost_ttc
                gap_cost_ht = reference_sensor["cost_ht"] - total_cost_ht
                gap_pct = (
                    (gap_energy / reference_sensor["energy_kwh"] * 100.0)
                    if reference_sensor["energy_kwh"] > 0
                    else 0.0
                )

                gap_info = {
                    "energy_kwh": round(gap_energy, 3),
                    "cost_ttc": round(gap_cost_ttc, 2),
                    "cost_ht": round(gap_cost_ht, 2),
                    "percent": round(gap_pct, 1),
                }

                _LOGGER.info(
                    f"[CURRENT-COSTS] Écart détecté: {gap_energy:.3f} kWh ({gap_pct:.1f}%) = {gap_cost_ttc:.2f}€ TTC"
                )

            _LOGGER.info(
                f"[CURRENT-COSTS] ✅ {len(cost_sensors)} capteurs uniques, "
                f"{excluded_count} exclus "
                f"(unavailable:{excluded_reasons['unavailable']}, "
                f"zero:{excluded_reasons['zero_values']}, "
                f"source_unavailable:{excluded_reasons['source_unavailable']}, "
                f"duplicate_ht:{excluded_reasons['duplicate_ht']}), "
                f"total={total_cost_ttc:.2f}€ TTC / {total_cost_ht:.2f}€ HT"
            )

            return self._success(
                {
                    "reference_sensor": reference_sensor,
                    "top_10": top_10,
                    "other_sensors": other_sensors,
                    "total_cost_ttc": round(total_cost_ttc, 2),
                    "total_cost_ht": round(total_cost_ht, 2),
                    "total_energy_kwh": round(total_energy, 3),
                    "sensor_count": len(cost_sensors),
                    "gap": gap_info,
                    "excluded_count": excluded_count,
                    "excluded_reasons": excluded_reasons,
                    "timestamp": self._get_timestamp(),
                }
            )

        except Exception as e:
            _LOGGER.exception(f"[CURRENT-COSTS] Erreur: {e}")
            return self._error(500, str(e))

    async def _analyze_cost_comparison(self, data):
        """
        POST /api/home_suivi_elec/history/cost_analysis
        Analyse comparative entre deux périodes en utilisant les capteurs coût existants.

        ✅ NOUVELLE APPROCHE :
        - Lit directement les valeurs des capteurs coût (pas de recalcul)
        - Merge les capteurs HT/TTC pour la même source
        - Récupère les statistiques historiques des capteurs coût

        ✅ NOUVELLE FEATURE :
        - Gestion d’un capteur de référence (compteur) via config_entries options["external_capteur"]
        - Le capteur de référence est renvoyé séparément et EXCLU des totaux / tops
        """
        try:
            from homeassistant.components.recorder.statistics import statistics_during_period
            from homeassistant.helpers import entity_registry as er
            from ..history_analytics import _to_datetime

            # ═══════════════════════════════════════════════════════════
            # 1. Parse et valide les paramètres
            # ═══════════════════════════════════════════════════════════
            baseline_start = data.get("baseline_start")
            baseline_end = data.get("baseline_end")
            event_start = data.get("event_start")
            event_end = data.get("event_end")
            top_limit = int(data.get("top_limit", 10))
            sort_by = data.get("sort_by", "cost_ttc")

            if not all([baseline_start, baseline_end, event_start, event_end]):
                return self._error(
                    400,
                    "Paramètres baseline_start, baseline_end, event_start, event_end requis",
                )

            # Convertir les timestamps en datetime
            try:
                baseline_start_dt = _to_datetime(baseline_start)
                baseline_end_dt = _to_datetime(baseline_end)
                event_start_dt = _to_datetime(event_start)
                event_end_dt = _to_datetime(event_end)
            except Exception as e:
                return self._error(400, f"Format de date invalide: {e}")

            _LOGGER.info(
                f"[COST-ANALYSIS] baseline: {baseline_start_dt.isoformat()} → {baseline_end_dt.isoformat()}"
            )
            _LOGGER.info(
                f"[COST-ANALYSIS] event: {event_start_dt.isoformat()} → {event_end_dt.isoformat()}"
            )

            # ═══════════════════════════════════════════════════════════
            # 🆕 RÉCUPÉRER LE CAPTEUR DE RÉFÉRENCE depuis config_entries
            # ═══════════════════════════════════════════════════════════
            external_capteur = None
            try:
                config_entries = self.hass.config_entries.async_entries(DOMAIN)
                if config_entries:
                    hse_entry = config_entries[0]  # Normalement une seule entry
                    external_capteur = (
                        hse_entry.options.get("external_capteur")
                        or hse_entry.options.get("external_sensor")
                    )
                    _LOGGER.info(f"[COST-ANALYSIS] Capteur de référence: {external_capteur}")
            except Exception as e:
                _LOGGER.warning(f"[COST-ANALYSIS] Impossible de lire external_capteur: {e}")

            # ═══════════════════════════════════════════════════════════
            # 2. Récupérer tous les capteurs de COÛT HSE avec leur source
            # (conservé tel quel, même si redondant avec sensors_map)
            # ═══════════════════════════════════════════════════════════
            entity_reg = er.async_get(self.hass)
            sensors_by_source = {}

            for entity_id, entry in entity_reg.entities.items():
                if (
                    entry.platform == "home_suivi_elec"
                    and entity_id.startswith("sensor.hse_")
                    and "_cout_daily" in entity_id
                ):
                    state = self.hass.states.get(entity_id)
                    if not state or state.state in ("unavailable", "unknown", "none", None):
                        continue

                    attrs = state.attributes or {}
                    source_entity = attrs.get("source_entity")

                    if not source_entity:
                        _LOGGER.debug(
                            f"[COST-ANALYSIS] Capteur {entity_id} sans source_entity, ignoré"
                        )
                        continue

                    is_ttc = "_ttc" in entity_id.lower()
                    is_ht = "_ht" in entity_id.lower() and "_ttc" not in entity_id.lower()

                    if not is_ht and not is_ttc:
                        _LOGGER.warning(
                            f"[COST-ANALYSIS] Capteur {entity_id} sans suffixe HT/TTC, supposé TTC"
                        )
                        is_ttc = True

                    variant = "ttc" if is_ttc else "ht"
                    statistic_id = attrs.get("statistic_id") or entity_id
                    price_per_kwh = float(attrs.get("price_per_kwh", 0.0))

                    sensor_info = {
                        "entity_id": entity_id,
                        "source_entity": source_entity,
                        "friendly_name": attrs.get("friendly_name", entity_id),
                        "statistic_id": statistic_id,
                        "variant": variant,
                        "price_per_kwh": price_per_kwh,
                        "cycle": attrs.get("cycle", "daily"),
                    }

                    if source_entity not in sensors_by_source:
                        sensors_by_source[source_entity] = {}

                    sensors_by_source[source_entity][variant] = sensor_info

            _LOGGER.info(
                f"[COST-ANALYSIS] {len(sensors_by_source)} sources avec capteurs coût trouvées"
            )

            # Réponse vide cohérente
            def _empty_result():
                return self._success(
                    {
                        "baseline_period": {
                            "start": baseline_start,
                            "end": baseline_end,
                            "total_kwh": 0.0,
                            "total_cost_ht": 0.0,
                            "total_cost_ttc": 0.0,
                            "sensor_count": 0,
                        },
                        "event_period": {
                            "start": event_start,
                            "end": event_end,
                            "total_kwh": 0.0,
                            "total_cost_ht": 0.0,
                            "total_cost_ttc": 0.0,
                            "sensor_count": 0,
                        },
                        "total_comparison": {
                            "delta_kwh": 0.0,
                            "delta_cost_ht": 0.0,
                            "delta_cost_ttc": 0.0,
                            "delta_pct_kwh": 0.0,
                            "delta_pct_cost": 0.0,
                            "trend": "stable",
                        },
                        "reference_sensor": None,
                        "top_variations": [],
                        "top_consumers": [],
                        "other_sensors": [],
                        "timestamp": self._get_timestamp(),
                    }
                )

            if not sensors_by_source:
                return _empty_result()

            # ═══════════════════════════════════════════════════════════
            # 3. Récupérer les capteurs avec flag is_reference
            # ═══════════════════════════════════════════════════════════
            entity_reg = er.async_get(self.hass)
            sensors_map = {}

            for entity_id, entry in entity_reg.entities.items():
                if (
                    entry.platform == "home_suivi_elec"
                    and entity_id.startswith("sensor.hse_")
                    and "_cout_daily" in entity_id
                ):
                    state = self.hass.states.get(entity_id)
                    if not state or state.state in ("unavailable", "unknown", "none", None):
                        continue

                    attrs = state.attributes or {}
                    source_entity = attrs.get("source_entity")

                    if not source_entity:
                        continue

                    # 🆕 Détecter si c'est le capteur de référence
                    # ✅ FIX: utiliser la variable existante dans ce scope (source_entity)
                    is_reference = bool(
                        external_capteur and self._is_derived_from(source_entity, external_capteur)
                    )

                    # Détecter si HT ou TTC
                    is_ttc = "_ttc" in entity_id.lower()
                    is_ht = "_ht" in entity_id.lower() and "_ttc" not in entity_id.lower()

                    if not is_ht and not is_ttc:
                        is_ttc = True  # Par défaut

                    price_per_kwh = float(attrs.get("price_per_kwh", 0.0))

                    if source_entity not in sensors_map:
                        # Friendly name depuis la source d'énergie
                        source_state = self.hass.states.get(source_entity)
                        source_attrs = source_state.attributes or {} if source_state else {}

                        sensors_map[source_entity] = {
                            "source_entity": source_entity,
                            "friendly_name": source_attrs.get("friendly_name", source_entity),
                            "statistic_id": source_attrs.get("statistic_id") or source_entity,
                            "prix_ht": None,
                            "prix_ttc": None,
                            "is_reference": is_reference,  # 🆕 Flag référence
                        }
                    else:
                        # ✅ Cohérence: si déjà créé, on force le flag à True si l'un des variants est référence
                        if is_reference:
                            sensors_map[source_entity]["is_reference"] = True

                    if is_ttc:
                        sensors_map[source_entity]["prix_ttc"] = price_per_kwh
                    else:
                        sensors_map[source_entity]["prix_ht"] = price_per_kwh

            # Compléter les prix manquants avec ratio 1.1
            for _source_entity, info in sensors_map.items():
                if info["prix_ttc"] and not info["prix_ht"]:
                    info["prix_ht"] = info["prix_ttc"] / 1.1
                elif info["prix_ht"] and not info["prix_ttc"]:
                    info["prix_ttc"] = info["prix_ht"] * 1.1

            _LOGGER.info(
                f"[COST-ANALYSIS] {len(sensors_map)} sources d'énergie avec pricing trouvées"
            )

            if not sensors_map:
                return _empty_result()

            # ═══════════════════════════════════════════════════════════
            # 4. Récupérer les statistiques ÉNERGIE (pas coût)
            # ═══════════════════════════════════════════════════════════
            statistic_ids = [info["statistic_id"] for info in sensors_map.values()]

            _LOGGER.info(
                f"[COST-ANALYSIS] Fetching energy statistics pour {len(statistic_ids)} sources"
            )

            baseline_stats = await self.hass.async_add_executor_job(
                statistics_during_period,
                self.hass,
                baseline_start_dt,
                baseline_end_dt,
                statistic_ids,
                "hour",
                None,
                {"sum"},
            )

            event_stats = await self.hass.async_add_executor_job(
                statistics_during_period,
                self.hass,
                event_start_dt,
                event_end_dt,
                statistic_ids,
                "hour",
                None,
                {"sum"},
            )

            # ═══════════════════════════════════════════════════════════
            # 5. Calculer les coûts depuis l'énergie + prix
            # ═══════════════════════════════════════════════════════════
            entity_comparisons = []
            baseline_duration_s = (baseline_end_dt - baseline_start_dt).total_seconds()
            event_duration_s = (event_end_dt - event_start_dt).total_seconds()

            for source_entity, info in sensors_map.items():
                statistic_id = info["statistic_id"]
                prix_ht = info["prix_ht"]
                prix_ttc = info["prix_ttc"]

                # === BASELINE ===
                baseline_rows = baseline_stats.get(statistic_id, [])
                if not baseline_rows:
                    _LOGGER.debug(f"[COST-ANALYSIS] Pas de stats baseline pour {statistic_id}")
                    continue

                baseline_last = baseline_rows[-1].get("sum", 0.0) if baseline_rows else 0.0
                baseline_first = baseline_rows[0].get("sum", 0.0) if baseline_rows else 0.0
                baseline_energy_kwh = float(baseline_last) - float(baseline_first)

                baseline_cost_ht = baseline_energy_kwh * prix_ht if prix_ht else 0.0
                baseline_cost_ttc = baseline_energy_kwh * prix_ttc if prix_ttc else 0.0

                # === EVENT ===
                event_rows = event_stats.get(statistic_id, [])
                if not event_rows:
                    _LOGGER.debug(f"[COST-ANALYSIS] Pas de stats event pour {statistic_id}")
                    continue

                event_last = event_rows[-1].get("sum", 0.0) if event_rows else 0.0
                event_first = event_rows[0].get("sum", 0.0) if event_rows else 0.0
                event_energy_kwh = float(event_last) - float(event_first)

                event_cost_ht = event_energy_kwh * prix_ht if prix_ht else 0.0
                event_cost_ttc = event_energy_kwh * prix_ttc if prix_ttc else 0.0

                if baseline_energy_kwh == 0.0 and event_energy_kwh == 0.0:
                    continue

                baseline_h = baseline_duration_s / 3600.0 if baseline_duration_s > 0 else 0.0
                event_h = event_duration_s / 3600.0 if event_duration_s > 0 else 0.0
                baseline_d = baseline_duration_s / 86400.0 if baseline_duration_s > 0 else 0.0
                event_d = event_duration_s / 86400.0 if event_duration_s > 0 else 0.0

                def safe_div(a, b, ndigits=3):
                    return round(a / b, ndigits) if b > 0 else 0.0

                baseline_kwh_h = safe_div(baseline_energy_kwh, baseline_h, 3)
                event_kwh_h = safe_div(event_energy_kwh, event_h, 3)
                baseline_cost_ttc_h = safe_div(baseline_cost_ttc, baseline_h, 4)
                event_cost_ttc_h = safe_div(event_cost_ttc, event_h, 4)

                baseline_kwh_d = safe_div(baseline_energy_kwh, baseline_d, 3)
                event_kwh_d = safe_div(event_energy_kwh, event_d, 3)
                baseline_cost_ttc_d = safe_div(baseline_cost_ttc, baseline_d, 4)
                event_cost_ttc_d = safe_div(event_cost_ttc, event_d, 4)

                delta_energy = event_energy_kwh - baseline_energy_kwh
                delta_cost_ht = event_cost_ht - baseline_cost_ht
                delta_cost_ttc = event_cost_ttc - baseline_cost_ttc

                pct_energy = (
                    safe_div(delta_energy, baseline_energy_kwh, 1) * 100
                    if baseline_energy_kwh > 0
                    else 0.0
                )
                pct_cost_ttc = (
                    safe_div(delta_cost_ttc, baseline_cost_ttc, 1) * 100
                    if baseline_cost_ttc > 0
                    else 0.0
                )

                comparison = {
                    "entity_id": source_entity,
                    "display_name": info["friendly_name"],
                    "source_entity": source_entity,
                    # Baseline
                    "baseline_energy_kwh": round(baseline_energy_kwh, 3),
                    "baseline_cost_ht": round(baseline_cost_ht, 2),
                    "baseline_cost_ttc": round(baseline_cost_ttc, 2),
                    "baseline_energy_kwh_per_hour": baseline_kwh_h,
                    "baseline_cost_ttc_per_hour": baseline_cost_ttc_h,
                    "baseline_energy_kwh_per_day": baseline_kwh_d,
                    "baseline_cost_ttc_per_day": baseline_cost_ttc_d,
                    # Event
                    "event_energy_kwh": round(event_energy_kwh, 3),
                    "event_cost_ht": round(event_cost_ht, 2),
                    "event_cost_ttc": round(event_cost_ttc, 2),
                    "event_energy_kwh_per_hour": event_kwh_h,
                    "event_cost_ttc_per_hour": event_cost_ttc_h,
                    "event_energy_kwh_per_day": event_kwh_d,
                    "event_cost_ttc_per_day": event_cost_ttc_d,
                    # Deltas
                    "delta_energy_kwh": round(delta_energy, 3),
                    "delta_cost_ht": round(delta_cost_ht, 2),
                    "delta_cost_ttc": round(delta_cost_ttc, 2),
                    "delta_energy_kwh_per_hour": round(event_kwh_h - baseline_kwh_h, 3),
                    "delta_cost_ttc_per_hour": round(event_cost_ttc_h - baseline_cost_ttc_h, 4),
                    "delta_energy_kwh_per_day": round(event_kwh_d - baseline_kwh_d, 3),
                    "delta_cost_ttc_per_day": round(event_cost_ttc_d - baseline_cost_ttc_d, 4),
                    # Pourcentages
                    "pct_energy_kwh": round(pct_energy, 1),
                    "pct_cost_ttc": round(pct_cost_ttc, 1),
                }

                entity_comparisons.append(comparison)

            _LOGGER.info(
                f"[COST-ANALYSIS] {len(entity_comparisons)} capteurs avec données comparées"
            )

            if not entity_comparisons:
                return _empty_result()

            # ═══════════════════════════════════════════════════════════
            # 🆕 Séparer le capteur de référence des autres
            # ═══════════════════════════════════════════════════════════
            reference_comparison = None
            internal_comparisons = []

            for comparison in entity_comparisons:
                source_entity = comparison.get("source_entity")
                info = sensors_map.get(source_entity, {}) if source_entity else {}

                if info.get("is_reference"):
                    comparison["is_reference"] = True
                    reference_comparison = comparison
                    _LOGGER.info(
                        f"[COST-ANALYSIS] Capteur de référence identifié: {source_entity}"
                    )
                else:
                    comparison["is_reference"] = False
                    internal_comparisons.append(comparison)

            # ═══════════════════════════════════════════════════════════
            # Calculer les totaux (SANS le capteur de référence)
            # ═══════════════════════════════════════════════════════════
            total_baseline_kwh = sum(c["baseline_energy_kwh"] for c in internal_comparisons)
            total_baseline_cost_ht = sum(c["baseline_cost_ht"] for c in internal_comparisons)
            total_baseline_cost_ttc = sum(c["baseline_cost_ttc"] for c in internal_comparisons)

            total_event_kwh = sum(c["event_energy_kwh"] for c in internal_comparisons)
            total_event_cost_ht = sum(c["event_cost_ht"] for c in internal_comparisons)
            total_event_cost_ttc = sum(c["event_cost_ttc"] for c in internal_comparisons)

            delta_kwh = total_event_kwh - total_baseline_kwh
            delta_cost_ht = total_event_cost_ht - total_baseline_cost_ht
            delta_cost_ttc = total_event_cost_ttc - total_baseline_cost_ttc

            delta_pct_kwh = (
                (delta_kwh / total_baseline_kwh * 100.0) if total_baseline_kwh > 0 else 0.0
            )
            delta_pct_cost = (
                (delta_cost_ttc / total_baseline_cost_ttc * 100.0)
                if total_baseline_cost_ttc > 0
                else 0.0
            )

            if abs(delta_pct_cost) < 5.0:
                trend = "stable"
            elif delta_cost_ttc > 0:
                trend = "hausse"
            else:
                trend = "baisse"

            # ═══════════════════════════════════════════════════════════
            # Trier et séparer (SANS le capteur de référence)
            # ═══════════════════════════════════════════════════════════
            if sort_by == "energy_kwh":
                internal_comparisons.sort(
                    key=lambda x: abs(x["delta_energy_kwh"]), reverse=True
                )
            else:
                internal_comparisons.sort(
                    key=lambda x: abs(x["delta_cost_ttc"]), reverse=True
                )

            top_variations = internal_comparisons[:top_limit]
            other_sensors = internal_comparisons[top_limit:]

            top_consumers = sorted(
                internal_comparisons, key=lambda x: x["event_cost_ttc"], reverse=True
            )[:top_limit]

            # ═══════════════════════════════════════════════════════════
            # 🆕 Construire la réponse avec le capteur de référence séparé
            # ═══════════════════════════════════════════════════════════
            result = {
                "baseline_period": {
                    "start": baseline_start,
                    "end": baseline_end,
                    "total_kwh": round(total_baseline_kwh, 3),
                    "total_cost_ht": round(total_baseline_cost_ht, 2),
                    "total_cost_ttc": round(total_baseline_cost_ttc, 2),
                    "sensor_count": len(internal_comparisons),
                },
                "event_period": {
                    "start": event_start,
                    "end": event_end,
                    "total_kwh": round(total_event_kwh, 3),
                    "total_cost_ht": round(total_event_cost_ht, 2),
                    "total_cost_ttc": round(total_event_cost_ttc, 2),
                    "sensor_count": len(internal_comparisons),
                },
                "total_comparison": {
                    "delta_kwh": round(delta_kwh, 3),
                    "delta_cost_ht": round(delta_cost_ht, 2),
                    "delta_cost_ttc": round(delta_cost_ttc, 2),
                    "delta_pct_kwh": round(delta_pct_kwh, 1),
                    "delta_pct_cost": round(delta_pct_cost, 1),
                    "trend": trend,
                },
                "reference_sensor": reference_comparison,
                "top_variations": top_variations,
                "top_consumers": top_consumers,
                "other_sensors": other_sensors,
                "timestamp": self._get_timestamp(),
            }

            log_ref = ""
            if reference_comparison:
                try:
                    log_ref = (
                        f" | Référence: {reference_comparison.get('display_name')} "
                        f"({reference_comparison.get('event_cost_ttc', 0.0):.2f}€)"
                    )
                except Exception:
                    log_ref = " | Référence: (log failed)"

            _LOGGER.info(
                f"[COST-ANALYSIS] ✅ Analyse terminée: "
                f"{len(top_variations)} top + {len(other_sensors)} autres{log_ref}"
            )

            return self._success(result)

        except Exception as e:
            _LOGGER.exception(f"[COST-ANALYSIS] Erreur: {e}")
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
    
    def _get_timestamp(self) -> str:
        return datetime.now().isoformat()

