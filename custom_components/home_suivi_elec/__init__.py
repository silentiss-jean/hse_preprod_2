# -*- coding: utf-8 -*-

"""

Home Suivi Élec — Backend principal de l'intégration Home Assistant.

PHASE 2.7: Migration Storage API intégrée au démarrage.

Orchestrateur global : gère initialisation, cycle de vie, enregistrement des services Home Assistant,

endpoints REST, configuration du panel UI, synchronisation et maintenance des capteurs énergétiques.

Coordonne les modules backend métiers : détection, sélection, scoring, diagnostics, tracking, backup.

Toutes les clés métier et hass.data transitent par ce module central.

"""

import logging

import os

import shutil

import asyncio

import json

from typing import Any, Dict, List, Optional

from datetime import datetime

from homeassistant.core import HomeAssistant, ServiceCall, callback, EVENT_HOMEASSISTANT_STARTED

from homeassistant.config_entries import ConfigEntry

from homeassistant.components.http import HomeAssistantView

from homeassistant.helpers.storage import Store

from homeassistant.components import frontend

from .const import DOMAIN, CONF_AUTO_GENERATE

from .detect_local import run_detect_local

from .generator import run_all

from .debug_json_sets import scan_sets

from .options_flow import HomeSuiviElecOptionsFlow

from . import manage_selection

from .proxy_api import SuiviElecProxyView

from .sensor_name_fixer import async_setup_sensor_name_fixer, async_fix_all_long_sensors

from .manage_selection_views import HSESensorsPublicView, SensorMappingView, GetHistoryCostsView

from .hidden_sensors_view import HiddenSensorsView

from .api.unified_api_extensions import ValidationActionView, HomeElecUnifiedConfigAPIView, HomeElecMigrationHelpersView, CacheClearView, CacheInvalidateEntityView, HistoryAnalysisView

# ✅ PHASE 2.7: Import StorageManager et migration

from .storage_manager import StorageManager

from .migration_storage import async_migrate_storage, async_export_storage_backup, async_rollback_to_legacy

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

# ============================================================================

# HELPERS (anti-régression + référence externe)

# ============================================================================

def _safe_unique_id(ent):

    """Retourne unique_id d'une entity (ou None)."""

    try:

        uid = getattr(ent, "unique_id", None)

        if uid:

            return str(uid)

    except Exception:

        pass

    try:

        uid = getattr(ent, "_attr_unique_id", None)

        if uid:

            return str(uid)

    except Exception:

        pass

    return None

def _merge_entities_unique(existing, new):

    """Fusionne 2 listes d'entités en évitant les doublons via unique_id."""

    out = []

    seen = set()

    for ent in list(existing or []) + list(new or []):

        uid = _safe_unique_id(ent)

        if uid:

            if uid in seen:

                continue

            seen.add(uid)

        out.append(ent)

    return out

async def _ensure_reference_sensors(hass: HomeAssistant, entry: ConfigEntry) -> None:

    """Prépare les sensors cycles du capteur de référence (options: useExternal/externalCapteur)."""

    try:

        opts = dict(entry.options or {})

        use_external = bool(opts.get("use_external", False))

        ref_entity_id = opts.get("external_capteur")

        if not (use_external and ref_entity_id):

            _LOGGER.info("[REF] Aucun capteur de référence activé")

            return

        from .energy_tracking import ensure_reference_energy_sensors

        _LOGGER.info("[REF] Capteur de référence activé: %s", ref_entity_id)

        ref_sensors = await ensure_reference_energy_sensors(hass, str(ref_entity_id))

        if not ref_sensors:

            _LOGGER.info("[REF] Aucun sensor référence à ajouter")

            return

        hass.data.setdefault(DOMAIN, {})

        existing = hass.data[DOMAIN].get("energy_sensors", [])

        hass.data[DOMAIN]["energy_sensors"] = _merge_entities_unique(existing, ref_sensors)

        _LOGGER.info(

            "[REF] %d sensor(s) référence ajoutés (total energy_sensors=%d)",

            len(ref_sensors),

            len(hass.data[DOMAIN].get("energy_sensors", [])),

        )

    except Exception as e:

        _LOGGER.exception("[REF] Erreur ensure_reference_sensors: %s", e)

