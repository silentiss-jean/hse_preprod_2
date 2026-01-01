"""
Energy Tracking Platform - Version COMPLETE FIXED
Crée sensors energy tracking avec cycles horaire/jour/semaine/mois/année

FIX COMPLET:
  - Utilise paramètre capteurs_data passé par __init__.py
  - Gère toutes catégories (mqtt, tplink, tuya, min_max)
  - Filtre enabled: true
  - Async I/O
  - native_unit_of_measurement pour Energy Dashboard
  - + helper ensure_reference_energy_sensors (capteur externe)

Date: 2025-11-10 (patched 2025-12-13)
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import List

from homeassistant.components.sensor import (
    RestoreEntity,
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

CYCLES = {
    "hourly": {"duration": timedelta(hours=1), "offset": timedelta(seconds=5)},
    "daily": {"duration": timedelta(days=1), "offset": timedelta(seconds=5)},
    "weekly": {"duration": timedelta(weeks=1), "offset": timedelta(minutes=1)},
    "monthly": {"duration": timedelta(days=30), "offset": timedelta(minutes=2)},
    "yearly": {"duration": timedelta(days=365), "offset": timedelta(minutes=3)},
}


async def ensure_reference_energy_sensors(
    hass: HomeAssistant,
    source_entity_id: str,
) -> List[SensorEntity]:
    """
    Crée les sensors cycles HSE pour un capteur de référence externe, si manquants.

    Déduplication:
    - check states HA (si déjà existants)
    - check objets déjà préparés dans hass.data[DOMAIN]["energy_sensors"] (si déjà injectés)
    """
    if not source_entity_id or not str(source_entity_id).startswith("sensor."):
        _LOGGER.warning("[REF] source_entity_id invalide: %s", source_entity_id)
        return []

    basename = (
        str(source_entity_id)
        .replace("sensor.", "")
        .replace("_today_energy", "")
        .replace("_consommation_d_aujourd_hui", "")
    )

    existing_state_eids = {s.entity_id for s in hass.states.async_all("sensor")}

    existing_uids = set()
    try:
        existing_objs = (hass.data.get("home_suivi_elec", {}) or {}).get("energy_sensors", []) or []
        for ent in existing_objs:
            uid = getattr(ent, "unique_id", None) or getattr(ent, "_attr_unique_id", None)
            if uid:
                existing_uids.add(str(uid))
    except Exception:
        pass

    created: List[SensorEntity] = []

    for cycle in CYCLES.keys():
        expected_entity_id = f"sensor.hse_energy_{basename}_{cycle}"
        expected_uid = f"hse_energy_{basename}_{cycle}"

        if expected_entity_id in existing_state_eids:
            continue
        if expected_uid in existing_uids:
            continue

        created.append(
            PowerEnergyCycleSensor(
                hass=hass,
                source_entity=str(source_entity_id),
                cycle=cycle,
                basename=basename,
            )
        )

    return created


async def create_energy_sensors(hass: HomeAssistant, capteurs_data=None) -> List[SensorEntity]:
    """
    Create energy sensors from capteurs data or capteurs_selection.json

    Args:
        hass: Home Assistant instance
        capteurs_data: Données déjà chargées par __init__.py (dict ou list)
                      Si None, charge depuis capteurs_selection.json

    Returns:
        List of energy sensor entities
    """
    _LOGGER.info("[CREATE-ENERGY] Début création sensors via helper")

    import os

    # Si données passées en paramètre, les utiliser
    if capteurs_data is not None:
        _LOGGER.info("[CREATE-ENERGY] Utilisation données passées en paramètre")
        data = capteurs_data
    else:
        # Sinon charger depuis fichier
        _LOGGER.info("[CREATE-ENERGY] Chargement depuis fichier")
        selection_file = os.path.join(
            hass.config.config_dir,
            "custom_components/home_suivi_elec/data/capteurs_selection.json",
        )

        def _load_capteurs_selection():
            try:
                with open(selection_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                _LOGGER.error("[CREATE-ENERGY] Erreur lecture fichier: %s", e)
                return None

        data = await hass.async_add_executor_job(_load_capteurs_selection)
        if data is None:
            return []

    # Extraire capteurs selon format
    capteurs = []

    if isinstance(data, dict):
        # Format avec catégories: {"mqtt": [...], "tplink": [...], ...}
        _LOGGER.info("[CREATE-ENERGY] Format dict détecté")

        # D'abord chercher power_sources (format unifié)
        if "power_sources" in data:
            capteurs = data["power_sources"]
            _LOGGER.info("[CREATE-ENERGY] Trouvé power_sources: %d capteurs", len(capteurs))
        else:
            # Sinon extraire de toutes les catégories
            for category in ["mqtt", "tplink", "tuya", "shelly", "min_max", "template"]:
                if category in data:
                    category_capteurs = data[category]
                    _LOGGER.info("[CREATE-ENERGY] Catégorie %s: %d capteurs", category, len(category_capteurs))
                    capteurs.extend(category_capteurs)

    elif isinstance(data, list):
        # Format liste directe: [{entity_id: ..., enabled: ...}, ...]
        _LOGGER.info("[CREATE-ENERGY] Format list détecté")
        capteurs = data

    else:
        _LOGGER.error("[CREATE-ENERGY] Format données inconnu: %s", type(data))
        return []

    _LOGGER.info("[CREATE-ENERGY] Total capteurs avant filtrage: %d", len(capteurs))

    # Filtrer enabled: true
    enabled_capteurs = [c for c in capteurs if isinstance(c, dict) and c.get("enabled", False)]
    _LOGGER.info("[CREATE-ENERGY] Capteurs enabled=true: %d", len(enabled_capteurs))

    if not enabled_capteurs:
        _LOGGER.warning("[CREATE-ENERGY] ⚠️ AUCUN capteur avec enabled=true !")
        _LOGGER.warning("[CREATE-ENERGY] Vérifiez capteurs_selection.json")
        return []

    sensors: List[SensorEntity] = []

    for capteur in enabled_capteurs:
        entity_id = capteur.get("entity_id", "")

        if not entity_id:
            _LOGGER.warning("[CREATE-ENERGY] Capteur sans entity_id: %s", capteur)
            continue

        # Skip sensors HSE déjà créés
        if entity_id.startswith("sensor.hse_live_") or entity_id.startswith("sensor.hse_energy_"):
            _LOGGER.debug("[SKIP] %s déjà sensor HSE", entity_id)
            continue

        # Déterminer si sensor energy ou power (heuristique)
        is_energy = (
            "_energy" in entity_id
            or "_today_energy" in entity_id
            or "consommation" in entity_id
        )

        basename = (
            entity_id.replace("sensor.", "")
            .replace("_today_energy", "")
            .replace("_consommation_d_aujourd_hui", "")
        )

        # Créer sensors par cycle
        for cycle in CYCLES.keys():
            if is_energy:
                sensor_id = f"sensor.hse_{basename}_{cycle}"
            else:
                sensor_id = f"sensor.hse_energy_{basename}_{cycle}"

            _LOGGER.info("[CREATE-ENERGY] Création %s", sensor_id)

            sensors.append(
                PowerEnergyCycleSensor(
                    hass=hass,
                    source_entity=entity_id,
                    cycle=cycle,
                    basename=basename,
                )
            )

    _LOGGER.info("[CREATE-ENERGY] ✅ %d sensors créés", len(sensors))
    return sensors


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """
    Setup energy tracking sensors via sensor platform
    Utilisé si configuré dans configuration.yaml
    """
    _LOGGER.info("[ENERGY-TRACKING] Setup via sensor platform")

    sensors = await create_energy_sensors(hass)
    async_add_entities(sensors, True)


class PowerEnergyCycleSensor(RestoreEntity, SensorEntity):
    """Sensor intégrant puissance en énergie par cycle."""

    def __init__(self, hass, source_entity, cycle, basename):
        """Initialize."""
        self.hass = hass
        self._source_entity = source_entity
        self._cycle = cycle
        self._basename = basename

        self._attr_name = f"HSE {basename.replace('_', ' ').title()} Energy {cycle.title()}"
        self._attr_unique_id = f"hse_energy_{basename}_{cycle}"
        self._attr_suggested_object_id = f"hse_energy_{basename}_{cycle}"

        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:flash"

        self._state = 0.0
        self._last_power = None
        self._last_update = None
        self._cycle_start = None

    @property
    def native_value(self):
        """Return state."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of measurement - FIX pour Energy Dashboard."""
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        attrs = {
            "source_entity": self._source_entity,
            "cycle": self._cycle,
            "source_type": "power",
        }

        if self._last_power is not None:
            attrs["last_power_w"] = self._last_power

        if self._cycle_start:
            attrs["cycle_start"] = self._cycle_start.isoformat()

        return attrs

    async def async_added_to_hass(self):
        """Setup tracking."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._state = float(last_state.state or 0)
            except Exception:
                self._state = 0.0

            if attrs := last_state.attributes:
                if cycle_start_str := attrs.get("cycle_start"):
                    try:
                        self._cycle_start = datetime.fromisoformat(cycle_start_str)
                    except Exception:
                        pass

        if not self._cycle_start:
            self._cycle_start = self._get_cycle_start()

        _LOGGER.info("[LIVE-POWER] %s tracking %s", self.entity_id, self._source_entity)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity],
                self._on_source_changed,
            )
        )

        self._schedule_cycle_reset()

    @callback
    def _on_source_changed(self, event):
        """Handle source state change."""
        new_state = event.data.get("new_state")
        if not new_state or new_state.state in ["unknown", "unavailable"]:
            return

        try:
            power = float(new_state.state)
        except ValueError:
            return

        now = dt_util.now()

        if self._last_power is not None and self._last_update is not None:
            delta_hours = (now - self._last_update).total_seconds() / 3600.0
            avg_power = (power + self._last_power) / 2.0
            energy_kwh = (avg_power / 1000.0) * delta_hours
            self._state += energy_kwh

        self._last_power = power
        self._last_update = now

        self.async_write_ha_state()

    def _get_cycle_start(self):
        """Calculate cycle start."""
        now = dt_util.now()

        if self._cycle == "hourly":
            return now.replace(minute=0, second=5, microsecond=0)
        elif self._cycle == "daily":
            return now.replace(hour=0, minute=0, second=5, microsecond=0)
        elif self._cycle == "weekly":
            days_since_monday = now.weekday()
            monday = now - timedelta(days=days_since_monday)
            return monday.replace(hour=0, minute=1, second=0, microsecond=0)
        elif self._cycle == "monthly":
            return now.replace(day=1, hour=0, minute=2, second=0, microsecond=0)
        elif self._cycle == "yearly":
            return now.replace(month=1, day=1, hour=0, minute=3, second=0, microsecond=0)

        return now

    def _schedule_cycle_reset(self):
        """Schedule next cycle reset."""
        cycle_config = CYCLES[self._cycle]
        next_reset = self._cycle_start + cycle_config["duration"]

        while next_reset < dt_util.now():
            next_reset += cycle_config["duration"]

        delay = (next_reset - dt_util.now()).total_seconds()

        async def reset_cycle():
            self._state = 0.0
            self._cycle_start = next_reset
            self._last_power = None
            self._last_update = None
            self.async_write_ha_state()
            self._schedule_cycle_reset()

        self.hass.loop.call_later(delay, lambda: asyncio.create_task(reset_cycle()))
