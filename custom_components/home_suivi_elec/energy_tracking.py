"""
Energy Tracking Platform - Unit-safe + Energy-delta support

Objectif:
- Éviter les FAUSSES infos (kWh/cout) quand une source énergie (kWh/Wh/MWh) est traitée comme une puissance.
- Normaliser systématiquement les unités à l'entrée:
  - Power: kW → W
  - Energy: Wh/MWh → kWh
- Choisir l'algorithme selon la nature réelle de la source:
  - source power → intégration (W→kWh)
  - source energy → delta cumulé (kWh→kWh)

Compat:
- On conserve les mêmes entity_id/unique_id "sensor.hse_energy_<basename>_<cycle>".
- Les capteurs coût (cost_tracking) restent inchangés car ils lisent les sensors energy HSE.

Date: 2026-01-27
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, Optional, Tuple

from homeassistant.components.sensor import (
    RestoreEntity,
    SensorDeviceClass,
    SensorEntity,
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

_POWER_UNITS_TO_W = {
    "W": 1.0,
    "kW": 1000.0,
}

_ENERGY_UNITS_TO_KWH = {
    "kWh": 1.0,
    "Wh": 1.0 / 1000.0,
    "MWh": 1000.0,
}


def _pick_unit(attrs: dict) -> Optional[str]:
    if not isinstance(attrs, dict):
        return None
    u = attrs.get("unit_of_measurement") or attrs.get("unit")
    if isinstance(u, str) and u.strip():
        return u.strip()
    return None


def _pick_device_class(attrs: dict) -> Optional[str]:
    if not isinstance(attrs, dict):
        return None
    dc = attrs.get("device_class")
    if dc is None:
        return None
    return str(dc)


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class SourceInfo:
    kind: str  # "power" | "energy"
    unit: Optional[str]


def _classify_source(device_class: Optional[str], unit: Optional[str]) -> Optional[SourceInfo]:
    # 1) Device class prioritaire
    if device_class == str(SensorDeviceClass.POWER) or device_class == "power":
        return SourceInfo(kind="power", unit=unit)
    if device_class == str(SensorDeviceClass.ENERGY) or device_class == "energy":
        return SourceInfo(kind="energy", unit=unit)

    # 2) Fallback via unit
    if unit in _POWER_UNITS_TO_W:
        return SourceInfo(kind="power", unit=unit)
    if unit in _ENERGY_UNITS_TO_KWH:
        return SourceInfo(kind="energy", unit=unit)

    return None


def _convert_power_to_w(value: float, unit: Optional[str]) -> Optional[float]:
    if unit is None:
        # Sans unité, on refuse pour éviter un faux calcul
        return None
    mul = _POWER_UNITS_TO_W.get(unit)
    if mul is None:
        return None
    return value * mul


def _convert_energy_to_kwh(value: float, unit: Optional[str]) -> Optional[float]:
    if unit is None:
        return None
    mul = _ENERGY_UNITS_TO_KWH.get(unit)
    if mul is None:
        return None
    return value * mul


def _get_cycle_start(cycle: str):
    now = dt_util.now()

    if cycle == "hourly":
        return now.replace(minute=0, second=5, microsecond=0)
    if cycle == "daily":
        return now.replace(hour=0, minute=0, second=5, microsecond=0)
    if cycle == "weekly":
        days_since_monday = now.weekday()
        monday = now - timedelta(days=days_since_monday)
        return monday.replace(hour=0, minute=1, second=0, microsecond=0)
    if cycle == "monthly":
        return now.replace(day=1, hour=0, minute=2, second=0, microsecond=0)
    if cycle == "yearly":
        return now.replace(month=1, day=1, hour=0, minute=3, second=0, microsecond=0)

    return now


async def _get_source_info(hass: HomeAssistant, entity_id: str) -> Optional[SourceInfo]:
    st = hass.states.get(entity_id)
    if not st:
        return None

    unit = _pick_unit(st.attributes)
    device_class = _pick_device_class(st.attributes)

    return _classify_source(device_class, unit)


async def ensure_reference_energy_sensors(
    hass: HomeAssistant,
    source_entity_id: str,
) -> List[SensorEntity]:
    """Crée les sensors cycles HSE pour un capteur de référence externe, si manquants."""
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

    src_info = await _get_source_info(hass, str(source_entity_id))
    if not src_info:
        # Référence: par défaut, on préfère le mode energy-delta (plus sûr que "power")
        _LOGGER.warning(
            "[REF] Impossible de classifier %s (unit/device_class inconnus) → mode 'energy' par défaut",
            source_entity_id,
        )
        src_info = SourceInfo(kind="energy", unit=None)

    created: List[SensorEntity] = []

    for cycle in CYCLES.keys():
        expected_entity_id = f"sensor.hse_energy_{basename}_{cycle}"
        expected_uid = f"hse_energy_{basename}_{cycle}"

        if expected_entity_id in existing_state_eids:
            continue
        if expected_uid in existing_uids:
            continue

        if src_info.kind == "power":
            created.append(
                PowerEnergyCycleSensor(
                    hass=hass,
                    source_entity=str(source_entity_id),
                    cycle=cycle,
                    basename=basename,
                )
            )
        else:
            created.append(
                EnergyDeltaCycleSensor(
                    hass=hass,
                    source_entity=str(source_entity_id),
                    cycle=cycle,
                    basename=basename,
                )
            )

    return created


async def create_energy_sensors(hass: HomeAssistant, capteurs_data=None) -> List[SensorEntity]:
    """Crée les capteurs cycles d'énergie HSE depuis la sélection (déjà filtrée enabled) ou fallback legacy."""
    _LOGGER.info("[CREATE-ENERGY] Début création sensors")

    # La Phase 2.7 passe déjà la sélection filtrée/merge depuis __init__.py.
    data = capteurs_data
    if data is None:
        _LOGGER.warning(
            "[CREATE-ENERGY] capteurs_data=None (fallback legacy) → aucun capteur généré (Phase 2.7 attend selection Storage)"
        )
        return []

    # Extraire capteurs selon format
    capteurs: list = []

    if isinstance(data, dict):
        if "power_sources" in data:
            capteurs = data["power_sources"]
        else:
            for category in ["mqtt", "tplink", "tuya", "shelly", "min_max", "template"]:
                if category in data and isinstance(data.get(category), list):
                    capteurs.extend(data[category])

    elif isinstance(data, list):
        capteurs = data

    else:
        _LOGGER.error("[CREATE-ENERGY] Format données inconnu: %s", type(data))
        return []

    enabled_capteurs = [c for c in capteurs if isinstance(c, dict) and c.get("enabled", False)]
    _LOGGER.info("[CREATE-ENERGY] Capteurs enabled=true: %d", len(enabled_capteurs))

    sensors: List[SensorEntity] = []

    for capteur in enabled_capteurs:
        entity_id = capteur.get("entity_id", "")
        if not entity_id:
            continue

        # Skip sensors HSE déjà créés
        if entity_id.startswith("sensor.hse_live_") or entity_id.startswith("sensor.hse_energy_"):
            continue

        # Basename stable (on garde le comportement historique)
        basename = (
            entity_id.replace("sensor.", "")
            .replace("_today_energy", "")
            .replace("_consommation_d_aujourd_hui", "")
        )

        src_info = await _get_source_info(hass, entity_id)
        if not src_info:
            st = hass.states.get(entity_id)
            unit = _pick_unit(st.attributes) if st else None
            dc = _pick_device_class(st.attributes) if st else None
            _LOGGER.warning(
                "[CREATE-ENERGY] SKIP %s (device_class=%s, unit=%s) → impossible de classifier power/energy",
                entity_id,
                dc,
                unit,
            )
            continue

        for cycle in CYCLES.keys():
            if src_info.kind == "power":
                sensors.append(
                    PowerEnergyCycleSensor(
                        hass=hass,
                        source_entity=entity_id,
                        cycle=cycle,
                        basename=basename,
                    )
                )
            else:
                sensors.append(
                    EnergyDeltaCycleSensor(
                        hass=hass,
                        source_entity=entity_id,
                        cycle=cycle,
                        basename=basename,
                    )
                )

    _LOGGER.info("[CREATE-ENERGY] ✅ %d sensors créés", len(sensors))
    return sensors


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.info("[ENERGY-TRACKING] Setup via sensor platform")
    sensors = await create_energy_sensors(hass)
    async_add_entities(sensors, True)


