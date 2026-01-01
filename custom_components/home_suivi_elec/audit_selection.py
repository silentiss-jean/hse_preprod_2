#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Home Suivi Elec – Audit de sélection des capteurs.

But :
- Consolider ce qu'on a déduit en debug manuel.
- Générer un rapport texte clair sur :
  - les capteurs détectés (capteurs_power.json)
  - la sélection persistée (.storage/home_suivi_elec_capteurs_selection_v2)
  - les capteurs "filtrés" (présents dans la détection mais absents de la sélection)

Ce script ne modifie rien, il ne fait que lire et afficher.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Set


# Adaptation aux chemins habituels de Home Assistant
# - BACKEND_DIR : dossier du custom_component
# - STORAGE_DIR : dossier .storage de Home Assistant
BACKEND_DIR = Path("custom_components/home_suivi_elec")
DATA_DIR = BACKEND_DIR / "data"
STORAGE_DIR = Path(".storage")

CAPTEURS_POWER_PATH = DATA_DIR / "capteurs_power.json"
SELECTION_STORE_PATH = STORAGE_DIR / "home_suivi_elec_capteurs_selection_v2"


def load_json(path: Path) -> Any:
    if not path.exists():
        print(f"[WARN] Fichier introuvable: {path}")
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_detected_ids(power_data: Any) -> List[str]:
    """Retourne la liste des entity_id détectés dans capteurs_power.json."""
    if not isinstance(power_data, list):
        return []
    ids: List[str] = []
    for row in power_data:
        eid = row.get("entity_id")
        if eid and eid not in ids:
            ids.append(eid)
    return ids


def extract_selection_data(store_data: Any) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extrait la structure de sélection depuis le store HA.

    Schema attendu:
    {
      "version": 2,
      "key": "...",
      "data": {
        "template": [
          {"entity_id": "...", "enabled": true/false, ...},
          ...
        ],
        "autre_integration": [...]
      }
    }
    """
    if not isinstance(store_data, dict):
        return {}
    data = store_data.get("data") or {}
    if not isinstance(data, dict):
        return {}
    return {k: (v or []) for k, v in data.items() if isinstance(v, list)}


def extract_selected_ids(selection: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Retourne la liste des entity_id avec enabled:true."""
    selected: List[str] = []
    for integ, rows in selection.items():
        for row in rows:
            if row.get("enabled") and row.get("entity_id"):
                eid = row["entity_id"]
                if eid not in selected:
                    selected.append(eid)
    return selected


def extract_all_selection_ids(selection: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Retourne la liste de tous les entity_id présents dans la sélection (enabled ou non)."""
    all_ids: List[str] = []
    for integ, rows in selection.items():
        for row in rows:
            eid = row.get("entity_id")
            if eid and eid not in all_ids:
                all_ids.append(eid)
    return all_ids


def build_report() -> str:
    lines: List[str] = []
    lines.append("=== Audit sélection Home Suivi Elec ===")
    lines.append("")

    # 1) Détection brute
    power_data = load_json(CAPTEURS_POWER_PATH)
    detected_ids = extract_detected_ids(power_data)
    lines.append(f"- Fichier détection : {CAPTEURS_POWER_PATH}")
    lines.append(f"  → Capteurs détectés (capteurs_power.json) : {len(detected_ids)}")

    # 2) Sélection persistée (.storage)
    store_data = load_json(SELECTION_STORE_PATH)
    selection = extract_selection_data(store_data)
    all_selection_ids = extract_all_selection_ids(selection)
    selected_ids = extract_selected_ids(selection)

    lines.append(f"- Fichier sélection (Storage) : {SELECTION_STORE_PATH}")
    lines.append(f"  → Intégrations dans la sélection : {list(selection.keys()) or 'aucune'}")
    lines.append(f"  → Lignes de sélection (enabled + disabled) : {len(all_selection_ids)}")
    lines.append(f"  → Capteurs effectivement sélectionnés (enabled:true) : {len(selected_ids)}")
    lines.append("")

    # 3) Invariants simples
    set_detected: Set[str] = set(detected_ids)
    set_all_sel: Set[str] = set(all_selection_ids)
    set_sel_enabled: Set[str] = set(selected_ids)

    # a) Sélection incluse dans la détection ?
    missing_in_power = sorted(eid for eid in set_all_sel if eid not in set_detected)
    if missing_in_power:
        lines.append("⚠ Invariant cassé : certains entity_id sont dans la sélection mais pas dans capteurs_power.json :")
        for eid in missing_in_power:
            lines.append(f"  - {eid}")
    else:
        lines.append("✅ Invariant : tous les entity_id de la sélection existent dans capteurs_power.json.")

    # b) Capteurs détectés mais jamais mentionnés dans la sélection (les fameux 'filtrés')
    missing_in_selection = sorted(eid for eid in set_detected if eid not in set_all_sel)
    lines.append("")
    lines.append(f"- Capteurs détectés mais absents de TOUTE sélection (enabled ou disabled) : {len(missing_in_selection)}")
    if missing_in_selection:
        for eid in missing_in_selection:
            lines.append(f"  - {eid}")
    else:
        lines.append("  → Aucun : tous les capteurs détectés apparaissent au moins une fois dans la sélection.")

    # c) Résumé lisible type UI
    lines.append("")
    lines.append("=== Résumé type UI ===")
    lines.append(f"Total capteurs détectés        : {len(detected_ids)}")
    lines.append(f"Capteurs présents en sélection : {len(all_selection_ids)}")
    lines.append(f"Capteurs sélectionnés (actifs) : {len(selected_ids)}")
    lines.append(f"Capteurs 'filtrés' (détectés mais absents de la sélection) : {len(missing_in_selection)}")

    if missing_in_selection:
        lines.append("")
        lines.append("Interprétation :")
        lines.append(
            "- Le total détecté (par ex. 48) inclut aussi ces capteurs 'filtrés'. "
            "La grille de sélection n'en montre que "
            f"{len(all_selection_ids)}."
        )

    return "\n".join(lines)


def main() -> int:
    print(build_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
