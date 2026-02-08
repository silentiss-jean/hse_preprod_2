"""
Cost Tracking Platform - Création capteurs coût avec gestion HP/HC

Fonctionnement:
1. Détecte le type de contrat (fixe ou hp_hc)
2. Crée les sensors coût adaptés (unique ou hp/hc séparés)
3. Gère les prix depuis config_entries (data + options)

Version: 2.2 - FIX PERSISTANCE
Date: 2025-12-17
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .const import DOMAIN

from homeassistant.components.sensor import (
    RestoreEntity,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util


_LOGGER = logging.getLogger(__name__)

# Cycles supportés pour le coût (aligné avec l'intégration)
COST_CYCLES: Tuple[str, ...] = ("daily", "weekly", "monthly")
ALL_CYCLES: Tuple[str, ...] = ("hourly", "daily", "weekly", "monthly", "yearly")


def _pick(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Retourne la première valeur non vide trouvée pour une liste de clés."""
    for k in keys:
        if k in d and d.get(k) not in (None, ""):
            return d.get(k)
    return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _slug_alnum(text: str) -> str:
    """Conserve les underscores et convertit en snake_case propre."""
    s = (text or "").strip().lower()
    # Remplacer espaces/accents/traits par underscores
    s = re.sub(r"[^\w]+", "_", s)
    # Supprimer underscores multiples
    s = re.sub(r"_+", "_", s)
    # Trim underscores début/fin
    return s.strip("_")


def _normalize_contract_type(raw_type: Any) -> str:
    raw = str(raw_type or "").strip().lower()
    raw_clean = raw.replace("-", "").replace("_", "").replace(" ", "")

    if raw_clean in ("hphc", "heurescreuses", "heurecreuse", "hpc", "hchp"):
        return "hp_hc"
    if raw_clean in ("fixe", "prixunique", "prixfixe", "unique", "base"):
        return "fixe"

    _LOGGER.warning(
        "[PRICING] Type contrat inconnu '%s' (raw='%s'), utilisation 'fixe'",
        raw_clean,
        raw_type,
    )
    return "fixe"


def _default_pricing() -> Dict[str, Any]:
    """Configuration par défaut si aucune config trouvée."""
    return {
        "type_contrat": "fixe",
        "prix_ht": 0.0,
        "prix_ttc": 0.0,
        "prix_ht_hp": 0.0,
        "prix_ttc_hp": 0.0,
        "prix_ht_hc": 0.0,
        "prix_ttc_hc": 0.0,
    }