class _BaseCycleEnergySensor(RestoreEntity, SensorEntity):
    """Base pour capteurs cycles (reset par cycle + restore)."""

    def __init__(self, hass: HomeAssistant, source_entity: str, cycle: str, basename: str):
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

        self._state: float = 0.0
        self._cycle_start: Optional[datetime] = None

    @property
    def native_value(self):
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        return UnitOfEnergy.KILO_WATT_HOUR

    def _schedule_cycle_reset(self):
        cycle_config = CYCLES[self._cycle]
        next_reset = self._cycle_start + cycle_config["duration"]

        while next_reset < dt_util.now():
            next_reset += cycle_config["duration"]

        delay = (next_reset - dt_util.now()).total_seconds()

        async def reset_cycle():
            self._state = 0.0
            self._cycle_start = next_reset
            self._on_cycle_reset()
            self.async_write_ha_state()
            self._schedule_cycle_reset()

        self.hass.loop.call_later(delay, lambda: asyncio.create_task(reset_cycle()))

    def _on_cycle_reset(self) -> None:
        """Hook pour réinitialiser les variables internes lors du reset cycle."""
        return


class PowerEnergyCycleSensor(_BaseCycleEnergySensor):
    """Capteur cycle: source power (W/kW) → kWh via intégration temporelle."""

    def __init__(self, hass: HomeAssistant, source_entity: str, cycle: str, basename: str):
        super().__init__(hass, source_entity, cycle, basename)
        self._last_power_w: Optional[float] = None
        self._last_update: Optional[datetime] = None

    @property
    def extra_state_attributes(self):
        attrs = {
            "source_entity": self._source_entity,
            "cycle": self._cycle,
            "source_type": "power",
        }
        if self._last_power_w is not None:
            attrs["last_power_w"] = self._last_power_w
        if self._cycle_start:
            attrs["cycle_start"] = self._cycle_start.isoformat()
        return attrs

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._state = float(last_state.state or 0)
            except Exception:
                self._state = 0.0

            if last_state.attributes:
                cycle_start_str = last_state.attributes.get("cycle_start")
                if cycle_start_str:
                    try:
                        self._cycle_start = datetime.fromisoformat(cycle_start_str)
                    except Exception:
                        pass

        if not self._cycle_start:
            self._cycle_start = _get_cycle_start(self._cycle)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity],
                self._on_source_changed,
            )
        )

        self._schedule_cycle_reset()

    def _on_cycle_reset(self) -> None:
        self._last_power_w = None
        self._last_update = None

    @callback
    def _on_source_changed(self, event):
        new_state = event.data.get("new_state")
        if not new_state or new_state.state in ("unknown", "unavailable"):
            return

        raw_val = _to_float(new_state.state)
        if raw_val is None:
            return

        unit = _pick_unit(new_state.attributes)
        power_w = _convert_power_to_w(raw_val, unit)
        if power_w is None:
            # refuser plutôt que produire un faux kWh
            return

        now = dt_util.now()

        if self._last_power_w is not None and self._last_update is not None:
            delta_hours = (now - self._last_update).total_seconds() / 3600.0
            avg_power_w = (power_w + self._last_power_w) / 2.0
            energy_kwh = (avg_power_w / 1000.0) * delta_hours
            self._state += max(0.0, energy_kwh)

        self._last_power_w = power_w
        self._last_update = now
        self.async_write_ha_state()


