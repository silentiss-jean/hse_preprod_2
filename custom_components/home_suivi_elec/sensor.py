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
# But: permettre la régénération (dev) tout en évitant les doublons qui
# font spammer async_add_entities ou créent des erreurs "already exists".
#
# Choix "safe":
# - energy/power/cost: dédup OFF (comportement historique), mais on log.
# - room_totals/type_totals: dédup ON (ces capteurs sont 100% dérivés,
#   et peuvent être regénérés souvent via refresh_group_totals).
# ======================================================================


def _seed_added_uids_from_registry(hass: HomeAssistant) -> None:
    """Seed du set runtime avec les entités déjà présentes."""
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
    hass: HomeAssistant,
    sensors: Iterable,
    kind: str,
    *,
    enable_dedup: bool,
) -> Tuple[List, Set[str], int]:
    """Filtre les entités déjà ajoutées (par unique_id).

    - Si enable_dedup=False: on laisse passer (régénération), mais on log.
    - Si enable_dedup=True: on skip les unique_id déjà vus dans _added_uids.
    """
    added = _get_added_uids(hass)

    out: List = []
    new_uids: Set[str] = set()
    skipped = 0
    missing_uid = 0

    for e in list(sensors or []):
        uid = _uid(e)
        if not uid:
            missing_uid += 1
            out.append(e)
            continue

        if uid in added:
            if enable_dedup:
                skipped += 1
                continue

            LOGGER.debug(
                "🔄 [DEDUP-OFF] %s: entité %s déjà vue, réanimation autorisée",
                kind,
                uid,
            )

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


async def _reconcile_cost_sensors(hass: HomeAssistant) -> list:
    """Recrée les capteurs coût persistés au démarrage (réconciliation)."""
    try:
        mgr = hass.data.get(DOMAIN, {}).get("storage_manager")
        if not mgr:
            LOGGER.warning("[COST-RECONCILE] StorageManager non disponible, skip")
            return []

        user_cfg = await mgr.get_user_config()
        if not user_cfg.get("enable_cost_sensors_runtime"):
            LOGGER.info("[COST-RECONCILE] Runtime désactivé, skip")
            return []

        cost_ha_map = await mgr.get_cost_ha_config()
        if not cost_ha_map:
            LOGGER.info("[COST-RECONCILE] Aucun capteur coût persisté")
            return []

        enabled_sources = {
            entity_id: cfg
            for entity_id, cfg in cost_ha_map.items()
            if isinstance(cfg, dict) and cfg.get("enabled")
        }

        if not enabled_sources:
            LOGGER.info("[COST-RECONCILE] Aucun capteur coût enabled")
            return []

        LOGGER.info("[COST-RECONCILE] %d sources à réconcilier", len(enabled_sources))

        from .cost_tracking import get_pricing_config

        pricing = get_pricing_config(hass)
        current_type = pricing.get("type_contrat", "fixe")

        needs_migration = False
        for entity_id, cfg in enabled_sources.items():
            stored_type = cfg.get("type_contrat", "fixe")
            if stored_type != current_type:
                LOGGER.warning(
                    "[COST-RECONCILE] Type contrat changé (%s → %s) pour %s",
                    stored_type,
                    current_type,
                    entity_id,
                )
                needs_migration = True
                break

        if needs_migration:
            LOGGER.warning(
                "[COST-RECONCILE] Migration nécessaire (changement contrat), "
                "veuillez régénérer manuellement les capteurs coût"
            )
            return []

        from .cost_tracking import create_cost_sensors

        cost_sensors = await create_cost_sensors(
            hass,
            prix_ht=pricing.get("prix_ht"),
            prix_ttc=pricing.get("prix_ttc"),
            allowed_source_entity_ids=set(enabled_sources.keys()),
        )

        if cost_sensors:
            LOGGER.info("[COST-RECONCILE] ✅ %d capteurs coût réconciliés", len(cost_sensors))
        else:
            LOGGER.info("[COST-RECONCILE] Aucun capteur coût créé (allowlist vide?)")

        return cost_sensors or []

    except Exception as e:
        LOGGER.exception("[COST-RECONCILE] Erreur lors de la réconciliation: %s", e)
        return []


