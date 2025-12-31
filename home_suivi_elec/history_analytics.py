# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class EntityComparison(TypedDict, total=False):
    entity_id: str
    display_name: str

    baseline_energy_kwh: float
    baseline_cost_ht: float
    baseline_cost_ttc: float
    baseline_energy_kwh_per_hour: float
    baseline_cost_ttc_per_hour: float
    baseline_energy_kwh_per_day: float
    baseline_cost_ttc_per_day: float

    event_energy_kwh: float
    event_cost_ht: float
    event_cost_ttc: float
    event_energy_kwh_per_hour: float
    event_cost_ttc_per_hour: float
    event_energy_kwh_per_day: float
    event_cost_ttc_per_day: float

    delta_energy_kwh: float
    delta_cost_ttc: float
    delta_energy_kwh_per_hour: float
    delta_cost_ttc_per_hour: float
    delta_energy_kwh_per_day: float
    delta_cost_ttc_per_day: float

    pct_energy_kwh: float
    pct_cost_ttc: float


def _to_datetime(ts: Any) -> datetime:
    """
    Convertit un timestamp (float epoch, int, ou datetime) en datetime aware.
    """
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    
    # fallback string ISO
    try:
        return dt_util.parse_datetime(str(ts))
    except Exception:
        raise ValueError(f"Cannot convert to datetime: {ts}")


