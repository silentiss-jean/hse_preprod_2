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
