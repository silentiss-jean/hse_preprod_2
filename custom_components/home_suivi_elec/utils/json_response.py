"""
Helper centralisé pour les réponses JSON avec support datetime
"""
import json
from datetime import datetime, date
from aiohttp import web


def _json_default(obj):
    """Serializer JSON custom pour datetime/date"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def json_response(data, *, status=200, **kwargs) -> web.Response:
    """
    Wrapper pour web.json_response avec support datetime automatique
    
    Usage:
        return json_response({"data": some_data})
        return json_response({"error": "message"}, status=400)
    """
    return web.json_response(
        data,
        status=status,
        dumps=lambda x: json.dumps(x, default=_json_default),
        **kwargs
    )

