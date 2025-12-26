"""
Correcteur automatique des noms de sensors HSE trop longs.
Écoute la création des sensors et corrige silencieusement si nécessaire.
✅ FIX: Thread-safe callback
"""
import logging
import re
from typing import Optional

from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers import entity_registry as er
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

_LOGGER = logging.getLogger(__name__)

MAX_ENTITY_ID_LENGTH = 50


def _shorten_entity_name(entity_name: str, max_length: int = 999) -> str:
    """NO-TRANSFORM ABSOLU - Retour tel quel sauf _today_energy."""
    name = entity_name.replace("_today_energy", "")
    return name


def _compute_short_entity_id(long_entity_id: str) -> Optional[str]:
    if not long_entity_id.startswith("sensor.hse_"):
        return None
    
    match_today = re.match(r'sensor\.hse_(.+)_today_energy_([hdwmy])$', long_entity_id)
    match_live = re.match(r'sensor\.hse_live_(.+)_([hdwmy])$', long_entity_id)
    match_energy = re.match(r'sensor\.hse_(.+)_([hdwmy])$', long_entity_id)
    
    if match_today:
        base_long = match_today.group(1)
        cycle = match_today.group(2)
        prefix = "sensor.hse_"
    elif match_live:
        base_long = match_live.group(1)
        cycle = match_live.group(2)
        prefix = "sensor.hse_live_"
    elif match_energy:
        base_long = match_energy.group(1)
        cycle = match_energy.group(2)
        prefix = "sensor.hse_"
    else:
        return None
    
    base_short = _shorten_entity_name(base_long)
    return f"{prefix}{base_short}_{cycle}"


async def _fix_long_sensor_name(hass: HomeAssistant, entity_id: str) -> bool:
    """Corrige un nom de sensor trop long."""
    if len(entity_id) <= MAX_ENTITY_ID_LENGTH:
        return False
    
    new_entity_id = _compute_short_entity_id(entity_id)
    if not new_entity_id:
        _LOGGER.debug(f"[HSE-FIXER] Pattern non supporté, ignore: {entity_id}")
        return False
    
    registry = er.async_get(hass)
    
    if registry.async_get(new_entity_id):
        _LOGGER.debug(f"✅ [HSE] Nom court existe déjà : {new_entity_id}")
        registry.async_remove(entity_id)
        return True
    
    try:
        entity_entry = registry.async_get(entity_id)
        if entity_entry:
            registry.async_update_entity(entity_id, new_entity_id=new_entity_id)
            _LOGGER.info(f"✂️ [HSE] Nom raccourci : {entity_id} ({len(entity_id)}) → {new_entity_id} ({len(new_entity_id)})")
            return True
    except Exception as e:
        _LOGGER.error(f"❌ [HSE] Erreur renommage {entity_id}: {e}")
    
    return False


async def _on_entity_registry_updated(hass: HomeAssistant, event: Event) -> None:
    """Callback async pour les mises à jour du registre."""
    action = event.data.get("action")
    entity_id = event.data.get("entity_id")
    
    if action != "create" or not entity_id or not entity_id.startswith("sensor.hse_"):
        return
    
    await _fix_long_sensor_name(hass, entity_id)


async def async_fix_all_long_sensors(hass: HomeAssistant) -> int:
    """Correction massive au démarrage."""
    _LOGGER.info("🔧 [HSE] Démarrage correction massive des noms longs...")
    registry = er.async_get(hass)
    fixed_count = 0
    
    for entity in list(registry.entities.values()):
        entity_id = entity.entity_id
        if entity_id.startswith("sensor.hse_") and len(entity_id) > MAX_ENTITY_ID_LENGTH:
            if await _fix_long_sensor_name(hass, entity_id):
                fixed_count += 1
    
    _LOGGER.info(f"✅ [HSE] Correction terminée : {fixed_count} sensors raccourcis")
    return fixed_count


async def async_setup_sensor_name_fixer(hass: HomeAssistant) -> None:
    """Configure le correcteur automatique."""
    _LOGGER.info("🎯 [HSE] Activation du correcteur automatique de noms")
    
    # ✅ FIX: Thread-safe callback using call_soon_threadsafe
    @callback
    def _sync_callback(event: Event) -> None:
        """Wrapper thread-safe."""
        # Utiliser call_soon_threadsafe pour garantir l'exécution dans l'event loop
        hass.loop.call_soon_threadsafe(
            hass.async_create_task,
            _on_entity_registry_updated(hass, event)
        )
    
    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _sync_callback)
    
    # Correction au démarrage
    @callback
    async def _fix_on_startup(event: Event) -> None:
        await async_fix_all_long_sensors(hass)
    
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _fix_on_startup)
    
    _LOGGER.info("✅ [HSE] Correcteur automatique activé")
