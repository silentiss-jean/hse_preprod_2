# -*- coding: utf-8 -*-

"""
Storage Manager - Gestionnaire centralisé de la Storage API Home Assistant.

Objectifs (clean + rétro-compat) :
- Stockage persistant via Store HA
- Migration depuis fichiers legacy (data/*.json)
- Normalisation des clés vers les CANONS const.py (snake_case + underscore)
- Tolérance en lecture aux clés legacy :
  - camelCase (typeContrat, useExternal, ...)
  - compact sans underscore (typecontrat, useexternal, abonnementht, ...)
- Normalisation des valeurs sensibles :
  - type_contrat -> prix_unique | heures_creuses
- Point d’entrée unique pour une config "effective" (Store + entry.data + entry.options)

Extensions (group_sets v1) :
- Nouveau store canon group_sets: sets.rooms + sets.types + ...
- Rétro-compat: sensor_groups (get_sensor_groups/save_sensor_groups) devient un alias de group_sets.sets.rooms.groups
"""

import logging
import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    STORAGE_VERSION,
    STORE_USER_CONFIG,
    STORE_CAPTEURS_SELECTION,
    CAPTEURS_POWER_STORAGE_VERSION,  # ← À AJOUTER
    STORE_CAPTEURS_POWER,             # ← À AJOUTER
    STORE_IGNORED_ENTITIES,
    STORE_SENSOR_GROUPS,
    KEY_ALIASES_TO_CANONICAL,
    CONF_TYPE_CONTRAT,
    CONF_USE_EXTERNAL,
    CONF_EXTERNAL_CAPTEUR,
    CONF_CONSOMMATION_EXTERNE,
    CONF_ENABLE_COST_SENSORS_RUNTIME,
    CONF_ABONNEMENT_MENSUEL_HT,
    CONF_ABONNEMENT_MENSUEL_TTC,
    CONF_PRIX_HT,
    CONF_PRIX_TTC,
    CONF_PRIX_HT_HP,
    CONF_PRIX_TTC_HP,
    CONF_PRIX_HT_HC,
    CONF_PRIX_TTC_HC,
    CONF_HC_START,
    CONF_HC_END,
    CONF_MODE,
    GROUP_SETS_STORAGE_VERSION,
    STORE_GROUP_SETS,
)

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rétro-compat imports (anciens fichiers qui importaient ces noms)
# ---------------------------------------------------------------------------

# to delete STORAGEVERSION = 2
IGNORED_ENTITIES_STORAGE_VERSION = 2
SENSOR_GROUPS_STORAGE_VERSION = 2
COST_HA_STORAGE_VERSION = 1
STORE_COST_HA = "home_suivi_elec_cost_ha_v1"

# ---------------------------------------------------------------------------
# Legacy files (migration)
# ---------------------------------------------------------------------------

LEGACY_DATA_DIR = Path(__file__).parent / "data"
LEGACY_USER_CONFIG = LEGACY_DATA_DIR / "userconfig.json"
LEGACY_CAPTEURS_SELECTION = LEGACY_DATA_DIR / "capteursselection.json"
LEGACY_CAPTEURS_POWER = LEGACY_DATA_DIR / "capteurs_power.json"


# ---------------------------------------------------------------------------
# Normalisation clés/valeurs
# ---------------------------------------------------------------------------

_FALLBACK_ALIASES = {
    # camelCase
    "typeContrat": CONF_TYPE_CONTRAT,
    "useExternal": CONF_USE_EXTERNAL,
    "externalCapteur": CONF_EXTERNAL_CAPTEUR,
    "consommationExterne": CONF_CONSOMMATION_EXTERNE,
    "enableCostSensorsRuntime": CONF_ENABLE_COST_SENSORS_RUNTIME,
    "abonnementHT": CONF_ABONNEMENT_MENSUEL_HT,
    "abonnementTTC": CONF_ABONNEMENT_MENSUEL_TTC,
    # compact
    "typecontrat": CONF_TYPE_CONTRAT,
    "useexternal": CONF_USE_EXTERNAL,
    "externalcapteur": CONF_EXTERNAL_CAPTEUR,
    "consommationexterne": CONF_CONSOMMATION_EXTERNE,
    "enablecostsensorsruntime": CONF_ENABLE_COST_SENSORS_RUNTIME,
    "abonnementht": CONF_ABONNEMENT_MENSUEL_HT,
    "abonnementttc": CONF_ABONNEMENT_MENSUEL_TTC,
    "prixht": CONF_PRIX_HT,
    "prixttc": CONF_PRIX_TTC,
    "prixhthp": CONF_PRIX_HT_HP,
    "prixttchp": CONF_PRIX_TTC_HP,
    "prixhthc": CONF_PRIX_HT_HC,
    "prixttchc": CONF_PRIX_TTC_HC,
    "hcstart": CONF_HC_START,
    "hcend": CONF_HC_END,
}

