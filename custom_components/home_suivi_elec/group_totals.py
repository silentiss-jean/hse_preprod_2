"""Group totals sensors (rooms/types) - facture/energy/power totals.

Creates HSE sensors that aggregate multiple underlying entities.

- Rooms: based on group_sets.sets.rooms.groups
- Types: based on group_sets.sets.types.groups

For V1 we implement:
- Facture totals TTC: daily + monthly (summing existing HSE cost sensors)
- Optional totals energy/power can be added later if needed

Event-driven integration:
- Generator will populate hass.data[DOMAIN]['room_totals_sensors_pending'] and fire 'hse_room_totals_ready'
- Generator will populate hass.data[DOMAIN]['type_totals_sensors_pending'] and fire 'hse_type_totals_ready'

"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from homeassistant.components.sensor import RestoreEntity, SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _slug_alnum(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


def _parse_energy_entity_id(entity_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Reuse cost_tracking parsing rules (subset) to get (basename, cycle)."""
    if not isinstance(entity_id, str):
        return None, None
    if not entity_id.startswith("sensor.hse"):
        return None, None

    s = entity_id.replace("sensor.", "", 1)  # hse...

    m = re.match(r"^hse_(?P<base>.+?)_energy_(?P<cycle>hourly|daily|weekly|monthly|yearly)$", s)
    if m:
        return m.group("base"), m.group("cycle")

    m = re.match(r"^hse_energy_(?P<base>.+?)_(?P<cycle>hourly|daily|weekly|monthly|yearly)$", s)
    if m:
        return m.group("base"), m.group("cycle")

    # fallback: try suffix _cycle
    for cycle in ("hourly", "daily", "weekly", "monthly", "yearly"):
        if entity_id.endswith(f"_{cycle}"):
            base = entity_id[: -len(f"_{cycle}")]
            base = base.replace("sensor.hse_", "", 1).replace("sensor.hse", "", 1)
            base = base.replace("_energy_", "_").replace("energy_", "").replace("_energy", "")
            return base, cycle

    return None, None


def _cost_entity_id_candidates_from_energy(energy_entity_id: str, cycle: str) -> List[str]:
    """Build expected cost entity_id candidates (TTC) from an energy sensor id.

    Prefer the unified TTC sensor if present (fixe or aggregated hp/hc), but also support
    legacy hp/hc split sensors by returning both candidates.
    """
    base_raw, _ = _parse_energy_entity_id(energy_entity_id)
    if not base_raw:
        return []
    base = _slug_alnum(base_raw)
    if not base:
        return []
    if cycle not in ("daily", "monthly"):
        return []

    # Unified TTC
    out = [f"sensor.hse_{base}_cout_{cycle}_ttc"]

    # Fallback hp/hc split TTC
    out.append(f"sensor.hse_{base}_cout_{cycle}_ttc_hp")
    out.append(f"sensor.hse_{base}_cout_{cycle}_ttc_hc")

    return out


@dataclass
class GroupDef:
    key: str  # stable name (dict key)
    mode: str
    energy: List[str]
    power: List[str]


def _extract_groups(group_sets: Dict[str, Any], namespace: str) -> List[GroupDef]:
    out: List[GroupDef] = []
    groups = (
        (group_sets or {})
        .get("sets", {})
        .get(namespace, {})
        .get("groups", {})
    )
    if not isinstance(groups, dict):
        return out

    for key, g in groups.items():
        if not isinstance(key, str) or not key.strip():
            continue
        if not isinstance(g, dict):
            g = {}
        out.append(
            GroupDef(
                key=key,
                mode=str(g.get("mode") or "manual"),
                energy=list(g.get("energy") or []) if isinstance(g.get("energy"), list) else [],
                power=list(g.get("power") or []) if isinstance(g.get("power"), list) else [],
            )
        )
    return out


