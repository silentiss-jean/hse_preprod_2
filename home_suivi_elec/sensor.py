# -*- coding: utf-8 -*-

"""Plateforme sensor pour Home Suivi Élec — Phase 3.0."""

import logging

from typing import Iterable, List, Optional, Set, Tuple

from homeassistant.core import HomeAssistant, callback

from homeassistant.config_entries import ConfigEntry

from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

def _uid(ent) -> Optional[str]:
    # HA Entities exposent généralement unique_id (property) + stockage interne _attr_unique_id
    return getattr(ent, "unique_id", None) or getattr(ent, "_attr_unique_id", None)

def _get_added_uids(hass: HomeAssistant) -> Set[str]:
    domain_data = hass.data.setdefault(DOMAIN, {})
    return domain_data.setdefault("_added_uids", set())

# ======================================================================
# ⚙️ DÉDUP HSE : CONFIG MODIFIÉE
# 
# - PAS de seed depuis l'entity_registry au démarrage (MODIFIÉ)
# - Dédup désactivée pour permettre régénération (MODIFIÉ)
# - Les capteurs existants dans le registry sont réanimés (NOUVEAU)
# ======================================================================
# Anciennement :
# - MODE DEV : pas de seed, pas de dédup (tous les sensors recréés à chaque reboot)
# - MODE PROD : seed registry + dédup stricte par unique_id
# 
# La config actuelle équivaut à :
# - PAS de seed registry (pour permettre régénération)
# - Dédup désactivée pour tous les types de capteurs

def _seed_added_uids_from_registry(hass: HomeAssistant) -> None:
    """
    Seed du set runtime avec les entités déjà présentes.
    
    ⚠️ DÉSACTIVÉ dans async_setup_entry pour permettre la régénération.
    """
    added = _get_added_uids(hass)
    added.clear()
    
    ent_reg = er.async_get(hass)
    for entry in ent_reg.entities.values():
        if entry.domain != "sensor":
            continue
        if entry.platform != DOMAIN:
            continue
        if entry.unique_id:
            added.add(entry.unique_id)
    
    LOGGER.info("🧯 [DEDUP] seed: %s unique_id déjà présents", len(added))

def _dedupe_by_uid(
    hass: HomeAssistant, sensors: Iterable, kind: str
) -> Tuple[List, Set[str], int]:
    """
    Filtre les entités déjà ajoutées (par unique_id).
    
    MODIFIÉ: Dédup désactivée pour permettre régénération après redémarrage.
    """
    added = _get_added_uids(hass)
    
    out: List = []
    new_uids: Set[str] = set()
    skipped = 0
    missing_uid = 0
    
    for e in list(sensors or []):
        uid = _uid(e)
        if not uid:
            # Pas de dédup possible => on laisse passer, mais on log
            missing_uid += 1
            out.append(e)
            continue
        
        # 🔧 MODIFICATION CRITIQUE: Dédup désactivée pour tous les types
        if uid in added:
            LOGGER.debug(
                "🔄 [DEDUP] %s: entité %s existe dans registry, réanimation autorisée",
                kind,
                uid
            )
            # NE PAS skip - on laisse passer pour régénération
        
        out.append(e)
        new_uids.add(uid)
    
    if skipped:
        LOGGER.info("🧯 [DEDUP] %s: %s entités déjà ajoutées ignorées", kind, skipped)
    if missing_uid:
        LOGGER.warning(
            "🧯 [DEDUP] %s: %s entités sans unique_id (pas de dédup)",
            kind,
            missing_uid,
        )
    
    return out, new_uids, skipped