_ALIASES = dict(KEY_ALIASES_TO_CANONICAL)
_ALIASES.update(_FALLBACK_ALIASES)


def normalize_type_contrat(v: Any) -> str:
    """Normalise type_contrat vers valeurs canon: prix_unique | heures_creuses."""
    if v is None:
        return "prix_unique"
    s = str(v).strip().lower()
    if s in ("hp-hc", "hphc", "heurescreuses", "heures_creuses"):
        return "heures_creuses"
    if s in ("fixe", "prixunique", "prix_unique"):
        return "prix_unique"
    return s or "prix_unique"


def _normalize_key(k: Any) -> Any:
    """Retourne la clé canon si c'est une string connue, sinon renvoie k tel quel."""
    if not isinstance(k, str):
        return k
    raw = k.strip()
    if raw in _ALIASES:
        return _ALIASES[raw]
    low = raw.lower()
    if low in _ALIASES:
        return _ALIASES[low]
    return raw


def contains_camelcase_keys(d: Dict[str, Any]) -> bool:
    """Détecte du camelCase (ou toute clé contenant une majuscule)."""
    for k in (d or {}).keys():
        if isinstance(k, str) and any(c.isupper() for c in k):
            return True
    return False


def normalize_dict_keys_deep(obj: Any) -> Any:
    """Normalisation récursive des clés via _normalize_key()."""
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            nk = _normalize_key(k)
            out[nk] = normalize_dict_keys_deep(v)
        return out
    if isinstance(obj, list):
        return [normalize_dict_keys_deep(x) for x in obj]
    return obj


