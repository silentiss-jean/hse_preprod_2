"""Handler minimal pour diagnostics_handler"""
import logging
from .base_handler import BaseHandler

_LOGGER = logging.getLogger(__name__)

class Diagnostics_handler(BaseHandler):
    async def handle(self, method, resource, request):
        return self.success({"message": "diagnostics_handler handler fonctionnel", "method": method, "resource": resource})