def get_pricing_config(hass: HomeAssistant) -> Dict[str, Any]:
    """
    Récupère la configuration des prix depuis config_entries.

    Accepte les variantes de clés:
    - typeContrat / type_contrat / typecontrat
    - prixht / prix_ht / prixHT
    - prixttc / prix_ttc / prixTTC
    - prixhthp / prix_ht_hp, etc.
    """
    try:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            _LOGGER.warning("[PRICING] Aucun config_entry trouvé")
            return _default_pricing()

        entry = entries[0]
        data = entry.data or {}
        options = entry.options or {}

        raw_type = _pick(
            options,
            "type_contrat",
            "type_contrat",
            "typecontrat",
            default=_pick(data, "type_contrat", "type_contrat", "typecontrat", default="fixe"),
        )

        type_contrat = _normalize_contract_type(raw_type)

        prix_ht = _to_float(
            _pick(options, "prixht", "prix_ht", "prixHT", default=_pick(data, "prixht", "prix_ht", "prixHT", default=0.0))
        )
        prix_ttc = _to_float(
            _pick(options, "prixttc", "prix_ttc", "prixTTC", default=_pick(data, "prixttc", "prix_ttc", "prixTTC", default=0.0))
        )

        config: Dict[str, Any] = {
            "type_contrat": type_contrat,
            "prix_ht": prix_ht,
            "prix_ttc": prix_ttc,
        }

        if type_contrat == "hp_hc":
            config.update(
                {
                    "prix_ht_hp": _to_float(_pick(options, "prixhthp", "prix_ht_hp", "prixHTHP", default=prix_ht)),
                    "prix_ttc_hp": _to_float(_pick(options, "prixttchp", "prix_ttc_hp", "prixTTCHP", default=prix_ttc)),
                    "prix_ht_hc": _to_float(_pick(options, "prixhthc", "prix_ht_hc", "prixHTHC", default=prix_ht)),
                    "prix_ttc_hc": _to_float(_pick(options, "prixttchc", "prix_ttc_hc", "prixTTCHC", default=prix_ttc)),
                }
            )
        else:
            config.update(
                {
                    "prix_ht_hp": prix_ht,
                    "prix_ttc_hp": prix_ttc,
                    "prix_ht_hc": prix_ht,
                    "prix_ttc_hc": prix_ttc,
                }
            )

        _LOGGER.info(
            "[PRICING] Config: type=%s (raw='%s'), prix_ht=%.4f, prix_ttc=%.4f",
            type_contrat,
            raw_type,
            config["prix_ht"],
            config["prix_ttc"],
        )

        if type_contrat == "hp_hc":
            _LOGGER.info(
                "[PRICING] HP/HC: HP_HT=%.4f, HP_TTC=%.4f, HC_HT=%.4f, HC_TTC=%.4f",
                config["prix_ht_hp"],
                config["prix_ttc_hp"],
                config["prix_ht_hc"],
                config["prix_ttc_hc"],
            )

        return config

    except Exception as e:
        _LOGGER.exception("[PRICING] Erreur récupération config: %s", e)
        return _default_pricing()


def _parse_energy_entity_id(entity_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrait (basename, cycle) depuis plusieurs conventions d'entity_id.

    Supporte notamment:
    - sensor.hse_<basename>_energy_<cycle>
    - sensor.hse_energy_<basename>_<cycle>
    - sensor.hse<basename>energy<cycle> (sans underscores)
    """
    if not entity_id.startswith("sensor.hse"):
        return None, None

    s = entity_id.replace("sensor.", "", 1)  # hse...

    # 1) hse_<basename>_energy_<cycle>
    m = re.match(r"^hse_(?P<base>.+?)_energy_(?P<cycle>hourly|daily|weekly|monthly|yearly)$", s)
    if m:
        return m.group("base"), m.group("cycle")

    # 2) hse_energy_<basename>_<cycle>
    m = re.match(r"^hse_energy_(?P<base>.+?)_(?P<cycle>hourly|daily|weekly|monthly|yearly)$", s)
    if m:
        return m.group("base"), m.group("cycle")

    # 3) hse<basename>energy<cycle> (pas d'underscores)
    for cycle in ALL_CYCLES:
        if s.endswith(f"energy{cycle}"):
            base = s[: -len(f"energy{cycle}")]
            # enlever le prefix hse
            if base.startswith("hse"):
                base = base[3:]
            return base, cycle

    # 4) fallback: cycle par suffixe _cycle, basename best-effort
    for cycle in ALL_CYCLES:
        if entity_id.endswith(f"_{cycle}"):
            base = entity_id[:-len(f"_{cycle}")]
            base = base.replace("sensor.hse_", "", 1).replace("sensor.hse", "", 1)
            base = base.replace("_energy_", "_").replace("energy_", "").replace("_energy", "")
            return base, cycle

    return None, None


class HSECostAggregateSensor(RestoreEntity, SensorEntity):
    """Capteur coût agrégé (ex: TTC total = TTC_HP + TTC_HC).

    Utilisé en mode HP/HC pour exposer un capteur compatible avec le mode fixe:
    - sensor.hse_<basename>_cout_<cycle>_ttc
    - sensor.hse_<basename>_cout_<cycle>_ht

    Les sources attendues sont des entités HSECostSensor.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        basename: str,
        cycle: str,
        variant: str,  # 'ht' | 'ttc'
        source_entities: List[str],
    ):
        self.hass = hass

        self._basename = basename
        self._cycle = cycle
        self._variant = variant
        self._sources = [s for s in (source_entities or []) if isinstance(s, str) and s]

        object_id = f"hse_{self._basename}_cout_{self._cycle}_{self._variant}"
        self._attr_unique_id = object_id
        self._attr_suggested_object_id = object_id
        self._attr_name = f"HSE {self._basename} Cout {self._cycle.title()} {self._variant.upper()}"

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
            "basename": self._basename,
            "cycle": self._cycle,
            "variant": self._variant,
            "currency": self.native_unit_of_measurement,
            "sources": list(self._sources),
            "last_updated": self._last_updated,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

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


