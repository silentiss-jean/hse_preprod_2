"""Handler minimal pour ui_handler"""
import logging
from .base_handler import BaseHandler

_LOGGER = logging.getLogger(__name__)

class Ui_handler(BaseHandler):
    async def handle(self, method, resource, request):
        return self.success({"message": "ui_handler handler fonctionnel", "method": method, "resource": resource})
