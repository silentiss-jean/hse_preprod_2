# -*- coding: utf-8 -*-
"""
Gestionnaire de synchronisation automatique des capteurs.

FONCTIONNALITÉS :
  - Détection automatique des changements (ajout, suppression, indisponibilité)
  - Mise à jour incrémentale de capteurs_power.json
  - Backup automatique avant modifications
  - Gestion des états : active, unavailable, pending_removal, removed
  - Événements Home Assistant : entity_registry_updated, state_changed
  - Scan périodique throttled (toutes les 5 minutes si changements)

ARCHITECTURE :
  - Un seul fichier JSON (capteurs_power.json) enrichi
  - Pas de fichiers séparés (historique intégré)
  - Coordinateur léger (pas de stockage propre)
"""

import os
import json
import logging
import asyncio
import shutil
from datetime import datetime, timedelta
from typing import Set, Tuple, Optional, Dict, Any, List

from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CAPTEURS_FILE = os.path.join(DATA_DIR, "capteurs_power.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

# Configuration
SYNC_INTERVAL = timedelta(minutes=5)  # Scan périodique
UNAVAILABLE_TIMEOUT = timedelta(days=7)  # Timeout avant suppression
THROTTLE_DELAY = 30  # Secondes avant de synchroniser après un changement


class SensorSyncManager:
    """
    Gestionnaire de synchronisation automatique des capteurs.
    """
    
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._listeners = []
        self._pending_changes: Set[Tuple[str, str]] = set()  # (action, entity_id)
        self._sync_task: Optional[asyncio.Task] = None
        self._last_sync: Optional[datetime] = None
        self._running = False
        _LOGGER.info("🔄 SensorSyncManager initialisé")
    
    async def start(self):
        """Démarre la synchronisation automatique."""
        if self._running:
            _LOGGER.warning("SensorSyncManager déjà démarré")
            return
        
        self._running = True
        _LOGGER.info("🔄 Démarrage SensorSyncManager...")
        
        # S'abonner aux événements Home Assistant
        self._listeners.append(
            self.hass.bus.async_listen("entity_registry_updated", self._on_entity_registry_changed)
        )
        self._listeners.append(
            self.hass.bus.async_listen("state_changed", self._on_state_changed)
        )
        
        # Scan périodique (toutes les 5 minutes)
        self._listeners.append(
            async_track_time_interval(self.hass, self._periodic_sync, SYNC_INTERVAL)
        )
        
        _LOGGER.info("✅ SensorSyncManager démarré (scan toutes les 5min)")
    
    async def stop(self):
        self._running = False
        for remove_listener in self._listeners:
            remove_listener()
        self._listeners.clear()
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
        _LOGGER.info("🛑 SensorSyncManager arrêté")
    
    @callback
    def _on_entity_registry_changed(self, event: Event):
        action = event.data.get("action")
        entity_id = event.data.get("entity_id")
        
        if not entity_id or not entity_id.startswith("sensor."):
            return
        
        if action == "create":
            _LOGGER.debug(f"📥 Nouveau sensor détecté: {entity_id}")
            self._pending_changes.add(("add", entity_id))
            asyncio.create_task(self._schedule_sync())
        
        elif action == "remove":
            _LOGGER.debug(f"🗑️  Sensor supprimé: {entity_id}")
            self._pending_changes.add(("remove", entity_id))
            asyncio.create_task(self._schedule_sync())
        
        elif action == "update":
            _LOGGER.debug(f"✏️  Sensor modifié: {entity_id}")
            self._pending_changes.add(("update", entity_id))
            asyncio.create_task(self._schedule_sync())
    
    @callback
    def _on_state_changed(self, event: Event):
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if not new_state or not new_state.entity_id.startswith("sensor."):
            return
        if new_state.state == "unavailable" and (not old_state or old_state.state != "unavailable"):
            entity_id = new_state.entity_id
            _LOGGER.debug(f"⚠️  Sensor unavailable: {entity_id}")
            self._pending_changes.add(("unavailable", entity_id))
            asyncio.create_task(self._schedule_sync())
        elif old_state and old_state.state == "unavailable" and new_state.state != "unavailable":
            entity_id = new_state.entity_id
            _LOGGER.debug(f"✅ Sensor disponible: {entity_id}")
            self._pending_changes.add(("available", entity_id))
            asyncio.create_task(self._schedule_sync())
    
    async def _schedule_sync(self, delay: int = THROTTLE_DELAY):
        if self._sync_task and not self._sync_task.done():
            return
        async def delayed_sync():
            await asyncio.sleep(delay)
            await self._process_pending_changes()
        self._sync_task = asyncio.create_task(delayed_sync())
    
    async def _periodic_sync(self, now):
        if not self._pending_changes:
            return
        _LOGGER.info(f"🔄 Sync périodique : {len(self._pending_changes)} changements en attente")
        await self._process_pending_changes()
    
    async def _process_pending_changes(self):
        if not self._pending_changes:
            return
        
        _LOGGER.info(f"🔄 Traitement de {len(self._pending_changes)} changements...")
        
        try:
            await self._backup_capteurs_file()
            capteurs = await self._load_capteurs()
            capteurs_dict = {c["entity_id"]: c for c in capteurs if c.get("entity_id")}
            
            # 🔧 FIX: Copier le set avant d'itérer pour éviter "Set changed size during iteration"
            pending_copy = list(self._pending_changes)
            
            for action, entity_id in pending_copy:
                if action == "add":
                    await self._add_sensor(entity_id, capteurs_dict)
                elif action == "remove":
                    await self._remove_sensor(entity_id, capteurs_dict)
                elif action == "update":
                    await self._update_sensor(entity_id, capteurs_dict)
                elif action == "unavailable":
                    await self._mark_unavailable(entity_id, capteurs_dict)
                elif action == "available":
                    await self._mark_available(entity_id, capteurs_dict)
            
            await self._cleanup_old_sensors(capteurs_dict)
            updated_capteurs = list(capteurs_dict.values())
            await self._save_capteurs(updated_capteurs)
            
            self._pending_changes.clear()
            self._last_sync = datetime.now()
            
            _LOGGER.info(f"✅ Synchronisation terminée ({len(updated_capteurs)} capteurs)")
        
        except Exception as e:
            _LOGGER.exception(f"❌ Erreur synchronisation: {e}")

    
    async def _add_sensor(self, entity_id: str, capteurs_dict: Dict[str, Any]):
        if entity_id in capteurs_dict:
            _LOGGER.debug(f"Sensor {entity_id} déjà présent")
            return
        from .detect_local import run_detect_local
        await run_detect_local(hass=self.hass)
        _LOGGER.info(f"📥 Sensor ajouté: {entity_id}")
    
    async def _remove_sensor(self, entity_id: str, capteurs_dict: Dict[str, Any]):
        if entity_id not in capteurs_dict:
            return
        capteurs_dict[entity_id]["sync_status"] = "pending_removal"
        capteurs_dict[entity_id]["removal_scheduled"] = (
            datetime.now() + UNAVAILABLE_TIMEOUT
        ).isoformat()
        _LOGGER.info(f"🗑️  Sensor marqué pour suppression: {entity_id}")
    
    async def _update_sensor(self, entity_id: str, capteurs_dict: Dict[str, Any]):
        if entity_id not in capteurs_dict:
            return
        capteurs_dict[entity_id]["last_seen"] = datetime.now().isoformat()
        _LOGGER.debug(f"✏️  Sensor mis à jour: {entity_id}")
    
    async def _mark_unavailable(self, entity_id: str, capteurs_dict: Dict[str, Any]):
        if entity_id not in capteurs_dict:
            return
        sensor = capteurs_dict[entity_id]
        if sensor.get("sync_status") != "unavailable":
            sensor["sync_status"] = "unavailable"
            sensor["unavailable_since"] = datetime.now().isoformat()
            _LOGGER.info(f"⚠️  Sensor unavailable: {entity_id}")
    
    async def _mark_available(self, entity_id: str, capteurs_dict: Dict[str, Any]):
        if entity_id not in capteurs_dict:
            return
        sensor = capteurs_dict[entity_id]
        if sensor.get("sync_status") == "unavailable":
            sensor["sync_status"] = "active"
            sensor["unavailable_since"] = None
            sensor["last_seen"] = datetime.now().isoformat()
            _LOGGER.info(f"✅ Sensor récupéré: {entity_id}")
    
    async def _cleanup_old_sensors(self, capteurs_dict: Dict[str, Any]):
        now = datetime.now()
        to_remove = []
        for entity_id, sensor in capteurs_dict.items():
            if sensor.get("sync_status") != "pending_removal":
                continue
            removal_date = sensor.get("removal_scheduled")
            if not removal_date:
                continue
            try:
                removal_datetime = datetime.fromisoformat(removal_date)
                if now >= removal_datetime:
                    to_remove.append(entity_id)
            except Exception:
                continue
        for entity_id in to_remove:
            del capteurs_dict[entity_id]
            _LOGGER.info(f"🗑️  Sensor supprimé définitivement: {entity_id}")
    
    async def _backup_capteurs_file(self):
        if not os.path.exists(CAPTEURS_FILE):
            return
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"capteurs_power_{timestamp}.json")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, shutil.copy2, CAPTEURS_FILE, backup_file)
        _LOGGER.debug(f"💾 Backup créé: {backup_file}")
        await self._cleanup_old_backups()
    
    async def _cleanup_old_backups(self):
        if not os.path.exists(BACKUP_DIR):
            return
        loop = asyncio.get_running_loop()
        def list_and_cleanup():
            backups = sorted(
                [f for f in os.listdir(BACKUP_DIR) if f.startswith("capteurs_power_")],
                reverse=True
            )
            for backup in backups[10:]:
                backup_path = os.path.join(BACKUP_DIR, backup)
                try:
                    os.remove(backup_path)
                    _LOGGER.debug(f"🗑️  Ancien backup supprimé: {backup}")
                except Exception as e:
                    _LOGGER.warning(f"Erreur suppression backup {backup}: {e}")
        await loop.run_in_executor(None, list_and_cleanup)
    
    async def _load_capteurs(self) -> List[Dict[str, Any]]:
        if not os.path.exists(CAPTEURS_FILE):
            return []
        loop = asyncio.get_running_loop()
        def load():
            with open(CAPTEURS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return await loop.run_in_executor(None, load)
    
    async def _save_capteurs(self, capteurs: List[Dict[str, Any]]):
        os.makedirs(DATA_DIR, exist_ok=True)
        loop = asyncio.get_running_loop()
        def save():
            with open(CAPTEURS_FILE, "w", encoding="utf-8") as f:
                json.dump(capteurs, f, ensure_ascii=False, indent=2)
        await loop.run_in_executor(None, save)
    
    async def force_sync(self):
        _LOGGER.info("🔄 Synchronisation forcée demandée")
        from .detect_local import run_detect_local
        await run_detect_local(hass=self.hass)
        self._last_sync = datetime.now()
        _LOGGER.info("✅ Synchronisation forcée terminée")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "pending_changes": len(self._pending_changes),
            "backup_count": self._get_backup_count(),
        }
    
    def _get_backup_count(self) -> int:
        if not os.path.exists(BACKUP_DIR):
            return 0
        try:
            return len([f for f in os.listdir(BACKUP_DIR) if f.startswith("capteurs_power_")])
        except Exception:
            return 0

__all__ = ["SensorSyncManager"]