async def create_cost_sensors(
    hass: HomeAssistant,
    prix_ht: Optional[float] = None,
    prix_ttc: Optional[float] = None,
    allowed_source_entity_ids: Optional[set[str]] = None,
) -> List[SensorEntity]:
    """
    Crée les sensors coût à partir des sensors energy existants.
    
    Modes:
    - fixe: HT + TTC par cycle
    - hp_hc: HT_HP + TTC_HP + HT_HC + TTC_HC par cycle
    
    allowed_source_entity_ids:
    - None => comportement historique (tous les sensors energy HSE)
    - set() vide ou non fourni => tous les sensors energy HSE
    - set() avec entity_ids => ne génère que pour ces sources
    """
    _LOGGER.warning(
        "HSE-TRACE: create_cost_sensors CALLED prix_ht=%s prix_ttc=%s allowed=%s",
        prix_ht,
        prix_ttc,
        allowed_source_entity_ids
    )
    _LOGGER.info("[COST-TRACKING] ═══════════════════════════════════════")
    _LOGGER.info("[COST-TRACKING] Début création sensors coût")
    
    pricing = get_pricing_config(hass)
    
    # Override API
    if prix_ht is not None and float(prix_ht) > 0:
        pricing["prix_ht"] = float(prix_ht)
        pricing["prix_ht_hp"] = float(prix_ht)
        pricing["prix_ht_hc"] = float(prix_ht)
    if prix_ttc is not None and float(prix_ttc) > 0:
        pricing["prix_ttc"] = float(prix_ttc)
        pricing["prix_ttc_hp"] = float(prix_ttc)
        pricing["prix_ttc_hc"] = float(prix_ttc)
    
    type_contrat = pricing.get("type_contrat", "fixe")
    
    _LOGGER.info(
        "[COST-TRACKING] Type contrat: %s, Prix: HT=%.4f EUR/kWh, TTC=%.4f EUR/kWh",
        type_contrat,
        pricing["prix_ht"],
        pricing["prix_ttc"],
    )
    
    # 🔧 MODIFICATION CRITIQUE: Désactiver l'allowlist si elle est vide
    use_allowlist = (
        allowed_source_entity_ids is not None 
        and len(allowed_source_entity_ids) > 0
    )
    
    if not use_allowlist:
        _LOGGER.info(
            "[COST-TRACKING] Allowlist vide ou non fournie → génération pour TOUS les sensors energy HSE"
        )
    else:
        _LOGGER.info(
            "[COST-TRACKING] Allowlist active: %d sources autorisées",
            len(allowed_source_entity_ids)
        )
    
    # Récupérer tous les sensors energy existants (registry)
    entity_reg = er.async_get(hass)
    existing_energy_sensors: List[str] = []
    filtered_out = 0
    
    for entity_id, entry in entity_reg.entities.items():
        if entry.platform != DOMAIN:
            continue
        if not entity_id.startswith("sensor.hse"):
            continue
        if "energy" not in entity_id.lower():
            continue
        # Exclure les capteurs coût (cout/cost)
        if "cout" in entity_id.lower() or "cost" in entity_id.lower():
            continue
        
        # ✅ MODIFIÉ: Appliquer l'allowlist UNIQUEMENT si elle est fournie ET non vide
        if use_allowlist and entity_id not in allowed_source_entity_ids:
            filtered_out += 1
            _LOGGER.debug(
                "[COST-TRACKING] Sensor %s filtré par allowlist",
                entity_id
            )
            continue
        
        existing_energy_sensors.append(entity_id)
    
    if use_allowlist and filtered_out > 0:
        _LOGGER.info(
            "[COST-TRACKING] Allowlist: %d sources autorisées, %d filtrées",
            len(existing_energy_sensors),
            filtered_out,
        )
    
    _LOGGER.info("[COST-TRACKING] 🔍 %d sensors energy trouvés", len(existing_energy_sensors))
    
    if not existing_energy_sensors:
        _LOGGER.warning("[COST-TRACKING] ⚠️ Aucun sensor energy trouvé !")
        _LOGGER.info("[COST-TRACKING] ═══════════════════════════════════════")
        return []
    
    # Grouper par (basename, cycle)
    energy_map: Dict[Tuple[str, str], str] = {}
    for entity_id in existing_energy_sensors:
        base_raw, cycle = _parse_energy_entity_id(entity_id)
        if not base_raw or not cycle:
            continue
        energy_map[(str(base_raw), str(cycle))] = entity_id
    
    _LOGGER.info("[COST-TRACKING] 📊 %d combinaisons (basename, cycle)", len(energy_map))
    
    cost_sensors: List[SensorEntity] = []
    skipped = 0

    # Track per (basename, cycle) the cost entity ids we generate in hp/hc
    hp_hc_cost_id_map: Dict[Tuple[str, str, str], Dict[str, str]] = {}
    
    for (basename_raw, cycle), energy_entity_id in energy_map.items():
        if cycle not in COST_CYCLES:
            skipped += 1
            continue
        
        basename = _slug_alnum(basename_raw)
        if not basename:
            skipped += 1
            continue
        
        # MODE 1 : Contrat fixe
        if type_contrat in ("fixe", "prix_unique", "prixunique", "unique"):
            for variant in ("ht", "ttc"):
                price = pricing.get(f"prix_{variant}", 0.0)
                cost_sensors.append(
                    HSECostSensor(
                        hass=hass,
                        basename=basename,
                        cycle=cycle,
                        variant=variant,
                        price_per_kwh=price,
                        source_energy_entity=energy_entity_id,
                        tarif_type=None,
                    )
                )
        
        # MODE 2 : Contrat HP/HC
        elif type_contrat == "hp_hc":
            key = (basename, cycle, energy_entity_id)
            hp_hc_cost_id_map.setdefault(key, {})

            for tarif in ("hp", "hc"):
                for variant in ("ht", "ttc"):
                    price = pricing.get(f"prix_{variant}_{tarif}", 0.0)
                    ent = HSECostSensor(
                        hass=hass,
                        basename=basename,
                        cycle=cycle,
                        variant=variant,
                        price_per_kwh=price,
                        source_energy_entity=energy_entity_id,
                        tarif_type=tarif,
                    )
                    cost_sensors.append(ent)

                    # Store the would-be entity_id for aggregate wiring
                    ent_id = f"sensor.hse_{basename}_cout_{cycle}_{variant}_{tarif}"
                    hp_hc_cost_id_map[key][f"{variant}_{tarif}"] = ent_id

    # Add aggregate total sensors for HP/HC: ht = ht_hp + ht_hc, ttc = ttc_hp + ttc_hc
    if type_contrat == "hp_hc":
        for (basename, cycle, _energy_entity_id), ids in hp_hc_cost_id_map.items():
            # TTC total
            src_ttc = []
            if ids.get("ttc_hp"):
                src_ttc.append(ids["ttc_hp"])
            if ids.get("ttc_hc"):
                src_ttc.append(ids["ttc_hc"])
            if src_ttc:
                cost_sensors.append(
                    HSECostAggregateSensor(
                        hass=hass,
                        basename=basename,
                        cycle=cycle,
                        variant="ttc",
                        source_entities=src_ttc,
                    )
                )

            # HT total
            src_ht = []
            if ids.get("ht_hp"):
                src_ht.append(ids["ht_hp"])
            if ids.get("ht_hc"):
                src_ht.append(ids["ht_hc"])
            if src_ht:
                cost_sensors.append(
                    HSECostAggregateSensor(
                        hass=hass,
                        basename=basename,
                        cycle=cycle,
                        variant="ht",
                        source_entities=src_ht,
                    )
                )

    _LOGGER.info("[COST-TRACKING] 🎉 %d sensors créés, %d cycles skipped", len(cost_sensors), skipped)
    _LOGGER.info("[COST-TRACKING] ═══════════════════════════════════════")
    return cost_sensors