def normalize_user_config(d: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise userconfig vers canons const.py + defaults."""
    out = normalize_dict_keys_deep(dict(d or {}))

    # defaults "présence"
    out.setdefault(CONF_TYPE_CONTRAT, "prix_unique")
    out.setdefault(CONF_EXTERNAL_CAPTEUR, None)
    out.setdefault(CONF_USE_EXTERNAL, False)
    out.setdefault(CONF_MODE, "sensor")
    out.setdefault(CONF_CONSOMMATION_EXTERNE, None)
    out.setdefault(CONF_ENABLE_COST_SENSORS_RUNTIME, False)
    out.setdefault("version", STORAGE_VERSION)

    # normalisations de valeurs
    out[CONF_TYPE_CONTRAT] = normalize_type_contrat(out.get(CONF_TYPE_CONTRAT))
    out[CONF_USE_EXTERNAL] = bool(out.get(CONF_USE_EXTERNAL))
    out[CONF_ENABLE_COST_SENSORS_RUNTIME] = bool(out.get(CONF_ENABLE_COST_SENSORS_RUNTIME))

    return out


# ---------------------------------------------------------------------------
# Storage Manager
# ---------------------------------------------------------------------------

class StorageManager:
    """Gestionnaire centralisé de la Storage API Home Assistant."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.cache: Dict[str, Any] = {}

        # Stores principaux v2
        self.store_user_config = Store(hass, STORAGE_VERSION, STORE_USER_CONFIG)
        self.store_selection = Store(hass, STORAGE_VERSION, STORE_CAPTEURS_SELECTION)
        self.store_capteurs_power = Store(hass, CAPTEURS_POWER_STORAGE_VERSION, STORE_CAPTEURS_POWER)

        # Stores annexes v1
        self.store_ignored = Store(
            hass,
            IGNORED_ENTITIES_STORAGE_VERSION,
            STORE_IGNORED_ENTITIES,
        )

        # Legacy: store des groupes "sensor_groups"
        self.store_groups = Store(
            hass,
            SENSOR_GROUPS_STORAGE_VERSION,
            STORE_SENSOR_GROUPS,
        )

        # ✅ Canon: store group_sets
        self.store_group_sets = Store(
            hass,
            GROUP_SETS_STORAGE_VERSION,
            STORE_GROUP_SETS,
        )

        # Nouveau store pour Coût HA
        self.store_cost_ha = Store(
            hass,
            COST_HA_STORAGE_VERSION,
            STORE_COST_HA,
        )

        _LOGGER.info("STORAGE-MANAGER Initialisé version=%s", STORAGE_VERSION)

    # ---------------------------------------------------------------------
    # Helpers group_sets
    # ---------------------------------------------------------------------

    def _default_group_sets(self) -> Dict[str, Any]:
        return {
            "version": GROUP_SETS_STORAGE_VERSION,
            "sets": {
                "rooms": {"mode": "exclusive", "groups": {}},
                "types": {"mode": "multi", "groups": {}},
            },
        }

    def _ensure_group_sets_shape(self, raw: Any) -> Dict[str, Any]:
        """Retourne un dict canon {version, sets:{rooms:{mode,groups}, types:{...}}} avec fallback safe."""
        if not isinstance(raw, dict):
            return self._default_group_sets()

        out: Dict[str, Any] = dict(raw)
        out.setdefault("version", GROUP_SETS_STORAGE_VERSION)
        sets = out.get("sets")
        if not isinstance(sets, dict):
            out["sets"] = {}
            sets = out["sets"]

        # rooms
        rooms = sets.get("rooms")
        if not isinstance(rooms, dict):
            rooms = {}
            sets["rooms"] = rooms
        rooms.setdefault("mode", "exclusive")
        if not isinstance(rooms.get("groups"), dict):
            rooms["groups"] = {}

        # types
        types = sets.get("types")
        if not isinstance(types, dict):
            types = {}
            sets["types"] = types
        types.setdefault("mode", "multi")
        if not isinstance(types.get("groups"), dict):
            types["groups"] = {}

        return out

    def _coerce_legacy_groups_to_dict(self, legacy: Any) -> Dict[str, Any]:
        """\
        Migration soft: accepte plusieurs formes legacy et renvoie toujours un dict {group_name: {..}}.

        Formes supportées :
        - dict déjà conforme -> retourné tel quel
        - list[dict] où chaque item est du style {name, mode?, energy?, power?}
        - list[str] (très vieux) -> convertit en {name:{name,mode:"manual",energy:[],power:[]}}
        """
        if isinstance(legacy, dict):
            return legacy

        if isinstance(legacy, list):
            out: Dict[str, Any] = {}
            for item in legacy:
                # Cas liste de noms
                if isinstance(item, str):
                    name = item.strip() or ""
                    if not name:
                        continue
                    out[name] = {
                        "name": name,
                        "mode": "manual",
                        "energy": [],
                        "power": [],
                    }
                    continue

                # Cas liste d'objets
                if isinstance(item, dict):
                    name = str(item.get("name") or item.get("group") or "").strip()
                    if not name:
                        continue

                    mode = str(item.get("mode") or "manual")
                    energy = item.get("energy", [])
                    power = item.get("power", [])

                    out[name] = {
                        "name": name,
                        "mode": mode,
                        "energy": list(energy) if isinstance(energy, list) else [],
                        "power": list(power) if isinstance(power, list) else [],
                    }

            return out

        return {}

    async def get_group_sets(self, forcereload: bool = False) -> Dict[str, Any]:
        cachekey = "group_sets"
        if not forcereload and cachekey in self.cache and isinstance(self.cache[cachekey], dict):
            return self.cache[cachekey]

        # 1) Lire le store canon
        raw = await self.store_group_sets.async_load()
        group_sets = self._ensure_group_sets_shape(raw)

        # 2) Migration auto depuis legacy sensor_groups -> sets.rooms.groups
        rooms_groups = group_sets.get("sets", {}).get("rooms", {}).get("groups", {})
        if isinstance(rooms_groups, dict) and len(rooms_groups) == 0:
            legacy_raw = await self.store_groups.async_load()
            legacy = self._coerce_legacy_groups_to_dict(legacy_raw)

            if len(legacy) > 0:
                group_sets["sets"]["rooms"]["groups"] = legacy
                try:
                    await self.store_group_sets.async_save(group_sets)
                    _LOGGER.info(
                        "STORAGE group_sets: migration legacy sensor_groups -> sets.rooms.groups (%s groupes)",
                        len(legacy),
                    )
                except Exception:
                    _LOGGER.exception("STORAGE group_sets: erreur sauvegarde post-migration")

        self.cache[cachekey] = group_sets
        return group_sets

    async def save_group_sets(self, group_sets: Dict[str, Any]) -> bool:
        try:
            clean = self._ensure_group_sets_shape(group_sets)
            await self.store_group_sets.async_save(clean)
            self.cache["group_sets"] = clean

            # Optionnel: synchro legacy store_groups pour compat immédiate
            rooms_groups = clean.get("sets", {}).get("rooms", {}).get("groups", {})
            if isinstance(rooms_groups, dict):
                await self.store_groups.async_save(rooms_groups)
                self.cache["sensor_groups"] = rooms_groups

            return True
        except Exception as e:
            _LOGGER.exception("STORAGE Erreur save_group_sets: %s", e)
            return False

    # ---------------------------------------------------------------------
    # Rétro-compat : groups (Pièces)
    # ---------------------------------------------------------------------

    async def get_sensor_groups(self, forcereload: bool = False) -> Dict[str, Any]:
        """Legacy API: retourne le mapping groups des pièces (= group_sets.sets.rooms.groups)."""
        gs = await self.get_group_sets(forcereload=forcereload)
        groups = gs.get("sets", {}).get("rooms", {}).get("groups", {})
        if not isinstance(groups, dict):
            groups = {}
        # Maintenir aussi l'ancien cachekey pour code existant
        self.cache["sensor_groups"] = groups
        return groups

    async def save_sensor_groups(self, groups: Dict[str, Any]) -> bool:
        """Legacy API: sauve groups des pièces dans group_sets + sync legacy store."""
        if not isinstance(groups, dict):
            _LOGGER.error("STORAGE sensor_groups invalide (pas un dict)")
            return False

        gs = await self.get_group_sets(forcereload=False)
        gs = self._ensure_group_sets_shape(gs)
        gs["sets"]["rooms"]["groups"] = groups
        ok = await self.save_group_sets(gs)
        if ok:
            self.cache["sensor_groups"] = groups
            _LOGGER.info("STORAGE sensor_groups sauvegardés (via group_sets) (%s groupes)", len(groups))
        return ok

    # ---------------------------------------------------------------------
    # Le reste du StorageManager (inchangé)
    # ---------------------------------------------------------------------

    def get_first_entry(self):
        entries = self.hass.config_entries.async_entries(DOMAIN)
        return entries[0] if entries else None

    def _is_wrapper(self, obj: Any) -> bool:
        if not isinstance(obj, dict):
            return False
        if "data" not in obj:
            return False
        allowed = {"version", "minor_version", "key", "data"}
        if not set(obj.keys()).issubset(allowed):
            return False
        v = obj.get("version", None)
        d = obj.get("data", None)
        return isinstance(v, int) and isinstance(d, dict)

    def _extract_cost_ha_mapping(self, raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return {}
        cur: Any = raw.get("data", raw)
        for _ in range(10):
            if self._is_wrapper(cur):
                cur = cur.get("data", {})
                continue
            break
        return cur if isinstance(cur, dict) else {}

    def _unwrap_cost_ha_map(self, raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return {}
        cur: Any = raw.get("data", raw)
        for _ in range(10):
            if (
                isinstance(cur, dict)
                and "data" in cur
                and isinstance(cur.get("data"), dict)
                and isinstance(cur.get("version", 1), int)
                and set(cur.keys()).issubset({"version", "minor_version", "key", "data"})
            ):
                cur = cur["data"]
                continue
            break
        return cur if isinstance(cur, dict) else {}

    async def get_cost_ha_config(self) -> Dict[str, Any]:
        cache_key = "cost_ha_config"
        if cache_key in self.cache and isinstance(self.cache[cache_key], dict):
            return self.cache[cache_key]

        raw = await self.store_cost_ha.async_load()
        sensors_map = self._unwrap_cost_ha_map(raw)

        try:
            if isinstance(raw, dict):
                root_data = raw.get("data")
                if isinstance(root_data, dict) and "data" in root_data and "version" in root_data:
                    await self.store_cost_ha.async_save(sensors_map)
        except Exception:
            pass

        self.cache[cache_key] = sensors_map
        return sensors_map

    async def save_cost_ha_config(self, sensors_map: Dict[str, Any]) -> bool:
        try:
            clean_map = self._unwrap_cost_ha_map(sensors_map)
            await self.store_cost_ha.async_save(clean_map)
            self.cache["cost_ha_config"] = clean_map
            return True
        except Exception as e:
            _LOGGER.exception("STORAGE Erreur save_cost_ha_config: %s", e)
            return False

    async def ensure_cost_sensor_for(self, entity_id: str, enabled: bool) -> Dict[str, Any]:
        sensors_map = await self.get_cost_ha_config()

        entry = sensors_map.get(entity_id) or {"enabled": False, "cost_entity_id": None}
        if not isinstance(entry, dict):
            entry = {"enabled": False, "cost_entity_id": None}

        entry["enabled"] = bool(enabled)
        cost_entity_id = entry.get("cost_entity_id")

        if enabled:
            cost_entity_id = await self._create_or_update_cost_sensor(entity_id, cost_entity_id)
            entry["cost_entity_id"] = cost_entity_id
        else:
            pass

        sensors_map[entity_id] = entry
        await self.save_cost_ha_config(sensors_map)

        return {
            "enabled": bool(entry.get("enabled", False)),
            "cost_entity_id": entry.get("cost_entity_id"),
        }

    async def _create_or_update_cost_sensor(
        self,
        source_entity_id: str,
        existing_cost_entity_id: Optional[str],
    ) -> str:
        user_cfg = await self.get_user_config()
        prix_ht = float(user_cfg.get(CONF_PRIX_HT, 0.0) or 0.0)
        prix_ttc = float(user_cfg.get(CONF_PRIX_TTC, 0.0) or 0.0)

        slug = source_entity_id.replace(".", "_")
        cost_entity_id = existing_cost_entity_id or f"sensor.hse_cost_{slug}"

        _LOGGER.info(
            "[COST-HA] ensure_cost_sensor_for %s -> %s (HT=%.4f, TTC=%.4f, v1 soft)",
            source_entity_id,
            cost_entity_id,
            prix_ht,
            prix_ttc,
        )

        return cost_entity_id

    async def get_user_config(self, forcereload: bool = False) -> Dict[str, Any]:
        cachekey = "user_config"
        if not forcereload and cachekey in self.cache:
            return self.cache[cachekey]

        data = await self.store_user_config.async_load()
        if data is None:
            data = {}
        normalized_store = normalize_user_config(data)
        if normalized_store != data:
            await self.store_user_config.async_save(normalized_store)

        eff: Dict[str, Any] = dict(normalized_store)

        try:
            entry = self.get_first_entry()
            if entry:
                raw_data = dict(entry.data or {})
                raw_opts = dict(entry.options or {})

                norm_data = normalize_user_config(raw_data)
                norm_opts = normalize_user_config(raw_opts)

                if norm_opts != raw_opts:
                    self.hass.config_entries.async_update_entry(entry, options=norm_opts)
                eff.update(norm_data)
                eff.update(norm_opts)
        except Exception as e:
            _LOGGER.warning("STORAGE Impossible de lire/migrer configentry: %s", e)

        eff = normalize_user_config(eff)
        self.cache[cachekey] = eff
        return eff

    async def save_user_config(self, cfg: Dict[str, Any], strict: bool = False) -> bool:
        if not isinstance(cfg, dict):
            return False

        if strict and contains_camelcase_keys(cfg):
            _LOGGER.error("STORAGE Payload camelCase refusé (strict=True): %s", list(cfg.keys()))
            return False

        normalized = normalize_user_config(cfg)
        await self.store_user_config.async_save(normalized)
        self.cache["user_config"] = normalized
        return True

    async def get_capteurs_power(self, forcereload: bool = False) -> List[Dict[str, Any]]:
        cachekey = "capteurs_power"
        if not forcereload and cachekey in self.cache:
            return self.cache[cachekey]

        data = await self.store_capteurs_power.async_load()
        if data is None:
            _LOGGER.info("STORAGE capteurs_power vide, initialisation...")
            data = []

        if not isinstance(data, list):
            data = []

        data = [x for x in data if isinstance(x, dict)]
        self.cache[cachekey] = data
        return data

    async def save_capteurs_power(self, capteurs: List[Dict[str, Any]]) -> bool:
        try:
            if not isinstance(capteurs, list):
                _LOGGER.error("STORAGE capteurs_power invalide (pas une liste)")
                return False

            clean = [x for x in capteurs if isinstance(x, dict)]
            await self.store_capteurs_power.async_save(clean)
            self.cache["capteurs_power"] = clean
            _LOGGER.info("STORAGE capteurs_power sauvegardé (%s entrées)", len(clean))
            return True
        except Exception as e:
            _LOGGER.exception("STORAGE Erreur sauvegarde capteurs_power: %s", e)
            return False

    async def get_capteurs_selection(self, forcereload: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        cachekey = "capteurs_selection"
        if not forcereload and cachekey in self.cache:
            return self.cache[cachekey]

        data = await self.store_selection.async_load()
        if data is None:
            _LOGGER.info("STORAGE capteurs_selection vide, initialisation...")
            data = {}

        if not isinstance(data, dict):
            data = {}

        self.cache[cachekey] = data
        return data

    async def save_capteurs_selection(self, selection: Dict[str, List[Dict[str, Any]]]) -> bool:
        try:
            if not isinstance(selection, dict):
                _LOGGER.error("STORAGE capteurs_selection invalide (pas un dict)")
                return False

            await self.store_selection.async_save(selection)
            self.cache["capteurs_selection"] = selection

            total_sensors = sum(len(sensors) for sensors in selection.values() if isinstance(sensors, list))
            _LOGGER.info("STORAGE capteurs_selection sauvegardée (%s capteurs)", total_sensors)
            return True
        except Exception as e:
            _LOGGER.exception("STORAGE Erreur sauvegarde capteurs_selection: %s", e)
            return False

    async def update_sensor_enabled(self, entity_id: str, enabled: bool) -> bool:
        selection = await self.get_capteurs_selection()
        for _, sensors in selection.items():
            for sensor in sensors:
                if sensor.get("entityid") == entity_id or sensor.get("entity_id") == entity_id or sensor.get("entityId") == entity_id:
                    sensor["enabled"] = enabled
                    await self.save_capteurs_selection(selection)
                    _LOGGER.info("STORAGE Capteur %s enabled=%s", entity_id, enabled)
                    return True
        _LOGGER.warning("STORAGE Capteur %s non trouvé", entity_id)
        return False

    async def get_ignored_entities(self, forcereload: bool = False) -> List[str]:
        cachekey = "ignored_entities"
        if not forcereload and cachekey in self.cache:
            return self.cache[cachekey]

        data = await self.store_ignored.async_load()

        if data is None:
            entities: List[str] = []
        elif isinstance(data, list):
            entities = [str(x) for x in data if x]
        elif isinstance(data, dict):
            raw = data.get("entities", [])
            entities = [str(x) for x in raw if x] if isinstance(raw, list) else []
        else:
            entities = []

        self.cache[cachekey] = entities
        return entities

    async def save_ignored_entities(self, entities: List[str]) -> bool:
        try:
            if not isinstance(entities, list):
                _LOGGER.error("STORAGE ignored_entities invalide (pas une liste)")
                return False

            entities = sorted(set(str(x) for x in entities if x))
            payload = {"entities": entities, "version": 1}
            await self.store_ignored.async_save(payload)

            self.cache["ignored_entities"] = entities
            _LOGGER.info("STORAGE ignored_entities sauvegardée (%s entités)", len(entities))
            return True
        except Exception as e:
            _LOGGER.exception("STORAGE Erreur sauvegarde ignored_entities: %s", e)
            return False

    async def add_ignored_entity(self, entity_id: str) -> bool:
        entities = await self.get_ignored_entities()
        if entity_id not in entities:
            entities.append(entity_id)
            return await self.save_ignored_entities(entities)
        return True

    async def remove_ignored_entity(self, entity_id: str) -> bool:
        entities = await self.get_ignored_entities()
        if entity_id in entities:
            entities.remove(entity_id)
            return await self.save_ignored_entities(entities)
        return True

    async def migrate_from_legacy_files(self) -> bool:
        _LOGGER.info("MIGRATION Vérification fichiers legacy...")
        migrated_any = False

        def load_json_file(filepath: Path):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)

        def rename_file(src: Path, dst: Path):
            src.rename(dst)

        if LEGACY_USER_CONFIG.exists():
            try:
                _LOGGER.info("MIGRATION Migration userconfig.json...")
                legacy_data = await self.hass.async_add_executor_job(load_json_file, LEGACY_USER_CONFIG)
                await self.save_user_config(legacy_data, strict=False)

                backup_path = LEGACY_USER_CONFIG.with_suffix(".json.migrated")
                await self.hass.async_add_executor_job(rename_file, LEGACY_USER_CONFIG, backup_path)
                _LOGGER.info("MIGRATION userconfig.json migré -> backup %s", backup_path.name)
                migrated_any = True
            except Exception as e:
                _LOGGER.exception("MIGRATION Erreur migration userconfig.json: %s", e)
                return False

        if LEGACY_CAPTEURS_SELECTION.exists():
            try:
                _LOGGER.info("MIGRATION Migration capteursselection.json...")
                legacy_data = await self.hass.async_add_executor_job(load_json_file, LEGACY_CAPTEURS_SELECTION)
                await self.save_capteurs_selection(legacy_data)

                backup_path = LEGACY_CAPTEURS_SELECTION.with_suffix(".json.migrated")
                await self.hass.async_add_executor_job(rename_file, LEGACY_CAPTEURS_SELECTION, backup_path)
                _LOGGER.info("MIGRATION capteursselection.json migré -> backup %s", backup_path.name)
                migrated_any = True
            except Exception as e:
                _LOGGER.exception("MIGRATION Erreur migration capteursselection.json: %s", e)
                return False

        if LEGACY_CAPTEURS_POWER.exists():
            try:
                _LOGGER.info("MIGRATION Migration capteurs_power.json...")
                legacy_data = await self.hass.async_add_executor_job(load_json_file, LEGACY_CAPTEURS_POWER)
                await self.save_capteurs_power(legacy_data)
                backup_path = LEGACY_CAPTEURS_POWER.with_suffix(".json.migrated")
                await self.hass.async_add_executor_job(rename_file, LEGACY_CAPTEURS_POWER, backup_path)
                _LOGGER.info("MIGRATION capteurs_power.json migré -> backup %s", backup_path.name)
                migrated_any = True
            except Exception as e:
                _LOGGER.exception("MIGRATION Erreur migration capteurs_power.json: %s", e)
                return False

        _LOGGER.info("MIGRATION %s", "Migration terminée" if migrated_any else "Aucun fichier legacy à migrer")
        return True

    async def export_to_json(self, outputdir: Path) -> bool:
        try:
            outputdir.mkdir(parents=True, exist_ok=True)

            userconfig = await self.get_user_config()
            with open(outputdir / "userconfig.json", "w", encoding="utf-8") as f:
                json.dump(userconfig, f, indent=2, ensure_ascii=False)

            selection = await self.get_capteurs_selection()
            with open(outputdir / "capteursselection.json", "w", encoding="utf-8") as f:
                json.dump(selection, f, indent=2, ensure_ascii=False)

            ignored = await self.get_ignored_entities()
            with open(outputdir / "ignoredentities.json", "w", encoding="utf-8") as f:
                json.dump(ignored, f, indent=2, ensure_ascii=False)

            groups = await self.get_sensor_groups()
            with open(outputdir / "sensorgroups.json", "w", encoding="utf-8") as f:
                json.dump(groups, f, indent=2, ensure_ascii=False)

            # group_sets export
            group_sets = await self.get_group_sets()
            with open(outputdir / "groupsets.json", "w", encoding="utf-8") as f:
                json.dump(group_sets, f, indent=2, ensure_ascii=False)

            _LOGGER.info("EXPORT Données exportées vers %s", outputdir)
            return True
        except Exception as e:
            _LOGGER.exception("EXPORT Erreur export JSON: %s", e)
            return False

    def clear_cache(self) -> None:
        self.cache.clear()
        _LOGGER.info("STORAGE Cache vidé")

    async def get_storage_stats(self) -> Dict[str, Any]:
        userconfig = await self.get_user_config()
        selection = await self.get_capteurs_selection()
        ignored = await self.get_ignored_entities()

        total_sensors = sum(len(sensors) for sensors in selection.values() if isinstance(sensors, list))
        enabled_sensors = sum(
            len([s for s in sensors if isinstance(s, dict) and s.get("enabled", False)])
            for sensors in selection.values()
            if isinstance(sensors, list)
        )

        return {
            "version": STORAGE_VERSION,
            "user_config": {
                "has_reference": userconfig.get(CONF_EXTERNAL_CAPTEUR) is not None,
                "options_count": len(userconfig) if isinstance(userconfig, dict) else 0,
            },
            "capteurs_selection": {
                "zones": len(selection),
                "total_sensors": total_sensors,
                "enabled_sensors": enabled_sensors,
                "disabled_sensors": total_sensors - enabled_sensors,
            },
            "ignored_entities": {"count": len(ignored)},
            "cache_size": len(self.cache),
        }
