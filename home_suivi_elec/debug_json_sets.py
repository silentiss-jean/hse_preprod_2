# -*- coding: utf-8 -*-
"""Outils de debug JSON pour Home Suivi Élec."""

import logging
import json
import asyncio
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


async def scan_sets(hass):
    """Vérifie les structures JSON pour détecter des sets non convertibles, sans bloquer la loop."""
    data_dir = Path(hass.config.path("custom_components/home_suivi_elec/data"))
    loop = asyncio.get_running_loop()

    for fichier in data_dir.glob("*.json"):
        try:
            contenu = await loop.run_in_executor(None, _read_json_file, fichier)
            if isinstance(contenu, set):
                _LOGGER.warning("⚠️ Set détecté dans %s", fichier)
        except Exception as e:
            _LOGGER.error("❌ Erreur lecture JSON %s : %s", fichier, e)


def _read_json_file(fichier: Path):
    """Lecture d’un fichier JSON dans un thread dédié (évite le warning Home Assistant)."""
    with open(fichier, "r", encoding="utf-8") as f:
        return json.load(f)