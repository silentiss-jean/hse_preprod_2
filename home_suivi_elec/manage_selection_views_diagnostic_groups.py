from __future__ import annotations

import logging
from typing import Any, Dict, List
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

class DiagnosticGroupsView(HomeAssistantView):
    """
    GET /api/home_suivi_elec/diagnostic_groups

    Retourne un groupement backend fiable:
      - parents: liste des capteurs HSE Live (power) disponibles
      - children_by_parent: mapping parent → enfants (cycles energy)
      - orphans: enfants sans parent trouvé
      - stats: totaux et répartition
    """
    url = "/api/home_suivi_elec/diagnostic_groups"
    name = "api:home_suivi_elec:diagnostic_groups"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        try:
            states = self.hass.states.async_all("sensor")
            parents: List[Dict[str, Any]] = []
            children_by_parent: Dict[str, List[Dict[str, Any]]] = {}
            orphans: List[Dict[str, Any]] = []

            def is_parent(eid: str) -> bool:
                # parent: sensor.hse_live_* sans suffixe cycle
                return eid.startswith("sensor.hse_live_") and eid.count("_") > 2 and eid[-2] != "_"

            def parent_key_from_child(eid: str) -> str | None:
                # enfant: sensor.hse(_live)_<short>_<h|d|w|m|y>
                if not eid.startswith("sensor.hse_"):
                    return None
                parts = eid.split("_")
                if len(parts) < 4:
                    return None
                if parts[1] == "live":
                    # child of live → parent is sensor.hse_live_<short>
                    base = "_".join(parts[:3])  # sensor.hse.live
                    short = "_".join(parts[3:-1])
                    return f"sensor.hse_live_{short}"
                else:
                    short = "_".join(parts[2:-1])
                    return f"sensor.hse_live_{short}"

            # Index parents
            for s in states:
                eid = s.entity_id
                if is_parent(eid):
                    parents.append({
                        "entity_id": eid,
                        "state": s.state,
                        "friendly_name": s.attributes.get("friendly_name", eid),
                    })
                    children_by_parent[eid] = []

            # Associer enfants
            for s in states:
                eid = s.entity_id
                if eid.startswith("sensor.hse_") and (eid.endswith("_h") or eid.endswith("_d") or eid.endswith("_w") or eid.endswith("_m") or eid.endswith("_y")):
                    p = parent_key_from_child(eid)
                    if p and p in children_by_parent:
                        children_by_parent[p].append({
                            "entity_id": eid,
                            "state": s.state,
                            "friendly_name": s.attributes.get("friendly_name", eid),
                        })
                    else:
                        orphans.append({
                            "entity_id": eid,
                            "state": s.state,
                            "friendly_name": s.attributes.get("friendly_name", eid),
                        })

            stats = {
                "parents": len(parents),
                "children": sum(len(v) for v in children_by_parent.values()),
                "orphans": len(orphans),
            }

            return self.json({
                "success": True,
                "parents": parents,
                "children_by_parent": children_by_parent,
                "orphans": orphans,
                "stats": stats,
            })
        except Exception as e:
            _LOGGER.exception("diagnostic_groups error: %s", e)
            return self.json({"success": False, "error": str(e)}, status_code=500)
