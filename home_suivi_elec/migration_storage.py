# -*- coding: utf-8 -*-
"""
Script de migration Storage API - Exécution autonome et intégration __init__.py.

Permet de migrer manuellement ou automatiquement les fichiers data/ vers Storage API.
"""

import logging
import asyncio
from pathlib import Path

from homeassistant.core import HomeAssistant

from .storage_manager import StorageManager, LEGACY_DATA_DIR

_LOGGER = logging.getLogger(__name__)


async def async_migrate_storage(hass: HomeAssistant) -> bool:
    """
    Point d'entrée principal de la migration Storage API.
    
    Appelé automatiquement au démarrage de l'intégration si fichiers legacy détectés.
    
    Args:
        hass: Instance Home Assistant
        
    Returns:
        True si migration réussie, False sinon
    """
    _LOGGER.info("=" * 60)
    _LOGGER.info("🚀 MIGRATION STORAGE API - DÉBUT")
    _LOGGER.info("=" * 60)
    
    try:
        # Initialiser StorageManager
        storage_manager = StorageManager(hass)
        
        # Exécuter migration
        success = await storage_manager.migrate_from_legacy_files()
        
        if success:
            _LOGGER.info("=" * 60)
            _LOGGER.info("✅ MIGRATION STORAGE API - SUCCÈS")
            _LOGGER.info("=" * 60)
            
            # Afficher statistiques post-migration
            stats = await storage_manager.get_storage_stats()
            _LOGGER.info("📊 Statistiques post-migration:")
            _LOGGER.info("   - Zones: %d", stats["capteurs_selection"]["zones"])
            _LOGGER.info("   - Capteurs totaux: %d", stats["capteurs_selection"]["total_sensors"])
            _LOGGER.info("   - Capteurs activés: %d", stats["capteurs_selection"]["enabled_sensors"])
            _LOGGER.info("   - Entités ignorées: %d", stats["ignored_entities"]["count"])
            
            # Stocker dans hass.data pour usage ultérieur
            if "home_suivi_elec" not in hass.data:
                hass.data["home_suivi_elec"] = {}
            hass.data["home_suivi_elec"]["storage_manager"] = storage_manager
            
        else:
            _LOGGER.error("=" * 60)
            _LOGGER.error("❌ MIGRATION STORAGE API - ÉCHEC")
            _LOGGER.error("=" * 60)
        
        return success
        
    except Exception as e:
        _LOGGER.exception("💥 Erreur critique migration Storage API: %s", e)
        return False


async def async_export_storage_backup(hass: HomeAssistant, output_dir: str = None) -> bool:
    """
    Service Home Assistant pour exporter un backup manuel du Storage API.
    
    Args:
        hass: Instance Home Assistant
        output_dir: Répertoire de sortie (défaut: config/home_suivi_elec_backup)
        
    Returns:
        True si export réussi, False sinon
    """
    try:
        # Récupérer StorageManager
        storage_manager = hass.data.get("home_suivi_elec", {}).get("storage_manager")
        
        if not storage_manager:
            _LOGGER.error("[BACKUP] StorageManager non initialisé")
            return False
        
        # Déterminer répertoire de sortie
        if output_dir is None:
            output_dir = Path(hass.config.path("home_suivi_elec_backup"))
        else:
            output_dir = Path(output_dir)
        
        # Export
        success = await storage_manager.export_to_json(output_dir)
        
        if success:
            _LOGGER.info("[BACKUP] ✅ Backup créé dans %s", output_dir)
        else:
            _LOGGER.error("[BACKUP] ❌ Échec création backup")
        
        return success
        
    except Exception as e:
        _LOGGER.exception("[BACKUP] Erreur export backup: %s", e)
        return False


async def async_rollback_to_legacy(hass: HomeAssistant) -> bool:
    """
    Service d'urgence pour revenir aux fichiers legacy.
    
    Restaure les fichiers .migrated en .json si problème avec Storage API.
    
    Args:
        hass: Instance Home Assistant
        
    Returns:
        True si rollback réussi, False sinon
    """
    _LOGGER.warning("🔄 ROLLBACK vers fichiers legacy demandé...")
    
    try:
        rollback_done = False
        
        # Restaurer user_config.json
        legacy_backup = LEGACY_DATA_DIR / "user_config.json.migrated"
        legacy_target = LEGACY_DATA_DIR / "user_config.json"
        
        if legacy_backup.exists():
            legacy_backup.rename(legacy_target)
            _LOGGER.info("[ROLLBACK] ✅ user_config.json restauré")
            rollback_done = True
        
        # Restaurer capteurs_selection.json
        legacy_backup = LEGACY_DATA_DIR / "capteurs_selection.json.migrated"
        legacy_target = LEGACY_DATA_DIR / "capteurs_selection.json"
        
        if legacy_backup.exists():
            legacy_backup.rename(legacy_target)
            _LOGGER.info("[ROLLBACK] ✅ capteurs_selection.json restauré")
            rollback_done = True
        
        if rollback_done:
            _LOGGER.warning("=" * 60)
            _LOGGER.warning("✅ ROLLBACK TERMINÉ - Redémarrez Home Assistant")
            _LOGGER.warning("=" * 60)
            return True
        else:
            _LOGGER.info("[ROLLBACK] Aucun fichier .migrated à restaurer")
            return False
        
    except Exception as e:
        _LOGGER.exception("[ROLLBACK] ❌ Erreur rollback: %s", e)
        return False