def _take_pool(hass: HomeAssistant, pending_key: str, stable_key: str) -> list:
    """Récupère la liste à ajouter."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    sensors = domain_data.pop(pending_key, None)
    if sensors is None:
        sensors = domain_data.get(stable_key, []) or []
    return sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry — EVENT-DRIVEN."""
    LOGGER.info("🎯 [EVENT-DRIVEN] Setup sensor platform - Attente events...")

    _get_added_uids(hass).clear()
    LOGGER.info("🧯 [DEDUP] Set runtime vidé pour régénération complète")

    EVENT_TO_KEYS = {
        "hse_energy_sensors_ready": ("energy_sensors_pending", "energy_sensors", "energy"),
        "hse_power_sensors_ready": (
            "live_power_sensors_pending",
            "live_power_sensors",
            "power",
        ),
        "hse_power_energy_sensors_ready": (
            "power_energy_sensors_pending",
            "power_energy_sensors",
            "power_energy",
        ),
        "hse_cost_sensors_ready": ("cost_sensors_pending", "cost_sensors", "cost"),
        # NEW: group totals
        "hse_room_totals_ready": (
            "room_totals_sensors_pending",
            "room_totals_sensors",
            "room_totals",
        ),
        "hse_type_totals_ready": (
            "type_totals_sensors_pending",
            "type_totals_sensors",
            "type_totals",
        ),
    }

    def _dedup_enabled_for_kind(kind: str) -> bool:
        # Safe: on dédup uniquement les capteurs 100% dérivés (totaux) pour éviter spam.
        return kind in ("room_totals", "type_totals")

    def _process(kind: str, pending_key: str, stable_key: str) -> None:
        sensors = _take_pool(hass, pending_key, stable_key)

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

        sensors, new_uids, skipped = _dedupe_by_uid(
            hass,
            sensors,
            kind,
            enable_dedup=_dedup_enabled_for_kind(kind),
        )

        LOGGER.info(
            "🧩 [EVENT-DEDUP] %s: kept=%s skipped=%s new_uids=%s",
            kind,
            len(sensors or []),
            skipped,
            list(new_uids)[:10],
        )

        if not sensors:
            LOGGER.warning(
                "⚠️ [EVENT] %s: aucun sensor à ajouter (pool vide ou tout filtré)",
                kind,
            )
            return

        try:
            async_add_entities(sensors, True)

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

    for ev in EVENT_TO_KEYS.keys():
        hass.bus.async_listen(ev, on_hse_sensors_ready)

    LOGGER.info("🎧 [EVENT-DRIVEN] Listeners activés - En attente des events sensors...")

    LOGGER.info("🔄 [STARTUP] Tentative flush des pools existants...")
    for _ev, (pending_key, stable_key, kind) in EVENT_TO_KEYS.items():
        _process(kind, pending_key, stable_key)

    LOGGER.info("🔄 [COST-RECONCILE] Réconciliation des capteurs coût...")

    try:
        cost_sensors = await _reconcile_cost_sensors(hass)

        if cost_sensors:
            cost_sensors, new_uids, skipped = _dedupe_by_uid(
                hass,
                cost_sensors,
                "cost_reconcile",
                enable_dedup=False,
            )

            if cost_sensors:
                async_add_entities(cost_sensors, update_before_add=True)
                _get_added_uids(hass).update(new_uids)
                LOGGER.info(
                    "✅ [COST-RECONCILE] %d capteurs coût ajoutés (%d dédupliqués)",
                    len(cost_sensors),
                    skipped,
                )
            else:
                LOGGER.info("[COST-RECONCILE] Tous les capteurs coût étaient déjà présents")
        else:
            LOGGER.info("[COST-RECONCILE] Aucun capteur coût à réconcilier")

    except Exception as e:
        LOGGER.exception("[COST-RECONCILE] Erreur lors de la réconciliation: %s", e)