def _take_pool(hass: HomeAssistant, pending_key: str, stable_key: str) -> list:
    """
    Récupère la liste à ajouter.
    
    - Priorité au pending (pop => consommé une fois)
    - Fallback sur stable (get), mais dédupliqué ensuite
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    sensors = domain_data.pop(pending_key, None)
    if sensors is None:
        sensors = domain_data.get(stable_key, []) or []
    return sensors

# NOTE: Cette fonction _process() globale n'est JAMAIS utilisée car elle est
# redéfinie à l'intérieur de async_setup_entry(). Elle est conservée pour
# référence mais pourrait être supprimée.
def _process(kind: str, pending_key: str, stable_key: str) -> None:
    """Version globale NON UTILISÉE - voir version dans async_setup_entry()."""
    # Cette fonction ne peut pas fonctionner ici car hass et async_add_entities
    # ne sont pas accessibles à ce niveau
    pass

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry — EVENT-DRIVEN."""
    LOGGER.info("🎯 [EVENT-DRIVEN] Setup sensor platform - Attente events...")
    
    # 🔧 MODIFICATION CRITIQUE: Ne plus seed depuis le registry
    # _seed_added_uids_from_registry(hass)  # DÉSACTIVÉ
    
    # À la place, on vide le set pour permettre régénération complète
    _get_added_uids(hass).clear()
    LOGGER.info("🧯 [DEDUP] Set runtime vidé pour régénération complète")
    
    EVENT_TO_KEYS = {
        "hse_energy_sensors_ready": ("energy_sensors_pending", "energy_sensors", "energy"),
        "hse_power_sensors_ready": ("live_power_sensors_pending", "live_power_sensors", "power"),
        "hse_power_energy_sensors_ready": ("power_energy_sensors_pending", "power_energy_sensors", "power_energy"),
        "hse_cost_sensors_ready": ("cost_sensors_pending", "cost_sensors", "cost"),
    }
    
    def _process(kind: str, pending_key: str, stable_key: str) -> None:
        sensors = _take_pool(hass, pending_key, stable_key)
        
        # --- DEBUG: état brut avant dédup
        raw_count = len(list(sensors or []))
        raw_uids = []
        raw_names = []
        for e in list(sensors or [])[:8]:
            raw_uids.append(_uid(e))
            raw_names.append(getattr(e, "name", None) or getattr(e, "_attr_name", None))
        
        LOGGER.info(
            "🧩 [EVENT-RAW] %s: pool=%s/%s raw_count=%s sample_uids=%s sample_names=%s",
            kind,
            pending_key,
            stable_key,
            raw_count,
            raw_uids,
            raw_names,
        )
        
        sensors, new_uids, skipped = _dedupe_by_uid(hass, sensors, kind)
        
        # --- DEBUG: résultat après dédup
        LOGGER.info(
            "🧩 [EVENT-DEDUP] %s: kept=%s skipped=%s new_uids=%s",
            kind,
            len(sensors or []),
            skipped,
            list(new_uids)[:10],
        )
        
        if not sensors:
            LOGGER.warning("⚠️ [EVENT] %s: aucun sensor à ajouter (pool vide ou tout filtré)", kind)
            return
        
        # Ajout HA
        try:
            async_add_entities(sensors, True)
            
            # Marquer ajouté après l'appel (évite de "brûler" des UID si une exception arrive avant)
            _get_added_uids(hass).update(new_uids)
            LOGGER.info("✅ [EVENT-PROCESSED] %s: %s sensors ajoutés", kind, len(sensors))
        except Exception as e:
            LOGGER.exception("❌ [EVENT-ERROR] Échec ajout sensors %s: %s", kind, e)
    
    @callback
    def on_hse_sensors_ready(event):
        try:
            info = EVENT_TO_KEYS.get(event.event_type)
            if not info:
                LOGGER.warning("⚠️ [EVENT] event inconnu: %s", event.event_type)
                return
            
            pending_key, stable_key, kind = info
            LOGGER.info("📣 [EVENT] Réception event: %s", event.event_type)
            _process(kind, pending_key, stable_key)
        except Exception as e:
            LOGGER.exception("❌ [EVENT-ERROR] %s", e)
    
    # listeners
    for ev in EVENT_TO_KEYS.keys():
        hass.bus.async_listen(ev, on_hse_sensors_ready)
    
    LOGGER.info("🎧 [EVENT-DRIVEN] Listeners activés - En attente des events sensors...")
    
    # backup flush (startup): on tente d'ajouter ce qui est déjà prêt
    LOGGER.info("🔄 [STARTUP] Tentative flush des pools existants...")
    for _ev, (pending_key, stable_key, kind) in EVENT_TO_KEYS.items():
        _process(kind, pending_key, stable_key)
