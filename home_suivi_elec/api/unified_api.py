"""API REST Unifiée Home Suivi Élec - Connectée aux données réelles"""
import logging
import json
import os
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from ..export import ExportService
from ..cache_manager import get_cache_manager
from ..calculation_engine import CalculationEngine, PricingProfile

_LOGGER = logging.getLogger(__name__)

class HomeElecUnifiedAPIView(HomeAssistantView):
    """API REST unifiée - Données réelles backend"""
    
    url = "/api/home_suivi_elec/{resource}"
    name = "api:home_suivi_elec:unified"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        _LOGGER.info("🏗️ API Unifiée - Connectée aux données backend")
        
    async def get(self, request, resource=None):
        """GET unifié - données réelles depuis backend"""
        try:
            # Récupérer resource depuis paramètre OU match_info
            if resource is None:
                resource = request.match_info.get("resource", "unknown")
            
            _LOGGER.info(f"🧪 API Unifiée GET: /{resource}")
            
            # Router selon resource avec données réelles
            if resource == "sensors":
                return await self._handle_sensors()
            elif resource == "data":
                return await self._handle_data()
            elif resource == "diagnostics":
                return await self._handle_diagnostics()
            elif resource == "config":
                return await self._handle_config()
            elif resource == "ui":
                return await self._handle_ui()
            elif resource == "get_sensors_health":
                return await self.handle_sensors_health()
            elif resource == "get_integrations_status":
                return await self._handle_integrations_status()
            elif resource == "get_logs":
                return await self._handle_logs()
            elif resource == 'sensor_mapping':
            	return await self.handle_sensor_mapping()
            elif resource == 'get_backend_health':
            	return await self._handle_backend_health()
            elif resource == "get_groups":
                return await self._handle_groups()
            elif resource == "migration":
                return await self._handle_migration(request)
            elif resource == "cache_stats":
                return await self._handle_cache_stats()
            elif resource == "summary_metrics":
                return await self._handle_summary_metrics(request)
            else:
                return self._success({
                    "message": f"API Unifiée opérationnelle - resource: {resource}",
                    "available_endpoints": ["sensors", "data", "diagnostics", "config", "ui", "get_sensors_health", "get_integrations_status", "get_logs","sensor_mapping","get_backend_health","get_groups","migration","cache_stats","summary_metrics"],
                    "version": "unified-v1.0.42-final",
                    "status": "connected_to_backend"
                })
                
        except Exception as e:
            _LOGGER.exception(f"Erreur API GET: {e}")
            return self._error(500, str(e))
    
    async def _handle_sensors(self):
        """Endpoint /sensors - Liste des capteurs détectés avec fusion sélection"""
        try:
            # ✅ 1. Charger capteurs détectés (capteurs_power.json)
            sensors_data = await self._load_sensors_data()
            
            # ✅ 2. Charger sélection utilisateur (capteurs_selection.json) 
            selection_data = await self._load_selection_data()
            
            # ✅ 3. Créer index de sélection pour fusion rapide
            selection_index = {}
            for category, items in selection_data.items():
                if isinstance(items, list):
                    for item in items:
                        entity_id = item.get("entity_id")
                        if entity_id:
                            selection_index[entity_id] = item.get("enabled", False)
            
            _LOGGER.info(f"🔀 Fusion: {len(sensors_data)} capteurs détectés + {len(selection_index)} sélections")
            
            # ✅ 4. Enrichir capteurs avec état HA + sélection
            enriched_sensors = []
            for sensor in sensors_data:
                entity_id = sensor.get("entity_id")
                if entity_id:
                    state_obj = self.hass.states.get(entity_id)
                    sensor_info = sensor.copy()
                    
                    # Fusion avec sélection utilisateur
                    sensor_info["enabled"] = selection_index.get(entity_id, False)
                    
                    # Fusion avec état Home Assistant
                    sensor_info.update({
                        "current_state": state_obj.state if state_obj else "unavailable",
                        "last_changed": state_obj.last_changed.isoformat() if state_obj else None,
                        "attributes": dict(state_obj.attributes) if state_obj else {}
                    })
                    enriched_sensors.append(sensor_info)
            
            # ✅ 5. Statistiques
            enabled_count = len([s for s in enriched_sensors if s.get("enabled", False)])
            _LOGGER.info(f"📊 Fusion résultat: {enabled_count}/{len(enriched_sensors)} capteurs activés")
            
            return self._success({
                "sensors": enriched_sensors,
                "count": len(enriched_sensors),
                "enabled_count": enabled_count,
                "type": "sensors",
                "source": "capteurs_power.json + capteurs_selection.json + live_states"
            })
            
        except Exception as e:
            _LOGGER.exception(f"Erreur _handle_sensors: {e}")
            return self._error(500, f"Erreur chargement capteurs: {e}")
    
    async def _handle_data(self):
        """Endpoint /data - Données de consommation"""
        try:
            # Charger sélection utilisateur
            selection_data = await self._load_selection_data()
            
            # Récupérer données des capteurs HSE energy
            energy_sensors = self._get_hse_energy_sensors()
            
            consumptions = []
            for sensor_state in energy_sensors:
                entity_id = sensor_state.entity_id
                state = sensor_state.state
                attributes = dict(sensor_state.attributes)
                
                try:
                    value = float(state) if state not in ('unknown', 'unavailable') else 0.0
                except (ValueError, TypeError):
                    value = 0.0
                
                consumptions.append({
                    "entity_id": entity_id,
                    "friendly_name": attributes.get("friendly_name", entity_id),
                    "value": value,
                    "unit": attributes.get("unit_of_measurement", "kWh"),
                    "cycle": self._extract_cycle_from_entity(entity_id),
                    "last_reset": attributes.get("last_reset"),
                    "source_sensor": attributes.get("source_sensor")
                })
            
            return self._success({
                "consumptions": consumptions,
                "count": len(consumptions),
                "type": "data",
                "timestamp": self._get_timestamp()
            })
            
        except Exception as e:
            _LOGGER.exception(f"Erreur _handle_data: {e}")
            return self._error(500, f"Erreur chargement données: {e}")
    
    async def _handle_diagnostics(self):
        """Endpoint /diagnostics - État système"""
        try:
            # Statistiques générales
            all_sensors = await self._load_sensors_data()
            hse_sensors = self._get_hse_energy_sensors()
            
            # Analyser état des capteurs
            health_check = {
                "total_detected": len(all_sensors),
                "hse_energy_sensors": len(hse_sensors),
                "unavailable_sensors": len([
                    s for s in hse_sensors 
                    if s.state in ('unavailable', 'unknown')
                ]),
                "last_detection": self._get_last_detection_time(),
                "api_endpoints_active": 6
            }
            
            # État global
            system_status = "operational"
            if health_check["unavailable_sensors"] > health_check["hse_energy_sensors"] * 0.3:
                system_status = "degraded"
            if health_check["hse_energy_sensors"] == 0:
                system_status = "critical"
            
            return self._success({
                "system_status": system_status,
                "api_version": "unified-v1.0.42-final",
                "health_check": health_check,
                "backend_connected": True,
                "data_sources": {
                    "capteurs_power": os.path.exists(self._get_sensors_file_path()),
                    "capteurs_selection": os.path.exists(self._get_selection_file_path()),
                    "hass_states": len(self.hass.states.async_all()) > 0
                }
            })
            
        except Exception as e:
            _LOGGER.exception(f"Erreur _handle_diagnostics: {e}")
            return self._error(500, f"Erreur diagnostics: {e}")
    
    async def _handle_config(self):
        """Endpoint /config - Configuration actuelle"""
        try:
            from ..const import DOMAIN
            
            config_data = self.hass.data.get(DOMAIN, {}).get("config", {})
            options_data = self.hass.data.get(DOMAIN, {}).get("options", {})
            
            return self._success({
                "config": config_data,
                "options": options_data,
                "type": "config",
                "domain": DOMAIN
            })
            
        except Exception as e:
            _LOGGER.exception(f"Erreur _handle_config: {e}")
            return self._error(500, f"Erreur configuration: {e}")
    
    async def _handle_ui(self):
        """Endpoint /ui - Informations interface"""
        try:
            ui_info = {
                "panel_registered": True,
                "panel_url": "/local/community/home_suivi_elec_ui/index.html",
                "sidebar_title": "⚡ Suivi Élec",
                "api_base_url": "/api/home_suivi_elec",
                "available_views": [
                    "sensors", "data", "diagnostics", "config"
                ]
            }
            
            return self._success({
                "ui_info": ui_info,
                "type": "ui"
            })
            
        except Exception as e:
            _LOGGER.exception(f"Erreur _handle_ui: {e}")
            return self._error(500, f"Erreur UI: {e}")
    
    # === MÉTHODES UTILITAIRES ===
    
    async def _load_sensors_data(self):
        """Charge capteurs_power.json de manière asynchrone"""
        import asyncio
        
        def _load_file():
            file_path = self._get_sensors_file_path()
            if not os.path.exists(file_path):
                return []
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                _LOGGER.error(f"Erreur lecture {file_path}: {e}")
                return []
        
        return await asyncio.get_event_loop().run_in_executor(None, _load_file)
    
    async def _load_selection_data(self):
        """Charge capteurs_selection.json de manière asynchrone"""
        import asyncio
        
        def _load_file():
            file_path = self._get_selection_file_path()
            if not os.path.exists(file_path):
                return {}
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                _LOGGER.error(f"Erreur lecture {file_path}: {e}")
                return {}
        
        return await asyncio.get_event_loop().run_in_executor(None, _load_file)
    
    def _get_hse_energy_sensors(self):
        """Récupère tous les capteurs HSE energy depuis les états HA (aligné Phase 2)"""
        all_states = self.hass.states.async_all("sensor")
        # Inclure sensor.hse_*_{cycle} (today_energy) ET sensor.hse_energy_*_{cycle}
        cycles = ("_hourly", "_daily", "_weekly", "_monthly", "_yearly")
        return [
            s for s in all_states
            if s.entity_id.startswith("sensor.hse_") and s.entity_id.endswith(cycles)
        ]
    
    def _get_sensors_file_path(self):
        """Chemin vers capteurs_power.json"""
        return os.path.join(
            os.path.dirname(__file__), "..", "data", "capteurs_power.json"
        )
    
    def _get_selection_file_path(self):
        """Chemin vers capteurs_selection.json"""
        return os.path.join(
            os.path.dirname(__file__), "..", "data", "capteurs_selection.json"
        )
    
    def _extract_cycle_from_entity(self, entity_id):
        """Extrait le cycle depuis l'entity_id (Phase 2: cycles complets)"""
        for c in ("hourly", "daily", "weekly", "monthly", "yearly"):
            if entity_id.endswith("_" + c):
                return c
        return "unknown"
    
    def _get_timestamp(self):
        """Timestamp ISO actuel"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _get_last_detection_time(self):
        """Dernière fois que la détection a été exécutée"""
        # Pour l'instant, timestamp actuel - sera amélioré plus tard
        return self._get_timestamp()
    
    def _success(self, data):
        """Réponse succès avec données"""
        return web.json_response({"error": False, "data": data})
    
    def _error(self, status, message):
        """Réponse erreur avec statut"""
        return web.json_response({"error": True, "message": message}, status=status)
    
    async def handle_sensors_health(self):
        """Endpoint get_sensors_health - Diagnostic capteurs pour capteursSensor.js."""
        try:
            # Réutiliser logique sensors existante
            sensors_data = await self._load_sensors_data()
            selection_data = await self._load_selection_data()
            
            # Index de sélection
            selection_index = {}
            for category, items in selection_data.items():
                if isinstance(items, list):
                    for item in items:
                        entity_id = item.get("entity_id")
                        if entity_id:
                            selection_index[entity_id] = item.get("enabled", False)
            
            # Format spécial pour diagnostic capteursSensor.js
            sensors_health = {}
            
            for sensor in sensors_data:
                entity_id = sensor.get("entity_id")
                if entity_id:
                    state_obj = self.hass.states.get(entity_id)
                    
                    # Calcul état santé selon logique capteursSensor.js
                    health_state = "absent"
                    if state_obj:
                        if state_obj.state in ["unavailable", "unknown", "error", "none"]:
                            health_state = "ko"
                        else:
                            health_state = "ok"
                    
                    # Format exact attendu par capteursSensor.js
                    sensors_health[entity_id] = {
                        "friendly_name": state_obj.attributes.get("friendly_name", entity_id) if state_obj else entity_id,
                        "value": state_obj.state if state_obj else "N/A",
                        "state": health_state,
                        "unit_of_measurement": state_obj.attributes.get("unit_of_measurement", "") if state_obj else "",
                        "integration": sensor.get("integration", "unknown"),
                        "quarantine": sensor.get("quarantine", False),
                        "last_seen": state_obj.last_changed.isoformat() if state_obj else None,
                        "device_id": sensor.get("device_id", ""),
                        "area": sensor.get("zone", ""),
                        "duplicate_group": sensor.get("duplicate_group", "")
                    }
            
            _LOGGER.info(f"🩺 Sensors health: {len(sensors_health)} capteurs analysés")
            
            # ✅ Format SUCCESS pour capteursSensor.js (pas self.success !)
            return web.json_response({
                "success": True,
                "sensors": sensors_health,
                "count": len(sensors_health)
            })
            
        except Exception as e:
            _LOGGER.exception(f"Erreur handle_sensors_health: {e}")
            
    async def _handle_integrations_status(self):
        """Endpoint /get_integrations_status - État des intégrations HA"""
        try:
            _LOGGER.info("🔍 Analyse des intégrations depuis états HA")
            
            # 1. Récupérer toutes les intégrations depuis HA
            integrations_data = []
            
            # Analyse basée sur les domaines d'entités
            all_states = self.hass.states.async_all()
            domain_stats = {}
            
            # Grouper par domaine (intégration)
            for state in all_states:
                domain = state.entity_id.split('.')[0]
                
                if domain not in domain_stats:
                    domain_stats[domain] = {
                        'domain': domain,
                        'entities_total': 0,
                        'entities_ok': 0,
                        'entities_unavailable': 0,
                        'last_updated': None
                    }
                
                domain_stats[domain]['entities_total'] += 1
                
                if state.state in ('unavailable', 'unknown'):
                    domain_stats[domain]['entities_unavailable'] += 1
                else:
                    domain_stats[domain]['entities_ok'] += 1
                
                # Dernière mise à jour
                if not domain_stats[domain]['last_updated'] or state.last_updated > domain_stats[domain]['last_updated']:
                    domain_stats[domain]['last_updated'] = state.last_updated
            
            # 2. Transformer en format pour frontend
            for domain, stats in domain_stats.items():
                # Filtrer les domaines système et peu utiles
                if domain in ('homeassistant', 'persistent_notification', 'updater'):
                    continue
                
                unavailable_ratio = stats['entities_unavailable'] / stats['entities_total'] if stats['entities_total'] > 0 else 0
                
                # Déterminer l'état de santé
                if unavailable_ratio > 0.3:  # >30% indisponible
                    health_state = 'critical'
                    status_text = 'Défaillante'
                elif unavailable_ratio > 0.1:  # 10-30% indisponible  
                    health_state = 'warning'
                    status_text = 'Attention'
                else:
                    health_state = 'ok'
                    status_text = 'Opérationnelle'
                
                integrations_data.append({
                    'domain': domain,
                    'friendly_name': domain.replace('_', ' ').title(),
                    'status': status_text,
                    'health_state': health_state,
                    'entities_count': stats['entities_total'],
                    'entities_ok': stats['entities_ok'],
                    'entities_unavailable': stats['entities_unavailable'],
                    'last_updated': stats['last_updated'].isoformat() if stats['last_updated'] else None,
                    'unavailable_ratio': round(unavailable_ratio * 100, 1)
                })
            
            # 3. Trier par nombre d'entités (plus importantes en premier)
            integrations_data.sort(key=lambda x: x['entities_count'], reverse=True)
            
            _LOGGER.info(f"✅ Analysé {len(integrations_data)} intégrations")
            
            return self._success({
                'integrations': integrations_data,
                'count': len(integrations_data),
                'summary': {
                    'total': len(integrations_data),
                    'ok': len([i for i in integrations_data if i['health_state'] == 'ok']),
                    'warning': len([i for i in integrations_data if i['health_state'] == 'warning']),
                    'critical': len([i for i in integrations_data if i['health_state'] == 'critical'])
                }
            })

        except Exception as e:
            _LOGGER.exception(f"Erreur _handle_integrations_status: {e}")
            return self._error(500, f"Erreur analyse intégrations: {e}")

    async def _handle_logs(self):
        """Endpoint /get_logs - Logs en temps réel avec filtrage et synthèse"""
        try:
            # ✅ 1. Récupérer tous les loggers et leurs handlers
            import logging
            
            log_records = []
            error_patterns = {}
            module_stats = {}
            
            # ✅ 2. Accéder au root logger et tous ses handlers
            root_logger = logging.getLogger()
            
            # Parcourir tous les loggers enregistrés
            for logger_name in logging.Logger.manager.loggerDict:
                logger = logging.getLogger(logger_name)
                
                # Pour chaque handler du logger
                for handler in logger.handlers:
                    # Si c'est un handler MemoryHandler ou buffer (in-memory)
                    if hasattr(handler, 'buffer') and handler.buffer:
                        for record in handler.buffer:
                            log_entry = self._format_log_record(record, logger_name)
                            log_records.append(log_entry)
                            
                            # Statistiques par module
                            module = logger_name.split('.')[0] if '.' in logger_name else logger_name
                            if module not in module_stats:
                                module_stats[module] = {"total": 0, "errors": 0, "warnings": 0}
                            module_stats[module]["total"] += 1
                            if record.levelno >= logging.ERROR:
                                module_stats[module]["errors"] += 1
                                # Détecter patterns d'erreurs
                                error_key = f"{module}:{record.msg[:50]}"
                                error_patterns[error_key] = error_patterns.get(error_key, 0) + 1
                            elif record.levelno >= logging.WARNING:
                                module_stats[module]["warnings"] += 1
            
            # ✅ 3. Fallback : si pas de MemoryHandler, créer capture temporaire
            if not log_records:
                # Créer un handler temporaire pour capturer les logs
                temp_handler = logging.handlers.MemoryHandler(capacity=500)
                root_logger.addHandler(temp_handler)
                
                # Attendre un peu pour capturer les logs
                import asyncio
                await asyncio.sleep(0.1)
                
                for record in temp_handler.buffer:
                    log_entry = self._format_log_record(record, "root")
                    log_records.append(log_entry)
                
                root_logger.removeHandler(temp_handler)
            
            # ✅ 4. Trier par timestamp (plus récent en premier)
            log_records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # ✅ 5. Filtrer les logs critiques (ERROR + WARNING)
            critical_logs = [
                log for log in log_records 
                if log.get("level") in ["ERROR", "CRITICAL"]
            ][:20]  # Top 20 erreurs
            
            # ✅ 6. Créer synthèse
            synthesis = {
                "total_logs": len(log_records),
                "error_count": len([l for l in log_records if l.get("level") == "ERROR"]),
                "warning_count": len([l for l in log_records if l.get("level") == "WARNING"]),
                "top_error_patterns": sorted(
                    error_patterns.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5],
                "module_statistics": module_stats,
                "health_status": "critical" if len(critical_logs) > 10 else "degraded" if len(critical_logs) > 0 else "healthy"
            }
            
            _LOGGER.info(f"📋 Logs synthèse: {len(log_records)} logs, {synthesis['error_count']} erreurs, {synthesis['warning_count']} avertissements")
            
            return self._success({
                "logs": log_records[-100:],  # Derniers 100 logs
                "critical_logs": critical_logs,
                "synthesis": synthesis,
                "type": "logs",
                "timestamp": self._get_timestamp(),
                "source": "python_logging_system_realtime"
            })
            
        except Exception as e:
            _LOGGER.exception(f"Erreur _handle_logs: {e}")
            return self._error(500, f"Erreur chargement logs: {e}")
    
    def _format_log_record(self, record, logger_name):
        """Formate un LogRecord en dictionnaire"""
        try:
            return {
                "timestamp": record.created,
                "level": record.levelname,
                "logger": logger_name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
        except Exception as e:
            return {
                "timestamp": record.created,
                "level": "UNKNOWN",
                "logger": logger_name,
                "message": str(e),
                "module": "error_formatting",
                "function": "unknown",
                "line": 0
            }

    async def handle_sensor_mapping(self):
        """
        Endpoint sensor_mapping - Mapping sensors source → HSE energy cycles
        
        Retourne pour chaque sensor source:
        {
          "sensor.source_1": {
            "hourly": 0.0,
            "hourly_entity": "sensor.hse_source_1_energy_hourly",
            "daily": 1.234,
            "daily_entity": "sensor.hse_source_1_energy_daily",
            ...
          }
        }
        """
        try:
            _LOGGER.info('[API-MAPPING] Récupération mapping sensors source → HSE')
            
            # 1. Récupérer tous sensors HSE energy
            hse_sensors = {}
            for state in self.hass.states.async_all("sensor"):
                entity_id = state.entity_id
                if entity_id.startswith('sensor.hse_') and '_energy_' in entity_id:
                    hse_sensors[entity_id] = state
            
            _LOGGER.info(f'[API-MAPPING] {len(hse_sensors)} sensors HSE trouvés')
            
            # 2. Grouper par source_entity
            sources = {}
            for entity_id, state in hse_sensors.items():
                source_entity = state.attributes.get('source_entity')
                cycle = state.attributes.get('cycle')
                
                if source_entity and cycle:
                    if source_entity not in sources:
                        sources[source_entity] = {}
                    
                    # Stocker state + metadata
                    sources[source_entity][cycle] = {
                        'entity_id': entity_id,
                        'state': state.state,
                        'unit': state.attributes.get('unit_of_measurement'),
                        'cycle_start': state.attributes.get('cycle_start'),
                        'last_power_w': state.attributes.get('last_power_w')
                    }
            
            _LOGGER.info(f'[API-MAPPING] {len(sources)} sources mappées')
            
            # 3. Format final pour frontend
            mapping = {}
            for source, cycles in sources.items():
                mapping[source] = {}
                
                for cycle, data in cycles.items():
                    # Entity ID HSE
                    mapping[source][f'{cycle}_entity'] = data['entity_id']
                    
                    # Valeur float pour calculs
                    try:
                        mapping[source][cycle] = float(data['state'])
                    except (ValueError, TypeError):
                        mapping[source][cycle] = 0.0
                    
                    # Métadonnées optionnelles
                    mapping[source][f'{cycle}_unit'] = data['unit']
                    mapping[source][f'{cycle}_last_power'] = data['last_power_w']
            
            _LOGGER.info(f'[API-MAPPING] ✅ Mapping généré pour {len(mapping)} sources')
            
            return self._success({
                'mapping': mapping,
                'total_sources': len(sources),
                'total_hse_sensors': len(hse_sensors),
                'type': 'sensor_mapping',
                'timestamp': self._get_timestamp()
            })
            
        except Exception as e:
            _LOGGER.exception(f'[API-MAPPING] ❌ Erreur: {e}')
            return self._error(500, f'Erreur mapping sensors: {e}')

    async def _handle_backend_health(self):
        """Endpoint /get_backend_health - Métriques santé backend pour UI Diagnostics."""
        try:
            import time
            from datetime import datetime

            # Uptime basé sur un timestamp stocké en mémoire HA
            start_time = self.hass.data.get("home_suivi_elec_start_time")
            if not start_time:
                start_time = datetime.now()
                self.hass.data["home_suivi_elec_start_time"] = start_time

            uptime_seconds = (datetime.now() - start_time).total_seconds()

            # Compteur de requêtes simple (optionnel, pour illustrer)
            req_count = self.hass.data.get("home_suivi_elec_request_count", 0) + 1
            self.hass.data["home_suivi_elec_request_count"] = req_count

            health_data = {
                "uptime": int(uptime_seconds),
                "uptime_percent": 99.5,           # Valeur fictive pour l’instant
                "requests_per_hour": 120,         # À raffiner plus tard
                "errors_per_hour": 0,
                "avg_latency": 45,                # ms (simulé)
                "memory_used": 52_428_800,        # ~50 Mo (simulé)
                "memory_percent": 12.0,
                "version": "unified-v1.0.42-final",
                "start_time": start_time.isoformat(),
                "last_request": datetime.now().isoformat(),
                "total_requests": req_count,
                "total_errors": 0,
                "success_rate": 99.8,
            }

            _LOGGER.info("🩺 Backend health généré")
            return web.json_response({
                "success": True,
                "health": health_data,
            })

        except Exception as e:
            _LOGGER.exception(f"Erreur _handle_backend_health: {e}")
            return self._error(500, f"Erreur santé backend: {e}")

    async def _handle_migration(self, request):
        """Endpoint /migration - export YAML (utility_meter, templates, cost)."""
        try:
            kind = (request.query.get("type", "utility_meter") or "utility_meter").lower()
            preview = request.query.get("preview", "0") in ("1", "true", "True")

            export_service = ExportService(self.hass)

            if kind == "utility_meter":
                yaml_str = await export_service.generate_utility_meter_yaml()
                filename = "utility_meter.yaml"
            elif kind == "templates":
                yaml_str = await export_service.generate_template_sensors_yaml()
                filename = "template_sensors.yaml"
            elif kind == "cost":
                yaml_str = await export_service.generate_cost_sensors_yaml()
                filename = "cost_sensors.yaml"
            else:
                return self._error(400, f"type inconnu pour migration: {kind}")

            # Mode "preview" : juste le YAML brut, sans Content-Disposition
            if preview:
                return web.Response(
                    text=yaml_str,
                    content_type="text/yaml",
                )

            # Mode "download" : header Content-Disposition
            return web.Response(
                text=yaml_str,
                content_type="text/yaml",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        except Exception as e:
            _LOGGER.exception(f"Erreur _handle_migration: {e}")
            return self._error(500, f"Erreur migration: {e}")


    async def _handle_cache_stats(self):
        """Endpoint /cache/stats - Statistiques du cache"""
        try:
            cache = get_cache_manager()    
            stats = cache.get_stats()
            
            _LOGGER.info(f"[cache] Stats: {stats['total_entries']} entrées, {stats['memory_kb']:.1f} KB")
            
            return self._success({
                "stats": stats,
                "type": "cache_stats",
                "timestamp": self._get_timestamp()
            })
        except Exception as e:
            _LOGGER.exception(f"Erreur _handle_cache_stats: {e}")
            return self._error(500, f"Erreur stats cache: {e}")


    async def _handle_groups(self):
        try:
            from ..storage_manager import StorageManager
            from ..const import DOMAIN

            _LOGGER.debug("[get_groups] Début handler")

            data = self.hass.data.get(DOMAIN, {})
            mgr = data.get("storage_manager")
            _LOGGER.debug("[get_groups] mgr in hass.data: %r", type(mgr))

            if not isinstance(mgr, StorageManager):
                _LOGGER.debug("[get_groups] mgr pas StorageManager, on instancie")
                mgr = StorageManager(self.hass)

            groups = await mgr.get_sensor_groups()
            _LOGGER.debug("[get_groups] groups chargés: type=%s, len=%s",
                        type(groups), len(groups) if isinstance(groups, dict) else "n/a")

            if groups is None or not isinstance(groups, dict):
                _LOGGER.warning("[get_groups] format inattendu, fallback {}: %r", groups)
                groups = {}

            return self._success({
                "groups": groups,
                "count": len(groups),
                "type": "sensor_groups",
            })

        except Exception as e:
            _LOGGER.exception("Erreur _handle_groups: %s", e)
            return self._error(500, f"Erreur chargement groupes: {e}")


    async def _handle_summary_metrics(self, request):
        """Endpoint /summary_metrics - métriques internal/external/delta avec cache."""
        try:
            data = await request.json() if request.can_read_body else {}
            # entity_ids internes
            internal_ids = data.get("internal_ids") or []
            # capteur externe (kWh déjà agrégé)
            external_entity = data.get("external_entity")
            # période demandée: hourly/daily/weekly/monthly/yearly
            period = data.get("period", "daily")

            # Profil tarifaire depuis les options déjà stockées
            options = self.hass.data.get("home_suivi_elec", {}).get("options", {}) or {}
            profile = PricingProfile({
                "type_contrat": options.get("type_contrat", "fixe"),
                "prix_ht": options.get("prix_ht") or options.get("prixht") or 0,
                "prix_ttc": options.get("prix_ttc") or options.get("prixttc") or 0,
                "abonnement_ht": options.get("abonnement_ht") or options.get("abonnementht") or 0,
                "abonnement_ttc": options.get("abonnement_ttc") or options.get("abonnementttc") or 0,
            })

            engine = CalculationEngine(self.hass)

            # INTERNAL
            internal = await engine.get_group_metrics(
                "internal", period, profile, internal_ids
            )

            # EXTERNAL (si capteur défini)
            external = None
            if external_entity:
                external = await engine.get_group_metrics(
                    "external", period, profile, [external_entity]
                )

            # DELTA (external - internal) dérivé
            delta = None
            if external:
                delta = {
                    "energy_kwh": round(external["energy_kwh"] - internal["energy_kwh"], 3),
                    "cost_ht": round(external["cost_ht"] - internal["cost_ht"], 2),
                    "cost_ttc": round(external["cost_ttc"] - internal["cost_ttc"], 2),
                    "total_ht": round(external["total_ht"] - internal["total_ht"], 2),
                    "total_ttc": round(external["total_ttc"] - internal["total_ttc"], 2),
                    "timestamp": internal["timestamp"],
                    "from_cache": internal["from_cache"] and external["from_cache"],
                    "cached_age": min(internal["cached_age"], external["cached_age"]),
                }

            return self._success({
                "internal": internal,
                "external": external,
                "delta": delta,
                "period": period,
            })

        except Exception as e:
            _LOGGER.exception("[SUMMARY-METRICS] Erreur: %s", e)
            return self._error(500, f"Erreur summary metrics: {e}")
