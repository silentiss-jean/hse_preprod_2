"""
Module d'analyse des données d'énergie.
Détection d'anomalies, prédictions, comparaisons.
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.components.recorder import get_instance, history

_LOGGER = logging.getLogger(__name__)


async def detect_consumption_anomaly(
    hass: HomeAssistant, sensor_id: str, threshold_stddev: float = 2.0
) -> dict[str, Any]:
    """
    Détecte si la consommation actuelle est anormale.
    
    Args:
        sensor_id: ID du sensor à analyser
        threshold_stddev: Nombre d'écarts-types pour déclencher l'alerte
    
    Returns:
        Dict avec résultats de l'analyse
    """
    try:
        # Récupérer l'historique sur 30 jours
        end_time = datetime.now()
        start_time = end_time - timedelta(days=30)
        
        history_data = await hass.async_add_executor_job(
            history.state_changes_during_period,
            hass,
            start_time,
            end_time,
            sensor_id,
        )
        
        if not history_data or sensor_id not in history_data:
            return {"error": "Pas assez de données historiques"}
        
        # Extraire les valeurs
        values = []
        for state in history_data[sensor_id]:
            if state.state not in ("unknown", "unavailable"):
                try:
                    values.append(float(state.state))
                except (ValueError, TypeError):
                    continue
        
        if len(values) < 10:
            return {"error": "Pas assez de données valides"}
        
        # Calculer statistiques
        avg = statistics.mean(values)
        std_dev = statistics.stdev(values)
        
        # Valeur actuelle
        current_state = hass.states.get(sensor_id)
        if not current_state:
            return {"error": "Sensor non trouvé"}
        
        current_value = float(current_state.state)
        
        # Calculer la déviation
        deviation = abs(current_value - avg) / std_dev if std_dev > 0 else 0
        is_anomaly = deviation > threshold_stddev
        
        return {
            "sensor_id": sensor_id,
            "current_value": current_value,
            "average": round(avg, 2),
            "std_dev": round(std_dev, 2),
            "deviation": round(deviation, 2),
            "is_anomaly": is_anomaly,
            "threshold": threshold_stddev,
            "message": (
                f"⚠️ ANOMALIE DÉTECTÉE: {current_value:.2f} "
                f"(moyenne={avg:.2f}, écart={deviation:.1f}σ)"
                if is_anomaly
                else f"✅ Normal: {current_value:.2f} (moyenne={avg:.2f})"
            ),
        }
    
    except Exception as e:
        _LOGGER.error(f"❌ Erreur analyse anomalie {sensor_id}: {e}")
        return {"error": str(e)}


async def predict_monthly_consumption(
    hass: HomeAssistant, daily_sensor_id: str
) -> dict[str, Any]:
    """
    Prédit la consommation mensuelle basée sur la moyenne journalière.
    
    Args:
        daily_sensor_id: ID du sensor daily_energy
    
    Returns:
        Dict avec la prédiction
    """
    try:
        current_state = hass.states.get(daily_sensor_id)
        if not current_state:
            return {"error": "Sensor non trouvé"}
        
        # Récupérer l'historique du mois en cours
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        history_data = await hass.async_add_executor_job(
            history.state_changes_during_period,
            hass,
            start_of_month,
            now,
            daily_sensor_id,
        )
        
        if not history_data or daily_sensor_id not in history_data:
            return {"error": "Pas de données pour le mois en cours"}
        
        # Calculer moyenne journalière
        daily_values = []
        for state in history_data[daily_sensor_id]:
            if state.state not in ("unknown", "unavailable"):
                try:
                    daily_values.append(float(state.state))
                except (ValueError, TypeError):
                    continue
        
        if not daily_values:
            return {"error": "Pas de données valides"}
        
        avg_daily = statistics.mean(daily_values)
        
        # Calculer nombre de jours dans le mois
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        
        days_in_month = (next_month - start_of_month).days
        days_elapsed = (now - start_of_month).days + 1
        
        # Prédiction
        predicted_monthly = avg_daily * days_in_month
        current_monthly = avg_daily * days_elapsed
        
        return {
            "daily_sensor": daily_sensor_id,
            "avg_daily_kwh": round(avg_daily, 2),
            "days_elapsed": days_elapsed,
            "days_in_month": days_in_month,
            "current_monthly_kwh": round(current_monthly, 2),
            "predicted_monthly_kwh": round(predicted_monthly, 2),
            "message": (
                f"📊 Prédiction: {predicted_monthly:.2f} kWh ce mois "
                f"(basé sur {avg_daily:.2f} kWh/jour)"
            ),
        }
    
    except Exception as e:
        _LOGGER.error(f"❌ Erreur prédiction {daily_sensor_id}: {e}")
        return {"error": str(e)}


async def compare_yearly_consumption(
    hass: HomeAssistant, yearly_sensor_id: str
) -> dict[str, Any]:
    """
    Compare la consommation de l'année en cours avec l'année précédente.
    
    Args:
        yearly_sensor_id: ID du sensor yearly_energy
    
    Returns:
        Dict avec la comparaison
    """
    try:
        current_state = hass.states.get(yearly_sensor_id)
        if not current_state:
            return {"error": "Sensor non trouvé"}
        
        current_year_value = float(current_state.state)
        
        # Récupérer la valeur de l'année précédente (même date)
        now = datetime.now()
        last_year_date = now.replace(year=now.year - 1)
        
        history_data = await hass.async_add_executor_job(
            history.get_significant_states,
            hass,
            last_year_date - timedelta(days=1),
            last_year_date + timedelta(days=1),
            [yearly_sensor_id],
        )
        
        last_year_value = None
        if history_data and yearly_sensor_id in history_data:
            for state in history_data[yearly_sensor_id]:
                if state.state not in ("unknown", "unavailable"):
                    try:
                        last_year_value = float(state.state)
                        break
                    except (ValueError, TypeError):
                        continue
        
        if last_year_value is None:
            return {
                "current_year_kwh": round(current_year_value, 2),
                "last_year_kwh": None,
                "message": "📊 Pas de données pour l'année précédente",
            }
        
        # Calculer la différence
        diff = current_year_value - last_year_value
        diff_percent = (diff / last_year_value * 100) if last_year_value > 0 else 0
        
        return {
            "yearly_sensor": yearly_sensor_id,
            "current_year_kwh": round(current_year_value, 2),
            "last_year_kwh": round(last_year_value, 2),
            "difference_kwh": round(diff, 2),
            "difference_percent": round(diff_percent, 1),
            "trend": "📈 Hausse" if diff > 0 else "📉 Baisse",
            "message": (
                f"{'📈' if diff > 0 else '📉'} {abs(diff_percent):.1f}% "
                f"vs année précédente ({current_year_value:.2f} vs {last_year_value:.2f} kWh)"
            ),
        }
    
    except Exception as e:
        _LOGGER.error(f"❌ Erreur comparaison {yearly_sensor_id}: {e}")
        return {"error": str(e)}
