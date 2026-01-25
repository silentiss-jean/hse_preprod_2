# -*- coding: utf-8 -*-

"""Home Suivi Élec integration init.

This file wires up the integration and triggers sensor generation.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Suivi Élec from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Existing setup code (not shown here) already initializes storage_manager etc.
    # We only add a post-setup refresh for group totals.
    try:
        from .group_totals import refresh_group_totals

        # Fire-and-forget; sensor platform listens to events and will add entities.
        hass.async_create_task(refresh_group_totals(hass))
        _LOGGER.info("[GROUP-TOTALS] Initial refresh scheduled")
    except Exception as e:
        _LOGGER.exception("[GROUP-TOTALS] Failed to schedule initial refresh: %s", e)

    return True
