"""
Système de scoring de qualité pour les capteurs.
Aide à choisir automatiquement le meilleur capteur parmi plusieurs options.

⚠️  IMPORTANT : Les helpers (min_max, template, etc.) sont EXCLUS du calcul de coût.
"""
import logging
from typing import Dict, List, Any, Optional
from collections import defaultdict

_LOGGER = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# CONFIGURATION : INTÉGRATIONS EXCLUES DU CALCUL DE COÛT
# ════════════════════════════════════════════════════════════════════════════
# Ces intégrations sont des HELPERS/AGRÉGATIONS et ne doivent PAS être utilisées
# pour le calcul de coût. Elles servent uniquement pour l'affichage et les stats.

EXCLUDED_FROM_COST_CALCULATION = [
    'min_max',          # Agrégation min/max de plusieurs capteurs
    'statistics',       # Statistiques calculées
    'average',          # Moyennes calculées
    'template',         # Templates personnalisés
    'utility_meter',    # Découpage temporel (jour/semaine/mois)
    'integration',      # Helper d'intégration (cumul)
    'history_stats',    # Statistiques historiques
    'derivative',       # Dérivée (calcul de variation)
    'filter',           # Filtre de données
]


def is_physical_sensor(sensor: Dict[str, Any]) -> bool:
    """
    Vérifie si un capteur est PHYSIQUE (pas un helper/agrégation).
    
    Les capteurs physiques sont les SEULS valides pour le calcul de coût.
    Les helpers (min_max, template, etc.) sont EXCLUS.
    
    Args:
        sensor: Dictionnaire contenant les infos du capteur
        
    Returns:
        True si c'est un capteur physique, False si c'est un helper
        
    Examples:
        >>> is_physical_sensor({'integration': 'shelly'})
        True
        >>> is_physical_sensor({'integration': 'min_max'})
        False
    """
    integration = sensor.get('integration', '').lower()
    
    # Vérifier l'intégration
    if integration in EXCLUDED_FROM_COST_CALCULATION:
        _LOGGER.debug(f"Helper détecté (integration={integration}): {sensor.get('entity_id')}")
        return False
    
    # Vérifier l'entity_id (parfois les helpers n'ont pas d'intégration explicite)
    entity_id = sensor.get('entity_id', '').lower()
    if any(x in entity_id for x in ['_helper_', '_average_', '_total_', '_sum_', '_min_', '_max_']):
        _LOGGER.debug(f"Helper détecté (entity_id): {entity_id}")
        return False
    
    return True


