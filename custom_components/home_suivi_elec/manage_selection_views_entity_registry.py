from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView

from .entity_name_registry import EntityNameRegistry

_LOGGER = logging.getLogger(__name__)

class GetEntityNameRegistryView(HomeAssistantView):
    """
    GET /api/home_suivi_elec/entity_name_registry
    Retourne le mapping nom_court → nom_affichage et stats.
    """
    url = "/api/home_suivi_elec/entity_name_registry"
    name = "api:home_suivi_elec:entity_name_registry"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.data_dir = Path(__file__).parent / "data"

    async def get(self, request):
        try:
            registry = EntityNameRegistry(self.data_dir)
            return self.json({
                "success": True,
                "mappings": registry.mappings(),
                "stats": registry.stats(),
            })
        except Exception as e:
            _LOGGER.exception("[ENTITY-NAME-REGISTRY] GET failed: %s", e)
            return self.json({"success": False, "error": str(e)}, status_code=500)
