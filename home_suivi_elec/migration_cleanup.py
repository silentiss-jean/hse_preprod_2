# -*- coding: utf-8 -*-
"""
Script de migration pour nettoyer les sensors d'intégration aberrants.
Compatible Home Assistant 2024.x et 2025.x
Exécution asynchrone pour éviter le blocage de l'event loop.
"""

import logging
import asyncio
from homeassistant.core import HomeAssistant
from homeassistant.components.recorder import get_instance

_LOGGER = logging.getLogger(__name__)

async def migrate_cleanup_integration_sensors(hass: HomeAssistant, threshold_kwh: float = 1000.0):
    """
    Supprime les statistics des sensors d'intégration hse_energy_*
    qui ont des valeurs > threshold_kwh cumulés.
    
    Args:
        hass: Instance Home Assistant
        threshold_kwh: Seuil (défaut 1000 kWh)
    
    Returns:
        Nombre de sensors nettoyés
    """
    recorder = get_instance(hass)
    if not recorder:
        _LOGGER.error("[Migration] Recorder non disponible")
        return 0
    
    # Exécuter dans un thread séparé pour éviter le blocage
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _cleanup_sync, hass, threshold_kwh)


def _cleanup_sync(hass: HomeAssistant, threshold_kwh: float) -> int:
    """
    Fonction synchrone de nettoyage (exécutée dans un executor).
    """
    try:
        # Importer les modèles recorder de manière compatible
        try:
            # Home Assistant 2024.11+
            from homeassistant.components.recorder.models.statistics import (
                StatisticsMeta,
                Statistics,
            )
        except ImportError:
            try:
                # Home Assistant 2024.1-2024.10
                from homeassistant.components.recorder.models import (
                    StatisticsMeta,
                    Statistics,
                )
            except ImportError:
                # Fallback pour versions anciennes
                from homeassistant.components.recorder.statistics import (
                    StatisticsMeta,
                    Statistics,
                )
        
        from homeassistant.components.recorder.util import session_scope
        
        with session_scope(hass=hass, read_only=False) as session:
            # Trouver tous les sensors hse_energy_*
            metas = session.query(StatisticsMeta).filter(
                StatisticsMeta.statistic_id.like("sensor.hse_energy_%")
            ).all()
            
            if not metas:
                _LOGGER.info("[Migration] Aucun sensor hse_energy_* trouvé dans les statistics")
                return 0
            
            _LOGGER.info("[Migration] %d sensors hse_energy_* trouvés, analyse en cours...", len(metas))
            
            cleaned_count = 0
            for meta in metas:
                # Récupérer la dernière valeur
                last_stat = session.query(Statistics).filter(
                    Statistics.metadata_id == meta.id
                ).order_by(Statistics.start.desc()).first()
                
                if not last_stat:
                    _LOGGER.debug("[Migration] Pas de statistics pour %s", meta.statistic_id)
                    continue
                
                current_value = last_stat.sum if last_stat.sum is not None else 0
                
                if current_value > threshold_kwh:
                    _LOGGER.warning(
                        "[Migration] Nettoyage de %s (valeur aberrante: %.2f kWh > %.2f kWh)",
                        meta.statistic_id, current_value, threshold_kwh
                    )
                    # Supprimer toutes les statistics
                    deleted = session.query(Statistics).filter(
                        Statistics.metadata_id == meta.id
                    ).delete()
                    cleaned_count += 1
                    _LOGGER.info("[Migration] %d enregistrements supprimés pour %s", deleted, meta.statistic_id)
                else:
                    _LOGGER.debug(
                        "[Migration] %s OK (%.2f kWh < %.2f kWh)",
                        meta.statistic_id, current_value, threshold_kwh
                    )
            
            session.commit()
            
            if cleaned_count > 0:
                _LOGGER.info("[Migration] ✅ Nettoyage terminé: %d sensors traités sur %d", cleaned_count, len(metas))
            else:
                _LOGGER.info("[Migration] ✅ Aucun sensor aberrant détecté (toutes les valeurs < %.2f kWh)", threshold_kwh)
            
            return cleaned_count
            
    except Exception as e:
        _LOGGER.error("[Migration] ❌ Erreur lors du nettoyage: %s", e, exc_info=True)
        return 0
