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

from .manage_selection_views import HSESensorsPublicView, SensorMappingView

from .api.unified_api_extensions import ValidationActionView, HomeElecUnifiedConfigAPIView, HomeElecMigrationHelpersView, CacheClearView, CacheInvalidateEntityView

# ✅ PHASE 2.7: Import StorageManager et migration

from .storage_manager import StorageManager

from .migration_storage import async_migrate_storage, async_export_storage_backup, async_rollback_to_legacy

_LOGGER = logging.getLogger(__name__)

# ⚠️ DEPRECATED - Utiliser StorageManager à la place

USER_STORE_KEY = f"{DOMAIN}_user_config_v1"

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

    store = Store(hass, 1, USER_STORE_KEY)  # Garde pour rétrocompatibilité temporaire

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

    class DiagnosticsView(HomeAssistantView):

        """API REST pour diagnostics natifs HSE."""

        url = "/api/home_suivi_elec/get_diagnostics"

        name = "api:home_suivi_elec:get_diagnostics"

        requires_auth = False

        cors_allowed = True

        def __init__(self, hass: HomeAssistant) -> None:

            self.hass = hass

        async def get(self, request):

            """

            Diagnostic natif HSE (remplace UtilityMeter) :

            Liste tous les capteurs HSE activés, affiche leur état, statut, et remonte alertes/anomalies.

            """

            try:

                from .manage_selection_views import _load_json, CAPTEURS_POWER_PATH, _enrich_device_info

                import os

                import asyncio

                loop = asyncio.get_running_loop()

                sensors = []

                if os.path.exists(CAPTEURS_POWER_PATH):

                    sensors = await loop.run_in_executor(None, lambda: _load_json(CAPTEURS_POWER_PATH))

                sensors = _enrich_device_info(self.hass, sensors or [])

                sources = []

                alerts = []

                dump_sensors = []

                for sensor in sensors:

                    eid = sensor.get("entity_id")

                    friendly = sensor.get("friendly_name", eid)

                    state_obj = self.hass.states.get(eid)

                    state = state_obj.state if state_obj else "unavailable"

                    unit = sensor.get("unit", "?")

                    last_changed = state_obj.last_changed.isoformat() if state_obj else None

                    status = "✅ OK"

                    data_type = "numérique"

                    action = "-"

                    anomaly = None

                    if state in ("unknown", "unavailable"):

                        status = "❌ Indisponible" if state == "unavailable" else "⚠️ Unknown"

                        anomaly = status

                        alerts.append({

                            "type": "warning",

                            "entity_id": eid,

                            "message": f"Capteur {eid} est {state}"

                        })

                    else:

                        try:

                            float(state)

                        except Exception:

                            status = "⚠️ Non numérique"

                            data_type = "chaîne"

                            action = "Normaliser via template"

                            anomaly = status

                            alerts.append({

                                "type": "error",

                                "entity_id": eid,

                                "message": f"Capteur {eid} publie une chaîne: '{state}'"

                            })

                    sources.append({

                        "entity_id": eid,

                        "friendly_name": friendly,

                        "state": state,

                        "unit": unit,

                        "status": status,

                        "data_type": data_type,

                        "last_changed": last_changed,

                        "action": action

                    })

                    dump_sensors.append({

                        "entity_id": eid,

                        "nom": friendly,

                        "zone": sensor.get("zone"),

                        "type": sensor.get("type"),

                        "integration": sensor.get("integration"),

                        "enabled": sensor.get("enabled", True),

                        "anomaly": anomaly

                    })

                errors = len([a for a in alerts if a["type"] == "error"])

                warnings = len([a for a in alerts if a["type"] == "warning"])

                global_status = "error" if errors > 0 else "warning" if warnings > 0 else "ok"

                dump_global = {

                    "total_detected": len(sensors),

                    "total_enabled": len([s for s in dump_sensors if s["enabled"]]),

                    "total_non_enabled": len([s for s in dump_sensors if not s["enabled"]]),

                    "sensors": dump_sensors

                }

                return self.json({

                    "sources": sources,

                    "alerts": alerts,

                    "global_status": global_status,

                    "dump": dump_global

                })

            except Exception as e:

                _LOGGER.exception("Erreur get_diagnostics: %s", e)

                return self.json({"error": str(e)}, status_code=500)

    class EntityNameRegistryView(HomeAssistantView):

        """GET /api/home_suivi_elec/entity_name_registry - Registry nom court → nom complet"""

        url = "/api/home_suivi_elec/entity_name_registry"

        name = "api:home_suivi_elec:entity_name_registry"

        requires_auth = False

        cors_allowed = True

        def __init__(self, hass: HomeAssistant) -> None:

            self.hass = hass

        async def get(self, request):

            try:

                return self.json({

                    "success": True,

                    "mappings": {},

                    "stats": {"total": 0, "version": "1.0", "created": datetime.now().isoformat()},

                })

            except Exception as e:

                _LOGGER.exception("[ENTITY-NAME-REGISTRY] GET failed: %s", e)

                return self.json({"success": False, "error": str(e)}, status_code=500)

    class DiagnosticGroupsView(HomeAssistantView):

        """GET /api/home_suivi_elec/diagnostic_groups - Regroupement parent→enfants + orphelins"""

        url = "/api/home_suivi_elec/diagnostic_groups"

        name = "api:home_suivi_elec:diagnostic_groups"

        requires_auth = False

        cors_allowed = True

        def __init__(self, hass: HomeAssistant) -> None:

            self.hass = hass

        async def get(self, request):

            try:

                states = self.hass.states.async_all("sensor")

                parents: List[Dict[str, Any]] = []

                children_by_parent: Dict[str, List[Dict[str, Any]]] = {}

                orphans: List[Dict[str, Any]] = []

                def is_parent(eid: str) -> bool:

                    if not eid.startswith("sensor.hse_live_"):

                        return False

                    return not (eid.endswith("_h") or eid.endswith("_d") or eid.endswith("_w") or eid.endswith("_m") or eid.endswith("_y"))

                def parent_key_from_child(eid: str) -> str | None:

                    if not eid.startswith("sensor.hse"):

                        return None

                    if not (eid.endswith("_h") or eid.endswith("_d") or eid.endswith("_w") or eid.endswith("_m") or eid.endswith("_y")):

                        return None

                    parent_expected = eid[:-2]

                    if parent_expected in children_by_parent:

                        return parent_expected

                    return None

                for s in states:

                    eid = s.entity_id

                    if is_parent(eid):

                        parents.append({

                            "entity_id": eid,

                            "state": s.state,

                            "friendly_name": s.attributes.get("friendly_name", eid),

                        })

                        children_by_parent[eid] = []

                for s in states:

                    eid = s.entity_id

                    if eid.startswith("sensor.hse_") and (eid.endswith("_h") or eid.endswith("_d") or eid.endswith("_w") or eid.endswith("_m") or eid.endswith("_y")):

                        p = parent_key_from_child(eid)

                        if p and p in children_by_parent:

                            children_by_parent[p].append({

                                "entity_id": eid,

                                "state": s.state,

                                "friendly_name": s.attributes.get("friendly_name", eid),

                            })

                        else:

                            orphans.append({

                                "entity_id": eid,

                                "state": s.state,

                                "friendly_name": s.attributes.get("friendly_name", eid),

                            })

                stats = {

                    "parents": len(parents),

                    "children": sum(len(v) for v in children_by_parent.values()),

                    "orphans": len(orphans),

                }

                return self.json({

                    "success": True,

                    "parents": parents,

                    "children_by_parent": children_by_parent,

                    "orphans": orphans,

                    "stats": stats,

                })

            except Exception as e:

                _LOGGER.exception("diagnostic_groups error: %s", e)

                return self.json({"success": False, "error": str(e)}, status_code=500)

    # Import des vues de manage_selection_views

    from .manage_selection_views import (

        AutoSelectBestSensorsView,

        GetSensorQualityScoresView

    )

    # Enregistrement des vues API REST

    hass.http.register_view(SetIgnoredEntityView(hass))

    hass.http.register_view(ChooseBestForDeviceView(hass))

    hass.http.register_view(DiagnosticsView(hass))

    hass.http.register_view(SuiviElecProxyView())

    hass.http.register_view(AutoSelectBestSensorsView(hass))

    hass.http.register_view(GetSensorQualityScoresView(hass))

    hass.http.register_view(HSESensorsPublicView(hass))

    hass.http.register_view(ValidationActionView(hass))

    hass.http.register_view(PingView())

    hass.http.register_view(EntityNameRegistryView(hass))

    hass.http.register_view(DiagnosticGroupsView(hass))

    hass.http.register_view(HomeElecMigrationHelpersView(hass))

    hass.http.register_view(SensorMappingView(hass))

    hass.http.register_view(CacheClearView(hass))

    hass.http.register_view(CacheInvalidateEntityView(hass))

    _LOGGER.info("✅ [API] Toutes les vues REST enregistrées")

    try:

        await scan_sets(hass)

    except TypeError:

        scan_sets(hass)

    if hass.data[DOMAIN]["options"].get(CONF_AUTO_GENERATE, True):

        await run_all(hass, hass.data[DOMAIN]["options"])

    # ========================================

    # 🎯 NOUVEAU: Setup HSE AVANT sensor.py

    # ========================================

    async def setup_hse_before_sensor_platform():

        """Prépare les pools HSE AVANT que sensor.py ne les consomme."""

        _LOGGER.info("[INIT] ⏳ Attente démarrage HA...")

        # Attendre que HA soit démarré

        event = asyncio.Event()

        @callback

        def on_started(event_data):

            event.set()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, on_started)

        await event.wait()

        # Court délai pour que tous les états soient disponibles

        await asyncio.sleep(3)

        _LOGGER.info("[INIT] ✅ HA démarré, préparation pools HSE...")

        # ✅ VÉRIFIER que StorageManager est bien disponible

        storage_manager = hass.data.get(DOMAIN, {}).get("storage_manager")

        if not storage_manager:

            _LOGGER.error("[INIT] ❌ StorageManager non disponible dans hass.data[%s]", DOMAIN)

            return

        try:

            # 1. Détection locale + stockage du catalogue
            _LOGGER.info("[INIT] 🔍 Lancement détection locale...")

            capteurs_power = await run_detect_local(hass=hass, entry=entry)

            _LOGGER.info("[INIT] ✅ Détection locale terminée (%s capteurs)", len(capteurs_power or []))

            storage_manager = hass.data.get(DOMAIN, {}).get("storage_manager")

            if storage_manager and capteurs_power:

                await storage_manager.save_capteurs_power(capteurs_power)

                _LOGGER.info("[INIT] 💾 Catalogue capteurs_power sauvegardé en Storage (%s entrées)", len(capteurs_power))

            # 2. Capteur de référence externe

            _LOGGER.info("[INIT] 📌 Préparation capteur de référence...")

            await _ensure_reference_sensors(hass, entry)

            # 3. Energy tracking (crée les energy sensors)

            _LOGGER.info("[INIT] ⚡ Setup energy tracking...")

            await async_setup_energy_tracking(hass, entry)

            # 4. Power monitoring (crée les power sensors)

            _LOGGER.info("[INIT] 🔌 Setup power monitoring...")

            try:

                from .power_monitoring import async_setup_power_monitoring

                await async_setup_power_monitoring(hass, entry)

            except Exception as e:

                _LOGGER.exception("[INIT] Erreur power monitoring: %s", e)

            # 5. Sensor Sync Manager

            _LOGGER.info("[INIT] 🔄 Setup sensor sync manager...")

            try:

                from .sensor_sync_manager import SensorSyncManager

                sync_manager = SensorSyncManager(hass)

                hass.data[DOMAIN]["sync_manager"] = sync_manager

                await sync_manager.start()

                await manage_selection.async_setup_selection_api(hass, sync_manager)

            except Exception as e:

                _LOGGER.exception("[INIT] Erreur sensor sync manager: %s", e)

            # 5.5. Cost Sensors (crée les cost sensors)
            _LOGGER.info("[INIT] 💰 Setup cost sensors...")
            try:
                from .cost_tracking import create_cost_sensors
                from datetime import datetime
                
                cost_sensors = await create_cost_sensors(hass)
                
                if cost_sensors:
                    hass.data[DOMAIN]["cost_sensors_pending"] = cost_sensors
                    
                    # Déclencher l'event pour sensor.py
                    hass.bus.async_fire(
                        "hse_cost_sensors_ready",
                        {
                            "type": "cost",
                            "count": len(cost_sensors),
                            "timestamp": datetime.now().isoformat(),
                        },
                    )
                    
                    _LOGGER.info("[INIT] ✅ %d capteurs coût créés et enregistrés", len(cost_sensors))
                else:
                    _LOGGER.info("[INIT] ⚠️ Aucun capteur coût à créer (pas de sensors energy)")
                    
            except Exception as e:
                _LOGGER.exception("[INIT] Erreur cost tracking: %s", e)


            # 6. Vérifier que les pools sont bien remplis

            domain = hass.data.get(DOMAIN, {})

            energy_count = len(domain.get("energy_sensors", []))

            power_count = len(domain.get("live_power_sensors", []))

            cost_count = len(domain.get("cost_sensors_pending", [])) or len(domain.get("cost_sensors", []))

            _LOGGER.info(

                "[INIT] 📊 Pools HSE prêts : %d energy, %d power, %d cost",

                energy_count,

                power_count,

                cost_count,

            )

            if energy_count == 0 and power_count == 0:

                _LOGGER.warning(

                    "[INIT] ⚠️ POOLS VIDES - Vérifiez la configuration !"

                )

        except Exception as e:

            _LOGGER.exception("[INIT] ❌ Erreur critique préparation pools HSE: %s", e)

        # 7. MAINTENANT charger la plateforme sensor.py

        _LOGGER.info("[INIT] 🚀 Chargement plateforme sensor...")

        await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

        _LOGGER.info("[INIT] ✅ Plateforme sensor chargée - Capteurs HSE disponibles")

    # ✅ LANCER LA TÂCHE

    asyncio.create_task(setup_hse_before_sensor_platform())

    # ✅ GARDER _delayed_start

    asyncio.create_task(_delayed_start(hass, entry))

    # Copie UI

    loop = asyncio.get_running_loop()

    src = hass.config.path("custom_components", "home_suivi_elec", "web_static")

    dst = hass.config.path("www", "community", "home_suivi_elec_ui")

    await loop.run_in_executor(None, lambda: _copy_ui_fresh_complete(src, dst))

    _LOGGER.info("[SETUP-ENTRY] ✅ Home Suivi Élec setup terminé - sensors seront chargés après détection")

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    """Nettoie les pools HSE et décharge les plateformes."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:

        domain = hass.data.get(DOMAIN, {})

        for key in [

            "cost_sensors_pending",

            "cost_sensors",

            "_added_cost_uids",

            "energy_sensors_pending",

            "energy_sensors",

            "live_power_sensors_pending",

            "live_power_sensors",

            "power_energy_sensors_pending",

            "power_energy_sensors",

        ]:

            domain.pop(key, None)

    return unload_ok

async def _delayed_start(hass: HomeAssistant, entry: ConfigEntry, timeout: int = 60):

    """Fallback si détection initiale échoue."""

    await asyncio.sleep(timeout)

    _LOGGER.info(f"[INIT] Timeout atteint ({timeout}s), lancement fallback detection/selection")

    try:

        await run_detect_local(hass=hass, entry=entry)

    except Exception as e:

        _LOGGER.exception("Erreur fallback detection/selection: %s", e)

def _copy_ui_fresh_complete(src, dst):

    """Copie UI en mode 'fresh complete'."""

    if not os.path.exists(src):

        _LOGGER.warning(f"[COPY_UI] Source introuvable: {src}")

        return

    if os.path.exists(dst):

        try:

            shutil.rmtree(dst)

            _LOGGER.info(f"[COPY_UI] Dossier cible supprimé complètement: {dst}")

        except Exception as e:

            _LOGGER.error(f"[COPY_UI] Erreur suppression {dst}: {e}")

            return

    try:

        shutil.copytree(src, dst)

        _LOGGER.info(f"[COPY_UI] ✅ Copie fraîche complète: {src} → {dst}")

    except Exception as e:

        _LOGGER.exception(f"[COPY_UI] Erreur copytree: {e}")

async def copy_ui_files(hass: HomeAssistant):

    """Service de copie UI manuelle."""

    loop = asyncio.get_running_loop()

    src = hass.config.path("custom_components", "home_suivi_elec", "web_static")

    dst = hass.config.path("www", "community", "home_suivi_elec_ui")

    await loop.run_in_executor(None, lambda: _copy_ui_fresh_complete(src, dst))

@callback

def async_get_options_flow(config_entry: ConfigEntry):

    return HomeSuiviElecOptionsFlow(config_entry)

# ============================================================================

# ENERGY TRACKING - Phase 2

# ============================================================================

async def load_capteurs_selection(hass: HomeAssistant) -> list[dict]:
    """
    Charge les capteurs sélectionnés.
    PHASE 2.7: Utilise StorageManager + fusion avec capteurs power (catalog) stocké en Storage.
    """
    from .const import DOMAIN

    domain_data = hass.data.get(DOMAIN, {})
    
    storage_manager = domain_data.get("storage_manager")

    if not storage_manager:
    
        _LOGGER.error("[LOAD-SELECTION] StorageManager non disponible (hass.data[%s])", DOMAIN)
    
        return []

    # 1) Sélection (zones -> liste de dict)

    selection_data = await storage_manager.get_capteurs_selection()

    # 2) Catalogue power/energy détecté (liste de dict)

    power_data = await storage_manager.get_capteurs_power()

    _LOGGER.info("[LOAD-SELECTION] selection zones=%s", len(selection_data or {}))
    _LOGGER.info("[LOAD-SELECTION] catalogue power=%s", len(power_data or []))


    def _get_entity_id(d: dict) -> str | None:

        # Supporte plusieurs variantes (selon les générations de JSON / détection)

        return d.get("entity_id") or d.get("entityid") or d.get("entityId")

    power_index: dict[str, dict] = {}

    for item in power_data or []:

        if not isinstance(item, dict):

            continue

        entity_id = _get_entity_id(item)

        if entity_id:

            power_index[entity_id] = item

    result: list[dict] = []

    for _, items in (selection_data or {}).items():
        if not isinstance(items, list):
            continue

        for sensor in items:
            if not isinstance(sensor, dict) or not sensor.get("enabled", False):
                continue

            entity_id = _get_entity_id(sensor)
            if not entity_id:
                continue

            src = power_index.get(entity_id)
            if src:
                merged = dict(src)
                merged.update(sensor)          # la sélection peut surcharger certains champs
                merged["enabled"] = True       # forcer cohérence
                result.append(merged)
            else:
                _LOGGER.debug("[SKIP] %s absent du catalogue power (Storage)", entity_id)

    _LOGGER.info("%s capteurs chargés", len(result))
    return result

async def async_setup_energy_tracking(hass: HomeAssistant, entry: ConfigEntry):

    """Configure le tracking d'énergie (Phase 2)."""

    from .energy_tracking import create_energy_sensors

    _LOGGER.info("🔋 [PHASE 2] Configuration Energy Tracking...")

    capteurs_selection = await load_capteurs_selection(hass)

    _LOGGER.info(f"🔍 [DEBUG] capteurs_selection: {len(capteurs_selection)} capteurs")

    if capteurs_selection:

        _LOGGER.debug(f"🔍 [DEBUG] Premier capteur: {capteurs_selection[0]}")

    if not capteurs_selection:

        # Cas event-driven: si une référence externe a déjà injecté des sensors,

        # on émet quand même l'event pour que sensor.py les ajoute.

        existing = hass.data.get(DOMAIN, {}).get("energy_sensors", [])

        if existing:

            from datetime import datetime

            hass.bus.async_fire("hse_energy_sensors_ready", {

                "entity_ids": [s.entity_id for s in existing if getattr(s, "entity_id", None)],

                "count": len(existing),

                "type": "energy",

                "timestamp": datetime.now().isoformat()

            })

            _LOGGER.info("📡 [EVENT] hse_energy_sensors_ready émis (référence seule)")

        else:

            _LOGGER.info("ℹ️ Aucun capteur sélectionné, skip energy tracking")

        return

    _LOGGER.info(f"📊 {len(capteurs_selection)} capteurs à tracker")

    try:

        _LOGGER.info("🔋 [DEBUG] Appel create_energy_sensors...")

        energy_sensors = await create_energy_sensors(hass, capteurs_selection)

        _LOGGER.info(f"🔋 [DEBUG] Retour create_energy_sensors: {len(energy_sensors or [])}")

    except Exception as e:

        _LOGGER.exception(f"❌ [ENERGY-TRACKING] Erreur création sensors: {e}")

        energy_sensors = []

    if energy_sensors is None:

        _LOGGER.error("❌ create_energy_sensors a retourné None")

        energy_sensors = []

    if not energy_sensors:

        _LOGGER.warning("⚠️ Aucun sensor d'énergie créé")

        return

    _LOGGER.info(f"✅ {len(energy_sensors)} sensors d'énergie créés")

    if DOMAIN not in hass.data:

        hass.data[DOMAIN] = {}

    existing = hass.data.get(DOMAIN, {}).get("energy_sensors", [])

    merged = _merge_entities_unique(existing, energy_sensors)

    hass.data[DOMAIN]["energy_sensors"] = merged

    _LOGGER.info(f"💾 [DEBUG] Stocké {len(merged)} sensors dans hass.data (merged)")

    from datetime import datetime

    hass.bus.async_fire("hse_energy_sensors_ready", {

        "entity_ids": [s.entity_id for s in merged if getattr(s, "entity_id", None)],

        "count": len(merged),

        "type": "energy",

        "timestamp": datetime.now().isoformat()

    })

    _LOGGER.info(f"📡 [EVENT] hse_energy_sensors_ready émis")

    try:

        energy_count = sum(

            1 for s in merged

            if hasattr(s, 'extra_state_attributes') and s.extra_state_attributes.get('source_type') == 'energy'

        )

        power_count = sum(

            1 for s in merged

            if hasattr(s, 'extra_state_attributes') and s.extra_state_attributes.get('source_type') == 'power'

        )

        virtual_count = sum(

            1 for s in merged

            if hasattr(s, 'extra_state_attributes') and s.extra_state_attributes.get('is_virtual', False)

        )

        _LOGGER.info(

            f"📈 Répartition: "

            f"{energy_count} energy (delta), "

            f"{power_count} power (intégration), "

            f"{virtual_count} virtuels"

        )

    except Exception as e:

        _LOGGER.exception(f"❌ Erreur calcul stats: {e}")

    _LOGGER.info("🔋 [PHASE 2] Energy Tracking configuré avec succès")
