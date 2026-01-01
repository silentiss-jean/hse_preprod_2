"""Handler pour gestion capteurs"""
import logging
from .base_handler import BaseHandler

_LOGGER = logging.getLogger(__name__)

class SensorsHandler(BaseHandler):
    """Handler pour capteurs et sélections"""
    
    async def handle(self, method: str, resource: str, request):
        """Router des requêtes sensors"""
        
        if method == "GET":
            if resource == "sensors":
                return await self._get_all_sensors()
            else:
                return self.error(404, f"GET {resource} not found")
        
        return self.error(405, f"Method {method} not allowed")
    
    async def _get_all_sensors(self):
        """Test simple - récupère sensors depuis hass.data"""
        try:
            domain_data = self.hass.data.get("home_suivi_elec", {})
            energy_sensors = domain_data.get("energy_sensors", [])
            power_sensors = domain_data.get("live_power_sensors", [])
            
            total = len(energy_sensors) + len(power_sensors)
            
            return self.success({
                "energy_sensors": len(energy_sensors),
                "power_sensors": len(power_sensors),
                "total": total,
                "message": f"API Unifiée fonctionnelle - {total} sensors détectés"
            })
            
        except Exception as e:
            _LOGGER.exception(f"Error getting sensors: {e}")
            return self.error(500, f"Failed to get sensors: {e}")
