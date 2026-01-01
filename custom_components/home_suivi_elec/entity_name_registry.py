"""
Registry universel des noms d'entités : mapping short_name ↔ display_name
Évite les répétitions de logique de nommage entre modules.
✅ FIX: Async I/O pour éviter le blocking
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

_LOGGER = logging.getLogger(__name__)


class EntityNameRegistry:
    """
    Registry persistent pour mapper :
    - short_name (pour entity_id courts) ↔ display_name (pour friendly_name lisibles)
    
    Évite duplication calculs de noms entre energy_tracking, power_monitoring, etc.
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.registry_file = data_dir / "entity_name_registry.json"
        self._mappings: Dict[str, str] = {}
        self._hass = None
    
    def _load_sync(self) -> Dict[str, str]:
        """Charge le registry depuis le disque (synchrone)."""
        try:
            if self.registry_file.exists():
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    mappings = json.load(f)
                _LOGGER.debug(f"📖 Registry chargé : {len(mappings)} mappings")
                return mappings
            else:
                _LOGGER.debug("📖 Registry nouveau (fichier inexistant)")
                return {}
        except Exception as e:
            _LOGGER.warning(f"⚠️ Erreur chargement registry : {e}")
            return {}
    
    def _save_sync(self, mappings: Dict[str, str]) -> None:
        """Sauvegarde le registry sur disque (synchrone)."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(mappings, f, ensure_ascii=False, indent=2)
            _LOGGER.debug(f"💾 Registry sauvé : {len(mappings)} mappings")
        except Exception as e:
            _LOGGER.error(f"❌ Erreur sauvegarde registry : {e}")
    
    async def async_load(self, hass) -> None:
        """Charge le registry de manière asynchrone."""
        self._hass = hass
        self._mappings = await hass.async_add_executor_job(self._load_sync)
    
    async def async_save(self) -> None:
        """Sauvegarde le registry de manière asynchrone."""
        if self._hass is None:
            _LOGGER.error("❌ async_load doit être appelé avant async_save")
            return
        await self._hass.async_add_executor_job(self._save_sync, self._mappings.copy())
    
    def register_sync(self, entity_id: str, short_name: str) -> str:
        """
        Version synchrone de register (sans sauvegarde automatique).
        Utilisez async_save() manuellement après plusieurs appels.
        """
        display_name = self._generate_display_name(entity_id)
        self._mappings[short_name] = display_name
        return display_name
    
    def get_display_name(self, short_name: str) -> Optional[str]:
        """Récupère le display_name depuis short_name."""
        return self._mappings.get(short_name)
    
    def get_all_mappings(self) -> Dict[str, str]:
        """Retourne tous les mappings."""
        return self._mappings.copy()
    
    def _generate_display_name(self, entity_id: str) -> str:
        """Génère un nom d'affichage lisible depuis entity_id."""
        name = entity_id.replace("sensor.", "")
        name = name.replace("_today_energy", "")
        
        expansions = {
            "pwr": "puissance",
            "cur": "consommation actuelle", 
            "plug": "prise connectée",
            "smart": "prise intelligente",
        }
        
        for abbrev, full in expansions.items():
            name = name.replace(f"_{abbrev}", f"_{full}")
        
        words = name.split("_")
        title_words = []
        
        for word in words:
            if word:
                if word.lower() == "connectee":
                    title_words.append("Connectée")
                elif word.lower() == "intelligente":
                    title_words.append("Intelligente")
                else:
                    title_words.append(word.capitalize())
        
        return " ".join(title_words)
