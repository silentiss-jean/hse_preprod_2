"""Handler minimal pour data_handler"""
import logging
from .base_handler import BaseHandler

_LOGGER = logging.getLogger(__name__)

class Data_handler(BaseHandler):
    async def handle(self, method, resource, request):
        return self.success({"message": "data_handler handler fonctionnel", "method": method, "resource": resource})
