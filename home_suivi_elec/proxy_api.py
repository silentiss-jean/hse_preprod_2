"""Proxy API pour authentification backend."""
import logging
import aiohttp
from aiohttp import web
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

class SuiviElecProxyView(HomeAssistantView):
    """Proxy les requêtes frontend vers les API backend."""
    url = "/api/home_suivi_elec/proxy"
    name = "api:home_suivi_elec:proxy"
    requires_auth = False
    cors_allowed = True

    async def post(self, request):
        """Proxy une requête."""
        try:
            data = await request.json()
            endpoint = data.get("endpoint")
            method = data.get("method", "GET").upper()
            
            if not endpoint:
                return web.json_response({"error": "endpoint requis"}, status=400)
            
            _LOGGER.info(f"[PROXY] {method} {endpoint}")
            
            # Construire l'URL complète
            base_url = str(request.url).replace("/api/home_suivi_elec/proxy", "")
            target_url = base_url + endpoint
            
            # Faire la requête vers l'API cible
            async with aiohttp.ClientSession() as session:
                async with session.request(method, target_url) as resp:
                    if resp.content_type == 'application/json':
                        result = await resp.json()
                    else:
                        result = {"error": await resp.text()}
                    return web.json_response(result, status=resp.status)
            
        except Exception as e:
            _LOGGER.error(f"[PROXY] Erreur: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