def compute_sensor_score(sensor: Dict[str, Any]) -> int:
    """
    Calcule le score de qualité d'un capteur (0-150).
    
    ⚠️  IMPORTANT : Les helpers reçoivent un score réduit (max 50)
    pour éviter qu'ils soient sélectionnés automatiquement.
    
    Critères de notation :
    - Type de mesure : Energy (kWh) = 100 pts, Power (W) = 50 pts
    - State class : total = 20 pts, measurement = 10 pts
    - Qualité intégration : Premium = 15 pts
    - Physique vs virtuel : Non-virtuel = 10 pts
    - Disponibilité : Disponible = 5 pts
    
    Args:
        sensor: Dictionnaire avec métadonnées du capteur
        
    Returns:
        Score total (0-150 pour physiques, 0-50 pour helpers)
    """
    # 🚫 Si c'est un helper, score maximum de 50
    if not is_physical_sensor(sensor):
        base_score = _compute_base_score(sensor)
        reduced_score = min(50, base_score // 3)  # Divisé par 3, max 50
        _LOGGER.debug(
            f"Helper: {sensor.get('entity_id')} "
            f"(integration: {sensor.get('integration')}) "
            f"→ Score réduit: {reduced_score}/50"
        )
        return reduced_score
    
    # ✅ Calcul normal pour les capteurs physiques
    return _compute_base_score(sensor)


def _compute_base_score(sensor: Dict[str, Any]) -> int:
    """Calcul du score de base (logique existante)."""
    score = 0
    
    # 1️⃣ Type de mesure (PRIORITÉ MAXIMALE)
    unit = (sensor.get("unit") or sensor.get("unit_of_measurement") or "").lower()
    if unit in ("kwh", "wh"):
        score += 100  # ✅ Energy = mesure directe, plus précise
    elif unit in ("w", "watt", "watts"):
        score += 50   # ⚠️  Power = nécessite intégration, moins précis
    
    # 2️⃣ State class (fiabilité de la mesure)
    state_class = sensor.get("state_class", "").lower()
    if state_class == "total":
        score += 20  # Compteur cumulatif (optimal pour energy)
    elif state_class in ("measurement", "total_increasing"):
        score += 10  # Mesure instantanée
    
    # 3️⃣ Qualité de l'intégration
    if sensor.get("is_premium", False):
        score += 15  # Intégration officielle (Platinum/Gold)
    
    quality = sensor.get("quality_scale", "").lower()
    if quality in ("platinum", "gold"):
        score += 10
    elif quality == "silver":
        score += 5
    
    # 4️⃣ Physique vs virtuel
    if not sensor.get("is_virtual", False):
        score += 10  # Capteur physique réel
    
    # 5️⃣ Disponibilité actuelle
    state = sensor.get("state", "").lower()
    if state not in ("unavailable", "unknown", "none", ""):
        score += 5
    
    return score


def get_sensor_recommendation_label(score: int) -> str:
    """Retourne un label de recommandation basé sur le score."""
    if score >= 130:
        return "✅ EXCELLENT - Recommandé"
    elif score >= 100:
        return "✅ BON - Recommandé"
    elif score >= 70:
        return "⚠️  ACCEPTABLE"
    elif score >= 50:
        return "⚠️  HELPER - Pour statistiques uniquement"
    else:
        return "❌ FAIBLE - Non recommandé"


def get_sensor_stars(score: int) -> str:
    """Retourne une représentation en étoiles du score."""
    if score >= 130:
        return "⭐⭐⭐⭐"
    elif score >= 100:
        return "⭐⭐⭐"
    elif score >= 70:
        return "⭐⭐"
    elif score >= 50:
        return "⭐"
    else:
        return "☆"


def auto_select_best_sensors(sensors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sélectionne automatiquement les meilleurs capteurs par appareil.
    
    ⚠️  FILTRE : Garde UNIQUEMENT les capteurs physiques (helpers exclus).
    
    Logique :
    - Filtre les helpers (min_max, template, etc.)
    - Groupe les capteurs physiques par device_id
    - Pour chaque appareil, choisit le capteur avec le meilleur score
    - Si égalité, privilégie energy > power
    
    Args:
        sensors: Liste de capteurs détectés
        
    Returns:
        Liste des capteurs sélectionnés (1 par appareil, physiques uniquement)
    """
    # 🔍 Étape 1 : FILTRER les capteurs physiques uniquement
    physical_sensors = [s for s in sensors if is_physical_sensor(s)]
    helpers_excluded = len(sensors) - len(physical_sensors)
    
    _LOGGER.info(
        f"[AUTO_SELECT] Total: {len(sensors)} | "
        f"Physiques: {len(physical_sensors)} | "
        f"Helpers exclus: {helpers_excluded}"
    )
    
    # 🏗️  Étape 2 : Grouper par device_id
    by_device: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    for sensor in physical_sensors:
        device_id = sensor.get("device_id")
        if device_id:
            by_device[device_id].append(sensor)
    
    # 🎯 Étape 3 : Sélectionner le meilleur pour chaque appareil
    selected = []
    
    for device_id, device_sensors in by_device.items():
        if not device_sensors:
            continue
        
        # Calculer les scores
        scored = []
        for sensor in device_sensors:
            score = compute_sensor_score(sensor)
            scored.append((score, sensor))
        
        # Trier par score décroissant
        scored.sort(reverse=True, key=lambda x: x[0])
        
        # Prendre le meilleur
        best_score, best_sensor = scored[0]
        
        _LOGGER.debug(
            f"[AUTO_SELECT] Device {device_id}: "
            f"Choix de {best_sensor.get('entity_id')} "
            f"(score: {best_score})"
        )
        
        selected.append({
            **best_sensor,
            "enabled": True,
            "auto_selected": True,
            "quality_score": best_score,
            "recommendation": get_sensor_recommendation_label(best_score),
            "stars": get_sensor_stars(best_score)
        })
    
    # 📦 Étape 4 : Capteurs sans device_id (sélectionner ceux avec score > 70)
    orphans = [s for s in physical_sensors if not s.get("device_id")]
    for sensor in orphans:
        score = compute_sensor_score(sensor)
        if score >= 70:  # Seuil minimal
            selected.append({
                **sensor,
                "enabled": True,
                "auto_selected": True,
                "quality_score": score,
                "recommendation": get_sensor_recommendation_label(score),
                "stars": get_sensor_stars(score)
            })
    
    _LOGGER.info(
        f"[AUTO_SELECT] ✅ {len(selected)} capteurs physiques sélectionnés "
        f"({helpers_excluded} helpers exclus)"
    )
    
    return selected


def enrich_sensors_with_quality(sensors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enrichit une liste de capteurs avec leurs scores de qualité.
    
    Args:
        sensors: Liste de capteurs bruts
        
    Returns:
        Liste de capteurs enrichis avec quality_score, recommendation, stars
    """
    enriched = []
    
    for sensor in sensors:
        score = compute_sensor_score(sensor)
        
        enriched.append({
            **sensor,
            "quality_score": score,
            "recommendation": get_sensor_recommendation_label(score),
            "stars": get_sensor_stars(score),
            "is_helper": not is_physical_sensor(sensor)
        })
    
    return enriched