# Alias backward-compat (ton API actuelle importe createcostsensors)
createcostsensors = create_cost_sensors


class HSECostSensor(RestoreEntity, SensorEntity):
    """Capteur coût basé sur un capteur énergie HSE existant."""

    def __init__(
        self,
        hass: HomeAssistant,
        basename: str,
        cycle: str,
        variant: str,
        price_per_kwh: float,
        source_energy_entity: str,
        tarif_type: Optional[str] = None,
    ):
        self.hass = hass

        self._basename = basename
        self._cycle = cycle
        self._variant = variant
        self._tarif_type = tarif_type  # None, "hp", "hc"

        self._price_per_kwh = float(price_per_kwh or 0.0)
        self._source_energy_entity = source_energy_entity

        # suffix = ht | ttc | hthp | ttchp | hthc | ttchc
        # Naming: avec underscores (ex: hse_ballonbuanderie_cout_daily_ht)
        if self._tarif_type:
            suffix = f"{self._variant}_{self._tarif_type}"
            name_suffix = f"{self._variant.upper()} {self._tarif_type.upper()}"
        else:
            suffix = self._variant
            name_suffix = self._variant.upper()

        object_id = f"hse_{self._basename}_cout_{self._cycle}_{suffix}"
        self._attr_unique_id = object_id
        self._attr_suggested_object_id = object_id
        self._attr_name = f"HSE {self._basename} Cout {self._cycle.title()} {name_suffix}"

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
        attrs = {
            "basename": self._basename,
            "cycle": self._cycle,
            "variant": self._variant,
            "tarif_type": self._tarif_type or "fixe",
            "price_per_kwh": self._price_per_kwh,
            "currency": self.native_unit_of_measurement,
            "last_updated": self._last_updated,
            # compat attrs (certains modules HSE utilisent 'source_entity')
            "source_entity": self._source_energy_entity,
            "source_energy_entity": self._source_energy_entity,
        }
        return attrs

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

        # Calcul initial si source dispo
        source_state = self.hass.states.get(self._source_energy_entity)
        if source_state:
            try:
                energy_kwh = float(source_state.state)
                self._state = max(0.0, energy_kwh * self._price_per_kwh)
                self._last_updated = dt_util.now().isoformat()
                _LOGGER.debug(
                    "[COST-SENSOR] %s calcul initial: %.4f kWh × %.6f = %.4f %s",
                    self.entity_id,
                    energy_kwh,
                    self._price_per_kwh,
                    self._state,
                    self.native_unit_of_measurement,
                )
            except (ValueError, TypeError) as e:
                _LOGGER.debug("[COST-SENSOR] %s erreur calcul initial: %s", self.entity_id, e)

        # Écouter changements
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_energy_entity],
                self._on_source_changed,
            )
        )

    @callback
    def _on_source_changed(self, event):
        new_state = event.data.get("new_state")
        if not new_state or new_state.state in ("unknown", "unavailable"):
            return

        try:
            energy_kwh = float(new_state.state)
        except (ValueError, TypeError):
            return

        self._state = max(0.0, energy_kwh * self._price_per_kwh)
        self._last_updated = dt_util.now().isoformat()
        self.async_write_ha_state()