class HSEFactureTotalSensor(RestoreEntity, SensorEntity):
    """Aggregated TTC cost total for a group (room/type)."""

    def __init__(
        self,
        hass: HomeAssistant,
        scope: str,  # 'room' | 'type'
        group_key: str,
        cycle: str,  # 'daily' | 'monthly'
        source_cost_entities: Sequence[str],
    ):
        self.hass = hass
        self._scope = scope
        self._group_key = group_key
        self._cycle = cycle
        self._sources = [s for s in (source_cost_entities or []) if isinstance(s, str) and s]

        slug = _slug_alnum(group_key)
        object_id = f"hse_{scope}_{slug}_facture_total_{cycle}_ttc"

        self._attr_unique_id = object_id
        self._attr_suggested_object_id = object_id
        self._attr_name = f"HSE {scope.title()} {group_key} Facture Total {cycle.title()} TTC"

        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_should_poll = False

        self._state = 0.0
        self._last_updated = dt_util.now().isoformat()

    @property
    def native_value(self):
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        return getattr(self.hass.config, "currency", "EUR")

    @property
    def extra_state_attributes(self):
        return {
            "scope": self._scope,
            "group_key": self._group_key,
            "cycle": self._cycle,
            "currency": self.native_unit_of_measurement,
            "sources": list(self._sources),
            "last_updated": self._last_updated,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        # Restore state
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._state = float(last_state.state or 0)
            except Exception:
                self._state = 0.0
            if last_state.attributes:
                self._last_updated = last_state.attributes.get("last_updated", self._last_updated)

        self._recompute_from_hass_states()

        if self._sources:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    list(self._sources),
                    self._on_sources_changed,
                )
            )

    def _recompute_from_hass_states(self) -> None:
        total = 0.0
        for ent_id in self._sources:
            st = self.hass.states.get(ent_id)
            if not st or st.state in ("unknown", "unavailable"):
                continue
            try:
                total += float(st.state)
            except (TypeError, ValueError):
                continue
        self._state = max(0.0, total)
        self._last_updated = dt_util.now().isoformat()

    @callback
    def _on_sources_changed(self, event):
        self._recompute_from_hass_states()
        self.async_write_ha_state()


async def create_group_total_sensors(
    hass: HomeAssistant,
    group_sets: Dict[str, Any],
    namespace: str,  # rooms|types
) -> List[SensorEntity]:
    """Create facture total sensors (daily/monthly TTC) for each group in namespace."""
    scope = "room" if namespace == "rooms" else "type"

    groups = _extract_groups(group_sets, namespace)
    sensors: List[SensorEntity] = []

    for g in groups:
        group_key = g.key

        daily_sources: List[str] = []
        monthly_sources: List[str] = []

        for energy_entity_id in g.energy:
            daily_sources.extend(_cost_entity_id_candidates_from_energy(energy_entity_id, "daily"))
            monthly_sources.extend(_cost_entity_id_candidates_from_energy(energy_entity_id, "monthly"))

        # Dedup while preserving order
        def _dedup(seq: Iterable[str]) -> List[str]:
            seen = set()
            out = []
            for x in seq:
                if x in seen:
                    continue
                seen.add(x)
                out.append(x)
            return out

        daily_sources = _dedup(daily_sources)
        monthly_sources = _dedup(monthly_sources)

        sensors.append(
            HSEFactureTotalSensor(
                hass=hass,
                scope=scope,
                group_key=group_key,
                cycle="daily",
                source_cost_entities=daily_sources,
            )
        )
        sensors.append(
            HSEFactureTotalSensor(
                hass=hass,
                scope=scope,
                group_key=group_key,
                cycle="monthly",
                source_cost_entities=monthly_sources,
            )
        )

    _LOGGER.info(
        "[GROUP-TOTALS] Created %d facture sensors for namespace=%s (%d groups)",
        len(sensors),
        namespace,
        len(groups),
    )
    return sensors


async def refresh_group_totals(hass: HomeAssistant) -> None:
    """Regenerate totals for rooms and types and fire corresponding events."""
    mgr = hass.data.get(DOMAIN, {}).get("storage_manager")
    if not mgr:
        _LOGGER.warning("[GROUP-TOTALS] StorageManager not available")
        return

    group_sets = await mgr.get_group_sets()

    # Rooms
    room_sensors = await create_group_total_sensors(hass, group_sets, "rooms")
    hass.data.setdefault(DOMAIN, {})["room_totals_sensors_pending"] = room_sensors
    hass.bus.async_fire("hse_room_totals_ready")

    # Types
    type_sensors = await create_group_total_sensors(hass, group_sets, "types")
    hass.data.setdefault(DOMAIN, {})["type_totals_sensors_pending"] = type_sensors
    hass.bus.async_fire("hse_type_totals_ready")
