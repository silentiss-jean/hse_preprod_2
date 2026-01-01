"""
Module d'export des données d'énergie.
Backup JSON et export InfluxDB optionnel.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

_LOGGER = logging.getLogger(__name__)


async def setup_json_backup(hass: HomeAssistant, backup_enabled: bool = True) -> None:
    """
    Configure le backup JSON quotidien.
    
    Args:
        hass: Instance Home Assistant
        backup_enabled: Activer ou non le backup
    """
    if not backup_enabled:
        _LOGGER.info("ℹ️ Backup JSON désactivé")
        return
    
    _LOGGER.info("✅ Backup JSON quotidien activé (00h05)")
    
    async def daily_backup(now):
        """Execute daily backup."""
        try:
            backup_file = hass.config.path(".storage", "home_suivi_elec_energy_backup.json")
            
            data = {
                "timestamp": now.isoformat(),
                "version": "1.0",
                "sensors": {},
            }
            
            # Récupérer tous les sensors d'énergie
            for state in hass.states.async_all():
                if "_energy" in state.entity_id:
                    data["sensors"][state.entity_id] = {
                        "value": state.state,
                        "unit": state.attributes.get("unit_of_measurement"),
                        "attributes": dict(state.attributes),
                    }
            
            # Écrire le fichier
            with open(backup_file, "w") as f:
                json.dump(data, f, indent=2)
            
            _LOGGER.info(
                f"✅ Backup JSON sauvegardé: {len(data['sensors'])} sensors → {backup_file}"
            )
        
        except Exception as e:
            _LOGGER.error(f"❌ Erreur backup JSON: {e}")
    
    # Planifier le backup à 00h05 tous les jours
    async_track_time_change(hass, daily_backup, hour=0, minute=5, second=0)


async def setup_influxdb_export(hass: HomeAssistant) -> None:
    """
    Configure l'export vers InfluxDB si disponible.
    
    Args:
        hass: Instance Home Assistant
    """
    if "influxdb" not in hass.config.components:
        _LOGGER.debug("ℹ️ InfluxDB non installé, export désactivé")
        return
    
    _LOGGER.info("✅ InfluxDB détecté, export horaire activé")
    
    async def hourly_export(now):
        """Export vers InfluxDB toutes les heures."""
        try:
            # Note: InfluxDB dans HA écoute automatiquement les changements d'état
            # Si l'intégration InfluxDB est configurée, elle exporte déjà
            # Ce callback peut servir pour des exports custom si nécessaire
            _LOGGER.debug("ℹ️ Export InfluxDB (géré par intégration InfluxDB)")
        
        except Exception as e:
            _LOGGER.error(f"❌ Erreur export InfluxDB: {e}")
    
    # Optionnel: callback toutes les heures pour logs
    async_track_time_change(hass, hourly_export, minute=0, second=0)


async def export_to_csv(hass: HomeAssistant, sensor_ids: list[str], output_file: str) -> bool:
    """
    Exporte les données vers un fichier CSV.
    
    Args:
        hass: Instance Home Assistant
        sensor_ids: Liste des sensors à exporter
        output_file: Chemin du fichier CSV de sortie
    
    Returns:
        True si succès, False sinon
    """
    try:
        import csv
        
        with open(output_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["timestamp", "sensor_id", "value", "unit"])
            
            for sensor_id in sensor_ids:
                state = hass.states.get(sensor_id)
                if state:
                    writer.writerow([
                        datetime.now().isoformat(),
                        sensor_id,
                        state.state,
                        state.attributes.get("unit_of_measurement", ""),
                    ])
        
        _LOGGER.info(f"✅ Export CSV: {len(sensor_ids)} sensors → {output_file}")
        return True
    
    except Exception as e:
        _LOGGER.error(f"❌ Erreur export CSV: {e}")
        return False
