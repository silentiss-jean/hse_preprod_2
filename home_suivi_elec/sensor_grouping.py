"""
Service de regroupement de capteurs par zone / pièce.

Objectifs :
- Regrouper automatiquement les capteurs energy/power par "pièce" via des mots-clés.
- Permettre de fusionner ces groupes avec une configuration manuelle existante.
- Fournir une structure JSON consommable par le frontend et la génération de cartes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Iterable, Any

# -----------------------------
# Modèles de données
# -----------------------------


@dataclass
class SensorInfo:
    entity_id: str
    device_class: str | None = None
    integration: str | None = None
    area: str | None = None
    friendly_name: str | None = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GroupConfig:
    """Configuration d'un groupe (pièce)."""
    name: str
    mode: str = "auto"  # "auto" / "manual" / "mixed"
    energy: List[str] = field(default_factory=list)
    power: List[str] = field(default_factory=list)


GroupsDict = Dict[str, GroupConfig]


# -----------------------------
# Heuristiques de regroupement
# -----------------------------


def _build_keyword_mapping(
    manual_mapping: Dict[str, str] | None = None,
    ) -> Dict[str, str]:
    """
    Construit une table {mot_clé -> nom_de_groupe}.

    manual_mapping vient d'un fichier de config utilisateur
    ou d'options (ex: {"salon": "Salon", "cuisine": "Cuisine"}).
    """
    base: Dict[str, str] = {}

    # Valeurs par défaut raisonnables (peuvent être enrichies plus tard)
    defaults = {
        "salon": "Salon",
        "sejour": "Salon",
        "living": "Salon",
        "bureau": "Bureau",
        "cuisine": "Cuisine",
        "kitchen": "Cuisine",
        "chambre": "Chambres",
        "bedroom": "Chambres",
        "garage": "Garage",
        "buanderie": "Buanderie",
        "cellier": "Buanderie",
    }

    base.update(defaults)

    if manual_mapping:
        # L'utilisateur peut surcharger / compléter les mots-clés
        for keyword, group_name in manual_mapping.items():
            base[str(keyword).lower()] = str(group_name)

    return base


def _detect_group_name(sensor: SensorInfo, keyword_mapping: Dict[str, str]) -> str:
    """
    Détermine le nom de groupe pour un capteur donné.

    Ordre de priorité :
    1) zone / area explicite si présente
    2) mot-clé trouvé dans entity_id ou friendly_name
    3) groupe "Autres"
    """
    # 1. Zone explicite
    if sensor.area:
        return sensor.area

    source = f"{sensor.entity_id} {sensor.friendly_name or ''}".lower()

    # 2. Mots-clés
    for keyword, group_name in keyword_mapping.items():
        if keyword in source:
            return group_name

    # 3. Fallback
    return "Autres"


def build_auto_groups(
    sensors: Iterable[Dict[str, Any]],
    manual_keyword_mapping: Dict[str, str] | None = None,
    ) -> GroupsDict:
    """
    Construit des groupes automatiquement à partir d'une liste de capteurs HSE.
    """
    keyword_mapping = _build_keyword_mapping(manual_keyword_mapping)
    groups: GroupsDict = {}

    for raw in sensors:
        entity_id = raw.get("entity_id")
        if not entity_id:
            continue

        info = SensorInfo(
            entity_id=entity_id,
            device_class=raw.get("device_class"),
            integration=raw.get("integration"),
            area=raw.get("area"),
            friendly_name=raw.get("friendly_name"),
            extra=raw,
        )

        group_name = _detect_group_name(info, keyword_mapping)
        group = groups.setdefault(group_name, GroupConfig(name=group_name))

        # 1) Utiliser les flags backend quand ils existent
        is_power = raw.get("is_power")
        is_energy = raw.get("is_energy")

        # 2) Fallback legacy sur type / source_type
        if is_power is None and is_energy is None:
            sensor_type = (raw.get("type") or raw.get("source_type") or "").lower()
            if sensor_type == "power":
                is_power = True
            elif sensor_type in ("energy", "energy_direct", "energy_utility", "hse_energy"):
                is_energy = True

        if is_energy:
            if entity_id not in group.energy:
                group.energy.append(entity_id)
        if is_power:
            if entity_id not in group.power:
                group.power.append(entity_id)

    return groups


# -----------------------------
# Fusion avec la config manuelle
# -----------------------------


def merge_with_existing(
    auto_groups: GroupsDict,
    existing_config: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
    """
    Fusionne les groupes auto avec une config existante (groups.json).

    Règles simples :
    - Si un groupe est marqué "manual", on NE modifie pas ses listes.
    - Si "mixed", on ajoute les nouveaux capteurs auto sans retirer les anciens.
    - Si absent ou "auto", on remplace par le calcul auto.
    """
    if existing_config is None:
        existing_config = {}

    result: Dict[str, Any] = {}

    # Normaliser l'existant
    for name, payload in existing_config.items():
        mode = payload.get("mode", "manual")
        result[name] = {
            "name": name,
            "mode": mode,
            "energy": list(payload.get("energy", [])),
            "power": list(payload.get("power", [])),
        }

    # Appliquer les groupes auto
    for name, group in auto_groups.items():
        if name not in result:
            # Nouveau groupe purement auto
            result[name] = {
                "name": name,
                "mode": "auto",
                "energy": list(group.energy),
                "power": list(group.power),
            }
            continue

        cfg = result[name]
        mode = cfg.get("mode", "manual")

        if mode == "manual":
            # Ne rien toucher, l'utilisateur gère entièrement ce groupe
            continue
        elif mode == "mixed":
            # Ajouter ce que l'on n'a pas encore
            existing_energy = set(cfg.get("energy", []))
            existing_power = set(cfg.get("power", []))
            for eid in group.energy:
                if eid not in existing_energy:
                    cfg.setdefault("energy", []).append(eid)
            for eid in group.power:
                if eid not in existing_power:
                    cfg.setdefault("power", []).append(eid)
        else:
            # mode "auto" ou inconnu -> écrasement par l'auto
            cfg["energy"] = list(group.energy)
            cfg["power"] = list(group.power)
            cfg["mode"] = "auto"

    return result