class EnergyDeltaCycleSensor(_BaseCycleEnergySensor):
    """Capteur cycle: source energy (kWh/Wh/MWh) → kWh via cumul des deltas."""

    def __init__(self, hass: HomeAssistant, source_entity: str, cycle: str, basename: str):
        super().__init__(hass, source_entity, cycle, basename)
        self._last_energy_kwh: Optional[float] = None

    @property
    def extra_state_attributes(self):
        attrs = {
            "source_entity": self._source_entity,
            "cycle": self._cycle,
            "source_type": "energy",
        }
        if self._last_energy_kwh is not None:
            attrs["last_energy_kwh"] = self._last_energy_kwh
        if self._cycle_start:
            attrs["cycle_start"] = self._cycle_start.isoformat()
        return attrs

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._state = float(last_state.state or 0)
            except Exception:
                self._state = 0.0

            if last_state.attributes:
                cycle_start_str = last_state.attributes.get("cycle_start")
                if cycle_start_str:
                    try:
                        self._cycle_start = datetime.fromisoformat(cycle_start_str)
                    except Exception:
                        pass
                try:
                    if last_state.attributes.get("last_energy_kwh") is not None:
                        self._last_energy_kwh = float(last_state.attributes.get("last_energy_kwh"))
                except Exception:
                    self._last_energy_kwh = None

        if not self._cycle_start:
            self._cycle_start = _get_cycle_start(self._cycle)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity],
                self._on_source_changed,
            )
        )

        self._schedule_cycle_reset()

    def _on_cycle_reset(self) -> None:
        # Important: on remet le "last" à None, car les compteurs "today" se reset.
        self._last_energy_kwh = None

    @callback
    def _on_source_changed(self, event):
        new_state = event.data.get("new_state")
        if not new_state or new_state.state in ("unknown", "unavailable"):
            return

        raw_val = _to_float(new_state.state)
        if raw_val is None:
            return

        unit = _pick_unit(new_state.attributes)
        energy_kwh = _convert_energy_to_kwh(raw_val, unit)
        if energy_kwh is None:
            return

        if self._last_energy_kwh is None:
            # première mesure: on initialise le last, sans modifier l'état
            self._last_energy_kwh = energy_kwh
            self.async_write_ha_state()
            return

        delta = energy_kwh - self._last_energy_kwh

        # Gestion resets (today_energy qui revient à 0) / valeurs négatives
        if delta < 0:
            delta = 0.0

        self._state += delta
        self._last_energy_kwh = energy_kwh
        self.async_write_ha_state()
