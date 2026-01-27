"""
Power Monitoring - Live sensors uniquement (unit-safe)

Fix 2026-01-27:
- Ne crée un sensor.hse_live_* que si la source est un capteur POWER (device_class=power ou unité W/kW).
- Conversion kW → W pour éviter des valeurs incohérentes.

Cela évite les fausses puissances (ex: source en kWh traitée comme W).
"""

import logging
from typing import Dict, List, Any, Optional
import json
import os

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_POWER_UNITS_TO_W = {
    "W": 1.0,
    "kW": 1000.0,
}


def _pick_unit(attrs: dict) -> Optional[str]:
    if not isinstance(attrs, dict):
        return None
    u = attrs.get("unit_of_measurement") or attrs.get("unit")
    if isinstance(u, str) and u.strip():
        return u.strip()
    return None


def _is_power_source(hass: HomeAssistant, entity_id: str) -> bool:
    st = hass.states.get(entity_id)
    if not st:
        return False

    dc = st.attributes.get("device_class")
    unit = _pick_unit(st.attributes)

    if str(dc) == str(SensorDeviceClass.POWER) or str(dc) == "power":
        return True

    if unit in _POWER_UNITS_TO_W:
        return True

    return False


def _to_w(value: Any, unit: Optional[str]) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None

    if unit is None:
        return None

    mul = _POWER_UNITS_TO_W.get(unit)
    if mul is None:
        return None

    return v * mul


async def async_load_power_sensors(hass: HomeAssistant) -> List[Dict[str, Any]]:
    """Charge liste capteurs "enabled" depuis StorageManager (selection Storage API) avec fallback legacy."""
    storage_manager = hass.data.get(DOMAIN, {}).get("storage_manager")

    if storage_manager:
        try:
            selection_data = await storage_manager.get_capteurs_selection()
            if not selection_data:
                _LOGGER.warning("[POWER MONITORING] Aucune sélection dans Storage API")
                return []

            power_sensors = []
            for _, sensors in selection_data.items():
                if isinstance(sensors, list):
                    power_sensors.extend([s for s in sensors if isinstance(s, dict) and s.get("enabled", False)])

            _LOGGER.info("[POWER MONITORING] %d capteurs chargés depuis Storage API", len(power_sensors))
            return power_sensors

        except Exception as e:
            _LOGGER.error("[POWER MONITORING] Erreur lecture Storage API: %s", e)
            _LOGGER.warning("[POWER MONITORING] Fallback sur fichier JSON legacy...")

    data_dir = hass.config.path(f"custom_components/{DOMAIN}/data")
    capteurs_file = os.path.join(data_dir, "capteurs_selection.json")

    if not os.path.exists(capteurs_file):
        _LOGGER.error(
            "[POWER MONITORING] Aucune source: StorageManager absent ET fichier %s introuvable",
            capteurs_file,
        )
        return []

    try:
        def _load_json():
            with open(capteurs_file, "r", encoding="utf-8") as f:
                return json.load(f)

        data = await hass.async_add_executor_job(_load_json)

        power_sensors = []
        if isinstance(data, dict):
            for _, sensors in data.items():
                if isinstance(sensors, list):
                    power_sensors.extend([s for s in sensors if isinstance(s, dict) and s.get("enabled", False)])
        elif isinstance(data, list):
            power_sensors = [s for s in data if isinstance(s, dict) and s.get("enabled", False)]
        else:
            _LOGGER.error("[POWER MONITORING] Format JSON invalide: %s", type(data))
            return []

        _LOGGER.info("[POWER MONITORING] %d capteurs chargés depuis fichier JSON legacy", len(power_sensors))
        return power_sensors

    except Exception as e:
        _LOGGER.error("[POWER MONITORING] Erreur chargement capteurs: %s", e)
        return []


def create_live_sensors(hass: HomeAssistant, sensors_data: List[Dict[str, Any]]) -> List[SensorEntity]:
    """Crée sensors LIVE (W) uniquement pour des sources POWER réelles."""
    live_sensors: List[SensorEntity] = []

    for sensor_data in sensors_data:
        entity_id = sensor_data.get("entity_id")
        if not entity_id:
            continue

        if not _is_power_source(hass, entity_id):
            _LOGGER.info(
                "[POWER MONITORING] SKIP live pour %s (pas un capteur power: device_class/unit incompatible)",
                entity_id,
            )
            continue

        try:
            live_sensor = LivePowerSensor(
                hass=hass,
                source_entity=entity_id,
                sensor_data=sensor_data,
            )
            live_sensors.append(live_sensor)
        except Exception as e:
            _LOGGER.error("[POWER MONITORING] Erreur création sensor live %s: %s", entity_id, e)

    _LOGGER.info("[POWER MONITORING] %d sensors live créés", len(live_sensors))
    return live_sensors


class LivePowerSensor(RestoreEntity, SensorEntity):
    """Sensor LIVE (W) pour monitoring temps réel."""

    def __init__(self, hass: HomeAssistant, source_entity: str, sensor_data: Dict[str, Any]):
        self.hass = hass
        self._source_entity = source_entity
        self._sensor_data = sensor_data

        basename = source_entity.replace("sensor.", "")
        self._attr_name = f"HSE Live {basename}"
        self._attr_entity_id = f"sensor.hse_live_{basename}"
        self._attr_unique_id = f"hse_live_power_{source_entity}"

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:flash"

        self._attr_native_value = None
        self._attr_available = True

    @property
    def extra_state_attributes(self):
        return {
            "source_entity": self._source_entity,
            "sensor_type": "live_power",
            "is_virtual": self._sensor_data.get("is_virtual", False),
            "reliability_score": self._sensor_data.get("reliability_score", 100),
            "reference_type": self._sensor_data.get("reference_type", "physical"),
        }

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._attr_native_value = float(last_state.state)
            except (ValueError, TypeError):
                pass

        async_track_state_change_event(self.hass, [self._source_entity], self._on_source_changed)

    @callback
    def _on_source_changed(self, event):
        new_state = event.data.get("new_state")
        if not new_state:
            return

        if new_state.state in ("unknown", "unavailable"):
            self._attr_available = False
            self._attr_native_value = None
            self.async_write_ha_state()
            return

        unit = _pick_unit(new_state.attributes)
        power_w = _to_w(new_state.state, unit)
        if power_w is None:
            self._attr_available = False
            self._attr_native_value = None
            self.async_write_ha_state()
            return

        self._attr_native_value = power_w
        self._attr_available = True
        self.async_write_ha_state()


async def async_setup_power_monitoring(hass: HomeAssistant, entry) -> bool:
    try:
        _LOGGER.info("[POWER MONITORING] Démarrage setup power monitoring...")

        sensors_data = await async_load_power_sensors(hass)
        if not sensors_data:
            _LOGGER.warning("[POWER MONITORING] Aucun capteur activé dans la sélection")
            return True

        live_sensors = create_live_sensors(hass, sensors_data)

        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        hass.data[DOMAIN]["live_power_sensors"] = live_sensors

        _LOGGER.info("[POWER MONITORING] ✅ %d sensors live prêts", len(live_sensors))
        return True

    except Exception as e:
        _LOGGER.error("[POWER MONITORING] ❌ Erreur setup: %s", e)
        return False
