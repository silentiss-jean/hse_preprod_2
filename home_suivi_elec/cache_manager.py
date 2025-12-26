"""
Gestionnaire de cache intelligent pour Home Suivi Élec
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, Tuple
from threading import Lock

_LOGGER = logging.getLogger(__name__)


class CacheManager:
    """Gestionnaire de cache avec TTL adaptatif"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        
        # Durées de cache par période (en secondes)
        self._ttl_config = {
            'hourly': 60,       # 1 min - données changent vite
            'daily': 300,       # 5 min - bon compromis
            'weekly': 600,      # 10 min - change peu
            'monthly': 1800,    # 30 min - très stable
            'yearly': 3600      # 1h - change rarement
        }
    
    def _generate_cache_key(
        self,
        entity_ids: list,
        period: str,
        pricing_config: dict,
        external_id: Optional[str] = None
    ) -> str:
        """Génère une clé de cache unique"""
        cache_data = {
            'entities': sorted(entity_ids),
            'period': period,
            'pricing': pricing_config,
            'external': external_id
        }
        
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def get(
        self,
        entity_ids: list,
        period: str,
        pricing_config: dict,
        external_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Récupère une entrée du cache si valide"""
        cache_key = self._generate_cache_key(
            entity_ids, period, pricing_config, external_id
        )
        
        with self._lock:
            if cache_key not in self._cache:
                _LOGGER.debug(f"[cache] MISS pour {period}")
                return None
            
            entry = self._cache[cache_key]
            cached_at = entry.get('cached_at')
            ttl = self._ttl_config.get(period, 300)
            
            age = (datetime.now() - cached_at).total_seconds()
            
            if age > ttl:
                _LOGGER.debug(
                    f"[cache] EXPIRED pour {period} "
                    f"(âge: {age:.1f}s, TTL: {ttl}s)"
                )
                del self._cache[cache_key]
                return None
            
            _LOGGER.debug(
                f"[cache] HIT pour {period} "
                f"(âge: {age:.1f}s, reste: {ttl - age:.1f}s)"
            )
            return entry['data']
    
    def set(
        self,
        entity_ids: list,
        period: str,
        pricing_config: dict,
        data: Dict[str, Any],
        external_id: Optional[str] = None
    ) -> None:
        """Stocke une entrée dans le cache"""
        cache_key = self._generate_cache_key(
            entity_ids, period, pricing_config, external_id
        )
        
        with self._lock:
            self._cache[cache_key] = {
                'data': data,
                'cached_at': datetime.now()
            }
            
            _LOGGER.debug(
                f"[cache] SET pour {period} "
                f"(TTL: {self._ttl_config.get(period, 300)}s)"
            )
    
    def invalidate_all(self) -> int:
        """Vide tout le cache"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            _LOGGER.info(f"[cache] 🗑️ Cache vidé ({count} entrées)")
            return count
    
    def invalidate_entity(self, entity_id: str) -> int:
        """Invalide toutes les entrées contenant un capteur"""
        with self._lock:
            keys_to_delete = []
            
            for key, entry in self._cache.items():
                # Reconstruire les entity_ids depuis les données
                data_str = json.dumps(entry['data'])
                if entity_id in data_str:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self._cache[key]
            
            _LOGGER.info(
                f"[cache] 🗑️ Invalidation partielle : "
                f"{entity_id} ({len(keys_to_delete)} entrées)"
            )
            return len(keys_to_delete)
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache"""
        with self._lock:
            now = datetime.now()
            entries_by_age = {
                'fresh': 0,  # < 1 min
                'valid': 0,  # 1-5 min
                'stale': 0   # > 5 min
            }

            for entry in self._cache.values():
                age = (now - entry['cached_at']).total_seconds()
                if age < 60:
                    entries_by_age['fresh'] += 1
                elif age < 300:
                    entries_by_age['valid'] += 1
                else:
                    entries_by_age['stale'] += 1

            # ⚠️ ICI : gérer datetime dans json.dumps
            try:
                raw = json.dumps(self._cache, default=str)
                memory_kb = len(raw) / 1024
            except Exception:
                memory_kb = 0.0

            return {
                'total_entries': len(self._cache),
                'entries_by_age': entries_by_age,
                'memory_kb': memory_kb,
            }


# Instance globale
_cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """Retourne l'instance du gestionnaire de cache"""
    return _cache_manager
