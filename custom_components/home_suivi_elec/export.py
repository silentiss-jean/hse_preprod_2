# custom_components/home_suivi_elec/export.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from pathlib import Path
import json
import logging

import yaml
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from .const import DOMAIN 

_LOGGER = logging.getLogger(__name__)

COMPONENT_DIR = Path(__file__).parent
DATA_DIR = COMPONENT_DIR / "data"
POWER_FILE = DATA_DIR / "capteurs_power.json"

def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

class ExportService:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.entity_registry = er.async_get(hass)

    # ---------- Helpers génériques ----------

    async def _load_json_file(self, path: Path, default):
        import asyncio

        def _load():
            if not path.exists():
                return default
            try:
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:  # noqa: BLE001
                _LOGGER.error("Erreur lecture %s: %s", path, e)
                return default

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _load)

    async def _load_power_sensors(self) -> List[Dict[str, Any]]:
        """Charge capteurs_power.json (catalogue capteurs)."""
        return await self._load_json_file(POWER_FILE, default=[])

    async def _load_storage_selection(self) -> Dict[str, Any]:
        """Charge la sélection v2 depuis le Storage API (.storage)."""
        import asyncio

        storage_path = Path(self.hass.config.path(".storage")) / "home_suivi_elec_capteurs_selection_v2"

        def _load():
            if not storage_path.exists():
                return {}
            try:
                with storage_path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                return raw.get("data", {})
            except Exception as e:  # noqa: BLE001
                _LOGGER.error("Erreur lecture %s: %s", storage_path, e)
                return {}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _load)

    async def _load_ignored_entities(self) -> List[str]:
        """Charge la liste des entités ignorées depuis Storage API."""
        import asyncio

        storage_path = Path(self.hass.config.path(".storage")) / "home_suivi_elec_ignored_entities_v1"

        def _load():
            if not storage_path.exists():
                return []
            try:
                with storage_path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                return raw.get("data", {}).get("entities", [])
            except Exception as e:  # noqa: BLE001
                _LOGGER.error("Erreur lecture %s: %s", storage_path, e)
                return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _load)

    async def _get_enabled_sensors(self) -> List[Dict[str, Any]]:
        """
        Fusionne:
          - capteurs_power.json (métadonnées)
          - sélection Storage v2 (enabled)
          - liste des entités ignorées
        pour produire la liste des capteurs éligibles à l'export.
        """
        power_sensors = await self._load_power_sensors()
        selection_data = await self._load_storage_selection()
        ignored_entities = set(await self._load_ignored_entities())

        # selection_data est de la forme {"template": [...], "un_autre_groupe": [...]}
        enabled_ids: set[str] = set()
        for group, items in selection_data.items():
            if not isinstance(items, list):
                continue
            for item in items:
                eid = item.get("entity_id")
                if eid and item.get("enabled", False):
                    enabled_ids.add(eid)

        enabled: List[Dict[str, Any]] = []
        for sensor in power_sensors:
            eid = sensor.get("entity_id")
            if not eid:
                continue
            if eid not in enabled_ids:
                continue
            if eid in ignored_entities:
                continue
            # Optionnel: filtrer uniquement les 'energy'
            if sensor.get("type") != "energy":
                continue

            # friendly_name depuis HA si dispo
            state_obj = self.hass.states.get(eid)
            friendly = sensor.get("friendly_name") or eid
            if state_obj:
                friendly = state_obj.attributes.get("friendly_name", friendly)

            enabled.append(
                {
                    "entity_id": eid,
                    "friendly_name": friendly,
                }
            )

        _LOGGER.info(
            "ExportService: %s capteurs éligibles à l'export (sur %s dans capteurs_power)",
            len(enabled),
            len(power_sensors),
        )
        return enabled

    # ---------- Génération YAML utility_meter ----------

    async def generate_utility_meter_yaml(self) -> str:
        """
        Génère le YAML utility_meter pour tous les capteurs sélectionnés.

        Retourne une chaîne YAML prête à écrire dans configuration.yaml
        (clé racine: utility_meter: …).
        """
        sensors = await self._get_enabled_sensors()
        cycles = ["daily", "weekly", "monthly", "yearly"]

        utility_meters: Dict[str, Dict[str, Any]] = {}

        for sensor in sensors:
            eid = sensor["entity_id"]
            friendly = sensor["friendly_name"]
            # On enlève le préfixe domain.
            short = eid.split(".", 1)[1]

            for cycle in cycles:
                meter_name = f"{short}_{cycle}"
                utility_meters[meter_name] = {
                    "source": eid,
                    "cycle": cycle,
                    "name": f"{friendly} {cycle.capitalize()}",
                }

        yaml_content = {"utility_meter": utility_meters}
        yaml_str = yaml.dump(
            yaml_content,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        return yaml_str

    # ---------- Génération YAML template sensors (Riemann) ----------

    async def generate_template_sensors_yaml(self) -> str:
        """
        Génère un YAML de template sensors de type « power → energy »,
        prêt à utiliser avec une intégration de type Riemann.
        """
        sensors = await self._get_enabled_sensors()

        templates: List[Dict[str, Any]] = []
        integrations: List[Dict[str, Any]] = []

        for sensor in sensors:
            eid = sensor["entity_id"]
            friendly = sensor["friendly_name"]
            short = eid.split(".", 1)[1]

            power_entity_id = f"sensor.{short}_power_template"
            energy_entity_id = f"sensor.{short}_energy"

            # Template power (W) → on se contente de refléter la source
            templates.append(
                {
                    "name": f"{friendly} Power",
                    "unique_id": f"{short}_power_template",
                    "state": f"{{{{ states('{eid}') | float(0) }}}}",
                    "unit_of_measurement": "W",
                    "device_class": "power",
                    "state_class": "measurement",
                }
            )

            # Intégration energy (kWh) type Riemann
            integrations.append(
                {
                    "platform": "integration",
                    "source": power_entity_id,
                    "name": f"{friendly} Energy",
                    "unique_id": f"{short}_energy",
                    "method": "trapezoidal",
                    "unit_prefix": "k",
                    "round": 2,
                }
            )

        yaml_content = {
            "template": templates,
            "sensor": integrations,
        }
        yaml_str = yaml.dump(
            yaml_content,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        return yaml_str

    async def create_helpers_auto(
        self,
        sensors: List[Dict[str, Any]],
        cycles: List[str],
    ) -> Dict[str, Any]:
        """Crée automatiquement des utility_meter pour chaque capteur × cycle.

        Retourne:
            {
                "success": bool,
                "created": [entity_id...],
                "skipped_existing": [entity_id...],
                "errors": [str...],
            }
        """

        # Si aucun capteur n'est fourni, on s'appuie sur la sélection backend
        # (même logique que pour generate_utility_meter_yaml / templates).
        if not sensors:
            base_sensors = await self._get_enabled_sensors()
            sensors = []
            for sensor in base_sensors:
                eid = sensor.get("entity_id")
                if not eid:
                    continue
                name = (
                    sensor.get("name")
                    or sensor.get("friendly_name")
                    or eid
                )
                sensors.append({"entity_id": eid, "name": name})

        # Si malgré tout il n'y a aucun capteur, on renvoie une erreur claire
        if not sensors:
            return {
                "success": False,
                "created": [],
                "skipped_existing": [],
                "errors": ["Aucun capteur éligible trouvé dans la sélection"],
            }

        if not cycles:
            cycles = ["daily", "weekly", "monthly", "yearly"]

        created: List[str] = []
        skipped_existing: List[str] = []
        errors: List[str] = []

        for sensor in sensors:
            entity_id = sensor.get("entity_id")
            friendly_name = (
                sensor.get("name")
                or sensor.get("friendly_name")
                or entity_id
            )

            if not entity_id:
                errors.append("Capteur sans entity_id ignoré")
                continue

            base_id = entity_id.split(".", 1)[1]  # "sensor.xxx" -> "xxx"

            for cycle in cycles:
                meter_id = f"{base_id}_{cycle}"
                meter_entity_id = f"sensor.{meter_id}"
                meter_friendly = f"{friendly_name} {cycle.capitalize()}"

                # 1) Sauter si déjà présent (état ou registry)
                if self.hass.states.get(meter_entity_id) or self.entity_registry.async_get(
                    meter_entity_id
                ):
                    skipped_existing.append(meter_entity_id)
                    continue

                # 2) Tenter la création
                try:
                    _LOGGER.info(
                        "Création utility_meter '%s' (source=%s, cycle=%s)",
                        meter_id,
                        entity_id,
                        cycle,
                    )

                    await self.hass.services.async_call(
                        "utility_meter",
                        "create",
                        {
                            "source": entity_id,
                            "cycle": cycle,
                            "name": meter_friendly,
                            "meter": meter_id,
                        },
                        blocking=True,
                    )

                    created.append(meter_entity_id)

                except Exception as exc:  # pylint: disable=broad-except
                    msg = f"Erreur création {meter_entity_id}: {exc}"
                    _LOGGER.error(msg)
                    errors.append(msg)

        # Rollback best-effort si erreurs et créations partielles
        if errors and created:
            await self.rollback_helpers(created)

        success = not errors
        return {
            "success": success,
            "created": created,
            "skipped_existing": skipped_existing,
            "errors": errors,
        }


    async def rollback_helpers(self, entity_ids: List[str]) -> None:
        """Supprime les helpers créés (best-effort)."""
        for entity_id in entity_ids:
            try:
                if self.entity_registry.async_get(entity_id):
                    _LOGGER.info(
                        "Rollback: suppression de %s dans entity_registry", entity_id
                    )
                    self.entity_registry.async_remove(entity_id)

                if self.hass.states.get(entity_id) is not None:
                    _LOGGER.info("Rollback: suppression de l'état %s", entity_id)
                    self.hass.states.async_remove(entity_id)
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error("Erreur rollback %s: %s", entity_id, exc)

    async def validate_helpers(self, entity_ids: List[str]) -> Dict[str, bool]:
        """Vérifie que les helpers existent côté HA."""
        result: Dict[str, bool] = {}
        for entity_id in entity_ids or []:
            result[entity_id] = self.hass.states.get(entity_id) is not None
        return result

    def _get_pricing_from_options(self) -> Dict[str, Any]:
        """
        Normalise les options utilisateur en un dict homogène.
        Supporte prix unique et HP/HC (si les prix séparés existent).
        """
        opts = (self.hass.data.get(DOMAIN) or {}).get("options") or {}

        def _first(*keys: str) -> Any:
            """Retourne la première valeur non-None trouvée parmi plusieurs clés."""
            for k in keys:
                if k in opts and opts.get(k) is not None:
                    return opts.get(k)
            return None

        # ---- Normalisation contrat ----
        raw_type = _first("type_contrat", "typecontrat", "type_contrat") or "prixunique"
        raw = str(raw_type).strip().lower()

        # Normalise en supprimant séparateurs usuels
        norm = raw.replace(" ", "").replace("_", "").replace("-", "").replace("/", "")

        # Canonicalisation (ton runtime peut donner "hp-hc")
        if norm in ("hphc", "hchp", "heurescreuses", "heurecreuse"):
            type_contrat = "heurescreuses"
        elif norm in ("prixunique", "prixfixe", "fixe", "unique"):
            type_contrat = "prixunique"
        else:
            # fallback: garder une version "compacte" mais stable
            type_contrat = norm or "prixunique"

        # ---- Lecture prix (support snake_case + anciennes variantes) ----
        base_ht = _to_float(_first("prix_ht", "prixHT", "prixht"))
        base_ttc = _to_float(_first("prix_ttc", "prixTTC", "prixttc"))

        # Si non fourni, HP/HC doivent retomber sur le prix de base
        ht_hp_raw = _first("prix_ht_hp", "prixHTHP", "prixhthp", "prix_htHP", "prixHT_hp")
        ht_hc_raw = _first("prix_ht_hc", "prixHTHC", "prixhthc", "prix_htHC", "prixHC_ht")

        ttc_hp_raw = _first("prix_ttc_hp", "prixTTCHP", "prixttchp", "prix_ttcHP", "prixTTC_hp")
        ttc_hc_raw = _first("prix_ttc_hc", "prixTTCHC", "prixttchc", "prix_ttcHC", "prixHC_ttc")

        pricing = {
            "type_contrat": type_contrat,
            "prix_ht": base_ht,
            "prix_ttc": base_ttc,
            "prix_ht_hp": _to_float(ht_hp_raw, default=base_ht),
            "prix_ht_hc": _to_float(ht_hc_raw, default=base_ht),
            "prix_ttc_hp": _to_float(ttc_hp_raw, default=base_ttc),
            "prix_ttc_hc": _to_float(ttc_hc_raw, default=base_ttc),
        }
        return pricing


    def _pick_price_for_entity(self, pricing: Dict[str, Any], entity_id: str) -> Tuple[float, float]:
        """
        Retourne (prix_ht, prix_ttc) applicable à CETTE entité.

        Règle:
        - Si contrat heures creuses ET entity_id contient un token '_hp' => prix HP
        - Si contrat heures creuses ET entity_id contient un token '_hc' => prix HC
        - Sinon => prix de base
        """
        t = str(pricing.get("type_contrat") or "prixunique").lower()

        # Contrat HP/HC
        if t in ("heurescreuses", "hphc"):
            # entity_id est de la forme domain.object_id, on ne garde que l'object_id
            obj = entity_id.split(".", 1)[1].lower() if "." in entity_id else entity_id.lower()

            # Détection stricte de token: "_hp" ou "_hc" comme segment (délimité par _ ou bords)
            def _has_token(token: str) -> bool:
                parts = obj.split("_")
                return token in parts

            if _has_token("hp"):
                return (
                    pricing.get("prix_ht_hp", pricing["prix_ht"]),
                    pricing.get("prix_ttc_hp", pricing["prix_ttc"]),
                )

            if _has_token("hc"):
                return (
                    pricing.get("prix_ht_hc", pricing["prix_ht"]),
                    pricing.get("prix_ttc_hc", pricing["prix_ttc"]),
                )

        return pricing["prix_ht"], pricing["prix_ttc"]


    async def generate_cost_sensors_yaml(self) -> str:
        """
        Génère des template sensors de coût (€) à partir des capteurs energy sélectionnés.
        - 2 capteurs par entité: HT et TTC
        - Prix injectés depuis options utilisateur au moment de la génération.
        """
        sensors = await self._get_enabled_sensors()
        pricing = self._get_pricing_from_options()

        templates: List[Dict[str, Any]] = []

        for sensor in sensors:
            eid = sensor["entity_id"]
            friendly = sensor["friendly_name"]
            short = eid.split(".", 1)[1]

            prix_ht, prix_ttc = self._pick_price_for_entity(pricing, eid)

            # Coût HT
            templates.append(
                {
                    "name": f"{friendly} Coût HT",
                    "unique_id": f"{short}_cost_ht",
                    "state": (
                        f"{{{{ (states('{eid}') | float(0) * {prix_ht}) | round(2) }}}}"
                    ),
                    "unit_of_measurement": "€",
                    "device_class": "monetary",
                    "state_class": "total",
                    "availability": f"{{{{ states('{eid}') not in ['unknown','unavailable','none'] }}}}",
                }
            )

            # Coût TTC
            templates.append(
                {
                    "name": f"{friendly} Coût TTC",
                    "unique_id": f"{short}_cost_ttc",
                    "state": (
                        f"{{{{ (states('{eid}') | float(0) * {prix_ttc}) | round(2) }}}}"
                    ),
                    "unit_of_measurement": "€",
                    "device_class": "monetary",
                    "state_class": "total",
                    "availability": f"{{{{ states('{eid}') not in ['unknown','unavailable','none'] }}}}",
                }
            )

        yaml_content = {"template": templates}
        yaml_str = yaml.dump(
            yaml_content,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        return yaml_str