# ============================================================================

# VUES ADDITIONNELLES INLINE (évite imports manquants)

# ============================================================================

class PingView(HomeAssistantView):

    """Test simple pour vérifier que nos vues sont bien enregistrées."""

    url = "/api/home_suivi_elec/ping"

    name = "api:home_suivi_elec:ping"

    requires_auth = False

    cors_allowed = True

    async def get(self, request):

        return self.json({

            "success": True,

            "message": "Home Suivi Elec API is working",

            "timestamp": datetime.now().isoformat()

        })

async def async_setup(hass: HomeAssistant, config: dict) -> bool:

    """

    Setup minimal pour initialisation Home Suivi Élec.

    Initialise le log et prépare l'environnement Home Assistant pour une future configuration.

    Retourne True si l'environnement est prêt.

    """

    _LOGGER.info("[SETUP] async_setup appelé")

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    """

    Point d'entrée principal du backend Home Suivi Élec lors de l'ajout ou du reload de l'intégration.

    PHASE 2.7: Migration automatique Storage API au démarrage.

    - Initialise tous les modules critiques backend (dictionnaires hass.data, correcteur de noms, panel UI).

    - Migre automatiquement data/*.json vers Storage API si fichiers legacy détectés.

    - Enregistre tous les services Home Assistant (détection auto, sélection, génération Lovelace, maintenance...).

    - Déploie toutes les API REST pour accès frontend, selection, diagnostics, et actions personnalisées.

    - Orchestration complète du setup différé et fallback si certains modules ou states ne sont pas encore disponibles.

    - Débute la synchronisation et l'enregistrement des sensors (énergie + power live).

    Retourne True si tout le setup est réussi.

    """

    _LOGGER.info("[SETUP-ENTRY] Initialisation Home Suivi Élec")

    hass.data.setdefault(DOMAIN, {})

    raw_data = dict(entry.data or {})

    raw_options = dict(entry.options or {})

    # Standard HA: options écrasent data

    effective = dict(raw_data)

    effective.update(raw_options)

    hass.data[DOMAIN]["config"] = raw_data

    hass.data[DOMAIN]["options"] = raw_options

    hass.data[DOMAIN]["effective_options"] = effective

    # ========================================

    # 🎯 PHASE 2.7: MIGRATION STORAGE API

    # ========================================

    _LOGGER.info("=" * 70)

    _LOGGER.info("🔄 [PHASE 2.7] Vérification migration Storage API...")

    _LOGGER.info("=" * 70)

    try:

        # ✅ Initialiser StorageManager ICI (AVANT tout le reste)

        storage_manager = StorageManager(hass)

        hass.data[DOMAIN]["storage_manager"] = storage_manager

        # Migration automatique si fichiers legacy détectés

        migration_success = await async_migrate_storage(hass)

        if migration_success:

            _LOGGER.info("✅ [STORAGE] Migration Storage API terminée")

            # Émettre event pour notifier les composants

            hass.bus.async_fire("hse_storage_migrated", {

                "timestamp": datetime.now().isoformat(),

                "status": "success"

            })

        else:

            _LOGGER.warning("⚠️ [STORAGE] Migration échouée, tentative de fonctionnement en mode dégradé")

    except Exception as e:

        _LOGGER.exception("❌ [STORAGE] Erreur critique migration Storage API: %s", e)

        # Continuer le setup malgré l'erreur (mode dégradé)

    _LOGGER.info("=" * 70)

    # ========================================

    # 🎯 AJOUT : Correcteur automatique de noms

    # ========================================

    try:

        await async_setup_sensor_name_fixer(hass)

        _LOGGER.info("✅ Correcteur automatique de noms activé")

    except Exception as e:

        _LOGGER.error(f"❌ Erreur activation correcteur de noms: {e}")

    # 🔧 Service manuel pour forcer la correction

    if not hass.services.has_service(DOMAIN, "fix_sensor_names"):

        async def handle_fix_sensor_names(call):

            """Service pour forcer la correction des noms."""

            try:

                fixed = await async_fix_all_long_sensors(hass)

                _LOGGER.info(f"✅ Service fix_sensor_names : {fixed} sensors corrigés")

            except Exception as e:

                _LOGGER.error(f"❌ Erreur service fix_sensor_names: {e}")

        hass.services.async_register(

            DOMAIN,

            "fix_sensor_names",

            handle_fix_sensor_names

        )

        _LOGGER.info("📋 Service 'fix_sensor_names' enregistré")

    # === PANEL HOME ASSISTANT ===

    async def register_panel_when_ready(*args):

        """Enregistre le panel dans la sidebar après démarrage HA."""

        await asyncio.sleep(3)  # Attendre que frontend soit prêt

        try:

            frontend.async_register_built_in_panel(

                hass,

                component_name="iframe",

                sidebar_title="⚡ Suivi Élec",

                sidebar_icon="mdi:lightning-bolt",

                frontend_url_path="home-suivi-elec",

                config={

                    "url": "/local/community/home_suivi_elec_ui/index.html"

                },

                require_admin=False,

            )

            _LOGGER.info("✅ Panel Home Suivi Élec enregistré")

        except Exception as e:

            _LOGGER.error("❌ Erreur enregistrement panel: %s", e)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, register_panel_when_ready)

    # ========================================

    # 📋 SERVICES HOME ASSISTANT

    # ========================================

    async def handle_generate_local_data(call: ServiceCall):

        """

        Service Home Assistant : `generate_local_data`

        Déclenche une détection automatique complète des capteurs d'énergie/power intégrés dans Home Assistant.

        Appelle la fonction run_detect_local, met à jour hass.data, et expose les nouveaux capteurs en backend.

        Journalise les erreurs et exceptions durant la détection.

        """
        try:
            capteurs_power = await run_detect_local(hass=hass, entry=entry)

            capteurs_power = capteurs_power or []

            storage_manager = hass.data.get(DOMAIN, {}).get("storage_manager")

            if not storage_manager:

                _LOGGER.error("[SERVICE] StorageManager non disponible, impossible de sauvegarder capteurs_power")
                
                return

            await storage_manager.save_capteurs_power(capteurs_power)
            
            _LOGGER.info(
            
                "[SERVICE] 💾 Catalogue capteurs_power sauvegardé en Storage (%s entrées)",
            
                len(capteurs_power),
            
            )

        except Exception as e:
            _LOGGER.exception("Erreur generate_local_data: %s", e)


    async def handle_generate_lovelace_auto(call: ServiceCall):

        """

        Service Home Assistant : `generate_lovelace_auto`

        Génère et expose automatiquement le dashboard Lovelace en utilisant la configuration backend (options métier).

        Appelle run_all pour créer la config Lovelace/YAML adaptée à la sélection de capteurs.

        """

        try:

            opts = hass.data[DOMAIN]["effective_options"]

            await run_all(hass, opts)

        except Exception as e:

            _LOGGER.exception("Erreur generate_lovelace_auto: %s", e)

    async def handle_generate_selection(call: ServiceCall):

        """

        Service Home Assistant : `generate_selection`

        Génère le mapping des capteurs sélectionnés pour synchronisation Utility Meter (YAML).

        PHASE 2.7: Utilise StorageManager pour récupérer la sélection.

        """

        try:

            storage_manager = hass.data.get(DOMAIN, {}).get("storage_manager")

            if not storage_manager:

                _LOGGER.error("[SERVICE] StorageManager non disponible")

                return

            selection = await storage_manager.get_capteurs_selection()

            def extract_ids(selection_dict):

                ids = set()

                for lst in selection_dict.values():

                    ids.update([c.get("entity_id") for c in lst if c.get("enabled")])

                return ids

            entity_ids = extract_ids(selection)

            _LOGGER.info("[SERVICE] %d capteurs activés extraits", len(entity_ids))

        except Exception as e:

            _LOGGER.exception("Erreur handle_generate_selection: %s", e)

    async def handle_copy_ui(call: ServiceCall):

        """

        Service Home Assistant : `copy_ui_files`

        Copie manuellement tous les fichiers UI statiques dans le répertoire Home Assistant pour assurer l'accès panel.

        Journalise les actions et erreurs d'IO.

        """

        _LOGGER.info("[SERVICE] copy_ui_files appelé manuellement")

        await copy_ui_files(hass)

        _LOGGER.info("[SERVICE] ✅ UI copiée avec succès")

    async def handle_reset_integration_sensor(call: ServiceCall):

        """

        Service Home Assistant : `reset_integration_sensor`

        Réinitialise un capteur d'intégration selon son entity_id, supprime les valeurs aberrantes ou historiques trop élevées.

        Utilise migration_cleanup, recharge la config si besoin, journalise tout le cycle.

        """

        entity_id = call.data.get("entity_id")

        threshold = call.data.get("threshold_kwh", 1000.0)

        if not entity_id:

            _LOGGER.error("[RESET] entity_id requis")

            return

        if not entity_id.startswith("sensor.hse_energy_"):

            _LOGGER.error("[RESET] entity_id doit commencer par sensor.hse_energy_")

            return

        try:

            from .migration_cleanup import migrate_cleanup_integration_sensors

            _LOGGER.info("[RESET] Nettoyage de %s (seuil: %.2f kWh)", entity_id, threshold)

            count = await migrate_cleanup_integration_sensors(hass, threshold_kwh=threshold)

            if count > 0:

                _LOGGER.info("[RESET] %d sensor(s) nettoyé(s)", count)

                await hass.config_entries.async_reload(entry.entry_id)

                _LOGGER.info("[RESET] ✅ Sensors réinitialisés avec succès")

            else:

                _LOGGER.warning("[RESET] Aucun sensor nettoyé (valeurs en dessous du seuil)")

        except Exception as e:

            _LOGGER.exception("[RESET] Erreur lors du reset: %s", e)

    async def handle_migrate_cleanup(call: ServiceCall):

        """

        Service Home Assistant : `migrate_cleanup`

        Nettoie tous les capteurs aberrants en une action globale, typiquement lors de migrations ou maintenance automatisée.

        Appelle migration_cleanup sur la base d'un seuil kWh configurable, recharge la configuration, journalise les résultats.

        """

        threshold = call.data.get("threshold_kwh", 1000.0)

        try:

            from .migration_cleanup import migrate_cleanup_integration_sensors

            _LOGGER.info("[MIGRATION] Lancement nettoyage automatique (seuil: %.2f kWh)", threshold)

            count = await migrate_cleanup_integration_sensors(hass, threshold_kwh=threshold)

            if count > 0:

                _LOGGER.info("[MIGRATION] %d sensor(s) nettoyé(s)", count)

                await hass.config_entries.async_reload(entry.entry_id)

                _LOGGER.info("[MIGRATION] ✅ Migration terminée avec succès")

            else:

                _LOGGER.info("[MIGRATION] Aucun sensor aberrant détecté")

        except Exception as e:

            _LOGGER.exception("[MIGRATION] Erreur lors de la migration: %s", e)

    # 🆕 PHASE 2.7: SERVICES STORAGE API

    async def handle_export_storage_backup(call: ServiceCall):

        """

        Service Home Assistant : `export_storage_backup`

        Exporte un backup manuel du Storage API vers fichiers JSON.

        """

        output_dir = call.data.get("output_dir")

        try:

            success = await async_export_storage_backup(hass, output_dir)

            if success:

                _LOGGER.info("[SERVICE] ✅ Backup Storage API exporté")

            else:

                _LOGGER.error("[SERVICE] ❌ Échec export backup")

        except Exception as e:

            _LOGGER.exception("[SERVICE] Erreur export_storage_backup: %s", e)

    async def handle_rollback_to_legacy(call: ServiceCall):

        """

        Service Home Assistant : `rollback_to_legacy`

        Service d'urgence pour revenir aux fichiers JSON legacy.

        ⚠️ Nécessite un redémarrage après exécution.

        """

        try:

            success = await async_rollback_to_legacy(hass)

            if success:

                _LOGGER.warning("[SERVICE] ✅ Rollback effectué - REDÉMARREZ Home Assistant")

            else:

                _LOGGER.info("[SERVICE] Aucun rollback nécessaire")

        except Exception as e:

            _LOGGER.exception("[SERVICE] Erreur rollback_to_legacy: %s", e)

    async def handle_get_storage_stats(call: ServiceCall):

        """

        Service Home Assistant : `get_storage_stats`

        Affiche les statistiques du Storage API dans les logs.

        """

        try:

            storage_manager = hass.data.get(DOMAIN, {}).get("storage_manager")

            if not storage_manager:

                _LOGGER.error("[SERVICE] StorageManager non disponible")

                return

            stats = await storage_manager.get_storage_stats()

            _LOGGER.info("=" * 60)

            _LOGGER.info("📊 STATISTIQUES STORAGE API")

            _LOGGER.info("=" * 60)

            _LOGGER.info("Version: %d", stats["version"])

            _LOGGER.info("")

            _LOGGER.info("User Config:")

            _LOGGER.info("  - Capteur référence: %s", "Oui" if stats["user_config"]["has_reference"] else "Non")

            _LOGGER.info("  - Options: %d", stats["user_config"]["options_count"])

            _LOGGER.info("")

            _LOGGER.info("Capteurs Sélection:")

            _LOGGER.info("  - Zones: %d", stats["capteurs_selection"]["zones"])

            _LOGGER.info("  - Total: %d", stats["capteurs_selection"]["total_sensors"])

            _LOGGER.info("  - Activés: %d", stats["capteurs_selection"]["enabled_sensors"])

            _LOGGER.info("  - Désactivés: %d", stats["capteurs_selection"]["disabled_sensors"])

            _LOGGER.info("")

            _LOGGER.info("Entités ignorées: %d", stats["ignored_entities"]["count"])

            _LOGGER.info("Cache mémoire: %d entrées", stats["cache_size"])

            _LOGGER.info("=" * 60)

        except Exception as e:

            _LOGGER.exception("[SERVICE] Erreur get_storage_stats: %s", e)

    # Enregistrement des services

    hass.services.async_register(DOMAIN, "generate_local_data", handle_generate_local_data)

    hass.services.async_register(DOMAIN, "generate_lovelace_auto", handle_generate_lovelace_auto)

    hass.services.async_register(DOMAIN, "generate_selection", handle_generate_selection)

    hass.services.async_register(DOMAIN, "copy_ui_files", handle_copy_ui)

    hass.services.async_register(DOMAIN, "reset_integration_sensor", handle_reset_integration_sensor)

    hass.services.async_register(DOMAIN, "migrate_cleanup", handle_migrate_cleanup)

    # 🆕 Services Storage API

    hass.services.async_register(DOMAIN, "export_storage_backup", handle_export_storage_backup)

    hass.services.async_register(DOMAIN, "rollback_to_legacy", handle_rollback_to_legacy)

    hass.services.async_register(DOMAIN, "get_storage_stats", handle_get_storage_stats)

    _LOGGER.info("✅ [SERVICES] %d services enregistrés", 9)

    # ========================================

    # 🌐 API REST

    # ========================================

    await manage_selection.async_setup_selection_api(hass)

    # API REST: doublons/ignored + best-per-device

    # ✅ NOUVELLE API UNIFIÉE (remplace progressivement les 18 endpoints)

    try:

        from .api.unified_api import HomeElecUnifiedAPIView

        hass.http.register_view(HomeElecUnifiedAPIView(hass))

        _LOGGER.info("✅ [API] API Unifiée enregistrée: /api/home_suivi_elec/{resource}")

    except Exception as e:

        _LOGGER.error("❌ [API] Erreur API Unifiée: %s", e)

    # ✅ API CONFIGURATION ÉTENDUE (méthodes POST)

    try:

        from .api.unified_api_extensions import HomeElecUnifiedConfigAPIView

        hass.http.register_view(HomeElecUnifiedConfigAPIView(hass))

        _LOGGER.info("✅ [API] API Configuration enregistrée: /api/home_suivi_elec/config/{action}")

    except Exception as e:

        _LOGGER.error("❌ [API] Erreur API Configuration: %s", e)

    class SetIgnoredEntityView(HomeAssistantView):

        """

        API REST pour marquer/démarquer une entité comme ignorée.

        PHASE 2.7: Utilise StorageManager.

        """

        url = "/api/home_suivi_elec/set_ignored_entity"

        name = "api:home_suivi_elec:set_ignored_entity"

        requires_auth = False

        cors_allowed = True

        def __init__(self, hass: HomeAssistant) -> None:

            self.hass = hass

        async def post(self, request):

            try:

                data = await request.json()

                entity_id = (data or {}).get("entity_id")

                ignore = bool((data or {}).get("ignore"))

                if not entity_id:

                    return self.json({"success": False, "error": "entity_id missing"}, status_code=400)

                storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")

                if not storage_manager:

                    return self.json({"success": False, "error": "StorageManager unavailable"}, status_code=500)

                if ignore:

                    await storage_manager.add_ignored_entity(entity_id)

                else:

                    await storage_manager.remove_ignored_entity(entity_id)

                ignored_entities = await storage_manager.get_ignored_entities()

                return self.json({"success": True, "ignored_entities": ignored_entities})

            except Exception as e:

                _LOGGER.exception("set_ignored_entity error: %s", e)

                return self.json({"success": False, "error": "internal"}, status_code=500)

    class ChooseBestForDeviceView(HomeAssistantView):

        """API REST pour choisir automatiquement le meilleur capteur d'un device."""

        url = "/api/home_suivi_elec/choose_best_for_device"

        name = "api:home_suivi_elec:choose_best_for_device"

        requires_auth = False

        cors_allowed = True

        def __init__(self, hass: HomeAssistant) -> None:

            self.hass = hass

        async def post(self, request):

            try:

                data = await request.json()

                device_id = (data or {}).get("device_id")

                if not device_id:

                    return self.json({"success": False, "error": "device_id missing"}, status_code=400)

                idx: Dict[str, Dict[str, Any]] = {}

                try:

                    idx = await manage_selection.async_get_capteurs_index(self.hass)

                except Exception:

                    idx = (self.hass.data.get(DOMAIN) or {}).get("capteurs_index") or {}

                members = [eid for eid, info in (idx or {}).items() if (info or {}).get("device_id") == device_id]

                if not members:

                    return self.json({"success": True, "best": None, "ignored": []})

                if len(members) == 1:

                    return self.json({"success": True, "best": members[0], "ignored": []})

                def score(info: Dict[str, Any]) -> int:

                    s = 0

                    unit = info.get("unit_of_measurement") or info.get("unit")

                    if unit == "W":

                        s += 5

                    if info.get("state_class") == "measurement":

                        s += 3

                    if info.get("is_premium"):

                        s += 2

                    if info.get("ui_checked"):

                        s += 1

                    if not info.get("ignored", False):

                        s += 1

                    return s

                best: Optional[str] = None

                best_s = -999

                for eid in members:

                    info = (idx or {}).get(eid) or {}

                    sc = score(info)

                    if sc > best_s:

                        best = eid

                        best_s = sc

                storage_manager = self.hass.data.get("home_suivi_elec", {}).get("storage_manager")

                if storage_manager:

                    for eid in members:

                        if eid != best:

                            await storage_manager.add_ignored_entity(eid)

                others = [eid for eid in members if eid != best]

                return self.json({"success": True, "best": best, "ignored": others})

            except Exception as e:

                _LOGGER.exception("choose_best_for_device error: %s", e)

                return self.json({"success": False, "error": "internal"}, status_code=500)

    # (reste du fichier identique à la version précédente)

    # ✅ AJOUT: refresh initial des totals rooms/types après setup
    try:
        from .group_totals import refresh_group_totals

        hass.async_create_task(refresh_group_totals(hass))
        _LOGGER.info("[GROUP-TOTALS] Initial refresh scheduled")
    except Exception as e:
        _LOGGER.exception("[GROUP-TOTALS] Failed to schedule initial refresh: %s", e)

    return True
