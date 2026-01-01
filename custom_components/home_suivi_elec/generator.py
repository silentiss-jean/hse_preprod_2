# -*- coding: utf-8 -*-
"""
Génération de cartes Lovelace pour Home Suivi Élec.

Génère automatiquement :
- Vue d'ensemble (Top 10)
- Graphiques historiques
- Distribution énergie
- Cartes par pièce
"""

import logging
import aiofiles
from pathlib import Path
from typing import Dict, List, Any
import yaml

_LOGGER = logging.getLogger(__name__)

# ===========================================================================
# GÉNÉRATEURS DE CARTES LOVELACE
# ===========================================================================

def generate_overview_card(sensors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Génère une carte vue d'ensemble (Top 10 consommateurs).
    
    Args:
        sensors: Liste des sensors avec leurs valeurs
        
    Returns:
        Configuration de carte Lovelace
    """
    # Trier par consommation journalière (cycle daily)
    daily_sensors = [s for s in sensors if s.get("cycle") == "daily"]
    daily_sensors.sort(key=lambda x: float(x.get("value", 0)), reverse=True)
    
    # Top 10
    top_10 = daily_sensors[:10]
    
    entities = []
    for sensor in top_10:
        entities.append({
            "entity": sensor["entity_id"],
            "name": sensor.get("friendly_name", sensor["entity_id"]),
            "secondary_info": "last-changed"
        })
    
    return {
        "type": "entities",
        "title": "📊 Top 10 consommateurs aujourd'hui",
        "entities": entities,
        "show_header_toggle": False
    }


def generate_history_card(sensors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Génère une carte graphique historique (7 derniers jours).
    
    Args:
        sensors: Liste des sensors
        
    Returns:
        Configuration de carte Lovelace
    """
    # Prendre les sensors daily pour l'historique
    daily_sensors = [s for s in sensors if s.get("cycle") == "daily"][:10]
    
    entities = [s["entity_id"] for s in daily_sensors]
    
    return {
        "type": "history-graph",
        "title": "📈 Consommation 7 derniers jours",
        "entities": entities,
        "hours_to_show": 168,  # 7 jours
        "refresh_interval": 300
    }


def generate_energy_distribution_card(sensors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Génère une carte distribution énergie (camembert).
    
    Args:
        sensors: Liste des sensors
        
    Returns:
        Configuration de carte Lovelace
    """
    # Prendre les sensors daily
    daily_sensors = [s for s in sensors if s.get("cycle") == "daily"][:10]
    
    entities = []
    for sensor in daily_sensors:
        entities.append({
            "entity": sensor["entity_id"]
        })
    
    return {
        "type": "energy-distribution",
        "title": "⚡ Répartition journalière",
        "entities": entities
    }


def generate_gauge_card(sensor: Dict[str, Any], max_value: float = 10.0) -> Dict[str, Any]:
    """
    Génère une carte jauge pour un sensor.
    
    Args:
        sensor: Sensor individuel
        max_value: Valeur max de la jauge (kWh)
        
    Returns:
        Configuration de carte Lovelace
    """
    return {
        "type": "gauge",
        "entity": sensor["entity_id"],
        "name": sensor.get("friendly_name", sensor["entity_id"]),
        "unit": "kWh",
        "min": 0,
        "max": max_value,
        "severity": {
            "green": 0,
            "yellow": max_value * 0.6,
            "red": max_value * 0.9
        }
    }


def generate_statistic_cards(sensors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Génère des cartes statistiques pour chaque cycle.
    
    Args:
        sensors: Liste des sensors
        
    Returns:
        Liste de cartes statistiques
    """
    cards = []
    
    # Grouper par cycle
    cycles = {"hourly": "Heure", "daily": "Jour", "weekly": "Semaine", "monthly": "Mois", "yearly": "Année"}
    
    for cycle_key, cycle_label in cycles.items():
        cycle_sensors = [s for s in sensors if s.get("cycle") == cycle_key][:5]
        
        if not cycle_sensors:
            continue
        
        entities = []
        for sensor in cycle_sensors:
            entities.append({
                "entity": sensor["entity_id"]
            })
        
        cards.append({
            "type": "entities",
            "title": f"📊 Consommation {cycle_label}",
            "entities": entities
        })
    
    return cards


def generate_complete_dashboard(sensors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Génère un dashboard complet avec toutes les cartes.
    
    Args:
        sensors: Liste de tous les sensors HSE
        
    Returns:
        Configuration complète du dashboard
    """
    views = []
    
    # Vue 1 : Vue d'ensemble
    overview_cards = [
        generate_overview_card(sensors),
        generate_history_card(sensors),
        generate_energy_distribution_card(sensors)
    ]
    
    views.append({
        "title": "Vue d'ensemble",
        "path": "overview",
        "icon": "mdi:home-analytics",
        "cards": overview_cards
    })
    
    # Vue 2 : Détails par cycle
    detail_cards = generate_statistic_cards(sensors)
    
    views.append({
        "title": "Détails",
        "path": "details",
        "icon": "mdi:chart-line",
        "cards": detail_cards
    })
    
    # Vue 3 : Jauges individuelles
    gauge_cards = []
    daily_sensors = [s for s in sensors if s.get("cycle") == "daily"][:20]
    
    for sensor in daily_sensors:
        gauge_cards.append(generate_gauge_card(sensor, max_value=10.0))
    
    views.append({
        "title": "Jauges",
        "path": "gauges",
        "icon": "mdi:gauge",
        "type": "grid",
        "cards": gauge_cards
    })
    
    return {
        "title": "⚡ Home Suivi Élec",
        "views": views
    }


# ===========================================================================
# FONCTIONS UTILITAIRES
# ===========================================================================

async def get_all_hse_sensors(hass) -> List[Dict[str, Any]]:
    """
    Récupère tous les sensors HSE avec leurs valeurs actuelles.
    
    Args:
        hass: Instance Home Assistant
        
    Returns:
        Liste des sensors avec métadonnées
    """
    sensors = []
    
    # ✅ CORRECTION : async_all() retourne une liste de State objects
    for state in hass.states.async_all():
        entity_id = state.entity_id
        
        # Filtrer les sensors HSE
        if entity_id.startswith("sensor.hse_"):
            try:
                value = float(state.state) if state.state not in ("unknown", "unavailable") else 0.0
                
                sensors.append({
                    "entity_id": entity_id,
                    "friendly_name": state.attributes.get("friendly_name", entity_id),
                    "value": value,
                    "unit": state.attributes.get("unit_of_measurement", "kWh"),
                    "cycle": state.attributes.get("cycle", "unknown"),
                    "source_entity": state.attributes.get("source_entity", ""),
                    "last_reset": state.attributes.get("last_reset")
                })
            except (ValueError, TypeError):
                continue
    
    return sensors


async def generate_yaml_config(capteurs):
    """Génération YAML basique (legacy)."""
    lignes = ["# Home Suivi Élec — YAML auto-généré", ""]
    for c in capteurs:
        lignes.append(f"# Capteur : {c.get('entity_id', 'unknown')}")
    return "\n".join(lignes)


async def write_yaml_file(filename, content):
    """Écrit un fichier YAML de façon asynchrone."""
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)
    _LOGGER.info("📄 Fichier YAML généré : %s", path)


# ===========================================================================
# POINT D'ENTRÉE PRINCIPAL
# ===========================================================================

async def run_all(hass, options):
    """
    Point d'entrée pour la génération complète.
    
    Génère :
    - Dashboard Lovelace complet
    - YAML de configuration
    
    Args:
        hass: Instance Home Assistant
        options: Options de configuration
    """
    _LOGGER.info("🧩 Lancement de la génération Lovelace Home Suivi Élec")
    
    # Récupérer tous les sensors HSE
    sensors = await get_all_hse_sensors(hass)
    _LOGGER.info(f"📊 {len(sensors)} sensors HSE détectés")
    
    if not sensors:
        _LOGGER.warning("⚠️ Aucun sensor HSE trouvé !")
        return
    
    # Générer le dashboard complet
    dashboard = generate_complete_dashboard(sensors)
    
    # Convertir en YAML
    yaml_content = yaml.dump(dashboard, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    # Ajouter un header
    header = """# ⚡ Home Suivi Élec - Dashboard Auto-généré
# Généré automatiquement par l'intégration Home Suivi Élec
# Pour utiliser : Copier/coller dans Configuration > Dashboards > Raw Editor
#
# OU ajouter dans ui-lovelace.yaml si en mode YAML
#

"""
    
    final_yaml = header + yaml_content
    
    # Sauvegarder le fichier
    output_path = "/config/home_suivi_elec_dashboard.yaml"
    await write_yaml_file(output_path, final_yaml)
    
    _LOGGER.info(f"✅ Dashboard généré : {output_path}")
    _LOGGER.info(f"📋 {len(sensors)} sensors inclus dans {len(dashboard.get('views', []))} vues")