async def fetch_statistics_hourly_sum(
    hass: HomeAssistant,
    statistic_ids: List[str],
    start: datetime,
    end: datetime,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Retourne les stats horaires pour chaque statistic_id, avec "sum" (cumul).
    Convertit tous les timestamps en datetime.
    """
    if not statistic_ids:
        return {}

    recorder_instance = get_instance(hass)
    if not recorder_instance:
        _LOGGER.error("[HISTORY] Recorder instance not available")
        return {}

    _LOGGER.info(
        "[HISTORY] Fetching statistics for %d entities from %s to %s",
        len(statistic_ids),
        start.isoformat(),
        end.isoformat(),
    )

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        start,
        end,
        statistic_ids,
        "hour",
        None,
        {"sum"},
    )

    # stats: {statistic_id: [{start, end, sum}, ...]}
    # Les timestamps sont des floats (epoch) => conversion nécessaire
    out: Dict[str, List[Dict[str, Any]]] = {}
    
    for sid, rows in (stats or {}).items():
        converted_rows = []
        for r in rows or []:
            try:
                start_dt = _to_datetime(r.get("start"))
                end_dt = _to_datetime(r.get("end"))
                sum_val = r.get("sum")
                
                converted_rows.append({
                    "start": start_dt,
                    "end": end_dt,
                    "sum": float(sum_val) if sum_val is not None else None,
                })
            except Exception as e:
                _LOGGER.warning("[HISTORY] Failed to convert timestamp for %s: %s", sid, e)
                continue
        
        out[sid] = converted_rows
    
    _LOGGER.info("[HISTORY] Fetched %d entities with statistics", len(out))
    return out


def compute_hourly_deltas_kwh(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transforme une série horaire de 'sum' en 'change_kwh' par différence.
    """
    out: List[Dict[str, Any]] = []
    prev: Optional[float] = None

    for r in rows or []:
        current_sum = r.get("sum")
        
        if current_sum is None:
            change = 0.0
        elif prev is None:
            # Première heure : pas de delta calculable
            change = 0.0
        else:
            change = float(current_sum) - float(prev)
            if change < 0:
                # Sécurité si reset/erreur (ex: compteur remis à zéro)
                _LOGGER.debug("[HISTORY] Negative change detected, resetting to 0")
                change = 0.0

        out.append({
            "start": r.get("start"),
            "end": r.get("end"),
            "change_kwh": float(change),
        })
        
        if current_sum is not None:
            prev = float(current_sum)

    return out


def compute_costs_per_hour(
    hourly_deltas: List[Dict[str, Any]],
    pricing_profile: Any,  # PricingProfile
) -> List[Dict[str, Any]]:
    """
    Applique HP/HC heure par heure.
    """
    out: List[Dict[str, Any]] = []
    
    for h in hourly_deltas or []:
        ts = h["start"]
        energy_kwh = float(h.get("change_kwh") or 0.0)

        # Vérifier que ts est bien un datetime
        if not isinstance(ts, datetime):
            _LOGGER.warning("[HISTORY] Invalid timestamp type: %s", type(ts))
            continue

        is_hp = pricing_profile.is_hp(ts)
        tarif_ht, tarif_ttc = pricing_profile.get_tarif_kwh(is_hp)

        cost_ht = energy_kwh * float(tarif_ht)
        cost_ttc = energy_kwh * float(tarif_ttc)

        out.append({
            "start": ts,
            "end": h["end"],
            "energy_kwh": round(energy_kwh, 3),
            "cost_ht": round(cost_ht, 4),
            "cost_ttc": round(cost_ttc, 4),
        })
    
    return out


def aggregate_period(
    hourly_costs: List[Dict[str, Any]],
    start: datetime,
    end: datetime,
) -> Dict[str, float]:
    """
    Agrège les coûts horaires sur une période donnée.
    """
    total_energy = 0.0
    total_ht = 0.0
    total_ttc = 0.0

    for h in hourly_costs or []:
        ts = h["start"]
        
        # Vérifier que ts est comparable avec start/end
        if not isinstance(ts, datetime):
            continue
            
        if start <= ts < end:
            total_energy += float(h.get("energy_kwh") or 0.0)
            total_ht += float(h.get("cost_ht") or 0.0)
            total_ttc += float(h.get("cost_ttc") or 0.0)

    return {
        "energy_kwh": round(total_energy, 3),
        "cost_ht": round(total_ht, 4),
        "cost_ttc": round(total_ttc, 4),
    }


def normalize_comparison(
    baseline: Dict[str, float],
    event: Dict[str, float],
    baseline_duration_s: float,
    event_duration_s: float,
) -> Dict[str, Any]:
    """
    Calcule les métriques normalisées (par heure et par jour).
    """
    baseline_h = baseline_duration_s / 3600.0 if baseline_duration_s > 0 else 0.0
    event_h = event_duration_s / 3600.0 if event_duration_s > 0 else 0.0
    baseline_d = baseline_duration_s / 86400.0 if baseline_duration_s > 0 else 0.0
    event_d = event_duration_s / 86400.0 if event_duration_s > 0 else 0.0

    def safe_div(a: float, b: float, ndigits: int) -> float:
        return round(a / b, ndigits) if b > 0 else 0.0

    delta_energy = float(event["energy_kwh"]) - float(baseline["energy_kwh"])
    delta_cost_ttc = float(event["cost_ttc"]) - float(baseline["cost_ttc"])

    baseline_kwh_h = safe_div(float(baseline["energy_kwh"]), baseline_h, 3)
    event_kwh_h = safe_div(float(event["energy_kwh"]), event_h, 3)
    baseline_cost_h = safe_div(float(baseline["cost_ttc"]), baseline_h, 4)
    event_cost_h = safe_div(float(event["cost_ttc"]), event_h, 4)

    baseline_kwh_d = safe_div(float(baseline["energy_kwh"]), baseline_d, 3)
    event_kwh_d = safe_div(float(event["energy_kwh"]), event_d, 3)
    baseline_cost_d = safe_div(float(baseline["cost_ttc"]), baseline_d, 4)
    event_cost_d = safe_div(float(event["cost_ttc"]), event_d, 4)

    pct_energy = (delta_energy / float(baseline["energy_kwh"]) * 100.0) if float(baseline["energy_kwh"]) > 0 else 0.0
    pct_cost = (delta_cost_ttc / float(baseline["cost_ttc"]) * 100.0) if float(baseline["cost_ttc"]) > 0 else 0.0

    return {
        "baseline_energy_kwh": baseline["energy_kwh"],
        "baseline_cost_ht": baseline["cost_ht"],
        "baseline_cost_ttc": baseline["cost_ttc"],
        "baseline_energy_kwh_per_hour": baseline_kwh_h,
        "baseline_cost_ttc_per_hour": baseline_cost_h,
        "baseline_energy_kwh_per_day": baseline_kwh_d,
        "baseline_cost_ttc_per_day": baseline_cost_d,

        "event_energy_kwh": event["energy_kwh"],
        "event_cost_ht": event["cost_ht"],
        "event_cost_ttc": event["cost_ttc"],
        "event_energy_kwh_per_hour": event_kwh_h,
        "event_cost_ttc_per_hour": event_cost_h,
        "event_energy_kwh_per_day": event_kwh_d,
        "event_cost_ttc_per_day": event_cost_d,

        "delta_energy_kwh": round(delta_energy, 3),
        "delta_cost_ttc": round(delta_cost_ttc, 4),
        "delta_energy_kwh_per_hour": round(event_kwh_h - baseline_kwh_h, 3),
        "delta_cost_ttc_per_hour": round(event_cost_h - baseline_cost_h, 4),
        "delta_energy_kwh_per_day": round(event_kwh_d - baseline_kwh_d, 3),
        "delta_cost_ttc_per_day": round(event_cost_d - baseline_cost_d, 4),

        "pct_energy_kwh": round(pct_energy, 1),
        "pct_cost_ttc": round(pct_cost, 1),
    }


def compute_top_entities(
    entity_comparisons: List[EntityComparison],
    sort_by: str,
    limit: int,
) -> List[EntityComparison]:
    """
    Trie les entités par delta et retourne le top N.
    """
    limit = int(limit or 10)
    limit = max(1, min(50, limit))

    if sort_by == "energy_kwh":
        key_fn = lambda x: abs(float(x.get("delta_energy_kwh") or 0.0))
    else:
        key_fn = lambda x: abs(float(x.get("delta_cost_ttc") or 0.0))

    return sorted(entity_comparisons, key=key_fn, reverse=True)[:limit]
