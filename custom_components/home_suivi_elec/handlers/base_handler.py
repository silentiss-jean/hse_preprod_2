"""Handler de base pour tous les handlers API"""
import logging
from abc import ABC, abstractmethod
from typing import Any
from aiohttp import web
from homeassistant.core import HomeAssistant
from ..utils.json_response import json_response

_LOGGER = logging.getLogger(__name__)

class BaseHandler(ABC):
    """Classe de base pour tous les handlers API"""
    
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
    
    @abstractmethod
    async def handle(self, method: str, resource: str, request) -> web.Response:
        """Méthode abstraite à implémenter par chaque handler"""
        pass
    
    def success(self, data: Any) -> web.Response:
        """Réponse de succès standardisée"""
        return json_response({
            "error": False,
            "data": data
        })
    
    def error(self, status: int, message: str) -> web.Response:
        """Réponse d'erreur standardisée"""
        return json_response({
            "error": True,
            "status": status,
            "message": message
        }, status=status)
    
    async def get_request_json(self, request) -> dict:
        """Extraction JSON sécurisée depuis request"""
        try:
            return await request.json()
        except Exception as e:
            _LOGGER.warning(f"Invalid JSON in request: {e}")
            return {}
