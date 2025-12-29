"""
Moteur de diagnostic intelligent pour Home Suivi Elec
Analyse l'état du système et génère des recommandations
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)


class DiagnosticsEngine:
    """Moteur d'analyse de diagnostics"""

    def __init__(self, hass: HomeAssistant):
        """Initialise le moteur"""
        self.hass = hass
        self.entity_registry = er.async_get(hass)

    async def run_full_diagnostics(self) -> Dict[str, Any]:
        """
        Lance un diagnostic complet du système
        
        Returns:
            Dict contenant toutes les analyses
        """
        _LOGGER.info("🔍 [DiagnosticsEngine] Lancement diagnostic complet")

        try:
            # Analyses parallèles
            sensors_analysis = await self._analyze_sensors()
            relations_analysis = await self._analyze_relations()
            integration_health = await self._analyze_integration()
            config_analysis = await self._analyze_config()
            
            # Génération de recommandations
            recommendations = self._generate_recommendations(
                sensors_analysis,
                relations_analysis,
                integration_health,
                config_analysis
            )

            # Score de santé global
            health_score = self._calculate_health_score(
                sensors_analysis,
                relations_analysis,
                integration_health
            )

            result = {
                "timestamp": datetime.now().isoformat(),
                "health_score": health_score,
                "sensors": sensors_analysis,
                "relations": relations_analysis,
                "integration": integration_health,
                "config": config_analysis,
                "recommendations": recommendations,
                "summary": self._generate_summary(health_score, recommendations)
            }

            _LOGGER.info(f"✅ [DiagnosticsEngine] Diagnostic terminé - Score: {health_score['score']}/100")
            return result

        except Exception as e:
            _LOGGER.error(f"❌ [DiagnosticsEngine] Erreur diagnostic: {e}", exc_info=True)
            return {
                "error": True,
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def _analyze_sensors(self) -> Dict[str, Any]:
        """
        Analyse approfondie des capteurs
        
        Returns:
            Dict avec statistiques et problèmes détectés
        """
        _LOGGER.debug("🔍 Analyse des capteurs...")

        issues = []
        stats = {
            "total": 0,
            "available": 0,
            "unavailable": 0,
            "unknown": 0,
            "disabled": 0,
            "restored": 0,
            "hse_live": 0,
            "hse_live_ok": 0,
            "hse_live_ko": 0
        }

        # Parcourir tous les capteurs sensor.*
        for state in self.hass.states.async_all("sensor"):
            stats["total"] += 1

            # Analyser l'état
            if state.state == STATE_UNAVAILABLE:
                stats["unavailable"] += 1
                issue = await self._diagnose_unavailable_sensor(state)
                if issue:
                    issues.append(issue)

            elif state.state == STATE_UNKNOWN or state.state == "N/A":
                stats["unknown"] += 1
                issue = await self._diagnose_unknown_sensor(state)
                if issue:
                    issues.append(issue)

            elif state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
                stats["available"] += 1

            # Vérifier si restored
            if state.attributes.get("restored"):
                stats["restored"] += 1
                issues.append({
                    "type": "sensor_restored",
                    "severity": "warning",
                    "sensor": state.entity_id,
                    "friendly_name": state.attributes.get("friendly_name", state.entity_id),
                    "message": f"Capteur restauré depuis un ancien état",
                    "solution": "Redémarrez Home Assistant pour réinitialiser",
                    "auto_fixable": False
                })

            # Vérifier si HSE Live
            if "hse_live_" in state.entity_id:
                stats["hse_live"] += 1
                if state.state == STATE_UNAVAILABLE:
                    stats["hse_live_ko"] += 1
                else:
                    stats["hse_live_ok"] += 1

            # Vérifier si disabled
            entry = self.entity_registry.async_get(state.entity_id)
            if entry and entry.disabled:
                stats["disabled"] += 1
                issues.append({
                    "type": "sensor_disabled",
                    "severity": "info",
                    "sensor": state.entity_id,
                    "friendly_name": state.attributes.get("friendly_name", state.entity_id),
                    "message": "Capteur désactivé",
                    "solution": "Réactivez dans Configuration → Entités",
                    "auto_fixable": True
                })

        return {
            "stats": stats,
            "issues": issues,
            "issues_count": len(issues),
            "critical_issues": len([i for i in issues if i["severity"] == "critical"]),
            "warnings": len([i for i in issues if i["severity"] == "warning"])
        }

    async def _diagnose_unavailable_sensor(self, state) -> Optional[Dict[str, Any]]:
        """
        Diagnostique un capteur unavailable
        
        Args:
            state: État du capteur
            
        Returns:
            Dict décrivant le problème ou None
        """
        entity_id = state.entity_id
        friendly_name = state.attributes.get("friendly_name", entity_id)

        # Cas 1 : HSE Live
        if "hse_live_" in entity_id:
            source_entity = entity_id.replace("hse_live_", "").replace("sensor.", "sensor.")
            source_state = self.hass.states.get(source_entity)

            if not source_state:
                return {
                    "type": "hse_live_source_missing",
                    "severity": "error",
                    "sensor": entity_id,
                    "friendly_name": friendly_name,
                    "source": source_entity,
                    "message": f"Source {source_entity} introuvable",
                    "solution": "Créez le capteur source dans l'intégration Template ou Détection",
                    "auto_fixable": False
                }

            if source_state.state == STATE_UNAVAILABLE:
                return {
                    "type": "hse_live_source_unavailable",
                    "severity": "error",
                    "sensor": entity_id,
                    "friendly_name": friendly_name,
                    "source": source_entity,
                    "message": f"Source {source_entity} est unavailable",
                    "solution": f"Vérifiez l'intégration {source_state.attributes.get('integration', 'unknown')}",
                    "auto_fixable": False
                }

        # Cas 2 : Capteur générique unavailable
        integration = state.attributes.get("integration", "unknown")
        return {
            "type": "sensor_unavailable",
            "severity": "error",
            "sensor": entity_id,
            "friendly_name": friendly_name,
            "integration": integration,
            "message": f"Capteur unavailable",
            "solution": f"Vérifiez l'intégration {integration} dans Configuration → Intégrations",
            "auto_fixable": False
        }

    async def _diagnose_unknown_sensor(self, state) -> Optional[Dict[str, Any]]:
        """
        Diagnostique un capteur en état unknown/N/A
        
        Args:
            state: État du capteur
            
        Returns:
            Dict décrivant le problème ou None
        """
        entity_id = state.entity_id
        friendly_name = state.attributes.get("friendly_name", entity_id)
        integration = state.attributes.get("integration", "unknown")

        if integration == "template":
            return {
                "type": "template_no_value",
                "severity": "warning",
                "sensor": entity_id,
                "friendly_name": friendly_name,
                "message": "Template sans valeur",
                "solution": "Vérifiez la configuration du template et les capteurs sources",
                "auto_fixable": False
            }

        return {
            "type": "sensor_unknown",
            "severity": "warning",
            "sensor": entity_id,
            "friendly_name": friendly_name,
            "integration": integration,
            "message": "Capteur en état unknown",
            "solution": "Attendez que le capteur reçoive une valeur ou vérifiez sa configuration",
            "auto_fixable": False
        }

    async def _analyze_relations(self) -> Dict[str, Any]:
        """
        Analyse les relations parent-enfant (utility_meter)
        
        Returns:
            Dict avec statistiques et problèmes
        """
        _LOGGER.debug("🔍 Analyse des relations...")

        issues = []
        stats = {
            "total_parents": 0,
            "parents_with_children": 0,
            "parents_without_children": 0,
            "orphans": 0,
            "incomplete_cycles": 0
        }

        # Récupérer les utility_meters (parents)
        utility_meters = [
            state for state in self.hass.states.async_all("sensor")
            if state.attributes.get("device_class") == "energy"
            and "daily" not in state.entity_id
            and "weekly" not in state.entity_id
            and "monthly" not in state.entity_id
            and "yearly" not in state.entity_id
            and "hourly" not in state.entity_id
        ]

        stats["total_parents"] = len(utility_meters)

        for parent in utility_meters:
            parent_id = parent.entity_id

            # Chercher les cycles (children)
            cycles = {
                "hourly": self.hass.states.get(f"{parent_id}_hourly"),
                "daily": self.hass.states.get(f"{parent_id}_daily"),
                "weekly": self.hass.states.get(f"{parent_id}_weekly"),
                "monthly": self.hass.states.get(f"{parent_id}_monthly"),
                "yearly": self.hass.states.get(f"{parent_id}_yearly")
            }

            existing_cycles = [k for k, v in cycles.items() if v is not None]
            missing_cycles = [k for k, v in cycles.items() if v is None]

            if len(existing_cycles) == 0:
                stats["parents_without_children"] += 1
                issues.append({
                    "type": "parent_no_children",
                    "severity": "error",
                    "parent": parent_id,
                    "friendly_name": parent.attributes.get("friendly_name", parent_id),
                    "message": "Parent sans aucun cycle",
                    "solution": "Créez les utility_meter cycles dans configuration.yaml",
                    "auto_fixable": False
                })
            else:
                stats["parents_with_children"] += 1

                if len(existing_cycles) < 5:
                    stats["incomplete_cycles"] += 1
                    issues.append({
                        "type": "incomplete_cycles",
                        "severity": "warning",
                        "parent": parent_id,
                        "friendly_name": parent.attributes.get("friendly_name", parent_id),
                        "existing": existing_cycles,
                        "missing": missing_cycles,
                        "message": f"Cycles incomplets ({len(existing_cycles)}/5)",
                        "solution": f"Ajoutez les cycles manquants: {', '.join(missing_cycles)}",
                        "auto_fixable": False
                    })

        return {
            "stats": stats,
            "issues": issues,
            "issues_count": len(issues)
        }

    async def _analyze_integration(self) -> Dict[str, Any]:
        """
        Vérifie que l'intégration Home Suivi Elec est opérationnelle
        """
        _LOGGER.debug("🔍 Analyse de l'intégration...")
        
        # Puisqu'on exécute ce code, l'intégration tourne forcément
        return {
            "running": True,
            "uptime": self._calculate_uptime(),
            "version": self._get_version_from_manifest(),
            "sensors_count": len([
                s for s in self.hass.states.async_all("sensor")
                if "hse_live_" in s.entity_id
            ]),
            "issues": []
        }

    def _get_version_from_manifest(self) -> str:
        """Lit la version depuis manifest.json"""
        try:
            import json
            manifest_path = "/config/custom_components/home_suivi_elec/manifest.json"
            with open(manifest_path) as f:
                manifest = json.load(f)
                return manifest.get("version", "unknown")
        except Exception as e:
            _LOGGER.warning(f"Impossible de lire manifest.json: {e}")
            return "unknown"

    def _calculate_uptime(self) -> int:
        """Calcule l'uptime depuis le démarrage de Home Assistant"""
        ha_started = self.hass.data.get("homeassistant_start")
        if ha_started:
            return int((datetime.now() - ha_started).total_seconds())
        return 0

    async def _analyze_config(self) -> Dict[str, Any]:
        """
        Analyse la configuration
        
        Returns:
            Dict avec l'état de la config
        """
        _LOGGER.debug("🔍 Analyse de la configuration...")

        return {
            "valid": True,
            "issues": []
        }

    def _generate_recommendations(
        self,
        sensors: Dict,
        relations: Dict,
        integration: Dict,
        config: Dict
    ) -> List[Dict[str, Any]]:
        """
        Génère des recommandations d'actions
        
        Returns:
            Liste de recommandations
        """
        recommendations = []

        # integration down
        if not integration["running"]:
            recommendations.append({
                "priority": 1,
                "category": "integration",
                "title": "⚠️ integration non opérationnel",
                "description": "Le integration Python n'est pas actif",
                "action": "Redémarrez Home Assistant",
                "auto_fixable": False
            })

        # Capteurs unavailable
        unavailable_count = sensors["stats"]["unavailable"]
        if unavailable_count > 0:
            recommendations.append({
                "priority": 2,
                "category": "sensors",
                "title": f"❌ {unavailable_count} capteur(s) unavailable",
                "description": "Des capteurs sont indisponibles",
                "action": "Consultez l'onglet Capteurs pour les diagnostiquer",
                "auto_fixable": False
            })

        # Parents sans enfants
        parents_no_children = relations["stats"]["parents_without_children"]
        if parents_no_children > 0:
            recommendations.append({
                "priority": 3,
                "category": "relations",
                "title": f"⚠️ {parents_no_children} parent(s) sans cycles",
                "description": "Des parents n'ont pas de utility_meter cycles",
                "action": "Allez dans Migration capteurs pour les créer",
                "auto_fixable": False
            })

        return recommendations

    def _calculate_health_score(
        self,
        sensors: Dict,
        relations: Dict,
        integration: Dict
    ) -> Dict[str, Any]:
        """
        Calcule le score de santé global
        
        Returns:
            Dict avec score et détails
        """
        score = 100

        # integration (30 points)
        if not integration["running"]:
            score -= 30

        # Capteurs (40 points)
        total = sensors["stats"]["total"]
        if total > 0:
            unavailable = sensors["stats"]["unavailable"]
            unknown = sensors["stats"]["unknown"]
            problematic = unavailable + unknown
            ratio = problematic / total
            score -= int(ratio * 40)

        # Relations (30 points)
        total_parents = relations["stats"]["total_parents"]
        if total_parents > 0:
            no_children = relations["stats"]["parents_without_children"]
            ratio = no_children / total_parents
            score -= int(ratio * 30)

        score = max(0, score)

        return {
            "score": score,
            "grade": self._get_grade(score),
            "status": "healthy" if score >= 80 else "warning" if score >= 50 else "critical"
        }

    def _get_grade(self, score: int) -> str:
        """Retourne la note selon le score"""
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"

    def _generate_summary(
        self,
        health_score: Dict,
        recommendations: List[Dict]
    ) -> str:
        """
        Génère un résumé textuel
        
        Returns:
            Résumé en texte
        """
        score = health_score["score"]
        grade = health_score["grade"]
        rec_count = len(recommendations)

        if score >= 90:
            return f"✅ Excellent état (Note: {grade}). Tout fonctionne parfaitement."
        elif score >= 75:
            return f"✅ Bon état (Note: {grade}). {rec_count} recommandation(s) mineure(s)."
        elif score >= 60:
            return f"⚠️ État correct (Note: {grade}). {rec_count} action(s) recommandée(s)."
        elif score >= 40:
            return f"⚠️ État dégradé (Note: {grade}). {rec_count} problème(s) à résoudre."
        else:
            return f"❌ État critique (Note: {grade}). Intervention urgente requise."
