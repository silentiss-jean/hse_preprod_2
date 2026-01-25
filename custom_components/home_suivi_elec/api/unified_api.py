"""API REST Unifiée Home Suivi Élec - Connectée aux données réelles"""
import logging
import json
import os
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from ..export import ExportService
from ..cache_manager import get_cache_manager
from ..calculation_engine import CalculationEngine, PricingProfile
from ..diagnostics_engine import DiagnosticsEngine
from datetime import datetime, date
from ..utils.json_response import json_response

_LOGGER = logging.getLogger(__name__)

def _json_default(obj):
    """Serializer JSON custom pour gérer datetime/date automatiquement"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

class HomeElecUnifiedAPIView(HomeAssistantView):
    """API REST unifiée - Données réelles backend"""
    
    url = "/api/home_suivi_elec/{resource}"
    name = "api:home_suivi_elec:unified"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        _LOGGER.info("🏗️ API Unifiée - Connectée aux données backend")
        
    async def get(self, request, resource=None):
        """GET unifié - données réelles depuis backend"""
        try:
            # Récupérer resource depuis paramètre OU match_info
            if resource is None:
                resource = request.match_info.get("resource", "unknown")
            
            _LOGGER.info(f"🧪 API Unifiée GET: /{resource}")
            
            # Router selon resource avec données réelles
            if resource == "sensors":
                return await self._handle_sensors()
            elif resource == "data":
                return await self._handle_data()
            elif resource == "diagnostics":
                return await self._handle_diagnostics()
            elif resource == "config":
                return await self._handle_config()
            elif resource == "ui":
                return await self._handle_ui()
            elif resource == "get_sensors_health":
                return await self.handle_sensors_health()
            elif resource == "get_integrations_status":
                return await self._handle_integrations_status()
            elif resource == "get_logs":
                return await self._handle_logs()
            elif resource == 'sensor_mapping':
            	return await self.handle_sensor_mapping()
            elif resource == 'get_backend_health':
            	return await self._handle_backend_health()
            elif resource == "get_groups":
                return await self._handle_groups()
            elif resource == "get_group_sets":
                return await self._handle_group_sets()
            elif resource == "migration":
                return await self._handle_migration(request)
            elif resource == "cache_stats":
                return await self._handle_cache_stats()
            elif resource == "summary_metrics":
                return await self._handle_summary_metrics(request)
            elif resource == "deep_diagnostics":
                return await self._handle_deep_diagnostics()
            elif resource == "costs_overview":
                return await self._handle_costs_overview()
            else:
                return self._success({
                    "message": f"API Unifiée opérationnelle - resource: {resource}",
                    "available_endpoints": ["sensors", "data", "diagnostics", "config", "ui", "get_sensors_health", "get_integrations_status", "get_logs","sensor_mapping","get_backend_health","get_groups","get_group_sets","migration","cache_stats","summary_metrics", "deep_diagnostics", "costs_overview"],
                    "version": "unified-v1.0.42-final",
                    "status": "connected_to_backend"
                })
                
        except Exception as e:
            _LOGGER.exception(f"Erreur API GET: {e}")
            return self._error(500, str(e))

    # (reste du fichier inchangé)

    async def _handle_groups(self):
        try:
            from ..storage_manager import StorageManager
            from ..const import DOMAIN

            _LOGGER.debug("[get_groups] Début handler")

            data = self.hass.data.get(DOMAIN, {})
            mgr = data.get("storage_manager")
            _LOGGER.debug("[get_groups] mgr in hass.data: %r", type(mgr))

            if not isinstance(mgr, StorageManager):
                _LOGGER.debug("[get_groups] mgr pas StorageManager, on instancie")
                mgr = StorageManager(self.hass)

            groups = await mgr.get_sensor_groups()
            _LOGGER.debug("[get_groups] groups chargés: type=%s, len=%s",
                        type(groups), len(groups) if isinstance(groups, dict) else "n/a")

            if groups is None or not isinstance(groups, dict):
                _LOGGER.warning("[get_groups] format inattendu, fallback {}: %r", groups)
                groups = {}

            return self._success({
                "groups": groups,
                "count": len(groups),
                "type": "sensor_groups",
            })

        except Exception as e:
            _LOGGER.exception("Erreur _handle_groups: %s", e)
            return self._error(500, f"Erreur chargement groupes: {e}")

    async def _handle_group_sets(self):
        """Endpoint canon : retourne group_sets complet (rooms/types/...)"""
        try:
            from ..storage_manager import StorageManager
            from ..const import DOMAIN

            data = self.hass.data.get(DOMAIN, {})
            mgr = data.get("storage_manager")

            if not isinstance(mgr, StorageManager):
                mgr = StorageManager(self.hass)

            group_sets = await mgr.get_group_sets()
            if group_sets is None or not isinstance(group_sets, dict):
                group_sets = {"version": 1, "sets": {"rooms": {"mode": "exclusive", "groups": {}}, "types": {"mode": "multi", "groups": {}}}}

            sets = group_sets.get("sets") or {}
            count_sets = len(sets) if isinstance(sets, dict) else 0

            return self._success({
                "group_sets": group_sets,
                "count_sets": count_sets,
                "type": "group_sets",
            })

        except Exception as e:
            _LOGGER.exception("Erreur _handle_group_sets: %s", e)
            return self._error(500, f"Erreur chargement group_sets: {e}")
