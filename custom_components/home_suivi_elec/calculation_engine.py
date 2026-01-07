# -*- coding: utf-8 -*-
"""
Moteur de calcul centralisé pour métriques énergie/coûts
Réutilisable par Summary, Scénarios, Génération de cartes
Phase 2 - Backend calculation engine + Cache unifié
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class PricingProfile:
    """Profil tarifaire réutilisable avec support HP/HC"""

    def __init__(self, config: dict):
        """
        Initialise un profil tarifaire.

        Args:
            config: {
                "type_contrat": "prix_unique" | "heures_creuses",
                "prix_ht": 0.2516,
                "prix_ttc": 0.276,
                "abonnement_ht": 12.44,
                "abonnement_ttc": 13.48,
                "hp": { ... },  # utilisé si heures_creuses
                "hc": { ... }
            }
        """
        raw = str(config.get("type_contrat", "prix_unique")).strip().lower()

        if raw in ("hp-hc", "hphc", "heurescreuses", "heures_creuses"):
            self.type_contrat = "heures_creuses"
        elif raw in ("fixe", "prixunique", "prix_unique"):
            self.type_contrat = "prix_unique"
        else:
            # fallback safe
            self.type_contrat = "prix_unique"

        self.prix_ht = float(config.get("prix_ht", 0))
        self.prix_ttc = float(config.get("prix_ttc", 0))
        self.abonnement_ht = float(config.get("abonnement_ht", 0))
        self.abonnement_ttc = float(config.get("abonnement_ttc", 0))

        # HP/HC (utilisés seulement si type_contrat == "heures_creuses")
        self.hp_config = config.get("hp", {})
        self.hc_config = config.get("hc", {})
        self.hp_start = self.hp_config.get("debut", "06:00")
        self.hp_end = self.hp_config.get("fin", "22:00")

        _LOGGER.debug(
            "[PRICING] Profile créé: %s, HT=%.4f, TTC=%.4f",
            self.type_contrat,
            self.prix_ht,
            self.prix_ttc,
        )

    def is_hp(self, timestamp: datetime) -> bool:
        """
        Vérifie si timestamp est en heures pleines

        Args:
            timestamp: datetime à vérifier

        Returns:
            True si HP, False si HC (ou True si tarif fixe)
        """
        if self.type_contrat != "heures_creuses":
            return True  # Tarif unique = toujours considéré HP

        start = datetime.strptime(self.hp_start, "%H:%M").time()
        end = datetime.strptime(self.hp_end, "%H:%M").time()
        current = timestamp.time()

        # Gestion chevauchement minuit (ex: 22:00 → 06:00)
        if start < end:
            return start <= current < end
        return current >= start or current < end

    def get_tarif_kwh(self, is_hp: bool) -> Tuple[float, float]:
        """
        Retourne les tarifs HT/TTC selon type_contrat prix_unique | heures_creuses
        """
        # Tarif unique
        if self.type_contrat == "prix_unique":
            return self.prix_ht, self.prix_ttc

        # Heures pleines / creuses
        if self.type_contrat == "heures_creuses":
            if is_hp:
                return (
                    float(self.hp_config.get("prix_ht", self.prix_ht)),
                    float(self.hp_config.get("prix_ttc", self.prix_ttc)),
                )
            return (
                float(self.hc_config.get("prix_ht", self.prix_ht)),
                float(self.hc_config.get("prix_ttc", self.prix_ttc)),
            )

        # Sécurité si type invalide: on ne casse pas le calcul
        return self.prix_ht, self.prix_ttc


class CalculationEngine:
    """Moteur de calcul centralisé pour métriques énergie/coûts"""

    def __init__(self, hass: HomeAssistant):
        """
        Initialise le moteur de calcul

        Args:
            hass: Instance Home Assistant
        """
        self.hass = hass
        _LOGGER.info("[CALC-ENGINE] Moteur de calcul initialisé")

    async def get_group_metrics(
        self,
        group_key: str,
        period: str,
        pricing_profile: PricingProfile,
        entity_ids: List[str],
    ) -> Dict:
        """
        Calcule les métriques agrégées pour un groupe de capteurs

        Args:
            group_key: Identifiant du groupe (ex: "salon", "internal", "external")
            period: Période ("hourly", "daily", "weekly", "monthly", "yearly")
            pricing_profile: Profil tarifaire à appliquer
            entity_ids: Liste des entity_id des capteurs sources

        Returns:
            {
                "energy_kwh": float,     # Consommation en kWh
                "cost_ht": float,        # Coût HT hors abonnement
                "cost_ttc": float,       # Coût TTC hors abonnement
                "total_ht": float,       # Total HT avec abonnement proratisé
                "total_ttc": float,      # Total TTC avec abonnement proratisé
                "timestamp": str,        # ISO 8601
                "from_cache": bool,      # True si données en cache
                "cached_age": float      # Âge en secondes (si from_cache=True)
            }
        """
        # ✨ Utiliser le CacheManager centralisé
        pricing_config = {
            "type_contrat": pricing_profile.type_contrat,
            "prix_ht": pricing_profile.prix_ht,
            "prix_ttc": pricing_profile.prix_ttc,
            "abonnement_ht": pricing_profile.abonnement_ht,
            "abonnement_ttc": pricing_profile.abonnement_ttc,
            "hp": pricing_profile.hp_config,
            "hc": pricing_profile.hc_config,
        }

        try:
            from .cache_manager import get_cache_manager

            cache = get_cache_manager()

            cached_result = cache.get(entity_ids, period, pricing_config)
            if cached_result is not None:
                # S'assurer que les flags sont bien présents
                cached_result.setdefault("from_cache", True)
                cached_result.setdefault("cached_age", 0.0)

                _LOGGER.debug(
                    "[CALC-ENGINE] ⚡ Cache HIT: %s/%s (age: %.1fs)",
                    group_key,
                    period,
                    float(cached_result.get("cached_age", 0.0)),
                )
                return cached_result

        except Exception as e:
            _LOGGER.warning("[CALC-ENGINE] Cache non disponible: %s", e)

        # 🔹 Cache MISS → calculer
        _LOGGER.debug(
            "[CALC-ENGINE] 🔍 Calcul %s/%s pour %d capteurs",
            group_key,
            period,
            len(entity_ids),
        )

        # Récupérer consommations depuis sensor_mapping
        total_kwh = 0.0
        sensor_mapping = await self._get_sensor_mapping()

        # Agréger les kWh de tous les capteurs du groupe
        for entity_id in entity_ids:
            sensor_data = sensor_mapping.get(entity_id, {})
            value = sensor_data.get(period, 0)

            if isinstance(value, (int, float)) and value > 0:
                total_kwh += value
                _LOGGER.debug("  └─ %s: %.3f kWh", entity_id, value)
            elif isinstance(value, (int, float)) and value < 0:
                _LOGGER.warning(
                    "  └─ %s: valeur négative ignorée (%.3f kWh)", entity_id, value
                )

        # Calculs coûts
        timestamp = datetime.now()
        is_hp = pricing_profile.is_hp(timestamp)
        prix_ht, prix_ttc = pricing_profile.get_tarif_kwh(is_hp)

        cost_ht = round(total_kwh * prix_ht, 2)
        cost_ttc = round(total_kwh * prix_ttc, 2)

        # Abonnement proratisé selon période
        abonnement_ht = self._get_abonnement_prorate(
            pricing_profile.abonnement_ht, period
        )
        abonnement_ttc = self._get_abonnement_prorate(
            pricing_profile.abonnement_ttc, period
        )

        result = {
            "energy_kwh": round(total_kwh, 3),
            "cost_ht": cost_ht,
            "cost_ttc": cost_ttc,
            "total_ht": round(cost_ht + abonnement_ht, 2),
            "total_ttc": round(cost_ttc + abonnement_ttc, 2),
            "timestamp": timestamp.isoformat(),
            "from_cache": False,
            "cached_age": 0.0,
        }

        # ✨ Mise en cache via CacheManager
        try:
            from .cache_manager import get_cache_manager

            cache = get_cache_manager()
            cache.set(entity_ids, period, pricing_config, result)
            _LOGGER.debug("[CALC-ENGINE] ✅ Résultat mis en cache")
        except Exception as e:
            _LOGGER.warning("[CALC-ENGINE] Impossible de cacher: %s", e)

        _LOGGER.info(
            "[CALC-ENGINE] ✅ %s/%s: %.3f kWh → %.2f€ TTC",
            group_key,
            period,
            total_kwh,
            result["total_ttc"],
        )

        return result

    def _get_abonnement_prorate(self, abonnement_mensuel: float, period: str) -> float:
        """
        Proratise l'abonnement mensuel selon la période ÉCOULÉE (pas de projection!)
        
        Args:
            abonnement_mensuel: Abonnement mensuel en €
            period: Période de proratisation
            
        Returns:
            Montant proratisé en € pour la période écoulée uniquement
        """
        now = datetime.now()
        
        if period == "hourly":
            # 1 heure sur ~720h/mois
            return round(abonnement_mensuel / (30 * 24), 2)
        
        elif period == "daily":
            # 1 jour sur 30 jours
            return round(abonnement_mensuel / 30, 2)
        
        elif period == "weekly":
            # Jours écoulés depuis lundi 00:00
            jour_semaine = now.weekday()  # 0=lundi, 6=dimanche
            jours_ecoules = jour_semaine + 1
            
            abonnement_journalier = abonnement_mensuel / 30
            return round(abonnement_journalier * jours_ecoules, 2)
        
        elif period == "monthly":
            # Jours écoulés depuis le 1er à 00:00
            jour_du_mois = now.day
            
            abonnement_journalier = abonnement_mensuel / 30
            return round(abonnement_journalier * jour_du_mois, 2)
        
        elif period == "yearly":
            # Jours écoulés depuis le 1er janvier
            jour_annee = now.timetuple().tm_yday
            
            abonnement_annuel = abonnement_mensuel * 12
            annee = now.year
            est_bissextile = (annee % 4 == 0 and annee % 100 != 0) or (annee % 400 == 0)
            jours_dans_annee = 366 if est_bissextile else 365
            
            return round((abonnement_annuel / jours_dans_annee) * jour_annee, 2)
        
        # Fallback
        return round(abonnement_mensuel, 2)

    async def _get_sensor_mapping(self) -> Dict:
        """
        Récupère le mapping sensor_source → {period: kwh}
        Réutilise l'API unifiée existante

        Returns:
            {
                "sensor.source_1": {
                    "hourly": 0.5,
                    "daily": 12.3,
                    "monthly": 370.0,
                    ...
                },
                ...
            }
        """
        try:
            # Récupérer directement depuis les états HSE
            mapping: Dict[str, Dict[str, float]] = {}
            all_states = self.hass.states.async_all("sensor")

            hse_sensors = [
                s
                for s in all_states
                if s.entity_id.startswith("sensor.hse_")
                and (
                    "_energy_" in s.entity_id
                    or s.entity_id.endswith(
                        ("_hourly", "_daily", "_weekly", "_monthly", "_yearly")
                    )
                )
            ]

            _LOGGER.debug(
                "[CALC-ENGINE] 📊 %d sensors HSE trouvés", len(hse_sensors)
            )

            # Grouper par source
            for state in hse_sensors:
                attrs = state.attributes or {}
                source_entity = attrs.get("source_entity")
                cycle = attrs.get("cycle")

                if not source_entity or not cycle:
                    continue

                if source_entity not in mapping:
                    mapping[source_entity] = {}

                # Convertir state en float
                try:
                    value = float(state.state)
                except (ValueError, TypeError):
                    value = 0.0

                mapping[source_entity][cycle] = value

            _LOGGER.debug(
                "[CALC-ENGINE] 📊 Mapping construit: %d sources", len(mapping)
            )

            return mapping

        except Exception as e:
            _LOGGER.exception(
                "[CALC-ENGINE] ❌ Erreur récupération mapping: %s", e
            )
            return {}
