"""Handler minimal pour config_handler"""
import logging
from .base_handler import BaseHandler

_LOGGER = logging.getLogger(__name__)

class Config_handler(BaseHandler):
    async def handle(self, method, resource, request):
        return self.success({"message": "config_handler handler fonctionnel", "method": method, "resource": resource})
