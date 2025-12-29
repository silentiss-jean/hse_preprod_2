# -*- coding: utf-8 -*-
"""
Vue API REST pour l'analyse des capteurs cachés/désactivés.
"""

import logging
from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)


class HiddenSensorsView(HomeAssistantView):
    """GET /api/home_suivi_elec/hidden_sensors - Analyse capteurs cachés"""
    url = "/api/home_suivi_elec/hidden_sensors"
    name = "api:home_suivi_elec:hidden_sensors"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        try:
            from .detect_local import detect_hidden_sensors
            result = await detect_hidden_sensors(self.hass)
            return self.json(result)
        except Exception as e:
            _LOGGER.exception("[HIDDEN-SENSORS] Erreur: %s", e)
            return self.json({"success": False, "error": str(e)}, status_code=500)
