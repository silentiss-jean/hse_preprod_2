# -*- coding: utf-8 -*-
"""Validation des champs pour Home Suivi Élec."""

import re
import voluptuous as vol

HOUR_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

def validate_time(value: str) -> str:
    """Vérifie que la valeur est au format HH:MM."""
    if not HOUR_PATTERN.match(value):
        raise vol.Invalid(f"'{value}' n'est pas un format horaire valide (HH:MM)")
    return value
