from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict

from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView

from .const import HSE_CYCLES, is_hse_sensor

_LOGGER = logging.getLogger(__name__)


class DiagnosticGroupsView(HomeAssistantView):
    """
    GET /api/home_suivi_elec/diagnostic_groups

    Mode B : Groupement par parent (power/energy détectés), peu importe la pièce.
    
    Retourne:
      - parents: tous capteurs détectés (power+energy) avec statut actif/inactif
      - children_by_parent: enfants HSE cycles rattachés à chaque parent
      - orphans: enfants HSE sans parent trouvé
      - stats: compteurs et répartition
    
    Sources:
      - capteurs_power_v1 : inventaire détecté (parents)
      - capteurs_selection_v2 : sélection UI (actif/inactif)
      - cost_ha_v1 : config coût par enfant cycle
      - états HA : états actuels (fallback)
    """
    
    url = "/api/home_suivi_elec/diagnostic_groups"
    name = "api:home_suivi_elec:diagnostic_groups"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        try:
            from .storage_manager import StorageManager
            
            storage = StorageManager(self.hass)
            
            # 1) Charger les stores
            capteurs_power = await storage.get_capteurs_power()
            capteurs_selection_data = await storage.get_capteurs_selection()
            cost_map = await storage.get_cost_ha_config()
            
            # 2) Index de sélection (par entity_id)
            selection_index = {}
            for integration, sensors in capteurs_selection_data.items():
                if isinstance(sensors, list):
                    for s in sensors:
                        eid = s.get("entity_id")
                        if eid:
                            selection_index[eid] = s
            
            # 3) Construire les parents (mode B: power + energy)
            parents = []
            parent_by_id = {}
            
            for capteur in capteurs_power:
                if not isinstance(capteur, dict):
                    continue
                    
                entity_id = capteur.get("entity_id")
                if not entity_id:
                    continue
                
                sensor_type = capteur.get("type", "").lower()
                device_class = capteur.get("device_class", "").lower()
                
                # Mode B: on garde power ET energy
                if sensor_type not in ("power", "energy"):
                    continue
                if device_class not in ("power", "energy"):
                    continue
                
                # Déterminer si actif (sélectionné ET enabled)
                sel = selection_index.get(entity_id, {})
                selected = entity_id in selection_index
                enabled = sel.get("enabled", False) if selected else False
                active = selected and enabled
                
                # État HA (si dispo)
                state_obj = self.hass.states.get(entity_id)
                current_state = state_obj.state if state_obj else "unknown"
                friendly_name = capteur.get("friendly_name") or (
                    state_obj.attributes.get("friendly_name") if state_obj else entity_id
                )
                
                parent = {
                    "entity_id": entity_id,
                    "friendly_name": friendly_name,
                    "type": sensor_type,
                    "device_class": device_class,
                    "integration": capteur.get("integration"),
                    "device_id": capteur.get("device_id"),
                    "selected": selected,
                    "enabled": enabled,
                    "active": active,
                    "state": current_state,
                    "related_power": capteur.get("related_power"),
                    "related_energy": capteur.get("related_energy"),
                    "priority": capteur.get("priority", 0),
                    "reliability_score": capteur.get("reliability_score", 0),
                }
                
                parents.append(parent)
                parent_by_id[entity_id] = parent
            
            # 4) Trouver les enfants HSE cycles pour chaque parent
            children_by_parent: Dict[str, Dict[str, Any]] = {}
            orphans = []
            
            # Récupérer tous les états HSE
            all_states = self.hass.states.async_all("sensor")
            hse_sensors = [
                s for s in all_states 
                if s.entity_id.startswith(("sensor.hse_", "sensor.hse_energy_"))
            ]
            
            # Index enfants par parent via matching slug
            for state in hse_sensors:
                eid = state.entity_id
                
                # Vérifier que c'est bien un cycle HSE (pas un live ou autre)
                if not is_hse_sensor(eid):
                    continue
                
                # Extraire le cycle
                cycle = None
                for c in HSE_CYCLES:
                    if eid.endswith(f"_{c}"):
                        cycle = c
                        break
                
                if not cycle:
                    continue
                
                # Trouver le parent par matching slug
                parent_id = self._find_parent_for_child(eid, parent_by_id)
                
                # Config coût
                cost_config = cost_map.get(eid, {})
                cost_enabled = cost_config.get("enabled", False)
                cost_entity_id = cost_config.get("cost_entity_id")
                
                child = {
                    "entity_id": eid,
                    "friendly_name": state.attributes.get("friendly_name", eid),
                    "state": state.state,
                    "cycle": cycle,
                    "cost_enabled": cost_enabled,
                    "cost_entity_id": cost_entity_id,
                }
                
                if parent_id:
                    if parent_id not in children_by_parent:
                        children_by_parent[parent_id] = {
                            "cycles": defaultdict(list)
                        }
                    children_by_parent[parent_id]["cycles"][cycle].append(child)
                else:
                    orphans.append(child)
            
            # 5) Stats
            total_children = sum(
                len(children)
                for parent_children in children_by_parent.values()
                for children in parent_children["cycles"].values()
            )
            
            active_parents = [p for p in parents if p["active"]]
            inactive_parents = [p for p in parents if not p["active"]]
            
            stats = {
                "total_parents": len(parents),
                "active_parents": len(active_parents),
                "inactive_parents": len(inactive_parents),
                "power_parents": len([p for p in parents if p["type"] == "power"]),
                "energy_parents": len([p for p in parents if p["type"] == "energy"]),
                "total_children": total_children,
                "orphans": len(orphans),
                "cost_enabled_children": sum(
                    1 for parent_children in children_by_parent.values()
                    for children in parent_children["cycles"].values()
                    for child in children
                    if child.get("cost_enabled")
                ),
            }
            
            return self.json({
                "success": True,
                "mode": "B",
                "description": "Parents = power+energy détectés, enfants = cycles HSE",
                "parents": parents,
                "children_by_parent": children_by_parent,
                "orphans": orphans,
                "stats": stats,
            })
            
        except Exception as e:
            _LOGGER.exception("diagnostic_groups error: %s", e)
            return self.json({
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
            }, status_code=500)
    
    def _find_parent_for_child(
        self,
        child_entity_id: str,
        parent_by_id: Dict[str, Dict[str, Any]]
    ) -> Optional[str]:
        """
        Trouve le parent d'un enfant HSE cycle par matching slug.
        
        Exemples:
        - sensor.hse_tapo_salon_tv_power_energy_daily → sensor.tapo_salon_tv_power
        - sensor.hse_tapo_salon_tv_energy_daily → sensor.tapo_salon_tv_today_energy
        - sensor.hse_tp_link_salon_box_energy_daily → sensor.tp_link_salon_box_today_energy
        
        Logique:
        1. Enlever "sensor.hse_" ou "sensor.hse_energy_"
        2. Enlever le suffixe cycle (_hourly, _daily, etc.)
        3. Chercher un parent dont le slug (sans "sensor.") correspond
        """
        # Retirer préfixes HSE
        if child_entity_id.startswith("sensor.hse_energy_"):
            base = child_entity_id.replace("sensor.hse_energy_", "")
        elif child_entity_id.startswith("sensor.hse_"):
            base = child_entity_id.replace("sensor.hse_", "")
        else:
            return None
        
        # Retirer suffixe cycle
        for cycle in HSE_CYCLES:
            if base.endswith(f"_{cycle}"):
                base = base[: -len(cycle) - 1]
                break
        
        # Normaliser: retirer les suffixes courants "_power_energy" / "_energy"
        if base.endswith("_power_energy"):
            base = base.replace("_power_energy", "_power")
        elif base.endswith("_energy") and not base.endswith("today_energy"):
            # cas sensor.hse_tapo_salon_tv_energy_daily → chercher *_today_energy
            base_try = base.replace("_energy", "_today_energy")
            for parent_id in parent_by_id:
                parent_slug = parent_id.replace("sensor.", "").replace(".", "_")
                if parent_slug == base_try:
                    return parent_id
        
        # Matching direct
        for parent_id in parent_by_id:
            parent_slug = parent_id.replace("sensor.", "").replace(".", "_")
            
            # Match exact
            if parent_slug == base:
                return parent_id
            
            # Match partiel (base contenu dans parent_slug ou inverse)
            if base in parent_slug or parent_slug in base:
                # Vérifier cohérence (même racine de nom)
                common = self._common_prefix(base, parent_slug)
                if len(common) > len(base) * 0.6:  # 60% de similarité minimum
                    return parent_id
        
        return None
    
    def _common_prefix(self, s1: str, s2: str) -> str:
        """Retourne le préfixe commun entre 2 strings."""
        i = 0
        while i < len(s1) and i < len(s2) and s1[i] == s2[i]:
            i += 1
        return s1[:i]
